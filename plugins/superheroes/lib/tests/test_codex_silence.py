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
              write_progress=True, ended=True, extra_ended=None, extra_journal_lines=(),
              journal_prefix_lines=()):
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
    journal = list(journal_prefix_lines)
    journal.append(_jl({"kind": "run-opened", "runKind": run_kind, "engine": engine,
                        "orderId": order_id, "resolvedInputs": {"role": role}}))
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

# axis (group: test_stall_shape_reports_long_idle_silence_and_hit_bound,
# test_long_command_shape_is_not_idle_silence, test_clean_run_has_short_gaps_and_no_reason,
# test_stderr_only_growth_breaks_the_stdout_silent_gap): idle silence is counted only while neither
# stream grows and no command is open; a regression that counts a long command or stderr growth as
# idle silence, or loses a real stall, fails one of these.

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


# axis: a capture shorter than the journal's recorded stdoutBytes is unmeasured (truncated), never
# measured on partial data.
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


def _overlong(i, event="item.completed", kind="command_execution", pad=CS.MAX_PARTIAL_LINE_BYTES + 100,
              key="aggregated_output"):
    """A codex-shaped line (id and type first, the payload last) longer than the bound."""
    return _jl({"type": event, "item": {"id": "item_%d" % i, "type": kind, key: "a" * pad}})


# axis (group: every test_overlong_* below, through test_overlong_newline_inside_a_later_chunk_and_
# in_the_same_chunk_as_the_overflow): a line over MAX_PARTIAL_LINE_BYTES is classified by its head
# only, applied like a short line, bounded in memory, offset-exact, unknown while skipped, and sticky
# unknown only when the head matches no recognized prefix; each test fails when its one rule breaks.
def test_overlong_completed_line_closes_its_item_and_the_attempt_is_measured(tmp_path):
    big = _overlong(1)
    assert len(big) > CS.MAX_PARTIAL_LINE_BYTES
    lines = [_THREAD, _started(1), big, _started(2), _completed(2), _MESSAGE]
    beats = [(10.0, 2, 0), (20.0, 2, 0), (30.0, 3, 0), (40.0, 4, 0), (50.0, 5, 0), (60.0, 6, 0)]
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=60.0)
    row = _only(run)
    assert row["measured"] is True and row["reason"] is None
    assert row["commandOpenAtEnd"] is False
    assert row["longestCommandSeconds"] == pytest.approx(20, abs=1)


def test_overlong_completed_line_then_short_command_timing_is_right(tmp_path):
    lines = [_THREAD, _started(1), _overlong(1), _started(2), _completed(2), _MESSAGE]
    beats = [(10.0, 2, 0), (20.0, 3, 0), (30.0, 4, 0), (100.0, 5, 0), (110.0, 6, 0)]
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=110.0)
    row = _only(run)
    assert row["measured"] is True
    # item_1: open at 10, close at 20; item_2: open at 30, close at 100 (the longest)
    assert row["longestCommandSeconds"] == pytest.approx(70, abs=1)


def test_overlong_started_line_opens_its_item():
    t = CS.StreamTracker()
    t.feed(_overlong(1, event="item.started").encode())
    assert t.state == "busy"
    t.feed(_completed(1).encode())
    assert t.state == "idle"


def test_overlong_line_across_many_small_chunks_gives_the_same_result():
    data = (_THREAD + _overlong(1, event="item.started") + _started(2)
            + _overlong(1) + _MESSAGE).encode()
    whole_seen = []
    whole = CS.StreamTracker(on_item=lambda *a: whole_seen.append(a))
    whole.feed(data)
    for step in (1000, 4096, 65536, 70001):
        seen = []
        t = CS.StreamTracker(on_item=lambda *a: seen.append(a))
        for i in range(0, len(data), step):
            t.feed(data[i:i + step])
        assert seen == whole_seen, step
        assert t.state == whole.state == "busy", step
    assert [w[0] for w in whole_seen] == ["open", "open", "close"]


