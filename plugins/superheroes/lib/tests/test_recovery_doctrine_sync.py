"""Drift guard for launch-doctrine Recovery (CONVENTIONS §11).

Guards the relation between ``rubric/launch-doctrine.md`` § Recovery — taking over a build that
stopped (authoritative home) and its two enumerated copy-holders:

- ``skills/showrunner/SKILL.md`` § ``## Your duties``
- ``skills/workhorse/SKILL.md`` § ``## 1. Intake — read the route and get the go-ahead``

Per §11.3 anti-tautology, each **shared** clause is first asserted in the home sub-section that
owns it before it is checked in the copy-holders — re-wording the home breaks CI here first.
``holder_clauses`` are exempt from the home check by construction: they pin holder-specific wording
where the home states the same bound in different words — a deliberate, narrower guarantee that is
not home-derived (blind spot: holder clauses are not verified against the home).

Section extraction reuses ``_file_section`` and ``_normalized`` from ``test_charter_boundary_sync``;
that reader is deliberately **fence-blind** (fence-awareness was tried and reverted in PR #727).

**Limitations (residual blind spots):**

1. substring presence cannot detect a nearby contradicting exception ("unless …");
2. a clause is pinned to a section, not to a paragraph or sentence — same-section satisfaction
   from a different paragraph still passes;
3. the fence-blind reader's latent fail-open shape if a heading appears only inside a fenced
   example (all guarded files currently carry zero fence lines; see ``test_no_fence_lines``);
4. ``holder_clauses`` being holder-specific, not home-derived.
"""
import os

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
        "by taking the newest file",
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

# Shared copy-holder clauses: home-derived; each must appear in home_section before holder check.
_SHARED_COPY_HOLDER_CLAUSES = {
    "skills/showrunner/SKILL.md": [
        {
            "text": "both halves run, neither replaces the other",
            "home_section": "### Sweep for unpushed work before adopting",
        },
    ],
    "skills/workhorse/SKILL.md": [
        {
            "text": "integrated",
            "home_section": "### Sweep for unpushed work before adopting",
        },
        {
            "text": "subsumed",
            "home_section": "### Sweep for unpushed work before adopting",
        },
        {
            "text": "contested",
            "home_section": "### Sweep for unpushed work before adopting",
        },
    ],
}

_HOLDER_CLAUSES = {
    "skills/showrunner/SKILL.md": [
        "rubric/launch-doctrine.md` § Recovery",
        "the branch and the sha it adopted",
        "the only path across instances or accounts",
        "suspected quota death",
        "adoption is a launch",
    ],
    "skills/workhorse/SKILL.md": [
        "rubric/launch-doctrine.md` § Recovery",
        "sweep for work the dead build never pushed",
        "unverified until you re-run it yourself",
    ],
}

