#!/usr/bin/env python3
"""Ledger-driven single-shot wave watcher (#982).

Watch one launch batch until the first qualifying event. stdlib only.

Contract:
- Refusals (ok=False): batch-invalid, interval-invalid, max-seconds-invalid,
  repo-root-invalid, store-unresolvable, ledger-unreadable, internal-error.
- Events (ok=True): lane-terminal, lane-blocked, builder-exited, pr-set-changed,
  timer.
- Degradations (non-fatal): ledger-torn-tail, ledger-unreadable,
  heartbeat-unreadable, pid-probe-uncertain, pr-signal-unavailable.
- Precedence: lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >
  pr-set-changed (E4) > timer (E5).
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
EVENT_TIMER = "timer"

EVENTS = frozenset({
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_PR_SET_CHANGED,
    EVENT_TIMER,
})

DEGRADATION_LEDGER_TORN_TAIL = "ledger-torn-tail"
DEGRADATION_LEDGER_UNREADABLE = "ledger-unreadable"
DEGRADATION_HEARTBEAT_UNREADABLE = "heartbeat-unreadable"
DEGRADATION_PID_PROBE_UNCERTAIN = "pid-probe-uncertain"
DEGRADATION_PR_SIGNAL_UNAVAILABLE = "pr-signal-unavailable"

DEGRADATIONS = frozenset({
    DEGRADATION_LEDGER_TORN_TAIL,
    DEGRADATION_LEDGER_UNREADABLE,
    DEGRADATION_HEARTBEAT_UNREADABLE,
    DEGRADATION_PID_PROBE_UNCERTAIN,
    DEGRADATION_PR_SIGNAL_UNAVAILABLE,
})

# --- heartbeat cross-boundary tokens (home: heartbeat.py) ---------------------

HB_CLASS_UNKNOWN = "unknown"
HB_CLASS_TERMINAL = "terminal"
HB_STATE_BLOCKED = "blocked"
assert HB_CLASS_UNKNOWN in hb.SWEEP_CLASSES
assert HB_CLASS_TERMINAL in hb.SWEEP_CLASSES
assert HB_STATE_BLOCKED in hb.STATES

# heartbeat.py:373 uses this bare literal with no REASON_* constant at the
# producer — cannot import a home; pin locally so consumers do not scatter it.
REASON_HEARTBEAT_MISSING = "heartbeat-missing"


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


def _build_also_observed(event, terminal_launches, blocked_launches, exited_launches):
    also = {}
    if event != EVENT_LANE_TERMINAL and terminal_launches:
        also["terminal"] = _launch_ids(terminal_launches)
    if event != EVENT_LANE_BLOCKED and blocked_launches:
        also["blocked"] = _launch_ids(blocked_launches)
    if event != EVENT_BUILDER_EXITED and exited_launches:
        also["exited"] = _launch_ids(exited_launches)
    return also or None


def _derive_live_lanes(repo_root, batch_id, env, degraded, ignore_launch_ids):
    read_result = ll.read(repo_root, env=env)
    state = read_result["state"]
    if state in ("ok", "tornTail"):
        if state == "tornTail":
            degraded.add(DEGRADATION_LEDGER_TORN_TAIL)
        records = read_result["records"]
    elif state == "missing":
        records = []
    elif state in ("unreadable", "interiorCorrupt"):
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, False, state
    else:
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, False, state

    folded = ll.fold(records)
    if not folded["ok"]:
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, False, state

    ignore = set(ignore_launch_ids)
    return {
        lid: info
        for lid, info in folded["launches"].items()
        if (
            info.get("batchId") == batch_id
            and not info.get("terminal")
            and lid not in ignore
        )
    }, True, state


def _evaluate_lane_heartbeats(repo_root, live_lanes, env, degraded):
    """One heartbeat read per lane; derive E1 terminal and E2 blocked lists."""
    terminal_launches = []
    blocked_launches = []
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
    return terminal_launches, blocked_launches


def _evaluate_builder_exited(live_lanes, degraded):
    exited_launches = []
    pids = []
    for lid in sorted(live_lanes):
        info = live_lanes[lid]
        if not info.get("started"):
            continue
        # Only the latest attempt's pid is probed; info['pids'] history is
        # deliberately ignored because prior attempt pids are dead by construction
        # on a retried lane.
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
    if not exited_launches:
        return None
    return pids, exited_launches


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
    repo_root, deadline, monotonic, gh_run, pr_baseline, degraded,
):
    remaining = deadline - monotonic()
    timeout = max(1, min(30, int(remaining)))
    try:
        proc = gh_run(
            _GH_PR_LIST_ARGV,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_root,
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

        while True:
            live_lanes, ledger_readable, ledger_state = _derive_live_lanes(
                repo_root, batch_id, env, degraded, ignore_launch_ids,
            )

            if first_tick and not ledger_readable:
                if ledger_state == "interiorCorrupt" or ledger_state in ("ok", "tornTail"):
                    return _refusal(REFUSAL_LEDGER_UNREADABLE, batch_id)
            first_tick = False

            terminal_launches, blocked_launches = _evaluate_lane_heartbeats(
                repo_root, live_lanes, env, degraded,
            )
            exited = _evaluate_builder_exited(live_lanes, degraded)
            exited_launches = exited[1] if exited is not None else []

            if terminal_launches:
                payload = {
                    "launchId": terminal_launches[0]["launchId"],
                    "launches": terminal_launches,
                }
                also = _build_also_observed(
                    EVENT_LANE_TERMINAL,
                    terminal_launches,
                    blocked_launches,
                    exited_launches,
                )
                if also is not None:
                    payload["alsoObserved"] = also
                return _event_result(
                    EVENT_LANE_TERMINAL, batch_id, degraded, **payload,
                )

            if blocked_launches:
                payload = {
                    "launchId": blocked_launches[0]["launchId"],
                    "launches": blocked_launches,
                }
                also = _build_also_observed(
                    EVENT_LANE_BLOCKED,
                    terminal_launches,
                    blocked_launches,
                    exited_launches,
                )
                if also is not None:
                    payload["alsoObserved"] = also
                return _event_result(
                    EVENT_LANE_BLOCKED, batch_id, degraded, **payload,
                )

            if exited is not None:
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
                )
                if also is not None:
                    payload["alsoObserved"] = also
                return _event_result(
                    EVENT_BUILDER_EXITED, batch_id, degraded, **payload,
                )

            pr_change, pr_baseline = _evaluate_pr_set_changed(
                repo_root, deadline, monotonic, gh_run, pr_baseline, degraded,
            )
            if pr_change is not None:
                return _event_result(
                    EVENT_PR_SET_CHANGED,
                    batch_id,
                    degraded,
                    **pr_change,
                )

            if monotonic() >= deadline:
                if not ledger_readable:
                    return _refusal(REFUSAL_LEDGER_UNREADABLE, batch_id)
                return _event_result(EVENT_TIMER, batch_id, degraded)

            tick += 1
            target = min(start + tick * interval_seconds, deadline)
            naptime = target - monotonic()
            if naptime > 0:
                sleep(naptime)
    except Exception:
        return _refusal(REFUSAL_INTERNAL_ERROR, batch_for_refusal)


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
