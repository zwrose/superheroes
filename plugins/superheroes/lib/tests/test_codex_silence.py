"""#2370: the shared silence predicate, the stream tracker, and the read-only sample extractor.

Fixtures are small synthetic run dirs built in tmp_path: a journal.jsonl, a progress.jsonl, an
attempt-1.stdout. Heartbeats are given as (elapsed_s, visible_stdout_lines, stderr_bytes).
"""
import json
import os
import subprocess
import sys

import pytest

import codex_silence as CS
import engine_dispatch as ED

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE = os.path.join(_LIB, "codex_silence.py")


def _jl(obj):
    return json.dumps(obj) + "\n"


def _started(i, kind="command_execution"):
    return _jl({"type": "item.started", "item": {"id": "item_%d" % i, "type": kind,
                                                  "status": "in_progress"}})


def _completed(i, kind="command_execution"):
    return _jl({"type": "item.completed", "item": {"id": "item_%d" % i, "type": kind,
                                                    "status": "completed"}})


_THREAD = _jl({"type": "thread.started", "thread_id": "t"})
_TURN = _jl({"type": "turn.started"})
_MESSAGE = _jl({"type": "item.completed", "item": {"id": "item_m", "type": "agent_message",
                                                    "text": "hi"}})


def _make_run(root, name="run-a", *, lines=(), beats=(), wall=10.0, exit_code=0, timed_out=False,
              signal_source=None, engine="codex", run_kind="review", role="reviewer",
              order_id="ord-1", stdout_bytes=None, stdout_file=None, stderr_bytes=None,
              write_progress=True, ended=True, extra_ended=None, extra_journal_lines=()):
    """Build a run dir. stdout is the concatenation of `lines`; a beat's stdout_bytes is the length
    of its first n lines."""
    run_dir = root / name
    run_dir.mkdir(parents=True)
    prefix = [0]
    for line in lines:
        prefix.append(prefix[-1] + len(line.encode("utf-8")))
    if stdout_file is None:
        stdout_file = "".join(lines).encode("utf-8")
    if stdout_file is not False:
        (run_dir / "attempt-1.stdout").write_bytes(stdout_file)
    if stderr_bytes:
        (run_dir / "attempt-1.stderr").write_bytes(b"e" * stderr_bytes)
    journal = [_jl({"kind": "run-opened", "runKind": run_kind, "engine": engine,
                    "orderId": order_id, "resolvedInputs": {"role": role}})]
    journal.append(_jl({"kind": "engine-launching", "attempt": 1}))
    if ended:
        record = {"kind": "attempt-ended", "attempt": 1, "exit": exit_code,
                  "timedOut": timed_out, "signalSource": signal_source, "wallSeconds": wall,
                  "stdoutBytes": prefix[-1] if stdout_bytes is None else stdout_bytes}
        record.update(extra_ended or {})
        journal.append(_jl(record))
    journal.extend(extra_journal_lines)
    (run_dir / "journal.jsonl").write_text("".join(journal), encoding="utf-8")
    if write_progress:
        rows = [_jl({"alive": True, "attempt": 1, "elapsed_s": t, "stdout_bytes": prefix[n],
                     "stderr_bytes": err}) for t, n, err in beats]
        (run_dir / "progress.jsonl").write_text("".join(rows), encoding="utf-8")
    return run_dir


def _every(first, last, lines, stderr=0, step=10):
    return [(float(t), lines, stderr) for t in range(first, last + 1, step)]


def _only(run_dir):
    rows = CS.profile_run(str(run_dir))
    assert len(rows) == 1
    return rows[0]


# --- the profile: the shapes the sample must tell apart -------------------------------------------


