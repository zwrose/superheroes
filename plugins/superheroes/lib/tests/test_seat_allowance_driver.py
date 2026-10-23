#!/usr/bin/env python3
"""#2071 WO-C — the driver refuses a codex review result whose event record shows an action
outside the allowance, on every path that could admit one, and never on a write run."""
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from test_engine_dispatch import (  # noqa: E402, F401  (the autouse pin is a fixture)
    ED, FakeRunner, _VALID_FINDINGS_STDOUT, _WRITE_ROLE, _codex_event_stream, _codex_seat,
    _execution_record_completed_attempt, _fake_build_view, _install_fake_codex,
    _journal_codex_run_for_engine_files, _native_review_branch, _native_review_grade_state,
    _pin_temp_base_to_tmp_path, _production_run_child_setup, _repo, _valid_prompt,
    _wrap_native_review_result,
)

_COMMAND = "rm -rf build"
_SENTINEL_DETAIL = "sentinel-allowance-refusal"


def _line(item):
    return json.dumps({"type": "item.completed", "item": item})


def _command_line(command=_COMMAND):
    return _line({"id": "c1", "type": "command_execution", "command": command})


def _foreign_mcp_line():
    return _line({"id": "m1", "type": "mcp_tool_call", "server": "other_server", "tool": "run"})


def _read_tool_line():
    return _line({"id": "r1", "type": "mcp_tool_call", "server": "superheroes_read", "tool": "read"})


def _message_line(text="done"):
    return _line({"id": "a1", "type": "agent_message", "text": text})


def _stream(*lines):
    return "\n".join(lines) + "\n"


def _runner(stdout, branch=None):
    """An injected codex runner: writes the native result to its -o path, returns `stdout`."""
    branch = branch or _native_review_branch("findings")

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        with open(argv[argv.index("-o") + 1], "w", encoding="utf-8") as fh:
            json.dump(_wrap_native_review_result(branch), fh, separators=(",", ":"))
            fh.write("\n")
        return (stdout, False, 0, "")
    return runner


def _dispatch(tmp_path, stdout):
    fake = FakeRunner([_runner(stdout), _runner(stdout)])
    res = ED.dispatch_review(
        seat=_codex_seat(),
        prompt_path=_valid_prompt(tmp_path),
        repo_root=_repo(tmp_path),
        run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    return res, fake


def _assert_refused_once(res, fake):
    assert res.get("ok") is False
    assert res.get("terminal") is True
    assert res.get("reason") == "forfeited"
    assert res.get("detail", "").startswith(ED.ALLOWANCE_VIOLATION_DETAIL)
    assert res.get("attempts") == 1
    assert len(fake.calls) == 1


def test_command_execution_record_is_refused_without_retry(tmp_path):
    res, fake = _dispatch(tmp_path, _stream(_command_line(), _message_line()))
    _assert_refused_once(res, fake)
    assert any(_COMMAND in v for v in res["allowanceViolations"])
    assert _COMMAND in res["detail"]


def test_foreign_mcp_server_record_is_refused_without_retry(tmp_path):
    res, fake = _dispatch(tmp_path, _stream(_foreign_mcp_line(), _message_line()))
    _assert_refused_once(res, fake)
    assert any("other_server" in v for v in res["allowanceViolations"])


def test_clean_record_is_admitted(tmp_path):
    res, fake = _dispatch(
        tmp_path, _stream(_read_tool_line(), _message_line(), _read_tool_line()))
    assert res.get("ok") is True
    assert res.get("attempts") == 1
    assert "allowanceViolations" not in res
    assert len(fake.calls) == 1


def test_unreadable_scan_is_refused_as_record_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(ED.seat_allowance, "scan_stream", lambda path, limit=20, permitted_edit_paths=None, seat_cwd=None:([], False))
    res, fake = _dispatch(tmp_path, _stream(_message_line()))
    _assert_refused_once(res, fake)
    assert res["detail"] == "seat-ran-outside-allowance: record unreadable"
    assert res["allowanceViolations"] == []


def test_violation_after_truncated_capture_is_still_refused(tmp_path, monkeypatch):
    # axis: the scan reads the whole stream before _cap_file_tail cuts it to its tail.
    run_dir = str(tmp_path / "run")
    opened = _production_run_child_setup(tmp_path, run_dir)
    branch = _native_review_branch("findings")
    script = (
        "import json, sys\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "json.dump(%r, open(out, 'w'))\n"
        "sys.stdout.write(%r + '\\n')\n"
        "pad = json.dumps({'type': 'item.completed', 'item': {\n"
        "    'id': 'p', 'type': 'agent_message', 'text': 'x' * 1000}}) + '\\n'\n"
        "for _ in range(%d // len(pad) + 64):\n"
        "    sys.stdout.write(pad)\n"
    ) % (_wrap_native_review_result(branch), _command_line(), ED.MAX_STDOUT_CAPTURE)
    _install_fake_codex(monkeypatch, tmp_path, script)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.01)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    ED._run_engine_files(
        run_dir, 1, opened["argv"], opened["cwd"],
        opened["promptPath"], stdout_path, stderr_path,
        ED.RETRY_MIN_TIMEOUT, opened["progressPath"],
    )
    assert os.path.getsize(stdout_path) <= ED.MAX_STDOUT_CAPTURE
    with open(stdout_path, encoding="utf-8", errors="ignore") as fh:
        assert "command_execution" not in fh.read()
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert ended["allowanceScan"] == "ok"
    assert any(_COMMAND in v for v in ended["allowanceViolations"])
    res = ED._supervise(
        run_dir, run_kind=ED.RUN_KIND_REVIEW, deadline=time.monotonic() + 30)
    assert res.get("ok") is False
    assert res.get("terminal") is True
    assert res.get("reason") == "forfeited"
    assert res.get("detail", "").startswith(ED.ALLOWANCE_VIOLATION_DETAIL)
    assert res.get("attempts") == 1


