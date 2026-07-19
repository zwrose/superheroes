"""owner_authority_gate.py — the PreToolUse(Bash) owner-authority gate hook (#482).

Process contract: the hook classifies only Bash calls, emits a single atomic `ask` JSON for a
gated command on a calibrated project (and for any inspection failure — fail-closed), stays
silent otherwise, and NEVER exits non-zero in normal operation. Plus the hooks.json wiring: the
gate rides the Bash matcher with a `|| printf ...deny...` process-failure backstop, ahead of the
surviving bash_timeout hook, and the SessionStart entry is untouched.
"""
import json
import os
import subprocess

import mode_registry

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "owner_authority_gate.py")
_HOOKS_JSON = os.path.join(_PLUGIN, "hooks", "hooks.json")


def _run_hook(stdin_text):
    return subprocess.run(["python3", _HOOK], input=stdin_text,
                          capture_output=True, text=True, timeout=10)


def _calibrate(cwd):
    """Write a valid registry for cwd under the env-pinned (conftest) store root, so a
    subprocess that inherits the env resolves the same record and sees a calibrated project."""
    rec = mode_registry.write_registry(cwd, mode_registry.IN_REPO, None)
    assert rec is not None, "precondition: registry write landed for %s" % cwd
    return cwd


# --- process contract --------------------------------------------------------

def test_gated_command_on_calibrated_asks(tmp_path):
    cwd = _calibrate(str(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": "gh pr merge 42 --squash"}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "owner-authority" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_gated_command_on_uncalibrated_is_silent(tmp_path):
    # A fresh tmp dir with no registry and no hero evidence → uncalibrated → silent allow.
    cwd = str(tmp_path / "greenfield")
    os.makedirs(cwd)
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": "gh pr merge 42 --squash"}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_ordinary_command_on_calibrated_is_silent(tmp_path):
    cwd = _calibrate(str(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Bash", "cwd": cwd,
                              "tool_input": {"command": "git commit -m x"}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_non_bash_tool_is_silent(tmp_path):
    cwd = _calibrate(str(tmp_path))
    r = _run_hook(json.dumps({"tool_name": "Edit", "cwd": cwd,
                              "tool_input": {"command": "gh pr merge 42 --squash"}}))
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_malformed_stdin_fails_closed_to_ask():
    for garbage in ("", "not json {", "[1,2,3]"):
        r = _run_hook(garbage)
        assert r.returncode == 0, "hook must exit 0 on %r" % garbage
        out = json.loads(r.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "ask", \
            "fail-closed: %r must yield ask" % garbage


def test_bash_with_non_string_command_fails_closed_to_ask():
    r = _run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": None}}))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "fail-closed" in out["hookSpecificOutput"]["permissionDecisionReason"]


# --- wiring ------------------------------------------------------------------

def test_hooks_json_wires_gate_fail_closed_before_timeout():
    cfg = json.load(open(_HOOKS_JSON))
    bash_blocks = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert len(bash_blocks) == 1, "exactly one Bash matcher block"
    cmds = [h["command"] for h in bash_blocks[0]["hooks"]]

    gate = [c for c in cmds if "owner_authority_gate.py" in c]
    assert gate, "hooks.json must wire owner_authority_gate.py on the Bash matcher"
    gate_cmd = gate[0]
    assert "|| printf" in gate_cmd, "gate must carry a process-failure fallback"

    # The fallback JSON is the single-quoted printf argument; it must parse and deny.
    start = gate_cmd.index("printf ") + len("printf ")
    assert gate_cmd[start] == "'", "printf argument must be single-quoted"
    end = gate_cmd.index("'", start + 1)
    fallback = json.loads(gate_cmd[start + 1:end])
    assert fallback["hookSpecificOutput"]["permissionDecision"] == "deny"

    # bash_timeout still rides the same block.
    assert any("bash_timeout.py" in c for c in cmds), "bash_timeout.py must remain wired"

    # ...and the gate must be listed AHEAD of bash_timeout (fail-closed before timeout).
    gate_idx = next(i for i, c in enumerate(cmds) if "owner_authority_gate.py" in c)
    to_idx = next(i for i, c in enumerate(cmds) if "bash_timeout.py" in c)
    assert gate_idx < to_idx, "owner-authority gate must be listed ahead of bash_timeout"


def test_session_start_entry_untouched():
    cfg = json.load(open(_HOOKS_JSON))
    ss_cmds = [h["command"] for entry in cfg["hooks"].get("SessionStart", [])
               for h in entry["hooks"]]
    assert any("session_start.py" in c for c in ss_cmds), \
        "SessionStart must still reference session_start.py"
