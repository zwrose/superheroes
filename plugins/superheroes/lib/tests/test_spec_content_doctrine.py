"""Drift guards for the spec-content doctrine (issue #936, child C5).

Enforces mechanical presence of spec-content doctrine clauses across the template,
architect-spec reference, discovery/showrunner/review-spec charters, and the epic
register pin — section-scoped so partial drift reddens exactly one guard.
"""
# What this file does and does not guard (issue #936, child C5).
#
# Every assertion here rests on a mechanical fact about the document: a fixed literal
# present or absent, a parsed table cell, a count, a section-scoped match. The
# charter's MEANING is guarded by review, not by CI. If a doctrine claim can only be
# checked by judging what a sentence means, it does not belong here.
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))

_SPEC_TEMPLATE = os.path.join(_PLUGIN_ROOT, "templates", "spec.md")
_SPEC_CONTENT_REF = "skills/architect-spec/reference/spec-content.md"
_ARCHITECT_SPEC_CHARTER = "skills/architect-spec/SKILL.md"
_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"
_DISCOVERY_CHARTER = "skills/architect-discovery/SKILL.md"
_REVIEW_SPEC_CHARTER = "skills/review-spec/SKILL.md"
_REVIEW_SPEC_DETAIL = "skills/review-spec/reference/spec-detail.md"

_EPIC_REGISTER_REL = os.path.normpath(
    os.path.join("..", "..", "docs", "superheroes",
                 "front-half-sdlc-core-6181ee", "register.md")
)

# Pinned register literals (epic register is home of record; duplicated here because
# lib/tests/ ships inside the plugin to projects that do not carry the register file).
R4_AMENDMENT_CLASSES = (
    "Every post-approval spec amendment is classified `wording` (changes phrasing; "
    "decides nothing a builder could build differently against) or `substantive` "
    "(anything else — the default when ambiguous, failing closed), and every "
    "Amendments-log entry carries: date, owner stamp, class, and the section names "
    "it touched; entries are ordered in the log and numbered by order of addition "
    "(oldest = 1) — the number is positional, not a new field — and R1's anchor "
    "cursor reads that order; a wording amendment's total ceremony is the body edit, "
    "the log entry, and mechanical propagation; a substantive amendment additionally "
    "triggers the touched-parts re-read (UFR-4) before injection."
)

_COVERAGE_TABLE_HEADER = "| Area | Disposition | Show-it? | Where / why |"
_OLD_COVERAGE_TABLE_HEADER = "| Area | Disposition | Where / why |"
_BANNED_SHARED_CONTRACT = "the shared contract"

_EXPECTED_COVERAGE_AREAS = [
    "Empty & first-run",
    "Invalid & malformed input",
    "Boundaries & limits",
    "Errors & failures",
    "Access & permissions",
    "Duplicates & double-actions",
    "Conflicting / simultaneous use",
    "Misuse & abuse",
    "Reach (i18n / a11y)",
    "Wording & tone",
    "Workflow shape",
    "Placement & prominence",
    "Limits & defaults",
    "Tier & access boundaries",
    "Visibility & disclosure",
]

_DOCTRINE_SURFACES = [
    _SPEC_TEMPLATE,
    os.path.join(_PLUGIN_ROOT, _SPEC_CONTENT_REF),
    os.path.join(_PLUGIN_ROOT, _ARCHITECT_SPEC_CHARTER),
    os.path.join(_PLUGIN_ROOT, _SHOWRUNNER_CHARTER),
    os.path.join(_PLUGIN_ROOT, _DISCOVERY_CHARTER),
    os.path.join(_PLUGIN_ROOT, _REVIEW_SPEC_CHARTER),
    os.path.join(_PLUGIN_ROOT, _REVIEW_SPEC_DETAIL),
]

