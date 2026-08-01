"""Drift guard for the bite-proof doctrine one-home shape (CONVENTIONS §11, #765).

Bites on: a consumer that stops pointing at ``rubric/bite-proof.md``, and a home heading that is
renamed, removed, or reordered. Does **not** prove the doctrine's prose is correct, that anyone
obeys it, or that a bite-proof was actually recorded for any given change.
"""
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

_POINTER = "rubric/bite-proof.md"
_HOME = "rubric/bite-proof.md"

_CONSUMER_PATHS = [
    "skills/workhorse/SKILL.md",
    "agents/implementer.md",
    "agents/test-reviewer.md",
    "../../CONVENTIONS.md",
]

_HEADINGS = [
    "## The obligation",
    "## Four ways a bite-proof is vacuous",
    "## The record",
    "## When the proof cannot be produced",
    "## When the proof runs under a normalization",
    "## Who owes what",
]


def _read(rel):
    with open(os.path.normpath(os.path.join(PLUGIN, rel)), encoding="utf-8") as fh:
        return fh.read()


def _check_consumer_pointer(text, rel):
    if _POINTER not in text:
        raise AssertionError(
            f"{rel}: missing pointer {_POINTER!r} — re-add the pointer to the bite-proof home, "
            "or update test_bite_proof_doctrine.py if the path was deliberately changed"
        )


def _check_home_heading(text, heading):
    if heading not in text.splitlines():
        raise AssertionError(
            f"{_HOME}: heading {heading!r} missing as its own ## line — re-add it or update "
            "test_bite_proof_doctrine.py if deliberately renamed"
        )


def _check_home_heading_order(text):
    lines = text.splitlines()
    positions = []
    for heading in _HEADINGS:
        if heading not in lines:
            raise AssertionError(
                f"{_HOME}: cannot verify heading order — {heading!r} missing; re-add it or "
                "update test_bite_proof_doctrine.py if deliberately renamed"
            )
        positions.append(lines.index(heading))
    for i in range(len(_HEADINGS) - 1):
        if positions[i] >= positions[i + 1]:
            raise AssertionError(
                f"{_HOME}: {_HEADINGS[i]!r} must appear before {_HEADINGS[i + 1]!r} but is out "
                "of order — fix heading order or update test_bite_proof_doctrine.py"
            )


def _text_without_pointer(text, rel):
    count = text.count(_POINTER)
    assert count >= 1, (
        f"mutation setup: {_POINTER!r} not found in {rel} (count={count})"
    )
    mutated = text.replace(_POINTER, "rubric/bite-proof-DRIFT.md")
    assert _POINTER not in mutated, (
        f"mutation setup: {_POINTER!r} still present in mutated {rel}"
    )
    assert mutated != text, f"mutation setup: pointer removal left {rel} unchanged"
    return mutated


def _text_without_heading(text, heading):
    lines = text.splitlines()
    count = sum(1 for line in lines if line == heading)
    assert count == 1, (
        f"mutation setup: expected exactly one {heading!r} line in {_HOME}, found {count}"
    )
    mutated = "\n".join(line for line in lines if line != heading)
    if text.endswith("\n"):
        mutated += "\n"
    assert mutated != text, f"mutation setup: heading removal left {_HOME} unchanged"
    return mutated


@pytest.mark.parametrize("rel", _CONSUMER_PATHS, ids=_CONSUMER_PATHS)
def test_consumer_points_at_bite_proof_home(rel):
    _check_consumer_pointer(_read(rel), rel)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_home_has_heading(heading):
    _check_home_heading(_read(_HOME), heading)


def test_home_headings_in_cited_order():
    _check_home_heading_order(_read(_HOME))


@pytest.mark.parametrize("rel", _CONSUMER_PATHS, ids=_CONSUMER_PATHS)
def test_negative_consumer_pointer_missing(rel):
    original = _read(rel)
    mutated = _text_without_pointer(original, rel)
    with pytest.raises(AssertionError, match=_POINTER):
        _check_consumer_pointer(mutated, rel)


@pytest.mark.parametrize("heading", _HEADINGS)
def test_negative_home_heading_missing(heading):
    original = _read(_HOME)
    mutated = _text_without_heading(original, heading)
    with pytest.raises(AssertionError, match=heading):
        _check_home_heading(mutated, heading)
