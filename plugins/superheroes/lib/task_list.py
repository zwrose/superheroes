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


def parse(body):
    """Return an ordered list of {"id": "<n>", "title": "<title>"} — one per task heading, in
    document order. A non-string or a heading-less body returns []."""
    if not isinstance(body, str):
        return []
    tasks = []
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _TASK_RE.match(line)
        if m:
            tasks.append({"id": m.group(1), "title": m.group(2).strip()})
    return tasks
