#!/usr/bin/env python3
"""Issue-contract build-ready check (#932).

Deterministic, stdlib-only, advisory decider for whether an issue body may be marked
build-ready: the Anchor slot must be present, filled, and declare exactly one anchor
kind in its slot header. What and DoD slots are reported but never blocking at this step.
When an issue is named (`--issue` and `--repo`) the check also reads the issue's native
`blocked_by` dependency edges in full: an open blocker refuses (`blocker-open`) unless `judge_open_blockers`
accepts it as a lower layer of the same stack on evidence it read, and a read that fails or is malformed
refuses (`blockers-unreadable`), never read as no blockers.

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
import git_origin
import launch_ledger
import md_fence
import pr_body_regions
import review_record
import stack_check

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

def _load_stack_card_qualifier():
    """The qualifier that marks a PARKED vet line as held only for a card on the stack sheet of #<parent>.

    Its one home is `rubric/vet-verdict-form.json` (`stackCardQualifier`), beside the verdict tokens; None when
    the form cannot be read, and then no vet line reads as the card mark (the blocker holds)."""
    try:
        with open(stack_check._vet_verdict_form_path(), encoding="utf-8") as fh:
            value = json.load(fh).get("stackCardQualifier")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value.strip() else None


STACK_CARD_QUALIFIER = _load_stack_card_qualifier()
_PR_HEAD_SHA_RE = re.compile(r"[0-9a-f]{40}")
_PREMISE_KEYS = ("stack", "layerPosition", "dependency")

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


def _blockers_dict(
    checked, open_rows, detail, accepted=None, held=None, required_dependency=None, stack=None,
):
    return {
        "checked": checked,
        "open": open_rows,
        "accepted": accepted if accepted is not None else [],
        "held": held if held is not None else [],
        "requiredDependency": required_dependency,
        "stack": stack,
        "detail": detail,
    }


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


# --- the one judge of an open native blocker: is it an accepted lower layer of the same stack? ---


def _first_nonempty_line(text):
    for line in text.splitlines():
        if line.strip():
            return line
    return None


def stack_card_parent(body, head_sha):
    """The parent issue number when `body`'s vet line is the stack-card mark at `head_sha`, else None.

    The mark: the first non-empty line after the advisor-vet marker is the PARKED verdict line at `head_sha`
    (token, separator and sha as `rubric/vet-verdict-form.json` spells them, which `stack_check.read_vet_verdict`
    has already checked), then one space, STACK_CARD_QUALIFIER, the parent issue number in digits, then end of
    line or a space. A vet the reader refuses returns None here; the caller that must tell a refusal apart reads
    the vet itself."""
    verdict, refusal = stack_check.read_vet_verdict(body, head_sha)
    # axis: only a PARKED vet pinned to the current head can carry the card mark; a refused or other verdict never does — see bite-proof record wo_2652_stack_layer_blockers
    if refusal is not None or verdict != stack_check.VERDICT_PARKED or STACK_CARD_QUALIFIER is None:
        return None
    region_text, region_refusal = pr_body_regions.read_region(body, "advisor-vet")
    if region_refusal is not None or region_text is None:
        return None
    line = _first_nonempty_line(region_text)
    if line is None:
        return None
    # The verdict reader matched the PARKED token, the separator and the 40-hex sha at this line's start; the
    # qualifier follows the sha after one space.
    form, form_error = stack_check._load_vet_verdict_form()
    if form_error is not None:
        return None
    separator, tokens = form
    token = next((t for t, v in tokens if v == stack_check.VERDICT_PARKED), None)
    if token is None or not line.startswith(token + separator):
        return None
    tail = line[len(token) + len(separator) + 40:]
    prefix = " " + STACK_CARD_QUALIFIER
    # axis: a PARKED line without the exact qualifier and a parent number is a plain park, not a card mark — see bite-proof record wo_2652_stack_layer_blockers
    if not tail.startswith(prefix):
        return None
    digits = tail[len(prefix):].split(" ", 1)[0]
    if not digits.isascii() or not digits.isdigit():
        return None
    parent = int(digits)
    return parent if parent >= 1 else None


class _Unreadable(Exception):
    """A read the judge needed could not complete; the whole judgement is then unreadable."""


def _gh_call(run, endpoint):
    """The completed process of one `gh api <endpoint>` call, or None when it timed out or could not start."""
    try:
        return run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _gh_fetch(run):
    """A `gh_pages.read` fetch over `run`: stdout text, or None when the call failed."""

    def fetch(endpoint):
        proc = _gh_call(run, endpoint)
        if proc is None or proc.returncode != 0 or not isinstance(proc.stdout, str):
            return None
        return proc.stdout

    return fetch


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_not_found(proc):
    """True when a failed `gh api` call answered HTTP 404 (stdout status "404" or stderr naming it)."""
    stderr = getattr(proc, "stderr", None)
    if isinstance(stderr, str) and "(HTTP 404)" in stderr:
        return True
    try:
        payload = json.loads(proc.stdout) if isinstance(proc.stdout, str) else None
    except ValueError:
        return False
    return isinstance(payload, dict) and payload.get("status") == "404"


def _read_parent_number(run, repo, issue):
    """The number of the issue's parent, or None when GitHub says it has none; unreadable raises."""
    proc = _gh_call(run, "repos/%s/issues/%d/parent" % (repo, issue))
    # axis: a parent read that times out or cannot start is unreadable, never "no parent" — see bite-proof record wo_2652_stack_layer_blockers
    if proc is None:
        raise _Unreadable("the parent of %s#%d could not be read" % (repo, issue))
    if proc.returncode != 0:
        # axis: only an HTTP 404 means "no parent"; any other failed read is unreadable — see bite-proof record wo_2652_stack_layer_blockers
        if _is_not_found(proc):
            return None
        raise _Unreadable("the parent of %s#%d could not be read" % (repo, issue))
    try:
        payload = json.loads(proc.stdout) if isinstance(proc.stdout, str) else None
    except ValueError:
        payload = None
    # axis: a parent answer that is not an issue object with an int number is unreadable — see bite-proof record wo_2652_stack_layer_blockers
    if not isinstance(payload, dict) or not _is_int(payload.get("number")):
        raise _Unreadable("the parent of %s#%d is not an issue object with a number" % (repo, issue))
    return payload["number"]


