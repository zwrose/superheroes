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

def test_hooks_json_wires_timeout_floor_after_enforcer_fail_open():
    cfg = json.load(open(_HOOKS_JSON))
    bash_blocks = [h for h in cfg["hooks"]["PreToolUse"] if h["matcher"] == "Bash"]
    assert len(bash_blocks) == 1
    cmds = [h["command"] for h in bash_blocks[0]["hooks"]]
    idx = [i for i, c in enumerate(cmds) if "bash_timeout.py" in c]
    assert idx, "hooks.json must wire bash_timeout.py on the Bash matcher"
    assert "enforcer.py" in cmds[0], "the fail-closed enforcer stays the first Bash hook"
    assert idx[0] > 0, "the timeout floor rides after the enforcer entry"
    assert "|| true" in cmds[idx[0]], "process-level fail-open: a hook crash never breaks Bash"
