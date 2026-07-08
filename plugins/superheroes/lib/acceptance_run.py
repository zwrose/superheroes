"""Orchestrator for the acceptance harness — the invocation lifecycle (Task 10).

`invoke(deps)` sequences the whole one-shot acceptance run and enforces the
one-record / one-report contract. It is the *mechanical* layer (CONVENTIONS §10.1):
it does the I/O (via injected seams) and sequencing, but delegates EVERY judgment to a
pure decider (`acceptance_reclaim`, `acceptance_verdict`, `acceptance_cleanup`,
`acceptance_retry`). All I/O boundaries are injected so every deterministic behavior is
proven without a live run (DoD); only Task 13's single live run touches a real showrunner.

Lifecycle (fail-CLOSED everywhere — an internal error yields a fail verdict, never a pass):

  0. `root_ancestry()` (issue #298) — the FIRST pre-launch gate, BEFORE reclaim so a refusal
     takes no lease and stamps no fixture. Refuses when the `--root` checkout's HEAD is not an
     ancestor of origin/<default-branch> (a release-branch checkout would false-park on UFR-7
     mid-run); writes a refusal record, fails non-zero, and names the offending sha. Absent seam
     (injected bare deps) skips the check. `--allow-unmerged-root` bypasses it deliberately.
  1. `reclaim_probe()` → `acceptance_reclaim.decide`. On `refuse`, write this invocation's
     fail record and report naming the in-flight / unconfirmable prior run, without releasing
     the other holder's lease. On `reclaim`,
     run the record-less discovery cleanup and (when the dead run left no record) write its
     orphan failed record before proceeding.
  2. `materialize()` the stamped throwaway fixture work-item.
  3. `preflight_ok(work_item)` — a failed preflight refuses, naming the drifted/missing
     prerequisite (UFR-7).
  4. `launcher(stamped, budget_consumed, attempt)` — attempt 1 with a zero budget; the
     returned `spend` / `elapsed_sec` are the SOLE source of the FR-5 record fields. A
     `killed` outcome fails naming the tripped ceiling.
  5. Assemble `facts` from `run_outcome` + `gh_reader` + `expected_phases`; call
     `acceptance_verdict.decide`.
  6. On a fail verdict, consult `acceptance_retry.classify`; a confidently-environmental
     first-attempt failure gets exactly one retry — the first attempt is cleaned first, a
     fresh stamp is materialized, and the relaunch is fed attempt-1's consumed budget
     (`budget_consumed`) so it enforces the invocation's REMAINING budget, never a fresh
     ceiling. Both attempts fold into the single record (`retried: True`, `attempts: [..]`).
  7. `acceptance_cleanup.plan(discover_artifacts(stamp), run_stamp=stamp)` → `reap` — teardown
     runs on EVERY safe exit path (ready, parked, confirmed killed, or internal error). An
     unconfirmed process kill skips artifact cleanup and records the surviving risk instead.
  8. `write_record` — exactly one record per invocation, built from the verdict + the
     launcher's `spend` / `elapsed_sec` (aggregated across attempts when retried).
  9. `release_lease` — ONLY after the record is durably written. If `write_record` raised,
     the lease is held (so the next invocation's UFR-8 backstop writes the missing record).
 10. `render_report` — the single plain-language verdict report.

Teardown (steps 7) always runs, even when an internal seam raised: the except path routes
through the same cleanup → fail-verdict-naming-the-error → record write → report.
"""
import os
import json
import signal

import acceptance_reclaim
import acceptance_verdict
import acceptance_cleanup
import acceptance_retry
import acceptance_result
import acceptance_launch


def nesting_refusal(env):
    """Pure UFR-5 helper: refuse when invoked from inside a showrunner/acceptance run.

    The launcher sets `SUPERHEROES_ACCEPTANCE_CONTEXT` on the child's environment; a nested
    invocation reads it and refuses before doing anything. Shared by the skill and its test
    so the refusal is unit-tested without a live run.
    """
    if not isinstance(env, dict):
        env = {}
    if env.get("SUPERHEROES_ACCEPTANCE_CONTEXT"):
        return {
            "refuse": True,
            "reason": "refusing to nest: already inside a showrunner/acceptance run",
        }
    return {"refuse": False, "reason": "top-level invocation; safe to proceed"}


class _SignalTermination(Exception):
    """Raised in the main thread by the harness's SIGTERM/SIGINT handler so an in-flight run
    unwinds through `invoke`'s teardown/record path instead of the process dying with the
    child group orphaned (issue #245).

    Before #245 no signal handler existed anywhere in the harness stack: a SIGTERM to the
    harness process (observed live during the 0.10.0 qualification) exited WITHOUT killing the
    child group or running teardown. Carries the live child handle captured AT signal-delivery
    time (while the launcher's watch loop is still on the stack and the live-child slot is
    populated), so the except path can hard-kill the group even after the launcher has unwound.
    """

    def __init__(self, signum, child=None):
        super().__init__("terminated by signal %s" % signum)
        self.signum = signum
        self.child = child


