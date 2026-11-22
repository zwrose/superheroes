#!/usr/bin/env python3
"""Issue-contract build-ready check (#932).

Deterministic, stdlib-only, advisory decider for whether an issue body may be marked
build-ready: the Anchor slot must be present, filled, and declare exactly one anchor
kind in its slot header. What and DoD slots are reported but never blocking at this step.
When an issue is named (`--issue` and `--repo`) the check also reads the issue's native
`blocked_by` dependency edges in full: an open blocker refuses (`blocker-open`) and a read that
fails or is malformed refuses (`blockers-unreadable`), never read as no blockers.

This module is **advisory** — it always exits 0; the JSON result is the product, and a
non-zero exit would let a caller treat a refusal as a crash. The Showrunner charter's
build-ready marking duty is what declines the marking; this check is not a mechanical
enforcement boundary and is not claimed as one.

CONVENTIONS §11 authoritative home for the issue-contract vocabulary that
`skills/showrunner/reference/issue-contract.md` restates (slots, anchor kinds, refusal
reasons). Anchor resolution (spec approved, section exists, link live) is explicitly out
of scope — declared kind only; the citation body is never classified.
"""
import argparse
import json
import re
import subprocess
import sys

import gh_pages
import md_fence

# --- vocabulary: ONE authoritative home (CONVENTIONS §11) --------------------

SLOT_ANCHOR = "Anchor"
SLOT_WHAT = "What"
SLOT_DOD = "DoD"
SLOTS = (SLOT_ANCHOR, SLOT_WHAT, SLOT_DOD)

ANCHOR_HEADER_FORM = "Anchor (<kind>):"

KIND_SPEC_SECTION = "spec-section"
KIND_RECEIPT = "receipt"
KIND_RULING = "ruling"
ANCHOR_KINDS = frozenset({
    KIND_SPEC_SECTION,
    KIND_RECEIPT,
    KIND_RULING,
})

REFUSAL_ANCHOR_SLOT_MISSING = "anchor-slot-missing"
REFUSAL_ANCHOR_SLOT_EMPTY = "anchor-slot-empty"
REFUSAL_ANCHOR_KIND_MISSING = "anchor-kind-missing"
REFUSAL_ANCHOR_KIND_UNRECOGNIZED = "anchor-kind-unrecognized"
REFUSAL_ANCHOR_KIND_MULTIPLE = "anchor-kind-multiple"
REFUSAL_BODY_UNREADABLE = "body-unreadable"
REFUSAL_BLOCKER_OPEN = "blocker-open"
REFUSAL_BLOCKERS_UNREADABLE = "blockers-unreadable"
REFUSALS = frozenset({
    REFUSAL_ANCHOR_SLOT_MISSING,
    REFUSAL_ANCHOR_SLOT_EMPTY,
    REFUSAL_ANCHOR_KIND_MISSING,
    REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
    REFUSAL_ANCHOR_KIND_MULTIPLE,
    REFUSAL_BODY_UNREADABLE,
    REFUSAL_BLOCKER_OPEN,
    REFUSAL_BLOCKERS_UNREADABLE,
})

# Seconds one `gh api` call for the blocker edges may run before the read fails closed.
GH_TIMEOUT_SECONDS = 30
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ISSUE_PATTERN = re.compile(r"^[0-9]+$")
_BLOCKER_STATES = ("open", "closed")

SLOT_STATUS_MISSING = "missing"
SLOT_STATUS_EMPTY = "empty"
SLOT_STATUS_FILLED = "filled"
SLOT_STATUS_UNKNOWN = "unknown"
SLOT_STATUSES = frozenset({
    SLOT_STATUS_MISSING,
    SLOT_STATUS_EMPTY,
    SLOT_STATUS_FILLED,
    SLOT_STATUS_UNKNOWN,
})


def _normalize_header_line(line):
    """Strip markdown heading/emphasis decoration from a slot header line."""
    s = line.strip()
    changed = True
    while changed:
        changed = False
        stripped = s.strip()
        if stripped != s:
            s = stripped
            changed = True
        while s and s[0] in "*_#":
            s = s[1:]
            changed = True
        while s and s[-1] in "*_#":
            s = s[:-1]
            changed = True
    return s.strip()


