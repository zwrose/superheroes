"""The wave watch watches a resumed local lane again (#2410).

A started, outcome-terminal local lane that was not relaunched is watched like a live local lane when,
after its basis (its recorded outcome, or its newest amendment), its builder is running again: a live
process resumed on the lane's recorded session id, or a heartbeat stamped after the basis. A builder
comment is no signal, and the watch makes no comment read for a finished local lane. The pid recorded
before the resume never fires builder-exited, and a heartbeat from before the outcome never fires
lane-terminal or lane-blocked again.

Ledger outcome timestamps are wall-clock `time.time()`. The lane below was reserved 300 seconds ago,
started 290 seconds ago and had its outcome recorded 200 seconds ago, so its basis is `now - 200`: a
heartbeat "after the basis" is stamped later than that, and one "before" it earlier (but after the
reserve).
"""
import os
import subprocess
import time

import pytest

import heartbeat as hb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import _BATCH, _NoteGh, _arm, _cloud_lane  # noqa: F401
from test_wave_watch_cloud import _add_local_lane, _reserved, clock, repo  # noqa: F401
from test_wave_watch_fix_order import _later  # noqa: F401

_SID = "5f0e8c1a-2b3d-4e6f-8a9b-0c1d2e3f4a5b"
_RECORDED_PID = 999999999
_RESUMED_PID = 4242
_RESERVED_AGE = 300
_OUTCOME_AGE = 200
_BEFORE_BASIS = 250  # a stamp's age that is before the basis and after the reserve
_AFTER_BASIS = 50  # a stamp's age that is after the basis


def _local_lane(
    repo_root, launch_id="local-a", issue=201, *, session_id=_SID, outcome="handback",
    outcome_age=_OUTCOME_AGE,
):
    """A started local lane with its outcome recorded `outcome_age` seconds ago."""
    ll.append(repo_root, _reserved(
        launch_id, issue, "plugins/local-%d" % issue, repo_root, sessionId=session_id,
        ts=time.time() - _RESERVED_AGE,
    ))
    ll.append(repo_root, {
        "event": "started", "launchId": launch_id, "ts": time.time() - _RESERVED_AGE + 10,
        "schema": ll.SCHEMA, "attempt": 1, "pid": _RECORDED_PID,
        "logPath": "/tmp/log", "errPath": "/tmp/err",
    })
    assert ll._append_raw(repo_root, {
        "event": "outcome", "launchId": launch_id, "ts": time.time() - outcome_age,
        "schema": ll.SCHEMA, "outcome": outcome, "evidence": "built and gated",
    })


def _stamp(repo_root, state, age, launch_id="local-a"):
    stamped = hb.stamp(
        repo_root, state=state, phase="watch", launch_id=launch_id, now=time.time() - age,
    )
    assert stamped.get("ok") is True, stamped


def _scan(monkeypatch, result):
    """The process scan answers `result` = (pid, uncertain); every probed pid reads live."""
    monkeypatch.setattr(ww, "_resumed_session_pid", lambda session_id: result)
    monkeypatch.setattr(ww, "_pid_is_live", lambda pid: True)


def _derive(repo_root, local_resume=None, ignore=()):
    degraded = set()
    _all, live, readable = ww._derive_batch_lanes(
        repo_root, _BATCH, os.environ, degraded, ignore, local_resume=local_resume,
    )
    assert readable is True
    return live, degraded


def _run(repo_root, gh=None, **kwargs):
    return ww.run(repo_root, _BATCH, gh_run=gh or _NoteGh(), **kwargs)


# --- row 1: a resumed process makes the lane's next ending count -------------------------------------


def test_row1_a_resumed_process_and_a_handback_heartbeat_after_the_outcome_is_lane_terminal(
        repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (_RESUMED_PID, False))
    _stamp(repo, "handback", _AFTER_BASIS)
    result = _run(repo)
    assert result["event"] == ww.EVENT_LANE_TERMINAL, result
    assert result["launches"] == [{"launchId": "local-a", "state": "handback"}]


def test_row1_the_process_signal_reopens_by_builder_process_and_replaces_the_recorded_pid(
        repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (_RESUMED_PID, False))
    pids = {}
    live, _degraded = _derive(repo, {"pids": pids})
    lane = live["local-a"]
    assert (lane["reopenedBy"], lane["pid"]) == ("builder-process", _RESUMED_PID)
    assert lane["reopenedAt"] == pytest.approx(time.time() - _OUTCOME_AGE, abs=5)
    assert pids == {"local-a": (lane["reopenedAt"], _RESUMED_PID)}


# --- row 3: no signal, no watch ------------------------------------------------------------------


