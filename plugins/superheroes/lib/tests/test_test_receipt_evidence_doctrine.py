"""Drift guard for the test-receipt evidence doctrine one-home shape (CONVENTIONS §11).

Bites on: each rostered consumer section and its ``rubric/test-receipt-evidence.md`` pointer count;
the named clauses in their named home; and the home's headings.
"""
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

_POINTER = "rubric/test-receipt-evidence.md"
_HOME = "rubric/test-receipt-evidence.md"

_CONSUMER_ROSTER = [
    ("agents/grounding-seat.md", "## What you check (self-claims → repo)", 1),
    ("skills/review-code/SKILL.md", "## The verify command", 1),
]

# setup.md's verify pointer sits below comment lines that look like level-1 headings to
# _section_span — whole-file count is the honest pin for that consumer.
_WHOLE_FILE_CONSUMERS = [
    ("skills/review-code/reference/setup.md", 1),
]

_HEADINGS = [
    "## Verify receipt is not a test receipt",
    "## What does ground a test-pass claim",
]

_CLAUSE_ROWS = [
    {
        "clause": "does not ground a claim that tests passed",
        "home_section": "## Verify receipt is not a test receipt",
    },
    {
        "clause": "build's ordered suite run",
        "home_section": "## What does ground a test-pass claim",
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


def _file_section(rel, heading):
    lines = _read(rel).splitlines()
    start, end = _section_span(lines, heading, rel)
    return "\n".join(lines[start:end])


def _pointer_count_in_section(text, rel, section_heading):
    lines = text.splitlines()
    start, end = _section_span(lines, section_heading, rel)
    return "\n".join(lines[start:end]).count(_POINTER)


def _check_consumer_pointer_in_section(text, rel, section_heading, expected_count):
    actual = _pointer_count_in_section(text, rel, section_heading)
    if actual != expected_count:
        raise AssertionError(
            f"{rel} (section {section_heading}): expected {_POINTER!r} count {expected_count}, "
            f"found {actual} — re-add pointer(s) or update test_test_receipt_evidence_doctrine.py"
        )


def _check_home_heading(text, heading):
    if heading not in text.splitlines():
        raise AssertionError(
            f"{_HOME}: heading {heading!r} missing — re-add or update test_test_receipt_evidence_doctrine.py"
        )


@pytest.mark.parametrize("rel,section,expected_count", _CONSUMER_ROSTER, ids=[f"{r}::{s}" for r, s, _ in _CONSUMER_ROSTER])
def test_consumer_section_points_at_test_receipt_evidence_home(rel, section, expected_count):
    _check_consumer_pointer_in_section(_read(rel), rel, section, expected_count)


@pytest.mark.parametrize("rel,expected_count", _WHOLE_FILE_CONSUMERS)
def test_whole_file_consumer_points_at_test_receipt_evidence_home(rel, expected_count):
    actual = _read(rel).count(_POINTER)
    if actual != expected_count:
        raise AssertionError(
            f"{rel}: expected {_POINTER!r} count {expected_count}, found {actual}"
        )


@pytest.mark.parametrize("heading", _HEADINGS)
def test_home_has_heading(heading):
    _check_home_heading(_read(_HOME), heading)


@pytest.mark.parametrize("row", _CLAUSE_ROWS, ids=[r["clause"] for r in _CLAUSE_ROWS])
def test_clause_present_in_home(row):
    section = _normalized(_file_section(_HOME, row["home_section"]))
    if row["clause"] not in section:
        raise AssertionError(
            f"{_HOME} (section {row['home_section']}): clause missing — re-sync: {row['clause']!r}"
        )
