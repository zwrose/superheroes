"""#1467 item 3: every attempt-ended record carries host load and command time."""
import importlib.util
import json
import os
import time as time_mod
import tracemalloc

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E2E = _load_module("attempt_telemetry_e2e_helpers", "test_engine_dispatch_e2e.py")
ED = E2E.ED
EA = E2E.EA


@pytest.fixture(autouse=True)
def _pin_temp_and_journal(tmp_path, monkeypatch):
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _event(subtype, call_id, tool, ts):
    """One cursor stream-json tool_call line in the measured prefix/suffix shape."""
    return (
        '{"type":"tool_call","subtype":"%s","call_id":"%s","tool_call":{"%s":{"args":{"x":"y"}}},'
        '"model_call_id":"m-0-1","session_id":"s-1","timestamp_ms":%d}\n' % (subtype, call_id, tool, ts)
    )


def _stream(events):
    return "".join(_event(*e) for e in events)


_OVERLAP_EVENTS = [
    ("started", "a", "shellToolCall", 1000),
    ("started", "b", "shellToolCall", 2000),
    ("completed", "a", "shellToolCall", 3000),
    ("completed", "b", "shellToolCall", 4000),
    ("started", "c", "readToolCall", 5000),
    ("completed", "c", "readToolCall", 5500),
]


def _write(tmp_path, text, name="stream.stdout"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# --- T1 chokepoint -----------------------------------------------------------


def test_t1_journal_append_defaults_attempt_ended_keys(tmp_path):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    rec = {"kind": "attempt-ended", "attempt": 1, "exit": 0}
    before = dict(rec)
    assert ED._journal_append(run_dir, rec)
    assert rec == before
    other = {"kind": "engine-started", "attempt": 1}
    assert ED._journal_append(run_dir, other)
    records = E2E._journal_records(run_dir)
    ended, started = records
    load = ended["hostLoadAtEnd"]
    assert load is None or (len(load) == 3 and all(isinstance(v, float) for v in load))
    assert ended["hostLoadAtOpen"] is None
    assert ended["commandTime"] is None
    assert started == {"kind": "engine-started", "attempt": 1}


def test_host_load_sample_none_when_os_cannot_give_it(monkeypatch):
    def boom():
        raise OSError("no load")
    monkeypatch.setattr(ED.os, "getloadavg", boom)
    assert ED._host_load_sample() is None


# --- T2 real path ------------------------------------------------------------


def test_t2_real_path_records_load_and_command_time(tmp_path, monkeypatch):
    wt, _main = E2E._linked_worktree(tmp_path)
    run_dir = E2E._run_dir(tmp_path, "run-telemetry")
    prompt_path = E2E._prompt(tmp_path)
    E2E._install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        native_write_result=E2E._NATIVE_WRITE_OK_JSON, stdout=_stream(_OVERLAP_EVENTS),
    )
    E2E._poll_write_terminal(wt, run_dir, prompt_path)
    records = E2E._journal_records(run_dir)
    started = [r for r in records if r.get("kind") == "engine-started"]
    ended = [r for r in records if r.get("kind") == "attempt-ended"]
    assert len(started) == 1 and len(ended) == 1
    assert "hostLoadAtOpen" in started[0]
    assert ended[0]["hostLoadAtOpen"] == started[0]["hostLoadAtOpen"]
    assert "hostLoadAtEnd" in ended[0]
    ct = ended[0]["commandTime"]
    assert ct["source"] == "cursor-stream-json"
    assert ct["toolSeconds"] == 3.5
    assert ct["shellSeconds"] == 3.0
    assert ct["openCalls"] == 0


# --- T3 helper ---------------------------------------------------------------


def test_t3_overlapping_calls_union_not_sum(tmp_path):
    ct = EA.cursor_command_time(_write(tmp_path, _stream(_OVERLAP_EVENTS)), 9999)
    assert ct["toolSeconds"] == 3.5
    assert ct["shellSeconds"] == 3.0


def test_t3_overlong_completed_line_classified_by_head_and_tail(tmp_path):
    big = ('{"type":"tool_call","subtype":"completed","call_id":"a","tool_call":{"shellToolCall":'
           '{"args":{"command":"' + "x" * (2 * 1024 * 1024) + '"}}},"model_call_id":"m",'
           '"session_id":"s","timestamp_ms":4000}\n')
    text = _event("started", "a", "shellToolCall", 1000) + big
    ct = EA.cursor_command_time(_write(tmp_path, text), 9999)
    assert ct["toolSeconds"] == 3.0
    assert ct["shellSeconds"] == 3.0
    assert ct["unparsedLines"] == 0
    assert ct["complete"] is True


def test_t3_overlong_completed_call_id_before_subtype(tmp_path):
    big = ('{"type":"tool_call","call_id":"a","subtype":"completed","tool_call":{"shellToolCall":'
           '{"args":{"command":"' + "x" * (2 * 1024 * 1024) + '"}}},"timestamp_ms":4000}\n')
    text = _event("started", "a", "shellToolCall", 1000) + big
    ct = EA.cursor_command_time(_write(tmp_path, text), 9999)
    assert ct["toolSeconds"] == 3.0
    assert ct["shellSeconds"] == 3.0
    assert ct["unparsedLines"] == 0
    assert ct["openCalls"] == 0
    assert ct["complete"] is True


def test_t3_unmatched_completed_and_missing_timestamp(tmp_path):
    no_ts = ('{"type":"tool_call","subtype":"started","call_id":"n","tool_call":'
             '{"shellToolCall":{}}}\n')
    text = _event("completed", "ghost", "shellToolCall", 2000) + no_ts
    ct = EA.cursor_command_time(_write(tmp_path, text), 9999)
    assert ct["untimedCalls"] == 2
    assert ct["toolSeconds"] == 0.0


