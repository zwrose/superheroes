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
import acceptance_result
import control_plane
import hostinfo

# The pipeline's current phase list. Mirrors the committed fixture's declared
# `expected_phases` (plan.md/tasks.md `expected_phases:`); `acceptance_fixture.drift_check`
# is the one thing that notices when this and the fixture's declaration diverge, so a
# stale value here is caught (UFR-7) rather than silently miscomputing the FR-3 verdict.
PIPELINE_PHASES = ["plan", "tasks", "build", "review", "ship"]

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


def _write_lease(root, stamp):
    path = _lease_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({
            "stamp": stamp,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "bootId": hostinfo.boot_id(),
            "acquiredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ttl": _LEASE_TTL,
        }, fh)
    os.replace(tmp, path)


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


def real_reclaim_probe(root):
    """`deps["reclaim_probe"]`: read the lease file and confirm liveness for real."""
    lease = _read_lease(root)
    if lease is None:
        return {"in_flight": False, "stamp": None, "has_record": False}, "dead"
    has_record = acceptance_result.read_record(_record_dir(root)) is not None
    liveness = _lease_liveness(lease)
    return {"in_flight": True, "stamp": lease.get("stamp"), "has_record": has_record}, liveness


def real_release_lease(root):
    """`deps["release_lease"]`: drop the lease file. Idempotent."""
    try:
        os.remove(_lease_path(root))
    except OSError:
        pass


# --- materialize / preflight -----------------------------------------------------------


def real_materialize(fixture_dir, root):
    """`deps["materialize"]`: stamp a fresh unique id, write the lease, and copy the
    committed fixture triple into the throwaway work-item slug."""
    stamp_id = uuid.uuid4().hex
    stamped = acceptance_fixture.materialize(stamp_id, fixture_dir, _harness_dir(root))
    stamp = acceptance_fixture.make_stamp(stamp_id)
    stamped["stamp"] = stamp
    _write_lease(root, stamp)
    return stamped


def real_preflight_ok(fixture_dir, root):
    """`deps["preflight_ok"]`: the drift check (UFR-7) — a missing/drifted fixture refuses
    before anything launches. `work_item` is accepted for interface parity with the
    injected-test seam but the check runs entirely against the committed fixture dir."""
    def _check(_work_item):
        target_exists = os.path.isfile(os.path.join(fixture_dir, "target.txt"))
        return acceptance_fixture.drift_check(fixture_dir, PIPELINE_PHASES, target_exists)
    return _check


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

    A failed lookup (rc != 0: network blip / rate-limit / timeout) is "couldn't check",
    NOT "confirmed nothing to discover" — silently omitting that artifact class would let
    a real leaked branch/PR go both unreaped AND unreported. Instead of dropping it, a
    synthetic placeholder artifact is appended, carrying the BARE reserved prefix (with a
    non-`[a-z0-9]` separator so it deliberately never parses to a valid full stamp — see
    `acceptance_fixture.parse_stamp`) so `acceptance_cleanup.plan` routes it to
    `leave_behind` (never reaped) with a name that surfaces the degraded class in the report.
    """
    def _discover(_stamp):
        artifacts = []
        rc, out, _err = _run(["git", "branch", "--list", "wi-%s*" % acceptance_fixture.RESERVED_PREFIX],
                             cwd=root)
        if rc == 0:
            for line in out.splitlines():
                name = line.strip().lstrip("* ").strip()
                if name:
                    artifacts.append({"kind": "branch", "name": name})
        else:
            artifacts.append({
                "kind": "branch",
                "name": acceptance_fixture.RESERVED_PREFIX + " discovery degraded: branch lookup failed",
            })
        rc, out, _err = _run(
            ["gh", "pr", "list", "--search", acceptance_fixture.RESERVED_PREFIX,
             "--json", "title", "--jq", ".[].title"], cwd=root)
        if rc == 0:
            for title in out.splitlines():
                title = title.strip()
                if title:
                    artifacts.append({"kind": "pr", "name": title})
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
                rc, out, _err = _run(
                    ["gh", "pr", "list", "--search", name, "--json", "number,title",
                     "--jq", ".[0].number"], cwd=root)
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
    """`deps["gh_reader"]`: live PR/check facts for the stamped run's PR (found by title
    search, since the run's own final PR number is not known ahead of the launch)."""
    def _read():
        title = stamped.get("pr_title") if isinstance(stamped, dict) else None
        result = {"pr_exists": False, "pr_ready_for_review": False, "checks_green": False,
                  "live_checks_green": False, "live_pr": "", "unreadable": []}
        if not title:
            result["unreadable"] = ["pr_exists"]
            return result
        rc, out, _err = _run(
            ["gh", "pr", "list", "--search", title,
             "--json", "number,url,isDraft,statusCheckRollup", "--jq", "."], cwd=root)
        if rc != 0 or not out.strip():
            result["unreadable"] = ["pr_exists"]
            return result
        try:
            prs = json.loads(out)
        except ValueError:
            result["unreadable"] = ["pr_exists"]
            return result
        if not prs:
            return result
        pr = prs[0]
        result["pr_exists"] = True
        result["pr_ready_for_review"] = pr.get("isDraft") is False
        result["live_pr"] = pr.get("url") or ""
        rollup = pr.get("statusCheckRollup") or []
        green = bool(rollup) and all(
            (c.get("conclusion") or "").upper() == "SUCCESS" for c in rollup)
        result["checks_green"] = green
        result["live_checks_green"] = green
        return result
    return _read