def _termination_handler(signum, frame):
    """SIGTERM/SIGINT handler: capture the live child, DISARM further termination signals so a
    second signal can't re-enter teardown mid-kill (kill-unconfirmed double-report guard), then
    raise `_SignalTermination` so the main thread unwinds through `invoke`'s except path — which
    runs the EXISTING hard-kill + teardown + record machinery. Deliberately minimal: the actual
    reap happens on the main stack in the except path, not inside this async handler."""
    child = acceptance_launch.current_live_child()
    # Disarm: while teardown runs, ignore further SIGTERM/SIGINT so the bounded kill completes
    # and records exactly once. Bounded work (escalation ~seconds, reaps have subprocess
    # timeouts) makes ignoring the operator's second signal an acceptable tradeoff for a clean,
    # single teardown/record over a second ungraceful death.
    try:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass
    raise _SignalTermination(signum, child)


def _install_termination_handlers():
    """Install the SIGTERM/SIGINT handlers routing through `invoke`'s teardown path; return a
    zero-arg `restore()` that puts the previous handlers back. No-op (returns a no-op restore)
    when not on the main thread, where `signal.signal` is unavailable — the launcher's finite
    bg-wait ceiling (PR #244) remains the backstop there."""
    try:
        prev_term = signal.signal(signal.SIGTERM, _termination_handler)
        prev_int = signal.signal(signal.SIGINT, _termination_handler)
    except (ValueError, OSError):
        return lambda: None

    def restore():
        try:
            signal.signal(signal.SIGTERM, prev_term)
            signal.signal(signal.SIGINT, prev_int)
        except (ValueError, OSError):
            pass

    return restore


def _terminate_by_signal(deps, child, stamp, attempts, dead_run_teardown, prov,
                         orphan_record_path, prior_unsafe=False, lease_owned=True):
    """Route a caught `_SignalTermination` through the EXISTING kill+teardown+record path
    (issue #245): hard-kill the live child group FIRST (reusing `_hard_kill_group`), then apply
    the same kill-unconfirmed quarantine semantics the ceiling-kill path uses today — an
    unconfirmed group kill records `kill-unconfirmed`, SKIPS artifact cleanup, quarantines the
    lease, and holds it; a confirmed-dead group tears down normally and releases the lease.

    `prior_unsafe` (PR #246 review, premortem blocker): when the just-returned launcher already
    reported an UNCONFIRMED kill, the live-child slot was cleared as `run()` unwound, so the
    handler captured `child=None` and this call cannot re-confirm the group dead. Honoring the
    prior unsafe verdict keeps the quarantine (skip cleanup, hold+quarantine the lease) — a
    signal must never DOWNGRADE an unconfirmed kill into full deletion + lease release.

    The single record's reason is the honest "terminated by signal". No parallel path is built:
    the reap uses `acceptance_launch._hard_kill_group`, cleanup uses `_unsafe_kill_teardown` /
    `_teardown`, and the record/lease go through `_finalize` — exactly as steps 7–9 do."""
    confirmed = True
    if child is not None:
        confirmed = acceptance_launch._hard_kill_group(child)
    unsafe_kill = (not confirmed) or prior_unsafe
    reason = "terminated by signal"
    if unsafe_kill:
        reason += " but the process group was not confirmed dead; cleanup skipped"

    try:
        if unsafe_kill:
            teardown = _unsafe_kill_teardown(dead_run_teardown, stamp)
        else:
            teardown = _merge_teardown(dead_run_teardown, _teardown(deps, stamp))
    except Exception as td_exc:
        teardown = {"cleaned_up": [], "left_behind": [],
                    "note": "teardown also failed: %s" % td_exc}

    # #298 review r1: never quarantine a lease this invocation does not own (pre-lease window).
    if unsafe_kill and lease_owned and callable(deps.get("quarantine_lease")):
        try:
            deps["quarantine_lease"](stamp)
        except Exception:
            pass

    record_path = None
    try:
        record_path = _finalize(
            deps, "fail", reason, None, attempts, len(attempts) > 1, teardown,
            run_stamp=stamp, release_lease=(not unsafe_kill) and lease_owned,
            spine_provenance=prov)
    except Exception:
        record_path = None
    return {
        "verdict": "fail",
        "report": _report("fail", reason, record_path, teardown,
                          orphan_record_path=orphan_record_path, spine_provenance=prov),
        "record_path": record_path,
    }


def _spine_provenance(deps):
    """Resolve the #235 spine-under-test provenance seam (lib path + bundle SHA-256 +
    version), or None when no `--spine-lib` override was given / the seam is absent.
    Never raises — provenance is an honesty annotation, never a run blocker."""
    fn = deps.get("spine_provenance") if isinstance(deps, dict) else None
    if not callable(fn):
        return None
    try:
        return fn()
    except Exception:
        return None


