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
    norm = os.path.normpath(rel)
    if norm in {os.path.normpath(name) for name in _CENSUS_EXCLUDED_FILES}:
        return True
    return any(
        norm.startswith(os.path.normpath(d) + os.sep) for d in _CENSUS_EXCLUDED_DIRS
    )


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
        "clause": (
            "the guarded element, the neutralization to apply, and the detector expected to go red"
        ),
        "home_section": "## Who owes what",
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## Validating your work order",
    },
    {
        "clause": "Unprovable as placed",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
    },
    {
        "clause": "Unreachable through this entry point",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
    },
    {
        "clause": "Unrunnable here",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
    },
    {
        "clause": "32 KiB",
        "home_section": "## The record",
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
    },
    {
        "clause": "128 KiB",
        "home_section": "## The record",
        "copy_holder": "agents/implementer.md",
        "copy_holder_section": "## The rules",
    },
    {
        "clause": "names the bite-proof it expects",
        "home_section": "## Who owes what",
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## 6. Decompose into work orders",
    },
    {
        "clause": "per guarded element",
        "home_section": "## The record",
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## 8. Verify — re-run every receipt yourself",
    },
    {
        "clause": "A green run is equally consistent with",
        "home_section": "## The obligation",
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## When you're tempted",
    },
    {
        "clause": "with the detector unedited",
        "home_section": "## The record",
        "copy_holder": "skills/workhorse/SKILL.md",
        "copy_holder_section": "## When you're tempted",
    },
    {
        "clause": "through the path the test uses",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/test-reviewer.md",
        "copy_holder_section": "## What to Flag",
    },
    {
        "clause": "owed disclosure",
        "home_section": "## Who owes what",
        "copy_holder": "agents/test-reviewer.md",
        "copy_holder_section": "## Named test-smell taxonomy",
    },
]



def _read(rel):
    with open(os.path.normpath(os.path.join(PLUGIN, rel)), encoding="utf-8") as fh:
        return fh.read()


