#!/usr/bin/env python3
"""Ledger-driven single-shot wave watcher (#982).

Watch one launch batch until the first qualifying event. stdlib only.

Contract:
- Refusals (ok=False): batch-invalid, interval-invalid, max-seconds-invalid,
  repo-root-invalid, store-unresolvable, ledger-unreadable, internal-error.
- Events (ok=True): lane-terminal, lane-blocked, builder-exited, pr-set-changed,
  lane-stale, timer.
- Degradations (non-fatal): ledger-torn-tail, ledger-unreadable,
  heartbeat-unreadable, pid-probe-uncertain, pr-signal-unavailable,
  lane-never-stamped, pr-signal-never-sampled.
- gh child env-scrubbing: ambient git/GH routing variables in _GIT_SCRUB_VARS
  are stripped via _scrub_env before the gh subprocess runs.
- Deadline-bound polling: no gh poll starts when remaining time is below
  _MIN_PR_POLL_SECONDS; each poll's timeout is min(30.0, remaining).
- Precedence: lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >
  pr-set-changed (E4) > lane-stale (E5) > timer (E6).
- lane-stale: a lane whose heartbeat class is stale and whose latest recorded
  pid is positively live — a wedged builder alive but frozen past its own
  staleAfterSeconds promise.
- Observed latch: once the ledger has returned ok or tornTail, a subsequent
  missing read is blind (store loss), not benign pre-arm silence.
- When a lane's heartbeat is unreadable its higher-precedence E1/E2 state is
  UNKNOWN, so a lower-precedence event may be reported for it and the
  heartbeat-unreadable degradation token discloses that uncertainty.
- alsoObserved: when an event fires, co-occurring lower-precedence lane signals
  from the same interval are included under alsoObserved (launchIds only).
- ignore-launch: caller-supplied launch ids excluded from lane enumeration so
  an already-handled lane that cannot be terminalized does not re-fire.
- Pid liveness: probes ONLY the recorded leader pid (never the process group).
  launch_ledger._child_group_is_live biases uncertain toward ALIVE because a
  false dead there causes a wrong kill/outcome record; this watcher biases
  toward WAKING because a missed exit is the failure it exists to prevent.
  launcher._default_spawn uses start_new_session=True, so leader-gone/group-alive
  is a real and intended builder-exited wake. Only info['pid'] (latest attempt)
  is probed; info['pids'] history is ignored because prior attempt pids are dead
  by construction on a retried lane.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import launch_ledger as ll  # noqa: E402
import heartbeat as hb  # noqa: E402

_GH_PR_LIST_ARGV = [
    "gh", "pr", "list", "--state", "open", "--json", "number", "--limit", "1000",
]

_MIN_PR_POLL_SECONDS = 1.0

_GIT_SCRUB_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    # The child here is `gh`, not `git`: GH_REPO overrides repository resolution
    # outright (reference/owner-authority-allowlist.md documents this), and the
    # GIT_CONFIG family can inject a remote.origin.url override — either would
    # silently point the PR poll at a different repository. GH_TOKEN and
    # GH_CONFIG_DIR stay intact (auth); GH_HOST is deliberately left alone
    # (a genuine enterprise-host judgment call, recorded on the PR).
    "GH_REPO",
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
)


def _scrub_env(env):
    base = dict(env)
    for key in _GIT_SCRUB_VARS:
        base.pop(key, None)
    base.pop(ll.LEDGER_ROOT_ENV, None)
    return base

# --- wave_watch vocabulary (authoritative for this module) --------------------

REFUSAL_BATCH_INVALID = "batch-invalid"
REFUSAL_INTERVAL_INVALID = "interval-invalid"
REFUSAL_MAX_SECONDS_INVALID = "max-seconds-invalid"
REFUSAL_REPO_ROOT_INVALID = "repo-root-invalid"
REFUSAL_STORE_UNRESOLVABLE = "store-unresolvable"
REFUSAL_LEDGER_UNREADABLE = "ledger-unreadable"
REFUSAL_INTERNAL_ERROR = "internal-error"

REFUSALS = frozenset({
    REFUSAL_BATCH_INVALID,
    REFUSAL_INTERVAL_INVALID,
    REFUSAL_MAX_SECONDS_INVALID,
    REFUSAL_REPO_ROOT_INVALID,
    REFUSAL_STORE_UNRESOLVABLE,
    REFUSAL_LEDGER_UNREADABLE,
    REFUSAL_INTERNAL_ERROR,
})

EVENT_LANE_TERMINAL = "lane-terminal"
EVENT_LANE_BLOCKED = "lane-blocked"
EVENT_BUILDER_EXITED = "builder-exited"
EVENT_PR_SET_CHANGED = "pr-set-changed"
EVENT_LANE_STALE = "lane-stale"
EVENT_TIMER = "timer"

EVENTS = frozenset({
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_PR_SET_CHANGED,
    EVENT_LANE_STALE,
    EVENT_TIMER,
})

DEGRADATION_LEDGER_TORN_TAIL = "ledger-torn-tail"
DEGRADATION_LEDGER_UNREADABLE = "ledger-unreadable"
DEGRADATION_HEARTBEAT_UNREADABLE = "heartbeat-unreadable"
DEGRADATION_PID_PROBE_UNCERTAIN = "pid-probe-uncertain"
DEGRADATION_PR_SIGNAL_UNAVAILABLE = "pr-signal-unavailable"
DEGRADATION_LANE_NEVER_STAMPED = "lane-never-stamped"
DEGRADATION_PR_SIGNAL_NEVER_SAMPLED = "pr-signal-never-sampled"

DEGRADATIONS = frozenset({
    DEGRADATION_LEDGER_TORN_TAIL,
    DEGRADATION_LEDGER_UNREADABLE,
    DEGRADATION_HEARTBEAT_UNREADABLE,
    DEGRADATION_PID_PROBE_UNCERTAIN,
    DEGRADATION_PR_SIGNAL_UNAVAILABLE,
    DEGRADATION_LANE_NEVER_STAMPED,
    DEGRADATION_PR_SIGNAL_NEVER_SAMPLED,
})

EVENT_PRECEDENCE = (
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_PR_SET_CHANGED,
    EVENT_LANE_STALE,
    EVENT_TIMER,
)

# --- heartbeat cross-boundary tokens (home: heartbeat.py) ---------------------

HB_CLASS_UNKNOWN = "unknown"
HB_CLASS_TERMINAL = "terminal"
HB_CLASS_STALE = "stale"
HB_STATE_BLOCKED = "blocked"
assert HB_CLASS_UNKNOWN in hb.SWEEP_CLASSES
assert HB_CLASS_TERMINAL in hb.SWEEP_CLASSES
assert HB_CLASS_STALE in hb.SWEEP_CLASSES
assert HB_STATE_BLOCKED in hb.STATES

REASON_HEARTBEAT_MISSING = hb.REASON_HEARTBEAT_MISSING
assert REASON_HEARTBEAT_MISSING == "heartbeat-missing"


def _pid_is_live(pid):
    """True live, False exited, None uncertain. Never signals, never waits.

    Deliberately diverges from launch_ledger._child_group_is_live: this watcher
    probes ONLY the recorded leader pid via os.kill(pid, 0) and never the
    process group. launcher._default_spawn spawns builders with
    start_new_session=True (launcher.py:768), so leader-gone while the session
    group still has members is a real and intended builder-exited wake. The
    ledger's _child_group_is_live biases every uncertainty toward ALIVE because
    a false dead there causes a wrong kill/outcome record; this watcher must
    bias toward WAKING because a missed exit is the exact failure it exists to
    prevent.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def _refusal(reason, batch_id):
    return {"ok": False, "reason": reason, "batchId": batch_id}