def _report(verdict, reason, record_path, teardown, spend_partial=False,
            unwritten_record_note=None, orphan_record_path=None, spine_provenance=None):
    """Render the single plain-language verdict report via the tested FR-6 renderer
    (`acceptance_result.render_report`) so the Markdown/partial-spend output owners see
    is the same one the module's own tests pin — not a second, drifted format."""
    result = {
        "verdict": verdict,
        "reason": reason,
        "record_path": record_path if record_path else
        (unwritten_record_note or "NOT WRITTEN (lease held)"),
        "cleaned_up": (teardown or {}).get("cleaned_up") or [],
        "left_behind": (teardown or {}).get("left_behind") or [],
        "spend_partial": bool(spend_partial),
    }
    if orphan_record_path:
        result["orphan_record_path"] = orphan_record_path
    if spine_provenance:
        result["spine_provenance"] = spine_provenance
    return acceptance_result.render_report(result)


def _run_one_attempt(deps, stamped, budget_consumed, attempt):
    """Launch one attempt and assemble its verdict facts. Returns (launch, outcome, verdict)."""
    launch = deps["launcher"](stamped, budget_consumed=budget_consumed, attempt=attempt)

    if launch.get("outcome") in ("killed", "kill-unconfirmed"):
        unsafe = launch.get("teardown_safe") is False or launch.get("outcome") == "kill-unconfirmed"
        reason = "ceiling breached (%s) — run hard-killed" % launch.get("ceiling")
        if unsafe:
            reason += " but the process group was not confirmed dead; cleanup skipped"
        verdict = {
            "verdict": "fail",
            "reason": reason,
        }
        return launch, {"failure_kind": "ceiling-%s" % launch.get("ceiling"),
                        "failure_unreadable": False, "phases": []}, verdict

    outcome = deps["run_outcome"](launch.get("terminal_location"))
    gh = deps["gh_reader"]()
    outcome = dict(outcome or {})
    structured_failure_kind = gh.get("failure_kind")
    outcome["failure_kind"] = structured_failure_kind
    outcome["failure_unreadable"] = bool((gh.get("unreadable") or []) and not structured_failure_kind)
    facts = {
        "terminal": outcome.get("terminal"),
        "phases_traversed": outcome.get("phases") or [],
        "expected_phases": deps["expected_phases"](),
        "readout_exists": bool(outcome.get("readout_pr_link") is not None),
        "readout_pr_link": outcome.get("readout_pr_link") or "",
        "readout_claimed_checks_green": outcome.get("readout_claimed_checks_green"),
        "readout_claimed_pr": outcome.get("readout_claimed_pr"),
        "pr_exists": gh.get("pr_exists"),
        "pr_ready_for_review": gh.get("pr_ready_for_review"),
        "checks_green": gh.get("checks_green"),
        "checks_pending": gh.get("checks_pending"),
        "live_checks_green": gh.get("live_checks_green"),
        "live_pr": gh.get("live_pr"),
        "unreadable": gh.get("unreadable") or [],
    }
    # #299: assert the run's ACTUAL dispatch census matches the readout's EXPECTED rows (engines AND
    # models), failing loud on a silent fall-open under an external calibration or an off-policy model
    # (never Fable). Absent dep (custom test deps) / all-Claude calibration -> a trivial pass, so this
    # is additive and never flips an existing verdict on its own.
    census_dep = deps.get("dispatch_census") if isinstance(deps, dict) else None
    facts["dispatch_census"] = census_dep() if callable(census_dep) else {"ok": True, "failures": []}
    verdict = acceptance_verdict.decide(facts)
    return launch, outcome, verdict


def _attempt_record(stamp, launch, verdict):
    """One entry in the record's `attempts` list."""
    return {
        "stamp": stamp,
        "verdict": verdict.get("verdict"),
        "reason": verdict.get("reason"),
        "spend": launch.get("spend"),
        "elapsed_sec": launch.get("elapsed_sec"),
    }


