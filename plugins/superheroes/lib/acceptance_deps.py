"""Real dependency assembly for the acceptance harness (Task 13).

`acceptance_run.invoke(deps)` takes every I/O boundary injected so its lifecycle is
unit-tested without a live run (DoD). Something still has to build the REAL `deps` dict
for an actual live run — that assembly lived nowhere in the repo, so the documented CLI
command (`python3 acceptance_run.py --fixture <fixture> --root <root>`) could never
produce a verdict/record/report no matter who ran it. This module is that assembly: it
wires every seam (`acceptance_run.invoke` expects) to a real primitive already used
elsewhere in the band — `control_plane` for the harness namespace, `file_lock`-style
pid/host/bootId staleness for the lease, `git`/`gh` subprocess reads for discovery and
live PR facts, and `acceptance_launch.run` for the actual out-of-process showrunner spawn.

Nothing here is a decider — every judgment still routes through the pure
`acceptance_*` deciders `invoke` already calls. This module only answers "where do the
bytes live and how do we read/write them for real."

`build(fixture_dir, root)` returns the `deps` dict ready to hand to
`acceptance_run.invoke` — `acceptance_run._cli` (the actual `python3 acceptance_run.py
--fixture <fixture> --root <root>` entrypoint) calls this by default, then `invoke(deps)`,
so the documented command performs a genuine live run rather than a silent no-op or a
stub that declines (the DoD floor `test_acceptance_run_cli.py` pins).
"""
import json
import os
import socket
import subprocess
import time
import uuid

import acceptance_fixture
import acceptance_launch
import acceptance_ceiling
import acceptance_phases
import acceptance_result
import control_plane
import cost_report
import hostinfo
import journal
import preflight

_LEASE_TTL = 1800  # seconds; mirrors file_lock.DEFAULT_TTL / ref_lock.DEFAULT_TTL
_HARNESS_NS = "acceptance"  # sub-namespace under the per-checkout control-plane store


def _harness_dir(root):
    """The per-checkout control-plane dir this harness invocation reads/writes under.

    `root` here is the REPO root (`--root`, used as `checkout_dir`'s `cwd` so the checkout
    key hashes the right `--absolute-git-dir`) — NOT the control-plane store root, which
    `control_plane.checkout_dir` resolves itself (env override `SUPERHEROES_STORE_ROOT` /
    the default `~/.claude/superheroes`, per `control_plane.store_root`). Passing `None`
    here lets that resolution happen instead of conflating the two roots.
    """
    return os.path.join(control_plane.checkout_dir(root, None), _HARNESS_NS)


def _lease_path(root):
    return os.path.join(_harness_dir(root), "lease.json")


def _record_dir(root):
    return _harness_dir(root)


# --- reclaim / lease -----------------------------------------------------------------


def _read_lease(root):
    try:
        with open(_lease_path(root), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _lease_payload(stamp):
    return {
        "stamp": stamp,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "bootId": hostinfo.boot_id(),
        "acquiredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ttl": _LEASE_TTL,
    }


def _write_lease(root, stamp):
    """Overwrite the lease unconditionally. Only ever called after this invocation has
    already WON the atomic acquire in `_try_acquire_lease` (or on the fixed reclaim path
    where a confirmed-dead holder's lease was already unlinked) — never a substitute for
    the exclusive-create race-free acquire itself."""
    path = _lease_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_lease_payload(stamp), fh)
    os.replace(tmp, path)


def _try_acquire_lease(root, stamp):
    """Atomically create the lease file with this invocation's stamp using the same
    race-free `O_CREAT|O_EXCL` primitive `file_lock.acquire` uses (this module's own
    docstring names it as the model to follow) — closing the probe-then-write TOCTOU
    window: reading "no lease" and writing one are now a single indivisible step, so two
    concurrent invocations can never both observe "free" and both proceed.

    Returns True if this invocation now holds the lease (freshly created), False if an
    existing lease file is already present (caller must probe/decide on it)."""
    path = _lease_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as fh:
        json.dump(_lease_payload(stamp), fh)
    return True


