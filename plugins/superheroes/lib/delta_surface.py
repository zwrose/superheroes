#!/usr/bin/env python3
"""Hunk-level changed-surface + big-diff shard planning for the code leg's delta rounds (#507).

Extends the #157/#158 principle — derive the review surface from git, NEVER the fixer's
self-report — down to the hunk level. A delta round needs two things the file-level derivation
(`code_loop_plan._changed_files`) cannot give:

  - **What the fix touched vs. what it newly introduced.** Between the diff the reviewers saw
    and the post-fix tree, some hunks sit on top of the fixed findings (audit targets) and some
    are brand-new surface the fix added (scoped new-finding scan). `split_fix_surface`
    partitions them.
  - **Whether the diff is too big for one panel.** `shard_plan` groups an oversized diff by
    top-level path prefix so the driver can fan out.

stdlib only; fail-closed. ANY unparseable / ambiguous input yields the reinforced path — an
`unknown` surface (the caller escalates to a full panel) or a `big` shard verdict (the caller
fans out) — never a silently-small or silently-scoped result.
"""
import re

_DIFF_GIT = re.compile(r"^diff --git a/(.*) b/(.*)$")
# New-side (RIGHT) line range from a unified-diff hunk header: `@@ -a,b +c,d @@`.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

DEFAULT_SHARD_MAX_LINES = 1500
DEFAULT_SHARD_MAX_FILES = 20


def parse_hunks(diff_text):
    """Map each file in a unified diff to its NEW-file (RIGHT-side) hunk ranges.

    Returns {file: [{"start": int, "end": int, "text": str}]}. Returns None — never a guess — on
    any `diff --git` header it can't parse (a quoted path form `"a/x y"`, a rename/copy where the
    two paths differ), a binary hunk, or a `@@` header it can't parse. An unknown surface must
    fail toward the full-panel path, not a mis-attributed hunk set. A pure-deletion hunk (`+c,0`,
    zero new-side lines) is kept as the zero-width point (c, c), never an inverted range."""
    files = {}
    cur_hunks = None
    cur_hunk = None
    cur_file = None

    def _close():
        if cur_hunk is not None and cur_hunks is not None:
            cur_hunks.append(cur_hunk)

    for line in (diff_text or "").splitlines():
        if line.startswith("diff --git "):
            _close()
            cur_hunk = None
            m = _DIFF_GIT.match(line)
            if not m:
                return None
            a, b = m.group(1), m.group(2)
            if a != b:
                # rename/copy (or a form we can't be sure about) — don't guess at the new surface
                return None
            cur_file = b
            cur_hunks = files.setdefault(cur_file, [])
            continue
        if (line.startswith("rename from ") or line.startswith("rename to ")
                or line.startswith("copy from ") or line.startswith("copy to ")):
            return None
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            return None
        if line.startswith("@@"):
            m = _HUNK.match(line)
            if not m or cur_file is None:
                return None
            _close()
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            # A zero-count new-side hunk (`@@ ... +c,0 @@`) is a pure deletion: the new file has
            # NO lines in this hunk. `start + count - 1` would give `c - 1 < c` — an inverted
            # range that silently breaks `_overlaps` (a fixed line could never land inside it, so
            # the deletion escapes audit). Represent it instead as the zero-width point (c, c):
            # well-formed (end is never below start) and located AT the deletion point, so a
            # deletion over a fixed location still registers as an overlap and is never dropped.
            end = start + count - 1 if count else start
            cur_hunk = {"start": start, "end": end, "text": line}
            continue
        if cur_hunk is not None:
            cur_hunk["text"] += "\n" + line
    _close()
    return files


def changed_files(reviewed_diff_text, head_diff_text):
    """The FILES whose unified-diff sections differ between the reviewed diff and the post-fix head
    diff — the file-level "what the fix touched" surface, derived from git (#157/#158), never a
    self-report. Returns a set of paths, or None on ANY unparseable diff header (fail toward the
    caller's run-everything path). Reuses `parse_hunks`, so a file present on only one side, or one
    whose hunk set changed, counts as changed; identical sections on both sides do not."""
    reviewed = parse_hunks(reviewed_diff_text)
    head = parse_hunks(head_diff_text)
    if reviewed is None or head is None:
        return None
    return {f for f in set(reviewed) | set(head) if reviewed.get(f) != head.get(f)}


def fixed_locations(fix_batch, margin=10):
    """{file: [(lo, hi)]} — each finding's line ± margin. Malformed entries (no file / no int
    line) are skipped here; `split_fix_surface` is the one that maps a malformed fix_batch to an
    unknown surface."""
    out = {}
    for f in fix_batch or []:
        if not isinstance(f, dict):
            continue
        file = f.get("file")
        if not isinstance(file, str) or not file:
            continue
        try:
            line = int(f.get("line"))
        except (TypeError, ValueError):
            continue
        out.setdefault(file, []).append((line - margin, line + margin))
    return out


def _fix_batch_ok(fix_batch):
    """A usable fix_batch is a NON-EMPTY list whose every entry is a dict carrying a str file and
    an int-coercible line. Anything else is unknown surface (fail toward the full panel)."""
    if not isinstance(fix_batch, list) or not fix_batch:
        return False
    for f in fix_batch:
        if not isinstance(f, dict):
            return False
        if not isinstance(f.get("file"), str) or not f.get("file"):
            return False
        try:
            int(f.get("line"))
        except (TypeError, ValueError):
            return False
    return True


