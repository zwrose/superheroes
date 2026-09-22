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


def _ok_legs():
    return {
        "resultProduction": {"ok": True, "detail": None, "evidence": {}},
        "completionDetection": {"ok": True, "detail": None, "evidence": {}},
        "progressTelemetry": {"ok": True, "detail": None, "evidence": {}},
    }


def _failed_probe_result(engine, leg_name, detail=None, repo=None, **kwargs):
    legs = _ok_legs()
    legs[leg_name] = {"ok": False, "detail": detail or leg_name, "evidence": {}}
    out = _probe_result(
        engine, ok=False, repoRoot=repo, legs=legs,
        failed=[leg_name], **kwargs,
    )
    out["preflightCheck"]["state"] = "fail"
    return out


def _probe_result(engine, **overrides):
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    seat_cell = MR.matrix_config("reviewer-deep", engine)
    modes = CP._modes_for_engine(engine)
    mode_legs = overrides.pop("modeLegs", None)
    probed_modes = overrides.pop("probedModes", None)
    legs_override = overrides.pop("legs", None)
    if mode_legs is None:
        source_legs = legs_override if legs_override is not None else _ok_legs()
        mode_legs = {mode: dict(source_legs) for mode in modes}
    if probed_modes is None:
        probed_modes = list(modes)
    legs = CP._derive_flat_legs(mode_legs)
    base = {
        "schema": CP.SCHEMA,
        "ok": all(legs[n]["ok"] for n in CP._LEG_NAMES),
        "engine": engine,
        "channel": ERC.channel_for(engine),
        "seat": {"vendor": engine, "model": seat_cell[0], "effort": seat_cell[1], "role": "reviewer-deep"},
        "probedCell": [engine, seat_cell[0], seat_cell[1]],
        "repoRoot": overrides.pop("repoRoot", "/repo"),
        "startedAt": now,
        "completedAt": now,
        "wallSeconds": 1.0,
        "runDir": "/tmp/run",
        "probedModes": probed_modes,
        "modeLegs": mode_legs,
        "legs": legs,
        "failed": [n for n in CP._LEG_NAMES if not legs[n]["ok"]],
        "dependentRoles": [],
        "dependentLanes": "no calibrated role routes to %s" % engine,
        "preflightCheck": {"state": "pass", "reason": "ok", "evidence": "evidence"},
    }
    base.update(overrides)
    if legs_override is not None and "legs" not in overrides:
        base["legs"] = legs_override
    if "ok" in overrides:
        base["ok"] = overrides["ok"]
    if "failed" in overrides:
        base["failed"] = overrides["failed"]
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
            if "legs" in supplied:
                data = dict(supplied)
            else:
                merged = {"repoRoot": repo, **supplied}
                merged.pop("engine", None)
                data = _probe_result(engine, **merged)
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
    assert payload["legs"]["resultProduction"]["detail"] == "default: engine-not-dispatchable"
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


def test_probe_refuses_symlinked_run_dir(tmp_path):
    repo = _repo(tmp_path)
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    run_link = tmp_path / "run-link"
    os.symlink(str(real_dir), str(run_link))
    payload, code, stderr = CP.probe(
        "codex", repo_root=repo, run_dir=str(run_link), timeout=30,
    )
    assert code == 1
    # resolving the leaf symlink via realpath first (rather than refusing on the raw path)
    # would silently swap in the symlink's target and bypass this refusal entirely.
    assert payload["legs"]["resultProduction"]["detail"].endswith("run-dir-is-symlink")
    assert stderr is not None


def test_probe_refuses_parent_run_dir_with_unrecognized_entries(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "stray.txt").write_text("x", encoding="utf-8")
    payload, code, stderr = CP.probe(
        "claude", repo_root=repo, run_dir=str(run_dir), timeout=30,
    )
    assert code == 1
    assert payload["modeLegs"]["print"]["resultProduction"]["detail"] == "run-dir-not-empty-unopened"
    assert payload["modeLegs"]["background"]["resultProduction"]["detail"] == "run-dir-not-empty-unopened"
    assert stderr is not None


