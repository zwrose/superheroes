#!/usr/bin/env python3
"""The head-coverage check: whether the commit a review certified covers the pull request's current head. stdlib and
sibling lib modules only.

A review record certifies one commit, ``finalCommit.sha`` (X). This check decides whether X covers the pull request's
head, and the advisor's vet runs it for every pull request. It answers ``proven`` (git itself shows the pull
request's own change at the head equals the reviewed change at X), ``judgement`` (the vet must read the listed hunks:
every new commit is the builder's, and every remaining difference is either prose or comment and blank lines
(``prose-or-comments``) or the builder's hand-made lines of a merge that brings the base in (``conflict-fix``)) or
``needs-review`` (a returning-round review of the listed files is owed). It reads the repository and writes nothing.
A second, pure function, ``outcome``, turns that answer and CI on the head into the vet's outcome and the merge
sheet's action.

The rule, in order; the first step that applies answers:
  1. The record is not a dict, is not ``ok``, is abandoned, or has no full-sha ``finalCommit.sha``: needs-review
     (``record-unusable``).
  2. The head is X: proven (``same-commit``).
  3. The base or the head is not a full commit sha: needs-review (``input-invalid``).
  4. The changed files (``returning_review.changed_files``: the files whose own change differs between
     ``base...X`` and ``base...head``) cannot be produced by git: needs-review (``diff-unreadable``).
  5. A changed file is still proven when its mode at the head is its mode at X and a clean three-way merge of X's
     blob, the fork blob and the base blob equals the head blob byte for byte (``reconstructed``). This proof is the
     check's own; the returning-review decider keeps its stricter rule.
  6. A changed file is dropped when a copy-proof entry for it is re-validated by git at the head (its file is in the
     ``base...head`` change, bound to the head blob, and the head blob's bytes hash to the entry's sha256;
     ``review_record.revalidated_copies``), and the file keeps its mode at X or is new and plain (``100644``). An
     entry is never trusted for its own word; the entries relied on are listed in ``copies``.
  7. No changed file is left: proven (``own-change-unchanged``, or ``proven-copies`` when a copy was relied on).
  8. Otherwise the remaining files are read as ``git diff X head`` and the new commits as
     ``git rev-list head --not X base``. A file qualifies when its path ends ``.md``, ``.markdown``, ``.txt`` or
     ``.rst``, or, for a ``.py`` file, when every added and removed body line is one Python's tokenizer reads as a
     comment or blank line outside every string (in the file at X for a removed line, at the head for an added
     one); a comment in any other language cannot be told from data, so it never qualifies. A binary or unreadable
     section, a mode change, a rename or copy, a file the diff does not show and any
     other extension never qualify. A commit whose author email is not the builder's (the ``builder_author``
     given, else the author email of X), authors git cannot read, or no new commit to vouch for the difference:
     needs-review (``other-author``). All files qualify and every author is the builder: judgement
     (``prose-or-comments``), with the hunks to read. Otherwise needs-review (``behaviour-change``), except for a
     builder's conflict fix: when the files do not qualify, every author is the builder, no rename or copy source is
     outstanding, no remaining file is a moved one, and every new commit is a two-parent merge whose second parent is
     the base or an ancestor of it, whose first parent is X or another new commit, and whose two parents have one
     merge base, judgement (``conflict-fix``). Each remaining file is then read at every such merge. When the merge
     holds the first parent's version and the second parent still holds the merge base's, or the merge holds the
     second parent's version and the first still holds the merge base's, the file has no hand-made line there.
     Otherwise the file must be a regular file of one mode in all four trees, with no ``merge`` or
     ``conflict-marker-size`` attribute and no NUL byte, and git's own automatic merge of it (``git merge-file
     --diff3``, conflict blocks included) is compared with the file at the merge. The same: nothing to list. Git
     merged it cleanly yet the file differs, or a conflict block's markers survive in the file: needs-review.
     Otherwise every difference, each conflict block it touches widened to the whole block and given three lines of
     context, is a hunk (git's text against the file) the vet reads, so a resolution that drops one side's line
     shows the line. A merge with no hand-made line lists nothing, and the answer is the one above. Any failed git
     read leaves the answer as above.
  9. Any exception: needs-review (``check-failed``).
Every failure to read anything answers needs-review. The check never raises.

A stack layer whose layer below was rewritten (a straightening rebuilds it on a new commit) has a base that no longer
sits under the reviewed commit, so every file both layers edit would fail step 5. The caller may give ``base_at_review``,
the heads the layer below had before it was rewritten. A value that is not a full sha answers needs-review
(``input-invalid``). A full-sha value is tried only when git reads its tree, the tree equals the base's tree and it
shares a merge base with X; otherwise it is ignored (reason ``unreadable``, ``other-tree`` or ``no-merge-base``) and the
answer is the check's answer without it, with one ``base-at-review-ignored: <first 8 of the value> <reason>`` line per
ignored value. A well-formed value never makes the answer worse than the check without it. Steps 4 and 5 run again for
each value tried, with X's change read against that value instead of the base; the first that proves answers proven,
with a ``base-at-review`` line. With none given the check is exactly steps 1 to 9.

A hand-resolved merge of the base into the pull request has no three-way reconstruction, so the caller may give a union
proof (``--union-proof FILE``): the vet's tested probe, a two-parent commit that merged exactly the check's base with a
commit the review covers, and the test receipt of that probe's tree. It is consulted only when the answer is not already
proven and the check could read its inputs (a record that certifies, a valid base and head, a readable diff; otherwise
reason ``not-consulted``). It turns the answer to proven (``proven-union``) only when git itself shows, at check time,
eight things in this order: the proof is well formed (``malformed``); its receipt is one command with exit 0 on the
proof's tree (``no-receipt``); its base is the check's base (``other-base``); the probe is a commit (``probe-unreadable``);
git's tree of the probe is the proof's tree (``tree-unconfirmed``); the probe's parents are the base and one other commit
that is the certified commit or that the check, run from the certified commit to it, proves (``other-commit``); the base
is an ancestor of the head (``head-not-current``); and the head's tree is git's tree of the probe, mode bits included
(``other-tree``). The first that fails leaves the answer exactly as it was, adds one ``union-probe-ignored: <first 8 of
the probe> <reason>`` line and sets ``unionProbe.used`` false; so a proof never makes the answer worse. ``unionProbe``
(the probe, ``used``, ``reason`` and the files it ``covers``) is in the result only when a proof was given; without one the
result is exactly as it was.

``outcome(answer, ci, judged_clear, sheet, sheet_commit, head)`` is covered when the answer is proven, or judgement
with ``judged_clear``. CI red is NOT-READY (``ci-red``, no review owed: the fix arrives as a new commit); not covered
is NOT-READY (``needs-review``, or ``judged-meaningful`` for an uncleared judgement) with a returning review owed;
covered with CI pending or none is WAIT (``ci-not-green``); otherwise READY (``covered``). The sheet action is
``none`` with no sheet; a held sheet is ``republish-unsigned`` when READY, else ``keep``; a live sheet is
``take-down`` when NOT-READY; READY on a head other than the sheet's commit is ``republish-carried`` only when the
carry answer (the check run from the sheet's own commit to the head) is proven, or judgement with
``carry_judged_clear``, else ``republish-unsigned``; otherwise ``keep``. With a sheet, the sheet's commit and the head
must be full 40-hex shas, and a live sheet whose head moved needs a carry answer; either missing is a usage error.

CLI:
  head_coverage.py check --repo-root DIR --base SHA --record FILE --head SHA [--proof FILE] [--builder-author EMAIL]
                         [--base-at-review SHA]... [--union-proof FILE]
  head_coverage.py outcome --answer A --ci C [--judged-clear] [--sheet none|live|held] [--sheet-commit SHA]
                           [--head SHA] [--carry-answer A] [--carry-judged-clear]
prints the result as one JSON object. Exit 0 for every answer, 2 on a usage error (an unreadable record, proof or
union-proof file, a union-proof file holding null, a bad value)."""
import argparse
import difflib
import io
import json
import os
import re
import sys
import tokenize

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import countable_lines  # noqa: E402
import returning_review  # noqa: E402
import review_record  # noqa: E402