_EXPECTED_HOLDER_CLAUSE_COUNTS = {
    "skills/showrunner/SKILL.md": 5,
    "skills/workhorse/SKILL.md": 3,
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


def _heading_occurrences(rel, heading, read_text=None):
    """Count exact stripped-line matches for a heading; fail closed on zero or duplicate."""
    if read_text is None:
        read_text = _read_plugin
    lines = read_text(rel).splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    return indices


def _assert_heading_exactly_once(rel, heading, read_text=None):
    indices = _heading_occurrences(rel, heading, read_text)
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
    for rel, shared_entries in _SHARED_COPY_HOLDER_CLAUSES.items():
        for entry in shared_entries:
            clause = entry["text"]
            home_section = entry["home_section"]
            home_text = _file_section(_HOME, home_section, read_text)
            if clause not in home_text:
                raise AssertionError(
                    f"shared copy-holder clause no longer appears in authoritative home "
                    f"({_HOME}, section {home_section}) — re-sync the table: {clause!r} "
                    f"(declared for {rel})"
                )


def _validate_copy_holder_key_sets():
    declared = frozenset(_COPY_HOLDER_SECTIONS)
    for rel in _HOLDER_CLAUSES:
        if rel not in declared:
            raise AssertionError(
                f"unknown charter key in _HOLDER_CLAUSES: {rel!r} "
                f"(declared charters: {sorted(declared)!r})"
            )
    for rel in _SHARED_COPY_HOLDER_CLAUSES:
        if rel not in declared:
            raise AssertionError(
                f"unknown charter key in _SHARED_COPY_HOLDER_CLAUSES: {rel!r} "
                f"(declared charters: {sorted(declared)!r})"
            )
    for rel in declared:
        holder_count = len(_HOLDER_CLAUSES.get(rel, []))
        shared_count = len(_SHARED_COPY_HOLDER_CLAUSES.get(rel, []))
        if holder_count + shared_count == 0:
            raise AssertionError(
                f"charter {rel!r} has no clauses pinned in _HOLDER_CLAUSES "
                f"or _SHARED_COPY_HOLDER_CLAUSES"
            )
        expected_holder_count = _EXPECTED_HOLDER_CLAUSE_COUNTS.get(rel)
        if expected_holder_count is None:
            raise AssertionError(
                f"charter {rel!r} missing from _EXPECTED_HOLDER_CLAUSE_COUNTS"
            )
        if holder_count != expected_holder_count:
            raise AssertionError(
                f"charter {rel!r}: holder-clause count drift — "
                f"expected {expected_holder_count}, got {holder_count}"
            )


def _check_copy_holder_clauses(read_text=None):
    if read_text is None:
        read_text = _read_plugin
    _validate_copy_holder_key_sets()
    for rel, section in _COPY_HOLDER_SECTIONS.items():
        copy_text = _file_section(rel, section, read_text)
        for entry in _SHARED_COPY_HOLDER_CLAUSES.get(rel, []):
            clause = entry["text"]
            if clause not in copy_text:
                raise AssertionError(
                    f"shared clause missing from {rel} (section {section}) — "
                    f"re-sync against {_HOME}: {clause!r}"
                )
        for clause in _HOLDER_CLAUSES.get(rel, []):
            if clause not in copy_text:
                raise AssertionError(
                    f"holder clause missing from {rel} (section {section}): {clause!r}"
                )


def _synthetic_home_with_all_clauses_except(out_of_section_clause):
    """Build synthetic home text with every pinned home clause in-section except one."""
    lines = []
    for subsection, clauses in _HOME_CLAUSES.items():
        lines.append(subsection)
        for clause in clauses:
            if clause == out_of_section_clause:
                lines.append("Other content without the probe clause here.")
            else:
                lines.append(f"Contains {clause} in the right section.")
    if out_of_section_clause not in {
        c for clauses in _HOME_CLAUSES.values() for c in clauses
    }:
        raise ValueError(f"unknown clause {out_of_section_clause!r}")
    lines.extend([
        "## Appendix",
        f"{out_of_section_clause} — but only outside the declared section.",
    ])
    return "\n".join(lines)


def _synthetic_home_missing_shared_copy_holder_clause(entry):
    """Build home text with every _HOME_CLAUSES pin but omit one shared copy-holder clause."""
    clause = entry["text"]
    home_section = entry["home_section"]
    if clause in {c for clauses in _HOME_CLAUSES.values() for c in clauses}:
        raise ValueError(
            f"clause {clause!r} is also pinned in _HOME_CLAUSES — "
            "use _synthetic_home_with_all_clauses_except for that probe"
        )
    lines = []
    for subsection, clauses in _HOME_CLAUSES.items():
        lines.append(subsection)
        for pinned in clauses:
            lines.append(f"Contains {pinned}.")
    section_text = _file_section(_HOME, home_section)
    if clause not in section_text:
        raise AssertionError(
            f"shared copy-holder probe clause no longer in real home section "
            f"{home_section!r}: {clause!r}"
        )
    return "\n".join(lines)


def _synthetic_showrunner_with_all_clauses_except(out_of_section_clause):
    """Build synthetic showrunner text with every pinned clause in-section except one."""
    section = _COPY_HOLDER_SECTIONS["skills/showrunner/SKILL.md"]
    lines = [section]
    all_clauses = [
        entry["text"]
        for entry in _SHARED_COPY_HOLDER_CLAUSES.get("skills/showrunner/SKILL.md", [])
    ] + _HOLDER_CLAUSES["skills/showrunner/SKILL.md"]
    for clause in all_clauses:
        if clause == out_of_section_clause:
            lines.append("Other duties without the probe clause here.")
        else:
            lines.append(f"Duty includes {clause}.")
    lines.extend([
        "## When you're tempted",
        f"{out_of_section_clause} — but only outside declared section",
    ])
    return "\n".join(lines)


def test_recovery_heading_exactly_once_in_home():
    _assert_heading_exactly_once(_HOME, _RECOVERY_HEADING)


def test_recovery_subsection_headings_exactly_once_in_home():
    for heading in _SUBSECTION_HEADINGS:
        _assert_heading_exactly_once(_HOME, heading)


def test_recovery_clauses_present_in_home():
    _check_home_clauses()


def test_recovery_clauses_present_in_copy_holders():
    _check_copy_holder_clauses()


def test_shared_copy_holder_clause_must_appear_in_home():
    """A clause declared shared must exist in the home — not only in copy-holders."""
    # Use a showrunner-only shared clause: the _HOME_CLAUSES loop does not pin it, so
    # this negative proves the shared binding loop rather than the older home loop.
    entry = _SHARED_COPY_HOLDER_CLAUSES["skills/showrunner/SKILL.md"][0]
    synthetic_text = _synthetic_home_missing_shared_copy_holder_clause(entry)

    def read_text(rel):
        if rel == _HOME:
            return synthetic_text
        return _read_plugin(rel)

    with pytest.raises(
        AssertionError,
        match=r"shared copy-holder clause no longer appears in authoritative home",
    ):
        _check_home_clauses(read_text)


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


def test_negative_assert_heading_exactly_once_absent():
    def read_text(_rel):
        return "## Other section\n"

    with pytest.raises(AssertionError, match=r"heading .+ not found"):
        _assert_heading_exactly_once(
            "synthetic.md",
            _RECOVERY_HEADING,
            read_text=read_text,
        )


def test_negative_assert_heading_exactly_once_duplicated():
    duplicated = "\n".join([
        _RECOVERY_HEADING,
        "First.",
        _RECOVERY_HEADING,
        "Second.",
    ])

    def read_text(_rel):
        return duplicated

    with pytest.raises(AssertionError, match=r"appears 2 times"):
        _assert_heading_exactly_once(
            "synthetic.md",
            _RECOVERY_HEADING,
            read_text=read_text,
        )


def test_negative_home_clause_absent_from_section():
    out_of_section_clause = "not proof of deep headroom"
    synthetic_text = _synthetic_home_with_all_clauses_except(out_of_section_clause)

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
    out_of_section_clause = "adoption is a launch"
    synthetic_text = _synthetic_showrunner_with_all_clauses_except(out_of_section_clause)
    showrunner_path = "skills/showrunner/SKILL.md"

    def read_text(rel):
        if rel == showrunner_path:
            return synthetic_text
        return _read_plugin(rel)

    with pytest.raises(
        AssertionError,
        match=r"holder clause missing from .+ \(section ## Your duties\)",
    ):
        _check_copy_holder_clauses(read_text)


def test_negative_shared_copy_holder_clause_missing_from_section():
    out_of_section_clause = "both halves run, neither replaces the other"
    synthetic_text = _synthetic_showrunner_with_all_clauses_except(out_of_section_clause)
    showrunner_path = "skills/showrunner/SKILL.md"

    def read_text(rel):
        if rel == showrunner_path:
            return synthetic_text
        return _read_plugin(rel)

    with pytest.raises(
        AssertionError,
        match=r"shared clause missing from .+ \(section ## Your duties\)",
    ):
        _check_copy_holder_clauses(read_text)
