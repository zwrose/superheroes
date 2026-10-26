#!/usr/bin/env python3
"""Ledger-driven wave watcher (#982).

Watch one launch batch until the first qualifying event. stdlib only.

Verbs:
- run: one-shot evaluation tick — one ledger read, at most one open-PR poll, no sleep.
- watch_arm: windowed watch — one arm until the first event or arm deadline.
- loop: re-arms watch_arm internally, passes over benign events, and exits only
  on lane-ending events, attention events, refusals, or its ceiling; refuses a second live loop on
  the batch. loop owns one set of state
  cells (pr_state, stack_state, pr_sampled) threaded through every arm so
  PR deltas across an arm boundary are not absorbed into a fresh baseline, and
  a prior arm's successful PR poll is not forgotten on the next arm's timer.
- note-answered: record a builder note's or a cloud terminal comment's id as answered (the only writer here).

Contract:
- Refusals (ok=False): the REFUSALS constant.
- Events (ok=True): the EVENTS constant.
- Degradations (non-fatal): the DEGRADATIONS constant.
- gh child env-scrubbing: ambient git/GH routing variables in _GH_SCRUB_VARS
  are stripped via ll.scrub_env before the gh subprocess runs.
- Deadline-bound polling: no gh poll starts when remaining time is below
  _MIN_PR_POLL_SECONDS; each poll's timeout is min(30.0, remaining).
- Precedence: EVENT_PRECEDENCE, highest first.
- lane-stale: a started lane whose latest recorded pid is positively live and whose
  own session transcript was not written within LIVENESS_QUIET_WINDOW_SECONDS — a
  wedged builder alive but frozen past the quiet window. A lane whose transcript
  file does not exist yet gets the same window measured from its recorded start.
  Only terminal stamps
  (parked/handback) are excluded from this check; blocked lanes stay candidates so
  lane-blocked can win precedence while lane-stale still surfaces in alsoObserved.
- Transcript liveness (#1023, #1484): lane-stale fires when the lane's session
  transcript is unresolved, ambiguous, future-dated, or older than
  LIVENESS_QUIET_WINDOW_SECONDS. A transcript written within the window (inclusive
  at the boundary) is live. Every unresolvable read fails toward the alert, never
  toward silence. Ambiguity records transcript-ambiguous; a read that could not
  RESOLVE records transcript-unresolved (#1036). An absent projects root or absent
  candidate is NOT unresolved: that is a cold or absent transcript — the wedge
  signal itself. The one-shot `run` verb applies the same rule, so a scheduled
  `run` catches a wedged lane with no loop armed.
- Transcript identity: a transcript vouches for a lane only when the launch record
  carries that lane's session id and exactly one regular file named
  <sessionId>.jsonl resolves under the host config root's projects tree. The
  watcher stat's only — it never reads transcript contents. Exactly one config root
  is searched, never both: the lane's own recorded configDir when the launch record
  carries one (#1036 — a lane launched under another Claude instance keeps its
  transcript under that instance's root), else the watcher's env root (the
  CLAUDE_CONFIG_DIR override outright, else ~/.claude). A symlinked entry is never
  followed.
- A ledger file that is absent reads as blind, exactly like an unreadable one: at the
  first tick of an arm it refuses ledger-unreadable, mid-arm it degrades the next firing,
  and at the deadline it refuses. Every ledger-unreadable refusal carries ledgerPath.
- When a lane's heartbeat is unreadable its higher-precedence E1/E2 state is
  UNKNOWN, so a lower-precedence event may be reported for it and the
  heartbeat-unreadable degradation token discloses that uncertainty.
- alsoObserved: on a result that carries a payload, co-occurring lower-precedence
  lane signals from the same interval are included under alsoObserved (launchIds
  only). A timer result carries no payload and no alsoObserved, so a lane's
  signal is not visible through alsoObserved on timer.
- ignore-launch: caller-supplied launch ids excluded from lane enumeration so
  an already-handled lane that cannot be terminalized does not re-fire.
- ignore-events: caller-supplied (launchId, event) pairs suppress that event
  for that lane only — lane-terminal, lane-blocked, builder-exited, and
  lane-stale are suppressible; builder-note, stack-state-changed, pr-set-changed,
  and timer are not. Suppression
  affects actionability only. One note can be ignored by id: a (launchId, "builder-note",
  commentId) triple, on the CLI `LAUNCHID:builder-note:COMMENTID`, suppresses that one note on
  that lane for that invocation, and no other note. Every non-refusal result of run, watch_arm
  and loop given at least one such ignore carries `ignoredNotes`, the sorted comment ids, so a
  still-unanswered note is never invisible; without one the key is absent.
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
- Cloud lanes: a lane whose folded place is cloud has no pid, transcript or heartbeat
  to read — its recorded pid is the launch command's own and has already exited. The
  watch never concludes anything about it from those; it reads the lane's GitHub activity
  (its issue, the PRs that close it, the branches carrying its issue number) with one
  GraphQL request for all cloud lanes, at most once per CLOUD_ACTIVITY_POLL_SECONDS per
  watch. Activity (or the lane's start, if newer) quiet past LIVENESS_QUIET_WINDOW_SECONDS
  is lane-stale, as is a future-dated reference. A read that could not be made records
  cloud-activity-unavailable and the lane is neither stale nor clean. Every non-refusal
  tick/timer result carries cloudLanes while the batch has a live cloud lane.
- Builder notes: a cloud builder cannot message the advisor, so it posts an issue comment
  that opens with cloud_builder.NOTE_HEADER. One REST read of the repository's issue
  comments per tick (a 304 re-uses the stored list) surfaces an unanswered note on a live
  started cloud lane's issue, created at or after that lane's start, as builder-note. It
  keeps surfacing until `note-answered` records its comment id; a read that could not be
  made records builder-note-unavailable and the lane is neither noted nor clean. When the comments
  read was partial, every watched lane's issue may hold an unread comment, so the result
  names them under `unreadIssues` ([{launchId, issue}], present only when non-empty; across an arm
  or a loop a lane named once stays named).
- Fix orders: a terminal, started cloud lane is watched again, exactly like a live cloud lane, from
  the moment it is sent a fix order until its next ending. Openers: a `vet not-ready` amendment, or a
  fix-order relay record (cloud_relay.fix_orders, composed with --fix-order) whose check read delivered
  or may-hold-text, for the lane's session, opening at the message's compose time (`sentAfter`), never
  at the check. Closers: a `reoutcome` amendment, or a vet `ready` or
  `parked-blocker`; the newest opener must be later than the newest closer. The window is
  [reopenedAt, close): the close is the first handback, stop or park created at or after reopenedAt that
  is not a superseded park (a handover also closes, and surfaces nothing). Endings and notes before
  reopenedAt, or after the close, are not the lane's; the closing ending fires lane-terminal and the
  lane is never stale once closed. A comments read that made no request or was partial knows no close,
  so the lane stays watched. Staleness floors at reopenedAt. Cloud lanes only, never a refused or
  never-started lane, and a lane in ignore-launch is not re-added. An unreadable relay state records
  fix-order-unavailable and only the ledger's openers count.
- Cloud endings: the same comments read surfaces, per live started cloud lane, the newest
  comment opening with a `cloud_builder.TERMINAL_HEADERS` header (handback, stop, park),
  created at or after the lane's start and not recorded by `note-answered`, as lane-terminal
  with state handback, stopped or parked. A newer handover, or an answered newest comment,
  surfaces nothing. A park is superseded, and surfaces nothing, when the same lane has later
  builder activity in the same read: a builder note created strictly after the park was created
  (answered or not), or a progress comment updated more than PARK_SUPERSESSION_GRACE_SECONDS
  after the park was created whose phase reads resumed (no word beginning park or stop, unless
  a word begins resum). A handback or stop is never superseded, and a park at or after the
  latest activity, or whose progress edit is inside the window or reads parked, still fires.
- Cloud progress: a cloud builder keeps one progress comment on its issue, edited in place, that
  opens with cloud_builder.PROGRESS_HEADER and states how long its current step is expected to
  run. For a started cloud lane whose tick's comments read observed at least one such comment
  (created at or after the lane's start), that comment alone decides lane-stale: stale exactly
  when its updated_at age is negative or greater than its stated expected seconds plus
  LIVENESS_QUIET_WINDOW_SECONDS; the newest-updated comment wins, a missing or malformed
  expectation counts as zero extra seconds, and one over cb.PROGRESS_EXPECTED_MAX_MINUTES is
  capped. A lane with no observed progress comment keeps the activity rule unchanged. The
  comment is read from the same comments read as builder notes and endings: no extra request.
- Standing guarantees: the watcher never writes ledger or heartbeat state; under
  the store its only write is its own loop-lock sidecar (`wave-watch-locks/`);
  `--log` writes the caller-selected log. The `note-answered` verb alone writes
  builder-notes-answered.json beside the ledger. It never signals any process (pid
  liveness is os.kill(pid, 0) probing only).
"""
import argparse
import errno
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cloud_builder as cb  # noqa: E402
import cloud_relay as cr  # noqa: E402
import launch_ledger as ll  # noqa: E402
import heartbeat as hb  # noqa: E402
import stack_check as sc  # noqa: E402
import store_core  # noqa: E402

_GH_PR_LIST_ARGV = sc.open_prs_argv(("number",))

_MIN_PR_POLL_SECONDS = 1.0

CLOUD_ACTIVITY_POLL_SECONDS = 60
_CLOUD_ACTIVITY_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_CLOUD_ACTIVITY_QUERY_HEAD = (
    "query($owner: String!, $name: String!) "
    "{ repository(owner: $owner, name: $name) { "
)
_CLOUD_ACTIVITY_QUERY_TAIL = "} }"

# A builder edits its progress comment seconds after posting a park; only an edit later than this
# many seconds after the park, whose phase reads resumed, shows the lane resumed.
PARK_SUPERSESSION_GRACE_SECONDS = 300

BUILDER_NOTES_ANSWERED_NAME = "builder-notes-answered.json"
_NOTE_COMMENTS_MAX_PAGES = 10
_NOTE_LINK_NEXT = re.compile(r'<[^>]*>\s*;\s*rel="next"')

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

# Value and field-check narrative: lib/heartbeat.py LIVENESS_QUIET_WINDOW_SECONDS.
LIVENESS_QUIET_WINDOW_SECONDS = hb.LIVENESS_QUIET_WINDOW_SECONDS

RESULT_KEY_PASSED_OVER = "passedOver"
RESULT_KEY_PASSED_OVER_COUNT = "passedOverCount"
RESULT_KEY_LIVE_LOOP = "liveLoop"

RUN_READ_BUDGET_SECONDS = 30
PASSED_OVER_CAP = 100

_GH_SCRUB_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    # The child here is `gh`, not `git`: GH_REPO overrides repository resolution
    # overrides repository resolution outright, and the
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


def _gh_scrub_env(env):
    # Superset of the ledger's git scrub vars, deliberately — GH_REPO and the
    # GIT_CONFIG family can silently point the PR poll at a different repository.
    # The ledger root is stripped with the default roots= (LEDGER_ROOT_ENV).
    return ll.scrub_env(env, keys=_GH_SCRUB_VARS)

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
REFUSAL_LOOP_ALREADY_LIVE = "loop-already-live"
REFUSAL_LOOP_LOCK_UNAVAILABLE = "loop-lock-unavailable"
REFUSAL_COMMENT_ID_INVALID = "comment-id-invalid"
REFUSAL_NOTE_ANSWERS_UNREADABLE = "note-answers-unreadable"

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
    REFUSAL_LOOP_ALREADY_LIVE,
    REFUSAL_LOOP_LOCK_UNAVAILABLE,
    REFUSAL_COMMENT_ID_INVALID,
    REFUSAL_NOTE_ANSWERS_UNREADABLE,
})

EVENT_LANE_TERMINAL = "lane-terminal"
EVENT_LANE_BLOCKED = "lane-blocked"
EVENT_BUILDER_EXITED = "builder-exited"
EVENT_BUILDER_NOTE = "builder-note"
EVENT_STACK_STATE_CHANGED = "stack-state-changed"
EVENT_PR_SET_CHANGED = "pr-set-changed"
EVENT_LANE_STALE = "lane-stale"
EVENT_TIMER = "timer"

EVENTS = frozenset({
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_BUILDER_NOTE,
    EVENT_STACK_STATE_CHANGED,
    EVENT_PR_SET_CHANGED,
    EVENT_LANE_STALE,
    EVENT_TIMER,
})

LANE_ENDING_EVENTS = frozenset({
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_LANE_STALE,
})
BENIGN_EVENTS = frozenset({
    EVENT_STACK_STATE_CHANGED,
    EVENT_PR_SET_CHANGED,
    EVENT_TIMER,
})

# Ends the loop without ending a lane: the advisor is asked something and a builder waits.
ATTENTION_EVENTS = frozenset({
    EVENT_BUILDER_NOTE,
})

assert LANE_ENDING_EVENTS | BENIGN_EVENTS | ATTENTION_EVENTS == EVENTS
assert not LANE_ENDING_EVENTS & BENIGN_EVENTS
assert not LANE_ENDING_EVENTS & ATTENTION_EVENTS
assert not BENIGN_EVENTS & ATTENTION_EVENTS

DEGRADATION_LEDGER_TORN_TAIL = "ledger-torn-tail"
DEGRADATION_LEDGER_UNREADABLE = "ledger-unreadable"
DEGRADATION_HEARTBEAT_UNREADABLE = "heartbeat-unreadable"
DEGRADATION_PID_PROBE_UNCERTAIN = "pid-probe-uncertain"
DEGRADATION_PR_SIGNAL_UNAVAILABLE = "pr-signal-unavailable"
DEGRADATION_LANE_NEVER_STAMPED = "lane-never-stamped"
DEGRADATION_PR_SIGNAL_NEVER_SAMPLED = "pr-signal-never-sampled"
DEGRADATION_LOG_UNWRITABLE = "log-unwritable"
DEGRADATION_TRANSCRIPT_AMBIGUOUS = "transcript-ambiguous"
DEGRADATION_TRANSCRIPT_UNRESOLVED = "transcript-unresolved"
DEGRADATION_STACK_SIGNAL_UNAVAILABLE = "stack-signal-unavailable"
DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE = "cloud-activity-unavailable"
DEGRADATION_BUILDER_NOTE_UNAVAILABLE = "builder-note-unavailable"
DEGRADATION_FIX_ORDER_UNAVAILABLE = "fix-order-unavailable"