def _lease_liveness(lease):
    """"alive"|"dead"|"unconfirmable" for a recorded lease dict — mirrors file_lock.is_stale's
    pid/host/bootId staleness test, but reports a tri-state so an unreadable/foreign-host
    lease refuses fail-closed (UFR-4) instead of being silently treated as reclaimable."""
    if not isinstance(lease, dict) or not lease.get("pid"):
        return "unconfirmable"
    if lease.get("host") != socket.gethostname():
        # Can't signal a pid on another host — never claim it's dead.
        return "unconfirmable"
    boot = lease.get("bootId")
    cur_boot = hostinfo.boot_id()
    if boot is not None and cur_boot is not None and boot != cur_boot:
        return "dead"  # the host rebooted since the lease was written; the pid is meaningless
    try:
        os.kill(int(lease["pid"]), 0)
    except ProcessLookupError:
        return "dead"
    except (PermissionError, ValueError, OverflowError, TypeError):
        return "unconfirmable"
    return "alive"


def real_reclaim_probe(root, reserved_stamp=None):
    """`deps["reclaim_probe"]`: atomically claim the lease for real, folding the
    read-and-decide-liveness probe together with the exclusive-create acquire into one
    indivisible step (premortem-001) — closing the check-then-act TOCTOU where a probe at
    lifecycle step 1 and a non-exclusive `os.replace` write at step 2 let two concurrent
    invocations both observe "no lease" and both proceed.

    `reserved_stamp` is the stamp THIS invocation would use if it wins the acquire (its
    caller in `build()` mints it once, up front, so the same stamp that decides the
    acquire is the one `materialize()` later stamps its fixture with — probe and acquire
    share a single stamp rather than reserving one identity and materializing another).

    Tries the atomic `O_CREAT|O_EXCL` create FIRST (mirroring `file_lock.acquire`'s
    race-free primitive, the model this module's own docstring names): if it wins, no
    other lease existed a moment ago and none can appear between this call and
    `materialize()` reusing the win, so `proceed` is safe by construction — no separate
    read-then-write window remains for a second invocation to slip through. Only on
    `FileExistsError` (another lease is already there) does this fall into the existing
    read/liveness-classify path, exactly as before.
    """
    if reserved_stamp is not None and _try_acquire_lease(root, reserved_stamp):
        return {"in_flight": False, "stamp": None, "has_record": False,
                "lease_acquired": True}, "dead"
    lease = _read_lease(root)
    if lease is None:
        return {"in_flight": False, "stamp": None, "has_record": False}, "dead"
    has_record = _record_belongs_to_stamp(
        acceptance_result.read_record(_record_dir(root)), lease.get("stamp"))
    liveness = _lease_liveness(lease)
    return {"in_flight": True, "stamp": lease.get("stamp"), "has_record": has_record}, liveness


def _record_belongs_to_stamp(record, stamp):
    if not isinstance(record, dict) or not stamp:
        return False
    if record.get("run_stamp") == stamp:
        return True
    for attempt in record.get("attempts") or []:
        if isinstance(attempt, dict) and attempt.get("stamp") == stamp:
            return True
    return False


def real_release_lease(root):
    """`deps["release_lease"]`: drop the lease file. Idempotent."""
    try:
        os.remove(_lease_path(root))
    except OSError:
        pass


