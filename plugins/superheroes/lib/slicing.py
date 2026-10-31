#!/usr/bin/env python3
"""Size slices of a big change for first-round review, and what the slice reviewers left unread.

Pure: no git, no I/O. A change above the countable-lines bar is cut into slices that each stay at or under
the bar, every changed head line is owed to exactly one slice, and what the slice readers did not read is
worked out per seat. Every function fails closed: a malformed input gives more slicing or more unread,
never an exception. stdlib and sibling lib modules only.
"""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import countable_lines  # noqa: E402 - the bar, the diff sections and the range helpers

_HUNK_HEAD_RE = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", re.S)
# Files the counter leaves out of the count: they weigh nothing but a reviewer still sees them.
_ZERO_WHY = frozenset({"deleted-whole", "moved-unchanged", "lock-file", "generated"})
_PROBE_HEADER = "diff --git a/f b/f\n"


# --------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------

def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _bar():
    """The bar, read at call time from its one home."""
    bar = countable_lines.COUNTABLE_LINES_BAR
    return bar if _is_int(bar) and bar >= 1 else 1


def _merge_ranges(ranges):
    out = []
    for start, end in sorted((r[0], r[1]) for r in ranges):
        if out and start <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def _clean_ranges(lines):
    """``(merged valid ranges, all_valid)`` of one ``lines`` value; a non-list gives ``([], False)``."""
    # axis: only a list of well-formed [start, end] ranges is read; anything else yields no range.
    if not isinstance(lines, (list, tuple)):
        return [], False
    good = [[r[0], r[1]] for r in lines if countable_lines._valid_range(r)]
    return _merge_ranges(good), len(good) == len(lines)


def _count_lines(ranges):
    return sum(end - start + 1 for start, end in ranges)


def _named(file):
    return isinstance(file, str) and bool(file.strip())


def _readable(count_result):
    """True when ``count_result`` is a dict with an int ``countable`` >= 0, a ``files`` list and a sane ``unsettled``."""
    # axis: an unreadable count never excuses a change from slicing; the caller falls back to raw changed lines.
    if not isinstance(count_result, dict):
        return False
    countable = count_result.get("countable")
    if not (_is_int(countable) and countable >= 0):
        return False
    if not isinstance(count_result.get("files"), list):
        return False
    return isinstance(count_result.get("unsettled", []), list)


def _rows_by_file(count_result):
    """``{file: [row, ...]}`` in row order, from the well-formed rows of a readable count."""
    by_file = {}
    for row in count_result["files"]:
        if isinstance(row, dict) and isinstance(row.get("file"), str):
            by_file.setdefault(row["file"], []).append(row)
    return by_file


def _unsettled_files(count_result):
    found = set()
    for entry in count_result.get("unsettled", []):
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            found.add(entry["file"])
    return found


def _zero_files(count_result):
    """The files the counter left out of the count (all their rows excluded, none unsettled); empty when the count is unreadable."""
    # axis: with no readable count no file is known to weigh nothing, so every file is weighted.
    if not _readable(count_result):
        return set()
    unsettled = _unsettled_files(count_result)
    return {
        file
        for file, rows in _rows_by_file(count_result).items()
        if file not in unsettled and all(r.get("counted") is False and r.get("why") in _ZERO_WHY for r in rows)
    }


# --------------------------------------------------------------------------------------------
# Hunks
# --------------------------------------------------------------------------------------------

def _split_hunks(text):
    """``(header, [hunk text, ...])`` of one section's text: everything before the first ``@@`` line, then each hunk."""
    lines = countable_lines._lines_keepends(text)
    starts = [i for i, line in enumerate(lines) if _HUNK_HEAD_RE.match(line)]
    if not starts:
        return text, []
    bounds = starts + [len(lines)]
    header = "".join(lines[: starts[0]])
    return header, ["".join(lines[bounds[k] : bounds[k + 1]]) for k in range(len(starts))]


def _changed_count(hunk_text):
    return sum(1 for line in countable_lines._lines_keepends(hunk_text)[1:] if line[:1] in ("+", "-"))


def _hunk_heads(hunk_text):
    """The head line of each ``+``/``-`` line of one hunk, in order, exactly as the section parser assigns them."""
    sections = countable_lines.parse_sections(_PROBE_HEADER + hunk_text)
    return list(sections[0]["headLines"]) if sections else []