STACK_STATE_COMPLETE = "stack-complete"
STACK_STATE_INCOMPLETE = "stack-incomplete"
STACK_REASON_LAYERS_PLANNED_UNKNOWN = "layers-planned-unknown"
STACK_REASON_LAYERS_PLANNED_DISAGREED = "layers-planned-disagreed"
STACK_REASON_MEMBERSHIP_UNRESOLVED = "membership-unresolved"
FLAG_IDLE_SEAT_LAUNCHABLE_CHILD = "idle-seat-launchable-child"

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
    DEGRADATION_TRANSCRIPT_UNRESOLVED,
    DEGRADATION_STACK_SIGNAL_UNAVAILABLE,
    DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE,
    DEGRADATION_BUILDER_NOTE_UNAVAILABLE,
    DEGRADATION_FIX_ORDER_UNAVAILABLE,
})

EVENT_PRECEDENCE = (
    EVENT_LANE_TERMINAL,
    EVENT_LANE_BLOCKED,
    EVENT_BUILDER_EXITED,
    EVENT_BUILDER_NOTE,
    # Above pr-set-changed so a completion wins on a tick where both hold; the
    # PR-set evaluator does not run that tick and so never advances pr_state.
    EVENT_STACK_STATE_CHANGED,
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
HB_CLASS_NONTERMINAL = "nonterminal"
HB_STATE_BLOCKED = "blocked"
assert HB_CLASS_UNKNOWN in hb.SWEEP_CLASSES
assert HB_CLASS_TERMINAL in hb.SWEEP_CLASSES
assert HB_CLASS_NONTERMINAL in hb.SWEEP_CLASSES
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


def _with_ledger_path(result, ledger_path):
    if result.get("reason") == REFUSAL_LEDGER_UNREADABLE:
        result["ledgerPath"] = ledger_path
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
        if not isinstance(item, (tuple, list)) or len(item) not in (2, 3):
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
        launch_id, event = item[0], item[1]
        if not isinstance(launch_id, str) or not launch_id:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
        if not isinstance(event, str) or not event:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
        if len(item) == 3:
            # bite-axis: NOTE ID — the one-note form is `builder-note` with a positive int
            # comment id; any other event or id is refused, and the bare class stays refused.
            if event != EVENT_BUILDER_NOTE or not _valid_positive_int(item[2]):
                return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
            continue
        if event not in _SUPPRESSIBLE_EVENTS:
            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
    return None


def _ignore_events_set(ignore_events):
    return frozenset((item[0], item[1]) for item in ignore_events if len(item) == 2)


def _ignored_notes_set(ignore_events):
    """{(launch id, comment id)} of the one-note ignores."""
    return frozenset((item[0], item[2]) for item in ignore_events if len(item) == 3)


def _with_ignored_notes(result, ignore_events):
    """`result` with `ignoredNotes` (sorted comment ids) when a note was ignored; a refusal is left alone."""
    if result.get("ok") is not True:
        return result
    ids = sorted({comment_id for _launch_id, comment_id in _ignored_notes_set(ignore_events)})
    if ids:
        result["ignoredNotes"] = ids
    return result


def _filter_suppressed_launches(launches, event, ignore_set):
    if not ignore_set:
        return launches
    return [
        entry for entry in launches
        if (entry["launchId"], event) not in ignore_set
    ]


def _higher_precedence_lane_event_due(
    terminal_launches, blocked_launches, exited_launches, ignore_set,
):
    """True when an unsuppressed lane-terminal, lane-blocked, or builder-exited event is due."""
    if _filter_suppressed_launches(
        terminal_launches, EVENT_LANE_TERMINAL, ignore_set,
    ):
        return True
    if _filter_suppressed_launches(
        blocked_launches, EVENT_LANE_BLOCKED, ignore_set,
    ):
        return True
    if _filter_suppressed_launches(
        exited_launches, EVENT_BUILDER_EXITED, ignore_set,
    ):
        return True
    return False


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


def _derive_batch_lanes(
    repo_root, batch_id, env, degraded, ignore_launch_ids,
):
    read_result = ll.read(repo_root, env=env, create=False)
    state = read_result["state"]
    if state in ("ok", "tornTail"):
        if state == "tornTail":
            degraded.add(DEGRADATION_LEDGER_TORN_TAIL)
        records = read_result["records"]
    elif state == "missing":
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, {}, False
    elif state in ("unreadable", "interiorCorrupt"):
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, {}, False
    else:
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, {}, False

    folded = ll.fold(records)
    if not folded["ok"]:
        degraded.add(DEGRADATION_LEDGER_UNREADABLE)
        return {}, {}, False

    ignore = set(ignore_launch_ids)
    all_lanes = {
        lid: info
        for lid, info in folded["launches"].items()
        if info.get("batchId") == batch_id
    }
    live_lanes = {
        lid: info
        for lid, info in all_lanes.items()
        if not info.get("terminal") and lid not in ignore
    }
    terminal = {
        lid: info for lid, info in all_lanes.items() if info.get("terminal") and lid not in ignore
    }
    relay_times = {}
    if any(_is_cloud_lane(info) and info.get("started") for info in terminal.values()):
        relay_times = _fix_order_times(repo_root, env, degraded)
    for lid, info in terminal.items():
        name = info.get("cloudSessionName")
        reopened = _reopen_candidate(
            info, relay_times.get(name, ()) if isinstance(name, str) and name else (),
        )
        if reopened is not None:
            live_lanes[lid] = {**info, "reopenedAt": reopened[0], "reopenedBy": reopened[1]}
    return all_lanes, live_lanes, True


def _is_cloud_lane(info):
    return info.get("place") == ll.PLACE_CLOUD


_RELAY_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_CLOSING_VETS = ("ready", "parked-blocker")


def _fix_order_times(repo_root, env, degraded):
    """{session name: [epoch of each fix-order relay that may have reached it]}; {} when unreadable.

    An unreadable relay state records fix-order-unavailable: the ledger's openers still count.
    A record whose session or stamp cannot be read is skipped. Never raises.
    """
    try:
        read = cr.fix_orders(repo_root, env=env)
    except Exception:
        read = {"ok": False}
    if read.get("ok") is not True:
        degraded.add(DEGRADATION_FIX_ORDER_UNAVAILABLE)  # axis: an unreadable relay state is disclosed, never a silent "no fix order" — see bite-proof record wo_2148_fix_order.md
        return {}
    times = {}
    for record in read.get("records", ()):
        at = record.get("at") if isinstance(record, dict) else None
        try:
            epoch = datetime.strptime(at, _RELAY_TIME_FORMAT).replace(tzinfo=timezone.utc).timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if isinstance(record.get("session"), str):
            times.setdefault(record["session"], []).append(epoch)
    return times


def _reopen_candidate(info, relay_times):
    """(reopenedAt epoch, reopenedBy) for a terminal cloud lane sent a fix order after its newest closer, else None.

    Openers: a `vet not-ready` amendment, or a fix-order relay time. Closers: a `reoutcome` amendment, or a
    vet `ready` or `parked-blocker`. A malformed amendment is skipped. The comments decide the close, not this.
    """
    # axis: only a started, outcome-terminal cloud lane can reopen — a local lane re-added would fire builder-exited at once — see bite-proof record wo_2148_fix_order.md
    if not (info.get("place") == ll.PLACE_CLOUD and info.get("started") and info.get("terminal")
            and info.get("terminalKind") == "outcome"):
        return None
    opener, closed_at = None, float("-inf")
    for amendment in info.get("amendments") or ():
        if not isinstance(amendment, dict) or not _finite_number(amendment.get("ts")):
            continue
        kind, value, ts = amendment.get("kind"), amendment.get("value"), amendment["ts"]
        # axis: a reoutcome, or a vet ready or parked-blocker, closes the fix order before it — see bite-proof record wo_2148_fix_order.md
        if kind == "reoutcome" or (kind == "vet" and value in _CLOSING_VETS):
            closed_at = max(closed_at, ts)
        # axis: a vet not-ready amendment is a fix order — see bite-proof record wo_2148_fix_order.md
        elif kind == "vet" and value == "not-ready" and (opener is None or ts > opener[0]):
            opener = (ts, "vet-not-ready")
    # axis: a fix-order relay delivered, or that may have reached the builder, is a fix order — see bite-proof record wo_2148_fix_order.md
    for ts in (t for t in relay_times if _finite_number(t)):
        if opener is None or ts > opener[0]:
            opener = (ts, "fix-order-relay")
    return opener if opener is not None and opener[0] > closed_at else None


def _evaluate_lane_heartbeats(repo_root, live_lanes, env, degraded):
    """One heartbeat read per local lane; derive E1 terminal, E2 blocked, and hb states."""
    terminal_launches = []
    blocked_launches = []
    hb_states = {}
    for lid in sorted(live_lanes):
        # bite-axis: CLOUD LANE — a cloud lane never stamps a heartbeat, so a stray file
        # at its path is no evidence about it.
        if _is_cloud_lane(live_lanes[lid]):
            continue
        hb_result = hb.read_heartbeat(repo_root, lid, env=env)
        hb_class = hb_result.get("class")
        hb_reason = hb_result.get("reason")
        if hb_class == HB_CLASS_UNKNOWN and hb_reason != REASON_HEARTBEAT_MISSING:
            degraded.add(DEGRADATION_HEARTBEAT_UNREADABLE)
            continue
        hb_state = hb_result.get("state")
        if hb_state is not None:
            hb_states[lid] = hb_state
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
    return terminal_launches, blocked_launches, hb_states


def _lane_never_stamped_at_deadline(repo_root, live_lanes, env):
    """True when a started lane has no heartbeat stamp across the whole watch window."""
    for lid in sorted(live_lanes):
        info = live_lanes[lid]
        if not info.get("started"):
            continue
        # bite-axis: CLOUD LANE — a cloud lane never stamps, so a missing heartbeat is not
        # a lane that never stamped.
        if _is_cloud_lane(info):
            continue
        hb_result = hb.read_heartbeat(repo_root, lid, env=env)
        if (
            hb_result.get("class") == HB_CLASS_UNKNOWN
            and hb_result.get("reason") == REASON_HEARTBEAT_MISSING
        ):
            return True
    return False


def _evaluate_pid_signals(live_lanes, exclude_ids, degraded):
    """Probe each started lane once; derive builder-exited and live candidates."""
    exited_launches = []
    pids = []
    live_candidates = []
    exclude = set(exclude_ids)
    for lid in sorted(live_lanes):
        info = live_lanes[lid]
        if not info.get("started"):
            continue
        # bite-axis: CLOUD LANE — the recorded pid is the launch command's own and has
        # already exited; it says nothing about the lane, so it is never probed.
        if _is_cloud_lane(info):
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
        elif lid not in exclude:
            live_candidates.append({"launchId": lid})
    if not exited_launches:
        exited = None
    else:
        exited = (pids, exited_launches)
    return exited, live_candidates


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


def _transcript_config_dirs(env, recorded=None):
    """The host config dir to search — EXACTLY ONE, never both.

    The lane's OWN recorded root wins when the launch record carries one (#1036): a lane
    launched under another Claude instance (the owner's per-launch exception, e.g.
    .claude-two) writes its transcript under THAT instance's root, and the watcher's own
    root would find nothing. Otherwise the watcher's env root is used — the
    CLAUDE_CONFIG_DIR override outright, else ~/.claude — which is also what a
    pre-#1036 record (no recorded root) resolves under.

    The override wins outright rather than being searched alongside the default, for the
    same reason the recorded root does: a same-named transcript under any OTHER root
    belongs to some OTHER session and must never be allowed to vouch for this lane.

    Returns [] when a root was recorded but is unusable — the caller reads an empty list
    as UNRESOLVED, never as a licence to fall back to the env root.
    """
    if recorded is not None:
        # strip() detects an all-whitespace value; it never REWRITES the recorded root.
        # The grammar accepts any usable absolute path, so a directory whose name really
        # does end in a space is legal — searching a stripped version of it would look in
        # a directory the lane never wrote to, and the launcher already normalized once.
        # A watcher that rewrites what was recorded cannot be said to search "the lane's
        # own root" at all.
        if not isinstance(recorded, str) or not recorded.strip():
            return []
        if not os.path.isabs(recorded):
            return []
        return [recorded]
    configured = env.get(_TRANSCRIPT_CONFIG_DIR_ENV)
    if isinstance(configured, str) and configured.strip():
        return [_expand_home(configured.strip(), env)]
    return [_expand_home(_TRANSCRIPT_DEFAULT_CONFIG_DIR, env)]


# WORKAROUND: transcript file mtime as lane liveness when idle signals are unreliable
# delete-when: a re-run of the background-session trial observes its "transcript-mtime
# liveness" condition met; the condition is restated in the keep-or-retire record's marker
# inventory
def _session_transcript_mtime(session_id, env, config_dir=None):
    """(mtime, ambiguous, unresolved) for the lane's own transcript, by recorded id.

    The three outcomes are mutually exclusive by construction and each fails toward the
    alert; they differ only in what they DISCLOSE:

    - a resolved single match returns its mtime (the only outcome that can suppress);
    - ``ambiguous`` — two or more transcripts carry this id, so identity is unprovable;
    - ``unresolved`` — the lookup itself could not complete (an unreadable projects root,
      an unreadable bucket, a candidate stat failing for anything but absence, or a
      recorded config root that is unusable), so the watcher cannot tell a cold
      transcript from one it simply could not read (#1036).

    ABSENCE is deliberately not ``unresolved``: a missing projects root, a missing bucket,
    or a missing candidate all mean the transcript is not there, which is the wedge signal
    the event exists to report — not a failed reading of it. Absence means ENOENT and
    nothing else: ENOTDIR (a config root or bucket that is a FILE) is a malformed root the
    watcher could not read, not a transcript that is not there.

    ``ValueError`` is adjudicated alongside ``OSError`` because a path string can be
    absolute and still be unusable — an embedded NUL or an unencodable surrogate makes
    os.scandir raise ValueError, and letting that escape turns a lane's stale alert into a
    whole-watch internal-error refusal, which is the fail-toward-alert invariant inverted.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        return None, False, False
    if os.sep in session_id or "/" in session_id or ".." in session_id:
        return None, False, False

    roots = _transcript_config_dirs(env, recorded=config_dir)
    if not roots:
        # A recorded root we cannot use is a failed lookup, never a fall-back to the
        # watcher's own root: that fall-back is exactly how a foreign same-named
        # transcript would get to vouch for this lane.
        return None, False, True

    filename = session_id + _TRANSCRIPT_SUFFIX
    matches = []
    for root in roots:
        projects_root = os.path.join(root, _PROJECTS_DIR_NAME)
        try:
            bucket_entries = list(os.scandir(projects_root))
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            return None, False, True
        for bucket_entry in bucket_entries:
            try:
                if not bucket_entry.is_dir(follow_symlinks=False):
                    continue
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                return None, False, True
            candidate = os.path.join(bucket_entry.path, filename)
            try:
                st = os.stat(candidate, follow_symlinks=False)
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                return None, False, True
            if not stat.S_ISREG(st.st_mode):
                continue
            matches.append(st.st_mtime)

    if len(matches) == 0:
        return None, False, False
    if len(matches) >= 2:
        return None, True, False
    return matches[0], False, False


def _transcript_cold(
    live_candidates, live_lanes, env, *, hb_states, now=None, degraded=None,
    session_transcript_mtime=None,
):
    """Return pid-live lanes whose session transcript is outside the quiet window.

    Fail-toward-alert is the invariant: no session id, an unresolvable transcript,
    ambiguity, a cold transcript, or a future-dated transcript all mark the lane stale.
    Only a positively fresh transcript (age 0..LIVENESS_QUIET_WINDOW_SECONDS inclusive)
    is live.

    The lane's transcript is looked up under the lane's OWN recorded config root when
    its launch record carries one (#1036).
    """
    injected_now = now is not None
    if session_transcript_mtime is None:
        session_transcript_mtime = _session_transcript_mtime
    still_stale = []
    for entry in live_candidates:
        lid = entry["launchId"]
        lane_info = live_lanes.get(lid) or {}
        mtime, ambiguous, unresolved = session_transcript_mtime(
            lane_info.get("sessionId"), env, lane_info.get("configDir"),
        )
        lane_now = now if injected_now else time.time()
        if ambiguous and degraded is not None:
            degraded.add(DEGRADATION_TRANSCRIPT_AMBIGUOUS)
        # bite-axis: DISCLOSURE — a lookup that could not complete is reported as such, so
        # "the watcher could not read the transcript" is never silently indistinguishable
        # from "the transcript is cold". The lane stays stale either way (#1036).
        if unresolved and degraded is not None:
            degraded.add(DEGRADATION_TRANSCRIPT_UNRESOLVED)
        transcript_age = None
        if mtime is not None:
            transcript_age = lane_now - mtime
        # bite-axis: DIRECTION of failure — an unresolvable transcript alerts, never
        # suppresses.
        if mtime is None:
            # bite-axis: STARTUP GRACE — plain absence before the first transcript line
            # is not stale while the lane is still inside the quiet window from start.
            if not ambiguous and not unresolved:
                session_id = lane_info.get("sessionId")
                if isinstance(session_id, str) and session_id.strip():
                    started_ts = lane_info.get("startedTs")
                    if isinstance(started_ts, (int, float)) and not isinstance(
                        started_ts, bool,
                    ) and math.isfinite(started_ts):
                        startup_age = lane_now - started_ts
                        if 0 <= startup_age <= LIVENESS_QUIET_WINDOW_SECONDS:
                            continue
            still_stale.append({
                "launchId": lid,
                "state": hb_states.get(lid),
                "transcriptAgeSeconds": None,
                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
            })
            continue
        # bite-axis: a FUTURE-dated transcript is a skewed or wrong clock, not evidence
        # of work. The watcher and the transcript share one host clock, so there is no
        # skew to tolerate here, and tolerating any would contradict the documented
        # fail-toward-alert invariant.
        if transcript_age < 0:
            still_stale.append({
                "launchId": lid,
                "state": hb_states.get(lid),
                "transcriptAgeSeconds": round(transcript_age, 3),
                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
            })
            continue
        # bite-axis: FRESHNESS of the transcript against LIVENESS_QUIET_WINDOW_SECONDS —
        # written inside the window is live, outside it is wedged.
        if transcript_age > LIVENESS_QUIET_WINDOW_SECONDS:
            still_stale.append({
                "launchId": lid,
                "state": hb_states.get(lid),
                "transcriptAgeSeconds": round(transcript_age, 3),
                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
            })
    return still_stale


def _pr_numbers_from_rows(parsed):
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


def _stack_deadline_at(remaining):
    """The seconds left on the watch's deadline (measured on the injected monotonic) as the absolute
    time.monotonic() deadline_at the stack_check readers take."""
    return time.monotonic() + remaining


def _resolve_repo_slug(repo_root, deadline, monotonic, gh_run, env, granted=False):
    """Return (slug, refusal). Returns (None, None) when budget is below the poll minimum; otherwise exactly one is non-None. Never raises.

    granted=True means the caller already decided a request is worth starting and
    handed over this budget: only a spent budget is refused, and the read keeps at
    least the poll minimum, so elapsed bookkeeping cannot flip the caller's decision.
    """
    remaining = deadline - monotonic()
    if remaining < (0.0 if granted else _MIN_PR_POLL_SECONDS) or remaining <= 0:
        return None, None
    timeout = min(30.0, remaining)
    if granted:
        timeout = max(_MIN_PR_POLL_SECONDS, timeout)
        remaining = max(_MIN_PR_POLL_SECONDS, remaining)
    try:
        slug, refusal = sc.resolve_repo_slug(
            repo_root,
            deadline=remaining,
            timeout=timeout,
            run=gh_run,
            env=_gh_scrub_env(env),
        )
    except Exception:
        return None, {
            "ok": False,
            "reason": sc.REASON_STACK_UNREADABLE,
            "detail": "resolve_repo_slug raised",
        }
    if refusal is not None:
        return None, refusal
    return slug, None


# A tick's one-slot cell for the repository slug holds this until the slug has been resolved.
_SLUG_UNRESOLVED = object()


def _slug_for_read(repo_root, deadline, monotonic, gh_run, env, known_slug, slug_cell):
    """The slug a granted reader uses: the one the tick already knows, else what the tick's cell
    holds, else one resolution that fills the cell. A resolution that failed (None) is cached for
    the tick too, and is not tried again within it; a lookup skipped for a spent budget is not a
    failure, so it leaves the cell unresolved for a later reader with budget. Never raises."""
    if known_slug is not None:
        return known_slug
    if slug_cell is not None and slug_cell[0] is not _SLUG_UNRESOLVED:
        return slug_cell[0]
    slug, refusal_result = _resolve_repo_slug(
        repo_root, deadline, monotonic, gh_run, env, granted=True,
    )
    # bite-axis: SKIPPED LOOKUP — (None, None) is a budget skip, not a result: only a slug or a
    # real refusal fills the cell.
    if slug_cell is not None and (slug is not None or refusal_result is not None):
        slug_cell[0] = slug
    return slug


def _resolve_pr_stack_groups(
    repo_root, deadline, monotonic, gh_run, membership_reader, env, degraded,
    changed_prs, repo_slug,
):
    """Group changed PRs into stacks and ungrouped.

    membership_reader refusals degrade; membership_reader may raise AssertionError
    on a violated internal invariant, which propagates uncaught through this
    function (run/loop catch it as internal-error).
    """
    stacks = []
    ungrouped = []
    covered_prs = set()
    stack_position_maps = {}

    if repo_slug is None:
        return stacks, sorted(changed_prs), stack_position_maps

    for pr_num in sorted(changed_prs):
        # bite-axis: COVERED — a changed PR whose stack was already read costs
        # zero extra membership_reader calls.
        if pr_num in covered_prs:
            continue
        remaining = deadline - monotonic()
        # bite-axis: DEADLINE — remaining below _MIN_PR_POLL_SECONDS stops the
        # walk and marks stack-signal-unavailable; no further membership reads
        # start.
        if remaining < _MIN_PR_POLL_SECONDS:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
            for rest in sorted(changed_prs):
                if rest not in covered_prs and rest not in ungrouped:
                    ungrouped.append(rest)
            break
        # bite-axis: READ-BUDGET — the whole membership read is bounded by the
        # watcher's remaining budget; a read that outlives it refuses rather
        # than returning partial membership.
        read_result = membership_reader(
            pr=pr_num, repo=repo_slug, deadline=remaining,
        )
        if read_result.get("ok"):
            stack_number = read_result["stack"]["number"]
            members = sorted(
                read_result["members"], key=lambda item: item["position"],
            )
            member_prs = [member["number"] for member in members]
            covered_prs.update(member_prs)
            if ungrouped:
                ungrouped[:] = [
                    listed for listed in ungrouped if listed not in covered_prs
                ]
            position_pairs = stack_position_maps.get(stack_number)
            if position_pairs is None:
                position_pairs = []
                stack_position_maps[stack_number] = position_pairs
            for member in members:
                position_pairs.append(
                    (member["position"], member["number"], member.get("state")),
                )
        elif read_result.get("reason") == sc.REASON_NOT_LINKED:
            if pr_num not in covered_prs:
                ungrouped.append(pr_num)
        else:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
            if pr_num not in covered_prs:
                ungrouped.append(pr_num)

    for stack_number in sorted(stack_position_maps):
        position_pairs = stack_position_maps[stack_number]
        seen_numbers = set()
        ordered_prs = []
        for position in sorted({pair[0] for pair in position_pairs}):
            for pair_position, number, _state in sorted(position_pairs):
                if pair_position == position and number not in seen_numbers:
                    ordered_prs.append(number)
                    seen_numbers.add(number)
        stacks.append({
            "stack": stack_number,
            "prs": ordered_prs,
        })
    stacks.sort(key=lambda entry: entry["stack"])
    ungrouped.sort()
    return stacks, ungrouped, stack_position_maps


def _poll_open_pr_numbers(
    repo_root, deadline, monotonic, gh_run, env, degraded, pr_sampled,
):
    """One open-PR-list read per tick. Returns (sorted numbers, ok). Never raises."""
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None, False
    timeout = min(30.0, remaining)
    if timeout < _MIN_PR_POLL_SECONDS:
        return None, False
    try:
        # axis: the REST list is read only on the proxy's GraphQL refusal, inside list_open_prs
        rows, refusal = sc.list_open_prs(
            ("number",),
            run=gh_run,
            timeout=timeout,
            deadline_at=_stack_deadline_at(remaining),
            run_kwargs=dict(cwd=repo_root, env=_gh_scrub_env(env)),
        )
    except Exception:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None, False

    if refusal is not None:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None, False

    numbers = _pr_numbers_from_rows(rows)
    if numbers is None:
        degraded.add(DEGRADATION_PR_SIGNAL_UNAVAILABLE)
        return None, False

    if pr_sampled is not None:
        pr_sampled[0] = True

    return sorted(numbers), True


def _valid_issue_number(value):
    return ll.valid_lane_issue(value)


def _parse_activity_time(value):
    """Epoch seconds for an ISO-8601 UTC `...Z` timestamp, else None. Never raises."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, _CLOUD_ACTIVITY_TIME_FORMAT)
        return parsed.replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def _cloud_activity_query(issues):
    parts = []
    for number in issues:
        parts.append(
            "i%d: issue(number: %d) { updatedAt "
            "closedByPullRequestsReferences(first: 10, includeClosedPrs: true) "
            "{ pageInfo { hasNextPage } nodes { number updatedAt headRefName } } } "
            "b%d: refs(refPrefix: \"refs/heads/\", query: \"%d\", first: 50) "
            "{ pageInfo { hasNextPage } nodes { name target { ... on Commit { committedDate } } } } "
            % (number, number, number, number)
        )
    return _CLOUD_ACTIVITY_QUERY_HEAD + "".join(parts) + _CLOUD_ACTIVITY_QUERY_TAIL


def _has_next_page(connection):
    page_info = connection.get("pageInfo") if isinstance(connection, dict) else None
    return isinstance(page_info, dict) and page_info.get("hasNextPage") is not False


def carries_issue(name, number):
    """Whether a branch name carries the issue number as a whole number (170 is not 17)."""
    return re.search(r"(?<!\d)%d(?!\d)" % number, name) is not None


def _lane_activity_epoch(repository, number):
    """Newest GitHub activity for one issue number, or None when it cannot be read whole."""
    issue = repository.get("i%d" % number)
    branches = repository.get("b%d" % number)
    if not isinstance(issue, dict) or not isinstance(branches, dict):
        return None
    stamps = [issue.get("updatedAt")]
    closing = issue.get("closedByPullRequestsReferences")
    pr_nodes = closing.get("nodes") if isinstance(closing, dict) else None
    if not isinstance(pr_nodes, list):
        return None
    # A truncated page is a partial read: never let it stand for "no newer activity".
    if _has_next_page(closing):
        return None
    for pr_node in pr_nodes:
        if not isinstance(pr_node, dict):
            return None
        stamps.append(pr_node.get("updatedAt"))
    branch_nodes = branches.get("nodes")
    if not isinstance(branch_nodes, list) or _has_next_page(branches):
        return None
    # The refs query matches substrings, so keep only a branch carrying this issue number
    # as a whole number.
    for node in branch_nodes:
        if not isinstance(node, dict) or not isinstance(node.get("name"), str):
            return None
        # bite-axis: WHOLE NUMBER — a branch for issue 170 is not activity on issue 17.
        if not carries_issue(node["name"], number):
            continue
        target = node.get("target")
        stamps.append(target.get("committedDate") if isinstance(target, dict) else None)
    epochs = [_parse_activity_time(stamp) for stamp in stamps]
    if any(epoch is None for epoch in epochs):
        return None
    return max(epochs)


class _RestUnreadable(Exception):
    """A REST part of the cloud activity read failed, or cannot be established whole."""


# What GraphQL's `first:` returns for one issue; a longer list is a partial read (hasNextPage).
_ACTIVITY_PR_LIMIT = 10
_ACTIVITY_BRANCH_LIMIT = 50
_MANUAL_LINK_EVENTS = ("connected", "disconnected")


# GitHub's closing connection: the keyword and its reference sit together on one line, the
# reference being #n, owner/repo#n or an issue URL. (Not the shared first-line CLOSES_RE, which
# lets \s+ cross paragraphs and cannot read a URL.)
_CLOSING_REF_RE = re.compile(
    sc.CLOSING_KEYWORD + r"[ \t]*:?[ \t]+"
    r"(?:(?P<slug>[^/\s#]+/[^/\s#]+)#(?P<n>\d+)(?!\w)|#(?P<bare>\d+)(?!\w)"
    r"|https?://(?:www\.)?github\.com/(?P<uslug>[^/\s#]+/[^/\s#]+)/issues/(?P<un>\d+)(?![\w/]))",
    re.IGNORECASE)


def _closing_pr_numbers_rest(timeline, slug, number):
    """The PR numbers whose body names this repository's issue with a closing keyword. Raises
    _RestUnreadable for a link the REST timeline cannot name or a closing link from another repository."""
    # axis: a manual link names no PR in the REST timeline, so the closing set cannot be established
    if any(isinstance(row, dict) and row.get("event") in _MANUAL_LINK_EVENTS for row in timeline):
        raise _RestUnreadable("manual link")
    found = {}
    for row in timeline:
        if not isinstance(row, dict):
            raise _RestUnreadable("timeline row")
        if row.get("event") != "cross-referenced":
            continue
        source = row.get("source")
        issue = source.get("issue") if isinstance(source, dict) else None
        if not isinstance(issue, dict):
            raise _RestUnreadable("cross-reference without an issue")
        if "pull_request" not in issue:
            continue
        pr_number = issue.get("number")
        if not isinstance(pr_number, int) or isinstance(pr_number, bool):
            raise _RestUnreadable("cross-reference number")
        body = issue.get("body")
        if body is None:
            body = ""
        if not isinstance(body, str):
            raise _RestUnreadable("cross-reference body")
        repository = issue.get("repository")
        pr_repo = repository.get("full_name") if isinstance(repository, dict) else None
        in_repo = isinstance(pr_repo, str) and pr_repo.lower() == slug.lower()
        names_here = False
        for match in _CLOSING_REF_RE.finditer(body):
            ref_number = match.group("n") or match.group("bare") or match.group("un")
            if ref_number != str(number):
                continue
            target = match.group("slug") or match.group("uslug")
            if target is None:
                # A bare #n names the issue of the repository the pull request is in.
                if not isinstance(pr_repo, str):
                    raise _RestUnreadable("cross-reference repository")
                names_here = names_here or in_repo
            elif target.lower() == slug.lower():
                names_here = True
        if not names_here:
            continue
        # axis: a closing link from another repository is not readable here
        if not in_repo:
            raise _RestUnreadable("cross-repository closing link")
        found[pr_number] = True
    return sorted(found)


def _cloud_activity_repository_rest(
    slug, issues, repo_root, env, gh_run, timeout, deadline_at,
):
    """GraphQL's `data.repository` for the cloud activity query, built from REST reads, or None.

    Any one read that fails, or a completeness REST cannot establish, makes the whole read None,
    as one failed GraphQL query fails every issue. Never raises."""
    run_kwargs = dict(cwd=repo_root, env=_gh_scrub_env(env))
    base = "repos/%s" % slug

    def get(path):
        payload, refusal = sc._transport_rest(
            ["gh", "api", path], timeout, gh_run, None, None, 0,
            deadline_at=deadline_at, run_kwargs=run_kwargs,
        )
        # axis: a failed read makes the whole read None, never a partial answer
        if refusal is not None:
            raise _RestUnreadable(path)
        return payload

    def get_list(path):
        rows, refusal = sc.read_rest_list(
            path, run=gh_run, timeout=timeout, deadline_at=deadline_at, run_kwargs=run_kwargs,
        )
        # axis: a failed page makes the whole read None, never a partial answer
        if refusal is not None:
            raise _RestUnreadable(path)
        return rows

    try:
        default_branch = get(base).get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            return None
        heads = []
        for row in get_list(base + "/branches"):
            commit = row.get("commit") if isinstance(row, dict) else None
            name = row.get("name") if isinstance(row, dict) else None
            sha = commit.get("sha") if isinstance(commit, dict) else None
            if not isinstance(name, str) or not isinstance(sha, str):
                return None
            heads.append((name, sha))
        commit_dates = {}
        repository = {}
        for number in issues:
            issue = get("%s/issues/%d" % (base, number))
            # axis: GraphQL's issue(number:) errors on a pull request, which fails the whole query
            if "pull_request" in issue or issue.get("number") != number:
                return None
            pr_numbers = _closing_pr_numbers_rest(
                get_list("%s/issues/%d/timeline" % (base, number)), slug, number,
            )
            closing = []
            for pr_number in pr_numbers:
                pull = get("%s/pulls/%d" % (base, pr_number))
                pull_base = pull.get("base")
                head = pull.get("head")
                base_ref = pull_base.get("ref") if isinstance(pull_base, dict) else None
                head_ref = head.get("ref") if isinstance(head, dict) else None
                if not isinstance(base_ref, str):
                    return None
                if base_ref != default_branch:
                    snapshot, refusal = sc._parse_rest_pull(pull, slug, pr_number, 0)
                    # axis: a closing keyword counts off the default branch only for a stack layer; a stack read that cannot say makes the whole read None
                    if snapshot is None:
                        if refusal["reason"] == sc.REASON_NOT_LINKED:
                            continue
                        return None
                if not isinstance(head_ref, str) or not isinstance(pull.get("updated_at"), str):
                    return None
                closing.append({
                    "number": pr_number,
                    "updatedAt": pull.get("updated_at"),
                    "headRefName": head_ref,
                })
            repository["i%d" % number] = {
                "updatedAt": issue.get("updated_at"),
                "closedByPullRequestsReferences": {
                    "pageInfo": {"hasNextPage": len(closing) > _ACTIVITY_PR_LIMIT},
                    "nodes": closing[:_ACTIVITY_PR_LIMIT],
                },
            }
            # GraphQL's refs(query:) matches substrings; only a whole-number match is ever read.
            matching = [(name, sha) for name, sha in heads if str(number) in name]
            nodes = []
            for name, sha in matching[:_ACTIVITY_BRANCH_LIMIT]:
                target = {}
                if len(matching) <= _ACTIVITY_BRANCH_LIMIT and carries_issue(name, number):
                    if sha not in commit_dates:
                        committer = get("%s/git/commits/%s" % (base, sha)).get("committer")
                        commit_dates[sha] = committer.get("date") if isinstance(committer, dict) else None
                    if not isinstance(commit_dates[sha], str):
                        return None
                    target = {"committedDate": commit_dates[sha]}
                nodes.append({"name": name, "target": target})
            repository["b%d" % number] = {
                "pageInfo": {"hasNextPage": len(matching) > _ACTIVITY_BRANCH_LIMIT},
                "nodes": nodes,
            }
        return repository
    except Exception:
        return None


def _fetch_cloud_activity(
    repo_root, issues, deadline, monotonic, gh_run, env, known_slug, slug_cell=None,
):
    """One GraphQL read for every issue; {issue: epoch or None}. None = unreadable. Never raises.

    Returns None (not a mapping) when no request could start for lack of time budget,
    so the caller does not cache a read that was never made.
    """
    unreadable = {number: None for number in issues}
    # The caller decided whether a request is worth starting and granted the budget; this
    # reader only refuses a budget that is already spent. It never re-compares the grant
    # against the one-request minimum, so elapsed bookkeeping cannot flip that decision.
    if deadline - monotonic() <= 0:
        return None
    slug = _slug_for_read(repo_root, deadline, monotonic, gh_run, env, known_slug, slug_cell)
    if slug is None:
        return unreadable
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None
    # A granted request always gets at least one request's minimum (the documented overrun).
    timeout = max(_MIN_PR_POLL_SECONDS, min(30.0, remaining))
    owner, _sep, name = slug.partition("/")
    argv = [
        "gh", "api", "graphql",
        "-f", "owner=%s" % owner,
        "-f", "name=%s" % name,
        "-f", "query=%s" % _cloud_activity_query(issues),
    ]
    try:
        proc = gh_run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_root,
            env=_gh_scrub_env(env),
        )
        if proc.returncode != 0:
            # axis: only the proxy's GraphQL refusal re-reads through REST; any other failure stays unreadable
            if not sc._is_graphql_proxy_refusal_proc(proc):
                return unreadable
            repository = _cloud_activity_repository_rest(
                slug, issues, repo_root, env, gh_run, timeout,
                _stack_deadline_at(deadline - monotonic()),
            )
            if repository is None:
                return unreadable
            return {
                number: _lane_activity_epoch(repository, number) for number in issues
            }
        parsed = json.loads(proc.stdout)
        if not isinstance(parsed, dict) or "errors" in parsed:
            return unreadable
        data = parsed.get("data")
        repository = data.get("repository") if isinstance(data, dict) else None
        if not isinstance(repository, dict):
            return unreadable
        return {
            number: _lane_activity_epoch(repository, number) for number in issues
        }
    except Exception:
        return unreadable


def _cloud_activity_age(info, activity_time, now):
    """Seconds since a cloud lane's last activity; its start, or a fix order's time, counts when later."""
    reference = activity_time
    # axis: a reopened lane's quiet is measured from its fix order, never from the activity before it — see bite-proof record wo_2148_fix_order.md
    for key in ("startedTs", "reopenedAt"):
        if _finite_number(info.get(key)):
            reference = max(reference, info[key])
    return now - reference


def _evaluate_cloud_activity(
    repo_root, live_lanes, *, deadline, env, gh_run, monotonic, degraded,
    cloud_state, known_slug=None, slug_cell=None,
):
    """Stale started cloud lanes by their GitHub activity. No request without one."""
    started = {
        lid: info for lid, info in live_lanes.items()
        if _is_cloud_lane(info) and info.get("started")
    }
    if not started:
        return []
    issues = sorted({
        info.get("issue") for info in started.values()
        if _valid_issue_number(info.get("issue"))
    })
    activity = {}
    if issues:
        if cloud_state is None:
            cloud_state = [None]
        read_at = monotonic()
        cached = cloud_state[0]
        if (
            cached is not None
            and 0 <= read_at - cached[0] < CLOUD_ACTIVITY_POLL_SECONDS
            and all(number in cached[1] for number in issues)
        ):
            activity = cached[1]
        else:
            activity = _fetch_cloud_activity(
                repo_root, issues, deadline, monotonic, gh_run, env, known_slug, slug_cell,
            )
            if activity is None:
                # Skipped for lack of budget: no request was made, so leave the cache alone.
                activity = {number: None for number in issues}
            else:
                cloud_state[0] = (read_at, activity)
    now = time.time()
    stale = []
    for lid in sorted(started):
        info = started[lid]
        # bite-axis: NO RAISE — a lane whose issue is not a usable number was never
        # requested, so it reads as unavailable; looking it up (a list or dict is an
        # unhashable key) must not raise.
        if not _valid_issue_number(info.get("issue")):
            degraded.add(DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE)
            continue
        activity_time = activity.get(info.get("issue"))
        # bite-axis: DISCLOSURE — a read that could not be made is neither stale nor clean.
        if activity_time is None:
            degraded.add(DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE)
            continue
        age = _cloud_activity_age(info, activity_time, now)
        # bite-axis: QUIET WINDOW — activity quiet past the window is stale; a
        # future-dated reference fails toward the alert like a future-dated transcript.
        if age < 0 or age > LIVENESS_QUIET_WINDOW_SECONDS:
            stale.append({
                "launchId": lid,
                "state": None,
                "place": ll.PLACE_CLOUD,
                "activityAgeSeconds": round(age, 3),
                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
                "cloudSessionName": info.get("cloudSessionName"),
                "cloudSessionId": info.get("cloudSessionId"),
            })
    return stale


def _answered_notes_path(repo_root, env, *, create):
    """The answered-notes file's path. `create` is required: the note read passes False, so no
    ledger directory is made by a read; `note_answered` passes True, since it writes the file."""
    resolved = ll.ledger_path(repo_root, env=env, create=create)
    if not resolved["ok"]:
        return None
    return os.path.join(
        os.path.dirname(resolved["path"]), BUILDER_NOTES_ANSWERED_NAME,
    )


def _load_answered_notes(path):
    """(answered comment ids, readable). A missing file is readable and empty."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parsed = json.load(handle)
    except FileNotFoundError:
        return set(), True
    except (OSError, ValueError):
        return set(), False
    ids = parsed.get("answered") if isinstance(parsed, dict) else None
    if not isinstance(ids, list) or not all(_valid_positive_int(i) for i in ids):
        return set(), False
    return set(ids), True


def _parse_http_response(stdout):
    """(status, lower-cased headers, body) from `gh api -i` stdout, else None."""
    if not isinstance(stdout, str):
        return None
    parts = re.split(r"\r?\n\r?\n", stdout, maxsplit=1)
    lines = parts[0].splitlines()
    status = re.match(r"HTTP/\S+\s+(\d{3})\b", lines[0]) if lines else None
    if status is None:
        return None
    headers = {}
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        if colon:
            headers[name.strip().lower()] = value.strip()
    return int(status.group(1)), headers, parts[1] if len(parts) > 1 else ""


def _read_issue_comments(
    repo_root, since, deadline, monotonic, gh_run, env, known_slug, note_state, slug_cell=None,
):
    """(state, comments): state True read, False unreadable, None no request made. Never raises.

    A False after page one still carries the comments already read: a note seen on an
    earlier page stays observed while the incomplete read is disclosed. Only a complete
    read is cached.
    """
    if deadline - monotonic() <= 0:
        return None, []
    slug = _slug_for_read(repo_root, deadline, monotonic, gh_run, env, known_slug, slug_cell)
    if slug is None:
        return False, []
    url = "repos/%s/issues/comments?since=%s&per_page=100" % (slug, since)
    stored = note_state[0]
    # A stored read answers only for the same URL: another `since` is another list.
    if stored is not None and stored[0] != url:
        stored = None
    comments = []
    try:
        for page in range(1, _NOTE_COMMENTS_MAX_PAGES + 1):
            remaining = deadline - monotonic()
            if remaining <= 0:
                return (None, []) if page == 1 else (False, comments)
            argv = ["gh", "api", "-i"]
            # bite-axis: VALIDATOR — the stored ETag rides the first page's request.
            if page == 1 and stored is not None and stored[1]:
                argv += ["-H", "If-None-Match: %s" % stored[1]]
            argv.append(url if page == 1 else "%s&page=%d" % (url, page))
            proc = gh_run(
                argv,
                capture_output=True,
                text=True,
                timeout=max(_MIN_PR_POLL_SECONDS, min(30.0, remaining)),
                cwd=repo_root,
                env=_gh_scrub_env(env),
            )
            # The exit code is not read: gh exits 1 on a 304, which is no failure.
            response = _parse_http_response(proc.stdout)
            if response is None:
                return False, comments
            status, headers, body = response
            if status == 304 and page == 1:
                return (True, stored[2]) if stored is not None else (False, [])
            if status != 200:
                return False, comments
            parsed = json.loads(body)
            if not isinstance(parsed, list):
                return False, comments
            comments.extend(parsed)
            if not _NOTE_LINK_NEXT.search(headers.get("link", "")):
                # One page's ETag cannot vouch for later pages, so only a one-page read
                # is conditional next time.
                # A full first page may have a page two a later note lands on, so only a
                # short one-page read is conditional next time.
                etag = (
                    headers.get("etag") if page == 1 and len(comments) < 100 else None
                )
                note_state[0] = (url, etag, comments)
                return True, comments
        return False, comments
    except Exception:
        return False, comments


def _finite_number(value):
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _note_cutoff(info):
    """When the lane's attempt began for note purposes, else None.

    The reserved record is written before the launch command runs; the started record only
    after it returns, so a session can post its question in between. The started time is
    the fallback when the reserved time is not a finite number.
    """
    for key in ("reservedTs", "startedTs"):
        if _finite_number(info.get(key)):
            return info[key]
    return None


def _read_cutoff(info):
    """The earliest comment the read needs for a lane: a reopened lane's fix order, else its note cutoff."""
    return info["reopenedAt"] if "reopenedAt" in info else _note_cutoff(info)


def _in_window(info, key, close):
    """Whether a comment keyed `key` (created epoch, comment id) is in the lane's window: at or after a
    reopened lane's reopenedAt, and not after its close key (None when the lane has none)."""
    # axis: a reopened lane's comments from before its fix order are not its own, so an old note or ending never re-fires — see bite-proof record wo_2148_fix_order.md
    if "reopenedAt" in info and key[0] < info["reopenedAt"]:
        return False
    # axis: the close is a (created, comment id) key, so a comment sharing the closing second but posted after it is outside the window — see bite-proof record wo_2148_fix_order.md
    return close is None or key <= close


def _comment_lane(comment, watched):
    """(launch id, issue number, created epoch) of the watched lane a comment is for, else None.

    The one lane-assignment rule for every comment the cloud read surfaces. A malformed
    element is no lane's.
    """
    if not isinstance(comment, dict):
        return None
    issue_url = comment.get("issue_url")
    created = _parse_activity_time(comment.get("created_at"))
    if created is None or not isinstance(issue_url, str):
        return None
    match = re.search(r"/issues/(\d+)$", issue_url)
    number = int(match.group(1)) if match else None
    # bite-axis: WATCHED ISSUE — a comment on an issue no watched lane has is no lane's.
    on_issue = [lid for lid in watched if watched[lid]["issue"] == number]
    # bite-axis: STARTED — an earlier lane's comment on the same issue is not this lane's.
    lanes = [lid for lid in on_issue if created >= _note_cutoff(watched[lid])]
    if not lanes:
        return None
    lid = max(lanes, key=lambda lane: (_note_cutoff(watched[lane]), lane))
    return lid, number, created


def _builder_note(comment, watched, answered, closes=None):
    """The note a comment is for one watched lane, else None. A malformed element is skipped.

    A reopened lane's note is in its window `[reopenedAt, close]`, `closes` being `_cloud_closes`."""
    if not isinstance(comment, dict):
        return None
    comment_id = comment.get("id")
    issue_url, body = comment.get("issue_url"), comment.get("body")
    created = _parse_activity_time(comment.get("created_at"))
    if not _valid_positive_int(comment_id) or created is None:
        return None
    if not isinstance(issue_url, str) or not isinstance(body, str):
        return None
    # bite-axis: HEADER — only a body opening with the builder-note header is a note.
    if not body.lstrip().startswith(cb.NOTE_HEADER):
        return None
    # bite-axis: ANSWERED — a note the advisor recorded answered stops surfacing.
    if comment_id in answered:
        return None
    lane = _comment_lane(comment, watched)
    if lane is None:
        return None
    lid, number, lane_created = lane
    info = watched[lid]
    if not _in_window(info, (lane_created, comment_id), (closes or {}).get(lid)):
        return None
    return {
        "launchId": lid,
        "issue": number,
        "commentId": comment_id,
        "url": comment.get("html_url"),
        "createdAt": comment["created_at"],
        "cloudSessionName": info.get("cloudSessionName"),
        "cloudSessionId": info.get("cloudSessionId"),
        "configDir": info.get("configDir"),
    }


_TERMINAL_STATE = {"handback": "handback", "stop": "stopped", "park": "parked"}


def _cloud_note_times(comments, watched):
    """{launch id: created epoch of the lane's newest builder note}, answered or not.

    Never raises on a malformed element: one without a string body, the note header or a lane is skipped.
    """
    newest = {}
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if not isinstance(body, str) or not body.lstrip().startswith(cb.NOTE_HEADER):
            continue
        lane = _comment_lane(comment, watched)
        if lane is None:
            continue
        lid, _number, created = lane
        if lid not in newest or created > newest[lid]:
            newest[lid] = created
    return newest


def _phase_reads_resumed(phase):
    """Whether a progress phase reads as resumed: a non-empty string with no word starting park or stop, or one starting resum."""
    if not isinstance(phase, str) or not phase:
        return False
    words = re.findall(r"[a-z]+", phase.lower())
    return not any(word.startswith(("park", "stop")) for word in words) or any(
        word.startswith("resum") for word in words
    )


def _park_superseded(lid, parked_at, progress, note_times):
    """Whether a lane's park created at `parked_at` is superseded by the lane's later builder activity."""
    progress_at = progress[lid]["updatedEpoch"] if lid in progress else None
    if (progress_at is not None
            and progress_at - parked_at > PARK_SUPERSESSION_GRACE_SECONDS
            and _phase_reads_resumed(progress[lid]["phase"])):
        return True
    return lid in note_times and note_times[lid] > parked_at


def _cloud_endings(comments, watched):
    """(launch id, issue, created epoch, comment, kind) of each ending comment on a watched lane.

    An ending is a comment whose first line is a terminal header, or the handover wording; any other
    comment is free-form. Never raises on a malformed element.
    """
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        comment_id, body = comment.get("id"), comment.get("body")
        if not _valid_positive_int(comment_id) or not isinstance(body, str):
            continue
        # bite-axis: HEADER — only a body whose first line is a terminal header (or the
        # handover wording) is an ending; any other comment is free-form.
        kind = cb.terminal_kind(body)
        if kind is None:
            continue
        lane = _comment_lane(comment, watched)
        if lane is not None:
            yield (*lane, comment, kind)


def _cloud_closes(comments, watched):
    """{launch id: (created epoch, comment id) of the close} for each reopened watched lane whose comments show one."""
    return {lid: close for lid, (close, _kind) in _cloud_close_kinds(comments, watched).items()}


def _cloud_close_kinds(comments, watched):
    """{launch id: ((created epoch, comment id) of the close, its ending kind)} for each reopened watched lane showing one.

    The close is the lane's first ending (handback, stop, park or handover) created at or after its
    reopenedAt that is not a superseded park, by the same rule `_cloud_terminals` applies. The kind
    travels with the close so a later partial read can tell a park close, which later activity can
    supersede, from a handback, stop or handover close, which stays.
    """
    reopened = {lid for lid, info in watched.items() if "reopenedAt" in info}
    if not reopened:
        return {}
    progress = _cloud_progress(comments, watched)
    note_times = _cloud_note_times(comments, watched)
    endings = sorted(
        (created, comment["id"], lid, kind)
        for lid, _number, created, comment, kind in _cloud_endings(comments, watched)
        if lid in reopened and created >= watched[lid]["reopenedAt"]
    )
    closes = {}
    for created, comment_id, lid, kind in endings:
        # axis: the first ending that is not a superseded park closes a reopened lane, so a later note or ending is not its own — see bite-proof record wo_2148_fix_order.md
        if lid not in closes and not (
                kind == "park" and _park_superseded(lid, created, progress, note_times)):
            closes[lid] = ((created, comment_id), kind)
    return closes


def _cloud_terminals(comments, watched, answered, closes=None):
    """One lane-terminal entry per watched lane whose newest ending comment is unanswered.

    A park the same lane's later builder note, or progress edit, supersedes surfaces nothing. A note
    supersedes when created strictly after the park. A progress edit supersedes only when it is more
    than PARK_SUPERSESSION_GRACE_SECONDS after the park and its phase reads resumed (no word beginning
    park or stop, unless a word begins resum). A reopened lane's endings are those in its window
    `[reopenedAt, close]` (`closes` defaults to `_cloud_closes`). Never raises on a malformed element.
    Sorted by launch id.
    """
    progress = _cloud_progress(comments, watched)
    note_times = _cloud_note_times(comments, watched)
    if closes is None:
        closes = _cloud_closes(comments, watched)
    newest = {}
    for lid, number, created, comment, kind in _cloud_endings(comments, watched):
        # axis: a reopened lane's ending from before its fix order, or after its close, is not the lane's, with no fallback to it — see bite-proof record wo_2148_fix_order.md
        key = (created, comment["id"])
        if not _in_window(watched[lid], key, closes.get(lid)):
            continue
        # bite-axis: NEWEST — the lane's newest ending comment decides, never an older one.
        if lid not in newest or key > newest[lid][0]:
            newest[lid] = (key, kind, comment, number)
    entries = []
    for lid, (key, kind, comment, number) in newest.items():
        # bite-axis: HANDOVER — a newer handover means the lane moved on: no entry, and no
        # fallback to an older comment.
        if kind == "handover":
            continue
        # bite-axis: ANSWERED — a comment the advisor recorded answered stops surfacing.
        if comment["id"] in answered:
            continue
        # bite-axis: SUPERSEDED — a park is not terminal once the same lane has a builder note
        # strictly later than it, or a progress edit more than PARK_SUPERSESSION_GRACE_SECONDS later
        # whose phase reads resumed (a builder edits its progress seconds after a park, with a parked
        # phase: not a resume); no older ending is read in its place; a handback or stop is never
        # superseded, and a tie, or exactly the window, keeps the park.
        if kind == "park" and _park_superseded(lid, key[0], progress, note_times):
            continue
        info = watched[lid]
        entries.append({
            "launchId": lid,
            "state": _TERMINAL_STATE[kind],
            "kind": kind,
            "issue": number,
            "commentId": comment["id"],
            "url": comment.get("html_url"),
            "createdAt": comment["created_at"],
            "source": "comment",
            "cloudSessionName": info.get("cloudSessionName"),
            "cloudSessionId": info.get("cloudSessionId"),
            "configDir": info.get("configDir"),
        })
    return sorted(entries, key=lambda entry: entry["launchId"])


def _cloud_progress(comments, watched):
    """{launch id: the lane's progress comment} from one comments read; the lane's most recently updated wins.

    An entry is `commentId`, `updatedAt`, `updatedEpoch`, `phase` and `expectedSeconds`. Never raises
    on a malformed element: one without a usable id, string body, progress header or readable
    `updated_at` is skipped.
    """
    newest = {}
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        comment_id, body = comment.get("id"), comment.get("body")
        if not _valid_positive_int(comment_id) or not isinstance(body, str):
            continue
        # bite-axis: HEADER — only a body whose first line is the progress header is a progress comment.
        fields = cb.parse_progress(body)
        if fields is None:
            continue
        updated = _parse_activity_time(comment.get("updated_at"))
        if updated is None:
            continue
        lane = _comment_lane(comment, watched)
        if lane is None:
            continue
        key = (updated, comment_id)
        # bite-axis: NEWEST — the lane's most recently updated progress comment decides.
        if lane[0] not in newest or key > newest[lane[0]][0]:
            newest[lane[0]] = (key, {
                "commentId": comment_id,
                "updatedAt": comment["updated_at"],
                "updatedEpoch": updated,
                "phase": fields["phase"],
                "expectedSeconds": fields["expectedSeconds"],
            })
    return {lid: entry for lid, (_key, entry) in newest.items()}


def _apply_cloud_progress(stale_cloud_launches, live_lanes, progress, now):
    """The stale cloud lanes after progress comments decide for the lanes that have one.

    A lane with a progress comment loses its activity entry and is stale only by the comment's
    age; every other lane's entry stays. Sorted by launch id.
    """
    # bite-axis: PROGRESS — a lane with a progress comment is stale by that comment alone: a
    # builder inside its stated step is not stale however quiet its GitHub activity, and one past
    # it is stale however fresh the activity.
    decided = {
        lid: live_lanes[lid] for lid in progress
        if lid in live_lanes and _is_cloud_lane(live_lanes[lid]) and live_lanes[lid].get("started")
    }
    stale = [entry for entry in stale_cloud_launches if entry["launchId"] not in decided]
    for lid in sorted(decided):
        entry = progress[lid]
        updated = entry["updatedEpoch"]
        # axis: a reopened lane's progress comment ages from its fix order, not from its last edit before it — see bite-proof record wo_2148_fix_order.md
        if _finite_number(decided[lid].get("reopenedAt")):
            updated = max(updated, decided[lid]["reopenedAt"])
        age = now - updated
        if age < 0 or age > entry["expectedSeconds"] + LIVENESS_QUIET_WINDOW_SECONDS:
            stale.append({
                "launchId": lid,
                "state": None,
                "place": ll.PLACE_CLOUD,
                "progressAgeSeconds": round(age, 3),
                "progressExpectedSeconds": entry["expectedSeconds"],
                "phase": entry["phase"],
                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
                "cloudSessionName": decided[lid].get("cloudSessionName"),
                "cloudSessionId": decided[lid].get("cloudSessionId"),
            })
    return sorted(stale, key=lambda entry: entry["launchId"])


def _evaluate_cloud_comments(
    repo_root, live_lanes, *, deadline, env, gh_run, monotonic, degraded,
    note_state, known_slug=None, slug_cell=None, progress_out=None, closed_out=None, unread_out=None,
    known_closes=None,
):
    """(notes, cloud_terminals) on live started cloud lanes' issues, from one comments read.

    Notes are unanswered builder notes by comment id; terminals are the lanes whose newest
    ending comment is a handback, stop or park not recorded answered. `progress_out` is a one-slot
    list: when a request was made (complete or partial) its slot is set to `_cloud_progress` over what
    was observed, possibly `{}`; on every return where no request was made the slot is left as the
    caller set it. `closed_out` is a one-slot list set to the closes of the reopened lanes the complete read
    shows closed ({launch id: created epoch}, `_cloud_closes`); a read that made no request or was partial
    shows none, so the slot is left as the caller set it. `known_closes` is the closes an earlier complete
    read showed for the lanes' current reopening ({launch id: (close epoch, ending kind)}): a partial read
    filters notes and endings by them, after dropping from it (in place) each park close the observed
    comments show superseded. `unread_out` is a dict that gains {launch id: issue} for each watched
    lane when a request was made and came back partial: any watched issue may hold a comment on an unread page.
    """
    watched = {
        lid: info for lid, info in live_lanes.items()
        if _is_cloud_lane(info) and info.get("started")
        and _valid_issue_number(info.get("issue"))
        and _note_cutoff(info) is not None
    }
    if not watched:
        return [], []
    if note_state is None:
        note_state = [None]
    try:
        since = datetime.fromtimestamp(
            min(_read_cutoff(info) for info in watched.values()), tz=timezone.utc,
        ).strftime(_CLOUD_ACTIVITY_TIME_FORMAT)
    except (ValueError, OverflowError, OSError):
        degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)
        return [], []
    state, comments = _read_issue_comments(
        repo_root, since, deadline, monotonic, gh_run, env, known_slug, note_state, slug_cell,
    )
    if state is None:
        # A watched channel that was never sampled for lack of budget is disclosed.
        degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)
        return [], []
    if not state:
        # Disclose the incomplete read, but still evaluate whatever was observed.
        degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)
        # axis: only a request that came back partial names the issues it left unread, never a tick that made none — see bite-proof record wo_2148_fix_order.md
        _record_unread(unread_out, watched)
    if isinstance(progress_out, list) and progress_out:
        progress_out[0] = _cloud_progress(comments, watched)
    path = _answered_notes_path(repo_root, env, create=False)
    answered =_load_answered_notes(path)[0] if path is not None else set()
    # axis: a partial read filters notes and endings by the closes a complete read showed, never by an empty map — see bite-proof record wo_2148_fix_order.md
    close_kinds = _cloud_close_kinds(comments, watched) if state else {}
    closes = {lid: close for lid, (close, _kind) in close_kinds.items()}
    if not state and known_closes:
        progress = _cloud_progress(comments, watched)
        note_times = _cloud_note_times(comments, watched)
        for lid, (close, kind) in list(known_closes.items()):
            if lid not in watched:
                continue
            # axis: a cached park close that the comments a partial read observed show superseded is dropped from the cache, never kept to filter out the note that superseded it — see bite-proof record wo_2148_fix_order.md
            if kind == "park" and _park_superseded(lid, close[0], progress, note_times):
                del known_closes[lid]
                continue
            closes[lid] = close
    # axis: only a complete read sets the closed slot, so a partial read is never taken for "no close" — see bite-proof record wo_2148_fix_order.md
    if state and isinstance(closed_out, list) and closed_out:
        closed_out[0] = dict(close_kinds)
    notes = [_builder_note(comment, watched, answered, closes) for comment in comments]
    notes = sorted(
        (note for note in notes if note is not None),
        key=lambda note: note["commentId"],
    )
    return notes, _cloud_terminals(comments, watched, answered, closes)


