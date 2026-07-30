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
clauses appear in the copy-holder's declared section(s) — presence, not equality.

Per §11.3 anti-tautology: shared clause strings are hand-typed, so each is first asserted against
the authoritative home before it is used as the right-hand side for the copies — re-wording the
home breaks CI. ``holder_clauses`` are exempt from the home check by construction: they are
holder-specific pins using that file's own wording where the home states the same bound in
different words — a deliberate, narrower guarantee than the home-verified shared clauses.

**Limitations (residual blind spots):**

1. the home gaining a new qualifier / scope / exception that the copies do not mirror;
2. a copy that keeps every clause verbatim while adding a contradicting exception nearby
   (substring presence cannot detect an added "unless …");
3. matches that span a boundary after ``*``-stripping and whitespace collapse;
4. ``holder_clauses`` being holder-specific, not home-derived.

Copy-holder disposition (§11.2 caveat — adding a copy means extending the table):

- **``rubric/review-discipline.md``** — authoritative home for the cross-lane invariants.
- **``skills/showrunner/SKILL.md``** — all three invariant rows.
- **``skills/workhorse/SKILL.md``** — resolve-upward and not-engaged-never-passes only; deliberately
  excluded from the waiver-bounds row because micro is the showrunner's lane, not an oversight.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILLS = os.path.join(_PLUGIN_ROOT, "skills")
_HOME = "rubric/review-discipline.md"
_MARKER = "**The boundary (both charters state it):**"

_EXPECTED_INVARIANT_NAMES = frozenset({
    "resolve-upward",
    "not-engaged-never-passes",
    "waiver-bounds",
})

_EXPECTED_COPY_HOLDERS = {
    "resolve-upward": frozenset({
        "skills/showrunner/SKILL.md",
        "skills/workhorse/SKILL.md",
    }),
    "not-engaged-never-passes": frozenset({
        "skills/showrunner/SKILL.md",
        "skills/workhorse/SKILL.md",
    }),
    "waiver-bounds": frozenset({
        "skills/showrunner/SKILL.md",
    }),
}

_EXPECTED_SHARED_CLAUSE_COUNTS = {
    "resolve-upward": 5,
    "not-engaged-never-passes": 5,
    "waiver-bounds": 3,
}

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
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": ["## Your duties"],
            "skills/workhorse/SKILL.md": ["## Build lanes"],
        },
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
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": ["## Your duties"],
            "skills/workhorse/SKILL.md": ["## Build lanes"],
        },
    },
    {
        "name": "waiver-bounds",
        "home_sections": ["### The spine", "### Micro — owner authorization"],
        "clauses": [
            "owner-only, per change, never a standing grant",
            "quiet-failure question",
            "single named exception",
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": ["## Micro — hard-line edit"],
        },
        "holder_clauses": {
            "skills/showrunner/SKILL.md": [
                "owner-only, per change, never a standing grant; "
                "the risk must be stated explicitly",
            ],
        },
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


def _file_section(rel, heading, read_text=None):
    """Extract a named section from any plugin file.

    Exact stripped-line heading match; section runs to the next heading of same-or-higher
    level. Raises if the heading is absent or appears more than once.
    """
    if read_text is None:
        read_text = _read_plugin
    text = read_text(rel)
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) == 0:
        raise RuntimeError(f"{rel}: heading {heading!r} not found")
    if len(indices) > 1:
        raise RuntimeError(
            f"{rel}: heading {heading!r} appears {len(indices)} times"
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


def _section_union(rel, headings, read_text=None):
    return " ".join(_file_section(rel, heading, read_text) for heading in headings)


def _validate_invariant_table(table=None):
    if table is None:
        table = _INVARIANT_TABLE
    if not table:
        raise RuntimeError("INVARIANT_TABLE is empty")

    names = [row.get("name") for row in table]
    if any(not name or not str(name).strip() for name in names):
        raise RuntimeError("INVARIANT_TABLE: invariant name must be non-empty")
    if len(names) != len(set(names)):
        raise RuntimeError("INVARIANT_TABLE: duplicate invariant name")

    actual_names = frozenset(names)
    if actual_names != _EXPECTED_INVARIANT_NAMES:
        missing = _EXPECTED_INVARIANT_NAMES - actual_names
        extra = actual_names - _EXPECTED_INVARIANT_NAMES
        raise RuntimeError(
            "INVARIANT_TABLE roster drift: "
            f"missing={sorted(missing)!r}, extra={sorted(extra)!r}"
        )

    for row in table:
        name = row["name"]
        if not row.get("home_sections"):
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: home_sections must be non-empty"
            )
        if not row.get("clauses"):
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: clauses must be non-empty"
            )
        if not row.get("copy_holder_sections"):
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: "
                "copy_holder_sections must be non-empty"
            )

        expected_holders = _EXPECTED_COPY_HOLDERS.get(name)
        if expected_holders is None:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: unexpected invariant name"
            )
        actual_holders = frozenset(row["copy_holder_sections"])
        if _HOME in actual_holders:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: home must not appear as a copy-holder"
            )
        if actual_holders != expected_holders:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: copy-holder set drift — "
                f"expected {sorted(expected_holders)!r}, "
                f"got {sorted(actual_holders)!r}"
            )

        expected_count = _EXPECTED_SHARED_CLAUSE_COUNTS.get(name)
        if expected_count is None:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: unexpected invariant name"
            )
        if len(row["clauses"]) != expected_count:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: shared-clause count drift — "
                f"expected {expected_count}, got {len(row['clauses'])}"
            )

        for clause in row["clauses"]:
            if not clause or not clause.strip():
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    "clause must be non-empty and non-whitespace-only"
                )
        if len(row["clauses"]) != len(set(row["clauses"])):
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: duplicate shared clause"
            )

        holder_clauses = row.get("holder_clauses") or {}
        for rel, clauses in holder_clauses.items():
            if rel not in row["copy_holder_sections"]:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: holder_clauses key {rel!r} "
                    "is not a declared copy-holder"
                )
            if not clauses:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"holder_clauses[{rel!r}] must be non-empty"
                )
            for clause in clauses:
                if not clause or not clause.strip():
                    raise RuntimeError(
                        f"INVARIANT_TABLE row {name!r}: "
                        "holder clause must be non-empty and non-whitespace-only"
                    )
            if len(clauses) != len(set(clauses)):
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"duplicate holder clause for {rel!r}"
                )

        for rel, sections in row["copy_holder_sections"].items():
            if not sections:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"sections for {rel!r} must be non-empty"
                )
            if len(sections) != len(set(sections)):
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"duplicate section for {rel!r}"
                )


