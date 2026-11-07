"""#2389 (layer 2 of #2366): the PR-body line scanners of leftover_accepting.py and pr_sheet.py read Markdown line
boundaries (md_fence.split_lines: CRLF, lone CR, LF), never str.splitlines(), and leftover_accepting._visible never
keeps text GitHub renders hidden (md_hidden's reading intersected with the comment cut).

Guards (bite-proof record bite_proofs/i2389_scanner_line_boundaries.md; select one with ``-k test_gN_``):
  G1 test_g1_visible_split_*              _visible's line split
  G2 test_g2_visible_md_hidden_*          _visible's md_hidden intersection (includes the READY regression)
  G3 test_g3_accepting_listed_split_*     accepting_listed's line split
  G4 test_g4_degradations_listed_split_*  degradations_listed's line split
No real gh: every call the vet-slot tests make is faked by test_vet_slot_leftovers_2280's Fake."""
import json
import pathlib

import pytest

import leftover_accepting as la
import md_fence
import md_hidden
import pr_sheet
from test_vet_slot_leftovers_2280 import (  # noqa: F401
    body, record_comment, RECEIPT, F1, ACCEPT_ONLY_F1, write, _gh_on_path)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "md_hidden_github_renders_2366.json"
EOLS = ["\n", "\r", "\r\n"]


def eol(text, ending):
    return text.replace("\n", ending)


def line_count(text):
    return len(md_fence.split_lines(text))


# --- G1: _visible splits on Markdown line endings ---------------------------------------------------------------

def test_g1_visible_split_u2028_does_not_make_a_fence_line():
    # str.splitlines would read ``` as its own line and open a fence that shows the comment under it
    source = "x ```\n<!-- c -->\n"
    assert la._visible(source) == "x ```\n\n"


def test_g1_visible_split_u2028_does_not_make_a_marker_line():
    # str.splitlines would read the marker as a whole line and keep it
    source = "a <!-- superheroes:x -->\n"
    assert la._visible(source) == "a \n"


@pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
def test_g1_visible_split_every_other_str_splitlines_break_is_an_ordinary_character(char):
    source = "x" + char + "```\n<!-- c -->\n"
    out = la._visible(source)
    assert out == "x" + char + "```\n\n"
    assert line_count(out) == line_count(source) == 2


@pytest.mark.parametrize("ending", EOLS)
def test_g1_visible_split_comment_cut_is_the_same_under_every_line_ending(ending):
    source = eol("keep\n<!-- a\nhidden\n-->\nafter\n", ending)
    assert la._visible(source) == eol("keep\n\n\n\nafter\n", ending)
    assert line_count(la._visible(source)) == line_count(source)


@pytest.mark.parametrize("ending", EOLS)
def test_g1_visible_split_a_line_cut_to_nothing_keeps_its_own_terminator(ending):
    source = eol("a <!-- x\nb --> c\nlast <!-- y", ending)
    out = la._visible(source)
    assert out == eol("a \n c\nlast ", ending)
    assert line_count(out) == line_count(source)


@pytest.mark.parametrize("ending", EOLS)
def test_g1_visible_split_a_fence_opens_and_closes_under_every_line_ending(ending):
    source = eol("```\n<!-- shown -->\n```\n<!-- cut -->\nz\n", ending)
    assert la._visible(source) == eol("```\n<!-- shown -->\n```\n\nz\n", ending)


# --- G2: _visible keeps nothing md_hidden does not read VISIBLE ------------------------------------------------

DIV_PLAIN_CLOSER = "<div>\n<!-- a\n\nb -->\n\n"


def hidden_acceptance_body():
    """The layer-1 div_plain_closer shape above the acceptance: GitHub's comment is still open at What we're accepting."""
    accepting = ACCEPT_ONLY_F1 + "\n<!-- close -->\n"
    return body(accepting).replace("A change.\n", "A change.\n\n" + DIV_PLAIN_CLOSER, 1)


def test_g2_visible_md_hidden_drops_an_acceptance_the_comment_cut_alone_would_keep():
    source = hidden_acceptance_body()
    assert md_hidden.scan(source).state_at(source.index("## What we're accepting")) == md_hidden.HIDDEN
    out = la._visible(source)
    assert "f-1" not in out and "What we're accepting" not in out
    assert la._accepting_items(source) == []
    assert line_count(out) == line_count(source)


def test_g2_visible_md_hidden_keeps_the_same_acceptance_when_nothing_is_open():
    source = hidden_acceptance_body().replace(DIV_PLAIN_CLOSER, "")
    out = la._visible(source)
    assert "- f-1 the retry loop never backs off" in out
    assert len(la._accepting_items(source)) == 1


def test_g2_visible_md_hidden_blanks_a_fenced_line_md_hidden_reads_hidden():
    source = "x\n\n" + DIV_PLAIN_CLOSER + "```\nsecret\n```\n<!-- close -->\nafter\n"
    states = dict(md_hidden.scan(source).lines)
    assert states[source.index("secret")] == md_hidden.HIDDEN
    out = la._visible(source)
    assert "secret" not in out and "```" not in out
    assert out.endswith("after\n")
    assert line_count(out) == line_count(source)


def test_g2_visible_md_hidden_keeps_a_marker_line_whatever_md_hidden_reads():
    source = "x\n\n" + DIV_PLAIN_CLOSER + "<!-- superheroes:build-record -->\nafter\n"
    assert md_hidden.scan(source).state_at(source.index("<!-- superheroes:build-record")) == md_hidden.HIDDEN
    assert "<!-- superheroes:build-record -->\n" in la._visible(source)


