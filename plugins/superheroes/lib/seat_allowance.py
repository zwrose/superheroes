#!/usr/bin/env python3
"""The review-seat allowance (#2071): the one home of what a review seat may do.

A codex review seat runs under a CLOSED tool set: the user's own MCP servers, plugins and hooks
are dropped, the shell and unified-exec tools are disabled, and the only tool source is the
read-only file server in `seat_read_tool.py`, with its tools pre-approved (codex exec refuses an
MCP call that is not pre-approved). The allowance is positive — it names what a seat may do and
treats everything else as outside; no program or command name is listed here.

Exports: the two allowance sentences, `codex_review_args` (the argv tokens of the closed tool
set), `outside_allowance` (judges one parsed codex JSONL event) and `scan_stream` (judges a whole
captured stream file). stdlib only; nothing here raises."""
import json
import os
import sys

READ_SERVER_NAME = "superheroes_read"

REVIEW_ALLOWANCE = (
    "You may read, list and search files with your read tools, and you run no program: "
    "a test, check or command run you need is the driver's, which runs the project's "
    "declared verify command."
)

FIXER_ALLOWANCE = (
    "You run only the commands this order names (its scoped tests, validators, break-it "
    "commands and the commit) and your edit tools, and none of the project's own scripts "
    "beyond them; the full verify command stays the driver's."
)

ALLOWED_ITEM_TYPES = frozenset({"agent_message", "reasoning", "todo_list", "error", "web_search"})

_JUDGED_EVENTS = ("item.started", "item.completed")
_DESCRIPTION_CAP = 200
_COMMAND_CAP = 120

_READ_TOOL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "seat_read_tool.py")


def _toml_string(value):
    """A TOML basic string for `value` (json.dumps output is a valid TOML basic string)."""
    return json.dumps(value)


def codex_review_args(cwd):
    """The argv tokens that close a codex review seat's tool set, in order. Never raises."""
    tool_args = ["-I", "-B", _READ_TOOL_PATH]
    if isinstance(cwd, str) and cwd:
        tool_args += ["--root", cwd]
    prefix = "mcp_servers.%s." % READ_SERVER_NAME
    return [
        "--ignore-user-config",
        "--disable", "shell_tool",
        "--disable", "unified_exec",
        "-c", prefix + "command=" + _toml_string(str(sys.executable)),
        "-c", prefix + "args=[" + ",".join(_toml_string(a) for a in tool_args) + "]",
        "-c", prefix + 'default_tools_approval_mode="approve"',
    ]


def _cap(text, limit):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def outside_allowance(obj):
    """None when the parsed codex JSONL event `obj` is inside the allowance, else a short
    description (<= 200 chars) of what is outside it. Only item.started / item.completed events
    are judged; any other object is not a judged event and yields None."""
    if not isinstance(obj, dict) or obj.get("type") not in _JUDGED_EVENTS:
        return None
    item = obj.get("item")
    if not isinstance(item, dict):
        return None
    item_type = item.get("type")
    if isinstance(item_type, str) and item_type in ALLOWED_ITEM_TYPES:
        return None
    if item_type == "mcp_tool_call":
        server = item.get("server")
        if server == READ_SERVER_NAME:
            return None
        return _cap("mcp_tool_call: %s.%s" % (server, item.get("tool")), _DESCRIPTION_CAP)
    if item_type == "command_execution":
        return _cap("command_execution: %s" % _cap(item.get("command"), _COMMAND_CAP),
                    _DESCRIPTION_CAP)
    return _cap(item_type, _DESCRIPTION_CAP)


def scan_stream(path, limit=20):
    """(violations, ok) for the codex JSONL stream file at `path`. Reads the whole file one line
    at a time (binary), skips unparseable lines, dedupes violations and caps them at `limit`.
    ok is False only when the file cannot be opened. Never raises."""
    violations = []
    seen = set()
    try:
        handle = open(path, "rb")
    except (OSError, TypeError, ValueError):
        return [], False
    try:
        with handle:
            for raw in handle:
                try:
                    obj = json.loads(raw)
                except (ValueError, RecursionError):
                    continue
                try:
                    found = outside_allowance(obj)
                except Exception:
                    continue
                if found is None or found in seen:
                    continue
                seen.add(found)
                if len(violations) < limit:
                    violations.append(found)
    except (OSError, MemoryError):
        return violations, True
    return violations, True