def test_probe_accepts_parent_run_dir_with_only_recognized_mode_subdirs(tmp_path, monkeypatch):
    # Negative half of the guard above: a parent containing only the recognized print/
    # background/ mode subdirectories (both empty — no prior journal) is NOT refused as
    # run-dir-not-empty-unopened, and the probe proceeds to dispatch normally.
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "print").mkdir()
    (run_dir / "background").mkdir()
    structured = {"result": _native_verdicts_branch()}
    stdout = _claude_event_stream(tool_calls=1, structured_output=structured)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return stdout, False, 0, ""

    fake = FakeRunner([runner, runner], sync_native=False)
    payload, code, stderr = CP.probe(
        "claude", repo_root=repo, run_dir=str(run_dir), timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    for mode in ("print", "background"):
        assert payload["modeLegs"][mode]["resultProduction"]["detail"] != "run-dir-not-empty-unopened"


def test_claude_probe_background_mode_without_native_result_fails_overall(tmp_path, monkeypatch):
    # NOTE: this drives the injected `run_engine` test seam for BOTH claude modes. The
    # background runner below never writes a native result file, so this proves the
    # all-FAILED path for the background leg — it is not a claude happy-path test. See
    # test_claude_probe_green_as_far_as_the_injected_seam_can_reach below for how far a
    # green claude probe can be pushed under this harness, and why one leg stays red.
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
    assert payload["channel"] == ERC.CHANNEL_NATIVE
    assert payload["probedModes"] == ["print", "background"]
    assert set(payload["modeLegs"]) == {"print", "background"}
    for leg_name in CP._LEG_NAMES:
        assert payload["modeLegs"]["print"][leg_name]["ok"] is True
    assert payload["modeLegs"]["background"]["resultProduction"]["ok"] is False
    assert payload["modeLegs"]["background"]["resultProduction"]["detail"] == "native-result-missing"
    assert payload["modeLegs"]["background"]["completionDetection"]["ok"] is True
    assert payload["modeLegs"]["background"]["progressTelemetry"]["ok"] is False
    assert payload["modeLegs"]["background"]["progressTelemetry"]["detail"] == "telemetry-absent"
    assert payload["ok"] is False
    assert payload["legs"]["resultProduction"]["ok"] is False
    assert payload["legs"]["resultProduction"]["detail"] == "background: native-result-missing"
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "background: telemetry-absent"
    assert code == 1
    assert stderr is not None


def test_claude_probe_green_as_far_as_the_injected_seam_can_reach(tmp_path, monkeypatch):
    """Push the claude two-mode aggregation as close to all-green as this harness setup allows
    without also supplying background telemetry.

    print's three legs pass exactly as in the all-green single-mode tests above. background can
    be fed a schema-valid `StructuredOutput` transcript row (the shape
    `engine_adapter.claude_transcript_result` reads — see
    `test_claude_telemetry_absent_when_only_the_structured_output_call` above for the same
    shape), and `_materialize_stdout_result` genuinely writes a valid native result file for it;
    `_execute_injected_attempt` now stamps that outcome on `transcriptResult` and records
    `transcriptToolCalls` from the transcript rows, so background's resultProduction passes.
    This setup still omits a non-StructuredOutput tool call in the background transcript, so
    progressTelemetry stays `telemetry-absent` — see `test_claude_probe_all_green_both_modes`
    for the full both-mode green path.
    """
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    structured = {"result": _native_verdicts_branch()}
    print_stdout = _claude_event_stream(tool_calls=1, structured_output=structured)
    # Background delivery is RESULT_DELIVERY_TRANSCRIPT: `_materialize_stdout_result` reads the
    # last `StructuredOutput` tool_use block's `input` straight from the transcript rows (see
    # `engine_adapter.claude_transcript_result`) — the same shape used by the progressTelemetry
    # test above (`test_claude_telemetry_absent_when_only_the_structured_output_call`) — rather
    # than the `structured_output` envelope field STDOUT delivery reads.
    background_stdout = json.dumps({
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use", "id": "so1", "name": "StructuredOutput",
            "input": {"result": _native_verdicts_branch()},
        }]},
    })

    def print_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return print_stdout, False, 0, ""

    def background_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return background_stdout, False, 0, ""

    fake = FakeRunner([print_runner, background_runner], sync_native=False)
    payload, code, stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["probedModes"] == ["print", "background"]
    for leg_name in CP._LEG_NAMES:
        assert payload["modeLegs"]["print"][leg_name]["ok"] is True, leg_name
    assert payload["modeLegs"]["background"]["completionDetection"]["ok"] is True
    assert payload["modeLegs"]["background"]["resultProduction"]["ok"] is True
    assert payload["modeLegs"]["background"]["progressTelemetry"]["ok"] is False
    assert payload["modeLegs"]["background"]["progressTelemetry"]["detail"] == "telemetry-absent"
    assert payload["ok"] is False
    assert payload["legs"]["resultProduction"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "background: telemetry-absent"
    assert code == 1


def test_claude_probe_all_green_both_modes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    structured = {"result": _native_verdicts_branch()}
    print_stdout = _claude_event_stream(tool_calls=1, structured_output=structured)
    background_lines = [
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "tool-0", "name": "Glob", "input": {},
            }]},
        }),
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "so1", "name": "StructuredOutput",
                "input": {"result": _native_verdicts_branch()},
            }]},
        }),
        json.dumps({"type": "user", "toolEndsTurn": True}),
    ]
    background_stdout = "\n".join(background_lines) + "\n"

    def print_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return print_stdout, False, 0, ""

    def background_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return background_stdout, False, 0, ""

    fake = FakeRunner([print_runner, background_runner], sync_native=False)
    payload, code, stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert payload["probedModes"] == ["print", "background"]
    for mode in ("print", "background"):
        for leg_name in CP._LEG_NAMES:
            assert payload["modeLegs"][mode][leg_name]["ok"] is True, (mode, leg_name)
    for leg_name in CP._LEG_NAMES:
        assert payload["legs"][leg_name]["ok"] is True, leg_name
    assert payload["ok"] is True
    assert code == 0
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
    assert payload["modeLegs"]["print"]["resultProduction"]["ok"] is False
    assert payload["modeLegs"]["print"]["resultProduction"]["detail"] == "native-result-schema-invalid"
    assert payload["modeLegs"]["background"]["resultProduction"]["ok"] is False
    assert payload["modeLegs"]["background"]["resultProduction"]["detail"] == "native-result-missing"
    assert payload["legs"]["resultProduction"]["ok"] is False
    assert payload["legs"]["resultProduction"]["detail"] == (
        "print: native-result-schema-invalid; background: native-result-missing"
    )
    assert payload["legs"]["completionDetection"]["ok"] is True
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["legs"]["progressTelemetry"]["detail"] == "background: telemetry-absent"


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
    assert payload["modeLegs"]["print"]["resultProduction"]["ok"] is True
    assert payload["modeLegs"]["print"]["progressTelemetry"]["ok"] is False
    assert payload["modeLegs"]["print"]["progressTelemetry"]["detail"] == "telemetry-absent"
    assert payload["legs"]["progressTelemetry"]["ok"] is False
    assert payload["modeLegs"]["background"]["progressTelemetry"]["ok"] is False
    assert payload["modeLegs"]["background"]["progressTelemetry"]["detail"] == "telemetry-absent"
    assert "print: telemetry-absent" in payload["legs"]["progressTelemetry"]["detail"]
    assert "background: telemetry-absent" in payload["legs"]["progressTelemetry"]["detail"]


