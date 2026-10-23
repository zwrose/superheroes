#!/usr/bin/env python3
"""A minimal read-only MCP file server (#2071): the only tool source of a codex review seat.

Newline-delimited JSON-RPC 2.0 on stdin/stdout. Three tools — read_file, list_dir, search — read
files and nothing else: the module writes no file and starts no other program. Reads are not
restricted to the root (parity with the read-only sandbox, which reads any path); relative paths
resolve against the root, `--root DIR` or the working directory.

Run as `python3 -I -B seat_read_tool.py [--root DIR]`. stdlib only. The loop never raises."""
import json
import os
import re
import sys

DEFAULT_PROTOCOL = "2025-06-18"
READ_LIMIT_DEFAULT = 800
READ_LIMIT_MAX = 2000
LIST_CAP = 1000
SEARCH_DEFAULT = 200
SEARCH_MAX = 1000
SEARCH_FILE_MAX_BYTES = 2 * 1024 * 1024
SEARCH_TEXT_CAP = 300
# A response must stay far under the 1 MiB record line the allowance scan accepts, even after JSON
# escaping (up to 6x for a control character): the text of one reply is held to RESPONSE_BYTE_BUDGET
# UTF-8 bytes, and one file line to READ_LINE_CHAR_CAP characters.
RESPONSE_BYTE_BUDGET = 100000
READ_LINE_CHAR_CAP = 2000
# Bytes held back from a read_file page for its continuation footer, so the budget backstop never
# cuts the "offset=N" instruction away.
READ_FOOTER_RESERVE = 128

_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a text file: a 1-based window of lines, each prefixed with its "
                       "line number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (relative to the root)."},
                "offset": {"type": "integer", "description": "First line, 1-based (default 1)."},
                "limit": {"type": "integer",
                          "description": "Lines to return (default %d, max %d)."
                                         % (READ_LIMIT_DEFAULT, READ_LIMIT_MAX)},
                "column": {"type": "integer",
                           "description": "Characters to skip at the start of the first line "
                                          "returned, 0-based (default 0); a line longer than "
                                          "%d characters is cut and the cut names the column to "
                                          "continue from." % READ_LINE_CHAR_CAP},
            },
            "required": ["path"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "list_dir",
        "description": "List a directory: sorted entries, directories suffixed with /.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default .)."},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search",
        "description": "Regex search over text files under a file or directory; results are "
                       "path:line: text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python regular expression."},
                "path": {"type": "string", "description": "File or directory (default .)."},
                "max_results": {"type": "integer",
                                "description": "Result cap (default %d, max %d)."
                                               % (SEARCH_DEFAULT, SEARCH_MAX)},
            },
            "required": ["pattern"],
        },
        "annotations": {"readOnlyHint": True},
    },
]


class _ToolError(Exception):
    pass


def _resolve(root, path):
    if not isinstance(path, str) or not path:
        raise _ToolError("path must be a string with at least one character")
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(root, path))


def _int_arg(args, key, default, low, high):
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _ToolError("%s must be an integer" % key)
    return max(low, min(high, value))


def _read_file(root, args):
    target = _resolve(root, args.get("path"))
    offset = _int_arg(args, "offset", 1, 1, 2 ** 62)
    limit = _int_arg(args, "limit", READ_LIMIT_DEFAULT, 1, READ_LIMIT_MAX)
    column = _int_arg(args, "column", 0, 0, 2 ** 62)
    if os.path.isdir(target):
        raise _ToolError("%s is a directory; use list_dir" % target)
    out = []
    used = 0
    more = False
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, start=1):
                if number < offset:
                    continue
                if len(out) >= limit:
                    more = True
                    break
                text = line.rstrip("\r\n")
                start = column if number == offset else 0
                if start:
                    text = text[start:]
                if len(text) > READ_LINE_CHAR_CAP:
                    text = text[:READ_LINE_CHAR_CAP] + (
                        "...[line truncated: %d more characters; call read_file again with "
                        "offset=%d and column=%d]"
                        % (len(text) - READ_LINE_CHAR_CAP, number, start + READ_LINE_CHAR_CAP))
                rendered = "%6d\t%s" % (number, text)
                size = len(rendered.encode("utf-8", "replace")) + 1
                if out and used + size > RESPONSE_BYTE_BUDGET - READ_FOOTER_RESERVE:
                    more = True
                    limit = number - offset
                    break
                used += size
                out.append(rendered)
    except OSError as exc:
        raise _ToolError("cannot read %s: %s" % (target, exc.strerror or exc))
    text = "\n".join(out)
    if more:
        text += "\n[more lines remain; call read_file again with offset=%d]" % (offset + limit)
    elif not out:
        text = "[no lines at offset %d]" % offset
    return text


