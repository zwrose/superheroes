"""Tests for md_hidden (#2366): what GitHub hides in a PR body.

The oracle is ``fixtures/md_hidden_github_renders_2366.json``: GitHub's own render of each shape. The named-shape tests run
``scan`` on the exact body; the guarded elements (G1-G12) each have a ``test_guard_gN_*`` test whose body is built so that
removing the guard changes the verdict."""
import html
import json
import os
import re
import sys
from html.parser import HTMLParser

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import md_fence  # noqa: E402
import md_hidden as md  # noqa: E402

V, H, U = md.VISIBLE, md.HIDDEN, md.UNSURE

_FIXTURE = os.path.join(_HERE, "fixtures", "md_hidden_github_renders_2366.json")
with open(_FIXTURE, encoding="utf-8") as _fh:
    _ROWS = json.load(_fh)["rows"]
_ROW_BY_KEY = {(r["id"], r["form"]): r for r in _ROWS}

OWNER = {"builder": "## What's changing, and why", "bot": "## Advisor vet"}


def _offset(body, line):
    """The offset of the line of ``body`` that is exactly ``line``."""
    at = 0
    for item in md_fence.split_lines(body):
        if item.rstrip("\r\n") == line:
            return at
        at += len(item)
    raise AssertionError("no line %r in %r" % (line, body))


def _state(body, line):
    return md.scan(body).state_at(_offset(body, line))


def _visible_texts(body):
    return [text for _, text, state in md.scan(body).headings if state == V]


def _reads(body, heading, expected):
    """The heading line reads ``expected``; when HIDDEN its text is also not a VISIBLE entry of ``headings``."""
    got = _state(body, heading)
    assert got == expected, "heading %r reads %s, expected %s; unsure=%r" % (heading, got, expected, md.scan(body).unsure)
    if expected == H:
        text = heading.lstrip("#").strip()
        assert text not in _visible_texts(body)


# --- 1. The fixture oracle -----------------------------------------------------------------------------------------

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


