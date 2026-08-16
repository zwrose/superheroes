#!/usr/bin/env python3
"""Issue-contract build-ready check (#932).

Deterministic, stdlib-only, advisory decider for whether an issue body may be marked
build-ready: the Anchor slot must be present, filled, and cite exactly one anchor kind
by shape alone. What and DoD slots are reported but never blocking at this step.

This module is **advisory** — it always exits 0; the JSON result is the product, and a
non-zero exit would let a caller treat a refusal as a crash. The Showrunner charter's
build-ready marking duty is what declines the marking; this check is not a mechanical
enforcement boundary and is not claimed as one.

CONVENTIONS §11 authoritative home for the issue-contract vocabulary that
`skills/showrunner/reference/issue-contract.md` restates (slots, anchor kinds, refusal
reasons). Anchor resolution (spec approved, section exists, link live) is explicitly out
of scope — shape only.
"""
import argparse
import json
import re
import sys

# --- vocabulary: ONE authoritative home (CONVENTIONS §11) --------------------

SLOT_ANCHOR = "Anchor"
SLOT_WHAT = "What"
SLOT_DOD = "DoD"
SLOTS = (SLOT_ANCHOR, SLOT_WHAT, SLOT_DOD)

KIND_SPEC_SECTION = "spec-section"
KIND_RECEIPT = "receipt"
KIND_OWNER_RULING = "owner-ruling"
ANCHOR_KINDS = frozenset({
    KIND_SPEC_SECTION,
    KIND_RECEIPT,
    KIND_OWNER_RULING,
})

REFUSAL_ANCHOR_SLOT_MISSING = "anchor-slot-missing"
REFUSAL_ANCHOR_SLOT_EMPTY = "anchor-slot-empty"
REFUSAL_ANCHOR_KIND_UNRECOGNIZED = "anchor-kind-unrecognized"
REFUSAL_ANCHOR_KIND_AMBIGUOUS = "anchor-kind-ambiguous"
REFUSAL_BODY_UNREADABLE = "body-unreadable"
REFUSALS = frozenset({
    REFUSAL_ANCHOR_SLOT_MISSING,
    REFUSAL_ANCHOR_SLOT_EMPTY,
    REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
    REFUSAL_ANCHOR_KIND_AMBIGUOUS,
    REFUSAL_BODY_UNREADABLE,
})

_RE_WORK_ITEM_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*-[0-9a-f]{6}")
_RE_SECTION_REF = re.compile(
    r"§|(?:\bsection\b)|(?:\bFR-\d+\b)|(?:\bUFR-\d+\b)",
    re.IGNORECASE,
)
_RE_AS_OF = re.compile(r"as-of\s+amendment\s+#\d+", re.IGNORECASE)
_RE_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RE_RULING_WORD = re.compile(r"\bruling\b", re.IGNORECASE)
_RE_LOCATION_PREP = re.compile(r"\b(?:in|at)\s+(\w+)\b", re.IGNORECASE)
_RE_LOCATION_NOUN = re.compile(
    r"\b\w+\s+(?:channel|sitting|thread)\b",
    re.IGNORECASE,
)
_RE_LOCATION_RECORDED = re.compile(
    r"\brecorded\s+(?:in|at)\s+\S+",
    re.IGNORECASE,
)
_RE_LOCATION_MARKER = re.compile(
    r"\b(?:in|at|channel|sitting|thread|recorded)\b",
    re.IGNORECASE,
)
_LOCATION_PREP_STOP_WORDS = frozenset({
    "a", "an", "progress", "risk", "the", "this", "that",
})
_RE_RECEIPT = re.compile(r"https?://|\[[^\]]*\]\([^)]+\)")


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


def _parse_slot_header(line):
    """If `line` is a slot header, return (slot_name, remainder_after_colon)."""
    normalized = _normalize_header_line(line)
    for slot in SLOTS:
        prefix = slot + ":"
        if normalized.startswith(prefix):
            return slot, normalized[len(prefix):].lstrip()
    return None, None


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
    """Return slot statuses and per-slot content lines (header remainder + following)."""
    slots_content = {slot: [] for slot in SLOTS}
    found = {slot: False for slot in SLOTS}
    current_slot = None

    for line in body.splitlines():
        slot, rest = _parse_slot_header(line)
        if slot is not None:
            current_slot = slot
            found[slot] = True
            if rest:
                slots_content[slot].append(rest)
            continue
        if current_slot is not None:
            slots_content[current_slot].append(line)

    statuses = {}
    for slot in SLOTS:
        if not found[slot]:
            statuses[slot] = "missing"
        elif _content_has_word_char("\n".join(slots_content[slot])):
            statuses[slot] = "filled"
        else:
            statuses[slot] = "empty"
    return statuses, slots_content


