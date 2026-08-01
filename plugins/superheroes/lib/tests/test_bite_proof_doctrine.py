"""Drift guard for the bite-proof doctrine one-home shape (CONVENTIONS §11, #765).

Bites on: a consumer section that stops pointing at ``rubric/bite-proof.md``, load-bearing clauses
restated in copy-holders, and a home heading that is renamed or removed. Does **not** prove the
doctrine's prose is correct, that anyone obeys it, or that a bite-proof was recorded. Heading order
is deliberately unguarded — no consumer cites relative order. The consumer-pointer roster is
hand-maintained (§11.2 caveat).
"""
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO_ROOT = os.path.abspath(os.path.join(PLUGIN, "..", ".."))

_POINTER = "rubric/bite-proof.md"
_HOME = "rubric/bite-proof.md"

# Copy-holder disposition (§11.2 — extend roster when adding a pointer):
# workhorse §8 Verify — orchestrator re-reads doctrine when build adds detector
# workhorse § When you're tempted — temptation table row on vacuous bite-proofs
# implementer § The rules — disclosure shapes and doctrine reference in short-return rule
# implementer § Validating — validity rule 6 names expected bite-proof
# test-reviewer § Named test-smell taxonomy — axis-line smell cites doctrine home
# CONVENTIONS §12 — verification contracts pointer to vacuity-trap home
_CONSUMER_ROSTER = [
    ("skills/workhorse/SKILL.md", "## 8. Verify — re-run every receipt yourself"),
    ("skills/workhorse/SKILL.md", "## When you're tempted"),
    ("agents/implementer.md", "## The rules"),
    ("agents/implementer.md", "## Validating your work order"),
    ("agents/test-reviewer.md", "## Named test-smell taxonomy"),
    ("../../CONVENTIONS.md", "## 12. Verification contracts (fix-ships-its-detector, real-seam tests)"),
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
    },
    {
        "clause": "Unprovable as placed",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/implementer.md",
    },
    {
        "clause": "Unreachable through this entry point",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/implementer.md",
    },
    {
        "clause": "Unrunnable here",
        "home_section": "## When the proof cannot be produced",
        "copy_holder": "agents/implementer.md",
    },
]

_POINTER_ROSTER_EXCLUDED = frozenset({_HOME})  # home prose names filename, not consumer pointer


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


def _clause_regex(clause):
    return re.compile(r"\s+".join(re.escape(part) for part in clause.split()))


def _check_consumer_pointer_in_section(text, rel, section_heading):
    if _POINTER not in _file_section(rel, section_heading, lambda _rel: text):
        raise AssertionError(
            f"{rel} (section {section_heading}): missing pointer {_POINTER!r} — re-add it "
            "or update test_bite_proof_doctrine.py"
        )


def _check_home_heading(text, heading):
    if heading not in text.splitlines():
        raise AssertionError(
            f"{_HOME}: heading {heading!r} missing — re-add or update test_bite_proof_doctrine.py"
        )


def _check_clause_sync(row, read_text=None):
    if read_text is None:
        read_text = _read
    clause, home_section, copy_holder = row["clause"], row["home_section"], row["copy_holder"]
    if clause not in _file_section(_HOME, home_section, read_text):
        raise AssertionError(
            f"{_HOME} (section {home_section}): clause missing — re-sync: {clause!r}"
        )
    if clause not in _normalized(read_text(copy_holder)):
        raise AssertionError(f"{copy_holder}: clause missing — re-sync from {_HOME}: {clause!r}")


def _text_without_pointer_in_section(text, rel, section_heading):
    lines = text.splitlines()
    start, end = _section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    count = section_text.count(_POINTER)
    assert count >= 1, (
        f"mutation setup: {_POINTER!r} missing in {rel} section {section_heading!r} (count={count})"
    )
    new_section = section_text.replace(_POINTER, "rubric/bite-proof-DRIFT.md")
    assert _POINTER not in new_section
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


def _walk_pointer_carrying_md_files():
    found = set()
    for root, _dirs, files in os.walk(PLUGIN):
        for name in files:
            if name.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, name), PLUGIN)
                if _POINTER in _read(rel):
                    found.add(rel)
    with open(os.path.join(REPO_ROOT, "CONVENTIONS.md"), encoding="utf-8") as fh:
        if _POINTER in fh.read():
            found.add("../../CONVENTIONS.md")
    return found


def _check_pointer_roster_complete(found_files):
    roster_files = frozenset(rel for rel, _ in _CONSUMER_ROSTER)
    expected = found_files - _POINTER_ROSTER_EXCLUDED
    if expected != roster_files:
        missing, extra = sorted(roster_files - expected), sorted(expected - roster_files)
        raise AssertionError(
            f"pointer roster drift: missing={missing!r}, unrostered={extra!r} — extend roster"
        )


@pytest.mark.parametrize("rel,section", _CONSUMER_ROSTER, ids=[f"{r}::{s}" for r, s in _CONSUMER_ROSTER])
def test_consumer_section_points_at_bite_proof_home(rel, section):
    _check_consumer_pointer_in_section(_read(rel), rel, section)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_home_has_heading(heading):
    _check_home_heading(_read(_HOME), heading)


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_clause_present_in_home_and_copy_holder(row):
    _check_clause_sync(row)


def test_pointer_roster_is_complete():
    _check_pointer_roster_complete(_walk_pointer_carrying_md_files())


@pytest.mark.parametrize("rel,section", _CONSUMER_ROSTER, ids=[f"{r}::{s}" for r, s in _CONSUMER_ROSTER])
def test_negative_consumer_pointer_missing_in_section(rel, section):
    mutated = _text_without_pointer_in_section(_read(rel), rel, section)
    with pytest.raises(AssertionError, match=_POINTER):
        _check_consumer_pointer_in_section(mutated, rel, section)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_negative_home_heading_missing(heading):
    mutated = _text_without_heading(_read(_HOME), heading)
    with pytest.raises(AssertionError, match=heading):
        _check_home_heading(mutated, heading)


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_negative_clause_missing_from_copy_holder(row):
    mutated = _remove_clause(_read(row["copy_holder"]), row["clause"], row["copy_holder"])
    with pytest.raises(AssertionError, match=re.escape(row["clause"])):
        _check_clause_sync(row, lambda rel: mutated if rel == row["copy_holder"] else _read(rel))


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_negative_clause_missing_from_home_section(row):
    mutated = _text_without_clause_in_section(
        _read(_HOME), _HOME, row["home_section"], row["clause"],
    )
    with pytest.raises(AssertionError, match=re.escape(row["clause"])):
        _check_clause_sync(row, lambda rel: mutated if rel == _HOME else _read(rel))


def test_negative_pointer_roster_unrostered_file():
    roster = frozenset(rel for rel, _ in _CONSUMER_ROSTER)
    with pytest.raises(AssertionError, match="unrostered"):
        _check_pointer_roster_complete(roster | {"synthetic/unrostered.md"})