def _valid_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_batch_id(batch_id):
    if batch_id is None or not isinstance(batch_id, str) or not batch_id.strip():
        return False
    return True


def _valid_repo_root(repo_root):
    if not isinstance(repo_root, str) or not repo_root:
        return False
    return os.path.isdir(repo_root)


def _event_result(event, batch_id, degraded, **payload):
    result = {
        "ok": True,
        "event": event,
        "batchId": batch_id,
        "degraded": sorted(degraded),
    }
    result.update(payload)
    return result


def _launch_ids(launches):
    return [entry["launchId"] for entry in launches]


def _build_also_observed(
    event, terminal_launches, blocked_launches, exited_launches, stale_launches,
):
    also = {}
    if event != EVENT_LANE_TERMINAL and terminal_launches:
        also["terminal"] = _launch_ids(terminal_launches)
    if event != EVENT_LANE_BLOCKED and blocked_launches:
        also["blocked"] = _launch_ids(blocked_launches)
    if event != EVENT_BUILDER_EXITED and exited_launches:
        also["exited"] = _launch_ids(exited_launches)
    if event != EVENT_LANE_STALE and stale_launches:
        also["stale"] = _launch_ids(stale_launches)
    return also or None


def _derive_live_lanes(
    repo_root, batch_id, env, degraded, ignore_launch_ids, ledger_observed,
):
    read_result = ll.read(repo_root, env=env)
    state = read_result["state"]
    if state in ("ok", "tornTail"):
        ledger_observed[0] = True
        if state == "tornTail":
            degraded.add(DEGRADATION_LEDGER_TORN_TAIL)
        records = read_result["records"]
    elif state == "missing":
        if ledger_observed[0]:
            degraded.add(DEGRADATION_LEDGER_UNREADABLE)
            return {}, False
        records = []
    elif state in ("unreadable", "interiorCorrupt"):
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, False
    else:
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, False

    folded = ll.fold(records)
    if not folded["ok"]:
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, False

    ignore = set(ignore_launch_ids)
    return {
        lid: info
        for lid, info in folded["launches"].items()
        if (
            info.get("batchId") == batch_id
            and not info.get("terminal")
            and lid not in ignore
        )
    }, True