def test_claude_completion_fails_on_nonzero_exit(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    fake = FakeRunner([("", False, 1, ""), ("", False, 1, "")])
    payload, code, _stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    leg = payload["legs"]["completionDetection"]
    assert leg["ok"] is False
    assert leg["detail"] == "print: auth-or-config-refusal; background: auth-or-config-refusal"


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
    assert payload["legs"]["resultProduction"]["detail"] == "default: native-result-schema-invalid"
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
    assert payload["legs"]["progressTelemetry"]["detail"] == "default: telemetry-absent"


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
    assert payload["legs"]["resultProduction"]["detail"] == "default: native-result-schema-invalid"
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
    assert payload["legs"]["completionDetection"]["detail"] == "default: no-response-within-wait"


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
    assert leg["detail"] == "default: auth-or-config-refusal"
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
    assert payload["legs"]["progressTelemetry"]["detail"] == "default: telemetry-absent"


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
    assert payload["legs"]["progressTelemetry"]["detail"] == "default: telemetry-absent"


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
    codex_fail = _failed_probe_result("codex", "resultProduction", repo=repo)
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
    if case == "missing":
        paths = _ok_dispatchable_probe_paths(tmp_path, repo, omit=("codex",))
    else:
        codex_kw = {}
        if case == "foreign":
            codex_kw["repoRoot"] = "/other/repo"
        if case == "stale":
            old = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(microsecond=0)
            codex_kw["completedAt"] = old.isoformat().replace("+00:00", "Z")
        paths = _ok_dispatchable_probe_paths(tmp_path, repo, codex=codex_kw)
        if case == "duplicate":
            paths.append(str(tmp_path / "probe-codex.json"))
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
    codex_fail = _failed_probe_result("codex", "resultProduction", repo=repo)
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
    cursor_probe = _probe_result("cursor", repoRoot=repo)
    claude_probe = _probe_result("claude", repoRoot=repo)
    assert captured.get("live_cells") == [
        tuple(claude_probe["probedCell"]),
        tuple(cursor_probe["probedCell"]),
    ]


def test_preflight_entry_launch_without_claude_excludes_from_live_vendors(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    captured = {}

    def _capture_build(roster, live_vendors, *args, **kwargs):
        captured["live_vendors"] = list(live_vendors or [])
        return SM.build(roster, live_vendors, *args, **kwargs)

    monkeypatch.setattr(CP.seat_map, "build", _capture_build)
    cal = _calibration_rows()
    claude_fail = _failed_probe_result("claude", "resultProduction", repo=repo)
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, claude=claude_fail)
    payload, code = CP.preflight_entry(
        repo,
        paths,
        launch_without=["claude"],
        owner_words=["owner approves"],
        calibration_rows=cal,
    )
    assert code == 0
    assert "claude" not in captured["live_vendors"]
    seats = payload.get("seatMap", {}).get("seats") or {}
    assert all(v.get("vendor") != "claude" for v in seats.values())


def test_preflight_entry_launch_without_claude_parks_when_no_other_live(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def _park_build(*args, **kwargs):
        sm = SM.build(*args, **kwargs)
        degradations = list(sm.get("degradations") or [])
        degradations.append({
            "constraint": "same-family",
            "seat": "architecture-reviewer",
            "reason": (
                "seat architecture-reviewer seated the maker family xai — "
                "no alternative family is live"
            ),
        })
        out = dict(sm)
        out["degradations"] = degradations
        return out

    monkeypatch.setattr(CP.seat_map, "build", _park_build)
    cal = _calibration_rows()
    claude_fail = _failed_probe_result("claude", "resultProduction", repo=repo)
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, claude=claude_fail)
    payload, code = CP.preflight_entry(
        repo,
        paths,
        launch_without=["claude"],
        owner_words=["proceed anyway"],
        calibration_rows=cal,
    )
    assert code == 0
    assert payload["engine-auth"]["state"] == "fail"
    assert "PARK" in payload["engine-auth"]["reason"]
    seats = payload.get("seatMap", {}).get("seats") or {}
    assert all(v.get("vendor") != "claude" for v in seats.values())


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
    cursor_fail = _failed_probe_result("cursor", "resultProduction", repo=repo)
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
    assert payload2["legs"]["resultProduction"]["detail"] == "default: run-dir-reused"


def test_claude_probe_refuses_reused_background_before_any_mode_dispatches(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    seed_run = tmp_path / "seed-run"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "print").mkdir()
    structured = {"result": _native_verdicts_branch()}
    print_stdout = _claude_event_stream(tool_calls=1, structured_output=structured)
    background_lines = [
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "tool-0", "name": "Glob", "input": {},
            }]},
        }),
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "so1", "name": "StructuredOutput",
                "input": {"result": _native_verdicts_branch()},
            }]},
        }),
        json.dumps({"type": "user", "toolEndsTurn": True}),
    ]
    background_stdout = "\n".join(background_lines) + "\n"

    def print_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return print_stdout, False, 0, ""

    def background_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return background_stdout, False, 0, ""

    seed = FakeRunner([print_runner, background_runner], sync_native=False)
    payload1, code1, _ = CP.probe(
        "claude", repo_root=repo, run_dir=str(seed_run), timeout=30, run_engine=seed,
        build_view=_fake_build_view(tmp_path),
    )
    assert code1 == 0
    shutil.copytree(seed_run / "background", run_dir / "background")
    fake = FakeRunner([(print_stdout, False, 0, "")])
    payload2, code2, _ = CP.probe(
        "claude", repo_root=repo, run_dir=str(run_dir), timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert len(fake.calls) == 0
    assert code2 == 1
    assert payload2["modeLegs"]["print"]["resultProduction"]["detail"] == "run-dir-reused"
    assert payload2["modeLegs"]["background"]["resultProduction"]["detail"] == "run-dir-reused"


def test_probe_run_dir_setup_failure_never_raises(tmp_path, monkeypatch):
    repo = _repo(tmp_path)

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(CP.tempfile, "mkdtemp", _boom)
    payload, code, stderr = CP.probe("codex", repo_root=repo)
    assert code == 1
    assert payload["legs"]["resultProduction"]["detail"] == "default: run-dir-setup-failed:OSError"
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
    paths = _ok_dispatchable_probe_paths(tmp_path, repo)
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(),
    )
    assert code == 0
    assert payload["waveBinding"] == "none"


def test_preflight_entry_refuses_wave_mismatch(tmp_path):
    repo = _repo(tmp_path)
    wave_kw = {"wave": "wave-a"}
    paths = _ok_dispatchable_probe_paths(
        tmp_path, repo, codex=wave_kw, cursor=wave_kw, claude=wave_kw,
    )
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), wave="wave-b",
    )
    assert code == 1
    assert payload["reason"].startswith("probe-wave-mismatch:")


def test_preflight_entry_refuses_ok_disagreeing_with_legs(tmp_path):
    repo = _repo(tmp_path)
    codex = _failed_probe_result("codex", "resultProduction", repo=repo)
    codex["ok"] = True
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
    paths = _ok_dispatchable_probe_paths(tmp_path, repo)
    codex_data = json.loads((tmp_path / "probe-codex.json").read_text(encoding="utf-8"))
    assert "wave" not in codex_data
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), wave="wave-a",
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
    age_kw = {"completedAt": completed_iso}
    paths = _ok_dispatchable_probe_paths(
        tmp_path, repo, codex=age_kw, cursor=age_kw, claude=age_kw,
    )
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 0


def test_preflight_entry_stale_boundary_one_past_refuses(tmp_path, monkeypatch):
    """axis: age == max_age_seconds + 1 refuses probe-stale (the bound is >, pinned one past)."""
    repo = _repo(tmp_path)
    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(CP, "_now_utc", lambda: now)
    completed = (now - timedelta(seconds=3601)).replace(microsecond=0)
    completed_iso = completed.isoformat().replace("+00:00", "Z")
    healthy = (now - timedelta(seconds=1800)).replace(microsecond=0)
    healthy_iso = healthy.isoformat().replace("+00:00", "Z")
    paths = _ok_dispatchable_probe_paths(
        tmp_path, repo,
        codex={"completedAt": completed_iso},
        cursor={"completedAt": healthy_iso},
        claude={"completedAt": healthy_iso},
    )
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 1
    assert payload["reason"] == "probe-stale:codex"


