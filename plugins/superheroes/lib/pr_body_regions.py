"""PR-body region reader — reads the named PR-body regions (CONVENTIONS §10.7 markers).

The vet slot and the stack check read the ``advisor-vet`` region through here. stdlib
only, plus ``md_fence`` for live/inert line classification."""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import md_fence  # noqa: E402

REGION_MARKERS = {
    "dod-table": "<!-- superheroes:dod-table -->",
    "build-record": "<!-- superheroes:build-record -->",
    "degradations": "<!-- superheroes:degradations -->",
    "advisor-vet": "<!-- superheroes:advisor-vet -->",
}


class _BodyRefusal(Exception):
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _heading_level(line):
    stripped = line.strip()
    match = re.match(r"^(#{1,6})\s", stripped)
    return len(match.group(1)) if match else None


def _next_heading_boundary(text, section_level, scan, start_line):
    """Offset in text where a same-or-higher-level live heading begins after the opener."""
    offset = 0
    first_heading_seen = False
    for i, line in enumerate(text.splitlines(keepends=True)):
        body_line = start_line + i
        if body_line < len(scan.inert) and scan.inert[body_line]:
            offset += len(line)
            continue
        stripped = line.strip()
        if stripped:
            level = _heading_level(stripped)
            if level is not None:
                if not first_heading_seen:
                    first_heading_seen = True
                elif level <= section_level:
                    return offset
        offset += len(line)
    return len(text)


def _first_any_heading_offset(text, scan, start_line):
    """Offset in text where the first live heading of any level begins."""
    offset = 0
    for i, line in enumerate(text.splitlines(keepends=True)):
        body_line = start_line + i
        if body_line < len(scan.inert) and scan.inert[body_line]:
            offset += len(line)
            continue
        stripped = line.strip()
        if stripped and _heading_level(stripped) is not None:
            return offset
        offset += len(line)
    return len(text)


def _region_heading_bound(text, opening_level, scan, start_line):
    """Offset where the region's heading-boundary ends (exclusive)."""
    if opening_level is not None:
        return _next_heading_boundary(text, opening_level, scan, start_line)
    return _first_any_heading_offset(text, scan, start_line)


def _line_index_at_offset(lines, offset):
    pos = 0
    for i, line in enumerate(lines):
        if pos == offset:
            return i
        if pos < offset < pos + len(line):
            return i
        pos += len(line)
    return len(lines)


def _bare_lines_from_body(body):
    lines = body.splitlines(keepends=True)
    bare = []
    for line in lines:
        if line.endswith("\r\n"):
            bare.append(line[:-2])
        elif line.endswith("\n"):
            bare.append(line[:-1])
        elif line.endswith("\r"):
            bare.append(line[:-1])
        else:
            bare.append(line)
    return lines, bare


def _context_scan(body):
    """Return one combined live/inert classification for every line of ``body``."""
    _, bare = _bare_lines_from_body(body)
    return md_fence.scan_contexts(bare)


def _find_all_standalone_markers(body, marker, scan=None):
    """Return byte offsets of every live standalone ``marker`` line in ``body``."""
    lines, bare = _bare_lines_from_body(body)
    if scan is None:
        scan = _context_scan(body)
    offsets = []
    offset = 0
    for i, line in enumerate(lines):
        if not scan.inert[i]:
            if md_fence.indent_width(bare[i]) != 0:
                offset += len(line)
                continue
            if bare[i].strip() == marker:
                leading = len(bare[i]) - len(bare[i].lstrip())
                offsets.append(offset + leading)
        offset += len(line)
    return offsets


def _find_standalone_marker(body, marker, start=0, scan=None):
    """Return byte offset of the first standalone marker line at or after start."""
    for off in _find_all_standalone_markers(body, marker, scan):
        if off >= start:
            return off
    return -1


def _extract_region(body, marker, scan, marker_name):
    # bite-axis: region markers must be standalone comment lines outside code fences.
    offsets = _find_all_standalone_markers(body, marker, scan)
    if len(offsets) >= 2:
        raise _BodyRefusal(
            "region-marker-duplicated",
            "%s: %d live occurrences" % (marker_name, len(offsets)),
        )
    if not offsets:
        return None, 0, 0
    lines, _ = _bare_lines_from_body(body)
    idx = offsets[0]
    start = idx + len(marker)
    rest = body[start:]
    if rest.startswith("\r\n"):
        start += 2
        rest = body[start:]
    elif rest.startswith("\n"):
        start += 1
        rest = body[start:]
    region_start_line = _line_index_at_offset(lines, start)
    next_markers = [
        _find_standalone_marker(body, m, start, scan)
        for m in REGION_MARKERS.values()
    ]
    next_markers = [pos for pos in next_markers if pos >= 0]
    marker_end = min(next_markers) if next_markers else len(body)
    section_level = None
    for i, line in enumerate(rest.splitlines()):
        body_line = region_start_line + i
        if body_line < len(scan.inert) and scan.inert[body_line]:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        section_level = _heading_level(stripped)
        break
    heading_end = start + _region_heading_bound(rest, section_level, scan, region_start_line)
    end = min(marker_end, heading_end)
    region_text = body[start:end]
    region_lines = region_text.splitlines()
    while region_lines and not region_lines[0].strip():
        region_lines.pop(0)
        region_start_line += 1
    while region_lines and not region_lines[-1].strip():
        region_lines.pop()
    region_text = "\n".join(region_lines)
    line_count = len(region_lines)
    return region_text, line_count, region_start_line


def read_region(body, region_name):
    if region_name not in REGION_MARKERS:
        raise ValueError("unknown region name: %r" % region_name)
    scan = _context_scan(body)
    try:
        region_text, _line_count, _region_start_line = _extract_region(
            body, REGION_MARKERS[region_name], scan, region_name,
        )
    except _BodyRefusal as exc:
        return None, exc.reason
    if region_text is None:
        return None, None
    return region_text, None