# Axis: each guard bites when a doctrine clause is removed from, or reworded out of,
# the section that owns it.
#
# Tuple fields: (id, surface, section, literal, kind)
# kind: literal | table_header | coverage_rows | section_exists | section_order |
#       coverage_tables_equal | register_r4 | pointer_literal | banned_file |
#       banned_surfaces
_CLAUSE_ENTRIES = [
    # A. templates/spec.md
    (
        "template-coverage-header",
        "templates/spec.md",
        "## Coverage",
        _COVERAGE_TABLE_HEADER,
        "table_header",
    ),
    (
        "template-coverage-fifteen-rows",
        "templates/spec.md",
        "## Coverage",
        "",
        "coverage_rows",
    ),
    (
        "template-amendments-section",
        "templates/spec.md",
        "## Amendments",
        "",
        "section_exists",
    ),
    (
        "template-amendments-zero-state",
        "templates/spec.md",
        "## Amendments",
        "_No amendments since the last full approval._",
        "literal",
    ),
    (
        "template-amendments-entry-fields",
        "templates/spec.md",
        "## Amendments",
        "carrying its **date**",
        "literal",
    ),
    (
        "template-amendments-entry-fields-owner-stamp",
        "templates/spec.md",
        "## Amendments",
        "the **owner stamp**",
        "literal",
    ),
    (
        "template-amendments-entry-fields-class",
        "templates/spec.md",
        "## Amendments",
        "its **class** (`wording` or `substantive`)",
        "literal",
    ),
    (
        "template-amendments-entry-fields-sections-touched",
        "templates/spec.md",
        "## Amendments",
        "and the **section names it",
        "literal",
    ),
    (
        "template-amendments-oldest-first",
        "templates/spec.md",
        "## Amendments",
        "oldest first",
        "literal",
    ),
    (
        "template-amendments-numbered-by-position",
        "templates/spec.md",
        "## Amendments",
        "number is its position",
        "literal",
    ),
    (
        "template-amendments-before-coverage",
        "templates/spec.md",
        "## Amendments||## Coverage",
        "",
        "section_order",
    ),
    (
        "template-coverage-show-it-handback",
        "templates/spec.md",
        "## Coverage",
        "handback omission, not a build defect",
        "literal",
    ),
    (
        "template-coverage-initial-seed",
        "templates/spec.md",
        "## Coverage",
        "initial seed list",
        "literal",
    ),
    # B. spec-content.md
    (
        "spec-content-fr23-five-amendments",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "five amendments since its last full approval",
        "literal",
    ),
    (
        "spec-content-fr23-next-touch",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "obligation attaches to the touch **after** it",
        "literal",
    ),
    (
        "spec-content-fr23-guideline-not-tripline",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "guideline, never a trip-line",
        "literal",
    ),
    (
        "spec-content-fr23-nothing-blocks",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "Nothing blocks at five",
        "literal",
    ),
    (
        "spec-content-fr23-owner-restamp",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "re-stamp is the owner's",
        "literal",
    ),
    (
        "spec-content-fr23-cannot-substitute",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "cannot be substituted, delegated, or inferred from silence",
        "literal",
    ),
    (
        "spec-content-fr23-records-who-owes",
        _SPEC_CONTENT_REF,
        "## Consolidation re-read (FR-23)",
        "names who owes it",
        "literal",
    ),
    (
        "spec-content-fr24-elaborates-never-opinion",
        _SPEC_CONTENT_REF,
        "## Annexes (FR-24)",
        "never introduces a new",
        "literal",
    ),
    (
        "spec-content-fr24-elaborates-decisions",
        _SPEC_CONTENT_REF,
        "## Annexes (FR-24)",
        "elaborates decisions its core spec **already makes**",
        "literal",
    ),
    (
        "spec-content-fr24-named-finding-class",
        _SPEC_CONTENT_REF,
        "## Annexes (FR-24)",
        "named review-spec finding class",
        "literal",
    ),
    (
        "spec-content-fr25-no-rulings-ledger",
        _SPEC_CONTENT_REF,
        "## Rulings live where they were made (FR-25)",
        "no separate rulings ledger",
        "literal",
    ),
    (
        "spec-content-fr25-recorded-judgment",
        _SPEC_CONTENT_REF,
        "## Rulings live where they were made (FR-25)",
        "recorded advisor judgment",
        "literal",
    ),
    (
        "spec-content-fr25-no-mechanical-trigger",
        _SPEC_CONTENT_REF,
        "## Rulings live where they were made (FR-25)",
        "no mechanical absorption trigger",
        "literal",
    ),
    (
        "spec-content-fr25-no-count-age-size",
        _SPEC_CONTENT_REF,
        "## Rulings live where they were made (FR-25)",
        "no count of rulings, no age, no size, no threshold",
        "literal",
    ),
    (
        "spec-content-amendments-never-deleted-rule",
        _SPEC_CONTENT_REF,
        "## The Amendments section is never deleted",
        "Every spec renders a `## Amendments` section",
        "literal",
    ),
    (
        "spec-content-amendments-never-deleted-reason",
        _SPEC_CONTENT_REF,
        "## The Amendments section is never deleted",
        "fails closed when a spec carries no Amendments log at all",
        "literal",
    ),
    # C. architect-spec/SKILL.md
    (
        "architect-spec-amendments-exception",
        _ARCHITECT_SPEC_CHARTER,
        "## Weight never changes the artifact class",
        "Exception — `## Amendments`",
        "literal",
    ),
    (
        "architect-spec-spec-content-pointer",
        _ARCHITECT_SPEC_CHARTER,
        "",
        "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/architect-spec/reference/spec-content.md",
        "pointer_literal",
    ),
    # D. showrunner/SKILL.md
    (
        "showrunner-absorption-judgment",
        _SHOWRUNNER_CHARTER,
        "**Notify in-flight builds when a ruling is superseded.**",
        "recorded advisor judgment",
        "literal_bold_section",
    ),
    (
        "showrunner-absorption-no-trigger",
        _SHOWRUNNER_CHARTER,
        "**Notify in-flight builds when a ruling is superseded.**",
        "no mechanical trigger",
        "literal_bold_section",
    ),
    (
        "showrunner-consolidation-five",
        _SHOWRUNNER_CHARTER,
        "**Notify in-flight builds when a ruling is superseded.**",
        "five amendments since its last full approval",
        "literal_bold_section",
    ),
    (
        "showrunner-consolidation-next-touch",
        _SHOWRUNNER_CHARTER,
        "**Notify in-flight builds when a ruling is superseded.**",
        "next touch",
        "literal_bold_section",
    ),
    (
        "showrunner-consolidation-owner-restamp",
        _SHOWRUNNER_CHARTER,
        "**Notify in-flight builds when a ruling is superseded.**",
        "the **owner's** re-stamp",
        "literal_bold_section",
    ),
    # E. architect-discovery/SKILL.md
    (
        "discovery-fr19-admission-rule",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "the owner was asked, and cared",
        "literal",
    ),
    (
        "discovery-fr19-only-admission-rule",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "That is the **only** admission rule",
        "literal",
    ),
    (
        "discovery-fr19-exclude-mechanisms",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "**Mechanisms**",
        "literal",
    ),
    (
        "discovery-fr19-exclude-limits",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "**Limits the owner would not enforce**",
        "literal",
    ),
    (
        "discovery-fr19-exclude-vacuous-quality",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "**Vacuous quality lines**",
        "literal",
    ),
    (
        "discovery-fr19-exclude-design-handoff",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "**Design-handoff transcription**",
        "literal",
    ),
    (
        "discovery-fr19-exclude-test-obligations",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "**Test obligations**",
        "literal",
    ),
    (
        "discovery-fr19-exclude-mirror-facts",
        _DISCOVERY_CHARTER,
        "#### The elicitation test (FR-19)",
        "**Non-load-bearing mirror-facts**",
        "literal",
    ),
    (
        "discovery-fr20-specify-builder-defect",
        _DISCOVERY_CHARTER,
        "#### Failure semantics (FR-20)",
        "builder defect",
        "literal",
    ),
    (
        "discovery-fr20-show-it-handback",
        _DISCOVERY_CHARTER,
        "#### Failure semantics (FR-20)",
        "handback omission",
        "literal",
    ),
    (
        "discovery-fr20-defer-new-ruling",
        _DISCOVERY_CHARTER,
        "#### Failure semantics (FR-20)",
        "ruling, never a defect**",
        "literal",
    ),
    (
        "discovery-fr21-asked-and-deferred",
        _DISCOVERY_CHARTER,
        "#### The learning loop (FR-21)",
        "Asked and deferred",
        "literal",
    ),
    (
        "discovery-fr21-never-asked",
        _DISCOVERY_CHARTER,
        "#### The learning loop (FR-21)",
        "Never asked",
        "literal",
    ),
    (
        "discovery-fr21-growth-duty",
        _DISCOVERY_CHARTER,
        "#### The learning loop (FR-21)",
        "coverage checklist in this charter and to the template's Dispositions table",
        "literal",
    ),
    (
        "discovery-coverage-tables-match",
        _DISCOVERY_CHARTER,
        "### 3. Requirements dialogue (one question at a time)",
        "",
        "coverage_tables_equal",
    ),
    # F. review-spec
    (
        "review-spec-coherence-annex",
        _REVIEW_SPEC_CHARTER,
        "## Per-dimension framing (you are reviewing REQUIREMENTS — six doc-native lenses)",
        "annex that introduces a new opinion",
        "literal",
    ),
    (
        "review-spec-fifteen-rows",
        _REVIEW_SPEC_CHARTER,
        "## Spec-Content Requirements (Opinionated)",
        "fifteen rows: nine unhappy-path areas",
        "literal",
    ),
    (
        "review-spec-both-axes",
        _REVIEW_SPEC_CHARTER,
        "## Spec-Content Requirements (Opinionated)",
        "each row has `Disposition` (Specify / Defer-to-build / N-A) and `Show-it?`",
        "literal",
    ),
    (
        "review-spec-detail-annex-opinion-section",
        _REVIEW_SPEC_DETAIL,
        "## Annex opinion (finding class)",
        "annex that introduces a new opinion",
        "literal",
    ),
    (
        "review-spec-detail-annex-recognition-test",
        _REVIEW_SPEC_DETAIL,
        "## Annex opinion (finding class)",
        "If a builder reading only the core would build something different",
        "literal",
    ),
    # G. pinned register
    (
        "register-r4-pin",
        _EPIC_REGISTER_REL,
        "",
        R4_AMENDMENT_CLASSES,
        "register_r4",
    ),
    # H. banned strings
    (
        "banned-shared-contract",
        "",
        "",
        _BANNED_SHARED_CONTRACT,
        "banned_surfaces",
    ),
    (
        "banned-old-coverage-header",
        "templates/spec.md",
        "",
        _OLD_COVERAGE_TABLE_HEADER,
        "banned_file",
    ),
]