def test_preflight_entry_stale_boundary_future_completed_at_refuses(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(CP, "_now_utc", lambda: now)
    completed = (now + timedelta(seconds=60)).replace(microsecond=0)
    completed_iso = completed.isoformat().replace("+00:00", "Z")
    healthy = (now - timedelta(seconds=1800)).replace(microsecond=0)
    healthy_iso = healthy.isoformat().replace("+00:00", "Z")
    paths = _ok_dispatchable_probe_paths(
        tmp_path, repo,
        codex={"completedAt": completed_iso},
        cursor={"completedAt": healthy_iso},
        claude={"completedAt": healthy_iso},
    )
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), max_age_seconds=3600,
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
    paths = _ok_dispatchable_probe_paths(
        tmp_path, repo, codex={"completedAt": completed_at},
    )
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(), max_age_seconds=3600,
    )
    assert code == 1
    if expect.endswith(":"):
        assert payload["reason"].startswith(expect)
    else:
        assert payload["reason"] == expect


def test_preflight_entry_refuses_probe_cell_mismatch(tmp_path):
    repo = _repo(tmp_path)
    paths = _ok_dispatchable_probe_paths(
        tmp_path, repo, codex={"probedCell": ["codex", "wrong-model", None]},
    )
    payload, code = CP.preflight_entry(
        repo, paths, calibration_rows=_calibration_rows(),
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
    codex_fail = _failed_probe_result("codex", "resultProduction", repo=repo)
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, codex=codex_fail)
    cal = [{"role": "implementer", "engine": "codex"}]
    payload, code = CP.preflight_entry(
        repo, paths,
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
    codex_fail = _failed_probe_result("codex", "resultProduction", repo=repo)
    paths = _ok_dispatchable_probe_paths(tmp_path, repo, codex=codex_fail)
    payload, code = CP.preflight_entry(
        repo, paths,
        launch_without=["codex"], owner_words=["proceed"],
        calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "seat-map-failed:RuntimeError"


def test_preflight_entry_refuses_blank_owner_word_and_unfailed_engine(tmp_path):
    repo = _repo(tmp_path)
    paths = _ok_dispatchable_probe_paths(tmp_path, repo)
    payload, code = CP.preflight_entry(
        repo, paths,
        launch_without=["codex"], owner_words=["  "],
        calibration_rows=_calibration_rows(),
    )
    assert code == 1
    assert payload["reason"] == "owner-word-blank"
    payload2, code2 = CP.preflight_entry(
        repo, paths,
        launch_without=["cursor"], owner_words=["word"],
        calibration_rows=_calibration_rows(),
    )
    assert code2 == 1
    assert payload2["reason"] == "launch-without-not-failed:cursor"


def test_codex_probe_record_has_default_mode_legs(tmp_path):
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
    assert payload["probedModes"] == ["default"]
    assert set(payload["modeLegs"]) == {"default"}
    assert payload["modeLegs"]["default"]["resultProduction"]["ok"] is True


def test_derive_flat_legs_mode_failure_propagates_to_flat_view():
    mode_legs = {
        "print": _ok_legs(),
        "background": _ok_legs(),
    }
    mode_legs["background"]["progressTelemetry"] = {
        "ok": False, "detail": "telemetry-absent", "evidence": {},
    }
    flat = CP._derive_flat_legs(mode_legs)
    assert flat["resultProduction"]["ok"] is True
    assert flat["progressTelemetry"]["ok"] is False
    assert flat["progressTelemetry"]["detail"] == "background: telemetry-absent"


def test_validate_probe_record_refuses_empty_mode_legs():
    raw = _probe_result("codex")
    raw["modeLegs"] = {}
    err = CP._validate_probe_record(raw, "/tmp/codex.json")
    assert err == "probe-result-malformed:/tmp/codex.json"


def test_validate_probe_record_refuses_probed_modes_mode_legs_key_mismatch():
    raw = _probe_result("claude")
    raw["probedModes"] = ["print"]
    err = CP._validate_probe_record(raw, "/tmp/claude.json")
    assert err == "probe-result-malformed:/tmp/claude.json"


def test_payload_writer_probed_modes_matches_mode_legs_keys():
    seat = _claude_seat()
    mode_legs = {"print": _ok_legs(), "background": _ok_legs()}
    payload = CP._payload(
        "claude", ERC.channel_for("claude"), seat, "/repo",
        "2026-09-20T00:00:00Z", "2026-09-20T00:00:01Z", 1.0, "/tmp/run",
        mode_legs, ["print", "background"], [], "lanes",
    )
    assert CP._validate_probe_record(payload, "/tmp/claude.json") is None


def test_validate_probe_record_refuses_mode_legs_incomplete_leg_map():
    raw = _probe_result("claude")
    raw["modeLegs"]["print"].pop("progressTelemetry")
    err = CP._validate_probe_record(raw, "/tmp/claude.json")
    assert err == "probe-result-malformed:/tmp/claude.json"


def test_payload_writer_mode_legs_carry_all_leg_names():
    seat = _claude_seat()
    mode_legs = {"print": _ok_legs(), "background": _ok_legs()}
    payload = CP._payload(
        "claude", ERC.channel_for("claude"), seat, "/repo",
        "2026-09-20T00:00:00Z", "2026-09-20T00:00:01Z", 1.0, "/tmp/run",
        mode_legs, ["print", "background"], [], "lanes",
    )
    for mode in ("print", "background"):
        assert set(payload["modeLegs"][mode].keys()) == set(CP._LEG_NAMES)
    assert CP._validate_probe_record(payload, "/tmp/claude.json") is None


def test_validate_probe_record_refuses_non_claude_wrong_mode_keys():
    raw = _probe_result("codex")
    raw["probedModes"] = ["print"]
    raw["modeLegs"] = {"print": _ok_legs()}
    err = CP._validate_probe_record(raw, "/tmp/codex.json")
    assert err == "probe-result-malformed:/tmp/codex.json"


def test_validate_probe_record_refuses_flat_legs_disagreeing_with_mode_legs():
    raw = _probe_result("claude")
    raw["modeLegs"]["background"]["resultProduction"] = {
        "ok": False, "detail": "native-result-missing", "evidence": {},
    }
    # flat legs left claiming ok, ok/failed kept self-consistent so only the
    # modeLegs-vs-legs cross-check can fire
    assert raw["legs"]["resultProduction"]["ok"] is True
    err = CP._validate_probe_record(raw, "/tmp/claude.json")
    assert err == "probe-result-malformed:/tmp/claude.json"


def test_derive_flat_legs_records_failing_modes_in_evidence():
    mode_legs = {"print": _ok_legs(), "background": _ok_legs()}
    mode_legs["background"]["resultProduction"] = {
        "ok": False, "detail": "native-result-missing", "evidence": {},
    }
    flat = CP._derive_flat_legs(mode_legs)
    assert flat["resultProduction"]["evidence"]["failingModes"] == ["background"]


def test_stamp_mode_run_dir_records_run_dir_per_leg():
    stamped = CP._stamp_mode_run_dir(_ok_legs(), "/tmp/run/background")
    for name in CP._LEG_NAMES:
        assert stamped[name]["evidence"]["runDir"] == "/tmp/run/background"


def test_preflight_entry_refuses_schema_v1_record(tmp_path):
    repo = _repo(tmp_path)
    codex = _probe_result("codex", repoRoot=repo)
    codex["schema"] = "conformance-probe/1"
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


def test_claude_probe_second_mode_runs_when_first_refuses(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    def refuse_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return "", False, 127, "spawn-failed"

    structured = {"result": _native_verdicts_branch()}
    stdout = _claude_event_stream(tool_calls=1, structured_output=structured)

    def ok_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return stdout, False, 0, ""

    fake = FakeRunner(
        [refuse_runner, refuse_runner, ok_runner, ok_runner], sync_native=False,
    )
    payload, code, _stderr = CP.probe(
        "claude", repo_root=repo, run_dir=run_dir, timeout=30, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert len(fake.calls) >= 2
    assert payload["probedModes"] == ["print", "background"]
    assert payload["modeLegs"]["print"]["completionDetection"]["ok"] is False
    assert payload["modeLegs"]["print"]["completionDetection"]["detail"] == "auth-or-config-refusal"
    assert payload["modeLegs"]["background"]["completionDetection"]["ok"] is True
    assert payload["modeLegs"]["background"]["resultProduction"]["ok"] is False
    assert payload["modeLegs"]["background"]["resultProduction"]["detail"] == "native-result-missing"


DO = _load("dispatch_outcome", "dispatch_outcome.py")

_COMPLETION_BOUNDARY_CELLS = (
    ("codex", "default"),
    ("cursor", "default"),
    ("claude", "print"),
    ("claude", "background"),
)
_DEADLINE_MONO = 100.0
_BEFORE_CAP_AT = 50.0
_AFTER_CAP_AT = 101.0
_AT_CAP_AT = 100.0


def _native_review_envelope():
    return {"result": _native_verdicts_branch()}


def _envelope_digest(envelope):
    scrubbed = ED._scrub_native_payload(envelope)
    return ERC.canonical_payload_digest(scrubbed)


def _claude_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


def _patch_journal_completion_stamps(
        monkeypatch, envelope, *, complete_at, deadline_mono=None, timed_out=False,
        omit_completion=False, wrong_epoch=False):
    # probe() calls engine_dispatch imported by conformance_probe, not the test's ED copy.
    real_append = CP.engine_dispatch._journal_append
    digest = _envelope_digest(envelope)

    def patched_append(run_dir, record):
        if isinstance(record, dict) and record.get("kind") == "attempt-ended":
            record = dict(record)
            for key in (
                ERC.FIELD_RESULT_COMPLETE_AT,
                ERC.FIELD_RESULT_COMPLETE_EPOCH,
                ERC.FIELD_RESULT_COMPLETE_SHA256,
                ERC.FIELD_DEADLINE_MONO,
                ERC.FIELD_DEADLINE_EPOCH,
            ):
                record.pop(key, None)
            record["timedOut"] = timed_out
            if timed_out:
                record["timeoutAt"] = record.get("at", time.time())
            if not omit_completion and digest:
                stamp = ERC.completion_stamp(complete_at, digest)
                if stamp:
                    if wrong_epoch:
                        stamp = dict(stamp)
                        stamp[ERC.FIELD_RESULT_COMPLETE_EPOCH] = "wrong-epoch"
                    record.update(stamp)
            if deadline_mono is not None:
                dl = ERC.deadline_stamp(deadline_mono)
                if dl:
                    record.update(dl)
        return real_append(run_dir, record)

    monkeypatch.setattr(CP.engine_dispatch, "_journal_append", patched_append)


def _codex_boundary_runner(envelope):
    stdout = _codex_event_stream(action_items=2)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        if "-o" in argv:
            result_path = argv[argv.index("-o") + 1]
        else:
            result_path = ERC.result_file_path_from_prompt(
                prompt_bytes.decode("utf-8", "ignore"))
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, separators=(",", ":"))
            fh.write("\n")
        return stdout, False, 0, ""

    return runner


def _cursor_boundary_runner(envelope):
    stdout = _cursor_event_stream(tool_calls=2)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        result_path = ERC.result_file_path_from_prompt(
            prompt_bytes.decode("utf-8", "ignore"))
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, separators=(",", ":"))
            fh.write("\n")
        return stdout, False, 0, ""

    return runner


def _claude_print_boundary_runner(envelope):
    structured = {"result": envelope["result"]}
    stdout = _claude_event_stream(tool_calls=1, structured_output=structured)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return stdout, False, 0, ""

    return runner


def _claude_background_boundary_runner(envelope):
    background_lines = [
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "tool-0", "name": "Glob", "input": {},
            }]},
        }),
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "so1", "name": "StructuredOutput",
                "input": {"result": envelope["result"]},
            }]},
        }),
        json.dumps({"type": "user", "toolEndsTurn": True}),
    ]
    stdout = "\n".join(background_lines) + "\n"

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        return stdout, False, 0, ""

    return runner