def _check_home_clauses(table, read_text=None):
    """Assert shared clauses appear in the home sections.

    holder_clauses are intentionally exempt — they pin holder-specific wording, not
    home-derived shared clauses.
    """
    if read_text is None:
        read_text = _read_plugin
    for row in table:
        home_text = _section_union(_HOME, row["home_sections"], read_text)
        sections = ", ".join(row["home_sections"])
        for clause in row["clauses"]:
            if clause not in home_text:
                raise AssertionError(
                    f"INVARIANT_TABLE row {row['name']!r}: clause no longer appears in "
                    f"authoritative home ({_HOME}, sections {sections}) — "
                    f"re-sync the table: {clause!r}"
                )


def _check_copy_holder_clauses(table, read_text=None):
    """Assert shared and holder clauses appear in each copy-holder's declared sections."""
    if read_text is None:
        read_text = _read_plugin
    for row in table:
        holder_clauses = row.get("holder_clauses") or {}
        for rel, sections in row["copy_holder_sections"].items():
            copy_text = _section_union(rel, sections, read_text)
            section_label = ", ".join(sections)
            for clause in row["clauses"]:
                if clause not in copy_text:
                    raise AssertionError(
                        f"INVARIANT_TABLE row {row['name']!r}: clause missing from "
                        f"{rel} (sections {section_label}) — "
                        f"re-sync against {_HOME}: {clause!r}"
                    )
            for clause in holder_clauses.get(rel, []):
                if clause not in copy_text:
                    raise AssertionError(
                        f"INVARIANT_TABLE row {row['name']!r}: holder clause missing from "
                        f"{rel} (sections {section_label}): {clause!r}"
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
    _check_home_clauses(_INVARIANT_TABLE)


def test_invariant_clauses_present_in_copy_holders():
    _validate_invariant_table()
    _check_copy_holder_clauses(_INVARIANT_TABLE)


def test_invariant_table_is_well_formed():
    _validate_invariant_table()


# --- Negative tests (synthetic in-memory inputs; no repo mutation) ---


def _table_without_row(name):
    return [row for row in _INVARIANT_TABLE if row["name"] != name]


def _table_with_duplicate_row(name):
    duplicate = next(row for row in _INVARIANT_TABLE if row["name"] == name)
    return _INVARIANT_TABLE + [duplicate]


def _table_with_holder_removed(row_name, holder):
    table = []
    for row in _INVARIANT_TABLE:
        if row["name"] != row_name:
            table.append(row)
            continue
        sections = dict(row["copy_holder_sections"])
        sections.pop(holder, None)
        holder_clauses = dict(row.get("holder_clauses") or {})
        holder_clauses.pop(holder, None)
        updated = dict(row)
        updated["copy_holder_sections"] = sections
        if holder_clauses:
            updated["holder_clauses"] = holder_clauses
        elif "holder_clauses" in updated:
            del updated["holder_clauses"]
        table.append(updated)
    return table


def _table_with_clause_removed(row_name):
    table = []
    for row in _INVARIANT_TABLE:
        if row["name"] != row_name:
            table.append(row)
            continue
        updated = dict(row)
        updated["clauses"] = row["clauses"][:-1]
        table.append(updated)
    return table


def _table_with_home_as_copy_holder():
    table = []
    for row in _INVARIANT_TABLE:
        updated = dict(row)
        updated["copy_holder_sections"] = dict(row["copy_holder_sections"])
        updated["copy_holder_sections"][_HOME] = row["home_sections"]
        table.append(updated)
    return table


def test_negative_roster_missing_waiver_bounds_row():
    with pytest.raises(RuntimeError, match="roster drift"):
        _validate_invariant_table(_table_without_row("waiver-bounds"))


def test_negative_roster_duplicate_resolve_upward():
    with pytest.raises(RuntimeError, match="duplicate invariant name"):
        _validate_invariant_table(_table_with_duplicate_row("resolve-upward"))


def test_negative_roster_workhorse_holder_removed():
    with pytest.raises(RuntimeError, match="copy-holder set drift"):
        _validate_invariant_table(
            _table_with_holder_removed("not-engaged-never-passes", "skills/workhorse/SKILL.md")
        )


def test_negative_roster_clause_deleted():
    with pytest.raises(RuntimeError, match="shared-clause count drift"):
        _validate_invariant_table(_table_with_clause_removed("resolve-upward"))


def test_negative_roster_home_as_copy_holder():
    with pytest.raises(RuntimeError, match="home must not appear as a copy-holder"):
        _validate_invariant_table(_table_with_home_as_copy_holder())


def test_negative_section_scoped_copy_check_rejects_out_of_section_match():
    """Regression: FAQ prose must not satisfy doctrine-section bounds."""
    synthetic_path = "synthetic/showrunner.md"
    synthetic_text = "\n".join([
        "## Micro — hard-line edit",
        "Micro is a named hard-line edit lane.",
        "## When you're tempted",
        (
            "owner-only, per change, never a standing grant; quiet-failure question; "
            "single named exception; risk stated."
        ),
    ])
    texts = {synthetic_path: synthetic_text}

    def read_text(rel):
        if rel not in texts:
            raise FileNotFoundError(rel)
        return texts[rel]

    table = [{
        "name": "waiver-bounds",
        "home_sections": ["### The spine", "### Micro — owner authorization"],
        "clauses": [
            "owner-only, per change, never a standing grant",
            "quiet-failure question",
            "single named exception",
        ],
        "copy_holder_sections": {
            synthetic_path: ["## Micro — hard-line edit"],
        },
        "holder_clauses": {
            synthetic_path: [
                "owner-only, per change, never a standing grant; "
                "the risk must be stated explicitly",
            ],
        },
    }]
    with pytest.raises(AssertionError, match="clause missing"):
        _check_copy_holder_clauses(table, read_text)


def test_negative_missing_section_heading_raises():
    def read_text(_rel):
        return "## Other section\nSome text.\n"

    with pytest.raises(RuntimeError, match="heading '## Your duties' not found"):
        _file_section("synthetic.md", "## Your duties", read_text)


def test_negative_duplicate_section_heading_raises():
    def read_text(_rel):
        return "\n".join([
            "## Your duties",
            "First copy.",
            "## Your duties",
            "Second copy.",
        ])

    with pytest.raises(RuntimeError, match="appears 2 times"):
        _file_section("synthetic.md", "## Your duties", read_text)


def test_negative_empty_section_body_fails_clause_check():
    synthetic_path = "synthetic/empty.md"
    synthetic_text = "\n".join([
        "## Build lanes",
        "",
        "## Next",
        "Later content with moving down a lane is never mentioned elsewhere.",
    ])

    def read_text(rel):
        if rel == synthetic_path:
            return synthetic_text
        return _read_plugin(rel)

    table = [{
        "name": "resolve-upward",
        "home_sections": ["### The spine"],
        "clauses": ["moving down a lane is never"],
        "copy_holder_sections": {
            synthetic_path: ["## Build lanes"],
        },
    }]
    with pytest.raises(AssertionError, match="clause missing"):
        _check_copy_holder_clauses(table, read_text)
