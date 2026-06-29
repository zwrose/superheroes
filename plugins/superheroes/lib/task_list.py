# plugins/superheroes/lib/task_list.py
"""Enumerate the executable tasks from an approved tasks definition-doc body. Pure + fail-closed:
a malformed/empty doc yields [] (the caller finishes-without-building, UFR-8), never an invented
task. A task is a top-level '### Task N: Title' heading in the writing-plans body (CONVENTIONS
§3.2); headings inside fenced code blocks are ignored."""
import re

# Separator-tolerance: accept colon, em-dash (U+2014), en-dash (U+2013), or plain hyphen as the
# separator between the task number and title. The canonical authored format is colon
# ('### Task N: Title'); the alternatives are tolerated to survive format drift by the produce
# leaf. The produce-leaf prompt MUST keep instructing colon — this regex is a safety net only.
_TASK_RE = re.compile(r"^###\s+Task\s+(\d+)\s*[:—–-]\s*(.+?)\s*$")

# A line that LOOKS like a task heading regardless of the separator (or lack of one) — used by the
# raw-heading count to distinguish "doc has zero task headings" from "format mismatch / silent parse
# failure". Deliberately laxer than _TASK_RE: it must catch a real `### Task N` the parser REJECTED
# for a format reason (a bad separator), so the silent-zero guard still fires.
_RAW_HEADING_RE = re.compile(r"^###\s+Task\s+\d+")


def unfenced_lines(body):
    """Yield the lines of `body` that are OUTSIDE fenced code blocks, in document order.

    The single source of fence awareness for the module: both `parse` and the raw-heading count
    iterate these lines so they measure over the SAME (unfenced) text and cannot drift. A non-string
    body yields nothing. Fence toggles (``` lines, after optional leading whitespace) are themselves
    skipped, matching CONVENTIONS §3.2 ("headings inside fenced code blocks are ignored")."""
    if not isinstance(body, str):
        return
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield line


def parse(body):
    """Return an ordered list of {"id": "<n>", "title": "<title>"} — one per task heading, in
    document order. A non-string or a heading-less body returns []."""
    tasks = []
    for line in unfenced_lines(body):
        m = _TASK_RE.match(line)
        if m:
            tasks.append({"id": m.group(1), "title": m.group(2).strip()})
    return tasks


def raw_heading_count(body):
    """Count lines that LOOK like a task heading (`### Task N`, any/no separator) OUTSIDE code
    fences. Computed over the same unfenced lines as `parse`, so a fenced `### Task N` example does
    not inflate the count (no false "format mismatch"), while a real unfenced `### Task N` the parser
    rejected for a format reason is still counted (the silent-zero guard still fires)."""
    return sum(1 for line in unfenced_lines(body) if _RAW_HEADING_RE.match(line))
