#!/usr/bin/env python3
"""Ledger-driven wave watcher (#982).

Watch one launch batch until the first qualifying event. stdlib only.

Verbs:
- run: single-shot watch — one arm, one result.
- loop: re-arms run internally until a refusal or a non-timer event; the arming
  shape for a background advisor call per batch. loop owns one set of state
  cells (ledger_observed, pr_state, pr_sampled) threaded through every arm so
  store loss across an arm boundary is not mistaken for benign pre-arm silence,
  PR deltas across an arm boundary are not absorbed into a fresh baseline, and
  a prior arm's successful PR poll is not forgotten on the next arm's timer.

Contract:
- Refusals (ok=False): batch-invalid, max-total-seconds-invalid,
  ignore-event-invalid, interval-invalid, max-seconds-invalid, repo-root-invalid,
  store-unresolvable, ledger-unreadable, internal-error.
- Events (ok=True): lane-terminal, lane-blocked, builder-exited, pr-set-changed,
  lane-stale, timer.
- Degradations (non-fatal): ledger-torn-tail, ledger-unreadable,
  heartbeat-unreadable, pid-probe-uncertain, pr-signal-unavailable,
  lane-never-stamped, pr-signal-never-sampled, log-unwritable,
  transcript-ambiguous.
- gh child env-scrubbing: ambient git/GH routing variables in _GIT_SCRUB_VARS
  are stripped via _scrub_env before the gh subprocess runs.
- Deadline-bound polling: no gh poll starts when remaining time is below
  _MIN_PR_POLL_SECONDS; each poll's timeout is min(30.0, remaining).
- Precedence: lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >
  pr-set-changed (E4) > lane-stale (E5) > timer (E6).
- lane-stale: a lane whose heartbeat class is stale, whose latest recorded pid is
  positively live, and whose session transcript did NOT get written inside its own
  promise window — a wedged builder alive but frozen past its own
  staleAfterSeconds promise.
- Transcript second chance (#1023): before emitting lane-stale, the lane's session
  transcript is resolved from the session id the launcher recorded on the launch
  record, and a transcript written within staleAfterSeconds suppresses the event —
  that lane is working through a long step, not wedged. The suppression is recorded
  on the arm's result under staleSuppressed (note stale-suppressed-transcript-fresh),
  so the loop stays honest about what it saw instead of going quiet. Every
  unresolvable read — no session id on the ledger record, no transcript on disk,
  two-or-more transcripts with the same id, an unreadable projects directory, a
  future-dated mtime — leaves the lane STALE: the check fails toward the alert,
  never toward silence. Ambiguity additionally records transcript-ambiguous.
- Transcript identity: a transcript vouches for a lane only when the launch record
  carries that lane's session id and exactly one regular file named
  <sessionId>.jsonl resolves under the host config root's projects tree. The
  watcher stat's only — it never reads transcript contents. Exactly one config root
  is searched (the CLAUDE_CONFIG_DIR override outright, else ~/.claude), and a
  symlinked entry is never followed.
- staleSuppressed: accumulated across an arm's ticks, keyed by launchId, and cleared
  for a lane the moment a later tick finds it still stale. It rides EVERY result of
  that arm including timer, which is what puts it in loop's --log line.
- Observed latch: once the ledger has returned ok or tornTail, a subsequent
  missing read is blind (store loss), not benign pre-arm silence.
- When a lane's heartbeat is unreadable its higher-precedence E1/E2 state is
  UNKNOWN, so a lower-precedence event may be reported for it and the
  heartbeat-unreadable degradation token discloses that uncertainty.
- alsoObserved: on a result that carries a payload, co-occurring lower-precedence
  lane signals from the same interval are included under alsoObserved (launchIds
  only). A timer result carries no payload and no alsoObserved, so a lane whose
  only signal is suppressed is not visible in that arm's output.
- ignore-launch: caller-supplied launch ids excluded from lane enumeration so
  an already-handled lane that cannot be terminalized does not re-fire.
- ignore-events: caller-supplied (launchId, event) pairs suppress that event
  for that lane only — lane-terminal, lane-blocked, builder-exited, and
  lane-stale are suppressible; pr-set-changed and timer are not. Suppression
  affects actionability only.
- Pid liveness: probes ONLY the recorded leader pid (never the process group).
  launch_ledger._child_group_is_live biases uncertain toward ALIVE because a
  false dead there causes a wrong kill/outcome record; this watcher biases
  toward WAKING because a missed exit is the failure it exists to prevent.
  launcher._default_spawn uses start_new_session=True, so leader-gone/group-alive
  is a real and intended builder-exited wake. Only info['pid'] (latest attempt)
  is probed; info['pids'] history is ignored because prior attempt pids are dead
  by construction on a retried lane.
- max_total_seconds (loop only): a re-arm bound, not a hard kill — the loop will
  not start a new arm once the total is reached; the final arm's window is
  max(1, min(max_seconds, int(remaining))). The loop may therefore overrun the
  total by the final arm's rounding plus one evaluation pass.
- arms (loop only): count of run arms actually started in this loop call; rides
  loop results only (ok and refusal), never run results.
- Sub-second windows never poll gh: the poll guard is timeout < _MIN_PR_POLL_SECONDS
  (1.0), strict — so a window of exactly one second DOES poll (with timeout=1.0), and
  only a window shorter than one second is skipped. (Loop's final truncated arm polls
  when at least one full second remains.)
- Standing guarantees: the watcher is read-only over the store (it never
  writes, never mutates ledger or heartbeat state) and it never signals any
  process (pid liveness is os.kill(pid, 0) probing only).
"""
import argparse
import json
import math
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