def real_run_outcome(root):
    """`deps["run_outcome"]`: read the showrunner's terminal record + project the readout
    facts `acceptance_verdict.decide` needs. Missing/unreadable -> a `parked`-shaped
    outcome so the verdict fails naming the unreadable facts rather than crashing."""
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
        return {
            "terminal": record.get("terminal", "parked"),
            "phases": record.get("phasesTraversed") or record.get("phases") or [],
            "readout_pr_link": record.get("prUrl") or record.get("readout_pr_link") or "",
            "readout_claimed_checks_green": record.get("checksGreen",
                                                        record.get("readout_claimed_checks_green")),
            "readout_claimed_pr": record.get("prUrl") or record.get("readout_claimed_pr") or "",
            "failure_kind": record.get("failureKind"),
        }
    return _read


def real_expected_phases():
    return lambda: list(PIPELINE_PHASES)


def real_clock_now():
    return lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def real_launcher(root):
    """`deps["launcher"]`: `acceptance_launch.run` with its production real defaults
    (spawns the headless `claude` CLI as a process-group leader)."""
    def _launch(stamped, budget_consumed=None, attempt=1):
        from acceptance_ceiling import DEFAULT_CEILINGS
        terminal_path = os.path.join(_harness_dir(root), stamped.get("stamp", ""),
                                     "terminal-record.json")

        def _child_factory():
            return acceptance_launch._default_child_factory(stamped, terminal_path=terminal_path)

        return acceptance_launch.run(
            stamped, DEFAULT_CEILINGS, _child_factory, acceptance_launch._REAL_CLOCK,
            acceptance_launch._default_spend_sampler,
            lambda: acceptance_launch._default_engine_pref_reader(root, root),
            budget_consumed=budget_consumed, attempt=attempt,
        )
    return _launch


def real_write_record(root):
    def _write(record):
        return acceptance_result.write_record(record, _record_dir(root))
    return _write


# --- assembly --------------------------------------------------------------------------


def build(fixture_dir, root):
    """Assemble the full real `deps` dict `acceptance_run.invoke` expects.

    Every seam here is a real primitive (control-plane store, git/gh subprocess reads,
    the live launcher) — not a fake. `acceptance_run._cli` is what actually calls
    `invoke(deps)` with the dict this returns.
    """
    state = {"stamped": None}

    def materialize():
        stamped = real_materialize(fixture_dir, root)
        state["stamped"] = stamped
        return stamped

    def gh_reader():
        return real_gh_reader(root, state["stamped"] or {})()

    def discover_artifacts(stamp):
        return real_discover_artifacts(root)(stamp)

    def current_stamp():
        return (state["stamped"] or {}).get("stamp")

    return {
        "reclaim_probe": lambda: real_reclaim_probe(root),
        "materialize": materialize,
        "preflight_ok": real_preflight_ok(fixture_dir, root),
        "launcher": real_launcher(root),
        "run_outcome": real_run_outcome(root),
        "gh_reader": gh_reader,
        "expected_phases": real_expected_phases(),
        "discover_artifacts": discover_artifacts,
        "reap": real_reap(root, current_stamp),
        "write_record": real_write_record(root),
        "release_lease": lambda: real_release_lease(root),
        "clock_now": real_clock_now(),
    }
