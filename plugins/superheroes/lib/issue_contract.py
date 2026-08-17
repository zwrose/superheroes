#!/usr/bin/env python3
"""Issue-contract build-ready check (#932).

Deterministic, stdlib-only, advisory decider for whether an issue body may be marked
build-ready: the Anchor slot must be present, filled, and declare exactly one anchor
kind in its slot header. What and DoD slots are reported but never blocking at this step.

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
import sys

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
REFUSALS = frozenset({
    REFUSAL_ANCHOR_SLOT_MISSING,
    REFUSAL_ANCHOR_SLOT_EMPTY,
    REFUSAL_ANCHOR_KIND_MISSING,
    REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
    REFUSAL_ANCHOR_KIND_MULTIPLE,
    REFUSAL_BODY_UNREADABLE,
})

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


def _result(ok, reason, anchor_kind, declared_kinds, slots):
    return {
        "ok": ok,
        "reason": reason,
        "anchorKind": anchor_kind,
        "declaredKinds": declared_kinds,
        "slots": slots,
        "advisory": True,
    }


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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser(
        "check-build-ready",
        help="read an issue body and report build-ready anchor shape",
    )
    c.add_argument("--body-file", required=True, help="path to the issue body text")
    args = p.parse_args(argv)

    body = _read_body_file(args.body_file)
    if body is None:
        result = _fail_closed_unreadable_body()
    else:
        result = check_build_ready(body)
    _emit(result)
    # Exit 0 always: the JSON result is the product; a non-zero exit would let a caller
    # treat a refusal as a crash. The advisor reads ok/reason, not the exit code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