PROVEN = "proven"
JUDGEMENT = "judgement"
NEEDS_REVIEW = "needs-review"
ANSWERS = (PROVEN, JUDGEMENT, NEEDS_REVIEW)

WHY_RECORD_UNUSABLE = "record-unusable"
WHY_SAME_COMMIT = "same-commit"
WHY_INPUT_INVALID = "input-invalid"
WHY_DIFF_UNREADABLE = "diff-unreadable"
WHY_OWN_CHANGE_UNCHANGED = "own-change-unchanged"
WHY_PROVEN_COPIES = "proven-copies"
WHY_PROSE_OR_COMMENTS = "prose-or-comments"
WHY_OTHER_AUTHOR = "other-author"
WHY_BEHAVIOUR_CHANGE = "behaviour-change"
WHY_CHECK_FAILED = "check-failed"
WHY_BASE_AT_REVIEW = "base-at-review"
WHY_BASE_AT_REVIEW_IGNORED = "base-at-review-ignored"
WHY_PROVEN_UNION = "proven-union"
WHY_UNION_IGNORED = "union-probe-ignored"
WHY_CONFLICT_FIX = "conflict-fix"
WHY_TOKENS = (WHY_RECORD_UNUSABLE, WHY_SAME_COMMIT, WHY_INPUT_INVALID, WHY_DIFF_UNREADABLE, WHY_OWN_CHANGE_UNCHANGED,
              WHY_PROVEN_COPIES, WHY_PROSE_OR_COMMENTS, WHY_OTHER_AUTHOR, WHY_BEHAVIOUR_CHANGE, WHY_CHECK_FAILED,
              WHY_BASE_AT_REVIEW, WHY_BASE_AT_REVIEW_IGNORED, WHY_PROVEN_UNION, WHY_UNION_IGNORED, WHY_CONFLICT_FIX)

UNION_SCHEMA = "union-probe/1"
UNION_REASONS = ("malformed", "no-receipt", "other-base", "probe-unreadable", "tree-unconfirmed", "other-commit",
                 "head-not-current", "other-tree", "not-consulted")
# The answers for which the check could not read its inputs; a union proof is not consulted for them.
_UNION_UNREAD_WHY = (WHY_RECORD_UNUSABLE, WHY_INPUT_INVALID, WHY_DIFF_UNREADABLE, WHY_CHECK_FAILED)
_UNION_KEYS = {"schema", "probe", "tree", "base", "receipt"}
_UNION_RECEIPT_KEYS = {"command", "exitCode", "tree"}
_HEX_PREFIX_RE = re.compile(r"[0-9a-f]{1,8}")

CI_STATES = ("green", "pending", "red", "none")
SHEETS = ("none", "live", "held")
# The sheet's commit and the head, whenever outcome is given a sheet.
_FULL_SHA_40 = re.compile(r"[0-9a-f]{40}")
READY = "READY"
WAIT = "WAIT"
NOT_READY = "NOT-READY"