def test_g2_visible_md_hidden_scan_failure_keeps_only_markers_and_terminators(monkeypatch):
    source = "one\n<!-- superheroes:build-record -->\r\ntwo\r```\nthree\n```\nlast"

    def unsure_everywhere(text):
        starts, at = [], 0
        for item in md_fence.split_lines(text):
            starts.append((at, md_hidden.UNSURE))
            at += len(item)
        return md_hidden.Rendering(starts, (), [(0, "internal error: test")])

    monkeypatch.setattr(la.md_hidden, "scan", unsure_everywhere)
    # one, the marker line (kept whole), two\r, the three fence lines, then `last` (no terminator, so nothing)
    assert la._visible(source) == "\n<!-- superheroes:build-record -->\r\n" + "\r" + "\n\n\n"


def test_g2_visible_md_hidden_a_line_start_md_hidden_does_not_report_reads_as_not_visible(monkeypatch):
    monkeypatch.setattr(la.md_hidden, "scan", lambda text: md_hidden.Rendering([], (), []))
    assert la._visible("one\ntwo\n") == "\n\n"


def test_g2_visible_md_hidden_ready_write_refuses_an_acceptance_hidden_after_a_div_plain_closer(tmp_path):
    comments = [RECEIPT, record_comment([F1])]
    result, fake = write(hidden_acceptance_body(), comments, tmp_path)
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted"
    assert fake.edited == []


def test_g2_visible_md_hidden_ready_write_passes_without_the_div_block(tmp_path):
    comments = [RECEIPT, record_comment([F1])]
    result, fake = write(hidden_acceptance_body().replace(DIV_PLAIN_CLOSER, ""), comments, tmp_path)
    assert result["ok"] is True and len(fake.edited) == 1


def _fixture_rows():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
    return [pytest.param(row["stored"], id="%s-%s" % (row["id"], row["form"])) for row in rows]


@pytest.mark.parametrize("stored", _fixture_rows())
def test_g2_visible_md_hidden_github_render_rows_leave_no_hidden_line_behind(stored):
    out = la._visible(stored)
    source_lines, out_lines = md_fence.split_lines(stored), md_fence.split_lines(out)
    # a last line with no terminator that is cut to nothing leaves "" (no line at all); every other line stays a line
    if len(out_lines) == len(source_lines) - 1 and la._terminator(source_lines[-1]) == "":
        out_lines.append("")
    assert len(out_lines) == len(source_lines)
    rendering = md_hidden.scan(stored)
    offset = 0
    for src, kept in zip(source_lines, out_lines):
        if rendering.state_at(offset) != md_hidden.VISIBLE and not la._MARKER_LINE.match(src):
            assert kept.strip() == "", "a line md_hidden does not read VISIBLE kept text: %r" % (kept,)
            assert kept == la._terminator(src)
        offset += len(src)


# --- G3: accepting_listed splits on Markdown line endings --------------------------------------------------------

ACCEPTING_U2028 = "## What we're accepting\n\n- item one ## Not a heading\n- item two\n"
ACCEPTING_ITEMS = ["item one ## Not a heading", "item two"]


def test_g3_accepting_listed_split_u2028_cannot_make_a_heading_that_ends_the_section():
    assert pr_sheet.accepting_listed(ACCEPTING_U2028) == ACCEPTING_ITEMS


@pytest.mark.parametrize("ending", EOLS)
def test_g3_accepting_listed_split_same_answer_under_every_line_ending(ending):
    assert pr_sheet.accepting_listed(eol(ACCEPTING_U2028, ending)) == ACCEPTING_ITEMS


@pytest.mark.parametrize("ending", EOLS)
def test_g3_accepting_listed_split_a_real_heading_still_ends_the_section(ending):
    source = eol("## What we're accepting\n\n- one\n## Next\n- two\n", ending)
    assert pr_sheet.accepting_listed(source) == ["one"]


# --- G4: degradations_listed splits on Markdown line endings -----------------------------------------------------

DEGRADATIONS_U2028 = "<!-- superheroes:degradations -->\n- [harmless] note ## End\n- [costly] later\n"
DEGRADATIONS_LISTED = [("harmless", "note ## End"), ("costly", "later")]


def test_g4_degradations_listed_split_u2028_cannot_make_a_heading_that_ends_the_list():
    assert pr_sheet.degradations_listed(DEGRADATIONS_U2028) == DEGRADATIONS_LISTED


@pytest.mark.parametrize("ending", EOLS)
def test_g4_degradations_listed_split_same_answer_under_every_line_ending(ending):
    assert pr_sheet.degradations_listed(eol(DEGRADATIONS_U2028, ending)) == DEGRADATIONS_LISTED


def test_g4_degradations_listed_split_costly_unlisted_sees_the_costly_bullet():
    assert pr_sheet.costly_unlisted(DEGRADATIONS_U2028) == [("costly", "later")]


# --- fail-closed edges kept -------------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, 5, b"x", ["a"]])
def test_edge_a_non_string_body_lists_nothing(value):
    assert pr_sheet.accepting_listed(value) == []
    assert pr_sheet.degradations_listed(value) == []
    assert la._accepting_items(value) == []


def test_edge_an_empty_body_has_no_lines():
    assert la._visible("") == ""
    assert pr_sheet.accepting_listed("") == [] and pr_sheet.degradations_listed("") == []
