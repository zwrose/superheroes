"""Drift guard for launch-doctrine Recovery (CONVENTIONS §11).

Guards the relation between ``rubric/launch-doctrine.md`` § Recovery — taking over a build that
stopped (authoritative home) and its two enumerated copy-holders:

- ``skills/showrunner/SKILL.md`` § ``## Your duties``
- ``skills/workhorse/SKILL.md`` § ``## 1. Intake — read the route and get the go-ahead``

Per §11.3 anti-tautology, each shared clause is first asserted in the home sub-section that owns
it before it is checked in the copy-holders — re-wording the home breaks CI here first.

Section extraction reuses ``_file_section`` and ``_normalized`` from ``test_charter_boundary_sync``;
that reader is deliberately **fence-blind** (fence-awareness was tried and reverted in PR #727).

**Limitations (residual blind spots):**

1. substring presence cannot detect a nearby contradicting exception ("unless …");
2. a clause is pinned to a section, not to a paragraph or sentence — same-section satisfaction
   from a different paragraph still passes;
3. the fence-blind reader's latent fail-open shape if a heading appears only inside a fenced
   example (all guarded files currently carry zero fence lines; see ``test_no_fence_lines``).
"""
import os
import re

import pytest

from test_charter_boundary_sync import _file_section, _normalized

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_HOME = "rubric/launch-doctrine.md"
_RECOVERY_HEADING = "## Recovery — taking over a build that stopped"

_SUBSECTION_HEADINGS = [
    "### Adopt; do not resume across instances or accounts",
    "### Sweep for unpushed work before adopting",
    "### Pin the transcript; never re-discover it",
    "### Read liveness from the right signals",
    "### Suspect quota before you suspect a defect",
]

_HOME_CLAUSES = {
    "### Adopt; do not resume across instances or accounts": [
        "only from the same config dir",
        "appends to its original transcript file",
        "the pushed branch at a named sha",
        "adoption is the only path",
        "claim inherited from the dead session is unverified until re-run",
    ],
    "### Sweep for unpushed work before adopting": [
        "never pushed",
        "integrated",
        "subsumed",
        "contested",
        "adoption that records no sweep is an adoption that has not looked",
    ],
    "### Pin the transcript; never re-discover it": [
        "first 4KB",
        "issue token",
        "pin that file path",
        "never re-discover",
        "a dead launch attempt leaves a stub",
    ],
    "### Read liveness from the right signals": [
        "double-confirmed",
        "mtime",
        "stdout log is not a liveness signal",
        "buffers its output to exit",
        "identify a worker by a global process match",
    ],
    "### Suspect quota before you suspect a defect": [
        "unexplained early exit",
        "the account the builder was burning",
        "not proof of deep headroom",
    ],
}

_COPY_HOLDER_SECTIONS = {
    "skills/showrunner/SKILL.md": "## Your duties",
    "skills/workhorse/SKILL.md": "## 1. Intake — read the route and get the go-ahead",
}

_COPY_HOLDER_CLAUSES = {
    "skills/showrunner/SKILL.md": [
        "rubric/launch-doctrine.md",
        "the branch and the sha it adopted",
        "the only path across instances or accounts",
        "suspected quota death",
        "adoption is a launch",
    ],
    "skills/workhorse/SKILL.md": [
        "rubric/launch-doctrine.md",
        "sweep for work the dead build never pushed",
        "integrated",
        "subsumed",
        "contested",
        "unverified until you re-run it yourself",
    ],
}

_FENCE_GUARDED_FILES = (
    _HOME,
    "skills/showrunner/SKILL.md",
    "skills/workhorse/SKILL.md",
)