def _read_sibling_refs(run, repo, parent):
    """The refs of the parent's sub-issues, in the parent's order; unreadable raises."""
    rows = gh_pages.read(_gh_fetch(run), "repos/%s/issues/%d/sub_issues" % (repo, parent))
    # axis: a sub-issue list that cannot be read in full is unreadable, never an empty list — see bite-proof record wo_2652_stack_layer_blockers
    if rows is None:
        raise _Unreadable("the sub-issues of #%d could not be read in full" % parent)
    refs = []
    for row in rows:
        ref = _blocker_ref(row) if isinstance(row, dict) else None
        # axis: a sub-issue row that cannot name itself fails the whole read, even beside valid rows — see bite-proof record wo_2652_stack_layer_blockers
        if ref is None:
            raise _Unreadable("a sub-issue row of #%d has no usable number or repository_url" % parent)
        refs.append(ref)
    return refs


def _read_open_prs(run, repo):
    """Every open pull request of `repo` as {number, draft, head, body}; unreadable raises."""
    rows = gh_pages.read(_gh_fetch(run), "repos/%s/pulls?state=open" % repo)
    # axis: an open-PR list that cannot be read in full is unreadable, never an empty list — see bite-proof record wo_2652_stack_layer_blockers
    if rows is None:
        raise _Unreadable("the open pull requests of %s could not be read in full" % repo)
    prs = []
    for row in rows:
        head = row.get("head") if isinstance(row, dict) else None
        sha = head.get("sha") if isinstance(head, dict) else None
        body = row.get("body") if isinstance(row, dict) else None
        # axis: any pull-request row that is malformed fails the whole read, even after a matching row — see bite-proof record wo_2652_stack_layer_blockers
        # axis: a row with no body key is unreadable, never an empty body: an unread body cannot show it closes nothing
        if (
            not isinstance(row, dict)
            or "body" not in row
            or not _is_int(row.get("number"))
            or row.get("state") != "open"
            or not isinstance(row.get("draft"), bool)
            or not isinstance(sha, str)
            or not _PR_HEAD_SHA_RE.fullmatch(sha)
            or not (body is None or isinstance(body, str))
        ):
            raise _Unreadable("an open pull request row of %s is malformed" % repo)
        prs.append({
            "number": row["number"],
            "draft": row["draft"],
            "head": sha,
            "body": body if body is not None else "",
        })
    return prs