def test_row3_a_local_lane_with_no_signal_stays_out_of_the_live_set_and_fires_nothing(
        repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (None, False))
    _stamp(repo, "handback", _BEFORE_BASIS)  # stamped before the outcome: no signal
    live, degraded = _derive(repo, {"pids": {}})
    assert live == {}
    assert degraded == set()
    result = _run(repo)
    assert result["event"] == ww.EVENT_TIMER
    assert result["degraded"] == []


# --- row 4: the pre-resume pid never fires builder-exited ----------------------------------------


def test_row4_a_lane_reopened_by_a_heartbeat_does_not_fire_builder_exited_for_the_recorded_pid(
        repo, monkeypatch):
    _local_lane(repo)
    monkeypatch.setattr(ww, "_resumed_session_pid", lambda session_id: (None, False))
    monkeypatch.setattr(ww, "_pid_is_live", lambda pid: False)  # the recorded pid is dead
    _stamp(repo, "working", _AFTER_BASIS)
    result = _run(repo)
    assert result["event"] == ww.EVENT_TIMER, result
    live, _degraded = _derive(repo)
    assert (live["local-a"]["reopenedBy"], live["local-a"]["pid"]) == ("builder-heartbeat", None)


def test_row4_a_resumed_process_seen_once_fires_builder_exited_with_its_own_pid_when_it_ends(
        repo, monkeypatch):
    _local_lane(repo)
    scans = []

    def scan(session_id):
        scans.append(session_id)
        return (_RESUMED_PID, False) if len(scans) == 1 else (None, False)

    monkeypatch.setattr(ww, "_resumed_session_pid", scan)
    monkeypatch.setattr(ww, "_pid_is_live", lambda pid: len(scans) < 2)  # alive on the first tick
    result = _arm(repo, _NoteGh())
    assert result["event"] == ww.EVENT_BUILDER_EXITED, result
    assert result["pids"] == [_RESUMED_PID]
    assert result["launches"] == [{"launchId": "local-a", "pid": _RESUMED_PID}]
    assert scans == [_SID, _SID]


def test_row4_a_loop_keeps_the_resumed_pid_across_arms(repo, monkeypatch):
    _local_lane(repo)
    scans = []

    def scan(session_id):
        scans.append(session_id)
        return (_RESUMED_PID, False) if len(scans) == 1 else (None, False)

    monkeypatch.setattr(ww, "_resumed_session_pid", scan)
    # A one-second arm ticks twice (scans 1 and 2, the pid alive); the process is gone on the second arm.
    monkeypatch.setattr(ww, "_pid_is_live", lambda pid: len(scans) < 3)
    result = ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=40, gh_run=_NoteGh(),
    )
    assert result["event"] == ww.EVENT_BUILDER_EXITED, result
    assert result["pids"] == [_RESUMED_PID]
    assert result["arms"] == 2


def test_row4_a_one_shot_run_keeps_no_pid_between_calls(repo, monkeypatch):
    _local_lane(repo)
    scans = []

    def scan(session_id):
        scans.append(session_id)
        return (_RESUMED_PID, False) if len(scans) == 1 else (None, False)

    monkeypatch.setattr(ww, "_resumed_session_pid", scan)
    monkeypatch.setattr(ww, "_pid_is_live", lambda pid: False)
    assert _run(repo)["event"] == ww.EVENT_BUILDER_EXITED  # seen on the first call, and gone
    assert _run(repo)["event"] == ww.EVENT_TIMER  # the second call remembers nothing


def test_row4_a_retained_pid_of_another_basis_is_deleted_not_used(repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (None, False))
    pids = {"local-a": (12345.0, _RESUMED_PID)}  # a different basis
    live, _degraded = _derive(repo, {"pids": pids})
    assert live == {}
    assert pids == {}


# --- row 5: the old heartbeat never re-fires ------------------------------------------------------


@pytest.mark.parametrize("state", ["handback", "parked", "blocked"])
def test_row5_a_heartbeat_stamped_before_the_basis_fires_nothing_for_a_resumed_lane(
        repo, monkeypatch, state):
    _local_lane(repo)
    _scan(monkeypatch, (_RESUMED_PID, False))
    _stamp(repo, state, _BEFORE_BASIS)
    result = _run(repo)
    assert result["event"] == ww.EVENT_TIMER, result


def test_row5_the_same_state_stamped_after_the_basis_does_fire(repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (_RESUMED_PID, False))
    _stamp(repo, "blocked", _AFTER_BASIS)
    result = _run(repo)
    assert result["event"] == ww.EVENT_LANE_BLOCKED, result


def test_row5_a_missing_or_unreadable_heartbeat_is_not_stamped_after(repo):
    _local_lane(repo)
    assert ww._heartbeat_stamped_after(repo, "local-a", os.environ, 0) is False  # missing
    assert ww._heartbeat_stamped_after(repo, "no/such lane", os.environ, 0) is False  # invalid id
    _stamp(repo, "working", _AFTER_BASIS)
    assert ww._heartbeat_stamped_after(repo, "local-a", os.environ, time.time() - _OUTCOME_AGE) is True
    assert ww._heartbeat_stamped_after(repo, "local-a", os.environ, time.time()) is False
    assert ww._heartbeat_stamped_after(repo, "local-a", os.environ, float("nan")) is False


