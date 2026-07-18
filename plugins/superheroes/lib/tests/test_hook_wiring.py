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


def test_retired_spine_hooks_are_not_wired():
    # Regression guard for the spine retirement (#468): the enforcer PreToolUse floor and
    # the PreCompact resume-brief refresh are gone — neither may reappear in either host map.
    for path in (_HOOKS, _HOOKS_CODEX):
        raw = open(path).read()
        assert "enforcer.py" not in raw, f"{path} still wires the retired enforcer"
        assert "precompact.py" not in raw, f"{path} still wires the retired precompact hook"
    claude = json.load(open(_HOOKS))
    assert "PreCompact" not in claude["hooks"], "PreCompact hook must be unwired"
