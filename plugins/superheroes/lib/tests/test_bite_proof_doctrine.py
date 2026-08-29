"""Drift guard for the bite-proof doctrine one-home shape (CONVENTIONS §11, #765).

Bites on: each rostered consumer **section** and its ``rubric/bite-proof.md`` pointer **count**
(hand-maintained roster — a deliberate second pointer must be added to the roster rather than
absorbed silently); the named clauses in their named home and copy-holder sections; and the home's
headings.

**Residual blind spots:**

- the clause and pointer rosters are **hand-maintained**;
- heading **order and position** in the home are unguarded — headings are matched as whole-document
  line membership — and that is deliberate, because no consumer cites relative order;
- unlike the pointer roster, which has a completeness walker, the **heading and clause rosters have
  none** — a new heading or a new restated clause is silently unguarded until someone adds it;
- the guard proves nothing about whether the doctrine is correct, obeyed, or actually recorded for
  any change.
"""
import os
import re

import pytest

from clause_guard import (
    add_one_occurrence_in_section,
    census_excluded,
    check_clause,
    drop_one_occurrence_in_section,
    iter_headings,
    plant_clause_elsewhere,
    section_span,
    without_clause_in_section,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO_ROOT = os.path.abspath(os.path.join(PLUGIN, "..", ".."))

_POINTER = "rubric/bite-proof.md"
_HOME = "rubric/bite-proof.md"

# Bite-proof records are receipts, not consumed surfaces: they are categorically outside every
# content census, exactly as detector self-paths are. A proof must be free to quote the literal
# it proves — a census that polices its own evidence re-fires on every new proof.
# Standing advisor ruling, 2026-08-25 (#1136 shipped the code half; this is the pointer census's).
_CENSUS_EXCLUDED_DIRS = ("lib/tests/bite_proofs",)

# CHANGELOG quotes historical doctrine paths; it is not a consumer surface.
_CENSUS_EXCLUDED_FILES = ("CHANGELOG.md",)


def _census_excluded(rel):
    """The walk's one chokepoint: plugin-relative paths the pointer census must not read."""
    return census_excluded(rel, _CENSUS_EXCLUDED_DIRS, _CENSUS_EXCLUDED_FILES)


# Copy-holder disposition (§11.2 — extend roster when adding a pointer; bump expected_count when
# a section gains a deliberate second pointer):
# workhorse §6 Decompose — order-template doctrine points at bite-proof home (count=1)
# workhorse §8 Verify — orchestrator re-reads doctrine when build adds detector (count=1)
# workhorse § When you're tempted — temptation table row on vacuous bite-proofs (count=1)
# implementer § The rules — disclosure shapes and doctrine reference in short-return rule (count=1)
# implementer § Validating — validity rule 6 names expected bite-proof (count=1)
# test-reviewer § Named test-smell taxonomy — axis-line smell cites doctrine home (count=1)
# review-discipline § Review bars — Mechanical guards subsection structural-pin doctrine (count=1)
# CONVENTIONS §12 — verification contracts pointer to vacuity-trap home (count=2)
_CONSUMER_ROSTER = [
    ("skills/workhorse/SKILL.md", "## 6. Decompose into work orders", 1),
    ("skills/workhorse/SKILL.md", "## 8. Verify — re-run every receipt yourself", 1),
    ("skills/workhorse/SKILL.md", "## When you're tempted", 1),
    ("agents/implementer.md", "## The rules", 1),
    ("agents/implementer.md", "## Validating your work order", 1),
    ("agents/test-reviewer.md", "## Named test-smell taxonomy", 1),
    ("rubric/review-discipline.md", "## Review bars and recorded residuals", 1),
    (
        "../../CONVENTIONS.md",
        "## 12. Verification contracts (fix-ships-its-detector, real-seam tests)",
        2,
    ),
]

_HEADINGS = [
    "## The obligation",
    "## Four ways a bite-proof is vacuous",
    "## The record",
    "## When the proof cannot be produced",
    "## When the proof runs under a normalization",
    "## Who owes what",
]

_CLAUSE_ROWS = [
    {
        "home_clause": (
            "the guarded element, the neutralization to apply, and the detector expected to go red"
        ),
        "home_section": "## Who owes what",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## Validating your work order",
        "holder_count": 1,
    },
    {
        "home_clause": "Unprovable as placed",
        "home_section": "## When the proof cannot be produced",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
        "holder_count": 1,
    },
    {
        "home_clause": "Unreachable through this entry point",
        "home_section": "## When the proof cannot be produced",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
        "holder_count": 1,
    },
    {
        "home_clause": "Unrunnable here",
        "home_section": "## When the proof cannot be produced",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
        "holder_count": 1,
    },
    {
        "home_clause": "32 KiB",
        "home_section": "## The record",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
        "holder_count": 1,
    },
    {
        "home_clause": "128 KiB",
        "home_section": "## The record",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
        "holder_count": 1,
    },
    {
        "home_clause": "names the bite-proof it expects",
        "home_section": "## Who owes what",
        "home_count": 1,
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## 6. Decompose into work orders",
        "holder_count": 1,
    },
    {
        "home_clause": "per guarded element",
        "home_section": "## The record",
        "home_count": 2,
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## 8. Verify — re-run every receipt yourself",
        "holder_count": 1,
    },
    {
        "home_clause": "A green run is equally consistent with",
        "home_section": "## The obligation",
        "home_count": 1,
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## When you're tempted",
        "holder_count": 1,
    },
    {
        "home_clause": "with the detector unedited",
        "home_section": "## The record",
        "home_count": 1,
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## When you're tempted",
        "holder_count": 1,
    },
    {
        "home_clause": "through the path the test uses",
        "home_section": "## When the proof cannot be produced",
        "home_count": 1,
        "copy_holder": "agents/test-reviewer.md",
        "copy_holder_section": "## What to Flag",
        "holder_count": 1,
    },
    {
        "home_clause": "owed disclosure",
        "home_section": "## Who owes what",
        "home_count": 1,
        "copy_holder": "agents/test-reviewer.md",
        "copy_holder_section": "## Named test-smell taxonomy",
        "holder_count": 1,
    },
    {
        "id": "FA-1",
        "home_clause": "**The guarded-element set is declared up front.**",
        "home_section": "## The record",
        "home_count": 1,
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## Validating your work order",
        "holder_clause": (
            "**The guarded-element set is declared up front** — what an order must declare, "
            "what to do when it declares nothing, and how the record's ceilings apply over that "
            "enumeration are stated once in the bite-proof reference named above, § *The record*; "
            "read it there rather than here."
        ),
        "holder_count": 1,
    },
    {
        "id": "FA-2",
        "home_clause": (
            "A proof that reaches the constant through the symbol that defines it stays green under "
            "*any* value, so it proves the plumbing and nothing about the contract (PR #1159, vet "
            "181; same shape at PR #1156, vet 178)."
        ),
        "home_section": "## The obligation",
        "home_count": 1,
        "copy_holder": "agents/test-reviewer.md",
        "copy_holder_section": "## What to Flag",
        "holder_clause": (
            "**literal-pin** — a diff-added test that reaches an external-contract constant "
            "through the symbol that defines it rather than pinning the literal."
        ),
        "holder_count": 1,
    },
    {
        "id": "FA-3",
        "home_only": True,
        "home_clause": (
            "A neutralization that applies more than one replacement must assert that each "
            "replacement landed, never that the aggregate diff is merely non-empty. When one "
            "anchor drifts, a single replacement can silently no-op while the aggregate diff still "
            "looks applied and the detector goes red for the other replacement's sake — the proof "
            "is vacuous. An aggregate-only assertion is the rejected shape."
        ),
        "home_section": "## The record",
        "home_count": 1,
    },
]

_ROW_IDS = [row.get("id", row["home_clause"][:40]) for row in _CLAUSE_ROWS]
_COPY_HOLDER_ROWS = [row for row in _CLAUSE_ROWS if not row.get("home_only")]
_PARTIAL_DRIFT_ROWS = [row for row in _CLAUSE_ROWS if row["home_count"] > 1]


def _read(rel):
    with open(os.path.normpath(os.path.join(PLUGIN, rel)), encoding="utf-8") as fh:
        return fh.read()


def _holder_clause(row):
    return row.get("holder_clause", row["home_clause"])


def _plant_target_section(rel, source_section):
    """Pick a level-2 section in ``rel`` other than ``source_section`` for plant mutations."""
    swaps = {
        ("agents/implementer.md", "## Validating your work order"): "## The rules",
        ("agents/implementer.md", "## The rules"): "## Validating your work order",
        (
            "skills/workhorse/SKILL.md",
            "## 6. Decompose into work orders",
        ): "## When you're tempted",
        (
            "skills/workhorse/SKILL.md",
            "## 8. Verify — re-run every receipt yourself",
        ): "## 6. Decompose into work orders",
        ("skills/workhorse/SKILL.md", "## When you're tempted"): (
            "## 8. Verify — re-run every receipt yourself"
        ),
        ("agents/test-reviewer.md", "## What to Flag"): "## Named test-smell taxonomy",
        ("agents/test-reviewer.md", "## Named test-smell taxonomy"): "## What to Flag",
    }
    return swaps[(rel, source_section)]


def _pointer_count_in_section(text, rel, section_heading):
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    return "\n".join(lines[start:end]).count(_POINTER)


def _check_consumer_pointer_in_section(text, rel, section_heading, expected_count):
    actual = _pointer_count_in_section(text, rel, section_heading)
    if actual != expected_count:
        raise AssertionError(
            f"{rel} (section {section_heading}): expected {_POINTER!r} count {expected_count}, "
            f"found {actual} — re-add pointer(s) or update test_bite_proof_doctrine.py roster"
        )


def _check_home_heading(text, heading):
    lines = text.splitlines()
    found = any(lines[i] == heading for i, _ in iter_headings(lines))
    if not found:
        raise AssertionError(
            f"{_HOME}: heading {heading!r} missing — re-add or update test_bite_proof_doctrine.py"
        )


def _check_clause_sync(row, read_text=None):
    if read_text is None:
        read_text = _read
    check_clause(
        read_text(_HOME),
        _HOME,
        row["home_section"],
        row["home_clause"],
        row["home_count"],
    )
    if not row.get("home_only"):
        check_clause(
            read_text(row["copy_holder"]),
            row["copy_holder"],
            row["copy_holder_section"],
            _holder_clause(row),
            row["holder_count"],
        )


def _text_without_one_pointer_in_section(text, rel, section_heading):
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    count = section_text.count(_POINTER)
    assert count >= 1, (
        f"mutation setup: {_POINTER!r} missing in {rel} section {section_heading!r} (count={count})"
    )
    new_section = section_text.replace(_POINTER, "rubric/bite-proof-DRIFT.md", 1)
    assert new_section.count(_POINTER) == count - 1, (
        f"mutation setup: expected {_POINTER!r} count {count - 1} in {rel} section "
        f"{section_heading!r}, found {new_section.count(_POINTER)}"
    )
    new_lines = lines[:start] + new_section.splitlines() + lines[end:]
    mutated = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
    assert mutated != text
    return mutated


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
    for i, level in iter_headings(lines):
        if level != 2:
            continue
        heading = lines[i].strip()
        start, end = section_span(lines, heading, rel)
        if _POINTER in "\n".join(lines[start:end]):
            found.add((rel, heading))
    return found


def _walk_plugin_pointer_sections(plugin_root):
    """Every level-2 section under ``plugin_root`` carrying the pointer, minus the excluded paths.

    Bites on: exclusion breadth. The single ``_census_excluded`` call below is the chokepoint —
    the walk holds no per-file skip of its own.
    """
    found = set()
    for root, _dirs, files in os.walk(plugin_root):
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, name), plugin_root)
            if _census_excluded(rel):
                continue
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                found |= _sections_with_pointer(rel, fh.read())
    return found


