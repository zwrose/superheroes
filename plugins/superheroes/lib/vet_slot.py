#!/usr/bin/env python3
"""Write or check the advisor-vet slot of a PR body against its vet receipt.

Consumers: the showrunner vet's owner-half write (``write``) and the merged or
closed-PR follow-ups sweep (``check``). ``write`` changes the PR body only in the
span strictly between the advisor-vet marker line and the build-record marker
line, and only after every follow-up id in the build record has exactly one
recognized disposition bullet in the latest vet receipt (and vice versa). Any
failed read or check is a refusal with one of ten reasons (``bad-argument``,
``read-failed``, ``markers-invalid``, ``followups-malformed``, ``receipt-missing``,
``dispositions-malformed``, ``followup-undispositioned``, ``none-over-list``,
``write-failed``, ``write-unconfirmed``) and a detail naming what was wrong; no edit
is made, except for ``write-unconfirmed``: the edit call was launched (and may have
failed) but the readback failed or differed from the pushed body. One JSON line on stdout; exit 0 on ok, 1 on refusal."""
import argparse
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import grounding_stage  # noqa: E402
import md_fence  # noqa: E402

GH_TIMEOUT = 120
RECEIPT_MARKER = "<!-- superheroes:vet-receipt -->"
PENDING_MARKER = "<!-- superheroes:pending-proposals -->"
FOLLOWUPS_HEADING = "Follow-ups for the advisor"
DISPOSITIONS_PREFIX = "**Dispositions — completed"
CLASSES = frozenset({"owner-call", "defect", "craft", "flake", "info"})
DISPOSITIONS = frozenset({"fixed", "filed", "folded", "collector", "declined", "info"})
NONE_WORDS = ("None", "`None`")

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_ITEM_RE = re.compile(r"^- FU(\d+) \[([a-z-]+)\] \S")
_NESTED_RE = re.compile(r"^(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?FU\d+\b")
_ANY_ITEM_RE = re.compile(r"^(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?FU(\d+) \[")
_COUNT_RE = re.compile(r"^Follow-ups: (\d+) \((\d+) owner-call\)$")
_DISPOSITION_RE = re.compile(r"^- FU(\d+): (\S.*)$")


class _Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _malformed(detail):
    return _Refusal("followups-malformed", detail)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(2)  # no usage text: stdout carries exactly one JSON line


def _refusal(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail}


def _lines(text):
    """(bare lines, start offsets)."""
    lines = text.splitlines(keepends=True)
    starts, pos = [], 0
    for line in lines:
        starts.append(pos)
        pos += len(line)
    return [line.rstrip("\r\n") for line in lines], starts


def _heading(line):
    match = _HEADING_RE.match(line)
    if not match:
        return None, None
    text = re.sub(r"(?:^|[ \t]+)#+$", "", (match.group(2) or "")).strip()
    return len(match.group(1)), text


def _parse_followups(body, build_offset):
    """Return the list of FU ids, or None for an explicit ``None`` section.

    The section parse checks the format; then every FU-item-shaped live line anywhere below the
    build-record marker must be one of the section's own item lines, counted, not deduplicated."""
    bare, starts = _lines(body)
    inert = md_fence.scan_contexts(bare).inert
    first = next(i for i, s in enumerate(starts) if s >= build_offset)
    live = [i for i in range(first, len(bare)) if not inert[i]]
    headings = [i for i in live if _heading(bare[i])[1] == FOLLOWUPS_HEADING]
    if len(headings) > 1:
        raise _malformed("follow-ups heading appears %d times" % len(headings))
    ids = _parse_section(bare, inert, first)
    spare, outside = list(ids or []), []
    for i in live:
        match = _ANY_ITEM_RE.match(bare[i].strip())
        fu = match and "FU%d" % int(match.group(1))
        if fu in spare:
            spare.remove(fu)
        elif fu:
            outside.append(fu)
    if outside:
        raise _malformed("follow-up ids outside the follow-ups list: %s" % ", ".join(outside))
    return ids