def _cut_runs(hunk_text, bar):
    """``[(run text, head lines of its +/- lines), ...]``: the hunk cut into runs of at most ``bar`` +/- lines, each
    a valid hunk with its own header."""
    lines = countable_lines._lines_keepends(hunk_text)
    found = _HUNK_HEAD_RE.match(lines[0])
    old_start, old_len = int(found.group(1)), 1 if found.group(2) is None else int(found.group(2))
    new_start, new_len = int(found.group(3)), 1 if found.group(4) is None else int(found.group(4))
    old_next = old_start + 1 if old_len == 0 else old_start
    new_next = new_start + 1 if new_len == 0 else new_start
    heads = _hunk_heads(hunk_text)
    runs = []
    cur = {"lines": [], "old": 0, "new": 0, "changed": 0, "heads": []}
    seen = 0
    for line in lines[1:]:
        lead = line[:1]
        if lead == "+" or lead == "-":
            if cur["changed"] >= bar:
                runs.append(cur)
                cur = {"lines": [], "old": 0, "new": 0, "changed": 0, "heads": []}
            cur["changed"] += 1
            if seen < len(heads):
                cur["heads"].append(heads[seen])
            seen += 1
            cur["old" if lead == "-" else "new"] += 1
        elif lead == " " or line == "\n":
            cur["old"] += 1
            cur["new"] += 1
        cur["lines"].append(line)
    runs.append(cur)
    out = []
    for k, run in enumerate(runs):
        o_start = old_next if run["old"] > 0 else max(old_next - 1, 0)
        n_start = new_next if run["new"] > 0 else max(new_next - 1, 0)
        rest = found.group(5) if k == 0 else "\n"
        header = "@@ -%d,%d +%d,%d @@%s" % (o_start, run["old"], n_start, run["new"], rest)
        out.append((header + "".join(run["lines"]), run["heads"]))
        old_next += run["old"]
        new_next += run["new"]
    return out


# --------------------------------------------------------------------------------------------
# Units and slices
# --------------------------------------------------------------------------------------------

def _unit(weight, file, ranges, key, header, hunks):
    """One packable piece: ``ranges`` are its coverage obligation (``[]`` for a file-level one), ``hunks`` its
    ``(order, text)`` pieces under the section ``header``."""
    return {"weight": weight, "file": file, "ranges": ranges, "key": key, "header": header, "hunks": hunks}


def _weigh(section, row, unsettled, readable):
    """``(weight, copy_lines)`` of one section: ``copy_lines`` is the whole-file line count of an unproven copy."""
    raw = section["added"] + section["removed"]
    # axis: a file the counter did not settle, or that has no usable row, counts at its raw changed lines.
    if not readable or unsettled or row is None:
        return raw, None
    if row.get("counted") is True:
        lines = row.get("lines")
        if section["copied"] and _is_int(lines) and lines >= 0:
            return lines, lines
        return raw, None
    if row.get("why") in _ZERO_WHY:
        return 0, None
    return raw, None


def _section_units(idx, section, weight, copy_lines, bar):
    file = section["file"]
    text = section["text"]
    if copy_lines is not None and copy_lines >= 1:
        # An unproven copy owes the whole head file, in chunks of at most ``bar`` lines, each carrying the section diff.
        units = []
        start = 1
        while start <= copy_lines:
            end = min(copy_lines, start + bar - 1)
            units.append(_unit(end - start + 1, file, [[start, end]], idx, text, []))
            start = end + 1
        return units
    file_level = section["unreadable"] or section["binary"] or section["status"] == "deleted" or not section["headLines"]
    header, hunks = _split_hunks(text)
    if weight == 0 or not hunks or (file_level and weight <= bar):
        ranges = [] if file_level else _merge_numbers(section["headLines"])
        return [_unit(weight, file, ranges, idx, text, [])]
    units = []
    for h, hunk in enumerate(hunks):
        changed = _changed_count(hunk)
        if changed <= bar:
            pieces = [(hunk, _hunk_heads(hunk))]
        else:
            pieces = _cut_runs(hunk, bar)
        for r, (piece, heads) in enumerate(pieces):
            ranges = [] if file_level else _merge_numbers(heads)
            units.append(_unit(_changed_count(piece), file, ranges, idx, header, [((h, r), piece)]))
    return units