def test_overlong_agent_message_does_not_open_what_its_text_contains():
    embedded = _started(7)
    seen = []
    t = CS.StreamTracker(on_item=lambda *a: seen.append(a))
    t.feed(json.dumps({"type": "item.completed", "item": {
        "id": "item_m", "type": "agent_message",
        "text": embedded + "b" * CS.MAX_PARTIAL_LINE_BYTES}}).encode() + b"\n")
    assert seen == [] and t.state == "idle"
    # the item keys reordered, with the started object's bytes raw inside the head: still not opened
    raw = (b'{"type":"item.started","item":{"type":"agent_message","id":"item_m","text":"'
           + b'{"type":"item.started","item":{"id":"item_7","type":"command_execution"}}'
           + b"b" * CS.MAX_PARTIAL_LINE_BYTES + b'"}}\n')
    t2 = CS.StreamTracker(on_item=lambda *a: seen.append(a))
    t2.feed(raw)
    assert seen == []
    assert t2.state != "busy"


def test_overlong_non_action_item_and_other_event_change_nothing():
    for line in (_overlong(1, kind="agent_message", key="text"),
                 _overlong(2, kind="reasoning", key="text", event="item.started"),
                 _jl({"type": "turn.completed", "usage": "u" * (CS.MAX_PARTIAL_LINE_BYTES + 5)})):
        t = CS.StreamTracker()
        t.feed(line.encode())
        assert t.state == "idle"


def test_overlong_head_that_matches_no_prefix_is_stream_unknown(tmp_path):
    reordered = _jl({"item": {"id": "item_1", "type": "command_execution",
                              "aggregated_output": "a" * (CS.MAX_PARTIAL_LINE_BYTES + 100)},
                     "type": "item.completed"})
    lines = [_THREAD, _started(1), reordered, _MESSAGE]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 40, 3), wall=40.0)
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "stream-unknown"
    t = CS.StreamTracker()
    t.feed(reordered.encode())
    t.feed(_MESSAGE.encode())
    assert t.state == "unknown"


def test_overlong_line_with_no_newline_at_the_end_of_the_stream_is_stream_unknown(tmp_path):
    big = _overlong(1).rstrip("\n").encode()
    run = _make_run(tmp_path, stdout_file=big, beats=[(10.0, 0, 0)], wall=10.0,
                    stdout_bytes=len(big))
    (run / "progress.jsonl").write_text(
        _jl({"alive": True, "attempt": 1, "elapsed_s": 10.0, "stdout_bytes": len(big),
             "stderr_bytes": 0}), encoding="utf-8")
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "stream-unknown"


def test_overlong_line_is_unknown_while_partial_then_idle_or_busy_after_its_newline():
    t = CS.StreamTracker()
    big = _overlong(1, event="item.started").encode()
    t.feed(big[:CS.MAX_PARTIAL_LINE_BYTES + 50])
    assert t.state == "unknown" and t.unreadable is False
    t.feed(big[CS.MAX_PARTIAL_LINE_BYTES + 50:])
    assert t.state == "busy"
    done = CS.StreamTracker()
    done.feed(_overlong(1, kind="agent_message", key="text")[:CS.MAX_PARTIAL_LINE_BYTES + 50].encode())
    assert done.state == "unknown"
    done.feed(b"c" * 10 + b"\n")
    assert done.state == "idle"


def test_overlong_line_offsets_are_exact_and_count_the_skipped_bytes():
    seen = []
    t = CS.StreamTracker(on_item=lambda what, item_id, end: seen.append((what, item_id, end)))
    first, big, second, third = (_started(1), _overlong(1, pad=3 * 1024 * 1024), _started(2),
                                 _completed(2))
    data = (_THREAD + first + big + second + third).encode()
    for i in range(0, len(data), 65536):
        t.feed(data[i:i + 65536])
    base = len(_THREAD)
    assert seen == [("open", "item_1", base + len(first)),
                    ("close", "item_1", base + len(first) + len(big)),
                    ("open", "item_2", base + len(first) + len(big) + len(second)),
                    ("close", "item_2", len(data))]