def invoke(deps):
    """Drive the full acceptance-run lifecycle. Returns `{verdict, report, record_path}`.

    Fail-CLOSED: any internal error still routes through teardown and yields a fail verdict
    naming the error — never a pass. See the module docstring for the ordered lifecycle.
    """
    teardown = None
    stamp = None
    attempts = []
    orphan_record_path = None
    # Resolve once up front so it is available on every exit path, including the except
    # branch below (the record itself picks it up independently via `_record_payload`).
    prov = _spine_provenance(deps)
    # Signal-path state (issue #245 review). `unsafe`: the latest launch reported an
    # UNCONFIRMED kill — a signal arriving after the launcher returned (live-child slot already
    # cleared → handler captures child=None) must NOT downgrade that quarantine into deletion.
    # `finalized`/`result`: this invocation already wrote its terminal record + handled the
    # lease — a signal in the return-construction window must not re-teardown/re-write/re-release.
    sig_state = {"unsafe": False, "finalized": False, "result": None}
    # #298 review r1 (premortem, fail-direction): does THIS invocation own the store lease yet?
    # False until the reclaim decision resolves to proceed (the exclusive-create acquire lives in
    # reclaim_probe). A signal or internal error in the PRE-LEASE window — materially wider now
    # that step 0's root-ancestry probe does network git I/O — must NEVER release (or quarantine)
    # the lease: with run_stamp still None, release_lease(None) is the legacy UNCONDITIONAL
    # remove and would delete a CONCURRENT run's lease, re-opening the two-runs hazard the lease
    # exists to prevent. Both except paths below gate on this flag.
    lease_owned = False

    def _mark_finalized():
        # Fired by `_finalize` the instant the record is durably written, BEFORE the lease
        # release — so a signal during release/report can never re-finalize (double record /
        # double lease release).
        sig_state["finalized"] = True

    def _final(result):
        # Stash the true result (and belt-and-braces mark finalized) so a signal landing in the
        # return-construction window echoes it instead of re-running teardown/record.
        sig_state["finalized"] = True
        sig_state["result"] = result
        return result

    def _prelaunch_refusal(reason, unwritten_note):
        # Shared shape for a pre-launch refusal that writes a refusal record (never the terminal
        # record) and takes/holds NO new lease — the root-lineage gate (#298, step 0) and the
        # in-flight-run refusal (step 1). Marks the invocation finalized so a signal in the
        # return window echoes this result instead of re-entering teardown (no lease/stamp
        # exists to tear down). A missing writer leaves record_path None and the report shows the
        # unwritten note.
        record_path = None
        writer = deps.get("write_refusal_record") if isinstance(deps, dict) else None
        if callable(writer):
            try:
                record_path = _write_record_only(
                    deps, "fail", reason, None, [], False,
                    {"cleaned_up": [], "left_behind": []}, spend_partial=True,
                    writer=writer, spine_provenance=prov)
            except Exception:
                record_path = None
        return _final({
            "verdict": "fail",
            "report": _report(
                "fail", reason, record_path, None, spend_partial=True,
                unwritten_record_note=unwritten_note, spine_provenance=prov),
            "record_path": record_path,
        })

    try:
        # 0. Root-lineage refusal (issue #298) — the FIRST pre-launch gate, BEFORE reclaim so
        # a refusal takes NO lease and stamps NO fixture (the trap: a refusing run that held the
        # lease would break the next run). When the `--root` checkout's HEAD is not an ancestor
        # of origin/<default-branch> it carries commits not on the default branch (e.g. a
        # release-please version bump) and UFR-7's trailer gate would false-park mid-run. The
        # seam does all git I/O (injected, so tests drive it without a fetch) and self-emits the
        # offline-degrade warning; a fetch failure returns ok=True (never a silent pass here).
        # Absent seam (fake deps / an injected bare builder) -> skip, unchanged behavior.
        ancestry_probe = deps.get("root_ancestry") if isinstance(deps, dict) else None
        if callable(ancestry_probe):
            lineage = ancestry_probe() or {}
            if not lineage.get("ok"):
                reason = lineage.get("reason") or (
                    "--root checkout is not an ancestor of the remote default branch "
                    "(HEAD %s); root the run at merged main or pass --allow-unmerged-root"
                    % lineage.get("head_sha", "unknown"))
                return _prelaunch_refusal(
                    reason, "NOT WRITTEN (refused pre-launch; no lease taken)")

        # 1. Reclaim / refuse a prior in-flight run.
        recorded_state, liveness = deps["reclaim_probe"]()
        reclaim = acceptance_reclaim.decide(recorded_state, liveness)
        if reclaim["action"] == "refuse":
            # The refusal record is written and the OTHER holder's lease is intentionally held;
            # _prelaunch_refusal marks finalized so a signal after this can't re-teardown it.
            reason = "a prior acceptance run is in flight (%s); refusing to start another" % liveness
            return _prelaunch_refusal(
                reason, "NOT WRITTEN (prior run lease still held)")
        # Non-refuse: the reclaim probe's exclusive-create acquire succeeded — from here on the
        # lease is OURS, and the signal/error finalizers may (and should) release it.
        lease_owned = True
        # UFR-8: sweep any leftover accepted-stamp artifacts before this invocation launches.
        # This covers both a confirmed-dead lease holder and a lease-free checkout whose prior
        # completed invocation wrote a record but failed to reap everything.
        dead_run_teardown = _discovery_teardown(deps)
        if reclaim["action"] == "reclaim" and reclaim.get("write_orphan_record"):
            # The dead prior run left no record — write its orphan failed record before
            # proceeding, honestly reflecting what the discovery teardown above reaped.
            orphan_record_path = _write_record_only(
                deps, "fail", "orphan record for a reclaimed dead prior run",
                None, [{"stamp": recorded_state.get("stamp"), "verdict": "fail"}],
                False, dead_run_teardown, spend_partial=True,
                run_stamp=recorded_state.get("stamp"),
                writer=deps.get("write_orphan_record"), spine_provenance=prov)

        # 2. Materialize the stamped throwaway fixture work-item.
        stamped = deps["materialize"]()
        stamp = stamped.get("stamp")

        # 3. Preflight the fixture — a failed preflight refuses, naming the drifted piece.
        pf = deps["preflight_ok"](stamped.get("work_item"))
        if not pf.get("ok"):
            reason = "preflight refused the fixture: %s" % pf.get("reason", "prerequisite not met")
            teardown = _merge_teardown(dead_run_teardown, _teardown(deps, stamp))
            record_path = _finalize(deps, "fail", reason, None, [], False, teardown,
                                    run_stamp=stamp, spine_provenance=prov,
                                    on_recorded=_mark_finalized)
            return _final({
                "verdict": "fail",
                "report": _report("fail", reason, record_path, teardown,
                                  orphan_record_path=orphan_record_path,
                                  spine_provenance=prov),
                "record_path": record_path,
            })

        # 4-6. Launch attempt 1, judge, and retry once on a confidently-environmental failure.
        budget_consumed = {"elapsed_sec": 0.0, "spend": 0.0}
        attempt = 1
        launch, outcome, verdict = _run_one_attempt(deps, stamped, budget_consumed, attempt)
        sig_state["unsafe"] = launch.get("teardown_safe") is False
        attempts.append(_attempt_record(stamp, launch, verdict))

        pre_retry_cleanup_failed = False
        if verdict["verdict"] == "fail":
            retry = acceptance_retry.classify({
                "kind": outcome.get("failure_kind"),
                "unreadable": outcome.get("failure_unreadable"),
                "attempt": attempt,
            })
            if retry.get("retry"):
                # Clean the first attempt before relaunching (FR-9/UFR-3: when the
                # pre-retry cleanup leaves artifacts behind, no retry launches — the
                # invocation ends on the cleanup-failure path instead of spinning up a
                # second stamped run alongside the first attempt's surviving artifacts).
                pre_retry_teardown = _teardown(deps, stamp)
                if pre_retry_teardown.get("left_behind"):
                    pre_retry_cleanup_failed = True
                    teardown = _merge_teardown(dead_run_teardown, pre_retry_teardown)
                    verdict = {
                        "verdict": "fail",
                        "reason": (
                            "pre-retry cleanup left artifacts behind (%s); aborting the "
                            "retry instead of launching a second attempt alongside them"
                            % ", ".join(str(a) for a in pre_retry_teardown["left_behind"])
                        ),
                    }
                else:
                    budget_consumed = {
                        "elapsed_sec": launch.get("elapsed_sec") or 0.0,
                        "spend": launch.get("spend") or 0.0,
                    }
                    stamped = deps["materialize"]()
                    stamp = stamped.get("stamp")
                    attempt = 2
                    launch, outcome, verdict = _run_one_attempt(
                        deps, stamped, budget_consumed, attempt)
                    sig_state["unsafe"] = launch.get("teardown_safe") is False
                    attempts.append(_attempt_record(stamp, launch, verdict))

        # 7. Teardown — runs on every exit path (ready, parked, killed). When the pre-retry
        # cleanup already failed, that result IS the final teardown — the aborted stamp was
        # already torn down (as far as possible) and stamp is left in place only for record-
        # keeping, so we don't attempt a second reap of the same (already-attempted) artifacts.
        if not pre_retry_cleanup_failed:
            if launch.get("teardown_safe") is False:
                teardown = _unsafe_kill_teardown(dead_run_teardown, stamp)
            else:
                teardown = _merge_teardown(dead_run_teardown, _teardown(deps, stamp))

        # 8-9. Write the single record (both attempts), then release the lease. The
        # top-level spend/elapsed_sec are the INVOCATION total (module docstring line 32:
        # "aggregated across attempts when retried") — summed across every attempt's
        # `_attempt_record`, not just the final attempt's launch figures, so a retried
        # invocation's FR-5 cost fields reflect the true combined cost/time rather than
        # silently dropping the failed first attempt's spend/elapsed_sec.
        retried = len(attempts) > 1
        total_spend = sum(a.get("spend") or 0.0 for a in attempts)
        total_elapsed = sum(a.get("elapsed_sec") or 0.0 for a in attempts)
        unsafe_kill = launch.get("teardown_safe") is False
        if unsafe_kill and callable(deps.get("quarantine_lease")):
            deps["quarantine_lease"](stamp)
        record_path = _finalize(
            deps, verdict["verdict"], verdict["reason"],
            total_spend, attempts, retried, teardown,
            spend_partial=launch.get("spend_partial"),
            elapsed_sec=total_elapsed,
            pr_link=(outcome.get("readout_pr_link") if isinstance(outcome, dict) else "") or "",
            phases=(outcome.get("phases") if isinstance(outcome, dict) else []) or [],
            run_stamp=stamp,
            release_lease=not unsafe_kill,
            spine_provenance=prov,
            on_recorded=_mark_finalized,
        )

        # 10. Render the single verdict report.
        return _final({
            "verdict": verdict["verdict"],
            "report": _report(verdict["verdict"], verdict["reason"], record_path, teardown,
                              spend_partial=launch.get("spend_partial"),
                              orphan_record_path=orphan_record_path,
                              spine_provenance=prov),
            "record_path": record_path,
        })

    except _SignalTermination as sig_exc:
        # SIGTERM/SIGINT arrived (issue #245). Two guards, both from the PR #246 review:
        # (a) if the invocation already finalized (record written, lease handled), a signal in
        #     the return-construction window must NOT re-teardown / rewrite the record / re-release
        #     the lease — echo the already-computed result.
        if sig_state["finalized"]:
            return sig_state["result"] or {
                "verdict": "fail",
                "report": "run terminated by signal after its record was already written",
                "record_path": locals().get("record_path")}
        # (b) hard-kill the live child group captured by the handler, then route through the SAME
        #     kill+teardown+record machinery. `prior_unsafe` carries a just-returned UNCONFIRMED
        #     kill so a signal in the post-launch window can never DOWNGRADE that quarantine into
        #     full deletion + lease release (premortem blocker): treat it as unsafe even though
        #     the handler captured child=None.
        prior_unsafe = bool(sig_state["unsafe"]) or (
            isinstance(locals().get("launch"), dict)
            and locals()["launch"].get("teardown_safe") is False)
        return _terminate_by_signal(
            deps, sig_exc.child, stamp, attempts,
            locals().get("dead_run_teardown"), prov, orphan_record_path,
            prior_unsafe=prior_unsafe, lease_owned=lease_owned)

    except Exception as exc:
        # Fail-CLOSED: any internal error still teardowns and yields a fail naming the error.
        # If the last launch's process-group kill was unconfirmed, normal cleanup stays
        # disabled even here; the child may still be touching stamped artifacts.
        reason = "internal harness error: %s" % exc
        unsafe_kill = bool(locals().get("unsafe_kill")) or (
            isinstance(locals().get("launch"), dict)
            and locals()["launch"].get("teardown_safe") is False
        )
        try:
            if unsafe_kill:
                teardown = _unsafe_kill_teardown(locals().get("dead_run_teardown"), stamp)
            else:
                teardown = _merge_teardown(locals().get("dead_run_teardown"),
                                           _teardown(deps, stamp))
        except Exception as td_exc:
            teardown = {"cleaned_up": [], "left_behind": [],
                        "note": "teardown also failed: %s" % td_exc}
        record_path = None
        try:
            record_path = _finalize(deps, "fail", reason, None, attempts,
                                    len(attempts) > 1, teardown, run_stamp=stamp,
                                    release_lease=(not unsafe_kill) and lease_owned,
                                    spine_provenance=prov)
        except Exception:
            record_path = None
        return {
            "verdict": "fail",
            "report": _report("fail", reason, record_path, teardown,
                              orphan_record_path=locals().get("orphan_record_path"),
                              spine_provenance=prov),
            "record_path": record_path,
        }


