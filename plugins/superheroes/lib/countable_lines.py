#!/usr/bin/env python3
"""Countable lines of a change, from its unified diff (#2209, layer C1-L5). stdlib and sibling lib modules only.

Every changed line counts, test and doc lines included, except lines in files moved without change,
generated files, lock files, files deleted whole, and proven copies. A file whose countability the
counter could not settle is returned in ``unsettled``, never silently counted or dropped.
"""
import hashlib
import json
import os
import re
import stat
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import sanitized_view  # noqa: E402  the canonical ``diff --git`` header reader
import size_count  # noqa: E402  the one home of the lock-file list and the Git scrub

COUNTABLE_LINES_BAR = 1000
GENERATED_MARKER_LINES = 5
PROOF_SCHEMA = "copy-proof/1"
ATTR_TIMEOUT = 60

# The marker patterns are built from pieces so this file does not carry a literal marker itself.
_GENERATED_TAG = "@" + "generated"
_CODE_GENERATED_RE = re.compile("Code generated .* " + "DO NOT" + " EDIT")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_SIMILARITY_RE = re.compile(r"similarity index (\d+)%")
_HEADER_PREFIX = "diff --git "
_MAX_MARKER_LINE = 65536


# --------------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------------

def _lines_keepends(text):
    """Split on ``\\n`` only, keeping the terminators, so the pieces concatenate back to ``text``."""
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _read_sides(header_line):
    """``(old, new)`` from one ``diff --git`` line, or None when git's header cannot be read."""
    try:
        return sanitized_view.sides_from_diff_git_line(
            header_line.rstrip("\n").encode("utf-8", "surrogateescape")
        )
    except UnicodeError:
        return None


def _parse_section(lines):
    header = lines[0]
    sides = _read_sides(header)
    status = "modified"
    similarity = None
    binary = False
    renamed = False
    copied = False
    added_lines = []
    removed_lines = []
    head_lines = []
    in_hunks = False
    in_patch = False
    new_no = 1
    for line in lines[1:]:
        hunk = _HUNK_RE.match(line)
        if hunk:
            in_hunks = True
            new_no = int(hunk.group(1))
            if hunk.group(2) == "0":
                new_no += 1
            new_no = max(new_no, 1)
            continue
        if in_hunks:
            body = line[1:]
            if body.endswith("\n"):
                body = body[:-1]
            lead = line[:1]
            if lead == "+":
                added_lines.append(body)
                head_lines.append(new_no)
                new_no += 1
            elif lead == "-":
                removed_lines.append(body)
                head_lines.append(max(new_no, 1))
            elif lead == " " or line == "\n":
                new_no += 1
            continue
        if in_patch:
            continue
        if line.startswith("GIT binary patch"):
            binary = True
            in_patch = True
        elif line.startswith("Binary files ") and line.rstrip("\n").endswith(" differ"):
            binary = True
        elif line.startswith("new file mode"):
            status = "added"
        elif line.startswith("deleted file mode"):
            status = "deleted"
        elif line.startswith("rename from ") or line.startswith("rename to "):
            renamed = True
        elif line.startswith("copy from ") or line.startswith("copy to "):
            copied = True
        else:
            found = _SIMILARITY_RE.match(line)
            if found:
                similarity = int(found.group(1))
    if status == "modified":
        if renamed:
            status = "renamed"
        elif copied:
            status = "added"
    section = {
        "file": None,
        "oldFile": None,
        "status": status,
        "similarity": similarity,
        "binary": binary,
        "added": len(added_lines),
        "removed": len(removed_lines),
        "addedLines": added_lines,
        "removedLines": removed_lines,
        "headLines": head_lines,
        "text": "".join(lines),
    }
    if sides is None:
        section["file"] = header.rstrip("\n")[len(_HEADER_PREFIX):]
        section["unreadable"] = True
        return section
    old_path, new_path = sides
    section["unreadable"] = False
    if status == "deleted":
        section["file"] = old_path
        section["oldFile"] = old_path
    else:
        section["file"] = new_path
        section["oldFile"] = None if status == "added" else old_path
    return section


def _split(diff_text):
    """``(preamble, sections)``: the text before the first ``diff --git`` line, and the sections."""
    lines = _lines_keepends(diff_text)
    starts = [i for i, line in enumerate(lines) if line.startswith(_HEADER_PREFIX)]
    if not starts:
        return diff_text, []
    preamble = "".join(lines[: starts[0]])
    bounds = starts + [len(lines)]
    sections = [_parse_section(lines[bounds[k] : bounds[k + 1]]) for k in range(len(starts))]
    return preamble, sections


