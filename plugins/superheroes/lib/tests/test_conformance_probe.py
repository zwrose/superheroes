import importlib.util
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = _load("conformance_probe", "conformance_probe.py")
ED = _load("engine_dispatch", "engine_dispatch.py")
EA = _load("engine_adapter", "engine_adapter.py")
ERC = _load("engine_result_channel", "engine_result_channel.py")
PP = _load("preflight_probe", "preflight_probe.py")
MR = _load("model_registry", "model_registry.py")
SM = _load("seat_map", "seat_map.py")
PC = _load("payload_contracts", "payload_contracts.py")

_TIERS = {
    "implementer": "composer-2.5",
    "pilot": "sonnet",
    "reviewer": "gpt-5.6-terra",
    "reviewer-deep": "gpt-5.6-sol",
}
_CALIB_PREFS = {"implementation": "cursor", "reviewer": "codex"}


def test_probe_prompt_is_result_channel_neutral():
    assert "runner's declared result channel" in CP._PROBE_PROMPT
    assert "with nothing before or after the object" not in CP._PROBE_PROMPT


def _repo(tmp_path, git_as_file=True):
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    if git_as_file:
        (root / ".git").write_text("gitdir: /fake/worktree\n", encoding="utf-8")
    else:
        (root / ".git").mkdir()
    return str(root)