def test_overlong_buffer_never_exceeds_the_bound():
    t = CS.StreamTracker()
    data = _overlong(1, event="item.started", pad=3 * 1024 * 1024).encode()
    assert len(data) > 3 * 1024 * 1024
    limit = CS.MAX_PARTIAL_LINE_BYTES + CS.OVERLONG_HEAD_BYTES
    for i in range(0, len(data), 65536):
        t.feed(data[i:i + 65536])
        assert len(t._buf) <= limit
    assert t.state == "busy"


def test_overlong_lines_back_to_back_and_unopened_completion():
    seen = []
    t = CS.StreamTracker(on_item=lambda *a: seen.append(a))
    t.feed((_overlong(1, event="item.started") + _overlong(2, event="item.started")).encode())
    assert t.state == "busy" and [s[1] for s in seen] == ["item_1", "item_2"]
    t.feed((_overlong(1) + _overlong(2)).encode())
    assert t.state == "idle"
    fresh = CS.StreamTracker()
    fresh.feed(_overlong(9).encode())
    assert fresh.state == "idle"


def test_overlong_head_with_an_escaped_id_is_sticky_unknown():
    line = (b'{"type":"item.started","item":{"id":"item\\"_1","type":"command_execution","x":"'
            + b"a" * CS.MAX_PARTIAL_LINE_BYTES + b'"}}\n')
    t = CS.StreamTracker()
    t.feed(line)
    assert t.state == "unknown" and t.unreadable is True


def test_overlong_head_with_whitespace_between_tokens_classifies():
    line = (b'  {"type": "item.started", "item": {"id": "item_1", "type": "command_execution", "x": "'
            + b"a" * CS.MAX_PARTIAL_LINE_BYTES + b'"}}\n')
    t = CS.StreamTracker()
    t.feed(line)
    assert t.state == "busy"


def test_overlong_newline_inside_a_later_chunk_and_in_the_same_chunk_as_the_overflow():
    line = _overlong(1, event="item.started", pad=CS.MAX_PARTIAL_LINE_BYTES).encode()
    cut = CS.MAX_PARTIAL_LINE_BYTES + 1
    t = CS.StreamTracker()
    t.feed(line[:cut])
    t.feed(line[cut:] + _completed(1).encode())
    assert t.state == "idle"


# axis: a complete line that is not JSON makes the attempt stream-unknown, never a measured result.
def test_non_json_line_is_stream_unknown(tmp_path):
    lines = [_THREAD, "this is not json\n", _MESSAGE]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 30, 3), wall=30.0)
    row = _only(run)
    assert row["measured"] is False and row["reason"] == "stream-unknown"
    assert row["longestIdleSilenceSeconds"] is None


# axis: a command still open at the end is timed to the wall and flagged commandOpenAtEnd, not
# dropped or counted as idle silence.
def test_command_open_at_end_runs_to_wall(tmp_path):
    lines = [_THREAD, _started(1)]
    run = _make_run(tmp_path, lines=lines, beats=_every(10, 100, 2), wall=105.0, timed_out=True,
                    exit_code=-9)
    row = _only(run)
    assert row["commandOpenAtEnd"] is True
    assert row["longestCommandSeconds"] == pytest.approx(95, abs=1)
    assert row["longestIdleSilenceSeconds"] < 20


# axis: a heartbeat gap over the limit is reported as reason heartbeat-gap but keeps its measurements.
def test_heartbeat_gap_keeps_measurements(tmp_path):
    lines = [_THREAD, _MESSAGE]
    beats = [(10.0, 1, 0), (20.0, 2, 0), (80.0, 2, 0)]
    run = _make_run(tmp_path, lines=lines, beats=beats, wall=80.0)
    row = _only(run)
    assert row["measured"] is True
    assert row["reason"] == "heartbeat-gap"
    assert row["longestIdleSilenceSeconds"] == pytest.approx(60, abs=1)


# axis: the exit/timedOut/signalSource triple maps to exactly one outcome class; a wrong mapping
# files an attempt under the wrong sample group.
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