def _parse_section(bare, inert, first):
    heading_at = level = None
    depth = 0  # live <details nesting; the first opener is the build record's own

    def closes_record(i):
        nonlocal depth
        if inert[i]:
            return False
        line = bare[i].strip()
        if line.startswith("<details") and not line.endswith("</details>"):
            depth += 1
        elif line == "</details>":
            depth -= 1
            return depth <= 0
        return False

    for i in range(first, len(bare)):
        if closes_record(i):
            break
        lvl, text = (None, None) if inert[i] else _heading(bare[i])
        if lvl is not None and text == FOLLOWUPS_HEADING:
            heading_at, level = i, lvl
            break
    if heading_at is None:
        raise _malformed("no %r heading inside the build record" % FOLLOWUPS_HEADING)
    section = []
    for i in range(heading_at + 1, len(bare)):
        if not inert[i]:
            lvl, _ = _heading(bare[i])
            if (lvl is not None and lvl <= level) or closes_record(i):
                break
        if bare[i].strip():
            section.append((bare[i], inert[i]))
    count = None
    if section and not section[0][1] and _COUNT_RE.match(section[0][0].rstrip()):
        count = _COUNT_RE.match(section[0][0].rstrip())
        section = section[1:]
    if len(section) == 1 and not section[0][1] and section[0][0].strip() in NONE_WORDS:
        if count is not None and (count.group(1), count.group(2)) != ("0", "0"):
            raise _malformed("count line says %s (%s owner-call) over None" % (
                count.group(1), count.group(2)))
        return None
    ids, owner_calls, have_item = [], 0, False
    for line, is_inert in section:
        indent = md_fence.indent_width(line)
        if is_inert or indent >= 2:
            if _NESTED_RE.match(line.lstrip()):
                raise _malformed("nested follow-up id: %s" % line.strip())
            if not have_item:
                raise _malformed("unkeyed line: %s" % line.strip())
            continue
        match = _ITEM_RE.match(line)
        if not match:
            raise _malformed("unkeyed line: %s" % line.strip())
        if match.group(2) not in CLASSES:
            raise _malformed("unknown class: %s" % match.group(2))
        fu_id = "FU%d" % int(match.group(1))
        if fu_id in ids:
            raise _malformed("duplicate follow-up id: %s" % fu_id)
        ids.append(fu_id)
        owner_calls += match.group(2) == "owner-call"
        have_item = True
    if not ids:
        raise _malformed("unkeyed section: no follow-up items and not None")
    if count is not None and (int(count.group(1)), int(count.group(2))) != (len(ids), owner_calls):
        raise _malformed("count line says %s (%s owner-call), items are %d (%d owner-call)" % (
            count.group(1), count.group(2), len(ids), owner_calls))
    return ids


def analyze_body(body):
    """Check the body's markers and follow-ups; return (advisor_offset, build_offset, ids)."""
    if not body.strip():
        raise _Refusal("read-failed", "PR body is empty")
    offsets = {}
    for name in ("advisor-vet", "build-record"):
        found = grounding_stage.find_standalone_markers(body, grounding_stage.REGION_MARKERS[name])
        if len(found) != 1:
            raise _Refusal("markers-invalid", "%s marker appears %d times" % (name, len(found)))
        offsets[name] = found[0]
    if offsets["advisor-vet"] >= offsets["build-record"]:
        raise _Refusal("markers-invalid", "advisor-vet marker is not above the build-record marker")
    ids = _parse_followups(body, offsets["build-record"])
    return offsets["advisor-vet"], offsets["build-record"], ids


def check_slot_text(slot_text):
    if not isinstance(slot_text, str) or not slot_text.strip():
        raise _Refusal("write-failed", "slot text is empty")
    for line in slot_text.splitlines():
        if line.strip().startswith("<!-- superheroes:"):
            raise _Refusal("write-failed", "slot text carries a marker: %s" % line.strip())


def _select_receipt(comments):
    best = None
    for comment in comments:
        first = comment["body"].lstrip("﻿ \t\r\n").splitlines()
        if first and first[0].rstrip() == RECEIPT_MARKER:
            if best is None or comment["created_at"] >= best["created_at"]:
                best = comment
    return best


