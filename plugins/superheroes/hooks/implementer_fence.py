#!/usr/bin/env python3
"""PreToolUse(Bash|Edit|Write) native implementer fence (#1947).

Reads the PreToolUse payload from stdin and asks native_fence.fence_decision. The fence acts only
on the `superheroes:implementer` subagent of a native run; for every other payload it stays silent.

Contract (atomic single write, exit 0 always):

- stdout is written EXACTLY ONCE, at the very end — a single `permissionDecision: "deny"` JSON, or
  nothing at all.
- The whole body is wrapped in try/except. A failure denies ONLY when the parsed payload is the
  implementer's (fail-closed for the fenced agent); for any other payload, or a payload that could
  not be parsed, the hook stays silent so it can never break the builder's or another agent's call.
- It never prompts and never waits: stdin, a few small file reads and one journal append.

Stdlib-only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

_IMPLEMENTER = "superheroes:implementer"
_DENY_ERROR = "superheroes native fence error (fail-closed)"


def _deny_json(reason):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}})


def main():
    out = None  # the single string to write, computed fully before any output (atomic single write)
    is_implementer = False
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        is_implementer = payload.get("agent_type") == _IMPLEMENTER
        if is_implementer:
            import native_fence
            reason = native_fence.fence_decision(payload)
            if reason is not None:
                out = _deny_json(reason)
    except Exception:
        if is_implementer:
            out = _deny_json(_DENY_ERROR)

    if out is not None:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
