"""Orchestrator for the acceptance harness — the invocation lifecycle (Task 10).

`invoke(deps)` sequences the whole one-shot acceptance run and enforces the
one-record / one-report contract. It is the *mechanical* layer (CONVENTIONS §10.1):
it does the I/O (via injected seams) and sequencing, but delegates EVERY judgment to a
pure decider (`acceptance_reclaim`, `acceptance_verdict`, `acceptance_cleanup`,
`acceptance_retry`). All I/O boundaries are injected so every deterministic behavior is
proven without a live run (DoD); only Task 13's single live run touches a real showrunner.

Lifecycle (fail-CLOSED everywhere — an internal error yields a fail verdict, never a pass):

  1. `reclaim_probe()` → `acceptance_reclaim.decide`. On `refuse`, return a fail verdict +
     report naming the in-flight / unconfirmable prior run, creating NOTHING. On `reclaim`,
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
     runs on EVERY exit path (ready, parked, or internal error).
  8. `write_record` — exactly one record per invocation, built from the verdict + the
     launcher's `spend` / `elapsed_sec` (aggregated across attempts when retried).
  9. `release_lease` — ONLY after the record is durably written. If `write_record` raised,
     the lease is held (so the next invocation's UFR-8 backstop writes the missing record).
 10. `render_report` — the single plain-language verdict report.

Teardown (steps 7) always runs, even when an internal seam raised: the except path routes
through the same cleanup → fail-verdict-naming-the-error → record write → report.
"""
import os

import acceptance_reclaim
import acceptance_verdict
import acceptance_cleanup
import acceptance_retry


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


def _report(verdict, reason, record_path, teardown):
    """Render the single plain-language verdict report (verdict, reason, record, cleanup)."""
    cleaned = (teardown or {}).get("cleaned_up") or []
    left = (teardown or {}).get("left_behind") or []
    lines = [
        "Acceptance verdict: %s" % verdict.upper(),
        "Reason: %s" % reason,
        "Record: %s" % (record_path if record_path else "NOT WRITTEN (lease held)"),
        "Cleaned up: %s" % (", ".join(str(c) for c in cleaned) if cleaned else "nothing"),
        "Left behind: %s" % (", ".join(str(l) for l in left) if left else "nothing"),
    ]
    return "\n".join(lines)