def _extract_declared_kinds(header_rest):
    # axis: kind tokens are parsed from parenthesized groups in the header — never from citation
    # prose; a header with no closing parenthesis or without a trailing colon is not a valid header.
    """Parse parenthesized kind-token groups after ``Anchor`` and before ``:``."""
    declared = []
    pos = 0
    while pos < len(header_rest) and header_rest[pos] == " ":
        pos += 1
    while pos < len(header_rest) and header_rest[pos] == "(":
        close = header_rest.find(")", pos)
        if close == -1:
            return None
        inner = header_rest[pos + 1:close]
        for token in inner.split(","):
            token = token.strip()
            if token:
                declared.append(token)
        pos = close + 1
        while pos < len(header_rest) and header_rest[pos] == " ":
            pos += 1
    if pos >= len(header_rest) or header_rest[pos] != ":":
        return None
    return declared, header_rest[pos + 1:].lstrip()


def _parse_slot_header(line):
    """If `line` is a slot header, return (slot_name, remainder, declared_kinds)."""
    normalized = _normalize_header_line(line)
    for slot in (SLOT_WHAT, SLOT_DOD):
        prefix = slot + ":"
        if normalized.startswith(prefix):
            return slot, normalized[len(prefix):].lstrip(), []
    if normalized == "Anchor:":
        return SLOT_ANCHOR, "", []
    if normalized.startswith("Anchor"):
        parsed = _extract_declared_kinds(normalized[len("Anchor"):])
        if parsed is None:
            return None, None, None
        declared, remainder = parsed
        return SLOT_ANCHOR, remainder, declared
    return None, None, None