def test_stall_shape_reports_long_idle_silence_and_hit_bound(tmp_path):
    lines = [_THREAD, _TURN, _started(1), _completed(1), _MESSAGE]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 710, 5), wall=710.0, timed_out=True,
                    exit_code=-9)
    row = _only(run)
    assert row["outcome"] == "hit-bound"
    assert row["measured"] is True and row["reason"] is None
    assert row["longestIdleSilenceSeconds"] == pytest.approx(700, abs=1)
    assert row["longestCommandSeconds"] == pytest.approx(0, abs=1)
    assert row["commandOpenAtEnd"] is False
    assert row["runDir"] == "run-a" and row["orderId"] == "ord-1" and row["seat"] == "reviewer"
    assert row["attempt"] == 1 and row["wallSeconds"] == 710.0


def test_long_command_shape_is_not_idle_silence(tmp_path):
    lines = [_THREAD, _started(1), _completed(1), _MESSAGE]
    beats = _every(10, 400, 2) + [(410.0, 3, 0), (420.0, 4, 0)]
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=420.0)
    row = _only(run)
    assert row["outcome"] == "answered"
    assert row["measured"] is True
    assert row["longestCommandSeconds"] == pytest.approx(400, abs=1)
    assert row["longestIdleSilenceSeconds"] < 20


def test_clean_run_has_short_gaps_and_no_reason(tmp_path):
    lines = [_THREAD, _TURN, _started(1), _completed(1), _MESSAGE, _jl({"type": "turn.completed"})]
    beats = [(10.0, 2, 0), (20.0, 3, 0), (30.0, 4, 0), (40.0, 5, 0), (50.0, 6, 0)]
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=50.0)
    row = _only(run)
    assert row["outcome"] == "answered"
    assert row["measured"] is True and row["reason"] is None
    assert row["longestIdleSilenceSeconds"] <= 40
    assert row["longestCommandSeconds"] <= 20


def test_stderr_only_growth_breaks_the_stdout_silent_gap(tmp_path):
    lines = [_THREAD, _TURN, _MESSAGE]
    beats = _every(10, 290, 3) + _every(300, 600, 3, stderr=50)
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=600.0, timed_out=True, exit_code=-9,
                    stderr_bytes=50)
    row = _only(run)
    assert row["measured"] is True
    assert 290 <= row["longestIdleSilenceSeconds"] <= 310


def test_truncated_capture_is_unmeasured(tmp_path):
    lines = [_THREAD, _TURN, _MESSAGE]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 30, 3), wall=30.0,
                    stdout_bytes=10_000_000)
    row = _only(run)
    assert row["measured"] is False
    assert row["reason"] == "stdout-capture-truncated"
    assert row["longestIdleSilenceSeconds"] is None
    assert row["longestCommandSeconds"] is None
    assert row["commandOpenAtEnd"] is None


def test_oversized_partial_line_is_stream_unknown(tmp_path):
    big = b"x" * (CS.MAX_PARTIAL_LINE_BYTES + 10)
    run = _make_run(tmp_path, beats=[(10.0, 0, 0)], wall=10.0, stdout_file=big,
                    stdout_bytes=len(big))
    (run / "progress.jsonl").write_text(
        _jl({"alive": True, "attempt": 1, "elapsed_s": 10.0, "stdout_bytes": len(big),
             "stderr_bytes": 0}), encoding="utf-8")
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "stream-unknown"


def test_non_json_line_is_stream_unknown(tmp_path):
    lines = [_THREAD, "this is not json\n", _MESSAGE]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 30, 3), wall=30.0)
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "stream-unknown"
    assert row["longestIdleSilenceSeconds"] is None


def test_command_open_at_end_runs_to_wall(tmp_path):
    lines = [_THREAD, _started(1)]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 100, 2), wall=105.0, timed_out=True,
                    exit_code=-9)
    row = _only(run)
    assert row["commandOpenAtEnd"] is True
    assert row["longestCommandSeconds"] == pytest.approx(95, abs=1)
    assert row["longestIdleSilenceSeconds"] < 20


def test_heartbeat_gap_keeps_measurements(tmp_path):
    lines = [_THREAD, _MESSAGE]
    beats = [(10.0, 1, 0), (20.0, 2, 0), (80.0, 2, 0)]
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=80.0)
    row = _only(run)
    assert row["measured"] is True
    assert row["reason"] == "heartbeat-gap"
    assert row["longestIdleSilenceSeconds"] == pytest.approx(60, abs=1)