def _evaluate_lane_heartbeats(repo_root, live_lanes, env, degraded):
    """One heartbeat read per lane; derive E1 terminal, E2 blocked, stale lists."""
    terminal_launches = []
    blocked_launches = []
    stale_launches = []
    for lid in sorted(live_lanes):
        hb_result = hb.read_heartbeat(repo_root, lid, env=env)
        hb_class = hb_result.get("class")
        hb_reason = hb_result.get("reason")
        if hb_class == HB_CLASS_UNKNOWN and hb_reason != REASON_HEARTBEAT_MISSING:
            degraded.add(DEGRADATION_HEARTBEAT_UNREADABLE)
            continue
        hb_state = hb_result.get("state")
        if hb_class == HB_CLASS_TERMINAL and hb_state in hb.TERMINAL_STATES:
            terminal_launches.append({
                "launchId": lid,
                "state": hb_state,
            })
        elif hb_state == HB_STATE_BLOCKED:
            blocked_launches.append({
                "launchId": lid,
                "state": HB_STATE_BLOCKED,
            })
        elif hb_class == HB_CLASS_STALE:
            stale_launches.append({
                "launchId": lid,
                "state": hb_state,
                "ageSeconds": hb_result.get("ageSeconds"),
                "staleAfterSeconds": hb_result.get("staleAfterSeconds"),
            })
    return terminal_launches, blocked_launches, stale_launches


def _lane_never_stamped_at_deadline(repo_root, live_lanes, env):
    """True when a started lane has no heartbeat stamp across the whole watch window."""
    for lid in sorted(live_lanes):
        info = live_lanes[lid]
        if not info.get("started"):
            continue
        hb_result = hb.read_heartbeat(repo_root, lid, env=env)
        if (
            hb_result.get("class") == HB_CLASS_UNKNOWN
            and hb_result.get("reason") == REASON_HEARTBEAT_MISSING
        ):
            return True
    return False


