#!/usr/bin/env python3
# STUB(#954): handback refusal class is unwired from the PreToolUse chain — the hook never runs, so gh pr ready / non-draft gh pr create are not gated; arming is #954's decision.
"""PreToolUse(Bash) review-receipt gate — blocks handback without a valid receipt (#624 §4).

**Shipped dark; nothing invokes this; the class does not arm; arming is owned by #954**
(retrospective would-refuse audit → shadow mode → preconditions → owner decision). The
parser-exactness question (the A-vs-B fork) is moot while dark and recorded on #954 — do not
resolve it here.

Reads the PreToolUse payload from stdin. When the tool is Bash and the command is a guarded
``gh pr ready`` / non-draft ``gh pr create`` in a mechanically-marked full-lane worktree that lacks
an allowlisted review receipt, it emits ``permissionDecision: "deny"``. For every other case it
stays silent (implicit allow).

Contract (fail-closed, atomic single write):

- ``tool_name`` gating is the HOOK's job: only a Bash tool call is classified. Any other tool_name
  (or a missing one) → silent, exit 0.
- stdout is written EXACTLY ONCE, atomically, at the very end — never partial output.
- The whole body is wrapped in try/except. ANY internal failure (unparseable stdin, a classifier
  raise, a non-string command that cannot be inspected) → a single valid ``deny`` JSON, exit 0. The
  hook NEVER exits non-zero in normal operation, so the hooks.json ``|| printf ...deny...`` wrapper
  is reserved purely for a process that cannot start.

Stdlib-only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

_DENY_INSPECT = ("superheroes review-receipt gate: could not inspect this command "
                 "(fail-closed)")
_FAMILY_PREFIX = "superheroes review-receipt gate"


def _deny_json(reason):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}})


def _format_reason(detail):
    detail = (detail or "").strip()
    if detail.startswith(_FAMILY_PREFIX):
        return detail
    if detail:
        return "%s: %s" % (_FAMILY_PREFIX, detail)
    return "%s: refused" % _FAMILY_PREFIX


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
            import handback_gate
            result = handback_gate.validate_handback(command, payload.get("cwd"))
            if result["decision"] == "refuse":
                out = _deny_json(_format_reason(result.get("detail")))
            # decision == "allow" → out stays None (write nothing)
    except Exception:
        out = _deny_json(_DENY_INSPECT)

    if out is not None:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