def _boundary_run_engine(engine, envelope):
    if engine == "codex":
        return _codex_boundary_runner(envelope)
    if engine == "cursor":
        return _cursor_boundary_runner(envelope)
    print_runner = _claude_print_boundary_runner(envelope)
    background_runner = _claude_background_boundary_runner(envelope)

    def claude_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        if "--bg" in argv:
            return background_runner(argv, prompt_bytes, timeout, progress_cb, cwd)
        return print_runner(argv, prompt_bytes, timeout, progress_cb, cwd)

    return claude_runner


def _claude_green_run_engine(envelope):
    structured = {"result": envelope["result"]}
    print_stdout = _claude_event_stream(tool_calls=1, structured_output=structured)
    background_lines = [
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "tool-0", "name": "Glob", "input": {},
            }]},
        }),
        json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "id": "so1", "name": "StructuredOutput",
                "input": {"result": envelope["result"]},
            }]},
        }),
        json.dumps({"type": "user", "toolEndsTurn": True}),
    ]
    background_stdout = "\n".join(background_lines) + "\n"
    print_runner = _claude_print_boundary_runner(envelope)
    background_runner = _claude_background_boundary_runner(envelope)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        if "--bg" in argv:
            return background_runner(argv, prompt_bytes, timeout, progress_cb, cwd)
        return print_runner(argv, prompt_bytes, timeout, progress_cb, cwd)

    return runner