def _record_unread(unread_out, watched):
    # axis: a comments read that did not complete names every watched issue it may have left unread — see bite-proof record wo_2148_fix_order.md
    if unread_out is not None:
        unread_out.update({lid: info["issue"] for lid, info in watched.items()})


def _unread_payload(unread):
    """The `unreadIssues` result key: [{launchId, issue}] by launch id; {} when no issue went unread."""
    return {"unreadIssues": [
        {"launchId": lid, "issue": issue} for lid, issue in sorted(unread.items())
    ]} if unread else {}


def _parse_comment_id(value):
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    return value if _valid_positive_int(value) else None


def note_answered(repo_root, comment_id, *, env=None):
    """Record a builder note's or a cloud terminal comment's id as answered. Never raises.

    Two concurrent calls can lose one id; that note surfaces again, which fails toward
    the advisor seeing it.
    """
    try:
        if env is None:
            env = os.environ
        number = _parse_comment_id(comment_id)
        if number is None:
            return {"ok": False, "reason": REFUSAL_COMMENT_ID_INVALID}
        if not _valid_repo_root(repo_root):
            return {"ok": False, "reason": REFUSAL_REPO_ROOT_INVALID}
        path = _answered_notes_path(repo_root, env, create=True)
        if path is None:
            return {"ok": False, "reason": REFUSAL_STORE_UNRESOLVABLE}
        answered, readable = _load_answered_notes(path)
        if not readable:
            return {"ok": False, "reason": REFUSAL_NOTE_ANSWERS_UNREADABLE}
        answered.add(number)
        store_core.atomic_write(
            path, json.dumps({"answered": sorted(answered)}, sort_keys=True) + "\n",
        )
        return {"ok": True, "commentId": number, "path": path}
    except OSError:
        return {"ok": False, "reason": REFUSAL_STORE_UNRESOLVABLE}
    except Exception as exc:
        return {
            "ok": False, "reason": REFUSAL_INTERNAL_ERROR, "detail": type(exc).__name__,
        }


