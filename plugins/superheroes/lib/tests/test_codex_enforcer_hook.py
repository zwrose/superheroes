# plugins/workhorse/lib/tests/test_codex_enforcer_hook.py
"""hooks-codex.json wiring: PreToolUse, ${PLUGIN_ROOT}-rooted, fail-closed deny.
The enforcer's deny BEHAVIOR is host-agnostic (the same enforcer.py runs on both
hosts) and is covered by test_enforcer.py. This test scopes to the Codex WIRING +
non-vacuity: the hook must invoke the REAL enforcer with the deny fallback, and
enforcer.py must exist — so removing/renaming it FAILS here, not silently passes."""
import json, os
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
HOOKS = os.path.join(_ROOT, "hooks", "hooks-codex.json")
ENFORCER = os.path.join(_ROOT, "lib", "enforcer.py")

def test_codex_hook_wires_pretooluse_deny_to_real_enforcer():
    with open(HOOKS, encoding="utf-8") as fh:
        cfg = json.load(fh)
    entries = cfg["hooks"]["PreToolUse"]
    assert entries, "no PreToolUse entries"
    for e in entries:
        cmd = e["hooks"][0]["command"]
        assert "${PLUGIN_ROOT}" in cmd                 # Codex-rooted, not CLAUDE_PLUGIN_ROOT
        assert "lib/enforcer.py" in cmd                 # invokes the REAL enforcer
        assert '"permissionDecision":"deny"' in cmd     # fail-closed fallback
    assert os.path.isfile(ENFORCER), "enforcer.py missing — the hook would always fall back to deny"