def _merge_numbers(numbers):
    return countable_lines._merge_numbers(numbers)


def _pack(units, bar):
    slices = []
    cur = []
    weight = 0
    for unit in units:
        if cur and weight + unit["weight"] > bar:
            slices.append(cur)
            cur = []
            weight = 0
        cur.append(unit)
        weight += unit["weight"]
    if cur:
        slices.append(cur)
    return slices


def _assemble(packed, prefix):
    """The slice dicts for packed unit lists: ids, weights, merged parts and the slice's own diff. A head line
    is owed to the first slice that reaches it, so no line is in two slices' parts."""
    claimed = {}
    out = []
    for k, units in enumerate(packed, 1):
        obligations = []
        groups = {}
        for unit in units:
            ranges = unit["ranges"]
            if ranges:
                taken = claimed.get(unit["file"], [])
                claimed[unit["file"]] = _merge_ranges(taken + ranges)
                ranges = countable_lines._subtract(ranges, taken)
            obligations.append({"file": unit["file"], "lines": ranges})
            group = groups.setdefault(unit["key"], {"header": unit["header"], "hunks": {}})
            for order, hunk in unit["hunks"]:
                group["hunks"].setdefault(order, hunk)
        pieces = []
        for group in groups.values():
            text = group["header"] + "".join(group["hunks"][o] for o in sorted(group["hunks"]))
            if text and not text.endswith("\n"):
                text += "\n"
            pieces.append(text)
        out.append({
            "id": "%s%d" % (prefix, k),
            "weight": sum(u["weight"] for u in units),
            "parts": merge_parts(obligations),
            "diff": "".join(pieces),
        })
    return out


# --------------------------------------------------------------------------------------------
# The public functions
# --------------------------------------------------------------------------------------------

def plan(diff_text, count_result, proven=()):
    """Cut ``diff_text`` into slices of at most the bar when its weight is above the bar: ``{"sliced", "weight", "countable", "bar", "slices"}``."""
    bar = _bar()
    sections = countable_lines.parse_sections(countable_lines.reviewer_diff(diff_text, proven))
    readable = _readable(count_result)
    rows = _rows_by_file(count_result) if readable else {}
    unsettled = _unsettled_files(count_result) if readable else set()
    used = {}
    infos = []
    extra = 0
    raw_total = 0
    for section in sections:
        file = section["file"]
        row = None
        if readable:
            pos = used.get(file, 0)
            used[file] = pos + 1
            file_rows = rows.get(file, [])
            row = file_rows[pos] if pos < len(file_rows) else None
        in_unsettled = file in unsettled
        weight, copy_lines = _weigh(section, row, in_unsettled, readable)
        if in_unsettled:
            extra += weight
        raw_total += weight
        infos.append((section, weight, copy_lines))
    countable = count_result["countable"] + extra if readable else raw_total
    sliced = countable > bar
    slices = []
    if sliced:
        units = []
        for idx, (section, weight, copy_lines) in enumerate(infos):
            units.extend(_section_units(idx, section, weight, copy_lines, bar))
        slices = _assemble(_pack(units, bar), "s")
    return {"sliced": sliced, "weight": countable, "countable": countable, "bar": bar, "slices": slices}


def merge_parts(obligations):
    """The ``{"file", "lines"}`` parts of ``obligations`` in first-seen file order with ranges merged; a file with no range keeps ``lines: []``."""
    # axis: only a list of obligations is read; an entry without a named file cannot be recorded and is skipped.
    if not isinstance(obligations, (list, tuple)):
        return []
    files = {}
    for obligation in obligations:
        if not isinstance(obligation, dict) or not _named(obligation.get("file")):
            continue
        ranges, _ = _clean_ranges(obligation.get("lines"))
        files.setdefault(obligation["file"], []).extend(ranges)
    return [{"file": file, "lines": _merge_ranges(ranges)} for file, ranges in files.items()]


