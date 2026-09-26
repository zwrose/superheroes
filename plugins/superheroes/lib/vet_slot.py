#!/usr/bin/env python3
"""Write or check the advisor-vet slot of a PR body against its vet receipt.

Consumers: the showrunner vet's owner-half write (``write``) and the merged or
closed-PR follow-ups sweep (``check``). The writer compares two machine-readable
marker lists and reads no other prose: the build record's
``<!-- superheroes:followups FU1 FU2 -->`` marker (or ``none``) and the latest vet
receipt's ``<!-- superheroes:dispositions FU1 FU2 -->`` marker (or ``none``).
``write`` changes the PR body only in the span strictly between the advisor-vet
marker line and the build-record marker line, and only when the two lists name the
same ids. The followups marker is the builder's own declaration; the writer trusts
it and does not re-derive it from the prose; the vet reads both. Any failed read or
check is a refusal with one of nine reasons (``bad-argument``, ``read-failed``,
``markers-invalid``, ``receipt-missing``, ``followup-undispositioned``,
``disposition-unknown``, ``none-over-list``, ``write-failed``,
``write-unconfirmed``) and a detail naming what was wrong; no edit is made, except
for ``write-unconfirmed``: the edit call was launched (and may have failed) but the
readback failed or differed from the pushed body. One JSON line on stdout; exit 0
on ok, 1 on refusal."""
import argparse
import json
import os
import re
import shutil
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
FOLLOWUPS_MARKER_NAME = "followups"
DISPOSITIONS_MARKER_NAME = "dispositions"

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class _Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(2)  # no usage text: stdout carries exactly one JSON line


def _refusal(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail}


def _live_lines(text):
    """Yield ``(offset, line)`` for every line outside code fences and outside an open HTML comment.

    A line opens a comment only when, outside any fence, its first non-whitespace characters —
    after at most three columns of indentation — are ``<!--``; that comment stays open through
    later lines until one contains ``-->`` at or after the opener, and a ``<!--`` anywhere else in
    a line never changes the comment state."""
    raw = text.splitlines(keepends=True)
    bare = [line.rstrip("\r\n") for line in raw]
    inert = md_fence.scan_contexts(bare).inert
    offset, in_comment = 0, False
    for line, dead, whole in zip(bare, inert, raw):
        if not dead:
            if not in_comment:
                yield offset, line
            if in_comment:
                if "-->" in line:
                    in_comment = False
            else:
                stripped = line.lstrip(" \t")
                lead = len(line) - len(stripped)
                if md_fence.indent_width(line) <= 3 and stripped.startswith("<!--"):
                    if "-->" not in line[lead + 4:]:
                        in_comment = True
        offset += len(whole)


def read_marker_list(text, name, after=0):
    """Return the ids of the one live ``<!-- superheroes:<name> ... -->`` line, or None for ``none``.

    A marker line starts at column zero, outside any code fence and outside any HTML comment left
    open by an earlier line; it must not start above offset ``after``."""
    prefix = "<!-- superheroes:%s" % name
    found = []
    for offset, line in _live_lines(text):
        rest = line[len(prefix):]
        if line.startswith(prefix) and (rest[:1] == " " or rest[:3] == "-->"):
            found.append((offset, line))
    # axis: a followups or dispositions marker present other than exactly once refuses markers-invalid
    if len(found) != 1:
        raise _Refusal("markers-invalid", "%s marker appears %d times" % (name, len(found)))
    start, line = found[0]
    # axis: a followups marker above the build-record marker refuses markers-invalid
    if start < after:
        raise _Refusal("markers-invalid", "%s marker is not below the build-record marker" % name)
    match = re.match(r"^<!-- superheroes:%s (none|FU[1-9][0-9]*(?: FU[1-9][0-9]*)*) -->$"
                     % re.escape(name), line.rstrip())
    # axis: a marker line off the exact shape refuses markers-invalid
    if not match:
        raise _Refusal("markers-invalid", "%s marker is malformed: %s" % (name, line))
    if match.group(1) == "none":
        return None
    ids = match.group(1).split()
    for i, fu_id in enumerate(ids):
        # axis: an id listed twice in one marker refuses markers-invalid
        if fu_id in ids[:i]:
            raise _Refusal("markers-invalid", "%s marker repeats %s" % (name, fu_id))
    return ids


def _find_live_standalone_markers(body, marker):
    """Fence-aware, zero-indent standalone ``marker`` lines outside open HTML comments."""
    found = []
    for offset, line in _live_lines(body):
        if md_fence.indent_width(line) == 0 and line.strip() == marker:
            leading = len(line) - len(line.lstrip())
            found.append(offset + leading)
    return found