def test_t3_open_call_runs_to_end(tmp_path):
    ct = EA.cursor_command_time(
        _write(tmp_path, _event("started", "a", "shellToolCall", 1000)), 3000)
    assert ct["openCalls"] == 1
    assert ct["toolSeconds"] == 2.0
    assert ct["shellSeconds"] == 2.0


def test_t3_missing_file_is_none_and_no_tool_events_is_zeros(tmp_path):
    assert EA.cursor_command_time(str(tmp_path / "nope"), 1) is None
    ct = EA.cursor_command_time(_write(tmp_path, '{"type":"system"}\n'), 1)
    assert ct["toolSeconds"] == 0.0 and ct["openCalls"] == 0 and ct["untimedCalls"] == 0


# --- T4 stream beyond the capture cap ----------------------------------------


def test_t4_stream_over_capture_cap_bounded_memory(tmp_path):
    path = str(tmp_path / "big.stdout")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_stream(_OVERLAP_EVENTS[:4]))
        chunk = "p" * (1024 * 1024)
        for _ in range(EA.ENGINE_OUTPUT_MAX_BYTES // len(chunk) + 1):
            fh.write(chunk)
        fh.write("\n")
        fh.write(_stream(_OVERLAP_EVENTS[4:]))
    assert os.path.getsize(path) > EA.ENGINE_OUTPUT_MAX_BYTES
    tracemalloc.start()
    try:
        ct = EA.cursor_command_time(path, 9999)
        _cur, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert ct["toolSeconds"] == 3.5
    assert ct["shellSeconds"] == 3.0
    assert ct["unparsedLines"] == 1
    assert peak < 16 * 1024 * 1024
    assert ct["complete"] is True


def test_cursor_command_time_byte_budget_returns_incomplete(tmp_path):
    path = str(tmp_path / "over-byte-budget.stdout")
    with open(path, "wb") as fh:
        fh.write(_event("started", "a", "shellToolCall", 1000).encode("utf-8"))
        fh.write(b"p" * (EA.CURSOR_COMMAND_TIME_MAX_BYTES + 4096))
        fh.write(_event("completed", "a", "shellToolCall", 5000).encode("utf-8"))
    assert os.path.getsize(path) > EA.CURSOR_COMMAND_TIME_MAX_BYTES
    t0 = time_mod.monotonic()
    ct = EA.cursor_command_time(path, 9999)
    assert time_mod.monotonic() - t0 < 3.0
    assert ct["complete"] is False


def test_host_load_at_end_sampled_before_command_time_parse(tmp_path, monkeypatch):
    ted = _load_module("ted_host_load_order", "test_engine_dispatch.py")
    order = []
    real_load = ED._host_load_sample
    real_ct = ED.engine_adapter.cursor_command_time

    def track_load():
        order.append("hostLoadAtEnd")
        return real_load()

    def track_ct(path, end_ms):
        order.append("commandTime")
        return real_ct(path, end_ms)

    monkeypatch.setattr(ED, "_host_load_sample", track_load)
    monkeypatch.setattr(ED.engine_adapter, "cursor_command_time", track_ct)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    script = "import sys\nsys.stdout.write(%r)\n" % _stream(_OVERLAP_EVENTS)
    seat = E2E._cursor_seat()
    argv = ted._journal_cursor_run_for_engine_files(
        run_dir, prompt_path, seat=seat, role_kind="build", run_kind=ED.RUN_KIND_WRITE,
    )
    ted._install_fake_cursor(monkeypatch, tmp_path, script)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.05)
    ED._run_engine_files(
        run_dir, 1, argv, run_dir,
        prompt_path, stdout_path, stderr_path, 30,
        os.path.join(run_dir, "progress.jsonl"),
    )
    assert order.index("hostLoadAtEnd") < order.index("commandTime")


# --- T5 synthesized attempt-died-unrecorded ----------------------------------
# No existing test drives the supervisor's attempt-died-unrecorded path without a real child,
# so this is the unit shape: the _journal_state fold that the supervisor reads.


def test_t5_engine_started_load_folds_into_attempt_slot():
    load = [0.5, 0.6, 0.7]
    state = ED._journal_state([
        {"kind": "attempt-started", "attempt": 1, "childPid": 1},
        {"kind": "engine-started", "attempt": 1, "enginePgid": 2, "hostLoadAtOpen": load},
        {"kind": "attempt-started", "attempt": 2, "childPid": 1},
        {"kind": "engine-started", "attempt": 2, "enginePgid": 3},
    ])
    assert state["attempts"][1]["hostLoadAtOpen"] == load
    assert state["attempts"][2].get("hostLoadAtOpen") is None


# --- T6 pin ------------------------------------------------------------------


def test_t6_default_timeout_stays_900(tmp_path):
    assert ED.RETRY_MIN_TIMEOUT == 900
    wt, _main = E2E._linked_worktree(tmp_path)
    run_dir = E2E._run_dir(tmp_path, "run-default")
    prompt_path = E2E._prompt(tmp_path)
    ED.dispatch_write(
        seat=E2E._cursor_seat(), prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="t6", run_engine=lambda argv, pb, t, cb, cwd: ("", False, 0, ""),
    )
    opened = [r for r in E2E._journal_records(run_dir) if r.get("kind") == "run-opened"]
    assert opened and opened[0]["timeout"] == 900