_PROSE_SUFFIXES = (".md", ".markdown", ".txt", ".rst")
# A line that begins with a comment marker yet is read by a tool as an instruction is no comment.
_DIRECTIVE_PREFIXES = ("#!",)
_LAYOUT_TOKENS = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)
_HUNK_NUMBERS_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_REGULAR_MODES = ("100644", "100755")
_MODE_LINES = ("old mode ", "new mode ")
_FILE_MODE_LINES = ("new file mode ", "deleted file mode ")
_HUNK_LINE_RE = re.compile(r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
# one ``git ls-tree`` entry: ``<mode> <type> <sha>\t<path>``
_TREE_ENTRY_RE = re.compile(r"^(\d{6}) (blob|tree|commit) ([0-9a-f]{40}|[0-9a-f]{64})\t.+$")
# ``_mode`` answer for a file that is not in that tree (git exited 0 and listed nothing); None means git failed
ABSENT = object()


def _plain(value):
    return value if isinstance(value, str) else None


def _line(token, text):
    return "%s: %s" % (token, text)


def _result(base, head, certified=None):
    return {
        "answer": NEEDS_REVIEW,
        "why": [],
        "certified": certified,
        "head": _plain(head),
        "base": _plain(base),
        "files": [],
        "reconstructed": [],
        "copies": [],
        "hunks": [],
        "commits": [],
    }


def _needs_review(result, token, text):
    result["answer"] = NEEDS_REVIEW
    result["why"].append(_line(token, text))
    return result


def _certified(record):
    """X, the full sha the record certifies, or None when the record is not a usable, finished-or-not, ok record
    that is not abandoned."""
    if not isinstance(record, dict):
        return None
    # A record that is not ok, or that carries ``abandoned``, certifies nothing, whatever final commit it names.
    if "ok" in record and record["ok"] is not True:
        return None
    if "abandoned" in record:
        return None
    final = record.get("finalCommit")
    sha = final.get("sha") if isinstance(final, dict) else None
    return sha if returning_review._is_sha(sha) else None


def _copies_of(proof):
    if isinstance(proof, dict):
        proof = proof.get("copies")
    if isinstance(proof, (list, tuple)):
        return list(proof)
    return []


def _section_headers(section):
    return [line.rstrip("\r") for line in section["text"].split("\n") if _HUNK_LINE_RE.match(line)]


def _mode(run, rev, path):
    """The tree-entry mode of ``path`` at ``rev`` (for example ``100644``); ``ABSENT`` when git exited 0 and listed
    nothing (the file is not in that tree); None when git failed or printed anything but one
    ``<mode> <type> <sha>\\t<path>`` entry. A failed read is never an absent file."""
    # axis: a mode git could not read is not an absent file, so a failed ls-tree keeps the file changed instead of passing the equality or the new-and-plain test — see bite-proof record i2496_wo_a_head_coverage (E-mode-read)
    code, text = run(["ls-tree", rev, "--", path])
    if code != 0 or not isinstance(text, str):
        return None
    if not text.strip():
        return ABSENT
    lines = text.splitlines()
    entry = _TREE_ENTRY_RE.match(lines[0]) if len(lines) == 1 else None
    return entry.group(1) if entry else None


def _real_mode(mode):
    """True for a mode string git printed: neither ``ABSENT`` nor None."""
    return isinstance(mode, str)


def _changed_lines(section):
    """``(removed, added)``: the line numbers, at X and at the head, of every removed and added body line of
    ``section``, read from its hunk headers; None when a hunk header cannot be read."""
    removed, added, old, new = [], [], None, None
    for line in section["text"].split("\n"):
        hunk = _HUNK_NUMBERS_RE.match(line)
        if hunk:
            old, new = int(hunk.group(1)), int(hunk.group(2))
            continue
        if old is None or line.startswith(("--- ", "+++ ")):
            continue
        if line.startswith("-"):
            removed.append(old)
            old += 1
        elif line.startswith("+"):
            added.append(new)
            new += 1
        elif line.startswith(" "):
            old, new = old + 1, new + 1
    return removed, added


def _insignificant_lines(text):
    """The line numbers of ``text`` that Python's tokenizer reads as holding nothing but a comment or whitespace,
    outside every string; None when ``text`` cannot be tokenized."""
    significant = set()
    fstring_start = getattr(tokenize, "FSTRING_START", None)
    fstring_end = getattr(tokenize, "FSTRING_END", None)
    open_starts = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            # axis: every line from an f-string's start row to its matching end row is significant, whatever tokens the tokenizer emits inside it (a blank line inside a debug f-string yields only NL), so an f-string edit never reads judgement — see bite-proof record i2496_wo_a_head_coverage (E-fstring)
            if fstring_start is not None and tok.type == fstring_start:
                open_starts.append(tok.start[0])
            elif fstring_end is not None and tok.type == fstring_end and open_starts:
                significant.update(range(open_starts.pop(), tok.end[0] + 1))
            if tok.type in _LAYOUT_TOKENS:
                continue
            # a string, a name or any other token makes every line it spans significant, so a comment-like line
            # inside a triple-quoted string is data
            significant.update(range(tok.start[0], tok.end[0] + 1))
    except (tokenize.TokenError, SyntaxError):
        return None
    if open_starts:
        # an f-string that never closed cannot be classified
        return None
    return {n for n in range(1, text.count("\n") + 2) if n not in significant}


def _file_text(run, rev, path):
    code, text = run(["show", "%s:%s" % (rev, path)])
    return text if code == 0 else None


def _lexically_insignificant(run, x, head, section):
    """True when every removed line of a Python ``section`` is a comment or blank line of the file at X, and every
    added line one of the file at the head, by the tokenizer; a line it cannot classify is significant."""
    numbers = _changed_lines(section)
    if numbers is None:
        return False
    removed, added = numbers
    for rev, lines in ((x, removed), (head, added)):
        if not lines:
            continue
        text = _file_text(run, rev, section["file"])
        quiet = _insignificant_lines(text) if text is not None else None
        if quiet is None or not set(lines) <= quiet:
            return False
    return True


def _section_qualifies(section, run=None, x=None, head=None):
    """True when ``section`` (one file's diff from X to the head) is prose, or, for a Python file, only lines the
    tokenizer reads as comments or blank lines outside every string."""
    if section["unreadable"] or section["binary"]:
        return False
    # A rename or a copy moves a file; whatever it says, the path is behaviour.
    if section["copied"] or section["status"] == "renamed":
        return False
    for line in section["text"].split("\n"):
        if line.startswith(_MODE_LINES):
            return False
        if line.startswith(_FILE_MODE_LINES) and line.split()[-1] not in _REGULAR_MODES:
            return False
    path = section["file"]
    if path.lower().endswith(_PROSE_SUFFIXES):
        return True
    # Only Python has a lexer here: a comment in any other language cannot be told from data, so it is review owed.
    if not path.lower().endswith(".py") or not _section_headers(section) or run is None:
        return False
    for body in section["addedLines"] + section["removedLines"]:
        text = body.strip()
        # axis: a non-prose file qualifies only when every added and removed line is blank or a comment of its own language, so a changed assertion or code line never reads judgement — see bite-proof record i2496_wo_a_head_coverage (E-judge)
        if text and not (text.startswith("#") and not text.startswith(_DIRECTIVE_PREFIXES)):
            return False
    # axis: a comment-looking line counts as a comment only where the tokenizer reads it as one, so a line inside a string stays data — see bite-proof record i2496_wo_a_head_coverage (E-lex)
    return _lexically_insignificant(run, x, head, section)


def _qualification(run, x, head, files, sources=()):
    """``(qualifies, hunks, why text)`` for ``files`` read as ``git diff X head``: every file must be shown by git and
    every section of it must qualify. ``sources`` are the outstanding rename and copy source paths, read with them
    so that git shows a move as a move; ``files`` may be empty when ``sources`` is not, and the sections the source
    paths show are then the whole read."""
    # axis: a rename's source path is part of the diff the check reads, so a move is never shown as an added file — see bite-proof record i2496_wo_a_head_coverage (E-rename)
    code, text = run(["diff", *returning_review._DIFF_ARGS, x, head, "--", *files, *[s for s in sources if s not in files]])
    if code != 0:
        return False, [], "git could not produce the diff from the certified commit to the head"
    sections = countable_lines.parse_sections(text)
    shown = {}
    for section in sections:
        shown.setdefault(section["file"], []).append(section)
    hunks = []
    bad = []
    for path in files:
        mine = shown.get(path)
        # A changed file the diff does not show cannot be judged, so it never qualifies.
        if not mine or not all(_section_qualifies(s, run, x, head) for s in mine):
            bad.append(path)
            continue
        for section in mine:
            hunks.extend({"file": path, "header": header} for header in _section_headers(section))
    # a file the diff shows beyond the asked paths (a rename's other side) is read too, and its hunks are listed for the
    # vet like any other
    for path, mine in shown.items():
        if path in files:
            continue
        if not all(_section_qualifies(s, run, x, head) for s in mine):
            bad.append(path)
            continue
        for section in mine:
            # axis: every section the judgement rests on is listed for the vet to read, a source path's included — see bite-proof record i2496_wo_a_head_coverage (E-hunks)
            headers = _section_headers(section) or [section["text"].split("\n", 1)[0]]
            hunks.extend({"file": path, "header": header} for header in headers)
    if bad:
        return False, [], "not only prose or comment lines: %s" % ", ".join(sorted(set(bad))[:5])
    return True, hunks, ""


def _author_email(run, rev):
    code, text = run(["log", "-1", "--format=%ae", rev])
    email = text.strip()
    return email if code == 0 and email else None


def _authors(run, base, x, head):
    """``[{"sha", "author"}]`` of every commit of ``git rev-list head --not X base``, or None when git cannot name them,
    names none, or cannot read an author."""
    code, text = run(["rev-list", head, "--not", x, base])
    shas = text.split()
    if code != 0 or not shas or not all(returning_review._is_sha(s) for s in shas):
        return None
    commits = []
    for sha in shas:
        email = _author_email(run, sha)
        if email is None:
            return None
        commits.append({"sha": sha, "author": email})
    return commits


# --------------------------------------------------------------------------------------------
# a builder's conflict fix (step 8)
# --------------------------------------------------------------------------------------------

KIND_CONFLICT_FIX = "conflict-fix"
_BLOB_ENTRY_RE = re.compile(r"^(\d{6}) blob ([0-9a-f]{40}|[0-9a-f]{64})\t.+$")
_CONFLICT_START, _CONFLICT_BASE, _CONFLICT_MID, _CONFLICT_END = "<<<<<<< ", "||||||| ", "=======", ">>>>>>> "
_HUNK_CONTEXT = 3
_MAX_CONFLICTS = 127  # ``git merge-file`` exits with the number of conflicts, at most this


def _blob_entry(run, rev, path):
    """``(mode, blob sha)`` of ``path`` at ``rev``; ``ABSENT`` when git exited 0 and listed nothing; None when git
    failed or printed anything but one blob entry."""
    code, text = run(["ls-tree", rev, "--", path])
    if code != 0 or not isinstance(text, str):
        return None
    if not text.strip():
        return ABSENT
    lines = text.splitlines()
    entry = _BLOB_ENTRY_RE.match(lines[0]) if len(lines) == 1 else None
    return (entry.group(1), entry.group(2)) if entry else None


def _lines_of(text):
    """``text`` as lines that keep their ``\\n``; git's own line ends, never a form feed or a separator character."""
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _conflict_blocks(lines):
    """``[(start, end, marker line numbers)]`` of every conflict block of git's diff3 text (half-open, markers
    included); None when a block is not exactly ``<<<<<<<``, ``|||||||``, ``=======`` and ``>>>>>>>``."""
    blocks = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith(_CONFLICT_START):
            i += 1
            continue
        marks = [i]
        j = i + 1
        while j < len(lines) and not lines[j].startswith(_CONFLICT_END):
            if lines[j].startswith(_CONFLICT_BASE) or lines[j].rstrip("\r\n") == _CONFLICT_MID:
                marks.append(j)
            j += 1
        if j >= len(lines):
            return None
        marks.append(j)
        if len(marks) != 4:
            return None
        blocks.append((i, j + 1, marks))
        i = j + 1
    return blocks


def _b_position(ops, pos):
    """The line of the file that sits where line ``pos`` of git's text does."""
    for tag, i1, i2, j1, j2 in ops:
        if i1 <= pos <= i2:
            if tag == "equal":
                return j1 + (pos - i1)
            return j1 if pos == i1 else j2
    return ops[-1][4] if ops else 0


def _hunk_text(a, b, ops, lo, hi):
    """``(header, text)``: lines ``lo`` to ``hi`` of git's text ``a`` as ``-`` lines against the file ``b`` as ``+``
    lines, in unified form (1-based numbers, git's convention)."""
    start_b = _b_position(ops, lo)
    body, a_n, b_n = [], 0, 0
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for k in range(max(i1, lo), min(i2, hi)):
                body.append(" " + a[k])
                a_n, b_n = a_n + 1, b_n + 1
        elif i1 >= lo and i2 <= hi:
            body.extend("-" + a[k] for k in range(i1, i2))
            body.extend("+" + b[k] for k in range(j1, j2))
            a_n, b_n = a_n + (i2 - i1), b_n + (j2 - j1)
    header = "@@ -%d,%d +%d,%d @@" % (lo + 1 if a_n else lo, a_n, start_b + 1 if b_n else start_b, b_n)
    return header, header + "\n" + "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                                           for line in body)


def _hunk_ranges(ops, blocks, length):
    """The merged half-open ranges of git's text that the hand-made lines (every non-equal opcode) fall in: each range
    widened to the whole of every conflict block it overlaps, given context, and joined with those it touches."""
    ranges = []
    for tag, i1, i2, _, _ in ops:
        if tag == "equal":
            continue
        lo, hi = i1, i2
        for start, end, _ in blocks:
            overlaps = (i1 < end and i2 > start) if i2 > i1 else (start < i1 < end)
            # axis: a hand-made line inside a conflict block is listed with the whole block, so the vet reads both sides and the markers beside the resolution — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-span)
            if overlaps:
                lo, hi = min(lo, start), max(hi, end)
        ranges.append((max(0, lo - _HUNK_CONTEXT), min(length, hi + _HUNK_CONTEXT)))
    merged = []
    for lo, hi in sorted(ranges):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _conflict_fix_file(run, path, c, p1, p2, mb):
    """The hunks of ``path`` at the merge ``c`` (parents ``p1``, ``p2``, merge base ``mb``) that git's own automatic
    merge did not make: ``[]`` when there are none, None when the file cannot be read this way."""
    entries = [_blob_entry(run, rev, path) for rev in (c, p1, mb, p2)]
    # axis: a tree entry git could not read is no absent file, so a failed read never passes the equality below and hides a hand edit — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-unreadable)
    if any(entry is None for entry in entries):
        return None
    at_c, at_p1, at_mb, at_p2 = entries
    # axis: a side's version taken wholesale counts as no hand-made line only while the other side still holds the merge base's, so a resolution that drops one side's change is read — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-onesided)
    if (at_c == at_p1 and at_p2 == at_mb) or (at_c == at_p2 and at_p1 == at_mb):
        return []
    if not all(isinstance(entry, tuple) for entry in entries):
        return None
    # axis: a merge that changes the file's mode, or a file that is not a regular file, is never read as a conflict fix, since a mode is no line of text — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-mode)
    if len({entry[0] for entry in entries}) != 1 or at_c[0] not in _REGULAR_MODES:
        return None
    code, text = run(["check-attr", "--source", c, "merge", "conflict-marker-size", "--", path])
    rows = [line.rsplit(": ", 2) for line in text.splitlines()] if code == 0 and isinstance(text, str) else []
    # axis: a file with a merge driver or a marker size attribute was not merged the way the check rebuilds it, so it is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-attr)
    if not (len(rows) == 2 and all(len(row) == 3 for row in rows)
            and [row[1] for row in rows] == ["merge", "conflict-marker-size"] and all(row[2] == "unspecified" for row in rows)):
        return None
    texts = []
    for entry in (at_p1, at_mb, at_p2, at_c):
        code, text = run(["cat-file", "blob", entry[1]])
        if code != 0 or not isinstance(text, str):
            return None
        texts.append(text)
    # axis: a file with a NUL byte anywhere is binary to the eye even when git's merge reads it as text, so it is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-binary)
    if any("\0" in text for text in texts):
        return None
    code, merged = run(["merge-file", "-p", "--diff3", "--object-id", "-L", "ours", "-L", "base", "-L", "theirs",
                        at_p1[1], at_mb[1], at_p2[1]])
    if not isinstance(code, int) or isinstance(code, bool) or not 0 <= code <= _MAX_CONFLICTS or not isinstance(merged, str):
        return None
    a, b = _lines_of(merged), _lines_of(texts[3])
    # axis: a file identical to git's automatic merge has no hand-made line only when that merge was clean; one that still holds git's conflict blocks was never resolved, so it is never passed over while another file's hunks are listed — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-unresolved-whole)
    if a == b:
        return [] if code == 0 else None
    # axis: a file git merged without a conflict has no hand-made line to read, so an edit in it, or in a file neither parent changed, is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-clean-edit, E-cf-untouched)
    if code == 0:
        return None
    blocks = _conflict_blocks(a)
    if blocks is None or min(len(blocks), _MAX_CONFLICTS) != code:
        return None
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    removed = set()
    for tag, i1, i2, _, _ in ops:
        if tag in ("replace", "delete"):
            removed.update(range(i1, i2))
    # axis: a conflict block whose markers survive in the file was never resolved, so it is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-unresolved)
    if not all(mark in removed for _, _, marks in blocks for mark in marks):
        return None
    hunks = []
    for lo, hi in _hunk_ranges(ops, blocks, len(a)):
        header, hunk = _hunk_text(a, b, ops, lo, hi)
        hunks.append({"file": path, "merge": c, "parents": [p1, p2], "mergeBase": mb, "kind": KIND_CONFLICT_FIX,
                      "header": header, "text": hunk})
    return hunks


def _conflict_fix(run, base, x, head, remaining, commits):
    """The hunks the vet reads when every new commit is the builder's merge of the base into the pull request and the
    only lines of the head that git's own automatic merge did not make are listed; else None (the module docstring's
    step 8 paragraph). ``[]`` means no hand-made line anywhere. Every failed git read is None."""
    if not commits:
        return None
    shas = {commit["sha"] for commit in commits}
    hunks = []
    for commit in commits:
        c = commit["sha"]
        code, text = run(["rev-list", "--parents", "-n", "1", c])
        words = text.split() if code == 0 and isinstance(text, str) else []
        if not words or words[0] != c or not all(returning_review._is_sha(word) for word in words):
            return None
        parents = words[1:]
        # axis: a new commit that is not a two-parent merge is code nobody saw merged, so it is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-nonmerge)
        if len(parents) != 2:
            return None
        p1, p2 = parents
        code, _ = run(["merge-base", "--is-ancestor", p2, base])
        # axis: the second parent is the base or an ancestor of it, so a merge of a side branch is never read as the base brought in — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-side)
        if code != 0:
            return None
        # axis: the first parent is the certified commit or another new commit, so a merge built on an older commit that drops reviewed code is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-first)
        if p1 != x and p1 not in shas:
            return None
        code, text = run(["merge-base", "--all", p1, p2])
        bases = text.split() if code == 0 and isinstance(text, str) else []
        # axis: the two parents have exactly one merge base, so a criss-cross merge, whose automatic merge the check cannot rebuild, is never read as a conflict fix — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-criss)
        if len(bases) != 1 or not returning_review._is_sha(bases[0]):
            return None
        for path in remaining:
            got = _conflict_fix_file(run, path, c, p1, p2, bases[0])
            if got is None:
                return None
            hunks.extend(got)
    return hunks


def check(repo_root, base, record, head, proof=(), builder_author=None, git=None, base_at_review=(), union_proof=None):
    """``{"answer": "proven" | "judgement" | "needs-review", ...}``: whether the commit ``record`` certifies covers
    ``head``. Never raises: every fault reads ``needs-review`` with a reason in ``why``. ``record`` is what
    ``review_record.py read --pr N`` prints, or the bare record. ``proof`` is a list of ``{file, source, sha256}``
    copy entries. ``git`` is the test seam ``returning_review.decide`` takes, ``git(argv) -> (returncode,
    stdout_text)``; production leaves it None. ``base_at_review`` is a list of full commit shas, each a second base
    whose tree git shows equals the base's tree (the second-base paragraph of the module docstring); a value that does
    not fit is ignored; empty, the check is as it was. ``union_proof`` is the vet's tested-union proof (the union
    paragraph of the module docstring); None, the result is exactly as it was and carries no ``unionProbe`` key."""
    try:
        got = _check_rewritten(repo_root, base, record, head, proof, builder_author, git, base_at_review)
        # axis: with no union proof the result is the check's own, key set included, so the proof path can never change an answer it was not asked about — see bite-proof record i2589_head_coverage_union_probe (E-absent)
        if union_proof is None:
            return got
        return _with_union(repo_root, base, record, head, proof, builder_author, git, base_at_review, got, union_proof)
    except Exception as exc:  # total: a fault nobody foresaw is still a review owed
        # axis: a fault of any kind reads needs-review, never an answer that covers the head — see bite-proof record i2496_wo_a_head_coverage (E-fail)
        result = _result(base, head)
        _needs_review(result, WHY_CHECK_FAILED, "the check failed on %s: %s" % (type(exc).__name__, exc))
        if union_proof is not None:
            _union_ignored(result, union_proof, "not-consulted")
        return result


def _token_of(line):
    return line.split(":", 1)[0]


def _tree_of(run, rev):
    """The tree sha of commit ``rev``, or None when git cannot read it."""
    code, text = run(["rev-parse", "--verify", "--quiet", "%s^{tree}" % rev])
    tree = text.strip() if isinstance(text, str) else ""
    return tree if code == 0 and returning_review._is_sha(tree) else None


def _check_rewritten(repo_root, base, record, head, proof, builder_author, git, base_at_review):
    """``_check`` against the base, and, when the caller gave second bases, against each valid one of them (the
    second-base paragraph of the module docstring). With none given, or none valid, the answer is ``_check``'s."""
    first = _check(repo_root, base, record, head, proof, builder_author, git)
    if base_at_review is None:
        values = []
    elif isinstance(base_at_review, str):
        values = [base_at_review]
    elif isinstance(base_at_review, (list, tuple)):
        values = list(base_at_review)
    else:
        values = [base_at_review]  # not a sha: it reads input-invalid below
    if not values:
        return first
    x = first["certified"]
    if x is None or (first["answer"] == PROVEN and any(_token_of(w) == WHY_SAME_COMMIT for w in first["why"])):
        return first
    if not (returning_review._is_sha(base) and all(returning_review._is_sha(v) for v in values)):
        return _needs_review(_result(base, head, x), WHY_INPUT_INVALID, "every base at review must be a full commit sha")
    run = git if git is not None else returning_review.production_git(repo_root)
    base_tree = _tree_of(run, base)
    valid = []
    ignored = []
    for value in values:
        reason = _ignored_reason(run, x, value, base_tree)
        if reason is None:
            valid.append(value)
        else:
            ignored.append(_line(WHY_BASE_AT_REVIEW_IGNORED, "%s %s" % (value[:8], reason)))
    # axis: a second base that is ignored never changes the answer from the check's own without it — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
    if first["answer"] == PROVEN or not valid:
        first["why"].extend(ignored)
        return first
    gots = [(value, _check(repo_root, base, record, head, proof, builder_author, git, x_base=value)) for value in valid]
    chosen = None
    for value, got in gots:
        if got["answer"] == PROVEN:
            chosen = (value, got)
            break
    if chosen is None and first["answer"] == JUDGEMENT:
        first["why"].extend(ignored)
        return first
    if chosen is None:
        for value, got in gots:
            if got["answer"] == JUDGEMENT:
                chosen = (value, got)
                break
    if chosen is None:
        chosen = gots[0]
    value, result = chosen
    result["why"].append(_line(WHY_BASE_AT_REVIEW, "the certified commit's own change was read against %s, a base at review "
                                                   "that holds the base's tree" % value[:7]))
    # axis: a second base that is ignored never changes the answer a valid second base proves, and is reported beside it — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
    result["why"].extend(ignored)
    return result


def _ignored_reason(run, x, value, base_tree):
    """Why a full-sha second base is ignored (``unreadable``, ``other-tree`` or ``no-merge-base``), or None when it is
    valid: git reads its tree, the tree equals the base's, and it shares a merge base with X."""
    tree = _tree_of(run, value)
    # axis: a second base whose tree git could not read, or that shares no merge base with the certified commit, is never tried — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
    if base_tree is None or tree is None:
        return "unreadable"
    # axis: a second base whose tree differs from the base's tree is never tried, so a commit from the layer's own history never lets a dropped change read proven — see bite-proof record i2561_head_coverage_rewritten_below (E-tree)
    if tree != base_tree:
        return "other-tree"
    code, text = run(["merge-base", x, value])
    if code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else ""):
        return "no-merge-base"
    return None


