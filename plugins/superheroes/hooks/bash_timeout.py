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

The hook keeps a firing record so its usefulness can be read later. The record is written
fail-open so it can never break a Bash call.
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


def record_firing(payload, timeout_ms):
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
        }
        with open(path, "a", encoding="utf-8") as record:
            record.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
        updated = decide(payload)
        if updated is not None:
            record_firing(payload, DEFAULT_TIMEOUT_MS)
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "updatedInput": updated}}))
    except Exception:
        pass  # fail-open: a hook error must never alter or block the call
    sys.exit(0)


if __name__ == "__main__":
    main()
