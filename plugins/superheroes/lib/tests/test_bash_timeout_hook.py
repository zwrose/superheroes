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
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    monkeypatch.delenv("BASH_DEFAULT_TIMEOUT_MS", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))


# --- decide(): pure ---------------------------------------------------------

def test_decide_injects_floor_when_timeout_omitted():
    m = _mod()
    out = m.decide({"tool_input": {"command": "sleep 300 && echo ok"}}, {})
    assert out == ("rewrite", {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": {"command": "sleep 300 && echo ok", "timeout": m.DEFAULT_TIMEOUT_MS}}})


def test_decide_never_touches_an_explicit_timeout():
    m = _mod()
    assert m.decide({"tool_input": {"command": "x", "timeout": 5000}}, {}) is None
    # even one ABOVE the floor stays untouched — omission is the failure mode, not misjudgment
    assert m.decide({"tool_input": {"command": "x", "timeout": 900000}}, {}) is None


def test_decide_treats_null_timeout_as_omitted():
    m = _mod()
    out = m.decide({"tool_input": {"command": "x", "timeout": None}}, {})
    assert out is not None
    branch, hook_output = out
    assert branch == "rewrite"
    assert hook_output["hookSpecificOutput"]["updatedInput"]["timeout"] == m.DEFAULT_TIMEOUT_MS


def test_decide_noops_on_bad_shapes():
    m = _mod()
    assert m.decide(None, {}) is None
    assert m.decide([], {}) is None
    assert m.decide({}, {}) is None
    assert m.decide({"tool_input": "not a dict"}, {}) is None


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


def _store_record_path(store_root):
    return os.path.join(store_root, "state", "bash-timeout-firings.jsonl")


def test_firing_record_isolated_when_test_sets_nothing(tmp_path):
    home = os.path.realpath(os.path.expanduser("~"))
    r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
    assert r.returncode == 0
    config_dir = os.environ["CLAUDE_CONFIG_DIR"]
    record = _record_path(config_dir)
    assert os.path.isfile(record)
    record_real = os.path.realpath(record)
    assert not record_real.startswith(home + os.sep) and record_real != home
    assert record_real.startswith(os.path.realpath(str(tmp_path)) + os.sep)


def test_firing_record_uses_default_root_when_env_unset(tmp_path, monkeypatch):
    for var in ("SUPERHEROES_STORE_ROOT", "WORKHORSE_STORE_ROOT", "CLAUDE_CONFIG_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
    assert r.returncode == 0
    record = _record_path(os.path.expanduser("~/.claude"))
    assert os.path.isfile(record)


def test_superheroes_store_root_wins_over_claude_config_dir(tmp_path, monkeypatch):
    store_root = tmp_path / "store"
    config_dir = tmp_path / "config"
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(store_root))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
    assert r.returncode == 0
    assert os.path.isfile(_store_record_path(store_root))
    assert not os.path.exists(_record_path(config_dir))


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
    assert set(entry) == {"ts", "timeout_ms", "session", "cwd", "branch"}
    assert entry["branch"] == "rewrite"
    assert entry["timeout_ms"] == _mod().DEFAULT_TIMEOUT_MS
    assert entry["ts"].endswith("Z")
    assert entry["session"] == "sess-1"
    assert entry["cwd"] == "/work"


def test_firing_record_appends_second_line_with_distinct_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    for session_id in ("sess-first", "sess-second"):
        r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"},
                                  "session_id": session_id}))
        assert r.returncode == 0
    record = _record_path(tmp_path)
    lines = open(record, encoding="utf-8").read().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["session"] == "sess-first"
    assert second["session"] == "sess-second"


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
    fillers = (b"generation-alpha-", b"generation-beta-")
    for filler in fillers:
        padding = threshold + 1 - len(filler)
        open(record, "wb").write(filler + b"x" * padding)
        r = _run_hook(json.dumps({"tool_input": {"command": "echo ok"}}))
        assert r.returncode == 0
    state_dir = os.path.dirname(record)
    assert sorted(os.listdir(state_dir)) == [
        "bash-timeout-firings.jsonl",
        "bash-timeout-firings.jsonl.1",
    ]
    rotated_text = open(record + ".1", encoding="utf-8").read()
    assert rotated_text.startswith("generation-beta-")


