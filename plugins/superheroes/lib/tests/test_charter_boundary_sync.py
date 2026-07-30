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
clauses appear in the copy-holder's declared section — presence, not equality.

Per §11.3 anti-tautology: shared clause strings are hand-typed, so each is first asserted against
the authoritative home section that owns it before it is used as the right-hand side for the
copies — re-wording the home breaks CI. ``holder_clauses`` are exempt from the home check by
construction: they are holder-specific pins using that file's own wording where the home states
the same bound in different words — a deliberate, narrower guarantee than the home-verified shared
clauses.

**Limitations (residual blind spots):**

1. the home gaining a new qualifier / scope / exception that the copies do not mirror;
2. a copy that keeps every clause verbatim while adding a contradicting exception nearby
   (substring presence cannot detect an added "unless …");
3. matches that span a boundary after ``*``-stripping and whitespace collapse;
4. ``holder_clauses`` being holder-specific, not home-derived;
5. same-section, different-paragraph satisfaction — a clause is pinned to a section, not to a
   paragraph or sentence (e.g. ``resolve upward to the full lane or park`` occurs 3× inside
   ``### What never changes in any lane``, so deleting the probe rule's own post-retry
   consequence leaves the clause satisfied by other paragraphs and the guard stays green);
   closing this needs paragraph/sentence anchoring (marker-delimited spans), which is out of this
   issue's ratified scope and is being handed to the advisor as a follow-up;
6. the spine's own waiver sentence (``owner-only, risk stated, never a standing grant``) is not
   separately pinned — it uses different wording from every copy paraphrase.
7. ``_file_section`` is deliberately **fence-blind**: a ````` ``` `````-fenced block inside a
   guarded section that contains a heading-looking line will **truncate** the section (or, if it
   repeats the target heading, be counted as a duplicate), so the guard **fails closed** with a
   spurious CI break rather than a silent pass; this is an **accepted residual** (PR #727,
   advisor-adjudicated): fence-awareness was implemented and **reverted** because it introduced a
   silent-pass path, and a real fence parser is not funded against a latent problem; **latency
   evidence:** all three guarded files carry **zero** ````` ``` ````` lines today; **revisit
   trigger:** only if a guarded doctrine file ever legitimately needs a fenced block.

Copy-holder disposition (§11.2 caveat — adding a copy means extending the table):

- **``rubric/review-discipline.md``** — authoritative home for the cross-lane invariants.
- **``skills/showrunner/SKILL.md``** — all three invariant rows.
- **``skills/workhorse/SKILL.md``** — resolve-upward and not-engaged-never-passes only; deliberately
  excluded from the waiver-bounds row because micro is the showrunner's lane, not an oversight.
