"""Drift guard for the cross-charter boundary line (CONVENTIONS §11).

The ratified charter design states the same boundary in BOTH the showrunner and workhorse
SKILL.md — the two-sided fact "Workhorse never merges/releases/bumps versions/wires the board/
re-scopes silently; Showrunner never builds." Two hand-maintained copies can silently disagree, so
this test extracts the boundary line from each charter, **fails closed** if either is missing, and
asserts the two are byte-identical — editing one charter's boundary breaks CI until both match.

There is no third "home" to point at: neither charter is authoritative over the other, so the guard
is a symmetric equality between the two live copies (§11.3 — the assertion's right-hand side is the
other file's line, not a hand-typed literal).

This file also guards **asymmetric** rubric→charters cross-lane invariants as **clause-presence**
sentinels anchored to ``rubric/review-discipline.md``. The charters deliberately paraphrase for
their audience; a byte-equality assertion would fail today, so each row asserts that load-bearing
clauses appear in the copy-holder's normalized text — presence, not equality.

Per §11.3 anti-tautology: clause strings are hand-typed, so each is first asserted against the
authoritative home before it is used as the right-hand side for the copies — re-wording the home
breaks CI.

**Limitation:** this guard catches a load-bearing clause being deleted or reworded in a copy. It
does **not** catch the home gaining a new qualifier, scope, or exception that the copies fail to
mirror.

Copy-holder disposition (§11.2 caveat — adding a copy means extending the table):

- **``rubric/review-discipline.md``** — authoritative home for the cross-lane invariants.
- **``skills/showrunner/SKILL.md``** — all three invariant rows.
- **``skills/workhorse/SKILL.md``** — resolve-upward and not-engaged-never-passes only; deliberately
  excluded from the waiver-bounds row because micro is the showrunner's lane, not an oversight.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILLS = os.path.join(_PLUGIN_ROOT, "skills")
_HOME = "rubric/review-discipline.md"
_MARKER = "**The boundary (both charters state it):**"

_INVARIANT_TABLE = [
    {
        "name": "resolve-upward",
        "home_sections": ["### The spine"],
        "clauses": [
            "Default to the full lane; anything unclear resolves upward",
            "moving down a lane is never",
            "it requires the owner, per change",
            "Disclosure alone never authorizes a downgrade",
            "the full lane at any size",
        ],
        "copy_holders": [
            "skills/showrunner/SKILL.md",
            "skills/workhorse/SKILL.md",
        ],
    },
    {
        "name": "not-engaged-never-passes",
        "home_sections": ["### What never changes in any lane"],
        "clauses": [
            "means that review did not happen",
            "re-dispatch once",
            "never a pass",
            "zero is not evidence of engagement",
            "resolve upward to the full lane or park",
        ],
        "copy_holders": [
            "skills/showrunner/SKILL.md",
            "skills/workhorse/SKILL.md",
        ],
    },
    {
        "name": "waiver-bounds",
        "home_sections": ["### The spine", "### Micro — owner authorization"],
        "clauses": [
            "owner-only, per change, never a standing grant",
            "quiet-failure question",
            "risk stated",
            "single named exception",
        ],
        "copy_holders": [
            "skills/showrunner/SKILL.md",
        ],
    },
]


def _read_plugin(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalized(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    if not match:
        return None
    return len(match.group(1))


def _home_section(heading):
    text = _read_plugin(_HOME)
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) == 0:
        raise RuntimeError(f"{_HOME}: heading {heading!r} not found")
    if len(indices) > 1:
        raise RuntimeError(
            f"{_HOME}: heading {heading!r} appears {len(indices)} times"
        )
    start = indices[0]
    start_level = _heading_level(lines[start])
    end = len(lines)
    for i in range(start + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= start_level:
            end = i
            break
    return _normalized("\n".join(lines[start:end]))


def _home_union(sections):
    return " ".join(_home_section(heading) for heading in sections)


def _validate_invariant_table():
    if not _INVARIANT_TABLE:
        raise RuntimeError("INVARIANT_TABLE is empty")
    for row in _INVARIANT_TABLE:
        if not row.get("home_sections"):
            raise RuntimeError(
                f"INVARIANT_TABLE row {row.get('name', '?')!r}: "
                "home_sections must be non-empty"
            )
        if not row.get("clauses"):
            raise RuntimeError(
                f"INVARIANT_TABLE row {row.get('name', '?')!r}: "
                "clauses must be non-empty"
            )
        if not row.get("copy_holders"):
            raise RuntimeError(
                f"INVARIANT_TABLE row {row.get('name', '?')!r}: "
                "copy_holders must be non-empty"
            )
        for clause in row["clauses"]:
            if not clause or not clause.strip():
                raise RuntimeError(
                    f"INVARIANT_TABLE row {row['name']!r}: "
                    "clause must be non-empty and non-whitespace-only"
                )


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


def test_invariant_clauses_present_in_home():
    _validate_invariant_table()
    for row in _INVARIANT_TABLE:
        home_text = _home_union(row["home_sections"])
        sections = ", ".join(row["home_sections"])
        for clause in row["clauses"]:
            assert clause in home_text, (
                f"INVARIANT_TABLE row {row['name']!r}: clause no longer appears in "
                f"authoritative home ({_HOME}, sections {sections}) — re-sync the table: "
                f"{clause!r}"
            )


def test_invariant_clauses_present_in_copy_holders():
    _validate_invariant_table()
    for row in _INVARIANT_TABLE:
        for rel in row["copy_holders"]:
            copy_text = _normalized(_read_plugin(rel))
            for clause in row["clauses"]:
                assert clause in copy_text, (
                    f"INVARIANT_TABLE row {row['name']!r}: clause missing from {rel} — "
                    f"re-sync against {_HOME}: {clause!r}"
                )


def test_invariant_table_is_well_formed():
    _validate_invariant_table()