def _first_prose_line(body):
    """The body's first non-empty line as GitHub reads it as prose, or None.

    The line is masked by `review_record._markdown_prose`, the closing-issue reader's own prose rule, so a
    closing keyword in an HTML comment, a code span or a quote on that line counts for nothing."""
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    masked = review_record._markdown_prose(body).split("\n")
    for index, line in enumerate(lines):
        if line.strip():
            # axis: the first non-empty line counts only as the prose GitHub reads — a masked line closes nothing
            return masked[index] if index < len(masked) and masked[index].strip() else None
    return None


def _closes_issue(pr, repo, number):
    """True when the PR body's first non-empty line holds a closing reference to `repo`#`number`."""
    # axis: only the first non-empty body line counts — a closing reference lower in the body is not a handed-back layer — see bite-proof record wo_2652_stack_layer_blockers
    line = _first_prose_line(pr["body"])
    if line is None:
        return False
    for match in stack_check.CLOSING_REF_RE.finditer(line):
        if match.group("bare") is not None:
            if int(match.group("bare")) == number:
                return True
            continue
        slug = match.group("slug") or match.group("uslug")
        named = match.group("n") or match.group("un")
        if slug is not None and slug.lower() == repo.lower() and int(named) == number:
            return True
    return False


def _held_row(row, why):
    return {"ref": row["ref"], "title": row["title"], "url": row["url"], "why": why}


def _accepted_row(row, layer):
    return {
        "ref": row["ref"],
        "title": row["title"],
        "url": row["url"],
        "pr": layer["pr"],
        "head": layer["head"],
        "form": layer["form"],
        "stack": layer["stack"],
    }


def _read_layer_membership(membership_reader, run, repo, pr, head):
    """(stack number or None, position or None) of a pull request read at `head`; any read other than not-linked
    failing raises, and so does an ok read taken at another head than the one the vet was read at."""
    result = membership_reader(pr=pr, repo=repo, run=run)
    if isinstance(result, dict) and result.get("ok") is True:
        stack = result.get("stack")
        queried = result.get("queried")
        number = stack.get("number") if isinstance(stack, dict) else None
        position = queried.get("position") if isinstance(queried, dict) else None
        read_head = queried.get("headRefOid") if isinstance(queried, dict) else None
        # axis: an ok membership read without an int stack number and position is unreadable — see bite-proof record wo_2652_stack_layer_blockers
        if not _is_int(number) or not _is_int(position):
            raise _Unreadable("the stack membership of pull request #%d is malformed" % pr)
        # axis: membership read at another head than the vet joins two snapshots; it is unreadable, never accepted
        if not stack_check.same_commit(read_head, head):
            raise _Unreadable(
                "pull request #%d moved between reads (vet read at %s, stack membership at %s)" % (pr, head, read_head)
            )
        return number, position
    # axis: only not-linked means "in no stack"; every other membership refusal is unreadable — see bite-proof record wo_2652_stack_layer_blockers
    if isinstance(result, dict) and result.get("reason") == stack_check.REASON_NOT_LINKED:
        return None, None
    raise _Unreadable("the stack membership of pull request #%d could not be read" % pr)