def _teardown(deps, stamp):
    """Plan + execute the stamp-scoped cleanup. Returns the reap result dict."""
    if stamp is None:
        return {"cleaned_up": [], "left_behind": []}
    planned = acceptance_cleanup.plan(deps["discover_artifacts"](stamp), run_stamp=stamp)
    return deps["reap"](planned)


def _merge_teardown(*parts):
    cleaned, left = [], []
    for part in parts:
        if not isinstance(part, dict):
            continue
        cleaned.extend(part.get("cleaned_up") or [])
        left.extend(part.get("left_behind") or [])
    return {"cleaned_up": cleaned, "left_behind": left}


def _unsafe_kill_teardown(dead_run_teardown, stamp):
    return _merge_teardown(dead_run_teardown, {
        "cleaned_up": [],
        "left_behind": [{
            "kind": "process-group",
            "name": stamp,
            "reason": "kill not confirmed; cleanup skipped",
        }],
    })


def _discovery_teardown(deps):
    """UFR-8: the record-less discovery cleanup for a reclaimed DEAD prior run.

    Distinct from `_teardown` (which no-ops on `stamp is None`, since that guard means
    "this invocation never got as far as materializing anything yet"): here `stamp=None`
    is deliberately passed to `acceptance_cleanup.plan` as `run_stamp`, putting it in
    discovery mode — ANY discovered name that parses to a valid full stamp is reaped,
    not just this (not-yet-materialized) invocation's own. `discover_artifacts` itself
    takes no meaningful stamp argument in this mode; `None` mirrors the other record-less
    discovery call sites in this module.
    """
    planned = acceptance_cleanup.plan(deps["discover_artifacts"](None), run_stamp=None)
    if not (planned.get("reap") or planned.get("leave_behind")):
        return {"cleaned_up": [], "left_behind": []}
    return deps["reap"](planned)