# axis (group: test_e1_journal_unreadable, test_e3_progress_file_missing,
# test_e4_no_heartbeat_rows_for_the_attempt, test_e5_stdout_file_missing,
# test_e10_wall_missing_or_non_numeric): each missing or unusable input yields an unmeasured row
# with its own named reason and null measurements, never a guessed measurement.
# axis (test_journal_found_through_the_pointer_file): a journal moved behind journal-root.txt is
# still found, so the attempt is measured.
# axis (test_e9_attempt_never_ended_is_counted_not_profiled): an attempt with no attempt-ended
# record is counted as unended and produces no row.
# axis (test_e11_missing_path_is_a_bad_path_and_the_cli_still_exits_zero): a missing path is listed
# in badPaths and the CLI still exits 0.

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


# axis: a journal line that is not a JSON object is skipped, not fatal; the noise comes before the
# valid records, so a reader that stops at the first bad row loses the run-opened record and fails.
@pytest.mark.parametrize("noise", ["[1, 2]\n", "not json\n", "42\n"])
def test_e2_non_object_journal_lines_are_skipped(tmp_path, noise):
    run = _make_run(tmp_path, lines=[_THREAD], beats=[(10.0, 1, 0)], wall=10.0,
                    journal_prefix_lines=[noise])
    row = _only(run)
    assert row["measured"] is True
    assert row["attempt"] == 1


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

# axis (group: test_non_codex_and_write_runs_are_skipped_and_counted,
# test_session_folder_is_searched_recursively): only codex review runs are profiled, non-codex and
# write runs are counted as skipped, and a session folder is walked recursively in sorted order.

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


# axis: the summary keeps the longest idle silence among answered attempts and the shortest among
# hit-bound ones; two attempts per group, so a reversed max/min picks the wrong one and fails.
def test_sample_shape_and_summary_keys(tmp_path):
    stall = _make_run(tmp_path, "run-stall", lines=[_THREAD, _MESSAGE],
                      beats=_every(10, 710, 2), wall=710.0, timed_out=True, exit_code=-9)
    short_stall = _make_run(tmp_path, "run-stall-short", lines=[_THREAD, _MESSAGE],
                            beats=_every(10, 110, 2), wall=110.0, timed_out=True, exit_code=-9)
    clean = _make_run(tmp_path, "run-clean", lines=[_THREAD, _MESSAGE],
                      beats=[(10.0, 1, 0), (20.0, 2, 0)], wall=20.0)
    slow_answer = _make_run(tmp_path, "run-slow-answer", lines=[_THREAD, _MESSAGE],
                            beats=[(10.0, 1, 0), (20.0, 2, 0)] + _every(30, 90, 2), wall=90.0)
    out = CS.sample([str(stall), str(short_stall), str(clean), str(clean), str(slow_answer)])
    assert out["schema"] == "codex-silence-sample/1"
    assert out["resolutionSeconds"] == 10
    assert set(out["summary"]) == {"attempts", "measured", "unended", "badPaths", "byOutcome",
                                   "longestIdleSilenceAnswered", "shortestIdleSilenceHitBound"}
    assert out["summary"]["byOutcome"] == {"answered": 2, "hit-bound": 2}
    assert out["summary"]["attempts"] == 4
    idle = {r["runDir"]: r["longestIdleSilenceSeconds"] for r in out["attempts"]}
    assert idle["run-clean"] <= 10
    assert idle["run-slow-answer"] == pytest.approx(70, abs=1)
    assert idle["run-stall-short"] == pytest.approx(100, abs=1)
    assert idle["run-stall"] == pytest.approx(700, abs=1)
    assert out["summary"]["longestIdleSilenceAnswered"] == idle["run-slow-answer"]
    assert out["summary"]["shortestIdleSilenceHitBound"] == idle["run-stall-short"]
    assert [r["runDir"] for r in out["attempts"]] == [
        "run-clean", "run-slow-answer", "run-stall", "run-stall-short"]


# axis: the CLI prints the sample JSON on success and exits 2 with usage on stderr for bad arguments.
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