def _layer_of(number, pulls, parent, repo, run, membership_reader, decided, index):
    """Steps 6-9 for one row: its handed-back layer {pr, head, form, stack, position}, or None once held."""
    closing = [pr for pr in pulls if _closes_issue(pr, repo, number)]
    if not closing:
        decided[index] = ("held", "no open pull request's first line closes it, so no handed-back layer builds it")
        return None
    # axis: more than one open pull request closing the same blocker is ambiguous and holds — see bite-proof record wo_2652_stack_layer_blockers
    if len(closing) > 1:
        names = ", ".join("#%d" % pr["number"] for pr in closing)
        decided[index] = ("held", "more than one open pull request closes it (%s)" % names)
        return None
    pr = closing[0]
    # axis: a draft pull request is work in flight, never a handed-back layer — see bite-proof record wo_2652_stack_layer_blockers
    if pr["draft"]:
        decided[index] = ("held", "its pull request #%d is a draft" % pr["number"])
        return None
    verdict, refusal = stack_check.read_vet_verdict(pr["body"], pr["head"])
    # axis: a vet the reader refuses is unreadable, never read as not-ready — see bite-proof record wo_2652_stack_layer_blockers
    if refusal is not None:
        raise _Unreadable(
            "the vet of pull request #%d could not be read: %s"
            % (pr["number"], refusal.get("detail") or refusal.get("reason"))
        )
    form = "ready"
    if verdict != stack_check.VERDICT_READY:
        card = stack_card_parent(pr["body"], pr["head"])
        # axis: a card mark counts only for this stack's own parent; another parent's card holds — see bite-proof record wo_2652_stack_layer_blockers
        if card is not None and card != parent:
            decided[index] = (
                "held",
                "its pull request #%d's vet holds it for a card on the stack sheet of #%d, not this stack's #%d"
                % (pr["number"], card, parent),
            )
            return None
        if card is None:
            decided[index] = (
                "held",
                "its pull request #%d's vet does not read READY, or held only for a card on the stack sheet of #%d, at its current head %s"
                % (pr["number"], parent, pr["head"]),
            )
            return None
        form = "stack-card"
    stack, position = _read_layer_membership(membership_reader, run, repo, pr["number"], pr["head"])
    return {"pr": pr["number"], "head": pr["head"], "form": form, "stack": stack, "position": position}


def _judge_with_premise(layers, premise, decided):
    """Step 10 with a premise: accept a layer only as the launch's own stack's lower layer or its one dependency."""
    required = None
    if "stack" in premise and "layerPosition" in premise:
        want, floor = premise["stack"], premise["layerPosition"]
        for index, layer in layers:
            n = layer["pr"]
            # axis: a layer counts only in the launch's own stack and below the launch's position — see bite-proof record wo_2652_stack_layer_blockers
            if layer["stack"] is None:
                decided[index] = ("held", "its pull request #%d is in no stack" % n)
            elif layer["stack"] != want:
                decided[index] = (
                    "held", "its pull request #%d is in stack %d, not the launch's stack %d" % (n, layer["stack"], want)
                )
            elif layer["position"] >= floor:
                decided[index] = (
                    "held",
                    "its pull request #%d is at position %d, not below the launch's position %d"
                    % (n, layer["position"], floor),
                )
            else:
                decided[index] = ("accepted", dict(layer, stack=want))
        return required, want
    if "dependency" in premise:
        dep = premise["dependency"]
        for index, layer in layers:
            n = layer["pr"]
            # axis: without a launch stack only the launch's one named dependency, in no stack, is a lower layer — see bite-proof record wo_2652_stack_layer_blockers
            if n != dep:
                decided[index] = ("held", "its pull request #%d is not the launch's dependency #%d" % (n, dep))
            elif layer["stack"] is not None:
                decided[index] = (
                    "held",
                    "its pull request #%d is in stack %d; the launch premise must name that stack" % (n, layer["stack"]),
                )
            else:
                decided[index] = ("accepted", dict(layer, stack=None))
                required = n
        return required, None
    for index, _layer in layers:
        decided[index] = (
            "held", "the launch premise names no stack and no dependency, so this launch is not a stack layer"
        )
    return required, None