def _lower_sha(value):
    """True for a full sha in the lower case git prints; ``returning_review._is_sha`` also reads upper case, which would
    never equal what git prints back."""
    return returning_review._is_sha(value) and value == value.lower()


def _union_probe_of(union_proof):
    """The probe the proof names when it is a string, else None; for the report only."""
    probe = union_proof.get("probe") if isinstance(union_proof, dict) else None
    return probe if isinstance(probe, str) else None


def _short(value):
    """The first 8 characters of a hex sha for a ``why`` line, or ``none``: text that is not hex is never echoed."""
    return value[:8] if isinstance(value, str) and _HEX_PREFIX_RE.fullmatch(value[:8]) else "none"


def _union_ignored(result, union_proof, reason):
    """``result`` with a ``union-probe-ignored`` line and a ``unionProbe`` that was not used; the answer is untouched."""
    probe = _union_probe_of(union_proof)
    result["why"].append(_line(WHY_UNION_IGNORED, "%s %s" % (_short(probe), reason)))
    result["unionProbe"] = {"probe": probe, "used": False, "reason": reason, "covers": []}
    return result


def _union_other_parent(run, probe, base):
    """The probe's parent that is not the base when git prints exactly two parents, one of them the base and the other
    not; else None."""
    code, text = run(["rev-list", "--parents", "-n", "1", probe])
    words = text.split() if code == 0 and isinstance(text, str) else []
    if len(words) != 3 or words[0] != probe or not all(returning_review._is_sha(w) for w in words):
        return None
    parents = words[1:]
    if base not in parents:
        return None
    other = parents[0] if parents[1] == base else parents[1]
    return other if other != base else None


