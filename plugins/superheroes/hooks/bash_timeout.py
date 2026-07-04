#!/usr/bin/env python3
"""PreToolUse(Bash) input rewrite: floor the Bash tool timeout when the model omits one.

The Bash tool defaults to 120s. Long spine commands (verify_gate.py wrapping a full
pytest gate, validators, test-pilot runs) legitimately run past that, and leaf prompts
can only ASK the courier model to pass `timeout: 600000` — compliance is stochastic
(live: verify couriers killed at 120s mid-run → doubled leaves, occasional parks when
both attempts died). This hook makes the floor structural: when a Bash call carries no
explicit `timeout`, inject 600000ms via `hookSpecificOutput.updatedInput` — matching
verify_gate.py's own DEFAULT_TIMEOUT (600s), so the gate reports `timeout` cleanly
instead of being killed underneath. Probe-verified 2026-07-04: injected timeout takes
effect, and plugin PreToolUse hooks fire inside subagent leaves.

Two deliberate bounds:
- An EXPLICIT model-passed timeout is never touched — the failure mode being fixed is
  omission, not misjudgment. (A `null` timeout counts as omitted.)
- FAIL-OPEN, unlike the enforcer: on any parse/shape error emit nothing and exit 0 —
  worst case is the pre-hook 120s default, never a broken Bash call. (The enforcer in
  the same matcher block stays fail-closed; a deny there wins over this rewrite.)
"""
import json
import sys

DEFAULT_TIMEOUT_MS = 600000  # mirrors verify_gate.DEFAULT_TIMEOUT (600s); a project that lowers
# BASH_MAX_TIMEOUT_MS below this gets the harness's clamp, not an error — still fail-open.


def decide(payload):
    """Pure: the updated tool_input dict, or None for no-op (explicit timeout / bad shape)."""
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    if tool_input.get("timeout") is not None:
        return None
    updated = dict(tool_input)
    updated["timeout"] = DEFAULT_TIMEOUT_MS
    return updated


def main():
    try:
        updated = decide(json.load(sys.stdin))
        if updated is not None:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "updatedInput": updated}}))
    except Exception:
        pass  # fail-open: a hook error must never alter or block the call
    sys.exit(0)


if __name__ == "__main__":
    main()