def _judge_without_premise(layers, decided):
    """Step 10 with no premise (build-ready): the lower layers must share one stack, or be one unstacked layer."""
    stacks = sorted({layer["stack"] for _index, layer in layers if layer["stack"] is not None})
    # axis: lower layers in more than one stack are never one stack's layers — see bite-proof record wo_2652_stack_layer_blockers
    if len(stacks) > 1:
        why = "the lower layers sit in more than one stack (%s)" % ", ".join(str(s) for s in stacks)
        for index, _layer in layers:
            decided[index] = ("held", why)
        return None, None
    if stacks:
        for index, layer in layers:
            if layer["stack"] is None:
                decided[index] = (
                    "held",
                    "its pull request #%d is in no stack, while the other lower layers are in stack %d"
                    % (layer["pr"], stacks[0]),
                )
            else:
                decided[index] = ("accepted", layer)
        return None, stacks[0]
    if len(layers) == 1:
        index, layer = layers[0]
        decided[index] = ("accepted", layer)
        return layer["pr"], None
    for index, _layer in layers:
        decided[index] = (
            "held",
            "more than one lower layer has a pull request but no stack is linked; a launch can depend on only one",
        )
    return None, None


def judge_open_blockers(open_rows, issue, repo, run, premise=None, membership_reader=None):
    """Judge every open native blocker of `repo`#`issue`: accepted as a lower layer of the same stack, or held.

    `open_rows` are `read_blockers` rows; `run` is a `subprocess.run`-shaped callable; `premise` is the launch's
    {stack, layerPosition, dependency} (None for the build-ready check); `membership_reader` defaults to
    `stack_check.read_membership`. Returns the full blockers dict: every row ends in exactly one of `accepted` or
    `held`, and a read that cannot complete returns the unreadable shape (checked False)."""
    if membership_reader is None:
        membership_reader = stack_check.read_membership
    try:
        return _judge(open_rows, issue, repo, run, premise, membership_reader)
    except _Unreadable as exc:
        return _blockers_dict(False, [], str(exc))


def _judge(open_rows, issue, repo, run, premise, membership_reader):
    decided = {}
    live = []
    for index, row in enumerate(open_rows):
        # axis: a blocker in another repository is never a layer of this repository's stack — see bite-proof record wo_2652_stack_layer_blockers
        # axis: GitHub repository names ignore case, so a differently cased same repository is not another one
        if not git_origin.same_repository(row["ref"].rsplit("#", 1)[0], repo):
            decided[index] = ("held", "it is in another repository, so it is not a layer of this stack")
        else:
            live.append(index)
    required, stack = None, None
    if live:
        parent = _read_parent_number(run, repo, issue)
        if parent is None:
            for index in live:
                decided[index] = ("held", "this issue is not a sub-issue of a feature, so it is not a stack layer")
            live = []
    if live:
        # Refs are compared with the repository part folded to lower case (GitHub names ignore case).
        siblings = [ref.lower() for ref in _read_sibling_refs(run, repo, parent)]
        own = ("%s#%d" % (repo, issue)).lower()
        # axis: the blocked issue must itself be listed under its parent, or the order of layers is unknown — see bite-proof record wo_2652_stack_layer_blockers
        if own not in siblings:
            raise _Unreadable("the sub-issue list of #%d does not list #%d" % (parent, issue))
        own_at = siblings.index(own)
        still = []
        for index in live:
            ref = open_rows[index]["ref"].lower()
            if ref not in siblings:
                decided[index] = ("held", "it is not a sub-issue of #%d, so it is not a layer of this stack" % parent)
            # axis: a blocker listed at or after the blocked issue is not a lower layer — see bite-proof record wo_2652_stack_layer_blockers
            elif siblings.index(ref) >= own_at:
                decided[index] = ("held", "it is listed after this issue under #%d, so it is not a lower layer" % parent)
            else:
                still.append(index)
        live = still
    if live:
        pulls = _read_open_prs(run, repo)
        layers = []
        for index in live:
            number = int(open_rows[index]["ref"].rsplit("#", 1)[1])
            layer = _layer_of(number, pulls, parent, repo, run, membership_reader, decided, index)
            if layer is not None:
                layers.append((index, layer))
        if premise is not None:
            required, stack = _judge_with_premise(layers, premise, decided)
        else:
            required, stack = _judge_without_premise(layers, decided)
    accepted, held = [], []
    for index, row in enumerate(open_rows):
        kind, detail = decided.get(index, ("held", "it could not be judged as a lower layer"))
        if kind == "accepted":
            accepted.append(_accepted_row(row, detail))
        else:
            held.append(_held_row(row, detail))
    return _blockers_dict(True, open_rows, None, accepted, held, required, stack)


