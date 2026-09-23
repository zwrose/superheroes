import importlib.util
import json
import os
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, "..", filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load("engine_dispatch", "engine_dispatch.py")
EA = _load("engine_adapter", "engine_adapter.py")
ERC = _load("engine_result_channel", "engine_result_channel.py")
PC = _load("payload_contracts", "payload_contracts.py")
MR = _load("model_registry", "model_registry.py")
_SV = _load("sanitized_view", "sanitized_view.py")


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(_SV.tempfile, "gettempdir", lambda: base)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _spawn_gate_resolved_inputs(seat, role_source="caller"):
    return {
        "engine": seat["vendor"],
        "engineSource": "caller",
        "model": seat["model"],
        "modelSource": "caller",
        "effort": seat.get("effort"),
        "effortSource": "declared-none" if seat.get("effort") is None else "caller",
        "role": seat["role"],
        "roleSource": role_source,
    }


def _reviewer_claude_seat():
    cell = MR.matrix_config("reviewer", "claude")
    return {"vendor": "claude", "model": cell[0], "effort": cell[1], "role": "reviewer"}


def _claude_argv_for_run(seat, role_kind, cwd):
    built = EA.build_argv_result(seat, role_kind, {"cwd": cwd})
    assert built["reason"] is None, built
    return built["argv"]


def _ensure_claude_config_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    cfg = home / ".claude"
    cfg.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return str(cfg)


def _install_fake_claude(monkeypatch, tmp_path, script_body):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake_claude = fake_bin / "claude"
    fake_claude.write_text("#!/usr/bin/env python3\n" + script_body, encoding="utf-8")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))


def _native_review_branch(kind):
    investigated = ["path/to/file.py"]
    if kind == "verdicts":
        contract, _ = PC.payload_contract(PC.P_VERIFIERS)
        elem = contract["elements"]["verdicts"]
        verdict = {}
        for field in list(elem.get("required") or []) + list(elem.get("optional") or ()):
            if field == "verdict":
                verdict[field] = elem["enums"]["verdict"][0]
            elif field == "id":
                verdict[field] = "finding-001"
            elif field == "reason":
                verdict[field] = "grounds"
            else:
                verdict[field] = None
        return {
            "resultKind": "verdicts",
            "findings": None,
            "verdicts": [verdict],
            "grouping": None,
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    raise ValueError(kind)


def _wrap_native_review_result(branch):
    return {"result": branch}


def _claude_event_stream(result=None):
    lines = []
    if result is not None:
        lines.append(json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": result,
            "session_id": "sess-1",
        }))
    return "\n".join(lines) + "\n"


def _journal_claude_stdout_run_for_engine_files(tmp_path, run_dir, prompt_path, monkeypatch):
    cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
    seat = _reviewer_claude_seat()
    argv = _claude_argv_for_run(seat, "review", run_dir)
    argv, native_err, native_schema_path = ED._open_native_channel_argv(
        run_dir, "claude", list(argv), ED.RUN_KIND_REVIEW,
    )
    assert native_err is None, native_err
    record = {
        "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "claude",
        "roleKind": ED.RUN_KIND_REVIEW, "orderId": "stdout-drop-test",
        "argv": argv, "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "channel": ERC.CHANNEL_NATIVE, "configDir": cfg,
        "supervisorPid": 1, "at": time.time(),
        "resolvedInputs": _spawn_gate_resolved_inputs(seat),
    }
    if native_schema_path is not None:
        record["nativeSchemaPath"] = native_schema_path
    ED._journal_append(run_dir, record)
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    return argv