def _run_one_attempt(deps, stamped, budget_consumed, attempt):
    """Launch one attempt and assemble its verdict facts. Returns (launch, outcome, verdict)."""
    launch = deps["launcher"](stamped, budget_consumed=budget_consumed, attempt=attempt)

    if launch.get("outcome") == "killed":
        verdict = {
            "verdict": "fail",
            "reason": "ceiling breached (%s) — run hard-killed" % launch.get("ceiling"),
        }
        return launch, {"failure_kind": "ceiling-%s" % launch.get("ceiling")}, verdict

    outcome = deps["run_outcome"](launch.get("terminal_location"))
    gh = deps["gh_reader"]()
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
        "live_checks_green": gh.get("live_checks_green"),
        "live_pr": gh.get("live_pr"),
        "unreadable": gh.get("unreadable") or [],
    }
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

    try:
        # 1. Reclaim / refuse a prior in-flight run — create nothing on refuse.
        recorded_state, liveness = deps["reclaim_probe"]()
        reclaim = acceptance_reclaim.decide(recorded_state, liveness)
        if reclaim["action"] == "refuse":
            reason = "a prior acceptance run is in flight (%s); refusing to start another" % liveness
            return {
                "verdict": "fail",
                "report": _report("fail", reason, None, None),
                "record_path": None,
            }
        if reclaim["action"] == "reclaim" and reclaim.get("write_orphan_record"):
            # The dead prior run left no record — write its orphan failed record before proceeding.
            deps["write_record"]({
                "verdict": "fail",
                "reason": "orphan record for a reclaimed dead prior run",
                "pr_link": "",
                "phases": [],
                "spend": None,
                "spend_partial": True,
                "elapsed_sec": 0.0,
                "launched_at": deps["clock_now"](),
                "terminated_at": deps["clock_now"](),
                "retried": False,
                "attempts": [{"stamp": recorded_state.get("stamp"), "verdict": "fail"}],
                "cleaned_up": [],
                "left_behind": [],
            })

        # 2. Materialize the stamped throwaway fixture work-item.
        stamped = deps["materialize"]()
        stamp = stamped.get("stamp")

        # 3. Preflight the fixture — a failed preflight refuses, naming the drifted piece.
        pf = deps["preflight_ok"](stamped.get("work_item"))
        if not pf.get("ok"):
            reason = "preflight refused the fixture: %s" % pf.get("reason", "prerequisite not met")
            teardown = _teardown(deps, stamp)
            record_path = _finalize(deps, "fail", reason, None, [], False, teardown)
            return {
                "verdict": "fail",
                "report": _report("fail", reason, record_path, teardown),
                "record_path": record_path,
            }

        # 4-6. Launch attempt 1, judge, and retry once on a confidently-environmental failure.
        budget_consumed = {"elapsed_sec": 0.0, "spend": 0.0}
        attempt = 1
        launch, outcome, verdict = _run_one_attempt(deps, stamped, budget_consumed, attempt)
        attempts.append(_attempt_record(stamp, launch, verdict))

        if verdict["verdict"] == "fail":
            retry = acceptance_retry.classify({
                "kind": outcome.get("failure_kind"),
                "unreadable": False,
                "attempt": attempt,
            })
            if retry.get("retry"):
                # Clean the first attempt before relaunching (UFR-3: a failed pre-retry
                # cleanup aborts the retry). Then re-materialize with a fresh stamp and
                # relaunch fed attempt-1's consumed budget (remaining, not a fresh ceiling).
                _teardown(deps, stamp)
                budget_consumed = {
                    "elapsed_sec": launch.get("elapsed_sec") or 0.0,
                    "spend": launch.get("spend") or 0.0,
                }
                stamped = deps["materialize"]()
                stamp = stamped.get("stamp")
                attempt = 2
                launch, outcome, verdict = _run_one_attempt(
                    deps, stamped, budget_consumed, attempt)
                attempts.append(_attempt_record(stamp, launch, verdict))

        # 7. Teardown — runs on every exit path (ready, parked, killed).
        teardown = _teardown(deps, stamp)

        # 8-9. Write the single record (both attempts), then release the lease.
        retried = len(attempts) > 1
        record_path = _finalize(
            deps, verdict["verdict"], verdict["reason"],
            launch.get("spend"), attempts, retried, teardown,
            spend_partial=launch.get("spend_partial"),
            elapsed_sec=launch.get("elapsed_sec"),
            pr_link=(outcome.get("readout_pr_link") if isinstance(outcome, dict) else "") or "",
            phases=(outcome.get("phases") if isinstance(outcome, dict) else []) or [],
        )

        # 10. Render the single verdict report.
        return {
            "verdict": verdict["verdict"],
            "report": _report(verdict["verdict"], verdict["reason"], record_path, teardown),
            "record_path": record_path,
        }

    except Exception as exc:
        # Fail-CLOSED: any internal error still teardowns and yields a fail naming the error.
        reason = "internal harness error: %s" % exc
        try:
            teardown = _teardown(deps, stamp)
        except Exception as td_exc:
            teardown = {"cleaned_up": [], "left_behind": [],
                        "note": "teardown also failed: %s" % td_exc}
        record_path = None
        try:
            record_path = _finalize(deps, "fail", reason, None, attempts,
                                    len(attempts) > 1, teardown)
        except Exception:
            record_path = None
        return {
            "verdict": "fail",
            "report": _report("fail", reason, record_path, teardown),
            "record_path": record_path,
        }


def _teardown(deps, stamp):
    """Plan + execute the stamp-scoped cleanup. Returns the reap result dict."""
    if stamp is None:
        return {"cleaned_up": [], "left_behind": []}
    planned = acceptance_cleanup.plan(deps["discover_artifacts"](stamp), run_stamp=stamp)
    return deps["reap"](planned)


def _finalize(deps, verdict, reason, spend, attempts, retried, teardown,
              spend_partial=False, elapsed_sec=0.0, pr_link="", phases=None):
    """Write the single record, then release the lease ONLY after a durable write.

    If `write_record` raises, the lease is NOT released (held so the UFR-8 backstop stays
    armed) and the failure propagates to the caller as a fail. Returns the record path.
    """
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
    record_path = deps["write_record"](record)
    # Only after the record is durably written do we release the lease.
    deps["release_lease"]()
    return record_path


def _cli(argv, env, stdout, stderr):
    """The DoD live-run entrypoint the acceptance SKILL.md documents (Task 13).

    `python3 acceptance_run.py --fixture <fixture> --root <root>` is the command the
    front-door skill runs to drive a live acceptance run. This guard makes that command
    HONEST: it refuses to nest (UFR-5) and never returns a silent exit-0 no-op. Assembling
    the real live-run `deps` (spawning the actual showrunner, sampling spend, holding the
    lease) is the skill's job on a real host; run bare like this it reports that and exits
    non-zero rather than pretending a live run happened.

    Returns the process exit code. All I/O (env, streams) is injected so it is unit-tested
    without a live run — consistent with the rest of the harness (DoD).
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

    # The live run mutates real state (spawns the showrunner, holds the lease, writes a
    # record) and must be driven by the front-door skill on a real host, which assembles
    # and injects the real deps into `invoke`. Refuse loudly rather than no-op silently.
    print(
        "acceptance_run: live-run deps are assembled by the `superheroes:acceptance` "
        "skill on a real host; this bare entrypoint does not spawn a live showrunner. "
        "fixture=%s root=%s" % (args.fixture, args.root),
        file=stderr,
    )
    return 4


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(_cli(_sys.argv[1:], os.environ, _sys.stdout, _sys.stderr))