def read_premise(path):
    """(premise, detail): the launch premise's `stack`, `layerPosition` and `dependency`, or None and why not."""
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
    except (OSError, ValueError):
        return None, "--premise %s could not be read as UTF-8 text" % path

    def no_duplicates(pairs):
        keys = [key for key, _value in pairs]
        # axis: a premise object with a repeated key is ambiguous and refuses — see bite-proof record wo_2652_stack_layer_blockers
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate key")
        return dict(pairs)

    try:
        data = json.loads(text, object_pairs_hook=no_duplicates)
    except ValueError:
        return None, "--premise %s is not JSON with unique keys" % path
    if not isinstance(data, dict):
        return None, "--premise %s is not a JSON object" % path
    # axis: stack and layerPosition go together — exactly one given is a refusal — see bite-proof record wo_2652_stack_layer_blockers
    if ("stack" in data) != ("layerPosition" in data):
        return None, "--premise %s has stack without layerPosition or the reverse" % path
    premise = {}
    for key in _PREMISE_KEYS:
        if key in data:
            value = data[key]
            # axis: stack, layerPosition and dependency must each be a positive int (a bool is not) — see bite-proof record wo_2652_stack_layer_blockers
            if not launch_ledger.is_positive_premise_int(value):
                return None, "--premise %s: %s is not a positive integer" % (path, key)
            premise[key] = value
    return premise, None


def read_judged_blockers(issue, repo, run, premise=None, membership_reader=None):
    """`read_blockers`, then `judge_open_blockers` over its open rows: the one reader both CLI verbs use."""
    blockers = read_blockers(issue, repo, run)
    if not blockers["checked"] or not blockers["open"]:
        return blockers
    return judge_open_blockers(blockers["open"], issue, repo, run, premise, membership_reader)


def _blockers_verdict(blockers):
    """(ok, reason) for a blockers read: unreadable, else a held blocker, else ok. The one home of this decision."""
    # axis: an unread or malformed edge list refuses — never read as no blockers.
    if not blockers["checked"]:
        return False, REFUSAL_BLOCKERS_UNREADABLE
    # axis: any open native blocker the judge did not accept as a lower layer refuses the marking — see bite-proof record wo_2652_stack_layer_blockers
    if blockers["held"]:
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


def check_build_ready_with_blockers(body, issue, repo, run, membership_reader=None):
    """Body check plus the issue's native blocker edges; ok only when both clear."""
    result = check_build_ready(body)
    return _apply_blockers(result, read_judged_blockers(issue, repo, run, None, membership_reader))


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


def main(argv=None, run=None, membership_reader=None):
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
    b.add_argument(
        "--premise", default=None,
        help="the launch's premise JSON: judges each open blocker as a layer of the launch's stack",
    )
    args = p.parse_args(argv)

    if args.cmd == "check-blockers":
        number, repo, detail = _parse_edge_args(args.issue, args.repo)
        premise = None
        if detail is None and args.premise is not None:
            # axis: a premise file that cannot be read or is malformed refuses before any gh call — see bite-proof record wo_2652_stack_layer_blockers
            premise, detail = read_premise(args.premise)
        if detail is not None:
            blockers = _blockers_refusal(detail)
        else:
            blockers = read_judged_blockers(number, repo, run, premise, membership_reader)
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
            result = check_build_ready_with_blockers(body, number, repo, run, membership_reader)
    _emit(result)
    # Exit 0 always: the JSON result is the product; a non-zero exit would let a caller
    # treat a refusal as a crash. The advisor reads ok/reason, not the exit code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