def _record_payload(deps, verdict, reason, spend, attempts, retried, teardown,
                    spend_partial=False, elapsed_sec=0.0, pr_link="", phases=None,
                    run_stamp=None, spine_provenance=None):
    record = {
        "verdict": verdict,
        "reason": reason,
        "pr_link": pr_link,
        "phases": phases or [],
        "spend": spend,
        "spend_partial": bool(spend_partial),
        "elapsed_sec": elapsed_sec if elapsed_sec is not None else 0.0,
        "launched_at": deps["clock_now"](),
        "terminated_at": deps["clock_now"](),
        "retried": bool(retried),
        "attempts": attempts,
        "cleaned_up": (teardown or {}).get("cleaned_up") or [],
        "left_behind": (teardown or {}).get("left_behind") or [],
    }
    if run_stamp:
        record["run_stamp"] = run_stamp
    # #235: stamp the record with which spine was under test (optional field — present
    # only on a `--spine-lib` pre-release-gate run; omitted on the default installed-plugin
    # path). Kept OPTIONAL rather than a REQUIRED_KEY so the default path's record shape is
    # unchanged and every other write path (refusal/orphan) need not synthesize a value.
    # `spine_provenance` is resolved ONCE by `invoke` (before launch) and threaded in, so the
    # record's bundle hash is the same single read the report shows — never a second re-hash
    # of the (possibly since-mutated) bundle at finalize time, which could otherwise diverge
    # from the report's hash on a long run or null out after the bundle moved (premortem #235).
    if spine_provenance:
        record["spine_provenance"] = spine_provenance
    return record