def _union_refusal(run, repo_root, base, record, head, proof, builder_author, git, base_at_review, got, union_proof):
    """``(reason, parent)``: the reason word of the first test the union proof fails (the module docstring's union
    paragraph), or ``(None, parent)`` when it passes all eight, with ``parent`` the probe's non-base parent."""
    # axis: a proof that is not exactly the union-probe/1 object, with full lower-case shas, proves nothing — see bite-proof record i2589_head_coverage_union_probe (E-shape)
    if not (isinstance(union_proof, dict) and set(union_proof) == _UNION_KEYS and union_proof["schema"] == UNION_SCHEMA
            and all(_lower_sha(union_proof[key]) for key in ("probe", "tree", "base"))):
        return "malformed", None
    probe, tree = union_proof["probe"], union_proof["tree"]
    receipt = union_proof["receipt"]
    command = receipt.get("command") if isinstance(receipt, dict) else None
    exit_code = receipt.get("exitCode") if isinstance(receipt, dict) else None
    # axis: a probe counts only with a test receipt that ran a command, exited 0 and names the proof's own tree — see bite-proof record i2589_head_coverage_union_probe (E-receipt)
    if not (isinstance(receipt, dict) and set(receipt) == _UNION_RECEIPT_KEYS and isinstance(command, str)
            and command.strip() and isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code == 0
            and receipt["tree"] == tree):
        return "no-receipt", None
    # axis: the probe merged exactly the check's base, so a probe of another base, even one with the same tree, proves nothing — see bite-proof record i2589_head_coverage_union_probe (E-base)
    if union_proof["base"] != base:
        return "other-base", None
    code, text = run(["cat-file", "-t", probe])
    # axis: the probe must be a commit git can read, so a missing object, a tree or a blob is never a probe — see bite-proof record i2589_head_coverage_union_probe (E-readable)
    if code != 0 or not isinstance(text, str) or text.strip() != "commit":
        return "probe-unreadable", None
    probe_tree = _tree_of(run, probe)
    # axis: the tree the receipt tested is git's tree of the probe, never the proof's own word for it — see bite-proof record i2589_head_coverage_union_probe (E-confirm)
    if probe_tree is None or probe_tree != tree:
        return "tree-unconfirmed", None
    other = _union_other_parent(run, probe, base)
    # axis: the probe is a two-parent merge of the base and a commit the review covers (the certified commit, or one the check proves from it), so a probe of unreviewed code proves nothing — see bite-proof record i2589_head_coverage_union_probe (E-parent)
    if other is None or not (other == got["certified"] or _check_rewritten(
            repo_root, base, record, other, proof, builder_author, git, base_at_review)["answer"] == PROVEN):
        return "other-commit", None
    code, _ = run(["merge-base", "--is-ancestor", base, head])
    # axis: the head contains the base, so a head that only holds the probe's files is not the tested merge — see bite-proof record i2589_head_coverage_union_probe (E-current)
    if code != 0:
        return "head-not-current", other
    head_tree = _tree_of(run, head)
    # axis: the head's tree is git's tree of the probe, byte and mode for byte and mode, so a head that differs at all was not tested — see bite-proof record i2589_head_coverage_union_probe (E-tree)
    if head_tree is None or head_tree != probe_tree:
        return "other-tree", other
    return None, other