def _cloud_lanes_payload(live_lanes, cloud_state=None, progress_state=None):
    """The `cloudLanes` result key for a batch's live cloud lanes; {} when there are none.

    A lane whose activity was read carries `activityAgeSeconds`; a failed read leaves it out. A
    started lane with a progress comment carries `phase`, `progressAgeSeconds` and
    `progressExpectedSeconds`; one without carries none of the three. A reopened lane (a terminal lane
    sent a fix order) carries `reopenedAt` (UTC ISO) and `reopenedBy`.
    """
    cached = cloud_state[0][1] if cloud_state and cloud_state[0] else {}
    progress = progress_state[0] if progress_state and progress_state[0] else {}
    now = time.time()
    entries = []
    for lid, info in sorted(live_lanes.items()):
        if not _is_cloud_lane(info):
            continue
        entry = {
            "launchId": lid,
            "issue": info.get("issue"),
            "cloudSessionName": info.get("cloudSessionName"),
            "cloudSessionId": info.get("cloudSessionId"),
        }
        if _finite_number(info.get("reopenedAt")):
            try:
                entry["reopenedAt"] = datetime.fromtimestamp(
                    info["reopenedAt"], tz=timezone.utc).strftime(_CLOUD_ACTIVITY_TIME_FORMAT)
            except (ValueError, OverflowError, OSError):
                pass
            entry["reopenedBy"] = info.get("reopenedBy")
        activity_time = (
            cached.get(info.get("issue")) if _valid_issue_number(info.get("issue")) else None
        )
        if info.get("started") and activity_time is not None:
            entry["activityAgeSeconds"] = round(_cloud_activity_age(info, activity_time, now), 3)
        if info.get("started") and lid in progress:
            entry["phase"] = progress[lid]["phase"]
            entry["progressAgeSeconds"] = round(now - progress[lid]["updatedEpoch"], 3)
            entry["progressExpectedSeconds"] = progress[lid]["expectedSeconds"]
        entries.append(entry)
    return {"cloudLanes": entries} if entries else {}


