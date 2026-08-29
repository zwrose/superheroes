"""Drift guard for the test-receipt evidence one-home (issue #1219).

Bites on: each rostered consumer **section** and its ``rubric/test-receipt-evidence.md``
pointer **count** (hand-maintained roster — a deliberate second pointer must be added to the
roster rather than absorbed silently); the home's level-2 headings; and the named clauses in
their named home sections (home-only — consumers point rather than restate).

**Residual blind spots:**

- the pointer and clause rosters are **hand-maintained**;
- heading **order and position** in the home are unguarded — headings are matched as whole-document
  line membership;
- unlike the pointer roster, which has a completeness walker, the **heading and clause rosters have
  none** — a new heading or a newly restated clause is silently unguarded until someone adds it;
- the guard proves nothing about whether the policy is correct, obeyed, or actually applied in any
  review;
- the walker keys on the literal path, so surfaces that restate the policy's substance **without**
  naming the file are invisible — ``skills/showrunner/SKILL.md`` does exactly that at its "Trust
  CI-green" bullet and in its temptation table; that is a known, deliberate residual for this build.
"""
import os
import re

import pytest

from clause_guard import (
    add_one_occurrence_in_section,
    census_excluded,
    check_clause,
    plant_clause_elsewhere,
    section_span,
    without_clause_in_section,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO_ROOT = os.path.abspath(os.path.join(PLUGIN, "..", ".."))

_POINTER = "rubric/test-receipt-evidence.md"
_HOME = "rubric/test-receipt-evidence.md"

_CENSUS_EXCLUDED_DIRS = ("lib/tests/bite_proofs",)
_CENSUS_EXCLUDED_FILES = ("CHANGELOG.md",)

_CONSUMER_ROSTER = [
    ("agents/grounding-seat.md", "## What you check (self-claims → repo)", 1),
    ("skills/review-code/SKILL.md", "## The verify command", 1),
    (
        "skills/review-code/reference/setup.md",
        "## Setup resolution — run these in order",
        1,
    ),
]

_HEADINGS = [
    "## Verify receipt is not a test receipt",
    "## What does ground a test-pass claim",
]

_OTHER_HOME_SECTION = {
    "## Verify receipt is not a test receipt": "## What does ground a test-pass claim",
    "## What does ground a test-pass claim": "## Verify receipt is not a test receipt",
}

_CLAUSE_ROWS = [
    {
        "id": "FB-8",
        "clause": (
            "A green verify exit is **not** evidence the test suite passed — calibration may "
            "run no tests at all."
        ),
        "home_section": "## Verify receipt is not a test receipt",
    },
    {
        "id": "FB-9",
        "clause": "A verify receipt does **not** ground a claim that tests passed.",
        "home_section": "## Verify receipt is not a test receipt",
    },
    {
        "id": "FB-10",
        "clause": (
            "For test-pass claims, look for a **successful** CI conclusion for the named workflow "
            "on the exact head sha (with evidence it runs the claimed tests) or the build's "
            "**ordered suite run** with the command, raw output, and successful exit/pass summary."
        ),
        "home_section": "## What does ground a test-pass claim",
    },
    {
        "id": "FB-11",
        "clause": (
            "A failed, cancelled, or skipped CI run — or a suite run ending in failures — does not "
            "ground the claim."
        ),
        "home_section": "## What does ground a test-pass claim",
    },
]

_BITE_PROOF_DIR = "lib/tests/bite_proofs"


def _census_excluded(rel):
    """The walk's one chokepoint: plugin-relative paths the pointer census must not read."""
    return census_excluded(rel, _CENSUS_EXCLUDED_DIRS, _CENSUS_EXCLUDED_FILES)


def _read(rel):
    with open(os.path.normpath(os.path.join(PLUGIN, rel)), encoding="utf-8") as fh:
        return fh.read()


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    return len(match.group(1)) if match else None


def _check_home_heading(text, heading):
    if heading not in text.splitlines():
        raise AssertionError(
            f"{_HOME}: heading {heading!r} missing — re-add or update "
            f"test_test_receipt_evidence_doctrine.py"
        )


def _check_home_clause(row, read_text=None):
    if read_text is None:
        read_text = _read
    check_clause(
        read_text(_HOME),
        _HOME,
        row["home_section"],
        row["clause"],
        1,
    )


def _text_without_heading(text, heading):
    lines = text.splitlines()
    count = sum(1 for line in lines if line == heading)
    assert count == 1, f"mutation setup: expected one {heading!r} in {_HOME}, found {count}"
    mutated = "\n".join(line for line in lines if line != heading)
    if text.endswith("\n"):
        mutated += "\n"
    assert mutated != text
    return mutated


def _sections_with_pointer(rel, text):
    if _POINTER not in text:
        return set()
    lines = text.splitlines()
    found = set()
    for line in lines:
        heading = line.strip()
        if _heading_level(line) != 2:
            continue
        start, end = section_span(lines, heading, rel)
        if _POINTER in "\n".join(lines[start:end]):
            found.add((rel, heading))
    return found


def _walk_plugin_pointer_sections(plugin_root):
    """Every level-2 section under ``plugin_root`` carrying the pointer, minus excluded paths."""
    found = set()
    for root, _dirs, files in os.walk(plugin_root):
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, name), plugin_root)
            if _census_excluded(rel):
                continue
            with open(os.path.join(plugin_root, rel), encoding="utf-8") as fh:
                found |= _sections_with_pointer(rel, fh.read())
    return found