def parse_sections(diff_text):
    """Per-file sections of ``diff_text`` in diff order; the sections' ``text`` fields concatenate to the diff
    from its first ``diff --git`` line on. A non-``str`` diff gives ``[]``."""
    if not isinstance(diff_text, str):
        return []
    return _split(diff_text)[1]


# --------------------------------------------------------------------------------------------
# The copy proof
# --------------------------------------------------------------------------------------------

def _blank(value):
    return not isinstance(value, str) or not value.strip()


def proof_fault(obj):
    """None when ``obj`` is a well-formed copy proof, else a short string naming the path at fault."""
    if not isinstance(obj, dict):
        return "proof"
    # Axis: a proof is exactly the schema tag plus a non-empty ``copies`` list; any other key is a fault.
    for key in obj:
        if key not in ("schema", "copies"):
            return str(key)
    if obj.get("schema") != PROOF_SCHEMA:
        return "schema"
    copies = obj.get("copies")
    if not isinstance(copies, list) or not copies:
        return "copies"
    seen = set()
    for i, copy in enumerate(copies):
        where = "copies[%d]" % i
        if not isinstance(copy, dict):
            return where
        for key in copy:
            if key not in ("file", "source", "sha256"):
                return "%s.%s" % (where, key)
        for key in ("file", "source"):
            if _blank(copy.get(key)):
                return "%s.%s" % (where, key)
        digest = copy.get("sha256")
        if not isinstance(digest, str) or not _HEX64_RE.fullmatch(digest):
            return where + ".sha256"
        if copy["file"] in seen:
            return where + ".file"
        seen.add(copy["file"])
    return None


