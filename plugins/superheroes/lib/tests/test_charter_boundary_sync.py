"""Drift guard for the cross-charter boundary line (CONVENTIONS §11).

The ratified charter design states the same boundary in BOTH the showrunner and workhorse
SKILL.md — the two-sided fact "Workhorse never merges/releases/bumps versions/wires the board/
re-scopes silently; Showrunner never builds." Two hand-maintained copies can silently disagree, so
this test extracts the boundary line from each charter, **fails closed** if either is missing, and
asserts the two are byte-identical — editing one charter's boundary breaks CI until both match.

There is no third "home" to point at: neither charter is authoritative over the other, so the guard
is a symmetric equality between the two live copies (§11.3 — the assertion's right-hand side is the
other file's line, not a hand-typed literal).
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILLS = os.path.normpath(os.path.join(_HERE, "..", "..", "skills"))
_MARKER = "**The boundary (both charters state it):**"


def _boundary_line(skill):
    path = os.path.join(_SKILLS, skill, "SKILL.md")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if _MARKER in line:
                return line.strip()
    raise RuntimeError(f"{skill}/SKILL.md: boundary line ({_MARKER!r}) not found")


def test_boundary_line_is_identical_in_both_charters():
    showrunner = _boundary_line("showrunner")
    workhorse = _boundary_line("workhorse")
    assert showrunner == workhorse, (
        "The boundary line differs between the showrunner and workhorse charters — "
        f"re-sync them.\n  showrunner: {showrunner}\n  workhorse:  {workhorse}"
    )