def _walk_pointer_carrying_sections():
    found = _walk_plugin_pointer_sections(PLUGIN)
    conventions = os.path.join(REPO_ROOT, "CONVENTIONS.md")
    if os.path.isfile(conventions):
        with open(conventions, encoding="utf-8") as fh:
            text = fh.read()
        if _POINTER in text:
            found |= _sections_with_pointer("../../CONVENTIONS.md", text)
    return found


def _check_pointer_roster_complete(found_sections):
    roster_sections = frozenset((rel, section) for rel, section, _ in _CONSUMER_ROSTER)
    if found_sections != roster_sections:
        missing = sorted(roster_sections - found_sections)
        extra = sorted(found_sections - roster_sections)
        raise AssertionError(
            f"pointer roster drift: missing={missing!r}, unrostered={extra!r} — extend roster"
        )


def _write_md(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _synthetic_plugin_tree(root):
    _write_md(
        os.path.join(root, "agents", "grounding-seat.md"),
        [
            "## What you check (self-claims → repo)",
            f"apply the policy in {_POINTER}.",
        ],
    )
    _write_md(
        os.path.join(root, *_BITE_PROOF_DIR.split("/"), "wo_synthetic.md"),
        ["## Neutralization", f"per {_POINTER}, the detector went red with itself unedited."],
    )
    _write_md(
        os.path.join(root, "CHANGELOG.md"),
        ["## 0.1.0", f"policy moved to {_POINTER}."],
    )


# --- census exclusion ---


def test_walk_skips_bite_proof_records(tmp_path):
    _synthetic_plugin_tree(str(tmp_path))
    found = _walk_plugin_pointer_sections(str(tmp_path))
    assert not [rel for rel, _ in found if rel.startswith(_BITE_PROOF_DIR)], (
        f"bite-proof record surfaced in the census walk: {sorted(found)!r}"
    )


def test_walk_still_bites_outside_bite_proofs(tmp_path):
    _synthetic_plugin_tree(str(tmp_path))
    assert _walk_plugin_pointer_sections(str(tmp_path)) == {
        ("agents/grounding-seat.md", "## What you check (self-claims → repo)"),
    }


def test_census_excludes_every_real_bite_proof_record():
    records = sorted(
        os.path.join(_BITE_PROOF_DIR, name)
        for name in os.listdir(os.path.join(PLUGIN, _BITE_PROOF_DIR))
        if name.endswith(".md")
    )
    assert records, f"no bite-proof records found under {_BITE_PROOF_DIR}"
    assert [rel for rel in records if not _census_excluded(rel)] == []


def test_census_excludes_changelog():
    assert _census_excluded("CHANGELOG.md")


@pytest.mark.parametrize(
    "rel",
    [
        _HOME,
        "agents/grounding-seat.md",
        "skills/review-code/SKILL.md",
        "lib/tests/bite_proofs_notes.md",
        "docs/bite_proofs/notes.md",
    ],
)
def test_census_does_not_exclude_consumer_surfaces(rel):
    assert not _census_excluded(rel)


# --- positives ---


@pytest.mark.parametrize(
    "rel,section,expected_count",
    _CONSUMER_ROSTER,
    ids=[f"FB-{i}" for i in range(1, len(_CONSUMER_ROSTER) + 1)],
)
def test_consumer_section_points_at_test_receipt_evidence_home(rel, section, expected_count):
    check_clause(_read(rel), rel, section, _POINTER, expected_count)


@pytest.mark.parametrize("heading", _HEADINGS, ids=["FB-6", "FB-7"])
def test_home_has_heading(heading):
    _check_home_heading(_read(_HOME), heading)


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["id"] for r in _CLAUSE_ROWS])
def test_home_clause_present(row):
    _check_home_clause(row)