def _parse_dispositions(receipt_body):
    """Return the list of FU ids disposed, or None for an explicit ``None`` field."""
    bare, _ = _lines(receipt_body)
    inert = md_fence.scan_contexts(bare).inert
    start = next((i for i, l in enumerate(bare)
                  if not inert[i] and l.lstrip().startswith(DISPOSITIONS_PREFIX)), None)
    end = None if start is None else next(
        (i for i in range(start + 1, len(bare)) if not inert[i] and bare[i].strip() == PENDING_MARKER),
        None)
    if end is None:
        raise _Refusal("dispositions-malformed", "no completed-dispositions field closed by the "
                       "pending-proposals marker")
    head = bare[start].lstrip()[len(DISPOSITIONS_PREFIX):]
    close = head.find("**")
    pieces = [head[close + 2:].strip()] if close >= 0 else []
    pieces = [p for p in pieces + [l.strip() for l in bare[start + 1:end]] if p]
    if len(pieces) == 1 and pieces[0] in NONE_WORDS:
        return None
    tail = [head[close + 2:].strip()] if close >= 0 else []
    has_none = any(p in NONE_WORDS for p in tail + [
        bare[i].strip() for i in range(start + 1, end) if not inert[i]])
    ids = []
    for i in range(start + 1, end):
        match = None if inert[i] else _DISPOSITION_RE.match(bare[i])
        if not match:
            continue
        fu_id = "FU%d" % int(match.group(1))
        word = match.group(2).split()[0].lower().rstrip(string.punctuation)
        if word not in DISPOSITIONS:
            raise _Refusal("dispositions-malformed", "unrecognized disposition %s: %s" % (fu_id, word))
        if fu_id in ids:
            raise _Refusal("dispositions-malformed", "duplicate disposition for %s" % fu_id)
        ids.append(fu_id)
    if has_none and ids:
        raise _Refusal("dispositions-malformed", "None and keyed dispositions both appear: %s"
                       % ", ".join(ids))
    return ids


def evaluate(verb, body, comments, slot_text=None):
    """The chokepoint: every check, then the result (with ``newBody`` for write)."""
    try:
        advisor_at, build_at, ids = analyze_body(body)
        if verb == "write":
            check_slot_text(slot_text)
        receipt = _select_receipt(comments)
        if receipt is None:
            if verb == "check" and ids is None:
                return {"ok": True, "verb": "check", "followups": [], "receipt": None,
                        "receiptPresent": False}
            raise _Refusal("receipt-missing", "no comment opens with the vet-receipt marker")
        disposed = _parse_dispositions(receipt["body"])
        if ids is not None and disposed is None:
            raise _Refusal("none-over-list", "receipt dispositions read None over %s" % ", ".join(ids))
        missing = [i for i in (ids or []) if i not in (disposed or [])]
        if missing:
            raise _Refusal("followup-undispositioned", "%s: no disposition" % ", ".join(missing))
        unknown = [i for i in (disposed or []) if i not in (ids or [])]
        if unknown:
            raise _Refusal("dispositions-malformed", "unknown follow-up ids: %s" % ", ".join(unknown))
    except _Refusal as exc:
        return _refusal(exc.reason, exc.detail)
    result = {"ok": True, "verb": verb, "followups": ids or [],
              "receipt": receipt.get("html_url") or receipt.get("id")}
    if verb == "check":
        result["receiptPresent"] = True
        return result
    a = body.index("\n", advisor_at) + 1
    b = body.rfind("\n", 0, build_at) + 1
    new_body = body[:a] + "\n" + slot_text.strip("\n") + "\n\n" + body[b:]
    tail = len(body) - b
    if new_body[:a] != body[:a] or new_body[len(new_body) - tail:] != body[b:]:
        return _refusal("write-failed", "span invariant violated")
    result["newBody"] = new_body
    return result