def _normalized(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    return len(match.group(1)) if match else None


def _section_span(lines, heading, label):
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) != 1:
        raise RuntimeError(f"{label}: expected exactly one {heading!r} line, found {len(indices)}")
    start = indices[0]
    start_level = _heading_level(lines[start])
    end = len(lines)
    for i in range(start + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= start_level:
            end = i
            break
    return start, end


def _file_section(rel, heading, read_text=None):
    if read_text is None:
        read_text = _read
    lines = read_text(rel).splitlines()
    start, end = _section_span(lines, heading, rel)
    return _normalized("\n".join(lines[start:end]))


def _pointer_count_in_section(text, rel, section_heading):
    lines = text.splitlines()
    start, end = _section_span(lines, section_heading, rel)
    return "\n".join(lines[start:end]).count(_POINTER)


def _clause_regex(clause):
    return re.compile(r"\s+".join(re.escape(part) for part in clause.split()))


def _check_consumer_pointer_in_section(text, rel, section_heading, expected_count):
    actual = _pointer_count_in_section(text, rel, section_heading)
    if actual != expected_count:
        raise AssertionError(
            f"{rel} (section {section_heading}): expected {_POINTER!r} count {expected_count}, "
            f"found {actual} — re-add pointer(s) or update test_bite_proof_doctrine.py roster"
        )


def _check_home_heading(text, heading):
    if heading not in text.splitlines():
        raise AssertionError(
            f"{_HOME}: heading {heading!r} missing — re-add or update test_bite_proof_doctrine.py"
        )


def _check_clause_sync(row, read_text=None):
    if read_text is None:
        read_text = _read
    clause = row["clause"]
    home_section = row["home_section"]
    copy_holder = row["copy_holder"]
    copy_holder_section = row["copy_holder_section"]
    if clause not in _file_section(_HOME, home_section, read_text):
        raise AssertionError(
            f"{_HOME} (section {home_section}): clause missing — re-sync: {clause!r}"
        )
    if clause not in _file_section(copy_holder, copy_holder_section, read_text):
        raise AssertionError(
            f"{copy_holder} (section {copy_holder_section}): clause missing — "
            f"re-sync from {_HOME}: {clause!r}"
        )


def _text_without_one_pointer_in_section(text, rel, section_heading):
    lines = text.splitlines()
    start, end = _section_span(lines, section_heading, rel)
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


def _remove_clause(text, clause, label):
    pattern = _clause_regex(clause)
    matches = list(pattern.finditer(text))
    assert matches, f"mutation setup: clause {clause!r} not found in {label}"
    mutated = pattern.sub("", text, count=len(matches))
    assert not pattern.search(mutated), f"mutation setup: clause still in mutated {label}"
    assert mutated != text
    return mutated


def _text_without_clause_in_section(text, rel, section_heading, clause):
    lines = text.splitlines()
    start, end = _section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    new_section = _remove_clause(section_text, clause, f"{rel} section {section_heading!r}")
    new_lines = lines[:start] + new_section.splitlines() + lines[end:]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")


def _plant_clause_elsewhere_in_home(text, home_section, clause, plant_section):
    without = _text_without_clause_in_section(text, _HOME, home_section, clause)
    lines = without.splitlines()
    start, end = _section_span(lines, plant_section, _HOME)
    planted_line = f"{clause} — planted outside {home_section}."
    new_lines = lines[: start + 1] + [planted_line] + lines[start + 1 :]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")


def _sections_with_pointer(rel, text):
    if _POINTER not in text:
        return set()
    lines = text.splitlines()
    found = set()
    for line in lines:
        heading = line.strip()
        if _heading_level(line) != 2:
            continue
        start, end = _section_span(lines, heading, rel)
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
            with open(os.path.join(plugin_root, rel), encoding="utf-8") as fh:
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


# --- _section_span direct tests (synthetic in-memory documents) ---


def test_section_span_includes_deeper_subheading():
    lines = "\n".join([
        "## Parent",
        "parent body",
        "### Child",
        "child body",
        "## Sibling",
    ]).splitlines()
    start, end = _section_span(lines, "## Parent", "synthetic")
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
    start, end = _section_span(lines, "## First", "synthetic")
    assert lines[end] == "## Second"
    assert "first body" in "\n".join(lines[start:end])
    assert "second body" not in "\n".join(lines[start:end])


def test_section_span_zero_headings_raises():
    lines = ["## Other", "text"]
    with pytest.raises(RuntimeError, match="expected exactly one '## Missing'"):
        _section_span(lines, "## Missing", "synthetic")


def test_section_span_duplicate_headings_raises():
    lines = "\n".join(["## Dup", "a", "## Dup", "b"]).splitlines()
    with pytest.raises(RuntimeError, match="expected exactly one '## Dup'"):
        _section_span(lines, "## Dup", "synthetic")


@pytest.mark.parametrize("rel,section,expected_count", _CONSUMER_ROSTER, ids=[f"{r}::{s}" for r, s, _ in _CONSUMER_ROSTER])
def test_consumer_section_points_at_bite_proof_home(rel, section, expected_count):
    _check_consumer_pointer_in_section(_read(rel), rel, section, expected_count)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_home_has_heading(heading):
    _check_home_heading(_read(_HOME), heading)


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
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


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_negative_clause_missing_from_copy_holder(row):
    lines = _read(row["copy_holder"]).splitlines()
    start, end = _section_span(lines, row["copy_holder_section"], row["copy_holder"])
    section_text = "\n".join(lines[start:end])
    mutated_section = _remove_clause(section_text, row["clause"], row["copy_holder_section"])
    new_lines = lines[:start] + mutated_section.splitlines() + lines[end:]
    mutated = "\n".join(new_lines) + ("\n" if _read(row["copy_holder"]).endswith("\n") else "")
    with pytest.raises(AssertionError, match=re.escape(row["copy_holder_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == row["copy_holder"] else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_negative_clause_missing_from_home_section(row):
    mutated = _text_without_clause_in_section(
        _read(_HOME), _HOME, row["home_section"], row["clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["home_section"])):
        _check_clause_sync(row, lambda rel: mutated if rel == _HOME else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_negative_clause_planted_elsewhere_in_home(row):
    mutated = _plant_clause_elsewhere_in_home(
        _read(_HOME), row["home_section"], row["clause"], "## When the proof runs under a normalization",
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


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_negative_clause_planted_elsewhere_in_copy_holder(row):
    plant_section = (
        "## The rules" if row["copy_holder_section"] != "## The rules" else "## Validating your work order"
    )
    synthetic_text = "\n".join([
        row["copy_holder_section"],
        "Section body without the clause.",
        plant_section,
        f"{row['clause']} — planted outside {row['copy_holder_section']}.",
    ])
    read_text = lambda rel: synthetic_text if rel == row["copy_holder"] else _read(rel)
    with pytest.raises(AssertionError, match=re.escape(row["copy_holder_section"])):
        _check_clause_sync(row, read_text)