def _evaluate_pid_signals(live_lanes, stale_launches, degraded):
    """Probe each started lane once; derive builder-exited and live-stale lists."""
    exited_launches = []
    pids = []
    stale_live = []
    stale_by_id = {entry["launchId"]: entry for entry in stale_launches}
    for lid in sorted(live_lanes):
        info = live_lanes[lid]
        if not info.get("started"):
            continue
        pid = info.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            continue
        live = _pid_is_live(pid)
        if live is None:
            degraded.add(DEGRADATION_PID_PROBE_UNCERTAIN)
            continue
        if not live:
            pids.append(pid)
            exited_launches.append({"launchId": lid, "pid": pid})
        elif lid in stale_by_id:
            stale_live.append(stale_by_id[lid])
    if not exited_launches:
        exited = None
    else:
        exited = (pids, exited_launches)
    return exited, stale_live


def _parse_pr_numbers(stdout):
    try:
        parsed = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, list):
        return None
    numbers = []
    for item in parsed:
        if not isinstance(item, dict):
            return None
        number = item.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            return None
        numbers.append(number)
    return numbers


def _evaluate_pr_set_changed(
    repo_root, poll_remaining, gh_run, pr_baseline, degraded, env,
    pr_poll_ever_succeeded=None,
):
    if poll_remaining <= 0:
        return None, pr_baseline
    timeout = min(30.0, poll_remaining)
    if timeout < _MIN_PR_POLL_SECONDS:
        return None, pr_baseline
    try:
        proc = gh_run(
            _GH_PR_LIST_ARGV,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_root,
            env=_scrub_env(env),
        )
    except Exception:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None, pr_baseline

    if proc.returncode != 0:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None, pr_baseline

    numbers = _parse_pr_numbers(proc.stdout)
    if numbers is None:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None, pr_baseline

    if pr_poll_ever_succeeded is not None:
        pr_poll_ever_succeeded[0] = True

    pr_set = set(numbers)
    if pr_baseline is None:
        return None, pr_set
    if pr_set == pr_baseline:
        return None, pr_baseline
    added = sorted(pr_set - pr_baseline)
    removed = sorted(pr_baseline - pr_set)
    return {
        "prs": sorted(pr_set),
        "prsAdded": added,
        "prsRemoved": removed,
    }, pr_baseline


def _try_event_lane_terminal(
    terminal_launches, blocked_launches, exited_launches, stale_live_launches,
    batch_id, degraded,
):
    if not terminal_launches:
        return None
    payload = {
        "launchId": terminal_launches[0]["launchId"],
        "launches": terminal_launches,
    }
    also = _build_also_observed(
        EVENT_LANE_TERMINAL,
        terminal_launches,
        blocked_launches,
        exited_launches,
        stale_live_launches,
    )
    if also is not None:
        payload["alsoObserved"] = also
    return _event_result(EVENT_LANE_TERMINAL, batch_id, degraded, **payload)


def _try_event_lane_blocked(
    terminal_launches, blocked_launches, exited_launches, stale_live_launches,
    batch_id, degraded,
):
    if not blocked_launches:
        return None
    payload = {
        "launchId": blocked_launches[0]["launchId"],
        "launches": blocked_launches,
    }
    also = _build_also_observed(
        EVENT_LANE_BLOCKED,
        terminal_launches,
        blocked_launches,
        exited_launches,
        stale_live_launches,
    )
    if also is not None:
        payload["alsoObserved"] = also
    return _event_result(EVENT_LANE_BLOCKED, batch_id, degraded, **payload)


def _try_event_builder_exited(
    terminal_launches, blocked_launches, exited, exited_launches,
    stale_live_launches, batch_id, degraded,
):
    if exited is None:
        return None
    pids, exited_launches = exited
    payload = {
        "pids": pids,
        "launches": exited_launches,
    }
    also = _build_also_observed(
        EVENT_BUILDER_EXITED,
        terminal_launches,
        blocked_launches,
        exited_launches,
        stale_live_launches,
    )
    if also is not None:
        payload["alsoObserved"] = also
    return _event_result(EVENT_BUILDER_EXITED, batch_id, degraded, **payload)