def test_write_run_with_command_record_is_unaffected(tmp_path, monkeypatch):
    # fixers keep their shell: a write run neither scans nor refuses.
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    prompt_path = os.path.join(run_dir, "prompt.txt")
    with open(prompt_path, "w", encoding="utf-8") as fh:
        fh.write("go\n")
    seat = _codex_seat(role=_WRITE_ROLE)
    argv = _journal_codex_run_for_engine_files(
        run_dir, prompt_path, seat=seat, role_kind="build", run_kind=ED.RUN_KIND_WRITE,
    )
    script = "import sys\nsys.stdout.write(%r + '\\n')\n" % _command_line()
    _install_fake_codex(monkeypatch, tmp_path, script)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.01)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    ED._run_engine_files(
        run_dir, 1, argv, run_dir,
        prompt_path, stdout_path, stderr_path, 30, os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert "allowanceScan" not in ended
    assert "allowanceViolations" not in ended
    opened = ED._journal_state(records)["opened"]
    assert ED._allowance_refusal(opened, ended) is None


@pytest.mark.parametrize("opened", [
    {"engine": "claude", "runKind": "review"},
    {"engine": "cursor", "runKind": "write"},
    {"engine": "codex", "runKind": "write"},
])
def test_helper_ignores_non_codex_engines_and_write_runs(opened):
    dirty = {"allowanceViolations": ["command_execution: x"], "allowanceScan": "ok"}
    assert ED._allowance_refusal(opened, dirty) is None
    assert ED._allowance_refusal(opened, {}) is None
    assert ED._allowance_scan_fields(opened, "/nonexistent/attempt-1.stdout") == {}


def test_cursor_review_shell_tool_call_is_refused(tmp_path):
    opened = {"engine": "cursor", "runKind": "review"}
    stdout = tmp_path / "attempt-1.stdout"
    stdout.write_text(
        '{"type":"tool_call","subtype":"started","call_id":"c1","tool_call":'
        '{"shellToolCall":{"args":{"command":"make test"}}}}\n', encoding="utf-8")
    fields = ED._allowance_scan_fields(opened, str(stdout))
    assert fields["allowanceScan"] == "ok"
    assert fields["allowanceViolations"] == ["shellToolCall: make test"]
    refusal = ED._allowance_refusal(opened, fields)
    assert refusal["forfeit"] is True
    assert refusal["detail"].startswith(ED.ALLOWANCE_VIOLATION_DETAIL)


def test_helper_shape_and_missing_record_rule():
    opened = {"engine": "codex", "runKind": "review"}
    unreadable = {
        "forfeit": True, "reason": "forfeited",
        "detail": "seat-ran-outside-allowance: record unreadable",
        "allowanceViolations": [], "allowanceTerminal": True,
    }
    # no ended record, a scan that is missing, and a scan that is not "ok" all fail closed
    assert ED._allowance_refusal(opened, None) == unreadable
    assert ED._allowance_refusal(opened, {}) == unreadable
    assert ED._allowance_refusal(opened, {"refusal": None, "exit": 0}) == unreadable
    assert ED._allowance_refusal(
        opened, {"allowanceScan": "unreadable", "allowanceViolations": []}) == unreadable
    assert ED._allowance_refusal(opened, {"allowanceScan": "ok"}) is None
    assert ED._allowance_refusal(
        opened, {"allowanceScan": "ok", "allowanceViolations": []}) is None
    # an attempt the engine never ran keeps its existing grading
    assert ED._allowance_refusal(opened, {"refusal": "spawn-failed: x"}) is None
    assert ED._allowance_refusal(opened, {"guardRefusal": True, "refusal": "g"}) is None
    # a launched attempt that died unrecorded may have run the engine: terminal, not exempt
    assert ED._allowance_refusal(
        opened, {"refusal": "attempt-died-unrecorded"}) == unreadable
    named = ED._allowance_refusal(
        opened, {"allowanceScan": "ok", "allowanceViolations": ["a", "b"]})
    assert named["detail"] == "seat-ran-outside-allowance: a; b"
    assert named["allowanceViolations"] == ["a", "b"]
    assert named["allowanceTerminal"] is True


def test_helper_detail_stays_under_one_thousand_characters():
    opened = {"engine": "codex", "runKind": "review"}
    many = ["command_execution: %s" % ("x" * 150 + str(i)) for i in range(20)]
    refusal = ED._allowance_refusal(
        opened, {"allowanceScan": "ok", "allowanceViolations": many})
    assert len(refusal["detail"]) < 1000
    assert refusal["detail"].startswith("seat-ran-outside-allowance: command_execution: ")
    assert refusal["allowanceViolations"] == many


def _grade_state(tmp_path, **ended_overrides):
    tmp_path.mkdir(exist_ok=True)
    run_dir, state = _native_review_grade_state(tmp_path, _native_review_branch("findings"))
    state["attempts"][1]["ended"].update(ended_overrides)
    return run_dir, state


def test_grade_review_attempt_refuses_violation_unreadable_and_missing_scan(tmp_path):
    run_dir, state = _grade_state(tmp_path)
    assert ED._grade_review_attempt(run_dir, state, 1).get("ok") is True

    run_dir, state = _grade_state(
        tmp_path / "v", allowanceViolations=["command_execution: ls"])
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("ok") is not True
    assert grade["detail"] == "seat-ran-outside-allowance: command_execution: ls"
    assert grade["allowanceTerminal"] is True

    run_dir, state = _grade_state(tmp_path / "u", allowanceScan="unreadable")
    assert ED._grade_review_attempt(run_dir, state, 1)["detail"].endswith("record unreadable")

    run_dir, state = _grade_state(tmp_path / "m")
    del state["attempts"][1]["ended"]["allowanceScan"]
    assert ED._grade_review_attempt(run_dir, state, 1)["detail"].endswith("record unreadable")

    run_dir, state = _grade_state(tmp_path / "n")
    state["attempts"][1] = {}
    assert ED._grade_review_attempt(run_dir, state, 1)["detail"].endswith("record unreadable")


def test_grade_review_attempt_keeps_refusal_grading_for_an_attempt_that_never_ran(tmp_path):
    run_dir, state = _grade_state(tmp_path, refusal="spawn-failed: boom")
    del state["attempts"][1]["ended"]["allowanceScan"]
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("detail") == "spawn-failed: boom"
    assert "allowanceTerminal" not in grade


def _record_fixture(tmp_path, name, **ended_overrides):
    run_dir = str(tmp_path / name)
    _execution_record_completed_attempt(
        tmp_path, run_dir, stdout=_VALID_FINDINGS_STDOUT, ended_overrides=ended_overrides)
    return run_dir


def test_execution_record_paths_refuse_a_violating_attempt(tmp_path):
    # census: _parse_review_attempt and _observation_from_attempt (both reached through
    # run_execution_record) must not admit the result of an attempt outside the allowance.
    clean = _record_fixture(tmp_path, "clean")
    record, error = ED.run_execution_record(clean)
    assert error is None
    assert record["observation"]["read"] == "engaged"
    assert "resultDigest" in record

    dirty = _record_fixture(
        tmp_path, "dirty", allowanceViolations=["command_execution: ls"])
    record, error = ED.run_execution_record(dirty)
    assert error is None
    assert record["observation"]["read"] != "engaged"
    assert "resultDigest" not in record
    records, _ = ED._journal_read(dirty)
    state = ED._journal_state(records)
    assert ED._parse_review_attempt(dirty, state, 1) is None
    assert ED._observation_from_attempt(dirty, state, 1)["read"] != "engaged"


def test_every_review_success_path_routes_through_the_shared_helper(tmp_path, monkeypatch):
    # census: _grade_review_attempt (and through it _grade_native_review_attempt,
    # _finish_review_grade_from_parse, _build_running_graded and the _supervise success arm),
    # _parse_review_attempt and _observation_from_attempt each ask _allowance_refusal first;
    # a refusal from it alone, on an otherwise clean record, turns each one down.
    grade_dir, grade_state = _grade_state(tmp_path / "g")
    clean = _record_fixture(tmp_path, "clean")
    records, _ = ED._journal_read(clean)
    clean_state = ED._journal_state(records)
    assert ED._grade_review_attempt(grade_dir, grade_state, 1).get("ok") is True
    assert ED._parse_review_attempt(clean, clean_state, 1) is not None
    assert ED._observation_from_attempt(clean, clean_state, 1)["read"] == "engaged"

    calls = []

    def sentinel(opened, ended):
        calls.append((opened.get("engine"), dict(ended)))
        return {
            "forfeit": True, "reason": "forfeited", "detail": _SENTINEL_DETAIL,
            "allowanceViolations": [], "allowanceTerminal": True,
        }

    monkeypatch.setattr(ED, "_allowance_refusal", sentinel)
    assert ED._grade_review_attempt(grade_dir, grade_state, 1)["detail"] == _SENTINEL_DETAIL
    assert ED._parse_review_attempt(clean, clean_state, 1) is None
    assert ED._observation_from_attempt(clean, clean_state, 1)["read"] != "engaged"
    assert len(calls) == 3
    grade_state["opened"]["runKind"] = ED.RUN_KIND_REVIEW
    running = ED._build_running_graded(grade_dir, grade_state)
    assert running and running[0]["reason"] == "forfeited"


def test_scan_fields_are_journaled_on_the_injected_attempt_end(tmp_path):
    res, fake = _dispatch(tmp_path, _stream(_command_line(), _message_line()))
    records, _ = ED._journal_read(res["runDir"])
    ended = [r for r in records if r.get("kind") == "attempt-ended"]
    assert len(ended) == 1
    assert ended[0]["allowanceScan"] == "ok"
    assert any(_COMMAND in v for v in ended[0]["allowanceViolations"])


def test_review_terminal_forfeit_disclosure_tells_unreadable_from_violation():
    unreadable = ED._review_terminal_forfeit(
        "codex", "forfeited", 1, detail="seat-ran-outside-allowance: record unreadable",
        allowance_violations=[])
    assert unreadable["forfeited"] is True and unreadable["terminal"] is True
    assert unreadable["allowanceViolations"] == []
    assert "could not be read" in unreadable["disclosure"]
    assert ED.ALLOWANCE_RECORD_UNREADABLE in unreadable["disclosure"]
    assert "ran outside the review allowance" not in unreadable["disclosure"]
    assert "fall open to a reviewer on the host model" in unreadable["disclosure"]

    violation = ED._review_terminal_forfeit(
        "codex", "forfeited", 1, detail="seat-ran-outside-allowance: command_execution: ls",
        allowance_violations=["command_execution: ls"])
    assert violation["disclosure"] == (
        "codex reviewer ran outside the review allowance (seat-ran-outside-allowance); its result "
        "is refused and not retried; fall open to a reviewer on the host model and disclose the "
        "degraded vendor mix")