def test_pointer_roster_is_complete():
    _check_pointer_roster_complete(_walk_pointer_carrying_sections())


# --- negatives: consumer pointers (FB-1 … FB-3) ---


@pytest.mark.parametrize(
    "rel,section,expected_count",
    _CONSUMER_ROSTER,
    ids=[f"FB-{i}" for i in range(1, len(_CONSUMER_ROSTER) + 1)],
)
def test_negative_consumer_pointer_missing_in_section(rel, section, expected_count):
    mutated = without_clause_in_section(_read(rel), rel, section, _POINTER)
    with pytest.raises(AssertionError, match=re.escape(_POINTER)):
        check_clause(mutated, rel, section, _POINTER, expected_count)


@pytest.mark.parametrize(
    "rel,section,expected_count",
    _CONSUMER_ROSTER,
    ids=[f"FB-{i}" for i in range(1, len(_CONSUMER_ROSTER) + 1)],
)
def test_negative_consumer_pointer_over_count_in_section(rel, section, expected_count):
    mutated = add_one_occurrence_in_section(_read(rel), rel, section, _POINTER)
    with pytest.raises(AssertionError, match=re.escape(_POINTER)):
        check_clause(mutated, rel, section, _POINTER, expected_count)


# --- negatives: roster completeness (FB-4) ---


def test_negative_pointer_roster_unrostered_file():
    roster = frozenset((rel, section) for rel, section, _ in _CONSUMER_ROSTER)
    with pytest.raises(AssertionError, match="unrostered"):
        _check_pointer_roster_complete(roster | {("synthetic/unrostered.md", "## Synthetic")})


def test_negative_pointer_in_unrostered_section_of_rostered_file():
    rel, section, _ = _CONSUMER_ROSTER[0]
    with pytest.raises(AssertionError, match="unrostered"):
        _check_pointer_roster_complete(
            _walk_pointer_carrying_sections() | {(rel, "## Unrostered section")}
        )


# --- negatives: headings (FB-6, FB-7) ---


@pytest.mark.parametrize("heading", _HEADINGS, ids=["FB-6", "FB-7"])
def test_negative_home_heading_missing(heading):
    mutated = _text_without_heading(_read(_HOME), heading)
    with pytest.raises(AssertionError, match=re.escape(heading)):
        _check_home_heading(mutated, heading)


# --- negatives: home clauses (FB-8 … FB-11) ---


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["id"] for r in _CLAUSE_ROWS])
def test_negative_home_clause_missing_from_section(row):
    mutated = without_clause_in_section(
        _read(_HOME), _HOME, row["home_section"], row["clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["home_section"])):
        _check_home_clause(row, lambda rel: mutated if rel == _HOME else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["id"] for r in _CLAUSE_ROWS])
def test_negative_home_clause_planted_elsewhere(row):
    other = _OTHER_HOME_SECTION[row["home_section"]]
    mutated = plant_clause_elsewhere(
        _read(_HOME), _HOME, row["home_section"], other, row["clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["home_section"])):
        _check_home_clause(row, lambda rel: mutated if rel == _HOME else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["id"] for r in _CLAUSE_ROWS])
def test_negative_home_clause_over_count(row):
    mutated = add_one_occurrence_in_section(
        _read(_HOME), _HOME, row["home_section"], row["clause"],
    )
    with pytest.raises(AssertionError, match="expected count 1"):
        _check_home_clause(row, lambda rel: mutated if rel == _HOME else _read(rel))
