"""Self-tests for the shared clause-guard chokepoint (issue #1219)."""
import os

import pytest

from clause_guard import (
    add_one_occurrence_in_section,
    census_excluded,
    check_clause,
    count_clause_in_section,
    drop_one_occurrence_in_section,
    plant_clause_elsewhere,
    section_span,
    without_clause_in_section,
)

CLAUSE = "the guarded phrase appears here"
CLAUSE_TWICE = "duplicate phrase here"
REL = "synthetic.md"
SECTION_A = "## Section A"
SECTION_B = "## Section B"


def _doc(*lines):
    return "\n".join(lines)


def _base_doc():
    return _doc(
        SECTION_A,
        f"Intro with {CLAUSE} in section A.",
        "### Sub A",
        "nested content",
        SECTION_B,
        "Section B has no target clause.",
    )


def test_section_span_includes_deeper_subheading():
    """section_span includes a deeper subheading while excluding the next same-level heading."""
    lines = _base_doc().splitlines()
    start, end = section_span(lines, SECTION_A, REL)
    body = "\n".join(lines[start:end])
    assert "### Sub A" in body
    assert "nested content" in body
    assert SECTION_B not in body


def test_check_clause_passes_correct_document():
    text = _doc(
        SECTION_A,
        f"First {CLAUSE_TWICE}.",
        f"Second {CLAUSE_TWICE}.",
        SECTION_B,
        "other",
    )
    check_clause(text, REL, SECTION_A, CLAUSE_TWICE, 2)


def test_cg1_absent_clause_raises():
    """CG-1: a clause absent from its declared section makes check_clause raise."""
    text = _doc(
        SECTION_A,
        "No target clause in this section.",
        SECTION_B,
        "other",
    )
    with pytest.raises(AssertionError, match=SECTION_A):
        check_clause(text, REL, SECTION_A, CLAUSE, 1)


def test_cg2_partial_drift_raises():
    """CG-2: dropping one of two occurrences makes check_clause raise."""
    text = _doc(
        SECTION_A,
        f"First {CLAUSE_TWICE}.",
        f"Second {CLAUSE_TWICE}.",
        SECTION_B,
        "other",
    )
    mutated = drop_one_occurrence_in_section(text, REL, SECTION_A, CLAUSE_TWICE)
    with pytest.raises(AssertionError, match="expected count 2"):
        check_clause(mutated, REL, SECTION_A, CLAUSE_TWICE, 2)


def test_cg3_over_count_raises():
    """CG-3: adding an extra occurrence makes check_clause raise."""
    text = _doc(
        SECTION_A,
        f"One {CLAUSE_TWICE}.",
        f"Two {CLAUSE_TWICE}.",
        SECTION_B,
        "other",
    )
    mutated = add_one_occurrence_in_section(text, REL, SECTION_A, CLAUSE_TWICE)
    with pytest.raises(AssertionError, match="expected count 2"):
        check_clause(mutated, REL, SECTION_A, CLAUSE_TWICE, 2)


def test_cg4_restatement_elsewhere_raises():
    """CG-4: a clause restated in another section still makes check_clause raise."""
    text = _doc(
        SECTION_A,
        "Section A without the clause.",
        SECTION_B,
        f"Restated {CLAUSE} in section B.",
    )
    with pytest.raises(AssertionError, match=SECTION_A):
        check_clause(text, REL, SECTION_A, CLAUSE, 1)


def test_cg5_following_section_only_raises():
    """CG-5: a clause present only in the following section makes check_clause raise."""
    text = _doc(
        SECTION_A,
        "Section A without the clause.",
        SECTION_B,
        f"Only here: {CLAUSE}.",
    )
    with pytest.raises(AssertionError, match=SECTION_A):
        check_clause(text, REL, SECTION_A, CLAUSE, 1)


def test_cg6_section_span_zero_headings_raises():
    """CG-6: section_span with zero matching headings raises RuntimeError."""
    lines = [SECTION_B, "text"]
    with pytest.raises(RuntimeError, match="expected exactly one '## Missing'"):
        section_span(lines, "## Missing", REL)


