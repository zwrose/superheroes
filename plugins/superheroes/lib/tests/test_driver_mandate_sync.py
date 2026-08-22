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
whitespace collapse inside its **declared section** on every enumerated surface. Section
extraction reuses ``_file_section`` and ``_normalized`` from ``test_charter_boundary_sync``;
that reader is deliberately **fence-blind** (fence-awareness was tried and reverted in PR #727).

The guard does **not** detect a literal that is present but neutralized by surrounding prose (for
example an appended exception clause); that semantic check is deliberately out of scope — the
enumeration exists to prevent exactly that overclaim.
"""
import os

import pytest

from test_charter_boundary_sync import _file_section, _normalized

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"
_VET_RECEIPT = "skills/showrunner/reference/vet-receipt.md"

_DRIVER_MANDATE_SECTION = (
    "## The driver mandate — the certified loop, its skips, and the flip"
)
_VET_TRIGGERED_SECTION = (
    "## Triggered fields — the artifacts raise them, not your memory"
)
_WORKHORSE_DELEGATE_SECTION = (
    "## 7. Delegate every implementation (lane-scoped — no size exception)"
)
_ROUND_DRIVER_ACTIONS_SECTION = "## Actions and payloads"

_BACKGROUNDABLE_VERIFY = (
    "The verify step may run harness-backgrounded and polled in-turn — the already-sanctioned "
    "shape for long local work — because the host's foreground command-timeout cap bounds a "
    "single call, not the step; what stays forbidden is unchanged, `&`/setsid/nohup and ending "
    "the turn to wait."
)

_SKIP_CITATION_HOME = (
    "A skip citing nothing, and a skip citing a closed issue, are each a vet finding"
)
_SKIP_CITATION_COPY = (
    "A citation that is absent, or that names a closed issue, is a finding"
)

_PARITY_HOME = (
    "A panel seated off the configured reviewer engine with no recorded forfeit on that "
    "engine is a vet finding"
)
_PARITY_COPY = (
    "A seat substituted with no recorded forfeit on the engine it replaced is a finding"
)

_BACKGROUNDABLE_VERIFY_SURFACES = {
    "skills/review-code/reference/round-driver.md": _ROUND_DRIVER_ACTIONS_SECTION,
    "skills/workhorse/SKILL.md": _WORKHORSE_DELEGATE_SECTION,
}


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section_text(rel, section):
    return _file_section(rel, section, _read)


def _assert_clause_in_section(rel, section, literal):
    section_text = _section_text(rel, section)
    normalized_literal = _normalized(literal)
    if normalized_literal not in section_text:
        raise AssertionError(
            f"literal missing from {rel} (section {section!r}) — "
            f"expected substring: {normalized_literal!r}"
        )


@pytest.mark.parametrize(
    "rel,section",
    list(_BACKGROUNDABLE_VERIFY_SURFACES.items()),
    ids=["round-driver", "workhorse"],
)
def test_backgroundable_verify_present(rel, section):
    # axis: presence of BACKGROUNDABLE_VERIFY literal in enumerated copy-holder section
    _assert_clause_in_section(rel, section, _BACKGROUNDABLE_VERIFY)


def test_skip_citation_present_in_home():
    # axis: presence of the skip-citation rule clause in review-discipline.md home section
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert _normalized(_SKIP_CITATION_HOME) in home_section_text


def test_skip_citation_present_in_vet_receipt_copy():
    # axis: presence of the holder-specific skip-citation clause in vet-receipt.md
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert _normalized(_SKIP_CITATION_HOME) in home_section_text
    copy_section_text = _section_text(_VET_RECEIPT, _VET_TRIGGERED_SECTION)
    assert _normalized(_SKIP_CITATION_COPY) in copy_section_text


def test_parity_present_in_home():
    # axis: presence of the parity rule clause in review-discipline.md home, exactly once
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert home_section_text.count(_normalized(_PARITY_HOME)) == 1


def test_parity_present_in_vet_receipt_copy():
    # axis: presence of the holder-specific parity clause in vet-receipt.md
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert home_section_text.count(_normalized(_PARITY_HOME)) == 1
    copy_section_text = _section_text(_VET_RECEIPT, _VET_TRIGGERED_SECTION)
    assert _normalized(_PARITY_COPY) in copy_section_text
