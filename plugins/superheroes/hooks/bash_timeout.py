#!/usr/bin/env python3
"""PreToolUse(Bash) timeout floor: act when the model omits a Bash timeout.

The Bash tool defaults to 120s. Long spine commands (verify_gate.py wrapping a full
pytest gate, validators, test-pilot runs) legitimately run past that, and leaf prompts
can only ASK the courier model to pass `timeout: 600000` — compliance is stochastic
(live: verify couriers killed at 120s mid-run → doubled leaves, occasional parks when
both attempts died). This hook makes the floor structural. For every PreToolUse(Bash)
payload it emits exactly one of three outcomes:

1. Nothing. The env switch is on, the input cannot be parsed or has a bad shape, or the
   call carries an explicit `timeout`.
2. A rewrite (every mode except auto): `hookSpecificOutput.updatedInput` with
   `timeout: 600000` injected — matching verify_gate.py's own DEFAULT_TIMEOUT (600s), so
   the gate reports `timeout` cleanly instead of being killed underneath. Probe-verified
   2026-07-04: injected timeout takes effect, and plugin PreToolUse hooks fire inside
   subagent leaves.
3. A refusal (auto mode only): `permissionDecision: deny` whose reason names the route
   `timeout: 600000`. In auto mode a rewritten input is not covered by auto mode's
   approval, so the rewritten call becomes an owner prompt. A refusal instead reaches the
   model as a retryable reason, and the model re-issues the call with the timeout named.
   Probe-verified 2026-11-18 in a child `claude -p --permission-mode auto` run, CLI 2.1.327.

The env switch: when `BASH_DEFAULT_TIMEOUT_MS` parses (`int(value.strip())`) to an integer
at or above the floor, the host default already meets it, so the hook emits nothing and
writes no firing record. Unset, empty, below the floor, or not an integer never switches
the hook off, and a parse failure there is never an error.

Two deliberate bounds:
- An EXPLICIT model-passed timeout is never touched, in every mode, auto included — the
  failure mode being fixed is omission, not misjudgment. (A `null` timeout counts as
  omitted.)
- FAIL-OPEN, unlike the enforcer: on any parse/shape error emit nothing and exit 0 —
  worst case is the pre-hook 120s default, never a broken Bash call. (The enforcer in
  the same matcher block stays fail-closed; a deny there wins over this rewrite.)

The hook keeps a firing record, one line per rewrite or refusal and naming the branch, so
its usefulness can be read later. The record is written fail-open so it can never break a
Bash call.
"""
import datetime
import json
import os
import sys

_STORE_ROOT_ENV_NEW = "SUPERHEROES_STORE_ROOT"
_STORE_ROOT_ENV_LEGACY = "WORKHORSE_STORE_ROOT"
_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
_DEFAULT_CONFIG_DIR = "~/.claude"
_RECORD_UNDER_STORE = os.path.join("state", "bash-timeout-firings.jsonl")
_RECORD_UNDER_CONFIG = os.path.join("superheroes", "state", "bash-timeout-firings.jsonl")
_RECORD_ROTATE_BYTES = 2 * 1024 * 1024

# WORKAROUND: PreToolUse Bash timeout floor when the model omits an explicit timeout.
# delete-when: the host Bash tool defaults to at least 600 s without a PreToolUse rewrite hook.
DEFAULT_TIMEOUT_MS = 600000  # mirrors verify_gate.DEFAULT_TIMEOUT (600s); a project that lowers
# BASH_MAX_TIMEOUT_MS below this gets the harness's clamp, not an error — still fail-open.


_ENV_SWITCH = "BASH_DEFAULT_TIMEOUT_MS"

REFUSAL_REASON = (
    "superheroes timeout floor: this Bash call names no timeout. Route: re-issue this same "
    "Bash call once, unchanged except for timeout: 600000. In auto mode the floor asks you "
    "instead of rewriting the call, because a rewritten call waits for the owner's approval."
)


def _env_switch_on(environ):
    """True when BASH_DEFAULT_TIMEOUT_MS parses to an integer at or above the floor."""
    value = environ.get(_ENV_SWITCH)
    if value is None:
        return False
    try:
        return int(value.strip()) >= DEFAULT_TIMEOUT_MS
    except (ValueError, AttributeError):
        return False


def decide(payload, environ):
    """Pure: None (emit nothing) or (branch, hook_output) with the JSON-ready dict to print."""
    if _env_switch_on(environ):
        return None
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    if tool_input.get("timeout") is not None:
        return None
    if payload.get("permission_mode") == "auto":
        return "refuse", {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": REFUSAL_REASON}}
    updated = dict(tool_input)
    updated["timeout"] = DEFAULT_TIMEOUT_MS
    return "rewrite", {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "updatedInput": updated}}


def _record_file_path():
    # The record is config-dir-scoped. The env override order below matches
    # control_plane.store_root() (plugins/superheroes/lib/control_plane.py); the legacy
    # projects/-presence fallback that function also carries is deliberately not
    # replicated, because the hook stays import-free and a second copy of that
    # branch would be one more thing nothing keeps honest.
    store_env = os.environ.get(_STORE_ROOT_ENV_NEW) or os.environ.get(_STORE_ROOT_ENV_LEGACY)
    if store_env:
        base = os.path.expanduser(store_env)
        return os.path.join(base, _RECORD_UNDER_STORE)
    config_dir = os.environ.get(_CONFIG_DIR_ENV)
    base = os.path.expanduser(config_dir if config_dir else _DEFAULT_CONFIG_DIR)
    return os.path.join(base, _RECORD_UNDER_CONFIG)


def _rotate_record_if_needed(path):
    if os.path.isfile(path) and os.path.getsize(path) > _RECORD_ROTATE_BYTES:
        rotated = path + ".1"
        os.replace(path, rotated)


def record_firing(payload, timeout_ms, branch):
    """Append one firing line; fail-open on any error."""
    try:
        path = _record_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _rotate_record_if_needed(path)
        if isinstance(payload, dict):
            session = payload.get("session_id")
            cwd = payload.get("cwd")
        else:
            session = None
            cwd = None
        entry = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "timeout_ms": timeout_ms,
            "session": session,
            "cwd": cwd,
            "branch": branch,
        }
        with open(path, "a", encoding="utf-8") as record:
            record.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
        decision = decide(payload, os.environ)
        if decision is not None:
            branch, hook_output = decision
            record_firing(payload, DEFAULT_TIMEOUT_MS, branch)
            print(json.dumps(hook_output))
    except Exception:
        pass  # fail-open: a hook error must never alter or block the call
    sys.exit(0)


if __name__ == "__main__":
    main()
