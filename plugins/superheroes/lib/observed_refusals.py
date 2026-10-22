#!/usr/bin/env python3
"""Read the refusals a Claude Code subagent transcript shows, and compare them with a report (#2046).

`read_transcript` turns a subagent transcript (JSONL) into the tool calls the harness refused, by the
closed, best-effort `MARKERS` list: a refused call is an assistant `tool_use` row followed by a user
`tool_result` row with `is_error` true whose text opens with one of the harness's refusal messages.
Anything else that errors (a command that exited non-zero, a stale edit) ran and failed, and is not
a refusal. `unreported` lists the observed refusals a fixer's `refusals` list does not account for.
Leaf module: stdlib only, imports nothing from `lib/`. Every public function never raises.
"""
import json
import os
from collections import Counter

# The three `command_refusals.REFUSED_BY` values, duplicated here because this module is a leaf.
PERMISSION = "permission"
HOOK = "hook"

FAULT_MISSING = "transcript-missing"
FAULT_UNREADABLE = "transcript-unreadable"
FAULT_UNPARSEABLE = "transcript-unparseable"

UNKNOWN_CALL = "<unknown tool call>"

# One home of the closed marker list. Each row is (prefix, contains, refusedBy): a tool_result text
# (leading whitespace and a leading "Error: " stripped) matches a row when it starts with `prefix`
# and, if `contains` is not empty, contains at least one of its fragments. No catch-all row exists.
MARKERS = (
    ("Permission to use ", (" has been denied",), PERMISSION),
    ("PreToolUse:", (" hook error:", " hook blocking error"), HOOK),
    ("Permission for this action was denied by the Claude Code auto mode classifier", (), PERMISSION),
    ("Permission for this command was denied by a built-in Claude Code safety check", (), PERMISSION),
    ("<tool_use_error>Blocked:", (), PERMISSION),
    ("The user doesn't want to proceed with this tool use", (), PERMISSION),
    ("This command requires approval", (), PERMISSION),
    ("This Bash command contains multiple operations", ("requires approval",), PERMISSION),
)

_ERROR_PREFIX = "Error: "


def _result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return ""


def _refused_by(text):
    """The `refusedBy` value of the first marker row ``text`` matches, else ``None``."""
    text = text.lstrip()
    if text.startswith(_ERROR_PREFIX):
        text = text[len(_ERROR_PREFIX):]
    for prefix, contains, refused_by in MARKERS:
        if not text.startswith(prefix):
            continue
        if contains and not any(fragment in text for fragment in contains):
            continue
        return refused_by
    return None


def _command_of(tool_input):
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "path"):
            if isinstance(tool_input.get(key), str):
                return tool_input[key]
    return json.dumps(tool_input, sort_keys=True, default=str)


def _blocks(row):
    message = row.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _fault_of(path):
    if path is None:
        return FAULT_MISSING
    if not os.path.lexists(path):
        return FAULT_MISSING
    if not os.path.isfile(path):
        return FAULT_UNREADABLE
    return None


def _read_rows(path):
    """Return ``(rows, fault)``: the JSON objects of the file, in order, or a fault token."""
    fault = _fault_of(path)
    if fault:
        return [], fault
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return [], FAULT_UNREADABLE
    rows = []
    has_content = False
    for line in lines:
        if not line.strip():
            continue
        has_content = True
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    if has_content and not rows:
        return [], FAULT_UNPARSEABLE
    return rows, None


def read_transcript(path):
    """Return ``(observed, fault)`` for the transcript at ``path``. Never raises.

    ``observed`` is a list of ``{"tool", "command", "refusedBy"}`` in transcript order; ``fault`` is
    ``None`` or one of the ``transcript-*`` tokens, and then ``observed`` is ``[]``.
    """
    try:
        rows, fault = _read_rows(path)
        if fault:
            return [], fault
        tools = {}
        observed = []
        for row in rows:
            kind = row.get("type")
            for block in _blocks(row):
                if kind == "assistant" and block.get("type") == "tool_use":
                    if isinstance(block.get("id"), str):
                        tools[block["id"]] = (block.get("name"), block.get("input"))
                elif kind == "user" and block.get("type") == "tool_result" and block.get("is_error") is True:
                    refused_by = _refused_by(_result_text(block.get("content")))
                    if refused_by is None:
                        continue
                    call_id = block.get("tool_use_id")
                    if isinstance(call_id, str) and call_id in tools:
                        name, tool_input = tools[call_id]
                        observed.append({"tool": name, "command": _command_of(tool_input), "refusedBy": refused_by})
                    else:
                        observed.append({"tool": None, "command": UNKNOWN_CALL, "refusedBy": refused_by})
        return observed, None
    except Exception:  # noqa: BLE001 — a reader must never raise
        return [], FAULT_UNREADABLE


def unreported(observed, refusals):
    """Return the ``observed`` entries ``refusals`` does not account for. Never raises.

    Matching is by ``command`` with surrounding whitespace stripped, multiset semantics: two observed
    refusals of one command need two reported entries. Non-dict entries and a non-list ``refusals``
    report nothing.
    """
    try:
        if not isinstance(observed, list):
            return []
        reported = Counter()
        if isinstance(refusals, list):
            for entry in refusals:
                if isinstance(entry, dict) and isinstance(entry.get("command"), str):
                    reported[entry["command"].strip()] += 1
        missing = []
        for entry in observed:
            if not isinstance(entry, dict):
                continue
            command = entry.get("command")
            key = command.strip() if isinstance(command, str) else command
            try:
                if reported[key] > 0:
                    reported[key] -= 1
                    continue
            except TypeError:
                pass
            missing.append(entry)
        return missing
    except Exception:  # noqa: BLE001 — a comparison must never raise
        return []