def unread_obligations(assigned, read_lists):
    """``[{"seat", "file", "lines"}]``: each seat's assigned parts less that seat's own read list; a seat missing from ``read_lists`` read nothing."""
    # axis: only a dict of seats is read; a seat's parts must be a list, else it names nothing to owe.
    if not isinstance(assigned, dict):
        return []
    out = []
    for seat, parts in assigned.items():
        if not isinstance(parts, (list, tuple)):
            continue
        own = read_lists.get(seat) if isinstance(read_lists, dict) else None
        # axis: a seat's read list counts only as a list; any other value means that seat read nothing.
        taken = countable_lines._read_ranges([own]) if isinstance(own, list) else {}
        for part in parts:
            if not isinstance(part, dict) or not _named(part.get("file")):
                continue
            file = part["file"]
            ranges, _ = _clean_ranges(part.get("lines"))
            if ranges:
                left = countable_lines._subtract(ranges, taken.get(file, []))
                if left:
                    out.append({"seat": seat, "file": file, "lines": left})
            elif file not in taken:
                # A file-level part (or one whose ranges are unreadable) is met only by an entry naming the file.
                out.append({"seat": seat, "file": file, "lines": []})
    return out


def unread_share(unread_parts, plan_obj, count_result):
    """``{"unreadLines", "countableLines", "parts"}`` for the unread parts, counting only files that weigh something and never above the countable lines."""
    parts = merge_parts(unread_parts)
    countable = 0
    # axis: the share never exceeds the countable lines, and a plan that cannot be read has none.
    if isinstance(plan_obj, dict) and _is_int(plan_obj.get("countable")) and plan_obj["countable"] >= 0:
        countable = plan_obj["countable"]
    zero = _zero_files(count_result)
    unread = sum(_count_lines(part["lines"]) for part in parts if part["file"] not in zero)
    return {"unreadLines": min(unread, countable), "countableLines": countable, "parts": parts}


def _file_views(plan_obj):
    """``{file: {"header", "hunks": [{"text", "heads"}], "copied"}}`` rebuilt from the slice diffs of ``plan_obj``."""
    views = {}
    slices = plan_obj.get("slices") if isinstance(plan_obj, dict) else None
    # axis: a plan without a slice list shows no file, so no unread part can be re-sliced from it.
    if not isinstance(slices, list):
        return views
    for entry in slices:
        diff = entry.get("diff") if isinstance(entry, dict) else None
        for section in countable_lines.parse_sections(diff):
            view = views.setdefault(section["file"], {"header": None, "hunks": [], "seen": set(), "copied": False})
            header, hunks = _split_hunks(section["text"])
            if view["header"] is None:
                view["header"] = header
            view["copied"] = view["copied"] or section["copied"]
            for hunk in hunks:
                if hunk not in view["seen"]:
                    view["seen"].add(hunk)
                    view["hunks"].append({"text": hunk, "heads": set(_hunk_heads(hunk))})
    return views


def _chunk_ranges(ranges, bar):
    chunks = []
    cur = []
    room = bar
    for start, end in ranges:
        while start <= end:
            take = min(room, end - start + 1)
            cur.append([start, start + take - 1])
            start += take
            room -= take
            if room == 0:
                chunks.append(cur)
                cur = []
                room = bar
    if cur:
        chunks.append(cur)
    return chunks


def slice_parts_for(unread_parts, plan_obj, count_result):
    """Slices (ids ``u1``...) cut from the unread parts for the next wave, each at most the bar, their diffs restricted to the hunks that touch the unread ranges."""
    bar = _bar()
    zero = _zero_files(count_result)
    views = _file_views(plan_obj)
    units = []
    for part in merge_parts(unread_parts):
        file = part["file"]
        view = views.get(file)
        # axis: a file no slice ever showed (a proven copy) has no diff to re-slice and gets no slice.
        if view is None:
            continue
        everything = [(i, h["text"]) for i, h in enumerate(view["hunks"])]
        if not part["lines"]:
            units.append(_unit(0, file, [], file, view["header"], everything))
            continue
        chunks = [part["lines"]] if file in zero else _chunk_ranges(part["lines"], bar)
        for chunk in chunks:
            picked = [
                (i, h["text"])
                for i, h in enumerate(view["hunks"])
                if view["copied"] or any(s <= n <= e for n in h["heads"] for s, e in chunk)
            ]
            weight = 0 if file in zero else _count_lines(chunk)
            units.append(_unit(weight, file, chunk, file, view["header"], picked or everything))
    return _assemble(_pack(units, bar), "u")