def _run_probe_completion_boundary(
        tmp_path, monkeypatch, engine, mode, envelope, stamp_kw, *,
        claude_home=False):
    if claude_home or engine == "claude":
        _claude_home(monkeypatch, tmp_path)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    _patch_journal_completion_stamps(monkeypatch, envelope, **stamp_kw)
    runner = _boundary_run_engine(engine, envelope)
    return CP.probe(
        engine, repo_root=repo, run_dir=run_dir, timeout=30, run_engine=runner,
        build_view=_fake_build_view(tmp_path),
    )


@pytest.mark.parametrize("engine,mode", _COMPLETION_BOUNDARY_CELLS)
def test_probe_completion_before_cap_admits(tmp_path, monkeypatch, engine, mode):
    # axis: completion observed before deadline → native result admitted
    envelope = _native_review_envelope()
    payload, code, _stderr = _run_probe_completion_boundary(
        tmp_path, monkeypatch, engine, mode, envelope,
        {
            "complete_at": _BEFORE_CAP_AT,
            "deadline_mono": _DEADLINE_MONO,
            "timed_out": False,
        },
        claude_home=(engine == "claude"),
    )
    leg = payload["modeLegs"][mode]["resultProduction"]
    assert leg["ok"] is True
    assert leg["detail"] != "result-completion-after-deadline"
    if engine != "claude":
        assert code == 0


@pytest.mark.parametrize("engine,mode", _COMPLETION_BOUNDARY_CELLS)
def test_probe_completion_after_cap_forfeits(tmp_path, monkeypatch, engine, mode):
    # axis: completion after deadline → result-completion-after-deadline forfeit
    envelope = _native_review_envelope()
    payload, code, _stderr = _run_probe_completion_boundary(
        tmp_path, monkeypatch, engine, mode, envelope,
        {
            "complete_at": _AFTER_CAP_AT,
            "deadline_mono": _DEADLINE_MONO,
            "timed_out": False,
        },
        claude_home=(engine == "claude"),
    )
    leg = payload["modeLegs"][mode]["resultProduction"]
    assert leg["ok"] is False
    assert leg["detail"] == "result-completion-after-deadline"
    assert code == 1


