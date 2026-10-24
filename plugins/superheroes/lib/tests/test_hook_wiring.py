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


def test_worktree_guard_gate_wired_fail_closed_before_bash_timeout():
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

    guard_idx = next(i for i, c in enumerate(cmds) if "worktree_guard_gate.py" in c)
    to_idx = next(i for i, c in enumerate(cmds) if "bash_timeout.py" in c)
    # axis: the worktree guard precedes bash_timeout on the Bash matcher
    assert guard_idx < to_idx, \
        "worktree guard must be listed before bash_timeout on the Bash matcher"


def test_iphone_allow_hook_is_wired_fail_soft_after_worktree_guard():
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]

    iphone = [c for c in cmds if "iphone_allow.py" in c]
    assert iphone, "hooks.json must wire iphone_allow.py on the Bash matcher"
    # axis: the iPhone approver is fail-soft — a failure to start leaves no decision, never a block
    assert "|| true" in iphone[0]

    guard_idx = next(i for i, c in enumerate(cmds) if "worktree_guard_gate.py" in c)
    iphone_idx = next(i for i, c in enumerate(cmds) if "iphone_allow.py" in c)
    # axis: the iPhone approver is listed after the worktree guard on the Bash matcher
    assert guard_idx < iphone_idx, \
        "iphone_allow must be listed after the worktree guard on the Bash matcher"


_PLUGIN_SCRIPTS_ALLOW_COMMAND = 'python3 -B "${CLAUDE_PLUGIN_ROOT}/hooks/plugin_scripts_allow.py" || true'


def test_plugin_scripts_allow_hook_is_wired_fail_soft_after_worktree_guard():
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]

    approver = [c for c in cmds if "plugin_scripts_allow.py" in c]
    assert approver, "hooks.json must wire plugin_scripts_allow.py on the Bash matcher"
    # axis: the whole own-scripts approver invocation is pinned — the interpreter, the plugin-root path and fail-soft
    assert approver == [_PLUGIN_SCRIPTS_ALLOW_COMMAND]

    guard_idx = next(i for i, c in enumerate(cmds) if "worktree_guard_gate.py" in c)
    approver_idx = next(i for i, c in enumerate(cmds) if "plugin_scripts_allow.py" in c)
    # axis: the own-scripts approver is listed after the worktree guard on the Bash matcher
    assert guard_idx < approver_idx, \
        "plugin_scripts_allow must be listed after the worktree guard on the Bash matcher"


def test_bash_pretooluse_chain_is_exactly_guard_timeout_iphone_scripts_then_fence():
    """The Bash PreToolUse chain is pinned: adding a hook requires changing this test deliberately."""
    cfg = json.load(open(_HOOKS))
    bash = [h for h in cfg["hooks"]["PreToolUse"] if h.get("matcher") == "Bash"]
    assert bash, "no Bash PreToolUse matcher"
    cmds = [h["command"] for entry in bash for h in entry["hooks"]]

    expected = [
        "worktree_guard_gate.py",
        "bash_timeout.py",
        "iphone_allow.py",
        "plugin_scripts_allow.py",
        "implementer_fence.py",
    ]
    # axis: the Bash PreToolUse chain is exactly five hooks — the worktree guard, bash_timeout, the iPhone approver, the own-scripts approver, then the native fence
    assert len(cmds) == len(expected), (
        f"Bash PreToolUse chain must be exactly {len(expected)} hooks, got {len(cmds)}"
    )
    for i, name in enumerate(expected):
        # axis: hook order and identity pinned to the five-hook chain
        assert name in cmds[i], f"hook {i} must be {name}, got {cmds[i]!r}"


_FENCE_COMMAND = 'python3 -B "${CLAUDE_PLUGIN_ROOT}/hooks/implementer_fence.py" || true'


def test_implementer_fence_is_wired_on_bash_and_edit_write_fail_open():
    cfg = json.load(open(_HOOKS))
    entries = cfg["hooks"]["PreToolUse"]
    for matcher in ("Bash", "Edit|Write"):
        cmds = [h["command"] for e in entries if e.get("matcher") == matcher for h in e["hooks"]]
        # axis: the native fence runs on both the Bash matcher and the Edit|Write matcher, with the exact command
        assert _FENCE_COMMAND in cmds, f"{matcher} matcher must carry the exact fence command"
    edit_write = [h["command"] for e in entries if e.get("matcher") == "Edit|Write" for h in e["hooks"]]
    # axis: the Edit|Write matcher carries the fence alone
    assert edit_write == [_FENCE_COMMAND]
    # axis: the shim the command names exists
    assert os.path.isfile(os.path.join(_PLUGIN, "hooks", "implementer_fence.py"))


def test_hooks_codex_still_wires_nothing():
    cfg = json.load(open(_HOOKS_CODEX))
    assert cfg.get("hooks") == {}


def test_retired_spine_hooks_are_not_wired():
    # Regression guard for the spine retirement (#468): the enforcer PreToolUse floor and
    # the retired precompact.py resume-brief refresh must not return. Issue #911 ratified a
    # new stateless PreCompact hook (compaction_context.py) — a different file, different
    # contract — so the blanket "no PreCompact" guard narrows to filename checks only.
    for path in (_HOOKS, _HOOKS_CODEX):
        raw = open(path).read()
        assert "enforcer.py" not in raw, f"{path} still wires the retired enforcer"
        assert "precompact.py" not in raw, f"{path} still wires the retired precompact hook"
    claude = json.load(open(_HOOKS))
    pc_cmds = _cmds(claude, "PreCompact")
    if pc_cmds:
        for c in pc_cmds:
            assert "compaction_context.py" in c, (
                "PreCompact must wire compaction_context.py, not another hook"
            )
            assert "precompact.py" not in c, "retired precompact.py must not reappear"
            assert "|| true" in c, "PreCompact must be fail-open (|| true suffix)"


def test_precompact_hook_is_wired_fail_open():
    cfg = json.load(open(_HOOKS))
    pc = _cmds(cfg, "PreCompact")
    assert pc, "PreCompact must wire compaction_context.py"
    assert all("compaction_context.py" in c for c in pc)
    assert all("|| true" in c for c in pc)