def _strip_markdown_noise(text):
    """Remove common markdown bullet/emphasis noise before emptiness checks."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"^[\s>*+\-]+", "", stripped)
        stripped = re.sub(r"[*_`#]", "", stripped)
        out.append(stripped)
    return "\n".join(out)


def _content_has_word_char(text):
    cleaned = _strip_markdown_noise(text)
    return bool(re.search(r"[A-Za-z0-9]", cleaned))


def _parse_slots(body):
    """Return slot statuses, per-slot content, and Anchor declared kind tokens."""
    slots_content = {slot: [] for slot in SLOTS}
    found = {slot: False for slot in SLOTS}
    current_slot = None
    anchor_declared_kinds = []
    lines = body.splitlines()
    # axis: unterminated fence is not a refusal here — every later line is fence content, so a real
    # header after it is swallowed and reports as missing (fail-closed).
    scan = md_fence.scan(lines)

    for line, kind in zip(lines, scan.kinds):
        # axis: slot headers inside fenced blocks are ignored — md_fence.scan kinds gate header parsing.
        if kind == md_fence.KIND_OPENER:
            continue
        if kind == md_fence.KIND_CLOSER:
            continue
        if kind == md_fence.KIND_CONTENT:
            if current_slot is not None:
                slots_content[current_slot].append(line)
            continue
        # axis: indented code block (4+ columns) — never a live slot header; prevents fail-open on
        # indent-4 headers and on headers inside indent-4 fences that scan does not classify as inert.
        if md_fence.indent_width(line) >= md_fence.INDENT_CODE_BLOCK_COLUMNS:
            if current_slot is not None:
                slots_content[current_slot].append(line)
            continue
        slot, rest, declared = _parse_slot_header(line)
        if slot is not None:
            current_slot = slot
            found[slot] = True
            if slot == SLOT_ANCHOR:
                anchor_declared_kinds = declared
            if rest:
                slots_content[slot].append(rest)
            continue
        if current_slot is not None:
            slots_content[current_slot].append(line)

    statuses = {}
    for slot in SLOTS:
        if not found[slot]:
            statuses[slot] = SLOT_STATUS_MISSING
        elif _content_has_word_char("\n".join(slots_content[slot])):
            statuses[slot] = SLOT_STATUS_FILLED
        else:
            statuses[slot] = SLOT_STATUS_EMPTY
    return statuses, slots_content, anchor_declared_kinds


def check_build_ready(body):
    """Decide build-ready marking from an issue body string. Always returns a result dict."""
    statuses, slots_content, declared_kinds = _parse_slots(body)

    # axis: no Anchor slot header line anywhere in the body — slot status missing, not empty or filled.
    if statuses[SLOT_ANCHOR] == SLOT_STATUS_MISSING:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_SLOT_MISSING,
            anchor_kind=None,
            declared_kinds=declared_kinds,
            slots=statuses,
        )
    # axis: Anchor header declares zero kind tokens (Anchor: or Anchor ():) — not whether content is empty.
    if len(declared_kinds) == 0:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_KIND_MISSING,
            anchor_kind=None,
            declared_kinds=declared_kinds,
            slots=statuses,
        )
    # axis: how many kind tokens the header declares — two or more is refused before any validity check.
    if len(declared_kinds) >= 2:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_KIND_MULTIPLE,
            anchor_kind=None,
            declared_kinds=declared_kinds,
            slots=statuses,
        )
    declared = declared_kinds[0]
    # axis: the single declared token is not a recognized anchor kind — membership in ANCHOR_KINDS.
    if declared not in ANCHOR_KINDS:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
            anchor_kind=None,
            declared_kinds=declared_kinds,
            slots=statuses,
        )
    # axis: Anchor slot header present and kind valid but citation body has no word character.
    if statuses[SLOT_ANCHOR] == SLOT_STATUS_EMPTY:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_SLOT_EMPTY,
            anchor_kind=None,
            declared_kinds=declared_kinds,
            slots=statuses,
        )
    return _result(
        ok=True,
        reason=None,
        anchor_kind=declared,
        declared_kinds=declared_kinds,
        slots=statuses,
    )


def _blockers_dict(checked, open_rows, detail):
    return {"checked": checked, "open": open_rows, "detail": detail}


def _result(ok, reason, anchor_kind, declared_kinds, slots, blockers=None):
    return {
        "ok": ok,
        "reason": reason,
        "anchorKind": anchor_kind,
        "declaredKinds": declared_kinds,
        "slots": slots,
        "blockers": blockers if blockers is not None else _blockers_dict(False, [], None),
        "advisory": True,
    }


# --- native blocker edges: ONE reader (read_blockers), called by both CLI verbs ---


def _blocker_ref(row):
    """`owner/name#number` for a blocker row, or None when the row cannot name itself."""
    number = row.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        return None
    url = row.get("repository_url")
    if not isinstance(url, str) or "/repos/" not in url:
        return None
    name = url.split("/repos/", 1)[1]
    if not _REPO_PATTERN.match(name):
        return None
    return "%s#%d" % (name, number)


def _row_label(row):
    number = row.get("number") if isinstance(row, dict) else None
    if isinstance(number, int) and not isinstance(number, bool):
        return "row #%d" % number
    return "a row"


def read_blockers(issue, repo, run):
    """Read every native `blocked_by` edge of `repo`#`issue`; never read a failure as "no blockers".

    `run` is a `subprocess.run`-shaped callable. Returns {"checked", "open", "detail"}:
    checked True only when every page was read and every row is a well-formed open or closed issue."""
    path = "repos/%s/issues/%d/dependencies/blocked_by" % (repo, issue)

    def fetch(endpoint):
        try:
            proc = run(
                ["gh", "api", endpoint],
                capture_output=True,
                text=True,
                timeout=GH_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0 or not isinstance(proc.stdout, str):
            return None
        return proc.stdout

    rows = gh_pages.read(fetch, path)
    # axis: a blocker-edge read that fails, times out, or returns a non-list page is unreadable, never an empty list.
    if rows is None:
        return _blockers_dict(
            False, [], "the blocked_by edges of %s#%d could not be read in full" % (repo, issue)
        )
    open_rows = []
    for row in rows:
        # axis: a row that is not an object fails the whole read — it cannot be called closed.
        if not isinstance(row, dict):
            return _blockers_dict(False, [], "a blocked_by row is not an object (state unknown)")
        state = row.get("state")
        # axis: a state that is not exactly "open" or "closed" fails the whole read, even beside valid rows.
        if not isinstance(state, str) or state not in _BLOCKER_STATES:
            return _blockers_dict(
                False, [], "%s has state %r, not open or closed" % (_row_label(row), state)
            )
        ref = _blocker_ref(row)
        # axis: a row with no int number or no /repos/ owner/name in repository_url cannot be named — fails the read.
        if ref is None:
            return _blockers_dict(
                False, [], "%s has no usable number or repository_url" % _row_label(row)
            )
        if state == "open":
            title = row.get("title")
            html_url = row.get("html_url")
            open_rows.append({
                "ref": ref,
                "title": title if isinstance(title, str) else "",
                "url": html_url if isinstance(html_url, str) else "",
            })
    return _blockers_dict(True, open_rows, None)


def _blockers_verdict(blockers):
    """(ok, reason) for a blockers read: unreadable, else open, else ok. The one home of this decision."""
    # axis: an unread or malformed edge list refuses — never read as no blockers.
    if not blockers["checked"]:
        return False, REFUSAL_BLOCKERS_UNREADABLE
    # axis: any open native blocker refuses the marking.
    if blockers["open"]:
        return False, REFUSAL_BLOCKER_OPEN
    return True, None


def _apply_blockers(result, blockers):
    """Fold a blockers read into a result: body refusal keeps its reason, else the blockers verdict."""
    result["blockers"] = blockers
    # axis: a body refusal already holds the one reason token (body first) — blockers never overwrite it.
    if not result["ok"]:
        return result
    ok, reason = _blockers_verdict(blockers)
    if not ok:
        result["ok"] = False
        result["reason"] = reason
    return result


def check_build_ready_with_blockers(body, issue, repo, run):
    """Body check plus the issue's native blocker edges; ok only when both clear."""
    result = check_build_ready(body)
    return _apply_blockers(result, read_blockers(issue, repo, run))


