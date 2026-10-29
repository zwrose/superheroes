#!/usr/bin/env python3
"""Countable lines of a change, from its unified diff (#2209, layer C1-L5). stdlib and sibling lib modules only.

Every changed line counts, test and doc lines included, except lines in files moved without change,
generated files, lock files, files deleted whole, and proven copies. A file whose countability the
counter could not settle is returned in ``unsettled``, never silently counted or dropped.
"""
import hashlib
import io
import json
import os
import re
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
_INDEX_RE = re.compile(r"index [0-9a-fA-F]+\.\.([0-9a-fA-F]+)(?: [0-7]+)?")
_BINDING_MIN_HEX = 7
_REGULAR_MODES = ("100644", "100755")
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
    index_new = None
    added_lines = []
    removed_lines = []
    head_lines = []
    added_no_eol = False
    removed_no_eol = False
    last_lead = ""
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
            if lead == "\\":
                # git's "\ No newline at end of file" qualifies the line before it: one side after a +/- line, both after context
                if last_lead == "+":
                    added_no_eol = True
                elif last_lead == "-":
                    removed_no_eol = True
                elif last_lead == " ":
                    added_no_eol = removed_no_eol = True
                continue
            if lead == "+" or lead == "-" or lead == " " or line == "\n":
                last_lead = lead if line != "\n" else " "
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
        elif line.startswith("index "):
            found = _INDEX_RE.fullmatch(line.rstrip("\n"))
            if found and index_new is None:
                index_new = found.group(1).lower()
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
        "indexNew": index_new,
        "added": len(added_lines),
        "removed": len(removed_lines),
        "addedLines": added_lines,
        "removedLines": removed_lines,
        "addedNoEol": added_no_eol,
        "removedNoEol": removed_no_eol,
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
    fault = copies_fault(obj.get("copies"), name_extra_key=True)
    return None if fault is None else "copies" + fault


def copies_fault(copies, name_extra_key=False):
    """The one definition of the copy-list contract, shared by proof ingestion and the review record: ``None``
    when ``copies`` is a non-empty list of entries with exactly a file, a source (both non-blank strings) and a
    lowercase 64-hex sha256, no file twice; else the path at fault as a suffix (``""`` for the list itself,
    ``[i]`` for an entry, ``[i].key`` for a key). ``name_extra_key`` names the first bad key in the suffix; off, an
    unknown or missing key faults the whole entry. Either way the same entries pass and the same fail."""
    if not isinstance(copies, list) or not copies:
        return ""
    seen = set()
    for i, copy in enumerate(copies):
        where = "[%d]" % i
        if not isinstance(copy, dict):
            return where
        if name_extra_key:
            for key in copy:
                if key not in ("file", "source", "sha256"):
                    return "%s.%s" % (where, key)
        elif set(copy) != {"file", "source", "sha256"}:
            return where
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
    # Axis: any backslash makes a path unsafe, because the leave-out loader refuses an entry holding one.
    if os.path.isabs(file) or file.startswith("/") or "\\" in file:
        return True
    return ".." in file.split("/")


def _git_env():
    """The environment every Git call here runs under: routing variables scrubbed, optional locks off."""
    with size_count._git_routing_scrubbed_environ():
        env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _usable_head(head):
    """True for a non-empty revision string that Git cannot take for an option."""
    return isinstance(head, str) and bool(head) and not head.startswith("-")


def _head_entry(repo_root, head, file):
    """``(mode, type, oid)`` of the one tree entry at ``head`` whose path is exactly ``file``, else None.

    ``file`` is passed bare after ``--``, which ``ls-tree`` matches literally. None also covers a Git
    failure, a timeout and a ``head`` that names no commit."""
    if not _usable_head(head):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", os.fspath(repo_root), "ls-tree", "-z", head, "--", file],
            capture_output=True, timeout=ATTR_TIMEOUT, env=_git_env(),
        )
        wanted = file.encode("utf-8", "surrogateescape")
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, TypeError):
        return None
    if proc.returncode != 0:
        return None
    found = []
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        meta, tab, path = entry.partition(b"\t")
        fields = meta.split(b" ")
        if tab and path == wanted and len(fields) == 3:
            found.append(tuple(f.decode("ascii", "replace") for f in fields))
    return found[0] if len(found) == 1 else None