# axis (group: test_tracker_opens_and_closes_by_id, test_tracker_unmatched_completed_changes_nothing,
# test_tracker_non_action_items_change_nothing, test_tracker_every_action_type_opens): open action
# items are tracked by id over exactly the action item types; a close that matches no open id and a
# non-action item change nothing.

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


# axis: a line split across two feeds (or fed a byte at a time) is read exactly like the whole line;
# the exact open/close callback sequence catches a dropped item.completed whose line spans feeds.
def test_tracker_chunk_boundary_inside_a_line():
    data = (_started(1) + _completed(1) + _started(2)).encode()
    expected = [("open", "item_1", len(_started(1).encode())),
                ("close", "item_1", len((_started(1) + _completed(1)).encode())),
                ("open", "item_2", len(data))]
    for cut in range(1, len(data)):
        seen = []
        t = CS.StreamTracker(on_item=lambda *a: seen.append(a))
        t.feed(data[:cut])
        t.feed(data[cut:])
        assert seen == expected, cut
        assert t.state == "busy", cut
        t.feed(_completed(2).encode())
        assert t.state == "idle", cut
    one_seen = []
    one_byte = CS.StreamTracker(on_item=lambda *a: one_seen.append(a))
    for i in range(len(data)):
        one_byte.feed(data[i:i + 1])
    assert one_seen == expected
    assert one_byte.state == "busy"
    one_byte.feed(_completed(2).encode())
    assert one_byte.state == "idle"


# axis: a non-blank unfinished line reads unknown (not sticky, not unreadable) until its newline
# arrives; a tracker that calls it idle or busy trusts an unread record.
def test_tracker_short_partial_line_is_unknown_until_its_newline():
    t = CS.StreamTracker()
    t.feed(_started(1).encode()[:-1])
    assert t.state == "unknown"
    assert t.unreadable is False
    t.feed(b"\n")
    assert t.state == "busy"
    assert t.unreadable is False


# axis: a whitespace-only remainder (spaces, \r, no newline) is not an unfinished record, so a
# complete stream followed by trailing whitespace stays idle rather than unknown.
def test_tracker_whitespace_only_remainder_is_idle():
    t = CS.StreamTracker()
    t.feed(_THREAD.encode())
    assert t.state == "idle"
    t.feed(b"  \r  ")
    assert t.state == "idle"
    assert t.unreadable is False


# axis: an attempt whose stdout ends on a short unfinished record (below the over-long bound) is
# stream-unknown, never a measured idle; a measurer that accepts it at EOF reports measured: true.
def test_short_incomplete_stdout_is_unmeasured(tmp_path):
    # bite-axis: an incomplete JSON record at EOF must invalidate the measurement,
    # including records below the overlong-line bound that remain buffered.
    run = tmp_path / "run-incomplete"
    run.mkdir()
    complete = (json.dumps({"type": "thread.started"}) + "\n").encode("utf-8")
    partial = b'{"type":"item.started","item":{"id":"item_1","type":"command_execution"'
    stdout = complete + partial
    (run / "attempt-1.stdout").write_bytes(stdout)
    (run / "attempt-1.stderr").write_bytes(b"")
    records = [
        {"kind": "run-opened", "engine": "codex", "runKind": "review",
         "orderId": "incomplete-stream", "resolvedInputs": {"role": "test-reviewer"}},
        {"kind": "engine-launching", "attempt": 1},
        {"kind": "attempt-ended", "attempt": 1, "exit": -9,
         "timedOut": True, "wallSeconds": 70.0, "stdoutBytes": len(stdout)},
    ]
    (run / "journal.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    beats = [
        {"alive": True, "attempt": 1, "elapsed_s": elapsed,
         "stdout_bytes": len(stdout), "stderr_bytes": 0}
        for elapsed in range(10, 71, 10)
    ]
    (run / "progress.jsonl").write_text(
        "".join(json.dumps(beat) + "\n" for beat in beats), encoding="utf-8"
    )

    rows = CS.profile_run(str(run))
    assert len(rows) == 1
    row = rows[0]
    assert row["outcome"] == "hit-bound"
    assert row["measured"] is False, row
    assert row["reason"] == "stream-unknown"
    assert row["longestIdleSilenceSeconds"] is None
    assert row["longestCommandSeconds"] is None
    assert row["commandOpenAtEnd"] is None


