#!/usr/bin/env python3
"""PostToolUse(Bash): record the native implementer's ``native-enrolled`` binding (#1947).

The native subagent's first Bash command is ``native_engine.py enroll --run-dir D``. The command
itself only checks (it cannot know its own agent id); once it has succeeded, this hook journals the
binding ``close`` requires: the agent id the harness reports and the worktree the command ran in.

FAIL-OPEN: on any parse, shape or write error it emits nothing and exits 0, so it can never break a
Bash call. A missing record is not unsafe: ``close`` forfeits ``native-not-enrolled``.
"""
import json
import os
import shlex
import sys

_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")


def _enroll_run_dir(command):
    """The ``--run-dir`` of a ``native_engine.py enroll`` command, or None."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for i, tok in enumerate(tokens):
        if os.path.basename(tok) != "native_engine.py":
            continue
        rest = tokens[i + 1:]
        if not rest or rest[0] != "enroll":
            return None
        for j, arg in enumerate(rest):
            if arg == "--run-dir" and j + 1 < len(rest):
                return rest[j + 1]
            if arg.startswith("--run-dir="):
                return arg.split("=", 1)[1]
        return None
    return None


def _enroll_succeeded(response):
    text = response.get("stdout") if isinstance(response, dict) else response
    if not isinstance(text, str):
        return False
    for line in text.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("ok") is True:
            return True
    return False


def record(payload):
    """Journal the binding; True when written. Pure of stdin/stdout for tests."""
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return False
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    agent_id = payload.get("agent_id")
    cwd = payload.get("cwd")
    if not (isinstance(command, str) and isinstance(agent_id, str) and agent_id
            and isinstance(cwd, str) and cwd):
        return False
    run_dir = _enroll_run_dir(command)
    if not run_dir or not _enroll_succeeded(payload.get("tool_response")):
        return False
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    import engine_dispatch
    import native_engine
    run_dir = os.path.realpath(run_dir)
    state = native_engine._state(run_dir)
    if state["opened"] is None or state["closed"] is not None or state["enrolled"] is not None:
        return False
    return bool(engine_dispatch._journal_append(run_dir, {
        "kind": "native-enrolled", "agentId": agent_id,
        "worktree": native_engine.worktree_top(cwd),
        "at": native_engine._stamp(native_engine._now())}))


def main():
    try:
        record(json.load(sys.stdin))
    except Exception:  # fail-open
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