# --- env off switch, auto-mode refusal, branch record (issue 2563) -----------
# Bite-proof record for every axis below: bite_proofs/wo_a_2563_timeout_hook.md

_MISSING = object()

_OTHER_MODES = [
    pytest.param("default", id="default"),
    pytest.param("acceptEdits", id="acceptEdits"),
    pytest.param("plan", id="plan"),
    pytest.param("bypassPermissions", id="bypassPermissions"),
    pytest.param("dontAsk", id="dontAsk"),
    pytest.param(_MISSING, id="missing-key"),
    pytest.param(1, id="int-mode"),
    pytest.param(None, id="null-mode"),
]


def _payload(mode=_MISSING, **tool_input_extra):
    tool_input = {"command": "echo ok"}
    tool_input.update(tool_input_extra)
    payload = {"tool_input": tool_input}
    if mode is not _MISSING:
        payload["permission_mode"] = mode
    return payload


def _assert_rewrite_output(stdout):
    hso = json.loads(stdout)["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["updatedInput"]["timeout"] == _mod().DEFAULT_TIMEOUT_MS
    assert "permissionDecision" not in hso
    return hso


@pytest.mark.parametrize("mode", [_MISSING, "auto"], ids=["no-mode", "auto-mode"])
@pytest.mark.parametrize("env_value", ["600000", "900000", " 600000 "])
def test_env_at_or_above_floor_switches_hook_off(tmp_path, monkeypatch, env_value, mode):
    monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
    assert _mod().decide(_payload(mode), {"BASH_DEFAULT_TIMEOUT_MS": env_value}) is None
    r = _run_hook(json.dumps(_payload(mode)))
    assert r.returncode == 0
    # axis: env value >= 600000 means no output and no firing record, bite-proof record wo_a_2563_timeout_hook (E1)
    assert r.stdout.strip() == ""
    assert not os.path.exists(_record_path(tmp_path))


@pytest.mark.parametrize("env_value", [None, "599999", "", "abc", "600000.5", "-1"],
                         ids=["unset", "below-floor", "empty", "non-integer", "float", "negative"])
def test_env_below_floor_or_non_number_still_rewrites(monkeypatch, env_value):
    environ = {}
    if env_value is not None:
        monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", env_value)
        environ["BASH_DEFAULT_TIMEOUT_MS"] = env_value
    decision = _mod().decide(_payload(), environ)
    assert decision is not None and decision[0] == "rewrite"
    r = _run_hook(json.dumps(_payload()))
    assert r.returncode == 0
    # axis: env unset/low/non-numeric must not switch the hook off, bite-proof record wo_a_2563_timeout_hook (E2)
    _assert_rewrite_output(r.stdout)


def test_auto_mode_refuses_with_route_and_never_rewrites():
    m = _mod()
    branch, hook_output = m.decide(_payload("auto"), {})
    assert branch == "refuse"
    hso = hook_output["hookSpecificOutput"]
    # axis: auto mode refuses instead of rewriting, bite-proof record wo_a_2563_timeout_hook (E3)
    assert hso["permissionDecision"] == "deny"
    assert "updatedInput" not in hso
    # axis: the refusal reason names the route timeout: 600000, bite-proof record wo_a_2563_timeout_hook (E4)
    assert "timeout: 600000" in hso["permissionDecisionReason"]
    assert "Route:" in hso["permissionDecisionReason"]
    assert hso["hookEventName"] == "PreToolUse"

    r = _run_hook(json.dumps(_payload("auto")))
    assert r.returncode == 0
    out_hso = json.loads(r.stdout)["hookSpecificOutput"]
    # axis: the subprocess output refuses in auto mode with no rewrite, bite-proof record wo_a_2563_timeout_hook (E3)
    assert out_hso["permissionDecision"] == "deny"
    assert "updatedInput" not in out_hso
    # axis: the printed reason names timeout: 600000, bite-proof record wo_a_2563_timeout_hook (E4)
    assert "timeout: 600000" in out_hso["permissionDecisionReason"]
    assert out_hso["permissionDecisionReason"] == m.REFUSAL_REASON


@pytest.mark.parametrize("mode", _OTHER_MODES)
def test_every_other_mode_rewrites(mode):
    decision = _mod().decide(_payload(mode), {})
    # axis: only auto refuses; every other mode value rewrites, bite-proof record wo_a_2563_timeout_hook (E5)
    assert decision is not None and decision[0] == "rewrite"
    r = _run_hook(json.dumps(_payload(mode)))
    assert r.returncode == 0
    # axis: the printed output for a non-auto mode is the rewrite, bite-proof record wo_a_2563_timeout_hook (E5)
    _assert_rewrite_output(r.stdout)


@pytest.mark.parametrize("mode", _OTHER_MODES + [pytest.param("auto", id="auto")])
def test_explicit_timeout_untouched_in_every_mode(tmp_path, mode):
    payload = _payload(mode, timeout=5000)
    # axis: an explicit timeout is never touched, auto mode included, bite-proof record wo_a_2563_timeout_hook (E6)
    assert _mod().decide(payload, {}) is None
    r = _run_hook(json.dumps(payload))
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert not os.path.exists(_record_path(tmp_path))


@pytest.mark.parametrize("payload", [
    pytest.param({"permission_mode": "auto", "tool_input": "x"}, id="tool-input-not-dict"),
    pytest.param({"permission_mode": "auto"}, id="no-tool-input"),
])
def test_malformed_auto_payload_emits_nothing(tmp_path, payload):
    # axis: a malformed payload in auto mode fails open with no refusal, bite-proof record wo_a_2563_timeout_hook (E7)
    assert _mod().decide(payload, {}) is None
    r = _run_hook(json.dumps(payload))
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert not os.path.exists(_record_path(tmp_path))


def test_garbage_stdin_emits_nothing_in_auto_environment(monkeypatch):
    monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", "1000")
    for garbage in ("", "not json {", "[1,2,3]", '"auto"'):
        r = _run_hook(garbage)
        assert r.returncode == 0, "fail-open: hook must exit 0 on %r" % garbage
        # axis: unparsable stdin never emits, bite-proof record wo_a_2563_timeout_hook (E7)
        assert r.stdout.strip() == "", "fail-open: no output on %r" % garbage


def test_firing_record_names_the_branch(tmp_path):
    for mode, expected_branch in ((_MISSING, "rewrite"), ("auto", "refuse")):
        payload = _payload(mode)
        payload["session_id"] = "sess-" + expected_branch
        payload["cwd"] = "/work"
        r = _run_hook(json.dumps(payload))
        assert r.returncode == 0
    lines = open(_record_path(tmp_path), encoding="utf-8").read().splitlines()
    assert len(lines) == 2
    by_session = {entry["session"]: entry for entry in map(json.loads, lines)}
    for expected_branch in ("rewrite", "refuse"):
        entry = by_session["sess-" + expected_branch]
        # axis: the record names the branch taken, bite-proof record wo_a_2563_timeout_hook (E8)
        assert entry["branch"] == expected_branch
        assert set(entry) == {"ts", "timeout_ms", "session", "cwd", "branch"}
        assert entry["timeout_ms"] == _mod().DEFAULT_TIMEOUT_MS
        assert entry["cwd"] == "/work"


def test_refused_call_firing_record_never_contains_command_text(tmp_path):
    secret_marker = "DISTINCTIVE_SECRET_COMMAND_MARKER_REFUSE"
    r = _run_hook(json.dumps(_payload("auto", command=secret_marker)))
    assert r.returncode == 0
    assert secret_marker not in open(_record_path(tmp_path), encoding="utf-8").read()