def _has_location_clause(content):
    """Location names a place: prep+target, qualified noun, or recorded in/at <target>."""
    if _RE_LOCATION_NOUN.search(content):
        return True
    if _RE_LOCATION_RECORDED.search(content):
        return True
    for match in _RE_LOCATION_PREP.finditer(content):
        if match.group(1).lower() not in _LOCATION_PREP_STOP_WORDS:
            return True
    return False


def _is_spec_partial(content):
    """Any spec marker present but not all three — malformed, never a receipt."""
    markers = (
        bool(_RE_WORK_ITEM_SLUG.search(content)),
        bool(_RE_SECTION_REF.search(content)),
        bool(_RE_AS_OF.search(content)),
    )
    present = sum(markers)
    return 0 < present < 3


def _is_ruling_partial(content):
    """Any ruling marker present but not all three — malformed, never a receipt."""
    markers = (
        bool(_RE_ISO_DATE.search(content)),
        bool(_RE_RULING_WORD.search(content)),
        bool(_RE_LOCATION_MARKER.search(content)),
    )
    present = sum(markers)
    return 0 < present < 3


def _matches_spec_section(content):
    """Full spec-section shape: work-item slug + section ref + as-of cursor."""
    return (
        _RE_WORK_ITEM_SLUG.search(content)
        and _RE_SECTION_REF.search(content)
        and _RE_AS_OF.search(content)
    )


def _matches_owner_ruling(content):
    """Full owner-ruling shape: ISO date + ruling word + location clause."""
    return (
        _RE_ISO_DATE.search(content)
        and _RE_RULING_WORD.search(content)
        and _has_location_clause(content)
    )


def _matches_receipt(content, spec_matched, ruling_matched, spec_partial, ruling_partial):
    """Receipt: link present and anchor is neither full nor partial spec/ruling."""
    if spec_matched or ruling_matched or spec_partial or ruling_partial:
        return False
    return _RE_RECEIPT.search(content) is not None


def _match_anchor_kinds(content):
    """Detect anchor kinds by full shape with receipt weakest — shape only, no resolution."""
    spec = _matches_spec_section(content)
    ruling = _matches_owner_ruling(content)
    spec_partial = _is_spec_partial(content)
    ruling_partial = _is_ruling_partial(content)
    receipt = _matches_receipt(content, spec, ruling, spec_partial, ruling_partial)
    kinds = set()
    if spec:
        kinds.add(KIND_SPEC_SECTION)
    if ruling:
        kinds.add(KIND_OWNER_RULING)
    if receipt:
        kinds.add(KIND_RECEIPT)
    return kinds


def check_build_ready(body):
    """Decide build-ready marking from an issue body string. Always returns a result dict."""
    statuses, slots_content = _parse_slots(body)
    anchor_content = "\n".join(slots_content[SLOT_ANCHOR])
    matched = sorted(_match_anchor_kinds(anchor_content))

    if statuses[SLOT_ANCHOR] == "missing":
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_SLOT_MISSING,
            anchor_kind=None,
            matched_kinds=matched,
            slots=statuses,
        )
    if statuses[SLOT_ANCHOR] == "empty":
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_SLOT_EMPTY,
            anchor_kind=None,
            matched_kinds=matched,
            slots=statuses,
        )
    if not matched:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_KIND_UNRECOGNIZED,
            anchor_kind=None,
            matched_kinds=matched,
            slots=statuses,
        )
    if len(matched) >= 2:
        return _result(
            ok=False,
            reason=REFUSAL_ANCHOR_KIND_AMBIGUOUS,
            anchor_kind=None,
            matched_kinds=matched,
            slots=statuses,
        )
    return _result(
        ok=True,
        reason=None,
        anchor_kind=matched[0],
        matched_kinds=matched,
        slots=statuses,
    )


def _result(ok, reason, anchor_kind, matched_kinds, slots):
    return {
        "ok": ok,
        "reason": reason,
        "anchorKind": anchor_kind,
        "matchedKinds": matched_kinds,
        "slots": slots,
        "advisory": True,
    }


def _fail_closed_unreadable_body():
    slots = {slot: "unknown" for slot in SLOTS}
    return _result(
        ok=False,
        reason=REFUSAL_BODY_UNREADABLE,
        anchor_kind=None,
        matched_kinds=[],
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