def _list_dir(root, args):
    target = _resolve(root, args.get("path", "."))
    try:
        names = sorted(os.listdir(target))
    except OSError as exc:
        raise _ToolError("cannot list %s: %s" % (target, exc.strerror or exc))
    lines = []
    used = 0
    shown = 0
    for name in names[:LIST_CAP]:
        entry = name + "/" if os.path.isdir(os.path.join(target, name)) else name
        used += len(entry.encode("utf-8", "replace")) + 1
        if used > RESPONSE_BYTE_BUDGET:
            break
        lines.append(entry)
        shown += 1
    if len(names) > shown:
        lines.append("[%d more entries not shown]" % (len(names) - shown))
    return "\n".join(lines) if lines else "[no entries]"


def _search_files(target):
    if os.path.isfile(target):
        yield target
        return
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def _search(root, args):
    pattern = args.get("pattern")
    if not isinstance(pattern, str):
        raise _ToolError("pattern must be a string")
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise _ToolError("bad regular expression: %s" % exc)
    target = _resolve(root, args.get("path", "."))
    if not os.path.exists(target):
        raise _ToolError("no such path: %s" % target)
    cap = _int_arg(args, "max_results", SEARCH_DEFAULT, 1, SEARCH_MAX)
    results = []
    used = 0
    for file_path in _search_files(target):
        try:
            if os.path.islink(file_path) or os.path.getsize(file_path) > SEARCH_FILE_MAX_BYTES:
                continue
            with open(file_path, "r", encoding="utf-8") as handle:
                for number, line in enumerate(handle, start=1):
                    if regex.search(line):
                        text = line.rstrip("\r\n")
                        if len(text) > SEARCH_TEXT_CAP:
                            text = text[:SEARCH_TEXT_CAP]
                        entry = "%s:%d: %s" % (file_path, number, text)
                        used += len(entry.encode("utf-8", "replace")) + 1
                        if used > RESPONSE_BYTE_BUDGET:
                            return "\n".join(results) + "\n[response size budget reached]"
                        results.append(entry)
                        if len(results) >= cap:
                            return "\n".join(results) + "\n[result cap %d reached]" % cap
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(results) if results else "[no matches]"


_HANDLERS = {"read_file": _read_file, "list_dir": _list_dir, "search": _search}


def _call_tool(root, params):
    if not isinstance(params, dict):
        return _tool_result("params must be an object", True)
    name = params.get("name")
    args = params.get("arguments", {})
    if args is None:
        args = {}
    handler = _HANDLERS.get(name) if isinstance(name, str) else None
    if handler is None:
        return _tool_result("unknown tool: %s" % (name,), True)
    if not isinstance(args, dict):
        return _tool_result("arguments must be an object", True)
    try:
        return _tool_result(handler(root, args), False)
    except _ToolError as exc:
        return _tool_result(str(exc), True)
    except Exception as exc:
        return _tool_result("tool failed: %s" % exc, True)


def _bounded(text):
    """`text` held to RESPONSE_BYTE_BUDGET UTF-8 bytes (a backstop; the tools budget themselves)."""
    text = str(text)
    raw = text.encode("utf-8", "replace")
    if len(raw) <= RESPONSE_BYTE_BUDGET:
        return text
    return raw[:RESPONSE_BYTE_BUDGET].decode("utf-8", "ignore") + "\n[response truncated]"


def _tool_result(text, is_error):
    text = _bounded(text)
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle_message(root, msg):
    """The reply object for one parsed JSON-RPC message, or None when it gets no reply."""
    if not isinstance(msg, dict):
        return _error(None, -32600, "invalid request")
    method = msg.get("method")
    if "id" not in msg:
        return None
    msg_id = msg["id"]
    params = msg.get("params")
    if method == "initialize":
        version = params.get("protocolVersion") if isinstance(params, dict) else None
        result = {
            "protocolVersion": version if isinstance(version, str) and version
            else DEFAULT_PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "superheroes_read", "version": "1"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": _TOOLS}
    elif method == "tools/call":
        result = _call_tool(root, params)
    else:
        return _error(msg_id, -32601, "method not found: %s" % (method,))
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def serve(root, stdin, stdout):
    for raw in stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except (ValueError, RecursionError):
            reply = _error(None, -32700, "parse error")
        else:
            try:
                reply = handle_message(root, msg)
            except Exception as exc:
                msg_id = msg.get("id") if isinstance(msg, dict) else None
                reply = _error(msg_id, -32603, "internal error: %s" % exc)
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = None
    if "--root" in argv:
        index = argv.index("--root")
        if index + 1 < len(argv):
            root = argv[index + 1]
    if not root:
        root = os.getcwd()
    stdin = open(sys.stdin.fileno(), "r", encoding="utf-8", errors="replace", closefd=False)
    stdout = open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)
    serve(root, stdin, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