_MIN_PR_POLL_SECONDS = 1.0

# --- session-transcript liveness oracle (#1023) -------------------------------
#
# The host writes one append-only JSONL transcript per session under
# <config-dir>/projects/<bucket>/<session-id>.jsonl. The launcher mints the
# builder's session id, passes it on the claude argv, and records it on the lane's
# reserved ledger record — so the watcher resolves the transcript by identity,
# never by bucket mangling or transcript contents. Transcript mtime is the only
# liveness oracle that held on both measured hosts.
_TRANSCRIPT_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
_TRANSCRIPT_DEFAULT_CONFIG_DIR = "~/.claude"
_PROJECTS_DIR_NAME = "projects"
_TRANSCRIPT_SUFFIX = ".jsonl"

NOTE_STALE_SUPPRESSED_TRANSCRIPT_FRESH = "stale-suppressed-transcript-fresh"
# The result key is part of the same wire contract as the note token, so it gets the
# same authoritative definition — a doc-drift guard that compared two hardcoded
# literals would still pass if the runtime key were renamed underneath it.
RESULT_KEY_STALE_SUPPRESSED = "staleSuppressed"

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
REFUSAL_MAX_TOTAL_SECONDS_INVALID = "max-total-seconds-invalid"
REFUSAL_IGNORE_EVENT_INVALID = "ignore-event-invalid"
REFUSAL_INTERVAL_INVALID = "interval-invalid"
REFUSAL_MAX_SECONDS_INVALID = "max-seconds-invalid"
REFUSAL_REPO_ROOT_INVALID = "repo-root-invalid"
REFUSAL_STORE_UNRESOLVABLE = "store-unresolvable"
REFUSAL_LEDGER_UNREADABLE = "ledger-unreadable"
REFUSAL_INTERNAL_ERROR = "internal-error"

