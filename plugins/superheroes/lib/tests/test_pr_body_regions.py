import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PBR = _load("pr_body_regions")


def _marker_body(case_id, marker):
    """Build a PR body placing ``marker`` in the census context named by ``case_id``."""
    if case_id == "column_0":
        return marker + "\n"
    if case_id == "indent_1":
        return " " + marker + "\n"
    if case_id == "indent_2":
        return "  " + marker + "\n"
    if case_id == "indent_3":
        return "   " + marker + "\n"
    if case_id == "indent_4":
        return "    " + marker + "\n"
    if case_id == "inside_fence":
        return "```\n" + marker + "\n```\n"
    if case_id == "inside_pre":
        return "<pre>\n" + marker + "\n</pre>\n"
    if case_id == "inside_details":
        return "<details>\n" + marker + "\n</details>\n"
    if case_id == "blockquote":
        return "> " + marker + "\n"
    if case_id == "list_item":
        return "- " + marker + "\n"
    if case_id == "trailing_whitespace":
        return marker + "   \n"
    if case_id == "other_text_on_line":
        return marker + " extra\n"
    raise ValueError("unknown marker census case: %r" % case_id)


_MARKER_CENSUS_CASES = [
    pytest.param("column_0", True, id="column_0"),
    pytest.param("indent_1", False, id="indent_1"),
    pytest.param("indent_2", False, id="indent_2"),
    pytest.param("indent_3", False, id="indent_3"),
    pytest.param("indent_4", False, id="indent_4"),
    pytest.param("inside_fence", False, id="inside_fence"),
    pytest.param("inside_pre", False, id="inside_pre"),
    pytest.param("inside_details", True, id="inside_details"),
    pytest.param("blockquote", False, id="blockquote"),
    pytest.param("list_item", False, id="list_item"),
    pytest.param("trailing_whitespace", True, id="trailing_whitespace"),
    pytest.param("other_text_on_line", False, id="other_text_on_line"),
]


@pytest.mark.parametrize("region_name", sorted(PBR.REGION_MARKERS))
@pytest.mark.parametrize("case_id,live", _MARKER_CENSUS_CASES)
def test_marker_census(region_name, case_id, live):
    marker = PBR.REGION_MARKERS[region_name]
    body = _marker_body(case_id, marker)
    idx = PBR._find_standalone_marker(body, marker)
    if live:
        assert idx >= 0, "expected live marker for %s/%s" % (region_name, case_id)
    else:
        assert idx < 0, "expected inert marker for %s/%s" % (region_name, case_id)


def test_find_all_standalone_markers_returns_every_live_occurrence():
    marker = PBR.REGION_MARKERS["dod-table"]
    body = marker + "\ncontent\n" + marker + "\n"
    offsets = PBR._find_all_standalone_markers(body, marker)
    assert offsets == [0, len(marker) + 1 + len("content\n")]


def _duplicate_marker_body(marker):
    return (
        marker + "\n"
        "decoy content\n\n"
        + marker + "\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| real row | done | tests/a.py |\n"
    )


def test_read_region_returns_text_when_marker_present():
    body = (
        "<!-- superheroes:advisor-vet -->\n"
        "**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01\n"
    )
    region_text, refusal = PBR.read_region(body, "advisor-vet")
    assert refusal is None
    assert region_text == (
        "**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01"
    )


def test_read_region_returns_none_when_marker_absent():
    body = "## Summary\nNo advisor-vet region in this body.\n"
    region_text, refusal = PBR.read_region(body, "advisor-vet")
    assert region_text is None
    assert refusal is None


def test_read_region_returns_refusal_when_marker_duplicated():
    marker = PBR.REGION_MARKERS["advisor-vet"]
    body = _duplicate_marker_body(marker)
    region_text, refusal = PBR.read_region(body, "advisor-vet")
    assert region_text is None
    assert refusal == "region-marker-duplicated"


def test_read_region_raises_for_unknown_region_name():
    with pytest.raises(ValueError):
        PBR.read_region("body", "not-a-region")


def test_region_start_line_aligns_with_region_text():
    body = (
        "<!-- superheroes:dod-table -->\n"
        "\n"
        "\n"
        "```\n"
        "| fake | done | planted |\n"
        "```\n"
        "| DoD | Status | Evidence |\n"
        "| --- | --- | --- |\n"
        "| real row | done | tests/a.py |\n"
    )
    scan = PBR._context_scan(body)
    region_text, _, region_start_line = PBR._extract_region(
        body, PBR.REGION_MARKERS["dod-table"], scan, "dod-table",
    )
    _, bare = PBR._bare_lines_from_body(body)
    region_lines = region_text.splitlines()
    for i, line in enumerate(region_lines):
        assert bare[region_start_line + i] == line