def _head_blob(repo_root, oid):
    """The bytes of blob ``oid``, or None when Git fails or times out."""
    try:
        proc = subprocess.run(
            ["git", "-C", os.fspath(repo_root), "cat-file", "blob", oid],
            capture_output=True, timeout=ATTR_TIMEOUT, env=_git_env(),
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, TypeError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _regular_head_blob(repo_root, head, file):
    """``(oid, bytes)`` for a regular file at ``head``, else ``(None, None)``."""
    entry = _head_entry(repo_root, head, file)
    if entry is None or entry[1] != "blob" or entry[0] not in _REGULAR_MODES:
        return None, None
    return entry[2], _head_blob(repo_root, entry[2])


def proven_copies(diff_text, repo_root, proof, head="HEAD"):
    """``(proven, rejected)``: the proof copies whose file is in the change, not deleted, shown in the diff by a
    section bound to the blob at ``head``, and whose bytes at ``head`` hash to the proof's checksum, and every
    other copy as ``{"file", "reason"}``. The working tree is never read. A proof that fails ``proof_fault``
    proves nothing."""
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
        reason = _reject_reason(by_file, repo_root, head, copy)
        if reason is None:
            proven.append({"file": file, "source": copy["source"], "sha256": copy["sha256"]})
        else:
            rejected.append({"file": file, "reason": reason})
    return proven, rejected


def _reject_reason(by_file, repo_root, head, copy):
    file = copy["file"]
    if _lexically_unsafe(file):
        return "path-unsafe"
    sections = by_file.get(file, [])
    # Axis: a proof copy counts only when its file is a section of the change.
    if not sections:
        return "not-in-change"
    if sections and all(section["status"] == "deleted" for section in sections):
        return "deleted"
    entry = _head_entry(repo_root, head, file)
    if entry is None:
        return "unreadable"
    mode, kind, oid = entry
    if kind != "blob" or mode not in _REGULAR_MODES:
        return "path-unsafe"
    # Axis: a proof copy counts only when every diff section shown for it is bound to the head blob (its
    # ``index`` new id is a prefix of the head oid), so the diff the reviewer reads is of the bytes proven.
    for section in sections:
        if section["status"] == "deleted":
            continue
        new = section["indexNew"]
        if new is None or len(new) < _BINDING_MIN_HEX or not oid.startswith(new):
            return "section-unbound"
    data = _head_blob(repo_root, oid)
    if data is None:
        return "unreadable"
    # Axis: a proof copy counts only when the head blob's bytes hash to the proof's checksum.
    if hashlib.sha256(data).hexdigest() != copy["sha256"]:
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
    section in the same diff, with the same final-newline status; each deleted section pairs at most once."""
    free = [
        (i, (s["removedLines"], s["removedNoEol"]))
        for i, s in enumerate(sections)
        if s["status"] == "deleted" and not s["unreadable"] and s["removedLines"]
    ]
    moved = set()
    for i, section in enumerate(sections):
        if section["status"] != "added" or section["unreadable"] or not section["addedLines"]:
            continue
        for slot, (_, removed) in enumerate(free):
            # Axis: a move keeps the bytes, so the final-newline status must match as well as the lines.
            if removed == (section["addedLines"], section["addedNoEol"]):
                moved.add(i)
                del free[slot]
                break
    return moved


def _attribute_flags(repo_root, files, head):
    """``{file: bool}`` for ``linguist-generated`` set/true as ``head`` records it, or None when
    ``git check-attr`` failed."""
    if not _usable_head(head):
        return None
    try:
        stdin = b"".join(f.encode("utf-8", "surrogateescape") + b"\0" for f in files)
        # Axis: the attribute is read from the head commit's tree, never from the checkout's .gitattributes.
        proc = subprocess.run(
            ["git", "-C", os.fspath(repo_root), "check-attr", "--source", head, "-z", "linguist-generated", "--stdin"],
            input=stdin, capture_output=True, timeout=ATTR_TIMEOUT, env=_git_env(),
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


def _has_generated_marker(repo_root, file, head):
    """True/False for the first ``GENERATED_MARKER_LINES`` lines of the blob at ``head``, None when the entry is
    missing, is not a regular file, or cannot be read."""
    _, data = _regular_head_blob(repo_root, head, file)
    if data is None:
        return None
    handle = io.BytesIO(data)
    top = [handle.readline(_MAX_MARKER_LINE) for _ in range(GENERATED_MARKER_LINES)]
    for raw in top:
        text = raw.decode("utf-8", "replace")
        if _GENERATED_TAG in text or _CODE_GENERATED_RE.search(text):
            return True
    return False


def _settle_generated(repo_root, files, head):
    """``{file: ("generated" | "countable" | <unsettled reason>)}`` for every file that reached the generated test."""
    unique = list(dict.fromkeys(files))
    if not unique:
        return {}
    flags = _attribute_flags(repo_root, unique, head)
    if flags is None:
        return {f: "attribute-unreadable" for f in unique}
    out = {}
    for file in unique:
        if flags[file]:
            out[file] = "generated"
            continue
        marker = _has_generated_marker(repo_root, file, head)
        if marker is None:
            out[file] = "content-unreadable"
        else:
            out[file] = "generated" if marker else "countable"
    return out


def count(diff_text, repo_root, proven=(), head="HEAD"):
    """The countable lines of ``diff_text``: ``{"countable", "bar", "files", "unsettled"}``.

    ``proven`` is an iterable of file paths or of dicts with a ``"file"`` key. Attributes and content are read
    from the commit ``head``, never from the working tree."""
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
    settled = _settle_generated(repo_root, candidates, head)
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


def section_digest(diff_text, file):
    """sha256 hex of the concatenated ``text`` of every section of ``diff_text`` whose ``file`` is ``file``, in
    diff order, or None when no section is for it."""
    texts = [s["text"] for s in parse_sections(diff_text) if s["file"] == file]
    if not texts:
        return None
    return hashlib.sha256("".join(texts).encode("utf-8", "surrogatepass")).hexdigest()


def still_proven(entries, diff_text):
    """The stored proven-copy ``entries`` (``{file, source, sha256, section}``), in stored order and as
    ``{file, source, sha256}``, whose file's section digest in ``diff_text`` still equals the entry's ``section``.
    A malformed entry is skipped, and a non-``str`` diff leaves none."""
    if not isinstance(diff_text, str) or not isinstance(entries, (list, tuple)):
        return []
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fields = [entry.get(k) for k in ("file", "source", "sha256", "section")]
        if not all(isinstance(v, str) for v in fields):
            continue
        # Axis: a copy stays out of a diff only while its section is the one the proof was checked against.
        if section_digest(diff_text, entry["file"]) == entry["section"]:
            kept.append({"file": entry["file"], "source": entry["source"], "sha256": entry["sha256"]})
    return kept


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