def _evaluate_pr_set_changed(
    open_pr_numbers, pr_state, repo_root, deadline, monotonic, gh_run,
    membership_reader, env, degraded, repo_slug,
):
    if open_pr_numbers is None:
        return None
    pr_set = set(open_pr_numbers)
    pr_baseline = pr_state[0]
    if pr_baseline is None:
        pr_state[0] = pr_set
        return None
    if pr_set == pr_baseline:
        return None
    added = sorted(pr_set - pr_baseline)
    removed = sorted(pr_baseline - pr_set)
    changed_prs = added + removed
    stacks, ungrouped, _position_maps = _resolve_pr_stack_groups(
        repo_root, deadline, monotonic, gh_run, membership_reader, env,
        degraded, changed_prs, repo_slug,
    )
    pr_state[0] = pr_set
    return {
        "prs": sorted(pr_set),
        "prsAdded": added,
        "prsRemoved": removed,
        "stacks": stacks,
        "ungrouped": ungrouped,
    }


def _batch_stack_numbers(batch_lanes):
    stacks = set()
    for info in batch_lanes.values():
        stack = info.get("stack")
        if stack is not None:
            stacks.add(stack)
    return sorted(stacks)


def _layers_planned_for_stack(batch_lanes, stack_number):
    values = set()
    for info in batch_lanes.values():
        if info.get("stack") != stack_number:
            continue
        layers_planned = info.get("layersPlanned")
        if layers_planned is not None:
            values.add(layers_planned)
    return values