def _read_plugin(rel):
    path = rel if os.path.isabs(rel) else os.path.join(_PLUGIN_ROOT, rel)
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


def _file_section_raw(rel, heading, read_text=None):
    if read_text is None:
        read_text = _read_plugin
    text = read_text(rel)
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) == 0:
        raise AssertionError(f"{rel}: heading {heading!r} not found")
    if len(indices) > 1:
        raise AssertionError(
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
    return "\n".join(lines[start:end])


def _bold_section_raw(rel, marker, read_text=None):
    if read_text is None:
        read_text = _read_plugin
    text = read_text(rel)
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if marker in line]
    if len(indices) == 0:
        raise AssertionError(f"{rel}: bold marker {marker!r} not found")
    if len(indices) > 1:
        raise AssertionError(
            f"{rel}: bold marker {marker!r} appears {len(indices)} times"
        )
    start = indices[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("**") and stripped.endswith("**") and marker not in lines[i]:
            end = i
            break
        if re.match(r"^\d+\.\s+\*\*", stripped) and i > start:
            end = i
            break
    return "\n".join(lines[start:end])


def _parse_markdown_table(section_text):
    table_lines = []
    in_table = False
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_lines.append(stripped)
        elif in_table:
            break
    if not table_lines:
        raise AssertionError("no markdown table found in section")
    if len(table_lines) < 2:
        raise AssertionError("markdown table has no header row")
    separator_cells = [
        cell.strip() for cell in table_lines[1].strip("|").split("|")
    ]
    separator_re = re.compile(r"^:?-{3,}:?$")
    for cell in separator_cells:
        if not separator_re.match(cell):
            raise AssertionError("markdown table has no separator row")
    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows = []
    for table_line in table_lines[2:]:
        cells = [cell.strip() for cell in table_line.strip("|").split("|")]
        if len(cells) != len(headers):
            raise AssertionError(
                "markdown table row has %d cells, expected %d"
                % (len(cells), len(headers))
            )
        rows.append(dict(zip(headers, cells)))
    if not rows:
        raise AssertionError("markdown table has no data rows")
    return rows


def _coverage_area_names_from_rows(rows):
    return [row["Area"].strip("`").strip() for row in rows]


def _template_coverage_areas():
    section_text = _file_section_raw("templates/spec.md", "## Coverage")
    rows = _parse_markdown_table(section_text)
    return _coverage_area_names_from_rows(rows)


def _assert_coverage_rows_in_order(rel, heading):
    section_text = _file_section_raw(rel, heading)
    rows = _parse_markdown_table(section_text)
    areas = _coverage_area_names_from_rows(rows)
    expected = list(_EXPECTED_COVERAGE_AREAS)
    if len(areas) != len(expected):
        raise AssertionError(
            f"{rel}: coverage table has {len(areas)} rows, expected {len(expected)}"
        )
    if areas != expected:
        raise AssertionError(
            f"{rel}: coverage areas {areas!r} do not match expected order {expected!r}"
        )


def _discovery_coverage_areas():
    section_text = _file_section_raw(
        _DISCOVERY_CHARTER,
        "### 3. Requirements dialogue (one question at a time)",
    )
    rows = _parse_markdown_table(section_text)
    areas = []
    for row in rows:
        area = row.get("Coverage area", "").strip("`").strip()
        if area.startswith("**") and area.endswith("**"):
            area = area[2:-2]
        areas.append(area)
    return areas


def _assert_literal_in_section(rel, heading, literal, *, bold=False):
    if bold:
        section_text = _bold_section_raw(rel, heading)
    else:
        section_text = _file_section_raw(rel, heading)
    normalized = _normalized(section_text)
    if _normalized(literal) not in normalized:
        raise AssertionError(
            f"{rel}: clause missing from section {heading!r}: {literal!r}"
        )


def _assert_table_header_in_section(rel, heading, header):
    section_text = _file_section_raw(rel, heading)
    if header not in section_text:
        raise AssertionError(
            f"{rel}: table header missing from section {heading!r}: {header!r}"
        )


def _assert_section_exists(rel, heading):
    text = _read_plugin(rel)
    if heading not in text.splitlines() and f"{heading}\n" not in text:
        lines = text.splitlines()
        if heading not in [line.strip() for line in lines]:
            raise AssertionError(f"{rel}: section {heading!r} not found")


def _h2_heading_indices(text):
    """Return (heading, line_index) for each ^## heading line."""
    indices = []
    for i, line in enumerate(text.splitlines()):
        if re.match(r"^## ", line):
            indices.append((line.strip(), i))
    return indices


def _assert_section_order(rel, first_heading, second_heading):
    text = _read_plugin(rel)
    headings = _h2_heading_indices(text)
    first_matches = [i for h, i in headings if h == first_heading]
    second_matches = [i for h, i in headings if h == second_heading]
    if len(first_matches) == 0:
        raise AssertionError(f"{rel}: section {first_heading!r} not found")
    if len(second_matches) == 0:
        raise AssertionError(f"{rel}: section {second_heading!r} not found")
    if len(first_matches) > 1:
        raise AssertionError(
            f"{rel}: section {first_heading!r} appears {len(first_matches)} times"
        )
    if len(second_matches) > 1:
        raise AssertionError(
            f"{rel}: section {second_heading!r} appears {len(second_matches)} times"
        )
    if first_matches[0] >= second_matches[0]:
        raise AssertionError(
            f"{rel}: {first_heading!r} must appear before {second_heading!r}"
        )


def _assert_coverage_tables_equal():
    template_areas = _template_coverage_areas()
    discovery_areas = _discovery_coverage_areas()
    if discovery_areas != template_areas:
        raise AssertionError(
            "discovery coverage checklist areas %r do not match template areas %r"
            % (discovery_areas, template_areas)
        )


def _assert_register_r4():
    path = os.path.normpath(os.path.join(_PLUGIN_ROOT, _EPIC_REGISTER_REL))
    if not os.path.isfile(path):
        pytest.skip(path)
    text = _read_plugin(_EPIC_REGISTER_REL)
    if text.count(R4_AMENDMENT_CLASSES) != 1:
        raise AssertionError(
            "register R4 pinned literal found %d times, expected 1"
            % text.count(R4_AMENDMENT_CLASSES)
        )


_POINTER_SUFFIX = "skills/architect-spec/reference/spec-content.md"


def _assert_pointer_literal(rel, pointer):
    text = _read_plugin(rel)
    if pointer + "`" not in text:
        raise AssertionError(
            f"{rel}: plugin-relative pointer missing: {pointer!r}"
        )
    if _POINTER_SUFFIX not in pointer:
        raise AssertionError(
            f"{rel}: pointer does not name {_POINTER_SUFFIX!r}: {pointer!r}"
        )
    path = os.path.join(_PLUGIN_ROOT, _POINTER_SUFFIX)
    if not os.path.isfile(path):
        raise AssertionError(
            f"plugin-relative path does not resolve: {_POINTER_SUFFIX!r}"
        )


def _assert_banned_in_file(rel, banned):
    text = _read_plugin(rel)
    if banned in text:
        raise AssertionError(f"{rel}: banned string found: {banned!r}")


def _assert_banned_across_surfaces(banned):
    for path in _DOCTRINE_SURFACES:
        rel = os.path.relpath(path, _PLUGIN_ROOT)
        _assert_banned_in_file(rel, banned)


def _run_clause_check(entry):
    clause_id, surface, section, literal, kind = entry
    if kind == "literal":
        _assert_literal_in_section(surface, section, literal)
    elif kind == "literal_bold_section":
        _assert_literal_in_section(surface, section, literal, bold=True)
    elif kind == "table_header":
        _assert_table_header_in_section(surface, section, literal)
    elif kind == "coverage_rows":
        _assert_coverage_rows_in_order(surface, section)
    elif kind == "section_exists":
        _assert_section_exists(surface, section)
    elif kind == "section_order":
        first, second = section.split("||")
        _assert_section_order(surface, first, second)
    elif kind == "coverage_tables_equal":
        _assert_coverage_tables_equal()
    elif kind == "register_r4":
        _assert_register_r4()
    elif kind == "pointer_literal":
        _assert_pointer_literal(surface or _ARCHITECT_SPEC_CHARTER, literal)
    elif kind == "banned_file":
        _assert_banned_in_file(surface, literal)
    elif kind == "banned_surfaces":
        _assert_banned_across_surfaces(literal)
    else:
        raise AssertionError(f"unknown clause kind {kind!r} for {clause_id!r}")


@pytest.mark.parametrize(
    "entry",
    _CLAUSE_ENTRIES,
    ids=[entry[0] for entry in _CLAUSE_ENTRIES],
)
def test_clause_present(entry):
    _run_clause_check(entry)


def test_clause_table_populated():
    assert len(_CLAUSE_ENTRIES) >= 36