# axis: a heartbeat boundary that falls mid-line on an attempt that keeps growing does not stop
# measurement (an unfinished line is not the sticky unreadable state), and a stream that ends at a
# newline stays measured; only an unfinished line at the very end reads stream-unknown.
def test_mid_line_heartbeat_boundary_keeps_measuring_when_the_line_finishes(tmp_path):
    first, second = _started(1), _completed(1)
    cut = len(first.encode()) + 10
    data = (_THREAD + first + second).encode()
    prefix = len(_THREAD.encode())
    run = tmp_path / "run-midline"
    run.mkdir()
    (run / "attempt-1.stdout").write_bytes(data)
    records = [
        {"kind": "run-opened", "engine": "codex", "runKind": "review", "orderId": "o",
         "resolvedInputs": {"role": "r"}},
        {"kind": "engine-launching", "attempt": 1},
        {"kind": "attempt-ended", "attempt": 1, "exit": 0, "timedOut": False,
         "wallSeconds": 30.0, "stdoutBytes": len(data)},
    ]
    (run / "journal.jsonl").write_text("".join(_jl(r) for r in records), encoding="utf-8")
    beats = [(10.0, prefix + cut), (20.0, len(data)), (30.0, len(data))]
    (run / "progress.jsonl").write_text(
        "".join(_jl({"alive": True, "attempt": 1, "elapsed_s": t, "stdout_bytes": n,
                     "stderr_bytes": 0}) for t, n in beats), encoding="utf-8")
    row = _only(run)
    assert row["measured"] is True and row["reason"] is None
    assert row["commandOpenAtEnd"] is False


# axis: on_item reports the byte offset just past each line's newline, even for lines split across feeds.
def test_tracker_reports_line_end_offsets():
    seen = []
    t = CS.StreamTracker(on_item=lambda what, item_id, end: seen.append((what, item_id, end)))
    first, second = _started(1), _completed(1)
    data = (_THREAD + first + second).encode()
    t.feed(data[:7])
    t.feed(data[7:])
    start_end = len(_THREAD) + len(first)
    assert seen == [("open", "item_1", start_end), ("close", "item_1", start_end + len(second))]


# axis (group: test_tracker_oversized_partial_line_is_unknown_and_sticky,
# test_tracker_oversized_partial_line_across_chunks, test_tracker_line_at_the_bound_is_not_unknown):
# a non-blank partial line over MAX_PARTIAL_LINE_BYTES is sticky unknown, also across chunks, while a
# whitespace-only line at the bound is not.
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


# axis (group: test_tracker_non_json_line_is_unknown_and_sticky,
# test_tracker_non_object_json_is_unknown): a complete line that is not a JSON object makes the
# stream sticky unknown; later valid lines do not recover it.
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


# axis: blank lines are ignored, and a non-bytes feed makes the tracker unknown instead of raising.
def test_tracker_blank_lines_are_ignored_and_feed_never_raises():
    t = CS.StreamTracker()
    t.feed(b"\n\n  \r\n")
    assert t.state == "idle"
    t.feed(None)
    assert t.state == "unknown"


# axis: a tracker in the unknown state never satisfies the silence predicate.
def test_unknown_is_never_idle():
    t = CS.StreamTracker()
    t.feed(b"garbage\n")
    assert CS.silent_and_idle(False, False, t.state) is False


# --- silent_and_idle -------------------------------------------------------------------------------

# axis (group: test_silent_and_idle_truth_table, test_silent_and_idle_only_exact_idle): the predicate
# is True only when neither stream grew and the state is exactly "idle"; any growth, busy, unknown or
# near-miss state value makes it False.

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

# axis (group: test_read_increment_reads_a_bounded_slice, test_read_increment_unreadable_is_none_not_empty,
# test_constants): read_increment returns at most max_bytes and the new offset, returns None (never
# b"") on a read error, and the pinned bounds keep their values.

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