def _walk_pointer_carrying_sections():
    found = _walk_plugin_pointer_sections(PLUGIN)
    with open(os.path.join(REPO_ROOT, "CONVENTIONS.md"), encoding="utf-8") as fh:
        text = fh.read()
        if _POINTER in text:
            found |= _sections_with_pointer("../../CONVENTIONS.md", text)
    return found


def _check_pointer_roster_complete(found_sections):
    roster_sections = frozenset((rel, section) for rel, section, _ in _CONSUMER_ROSTER)
    if found_sections != roster_sections:
        missing, extra = sorted(roster_sections - found_sections), sorted(found_sections - roster_sections)
        raise AssertionError(
            f"pointer roster drift: missing={missing!r}, unrostered={extra!r} — extend roster"
        )


# --- census exclusion: bite-proof records are receipts, outside the census (#1155) ---


_BITE_PROOF_DIR = "lib/tests/bite_proofs"


def _write_md(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _synthetic_plugin_tree(root):
    """A miniature plugin tree: a consumer surface, a bite-proof record, and a CHANGELOG — each
    carrying the pointer *inside* a level-2 section, which is the only shape the walk records."""
    _write_md(
        os.path.join(root, "skills", "workhorse", "SKILL.md"),
        ["## 8. Verify", f"the record shape lives in {_POINTER}."],
    )
    _write_md(
        os.path.join(root, *_BITE_PROOF_DIR.split("/"), "wo_synthetic.md"),
        ["## Neutralization", f"per {_POINTER}, the detector went red with itself unedited."],
    )
    _write_md(
        os.path.join(root, "CHANGELOG.md"),
        ["## 0.1.0", f"doctrine moved to {_POINTER}."],
    )


def test_walk_skips_bite_proof_records(tmp_path):
    """Red on the pre-#1155 shape: without the exclusion the record is returned as a section."""
    _synthetic_plugin_tree(str(tmp_path))
    found = _walk_plugin_pointer_sections(str(tmp_path))
    assert not [rel for rel, _ in found if rel.startswith(_BITE_PROOF_DIR)], (
        f"bite-proof record surfaced in the census walk: {sorted(found)!r}"
    )


def test_walk_still_bites_outside_bite_proofs(tmp_path):
    """The census still bites: a consumer surface carrying the pointer is still returned, and the
    exclusion is not wide enough to swallow it (or to re-admit the CHANGELOG)."""
    _synthetic_plugin_tree(str(tmp_path))
    assert _walk_plugin_pointer_sections(str(tmp_path)) == {
        ("skills/workhorse/SKILL.md", "## 8. Verify"),
    }


def test_census_excludes_every_real_bite_proof_record():
    """Real-channel: the predicate holds over the repository's actual record paths, not only
    synthetic ones."""
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
        "skills/workhorse/SKILL.md",
        "agents/implementer.md",
        # A sibling whose name merely *prefixes* the excluded directory is not excluded.
        "lib/tests/bite_proofs_notes.md",
        # A directory of the same name somewhere else is not the rostered exclusion.
        "docs/bite_proofs/notes.md",
    ],
)
def test_census_does_not_exclude_consumer_surfaces(rel):
    assert not _census_excluded(rel)