def _fake_build_view(tmp_path):
    counter = {"n": 0}

    def build_view(repo_real, *, diff_base=None, pr_body_path=None, session_dir=None):
        counter["n"] += 1
        view_dir = str(tmp_path / ("view-%d" % counter["n"]))
        os.makedirs(view_dir, exist_ok=True)
        repo = os.path.realpath(repo_real)
        for name in os.listdir(repo):
            src = os.path.join(repo, name)
            dst = os.path.join(view_dir, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        return {
            "path": view_dir,
            "strategy": "git-archive-export",
            "stripped": [],
            "strippedCount": 0,
            "headSha": "abc123fake",
            "sourceDirty": False,
            "buildSeconds": 0.01,
            "bytes": 1,
            "fileCount": 1,
        }

    return build_view


def _valid_prompt(tmp_path, content="Review.\n"):
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


def _codex_seat():
    cell = MR.matrix_config("reviewer-deep", "codex")
    return {"vendor": "codex", "model": cell[0], "effort": cell[1], "role": "reviewer-deep"}


def _native_verdicts_branch():
    contract, _ = PC.payload_contract(PC.P_VERIFIERS)
    elem = contract["elements"]["verdicts"]
    verdict = {}
    for field in list(elem.get("required") or []) + list(elem.get("optional") or ()):
        if field == "verdict":
            verdict[field] = elem["enums"]["verdict"][0]
        elif field == "id":
            verdict[field] = "conformance-probe-1"
        elif field == "reason":
            verdict[field] = "verified"
        else:
            verdict[field] = None
    return {
        "resultKind": "verdicts",
        "verdicts": [verdict],
        "findings": None,
        "grouping": None,
        "id": None,
        "ruling": None,
        "reason": None,
        "newIssues": None,
        "evidence": None,
        "auditorVendor": None,
        "investigated": ["plugins/superheroes/lib/engine_result_channel.py"],
    }


def _codex_event_stream(action_items=1):
    lines = []
    for i in range(action_items):
        lines.append(json.dumps({
            "type": "item.completed",
            "item": {"id": "action_%d" % i, "type": "command_execution"},
        }))
    payload = json.dumps({"verdicts": [{"id": "conformance-probe-1", "verdict": "CONFIRMED", "reason": "ok"}]})
    lines.append(json.dumps({
        "type": "item.completed",
        "item": {"id": "agent_msg", "type": "agent_message", "text": payload},
    }))
    lines.append(json.dumps({
        "type": "turn.completed",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }))
    return "\n".join(lines)


def _cursor_event_stream(tool_calls=1, verdicts=None):
    lines = []
    for i in range(tool_calls):
        call_id = "c%d" % (i + 1)
        lines.append(json.dumps({"type": "tool_call", "call_id": call_id, "subtype": "started"}))
        lines.append(json.dumps({"type": "tool_call", "call_id": call_id, "subtype": "completed"}))
    if verdicts is None:
        verdicts = [{"id": "conformance-probe-1", "verdict": "CONFIRMED", "reason": "ok"}]
    lines.append(json.dumps({"type": "result", "verdicts": verdicts}))
    return "\n".join(lines)


class FakeRunner:
    def __init__(self, responses, *, sync_native=True):
        self.responses = list(responses)
        self.calls = []
        self.sync_native = sync_native

    def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
        self.calls.append({"argv": argv, "timeout": timeout, "cwd": cwd})
        idx = len(self.calls) - 1
        resp = self.responses[idx] if idx < len(self.responses) else self.responses[-1]
        if callable(resp):
            out = resp(argv, prompt_bytes, timeout, progress_cb, cwd)
        else:
            out = resp
        if isinstance(out, tuple) and len(out) == 4:
            stdout, timed_out, rc, stderr_tail = out
        else:
            stdout, timed_out, rc, stderr_tail = out, False, 0, ""
        if self.sync_native and isinstance(stdout, str):
            result_path = None
            if "-o" in argv:
                result_path = argv[argv.index("-o") + 1]
            elif prompt_bytes is not None:
                result_path = ERC.result_file_path_from_prompt(
                    prompt_bytes.decode("utf-8", "ignore"))
            if result_path:
                try:
                    branch = _native_verdicts_branch()
                    with open(result_path, "w", encoding="utf-8") as fh:
                        json.dump({"result": branch}, fh, separators=(",", ":"))
                        fh.write("\n")
                except OSError:
                    pass
        return stdout, timed_out, rc, stderr_tail


def _probe_result(engine, **overrides):
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    seat_cell = MR.matrix_config("reviewer-deep", engine)
    base = {
        "schema": CP.SCHEMA,
        "ok": True,
        "engine": engine,
        "channel": ERC.channel_for(engine),
        "seat": {"vendor": engine, "model": seat_cell[0], "effort": seat_cell[1], "role": "reviewer-deep"},
        "probedCell": [engine, seat_cell[0], seat_cell[1]],
        "repoRoot": overrides.pop("repoRoot", "/repo"),
        "startedAt": now,
        "completedAt": now,
        "wallSeconds": 1.0,
        "runDir": "/tmp/run",
        "legs": {
            "resultProduction": {"ok": True, "detail": None, "evidence": {}},
            "completionDetection": {"ok": True, "detail": None, "evidence": {}},
            "progressTelemetry": {"ok": True, "detail": None, "evidence": {}},
        },
        "failed": [],
        "dependentRoles": [],
        "dependentLanes": "no calibrated role routes to %s" % engine,
        "preflightCheck": {"state": "pass", "reason": "ok", "evidence": "evidence"},
    }
    base.update(overrides)
    return base


def _ok_dispatchable_probe_paths(tmp_path, repo, omit=(), **per_engine):
    """Write one probe JSON per dispatchable engine; values are overrides or full records."""
    paths = []
    for engine in CP.DISPATCHABLE_ENGINES:
        if engine in omit:
            continue
        supplied = per_engine.get(engine)
        if supplied is not None and not isinstance(supplied, dict):
            data = supplied
        elif isinstance(supplied, dict):
            data = _probe_result(engine, repoRoot=repo, **supplied)
        else:
            data = _probe_result(engine, repoRoot=repo)
        path = tmp_path / ("probe-%s.json" % engine)
        path.write_text(json.dumps(data), encoding="utf-8")
        paths.append(str(path))
    return paths


def _calibration_rows(**prefs):
    merged = dict(_CALIB_PREFS)
    merged.update(prefs)
    return PP.dispatch_calibration(prefs=merged, tiers=_TIERS)


# --- required tests -----------------------------------------------------------


def test_engine_set_is_derived_from_adapter_and_channel_map():
    assert CP.DISPATCHABLE_ENGINES == ("codex", "cursor", "claude")
    payload, code, stderr = CP.probe("openai", repo_root="/tmp", run_dir="/tmp/run")
    assert code == 1
    assert payload["legs"]["resultProduction"]["detail"] == "engine-not-dispatchable"
    assert stderr is not None


def test_dispatchable_engines_include_claude():
    assert CP.DISPATCHABLE_ENGINES == ("codex", "cursor", "claude")


def _claude_seat():
    cell = MR.matrix_config("reviewer-deep", "claude")
    return {"vendor": "claude", "model": cell[0], "effort": cell[1], "role": "reviewer-deep"}


def _claude_event_stream(tool_calls=1, structured_output=None):
    lines = []
    for i in range(tool_calls):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "tool-%d" % i,
                    "name": "Glob",
                    "input": {},
                }],
            },
        }))
    if structured_output is None:
        structured_output = {"result": _native_verdicts_branch()}
    lines.append(json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "structured_output": structured_output,
    }))
    return "\n".join(lines) + "\n"