def _gh(run, argv, what, reason="read-failed"):
    """Run one gh call; a failure is ``reason`` with ``what`` leading the detail."""
    try:
        proc = run(argv, capture_output=True, text=True, timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise _Refusal(reason, "%s: gh call timed out" % what)
    except OSError as exc:
        raise _Refusal(reason, "%s: %s" % (what, exc))
    if proc.returncode != 0:
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        raise _Refusal(reason, "%s: exit %d %s" % (what, proc.returncode, out))
    return proc.stdout or ""


def _gh_json(run, argv, what):
    try:
        return json.loads(_gh(run, argv, what))
    except ValueError as exc:
        raise _Refusal("read-failed", "%s: bad JSON: %s" % (what, exc))


def _read_body(run, pr, repo):
    payload = _gh_json(run, ["gh", "pr", "view", str(pr), "-R", repo, "--json", "body"], "PR body")
    if not isinstance(payload, dict) or not isinstance(payload.get("body"), str):
        raise _Refusal("read-failed", "PR body: body is not a string")
    return payload["body"]


def _read_comments(run, pr, repo):
    argv = ["gh", "api", "repos/%s/issues/%d/comments" % (repo, pr), "--paginate", "--slurp"]
    pages = _gh_json(run, argv, "comments")
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise _Refusal("read-failed", "comments: pages are not lists")
    comments = [c for page in pages for c in page]
    for c in comments:
        if not (isinstance(c, dict) and isinstance(c.get("body"), str)
                and isinstance(c.get("created_at"), str)):
            raise _Refusal("read-failed", "comments: a comment lacks a string body or created_at")
    return comments


def _normalize(text):
    return text.replace("\r\n", "\n").rstrip()


def run_verb(verb, pr, repo, slot_file=None, run=None):
    if not isinstance(pr, int) or isinstance(pr, bool) or pr < 1:
        return _refusal("bad-argument", "pr must be a positive integer")
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        return _refusal("bad-argument", "repo must be owner/name")
    if verb not in ("write", "check") or (verb == "write") != (slot_file is not None):
        return _refusal("bad-argument", "write needs --slot-file; check takes none")
    try:
        return _run_verb(verb, pr, repo, slot_file, run or subprocess.run)
    except _Refusal as exc:
        return _refusal(exc.reason, exc.detail)


def _run_verb(verb, pr, repo, slot_file, run):
    if not shutil.which("gh"):
        raise _Refusal("read-failed", "gh not on PATH")
    body = _read_body(run, pr, repo)
    analyze_body(body)
    slot_text = None
    if verb == "write":
        try:
            with open(slot_file, encoding="utf-8") as handle:
                slot_text = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise _Refusal("write-failed", "slot file unreadable: %s" % exc)
        check_slot_text(slot_text)
    comments = _read_comments(run, pr, repo)
    result = evaluate(verb, body, comments, slot_text)
    if not result["ok"] or verb == "check":
        return result
    new_body = result.pop("newBody")
    if _read_body(run, pr, repo) != body:
        raise _Refusal("write-failed", "PR body changed between the read and the push")
    path = None
    pushed = "slot write already pushed"
    try:
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md",
                                             prefix="vet-slot-", delete=False) as handle:
                path = handle.name
                handle.write(new_body)
        except OSError as exc:
            raise _Refusal("write-failed", "edit: %s" % exc)
        try:  # once launched, a failed edit call is an unconfirmed write: read back
            _gh(run, ["gh", "pr", "edit", str(pr), "-R", repo, "--body-file", path], "edit",
                reason="write-unconfirmed")
        except _Refusal as exc:
            pushed = "slot edit call failed (%s)" % exc.detail
    finally:
        if path is not None and os.path.exists(path):
            os.unlink(path)
    try:
        readback = _read_body(run, pr, repo)
    except _Refusal as exc:
        raise _Refusal("write-unconfirmed", "%s; readback: %s" % (pushed, exc.detail))
    if _normalize(readback) != _normalize(new_body):
        raise _Refusal("write-unconfirmed", "%s; readback differs from the pushed body" % pushed)
    return result


def main(argv=None, run=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        parser = _Parser(prog="vet_slot", add_help=False)
        verbs = parser.add_subparsers(dest="verb")
        for name in ("write", "check"):
            sub = verbs.add_parser(name, add_help=False)
            sub.add_argument("--pr", type=int, required=True)
            sub.add_argument("--repo", required=True)
            if name == "write":
                sub.add_argument("--slot-file", required=True)
        args = parser.parse_args(argv)
        if args.verb not in ("write", "check"):
            raise SystemExit(2)
    except SystemExit:
        result = _refusal("bad-argument", "invalid command-line arguments")
    else:
        result = run_verb(args.verb, args.pr, args.repo, getattr(args, "slot_file", None), run=run)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