def _with_union(repo_root, base, record, head, proof, builder_author, git, base_at_review, got, union_proof):
    """``got`` with the union proof applied (the union paragraph of the module docstring): proven when git shows the
    head is the tree of the tested probe, else ``got`` as it was with a ``union-probe-ignored`` line. Always adds
    ``unionProbe``."""
    if got["answer"] == PROVEN:
        got["unionProbe"] = {"probe": _union_probe_of(union_proof), "used": False, "reason": None, "covers": []}
        return got
    # axis: a check that could not read its inputs never consults the proof, so a proof cannot turn an unreadable check into an answer — see bite-proof record i2589_head_coverage_union_probe (E-consulted)
    if got["certified"] is None or any(_token_of(line) in _UNION_UNREAD_WHY for line in got["why"]):
        return _union_ignored(got, union_proof, "not-consulted")
    run = git if git is not None else returning_review.production_git(repo_root)
    reason, other = _union_refusal(run, repo_root, base, record, head, proof, builder_author, git, base_at_review, got,
                                   union_proof)
    if reason is not None:
        return _union_ignored(got, union_proof, reason)
    covers = list(got["files"])
    probe = union_proof["probe"]
    got["unionProbe"] = {"probe": probe, "used": True, "reason": None, "covers": covers, "tree": union_proof["tree"],
                         "base": base, "parent": other, "receipt": union_proof["receipt"]}
    got["answer"] = PROVEN
    got["files"] = []
    got["hunks"] = []
    got["why"] = [_line(WHY_PROVEN_UNION, "the head's tree is git's tree of the vet's tested union probe %s of %s and the "
                                          "base %s; it covers %d file(s)" % (_short(probe), _short(other), _short(base),
                                                                              len(covers)))]
    return got


