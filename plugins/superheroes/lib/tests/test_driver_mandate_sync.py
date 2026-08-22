"""Drift guard for driver-mandate facts across enumerated surfaces (CONVENTIONS §11.2 pattern 2).

Guards six driver-mandate literals that now live in two hand-maintained homes each — the
authoritative home is read first for home-derived pins, and every copy-holder is asserted against
the same literal:

- ``skills/review-code/reference/round-driver.md`` — BACKGROUNDABLE_VERIFY copy-holder 1
- ``skills/workhorse/SKILL.md`` — BACKGROUNDABLE_VERIFY copy-holder 2
- ``rubric/review-discipline.md`` — authoritative home for SKIP_CITATION and PARITY
- ``skills/showrunner/reference/vet-receipt.md`` — SKIP_CITATION and PARITY copy-holder

Six guarded elements (two single-home facts — the flip conditional and the post-handback merge
policy — are deliberately out of scope; they live only in ``rubric/review-discipline.md``).

What is guaranteed is **presence** of each pinned literal verbatim modulo ``*``-stripping and
whitespace collapse on every enumerated surface. The guard does **not** detect a literal that is
present but neutralized by surrounding prose (for example an appended exception clause); that
semantic check is deliberately out of scope — the enumeration exists to prevent exactly that
overclaim.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"
_VET_RECEIPT = "skills/showrunner/reference/vet-receipt.md"

_BACKGROUNDABLE_VERIFY = (
    "The verify step may run harness-backgrounded and polled in-turn — the already-sanctioned "
    "shape for long local work — because the host's foreground command-timeout cap bounds a "
    "single call, not the step; what stays forbidden is unchanged, `&`/setsid/nohup and ending "
    "the turn to wait."
)

_SKIP_CITATION = "`driver-blocker` issue by number"

_PARITY = "configured reviewer engine"

_BACKGROUNDABLE_VERIFY_SURFACES = (
    "skills/review-code/reference/round-driver.md",
    "skills/workhorse/SKILL.md",
)


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalize(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def _assert_literal_present(rel, text, literal):
    normalized_literal = _normalize(literal)
    if normalized_literal not in _normalize(text):
        raise AssertionError(
            f"literal missing from {rel} — expected substring: {normalized_literal!r}"
        )


@pytest.mark.parametrize(
    "rel",
    _BACKGROUNDABLE_VERIFY_SURFACES,
    ids=["round-driver", "workhorse"],
)
def test_backgroundable_verify_present(rel):
    # axis: presence of BACKGROUNDABLE_VERIFY literal in enumerated copy-holder surface
    text = _read(rel)
    _assert_literal_present(rel, text, _BACKGROUNDABLE_VERIFY)


def test_skip_citation_present_in_home():
    # axis: presence of SKIP_CITATION literal in review-discipline.md home (anti-tautology leg)
    home_text = _read(_HOME)
    _assert_literal_present(_HOME, home_text, _SKIP_CITATION)


def test_skip_citation_present_in_vet_receipt_copy():
    # axis: presence of home-derived SKIP_CITATION literal in vet-receipt.md copy
    home_text = _read(_HOME)
    _assert_literal_present(_HOME, home_text, _SKIP_CITATION)
    copy_text = _read(_VET_RECEIPT)
    _assert_literal_present(_VET_RECEIPT, copy_text, _SKIP_CITATION)


def test_parity_present_in_home():
    # axis: presence of PARITY literal in review-discipline.md home (anti-tautology leg)
    home_text = _read(_HOME)
    _assert_literal_present(_HOME, home_text, _PARITY)


def test_parity_present_in_vet_receipt_copy():
    # axis: presence of home-derived PARITY literal in vet-receipt.md copy
    home_text = _read(_HOME)
    _assert_literal_present(_HOME, home_text, _PARITY)
    copy_text = _read(_VET_RECEIPT)
    _assert_literal_present(_VET_RECEIPT, copy_text, _PARITY)
