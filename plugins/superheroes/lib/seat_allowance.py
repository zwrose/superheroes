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

# editToolCall is in the set because a cursor review seat delivers its typed result file by editing it.
CURSOR_ALLOWED_TOOL_CALLS = frozenset({
    "readToolCall", "grepToolCall", "globToolCall", "lsToolCall", "editToolCall"})

_JUDGED_EVENTS =("item.started", "item.completed")
_DESCRIPTION_CAP = 200
_COMMAND_CAP = 120
# The scan reads a stream the engine wrote without a size bound: one line over _MAX_LINE_BYTES, or
# a stream over _MAX_SCAN_BYTES in all, ends the scan as unreadable (ok False), not as a decode.
_MAX_LINE_BYTES = 1 << 20
_MAX_SCAN_BYTES = 64 << 20

_READ_TOOL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "seat_read_tool.py")


def _toml_string(value):
    """A TOML basic string for `value` (json.dumps output is a valid TOML basic string;
    ensure_ascii=False keeps a character outside the BMP whole, where the ASCII escape would
    write a UTF-16 surrogate pair, which TOML rejects)."""
    return json.dumps(value, ensure_ascii=False)


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


def _real(path):
    try:
        return os.path.realpath(path)
    except (OSError, TypeError, ValueError):
        return None


def _edit_target_permitted(args, permitted_edit_paths, seat_cwd=None):
    """True only when the edit call's `path` argument is a string that resolves to one of the
    permitted result-file paths. A relative target resolves against `seat_cwd` (the seat's own
    working directory, which is not the scanner's); with no seat_cwd a relative target has no
    verifiable meaning and is not permitted. No permitted paths, or no verifiable target, is not
    permitted."""
    if not permitted_edit_paths or not isinstance(args, dict):
        return False
    target = args.get("path")
    if not isinstance(target, str) or not target:
        return False
    if not os.path.isabs(target):
        if not isinstance(seat_cwd, str) or not os.path.isabs(seat_cwd):
            return False
        target = os.path.join(seat_cwd, target)
    real = _real(target)
    if real is None:
        return False
    return any(isinstance(p, str) and p and _real(p) == real for p in permitted_edit_paths)


def outside_allowance(obj, permitted_edit_paths=None, seat_cwd=None):
    """None when the parsed codex JSONL event `obj` is inside the allowance, else a short
    description (<= 200 chars) of what is outside it. Only item.started / item.completed events
    are judged; any other object is not a judged event and yields None. A cursor stream-json
    `tool_call` event is inside the allowance only when its call is a one-key dict whose key is in
    `CURSOR_ALLOWED_TOOL_CALLS`; every other call (a shell or mode call, an unknown key, a
    dict that is not one-key, a non-dict) is outside it. An `editToolCall` is inside only when its
    target path is one of `permitted_edit_paths` (the attempt's own result file and its handoff
    alias; a relative target resolves against `seat_cwd`); an edit of any other path, or one with no verifiable target, is outside."""
    if isinstance(obj, dict) and obj.get("type") == "tool_call":
        call = obj.get("tool_call")
        if isinstance(call, dict) and len(call) == 1:
            key = next(iter(call))
            body = call.get(key)
            args = body.get("args") if isinstance(body, dict) else None
            if key in CURSOR_ALLOWED_TOOL_CALLS:
                if key != "editToolCall":
                    return None
                if _edit_target_permitted(args, permitted_edit_paths, seat_cwd):
                    return None
                target = args.get("path") if isinstance(args, dict) else None
                return _cap("%s: %s" % (key, _cap(target, _COMMAND_CAP)), _DESCRIPTION_CAP) \
                    if isinstance(target, str) and target else _cap(key, _DESCRIPTION_CAP)
            command = args.get("command") if isinstance(args, dict) else None
            if command is None:
                return _cap(key, _DESCRIPTION_CAP)
            return _cap("%s: %s" % (key, _cap(command, _COMMAND_CAP)), _DESCRIPTION_CAP)
        return _cap("tool_call: %s" % _cap(
            sorted(call) if isinstance(call, dict) else type(call).__name__, _COMMAND_CAP),
            _DESCRIPTION_CAP)
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


def _call_id(obj):
    """The string call_id of a cursor tool_call lifecycle event, else None."""
    if isinstance(obj, dict) and obj.get("type") == "tool_call":
        call_id = obj.get("call_id")
        if isinstance(call_id, str) and call_id:
            return call_id
    return None


def _is_payloadless_start(obj):
    """True for a cursor `started` tool_call event that carries no call payload yet."""
    return obj.get("subtype") == "started" and obj.get("tool_call") is None


def scan_stream(path, limit=20, permitted_edit_paths=None, seat_cwd=None):
    """(violations, ok) for the codex JSONL stream file at `path`. Reads the whole file one line
    at a time (binary), skips unparseable lines, dedupes violations and caps them at `limit`.
    ok is True only when the whole file was read to EOF: it is False when the file cannot be
    opened, when a read fails part-way, when a line exceeds _MAX_LINE_BYTES and when the stream
    exceeds _MAX_SCAN_BYTES (the violations seen so far are kept). Never raises."""
    violations = []
    seen = set()
    pending_starts = set()

    def _record(found):
        if found is None or found in seen:
            return
        seen.add(found)
        if len(violations) < limit:
            violations.append(found)

    try:
        handle = open(path, "rb")
    except (OSError, TypeError, ValueError):
        return [], False
    try:
        with handle:
            scanned = 0
            while True:
                raw = handle.readline(_MAX_LINE_BYTES + 1)
                if not raw:
                    break
                scanned += len(raw)
                if len(raw) > _MAX_LINE_BYTES or scanned > _MAX_SCAN_BYTES:
                    return violations, False
                try:
                    obj = json.loads(raw)
                except (ValueError, RecursionError):
                    continue
                call_id = _call_id(obj)
                if call_id is not None:
                    if _is_payloadless_start(obj):
                        # A cursor start can carry its details only on completion: hold it
                        # until the same call_id's later event is judged.
                        pending_starts.add(call_id)
                        continue
                    pending_starts.discard(call_id)
                try:
                    found = outside_allowance(obj, permitted_edit_paths, seat_cwd)
                except Exception:
                    continue
                _record(found)
        for _ in pending_starts:
            _record(outside_allowance({"type": "tool_call"}))
    except (OSError, MemoryError):
        return violations, False
    return violations, True