def _try_event_pr_set_changed(
    pr_change, terminal_launches, blocked_launches, exited_launches,
    stale_live_launches, batch_id, degraded,
):
    if pr_change is None:
        return None
    payload = dict(pr_change)
    also = _build_also_observed(
        EVENT_PR_SET_CHANGED,
        terminal_launches,
        blocked_launches,
        exited_launches,
        stale_live_launches,
    )
    if also is not None:
        payload["alsoObserved"] = also
    return _event_result(EVENT_PR_SET_CHANGED, batch_id, degraded, **payload)


def _try_event_lane_stale(
    terminal_launches, blocked_launches, exited_launches, stale_live_launches,
    batch_id, degraded,
):
    if not stale_live_launches:
        return None
    payload = {
        "launchId": stale_live_launches[0]["launchId"],
        "launches": stale_live_launches,
    }
    also = _build_also_observed(
        EVENT_LANE_STALE,
        terminal_launches,
        blocked_launches,
        exited_launches,
        stale_live_launches,
    )
    if also is not None:
        payload["alsoObserved"] = also
    return _event_result(EVENT_LANE_STALE, batch_id, degraded, **payload)


_EVENT_TRY_HANDLERS = {
    EVENT_LANE_TERMINAL: lambda ctx: _try_event_lane_terminal(
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
        ctx["batch_id"],
        ctx["degraded"],
    ),
    EVENT_LANE_BLOCKED: lambda ctx: _try_event_lane_blocked(
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
        ctx["batch_id"],
        ctx["degraded"],
    ),
    EVENT_BUILDER_EXITED: lambda ctx: _try_event_builder_exited(
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
        ctx["batch_id"],
        ctx["degraded"],
    ),
    EVENT_PR_SET_CHANGED: lambda ctx: _try_event_pr_set_changed(
        ctx["pr_change"],
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
        ctx["batch_id"],
        ctx["degraded"],
    ),
    EVENT_LANE_STALE: lambda ctx: _try_event_lane_stale(
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
        ctx["batch_id"],
        ctx["degraded"],
    ),
}