# --- section_span direct tests (synthetic in-memory documents) ---


def test_section_span_includes_deeper_subheading():
    lines = "\n".join([
        "## Parent",
        "parent body",
        "### Child",
        "child body",
        "## Sibling",
    ]).splitlines()
    start, end = section_span(lines, "## Parent", "synthetic")
    assert lines[start] == "## Parent"
    body = "\n".join(lines[start:end])
    assert "### Child" in body
    assert "child body" in body
    assert "## Sibling" not in body


def test_section_span_ends_at_same_or_higher_level():
    lines = "\n".join([
        "## First",
        "first body",
        "## Second",
        "second body",
    ]).splitlines()
    start, end = section_span(lines, "## First", "synthetic")
    assert lines[end] == "## Second"
    assert "first body" in "\n".join(lines[start:end])
    assert "second body" not in "\n".join(lines[start:end])


def test_section_span_zero_headings_raises():
    lines = ["## Other", "text"]
    with pytest.raises(RuntimeError, match="expected exactly one '## Missing'"):
        section_span(lines, "## Missing", "synthetic")


def test_section_span_duplicate_headings_raises():
    lines = "\n".join(["## Dup", "a", "## Dup", "b"]).splitlines()
    with pytest.raises(RuntimeError, match="expected exactly one '## Dup'"):
        section_span(lines, "## Dup", "synthetic")


