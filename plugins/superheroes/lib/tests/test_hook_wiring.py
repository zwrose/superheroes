import json
import os

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOKS = os.path.join(_PLUGIN, "hooks", "hooks.json")
_HOOKS_CODEX = os.path.join(_PLUGIN, "hooks", "hooks-codex.json")


def _cmds(cfg, event):
    return [h["command"] for entry in cfg["hooks"].get(event, []) for h in entry["hooks"]]


def test_session_start_hook_declares_host_claude():
    # The session-start bootstrap is a survivor; assert hooks.json wires it with
    # `--host claude` and stays fail-soft (a hook failure never breaks the session).
    cfg = json.load(open(_HOOKS))
    ss = [c for c in _cmds(cfg, "SessionStart") if "session_start.py" in c]
    assert ss, "no SessionStart hook wires session_start.py"
    for c in ss:
        assert "--host claude" in c
        assert "|| true" in c


def test_bash_timeout_hook_is_wired_fail_soft():
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]
    assert any("bash_timeout.py" in c for c in cmds)


def test_owner_authority_gate_wired_fail_closed_before_worktree_guard():
    # Axis: owner-authority gate fails closed — hook process failure must deny Bash, not allow.
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]

    gate = [c for c in cmds if "owner_authority_gate.py" in c]
    assert gate, "hooks.json must wire owner_authority_gate.py on the Bash matcher"
    gate_cmd = gate[0]
    assert "|| printf" in gate_cmd, "gate must carry a process-failure fallback"

    start = gate_cmd.index("printf ") + len("printf ")
    assert gate_cmd[start] == "'", "printf argument must be single-quoted"
    end = gate_cmd.index("'", start + 1)
    fallback = json.loads(gate_cmd[start + 1 : end])
    assert fallback["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "owner-authority gate unavailable" in fallback["hookSpecificOutput"]["permissionDecisionReason"]

    guard_idx = next(i for i, c in enumerate(cmds) if "worktree_guard_gate.py" in c)
    owner_idx = next(i for i, c in enumerate(cmds) if "owner_authority_gate.py" in c)
    assert owner_idx < guard_idx, (
        "owner-authority gate must be listed before worktree guard on the Bash matcher"
    )


def test_worktree_guard_gate_wired_fail_closed_between_owner_and_timeout():
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]

    gate = [c for c in cmds if "worktree_guard_gate.py" in c]
    assert gate, "hooks.json must wire worktree_guard_gate.py on the Bash matcher"
    gate_cmd = gate[0]
    assert "|| printf" in gate_cmd, "gate must carry a process-failure fallback"

    start = gate_cmd.index("printf ") + len("printf ")
    assert gate_cmd[start] == "'", "printf argument must be single-quoted"
    end = gate_cmd.index("'", start + 1)
    fallback = json.loads(gate_cmd[start + 1:end])
    assert fallback["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "worktree guard unavailable" in fallback["hookSpecificOutput"]["permissionDecisionReason"]

    owner_idx = next(i for i, c in enumerate(cmds) if "owner_authority_gate.py" in c)
    guard_idx = next(i for i, c in enumerate(cmds) if "worktree_guard_gate.py" in c)
    to_idx = next(i for i, c in enumerate(cmds) if "bash_timeout.py" in c)
    assert owner_idx < guard_idx < to_idx, \
        "worktree guard must be listed after owner_authority_gate and before bash_timeout"


def test_handback_receipt_gate_is_not_wired_shipped_dark():
    """#954: the review-receipt handback refusal class ships dark — unwired from PreToolUse.

    Re-arming requires deleting or inverting this test deliberately.
    """
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]

    handback = [c for c in cmds if "handback_receipt_gate.py" in c]
    assert not handback, "handback_receipt_gate.py must not be wired on the Bash matcher (shipped dark, #954)"

    expected = [
        "owner_authority_gate.py",
        "worktree_guard_gate.py",
        "bash_timeout.py",
    ]
    assert len(cmds) == len(expected), (
        f"Bash PreToolUse chain must be exactly {len(expected)} hooks, got {len(cmds)}"
    )
    for i, name in enumerate(expected):
        assert name in cmds[i], f"hook {i} must be {name}, got {cmds[i]!r}"


def test_hooks_codex_still_wires_nothing():
    cfg = json.load(open(_HOOKS_CODEX))
    assert cfg.get("hooks") == {}


def test_retired_spine_hooks_are_not_wired():
    # Regression guard for the spine retirement (#468): the enforcer PreToolUse floor and
    # the PreCompact resume-brief refresh are gone — neither may reappear in either host map.
    for path in (_HOOKS, _HOOKS_CODEX):
        raw = open(path).read()
        assert "enforcer.py" not in raw, f"{path} still wires the retired enforcer"
        assert "precompact.py" not in raw, f"{path} still wires the retired precompact hook"
    claude = json.load(open(_HOOKS))
    assert "PreCompact" not in claude["hooks"], "PreCompact hook must be unwired"
