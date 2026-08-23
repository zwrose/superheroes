"""Drift guard for driver-mandate facts across enumerated surfaces (CONVENTIONS §11.2 pattern 2).

Guards three pinned clauses across four surfaces = six guarded elements — the
authoritative home is read first for hand-typed clauses asserted in the home before being asserted
in the copy (CONVENTIONS §11.3 anti-tautology leg):

- ``skills/review-code/reference/round-driver.md`` — BACKGROUNDABLE_VERIFY copy-holder 1
- ``skills/workhorse/SKILL.md`` — BACKGROUNDABLE_VERIFY copy-holder 2
- ``rubric/review-discipline.md`` — authoritative home for SKIP_CITATION and PARITY
- ``skills/showrunner/reference/vet-receipt.md`` — SKIP_CITATION and PARITY copy-holder

Neither BACKGROUNDABLE_VERIFY surface is authoritative — the pin is a symmetric two-copy equality
per CONVENTIONS §11.2. SKIP_CITATION and PARITY are home-first, then copy-holder.

One single-home fact — the post-handback merge policy — is deliberately out of scope; it lives
only in ``rubric/review-discipline.md``. The flip conditional's operative clause is pinned in its
single home (owner-authorized 2026-08-23) — presence-only, same limits as every pin here.

What is guaranteed is **presence** of each pinned literal verbatim modulo ``*``-stripping and
whitespace collapse. BACKGROUNDABLE_VERIFY is pinned **whole-file** (count == 1 on each copy-holder)
because its surfaces carry `` ``` `` fences inside section-scoped regions. SKIP_CITATION and
PARITY are pinned inside their **declared sections** on every enumerated surface. Section extraction
reuses ``_file_section`` and ``_normalized`` from ``test_charter_boundary_sync``; that reader is
deliberately **fence-blind** (fence-awareness was tried and reverted in PR #727).

**Known residual, not guarded here:** nothing mechanically asserts that a section-anchored
surface stays fence-free. A line-oriented fence check over ``_file_section`` output is inert by
construction — that reader returns whitespace-collapsed text, so ``splitlines()`` sees one line —
and a guard that cannot fail is worse than none. ``rubric/review-discipline.md`` is already
covered whole-file by ``test_charter_boundary_sync.test_no_fence_lines``; ``vet-receipt.md``
cannot join that tuple because it legitimately carries a fenced ``## Skeleton`` block outside the
guarded section. Today the guarded section is fence-free (measured); a correctly-homed raw-text
tripwire is handed up as a follow-up.

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
    "A seat that ran on a vendor other than its seat-map assignment with no recorded forfeit on the "
    "assigned vendor is a vet finding"
)
_PARITY_COPY = (
    "A seat that ran off its seat-map assignment with no recorded forfeit on the vendor it was "
    "assigned is a finding"
)

_FLIP_HOME = (
    "a full-lane review that is not the certified loop stops being a disclosable degradation and "
    "becomes a vet finding, and the only valve is driver-or-park — never driver-or-improvise"
)

_BACKGROUNDABLE_VERIFY_SURFACES = [
    "skills/review-code/reference/round-driver.md",
    "skills/workhorse/SKILL.md",
]


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
    "rel",
    _BACKGROUNDABLE_VERIFY_SURFACES,
    ids=["round-driver", "workhorse"],
)
def test_backgroundable_verify_present(rel):
    # axis: presence of BACKGROUNDABLE_VERIFY literal whole-file, exactly once
    normalized_file = _normalized(_read(rel))
    normalized_literal = _normalized(_BACKGROUNDABLE_VERIFY)
    count = normalized_file.count(normalized_literal)
    assert count == 1, (
        f"expected exactly one occurrence in {rel}, found {count}"
    )


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


def test_flip_operative_clause_present_in_home():
    # axis: presence of the flip's operative clause in its single home, exactly once
    # (owner-authorized pin, 2026-08-23: the release's most load-bearing sentence was
    # softenable with no red test — vet-156 probe)
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert home_section_text.count(_normalized(_FLIP_HOME)) == 1