def _check(repo_root, base, record, head, proof, builder_author, git, x_base=None):
    x = _certified(record)
    result = _result(base, head, x)
    # 1. the record
    if x is None:
        return _needs_review(result, WHY_RECORD_UNUSABLE,
                             "the review record is not an ok, unabandoned record with a full final commit sha")
    # 2. nothing happened since the review
    if head == x:
        result["answer"] = PROVEN
        result["why"].append(_line(WHY_SAME_COMMIT, "the head is the commit the review certified"))
        return result
    # 3. the inputs
    if not (returning_review._is_sha(base) and returning_review._is_sha(head)):
        return _needs_review(result, WHY_INPUT_INVALID, "the base and the head must each be a full commit sha")
    run = git if git is not None else returning_review.production_git(repo_root)

    # 4. the changed files
    changed = returning_review.changed_files(run, base, x, head, x_base=x_base)
    if changed is None:
        return _needs_review(result, WHY_DIFF_UNREADABLE,
                             "git could not produce the diff of the certified commit or of the head against the base")
    files, sources = changed
    # every rename or copy source path some changed file names; one rule reads them (see ``outstanding`` below)
    all_sources = set().union(*(sources.get(p, set()) for p in files))

    # 5. the reconstruction proof
    remaining = []
    modes = {path: (_mode(run, x, path), _mode(run, head, path)) for path in files}
    # A file the change renames or copies from another path, and that X does not hold yet (or whose mode at X git
    # could not read), was moved after the review: it is never reconstructed or proven by a copy.
    moved = {path for path in files if sources.get(path) and not _real_mode(modes[path][0])}
    for path in files:
        # axis: a renamed or copied file is never reconstructed and never dropped as a copy, since its path is behaviour — see bite-proof record i2496_wo_a_head_coverage (E-rename)
        if path in moved:
            remaining.append(path)
            continue
        # axis: a file whose mode differs between X and the head is never reconstructed, since equal bytes are not an equal file — see bite-proof record i2496_wo_a_head_coverage (E-mode)
        # a mode git could not read (None) and a file that is not in a tree (ABSENT) are no mode: two equal real modes only
        same_mode = _real_mode(modes[path][0]) and _real_mode(modes[path][1]) and modes[path][0] == modes[path][1]
        # axis: a file is reconstructed only when a clean three-way merge of X, the fork and the base reproduces the head blob byte for byte, so a hand-resolved file stays changed — see bite-proof record i2496_wo_a_head_coverage (E-recon)
        if same_mode and returning_review.merge_reproduces_head(run, base, x, head, path, fork_base=x_base):
            result["reconstructed"].append(path)
        else:
            remaining.append(path)

    # 6. the proven copies
    if remaining:
        entries = _copies_of(proof)
        # axis: a proof entry counts only when git re-validates it at the head; the entry's own word proves nothing — see bite-proof record i2496_wo_a_head_coverage (E-copy)
        valid = review_record.revalidated_copies(entries, os.fspath(repo_root), base, head) if entries else []
        # A copy proves bytes only: a copied file keeps its mode at X (two equal real modes), or is new (ABSENT at X,
        # git exited 0 and listed nothing) and plain (100644) at the head. A mode git could not read (None) keeps the
        # file changed.
        # A copy proof is judged on the file's own bytes and mode alone; a source path it leaves behind is read below.
        wanted = {path for path in remaining if path not in moved and (
                  (_real_mode(modes[path][0]) and modes[path][0] == modes[path][1])
                  or (modes[path][0] is ABSENT and modes[path][1] == "100644"))}
        for entry in valid:
            if entry["file"] in wanted and entry["file"] not in {c["file"] for c in result["copies"]}:
                result["copies"].append({"file": entry["file"], "source": entry["source"], "sha256": entry["sha256"]})
        relied = {c["file"] for c in result["copies"]}
        remaining = [path for path in remaining if path not in relied]
    result["files"] = remaining
    # A source path is read exactly when some changed file names it as a rename or copy source and it is not itself a
    # file a copy proof settled (a copy's own ``source`` field plays no part): no move hides a deletion, and no
    # reviewed rename blocks a proof. A source that is itself a remaining file is read as that file.
    # axis: every rename or copy source that no copy proof settled is read at the head, so a move over a reviewed path never hides the deletion of its source and a copy proof on the destination never settles it — see bite-proof record i2496_wo_a_head_coverage (E-rename-one-rule)
    outstanding = sorted(all_sources - {c["file"] for c in result["copies"]} - set(remaining))

    # 7. nothing left
    # With no file left, the only thing that can still differ is an outstanding source path: proven needs git to read
    # those paths and show nothing; a git failure there is a review owed, and a difference goes on to step 8.
    source_diff_empty = False
    if not remaining:
        source_diff_empty = True
        if outstanding:
            code, source_diff = run(["diff", *returning_review._DIFF_ARGS, x, head, "--", *outstanding])
            if code != 0 or not isinstance(source_diff, str):
                return _needs_review(result, WHY_DIFF_UNREADABLE,
                                     "git could not produce the diff of the rename and copy source paths from the certified "
                                     "commit to the head")
            source_diff_empty = source_diff == ""
    if not remaining and source_diff_empty:
        result["answer"] = PROVEN
        if result["copies"]:
            result["why"].append(_line(WHY_PROVEN_COPIES, "%d file(s) are copies git re-validated at the head, and the pull "
                                                          "request's own change is otherwise the reviewed change" % len(result["copies"])))
        else:
            result["why"].append(_line(WHY_OWN_CHANGE_UNCHANGED, "git shows the pull request's own change at the head equals "
                                                                 "the reviewed change"))
        return result

    # 8. judgement or a review owed
    # The outstanding source paths come in with the remaining files, so a move into a path the review already held still
    # shows its source's deletion; with no remaining file, the sections the source paths show are the whole read.
    qualifies, hunks, reason = _qualification(run, x, head, remaining, outstanding)
    commits = _authors(run, base, x, head)
    builder = builder_author.strip().lower() if isinstance(builder_author, str) and builder_author.strip() \
        else _author_email(run, x)
    if commits is not None:
        result["commits"] = commits
    # axis: a judgement answer needs the builder to have authored every new commit; another author, an unreadable author or no commit to name reads needs-review — see bite-proof record i2496_wo_a_head_coverage (E-author)
    authors_ok = commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)
    if not authors_ok:
        if commits is None or builder is None:
            text = "git could not name the new commits and their authors"
        else:
            text = "a new commit is by someone other than the builder: %s" % ", ".join(
                sorted({c["author"] for c in commits if c["author"].lower() != builder.lower()}))
        _needs_review(result, WHY_OTHER_AUTHOR, text)
    # A judgement answer needs the content rule and the author rule both; either failing is needs-review. The one
    # exception is a builder's conflict fix: files that do not qualify, read at the merges that made them.
    if not qualifies:
        # axis: a conflict fix is read only when the builder authored every new commit, so another author's merge stays needs-review — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-author)
        may_read = authors_ok
        # axis: a conflict fix is read only when no rename or copy source is outstanding and no remaining file is a moved one, so a move after review keeps today's answer — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-rename)
        may_read = may_read and not outstanding and not any(path in moved for path in remaining)
        fix = _conflict_fix(run, base, x, head, remaining, commits) if may_read else None
        if fix:
            result["answer"] = JUDGEMENT
            result["hunks"] = fix
            result["files"] = list(dict.fromkeys([*remaining, *(h["file"] for h in fix)]))
            result["why"].append(_line(WHY_CONFLICT_FIX, "every new commit is a merge by the builder that brings the base in; "
                                                         "the vet reads the %d hand-made hunk(s) of the conflict fix against "
                                                         "both sides" % len(fix)))
        else:
            _needs_review(result, WHY_BEHAVIOUR_CHANGE, reason)
    if authors_ok and qualifies:
        result["answer"] = JUDGEMENT
        result["hunks"] = hunks
        result["files"] = list(dict.fromkeys([*result["files"], *(h["file"] for h in hunks)]))
        result["why"].append(_line(WHY_PROSE_OR_COMMENTS, "every remaining difference is prose or comment lines by the builder; "
                                                          "the vet reads the %d hunk(s)" % len(hunks)))
    return result


