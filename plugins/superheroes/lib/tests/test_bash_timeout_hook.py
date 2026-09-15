"""bash_timeout.py — the PreToolUse(Bash) timeout-floor hook (run-27-era courier kills).

Covers the pure decide() plus the process contract: the hook must be FAIL-OPEN (any
error -> no output, exit 0 — worst case is the pre-hook 120s default), must never touch
an explicit model-passed timeout, and must ride hooks.json's Bash matcher AFTER the
fail-closed enforcer entry (deny wins over a rewrite).
"""
import importlib.util
import json
import os
import subprocess

import pytest

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "bash_timeout.py")
_HOOKS_JSON = os.path.join(_PLUGIN, "hooks", "hooks.json")


def _mod():
    spec = importlib.util.spec_from_file_location("bash_timeout", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_hook(stdin_text):
    return subprocess.run(["python3", _HOOK], input=stdin_text,
                          capture_output=True, text=True, timeout=10)


@pytest.fixture(autouse=True)
def _isolate_claude_config_dir(tmp_path, monkeypatch):
    """The hook writes a durable firing record; a test run must never land in a real one."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))


# --- decide(): pure ---------------------------------------------------------

def test_decide_injects_floor_when_timeout_omitted():
    m = _mod()
    out = m.decide({"tool_input": {"command": "sleep 300 && echo ok"}})
    assert out == {"command": "sleep 300 && echo ok", "timeout": m.DEFAULT_TIMEOUT_MS}


def test_decide_never_touches_an_explicit_timeout():
    m = _mod()
    assert m.decide({"tool_input": {"command": "x", "timeout": 5000}}) is None
    # even one ABOVE the floor stays untouched — omission is the failure mode, not misjudgment
    assert m.decide({"tool_input": {"command": "x", "timeout": 900000}}) is None


def test_decide_treats_null_timeout_as_omitted():
    m = _mod()
    out = m.decide({"tool_input": {"command": "x", "timeout": None}})
    assert out is not None and out["timeout"] == m.DEFAULT_TIMEOUT_MS


def test_decide_noops_on_bad_shapes():
    m = _mod()
    assert m.decide(None) is None
    assert m.decide([]) is None
    assert m.decide({}) is None
    assert m.decide({"tool_input": "not a dict"}) is None


# --- process contract: fail-open, correct hook JSON --------------------------

def test_hook_emits_updated_input_for_omitted_timeout():
    r = _run_hook(json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": "python3 verify_gate.py --command 'pytest -q'"}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["updatedInput"]["timeout"] == _mod().DEFAULT_TIMEOUT_MS
    assert hso["updatedInput"]["command"] == "python3 verify_gate.py --command 'pytest -q'"
    assert "permissionDecision" not in hso  # rewrite-only: permission stays the enforcer's call


def test_hook_stays_silent_for_explicit_timeout():
    r = _run_hook(json.dumps({"tool_input": {"command": "x", "timeout": 30000}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_hook_fails_open_on_garbage_stdin():
    for garbage in ("", "not json {", "[1,2,3]"):
        r = _run_hook(garbage)
        assert r.returncode == 0, "fail-open: hook must exit 0 on %r" % garbage
        assert r.stdout.strip() == "", "fail-open: no output on %r" % garbage


# --- wiring ------------------------------------------------------------------

def test_hooks_json_wires_timeout_floor_fail_open():
    cfg = json.load(open(_HOOKS_JSON))
    bash_blocks = [h for h in cfg["hooks"]["PreToolUse"] if h["matcher"] == "Bash"]
    assert len(bash_blocks) == 1
    cmds = [h["command"] for h in bash_blocks[0]["hooks"]]
    idx = [i for i, c in enumerate(cmds) if "bash_timeout.py" in c]
    assert idx, "hooks.json must wire bash_timeout.py on the Bash matcher"
    assert "|| true" in cmds[idx[0]], "process-level fail-open: a hook crash never breaks Bash"


# --- firing record -----------------------------------------------------------

def _record_path(config_root):
    return os.path.join(config_root, "superheroes", "state", "bash-timeout-firings.jsonl")


def test_firing_record_isolated_without_explicit_config_dir(tmp_path):
    home = os.path.realpath(os.path.expanduser("~"))
    r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
    assert r.returncode == 0
    config_dir = os.environ["CLAUDE_CONFIG_DIR"]
    record = _record_path(config_dir)
    assert os.path.isfile(record)
    record_real = os.path.realpath(record)
    assert not record_real.startswith(home + os.sep) and record_real != home
    assert record_real.startswith(os.path.realpath(str(tmp_path)) + os.sep)


def test_firing_record_writes_one_json_line(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"},
                              "session_id": "sess-1", "cwd": "/work"}))
    assert r.returncode == 0
    record = _record_path(tmp_path)
    assert os.path.isfile(record)
    lines = open(record, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert set(entry) == {"ts", "timeout_ms", "session", "cwd"}
    assert entry["timeout_ms"] == _mod().DEFAULT_TIMEOUT_MS
    assert entry["ts"].endswith("Z")
    assert entry["session"] == "sess-1"
    assert entry["cwd"] == "/work"


def test_explicit_timeout_writes_no_firing_record(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    r = _run_hook(json.dumps({"tool_input": {"command": "x", "timeout": 30000}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert not os.path.exists(_record_path(tmp_path))


def test_firing_record_never_contains_command_text(tmp_path, monkeypatch):
    secret_marker = "DISTINCTIVE_SECRET_COMMAND_MARKER_XYZ"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    r = _run_hook(json.dumps({"tool_input": {"command": secret_marker}}))
    assert r.returncode == 0
    record_text = open(_record_path(tmp_path), encoding="utf-8").read()
    assert secret_marker not in record_text


def test_unwritable_record_location_does_not_affect_hook(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(blocker / "config"))
    r = _run_hook(json.dumps({"tool_input": {"command": "x"}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["updatedInput"]["timeout"] == _mod().DEFAULT_TIMEOUT_MS


def test_firing_record_rotates_when_past_size_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    record = _record_path(tmp_path)
    os.makedirs(os.path.dirname(record), exist_ok=True)
    threshold = _mod()._RECORD_ROTATE_BYTES
    open(record, "wb").write(b"x" * (threshold + 1))
    r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
    assert r.returncode == 0
    assert os.path.isfile(record + ".1")
    lines = open(record, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    json.loads(lines[0])


def test_firing_record_rotation_replaces_prior_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    record = _record_path(tmp_path)
    os.makedirs(os.path.dirname(record), exist_ok=True)
    threshold = _mod()._RECORD_ROTATE_BYTES
    for _ in range(2):
        open(record, "wb").write(b"x" * (threshold + 1))
        r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
        assert r.returncode == 0
    state_dir = os.path.dirname(record)
    assert sorted(os.listdir(state_dir)) == [
        "bash-timeout-firings.jsonl",
        "bash-timeout-firings.jsonl.1",
    ]