def test_cg7_section_span_duplicate_headings_raises():
    """CG-7: section_span with two matching headings raises RuntimeError."""
    lines = _doc("## Dup", "a", "## Dup", "b").splitlines()
    with pytest.raises(RuntimeError, match="expected exactly one '## Dup'"):
        section_span(lines, "## Dup", REL)


def test_cg8_line_wrapped_clause_matches():
    """CG-8: a line-wrapped clause matches; one word changed does not."""
    wrapped = "line wrapped phrase matches"
    text = _doc(
        SECTION_A,
        "line wrapped",
        "phrase matches here.",
        SECTION_B,
        "other",
    )
    assert count_clause_in_section(text, REL, SECTION_A, wrapped) == 1
    assert count_clause_in_section(text, REL, SECTION_A, "line wrapped phrase fails") == 0


def test_cg9_census_excluded():
    """CG-9: census_excluded boundary for excluded dir, file, prefix-sibling, and elsewhere."""
    excluded_dirs = ("lib/tests/bite_proofs",)
    excluded_files = ("CHANGELOG.md",)
    assert census_excluded("lib/tests/bite_proofs/wo_a_1219.md", excluded_dirs, excluded_files)
    assert census_excluded("CHANGELOG.md", excluded_dirs, excluded_files)
    assert not census_excluded("lib/tests/bite_proofs_notes.md", excluded_dirs, excluded_files)
    assert not census_excluded("docs/bite_proofs/notes.md", excluded_dirs, excluded_files)


def test_cg10_mutation_helpers_raise_on_drifted_anchor():
    """CG-10: mutation helpers raise when their anchor has drifted."""
    absent_clause_doc = _doc(
        SECTION_A,
        "Section A without the target clause.",
        SECTION_B,
        "other",
    )
    with pytest.raises(AssertionError, match="not found"):
        without_clause_in_section(absent_clause_doc, REL, SECTION_A, CLAUSE)

    one_occurrence = _doc(
        SECTION_A,
        f"Only one {CLAUSE_TWICE}.",
        SECTION_B,
        "other",
    )
    with pytest.raises(AssertionError, match="at least 2"):
        drop_one_occurrence_in_section(one_occurrence, REL, SECTION_A, CLAUSE_TWICE)

    no_source = _doc(
        SECTION_A,
        "No clause in source section.",
        SECTION_B,
        "target section",
    )
    with pytest.raises(AssertionError, match="not found"):
        plant_clause_elsewhere(no_source, REL, SECTION_A, SECTION_B, CLAUSE)


def test_cg11_fence_aware_section_span():
    """CG-11: fenced ``#`` / ``##`` lines are not headings; real headings after fences still end spans."""
    clause_after_fence = "clause after the fence is guarded"
    text = _doc(
        "## Declared section",
        "intro",
        "```bash",
        "# shell comment must not truncate",
        "## fake heading inside fence",
        "```",
        f"Body with {clause_after_fence}.",
        "## Next section",
        "after",
    )
    assert count_clause_in_section(text, REL, "## Declared section", clause_after_fence) == 1
    check_clause(text, REL, "## Declared section", clause_after_fence, 1)

    fake_dup_heading = _doc(
        "## Real heading",
        "```",
        "## Real heading",
        "```",
        "body",
        "## Other",
    )
    dup_lines = fake_dup_heading.splitlines()
    start, end = section_span(dup_lines, "## Real heading", REL)
    assert dup_lines[start] == "## Real heading"
    assert dup_lines[end] == "## Other"
    assert "body" in "\n".join(dup_lines[start:end])

    bounded = _doc(
        "## Section with fence",
        "```",
        "# comment",
        "```",
        "more body",
        "## Ends here",
        "tail",
    )
    start, end = section_span(bounded.splitlines(), "## Section with fence", REL)
    lines = bounded.splitlines()
    assert lines[end] == "## Ends here"
    assert "more body" in "\n".join(lines[start:end])
    assert "tail" not in "\n".join(lines[start:end])