def _fail_closed_unreadable_body():
    # axis: unreadable body fails closed — every slot status is unknown, not missing or empty.
    slots = {slot: SLOT_STATUS_UNKNOWN for slot in SLOTS}
    return _result(
        ok=False,
        reason=REFUSAL_BODY_UNREADABLE,
        anchor_kind=None,
        declared_kinds=[],
        slots=slots,
    )


def _read_body_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def _emit(result):
    sys.stdout.write(json.dumps(result) + "\n")


def _parse_edge_args(issue, repo):
    """(issue_int, repo, detail): detail is None when both are given and well formed."""
    # axis: --issue and --repo go together — exactly one given is a refusal and no gh call is made.
    if (issue is None) != (repo is None):
        return None, None, "--issue and --repo go together; only one was given"
    # axis: --issue must be a positive integer, validated here (never an argparse exit).
    if issue is None or not _ISSUE_PATTERN.match(issue) or int(issue) < 1:
        return None, None, "--issue must be a positive integer, got %r" % (issue,)
    # axis: --repo must be owner/name — checked before it reaches a gh endpoint.
    if repo is None or not _REPO_PATTERN.match(repo):
        return None, None, "--repo must be owner/name, got %r" % (repo,)
    return int(issue), repo, None


def _blockers_refusal(detail):
    return _blockers_dict(False, [], detail)


def main(argv=None, run=None):
    run = subprocess.run if run is None else run
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser(
        "check-build-ready",
        help="read an issue body and report build-ready anchor shape; with --issue and --repo, "
        "also read its native blocker edges",
    )
    c.add_argument("--body-file", required=True, help="path to the issue body text")
    c.add_argument("--issue", default=None, help="issue number whose native blocked_by edges to read")
    c.add_argument("--repo", default=None, help="owner/name of the issue")
    b = sub.add_parser(
        "check-blockers",
        help="read an issue's native blocked_by edges alone",
    )
    b.add_argument("--issue", default=None, help="issue number")
    b.add_argument("--repo", default=None, help="owner/name of the issue")
    args = p.parse_args(argv)

    if args.cmd == "check-blockers":
        number, repo, detail = _parse_edge_args(args.issue, args.repo)
        if detail is not None:
            blockers = _blockers_refusal(detail)
        else:
            blockers = read_blockers(number, repo, run)
        ok, reason = _blockers_verdict(blockers)
        _emit({"ok": ok, "reason": reason, "blockers": blockers, "advisory": True})
        return 0

    body = _read_body_file(args.body_file)
    if body is None:
        result = _fail_closed_unreadable_body()
    elif args.issue is None and args.repo is None:
        result = check_build_ready(body)
    else:
        number, repo, detail = _parse_edge_args(args.issue, args.repo)
        if detail is not None:
            result = _apply_blockers(check_build_ready(body), _blockers_refusal(detail))
        else:
            result = check_build_ready_with_blockers(body, number, repo, run)
    _emit(result)
    # Exit 0 always: the JSON result is the product; a non-zero exit would let a caller
    # treat a refusal as a crash. The advisor reads ok/reason, not the exit code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