def outcome(answer, ci, judged_clear=False, sheet="none", sheet_commit=None, head=None, carry_answer=None,
            carry_judged_clear=False):
    """``{"outcome", "why", "review", "sheet"}`` from the check's ``answer``, CI on the head, whether the vet cleared a
    judgement, the merge sheet's state, and the second check's answer (``carry_answer``, run from the sheet's own commit
    to the head, with ``carry_judged_clear``). Pure; a value outside its set raises ``ValueError``."""
    if answer not in ANSWERS:
        raise ValueError("answer must be one of %s" % ", ".join(ANSWERS))
    if ci not in CI_STATES:
        raise ValueError("ci must be one of %s" % ", ".join(CI_STATES))
    if sheet not in SHEETS:
        raise ValueError("sheet must be one of %s" % ", ".join(SHEETS))
    if carry_answer is not None and carry_answer not in ANSWERS:
        raise ValueError("carry answer must be one of %s" % ", ".join(ANSWERS))
    if sheet != "none":
        # axis: with a sheet, the sheet's commit and the head are full 40-hex shas, never an abbreviation, a ref or
        # nothing, so "the head moved past the sheet" is a comparison of two commits — see bite-proof record
        # i2496_v962_carry_answer (E-sha)
        for name, value in (("sheet commit", sheet_commit), ("head", head)):
            if not (isinstance(value, str) and _FULL_SHA_40.fullmatch(value)):
                raise ValueError("%s must be a full 40-hex sha when a sheet is given" % name)
    moved = sheet == "live" and sheet_commit != head
    if moved and carry_answer is None:
        raise ValueError("a live sheet whose head moved needs the carry answer: the check run from the sheet's commit "
                         "to the head")
    covered = answer == PROVEN or (answer == JUDGEMENT and judged_clear is True)
    if ci == "red":
        verdict, why, review = NOT_READY, "ci-red", "none"
    elif not covered:
        verdict, review = NOT_READY, "returning"
        why = "judged-meaningful" if answer == JUDGEMENT else "needs-review"
    elif ci in ("pending", "none"):
        verdict, why, review = WAIT, "ci-not-green", "none"
    else:
        verdict, why, review = READY, "covered", "none"
    if sheet == "none":
        action = "none"
    elif sheet == "held":
        action = "republish-unsigned" if verdict == READY else "keep"
    elif verdict == NOT_READY:
        action = "take-down"
    elif verdict == READY and moved:
        # axis: a verdict carries onto the moved head only when the check from the sheet's own commit covers it
        # (proven, or a judgement the vet cleared); a head whose record proves it but whose sheet saw other code is
        # republished unsigned — see bite-proof record i2496_v962_carry_answer (E-carry)
        carried = carry_answer == PROVEN or (carry_answer == JUDGEMENT and carry_judged_clear is True)
        action = "republish-carried" if carried else "republish-unsigned"
    else:
        action = "keep"
    return {"outcome": verdict, "why": why, "review": review, "sheet": action}


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def _usage_error(message):
    sys.stderr.write("head_coverage: %s\n" % message)
    return 2


def _read_json(path):
    """``(object, None)`` for a JSON file, else ``(None, fault)``."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.loads(handle.read()), None
    except (OSError, ValueError, UnicodeError):
        return None, "unreadable"


def _check_cli(args):
    if not os.path.isdir(args.repo_root):
        return _usage_error("--repo-root is not a directory: %s" % args.repo_root)
    record, fault = _read_json(args.record)
    if fault is not None:
        return _usage_error("--record is not a readable JSON file: %s" % args.record)
    proof = []
    if args.proof is not None:
        loaded, fault = _read_json(args.proof)
        if fault is not None:
            return _usage_error("--proof is not a readable JSON file: %s" % args.proof)
        if isinstance(loaded, dict):
            loaded, fault = countable_lines.load_proof(args.proof)
            if fault is not None:
                return _usage_error("--proof is not a usable copy proof: %s" % fault)
            loaded = loaded["copies"]
        elif not isinstance(loaded, list) or countable_lines.copies_fault(loaded, name_extra_key=True) is not None:
            return _usage_error("--proof is not a usable list of copies")
        proof = loaded
    union_proof = None
    if args.union_proof is not None:
        union_proof, fault = _read_json(args.union_proof)
        if fault is not None:
            return _usage_error("--union-proof is not a readable JSON file: %s" % args.union_proof)
        # None always means no flag, so a file that holds null is no proof
        if union_proof is None:
            return _usage_error("--union-proof file holds no proof (null): %s" % args.union_proof)
    result = check(args.repo_root, args.base, record, args.head, proof, builder_author=args.builder_author,
                   base_at_review=args.base_at_review or [], union_proof=union_proof)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def _outcome_cli(args):
    try:
        result = outcome(args.answer, args.ci, judged_clear=args.judged_clear, sheet=args.sheet,
                         sheet_commit=args.sheet_commit, head=args.head, carry_answer=args.carry_answer,
                         carry_judged_clear=args.carry_judged_clear)
    except ValueError as exc:
        return _usage_error(str(exc))
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="head_coverage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("check")
    cp.add_argument("--repo-root", required=True)
    cp.add_argument("--base", required=True)
    cp.add_argument("--record", required=True)
    cp.add_argument("--head", required=True)
    cp.add_argument("--proof", default=None)
    cp.add_argument("--builder-author", default=None)
    cp.add_argument("--base-at-review", action="append", default=None)
    cp.add_argument("--union-proof", default=None)
    op = sub.add_parser("outcome")
    op.add_argument("--answer", required=True)
    op.add_argument("--ci", required=True)
    op.add_argument("--judged-clear", action="store_true")
    op.add_argument("--sheet", default="none")
    op.add_argument("--sheet-commit", default=None)
    op.add_argument("--head", default=None)
    op.add_argument("--carry-answer", default=None)
    op.add_argument("--carry-judged-clear", action="store_true")
    args = ap.parse_args(argv)
    return _check_cli(args) if args.cmd == "check" else _outcome_cli(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