def real_quarantine_lease(root):
    """Mark the lease unconfirmable after a child process group could not be killed safely."""
    def _quarantine(stamp):
        path = _lease_path(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "stamp": stamp,
            "pid": "unconfirmed-child",
            "host": socket.gethostname(),
            "bootId": hostinfo.boot_id(),
            "acquiredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ttl": _LEASE_TTL,
            "reason": "kill-unconfirmed",
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    return _quarantine


# --- materialize / preflight -----------------------------------------------------------


def real_materialize(fixture_dir, root, reserved_stamp=None, lease_acquired=False):
    """`deps["materialize"]`: copy the committed fixture triple into the throwaway
    work-item slug, stamped with the identity this invocation already reserved.

    `reserved_stamp` is the SAME stamp `real_reclaim_probe` decided against
    (premortem-001) — reusing it here means the lease that guarded proceed and the
    fixture that gets materialized always refer to the same run. `lease_acquired=True`
    means `real_reclaim_probe` already won the atomic `O_CREAT|O_EXCL` create for that
    stamp (the genuine no-prior-lease race), so this step must NOT write the lease again
    (a second write here would be exactly the non-atomic re-write premortem-001 flags).
    `lease_acquired=False` with a `reserved_stamp` covers the `reclaim` path (a confirmed
    -dead prior lease was found, not raced for) — this invocation still owns the identity
    it reserved but the lease file itself was never claimed under it, so it's written
    here for the first time. No `reserved_stamp` at all (legacy/direct callers with no
    atomic acquire upstream) falls back to minting + writing a fresh one, preserving
    prior behavior for those callers.
    """
    if reserved_stamp is not None:
        stamp = reserved_stamp
        stamp_id = stamp[len(acceptance_fixture.RESERVED_PREFIX):]
        if not lease_acquired:
            _write_lease(root, stamp)
    else:
        stamp_id = uuid.uuid4().hex
        stamp = acceptance_fixture.make_stamp(stamp_id)
        _write_lease(root, stamp)
    stamped = acceptance_fixture.materialize(stamp_id, fixture_dir, _harness_dir(root))
    stamped["stamp"] = stamp
    return stamped


def real_preflight_ok(fixture_dir, root):
    """`deps["preflight_ok"]`: the drift check (UFR-7) — a missing/drifted fixture refuses
    before anything launches. `work_item` is accepted for interface parity with the
    injected-test seam but the check runs entirely against the committed fixture dir."""
    def _check(work_item):
        target_exists = os.path.isfile(os.path.join(fixture_dir, "target.txt"))
        try:
            phases = acceptance_phases.read_pipeline_phases()
        except RuntimeError as exc:
            return {"ok": False, "reason": "pipeline phase source drift: %s" % exc}
        drift = acceptance_fixture.drift_check(fixture_dir, phases, target_exists)
        if not drift.get("ok"):
            return drift
        live = _acceptance_live_preflight(work_item, root)
        if not live.get("ok"):
            return live
        return {"ok": True, "reason": "no drift: phases match, target exists, and live preflight passed"}
    return _check


def _acceptance_live_preflight(work_item, root):
    """Reuse the showrunner preflight probes for the live-only launch blockers this harness needs.

    The committed fixture lives in the harness namespace, not necessarily in the owner's definition-doc
    location, so the acceptance front door only consumes the production probes that are independent of
    that fixture location: GitHub reachability/access and calibration/config readability.
    """
    try:
        probes = preflight.probe(work_item, root)
    except Exception as exc:
        return {"ok": False, "reason": "live preflight could not run: %s" % exc}
    gh = probes.get("gh") if isinstance(probes, dict) else None
    if not isinstance(gh, dict) or gh.get("ok") is not True:
        return {"ok": False, "reason": "github-access preflight failed: %s" %
                ((gh or {}).get("remediation") or "verify GitHub is reachable and retry")}
    if probes.get("config_resolves") is not True:
        return {"ok": False, "reason": "config-resolves preflight failed: run superheroes:configure and retry"}
    return {"ok": True, "reason": "live preflight passed"}


# --- git/gh discovery + reads -----------------------------------------------------------


def _run(args, cwd, timeout=15):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return 1, "", "subprocess failed"


def real_discover_artifacts(root):
    """`deps["discover_artifacts"]`: enumerate local/remote branches + open PRs whose
    names might carry a reserved stamp. Cleanup's own `acceptance_fixture.parse_stamp`
    routing decides what's actually reaped — this only lists candidates.

    Branch discovery globs BOTH the harness's own legacy `wi-<stamp>*` naming and the
    real showrunner build-branch naming (`buildtree.branch_name`:
    `superheroes/<work_item>-<content_hash>`, where `work_item` IS the stamp) — a live
    showrunner run never produces a `wi-<stamp>*` branch, so glob-ing only that pattern
    left every real fixture branch undiscovered (and therefore un-reaped) after a live
    run. `parse_stamp` still gates what's structurally a valid stamp before anything is
    ever deleted, so widening the glob cannot cause an unrelated branch to be reaped.

    A failed lookup (rc != 0: network blip / rate-limit / timeout) is "couldn't check",
    NOT "confirmed nothing to discover" — silently omitting that artifact class would let
    a real leaked branch/PR go both unreaped AND unreported. Instead of dropping it, a
    synthetic placeholder artifact is appended, carrying the BARE reserved prefix (with a
    non-`[a-z0-9]` separator so it deliberately never parses to a valid full stamp — see
    `acceptance_fixture.parse_stamp`) so `acceptance_cleanup.plan` routes it to
    `leave_behind` (never reaped) with a name that surfaces the degraded class in the report.

    PR discovery lists open+closed PRs and filters by `headRefName` (the branch the
    harness actually creates, `superheroes/<stamp>-...` or legacy `wi-<stamp>`) rather
    than a free-text title search — the live showrunner titles its PR from the first
    commit's Conventional-Commit subject (`gh pr create --fill-first`, see pr_entry.py),
    never the harness's synthetic `pr_title`, so a title search never reliably finds the
    real PR. The discovered PR artifact's `name` is the matching `headRefName` (which
    embeds the stamp, so `acceptance_cleanup.plan`'s `parse_stamp` routing still works),
    NOT the PR's own title — `real_reap` looks the PR back up by that same head branch.
    """
    def _discover(_stamp):
        artifacts = []
        branch_names = set()
        branch_lookup_failed = False
        for pattern in ("wi-%s*" % acceptance_fixture.RESERVED_PREFIX,
                        "superheroes/*%s*" % acceptance_fixture.RESERVED_PREFIX):
            rc, out, _err = _run(["git", "branch", "--list", pattern], cwd=root)
            if rc == 0:
                for line in out.splitlines():
                    name = line.strip().lstrip("* ").strip()
                    if name:
                        branch_names.add(name)
            else:
                branch_lookup_failed = True
        if branch_lookup_failed:
            # One degraded placeholder regardless of how many glob patterns failed —
            # never a per-pattern duplicate.
            artifacts.append({
                "kind": "branch",
                "name": acceptance_fixture.RESERVED_PREFIX + " discovery degraded: branch lookup failed",
            })
        for name in sorted(branch_names):
            artifacts.append({"kind": "branch", "name": name})
        rc, out, _err = _run(
            ["gh", "pr", "list", "--state", "all",
             "--json", "title,headRefName", "--jq", "."], cwd=root)
        if rc == 0:
            try:
                prs = json.loads(out) if out.strip() else []
            except ValueError:
                prs = None
            if prs is None:
                artifacts.append({
                    "kind": "pr",
                    "name": acceptance_fixture.RESERVED_PREFIX + " discovery degraded: pr lookup failed",
                })
            else:
                for pr in prs:
                    head = pr.get("headRefName") or ""
                    if acceptance_fixture.RESERVED_PREFIX in head:
                        artifacts.append({"kind": "pr", "name": head})
        else:
            artifacts.append({
                "kind": "pr",
                "name": acceptance_fixture.RESERVED_PREFIX + " discovery degraded: pr lookup failed",
            })
        return artifacts
    return _discover


def real_reap(root, current_stamp):
    """`deps["reap"]`: execute a cleanup plan's `reap` list for real (branch delete, PR
    close) and report `{cleaned_up, left_behind}`. Never raises — a failed reap for one
    artifact is reported left-behind (UFR-3) rather than aborting the others.

    `current_stamp` is a zero-arg callable returning this invocation's own stamp (read
    from the same materialize-time state `build()` tracks) — used only to also remove
    the invocation's own materialized store dir; `acceptance_cleanup.plan`'s `reap` list
    itself carries no stamp field, so this is not read from `planned`.
    """
    def _reap(planned):
        cleaned, left = [], list(planned.get("leave_behind") or [])
        for art in planned.get("reap") or []:
            kind, name = art.get("kind"), art.get("name")
            ok = False
            if kind == "branch":
                rc, _out, _err = _run(["git", "branch", "-D", name], cwd=root)
                ok = rc == 0
            elif kind == "pr":
                # `name` here is the PR's head branch (see real_discover_artifacts) — look
                # the PR back up by that exact branch, not a free-text title search, since
                # the harness's discovered PR artifacts carry no reliable title to search on.
                rc, out, _err = _run(
                    ["gh", "pr", "list", "--head", name, "--state", "all",
                     "--json", "number,title", "--jq", ".[0].number"], cwd=root)
                if rc != 0:
                    # The lookup itself failed (network blip / rate-limit / timeout) —
                    # this is "couldn't check", NOT "confirmed absent". Never fold a
                    # failed lookup into the empty-match sentinel: report it left-behind
                    # so a genuinely-leaked PR is surfaced rather than falsely reported
                    # cleaned (detectability: the report must never assert a teardown
                    # that did not happen).
                    ok = False
                    left.append({"kind": kind, "name": name,
                                "reason": "could not confirm PR state (gh lookup failed/timed out)"})
                    continue
                number = out.strip()
                if number:
                    rc2, _o, _e = _run(["gh", "pr", "close", number], cwd=root)
                    ok = rc2 == 0
                else:
                    ok = True  # confirmed: rc == 0 with no match -> already gone
            else:
                ok = True  # unknown kind: nothing this reaper knows how to remove
            (cleaned if ok else left).append(name if ok else
                                             {"kind": kind, "name": name,
                                              "reason": "reap action failed"})
        # also remove this invocation's own materialized store dir, if present.
        stamp = current_stamp()
        if stamp:
            work_dir = os.path.join(_harness_dir(root), stamp)
            if os.path.isdir(work_dir):
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
        return {"cleaned_up": cleaned, "left_behind": left}
    return _reap


def real_gh_reader(root, stamped):
    """`deps["gh_reader"]`: live PR/check facts for the stamped run's PR.

    Found by HEAD BRANCH PREFIX, not the harness's synthetic `pr_title` — the live
    showrunner titles its PR from the first commit's Conventional-Commit subject
    (`gh pr create --fill-first`, pr_entry.py), never `stamped["pr_title"]`, and that
    title is never threaded into the launch prompt either. The showrunner's real build
    branch is `buildtree.branch_name`: `superheroes/<work_item>-<content_hash>` — the
    content hash isn't known ahead of the run, so this lists PRs and matches by the
    `superheroes/<work_item>-` prefix (falling back to the harness's own legacy
    `wi-<work_item>` naming) rather than an exact `--head` lookup.
    """
    def _read():
        work_item = stamped.get("work_item") if isinstance(stamped, dict) else None
        result = {"pr_exists": False, "pr_ready_for_review": False, "checks_green": False,
                  "live_checks_green": False, "live_pr": "", "unreadable": [],
                  "failure_kind": None}
        if not work_item:
            result["unreadable"] = ["pr_exists"]
            return result
        rc, out, _err = _run(
            ["gh", "pr", "list", "--state", "all",
             "--json", "number,url,isDraft,statusCheckRollup,headRefName", "--jq", "."],
            cwd=root)
        if rc != 0 or not out.strip():
            result["unreadable"] = ["pr_exists"]
            result["failure_kind"] = _host_failure_kind(root)
            return result
        try:
            prs = json.loads(out)
        except ValueError:
            result["unreadable"] = ["pr_exists"]
            result["failure_kind"] = _host_failure_kind(root)
            return result
        prefixes = ("superheroes/%s-" % work_item, "wi-%s" % work_item)
        matches = [pr for pr in prs if (pr.get("headRefName") or "").startswith(prefixes)]
        if not matches:
            return result
        pr = matches[0]
        result["pr_exists"] = True
        result["pr_ready_for_review"] = pr.get("isDraft") is False
        result["live_pr"] = pr.get("url") or ""
        rollup = pr.get("statusCheckRollup") or []
        result["failure_kind"] = _check_failure_kind(rollup)
        green = bool(rollup) and all(
            (c.get("conclusion") or "").upper() == "SUCCESS" for c in rollup)
        result["checks_green"] = green
        result["live_checks_green"] = green
        return result
    return _read


def _host_failure_kind(root):
    try:
        import gh_preflight
        probe = gh_preflight.probe(root)
        ok, cause, _remediation = gh_preflight.decide(probe, required="read")
        if ok is False and cause == "indeterminate":
            return "host-unreachable"
    except Exception:
        return None
    return None


def _check_failure_kind(rollup):
    for check in rollup or []:
        if not isinstance(check, dict):
            continue
        conclusion = str(check.get("conclusion") or "").upper()
        status = str(check.get("status") or check.get("state") or "").upper()
        if conclusion == "STARTUP_FAILURE" or status == "ERROR":
            return "check-runner-errored-before-running"
    return None


def _phase_from_event(event):
    if not isinstance(event, dict):
        return None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if event.get("type") == "phase_record":
        return payload.get("phase")
    if event.get("type") == "phase_cost":
        return payload.get("phase")
    if event.get("type") == "run_completed":
        return "ship"
    return None


def _phases_from_journal(root, work_item):
    if not work_item:
        return []
    try:
        allowed = set(acceptance_phases.read_pipeline_phases())
        events = journal.read_events(control_plane.paths(root, work_item)["events"])
    except Exception:
        return []
    phases = []
    for event in events:
        phase = _phase_from_event(event)
        if phase in allowed and phase not in phases:
            phases.append(phase)
    return phases


def real_run_outcome(root, work_item=None):
    """`deps["run_outcome"]`: read the showrunner's terminal record + project the readout
    facts `acceptance_verdict.decide` needs. Missing/unreadable -> a `parked`-shaped
    outcome so the verdict fails naming the unreadable facts rather than crashing.

    The record on disk is whatever `run_readout.run_outcome(state)` (the "#112 consumer
    contract" — see run_readout.py) emits: `status`/`checks`/`reason`/`prUrl`/
    `phasesTraversed`/`readoutPath`. `status` is `"ready"` on a genuine success terminal
    (mirrored from `acceptance_verdict.decide`'s own `facts["terminal"] != "ready"`
    check) and `checks` is the CI string (`"green"`/`"none"`/`"red"`) — a claimed-green
    readout is exactly `checks == "green"`. Older/foreign field names (`terminal`,
    `checksGreen`, `failureKind`) are NOT read: they do not exist in the real projection
    and reading them would silently pin every real run to the fail-closed default."""
    def _read(terminal_location):
        default = {"terminal": "parked", "phases": [], "readout_pr_link": "",
                   "readout_claimed_checks_green": None, "readout_claimed_pr": "",
                   "failure_kind": "no-terminal-record"}
        if not terminal_location or not os.path.isfile(terminal_location):
            return default
        try:
            with open(terminal_location, encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return default
        if not isinstance(record, dict):
            return default
        pr_url = record.get("prUrl") or ""
        checks = record.get("checks")
        current_work_item = work_item() if callable(work_item) else work_item
        durable_phases = _phases_from_journal(root, current_work_item) if current_work_item else None
        return {
            "terminal": record.get("status") or "parked",
            "phases": durable_phases if durable_phases is not None else (record.get("phasesTraversed") or []),
            "readout_pr_link": pr_url,
            "readout_claimed_checks_green": (checks == "green") if checks is not None else None,
            "readout_claimed_pr": pr_url,
            "failure_kind": record.get("reason"),
        }
    return _read


def real_expected_phases():
    return lambda: acceptance_phases.read_pipeline_phases()


def real_clock_now():
    return lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def real_spend_sampler(root, work_item):
    def _sample():
        current_work_item = work_item() if callable(work_item) else work_item
        if not current_work_item:
            return (None, False)
        try:
            events = journal.read_events(control_plane.paths(root, current_work_item)["events"])
            summary = cost_report.summarize(events)
        except Exception:
            return (None, False)
        tokens = summary.get("outputTokens")
        if summary.get("measured") and tokens is not None:
            return (float(tokens), True)
        return (None, False)
    return _sample


def real_launcher(root, ceilings=None):
    """`deps["launcher"]`: `acceptance_launch.run` with its production real defaults
    (spawns `claude -p <prompt>` — the non-interactive CLI form — as a process-group
    leader, driving superheroes:showrunner on the stamped work-item)."""
    def _launch(stamped, budget_consumed=None, attempt=1):
        terminal_path = os.path.join(_harness_dir(root), stamped.get("stamp", ""),
                                     "terminal-record.json")

        def _child_factory():
            return acceptance_launch._default_child_factory(stamped, terminal_path=terminal_path)

        return acceptance_launch.run(
            stamped, acceptance_ceiling.normalize_ceilings(ceilings), _child_factory,
            acceptance_launch._REAL_CLOCK,
            real_spend_sampler(root, lambda: stamped.get("work_item")),
            lambda: acceptance_launch._default_engine_pref_reader(root, root),
            budget_consumed=budget_consumed, attempt=attempt,
        )
    return _launch


def real_write_record(root):
    def _write(record):
        return acceptance_result.write_record(record, _record_dir(root))
    return _write


def real_write_refusal_record(root):
    def _write(record):
        dest = os.path.join(_harness_dir(root), "refusals", uuid.uuid4().hex)
        return acceptance_result.write_record(record, dest)
    return _write


def real_write_orphan_record(root):
    def _write(record):
        stamp = record.get("run_stamp") if isinstance(record, dict) else None
        dest = os.path.join(_harness_dir(root), "orphans", stamp or uuid.uuid4().hex)
        return acceptance_result.write_record(record, dest)
    return _write


# --- assembly --------------------------------------------------------------------------


def build(fixture_dir, root, ceilings=None):
    """Assemble the full real `deps` dict `acceptance_run.invoke` expects.

    Every seam here is a real primitive (control-plane store, git/gh subprocess reads,
    the live launcher) — not a fake. `acceptance_run._cli` is what actually calls
    `invoke(deps)` with the dict this returns.

    premortem-001: `reclaim_probe` and the FIRST `materialize()` share one atomically-
    reserved stamp (`state["reserved_stamp"]`, minted once here and consumed exactly
    once) so the exclusive-create acquire in `real_reclaim_probe` and the fixture writer
    in `real_materialize` always agree on which identity won the race — there is no
    second, independent lease write for the first attempt. A retry's second
    `materialize()` call (this invocation already holds the lease from the first) mints
    and writes its own fresh stamp the ordinary way, since no second concurrent
    invocation needs arbitrating at that point — only the initial proceed/refuse decision
    is a genuine multi-invocation race.
    """
    state = {
        "stamped": None,
        "reserved_stamp": acceptance_fixture.make_stamp(uuid.uuid4().hex),
        "lease_acquired": False,
    }

    def reclaim_probe():
        recorded_state, liveness = real_reclaim_probe(root, reserved_stamp=state["reserved_stamp"])
        state["lease_acquired"] = bool(recorded_state.get("lease_acquired"))
        return recorded_state, liveness

    def materialize():
        reserved = state.pop("reserved_stamp", None)
        lease_acquired = state.pop("lease_acquired", False)
        stamped = real_materialize(fixture_dir, root, reserved_stamp=reserved,
                                   lease_acquired=lease_acquired)
        state["stamped"] = stamped
        return stamped

    def gh_reader():
        return real_gh_reader(root, state["stamped"] or {})()

    def discover_artifacts(stamp):
        return real_discover_artifacts(root)(stamp)

    def current_stamp():
        return (state["stamped"] or {}).get("stamp")

    return {
        "reclaim_probe": reclaim_probe,
        "materialize": materialize,
        "preflight_ok": real_preflight_ok(fixture_dir, root),
        "launcher": real_launcher(root, ceilings=ceilings),
        "run_outcome": real_run_outcome(root, lambda: (state["stamped"] or {}).get("work_item")),
        "gh_reader": gh_reader,
        "expected_phases": real_expected_phases(),
        "discover_artifacts": discover_artifacts,
        "reap": real_reap(root, current_stamp),
        "write_record": real_write_record(root),
        "write_refusal_record": real_write_refusal_record(root),
        "write_orphan_record": real_write_orphan_record(root),
        "quarantine_lease": real_quarantine_lease(root),
        "release_lease": lambda: real_release_lease(root),
        "clock_now": real_clock_now(),
    }