# --- row 6: the process scan matches the session value, nothing else -----------------------------------


class _Ps:
    """`subprocess.run` that answers `ps` from `stdout` (or fails as told) and delegates anything else."""

    def __init__(self, stdout="", returncode=0, raises=None):
        self.stdout, self.returncode, self.raises = stdout, returncode, raises
        self.calls = []
        self.real = subprocess.run

    def __call__(self, argv, **kwargs):
        if argv[0] != "ps":
            return self.real(argv, **kwargs)
        self.calls.append((list(argv), kwargs))
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.returncode, stdout=self.stdout, stderr="")


@pytest.mark.parametrize("command", [
    "claude --resume %s" % _SID,
    "claude -p x -r %s --verbose" % _SID,
    "claude --session-id %s" % _SID,
    "claude --session-id=%s" % _SID,
    "claude --resume=%s" % _SID,
])
def test_row6_a_session_flag_naming_the_session_id_matches(monkeypatch, command):
    # The watcher's pid is pinned apart from the synthetic one, so a test worker that happens to hold
    # the synthetic pid cannot make the match fail.
    monkeypatch.setattr(os, "getpid", lambda: 1)
    monkeypatch.setattr(subprocess, "run", _Ps("  %d %s\n" % (_RESUMED_PID, command)))
    assert ww._resumed_session_pid(_SID) == (_RESUMED_PID, False)


@pytest.mark.parametrize("command", [
    "rg %s dir" % _SID,
    "echo %s" % _SID,
    "claude --resume other-session-id-0000",
    "claude --model %s" % _SID,
    "claude --resume %sX" % _SID,
    "claude --resume-x=%s" % _SID,
])
def test_row6_a_session_id_anywhere_but_a_session_flags_value_does_not_match(monkeypatch, command):
    monkeypatch.setattr(subprocess, "run", _Ps("  %d %s\n" % (_RESUMED_PID, command)))
    assert ww._resumed_session_pid(_SID) == (None, False)


def test_row6_the_ps_read_is_one_listing_in_the_c_locale(monkeypatch):
    ps = _Ps("")
    monkeypatch.setattr(subprocess, "run", ps)
    assert ww._resumed_session_pid(_SID) == (None, False)
    [(argv, kwargs)] = ps.calls
    assert argv == ["ps", "-A", "-ww", "-o", "pid=", "-o", "command="]
    assert kwargs["env"]["LC_ALL"] == "C"
    assert kwargs["capture_output"] is True and kwargs["text"] is True
    assert kwargs["timeout"] == ll._PS_READ_TIMEOUT_SECONDS


def test_row6_two_matching_processes_give_the_lowest_pid_and_the_watchers_own_is_skipped(monkeypatch):
    # The watcher's pid is pinned below every synthetic one, so the skip is what keeps it out.
    monkeypatch.setattr(os, "getpid", lambda: 77)
    listing = "\n".join([
        "77 claude --resume %s" % _SID,
        "900 claude --resume %s" % _SID,
        "300 x -r %s" % _SID,
        "not-a-pid claude --resume %s" % _SID,
        "",
    ])
    monkeypatch.setattr(subprocess, "run", _Ps(listing))
    assert ww._resumed_session_pid(_SID) == (300, False)


@pytest.mark.parametrize("session_id", [None, 12345678, "", "short", "1234567", "has space in it", "tab\tin-it-0000"])
def test_row6_a_session_id_that_is_absent_short_or_has_whitespace_reads_nothing(monkeypatch, session_id):
    ps = _Ps("1 claude --resume %s" % session_id)
    monkeypatch.setattr(subprocess, "run", ps)
    assert ww._resumed_session_pid(session_id) == (None, False)
    assert ps.calls == []


@pytest.mark.parametrize("ps", [
    pytest.param(_Ps(returncode=1), id="non-zero"),
    pytest.param(_Ps(raises=subprocess.TimeoutExpired(["ps"], 5)), id="timeout"),
    pytest.param(_Ps(raises=FileNotFoundError("ps")), id="missing"),
    pytest.param(_Ps(raises=OSError("boom")), id="oserror"),
])
def test_row6_a_ps_that_fails_is_uncertain(monkeypatch, ps):
    monkeypatch.setattr(subprocess, "run", ps)
    assert ww._resumed_session_pid(_SID) == (None, True)


def test_row6_an_uncertain_scan_records_pid_probe_uncertain_and_reopens_nothing(repo, monkeypatch):
    _local_lane(repo)
    monkeypatch.setattr(subprocess, "run", _Ps(returncode=1))
    result = _run(repo)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_PID_PROBE_UNCERTAIN in result["degraded"]