def _finalize(deps, verdict, reason, spend, attempts, retried, teardown,
              spend_partial=False, elapsed_sec=0.0, pr_link="", phases=None,
              run_stamp=None, release_lease=True, spine_provenance=None, on_recorded=None):
    """Write the single record, then release the lease ONLY after a durable write.

    If `write_record` raises, the lease is NOT released (held so the UFR-8 backstop stays
    armed) and the failure propagates to the caller as a fail. Returns the record path.

    `on_recorded` (PR #246 review) fires RIGHT AFTER the record is durably written and BEFORE
    the lease release, so `invoke` can mark itself finalized inside that gap — closing the
    window where a signal arriving during `release_lease()` (or the subsequent report render)
    would otherwise re-enter teardown and double-write the record / double-release the lease.
    """
    record = _record_payload(deps, verdict, reason, spend, attempts, retried, teardown,
                             spend_partial=spend_partial, elapsed_sec=elapsed_sec,
                             pr_link=pr_link, phases=phases, run_stamp=run_stamp,
                             spine_provenance=spine_provenance)
    record_path = deps["write_record"](record)
    if callable(on_recorded):
        on_recorded()
    # Only after the record is durably written do we release the lease.
    if release_lease:
        deps["release_lease"]()
    return record_path


def _write_record_only(deps, verdict, reason, spend, attempts, retried, teardown,
                       spend_partial=False, elapsed_sec=0.0, pr_link="", phases=None,
                       run_stamp=None, writer=None, spine_provenance=None):
    return (writer or deps["write_record"])(_record_payload(
        deps, verdict, reason, spend, attempts, retried, teardown,
        spend_partial=spend_partial, elapsed_sec=elapsed_sec, pr_link=pr_link,
        phases=phases, run_stamp=run_stamp, spine_provenance=spine_provenance))