REFUSALS = frozenset({
    REFUSAL_BATCH_INVALID,
    REFUSAL_MAX_TOTAL_SECONDS_INVALID,
    REFUSAL_IGNORE_EVENT_INVALID,
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
DEGRADATION_LOG_UNWRITABLE = "log-unwritable"
DEGRADATION_TRANSCRIPT_AMBIGUOUS = "transcript-ambiguous"

DEGRADATIONS = frozenset({
    DEGRADATION_LEDGER_TORN_TAIL,
    DEGRADATION_LEDGER_UNREADABLE,
    DEGRADATION_HEARTBEAT_UNREADABLE,
    DEGRADATION_PID_PROBE_UNCERTAIN,
    DEGRADATION_PR_SIGNAL_UNAVAILABLE,
    DEGRADATION_LANE_NEVER_STAMPED,
    DEGRADATION_PR_SIGNAL_NEVER_SAMPLED,
    DEGRADATION_LOG_UNWRITABLE,
    DEGRADATION_TRANSCRIPT_AMBIGUOUS,
})

EVENT_PRECEDENCE = (
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_PR_SET_CHANGED,
    EVENT_LANE_STALE,
    EVENT_TIMER,
)

_SUPPRESSIBLE_EVENTS = frozenset({
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_LANE_STALE,
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


def _refusal(reason, batch_id, *, arms=None):
    result = {"ok": False, "reason": reason, "batchId": batch_id}
    if arms is not None:
        result["arms"] = arms
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


def _validate_ignore_events(ignore_events, batch_id, *, arms=None):
    for item in ignore_events:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
        launch_id, event = item[0], item[1]
        if not isinstance(launch_id, str) or not launch_id:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
        if not isinstance(event, str) or not event:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
        if event not in _SUPPRESSIBLE_EVENTS:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
    return None


def _ignore_events_set(ignore_events):
    return frozenset((item[0], item[1]) for item in ignore_events)


def _filter_suppressed_launches(launches, event, ignore_set):
    if not ignore_set:
        return launches
    return [
        entry for entry in launches
        if (entry["launchId"], event) not in ignore_set
    ]


def _event_result(event, batch_id, degraded, stale_suppressed=None, **payload):
    result = {
        "ok": True,
        "event": event,
        "batchId": batch_id,
        "degraded": sorted(degraded),
    }
    result.update(payload)
    if stale_suppressed:
        result[RESULT_KEY_STALE_SUPPRESSED] = sorted(
            stale_suppressed, key=lambda entry: entry["launchId"],
        )
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


def _expand_home(path, env):
    """expanduser against the SUPPLIED env's HOME, not the ambient process env."""
    if not path.startswith("~"):
        return path
    home = env.get("HOME")
    if not isinstance(home, str) or not home:
        return os.path.expanduser(path)
    if path == "~" or path.startswith("~" + os.sep):
        return home + path[1:]
    return os.path.expanduser(path)


def _transcript_config_dirs(env):
    """The host config dir to search — EXACTLY ONE.

    The override wins outright rather than being searched alongside the default: the
    launcher passes CLAUDE_CONFIG_DIR through to the builder, so when it is set, a
    same-named transcript under the default root belongs to some OTHER session and
    must never be allowed to vouch for this lane.
    """
    configured = env.get(_TRANSCRIPT_CONFIG_DIR_ENV)
    if isinstance(configured, str) and configured.strip():
        return [_expand_home(configured.strip(), env)]
    return [_expand_home(_TRANSCRIPT_DEFAULT_CONFIG_DIR, env)]


def _session_transcript_mtime(session_id, env):
    """(mtime, ambiguous) for the lane's own transcript, by recorded session id."""
    if not isinstance(session_id, str) or not session_id.strip():
        return None, False
    if os.sep in session_id or "/" in session_id or ".." in session_id:
        return None, False

    filename = session_id + _TRANSCRIPT_SUFFIX
    matches = []
    for root in _transcript_config_dirs(env):
        projects_root = os.path.join(root, _PROJECTS_DIR_NAME)
        try:
            bucket_entries = list(os.scandir(projects_root))
        except OSError:
            return None, False
        for bucket_entry in bucket_entries:
            try:
                if not bucket_entry.is_dir(follow_symlinks=False):
                    continue
            except (FileNotFoundError, NotADirectoryError):
                continue
            except OSError:
                return None, False
            candidate = os.path.join(bucket_entry.path, filename)
            try:
                st = os.stat(candidate, follow_symlinks=False)
            except (FileNotFoundError, NotADirectoryError):
                continue
            except OSError:
                return None, False
            if not stat.S_ISREG(st.st_mode):
                continue
            matches.append(st.st_mtime)

    if len(matches) == 0:
        return None, False
    if len(matches) >= 2:
        return None, True
    return matches[0], False


def _stale_second_chance(
    stale_live, live_lanes, env, *, now=None, degraded=None,
    session_transcript_mtime=None,
):
    """Split pid-live stale lanes into (still stale, suppressed as transcript-fresh).

    A lane whose transcript was written inside its own promise window is working
    through a long step, not wedged (#1023) — a pid-live lane already passed the
    liveness half of the pair, and a fresh transcript is the semantic half.

    Fail-toward-alert is the invariant: no session id, an unresolvable transcript,
    ambiguity, an unusable promise, a stale transcript, or a future-dated transcript
    all leave the lane in the still-stale list. Only a positively fresh transcript
    suppresses.
    """
    injected_now = now is not None
    if session_transcript_mtime is None:
        session_transcript_mtime = _session_transcript_mtime
    still_stale = []
    suppressed = []
    for entry in stale_live:
        promise = entry.get("staleAfterSeconds")
        lane_info = live_lanes.get(entry["launchId"]) or {}
        mtime, ambiguous = session_transcript_mtime(
            lane_info.get("sessionId"), env,
        )
        lane_now = now if injected_now else time.time()
        if ambiguous and degraded is not None:
            degraded.add(DEGRADATION_TRANSCRIPT_AMBIGUOUS)
        # bite-axis: DIRECTION of failure — an unresolvable transcript or an unusable
        # promise alerts, never suppresses.
        if not _valid_positive_int(promise) or mtime is None:
            still_stale.append(entry)
            continue
        transcript_age = lane_now - mtime
        # bite-axis: a FUTURE-dated transcript is a skewed or wrong clock, not evidence
        # of work. The watcher and the transcript share one host clock, so there is no
        # skew to tolerate here, and tolerating any would contradict the documented
        # fail-toward-alert invariant.
        if transcript_age < 0:
            still_stale.append(entry)
            continue
        # bite-axis: FRESHNESS of the transcript against the lane's own promise —
        # written inside the window is working, outside it is wedged.
        if transcript_age > promise:
            still_stale.append(entry)
            continue
        suppressed.append({
            "launchId": entry["launchId"],
            "note": NOTE_STALE_SUPPRESSED_TRANSCRIPT_FRESH,
            "state": entry.get("state"),
            "ageSeconds": entry.get("ageSeconds"),
            "staleAfterSeconds": promise,
            "transcriptAgeSeconds": round(transcript_age, 3),
        })
    return still_stale, suppressed


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
    pr_sampled=None,
):
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None
    timeout = min(30.0, remaining)
    if timeout < _MIN_PR_POLL_SECONDS:
        return None
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

    if pr_sampled is not None:
        pr_sampled[0] = True

    pr_set = set(numbers)
    pr_baseline = pr_state[0]
    if pr_baseline is None:
        pr_state[0] = pr_set
        return None
    if pr_set == pr_baseline:
        return None
    added = sorted(pr_set - pr_baseline)
    removed = sorted(pr_baseline - pr_set)
    return {
        "prs": sorted(pr_set),
        "prsAdded": added,
        "prsRemoved": removed,
    }


def _payload_lane_terminal(ctx):
    launches = _filter_suppressed_launches(
        ctx["terminal_launches"], EVENT_LANE_TERMINAL, ctx["ignore_set"],
    )
    if not launches:
        return None
    payload = {
        "launchId": launches[0]["launchId"],
        "launches": launches,
    }
    also = _build_also_observed(
        EVENT_LANE_TERMINAL,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload


def _payload_lane_blocked(ctx):
    launches = _filter_suppressed_launches(
        ctx["blocked_launches"], EVENT_LANE_BLOCKED, ctx["ignore_set"],
    )
    if not launches:
        return None
    payload = {
        "launchId": launches[0]["launchId"],
        "launches": launches,
    }
    also = _build_also_observed(
        EVENT_LANE_BLOCKED,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload


def _payload_builder_exited(ctx):
    exited = ctx["exited"]
    if exited is None:
        return None
    pids, exited_launches = exited
    launches = _filter_suppressed_launches(
        exited_launches, EVENT_BUILDER_EXITED, ctx["ignore_set"],
    )
    if not launches:
        return None
    filtered_pids = [entry["pid"] for entry in launches]
    payload = {
        "pids": filtered_pids,
        "launches": launches,
    }
    also = _build_also_observed(
        EVENT_BUILDER_EXITED,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        exited_launches,
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload


def _payload_pr_set_changed(ctx):
    pr_change = _evaluate_pr_set_changed(
        ctx["repo_root"],
        ctx["deadline"],
        ctx["monotonic"],
        ctx["gh_run"],
        ctx["pr_state"],
        ctx["degraded"],
        ctx["env"],
        ctx["pr_sampled"],
    )
    if pr_change is None:
        return None
    payload = dict(pr_change)
    also = _build_also_observed(
        EVENT_PR_SET_CHANGED,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload


def _payload_lane_stale(ctx):
    launches = _filter_suppressed_launches(
        ctx["stale_live_launches"], EVENT_LANE_STALE, ctx["ignore_set"],
    )
    if not launches:
        return None
    payload = {
        "launchId": launches[0]["launchId"],
        "launches": launches,
    }
    also = _build_also_observed(
        EVENT_LANE_STALE,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload


_EVENT_PAYLOAD_BUILDERS = {
    EVENT_LANE_TERMINAL: _payload_lane_terminal,
    EVENT_LANE_BLOCKED: _payload_lane_blocked,
    EVENT_BUILDER_EXITED: _payload_builder_exited,
    EVENT_PR_SET_CHANGED: _payload_pr_set_changed,
    EVENT_LANE_STALE: _payload_lane_stale,
}

for _event in EVENT_PRECEDENCE:
    if _event != EVENT_TIMER:
        assert _event in _EVENT_PAYLOAD_BUILDERS


def _close_log_silent(log_file):
    if log_file is not None:
        try:
            log_file.close()
        except OSError:
            pass


def _open_log_append(log_path):
    """Open log_path for append-only writes; return (file, degradation_or_none)."""
    if os.path.lexists(log_path):
        try:
            st = os.lstat(log_path)
            if not stat.S_ISREG(st.st_mode):
                return None, DEGRADATION_LOG_UNWRITABLE
        except OSError:
            return None, DEGRADATION_LOG_UNWRITABLE
    flags = os.O_APPEND | os.O_WRONLY | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(log_path, flags, 0o644)
    except OSError:
        return None, DEGRADATION_LOG_UNWRITABLE
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            return None, DEGRADATION_LOG_UNWRITABLE
        return os.fdopen(fd, "a"), None
    except OSError:
        os.close(fd)
        return None, DEGRADATION_LOG_UNWRITABLE


def _append_log_line(log_file, arm, elapsed_seconds, result):
    line = json.dumps({
        "arm": arm,
        "elapsedSeconds": round(elapsed_seconds, 3),
        "result": result,
    }, sort_keys=True)
    log_file.write(line + "\n")
    log_file.flush()


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
    ignore_events=(),
    ledger_observed=None,
    pr_state=None,
    pr_sampled=None,
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

        ignore_refusal = _validate_ignore_events(ignore_events, batch_id)
        if ignore_refusal is not None:
            return ignore_refusal

        if not _valid_positive_int(interval_seconds):
            return _refusal(REFUSAL_INTERVAL_INVALID, batch_id)
        if not _valid_positive_int(max_seconds):
            return _refusal(REFUSAL_MAX_SECONDS_INVALID, batch_id)
        if not _valid_repo_root(repo_root):
            return _refusal(REFUSAL_REPO_ROOT_INVALID, batch_id)

        ledger_path_result = ll.ledger_path(repo_root, env=env)
        if not ledger_path_result["ok"]:
            return _refusal(REFUSAL_STORE_UNRESOLVABLE, batch_id)

        if ledger_observed is None:
            ledger_observed = [False]
        if pr_state is None:
            pr_state = [None]
        if pr_sampled is None:
            pr_sampled = [False]

        start = monotonic()
        deadline = start + max_seconds
        tick = 0
        degraded = set()
        first_tick = True
        ignore_set = _ignore_events_set(ignore_events)
        # Accumulated across this arm's ticks so a suppression stays visible in the
        # arm's timer result (and therefore in loop's --log line) even when a later
        # tick observed nothing. A lane that goes still-stale later is dropped, so
        # the note can never contradict the event on the same result.
        arm_suppressed = {}

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
            stale_live_launches, tick_suppressed = _stale_second_chance(
                stale_live_launches, live_lanes, env, degraded=degraded,
            )
            for entry in tick_suppressed:
                arm_suppressed[entry["launchId"]] = entry
            # bite-axis: CONSISTENCY — a lane found still stale on a later tick loses
            # its earlier suppression, so the note can never contradict the event.
            for entry in stale_live_launches:
                arm_suppressed.pop(entry["launchId"], None)
            exited_launches = exited[1] if exited is not None else []

            event_ctx = {
                "terminal_launches": terminal_launches,
                "blocked_launches": blocked_launches,
                "exited": exited,
                "exited_launches": exited_launches,
                "stale_live_launches": stale_live_launches,
                "batch_id": batch_id,
                "degraded": degraded,
                "ignore_set": ignore_set,
                "repo_root": repo_root,
                "deadline": deadline,
                "monotonic": monotonic,
                "gh_run": gh_run,
                "pr_state": pr_state,
                "pr_sampled": pr_sampled,
                "env": env,
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
                        if not pr_sampled[0]:
                            degraded.add(DEGRADATION_PR_SIGNAL_NEVER_SAMPLED)
                        return _event_result(
                            EVENT_TIMER, batch_id, degraded,
                            stale_suppressed=list(arm_suppressed.values()),
                        )
                    break

                # Every non-timer member of EVENT_PRECEDENCE has a builder.
                payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)
                if payload is not None:
                    return _event_result(
                        event, batch_id, degraded,
                        stale_suppressed=list(arm_suppressed.values()),
                        **payload
                    )

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
    ignore_events=(),
    run_fn=None,
):
    """Re-arm run until a refusal or non-timer event. Returns the result dict; never raises."""
    batch_for_refusal = batch_id if isinstance(batch_id, str) else None
    arms = 0
    loop_degraded = set()
    log_file = None
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
            return _refusal(REFUSAL_BATCH_INVALID, batch_for_refusal, arms=0)

        batch_id = batch_id.strip()

        ignore_refusal = _validate_ignore_events(
            ignore_events, batch_id, arms=0,
        )
        if ignore_refusal is not None:
            return ignore_refusal

        if (
            max_total_seconds is not None
            and not _valid_positive_int(max_total_seconds)
        ):
            return _refusal(
                REFUSAL_MAX_TOTAL_SECONDS_INVALID, batch_id, arms=0,
            )
        if not _valid_positive_int(interval_seconds):
            return _refusal(REFUSAL_INTERVAL_INVALID, batch_id, arms=0)
        if not _valid_positive_int(max_seconds):
            return _refusal(REFUSAL_MAX_SECONDS_INVALID, batch_id, arms=0)
        if not _valid_repo_root(repo_root):
            return _refusal(REFUSAL_REPO_ROOT_INVALID, batch_id, arms=0)

        ledger_observed = [False]
        pr_state = [None]
        pr_sampled = [False]
        total_start = monotonic()
        total_deadline = (
            total_start + max_total_seconds
            if max_total_seconds is not None
            else None
        )
        last_timer_result = None
        log_degradation = None
        if log_path is not None:
            log_file, log_degradation = _open_log_append(log_path)
            if log_degradation is not None:
                loop_degraded.add(log_degradation)
                log_file = None

        while True:
            if total_deadline is not None:
                remaining = total_deadline - monotonic()
                if remaining <= 0:
                    # Fail-closed: only reachable after a timer arm set last_timer_result.
                    final = dict(last_timer_result)
                    final["arms"] = arms
                    final_degraded = set(final.get("degraded", []))
                    final_degraded.update(loop_degraded)
                    final["degraded"] = sorted(final_degraded)
                    _close_log_silent(log_file)
                    return final

            if total_deadline is not None:
                remaining = total_deadline - monotonic()
                arm_max_seconds = max(1, min(max_seconds, int(remaining)))
            else:
                arm_max_seconds = max_seconds

            arms += 1
            result = run_fn(
                repo_root,
                batch_id,
                max_seconds=arm_max_seconds,
                interval_seconds=interval_seconds,
                env=env,
                gh_run=gh_run,
                monotonic=monotonic,
                sleep=sleep,
                ignore_launch_ids=ignore_launch_ids,
                ignore_events=ignore_events,
                ledger_observed=ledger_observed,
                pr_state=pr_state,
                pr_sampled=pr_sampled,
            )

            result_degraded = set(result.get("degraded", []))
            loop_degraded.update(result_degraded)

            if result.get("ok") and result.get("event") == EVENT_TIMER:
                last_timer_result = result
                if log_file is not None:
                    try:
                        _append_log_line(
                            log_file,
                            arms,
                            monotonic() - total_start,
                            result,
                        )
                    except OSError:
                        loop_degraded.add(DEGRADATION_LOG_UNWRITABLE)
                        try:
                            log_file.close()
                        except OSError:
                            pass
                        log_file = None
                elif log_path is not None and log_degradation is None:
                    log_file, log_degradation = _open_log_append(log_path)
                    if log_degradation is not None:
                        loop_degraded.add(log_degradation)
                        log_file = None
                    elif log_file is not None:
                        try:
                            _append_log_line(
                                log_file,
                                arms,
                                monotonic() - total_start,
                                result,
                            )
                        except OSError:
                            loop_degraded.add(DEGRADATION_LOG_UNWRITABLE)
                            _close_log_silent(log_file)
                            log_file = None

                if total_deadline is not None:
                    remaining = total_deadline - monotonic()
                    if remaining <= 0:
                        final = dict(result)
                        final["arms"] = arms
                        final_degraded = set(final.get("degraded", []))
                        final_degraded.update(loop_degraded)
                        final["degraded"] = sorted(final_degraded)
                        _close_log_silent(log_file)
                        return final
                continue

            final = dict(result)
            final["arms"] = arms
            final_degraded = set(final.get("degraded", []))
            final_degraded.update(loop_degraded)
            final["degraded"] = sorted(final_degraded)
            _close_log_silent(log_file)
            return final
    except Exception as exc:
        _close_log_silent(log_file)
        result = _refusal(REFUSAL_INTERNAL_ERROR, batch_for_refusal, arms=arms)
        result["detail"] = type(exc).__name__
        if loop_degraded:
            result["degraded"] = sorted(loop_degraded)
        return result


def _parse_ignore_event_cli(value):
    if ":" not in value:
        return None
    launch_id, event = value.rsplit(":", 1)
    if not launch_id or not event:
        return None
    if event not in _SUPPRESSIBLE_EVENTS:
        return None
    return (launch_id, event)


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
    run_parser.add_argument(
        "--ignore-event",
        action="append",
        default=[],
        dest="ignore_event_raw",
        metavar="LAUNCHID:EVENT",
        help="suppress one event for one lane (repeatable)",
    )

    loop_parser = sub.add_parser("loop")
    loop_parser.add_argument("--repo-root", required=True)
    loop_parser.add_argument("--batch", required=True)
    loop_parser.add_argument("--max-seconds", type=int, default=2400)
    loop_parser.add_argument("--interval-seconds", type=int, default=60)
    loop_parser.add_argument("--max-total-seconds", type=int, default=None)
    loop_parser.add_argument("--log", dest="log_path", default=None)
    loop_parser.add_argument(
        "--ignore-launch",
        action="append",
        default=[],
        dest="ignore_launch_ids",
        metavar="launchId",
        help="exclude launch id from lane enumeration (repeatable)",
    )
    loop_parser.add_argument(
        "--ignore-event",
        action="append",
        default=[],
        dest="ignore_event_raw",
        metavar="LAUNCHID:EVENT",
        help="suppress one event for one lane (repeatable)",
    )

    args = ap.parse_args(argv[1:])

    ignore_events = []
    for raw in args.ignore_event_raw:
        parsed = _parse_ignore_event_cli(raw)
        if parsed is None:
            ignore_events.append((None, None))
        else:
            ignore_events.append(parsed)

    if args.cmd == "run":
        result = run(
            args.repo_root,
            args.batch,
            max_seconds=args.max_seconds,
            interval_seconds=args.interval_seconds,
            ignore_launch_ids=tuple(args.ignore_launch_ids),
            ignore_events=tuple(ignore_events),
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
            ignore_events=tuple(ignore_events),
        )
    else:
        return 1

    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