def _occupied_layer_positions(batch_lanes, stack_number):
    occupied = set()
    for info in batch_lanes.values():
        if info.get("stack") != stack_number:
            continue
        position = info.get("layerPosition")
        if position is not None:
            occupied.add(position)
    return occupied


def _position_ready_map(
    position_map, repo_slug, deadline, monotonic, gh_run, env, degraded,
    pr_vet_reader=None,
):
    """Return {position: True} for positions READY at current head; None on budget."""
    if pr_vet_reader is None:
        pr_vet_reader = sc.read_pr_vet_state
    ready = {}
    for position in sorted(position_map):
        remaining = deadline - monotonic()
        if remaining < _MIN_PR_POLL_SECONDS:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
            return None
        pr_number = position_map[position]
        state, refusal = pr_vet_reader(
            pr_number,
            repo_slug,
            deadline=remaining,
            run=gh_run,
            env=_gh_scrub_env(env),
        )
        if refusal is not None:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
            continue
        if state.get("state") != "OPEN" or state.get("isDraft"):
            continue
        verdict, vet_refusal = sc.read_vet_verdict(
            state["body"], state["headRefOid"],
        )
        if vet_refusal is not None:
            degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
            continue
        if verdict == sc.VERDICT_READY:
            ready[position] = True
    return ready


def _compute_stack_state_snapshot(
    batch_lanes, open_pr_numbers, repo_root, deadline, monotonic, gh_run,
    membership_reader, env, degraded, repo_slug, pr_vet_reader=None,
):
    """Compute per-stack completion snapshot and idle-seat flags. Never raises."""
    stacks_out = []
    flags = []
    if not _batch_stack_numbers(batch_lanes):
        return {"stacks": stacks_out, "flags": flags}
    if open_pr_numbers is None:
        open_pr_numbers = []

    _stacks, _ungrouped, membership_by_stack = _resolve_pr_stack_groups(
        repo_root,
        deadline,
        monotonic,
        gh_run,
        membership_reader,
        env,
        degraded,
        list(open_pr_numbers),
        repo_slug,
    )

    for stack_number in _batch_stack_numbers(batch_lanes):
        layers_values = _layers_planned_for_stack(batch_lanes, stack_number)
        entry = {
            "stack": stack_number,
            "layersPlanned": None,
            "missingPositions": [],
            "reason": None,
        }
        if not layers_values:
            entry["state"] = STACK_STATE_INCOMPLETE
            entry["reason"] = STACK_REASON_LAYERS_PLANNED_UNKNOWN
            stacks_out.append(entry)
            continue
        if len(layers_values) > 1:
            entry["state"] = STACK_STATE_INCOMPLETE
            entry["reason"] = STACK_REASON_LAYERS_PLANNED_DISAGREED
            stacks_out.append(entry)
            continue

        layers_planned = next(iter(layers_values))
        entry["layersPlanned"] = layers_planned

        position_map = {}
        open_member_positions = set()
        for position, number, state in membership_by_stack.get(stack_number, ()):
            position_map[position] = number
            if state == "OPEN":
                open_member_positions.add(position)
        if not position_map or repo_slug is None:
            entry["state"] = STACK_STATE_INCOMPLETE
            entry["reason"] = STACK_REASON_MEMBERSHIP_UNRESOLVED
            stacks_out.append(entry)
            continue

        ready_positions = _position_ready_map(
            position_map,
            repo_slug,
            deadline,
            monotonic,
            gh_run,
            env,
            degraded,
            pr_vet_reader=pr_vet_reader,
        )
        if ready_positions is None:
            entry["state"] = STACK_STATE_INCOMPLETE
            entry["missingPositions"] = list(range(1, layers_planned + 1))
            stacks_out.append(entry)
            continue

        # A position is occupied when this batch has a lane there or the
        # stack already has an OPEN member PR there (launched in another
        # batch). A member closed without merging leaves its seat idle.
        occupied = _occupied_layer_positions(batch_lanes, stack_number)
        occupied |= open_member_positions
        for position in sorted(ready_positions):
            next_position = position + 1
            if (
                next_position <= layers_planned
                and next_position not in occupied
            ):
                flags.append({
                    "flag": FLAG_IDLE_SEAT_LAUNCHABLE_CHILD,
                    "stack": stack_number,
                    "position": position,
                })

        missing = []
        for position in range(1, layers_planned + 1):
            if position not in position_map or position not in ready_positions:
                missing.append(position)
        if missing:
            entry["state"] = STACK_STATE_INCOMPLETE
            entry["missingPositions"] = missing
            stacks_out.append(entry)
            continue

        entry["state"] = STACK_STATE_COMPLETE
        stacks_out.append(entry)

    return {"stacks": stacks_out, "flags": flags}


def _stack_state_fires(snapshot, baseline):
    if baseline is None:
        return any(
            entry["state"] == STACK_STATE_COMPLETE for entry in snapshot["stacks"]
        ) or bool(snapshot.get("flags"))
    return snapshot != baseline