def _cli(argv, env, stdout, stderr, deps_builder=None):
    """The DoD live-run entrypoint the acceptance SKILL.md documents (Task 13).

    `python3 acceptance_run.py --fixture <fixture> --root <root>` is the command the
    front-door skill runs to drive a live acceptance run. It refuses to nest (UFR-5),
    then builds the REAL `deps` dict via `acceptance_deps.build` (control-plane lease +
    git/gh discovery + the real out-of-process launcher) and calls `invoke(deps)` for a
    genuine live run — never a silent exit-0 no-op and never a stub that declines to run.

    `deps_builder(fixture, root) -> deps` defaults to `acceptance_deps.build`; tests
    inject a fake builder so this CLI wiring is exercised without spawning a live
    showrunner (consistent with the rest of the harness's DoD: every deterministic
    behavior proven without a live run).

    Returns the process exit code: 0 on a `pass` verdict, 1 on `fail`, 3 on a nesting
    refusal, 2/argparse's code on bad args. All I/O (env, streams, deps) is injected.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="acceptance_run.py",
        description="Standalone showrunner acceptance harness — live run entrypoint.",
    )
    parser.add_argument("--fixture", required=True,
                        help="Path to the committed throwaway acceptance fixture.")
    parser.add_argument("--root", required=True,
                        help="Repo root the live showrunner runs against.")
    parser.add_argument("--ceilings-config", default=None,
                        help="Optional JSON file with acceptance ceilings: elapsed_sec and/or spend.")
    parser.add_argument("--ceiling-elapsed-sec", type=float, default=None,
                        help="Override the elapsed-time ceiling in seconds.")
    parser.add_argument("--ceiling-spend", type=float, default=None,
                        help="Override the measured output-token spend ceiling.")
    parser.add_argument("--spine-lib", default=None,
                        help="Pre-release gate (#235): pin the spine UNDER TEST to this lib "
                             "dir (must contain showrunner.bundle.js + showrunner.js) instead "
                             "of the installed plugin, so merged-but-unreleased spine changes "
                             "are validated before a release is cut. Unset = installed plugin.")
    parser.add_argument("--child-model", default=None,
                        help="Pin the child driver session's model (default: sonnet). The "
                             "child does only wrapper work; pinning it stops the driver from "
                             "inheriting the invoking user's CLI default (model-governance). "
                             "Recorded in the result-record provenance.")
    parser.add_argument("--allow-unmerged-root", action="store_true",
                        help="Escape hatch (issue #298): proceed even when the --root checkout's "
                             "HEAD is not an ancestor of origin/<default-branch>. Default refuses "
                             "pre-launch (a release-branch checkout false-parks on UFR-7 mid-run). "
                             "Use only for a deliberate pre-merge branch-spine validation.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse already printed usage to stderr; propagate its non-zero code.
        return exc.code if isinstance(exc.code, int) else 2

    # UFR-5: refuse before touching anything if we are already inside a run.
    # `nesting_refusal` expects a plain dict; `os.environ` is an `os._Environ`, so copy it.
    refusal = nesting_refusal(dict(env))
    if refusal["refuse"]:
        print(refusal["reason"], file=stderr)
        return 3

    try:
        ceilings = _ceilings_from_args(args, parser)
    except SystemExit as exc:
        return int(exc.code or 2)

    if deps_builder is None:
        import acceptance_deps
        # Only pass optional kwargs when set, so a spy builder with the legacy
        # (fixture, root) signature keeps working when neither override is given.
        build_kwargs = {}
        if ceilings is not None:
            build_kwargs["ceilings"] = ceilings
        if args.spine_lib is not None:
            build_kwargs["spine_lib"] = args.spine_lib
        if args.child_model is not None:
            build_kwargs["child_model"] = args.child_model
        # Only thread the escape hatch when set, so a legacy 2-arg spy builder still works
        # when no overrides are given (mirrors the spine_lib/child_model pattern above).
        if args.allow_unmerged_root:
            build_kwargs["allow_unmerged_root"] = True
        deps = acceptance_deps.build(args.fixture, args.root, **build_kwargs)
    else:
        deps = deps_builder(args.fixture, args.root)

    # Install SIGTERM/SIGINT handlers so an ungraceful harness termination routes through
    # invoke's kill+teardown+record path instead of exiting with the child group orphaned
    # (issue #245). Restored unconditionally so the process's signal disposition is not left
    # mutated (e.g. if invoke returns normally without a signal).
    restore = _install_termination_handlers()
    try:
        result = invoke(deps)
    except _SignalTermination:
        # A signal that lands while invoke is already unwinding a DIFFERENT exception (its
        # fail-closed teardown path) escapes invoke's own excepts — a raised exception is not
        # caught by a sibling except of the same try. Catch it here so the CLI exits cleanly
        # (fail) instead of dying with a traceback; the child, if any, stays bounded by the
        # bg-wait ceiling + the lease-pgid reclaim backstop (PR #246 review).
        result = {"verdict": "fail",
                  "report": "acceptance run terminated by signal during teardown",
                  "record_path": None}
    finally:
        restore()
    print(result["report"], file=stdout)
    return 0 if result["verdict"] == "pass" else 1


def _ceilings_from_args(args, parser):
    raw = {}
    if args.ceilings_config:
        try:
            with open(args.ceilings_config, encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError) as exc:
            parser.error("--ceilings-config is not readable JSON: %s" % exc)
        if not isinstance(loaded, dict):
            parser.error("--ceilings-config must contain a JSON object")
        raw.update(loaded)
    if args.ceiling_elapsed_sec is not None:
        raw["elapsed_sec"] = args.ceiling_elapsed_sec
    if args.ceiling_spend is not None:
        raw["spend"] = args.ceiling_spend
    if not raw:
        return None
    import acceptance_ceiling
    return acceptance_ceiling.normalize_ceilings(raw)


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(_cli(_sys.argv[1:], os.environ, _sys.stdout, _sys.stderr))