class _GitHubHeadings(HTMLParser):
    """The text of every heading element of GitHub's render, with whether it is nested in a quote, list or footnotes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []  # (text, nested, generated)
        self._quote = 0
        self._item = 0
        self._sections = []  # one bool per open <section>: is it the footnotes section
        self._cur = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "blockquote":
            self._quote += 1
        elif tag == "li":
            self._item += 1
        elif tag == "section":
            self._sections.append("footnotes" in (attrs.get("class") or "") or "data-footnotes" in attrs)
        elif tag in _HEADING_TAGS:
            self._cur = []

    def handle_endtag(self, tag):
        if tag == "blockquote":
            self._quote -= 1
        elif tag == "li":
            self._item -= 1
        elif tag == "section" and self._sections:
            self._sections.pop()
        elif tag in _HEADING_TAGS and self._cur is not None:
            text = "".join(self._cur).strip()
            in_footnotes = any(self._sections)
            generated = in_footnotes and text == "Footnotes"
            self.found.append((text, self._quote > 0 or self._item > 0 or in_footnotes, generated))
            self._cur = None

    def handle_data(self, data):
        if self._cur is not None:
            self._cur.append(data)


def _github_headings(rendered):
    parser = _GitHubHeadings()
    parser.feed(rendered)
    parser.close()
    return [(text, nested) for text, nested, generated in parser.found if not generated]


def _norm(text):
    """Heading text compared as GitHub shows it: md_hidden keeps the inline Markdown as written (WO-2 normalises), so
    the oracle drops image syntax, unwraps links and backslash escapes, and collapses whitespace on both sides."""
    text = html.unescape(text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\\(\W)", r"\1", text)
    return " ".join(text.split())


_SETEXT_LINE = re.compile(r" {0,3}(?:=+|-+) *\Z")
_FENCE_LINE = re.compile(r" {0,3}(?:`{3,}|~{3,})")


def _holds_setext(stored):
    lines = [item.rstrip("\r\n") for item in md_fence.split_lines(stored)]
    for i in range(1, len(lines)):
        if _SETEXT_LINE.match(lines[i]) and lines[i - 1].strip() and not _FENCE_LINE.match(lines[i - 1]):
            return True
    return False


_ORACLE = [pytest.param(r, id="%s-%s" % (r["id"], r["form"])) for r in _ROWS]


@pytest.mark.parametrize("row", _ORACLE)
def test_oracle_visible_headings_are_shown_by_github(row):
    """(a) md_hidden never reports as VISIBLE a heading GitHub does not show (same order)."""
    rendering = md.scan(row["stored"])
    mine = [_norm(text) for _, text, state in rendering.headings if state == V]
    shown = [_norm(text) for text, _ in _github_headings(row["html"])]
    remaining = iter(shown)
    for text in mine:
        assert any(text == s for s in remaining), "visible heading %r not shown by GitHub: mine=%r github=%r" % (
            text, mine, shown)


# The rows whose scan holds an unsure point, so (b) does not apply. Pinned so the skip set cannot widen unnoticed.
_UNSURE_SHAPES = frozenset({
    "footnote_div", "div_open_then_inline_comment", "div_open_then_inline_dashdash", "textarea_block",
    "script_attr_opener", "unclosed_attr", "div_title_unclosed_mid", "source_tag", "search_tag",
    "fence_tilde_256_cap", "fence_tick_256_cap", "fence_tilde_300_close_256",
    # vet 845 F2: a line that starts inside a tag or a bogus comment reads unsure (the declaration and processing-
    # instruction blocks; the stored CDATA row holds no such line, only the sent form does).
    "decl_block", "pi_block",
    # park ruling option (a): a reference definition's range holds the next line's backtick and the block holds a `<`,
    # so it reads unsure (the accepted refusal cost)
    "linkref_div",
})


def test_oracle_rows_with_an_unsure_point_are_the_expected_ones():
    got = {r["id"] for r in _ROWS if md.scan(r["stored"]).unsure}
    assert got == _UNSURE_SHAPES
    for r in _ROWS:  # both forms of a shape agree
        assert bool(md.scan(r["stored"]).unsure) == (r["id"] in _UNSURE_SHAPES), (r["id"], r["form"])


@pytest.mark.parametrize("row", _ORACLE)
def test_oracle_visible_headings_equal_github_top_level(row):
    """(b) with no unsure point, the VISIBLE headings equal GitHub's top-level headings. Skipped for a body holding a
    setext heading (outside ``headings`` by contract).

    A heading GitHub shows nested in a blockquote or list item whose Markdown is top-level (a comment opened in the
    container swallowed its closing tag: ``quote_opener_ends``, ``quote_tab_div``, ``list_div_opener``) is matched
    against md_hidden's heading but not required of it, so the alignment below is: every md_hidden VISIBLE heading is
    a GitHub heading (in order), and every GitHub heading not matched is nested."""
    if _holds_setext(row["stored"]):
        pytest.skip("setext heading in the body: setext headings are outside headings by contract")
    rendering = md.scan(row["stored"])
    if rendering.unsure:
        pytest.skip("the parse is unsure (%s)" % rendering.unsure[0][1])
    mine = [_norm(text) for _, text, state in rendering.headings if state == V]
    shown = [(_norm(text), nested) for text, nested in _github_headings(row["html"])]
    matched = set()
    at = 0
    for text in mine:
        while at < len(shown) and shown[at][0] != text:
            at += 1
        assert at < len(shown), "visible heading %r not shown by GitHub: mine=%r github=%r" % (text, mine, shown)
        matched.add(at)
        at += 1
    missed = [shown[i] for i in range(len(shown)) if i not in matched and not shown[i][1]]
    assert missed == [], "GitHub shows top-level headings md_hidden calls hidden: %r" % (missed,)


# --- 2. Named shapes, through scan on the exact body ---------------------------------------------------------------

_HIDDEN_SHAPES = [
    "pre_quoted_opener", "div_escaped_closer", "div_plain_closer",
    "false_fence_u2028", "false_fence_nel", "false_fence_ff",
    "div_u2028_then_quoted", "div_nel_then_quoted", "div_ff_then_quoted",
    "crlf_div", "cr_div", "cdata_block",
]


@pytest.mark.parametrize("form", ["builder", "bot"])
@pytest.mark.parametrize("shape", _HIDDEN_SHAPES)
def test_named_shape_hides_the_owner_heading(shape, form):
    """The sent body (the egress normalised U+2028, U+0085, form feed, CR and <![CDATA[ in transit)."""
    row = _ROW_BY_KEY[(shape, form)]
    # vet 845 F2: the line after "<![CDATA[" starts inside a bogus comment, which reads UNSURE (a ">" early in the line
    # can end the state), so the CDATA shape's owner heading is UNSURE; every other shape is HIDDEN.
    _reads(row["sent"], OWNER[form], U if shape == "cdata_block" else H)


@pytest.mark.parametrize("form", ["builder", "bot"])
def test_named_shape_inline_code_opener_keeps_the_owner_heading_visible(form):
    row = _ROW_BY_KEY[("inline_code_opener", form)]
    _reads(row["sent"], OWNER[form], V)
    if form == "builder":
        assert "Follow-ups for the advisor" in _visible_texts(row["sent"])  # the <details> build record heading


@pytest.mark.parametrize("shape", ["escaped_opener", "control_plain", "control_closed_comment"])
@pytest.mark.parametrize("form", ["builder", "bot"])
def test_named_shape_controls_keep_the_owner_heading_visible(shape, form):
    _reads(_ROW_BY_KEY[(shape, form)]["sent"], OWNER[form], V)


@pytest.mark.parametrize("form", ["builder", "bot"])
def test_named_shape_unclosed_comment_hides_until_its_raw_closer(form):
    _reads(_ROW_BY_KEY[("control_unclosed_comment", form)]["sent"], OWNER[form], H)


def test_false_fence_is_one_html_block_not_a_fence():
    """GitHub sees no fence after U+2028: the issue body's shape. ``split_lines`` is the line source."""
    for sep in ("\u2028", "\u0085", "\f"):
        body = "intro\n\n<!-- a -->" + sep + "~~~\n<!--\n\n## What's changing, and why\n"
        _reads(body, "## What's changing, and why", H)


# --- 3. split_lines ------------------------------------------------------------------------------------------------

def test_split_lines_three_terminators_keep_their_terminator():
    assert md_fence.split_lines("a\r\nb\rc\nd") == ["a\r\n", "b\r", "c\n", "d"]


def test_split_lines_last_line_without_terminator_and_empty():
    assert md_fence.split_lines("a\nb") == ["a\n", "b"]
    assert md_fence.split_lines("a\n") == ["a\n"]
    assert md_fence.split_lines("") == []
    assert md_fence.split_lines("\n\n") == ["\n", "\n"]
    assert md_fence.split_lines("\r\n\r") == ["\r\n", "\r"]


@pytest.mark.parametrize("char", ["\u2028", "\u2029", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
def test_split_lines_keeps_str_splitlines_only_characters_inside_a_line(char):
    text = "a" + char + "b\nc"
    assert len(text.splitlines()) == 3  # str.splitlines breaks on it; Markdown does not
    assert md_fence.split_lines(text) == ["a" + char + "b\n", "c"]


@pytest.mark.parametrize("char", ["\u2028", "\u2029", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
    """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
    body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
    rendering = md.scan(body)
    assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
    _reads(body, "## H", H)


# --- 4. Unsure points: UNSURE from the line on, VISIBLE before it --------------------------------------------------

def _off(body, index):
    """The offset of line number ``index`` (0-based) of ``body``."""
    return sum(len(item) for item in md_fence.split_lines(body)[:index])


def _check_unsure(body, index):
    """Every line before line ``index`` reads VISIBLE, every line from it on UNSURE, and a point is recorded there."""
    rendering = md.scan(body)
    at = _off(body, index)
    assert any(offset == at for offset, _ in rendering.unsure), rendering.unsure
    assert rendering.unsure[0][0] == at, rendering.unsure
    for offset, state in rendering.lines:
        assert state == (V if offset < at else U), (offset, state, rendering.lines, rendering.unsure)


def _no_unsure(body, heading_state=V, heading="## H"):
    rendering = md.scan(body)
    assert rendering.unsure == ()
    assert _state(body, heading) == heading_state


def test_unsure_footnote_definition():
    _check_unsure("a\n\n[^1]: note\n\n## H\n", 2)  # G7 (also guarded below)


def test_unsure_footnote_definition_inside_a_quote_and_not_a_link_label():
    _check_unsure("a\n\n> [^note]: text\n\n## H\n", 2)
    # vet-849 amendment: a block whose first line starts with `[` and holds `]:` reads unsure; GitHub shows this line, so this is a disclosed over-refusal
    _check_unsure("a\n\n[^ 1]: not a footnote\n\n## H\n", 2)


@pytest.mark.parametrize("row", [
    pytest.param("<span>", id="angle"),
    pytest.param("- item", id="list-marker"),
    pytest.param("1. item", id="ordered-marker"),
    pytest.param("===", id="setext-underline"),
])
def test_unsure_gfm_table_row_after_the_delimiter_row(row):
    _check_unsure("x\n\n| a |\n| - |\n" + row + "\n\n## H\n", 4)


def test_unsure_gfm_table_ordinary_rows_stay_decided():
    _no_unsure("x\n\n| a |\n| - |\n| b |\nplain\n\n## H\n")
    _no_unsure("x\n\n| a | b |\n| - | - |\n| c | d |\n\n## H\n")


def test_unsure_table_rule_needs_a_delimiter_row_with_a_pipe():
    _no_unsure("x\n\n| a |\n---\n\n## H\n")  # a setext heading, not a table


@pytest.mark.parametrize("fence", ["~", "`"])
def test_unsure_fence_run_longer_than_255_opening(fence):
    run = fence * 256
    _check_unsure("a\n\n" + run + "\nx\n" + run + "\n\n## H\n", 2)


@pytest.mark.parametrize("fence", ["~", "`"])
def test_unsure_fence_run_longer_than_255_closing(fence):
    _check_unsure("a\n\n" + fence * 3 + "\nx\n" + fence * 256 + "\n\n## H\n", 4)


@pytest.mark.parametrize("fence", ["~", "`"])
def test_fence_run_of_exactly_255_is_decided(fence):
    run = fence * 255
    _no_unsure("a\n\n" + run + "\nx\n" + run + "\n\n## H\n")


@pytest.mark.parametrize("tag", [
    "<textarea>", "<search>", "<source>", "<SOURCE src=\"x\">", "<search/>", "<textarea", "<Textarea\t>", "  <source>",
])
def test_unsure_version_dependent_tag_line(tag):
    _check_unsure("a\n\n" + tag + "\n<!--\n\n## H\n", 2)


def test_unsure_version_dependent_tag_names_are_whole_names():
    _no_unsure("a\n\n<sources>\nx\n\n## H\n")
    _no_unsure("a\n\n<searchbar>\nx\n\n## H\n")


@pytest.mark.parametrize("name", [
    "script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext", "SCRIPT", "Title",
])
def test_unsure_tagfilter_name_in_an_html_block(name):
    _check_unsure("a\n\n<div>\n<%s x>\n\n## H\n" % name, 3)


@pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
def test_unsure_tagfilter_name_in_paragraph_text(name):
    _check_unsure("a\n\ntext </%s>\n\n## H\n" % name, 2)


def test_unsure_tagfilter_in_a_heading_and_other_tags_decided():
    _check_unsure("a\n\n## <title>\n\n## H\n", 2)
    _no_unsure("a\n\n<div>\n<span x>\n\n## H\n")


def test_unsure_html_block_ending_inside_a_tag():
    body = "<div title=\"\n\n## H\n"
    # vet 854: a line holding an HTML-block tag with an attribute value reads U, on that line only
    rendering = md.scan(body)
    assert rendering.unsure[0][0] == _off(body, 1)  # the blank line that ended the block: from there the rest of the body is swallowed
    assert [s for _, s in rendering.lines] == [U, U, U]
    assert "tag" in md.scan(body).unsure[0][1]


def test_unsure_html_block_ending_inside_a_bogus_comment():
    # vet 854: in an HTML block, "</" followed by anything but an ASCII letter or ">" is a bogus comment to its first ">": the "</ " line reads H
    body = "x\n\n<div>\n</ \n\n## H\n"
    rendering = md.scan(body)
    assert rendering.unsure[0][0] == _off(body, 4)
    assert [s for _, s in rendering.lines] == [V, V, V, H, U, U]


def test_unsure_html_block_ending_inside_a_tag_at_the_end_of_the_body():
    rendering = md.scan("x\n\n<div title=\"")
    assert [offset for offset, _ in rendering.unsure] == [len("x\n\n<div title=\"")]
    # vet 854: a line holding an HTML-block tag with an attribute value reads U, on that line only
    assert [state for _, state in rendering.lines] == [V, V, U]


def test_unsure_comment_state_paragraph_holding_a_lt_and_a_later_closer():
    body = "<div>\n<!-- a\n\nb <!-- c --> e\n\n## H\n"
    rendering = md.scan(body)
    # final review: the "<!-- a" line holds only the comment's text, which GitHub hides, so it reads hidden
    assert [state for _, state in rendering.lines] == [V, H, H, U, U, U]
    assert rendering.unsure[0][0] == _off(body, 3)
    body = "<div>\n<!-- a\n\nb <i --!> e\n\n## H\n"
    assert [state for _, state in md.scan(body).lines] == [V, H, H, U, U, U]


def test_unsure_comment_state_inline_rule_needs_comment_state_and_a_lt_before_the_closer():
    _no_unsure("<div>\n<!-- a\n\nb --> <i> e\n\n## H\n", heading_state=H)
    _no_unsure("<div>\n<!-- a\n\n\\-->\n\n## H\n", heading_state=H)
    _no_unsure("x\n\nb <!-- c --> e\n\n## H\n")  # in the data state an inline comment is harmless
    _no_unsure("<div>\n<!-- a -->\n\nb <!-- c --> e\n\n## H\n")


def test_unsure_comment_state_inline_rule_covers_a_heading():
    body = "<div>\n<!-- a\n\n## b <i> -->\n\n## H\n"
    assert md.scan(body).unsure[0][0] == _off(body, 3)


def test_unsure_inline_processing_instruction_ended_early_by_html():
    _check_unsure("x <? a > <!-- b ?>\n\n## H\n", 0)
    _no_unsure("x <? a ?> y\n\n## H\n")


def test_unsure_rendering_shape_and_ordering():
    rendering = md.scan("a\n\n[^1]: n\n\n<textarea>\n\n## H\n")
    assert isinstance(rendering.unsure, tuple) and len(rendering.unsure) >= 2
    assert list(rendering.unsure) == sorted(rendering.unsure)
    assert all(isinstance(offset, int) and isinstance(why, str) and why for offset, why in rendering.unsure)
    assert isinstance(rendering.lines, tuple) and isinstance(rendering.headings, tuple)


def test_unsure_is_sticky_to_the_end_of_the_body():
    body = "a\n\n[^1]: n\n\n<!-- c -->\n\n## H\n"
    assert [state for _, state in md.scan(body).lines] == [V, V, U, U, U, U, U]


def test_internal_failure_reads_unsure_never_visible(monkeypatch):
    def boom(_body):
        raise RuntimeError("boom")

    monkeypatch.setattr(md, "_scan", boom)
    rendering = md.scan("a\n\n## H\n")
    assert [state for _, state in rendering.lines] == [U, U, U]
    assert rendering.unsure == ((0, "internal error: RuntimeError"),)


# --- 5. Edges E1-E10 -----------------------------------------------------------------------------------------------

def test_e1_empty_body():
    rendering = md.scan("")
    assert rendering.lines == () and rendering.headings == () and rendering.unsure == ()


def test_e2_last_line_without_a_terminator_is_a_line():
    rendering = md.scan("a\n## H")
    assert rendering.lines == ((0, V), (2, V))
    assert rendering.headings == ((2, "H", V),)
    assert rendering.state_at(2) == V


def test_e3_lone_cr_and_crlf_are_line_boundaries_and_unicode_breaks_are_not():
    rendering = md.scan("a\r\n## H\r## I\n ## J")
    assert [offset for offset, _ in rendering.lines] == [0, 3, 8, 13]
    assert [text for _, text, _ in rendering.headings] == ["H", "I"]  # " ## J" is paragraph text


def test_e4_unclosed_fence_runs_to_the_end_of_the_document_and_of_its_container():
    rendering = md.scan("```\n<!--\n## H\n")
    assert rendering.headings == () and {state for _, state in rendering.lines} == {V}
    rendering = md.scan("> ~~~\n> <!--\n\n## H\n")  # the quote ends at the blank line, the fence with it
    assert rendering.headings == ((_off("> ~~~\n> <!--\n\n## H\n", 3), "H", V),)
    assert md.scan("<div>\n## H\n").headings == ()  # an unclosed HTML block runs to the end too


def test_e5_comment_opened_in_a_container_that_ends_stays_open():
    _reads("> <!--\n\n## H\n", "## H", H)
    _reads("- <div>\n  <!--\n\n## H\n", "## H", H)
    _reads("> <div>\n> <!--\n\nx\n\n## H\n", "## H", H)


def test_e6_unclosed_comment_runs_to_the_end_of_the_body():
    body = "<!--\n\n## H\n\ntext\n\n> quote\n\n- item\n"
    states = [state for _, state in md.scan(body).lines]
    assert states == [V] + [H] * 8
    assert md.scan(body).headings == ()  # the whole rest is the unclosed comment block's own content


@pytest.mark.parametrize("opener", ["<pre>", "<?x", "<!X", "<![CDATA["])
def test_e7_block_whose_end_never_comes_runs_to_the_end_of_its_container(opener):
    body = opener + "\n\n## H\n"
    rendering = md.scan(body)
    assert rendering.headings == ()  # the heading is inside the block: no headings shown
    if opener == "<pre>":
        assert rendering.unsure == () and {state for _, state in rendering.lines} == {V}


def test_e7_the_block_ends_where_its_container_ends():
    body = "> <pre>\n> x\n\n## H\n"
    assert md.scan(body).headings == ((_off(body, 3), "H", V),)


def test_e8_indented_opener_is_code_not_a_comment():
    body = "    <!--\n\n## H\n"
    assert md.scan(body).headings == ((_off(body, 2), "H", V),)
    body = "\t<!--\n\n## H\n"  # a tab is four columns
    assert md.scan(body).headings == ((_off(body, 2), "H", V),)
    _reads("x\n\n   <!--\n\n## H\n", "## H", H)  # three spaces still open the comment


def test_e9_state_at_an_offset_that_is_not_a_line_start():
    rendering = md.scan("ab\ncd\n")
    assert rendering.state_at(0) == V and rendering.state_at(3) == V
    for bad in (1, 2, 4, 6, 7, -1, 100, "0", None, 1.0):
        with pytest.raises(ValueError):
            rendering.state_at(bad)
    with pytest.raises(ValueError):
        md.scan("").state_at(0)


@pytest.mark.parametrize("bad", [b"abc", None, 3, ["a"], ("a",), 1.5, bytearray(b"a")])
def test_e10_scan_rejects_a_non_str_argument(bad):
    with pytest.raises(TypeError):
        md.scan(bad)


# --- Comment pass and block structure ------------------------------------------------------------------------------

def test_closed_comment_hides_nothing_and_abrupt_comments_are_complete():
    _no_unsure("<!-- a -->\n\n## H\n")
    _no_unsure("<div>\n<!--> x\n\n## H\n")
    _no_unsure("<div>\n<!---> x\n\n## H\n")
    _no_unsure("<div>\n<!-- a --!> b\n\n## H\n")  # GitHub closes a comment on --!>
    _no_unsure("<div>\n<!---->\n\n## H\n")


def test_comment_closes_on_the_first_closer_and_a_second_opener_inside_is_inert():
    _no_unsure("<div>\n<!-- a <!-- b -->\n\n## H\n")
    _reads("<div>\n<!-- a\n\n## H\n", "## H", H)


def test_comment_opener_inside_an_attribute_value_is_not_a_comment():
    _no_unsure("x\n\n<div title=\"<!--\">\n\n## H\n")
    _no_unsure("x\n\n<div title='<!--'>\n\n## H\n")


def test_comment_opener_in_text_code_and_escapes_is_not_a_comment():
    _no_unsure("x `<!--` y\n\n## H\n")
    _no_unsure("x \\<!-- y\n\n## H\n")
    _no_unsure("```\n<!--\n```\n\n## H\n")
    _no_unsure("<https://example.invalid>\n`<!--`\n\n## H\n")


def test_html_comment_block_hides_its_own_lines_until_the_closer():
    body = "<!--\n\n## A\n-->\n\n## B\n"
    assert [state for _, state in md.scan(body).lines] == [V, H, H, H, V, V]
    assert md.scan(body).headings == ((_off(body, 5), "B", V),)


def test_heading_in_the_comment_state_is_listed_as_hidden():
    body = "<div>\n<!-- a\n\n## H\n"
    assert md.scan(body).headings == ((_off(body, 3), "H", H),)


def test_headings_are_direct_children_of_the_document_only():
    body = "> ## Q\n\n- ## L\n\n  ## M\n\n## D\n"
    assert [text for _, text, _ in md.scan(body).headings] == ["D"]


@pytest.mark.parametrize("line,text", [
    ("## Title", "Title"),
    ("##" + " " * 3 + "Title" + " " * 3 + "##" + " " * 2, "Title"),
    ("## Title #notclosing", "Title #notclosing"),
    ("## Title \\##", "Title \\##"),
    ("### ###", ""),
    ("#", ""),
    ("   # indented", "indented"),
    ("## <!-- x --> other", "other"),
    ("## a <b>c</b> d", "a c d"),
    ("## <!-- open without closer", "<!-- open without closer"),
    ("## x<!-- a --!>y", "xy"),
    ("## ![alt](u)", "![alt](u)"),
    ("## [text](u)", "[text](u)"),
    ("###### six", "six"),
])
def test_heading_text(line, text):
    rendering = md.scan(line + "\n")
    assert [t for _, t, _ in rendering.headings] == [text]


@pytest.mark.parametrize("line", ["#hashtag", "####### seven", "    ## code", "\\## escaped", "## nbsp"])
def test_not_an_atx_heading(line):
    assert md.scan(line + "\n").headings == ()


def test_setext_headings_are_not_in_headings_and_do_not_end_the_comment_state():
    assert md.scan("Title\n=====\n\n## H\n").headings == ((_off("Title\n=====\n\n## H\n", 3), "H", V),)
    assert [t for _, t, _ in md.scan("Title\n---\n").headings] == []
    # vet 854: open a comment first
    body = "<div>\n<!-- a\n\nTitle\n=====\n\n## H\n"
    assert [s for _, s in md.scan(body).lines][3:] == [H, H, H, H]


def test_tab_expansion_counts_columns_from_the_line_start():
    _reads(">\t<div>\n>\t`<!--`\n\n## H\n", "## H", H)
    _no_unsure("a\tb\n\n## H\n")


def test_list_item_with_html_block_and_lazy_text():
    _reads("- <div>\n  <!--\n\n## H\n", "## H", H)
    _reads("- a\n<!--\n\n## H\n", "## H", H)  # a type-2 start interrupts the item's paragraph, ending the list
    _reads("- a\n  <!-- b\n\n## H\n", "## H", H)  # a type-2 start interrupts the item's paragraph too
    _no_unsure("- a\n  x <!-- b\n\n## H\n")  # mid-line inside the item's paragraph it is text


def test_blockquote_lazy_paragraph_continuation_is_not_a_block_start():
    _no_unsure("> a\n<span>\n\n## H\n")


# --- Guarded elements G1-G12: the discriminating shape for each ----------------------------------------------------

def test_guard_g1_raw_html_block_content_opens_a_comment():
    _reads("x\n\n<pre>\n<!--\n</pre>\n\n## H\n", "## H", H)
    _reads("x\n\n<pre>\n\n`<!--`\n</pre>\n\n## H\n", "## H", H)
    _reads("x\n\n<div>\n`<!--`\n\n## H\n", "## H", H)


def test_guard_g2_escaped_closer_in_a_paragraph_does_not_close_a_comment():
    _reads("x\n\n<div>\n<!-- a\n\n\\-->\n\n## H\n", "## H", H)
    _reads("x\n\n<div>\n<!-- a\n\nb -->\n\n## H\n", "## H", H)
    _reads("x\n\n<div>\n<!-- a\n\n`-->`\n\n## H\n", "## H", H)


def test_guard_g3_split_lines_is_the_line_source():
    body = "x\n\n<!-- a --> ~~~\n<!--\n\n## H\n"
    _reads(body, "## H", H)


def test_guard_g4_comment_survives_the_end_of_its_container():
    _reads("x\n\n> <!--\n\n## H\n", "## H", H)
    _reads("x\n\n- <div>\n  <!--\n\n## H\n", "## H", H)


@pytest.mark.parametrize("fence", ["~", "`"])
def test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible(fence):
    run = fence * 256
    body = "a\n\n" + run + "\nx\n" + run + "\n\n## H\n"
    assert _state(body, "## H") == U
    assert _state(body, "a") == V
    body = "a\n\n" + fence * 3 + "\nx\n" + run + "\n\n## H\n"
    assert _state(body, "## H") == U
    assert _state(body, "x") == V


@pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
    body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
    assert _state(body, "## H") == U
    assert _state(body, "<div title=\"x\">") == U  # vet 854: a line holding an HTML-block tag with an attribute value reads U


def test_guard_g7_footnote_definition_reads_unsure():
    body = "x[^1]\n\n[^1]: <div>\n    `<!--`\n\n## H\n"
    assert _state(body, "## H") == U
    assert _state(body, "x[^1]") == V


def test_guard_g8_table_row_reads_unsure():
    body = "| a |\n| - |\n<span>\nx <!--\n\n## H\n"
    assert _state(body, "## H") == U
    assert _state(body, "| - |") == V


def test_guard_g9_comment_state_inline_closer_reads_unsure():
    body = "<div>\n<!-- a\n\nb <!-- c --> e\n\n## H\n"
    assert _state(body, "## H") == U
    assert _state(body, "<!-- a") == H  # final review: the line holds only hidden comment text


def test_guard_g10_block_ending_inside_a_tag_reads_unsure():
    body = "x\n\n<div title=\"\n\n## H\n"
    assert _state(body, "## H") == U
    assert _state(body, "x") == V


def test_guard_g11_type7_cannot_interrupt_a_paragraph():
    body = "a\n<span>\nx <!--\n\n## H\n"
    assert _state(body, "## H") == V
    assert md.scan(body).unsure == ()
    # alone, the same line does start a type-7 block, whose raw content holds the opener
    _reads("<span>\nx <!--\n\n## H\n", "## H", H)
    # a line that starts a block of its own does interrupt the paragraph
    _reads("a\n<div>\nx <!--\n\n## H\n", "## H", H)


def test_guard_g12_type4_needs_an_uppercase_letter():
    assert _state("x\n\n<!x\nfoo > <!--\n\n## H\n", "## H") == V  # lowercase: paragraph text, GitHub shows no block
    # uppercase: a declaration block; vet 845 F2 reads its `## H` UNSURE (a line starting inside a bogus comment)
    assert _state("x\n\n<!X\nfoo > <!--\n\n## H\n", "## H") == U


# --- Review round 1 (PR #2390): cmark whitespace, closing version tags, a leading byte-order mark ------------------

@pytest.mark.parametrize("ws", ["\f", "\v"], ids=["formfeed", "vtab"])
@pytest.mark.parametrize("shape", [
    "a\n<div{ws}>\nx <!--\n\n## H\n",                 # type 6 interrupting a paragraph
    "a\n<pre{ws}>\nx <!--\n</pre>\n\n## H\n",          # type 1 interrupting a paragraph
    "<span{ws}class=\"c\">\nx <!--\n\n## H\n",          # type 7: whitespace before an attribute
    "<span class{ws}={ws}\"c\"{ws}>\nx <!--\n\n## H\n",  # type 7: whitespace around = and before >
    "</span{ws}>\nx <!--\n\n## H\n",                   # type 7: a closing tag
], ids=["t6", "t1", "t7-attr", "t7-eq", "t7-close"])
def test_review_r1_form_feed_and_vertical_tab_are_tag_whitespace(shape, ws):
    _reads(shape.format(ws=ws), "## H", H)


@pytest.mark.parametrize("tag", ["source", "search", "textarea"])
def test_review_r1_a_closing_version_tag_reads_unsure(tag):
    body = "a\n</%s>\nx <!--\n\n## H\n" % tag
    assert _state(body, "## H") == U
    assert _state(body, "a") == V


def test_review_r1_a_leading_byte_order_mark_is_skipped():
    _reads("﻿<!--\n\n## H\n", "## H", H)
    # only the document's first character: a BOM at the start of a later line is ordinary text
    assert _state("x\n\n﻿<!--\n\n## H\n", "## H") == V


# --- Vet 845 fix leg (F1-F4): places GitHub hides text and the head read VISIBLE ------------------------------------
# Every expectation below was checked against the vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``.

_F1_TAGS = ["</pre>", "</PRE>", "</pre >", "<pre/>"]
_F1_SHAPES = {
    "top": "x\n\n{tag}\nx <!--\n\n## H\n",
    "item": "- x\n\n  {tag}\n  x <!--\n\n## H\n",
    "quote": "> {tag}\n> x <!--\n\n## H\n",
}


@pytest.mark.parametrize("tag", _F1_TAGS, ids=["close", "CLOSE", "close-space", "selfclose"])
@pytest.mark.parametrize("where", ["top", "item", "quote"])
def test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block(tag, where):
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid everything below the ``x <!--``
    line. cmark-gfm's type-7 scanner has no script/style/pre exclusion."""
    body = _F1_SHAPES[where].format(tag=tag)
    got = _state(body, "## H")
    assert got != V, "## H reads VISIBLE in %r; unsure=%r" % (body, md.scan(body).unsure)
    if where == "top":
        _reads(body, "## H", H)


def test_vet845_f1_the_builder_body_shape_does_not_read_visible():
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid ``## What we're accepting``."""
    body = (
        "## What's changing, and why\n\nText.\n\n</pre>\nQuotes `<!--` in code.\n\n"
        "## What we're accepting\n\nNone.\n"
    )
    assert _state(body, "## What we're accepting") != V


@pytest.mark.parametrize("name", ["script", "style"])
def test_vet845_f1_a_closing_script_or_style_tag_alone_reads_unsure(name):
    """The tagfilter rule, unchanged and pinned: the line and every later line read UNSURE (vet 845 receipt on PR #2390,
    comment 6709845874, ``POST /markdown``: GitHub escapes these tags)."""
    body = "a\n\n</%s>\nb\n" % name
    assert _state(body, "a") == V
    assert _state(body, "</%s>" % name) == U
    assert _state(body, "b") == U


def test_vet845_f2_a_line_inside_an_attribute_value_of_the_bot_path_reads_unsure():
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub put the marker and the verdict line
    inside the ``title`` attribute (hidden); the head read them VISIBLE."""
    body = 'Bumps x.\n\n## Advisor vet\n<div title="a\n<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abc\n">\n'
    assert _state(body, "<!-- superheroes:advisor-vet -->") == U
    assert _state(body, "**Verdict: READY** · abc") == U


def test_vet845_f2_a_line_inside_an_open_bogus_comment_reads_unsure_never_hidden():
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``after`` (the ``>`` ended the
    bogus comment) - so neither line may read HIDDEN, and ``middle`` must not read VISIBLE."""
    body = "<div>\n<? a\nmiddle\n> after\n</div>\n"
    assert _state(body, "middle") == U
    assert _state(body, "> after") == U


def test_vet845_f2_a_line_inside_an_unclosed_attribute_value_reads_unsure():
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid ``middle`` (inside the quoted
    ``title`` value that closes on the next line)."""
    body = '<div title="x\nmiddle\n">\n\n## H\n'
    assert _state(body, "middle") == U


def test_vet845_f2_control_plain_lines_in_a_closed_block_stay_visible():
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``plain``."""
    body = "<div>\n<span>\nplain\n</div>\n"
    assert _state(body, "plain") == V
    assert md.scan(body).unsure == ()


@pytest.mark.parametrize("opener", ['x <a\vb="> <!-- "> y', 'x <a b=\v"> <!-- "> y'], ids=["vtab-name", "vtab-value"])
@pytest.mark.parametrize("where", ["para", "atx", "item", "cell"])
def test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure(opener, where):
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid everything below (HTML parsing
    does not count ``\\v`` as tag whitespace, so the tag ended at the ``>`` inside the quoted value)."""
    shapes = {
        "para": "{o}\n\n## H\n",
        "atx": "# {o}\n\n## H\n",
        "item": "- {o}\n\n## H\n",
        "cell": "| a | b |\n| - | - |\n| {o} | z |\n\n## H\n",
    }
    body = shapes[where].format(o=opener)
    assert _state(body, "## H") == U, "unsure=%r" % (md.scan(body).unsure,)


@pytest.mark.parametrize("quote", ['"', "'"], ids=["dq", "sq"])
@pytest.mark.parametrize("form", ["pi", "cdata"])
def test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure(form, quote):
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid everything below (HTML parsing
    ended the bogus comment at the first ``>``, so the later ``<a title=`` opened an unclosed attribute quote)."""
    if form == "pi":
        body = "x <? > <a title=%s ?> y\n\n## H\n" % quote
    else:
        body = "x <![CDATA[ > <a title=%s ]]> y\n\n## H\n" % quote
    assert _state(body, "## H") == U, "unsure=%r" % (md.scan(body).unsure,)


@pytest.mark.parametrize("body", ['x <a b="c"> y\n\n## H\n', "x <? a ?> y\n\n## H\n"], ids=["tag", "pi"])
def test_vet845_f3_controls_a_closed_inline_tag_or_pi_stays_visible(body):
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``H``."""
    assert _state(body, "## H") == V
    assert md.scan(body).unsure == ()


@pytest.mark.parametrize("char", [0x17F, 0x212A, 0x130], ids=["long-s", "kelvin", "dotted-i"])
def test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start(char):
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``H`` (cmark is ASCII-only, so
    the opener stays paragraph text and the ``<!--`` is not raw HTML)."""
    tags = {0x17F: "<%section>", 0x212A: "<lin%s>", 0x130: "<d%sv>"}
    body = "a\n" + tags[char] % chr(char) + "\nx <!--\n\n## H\n"
    assert _state(body, "## H") == V


def test_vet845_f4b_a_vertical_tab_after_a_type7_tag_is_not_trailing_whitespace():
    """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``H`` after ``<span>\\v`` (a
    paragraph) and hid it after ``<span>\\f`` (a type-7 block)."""
    assert _state("<span>\v\nx <!--\n\n## H\n", "## H") == V
    _reads("<span>\f\nx <!--\n\n## H\n", "## H", H)


# --- Returning review round 1 (PR #2390, after vet 845) -------------------------------------------------------------

@pytest.mark.parametrize("body", [
    'x <a title=">" b=\v"> <!-- "> y\n\n## H\n',      # a quoted > before the vertical tab
    "x <a title='>' b=\v'> <!-- '> y\n\n## H\n",      # the same with single quotes
    'x <a title=">">\n<b c=\v"> <!-- "> y\n\n## H\n',  # the vertical tab on a later line of the paragraph
], ids=["double", "single", "later-line"])
def test_review_s2_a_quoted_gt_before_the_vertical_tab_still_reads_unsure(body):
    """The scoped finder's shape: cmark passes the whole tag through raw, HTML parsing ends it at the > after the
    vertical tab and the <!-- then hides ## H (the same mechanism as vet 845 F3(a), which GitHub hid)."""
    assert _state(body, "## H") == U


def test_review_s2_r2_a_vertical_tab_inside_a_quoted_value_still_reads_unsure():
    """The round-2 audit: the quote-aware walk keeps the earlier conservative reading of a vertical tab inside a quoted
    value (no GitHub render separates it; over-reading it unsure only refuses), and a complete tag followed by a
    vertical tab stays a paragraph (vet 845 F4(b))."""
    assert _state('x <a title="p\vq"> y\n\n## H\n', "## H") == U
    assert _state("x <a title='p\vq'> y\n\n## H\n", "## H") == U
    assert _state("x <a b=\"c\">\v y\n\n## H\n", "## H") == V


# --- Fix leg 2 (vet 846 F5, F6, F8): the inline raw-HTML pass --------------------------------------------------------------

_CORPUS_PATH = os.path.join(_HERE, "fixtures", "md_hidden_github_corpus_2388.json")
with open(_CORPUS_PATH, encoding="utf-8") as _fh:
    _CORPUS = json.load(_fh)

_CORPUS_851_PATH = os.path.join(_HERE, "fixtures", "md_hidden_github_renders_vet851.json")
with open(_CORPUS_851_PATH, encoding="utf-8") as _fh:
    _CORPUS_851 = json.load(_fh)

_CORPUS_854_PATH = os.path.join(_HERE, "fixtures", "md_hidden_github_renders_vet854.json")
with open(_CORPUS_854_PATH, encoding="utf-8") as _fh:
    _CORPUS_854_ROWS = json.load(_fh)
_CORPUS_854 = {row["body"]: row["html"] for row in _CORPUS_854_ROWS.values()}

_CORPUS_857_PATH = os.path.join(_HERE, "fixtures", "md_hidden_github_renders_vet857.json")
with open(_CORPUS_857_PATH, encoding="utf-8") as _fh:
    _CORPUS_857_ROWS = json.load(_fh)
_CORPUS_857 = {row["body"]: row["html"] for row in _CORPUS_857_ROWS.values()}

_SENTINEL = re.compile(r"\bZQ\d+\b")


class _VisibleText(HTMLParser):
    """The visible text of a render: ``handle_data`` only (comments and attribute values are not visible text)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _visible_sentinels(rendered):
    parser = _VisibleText()
    parser.feed(rendered)
    parser.close()
    found = set()
    for part in parser.parts:  # one text node at a time: adjacent nodes (``<h2>ZQ4</h2><h2>ZQ5</h2>``) never fuse a word
        found.update(_SENTINEL.findall(part))
    return found


def _corpus_hides(body, sentinel):
    """The advisor's corpus (``md_hidden_github_corpus_2388.json``) holds ``body`` and GitHub's render hides ``sentinel``."""
    assert body in _CORPUS, "body is not in the advisor's corpus: %r" % (body,)
    assert sentinel not in _visible_sentinels(_CORPUS[body]), "GitHub shows %s in %r" % (sentinel, body)


def _corpus_judge(body, renders=None):
    """(line index, offset, line, sentinels, GitHub shows all of them) for each line of ``body`` that holds a sentinel.
    ``renders`` is the corpus to read ``body``'s render from (default ``_CORPUS``)."""
    renders = _CORPUS if renders is None else renders
    shown = _visible_sentinels(renders[body])
    out = []
    offset = 0
    for index, item in enumerate(md_fence.split_lines(body)):
        sentinels = set(_SENTINEL.findall(item))
        if sentinels:
            out.append((index, offset, item, sentinels, sentinels <= shown))
        offset += len(item)
    return out


def _corpus_fail_open(body, renders=None):
    """The (body, line index, line) entries of ``body`` where GitHub hides a sentinel line and md_hidden reads it VISIBLE.
    ``renders`` is the corpus to read ``body``'s render from (default ``_CORPUS``)."""
    rendering = md.scan(body)
    return [(body, index, item) for index, offset, item, sentinels, shows in _corpus_judge(body, renders)
            if not shows and rendering.state_at(offset) == V]


def _corpus_false_hidden(body):
    """The (body, line index, line) entries of ``body`` where GitHub shows a sentinel line and md_hidden reads it HIDDEN."""
    rendering = md.scan(body)
    return [(body, index, item) for index, offset, item, sentinels, shows in _corpus_judge(body)
            if shows and rendering.state_at(offset) == H]


# Corpus bodies the advisor declined (each key is a corpus body, each value the ruling). An exception never outlives its
# cause: the test below asserts each declined body still fails the plain check.
_CORPUS_DECLINED_FALSE_HIDDEN = {
    'x\n\n<svg>\n\n<![CDATA[ x > <!-- y ]]>\n\n## ZQ1\n': "vet 845 F4(c), declined by the advisor: CDATA inside "
                                                          "``<svg>`` is foreign content, which md_hidden reads as a bogus "
                                                          "comment; it fails closed",
}


def test_corpus_no_line_github_hides_reads_visible():
    """The bound's check: advisor's corpus, ``md_hidden_github_corpus_2388.json`` (660 bodies, GitHub's own renders). A line
    with a sentinel word that GitHub's visible text lacks is hidden by GitHub and must not read VISIBLE. Every one of the
    660 bodies must pass; none is declined."""
    assert len(_CORPUS) == 660
    failing = []
    for body in _CORPUS:
        failing.extend(_corpus_fail_open(body))
    assert failing == [], "%d fail-open (body, line index, line):\n%s" % (
        len(failing), "\n".join(repr(entry) for entry in failing))


def test_corpus_no_line_github_shows_reads_hidden():
    """The reverse check (fails closed, so it is not the bound): advisor's corpus, ``md_hidden_github_corpus_2388.json``.
    A line whose sentinel words all appear in GitHub's visible text must not read HIDDEN. One body is declined by the
    advisor (``_CORPUS_DECLINED_FALSE_HIDDEN``) and must still fail the plain check."""
    assert list(_CORPUS_DECLINED_FALSE_HIDDEN) == ['x\n\n<svg>\n\n<![CDATA[ x > <!-- y ]]>\n\n## ZQ1\n']
    for declined in _CORPUS_DECLINED_FALSE_HIDDEN:
        assert declined in _CORPUS, "declined body is not in the advisor's corpus: %r" % (declined,)
        assert _corpus_false_hidden(declined) != [], "declined body no longer fails: drop it from _CORPUS_DECLINED_FALSE_HIDDEN: %r" % (declined,)
    failing = []
    for body in _CORPUS:
        if body in _CORPUS_DECLINED_FALSE_HIDDEN:
            continue
        failing.extend(_corpus_false_hidden(body))
    assert failing == [], "%d false-hidden (body, line index, line):\n%s" % (
        len(failing), "\n".join(repr(entry) for entry in failing))


def test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside():
    """Advisor's corpus, ``md_hidden_github_corpus_2388.json``: GitHub hides ``ZQ1``. The line that closes the comment
    shows the text after the closer, so it reads UNSURE (F8); the heading after it is decided."""
    body = "a <!-- b\nZQ1\n--> c\n\n## ZQ2\n"
    _corpus_hides(body, "ZQ1")
    assert _state(body, "a <!-- b") == U  # vet 851: the comment hides `b`, so this line shows only part of itself and reads unsure
    assert _state(body, "ZQ1") == H
    assert _state(body, "--> c") == U
    assert _state(body, "## ZQ2") == V
    assert md.scan(body).unsure == ()


def test_f5_a_comment_across_paragraph_lines_with_two_hidden_lines_and_a_sentinel_after_the_closer():
    """Advisor's corpus, ``md_hidden_github_corpus_2388.json``: GitHub hides ``ZQ1`` and ``ZQ2``, shows ``ZQ3``."""
    body = "Note <!-- hidden\nZQ1\nZQ2\nend --> after ZQ3\n\n## ZQ4\n"
    _corpus_hides(body, "ZQ1")
    _corpus_hides(body, "ZQ2")
    assert _state(body, "ZQ1") == H and _state(body, "ZQ2") == H
    assert _state(body, "end --> after ZQ3") == U
    assert _state(body, "## ZQ4") == V


def test_f5_a_double_quoted_value_across_list_item_lines_reads_unsure():
    """Advisor's corpus, ``md_hidden_github_corpus_2388.json``: GitHub hides ``ZQ1`` (inside the ``title`` value)."""
    body = '- x <span title="\n  ZQ1\n  "> y\n\n## ZQ2\n'
    assert _state(body, "  ZQ1") == U
    assert _state(body, "## ZQ2") == U  # sticky
    assert md.scan(body).unsure[0][0] == _off(body, 1)


def test_f5_a_single_quoted_value_across_paragraph_lines_reads_unsure():
    """Advisor's corpus, ``md_hidden_github_corpus_2388.json``: GitHub hides ``ZQ1`` (inside the single-quoted value)."""
    body = "x <span title='\nZQ1\n'> y\n\n## ZQ2\n"
    _corpus_hides(body, "ZQ1")
    assert _state(body, "x <span title='") == U  # vet 854: a line holding an inline tag with an attribute value reads U
    assert _state(body, "ZQ1") == U
    assert md.scan(body).unsure[0][0] == _off(body, 1)


def test_f5_an_unquoted_value_ended_by_a_line_break_reads_unsure():
    """The corpus class (a tag that spans lines): the tag is ``<a href=foo`` newline ``ZQ1`` newline ``class=z>``, so ``ZQ1``
    is an attribute name, hidden by HTML parsing (this exact body is not one of the corpus's 660)."""
    body = "x <a href=foo\nZQ1\nclass=z> y\n\n## ZQ2\n"
    assert _state(body, "ZQ1") == U


@pytest.mark.parametrize("opener,closer", [("<? a", "?>"), ("<![CDATA[ a", "]]>")], ids=["pi", "cdata"])
def test_f5_an_inline_pi_or_cdata_across_lines_reads_unsure(opener, closer):
    """The corpus class (a bogus comment that spans lines): HTML parsing reads ``<?`` and ``<![CDATA[`` as a bogus comment
    that ends at the first ``>``; the line inside it reads UNSURE, never VISIBLE (this exact body is not in the corpus)."""
    body = "x %s\nZQ1\n%s y\n\n## ZQ2\n" % (opener, closer)
    assert _state(body, "ZQ1") == U
    # vet 854: a text block in which a "![" is followed by a "]" on a later line reads unsure from its first line (cdata only)
    assert md.scan(body).unsure[0][0] == _off(body, 0 if opener.startswith("<![") else 1)


def test_f5_a_setext_heading_paragraph_holding_a_multi_line_comment():
    """The corpus class (a comment across the lines of a text block; here a setext heading): ``ZQ1`` sits inside the
    comment (this exact body is not one of the corpus's 660)."""
    body = "Title <!-- a\nZQ1\n-->\n=====\n\n## ZQ2\n"
    assert _state(body, "ZQ1") == H
    assert _state(body, "-->") == H
    assert _state(body, "## ZQ2") == V


def test_f5_the_leftovers_shape_does_not_read_visible():
    """Advisor's corpus, ``md_hidden_github_corpus_2388.json`` (the ``What we're accepting`` body): GitHub hides ``ZQ1``."""
    body = "## What we're accepting\n\nLeftovers: <!-- draft list\nF1 the retry loop ZQ1\n-->\n- F2 ZQ2\n"
    _corpus_hides(body, "ZQ1")
    assert _state(body, "F1 the retry loop ZQ1") in (H, U)
    assert _state(body, "F1 the retry loop ZQ1") != V


def test_f5_controls_an_unclosed_comment_opener_in_a_paragraph_stays_text():
    body = "a <!-- b\nZQ1\n\n## ZQ2\n"
    assert _state(body, "ZQ1") == V
    assert _state(body, "## ZQ2") == V
    assert md.scan(body).unsure == ()


def test_f5_controls_an_unclosed_tag_opener_is_literal_text():
    """E3: a construct whose end cmark's grammar never finds is literal text and changes nothing."""
    body = "x <a b='\nZQ1\n\n## ZQ2\n"
    assert _state(body, "ZQ1") == V
    assert md.scan(body).unsure == ()


@pytest.mark.parametrize("form", ["builder", "bot"])
def test_f5_controls_the_lower_decl_and_inline_code_opener_shapes_stay_visible(form):
    """``md_hidden_github_renders_2366.json``: GitHub showed the owner heading after ``<!x`` (lowercase, no declaration)
    and after a code span holding the opener."""
    _reads(_ROW_BY_KEY[("lower_decl", form)]["sent"], OWNER[form], V)
    _reads(_ROW_BY_KEY[("inline_code_opener", form)]["sent"], OWNER[form], V)


def test_f5_controls_a_code_span_across_lines_holding_an_opener_stays_visible():
    body = "x `a <!--\nb` y\n--> z\nZQ1\n\n## ZQ2\n"
    assert _state(body, "b` y") == V
    assert _state(body, "ZQ1") == V
    assert _state(body, "## ZQ2") == V
    assert md.scan(body).unsure == ()


def test_f5_controls_an_escaped_opener_stays_text():
    body = "x \\<!-- y\nZQ1\n--> z\n\n## ZQ2\n"
    assert _state(body, "ZQ1") == V
    assert md.scan(body).unsure == ()


def test_f6_code_spans_holding_a_pi_and_a_tag_leave_the_heading_visible():
    """Vet 846 receipt on PR #2390, comment 6711193618 (and the corpus's ``The reader skips a`` body): GitHub showed the
    heading after code spans holding ``<?xml ?>`` and ``<br>``."""
    body = "Quotes `<?xml ?>` here and `<br>` too.\n\n## H\n"
    assert _state(body, "## H") == V
    assert md.scan(body).unsure == ()
    corpus_body = "## What we're accepting\n\nThe reader skips a `<?xml ?>` header and keeps `<br>` tags ZQ1.\n\n## ZQ2\n"
    assert _state(corpus_body, "## ZQ2") == V
    assert md.scan(corpus_body).unsure == ()


def test_f5_c2_a_code_span_opener_is_no_comment_even_with_a_later_closer():
    """Code spans (the C2 discriminator): cmark sees no comment in ``x `<!--` y``, so GitHub shows ``ZQ1`` (this exact
    body is not one of the corpus's 660); read as a comment from ``<!--`` to ``-->`` it would hide ``ZQ1``."""
    body = "x `<!--` y\nZQ1\n--> w\n\n## ZQ2\n"
    assert _state(body, "ZQ1") == V
    assert _state(body, "## ZQ2") == V
    assert md.scan(body).unsure == ()


def test_f5_a_pi_that_html_parsing_ends_early_reads_unsure_at_its_end_line():
    """Advisor's corpus, ``md_hidden_github_corpus_2388.json`` (``x <? > <a title=' ?> y``): GitHub hid the heading."""
    body = "x <? > <a title=' ?> y\n\n## ZQ1\n"
    assert body in _CORPUS
    assert "ZQ1" not in _visible_sentinels(_CORPUS[body])
    assert _state(body, "## ZQ1") == U


def test_f5_an_inline_pass_failure_edges_never_raise():
    """E1: ``scan`` never raises on a str, whatever the inline openers."""
    for body in ["<", "`", "\\", "<!--", "<a b='", "<<<<<", "`<!--\n", "<?\n", "<![CDATA[", "<!A", "\\`<!-- `\n\n", "``a`<!--\n--> `` <",
                 "<a\n\n<b\n", "<a b=\n", "\x00<!-- \v", "a <!--\n\n--> <!-- \n-->", "- <a b='\n  x\n  '>\n", "> a <!-- b\n> c --> d\n"]:
        rendering = md.scan(body)
        assert len(rendering.lines) == len(md_fence.split_lines(body))


def test_f8_a_line_that_closes_a_comment_in_html_block_content_shows_its_tail():
    """F8 (vet 846): GitHub shows the text after the closer, so the closing line reads UNSURE, never HIDDEN."""
    body = "<div>\n<!-- a\nZQ1 --> ZQ2\n</div>\n\n## ZQ3\n"
    assert _state(body, "ZQ1 --> ZQ2") == U
    assert _state(body, "## ZQ3") in (V, U)
    assert _state(body, "## ZQ3") != H


def test_f8_a_closer_with_nothing_after_it_stays_hidden_and_a_bang_closer_counts():
    """The closing line with no text after the closer shows nothing (the existing ``-->`` line stays HIDDEN); ``--!>``
    closes a comment for GitHub too."""
    assert _state("<div>\n<!-- a\nZQ1 -->\n</div>\n\n## H\n", "ZQ1 -->") == H
    assert _state("<div>\n<!-- a\nZQ1 --!> ZQ2\n</div>\n\n## H\n", "ZQ1 --!> ZQ2") == U


# --- Returning review after vet 846, round 1 (PR #2390) -----------------------------------------------------------

def _line_state(body, needle):
    offset = 0
    for item in md_fence.split_lines(body):
        if needle in item:
            return md.scan(body).state_at(offset)
        offset += len(item)
    raise AssertionError("no line holds %r" % needle)


def test_review_s3_a_backtick_run_over_80_opens_no_code_span():
    """cmark-gfm's scan_to_closing_backticks refuses an opener longer than 80, so the comment between two 81-runs is
    raw and hides ZQ1; an 80-run still makes a code span (ZQ1 shown)."""
    ticks = "`" * 81
    assert _line_state("x %s <!-- b\nZQ1\nc --> %s y\n\n## ZQ2\n" % (ticks, ticks), "ZQ1") != V
    ticks = "`" * 80
    assert _line_state("x %s <!-- b\nZQ1\nc --> %s y\n\n## ZQ2\n" % (ticks, ticks), "ZQ1") == V


def test_review_s3_a_declaration_needs_an_uppercase_name_then_whitespace():
    """cmark-gfm's inline declaration is <!, an uppercase name, whitespace, then up to >: <!X< is literal text, so the
    later <a title="…"> spans the lines and hides ZQ1."""
    assert _line_state('x <!X<a title=">\nZQ1\n"> y\n\n## ZQ2\n', "ZQ1") != V
    assert _line_state("x <!DOCTYPE html> y\nZQ1\n\n## ZQ2\n", "ZQ1") == V


def test_review_s3_a_backtick_in_a_link_destination_opens_no_code_span():
    """cmark reads a link's destination when it closes the link, so its backtick opens no code span and the comment
    after it is raw and hides ZQ1."""
    assert _line_state("[a](x`y) <!-- b\nZQ1\n--> c `\n\n## ZQ2\n", "ZQ1") != V
    assert _line_state("[a](xy) `<!-- b`\nZQ1\n--> c\n\n## ZQ2\n", "ZQ1") == V


def test_review_s3_a_code_span_stays_inside_one_table_cell():
    """GFM inline-parses each table cell on its own, so the backticks in the first and last cells open no code span
    across the middle cell; its <? … ?> is raw HTML that GitHub's HTML parse ends at the first >, and the <!-- after it
    hides the rest (the finding's shape). Outside a table the same backticks do make one code span."""
    body = "| a | b | c |\n| - | - | - |\n| `x | <? > <!-- ?> | y` |\n\n## ZQ1\n"
    assert _line_state(body, "## ZQ1") != V
    assert _line_state("`x | <? > <!-- ?> | y`\n\n## ZQ1\n", "## ZQ1") == V


def test_review_s3_r2_a_quoted_title_parenthesis_does_not_end_the_link_check():
    """Round-2 audit and scoped finder: a ) inside a quoted title, or a ( inside one, must not end or widen the link
    reading wrongly. GitHub hides ZQ1 in both (cmark consumes the whole title before inline parsing resumes)."""
    assert _line_state('[a](/u "a) `b") <!-- hidden\nZQ1\n--> c`\n\n## H\n', "ZQ1") != V
    assert _line_state('[a](u "(") `one)two` <!-- b\nZQ1\n--> tail `\n', "ZQ1") != V


def test_review_s3_r2_a_link_and_a_code_quoted_opener_in_one_paragraph_stay_visible():
    """The link check flags only a code span that opens inside a link's destination or title, so an ordinary link
    beside a code-quoted opener does not refuse the body (the #2366 inline-code case)."""
    assert _line_state("Text with a [link](https://x) and `<!--` code here.\nZQ1\n\n## H\n", "ZQ1") == V
    assert md.scan("Text with a [link](https://x) and `<!--` code here.\n\n## H\n").unsure == ()


def test_review_s3_r2_a_delimiter_row_whose_cell_count_differs_is_no_table():
    """cmark-gfm makes a table only when the header and delimiter rows hold the same cell count; otherwise the lines
    stay one paragraph, its code span spans lines, and the PI after it leaves a comment that hides ZQ1."""
    assert _line_state("a `one\n| - | - |\ntwo` <? > <!-- ?> `\n\n## ZQ1\n", "## ZQ1") != V
    assert md._cell_count("| a | b |") == 2 and md._cell_count("a | b | c") == 3 and md._cell_count("| a \\| b |") == 1


@pytest.mark.parametrize("body", [
    "[a](x`y) `one` <!-- b\nZQ1\n--> tail `\n",                    # a later span re-paired by the metadata backtick
    '[a](x`y) `<a title="` <!-- b">\nZQ1\n--> c\n\n## H\n',        # a fake tag the shifted pairing exposes
    "[a](<u)`v>) <!-- b\nZQ1\n--> c`\n",                           # an angle-bracket destination holding a )
    '[r]: /u "`"\n`x` <!-- b\nZQ1\n--> c `\n',                     # a reference definition's title
], ids=["displaced-span", "fake-tag", "angle-destination", "reference-definition"])
def test_review_s3_r3_link_metadata_that_changes_backtick_pairing_reads_unsure(body):
    """Round-3 audits and scoped finder: cmark consumes a link's destination and title (or a reference definition)
    before inline parsing, so a backtick there changes how every later backtick pairs; GitHub hides ZQ1 in each. The
    comparison reading turns every construct the two pairings disagree on into an unsure point."""
    assert _line_state(body, "ZQ1") != V


# --- Link-metadata rule (park ruling, option a, issue #2388) -------------------------------------------------------
# A text block that holds a backtick inside a possible link destination, title or reference definition, and also holds
# a "<", reads unsure from the block's first line on. The ranges are an over-approximation used only to add that point.

@pytest.mark.parametrize("body", [
    # round-4 audit and scoped finder (PR #2390, comment 6713049081): an escaped > does not end an angle destination
    "[a](<u\\>)`v>) <!-- b\nZQ1\n--> c`\n",
    # round-4 audit (PR #2390, comment 6713049081): malformed metadata, the backtick pairing cmark reads differs
    "[bad](x `` ) `` [a](x`y) <!-- b\nZQ1\n--> c ` ``\n",
    # round-4 scoped finder (PR #2390, comment 6713049081): a reference-definition-shaped line inside a paragraph
    "[a](x`y)\n[r]: /u\n``one\ntwo`` <!-- b\nZQ1\n--> tail `` `\n",
], ids=["escaped-angle-close", "malformed-metadata", "ref-def-shaped-line-in-paragraph"])
def test_link_metadata_rule_round4_shapes_read_not_visible(body):
    """Each shape is one GitHub renders with ZQ1 hidden (checked against the round-4 audits and scoped finder of the
    returning review on PR #2390, raw output comment 6713049081); ZQ1's line must not read visible."""
    assert _line_state(body, "ZQ1") != V


def test_link_metadata_rule_controls_keep_their_answers():
    """Controls (checked against: control): no backtick in link metadata, a backtick after the link, and a backtick in
    metadata with no "<" anywhere in the block (no unsure point)."""
    assert _line_state("Text with a [link](https://x) and `<!--` code here.\nZQ1\n", "ZQ1") == V
    assert _line_state("[a](xy) `<!-- b`\nZQ1\n--> c\n\n## ZQ2\n", "ZQ1") == V
    body = "[a](x`y) no raw html here\nZQ1\n"
    assert _line_state(body, "ZQ1") == V
    assert md.scan(body).unsure == ()


def test_link_metadata_rule_puts_the_unsure_point_at_the_blocks_first_line():
    """The rule's point sits on the block's first source line (checked against: control, the rule as ruled): the block's
    own first line reads unsure, the paragraph before it stays visible."""
    body = "intro\n\n[a](x`y)\nmid <b>\nZQ1\n"
    assert _line_state(body, "[a]") == U
    assert _line_state(body, "intro") == V


# --- Table ruling and vet-849 amendment (issue #2388) -------------------------------------------------------------

@pytest.mark.parametrize("body, needle", [
    ('x\n\n[F-1]: https://example.com "The retry loop never backs off"\n\n## H\n', "[F-1]"),
    ("x\n\n[F-1 The retry loop never backs off]: https://example.com\n\n## H\n", "[F-1"),
    ("x\n\n[ZQ1]: /u\n\n## ZQ2\n", "[ZQ1]"),
], ids=["titled-definition", "label-with-spaces", "bare-definition"])
def test_amendment_link_reference_definition_lines_read_unsure(body, needle):
    """Checked against: the advisor's vet 849 (a text block whose first line starts with ``[`` and holds ``]:`` reads
    unsure; the ``[ZQ1]: /u`` corpus exception becomes a passing case). The needle's line reads UNSURE."""
    assert _line_state(body, needle) == U


def test_destination_quotes_do_not_stop_the_parenthesis_count():
    """Checked against: the review raw output comment 6714091519 on PR #2390, finding "Count parentheses inside quoted
    characters of bare destinations". cmark counts parentheses to the end of a bare destination, quotes included, so the
    ``(`` inside ``u"(x"`` keeps the link open and the code span after it is not a span; the comment is raw and hides
    ZQ1. The control has a balanced destination: its code span is a span, so ZQ1 shows and nothing is unsure."""
    assert _line_state('[a](u"(x")y`z) <!-- b\nZQ1\n--> c`\n', "ZQ1") != V
    control = '[a](u"x") `<!--` code\nZQ1\n'
    assert _line_state(control, "ZQ1") == V
    assert md.scan(control).unsure == ()


@pytest.mark.parametrize("body", [
    "| a | b |\n| - | - |\n| <b>x</b> | `<!--` |\n\nZQ1\n",
    "| a | b |\n| - | - |\n| <!-- c --> | d |\n\nZQ1\n",
], ids=["tag-beside-code-quoted-opener", "closed-comment-in-a-cell"])
def test_table_cells_controls_keep_their_answers(body):
    """Controls (checked against: control): each cell is parsed on its own, so a tag in one cell and a code-quoted
    opener in another, or a comment that opens and closes inside one cell, leave ZQ1 visible with no unsure point."""
    assert _line_state(body, "ZQ1") == V
    assert md.scan(body).unsure == ()


def test_reference_link_label_backtick_reads_unsure():
    """Final returning review on 68394b12 (finding "Include reference-link labels in the metadata uncertainty rule"):
    cmark reads a full reference link's second label apart from the text, so its backtick cannot pair with a later one
    and the comment after it hides ZQ1 on GitHub; ZQ1's line must not read visible. Control: a reference link with no
    backtick in its label next to a code-quoted opener keeps its answer."""
    assert _line_state("[a][x`y] <!-- b\nZQ1\n--> c`\n\n[x`y]: /u\n", "ZQ1") != V
    assert _line_state("[a][r] and `<!--` code\nZQ1\n\n[r]: /u\n", "ZQ1") == V


@pytest.mark.parametrize("body", [
    "[a][x\\]y`z] <!-- b\nZQ1\n--> c`\n\n[x\\]y`z]: /u\n",   # round-2 audit: an escaped ] inside the label
    "[a][x\\]\nZQ1\n]\n\n[x\\] ZQ1]: /u\n",                   # round-2 scoped finder: the label spans lines
], ids=["escaped-bracket-backtick", "escaped-bracket-multiline"])
def test_reference_link_label_with_an_escaped_bracket_reads_not_visible(body):
    """Final returning review on 68394b12, round 2 (audit and scoped finder, finding "Skip escaped closing brackets in
    reference labels"): a reference label holds escaped brackets and may span lines, so its range runs to the end of
    the block; GitHub hides or attribute-only renders ZQ1 in each body, which must not read visible."""
    assert _line_state(body, "ZQ1") != V


# --- Vet 851 fix leg (issue #2388): V851-1..5 and the per-line hiding rule ---------------------------------------------------

def _corpus_851_clean(body):
    """The vet 851 corpus holds ``body`` and no line GitHub hides reads VISIBLE."""
    assert body in _CORPUS_851, "body is not in the vet 851 corpus: %r" % (body,)
    assert _corpus_fail_open(body, _CORPUS_851) == [], "fail-open lines: %r" % (_corpus_fail_open(body, _CORPUS_851),)


def test_vet851_corpus_no_line_github_hides_reads_visible():
    """The invariant over the second corpus: vet 851 renders, ``md_hidden_github_renders_vet851.json`` (215 bodies, GitHub's
    own renders by ``POST /markdown``). A line with a sentinel word that GitHub's visible text lacks is hidden by GitHub and
    must not read VISIBLE. Every one of the 215 bodies must pass."""
    assert len(_CORPUS_851) == 215
    failing = []
    for body in _CORPUS_851:
        failing.extend(_corpus_fail_open(body, _CORPUS_851))
    assert failing == [], "%d fail-open (body, line index, line):\n%s" % (
        len(failing), "\n".join(repr(entry) for entry in failing))


def test_vet851_1_a_delimiter_row_without_a_pipe_makes_a_table():
    """V851-1, vet 851 renders, ``md_hidden_github_renders_vet851.json``: a delimiter row needs a ``|`` or a ``:``, so a
    dash-only line stays a setext underline; ``:--`` makes a table, whose cell holds the code span's backtick."""
    _corpus_851_clean('a\n:--\n` <? > <!-- ?>\nx `\n\n## ZQ1\n')
    _corpus_851_clean('| a\n:--\n` <? > <!-- ?>\nx `\n\n## ZQ1\n')


def test_vet851_2_a_lone_pipe_header_makes_no_table():
    """V851-2, vet 851 renders, ``md_hidden_github_renders_vet851.json``: a lone ``|`` holds 0 cells, so it is no table
    header and the comment after it runs across the lines."""
    _corpus_851_clean('|\n|-|\nx <!-- a | b\nZQ1\n-->\n\n## ZQ2\n')
    _corpus_851_clean(' | \n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n')


def test_vet851_3_cells_past_the_header_count_read_unsure():
    """V851-3, vet 851 renders, ``md_hidden_github_renders_vet851.json``: a table row with more cells than its header reads
    unsure."""
    _corpus_851_clean('| a |\n|---|\n| | ZQ1 |\n| ZQ2 |\n\n## ZQ3\n')


def test_vet851_4_image_alt_text_across_lines_reads_not_visible():
    """V851-4, vet 851 renders, ``md_hidden_github_renders_vet851.json``: an image's alt range is link metadata, so alt
    text across lines is not read visible."""
    _corpus_851_clean('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n')
    _corpus_851_clean('![ZQ1\nZQ2][r]\n\n## ZQ3\n\n[r]: https://example.com/a.png\n')


def test_vet851_5_video_reads_unsure():
    """V851-5, vet 851 renders, ``md_hidden_github_renders_vet851.json``: ``<video`` and ``</video`` read unsure."""
    _corpus_851_clean('<video>\nZQ1\n</video>\n\n## ZQ2\n')
    _corpus_851_clean('x <video>\nZQ1\n</video> y\n\n## ZQ2\n')


def test_vet851_controls_keep_their_answers():
    """Controls (vet 851 renders, ``md_hidden_github_renders_vet851.json``, fix leg): shapes the fixes must leave alone."""
    body = 'a\n---\n\nZQ1\n'  # a dash-only line stays a setext underline, no table
    assert _line_state(body, "a") == V
    assert _line_state(body, "ZQ1") == V
    assert md.scan(body).unsure == ()
    body = '| a | b |\n| - | - |\n| c | d |\n\nZQ1\n'
    assert _line_state(body, "ZQ1") == V
    assert md.scan(body).unsure == ()
    assert _line_state('![alt](x.png)\nZQ1\n', "ZQ1") == V
    assert _line_state('## Title <!-- note --> more\n\nZQ1\n', "## Title") == V


def test_html_block_line_reads_hidden_only_when_it_is_one_hiding_construct():
    """Final returning review on 66130a25 (scoped finder, round 2, "Preserve literal angle-bracket text when deciding
    HIDDEN"): ``<3 ZQ1>`` beside a comment is literal text GitHub shows, so that line must not read hidden; a line that is
    one whole comment reads hidden, as GitHub renders nothing for it (checked against: control, GitHub's HTML parsing)."""
    body = "<div>\n<3 ZQ1> <!-- note -->\n</div>\n"
    assert _line_state(body, "<3 ZQ1>") == U
    assert _line_state("<!-- ZQ1 -->\n\n## ZQ2\n", "<!-- ZQ1") == H
    assert _line_state("<!-- ZQ1 -->\n\n## ZQ2\n", "## ZQ2") == V


@pytest.mark.parametrize("body", [
    "![<https://example.com/]>\nZQ1](image.png)\n",   # round-3 scoped finder: an autolink holds the ]
    "x <![CDATA[alt]\nZQ1](x.png)\n",                 # round-3 audit: an unclosed CDATA prefix is literal, the image stands
], ids=["autolink-bracket", "unclosed-cdata-prefix"])
def test_image_description_skips_autolinks_and_needs_a_closed_cdata(body):
    """Final returning review on 66130a25, round 3 (scoped finder and audit): cmark-gfm parses an autolink inside an image
    description before it closes the brackets, and excludes only a complete CDATA section; ZQ1 shows only in the alt
    attribute on GitHub, so its line must not read visible."""
    assert _line_state(body, "ZQ1") != V


def test_html_block_line_with_text_after_a_closed_comment_reads_unsure():
    """Final returning review on 66130a25, round 3 (scoped finder and audits, "Preserve visible text after a closed
    comment"): HTML ends a comment at its first closer, so ``ZQ1`` after it shows on GitHub; the line must not read
    hidden. Checked against: GitHub's HTML parsing (control)."""
    assert _line_state("<div>\n<!-- note --> ZQ1\n</div>\n", "<!-- note") == U
    assert _line_state("<!-- a --> b -->\n\n## H\n", "<!-- a") == U


def test_image_after_an_escaped_cdata_opener_reads_not_visible():
    """Final returning review on 66130a25, round-4 audit ("Restrict the image exclusion to actual CDATA"): an escaped
    ``\\<`` opens no CDATA section, so the image after it stands and ZQ1 shows only in its alt attribute on GitHub. A real
    CDATA section is still no image (control)."""
    assert _line_state("x \\<![CDATA[alt]\nZQ1](x.png)]]>\n", "ZQ1") != V
    # vet 854: the CDATA exclusion is removed from _image_regions: a "<![" image range stands, and its line reads U
    assert md._image_regions("<![CDATA[ a ]]>") == [(3, 13)]
    assert md._image_regions("\\\\<![CDATA[ a ]]>") == [(5, 15)]


# --- Vet 854 fix leg (issue #2388): V854-1, V854-2, V854-4, the third renders corpus, test strength ----------------------------

# Vet 854 bodies the advisor declined (each key is a row id of the third corpus, each value the ruling). An exception never
# outlives its cause: the test below asserts each declined body still fails the plain check.
_CORPUS_854_DECLINED = {
    "b7_link_dest_word": "a link destination's text is not modelled (disclosed)",
    "d3_atx_comment_only": "the accepted ATX-heading exemption",
    "d4_atx_comment_tail": "the accepted ATX-heading exemption",
}


def test_vet854_corpus_no_line_github_hides_reads_visible():
    """The invariant over the third corpus: vet 854 renders, ``md_hidden_github_renders_vet854.json`` (44 bodies, GitHub's
    own renders taken by the advisor). A line with a sentinel word that GitHub's visible text lacks is hidden by GitHub and
    must not read VISIBLE. Every body must pass except the three the advisor declined (``_CORPUS_854_DECLINED``), each of
    which must still fail the check."""
    assert len(_CORPUS_854_ROWS) == 44
    assert sorted(_CORPUS_854_DECLINED) == ["b7_link_dest_word", "d3_atx_comment_only", "d4_atx_comment_tail"]
    for row_id in _CORPUS_854_DECLINED:
        assert row_id in _CORPUS_854_ROWS, "declined row is not in the vet 854 corpus: %r" % (row_id,)
        assert _corpus_fail_open(_CORPUS_854_ROWS[row_id]["body"], _CORPUS_854) != [], (
            "declined body no longer fails: drop it from _CORPUS_854_DECLINED: %r" % (row_id,))
    failing = []
    for row_id, row in _CORPUS_854_ROWS.items():
        if row_id in _CORPUS_854_DECLINED:
            continue
        failing.extend(_corpus_fail_open(row["body"], _CORPUS_854))
    assert failing == [], "%d fail-open (body, line index, line):\n%s" % (
        len(failing), "\n".join(repr(entry) for entry in failing))


def test_vet854_1_an_image_closing_on_a_later_line_reads_unsure():
    """V854-1, vet 854 renders, ``md_hidden_github_renders_vet854.json``: a text block in which a ``![`` is followed by a
    ``]`` on a later line reads unsure from its first line. Ids: a1_nested_dest_bracket, a2_nested_title_bracket,
    a3_nested_angle_dest_bracket, a6_nested_dest_bracket_list, a7_nested_ref_title, g2_nested_img_in_img_dest,
    g4_inline_link_paren_title, e1_cdata_triple_bracket_end, e4_table_cell_cdata."""
    for row_id in ("a1_nested_dest_bracket", "a2_nested_title_bracket", "a3_nested_angle_dest_bracket",
                   "a6_nested_dest_bracket_list", "a7_nested_ref_title", "g2_nested_img_in_img_dest",
                   "g4_inline_link_paren_title", "e1_cdata_triple_bracket_end", "e4_table_cell_cdata"):
        body = _CORPUS_854_ROWS[row_id]["body"]
        assert _corpus_fail_open(body, _CORPUS_854) == [], row_id


def test_vet854_2_a_block_end_tag_bogus_comment_hides_its_text():
    """V854-2, vet 854 renders, ``md_hidden_github_renders_vet854.json``: in an HTML block, ``</`` followed by anything but
    an ASCII letter or ``>`` is a bogus comment to its first ``>``, so its text is hidden. Ids: h1_block_endtag_bogus,
    h2_block_endtag_bogus_mid, h3_block_endtag_digit. Control h4_inline_endtag_bogus_ctrl: its ZQ1 line reads VISIBLE."""
    for row_id in ("h1_block_endtag_bogus", "h2_block_endtag_bogus_mid", "h3_block_endtag_digit"):
        body = _CORPUS_854_ROWS[row_id]["body"]
        assert _corpus_fail_open(body, _CORPUS_854) == [], row_id
    assert _line_state(_CORPUS_854_ROWS["h4_inline_endtag_bogus_ctrl"]["body"], "ZQ1") == V


def test_vet854_4_attribute_and_title_text_reads_unsure():
    """V854-4, vet 854 renders, ``md_hidden_github_renders_vet854.json``: a line reads unsure, on that line only, when it
    holds an HTML-block tag with an attribute value, an inline tag with an attribute value (ATX headings exempt), or a
    possible link or image title. Ids: b1_span_title_alone, b2_img_alt_block, b3_empty_link_title, b4_div_title_block,
    b5_link_title_inline, b6_img_inline, g1_img_empty_desc_title."""
    for row_id in ("b1_span_title_alone", "b2_img_alt_block", "b3_empty_link_title", "b4_div_title_block",
                   "b5_link_title_inline", "b6_img_inline", "g1_img_empty_desc_title"):
        body = _CORPUS_854_ROWS[row_id]["body"]
        assert _corpus_fail_open(body, _CORPUS_854) == [], row_id
        assert _line_state(body, "## ZQ2") == V, row_id


def test_vet854_h2_a_lone_pipe_header_with_pipeless_rows():
    """Vet 851 H2 re-proven (covers no new item), vet 854 renders, ``md_hidden_github_renders_vet854.json``: a lone ``|``
    header holds 0 cells, so it makes no table (``if text == "|":``); these rows hold no pipe, so V851-3 cannot mask the
    rule (J6). Ids: f1_h2_lone_pipe_no_row_pipes, f2_h2_lone_pipe_space."""
    for row_id in ("f1_h2_lone_pipe_no_row_pipes", "f2_h2_lone_pipe_space"):
        body = _CORPUS_854_ROWS[row_id]["body"]
        assert _corpus_fail_open(body, _CORPUS_854) == [], row_id


_DELIMITER_LINE = re.compile(r"(?m)^[ \t]*\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-*:?[ \t]*)*\|?[ \t]*$")


def _md_makes_table(body):
    offsets, texts, off = [], [], 0
    for item in md_fence.split_lines(body):
        offsets.append(off)
        off += len(item)
        texts.append(md._terminator_free(item).expandtabs(md._CODE_INDENT))
    parser = md._Parser(offsets, texts)
    parser.run()
    return any(block.table for block in parser.paras)


def test_vet851_table_detection_matches_github():
    """Test strength (vet 851 renders, ``md_hidden_github_renders_vet851.json``): for each body holding a possible delimiter
    line, the parser's table decision equals GitHub's (the render holds ``<table``)."""
    checked = 0
    for body, rendered in _CORPUS_851.items():
        if not _DELIMITER_LINE.search(body):
            continue
        checked += 1
        assert _md_makes_table(body) == ("<table" in rendered), body
    assert checked >= 150, checked


@pytest.mark.parametrize("sep", ["\f", "\v"], ids=["form-feed", "vertical-tab"])
def test_link_title_after_form_feed_or_vertical_tab_reads_unsure(sep):
    """Final returning review on 10ed80c6 ("Recognize form feed and vertical tab before link titles"): cmark-gfm accepts
    either before an inline link's title, so ZQ1 shows only as the title attribute and its line must not read visible."""
    body = "[](<https://example.com>" + sep + '"ZQ1")\n\n## ZQ2\n'
    assert _line_state(body, "[](") == U


def test_atx_heading_tag_with_a_quoted_bracket_reads_unsure():
    """Final returning review on 10ed80c6 (seams check, "Handle quoted tag boundaries before exempting ATX attributes"):
    ``heading_text`` drops a tag only up to its first ``>``, so a quoted ``>`` inside an attribute would leave attribute
    text as heading text GitHub never shows; such a heading reads unsure. Control: an ordinary attribute keeps the
    exemption."""
    assert _line_state('## <span title=">Advisor vet<"></span>\n', "## <span") == U
    assert _line_state('## <span title="x">Advisor vet</span>\n', "## <span") == V


@pytest.mark.parametrize("sep", ["\f", "\v"], ids=["form-feed", "vertical-tab"])
def test_bare_destination_then_title_after_form_feed_or_vertical_tab_reads_unsure(sep):
    """Final returning review on 10ed80c6, round-2 audit: the link cursor skips cmark-gfm's whitespace too, so
    ``md_hidden`` ends a bare destination at a form feed or vertical tab and finds the title after it. GitHub does not:
    for a bare destination it keeps ``\\f`` and ``\\v`` inside the address (vet 857 renders ``t3_bare_ff_title``,
    ``t4_bare_vt_sq_title`` and ``t5_bare_ff_paren_title`` put ZQ1 in ``href``, and ``t7_ff_multiline_title`` shows
    ``ZQ1")`` as text). Ending the address early only reads more lines unsure, so it fails closed. A quoted ``<`` alone in
    an ATX heading's attribute keeps the exemption (control)."""
    body = "[](https://example.com" + sep + '"ZQ1")\n\n## ZQ2\n'
    assert _line_state(body, "[](") == U
    assert _line_state('## <span title="<">Advisor vet</span>\n', "## <span") == V


@pytest.mark.parametrize("sep", ["\f", "\v"], ids=["form-feed", "vertical-tab"])
def test_link_cursor_whitespace_finds_a_multiline_title_holding_a_paren(sep):
    """Final returning review on 10ed80c6, round-3 audit: with the link cursor reading form feed and vertical tab as
    whitespace, ``md_hidden`` ends the bare destination there and reads the title (which holds a ``)`` and runs onto the
    next line) whole. GitHub does not end the address there: for a bare destination it keeps ``\\f`` and ``\\v`` inside the
    address (vet 857 renders ``t3_bare_ff_title``, ``t4_bare_vt_sq_title`` and ``t5_bare_ff_paren_title`` put ZQ1 in
    ``href``, and ``t7_ff_multiline_title`` shows ``ZQ1")`` as text). Reading the title anyway only reads more lines
    unsure, so it fails closed. Without the cursor fix the range ends at that ``)`` and the ZQ1 line reads visible (checked
    on e96abd35)."""
    body = "[](https://example.com" + sep + '"a)\nZQ1")\n\n## ZQ2\n'
    assert _line_state(body, "ZQ1") != V


def test_atx_heading_tag_with_a_quoted_comment_opener_reads_unsure():
    """Final returning review on 10ed80c6, round-3 scoped finder ("Keep comment openers in attributes outside the ATX
    exemption"): ``heading_text`` removes comments before tags without regard to attribute quotes, so a quoted ``<!--``
    would make the heading text differ from GitHub's; such a heading reads unsure."""
    assert _line_state('## <span title="<!--">Other</span> --> <b>Advisor vet</b>\n', "## <span") == U


# --- Vet 857 fix leg (issue #2388): V857-1, V857-2, test strength and honesty, the fourth renders corpus ------------------------

# Vet 857 bodies the advisor declined (each key is a row id of the fourth corpus, each value the ruling). An exception never
# outlives its cause: the test below asserts each declined body still fails the plain check.
_CORPUS_857_DECLINED = {
    "t11_ctrl_ff_no_title": "a link's address, the accepted limit",
    "k1_atx_attr_value": "an ATX heading's tag, whose text is read through heading_text",
    "k2_atx_img_alt": "an ATX heading's tag, whose text is read through heading_text",
    "h17_tag_name_in_heading": "an ATX heading's tag, whose text is read through heading_text",
    "h18_attr_name_in_heading": "an ATX heading's tag, whose text is read through heading_text",
    "k7_atx_pi_tail_text": "an ATX heading's PI, disclosed in the owner half",
    "k8_atx_decl_text": "an ATX heading's declaration, disclosed in the owner half",
}


def _body_states(body):
    """(line, state) for every line of ``body``, in order."""
    rendering = md.scan(body)
    out = []
    offset = 0
    for item in md_fence.split_lines(body):
        out.append((item, rendering.state_at(offset)))
        offset += len(item)
    return out


def _heading_line_state(body):
    """The state of the one ATX heading line (the line that starts with ``#``) of ``body``."""
    found = [state for item, state in _body_states(body) if item.lstrip().startswith("#")]
    assert len(found) == 1, "expected one heading line in %r, found %d" % (body, len(found))
    return found[0]


def test_vet857_corpus_no_line_github_hides_reads_visible():
    """The invariant over the fourth corpus: vet 857 renders, ``md_hidden_github_renders_vet857.json`` (98 bodies, GitHub's
    own renders taken by the advisor). A line with a sentinel word that GitHub's visible text lacks is hidden by GitHub and
    must not read VISIBLE. Every body must pass except the seven the advisor declined (``_CORPUS_857_DECLINED``), each of
    which must still fail the check."""
    assert len(_CORPUS_857_ROWS) == 98
    assert sorted(_CORPUS_857_DECLINED) == sorted([
        "t11_ctrl_ff_no_title", "k1_atx_attr_value", "k2_atx_img_alt", "h17_tag_name_in_heading",
        "h18_attr_name_in_heading", "k7_atx_pi_tail_text", "k8_atx_decl_text"])
    for row_id in _CORPUS_857_DECLINED:
        assert row_id in _CORPUS_857_ROWS, "declined row is not in the vet 857 corpus: %r" % (row_id,)
        assert _corpus_fail_open(_CORPUS_857_ROWS[row_id]["body"], _CORPUS_857) != [], (
            "declined body no longer fails: drop it from _CORPUS_857_DECLINED: %r" % (row_id,))
    failing = []
    for row_id, row in _CORPUS_857_ROWS.items():
        if row_id in _CORPUS_857_DECLINED:
            continue
        failing.extend(_corpus_fail_open(row["body"], _CORPUS_857))
    assert failing == [], "%d fail-open (body, line index, line):\n%s" % (
        len(failing), "\n".join(repr(entry) for entry in failing))


def test_vet857_1_words_inside_a_raw_tag_read_unsure():
    """V857-1, vet 857 renders, ``md_hidden_github_renders_vet857.json``: a raw tag whose name is off the HTML element list,
    or that holds anything but whitespace and ``/`` after its name, hides words GitHub never shows; its line reads
    unsure, in an HTML block and inline alike. Ids: e5_block_endtag_attr_name_only, e6_block_opentag_attr_name_only,
    e7_inline_attr_name_only, e9_block_tag_name, e10_inline_tag_name, e13_type7_tag_name_alone, e14_block_three_attr_names,
    e15_inline_data_attr_name, e16_block_endtag_name_attr, e17_inline_selfclose_attr_name, k10_list_item_attr_name,
    k11_quote_block_attr_name, k12_inline_attr_names_sentence."""
    for row_id in ("e5_block_endtag_attr_name_only", "e6_block_opentag_attr_name_only", "e7_inline_attr_name_only",
                   "e9_block_tag_name", "e10_inline_tag_name", "e13_type7_tag_name_alone", "e14_block_three_attr_names",
                   "e15_inline_data_attr_name", "e16_block_endtag_name_attr", "e17_inline_selfclose_attr_name",
                   "k10_list_item_attr_name", "k11_quote_block_attr_name", "k12_inline_attr_names_sentence"):
        body = _CORPUS_857_ROWS[row_id]["body"]
        assert _corpus_fail_open(body, _CORPUS_857) == [], row_id


def test_vet857_1_controls_stay_visible():
    """V857-1 controls, vet 857 renders, ``md_hidden_github_renders_vet857.json``: text that GitHub shows keeps reading
    VISIBLE. Ids: c1_plain_link, c2_plain_tags, c3_brackets, c4_bang_bracket_no_close, c5_div_text, c6_collapsed,
    c7_endtag_plain, c8_bare_link_with_paren (every line), and k6_details_open_ctrl (its ``<summary>ZQ1</summary>`` and
    ``ZQ2`` lines)."""
    for row_id in ("c1_plain_link", "c2_plain_tags", "c3_brackets", "c4_bang_bracket_no_close", "c5_div_text",
                   "c6_collapsed", "c7_endtag_plain", "c8_bare_link_with_paren"):
        body = _CORPUS_857_ROWS[row_id]["body"]
        for item, state in _body_states(body):
            assert state == V, (row_id, item)
    body = _CORPUS_857_ROWS["k6_details_open_ctrl"]["body"]
    assert _line_state(body, "<summary>ZQ1</summary>") == V
    assert _line_state(body, "ZQ2") == V


def test_vet857_2_a_heading_comment_opener_without_a_comment_reads_unsure():
    """V857-2, vet 857 renders, ``md_hidden_github_renders_vet857.json``: an ATX heading holding a ``<!-- … -->`` run that
    ``heading_text`` drops, where the inline pass found no comment at its opener, reads unsure. Ids: h4_review_shape,
    h5_pi_holding_comment_opener, h6_decl_holding_comment_opener, h8_codespan_comment_opener,
    h9_escaped_comment_opener, h16_pi_comment_opener_tail. Controls (one heading reading VISIBLE, with the text GitHub
    renders): h11_comment_then_attr_closer (``">ZQ1``), h12_unclosed_comment_ctrl (``x <!-- ZQ1``), h14_quoted_lt_ctrl
    (``ZQ1``), h15_attr_ctrl (``ZQ1``)."""
    for row_id in ("h4_review_shape", "h5_pi_holding_comment_opener", "h6_decl_holding_comment_opener",
                   "h8_codespan_comment_opener", "h9_escaped_comment_opener", "h16_pi_comment_opener_tail"):
        body = _CORPUS_857_ROWS[row_id]["body"]
        assert _heading_line_state(body) == U, row_id
    for row_id, text in (("h11_comment_then_attr_closer", '">ZQ1'), ("h12_unclosed_comment_ctrl", "x <!-- ZQ1"),
                         ("h14_quoted_lt_ctrl", "ZQ1"), ("h15_attr_ctrl", "ZQ1")):
        body = _CORPUS_857_ROWS[row_id]["body"]
        assert [(heading, state) for _, heading, state in md.scan(body).headings] == [(text, V)], row_id