def _payload_stack_state_changed(ctx):
    open_pr_numbers = ctx.get("open_pr_numbers")
    if open_pr_numbers is None:
        return None
    snapshot = _compute_stack_state_snapshot(
        ctx["batch_lanes"],
        open_pr_numbers,
        ctx["repo_root"],
        ctx["deadline"],
        ctx["monotonic"],
        ctx["gh_run"],
        ctx["membership_reader"],
        ctx["env"],
        ctx["degraded"],
        ctx["repo_slug"],
        pr_vet_reader=ctx.get("pr_vet_reader"),
    )
    stack_state = ctx["stack_state"]
    baseline = stack_state[0]
    if baseline is None and not _stack_state_fires(snapshot, baseline):
        stack_state[0] = snapshot
        return None
    if baseline is not None and snapshot == baseline:
        return None
    # The advance serves a caller that threads stack_state across watch_arm() calls.
    # loop() passes over this event and keeps the advanced baseline for the next arm.
    stack_state[0] = snapshot
    payload = dict(snapshot)
    also = _build_also_observed(
        EVENT_STACK_STATE_CHANGED,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload



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


def _payload_builder_note(ctx):
    notes = ctx["builder_notes"]
    if not notes:
        return None
    payload = {"launchId": notes[0]["launchId"], "notes": notes}
    also = _build_also_observed(
        EVENT_BUILDER_NOTE,
        ctx["terminal_launches"],
        ctx["blocked_launches"],
        ctx["exited_launches"],
        ctx["stale_live_launches"],
    )
    if also is not None:
        payload["alsoObserved"] = also
    return payload


def _payload_pr_set_changed(ctx):
    pr_change = _evaluate_pr_set_changed(
        ctx.get("open_pr_numbers"),
        ctx["pr_state"],
        ctx["repo_root"],
        ctx["deadline"],
        ctx["monotonic"],
        ctx["gh_run"],
        ctx["membership_reader"],
        ctx["env"],
        ctx["degraded"],
        ctx["repo_slug"],
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
    EVENT_BUILDER_NOTE: _payload_builder_note,
    EVENT_STACK_STATE_CHANGED: _payload_stack_state_changed,
    EVENT_PR_SET_CHANGED: _payload_pr_set_changed,
    EVENT_LANE_STALE: _payload_lane_stale,
}

for _event in EVENT_PRECEDENCE:
    if _event != EVENT_TIMER:
        assert _event in _EVENT_PAYLOAD_BUILDERS


def _loop_exits_on(result):
    if result.get("ok") is not True:
        return True
    event = result.get("event")
    if event == EVENT_STACK_STATE_CHANGED:
        for entry in result.get("flags") or ():
            if entry.get("flag") == FLAG_IDLE_SEAT_LAUNCHABLE_CHILD:
                return True
        return False
    return event not in BENIGN_EVENTS


def _utc_started_at():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _passed_over_keys_empty():
    return {
        RESULT_KEY_PASSED_OVER: [],
        RESULT_KEY_PASSED_OVER_COUNT: 0,
    }


def _passed_over_entry(arm, elapsed_seconds, result):
    entry = {
        "arm": arm,
        "elapsedSeconds": round(elapsed_seconds, 3),
        "event": result["event"],
    }
    skip = frozenset({"ok", "batch", "event", "degraded", "batchId"})
    for key, value in result.items():
        if key in skip:
            continue
        entry[key] = value
    return entry


def _append_passed_over(passed_over, passed_over_count, arm, elapsed, result):
    passed_over_count[0] += 1
    passed_over.append(_passed_over_entry(arm, elapsed, result))
    overflow = len(passed_over) - PASSED_OVER_CAP
    if overflow > 0:
        del passed_over[:overflow]


def _read_live_loop_record(lock_fd):
    try:
        os.lseek(lock_fd, 0, os.SEEK_SET)
        raw = os.read(lock_fd, 4096)
    except OSError:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


def _loop_lock_refusal(detail, batch_id):
    result = {
        "ok": False,
        "reason": REFUSAL_LOOP_LOCK_UNAVAILABLE,
        "batchId": batch_id,
        "detail": detail,
        "arms": 0,
    }
    result.update(_passed_over_keys_empty())
    return result


def _loop_already_live_refusal(batch_id, live_loop):
    pid = live_loop.get("pid") if isinstance(live_loop, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool):
        detail = "loop-already-live:holder-unreadable"
    else:
        detail = f"loop-already-live:pid={pid}"
    result = {
        "ok": False,
        "reason": REFUSAL_LOOP_ALREADY_LIVE,
        "batchId": batch_id,
        "detail": detail,
        "arms": 0,
        RESULT_KEY_LIVE_LOOP: live_loop,
    }
    result.update(_passed_over_keys_empty())
    return result


def _close_fd_quiet(fd):
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass


def _acquire_loop_lock(repo_root, batch_id, env, log_path):
    opened = ll._open_ledger_dirs(repo_root, env=env)
    if not opened["ok"]:
        reason = opened.get("reason") or "unknown"
        _close_fd_quiet(opened.get("root_fd"))
        _close_fd_quiet(opened.get("repo_fd"))
        return None, _loop_lock_refusal(f"store-door:{reason}", batch_id)

    root_fd = opened["root_fd"]
    repo_fd = opened["repo_fd"]
    locks_fd = None
    lock_fd = None
    try:
        try:
            os.mkdir("wave-watch-locks", 0o700, dir_fd=repo_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            return None, _loop_lock_refusal(
                f"lock-dir-mkdir:{errno.errorcode.get(exc.errno, exc.errno)}",
                batch_id,
            )

        try:
            locks_fd = os.open(
                "wave-watch-locks",
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=repo_fd,
            )
        except OSError as exc:
            return None, _loop_lock_refusal(
                f"lock-dir-open:{errno.errorcode.get(exc.errno, exc.errno)}",
                batch_id,
            )

        lock_name = (
            hashlib.sha256(batch_id.encode("utf-8")).hexdigest() + ".lock"
        )
        try:
            lock_fd = os.open(
                lock_name,
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=locks_fd,
            )
        except OSError as exc:
            return None, _loop_lock_refusal(
                f"lock-file-open:{errno.errorcode.get(exc.errno, exc.errno)}",
                batch_id,
            )

        try:
            lock_stat = os.fstat(lock_fd)
        except OSError as exc:
            return None, _loop_lock_refusal(
                f"lock-file-stat:{errno.errorcode.get(exc.errno, exc.errno)}",
                batch_id,
            )

        if not stat.S_ISREG(lock_stat.st_mode):
            return None, _loop_lock_refusal("lock-file-not-regular", batch_id)

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            live_loop = _read_live_loop_record(lock_fd)
            return None, _loop_already_live_refusal(batch_id, live_loop)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                live_loop = _read_live_loop_record(lock_fd)
                return None, _loop_already_live_refusal(batch_id, live_loop)
            return None, _loop_lock_refusal(
                f"flock:{errno.errorcode.get(exc.errno, exc.errno)}",
                batch_id,
            )

        try:
            os.ftruncate(lock_fd, 0)
            payload = json.dumps({
                "pid": os.getpid(),
                "startedAt": _utc_started_at(),
                "batch": batch_id,
                "log": log_path,
            }) + "\n"
            os.write(lock_fd, payload.encode("utf-8"))
            try:
                os.fsync(lock_fd)
            except OSError:
                pass
        except OSError as exc:
            return None, _loop_lock_refusal(
                f"lock-record-write:{errno.errorcode.get(exc.errno, exc.errno)}",
                batch_id,
            )

        held_fd = lock_fd
        lock_fd = None
        return held_fd, None
    finally:
        _close_fd_quiet(locks_fd)
        _close_fd_quiet(repo_fd)
        _close_fd_quiet(root_fd)
        _close_fd_quiet(lock_fd)


def _release_loop_lock(lock_fd):
    _close_fd_quiet(lock_fd)


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


def _evaluate_tick(
    repo_root,
    batch_id,
    *,
    deadline,
    env,
    gh_run,
    membership_reader,
    monotonic,
    degraded,
    ignore_launch_ids,
    pr_state,
    stack_state,
    pr_sampled,
    first_tick,
    ignore_set,
    cloud_state=None,
    cloud_payload_out=None,
    note_state=None,
    progress_state=None,
    closed_state=None,
    ignore_notes=frozenset(),
    unread_out=None,
):
    batch_lanes, live_lanes, ledger_readable = _derive_batch_lanes(
        repo_root, batch_id, env, degraded, ignore_launch_ids,
    )

    if first_tick[0] and not ledger_readable:
        return _refusal(REFUSAL_LEDGER_UNREADABLE, batch_id)
    first_tick[0] = False

    terminal_launches, blocked_launches, hb_states = (
        _evaluate_lane_heartbeats(
            repo_root, live_lanes, env, degraded,
        )
    )
    exclude_ids = _launch_ids(terminal_launches)
    exited, live_candidates = _evaluate_pid_signals(
        live_lanes, exclude_ids, degraded,
    )
    stale_live_launches = _transcript_cold(
        live_candidates, live_lanes, env, hb_states=hb_states,
        degraded=degraded,
    )
    exited_launches = exited[1] if exited is not None else []

    lane_event_due = _higher_precedence_lane_event_due(
        terminal_launches,
        blocked_launches,
        exited_launches,
        ignore_set,
    )
    stale_cloud_launches = []
    builder_notes = []
    # One slot for the tick: whichever read resolves the repository slug first fills it, and the
    # others reuse it, a failed resolution (None) included.
    slug_cell = [_SLUG_UNRESOLVED]
    if lane_event_due:
        open_pr_numbers = None
        repo_slug = None
    else:
        open_pr_numbers, _pr_poll_ok = _poll_open_pr_numbers(
            repo_root,
            deadline,
            monotonic,
            gh_run,
            env,
            degraded,
            pr_sampled,
        )

        needs_repo_slug = bool(_batch_stack_numbers(batch_lanes))
        if (
            not needs_repo_slug
            and open_pr_numbers is not None
            and pr_state[0] is not None
        ):
            needs_repo_slug = set(open_pr_numbers) != pr_state[0]
        if needs_repo_slug:
            repo_slug, _slug_refusal = _resolve_repo_slug(
                repo_root, deadline, monotonic, gh_run, env,
            )
            if repo_slug is not None or _slug_refusal is not None:
                slug_cell[0] = repo_slug  # a skipped lookup (None, None) stays unresolved for the first granted reader
            if repo_slug is None:
                degraded.add(DEGRADATION_STACK_SIGNAL_UNAVAILABLE)
        else:
            repo_slug = None

        # The cloud read gets half of what is left; the stack and vet reads that
        # follow keep the other half, so a slow cloud endpoint cannot starve them. The
        # share never falls below one request's minimum: a supported one-second arm
        # would otherwise halve to less than the minimum and never sample the cloud
        # (an overrun of that minimum is the loop's documented overrun).
        # The skip-or-start decision (any arm time left) is made here, once; the
        # grant handed to the reader is then a budget the reader cannot disagree with.
        # The cloud share is split in two: the activity read takes its first half and the
        # builder-note read its own second half, so an activity request that consumes its
        # whole grant cannot starve the comments request.
        cloud_now = monotonic()
        arm_remaining = deadline - monotonic()
        if arm_remaining <= 0:
            cloud_deadline = cloud_now
            activity_deadline = cloud_now
        else:
            cloud_deadline = cloud_now + max(
                arm_remaining / 2, _MIN_PR_POLL_SECONDS,
            )
            activity_deadline = cloud_now + max(
                (cloud_deadline - cloud_now) / 2, _MIN_PR_POLL_SECONDS,
            )
        stale_cloud_launches = _evaluate_cloud_activity(
            repo_root, live_lanes, deadline=activity_deadline, env=env, gh_run=gh_run,
            monotonic=monotonic, degraded=degraded, cloud_state=cloud_state,
            known_slug=repo_slug, slug_cell=slug_cell,
        )
        # No fresh clock read: the notes window is fixed from the activity grant, so it
        # still holds one request's minimum after an activity request spends its grant.
        if arm_remaining <= 0:
            notes_deadline = activity_deadline
        else:
            notes_deadline = max(
                cloud_deadline, activity_deadline + _MIN_PR_POLL_SECONDS,
            )
        progress_out = [None]
        closed_out = [None]
        # Stored closes ({launch id: (the reopenedAt it was closed at, its close epoch, its ending kind)})
        # hold only for the reopening they were read at: a newer fix order starts a new window.
        stored_closes = closed_state[0] if closed_state is not None else None
        known_closes = {
            lid: (triple[1], triple[2])
            for lid, triple in (stored_closes if isinstance(stored_closes, dict) else {}).items()
            if lid in live_lanes and live_lanes[lid].get("reopenedAt") == triple[0]
        }
        closes_before = set(known_closes)
        builder_notes, cloud_terminals = _evaluate_cloud_comments(
            repo_root, live_lanes, deadline=notes_deadline, env=env, gh_run=gh_run,
            monotonic=monotonic, degraded=degraded, note_state=note_state,
            known_slug=repo_slug, slug_cell=slug_cell, progress_out=progress_out,
            closed_out=closed_out, unread_out=unread_out, known_closes=known_closes,
        )
        # bite-axis: NOTE IGNORE — a note named by launch id and comment id is dropped here, before
        # the event context is built; every other note, and every other event, is untouched.
        if ignore_notes:
            builder_notes = [
                note for note in builder_notes
                if (note["launchId"], note["commentId"]) not in ignore_notes
            ]
        # A tick whose comments read made no request (budget spent, or no watched lane) reuses the
        # stored snapshot; one that made a request replaces it with what it observed, `{}` included.
        if progress_out[0] is None:
            stored = progress_state[0] if progress_state is not None else None
            progress = stored if isinstance(stored, dict) else {}
        else:
            progress = progress_out[0]
            if progress_state is not None:
                progress_state[0] = progress
        # bite-axis: PROGRESS — the progress comments the same read observed replace the activity
        # verdict for their lanes before the stale set joins the tick's.
        stale_cloud_launches = _apply_cloud_progress(
            stale_cloud_launches, live_lanes, progress, time.time(),
        )
        # A complete read replaces the stored closes ({launch id: (the reopenedAt it was closed at, the
        # close's created epoch, its ending kind)}); a tick without one keeps those whose lane has not
        # been sent a newer fix order since, less each park close a partial read showed superseded.
        if closed_out[0] is not None:
            closed = set(closed_out[0])
            if closed_state is not None:
                closed_state[0] = {
                    lid: (live_lanes[lid].get("reopenedAt"), close, kind)
                    for lid, (close, kind) in closed_out[0].items()
                }
        else:
            # axis: a stored close is kept on a tick with no complete read, only for the reopenedAt it was read at — see bite-proof record wo_2148_fix_order.md
            closed = set(known_closes)
            dropped = closes_before - closed
            if dropped and closed_state is not None and isinstance(closed_state[0], dict):
                closed_state[0] = {
                    lid: triple for lid, triple in closed_state[0].items() if lid not in dropped
                }
        # A reopened lane its comments show closed is no longer watched: never stale, whichever rule said so.
        stale_cloud_launches = [
            entry for entry in stale_cloud_launches if entry["launchId"] not in closed
        ]
        stale_live_launches = stale_live_launches + stale_cloud_launches
        # bite-axis: CLOUD ENDING — a cloud lane's ending comment joins the lane-terminal
        # set before the event is built, so it is reported and seen by alsoObserved.
        terminal_launches.extend(cloud_terminals)

    cloud_payload = _cloud_lanes_payload(live_lanes, cloud_state, progress_state)
    if cloud_payload_out is not None:
        cloud_payload_out.update(cloud_payload)

    event_ctx = {
        "terminal_launches": terminal_launches,
        "blocked_launches": blocked_launches,
        "exited": exited,
        "exited_launches": exited_launches,
        "stale_live_launches": stale_live_launches,
        "batch_lanes": batch_lanes,
        "batch_id": batch_id,
        "degraded": degraded,
        "ignore_set": ignore_set,
        "repo_root": repo_root,
        "deadline": deadline,
        "monotonic": monotonic,
        "gh_run": gh_run,
        "pr_state": pr_state,
        "stack_state": stack_state,
        "open_pr_numbers": open_pr_numbers,
        "pr_sampled": pr_sampled,
        "env": env,
        "membership_reader": membership_reader,
        "repo_slug": repo_slug,
        "builder_notes": builder_notes,
    }

    for event in EVENT_PRECEDENCE:
        if event == EVENT_TIMER:
            break
        payload = _EVENT_PAYLOAD_BUILDERS[event](event_ctx)
        if payload is not None:
            return _event_result(
                event, batch_id, degraded,
                **payload, **cloud_payload, **_unread_payload(unread_out or {}),
            )
    return None


def _timer_at_deadline(
    repo_root,
    batch_id,
    *,
    env,
    degraded,
    ignore_launch_ids,
    pr_sampled,
    add_window_degradations,
    cloud_state=None,
    progress_state=None,
    unread=None,
):
    _batch_lanes, live_lanes, deadline_readable = _derive_batch_lanes(
        repo_root, batch_id, env, degraded,
        ignore_launch_ids,
    )
    if not deadline_readable:
        return _refusal(REFUSAL_LEDGER_UNREADABLE, batch_id)
    if add_window_degradations:
        if _lane_never_stamped_at_deadline(repo_root, live_lanes, env):
            degraded.add(DEGRADATION_LANE_NEVER_STAMPED)
        if not pr_sampled[0]:
            degraded.add(DEGRADATION_PR_SIGNAL_NEVER_SAMPLED)
    return _event_result(
        EVENT_TIMER, batch_id, degraded,
        **_cloud_lanes_payload(live_lanes, cloud_state, progress_state),
        **_unread_payload(unread or {}),
    )


def _loop_attach_passed_over(final, passed_over, passed_over_count):
    final[RESULT_KEY_PASSED_OVER] = list(passed_over)
    final[RESULT_KEY_PASSED_OVER_COUNT] = passed_over_count[0]
    return final


def _loop_pre_arm_refusal(refusal):
    out = dict(refusal)
    out.update(_passed_over_keys_empty())
    return out


def _loop_log_arm_result(
    log_file,
    log_path,
    log_degradation,
    loop_degraded,
    arms,
    elapsed,
    result,
):
    if log_file is not None:
        try:
            _append_log_line(log_file, arms, elapsed, result)
        except OSError:
            loop_degraded.add(DEGRADATION_LOG_UNWRITABLE)
            _close_log_silent(log_file)
            return None, log_degradation
        return log_file, log_degradation
    if log_path is not None and log_degradation is None:
        log_file, log_degradation = _open_log_append(log_path)
        if log_degradation is not None:
            loop_degraded.add(log_degradation)
            return None, log_degradation
        if log_file is not None:
            try:
                _append_log_line(log_file, arms, elapsed, result)
            except OSError:
                loop_degraded.add(DEGRADATION_LOG_UNWRITABLE)
                _close_log_silent(log_file)
                return None, log_degradation
    return log_file, log_degradation


def _ceiling_timer_result(
    batch_id,
    loop_degraded,
    passed_over,
    passed_over_count,
    cloud_lanes=None,
    unread=None,
):
    final = _event_result(
        EVENT_TIMER,
        batch_id,
        loop_degraded,
    )
    if cloud_lanes:
        final["cloudLanes"] = cloud_lanes
    final.update(_unread_payload(unread or {}))
    return _loop_attach_passed_over(final, passed_over, passed_over_count)


def watch_arm(
    repo_root,
    batch_id,
    *,
    max_seconds=2400,
    interval_seconds=60,
    env=None,
    gh_run=None,
    membership_reader=None,
    monotonic=None,
    sleep=None,
    ignore_launch_ids=(),
    ignore_events=(),
    pr_state=None,
    stack_state=None,
    pr_sampled=None,
    cloud_state=None,
    note_state=None,
    progress_state=None,
    closed_state=None,
):
    """Windowed watch — one arm until the first event or arm deadline."""
    batch_for_refusal = batch_id if isinstance(batch_id, str) else None
    try:
        if env is None:
            env = os.environ
        if gh_run is None:
            gh_run = subprocess.run
        if membership_reader is None:
            membership_reader = sc.read_membership
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

        ledger_path_result = ll.ledger_path(repo_root, env=env, create=False)
        if not ledger_path_result["ok"]:
            return _refusal(REFUSAL_STORE_UNRESOLVABLE, batch_id)
        resolved_ledger_path = ledger_path_result["path"]

        if pr_state is None:
            pr_state = [None]
        if stack_state is None:
            stack_state = [None]
        if pr_sampled is None:
            pr_sampled = [False]
        if cloud_state is None:
            cloud_state = [None]
        if note_state is None:
            note_state = [None]
        if progress_state is None:
            progress_state = [None]
        if closed_state is None:
            closed_state = [None]

        start = monotonic()
        deadline = start + max_seconds
        tick = 0
        degraded = set()
        unread = {}
        first_tick = [True]
        ignore_set = _ignore_events_set(ignore_events)
        ignore_notes = _ignored_notes_set(ignore_events)

        while True:
            tick_result = _evaluate_tick(
                repo_root,
                batch_id,
                deadline=deadline,
                env=env,
                gh_run=gh_run,
                membership_reader=membership_reader,
                monotonic=monotonic,
                degraded=degraded,
                ignore_launch_ids=ignore_launch_ids,
                pr_state=pr_state,
                stack_state=stack_state,
                pr_sampled=pr_sampled,
                first_tick=first_tick,
                ignore_set=ignore_set,
                cloud_state=cloud_state,
                note_state=note_state,
                progress_state=progress_state,
                closed_state=closed_state,
                ignore_notes=ignore_notes,
                unread_out=unread,
            )
            if tick_result is not None:
                return _with_ignored_notes(
                    _with_ledger_path(tick_result, resolved_ledger_path), ignore_events,
                )

            if monotonic() >= deadline:
                return _with_ignored_notes(_with_ledger_path(_timer_at_deadline(
                    repo_root,
                    batch_id,
                    env=env,
                    degraded=degraded,
                    ignore_launch_ids=ignore_launch_ids,
                    pr_sampled=pr_sampled,
                    add_window_degradations=True,
                    cloud_state=cloud_state,
                    progress_state=progress_state,
                    unread=unread,
                ), resolved_ledger_path), ignore_events)

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


def run(
    repo_root,
    batch_id,
    *,
    env=None,
    gh_run=None,
    membership_reader=None,
    monotonic=None,
    ignore_launch_ids=(),
    ignore_events=(),
):
    """One evaluation tick — one ledger read, at most one PR poll, no sleep."""
    batch_for_refusal = batch_id if isinstance(batch_id, str) else None
    try:
        if env is None:
            env = os.environ
        if gh_run is None:
            gh_run = subprocess.run
        if membership_reader is None:
            membership_reader = sc.read_membership
        if monotonic is None:
            monotonic = time.monotonic

        if not _valid_batch_id(batch_id):
            return _refusal(REFUSAL_BATCH_INVALID, batch_for_refusal)

        batch_id = batch_id.strip()

        ignore_refusal = _validate_ignore_events(ignore_events, batch_id)
        if ignore_refusal is not None:
            return ignore_refusal

        if not _valid_repo_root(repo_root):
            return _refusal(REFUSAL_REPO_ROOT_INVALID, batch_id)

        ledger_path_result = ll.ledger_path(repo_root, env=env, create=False)
        if not ledger_path_result["ok"]:
            return _refusal(REFUSAL_STORE_UNRESOLVABLE, batch_id)
        resolved_ledger_path = ledger_path_result["path"]

        pr_state = [None]
        stack_state = [None]
        pr_sampled = [False]
        cloud_state = [None]
        progress_state = [None]
        closed_state = [None]
        cloud_payload = {}

        start = monotonic()
        deadline = start + RUN_READ_BUDGET_SECONDS
        degraded = set()
        unread = {}
        first_tick = [True]
        ignore_set = _ignore_events_set(ignore_events)
        ignore_notes = _ignored_notes_set(ignore_events)

        tick_result = _evaluate_tick(
            repo_root,
            batch_id,
            deadline=deadline,
            env=env,
            gh_run=gh_run,
            membership_reader=membership_reader,
            monotonic=monotonic,
            degraded=degraded,
            ignore_launch_ids=ignore_launch_ids,
            pr_state=pr_state,
            stack_state=stack_state,
            pr_sampled=pr_sampled,
            first_tick=first_tick,
            ignore_set=ignore_set,
            cloud_state=cloud_state,
            cloud_payload_out=cloud_payload,
            note_state=[None],
            progress_state=progress_state,
            closed_state=closed_state,
            ignore_notes=ignore_notes,
            unread_out=unread,
        )
        if tick_result is not None:
            return _with_ignored_notes(
                _with_ledger_path(tick_result, resolved_ledger_path), ignore_events,
            )

        return _with_ignored_notes(_event_result(
            EVENT_TIMER,
            batch_id,
            degraded,
            **cloud_payload,
            **_unread_payload(unread),
        ), ignore_events)
    except Exception as exc:
        result = _refusal(REFUSAL_INTERNAL_ERROR, batch_for_refusal)
        result["detail"] = type(exc).__name__
        return result


# WORKAROUND: loop re-arms watch_arm because there is no durable batch watcher daemon
# delete-when: a re-run of the background-session trial observes its "wave-watch arming and
# re-arm" condition met; the condition is restated in the keep-or-retire record's marker
# inventory
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
    membership_reader=None,
    monotonic=None,
    sleep=None,
    ignore_launch_ids=(),
    ignore_events=(),
    run_fn=None,
):
    """Re-arm watch_arm until lane-ending or attention exit, refusal, or ceiling."""
    batch_for_refusal = batch_id if isinstance(batch_id, str) else None
    arms = 0
    loop_degraded = set()
    log_file = None
    lock_fd = None
    passed_over = []
    passed_over_count = [0]
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
            run_fn = watch_arm

        if not _valid_batch_id(batch_id):
            return _loop_pre_arm_refusal(
                _refusal(REFUSAL_BATCH_INVALID, batch_for_refusal, arms=0),
            )

        batch_id = batch_id.strip()

        ignore_refusal = _validate_ignore_events(
            ignore_events, batch_id, arms=0,
        )
        if ignore_refusal is not None:
            return _loop_pre_arm_refusal(ignore_refusal)

        if (
            max_total_seconds is not None
            and not _valid_positive_int(max_total_seconds)
        ):
            return _loop_pre_arm_refusal(_refusal(
                REFUSAL_MAX_TOTAL_SECONDS_INVALID, batch_id, arms=0,
            ))
        if not _valid_positive_int(interval_seconds):
            return _loop_pre_arm_refusal(
                _refusal(REFUSAL_INTERVAL_INVALID, batch_id, arms=0),
            )
        if not _valid_positive_int(max_seconds):
            return _loop_pre_arm_refusal(
                _refusal(REFUSAL_MAX_SECONDS_INVALID, batch_id, arms=0),
            )
        if not _valid_repo_root(repo_root):
            return _loop_pre_arm_refusal(
                _refusal(REFUSAL_REPO_ROOT_INVALID, batch_id, arms=0),
            )

        lock_fd, lock_refusal = _acquire_loop_lock(
            repo_root, batch_id, env, log_path,
        )
        if lock_refusal is not None:
            return lock_refusal

        pr_state = [None]
        stack_state = [None]
        pr_sampled = [False]
        cloud_state = [None]
        note_state = [None]
        progress_state = [None]
        closed_state = [None]
        last_cloud_lanes = [None]
        loop_unread = {}
        total_start = monotonic()
        total_deadline = (
            total_start + max_total_seconds
            if max_total_seconds is not None
            else None
        )
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
                    final = _ceiling_timer_result(
                        batch_id,
                        loop_degraded,
                        passed_over,
                        passed_over_count,
                        last_cloud_lanes[0],
                        loop_unread,
                    )
                    final["arms"] = arms
                    final_degraded = set(final.get("degraded", []))
                    final_degraded.update(loop_degraded)
                    final["degraded"] = sorted(final_degraded)
                    _with_ignored_notes(final, ignore_events)
                    _close_log_silent(log_file)
                    _release_loop_lock(lock_fd)
                    lock_fd = None
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
                membership_reader=membership_reader,
                ignore_launch_ids=ignore_launch_ids,
                ignore_events=ignore_events,
                pr_state=pr_state,
                stack_state=stack_state,
                pr_sampled=pr_sampled,
                cloud_state=cloud_state,
                note_state=note_state,
                progress_state=progress_state,
                closed_state=closed_state,
            )

            result_degraded = set(result.get("degraded", []))
            loop_degraded.update(result_degraded)
            last_cloud_lanes[0] = result.get("cloudLanes")
            loop_unread.update({
                entry["launchId"]: entry["issue"] for entry in result.get("unreadIssues", ())
            })

            if _loop_exits_on(result):
                final = dict(result)
                final["arms"] = arms
                final.update(_unread_payload(loop_unread))
                final_degraded = set(final.get("degraded", []))
                final_degraded.update(loop_degraded)
                final["degraded"] = sorted(final_degraded)
                _loop_attach_passed_over(final, passed_over, passed_over_count)
                _with_ignored_notes(final, ignore_events)
                _close_log_silent(log_file)
                _release_loop_lock(lock_fd)
                lock_fd = None
                return final

            elapsed = monotonic() - total_start
            event = result.get("event")
            if event == EVENT_TIMER:
                log_file, log_degradation = _loop_log_arm_result(
                    log_file,
                    log_path,
                    log_degradation,
                    loop_degraded,
                    arms,
                    elapsed,
                    result,
                )
            else:
                _append_passed_over(
                    passed_over, passed_over_count, arms, elapsed, result,
                )
                log_file, log_degradation = _loop_log_arm_result(
                    log_file,
                    log_path,
                    log_degradation,
                    loop_degraded,
                    arms,
                    elapsed,
                    result,
                )

            if total_deadline is not None:
                remaining = total_deadline - monotonic()
                if remaining <= 0:
                    final = _ceiling_timer_result(
                        batch_id,
                        loop_degraded,
                        passed_over,
                        passed_over_count,
                        last_cloud_lanes[0],
                        loop_unread,
                    )
                    final["arms"] = arms
                    final_degraded = set(final.get("degraded", []))
                    final_degraded.update(loop_degraded)
                    final["degraded"] = sorted(final_degraded)
                    _with_ignored_notes(final, ignore_events)
                    _close_log_silent(log_file)
                    _release_loop_lock(lock_fd)
                    lock_fd = None
                    return final
            continue
    except Exception as exc:
        _close_log_silent(log_file)
        _release_loop_lock(lock_fd)
        lock_fd = None
        result = _refusal(REFUSAL_INTERNAL_ERROR, batch_for_refusal, arms=arms)
        result["detail"] = type(exc).__name__
        if loop_degraded:
            result["degraded"] = sorted(loop_degraded)
        _loop_attach_passed_over(result, passed_over, passed_over_count)
        return result

