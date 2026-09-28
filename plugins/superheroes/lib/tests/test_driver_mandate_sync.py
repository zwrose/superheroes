"""Drift guard for driver-mandate facts across enumerated surfaces (CONVENTIONS §11.2 pattern 2).

Guards two pinned clauses:

- ``skills/review-code/reference/round-driver.md`` and ``skills/workhorse/SKILL.md`` —
  BACKGROUNDABLE_VERIFY (symmetric two-surface pin: whole-file count == 1 on each copy-holder;
  neither surface is authoritative)
- ``rubric/review-discipline.md`` — the flip conditional's operative clause (single-home
  hard-line pin; presence-only, exactly once in the driver-mandate section)

SKIP_CITATION and PARITY bars live only in the authoritative home; ``vet-receipt.md`` points at
that home and does not restate those finding sentences — no copy-holder pins remain for them.

One single-home fact — the post-handback merge policy — is deliberately out of scope; it lives
only in ``rubric/review-discipline.md``.

What is guaranteed is **presence** of each pinned literal verbatim modulo ``*``-stripping and
whitespace collapse. BACKGROUNDABLE_VERIFY is pinned **whole-file** because its surfaces carry
`` ``` `` fences inside section-scoped regions. The flip clause is pinned inside the driver-mandate
section. Section extraction reuses ``_file_section`` and ``_normalized`` from
``test_charter_boundary_sync``; that reader is deliberately **fence-blind** (fence-awareness was
tried and reverted in PR #727).

The guard does **not** detect a literal that is present but neutralized by surrounding prose;
that semantic check is deliberately out of scope.
"""
import os

import pytest

from test_charter_boundary_sync import _file_section, _normalized

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"

_DRIVER_MANDATE_SECTION = (
    "## The driver mandate — the certified loop, its skips, and the flip"
)

_BACKGROUNDABLE_VERIFY = (
    "The verify step may run harness-backgrounded and polled in-turn — the already-sanctioned "
    "shape for long local work — because the host's foreground command-timeout cap bounds a "
    "single call, not the step; what stays forbidden is unchanged, `&`/setsid/nohup and ending "
    "the turn to wait."
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


def test_flip_operative_clause_present_in_home():
    # axis: presence of the flip's operative clause in its single home, exactly once
    # (owner-authorized pin, 2026-08-23: the release's most load-bearing sentence was
    # softenable with no red test — vet-156 probe)
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert home_section_text.count(_normalized(_FLIP_HOME)) == 1