def analyze_body(body):
    """Check the body read and its markers; return (advisor_offset, build_offset, followups)."""
    # axis: an empty or non-string body read refuses read-failed
    if not isinstance(body, str) or not body.strip():
        raise _Refusal("read-failed", "PR body is empty" if isinstance(body, str) else
                       "PR body is not a string")
    offsets = {}
    for name in ("advisor-vet", "build-record"):
        found = _find_live_standalone_markers(body, grounding_stage.REGION_MARKERS[name])
        # axis: a slot marker present other than exactly once refuses markers-invalid
        if len(found) != 1:
            raise _Refusal("markers-invalid", "%s marker appears %d times" % (name, len(found)))
        offsets[name] = found[0]
    # axis: an advisor-vet marker not above the build-record marker refuses markers-invalid
    if offsets["advisor-vet"] >= offsets["build-record"]:
        raise _Refusal("markers-invalid", "advisor-vet marker is not above the build-record marker")
    followups = read_marker_list(body, FOLLOWUPS_MARKER_NAME, after=offsets["build-record"])
    return offsets["advisor-vet"], offsets["build-record"], followups


def check_slot_text(slot_text):
    if not isinstance(slot_text, str) or not slot_text.strip():
        raise _Refusal("write-failed", "slot text is empty")
    for line in slot_text.splitlines():
        if line.strip().startswith("<!-- superheroes:"):
            raise _Refusal("write-failed", "slot text carries a marker: %s" % line.strip())


def _select_receipt(comments, advisor_login):
    best = None
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != advisor_login:
            continue
        first = comment["body"].lstrip("﻿ \t\r\n").splitlines()
        if first and first[0].rstrip() == RECEIPT_MARKER:
            if best is None or comment["created_at"] >= best["created_at"]:
                best = comment
    return best


def evaluate(verb, body, comments, slot_text=None, advisor_login=None):
    """The chokepoint: every check, then the result (with ``newBody`` for write)."""
    try:
        advisor_at, build_at, ids = analyze_body(body)
        if verb == "write":
            check_slot_text(slot_text)
        if not isinstance(advisor_login, str) or not advisor_login.strip():
            raise _Refusal("read-failed", "advisor login is missing")
        receipt = _select_receipt(comments, advisor_login.strip())
        if receipt is None:
            if verb == "check" and ids is None:
                return {"ok": True, "verb": "check", "followups": [], "receipt": None,
                        "receiptPresent": False}
            raise _Refusal("receipt-missing", "no comment opens with the vet-receipt marker")
        disposed = read_marker_list(receipt["body"], DISPOSITIONS_MARKER_NAME)
        # axis: a none dispositions marker over a followups list refuses none-over-list
        if ids is not None and disposed is None:
            raise _Refusal("none-over-list", "receipt dispositions read none over %s" % " ".join(ids))
        missing = [i for i in (ids or []) if i not in (disposed or [])]
        # axis: a follow-up id with no disposition refuses followup-undispositioned
        if missing:
            raise _Refusal("followup-undispositioned", "%s: no disposition" % ", ".join(missing))
        unknown = [i for i in (disposed or []) if i not in (ids or [])]
        # axis: a disposition id the build record lacks refuses disposition-unknown
        if unknown:
            raise _Refusal("disposition-unknown", "%s: not in the followups marker" % ", ".join(unknown))
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
    try:
        new_advisor_at, new_build_at, new_ids = analyze_body(new_body)
    except _Refusal as exc:
        return _refusal("write-failed", "composed body broke markers: %s" % exc.detail)
    if new_ids != ids or new_advisor_at != advisor_at or new_body[new_build_at:] != body[build_at:]:
        return _refusal("write-failed", "composed body moved or shadowed slot markers")
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
        if not isinstance(c, dict):
            raise _Refusal("read-failed", "comments: a comment lacks body, created_at, or user.login")
        user = c.get("user")
        if not (isinstance(c, dict) and isinstance(c.get("body"), str)
                and isinstance(c.get("created_at"), str)
                and isinstance(user, dict) and isinstance(user.get("login"), str)):
            raise _Refusal("read-failed", "comments: a comment lacks body, created_at, or user.login")
    return comments


def _read_advisor_login(run):
    login = _gh(run, ["gh", "api", "user", "-q", ".login"], "advisor login").strip()
    if not login:
        raise _Refusal("read-failed", "advisor login: empty")
    return login


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
    advisor_login = _read_advisor_login(run)
    comments = _read_comments(run, pr, repo)
    result = evaluate(verb, body, comments, slot_text, advisor_login=advisor_login)
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