def _parse_ignore_event_cli(value):
    """(launch id, event) or (launch id, "builder-note", comment id), else None.

    Launch ids may contain ':', so both forms split from the right.
    """
    if ":" not in value:
        return None
    launch_id, event = value.rsplit(":", 1)
    if launch_id and event in _SUPPRESSIBLE_EVENTS:
        return (launch_id, event)
    parts = value.rsplit(":", 2)
    if len(parts) != 3 or parts[1] != EVENT_BUILDER_NOTE or not parts[0]:
        return None
    comment_id = _parse_comment_id(parts[2])
    if comment_id is None:
        return None
    return (parts[0], EVENT_BUILDER_NOTE, comment_id)


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="wave watcher")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--repo-root", required=True)
    run_parser.add_argument("--batch", required=True)
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
        help=(
            "suppress one event for one lane, or one note: LAUNCHID:builder-note:COMMENTID "
            "(repeatable)"
        ),
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
        help=(
            "suppress one event for one lane, or one note: LAUNCHID:builder-note:COMMENTID "
            "(repeatable)"
        ),
    )

    answered_parser = sub.add_parser("note-answered")
    answered_parser.add_argument("--repo-root", required=True)
    answered_parser.add_argument("--comment-id", required=True)

    args = ap.parse_args(argv[1:])

    ignore_events = []
    for raw in getattr(args, "ignore_event_raw", ()):
        parsed = _parse_ignore_event_cli(raw)
        if parsed is None:
            ignore_events.append((None, None))
        else:
            ignore_events.append(parsed)

    if args.cmd == "run":
        result = run(
            args.repo_root,
            args.batch,
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
    elif args.cmd == "note-answered":
        result = note_answered(args.repo_root, args.comment_id)
    else:
        return 1

    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
