#!/usr/bin/env python3
"""PreToolUse(Bash) worktree guard — blocks destructive git discard on dirty trees (issue #682).

Reads the PreToolUse payload from stdin. When the tool is Bash and the command is a destructive
git discard on a superheroes-calibrated project with at-risk worktree content, it emits
`permissionDecision: "deny"`. For every other case it stays silent (implicit allow).

Contract (fail-closed, atomic single write):

- `tool_name` gating is the HOOK's job: only a Bash tool call is classified. Any other tool_name
  (or a missing one) → silent, exit 0.
- stdout is written EXACTLY ONCE, atomically, at the very end — never partial output.
- The whole body is wrapped in try/except. ANY internal failure (unparseable stdin, a classifier
  raise, a non-string command that cannot be inspected) → a single valid `deny` JSON, exit 0. The
  hook NEVER exits non-zero in normal operation, so the hooks.json `|| printf ...deny...` wrapper
  is reserved purely for a process that cannot start.

Stdlib-only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

_DENY_INSPECT = ("superheroes worktree guard: could not inspect this command "
                 "(fail-closed)")


def _deny_json(reason):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}})


def main():
    out = None  # the single string to write, computed fully before any output (atomic single write)
    try:
        # No `or "{}"` fallback: an empty/unparseable stdin is a payload we could not receive,
        # so it must fail CLOSED (→ deny via the except), not silently become a tool_name-less {}.
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")

        # tool_name gating is the hook's job: only classify a Bash call; anything else is silent.
        if payload.get("tool_name") != "Bash":
            return 0

        command = payload.get("tool_input", {}).get("command") \
            if isinstance(payload.get("tool_input"), dict) else None
        if not isinstance(command, str):
            # A Bash call we cannot inspect (no string command) → fail-closed to deny.
            out = _deny_json(_DENY_INSPECT)
        else:
            import worktree_guard
            decision, reason = worktree_guard.classify(command, payload.get("cwd"))
            if decision == "deny":
                out = _deny_json(reason)
            # decision == "allow" → out stays None (write nothing)
    except Exception:
        out = _deny_json(_DENY_INSPECT)

    if out is not None:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