def run(
    repo_root,
    batch_id,
    *,
    max_seconds=2400,
    interval_seconds=60,
    env=None,
    gh_run=None,
    monotonic=None,
    sleep=None,
    ignore_launch_ids=(),
):
    """Watch one batch until the first event. Returns the result dict; never raises."""
    batch_for_refusal = batch_id if isinstance(batch_id, str) else None
    try:
        if env is None:
            env = os.environ
        if gh_run is None:
            gh_run = subprocess.run
        if monotonic is None:
            monotonic = time.monotonic
        if sleep is None:
            sleep = time.sleep

        if not _valid_batch_id(batch_id):
            return _refusal(REFUSAL_BATCH_INVALID, batch_for_refusal)
        batch_id = batch_id.strip()

        if not _valid_positive_int(interval_seconds):
            return _refusal(REFUSAL_INTERVAL_INVALID, batch_id)
        if not _valid_positive_int(max_seconds):
            return _refusal(REFUSAL_MAX_SECONDS_INVALID, batch_id)
        if not _valid_repo_root(repo_root):
            return _refusal(REFUSAL_REPO_ROOT_INVALID, batch_id)

        ledger_path_result = ll.ledger_path(repo_root, env=env)
        if not ledger_path_result["ok"]:
            return _refusal(REFUSAL_STORE_UNRESOLVABLE, batch_id)

        start = monotonic()
        deadline = start + max_seconds
        tick = 0
        pr_baseline = None
        degraded = set()
        first_tick = True
        ledger_observed = [False]
        pr_poll_ever_succeeded = [False]

        while True:
            is_first_loop = first_tick
            loop_start_remaining = deadline - monotonic()

            live_lanes, ledger_readable = _derive_live_lanes(
                repo_root, batch_id, env, degraded, ignore_launch_ids,
                ledger_observed,
            )

            if first_tick and not ledger_readable:
                return _refusal(REFUSAL_LEDGER_UNREADABLE, batch_id)
            first_tick = False

            terminal_launches, blocked_launches, stale_launches = (
                _evaluate_lane_heartbeats(
                    repo_root, live_lanes, env, degraded,
                )
            )
            exited, stale_live_launches = _evaluate_pid_signals(
                live_lanes, stale_launches, degraded,
            )
            exited_launches = exited[1] if exited is not None else []

            event_ctx = {
                "terminal_launches": terminal_launches,
                "blocked_launches": blocked_launches,
                "exited": exited,
                "exited_launches": exited_launches,
                "stale_live_launches": stale_live_launches,
                "pr_change": None,
                "batch_id": batch_id,
                "degraded": degraded,
            }

            for event in EVENT_PRECEDENCE:
                if event == EVENT_TIMER:
                    if monotonic() >= deadline:
                        live_lanes, deadline_readable = _derive_live_lanes(
                            repo_root, batch_id, env, degraded,
                            ignore_launch_ids, ledger_observed,
                        )
                        if not deadline_readable:
                            return _refusal(
                                REFUSAL_LEDGER_UNREADABLE, batch_id,
                            )
                        if _lane_never_stamped_at_deadline(
                            repo_root, live_lanes, env,
                        ):
                            degraded.add(DEGRADATION_LANE_NEVER_STAMPED)
                        if not pr_poll_ever_succeeded[0]:
                            degraded.add(DEGRADATION_PR_SIGNAL_NEVER_SAMPLED)
                        return _event_result(EVENT_TIMER, batch_id, degraded)
                    break

                if event == EVENT_PR_SET_CHANGED:
                    poll_remaining = deadline - monotonic()
                    if is_first_loop:
                        ideal_remaining = float(max_seconds)
                        if ideal_remaining - loop_start_remaining < 0.01:
                            if poll_remaining < _MIN_PR_POLL_SECONDS:
                                poll_remaining = ideal_remaining
                            elif ideal_remaining - poll_remaining < 0.01:
                                poll_remaining = ideal_remaining
                    pr_change, pr_baseline = _evaluate_pr_set_changed(
                        repo_root, poll_remaining, gh_run, pr_baseline,
                        degraded, env, pr_poll_ever_succeeded,
                    )
                    event_ctx["pr_change"] = pr_change

                handler = _EVENT_TRY_HANDLERS.get(event)
                if handler is None:
                    continue
                result = handler(event_ctx)
                if result is not None:
                    return result

            tick = max(
                tick + 1,
                math.ceil((monotonic() - start) / interval_seconds),
            )
            target = min(start + tick * interval_seconds, deadline)
            naptime = target - monotonic()
            if naptime > 0:
                sleep(naptime)
    except Exception as exc:
        result = _refusal(REFUSAL_INTERNAL_ERROR, batch_for_refusal)
        result["detail"] = type(exc).__name__
        return result


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="wave watcher")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--repo-root", required=True)
    run_parser.add_argument("--batch", required=True)
    run_parser.add_argument("--max-seconds", type=int, default=2400)
    run_parser.add_argument("--interval-seconds", type=int, default=60)
    run_parser.add_argument(
        "--ignore-launch",
        action="append",
        default=[],
        dest="ignore_launch_ids",
        metavar="launchId",
        help="exclude launch id from lane enumeration (repeatable)",
    )
    args = ap.parse_args(argv[1:])
    if args.cmd != "run":
        return 1
    result = run(
        args.repo_root,
        args.batch,
        max_seconds=args.max_seconds,
        interval_seconds=args.interval_seconds,
        ignore_launch_ids=tuple(args.ignore_launch_ids),
    )
    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