def _run_claude_stdout_review_script(tmp_path, monkeypatch, script_body, *, timeout=30):
    run_dir = str(tmp_path / "stdout-review")
    os.makedirs(run_dir)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    argv = _journal_claude_stdout_run_for_engine_files(
        tmp_path, run_dir, prompt_path, monkeypatch,
    )
    _install_fake_claude(monkeypatch, tmp_path, script_body)
    ED._run_engine_files(
        run_dir, 1, argv, run_dir,
        prompt_path, stdout_path, stderr_path, timeout,
        os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    return run_dir, state, ended, stdout_path


def test_stdout_final_read_failed_reports_dropped_cause(tmp_path, monkeypatch):
    """axis: a terminal stdout read failure reports stdout-result-dropped with final-read-failed."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    script = "import sys\nsys.stdout.write(%r)\n" % result_stream
    real_observe = ED._observe_stdout_completion

    def observe_drop_on_terminal(obs_state, stdout_path, *, terminal=False):
        if not terminal:
            real_observe(obs_state, stdout_path, terminal=terminal)
            return
        if obs_state.get("event") is not None:
            try:
                os.remove(str(stdout_path))
            except OSError:
                pass
        real_observe(obs_state, stdout_path, terminal=True)

    monkeypatch.setattr(ED, "_observe_stdout_completion", observe_drop_on_terminal)
    run_dir, state, ended, _stdout_path = _run_claude_stdout_review_script(
        tmp_path, monkeypatch, script,
    )
    assert ended.get("stdoutResultDropped") == "final-read-failed"
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "stdout-result-dropped"
    assert grade.get("droppedCause") == "final-read-failed"


def test_stdout_shrunk_below_read_reports_dropped_cause(tmp_path, monkeypatch):
    """axis: stdout shrinking below bytes already read reports stdout-result-dropped."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    script = "import sys\nsys.stdout.write(%r)\n" % result_stream
    real_observe = ED._observe_stdout_completion
    shrunk = [False]

    def observe_shrink_after_stamp(obs_state, stdout_path, *, terminal=False):
        if (
            not terminal
            and not shrunk[0]
            and obs_state.get("event") is not None
            and obs_state.get("offset", 0) > 0
        ):
            shrunk[0] = True
            with open(stdout_path, "r+b") as fh:
                fh.truncate(obs_state["offset"] - 10)
        return real_observe(obs_state, stdout_path, terminal=terminal)

    monkeypatch.setattr(ED, "_observe_stdout_completion", observe_shrink_after_stamp)
    run_dir, state, ended, _stdout_path = _run_claude_stdout_review_script(
        tmp_path, monkeypatch, script,
    )
    assert ended.get("stdoutResultDropped") == "shrunk-below-read"
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "stdout-result-dropped"
    assert grade.get("droppedCause") == "shrunk-below-read"


def test_stdout_bytes_changed_reports_dropped_cause(tmp_path, monkeypatch):
    """axis: bytes changed after the held result was stamped drop with bytes-changed."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    script = "import sys\nsys.stdout.write(%r)\n" % result_stream
    real_observe_attempt = ED._observe_attempt_completions

    def observe_with_tamper(
            delivery, stdout_obs, native_obs, run_dir_real, attempt, stdout_path,
            *, terminal=False,
    ):
        real_observe_attempt(
            delivery, stdout_obs, native_obs, run_dir_real, attempt, stdout_path,
            terminal=terminal,
        )
        if (
            terminal
            and delivery == ERC.RESULT_DELIVERY_STDOUT
            and stdout_obs.get("event") is not None
        ):
            start = stdout_obs.get("stamp_line_start")
            length = stdout_obs.get("stamp_line_len")
            if start is not None and length is not None:
                with open(stdout_path, "r+b") as fh:
                    fh.seek(start)
                    original = fh.read(length)
                    fh.seek(start)
                    fh.write(bytes((b ^ 0x01) for b in original))

    monkeypatch.setattr(ED, "_observe_attempt_completions", observe_with_tamper)
    run_dir, state, ended, _stdout_path = _run_claude_stdout_review_script(
        tmp_path, monkeypatch, script,
    )
    assert ended.get("stdoutResultDropped") == "bytes-changed"
    assert ended.get("stdoutResult") == "absent"
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "stdout-result-dropped"
    assert grade.get("droppedCause") == "bytes-changed"


def test_held_stdout_bytes_unchanged_final_read_failed(tmp_path):
    """axis: save-time byte check clears held event and records final-read-failed on OSError."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    stdout_path = tmp_path / "final-read-failed.stdout"
    stdout_path.write_text(result_stream, encoding="utf-8")
    obs = {
        "offset": 0, "buf": b"", "overflow": False, "poisoned": False, "drop_cause": None,
    }
    ED._observe_stdout_completion(obs, str(stdout_path), terminal=True)
    assert obs.get("event") is not None
    os.remove(stdout_path)
    assert ED._held_stdout_bytes_unchanged(obs, str(stdout_path)) is False
    assert obs.get("event") is None
    assert obs.get("stamp") is None
    assert obs.get("drop_cause") == "final-read-failed"


def test_held_stdout_bytes_unchanged_missing_digest(tmp_path):
    """axis: missing held stamp digest metadata drops with bytes-changed."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    stdout_path = tmp_path / "missing-digest.stdout"
    stdout_path.write_text(result_stream, encoding="utf-8")
    obs = {
        "offset": 0, "buf": b"", "overflow": False, "poisoned": False, "drop_cause": None,
    }
    ED._observe_stdout_completion(obs, str(stdout_path), terminal=True)
    assert obs.get("event") is not None
    obs["stamp_line_sha256"] = None
    assert ED._held_stdout_bytes_unchanged(obs, str(stdout_path)) is False
    assert obs.get("event") is None
    assert obs.get("drop_cause") == "bytes-changed"


def test_held_stdout_bytes_check_never_reparses(tmp_path):
    """axis: the save-time byte check never calls json.loads."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    stdout_path = tmp_path / "byte-check.stdout"
    stdout_path.write_text(result_stream, encoding="utf-8")
    obs = {
        "offset": 0, "buf": b"", "overflow": False, "poisoned": False, "drop_cause": None,
    }
    ED._observe_stdout_completion(obs, str(stdout_path), terminal=True)
    assert obs.get("event") is not None
    loads_calls = []
    real_loads = ED.json.loads

    def spy_loads(data, *args, **kwargs):
        loads_calls.append(1)
        return real_loads(data, *args, **kwargs)

    ED.json.loads = spy_loads
    try:
        assert ED._held_stdout_bytes_unchanged(obs, str(stdout_path)) is True
    finally:
        ED.json.loads = real_loads
    assert loads_calls == []


def test_stdout_held_line_unchanged_admits_result(tmp_path, monkeypatch):
    """axis: an untouched held stdout result line admits exactly as before."""
    structured = _wrap_native_review_result(_native_review_branch("verdicts"))
    result_stream = _claude_event_stream(result=structured)
    script = "import sys\nsys.stdout.write(%r)\n" % result_stream
    run_dir, state, ended, _stdout_path = _run_claude_stdout_review_script(
        tmp_path, monkeypatch, script,
    )
    assert "stdoutResultDropped" not in ended
    assert ended["stdoutResult"] == "materialized"
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("ok") is True