def _read_plugin(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _heading_occurrences(rel, heading):
    """Count exact stripped-line matches for a heading; fail closed on zero or duplicate."""
    lines = _read_plugin(rel).splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    return indices


def _assert_heading_exactly_once(rel, heading):
    indices = _heading_occurrences(rel, heading)
    if len(indices) == 0:
        raise AssertionError(f"{rel}: heading {heading!r} not found")
    if len(indices) > 1:
        raise AssertionError(
            f"{rel}: heading {heading!r} appears {len(indices)} times"
        )


def _check_home_clauses(read_text=None):
    if read_text is None:
        read_text = _read_plugin
    for subsection, clauses in _HOME_CLAUSES.items():
        home_text = _file_section(_HOME, subsection, read_text)
        for clause in clauses:
            if clause not in home_text:
                raise AssertionError(
                    f"clause no longer appears in authoritative home "
                    f"({_HOME}, section {subsection}) — re-sync the table: {clause!r}"
                )


def _check_copy_holder_clauses(read_text=None):
    if read_text is None:
        read_text = _read_plugin
    for rel, section in _COPY_HOLDER_SECTIONS.items():
        copy_text = _file_section(rel, section, read_text)
        for clause in _COPY_HOLDER_CLAUSES[rel]:
            if clause not in copy_text:
                raise AssertionError(
                    f"clause missing from {rel} (section {section}) — "
                    f"re-sync against {_HOME}: {clause!r}"
                )


def test_recovery_heading_exactly_once_in_home():
    _assert_heading_exactly_once(_HOME, _RECOVERY_HEADING)


def test_recovery_subsection_headings_exactly_once_in_home():
    for heading in _SUBSECTION_HEADINGS:
        _assert_heading_exactly_once(_HOME, heading)


def test_recovery_clauses_present_in_home():
    _check_home_clauses()


def test_recovery_clauses_present_in_copy_holders():
    _check_copy_holder_clauses()


def test_copy_holder_table_names_exactly_two_charters():
    expected = frozenset({
        "skills/showrunner/SKILL.md",
        "skills/workhorse/SKILL.md",
    })
    actual = frozenset(_COPY_HOLDER_SECTIONS)
    assert actual == expected, (
        f"copy-holder table drift — expected {sorted(expected)!r}, got {sorted(actual)!r}"
    )


def test_no_fence_lines():
    # The section reader is fence-blind; all guarded files must carry zero ``` lines so
    # that premise stays true (see test_charter_boundary_sync blind spot 7).
    for rel in _FENCE_GUARDED_FILES:
        count = _read_plugin(rel).count("```")
        assert count == 0, f"{rel}: expected 0 triple-backtick lines, found {count}"


def test_negative_missing_recovery_heading_raises():
    def read_text(_rel):
        return "## Other section\nSome text.\n"

    with pytest.raises(RuntimeError, match="heading '## Recovery"):
        _file_section("synthetic.md", _RECOVERY_HEADING, read_text)


def test_negative_duplicate_recovery_heading_raises():
    def read_text(_rel):
        return "\n".join([
            _RECOVERY_HEADING,
            "First copy.",
            _RECOVERY_HEADING,
            "Second copy.",
        ])

    with pytest.raises(RuntimeError, match="appears 2 times"):
        _file_section("synthetic.md", _RECOVERY_HEADING, read_text)


def test_negative_home_clause_absent_from_section():
    synthetic_text = "\n".join([
        "### Adopt; do not resume across instances or accounts",
        "Content without the probe clause.",
        "## Appendix",
        "adoption is the only path — but only here.",
    ])

    def read_text(rel):
        if rel == _HOME:
            return synthetic_text
        return _read_plugin(rel)

    with pytest.raises(
        AssertionError,
        match=r"clause no longer appears in authoritative home",
    ):
        _check_home_clauses(read_text)


def test_negative_copy_holder_clause_missing_from_section():
    showrunner_path = "skills/showrunner/SKILL.md"
    synthetic_text = "\n".join([
        "## Your duties",
        "Other duties without recovery pointers.",
        "## When you're tempted",
        "adoption is a launch — but only outside declared section",
    ])

    def read_text(rel):
        if rel == showrunner_path:
            return synthetic_text
        return _read_plugin(rel)

    with pytest.raises(
        AssertionError,
        match=r"clause missing from .+ \(section ## Your duties\)",
    ):
        _check_copy_holder_clauses(read_text)