"""
import copy
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

_EXPECTED_HOLDER_CLAUSE_COUNTS = {
    "waiver-bounds": {
        "skills/showrunner/SKILL.md": 1,
    },
}

_EXPECTED_HOME_SECTIONS = {
    "resolve-upward": {
        "Default to the full lane; anything unclear resolves upward": "### The spine",
        "moving down a lane is never": "### The spine",
        "it requires the owner, per change": "### The spine",
        "Disclosure alone never authorizes a downgrade": "### The spine",
        "the full lane at any size": "### The spine",
    },
    "not-engaged-never-passes": {
        "means that review did not happen": "### What never changes in any lane",
        "re-dispatch once": "### What never changes in any lane",
        "never a pass": "### What never changes in any lane",
        "zero is not evidence of engagement": "### What never changes in any lane",
        "resolve upward to the full lane or park": "### What never changes in any lane",
    },
    "waiver-bounds": {
        "owner-only, per change, never a standing grant": "### Micro — owner authorization",
        "quiet-failure question": "### Micro — owner authorization",
        "single named exception": "### Micro — owner authorization",
    },
}

_EXPECTED_HOLDER_SECTIONS = {
    "resolve-upward": {
        "skills/showrunner/SKILL.md": "## Your duties",
        "skills/workhorse/SKILL.md": "## Build lanes",
    },
    "not-engaged-never-passes": {
        "skills/showrunner/SKILL.md": "## Your duties",
        "skills/workhorse/SKILL.md": "## Build lanes",
    },
    "waiver-bounds": {
        "skills/showrunner/SKILL.md": "## Micro — hard-line edit",
    },
}

_INVARIANT_TABLE = [
    {
        "name": "resolve-upward",
        "clauses": [
            {
                "text": "Default to the full lane; anything unclear resolves upward",
                "home_section": "### The spine",
            },
            {
                "text": "moving down a lane is never",
                "home_section": "### The spine",
            },
            {
                "text": "it requires the owner, per change",
                "home_section": "### The spine",
            },
            {
                "text": "Disclosure alone never authorizes a downgrade",
                "home_section": "### The spine",
            },
            {
                "text": "the full lane at any size",
                "home_section": "### The spine",
            },
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": "## Your duties",
            "skills/workhorse/SKILL.md": "## Build lanes",
        },
    },
    {
        "name": "not-engaged-never-passes",
        "clauses": [
            {
                "text": "means that review did not happen",
                "home_section": "### What never changes in any lane",
            },
            {
                "text": "re-dispatch once",
                "home_section": "### What never changes in any lane",
            },
            {
                "text": "never a pass",
                "home_section": "### What never changes in any lane",
            },
            {
                "text": "zero is not evidence of engagement",
                "home_section": "### What never changes in any lane",
            },
            {
                "text": "resolve upward to the full lane or park",
                "home_section": "### What never changes in any lane",
            },
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": "## Your duties",
            "skills/workhorse/SKILL.md": "## Build lanes",
        },
    },
    {
        "name": "waiver-bounds",
        "clauses": [
            {
                "text": "owner-only, per change, never a standing grant",
                "home_section": "### Micro — owner authorization",
            },
            {
                "text": "quiet-failure question",
                "home_section": "### Micro — owner authorization",
            },
            {
                "text": "single named exception",
                "home_section": "### Micro — owner authorization",
            },
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": "## Micro — hard-line edit",
        },
        "holder_clauses": {
            "skills/showrunner/SKILL.md": [
                "owner-only, per change, never a standing grant; "
                "the risk must be stated explicitly",
            ],
        },
    },
]

# Import-time snapshot: the invariance test compares against this, NOT against a copy taken
# inside the test body. pytest runs tests in declaration order, so a baseline captured in the
# test body is already polluted by every test declared above it (measured: mutations from
# earlier-declared tests went undetected).
_INVARIANT_TABLE_AT_IMPORT = copy.deepcopy(_INVARIANT_TABLE)


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


# Deliberately fence-blind (blind spot 7): fence-awareness was tried and reverted in PR #727
# because it introduced a silent-pass path — an unclosed or mis-classified fence suppresses the
# section terminator and lets a later section's content satisfy a clause; fence-blindness fails
# closed instead.
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


def _clause_text(clause_entry):
    return clause_entry["text"]


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

        expected_home_sections = _EXPECTED_HOME_SECTIONS.get(name)
        if expected_home_sections is None:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: unexpected invariant name"
            )
        clause_texts = []
        for clause_entry in row["clauses"]:
            if not isinstance(clause_entry, dict):
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    "each clause must be a dict with text and home_section"
                )
            clause = clause_entry.get("text")
            home_section = clause_entry.get("home_section")
            if not clause or not str(clause).strip():
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    "clause must be non-empty and non-whitespace-only"
                )
            if not home_section or not str(home_section).strip():
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    "home_section must be non-empty and non-whitespace-only"
                )
            expected_section = expected_home_sections.get(clause)
            if expected_section is None:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"unexpected shared clause {clause!r}"
                )
            if home_section != expected_section:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: home_section drift for "
                    f"{clause!r} — expected {expected_section!r}, "
                    f"got {home_section!r}"
                )
            clause_texts.append(clause)
        if len(clause_texts) != len(set(clause_texts)):
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: duplicate shared clause"
            )

        expected_holder_sections = _EXPECTED_HOLDER_SECTIONS.get(name)
        if expected_holder_sections is None:
            raise RuntimeError(
                f"INVARIANT_TABLE row {name!r}: unexpected invariant name"
            )
        for rel, section in row["copy_holder_sections"].items():
            if not section or not str(section).strip():
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"section for {rel!r} must be non-empty"
                )
            expected_section = expected_holder_sections.get(rel)
            if expected_section is None:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: "
                    f"unexpected copy-holder {rel!r}"
                )
            if section != expected_section:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: section drift for "
                    f"{rel!r} — expected {expected_section!r}, got {section!r}"
                )

        holder_clauses = row.get("holder_clauses")
        if holder_clauses is None:
            holder_clauses = {}
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
        expected_holder_counts = _EXPECTED_HOLDER_CLAUSE_COUNTS.get(name, {})
        for rel in expected_holders:
            expected_holder_count = expected_holder_counts.get(rel, 0)
            actual_holder_count = len(holder_clauses.get(rel, []))
            if actual_holder_count != expected_holder_count:
                raise RuntimeError(
                    f"INVARIANT_TABLE row {name!r}: holder-clause count drift "
                    f"for {rel!r} — expected {expected_holder_count}, "
                    f"got {actual_holder_count}"
                )


def _check_home_clauses(table, read_text=None):
    """Assert shared clauses appear in their declared home sections.

    holder_clauses are intentionally exempt — they pin holder-specific wording, not
    home-derived shared clauses.
    """
    if read_text is None:
        read_text = _read_plugin
    for row in table:
        for clause_entry in row["clauses"]:
            clause = _clause_text(clause_entry)
            home_section = clause_entry["home_section"]
            home_text = _file_section(_HOME, home_section, read_text)
            if clause not in home_text:
                raise AssertionError(
                    f"INVARIANT_TABLE row {row['name']!r}: clause no longer appears in "
                    f"authoritative home ({_HOME}, section {home_section}) — "
                    f"re-sync the table: {clause!r}"
                )


def _check_copy_holder_clauses(table, read_text=None):
    """Assert shared and holder clauses appear in each copy-holder's declared section."""
    if read_text is None:
        read_text = _read_plugin
    for row in table:
        holder_clauses = row.get("holder_clauses") or {}
        for rel, section in row["copy_holder_sections"].items():
            copy_text = _file_section(rel, section, read_text)
            for clause_entry in row["clauses"]:
                clause = _clause_text(clause_entry)
                if clause not in copy_text:
                    raise AssertionError(
                        f"INVARIANT_TABLE row {row['name']!r}: clause missing from "
                        f"{rel} (section {section}) — "
                        f"re-sync against {_HOME}: {clause!r}"
                    )
            for clause in holder_clauses.get(rel, []):
                if clause not in copy_text:
                    raise AssertionError(
                        f"INVARIANT_TABLE row {row['name']!r}: holder clause missing from "
                        f"{rel} (section {section}): {clause!r}"
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
        updated["copy_holder_sections"][_HOME] = row["clauses"][0]["home_section"]
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


def test_negative_roster_holder_clauses_removed():
    table = []
    for row in _INVARIANT_TABLE:
        if row["name"] != "waiver-bounds":
            table.append(row)
            continue
        updated = dict(row)
        del updated["holder_clauses"]
        table.append(updated)
    with pytest.raises(RuntimeError, match="holder-clause count drift"):
        _validate_invariant_table(table)


def test_negative_roster_holder_clauses_key_typo():
    table = []
    for row in _INVARIANT_TABLE:
        if row["name"] != "waiver-bounds":
            table.append(row)
            continue
        updated = dict(row)
        updated["holder_clauses"] = {
            "skills/showrunner/SKILL.md.typo": updated["holder_clauses"][
                "skills/showrunner/SKILL.md"
            ],
        }
        table.append(updated)
    with pytest.raises(RuntimeError, match="is not a declared copy-holder"):
        _validate_invariant_table(table)


def test_negative_roster_widened_holder_section():
    table = []
    for row in _INVARIANT_TABLE:
        if row["name"] != "waiver-bounds":
            table.append(row)
            continue
        updated = dict(row)
        updated["copy_holder_sections"] = dict(row["copy_holder_sections"])
        updated["copy_holder_sections"]["skills/showrunner/SKILL.md"] = (
            "## When you're tempted"
        )
        table.append(updated)
    with pytest.raises(RuntimeError, match="section drift"):
        _validate_invariant_table(table)


def test_negative_holder_clause_missing_from_declared_section():
    """Holder-clause branch must run after shared clauses pass in the declared section."""
    # Mutant killed: neuter the holder-clause loop
    # (`for clause in holder_clauses.get(rel, [])` -> `for clause in []`) and this test must fail.
    synthetic_path = "synthetic/showrunner.md"
    holder_clause = (
        "owner-only, per change, never a standing grant; "
        "the risk must be stated explicitly"
    )
    synthetic_text = "\n".join([
        "## Micro — hard-line edit",
        (
            "owner-only, per change, never a standing grant; quiet-failure question; "
            "single named exception"
        ),
        "## When you're tempted",
        f"{holder_clause} — only here, not in declared section",
    ])
    texts = {synthetic_path: synthetic_text}

    def read_text(rel):
        if rel not in texts:
            raise FileNotFoundError(rel)
        return texts[rel]

    table = [{
        "name": "waiver-bounds",
        "clauses": [
            {
                "text": "owner-only, per change, never a standing grant",
                "home_section": "### Micro — owner authorization",
            },
            {
                "text": "quiet-failure question",
                "home_section": "### Micro — owner authorization",
            },
            {
                "text": "single named exception",
                "home_section": "### Micro — owner authorization",
            },
        ],
        "copy_holder_sections": {
            synthetic_path: "## Micro — hard-line edit",
        },
        "holder_clauses": {
            synthetic_path: [holder_clause],
        },
    }]
    with pytest.raises(
        AssertionError,
        match=r"holder clause missing from",
    ):
        _check_copy_holder_clauses(table, read_text)


def test_negative_home_section_drift():
    # Mutant killed: neuter the home_section drift comparison
    # (`if home_section != expected_section: raise ...` -> `if False: pass`) and this test must fail.
    table = []
    for row in _INVARIANT_TABLE:
        if row["name"] != "resolve-upward":
            table.append(row)
            continue
        updated = dict(row)
        clauses = []
        for i, clause_entry in enumerate(row["clauses"]):
            if i == 0:
                clauses.append({
                    "text": clause_entry["text"],
                    "home_section": "### What never changes in any lane",
                })
            else:
                clauses.append(dict(clause_entry))
        updated["clauses"] = clauses
        table.append(updated)
    with pytest.raises(RuntimeError, match="home_section drift"):
        _validate_invariant_table(table)


def test_negative_home_per_clause_not_row_union():
    # Mutant killed: home check uses row-union of all clause sections
    # (`home_text = _file_section(_HOME, home_section, read_text)` ->
    #  `" ".join(_file_section(_HOME, sec, read_text)
    #            for sec in sorted({c['home_section'] for c in row['clauses']}))`)
    # and this test must fail.
    synthetic_text = "\n".join([
        "### Section One",
        "Content without clause A here.",
        "### Section Two",
        "Clause A text lives here: PROBE_CLAUSE_A only in section two.",
        "Clause B text: PROBE_CLAUSE_B correctly here.",
    ])

    def read_text(rel):
        if rel == _HOME:
            return synthetic_text
        return _read_plugin(rel)

    table = [{
        "name": "synthetic-row-union-probe",
        "clauses": [
            {
                "text": "PROBE_CLAUSE_A only in section two",
                "home_section": "### Section One",
            },
            {
                "text": "PROBE_CLAUSE_B correctly here",
                "home_section": "### Section Two",
            },
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": "## Your duties",
        },
    }]
    with pytest.raises(
        AssertionError,
        match=(
            r"clause no longer appears in authoritative home "
            r"\(rubric/review-discipline\.md, section ### Section One\)"
        ),
    ):
        _check_home_clauses(table, read_text)


def test_invariant_table_not_mutated_by_test_run():
    """Running every test in this module must not mutate the live _INVARIANT_TABLE."""
    current_module = globals()
    test_names = sorted(
        name for name in current_module
        if name.startswith("test_") and name != "test_invariant_table_not_mutated_by_test_run"
    )
    for order in (test_names, list(reversed(test_names))):
        for name in order:
            try:
                current_module[name]()
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                raise RuntimeError(
                    f"called test '{name}' failed; this is NOT a table-mutation failure"
                ) from exc
    if _INVARIANT_TABLE != _INVARIANT_TABLE_AT_IMPORT:
        raise AssertionError(
            "_INVARIANT_TABLE was mutated during test run — live table differs from "
            f"import-time snapshot: live={_INVARIANT_TABLE!r}, "
            f"snapshot={_INVARIANT_TABLE_AT_IMPORT!r}"
        )


def test_negative_section_scoped_copy_check_rejects_out_of_section_match():
    """Regression: FAQ prose must not satisfy doctrine-section bounds."""
    # Mutant killed: revert _check_copy_holder_clauses to whole-file
    # _normalized(read_text(rel)) and this test must fail.
    synthetic_path = "synthetic/showrunner.md"
    holder_clause = (
        "owner-only, per change, never a standing grant; "
        "the risk must be stated explicitly"
    )
    synthetic_text = "\n".join([
        "## Micro — hard-line edit",
        "Micro is a named hard-line edit lane.",
        "## When you're tempted",
        (
            "owner-only, per change, never a standing grant; quiet-failure question; "
            f"single named exception; {holder_clause}"
        ),
    ])
    texts = {synthetic_path: synthetic_text}

    def read_text(rel):
        if rel not in texts:
            raise FileNotFoundError(rel)
        return texts[rel]

    table = [{
        "name": "waiver-bounds",
        "clauses": [
            {
                "text": "owner-only, per change, never a standing grant",
                "home_section": "### Micro — owner authorization",
            },
            {
                "text": "quiet-failure question",
                "home_section": "### Micro — owner authorization",
            },
            {
                "text": "single named exception",
                "home_section": "### Micro — owner authorization",
            },
        ],
        "copy_holder_sections": {
            synthetic_path: "## Micro — hard-line edit",
        },
        "holder_clauses": {
            synthetic_path: [holder_clause],
        },
    }]
    with pytest.raises(
        AssertionError,
        match=r"clause missing from .+ \(section ## Micro — hard-line edit\)",
    ):
        _check_copy_holder_clauses(table, read_text)


def test_negative_home_clause_absent_from_section_but_present_elsewhere():
    # Mutant killed: replace _check_home_clauses' _file_section with whole-file
    # _normalized(read_text(_HOME)) and this test must fail.
    synthetic_text = "\n".join([
        "### The spine",
        "Other spine content.",
        "### What never changes in any lane",
        "Lane rules without the probe clause here.",
        "## Appendix",
        "means that review did not happen — but only in this appendix.",
    ])

    def read_text(rel):
        if rel == _HOME:
            return synthetic_text
        return _read_plugin(rel)

    table = [{
        "name": "not-engaged-never-passes",
        "clauses": [
            {
                "text": "means that review did not happen",
                "home_section": "### What never changes in any lane",
            },
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": "## Your duties",
        },
    }]
    with pytest.raises(
        AssertionError,
        match=(
            r"clause no longer appears in authoritative home "
            r"\(rubric/review-discipline\.md, section ### What never changes in any lane\)"
        ),
    ):
        _check_home_clauses(table, read_text)


def test_negative_home_clause_absent_entirely():
    # Mutant killed: delete _check_home_clauses' raise AssertionError block and
    # this test must fail.
    synthetic_text = "\n".join([
        "### What never changes in any lane",
        "Content with no matching clauses.",
    ])

    def read_text(rel):
        if rel == _HOME:
            return synthetic_text
        return _read_plugin(rel)

    table = [{
        "name": "not-engaged-never-passes",
        "clauses": [
            {
                "text": "never a pass",
                "home_section": "### What never changes in any lane",
            },
        ],
        "copy_holder_sections": {
            "skills/showrunner/SKILL.md": "## Your duties",
        },
    }]
    with pytest.raises(
        AssertionError,
        match=(
            r"clause no longer appears in authoritative home "
            r"\(rubric/review-discipline\.md, section ### What never changes in any lane\)"
        ),
    ):
        _check_home_clauses(table, read_text)


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
        "clauses": [
            {
                "text": "moving down a lane is never",
                "home_section": "### The spine",
            },
        ],
        "copy_holder_sections": {
            synthetic_path: "## Build lanes",
        },
    }]
    with pytest.raises(AssertionError, match=r"clause missing from .+ \(section ## Build lanes\)"):
        _check_copy_holder_clauses(table, read_text)