def test_run_grades_three_legs_ok_on_valid_native_result(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stdout = _codex_event_stream(action_items=2)
    fake = FakeRunner([(stdout, False, 0, "")])
    payload, code, stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    assert payload["ok"] is True
    assert payload["legs"]["resultProduction"]["ok"] is True
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is True
    assert payload["preflightCheck"]["state"] == "pass"
    assert stderr is None
    prompt_path = os.path.join(os.path.dirname(run_dir), os.path.basename(run_dir) + ".probe-prompt.md")
    prompt_text = open(prompt_path, encoding="utf-8").read()
    assert "at least one regular file at its top level" in prompt_text
    assert '"verdicts"' in prompt_text
    assert "reason" in prompt_text
    assert '"result":' not in prompt_text
    assert "plugins/superheroes" not in prompt_text


def test_run_grades_three_legs_ok_on_valid_claude_native_result(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    structured = {"result": _native_verdicts_branch()}
    stdout = _claude_event_stream(tool_calls=1, structured_output=structured)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return stdout, False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    assert payload["ok"] is True
    assert payload["channel"] == ERC.CHANNEL_NATIVE
    assert payload["legs"]["resultProduction"]["ok"] is True
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is True
    assert stderr is None


def test_result_production_fails_on_claude_native_schema_invalid(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    invalid = _native_verdicts_branch()
    invalid["investigated"] = ["path.py", 42]
    structured = {"result": invalid}

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return _claude_event_stream(structured_output=structured), False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, _stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["resultProduction"]["ok"] is False
    assert payload["legs"]["resultProduction"]["detail"] == "native-result-schema-invalid"
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is True


def test_claude_telemetry_absent_when_only_the_structured_output_call(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    structured = {"result": _native_verdicts_branch()}
    stdout = _claude_event_stream(tool_calls=0, structured_output=structured)
    stdout = json.dumps({
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use", "id": "so1", "name": "StructuredOutput", "input": {},
        }]},
    }) + "\n" + stdout

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return stdout, False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, _stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["resultProduction"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "telemetry-absent"


def test_claude_completion_fails_on_nonzero_exit(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    fake = FakeRunner([("", False, 1, "")])
    payload, code, _stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    leg = payload["legs"]["completionDetection"]
    assert leg["ok"] is False
    assert leg["detail"] == "auth-or-config-refusal"


def test_run_grades_three_legs_ok_on_valid_cursor_native_result(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stdout = _cursor_event_stream(tool_calls=2)
    fake = FakeRunner([(stdout, False, 0, "")])
    payload, code, stderr = CP.probe(
        "cursor", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    assert payload["ok"] is True
    assert payload["channel"] == ERC.CHANNEL_NATIVE
    assert payload["legs"]["resultProduction"]["ok"] is True
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is True
    assert payload["preflightCheck"]["state"] == "pass"
    assert stderr is None


def test_result_production_fails_on_schema_invalid_native_result(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    invalid = _native_verdicts_branch()
    invalid["investigated"] = ["path.py", 42]

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        result_path = argv[argv.index("-o") + 1]
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"result": invalid}, fh, separators=(",", ":"))
            fh.write("\n")
        return _codex_event_stream(), False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["resultProduction"]["ok"] is False
    assert payload["legs"]["resultProduction"]["detail"] == "native-result-schema-invalid"
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is True


def test_result_production_ok_but_telemetry_fails_when_only_the_result_write(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    branch = _native_verdicts_branch()

    def _cursor_edit_stream(result_path):
        return "\n".join([
            json.dumps({
                "type": "tool_call", "call_id": "w1", "subtype": "started",
                "tool_call": {"editToolCall": {"args": {"path": result_path}}},
            }),
            json.dumps({
                "type": "tool_call", "call_id": "w1", "subtype": "completed",
                "tool_call": {"editToolCall": {"args": {"path": result_path}}},
            }),
        ])

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        result_path = ERC.result_file_path_from_prompt(
            prompt_bytes.decode("utf-8", "ignore"))
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"result": branch}, fh, separators=(",", ":"))
            fh.write("\n")
        return _cursor_edit_stream(result_path), False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, _stderr = CP.probe(
        "cursor", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["resultProduction"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "telemetry-absent"


def test_result_production_fails_on_cursor_native_schema_invalid(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    invalid = _native_verdicts_branch()
    invalid["investigated"] = ["path.py", 42]

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        result_path = argv[argv.index("-o") + 1] if "-o" in argv else ERC.result_file_path_from_prompt(
            prompt_bytes.decode("utf-8", "ignore"))
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"result": invalid}, fh, separators=(",", ":"))
            fh.write("\n")
        return _cursor_event_stream(tool_calls=1), False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, _stderr = CP.probe(
        "cursor", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["resultProduction"]["ok"] is False
    assert payload["legs"]["resultProduction"]["detail"] == "native-result-schema-invalid"
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is True


def test_completion_fails_on_timeout(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    fake = FakeRunner([(_codex_event_stream(), True, 0, "")])
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["completionDetection"]["ok"] is False
    assert payload["legs"]["completionDetection"]["detail"] == "no-response-within-wait"


def test_completion_fails_on_refusal_names_auth_or_config(tmp_path):
  # axis: auth-or-config-refusal
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stderr_tail = "spawn-failed:CommandNotFound"
    fake = FakeRunner([("", False, 127, stderr_tail)])
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    leg = payload["legs"]["completionDetection"]
    assert leg["ok"] is False
    assert leg["detail"] == "auth-or-config-refusal"
    assert "spawn-failed" in (leg["evidence"].get("refusal") or "")


def test_telemetry_fails_on_zero_tool_call_count(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stdout = _codex_event_stream(action_items=0)
    fake = FakeRunner([(stdout, False, 0, "")])
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "telemetry-absent"


def test_grade_legs_accepts_production_last_activity_stamp():
    terminal = {
        "ok": True, "terminal": True, "attempts": 1,
        "resultKind": "verdicts", "verdicts": [{"id": "conformance-probe-1"}],
        "engagement": {"source": "codex-events", "telemetry": "tool-calls", "toolCalls": 2},
        "runDir": "/tmp/run",
    }
    state = {
        "attempts": {
            1: {"ended": {
                "exit": 0, "timedOut": False, "attempt": 1,
                "lastActivityAt": 1700000000.0, "activitySource": "codex-events",
            }},
        },
    }
    legs = CP._grade_legs(terminal, state, False)
    assert legs["progressTelemetry"]["ok"] is True


def test_grade_legs_rejects_missing_production_last_activity():
    terminal = {
        "ok": True, "terminal": True, "attempts": 1,
        "resultKind": "verdicts", "verdicts": [{"id": "conformance-probe-1"}],
        "engagement": {"source": "codex-events", "telemetry": "tool-calls", "toolCalls": 2},
        "runDir": "/tmp/run",
    }
    state = {
        "attempts": {
            1: {"ended": {
                "exit": 0, "timedOut": False, "attempt": 1,
                "lastActivityAt": None, "activitySource": "codex-events",
            }},
        },
    }
    legs = CP._grade_legs(terminal, state, False)
    assert legs["progressTelemetry"]["ok"] is False
    assert legs["progressTelemetry"]["detail"] == "telemetry-absent"


def test_grade_legs_rejects_injected_seam_record_without_stamp():
    terminal = {
        "ok": True, "terminal": True, "attempts": 1,
        "resultKind": "verdicts", "verdicts": [{"id": "conformance-probe-1"}],
        "engagement": {"source": "codex-events", "telemetry": "tool-calls", "toolCalls": 2},
        "runDir": "/tmp/run",
    }
    state = {
        "attempts": {
            1: {"ended": {
                "exit": 0, "timedOut": False, "attempt": 1,
                "lastActivityAt": None, "activitySource": "injected-seam", "at": 1700000000.0,
            }},
        },
    }
    legs = CP._grade_legs(terminal, state, False)
    assert legs["progressTelemetry"]["ok"] is False
    assert legs["progressTelemetry"]["detail"] == "telemetry-absent"


def test_probe_injected_seam_stamps_last_activity_at(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stdout = _codex_event_stream(action_items=2)
    fake = FakeRunner([(stdout, False, 0, "")])
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    assert payload["legs"]["progressTelemetry"]["ok"] is True
    records, _ = ED._journal_read(run_dir)
    ended = next(r for r in records if r.get("kind") == "attempt-ended")
    assert isinstance(ended["lastActivityAt"], float)
    assert ended["activitySource"] == "injected-seam"


def test_probe_prompt_lands_beside_a_given_run_dir(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stdout = _codex_event_stream(action_items=2)
    fake = FakeRunner([(stdout, False, 0, "")])
    CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    sibling = os.path.join(os.path.dirname(run_dir), os.path.basename(run_dir) + ".probe-prompt.md")
    assert os.path.isfile(sibling)
    assert not os.path.exists(os.path.join(os.path.dirname(run_dir), "probe-prompt.md"))


def test_probe_without_run_dir_uses_a_private_parent(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    parent = str(tmp_path / "probe-parent")
    os.makedirs(parent, exist_ok=True)
    calls = []

    def _mkdtemp(*_a, **_k):
        calls.append(parent)
        return parent

    monkeypatch.setattr(CP.tempfile, "mkdtemp", _mkdtemp)
    stdout = _codex_event_stream(action_items=2)
    fake = FakeRunner([(stdout, False, 0, "")])
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=None, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    assert payload["runDir"] == os.path.realpath(os.path.join(parent, "run"))
    assert os.path.isfile(os.path.join(parent, "probe-prompt.md"))


def test_telemetry_fails_when_stream_has_no_tool_calls(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    plain = json.dumps({"verdicts": [{"id": "conformance-probe-1", "verdict": "CONFIRMED", "reason": "x"}]})

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        result_path = argv[argv.index("-o") + 1]
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"result": _native_verdicts_branch()}, fh, separators=(",", ":"))
            fh.write("\n")
        return plain, False, 0, ""

    fake = FakeRunner([runner])
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "telemetry-absent"


def test_cli_failure_is_loud(tmp_path, capsys):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    fake = FakeRunner([("", False, 127, "spawn-failed:NoEngine")])

    bv = _fake_build_view(tmp_path)

    real_probe = CP.probe

    def _wrapped(*args, **kwargs):
        kwargs["run_engine"] = fake
        kwargs.setdefault("build_view", bv)
        return real_probe(*args, **kwargs)

    CP.probe = _wrapped
    try:
        code = CP.main([
            "conformance_probe", "run",
            "--engine", "codex", "--repo-root", repo, "--run-dir", run_dir, "--timeout", "30",
        ])
    finally:
        CP.probe = real_probe
    captured = capsys.readouterr()
    assert code == 1
    assert "CONFORMANCE PROBE FAILED engine=codex" in captured.err
    assert "dependent lanes:" in captured.err


def test_dependent_roles_from_calibration():
    rows = _calibration_rows()
    roles, lanes = CP._dependent_from_calibration(rows, "codex")
    assert "brief-check" in roles
    assert "review-code" in roles
    assert "codex" in lanes


def test_preflight_entry_hold_when_failed_without_owner_word(tmp_path):
  # axis: hold-without-owner-word
    repo = _repo(tmp_path)
    codex_fail = _probe_result("codex", ok=False, repoRoot=repo, failed=["resultProduction"])
    codex_fail["legs"]["resultProduction"]["ok"] = False
    codex_fail["failed"] = ["resultProduction"]
    codex_fail["preflightCheck"]["state"] = "fail"
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, codex=codex_fail)
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(),
    )
    assert code == 0
    assert payload["engine-auth"]["state"] == "fail"
    assert "hold" in payload["engine-auth"]["reason"]


@pytest.mark.parametrize("case,expect", [
    ("missing", "probe-missing:codex"),
    ("duplicate", "probe-duplicate:codex"),
    ("foreign", "probe-foreign-repo:codex"),
    ("stale", "probe-stale:codex"),
])
def test_preflight_entry_refuses_missing_duplicate_foreign_stale(tmp_path, case, expect):
  # axis: probe-missing-duplicate-foreign-stale
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    paths = []
    if case != "missing":
        cpath = tmp_path / "codex.json"
        if case == "foreign":
            codex["repoRoot"] = "/other/repo"
        if case == "stale":
            old = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(microsecond=0)
            codex["completedAt"] = old.isoformat().replace("+00:00", "Z")
        cpath.write_text(json.dumps(codex), encoding="utf-8")
        paths.append(str(cpath))
        if case == "duplicate":
            paths.append(str(cpath))
    paths.extend(_ok_dispatchable_probe_paths(tmp_path, repo, omit=("codex",), cursor=cursor))
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 1
    assert payload["reason"] == expect


def test_preflight_entry_launch_without_names_substitutes_from_probed_cells(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    captured = {}

    def _capture_build(*args, **kwargs):
        captured.update(kwargs)
        return SM.build(*args, **kwargs)

    monkeypatch.setattr(CP.seat_map, "build", _capture_build)
    cal = _calibration_rows()
    codex_fail = _probe_result("codex", ok=False, repoRoot=repo, failed=["resultProduction"])
    codex_fail["legs"]["resultProduction"]["ok"] = False
    codex_fail["failed"] = ["resultProduction"]
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, codex=codex_fail)
    payload, code = CP.preflight_entry(
        repo,
        paths,
        launch_without=["codex"],
        owner_words=["owner approves"],
        calibration_rows=cal,
    )
    assert code == 0
    assert payload["engine-auth"]["state"] == "pass"
    assert "substitutes" in payload["engine-auth"]["evidence"]
    assert captured.get("live_cells_source") == "probed"
    assert captured.get("live_cells") == [tuple(cursor_ok["probedCell"])]


def test_preflight_entry_parks_on_same_family(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def _park_build(*args, **kwargs):
        sm = SM.build(*args, **kwargs)
        degradations = list(sm.get("degradations") or [])
        degradations.append({
            "constraint": "same-family",
            "seat": "architecture-reviewer",
            "reason": (
                "seat architecture-reviewer seated the maker family openai — "
                "no alternative family is live"
            ),
        })
        out = dict(sm)
        out["degradations"] = degradations
        return out

    monkeypatch.setattr(CP.seat_map, "build", _park_build)
    cal = _calibration_rows(implementation="codex", reviewer="codex", pilot="cursor")
    cursor_fail = _probe_result("cursor", ok=False, repoRoot=repo, failed=["resultProduction"])
    cursor_fail["legs"]["resultProduction"]["ok"] = False
    cursor_fail["failed"] = ["resultProduction"]
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, cursor=cursor_fail)
    payload, code = CP.preflight_entry(
        repo,
        paths,
        launch_without=["cursor"],
        owner_words=["proceed anyway"],
        calibration_rows=cal,
    )
    assert code == 0
    assert payload["engine-auth"]["state"] == "fail"
    assert "PARK" in payload["engine-auth"]["reason"]


def test_probe_refuses_reused_run_dir_with_folded_result(tmp_path):
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    stdout = _codex_event_stream(action_items=1)
    fake = FakeRunner([(stdout, False, 0, "")])
    payload1, code1, _ = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code1 == 0
    payload2, code2, _ = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert code2 == 1
    assert payload2["legs"]["resultProduction"]["detail"] == "run-dir-reused"


def test_probe_run_dir_setup_failure_never_raises(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(CP.tempfile, "mkdtemp", _boom)
    payload, code, stderr = CP.probe("codex", repo_root=repo)
    assert code == 1
    assert payload["legs"]["resultProduction"]["detail"] == "run-dir-setup-failed:OSError"
    assert stderr is not None


def test_preflight_requires_all_dispatchable_engines_not_only_calibrated(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    cal = _calibration_rows(implementation="codex", reviewer="codex", pilot="codex")
    payload, code = CP.preflight_entry(repo, [str(cpath)], calibration_rows=cal)
    assert code == 1
    assert payload["reason"] == "probe-missing:claude"


def test_preflight_entry_wave_binding_none_without_wave_arg(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 0
    assert payload["waveBinding"] == "none"


def test_preflight_entry_refuses_wave_mismatch(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo, wave="wave-a")
    cursor = _probe_result("cursor", repoRoot=repo, wave="wave-a")
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(), wave="wave-b",
    )
    assert code == 1
    assert payload["reason"].startswith("probe-wave-mismatch:")


def test_preflight_entry_refuses_ok_disagreeing_with_legs(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo, ok=True)
    codex["legs"]["resultProduction"]["ok"] = False
    codex["failed"] = ["resultProduction"]
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "probe-result-malformed:%s" % cpath


def test_preflight_entry_refuses_failed_list_disagreeing_with_legs(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo, ok=True)
    codex["failed"] = ["progressTelemetry"]
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "probe-result-malformed:%s" % cpath


def test_preflight_entry_refuses_record_without_wave_under_wave(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    assert "wave" not in codex
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(), wave="wave-a",
    )
    assert code == 1
    assert payload["reason"].startswith("probe-wave-mismatch:")


def test_expected_probe_cell_reads_the_registry_home(monkeypatch):
    monkeypatch.setattr(CP.model_registry, "matrix_config", lambda role, eng: ("m-x", "e-x"))
    monkeypatch.setattr(CP.seat_map, "matrix_config", lambda role, eng: ("m-y", "e-y"))
    assert CP._expected_probe_cell("codex") == ["codex", "m-x", "e-x"]


def test_seat_for_engine_reads_model_registry_home(monkeypatch):
    monkeypatch.setattr(CP.model_registry, "matrix_config", lambda role, eng: ("m-x", "e-x"))
    monkeypatch.setattr(CP.seat_map, "matrix_config", lambda role, eng: ("m-y", "e-y"))
    seat, err = CP._seat_for_engine("codex")
    assert err is None
    assert seat["model"] == "m-x"
    assert seat["effort"] == "e-x"


def test_validate_probe_record_refuses_naive_completed_at():
    raw = _probe_result("codex", completedAt="2026-09-19T12:00:00")
    err = CP._validate_probe_record(raw, "/tmp/codex.json")
    assert err == "probe-result-malformed:/tmp/codex.json"


def test_preflight_entry_stale_boundary_exact_age_passes(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(CP, "_now_utc", lambda: now)
    completed = (now - timedelta(seconds=3600)).replace(microsecond=0)
    completed_iso = completed.isoformat().replace("+00:00", "Z")
    codex = _probe_result("codex", repoRoot=repo, completedAt=completed_iso)
    cursor = _probe_result("cursor", repoRoot=repo, completedAt=completed_iso)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 0


def test_preflight_entry_stale_boundary_one_past_refuses(tmp_path, monkeypatch):
    """axis: age == max_age_seconds + 1 refuses probe-stale (the bound is >, pinned one past)."""
    repo = _repo(tmp_path)
    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(CP, "_now_utc", lambda: now)
    completed = (now - timedelta(seconds=3601)).replace(microsecond=0)
    completed_iso = completed.isoformat().replace("+00:00", "Z")
    codex = _probe_result("codex", repoRoot=repo, completedAt=completed_iso)
    cursor = _probe_result("cursor", repoRoot=repo, completedAt=completed_iso)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 1
    assert payload["reason"] == "probe-stale:codex"


def test_preflight_entry_stale_boundary_future_completed_at_refuses(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(CP, "_now_utc", lambda: now)
    completed = (now + timedelta(seconds=60)).replace(microsecond=0)
    completed_iso = completed.isoformat().replace("+00:00", "Z")
    codex = _probe_result("codex", repoRoot=repo, completedAt=completed_iso)
    cursor = _probe_result("cursor", repoRoot=repo, completedAt=completed_iso)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 1
    assert payload["reason"] == "probe-stale:codex"


@pytest.mark.parametrize("completed_at,expect", [
    ("", "probe-stale:codex"),
    ("not-a-date", "probe-stale:codex"),
    ("2026-09-19T12:00:00", "probe-result-malformed:"),
    (12345, "probe-result-malformed:"),
])
def test_preflight_entry_completed_at_parse_edges(tmp_path, completed_at, expect):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo, completedAt=completed_at)
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 1
    if expect.endswith(":"):
        assert payload["reason"].startswith(expect)
    else:
        assert payload["reason"] == expect


def test_preflight_entry_refuses_probe_cell_mismatch(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    codex["probedCell"] = ["codex", "wrong-model", None]
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "probe-cell-mismatch:codex"


def test_preflight_entry_refuses_malformed_json(tmp_path):
    repo = _repo(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    cursor = _probe_result("cursor", repoRoot=repo)
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(repo, [str(bad), str(kpath)], calibration_rows=_calibration_rows())
    assert code == 1
    assert payload["reason"].startswith("probe-result-malformed:")


def test_preflight_entry_refuses_probe_taken_on_a_retired_channel(tmp_path):
    """A cursor probe record taken on the marker channel (pre-3c) is refused under the typed-file
    channel with its own token — a day-long freshness window must not admit a stale-channel proof.

    Bites on: the `channel != engine_result_channel.channel_for(eng)` check in `_validate_probe_record`."""
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    cursor["channel"] = "marker"
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "probe-channel-mismatch:cursor"


def test_preflight_entry_refuses_wrong_schema(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    codex["schema"] = "wrong/1"
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"].startswith("probe-result-malformed:")


def test_preflight_entry_refuses_truthy_ok_without_legs(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    codex.pop("legs")
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)], calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"].startswith("probe-result-malformed:")


def test_preflight_entry_refuses_owner_word_missing(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)],
        launch_without=["codex", "cursor"],
        owner_words=["only-one"],
        calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "owner-word-missing"


def test_preflight_entry_refuses_calibration_unreadable(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    cal = [{"role": "*", "readError": "cannot read prefs"}]
    payload, code = CP.preflight_entry(repo, [str(cpath), str(kpath)], calibration_rows=cal)
    assert code == 1
    assert payload["reason"] == "calibration-unreadable"


def test_preflight_entry_refuses_author_family_unresolved(tmp_path):
    repo = _repo(tmp_path)
    codex_fail = _probe_result("codex", ok=False, repoRoot=repo, failed=["resultProduction"])
    codex_fail["legs"]["resultProduction"]["ok"] = False
    codex_fail["failed"] = ["resultProduction"]
    cursor_ok = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex_fail), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor_ok), encoding="utf-8")
    cal = [{"role": "implementer", "engine": "codex"}]
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)],
        launch_without=["codex"], owner_words=["proceed"],
        calibration_rows=cal,
    )
    assert code == 1
    assert payload["reason"] == "author-family-unresolved"


def test_preflight_entry_refuses_seat_map_failed(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("seat-map-broken")

    monkeypatch.setattr(CP.seat_map, "build", _boom)
    codex_fail = _probe_result("codex", ok=False, repoRoot=repo, failed=["resultProduction"])
    codex_fail["legs"]["resultProduction"]["ok"] = False
    codex_fail["failed"] = ["resultProduction"]
    cursor_ok = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex_fail), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor_ok), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)],
        launch_without=["codex"], owner_words=["proceed"],
        calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "seat-map-failed:RuntimeError"


def test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    cursor = _probe_result("cursor", repoRoot=repo)
    cpath = tmp_path / "codex.json"
    cpath.write_text(json.dumps(codex), encoding="utf-8")
    kpath = tmp_path / "cursor.json"
    kpath.write_text(json.dumps(cursor), encoding="utf-8")
    payload, code = CP.preflight_entry(
        repo, [str(cpath), str(kpath)],
        launch_without=["codex"], owner_words=["  "],
        calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "owner-word-blank"
    payload2, code2 = CP.preflight_entry(
        repo, [str(cpath), str(kpath)],
        launch_without=["cursor"], owner_words=["word"],
        calibration_rows=_calibration_rows(),
    )
    assert code2 == 1
    assert payload2["reason"] == "launch-without-not-failed:cursor"