def load_proof(path):
    """``(proof, None)`` for a well-formed proof file, else ``(None, <fault>)``."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, ValueError, UnicodeError):
        return None, "proof-unreadable"
    try:
        proof = json.loads(text)
    except ValueError:
        return None, "proof-bad-json"
    fault = proof_fault(proof)
    if fault is not None:
        return None, fault
    return proof, None


def _lexically_unsafe(file):
    if os.path.isabs(file) or file.startswith("/") or file.startswith("\\"):
        return True
    return ".." in file.replace("\\", "/").split("/")


def _resolved_path(repo_root, file):
    """``(full_path, None)`` for a regular, non-symlink path inside ``repo_root``, else ``(None, reason)``."""
    try:
        if _lexically_unsafe(file):
            return None, "path-unsafe"
        real_root = os.path.realpath(os.fspath(repo_root))
        full = os.path.join(real_root, *[p for p in file.split("/") if p not in ("", ".")])
        if stat.S_ISLNK(os.lstat(full).st_mode):
            return None, "path-unsafe"
        if os.path.realpath(full) != full:
            return None, "path-unsafe"
    except (OSError, ValueError, TypeError, UnicodeError):
        return None, "unreadable"
    return full, None


def _sha256_of(full):
    digest = hashlib.sha256()
    fd = os.open(full, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proven_copies(diff_text, repo_root, proof):
    """``(proven, rejected)``: the proof copies whose file is in the change, not deleted, and whose working-tree
    bytes hash to the proof's checksum, and every other copy as ``{"file", "reason"}``. A proof that fails
    ``proof_fault`` proves nothing."""
    if not isinstance(diff_text, str) or proof_fault(proof) is not None:
        return [], []
    by_file = {}
    for section in parse_sections(diff_text):
        if not section["unreadable"]:
            by_file.setdefault(section["file"], []).append(section)
    proven = []
    rejected = []
    for copy in proof["copies"]:
        file = copy["file"]
        reason = _reject_reason(by_file, repo_root, copy)
        if reason is None:
            proven.append({"file": file, "source": copy["source"], "sha256": copy["sha256"]})
        else:
            rejected.append({"file": file, "reason": reason})
    return proven, rejected


def _reject_reason(by_file, repo_root, copy):
    file = copy["file"]
    if _lexically_unsafe(file):
        return "path-unsafe"
    sections = by_file.get(file, [])
    # Axis: a proof copy counts only when its file is a section of the change.
    if not sections:
        return "not-in-change"
    if sections and all(section["status"] == "deleted" for section in sections):
        return "deleted"
    full, reason = _resolved_path(repo_root, file)
    if reason is not None:
        return reason
    try:
        digest = _sha256_of(full)
    except (OSError, ValueError):
        return "unreadable"
    # Axis: a proof copy counts only when the working-tree bytes hash to the proof's checksum.
    if digest != copy["sha256"]:
        return "checksum-mismatch"
    return None


# --------------------------------------------------------------------------------------------
# The count
# --------------------------------------------------------------------------------------------

def _diff_unreadable():
    return {
        "countable": 0,
        "bar": COUNTABLE_LINES_BAR,
        "files": [],
        "unsettled": [{"file": None, "reason": "diff-unreadable"}],
    }


def _proven_files(proven):
    if isinstance(proven, str):
        return {proven}
    files = set()
    try:
        for entry in proven:
            if isinstance(entry, str):
                files.add(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("file"), str):
                files.add(entry["file"])
    except TypeError:
        return set()
    return files


def _moved_pairs(sections):
    """Indices of ``added`` sections whose added lines equal exactly the removed lines of a ``deleted``
    section in the same diff; each deleted section pairs at most once."""
    free = [
        (i, s["removedLines"])
        for i, s in enumerate(sections)
        if s["status"] == "deleted" and not s["unreadable"] and s["removedLines"]
    ]
    moved = set()
    for i, section in enumerate(sections):
        if section["status"] != "added" or section["unreadable"] or not section["addedLines"]:
            continue
        for slot, (_, removed) in enumerate(free):
            if removed == section["addedLines"]:
                moved.add(i)
                del free[slot]
                break
    return moved


def _attribute_flags(repo_root, files):
    """``{file: bool}`` for ``linguist-generated`` set/true, or None when ``git check-attr`` failed."""
    try:
        with size_count._git_routing_scrubbed_environ():
            env = dict(os.environ)
        env["GIT_OPTIONAL_LOCKS"] = "0"
        stdin = b"".join(f.encode("utf-8", "surrogateescape") + b"\0" for f in files)
        proc = subprocess.run(
            ["git", "-C", os.fspath(repo_root), "check-attr", "-z", "linguist-generated", "--stdin"],
            input=stdin, capture_output=True, timeout=ATTR_TIMEOUT, env=env,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, TypeError):
        return None
    if proc.returncode != 0:
        return None
    fields = proc.stdout.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 3 != 0:
        return None
    values = {}
    for k in range(0, len(fields), 3):
        path = fields[k].decode("utf-8", "surrogateescape")
        values[path] = fields[k + 2].decode("utf-8", "replace") in ("set", "true")
    if any(f not in values for f in files):
        return None
    return {f: values[f] for f in files}


def _has_generated_marker(repo_root, file):
    """True/False for the first ``GENERATED_MARKER_LINES`` lines of the working-tree file, None when unreadable."""
    full, reason = _resolved_path(repo_root, file)
    if reason is not None:
        return None
    try:
        fd = os.open(full, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            head = [handle.readline(_MAX_MARKER_LINE) for _ in range(GENERATED_MARKER_LINES)]
    except (OSError, ValueError):
        return None
    for raw in head:
        text = raw.decode("utf-8", "replace")
        if _GENERATED_TAG in text or _CODE_GENERATED_RE.search(text):
            return True
    return False


def _settle_generated(repo_root, files):
    """``{file: ("generated" | "countable" | <unsettled reason>)}`` for every file that reached the generated test."""
    unique = list(dict.fromkeys(files))
    if not unique:
        return {}
    flags = _attribute_flags(repo_root, unique)
    if flags is None:
        return {f: "attribute-unreadable" for f in unique}
    out = {}
    for file in unique:
        if flags[file]:
            out[file] = "generated"
            continue
        marker = _has_generated_marker(repo_root, file)
        if marker is None:
            out[file] = "content-unreadable"
        else:
            out[file] = "generated" if marker else "countable"
    return out


def count(diff_text, repo_root, proven=()):
    """The countable lines of ``diff_text``: ``{"countable", "bar", "files", "unsettled"}``.

    ``proven`` is an iterable of file paths or of dicts with a ``"file"`` key."""
    if not isinstance(diff_text, str):
        return _diff_unreadable()
    sections = parse_sections(diff_text)
    proven_files = _proven_files(proven)
    moved = _moved_pairs(sections)
    decisions = [None] * len(sections)
    candidates = []
    for i, section in enumerate(sections):
        decisions[i] = _early_decision(section, i in moved, proven_files)
        if decisions[i] is None:
            candidates.append(section["file"])
    settled = _settle_generated(repo_root, candidates)
    rows = []
    unsettled = []
    total = 0
    for section, decision in zip(sections, decisions):
        lines = section["added"] + section["removed"]
        if decision is None:
            decision = settled[section["file"]]
        if decision == "countable":
            rows.append({"file": section["file"], "lines": lines, "counted": True, "why": None})
            total += lines
        elif decision in _EXCLUSIONS:
            rows.append({"file": section["file"], "lines": lines, "counted": False, "why": decision})
        else:
            rows.append({"file": section["file"], "lines": lines, "counted": False, "why": "unsettled"})
            unsettled.append({"file": section["file"], "reason": decision})
    return {"countable": total, "bar": COUNTABLE_LINES_BAR, "files": rows, "unsettled": unsettled}


_EXCLUSIONS = frozenset({"deleted-whole", "moved-unchanged", "proven-copy", "lock-file", "generated"})


def _early_decision(section, is_moved, proven_files):
    """The decision for steps 1-5 of the order, or None when the file reaches the generated test.

    A section whose header could not be read has no trustworthy path, so the proven-copy and lock-file
    tests (which read the path) are skipped for it and it goes straight to unsettled."""
    if section["status"] == "deleted":
        return "deleted-whole"
    if section["status"] == "renamed" and section["similarity"] == 100 and not (section["added"] or section["removed"]):
        return "moved-unchanged"
    if is_moved:
        return "moved-unchanged"
    if section["unreadable"]:
        return "header-unreadable"
    if section["file"] in proven_files:
        return "proven-copy"
    if size_count.is_lockfile(section["file"]):
        return "lock-file"
    if section["binary"]:
        return "binary"
    return None


# --------------------------------------------------------------------------------------------
# The reviewer's diff and the changed parts
# --------------------------------------------------------------------------------------------

def reviewer_diff(diff_text, proven):
    """``diff_text`` with the whole sections of the ``proven`` files removed, every other byte unchanged."""
    if not isinstance(diff_text, str):
        return ""
    files = _proven_files(proven)
    preamble, sections = _split(diff_text)
    kept = [s["text"] for s in sections if s["unreadable"] or s["file"] not in files]
    return preamble + "".join(kept)


def _merge_numbers(numbers):
    ranges = []
    for n in sorted(set(numbers)):
        if ranges and n <= ranges[-1][1] + 1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    return ranges


def changed_parts(diff_text):
    """``[{"file", "lines": [[start, end], ...]}, ...]`` in head-file coordinates, in diff order. Files deleted
    whole, binary sections and unreadable headers have no head lines and are left out."""
    if not isinstance(diff_text, str):
        return []
    parts = []
    for section in parse_sections(diff_text):
        if section["unreadable"] or section["binary"] or section["status"] == "deleted":
            continue
        ranges = _merge_numbers(section["headLines"])
        if ranges:
            parts.append({"file": section["file"], "lines": ranges})
    return parts


def _valid_range(rng):
    return (
        isinstance(rng, (list, tuple)) and len(rng) == 2
        and all(isinstance(n, int) and not isinstance(n, bool) for n in rng)
        and 1 <= rng[0] <= rng[1]
    )


def _read_ranges(read_lists):
    """``{file: merged [[s, e], ...]}`` from the well-formed entries of ``read_lists``; malformed ones are skipped."""
    by_file = {}
    try:
        for read_list in read_lists:
            if not isinstance(read_list, (list, tuple)):
                continue
            for entry in read_list:
                if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
                    continue
                spans = entry.get("lines")
                if not isinstance(spans, (list, tuple)):
                    continue
                by_file.setdefault(entry["file"], []).extend([r[0], r[1]] for r in spans if _valid_range(r))
    except TypeError:
        return {}
    merged = {}
    for file, spans in by_file.items():
        out = []
        for start, end in sorted(spans):
            if out and start <= out[-1][1] + 1:
                out[-1][1] = max(out[-1][1], end)
            else:
                out.append([start, end])
        merged[file] = out
    return merged


def _subtract(ranges, taken):
    left = []
    for start, end in ranges:
        cursor = start
        for t_start, t_end in taken:
            if t_end < cursor or t_start > end:
                continue
            if t_start > cursor:
                left.append([cursor, t_start - 1])
            cursor = max(cursor, t_end + 1)
            if cursor > end:
                break
        if cursor <= end:
            left.append([cursor, end])
    return left


def unread_surface(diff_text, read_lists):
    """``changed_parts(diff_text)`` less every range in ``read_lists``, keeping only files with something left."""
    taken = _read_ranges(read_lists)
    out = []
    for part in changed_parts(diff_text):
        left = _subtract(part["lines"], taken.get(part["file"], []))
        if left:
            out.append({"file": part["file"], "lines": left})
    return out