@pytest.mark.parametrize("kwargs, outcome", [
    ({"exit_code": 0, "timed_out": False}, "answered"),
    ({"exit_code": -9, "timed_out": True}, "hit-bound"),
    ({"exit_code": -9, "timed_out": False, "signal_source": "silence-watchdog"}, "silence-watchdog"),
    ({"exit_code": 2, "timed_out": False}, "other"),
])
def test_outcome_classes(tmp_path, kwargs, outcome):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0, **kwargs)
    assert _only(run)["outcome"] == outcome


# --- fail-closed edges ------------------------------------------------------------------------------


def test_e1_journal_unreadable(tmp_path):
    run = tmp_path / "run-x"
    run.mkdir()
    pointer_root = tmp_path / "elsewhere"
    pointer_root.mkdir()
    (run / "journal-root.txt").write_text(str(pointer_root), encoding="utf-8")
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "journal-unreadable"
    assert row["attempt"] is None


def test_journal_found_through_the_pointer_file(tmp_path):
    run = _make_run(tmp_path / "src", lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0)
    moved = tmp_path / "moved"
    moved.mkdir()
    store = tmp_path / "store"
    (moved / "journal-root.txt").write_text(str(store), encoding="utf-8")
    target = ED._journal_path(os.path.realpath(str(moved)))
    os.makedirs(os.path.dirname(target))
    os.replace(str(run / "journal.jsonl"), target)
    os.replace(str(run / "progress.jsonl"), str(moved / "progress.jsonl"))
    os.replace(str(run / "attempt-1.stdout"), str(moved / "attempt-1.stdout"))
    row = _only(moved)
    assert row["measured"] is True and row["attempt"] == 1


def test_e2_non_object_journal_lines_are_skipped(tmp_path):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0,
                    extra_journal_lines=["[1, 2]\n", "not json\n", "42\n"])
    row = _only(run)
    assert row["measured"] is True


def test_e3_progress_file_missing(tmp_path):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[], wall=10.0, write_progress=False)
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "progress-missing"


def test_e4_no_heartbeat_rows_for_the_attempt(tmp_path):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[], wall=10.0)
    (run / "progress.jsonl").write_text(
        _jl({"alive": True, "attempt": 2, "elapsed_s": 10.0, "stdout_bytes": 5,
             "stderr_bytes": 0}), encoding="utf-8")
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "progress-missing"


def test_e5_stdout_file_missing(tmp_path):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0,
                    stdout_file=False)
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "stdout-missing"


def test_e9_attempt_never_ended_is_counted_not_profiled(tmp_path):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], ended=False)
    assert CS.profile_run(str(run)) == []
    out = CS.sample([str(run)])
    assert out["attempts"] == []
    assert out["summary"]["unended"] == 1


@pytest.mark.parametrize("wall", [None, "soon", True])
def test_e10_wall_missing_or_non_numeric(tmp_path, wall):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], wall=wall)
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "wall-missing"
    assert row["wallSeconds"] is None