@pytest.mark.parametrize("rel,section,expected_count", _CONSUMER_ROSTER, ids=[f"{r}::{s}" for r, s, _ in _CONSUMER_ROSTER])
def test_consumer_section_points_at_bite_proof_home(rel, section, expected_count):
    _check_consumer_pointer_in_section(_read(rel), rel, section, expected_count)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_home_has_heading(heading):
    _check_home_heading(_read(_HOME), heading)


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=_ROW_IDS)
def test_clause_present_in_home_and_copy_holder(row):
    _check_clause_sync(row)


def test_pointer_roster_is_complete():
    _check_pointer_roster_complete(_walk_pointer_carrying_sections())


@pytest.mark.parametrize("rel,section,expected_count", _CONSUMER_ROSTER, ids=[f"{r}::{s}" for r, s, _ in _CONSUMER_ROSTER])
def test_negative_consumer_pointer_missing_in_section(rel, section, expected_count):
    mutated = _text_without_one_pointer_in_section(_read(rel), rel, section)
    with pytest.raises(AssertionError, match=_POINTER):
        _check_consumer_pointer_in_section(mutated, rel, section, expected_count)


def test_negative_section_span_rejects_pointer_in_following_section():
    """Mutant killed: widen _section_span boundary (level <= start_level -> level < start_level)."""
    synthetic = "\n".join([
        "## Section A",
        "no pointer in declared section",
        "## Section B",
        f"only here: {_POINTER}",
    ])
    with pytest.raises(
        AssertionError,
        match=r"synthetic\.md \(section ## Section A\): expected 'rubric/bite-proof\.md' count 1",
    ):
        _check_consumer_pointer_in_section(synthetic, "synthetic.md", "## Section A", 1)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_negative_home_heading_missing(heading):
    mutated = _text_without_heading(_read(_HOME), heading)
    with pytest.raises(AssertionError, match=heading):
        _check_home_heading(mutated, heading)