def _seed_claude_mode_journal(tmp_path, monkeypatch, reused_mode):
    _claude_home(monkeypatch, tmp_path)
    repo = _repo(tmp_path)
    seed_run = str(tmp_path / "seed-run")
    envelope = _native_review_envelope()
    payload, code, _ = CP.probe(
        "claude", repo_root=repo, run_dir=seed_run, timeout=30,
        run_engine=_claude_green_run_engine(envelope),
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    return seed_run


def _claude_preflight_parent(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "print").mkdir()
    (run_dir / "background").mkdir()
    return run_dir


def test_probe_preflight_aborts_all_modes_when_one_mode_reused(tmp_path, monkeypatch):
    # axis: reused mode in preflight → no dispatch for any mode
    seed_run = _seed_claude_mode_journal(tmp_path, monkeypatch, "print")
    run_dir = _claude_preflight_parent(tmp_path)
    shutil.copytree(os.path.join(seed_run, "print"), run_dir / "print", dirs_exist_ok=True)
    calls = []

    def recording_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        calls.append({"argv": list(argv), "cwd": cwd})
        return "", False, 0, ""

    payload, code, _stderr = CP.probe(
        "claude", repo_root=_repo(tmp_path), run_dir=str(run_dir), timeout=30,
        run_engine=recording_runner, build_view=_fake_build_view(tmp_path),
    )
    assert len(calls) == 0
    assert code == 1
    for mode in CP._modes_for_engine("claude"):
        detail = payload["modeLegs"][mode]["resultProduction"]["detail"]
        assert detail == DO.DETAIL_RUN_DIR_REUSED


def test_probe_preflight_aborts_when_print_mode_reused_first_in_order(tmp_path, monkeypatch):
    # axis: edge 6 — reused first mode (print) blocks background dispatch
    seed_run = _seed_claude_mode_journal(tmp_path, monkeypatch, "print")
    run_dir = _claude_preflight_parent(tmp_path)
    shutil.copytree(os.path.join(seed_run, "print"), run_dir / "print", dirs_exist_ok=True)
    calls = []

    def recording_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        calls.append(1)
        return "", False, 0, ""

    payload, code, _ = CP.probe(
        "claude", repo_root=_repo(tmp_path), run_dir=str(run_dir), timeout=30,
        run_engine=recording_runner, build_view=_fake_build_view(tmp_path),
    )
    assert CP._modes_for_engine("claude")[0] == "print"
    assert len(calls) == 0
    assert code == 1
    assert payload["modeLegs"]["background"]["resultProduction"]["detail"] == DO.DETAIL_RUN_DIR_REUSED


def test_probe_preflight_aborts_when_background_mode_reused_second_in_order(tmp_path, monkeypatch):
    # axis: edge 6 — reused second mode (background) blocks print dispatch
    seed_run = _seed_claude_mode_journal(tmp_path, monkeypatch, "background")
    run_dir = _claude_preflight_parent(tmp_path)
    shutil.copytree(os.path.join(seed_run, "background"), run_dir / "background", dirs_exist_ok=True)
    calls = []

    def recording_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        calls.append(1)
        return "", False, 0, ""

    payload, code, _ = CP.probe(
        "claude", repo_root=_repo(tmp_path), run_dir=str(run_dir), timeout=30,
        run_engine=recording_runner, build_view=_fake_build_view(tmp_path),
    )
    assert CP._modes_for_engine("claude")[1] == "background"
    assert len(calls) == 0
    assert code == 1
    assert payload["modeLegs"]["print"]["resultProduction"]["detail"] == DO.DETAIL_RUN_DIR_REUSED


def test_probe_preflight_aborts_all_modes_on_setup_error(tmp_path, monkeypatch):
    # axis: setup_error in one mode → no dispatch for any mode
    _claude_home(monkeypatch, tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "print").write_text("not-a-directory", encoding="utf-8")
    (run_dir / "background").mkdir()
    calls = []

    def recording_runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        calls.append(1)
        return "", False, 0, ""

    payload, code, _stderr = CP.probe(
        "claude", repo_root=_repo(tmp_path), run_dir=str(run_dir), timeout=30,
        run_engine=recording_runner, build_view=_fake_build_view(tmp_path),
    )
    assert len(calls) == 0
    assert code == 1
    for mode in CP._modes_for_engine("claude"):
        detail = payload["modeLegs"][mode]["resultProduction"]["detail"]
        assert detail == "run-dir-not-a-directory" or detail.startswith("run-dir-setup-failed:")


def test_probe_successful_cell_journal_carries_completion_stamp(tmp_path, monkeypatch):
    # axis: R10 — successful probe cell stamps completion on attempt-ended
    envelope = _native_review_envelope()
    _patch_journal_completion_stamps(
        monkeypatch, envelope,
        complete_at=_BEFORE_CAP_AT,
        deadline_mono=_DEADLINE_MONO,
        timed_out=False,
    )
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    payload, code, _stderr = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30,
        run_engine=_codex_boundary_runner(envelope),
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 0
    mode_run_dir = payload["modeLegs"]["default"]["resultProduction"]["evidence"]["runDir"]
    records, _ = ED._journal_read(mode_run_dir)
    ended = next(r for r in records if r.get("kind") == "attempt-ended")
    assert ERC.FIELD_RESULT_COMPLETE_AT in ended
    assert ERC.FIELD_RESULT_COMPLETE_EPOCH in ended
    assert ERC.FIELD_RESULT_COMPLETE_SHA256 in ended
    assert ERC.FIELD_DEADLINE_EPOCH in ended
    assert ended[ERC.FIELD_DEADLINE_EPOCH] == ended[ERC.FIELD_RESULT_COMPLETE_EPOCH]


def test_probe_completion_without_deadline_admits(tmp_path, monkeypatch):
    # axis: edge 1 — completion stamp with no deadline on a clean run
    envelope = _native_review_envelope()
    payload, code, _ = _run_probe_completion_boundary(
        tmp_path, monkeypatch, "codex", "default", envelope,
        {"complete_at": _BEFORE_CAP_AT, "timed_out": False},
    )
    assert code == 0
    assert payload["modeLegs"]["default"]["resultProduction"]["ok"] is True


def test_probe_completion_with_deadline_but_no_stamp_forfeits(tmp_path, monkeypatch):
    # axis: edge 2 — deadline present, completion stamp omitted
    envelope = _native_review_envelope()
    payload, code, _ = _run_probe_completion_boundary(
        tmp_path, monkeypatch, "codex", "default", envelope,
        {
            "complete_at": _BEFORE_CAP_AT,
            "deadline_mono": _DEADLINE_MONO,
            "timed_out": False,
            "omit_completion": True,
        },
    )
    assert code == 1
    assert payload["modeLegs"]["default"]["resultProduction"]["detail"] == (
        "result-completion-unrecorded"
    )


def test_probe_completion_epoch_mismatch_forfeits(tmp_path, monkeypatch):
    # axis: edge 3 — completion and deadline epochs differ
    envelope = _native_review_envelope()
    payload, code, _ = _run_probe_completion_boundary(
        tmp_path, monkeypatch, "codex", "default", envelope,
        {
            "complete_at": _BEFORE_CAP_AT,
            "deadline_mono": _DEADLINE_MONO,
            "timed_out": False,
            "wrong_epoch": True,
        },
    )
    assert code == 1
    assert payload["modeLegs"]["default"]["resultProduction"]["detail"] == (
        "result-completion-unrecorded"
    )


def test_probe_completion_exactly_at_cap_admits(tmp_path, monkeypatch):
    # axis: edge 4 — resultCompleteAt exactly equal to deadlineMono admits
    envelope = _native_review_envelope()
    payload, code, _ = _run_probe_completion_boundary(
        tmp_path, monkeypatch, "codex", "default", envelope,
        {
            "complete_at": _AT_CAP_AT,
            "deadline_mono": _DEADLINE_MONO,
            "timed_out": False,
        },
    )
    assert code == 0
    assert payload["modeLegs"]["default"]["resultProduction"]["ok"] is True


def _astra_ledger(tmp_path, monkeypatch):
    ledger_dir = str(tmp_path / "ledger")
    os.makedirs(ledger_dir, exist_ok=True)

    def _fake_record_dir(repo_root, env=None):
        return ledger_dir, None

    monkeypatch.setattr(CP, "_conformance_record_dir", _fake_record_dir)
    return ledger_dir


def _astra_terminal_findings(findings, **overrides):
    base = {
        "ok": True,
        "terminal": True,
        "findings": findings,
        "reason": None,
    }
    base.update(overrides)
    return base


def _astra_pass_finding(**overrides):
    finding = {
        "file": "b/app/session_guard.py",
        "line": 25,
        "severity": "Critical",
        "title": "auth bypass on token decode failure",
        "body": "continues with admin role",
    }
    finding.update(overrides)
    return finding


def test_astra_probe_pass_matches_plant_and_records_attempt(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    calls = []

    def dispatch(**kwargs):
        calls.append(kwargs)
        return _astra_terminal_findings([_astra_pass_finding()])

    out, code = CP.astra_probe(
        repo, "wave-pass", run_dir, dispatch=dispatch,
    )
    assert code == 0
    assert out["ok"] is True
    assert out["outcome"] == "pass"
    assert out["matched"]["line"] == 25
    assert out["matched"]["severity"] == "Critical"
    ledger_dir, _ = CP._conformance_record_dir(repo)
    attempts = CP._read_astra_attempts(ledger_dir)
    assert len(attempts) == 1
    assert attempts[0]["wave"] == "wave-pass"
    assert calls[0]["seat"] == CP.ASTRA_PROBE_SEAT


def test_astra_probe_miss_wrong_severity(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)

    def dispatch(**_kwargs):
        return _astra_terminal_findings([_astra_pass_finding(severity="Important")])

    out, code = CP.astra_probe(repo, "wave-sev", run_dir, dispatch=dispatch)
    assert code == 1
    assert out["outcome"] == "miss"
    assert out["matched"] is None


def test_astra_probe_miss_unrelated_finding(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)

    def dispatch(**_kwargs):
        return _astra_terminal_findings([{
            "file": "other.py", "line": 1, "severity": "Critical",
            "title": "x", "body": "y",
        }])

    out, code = CP.astra_probe(repo, "wave-unrel", run_dir, dispatch=dispatch)
    assert code == 1
    assert out["outcome"] == "miss"
    assert out["matched"] is None


def test_astra_probe_miss_refusal(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)

    def dispatch(**_kwargs):
        return {"ok": False, "terminal": True, "reason": "refused", "findings": None}

    out, code = CP.astra_probe(repo, "wave-ref", run_dir, dispatch=dispatch)
    assert code == 1
    assert out["outcome"] == "miss"
    assert out["dispatchReason"] == "refused"


def test_astra_probe_miss_empty_findings(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)

    def dispatch(**_kwargs):
        return _astra_terminal_findings([])

    out, code = CP.astra_probe(repo, "wave-empty", run_dir, dispatch=dispatch)
    assert code == 1
    assert out["outcome"] == "miss"
    assert out["returned"] == []


def test_astra_probe_fixture_has_no_hint_words():
    text = CP.ASTRA_PROBE_FIXTURE.lower()
    for word in ("planted", "fail-open", "bypass", "vulnerability"):
        assert word not in text


# bite-axis: the prompt names every severity the grader can pass on, so the one passing answer is never steered away
def test_astra_probe_fixture_states_the_full_severity_scale():
    fixture = CP.ASTRA_PROBE_FIXTURE
    for level in ("Critical", "Important", "Minor", "Nit"):
        assert level in fixture
    assert CP.PLANT_SEVERITY in ("Critical", "Important", "Minor", "Nit")


def test_astra_probe_fixture_plant_lines_are_second_hunk_plus_lines():
    lines = CP.ASTRA_PROBE_DIFF.splitlines()
    plus_lines = [ln[1:] for ln in lines if ln.startswith("+") and not ln.startswith("+++")]
    assert len(plus_lines) >= 2
    assert plus_lines[-2].strip() == 'log.warning("token decode failed; continuing")'
    assert plus_lines[-1].strip() == 'claims = {"role": "admin"}'


def test_astra_probe_refuses_second_run_dir_same_wave(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run1 = str(tmp_path / "run1")
    run2 = str(tmp_path / "run2")
    os.makedirs(run1)
    os.makedirs(run2)
    calls = []

    def dispatch(**_kwargs):
        calls.append(1)
        return _astra_terminal_findings([_astra_pass_finding()])

    CP.astra_probe(repo, "wave-dup", run1, dispatch=dispatch)
    out, code = CP.astra_probe(repo, "wave-dup", run2, dispatch=dispatch)
    assert code == 1
    assert out["reason"] == "astra-probe-wave-already-attempted"
    assert len(calls) == 1


def test_astra_probe_continuation_redispatches_without_duplicate_record(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    calls = []

    def dispatch(**_kwargs):
        calls.append(1)
        if len(calls) == 1:
            return {"ok": False, "terminal": False, "findings": None}
        return _astra_terminal_findings([_astra_pass_finding()])

    out1, code1 = CP.astra_probe(repo, "wave-cont", run_dir, dispatch=dispatch)
    assert code1 == 0
    assert out1.get("continue") is True
    out2, code2 = CP.astra_probe(repo, "wave-cont", run_dir, dispatch=dispatch)
    assert code2 == 0
    assert out2["outcome"] == "pass"
    assert len(calls) == 2
    ledger_dir, _ = CP._conformance_record_dir(repo)
    assert len(CP._read_astra_attempts(ledger_dir)) == 1
    out3, code3 = CP.astra_probe(repo, "wave-cont", run_dir, dispatch=dispatch)
    assert code3 == 0
    assert out3 == out2
    assert len(calls) == 2


def test_astra_probe_owner_proposal_on_third_miss(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    waves = ("wave-m1", "wave-m2", "wave-m3")

    def dispatch(**_kwargs):
        return _astra_terminal_findings([])

    for wave in waves:
        run_dir = str(tmp_path / wave)
        os.makedirs(run_dir)
        out, code = CP.astra_probe(repo, wave, run_dir, dispatch=dispatch)
        assert code == 1
        if wave == "wave-m3":
            assert out["ownerProposal"] is True
            assert out["misses"] == 3
        else:
            assert out["ownerProposal"] is False


def test_astra_probe_orphan_claim_recorded_as_miss(tmp_path, monkeypatch):
    ledger_dir = _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    old_wave = "wave-orphan"
    old_run = str(tmp_path / "orphan-run")
    os.makedirs(old_run)
    CP._write_astra_claim(ledger_dir, old_wave, old_run)
    new_run = str(tmp_path / "new-run")
    os.makedirs(new_run)

    def dispatch(**_kwargs):
        return _astra_terminal_findings([_astra_pass_finding()])

    out, code = CP.astra_probe(repo, "wave-new", new_run, dispatch=dispatch)
    assert code == 0
    attempts = CP._read_astra_attempts(ledger_dir)
    orphan = next(a for a in attempts if a.get("wave") == old_wave)
    assert orphan["outcome"] == "incomplete"
    assert out["outcome"] == "pass"


def test_astra_probe_miss_string_line_not_matched(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)

    def dispatch(**_kwargs):
        return _astra_terminal_findings([_astra_pass_finding(line="25")])

    out, code = CP.astra_probe(repo, "wave-str", run_dir, dispatch=dispatch)
    assert code == 1
    assert out["matched"] is None


def test_astra_probe_empty_wave_refuses(tmp_path, monkeypatch):
    _astra_ledger(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    calls = []

    def dispatch(**_kwargs):
        calls.append(1)
        return _astra_terminal_findings([])

    out, code = CP.astra_probe(repo, "  ", run_dir, dispatch=dispatch)
    assert code == 2
    assert out["reason"] == "wave-required"
    assert calls == []


def test_probe_completion_payload_mismatch_forfeits(tmp_path, monkeypatch):
    # axis: edge 5 — admitted payload differs from digest stamped on ended record
    stamped_envelope = _native_review_envelope()
    admitted_envelope = _native_review_envelope()
    admitted_envelope["result"] = dict(admitted_envelope["result"])
    admitted_envelope["result"]["reason"] = "rewritten-after-stamp"
    _patch_journal_completion_stamps(
        monkeypatch, stamped_envelope,
        complete_at=_BEFORE_CAP_AT,
        deadline_mono=_DEADLINE_MONO,
        timed_out=False,
    )
    repo = _repo(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    payload, code, _ = CP.probe(
        "codex", repo_root=repo, run_dir=run_dir, timeout=30,
        run_engine=_codex_boundary_runner(admitted_envelope),
        build_view=_fake_build_view(tmp_path),
    )
    assert code == 1
    assert payload["modeLegs"]["default"]["resultProduction"]["detail"] == (
        "result-completion-payload-mismatch"
    )