def test_e11_missing_path_is_a_bad_path_and_the_cli_still_exits_zero(tmp_path):
    missing = str(tmp_path / "nope")
    out = CS.sample([missing])
    assert out["summary"]["badPaths"] == [missing]
    assert out["attempts"] == []
    proc = subprocess.run([sys.executable, "-B", _MODULE, "sample", missing],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["summary"]["badPaths"] == [missing]


# --- sample ----------------------------------------------------------------------------------------


def test_non_codex_and_write_runs_are_skipped_and_counted(tmp_path):
    _make_run(tmp_path, "run-claude", engine="claude", lines=[_THREAD],
              beats=[(10.0, 1, 0)], wall=10.0)
    _make_run(tmp_path, "run-write", run_kind="write", lines=[_THREAD],
              beats=[(10.0, 1, 0)], wall=10.0)
    _make_run(tmp_path, "run-codex", lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0)
    out = CS.sample([str(tmp_path)])
    assert out["skippedRuns"] == 2
    assert [r["runDir"] for r in out["attempts"]] == ["run-codex"]


def test_session_folder_is_searched_recursively(tmp_path):
    session = tmp_path / "session"
    _make_run(session / "a", "run-1", lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0)
    _make_run(session / "b" / "c", "run-2", lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0)
    out = CS.sample([str(session)])
    assert [r["runDir"] for r in out["attempts"]] == ["run-1", "run-2"]
    assert out["summary"]["attempts"] == 2 and out["summary"]["measured"] == 2


def test_sample_shape_and_summary_keys(tmp_path):
    stall = _make_run(tmp_path, "run-stall", lines=[_THREAD, _MESSAGE],
                      beats=_every(10, 710, 2), wall=710.0, timed_out=True, exit_code=-9)
    clean = _make_run(tmp_path, "run-clean", lines=[_THREAD, _MESSAGE],
                      beats=[(10.0, 1, 0), (20.0, 2, 0)], wall=20.0)
    out = CS.sample([str(stall), str(clean), str(clean)])
    assert out["schema"] == "codex-silence-sample/1"
    assert out["resolutionSeconds"] == 10
    assert set(out["summary"]) == {"attempts", "measured", "unended", "badPaths", "byOutcome",
                                   "longestIdleSilenceAnswered", "shortestIdleSilenceHitBound"}
    assert out["summary"]["byOutcome"] == {"answered": 1, "hit-bound": 1}
    assert out["summary"]["attempts"] == 2
    assert out["summary"]["longestIdleSilenceAnswered"] <= 10
    assert out["summary"]["shortestIdleSilenceHitBound"] == pytest.approx(700, abs=1)
    assert [r["runDir"] for r in out["attempts"]] == ["run-clean", "run-stall"]


def test_cli_prints_json_and_usage_exit_two(tmp_path):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0)
    proc = subprocess.run([sys.executable, "-B", _MODULE, "sample", str(run)],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["schema"] == "codex-silence-sample/1"
    for args in ([], ["sample"], ["bogus", str(run)]):
        bare = subprocess.run([sys.executable, "-B", _MODULE] + args,
                              capture_output=True, text=True)
        assert bare.returncode == 2
        assert bare.stdout == "" and "usage" in bare.stderr


# --- StreamTracker ---------------------------------------------------------------------------------


def test_tracker_opens_and_closes_by_id():
    t = CS.StreamTracker()
    assert t.state == "idle"
    t.feed(_started(1).encode())
    assert t.state == "busy"
    t.feed(_started(2, "file_change").encode())
    t.feed(_completed(1).encode())
    assert t.state == "busy"
    t.feed(_completed(2, "file_change").encode())
    assert t.state == "idle"


def test_tracker_unmatched_completed_changes_nothing():
    t = CS.StreamTracker()
    t.feed(_completed(9).encode())
    assert t.state == "idle"
    t.feed(_started(1).encode())
    t.feed(_completed(9).encode())
    assert t.state == "busy"


def test_tracker_non_action_items_change_nothing():
    t = CS.StreamTracker()
    t.feed(_started(1, "agent_message").encode())
    t.feed(_started(2, "reasoning").encode())
    t.feed(_MESSAGE.encode())
    t.feed(_jl({"type": "turn.started"}).encode())
    assert t.state == "idle"


def test_tracker_every_action_type_opens():
    for kind in sorted(CS.engine_adapter._CODEX_ACTION_ITEM_TYPES):
        t = CS.StreamTracker()
        t.feed(_started(1, kind).encode())
        assert t.state == "busy", kind


def test_tracker_chunk_boundary_inside_a_line():
    data = (_started(1) + _completed(1) + _started(2)).encode()
    for cut in range(1, len(data)):
        t = CS.StreamTracker()
        t.feed(data[:cut])
        t.feed(data[cut:])
        assert t.state == "busy", cut
    one_byte = CS.StreamTracker()
    for i in range(len(data)):
        one_byte.feed(data[i:i + 1])
    assert one_byte.state == "busy"


def test_tracker_reports_line_end_offsets():
    seen = []
    t = CS.StreamTracker(on_item=lambda what, item_id, end: seen.append((what, item_id, end)))
    first, second = _started(1), _completed(1)
    data = (_THREAD + first + second).encode()
    t.feed(data[:7])
    t.feed(data[7:])
    start_end = len(_THREAD) + len(first)
    assert seen == [("open", "item_1", start_end), ("close", "item_1", start_end + len(second))]


def test_tracker_oversized_partial_line_is_unknown_and_sticky():
    t = CS.StreamTracker()
    t.feed(b"x" * (CS.MAX_PARTIAL_LINE_BYTES + 1))
    assert t.state == "unknown"
    t.feed(_completed(1).encode())
    assert t.state == "unknown"


def test_tracker_oversized_partial_line_across_chunks():
    t = CS.StreamTracker()
    for _ in range(5):
        t.feed(b"y" * CS.FEED_CHUNK_BYTES)
    assert t.state == "unknown"


def test_tracker_line_at_the_bound_is_not_unknown():
    t = CS.StreamTracker()
    t.feed(b" " * CS.MAX_PARTIAL_LINE_BYTES)
    assert t.state == "idle"


def test_tracker_non_json_line_is_unknown_and_sticky():
    t = CS.StreamTracker()
    t.feed(b"not json at all\n")
    assert t.state == "unknown"
    t.feed(_completed(1).encode())
    assert t.state == "unknown"


@pytest.mark.parametrize("line", [b"[1,2]\n", b"42\n", b'"str"\n', b"null\n", b"\xff\xfe\n"])
def test_tracker_non_object_json_is_unknown(line):
    t = CS.StreamTracker()
    t.feed(line)
    assert t.state == "unknown"


def test_tracker_blank_lines_are_ignored_and_feed_never_raises():
    t = CS.StreamTracker()
    t.feed(b"\n\n  \r\n")
    assert t.state == "idle"
    t.feed(None)
    assert t.state == "unknown"


def test_unknown_is_never_idle():
    t = CS.StreamTracker()
    t.feed(b"garbage\n")
    assert CS.silent_and_idle(False, False, t.state) is False


# --- silent_and_idle -------------------------------------------------------------------------------


@pytest.mark.parametrize("stdout_grew, stderr_grew, state, expected", [
    (False, False, "idle", True),
    (False, False, "busy", False),
    (False, True, "idle", False),
    (False, True, "busy", False),
    (True, False, "idle", False),
    (True, False, "busy", False),
    (True, True, "idle", False),
    (True, True, "busy", False),
])
def test_silent_and_idle_truth_table(stdout_grew, stderr_grew, state, expected):
    assert CS.silent_and_idle(stdout_grew, stderr_grew, state) is expected


@pytest.mark.parametrize("state", ["unknown", "", None, "IDLE", "bogus"])
def test_silent_and_idle_only_exact_idle(state):
    assert CS.silent_and_idle(False, False, state) is False


# --- read_increment --------------------------------------------------------------------------------


def test_read_increment_reads_a_bounded_slice(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"0123456789")
    assert CS.read_increment(str(path), 0, 4) == (b"0123", 4)
    assert CS.read_increment(str(path), 4, 100) == (b"456789", 10)
    assert CS.read_increment(str(path), 10, 4) == (b"", 10)


def test_read_increment_unreadable_is_none_not_empty(tmp_path):
    assert CS.read_increment(str(tmp_path / "missing"), 7, 4) == (None, 7)
    assert CS.read_increment(str(tmp_path), 0, 4) == (None, 0)


def test_constants():
    assert CS.FEED_CHUNK_BYTES == 262144
    assert CS.MAX_PARTIAL_LINE_BYTES == 1048576
    assert CS.HEARTBEAT_RESOLUTION_SECONDS == 10