@pytest.mark.parametrize("row", _COPY_HOLDER_ROWS, ids=[row.get("id", row["home_clause"][:40]) for row in _COPY_HOLDER_ROWS])
def test_negative_clause_missing_from_copy_holder(row):
    mutated = without_clause_in_section(
        _read(row["copy_holder"]),
        row["copy_holder"],
        row["copy_holder_section"],
        _holder_clause(row),
    )
    with pytest.raises(AssertionError, match=re.escape(row["copy_holder_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == row["copy_holder"] else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=_ROW_IDS)
def test_negative_clause_missing_from_home_section(row):
    mutated = without_clause_in_section(
        _read(_HOME), _HOME, row["home_section"], row["home_clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["home_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == _HOME else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=_ROW_IDS)
def test_negative_clause_planted_elsewhere_in_home(row):
    mutated = plant_clause_elsewhere(
        _read(_HOME),
        _HOME,
        row["home_section"],
        "## When the proof runs under a normalization",
        row["home_clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["home_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == _HOME else _read(rel))


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


def test_negative_consumer_pointer_over_count_in_section():
    synthetic = "\n".join([
        "## Section A",
        f"{_POINTER} first pointer",
        f"and again: {_POINTER}",
    ])
    with pytest.raises(AssertionError, match=_POINTER):
        _check_consumer_pointer_in_section(synthetic, "synthetic.md", "## Section A", 1)


@pytest.mark.parametrize("row", _COPY_HOLDER_ROWS, ids=[row.get("id", row["home_clause"][:40]) for row in _COPY_HOLDER_ROWS])
def test_negative_clause_planted_elsewhere_in_copy_holder(row):
    target = _plant_target_section(row["copy_holder"], row["copy_holder_section"])
    mutated = plant_clause_elsewhere(
        _read(row["copy_holder"]),
        row["copy_holder"],
        row["copy_holder_section"],
        target,
        _holder_clause(row),
    )
    with pytest.raises(AssertionError, match=re.escape(row["copy_holder_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == row["copy_holder"] else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=_ROW_IDS)
def test_negative_clause_over_count_in_home(row):
    mutated = add_one_occurrence_in_section(
        _read(_HOME), _HOME, row["home_section"], row["home_clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["home_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == _HOME else _read(rel))


@pytest.mark.parametrize("row", _PARTIAL_DRIFT_ROWS, ids=[row["home_clause"] for row in _PARTIAL_DRIFT_ROWS])
def test_negative_clause_partial_drift_in_home(row):
    mutated = drop_one_occurrence_in_section(
        _read(_HOME), _HOME, row["home_section"], row["home_clause"],
    )
    with pytest.raises(AssertionError, match="expected count 2"):
        _check_clause_sync(row, lambda rel: mutated if rel == _HOME else _read(rel))
