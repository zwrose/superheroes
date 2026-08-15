#!/usr/bin/env python3
"""Ledger-driven wave watcher — run is single-shot; loop re-arms internally (#982).

Watch one launch batch until the first qualifying event. stdlib only.

Contract:
- Refusals (ok=False): batch-invalid, interval-invalid, max-seconds-invalid,
  max-total-seconds-invalid, repo-root-invalid, store-unresolvable,
  ledger-unreadable, internal-error.
- Events (ok=True): lane-terminal, lane-blocked, builder-exited, pr-set-changed,
  lane-stale, timer.
- Degradations (non-fatal): ledger-torn-tail, ledger-unreadable,
  heartbeat-unreadable, pid-probe-uncertain, pr-signal-unavailable,
  lane-never-stamped, log-unwritable.
- Precedence: lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >
  pr-set-changed (E4) > lane-stale (E5) > timer (E6).
- PRECEDENCE: ordered tuple (lane-terminal, lane-blocked, builder-exited,
  pr-set-changed, lane-stale, timer) from which run()'s return-arm order is
  derived.
- loop: re-arms run() until an actionable event or refusal; threads
  ledger_observed and pr_state across arms.
- gh child environment is scrubbed of repository-routing variables
  (_GIT_SCRUB_VARS: GH_REPO, the GIT_CONFIG* family, the GIT_DIR/GIT_WORK_TREE
  family) plus the ledger-root env var, so a poll can never be redirected at
  another repository; GH_TOKEN/GH_CONFIG_DIR are preserved for auth and GH_HOST
  is deliberately left alone.
- Read-only over the store: the watcher never writes, never mutates ledger or
  heartbeat state, and never signals any process — pid liveness is
  os.kill(pid, 0) probing only.
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
import os
import stat
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

_MIN_PR_POLL_SECONDS = 1.0


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
REFUSAL_MAX_TOTAL_SECONDS_INVALID = "max-total-seconds-invalid"
REFUSAL_REPO_ROOT_INVALID = "repo-root-invalid"
REFUSAL_STORE_UNRESOLVABLE = "store-unresolvable"
REFUSAL_LEDGER_UNREADABLE = "ledger-unreadable"
REFUSAL_INTERNAL_ERROR = "internal-error"

REFUSALS = frozenset({
    REFUSAL_BATCH_INVALID,
    REFUSAL_INTERVAL_INVALID,
    REFUSAL_MAX_SECONDS_INVALID,
    REFUSAL_MAX_TOTAL_SECONDS_INVALID,
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

PRECEDENCE = (
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_PR_SET_CHANGED,
    EVENT_LANE_STALE,
    EVENT_TIMER,
)

DEGRADATION_LEDGER_TORN_TAIL = "ledger-torn-tail"
DEGRADATION_LEDGER_UNREADABLE = "ledger-unreadable"
DEGRADATION_HEARTBEAT_UNREADABLE = "heartbeat-unreadable"
DEGRADATION_PID_PROBE_UNCERTAIN = "pid-probe-uncertain"
DEGRADATION_PR_SIGNAL_UNAVAILABLE = "pr-signal-unavailable"
DEGRADATION_LANE_NEVER_STAMPED = "lane-never-stamped"
DEGRADATION_LOG_UNWRITABLE = "log-unwritable"

DEGRADATIONS = frozenset({
    DEGRADATION_LEDGER_TORN_TAIL,
    DEGRADATION_LEDGER_UNREADABLE,
    DEGRADATION_HEARTBEAT_UNREADABLE,
    DEGRADATION_PID_PROBE_UNCERTAIN,
    DEGRADATION_PR_SIGNAL_UNAVAILABLE,
    DEGRADATION_LANE_NEVER_STAMPED,
    DEGRADATION_LOG_UNWRITABLE,
})

# --- heartbeat cross-boundary tokens (home: heartbeat.py) ---------------------

HB_CLASS_UNKNOWN = "unknown"
HB_CLASS_TERMINAL = "terminal"
HB_CLASS_STALE = "stale"
HB_STATE_BLOCKED = "blocked"
assert HB_CLASS_UNKNOWN in hb.SWEEP_CLASSES
assert HB_CLASS_TERMINAL in hb.SWEEP_CLASSES
assert HB_CLASS_STALE in hb.SWEEP_CLASSES
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


def _refusal(reason, batch_id, detail=None):
    result = {"ok": False, "reason": reason, "batchId": batch_id}
    if detail is not None:
        result["detail"] = detail
    return result


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


def _apply_pr_signal_degradation(degraded, pr_arm_reached, pr_state):
    if pr_arm_reached and pr_state[0] is None:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)


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
        if hb_class == HB_CLASS_UNKNOWN and hb_reason == REASON_HEARTBEAT_MISSING:
            if live_lanes[lid].get("started"):
                degraded.add(DEGRADATION_LANE_NEVER_STAMPED)
            continue
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
    repo_root, deadline, monotonic, gh_run, pr_state, degraded, env,
):
    remaining = deadline - monotonic()
    # Skip polls we cannot give a viable window — a sub-second timeout would
    # manufacture pr-signal-unavailable (R7). No baseline from a doomed poll
    # either; R6 discloses unsampled signal when pr_state is still None.
    if remaining < _MIN_PR_POLL_SECONDS:
        return None
    timeout = min(30.0, remaining)
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
        return None

    if proc.returncode != 0:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None

    numbers = _parse_pr_numbers(proc.stdout)
    if numbers is None:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None

    pr_set = set(numbers)
    if pr_state[0] is None:
        pr_state[0] = pr_set
        return None
    if pr_set == pr_state[0]:
        return None
    added = sorted(pr_set - pr_state[0])
    removed = sorted(pr_state[0] - pr_set)
    return {
        "prs": sorted(pr_set),
        "prsAdded": added,
        "prsRemoved": removed,
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
    ledger_observed=None,
    pr_state=None,
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
        if ledger_observed is None:
            ledger_observed = [False]
        if pr_state is None:
            pr_state = [None]

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
        degraded = set()
        first_tick = True
        pr_arm_reached = False

        while True:
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

            def _terminal_payload():
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
                return payload

            def _blocked_payload():
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
                return payload

            def _exited_payload():
                if exited is None:
                    return None
                pids, exited_list = exited
                payload = {
                    "pids": pids,
                    "launches": exited_list,
                }
                also = _build_also_observed(
                    EVENT_BUILDER_EXITED,
                    terminal_launches,
                    blocked_launches,
                    exited_list,
                    stale_live_launches,
                )
                if also is not None:
                    payload["alsoObserved"] = also
                return payload

            def _pr_payload():
                nonlocal pr_arm_reached
                pr_arm_reached = True
                pr_change = _evaluate_pr_set_changed(
                    repo_root, deadline, monotonic, gh_run, pr_state,
                    degraded, env,
                )
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
                return payload

            def _stale_payload():
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
                return payload

            candidates = {
                EVENT_LANE_TERMINAL: _terminal_payload,
                EVENT_LANE_BLOCKED: _blocked_payload,
                EVENT_BUILDER_EXITED: _exited_payload,
                EVENT_PR_SET_CHANGED: _pr_payload,
                EVENT_LANE_STALE: _stale_payload,
            }

            for event in PRECEDENCE:
                if event not in candidates:
                    continue
                payload = candidates[event]()
                if payload is not None:
                    _apply_pr_signal_degradation(degraded, pr_arm_reached, pr_state)
                    return _event_result(
                        event, batch_id, degraded, **payload,
                    )

            if monotonic() >= deadline:
                _, deadline_readable = _derive_live_lanes(
                    repo_root, batch_id, env, degraded, ignore_launch_ids,
                    ledger_observed,
                )
                if not deadline_readable:
                    return _refusal(REFUSAL_LEDGER_UNREADABLE, batch_id)
                _apply_pr_signal_degradation(degraded, pr_arm_reached, pr_state)
                return _event_result(EVENT_TIMER, batch_id, degraded)

            now = monotonic()
            elapsed = now - start
            tick = max(tick + 1, int(elapsed // interval_seconds) + 1)
            target = min(start + tick * interval_seconds, deadline)
            naptime = target - monotonic()
            if naptime > 0:
                sleep(naptime)
    except Exception as exc:
        return _refusal(
            REFUSAL_INTERNAL_ERROR, batch_for_refusal, detail=type(exc).__name__,
        )


def _append_watch_log(log_path, entry):
    """Append one JSON line; refuse symlinks, FIFOs, and other non-regular files."""
    line = json.dumps(entry, sort_keys=True) + "\n"
    encoded = line.encode("utf-8")
    fd = None
    try:
        fd = os.open(
            log_path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return False
        offset = 0
        while offset < len(encoded):
            written = os.write(fd, encoded[offset:])
            if written == 0:
                return False
            offset += written
        return True
    except OSError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


def loop(
    repo_root,
    batch_id,
    *,
    max_seconds=2400,
    interval_seconds=60,
    max_total_seconds=None,
    log_path=None,
    env=None,
    gh_run=None,
    monotonic=None,
    sleep=None,
    ignore_launch_ids=(),
    run_fn=None,
):
    """Re-arm run() until an actionable event or refusal. Never raises."""
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
        if run_fn is None:
            run_fn = run

        if not _valid_batch_id(batch_id):
            result = _refusal(REFUSAL_BATCH_INVALID, batch_for_refusal)
            result["arms"] = 0
            return result

        batch_id = batch_id.strip()

        if max_total_seconds is not None and not _valid_positive_int(max_total_seconds):
            result = _refusal(REFUSAL_MAX_TOTAL_SECONDS_INVALID, batch_id)
            result["arms"] = 0
            return result

        if not _valid_positive_int(interval_seconds):
            result = _refusal(REFUSAL_INTERVAL_INVALID, batch_id)
            result["arms"] = 0
            return result
        if not _valid_positive_int(max_seconds):
            result = _refusal(REFUSAL_MAX_SECONDS_INVALID, batch_id)
            result["arms"] = 0
            return result

        ledger_observed = [False]
        pr_state = [None]
        loop_degraded = set()
        start = monotonic()
        last_result = None
        arm_count = 0

        while True:
            if max_total_seconds is not None:
                remaining = max_total_seconds - (monotonic() - start)
                if remaining < 1 and last_result is not None:
                    break
                arm_max = max(1, min(max_seconds, int(remaining)))
            else:
                arm_max = max_seconds

            arm_count += 1
            result = run_fn(
                repo_root,
                batch_id,
                max_seconds=arm_max,
                interval_seconds=interval_seconds,
                env=env,
                gh_run=gh_run,
                monotonic=monotonic,
                sleep=sleep,
                ignore_launch_ids=ignore_launch_ids,
                ledger_observed=ledger_observed,
                pr_state=pr_state,
            )

            if result.get("ok"):
                loop_degraded.update(result.get("degraded", []))

            if not result.get("ok"):
                result["arms"] = arm_count
                result["degraded"] = sorted(
                    set(result.get("degraded", [])) | loop_degraded,
                )
                return result

            if result["event"] != EVENT_TIMER:
                result["arms"] = arm_count
                result["degraded"] = sorted(
                    set(result.get("degraded", [])) | loop_degraded,
                )
                return result

            last_result = result
            if log_path is not None:
                if not _append_watch_log(log_path, {
                    "arm": arm_count,
                    "elapsedSeconds": round(monotonic() - start, 3),
                    "result": result,
                }):
                    loop_degraded.add(DEGRADATION_LOG_UNWRITABLE)

            if max_total_seconds is None:
                continue

        if last_result is None:
            result = _refusal(REFUSAL_INTERNAL_ERROR, batch_id)
            result["arms"] = 0
            return result

        last_result["arms"] = arm_count
        last_result["degraded"] = sorted(
            set(last_result.get("degraded", [])) | loop_degraded,
        )
        return last_result
    except Exception as exc:
        result = _refusal(
            REFUSAL_INTERNAL_ERROR, batch_for_refusal, detail=type(exc).__name__,
        )
        result["arms"] = 0
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
    loop_parser = sub.add_parser("loop")
    loop_parser.add_argument("--repo-root", required=True)
    loop_parser.add_argument("--batch", required=True)
    loop_parser.add_argument("--max-seconds", type=int, default=2400)
    loop_parser.add_argument("--interval-seconds", type=int, default=60)
    loop_parser.add_argument("--max-total-seconds", type=int, default=None)
    loop_parser.add_argument("--log", default=None, dest="log_path")
    loop_parser.add_argument(
        "--ignore-launch",
        action="append",
        default=[],
        dest="ignore_launch_ids",
        metavar="launchId",
        help="exclude launch id from lane enumeration (repeatable)",
    )
    args = ap.parse_args(argv[1:])
    if args.cmd == "run":
        result = run(
            args.repo_root,
            args.batch,
            max_seconds=args.max_seconds,
            interval_seconds=args.interval_seconds,
            ignore_launch_ids=tuple(args.ignore_launch_ids),
        )
    elif args.cmd == "loop":
        result = loop(
            args.repo_root,
            args.batch,
            max_seconds=args.max_seconds,
            interval_seconds=args.interval_seconds,
            max_total_seconds=args.max_total_seconds,
            log_path=args.log_path,
            ignore_launch_ids=tuple(args.ignore_launch_ids),
        )
    else:
        return 1
    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