def _overlaps(hunk, ranges):
    start, end = hunk["start"], hunk["end"]
    for lo, hi in ranges:
        if start <= hi and end >= lo:
            return True
    return False


def _unknown_surface():
    return {"auditTargets": {}, "newSurface": {}, "unknown": True}


def split_fix_surface(reviewed_diff_text, head_diff_text, fix_batch):
    """Partition the changed hunks of the post-fix tree into audit targets and new surface.

    A file whose hunks DIFFER between the reviewed diff and the head diff was touched by the fix.
    Its head-diff hunks are split by overlap with `fixed_locations(fix_batch)`: hunks over the
    fixed lines are `auditTargets` (re-audit the fix), hunks elsewhere are `newSurface` (scan for
    new findings). ANY unparseable diff or malformed/empty fix_batch → {"unknown": True} with
    both maps empty, so the caller escalates to a full panel."""
    if not _fix_batch_ok(fix_batch):
        return _unknown_surface()
    reviewed = parse_hunks(reviewed_diff_text)
    head = parse_hunks(head_diff_text)
    if reviewed is None or head is None:
        return _unknown_surface()

    locs = fixed_locations(fix_batch)
    audit_targets = {}
    new_surface = {}
    for file in set(reviewed) | set(head):
        if reviewed.get(file) == head.get(file):
            continue  # section unchanged between the two diffs → the fix did not touch it
        head_hunks = head.get(file) or []
        if not head_hunks and (reviewed.get(file) or []):
            # The file was present in the reviewed diff but has NO hunks on the head side — the fix
            # REMOVED (or fully reverted) it between the reviewed and head diffs. A whole-file removal
            # has no head content to attribute to a fixed line, so it would otherwise vanish from BOTH
            # maps and escape audit AND scoped review (a deleted guard ships unseen). Fail closed into
            # `newSurface` as an explicit removal marker the scoped finder MUST scan — fresh eyes see
            # every deletion (#507 R2 v0). Never dropped from both surfaces.
            new_surface.setdefault(file, []).append(
                {"start": 0, "end": 0, "removed": True,
                 "text": "@@ file removed between the reviewed and head diffs @@"})
            continue
        file_locs = locs.get(file) or []
        for hunk in head_hunks:
            if _overlaps(hunk, file_locs):
                audit_targets.setdefault(file, []).append(hunk)
            else:
                new_surface.setdefault(file, []).append(hunk)
    return {"auditTargets": audit_targets, "newSurface": new_surface, "unknown": False}


def _top_segment(path):
    """Top-level path prefix used to group shards. A root file (no slash) shards under '.'."""
    head = path.split("/", 1)[0]
    return "." if head == path else head


def _scan_diff(diff_text):
    """(ordered files, changed-line count) for a unified diff, or None if the diff is
    unparseable / ambiguous. Mirrors `parse_hunks` strictness EXACTLY so `shard_plan` fails
    closed on the same inputs `parse_hunks` refuses: a `diff --git` header it can't parse (a
    quoted path form), a rename/copy where the two paths differ, or a binary marker. Without this
    parity an oversized rename/binary diff would scan as a small, parseable surface and skip the
    fan-out — the exact silently-small verdict the module exists to prevent. Changed lines =
    added + removed content lines (the +++/--- file headers do not count)."""
    files = []
    seen = set()
    changed = 0
    for line in (diff_text or "").splitlines():
        if line.startswith("diff --git "):
            m = _DIFF_GIT.match(line)
            if not m:
                return None
            a, b = m.group(1), m.group(2)
            if a != b:
                # rename/copy (or a form we can't be sure about) — fail closed, don't guess
                return None
            path = b
            if path not in seen:
                seen.add(path)
                files.append(path)
        elif (line.startswith("rename from ") or line.startswith("rename to ")
                or line.startswith("copy from ") or line.startswith("copy to ")):
            return None
        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            return None
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+") or line.startswith("-"):
            changed += 1
    return files, changed


def shard_plan(diff_text, max_lines=None, max_files=None):
    """Big-diff shard plan. `big` iff the changed (+/-) line count exceeds max_lines OR the
    changed file count exceeds max_files. Shards group the changed files by top-level path
    segment in deterministic (sorted) order. An unparseable diff → {"big": True, "shards": [],
    "unknown": True} — fail toward the reinforced (fan-out) path, never silently small."""
    max_lines = DEFAULT_SHARD_MAX_LINES if max_lines is None else max_lines
    max_files = DEFAULT_SHARD_MAX_FILES if max_files is None else max_files
    scanned = _scan_diff(diff_text)
    if scanned is None:
        return {"big": True, "shards": [], "unknown": True}
    files, changed_lines = scanned
    groups = {}
    for f in files:
        groups.setdefault(_top_segment(f), []).append(f)
    shards = [{"key": key, "files": sorted(groups[key])} for key in sorted(groups)]
    changed_files = len(files)
    big = changed_lines > max_lines or changed_files > max_files
    return {
        "big": big,
        "changedLines": changed_lines,
        "changedFiles": changed_files,
        "shards": shards,
        "thresholds": {"maxLines": max_lines, "maxFiles": max_files},
    }