def test_row6_an_uncertain_scan_still_lets_a_later_signal_reopen(repo, monkeypatch):
    _local_lane(repo)
    monkeypatch.setattr(subprocess, "run", _Ps(returncode=1))
    _stamp(repo, "working", _AFTER_BASIS)
    live, degraded = _derive(repo)
    assert live["local-a"]["reopenedBy"] == "builder-heartbeat"
    assert ww.DEGRADATION_PID_PROBE_UNCERTAIN in degraded


# --- row 7: a relaunched lane is not resumed ----------------------------------------------------


def test_row7_a_local_lane_relaunched_on_its_issue_is_not_reopened(repo, monkeypatch):
    _local_lane(repo)
    _add_local_lane(repo, "local-b", 201, pid=_RECORDED_PID)  # the relaunch, reserved later
    _scan(monkeypatch, (_RESUMED_PID, False))
    live, _degraded = _derive(repo, {"pids": {}})
    assert set(live) == {"local-b"}


# --- R2-new: a builder comment is no signal for a finished local lane, and no comment is read -----


def test_a_builder_comment_after_the_basis_does_not_reopen_a_finished_local_lane_and_no_comment_is_read(
        repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (None, False))
    gh = _NoteGh([_later(7, issue=201)])  # a builder note created after the basis, on the lane's issue
    result = _run(repo, gh)
    assert result["event"] == ww.EVENT_TIMER, result
    live, _degraded = _derive(repo, {"pids": {}})
    assert "local-a" not in live
    assert gh.note_calls() == []


def test_a_batch_of_only_local_lanes_ending_on_its_timer_records_no_builder_note_unavailable(
        repo, monkeypatch):
    # A finished local lane with no signal (a live local lane cannot be made quiet without a transcript: it
    # reads lane-stale): the arm ends on its timer and records no builder-note-unavailable on its account.
    _local_lane(repo)
    _scan(monkeypatch, (None, False))
    gh = _NoteGh([_later(7, issue=201)])
    # No `sleep` argument: the autouse virtual clock advances only through the default sleep it patches.
    result = ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER, result
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"], result["degraded"]
    assert gh.note_calls() == []


def test_the_heartbeat_stamp_time_uses_the_clock_sample_its_age_was_read_at(monkeypatch):
    # The age is measured against the read's own sample; a later sample would move an old stamp past the basis.
    clock_reads = iter([1000.0] + [1001.0] * 10)
    monkeypatch.setattr(ww.time, "time", lambda: next(clock_reads))

    def read_heartbeat(repo_root, launch_id, env=None, now=None):
        # Like heartbeat.py: an age measured against `now`, or against the reader's own clock sample.
        return {"ageSeconds": (ww.time.time() if now is None else now) - 900.0}

    monkeypatch.setattr(ww.hb, "read_heartbeat", read_heartbeat)
    assert ww._heartbeat_stamped_after("/unused", "local-a", {}, 900.5) is False


# --- the order of the signals, and the lanes that are never reopened -------------------------------


def test_the_process_signal_wins_over_the_heartbeat(repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (_RESUMED_PID, False))
    _stamp(repo, "working", _AFTER_BASIS)
    live, _degraded = _derive(repo, {"pids": {}})
    assert live["local-a"]["reopenedBy"] == "builder-process"


def test_a_lane_in_ignore_launch_is_never_reopened(repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (_RESUMED_PID, False))
    _stamp(repo, "working", _AFTER_BASIS)
    live, _degraded = _derive(repo, {"pids": {}}, ignore=("local-a",))
    assert live == {}


def test_a_live_local_lane_and_a_cloud_lane_are_unchanged(repo, monkeypatch):
    _add_local_lane(repo, "local-live", 301, pid=os.getpid())
    _cloud_lane(repo, "cloud-live", 302)
    _scan(monkeypatch, (_RESUMED_PID, False))
    recorded_cloud_pid = ww._derive_batch_lanes(repo, _BATCH, os.environ, set(), ())[1]["cloud-live"].get("pid")
    live, _degraded = _derive(repo, {"pids": {}})
    assert set(live) == {"local-live", "cloud-live"}
    assert "reopenedBy" not in live["local-live"] and "reopenedBy" not in live["cloud-live"]
    assert live["local-live"]["pid"] == os.getpid()
    assert live["cloud-live"].get("pid") == recorded_cloud_pid


def test_a_closed_local_lane_is_not_a_never_stamped_lane_at_the_deadline(repo, monkeypatch):
    _local_lane(repo)
    _scan(monkeypatch, (None, False))
    result = ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_NoteGh())
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_LANE_NEVER_STAMPED not in result["degraded"]
