"""#2389 V847-1, BR684-2, BR684-3 (fix leg of vet 847), redesigned segment-first (vet 853): the leftover check never counts text
GitHub hides within a line. The section and its items are read once from the body with the lines md_hidden does not read
VISIBLE blanked (``leftover_accepting._blanked``, ``pr_sheet.accepting_item_spans``); only then is each item cut, to the item's
end (``leftover_accepting._item_cut``). Every cut only removes text, so a miss fails toward a ``leftover-not-accepted`` refusal.

Oracle: ``fixtures/leftover_visible_github_renders_2389.json`` (GitHub's own render of 18 PR-body shapes, copied from the
advisor's renders). Guards (bite-proof record ``bite_proofs/i2389_leftover_visible_within_line.md``; select one with
``-k test_gN_``):
  G1 test_g1_escaped_opener_*     a backslash before an opener keeps both, then cuts the rest of the item
  G2 test_g2_code_span_opener_*   a code span holding an opener is kept, then the rest of the item is cut
  G3 test_g3_pi_declaration_*     an unescaped, unquoted ``<?``, ``<!X`` or ``<![`` cuts from the ``<``
  G4 test_g4_fenced_line_opener_* a fenced line is literal and is cut at its first entry ``<``
  G10 test_g10_claim_removed_*    a removed fixed-above claim makes its item count as nothing (#2389 vet 856: was a void body)
  G14 test_g14_tag_entry_*        the one entry condition: a ``<`` + ``!``, ``?``, ``/`` (not ``/>``) or an ASCII letter
  G17 test_g17_fence_shape_*      vet 852's list-fence forms: F-1 stays missing (regressions of the retired fence guards)
  G18 test_g18_whole_text_claims_* vet 852's whole-text claims
  G19 test_g19_item_cut_*         vet 853: a cut runs to the item's end, so it cannot join words GitHub separates
  G20 test_g20_*                  vet 853: the hidden or dropped stop point (``test_g20_stop_*``) and literal fenced lines
                                  (``test_g20_fenced_literal_*``)
  G21 test_g21_source_span_claims_* vet 853: the claim guards compare the cut item with the source lines of its span
                                  (#2389 vet 856: the summed guards are retired; the per-item comparison is G23)
  G22 test_g22_cut_item_counts_nothing_*  vet 856: an item where a within-line cut fires counts as nothing, so the words before
                                  the cut never read as whole (``f-1<span>-other</span>`` shows ``f-1-other``)
  G23 test_g23_per_item_claims_*  vet 856: claims are compared per item, so equal claims in two items cannot cancel
Retired with the redesign (their tests below are kept as regressions of the outcome): G12 block role, G13 and G16 per-line
claim guards, G15 cut heading, G17a and G17b fence-shape and fenced-state guards.
Rows with no GitHub render ("model-only") say so. No real gh: every call the vet-slot tests make is faked by
test_vet_slot_leftovers_2280's Fake."""
import json
import pathlib
import re
from html.parser import HTMLParser

import pytest

import leftover_accepting as la
import md_fence
import pr_sheet
from test_vet_slot_leftovers_2280 import (  # noqa: F401
    body, record_comment, read_ok, RECEIPT, write, _gh_on_path)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "leftover_visible_github_renders_2389.json"
ROWS = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
BY_ID = {row["id"]: row for row in ROWS}
F1_ROWS = [row for row in ROWS if row["id"].startswith("f1_")]
CLASS_ROWS = [row for row in ROWS if not row["id"].startswith("f1_")]

FINDING = {"id": "F-1", "title": "The retry loop never backs off", "outcome": "left-for-owner"}
GAP = [{"id": "F-1", "title": "The retry loop never backs off"}]
HEAD = "## What we're accepting\n\n"


class _Rendered(HTMLParser):
    """GitHub's HTML split into shown text (``handle_data``) and comment text (``handle_comment``)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data, self.comments = [], []

    def handle_data(self, data):
        self.data.append(data)

    def handle_comment(self, data):
        self.comments.append(data)


def shown_text(html):
    parser = _Rendered()
    parser.feed(html)
    parser.close()
    return "".join(parser.data)


def github_shows_f1(row):
    return "F-1" in shown_text(row["html"])


def missing(text):
    return la.missing(read_ok(FINDING), text)


def line_count(text):
    return len(md_fence.split_lines(text))


def ids(rows):
    return [row["id"] for row in rows]


def cuts(text):
    """The text of every item of ``text``'s What we're accepting (``_cut_items``: ``""`` for an item that counts as nothing)."""
    return la._cut_items(text)[0]


def raw_cuts(text):
    """The text of every item as ``_item_cut`` reads it, before the per-item claim check of ``_cut_items``."""
    blanked, shown = la._blanked(text)
    lines = md_fence.split_lines(blanked)
    return [la._item_cut(lines, span, shown) for span in pr_sheet.accepting_item_spans(blanked)]


def item_cut(source):
    """The cut text of the first item that ``source`` makes under the accepting heading ("" when it makes none)."""
    items = cuts(HEAD + source)
    return items[0] if items else ""


def source_texts(text):
    """The source text (before blanking) of every item span of ``text``, as the claim guards read it."""
    spans = pr_sheet.accepting_item_spans(la._blanked(text)[0])
    return [la._span_source(md_fence.split_lines(text), span) for span in spans]


def f1_counted(text):
    return any("F-1" in item for item in la._accepting_items(text))


# #2389 vet 856: GitHub shows F-1 in this row, but its item is continued by the tag line `</div>`, which holds an entry `<`, so the item
# counts as nothing (the disclosed over-refusal: the check fails toward a refusal, never toward counting hidden text)
OVER_REFUSED = {"f1_div_comment_then_item"}


def check_f1_row(row):
    """``missing`` reports F-1 exactly when GitHub hides it (a row in ``OVER_REFUSED`` is shown by GitHub but refused)."""
    gaps = missing(row["body"])
    if github_shows_f1(row) and row["id"] in OVER_REFUSED:
        # #2389 vet 856: was `gaps == []`; the item continued by `</div>` counts as nothing
        assert gaps == GAP, "%s is the disclosed over-refusal; the check must still refuse it" % row["id"]
    elif github_shows_f1(row):
        assert gaps == [], "GitHub shows F-1 in %s, but the leftover check does not count it: %r" % (row["id"], gaps)
    else:
        assert gaps == GAP, "GitHub hides F-1 in %s, but the leftover check counts it accepted" % row["id"]


# --- the F-1 oracle, every F-1 row, through ``missing``. The READY write path (run_verb) is run on the control, on the two
# closed V847-1 shapes f1_details_codespan_closed and f1_div_escaped_closed (their body already carries a verdict in place of
# the advisor's reminder; the write replaces that slot span), and, for the two unclosed twins, only to show they are never
# written. ---

def test_the_f1_rows_are_the_seven_taken_from_the_advisor_renders():
    assert len(F1_ROWS) == 7
    shows = {row["id"]: github_shows_f1(row) for row in F1_ROWS}
    assert [name for name, shown in shows.items() if shown] == ["f1_control_list_item", "f1_div_comment_then_item"]


@pytest.mark.parametrize("row", F1_ROWS, ids=ids(F1_ROWS))
def test_f1_oracle_missing_reports_f1_exactly_when_github_hides_it(row):
    check_f1_row(row)


# --- G1: a backslash before an opener ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["f1_div_escaped_unclosed", "f1_div_escaped_closed"])
def test_g1_escaped_opener_github_hides_f1_so_the_check_reports_it_missing(name):
    assert not github_shows_f1(BY_ID[name])
    check_f1_row(BY_ID[name])


@pytest.mark.parametrize("source, expected", [
    # #2389 V849-1: a backslash before an entry `<` is no longer kept; the item is cut from the backslash
    # #2389 redesign: the cut runs to the item's end and `_visible` cuts nothing, so the expected value is the item's cut text
    # #2389 vet 856: an item where a cut fires counts as nothing, so every expected value below that was the text before the cut is ""
    ("a \\<!-- tail\n", ""),  # #2389 vet 856: was "a"
    ("a \\<? tail\n", ""),  # #2389 vet 856: was "a"
    ("a \\<!X tail\n", ""),  # #2389 vet 856: was "a"
    # #2389 catch-up 41e75711: md_hidden now reads this line UNSURE, so the leftover check blanks it whole and the line makes no item
    # at all (was "a"): stricter, no text of the line counts
    ("a \\<![CDATA[ tail\n", ""),
    ("a \\<!-- tail\nnext -->\nz\n", ""),  # the lines after the cut are the item's, and are cut with it; #2389 vet 856: was "a"
    ("a \\<!-- tail", ""),  # a last line with no terminator; #2389 vet 856: was "a"
    # #2389 V849-1: these three were "an escape that is not an opener" and kept whole; `<b`, `<!-` and `<! ` are entries
    ("a \\* b \\` c \\< d \\<b> e\n", ""),  # #2389 vet 856: was "a \\* b \\` c \\< d"
    ("a \\<!- not an opener\n", ""),  # #2389 vet 856: was "a"
    ("a \\<! also not\n", ""),  # #2389 vet 856: was "a"
])
def test_g1_escaped_opener_cuts_the_item_from_the_backslash(source, expected):
    assert item_cut(source) == expected
    assert line_count(la._visible(source)) == line_count(source)


# #2389 V849-1: the `\\<b>` and the two bogus openers moved to the cut test above; what stays is an escape before a `<` that is no entry
@pytest.mark.parametrize("source", ["a \\* b \\` c \\< d e\n", "a \\< b \\<3 \\</> \\<\n"])
def test_g1_escaped_opener_an_escape_that_is_not_an_opener_changes_nothing(source):
    assert la._visible(source) == source
    assert item_cut(source) == source.strip()


def test_g1_escaped_opener_ready_write_refuses_leftover_not_accepted(tmp_path):
    row = BY_ID["f1_div_escaped_closed"]  # carries a verdict in place of the reminder; the write replaces that slot
    result, fake = write(row["body"], [RECEIPT, record_comment([FINDING])], tmp_path)
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted", result
    assert fake.edited == []


def test_g1_escaped_opener_the_unclosed_twin_is_stopped_earlier_and_never_written(tmp_path):
    # the unclosed `\<!--` leaves a comment open in the <div>, so md_hidden reads the composed body's marker line hidden and
    # evaluate refuses write-failed before the leftover check runs: the cut is reached through `missing` (above), not here
    row = BY_ID["f1_div_escaped_unclosed"]
    result, fake = write(row["body"], [RECEIPT, record_comment([FINDING])], tmp_path)
    assert result["ok"] is False and result["reason"] in ("leftover-not-accepted", "write-failed"), result
    assert fake.edited == []


def test_g1_escaped_opener_model_only_an_acceptance_before_the_escape_still_counts():
    # model-only (no GitHub render): the id and title come before the escaped opener
    # #2389 vet 856: was `== []`; the item holds a cut (the escaped entry `<`), so it counts as nothing and F-1 reads missing
    assert missing(body("- F-1 The retry loop never backs off; the note shows \\<!-- here\n")) == GAP


# --- G2: a code span holding an opener --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["f1_details_codespan_closed", "f1_details_codespan_unclosed", "f1_div_codespan_unclosed"])
def test_g2_code_span_opener_github_hides_f1_so_the_check_reports_it_missing(name):
    assert not github_shows_f1(BY_ID[name])
    check_f1_row(BY_ID[name])


@pytest.mark.parametrize("source, expected", [
    # #2389 review (test-role s1): the span is kept only up to its opener, so text inside the span after the opener never counts
    # #2389 vet 856: an item where a cut fires counts as nothing, so every expected value below that kept the text before the cut is ""
    ("a `<!--` tail\n", ""),  # #2389 vet 856: was "a `"
    ("a `<?` tail\n", ""),  # #2389 vet 856: was "a `"
    ("a `<!X` tail\n", ""),  # #2389 vet 856: was "a `"
    # #2389 catch-up 41e75711: md_hidden now reads this line UNSURE (a backtick in possible link metadata in a block that holds raw HTML),
    # so the leftover check blanks it whole and the line makes no item at all (was "a `"): stricter, no text of the line counts
    ("a `<![` tail\n", ""),
    ("a `see <?x` tail\n", ""),  # the opener is anywhere in the span's content; #2389 vet 856: was "a `see"
    ("a ``<!-- ` -->`` tail\n", ""),  # a double-backtick span; #2389 vet 856: was "a ``"
    ("a `<!--` tail\nnext -->\nz\n", ""),  # the lines after the cut are the item's, and are cut with it; #2389 vet 856: was "a `"
    ("a `<!--` tail", ""),  # a last line with no terminator; #2389 vet 856: was "a `"
    ("a `<b>` and `<` and `!` c\n", ""),  # #2389 V849-1: was "a span without an opener, kept whole"; `<b` is an entry; #2389 vet 856: was "a `"
])
def test_g2_code_span_opener_keeps_the_span_then_cuts_the_item(source, expected):
    assert item_cut(source) == expected
    assert line_count(la._visible(source)) == line_count(source)


# #2389 V849-1: `<b>` left this list (it is cut above); `a < b` and `</>` are no entry
@pytest.mark.parametrize("source", ["a `x` b `y z` c\n", "a ``x ` y`` b\n", "a `<` and `!` c `a < b` `</>`\n", "a ` b\n"])
def test_g2_code_span_opener_a_span_without_an_opener_changes_nothing(source):
    assert la._visible(source) == source
    assert item_cut(source) == source.strip()


def test_g2_code_span_opener_ready_write_refuses_leftover_not_accepted(tmp_path):
    row = BY_ID["f1_details_codespan_closed"]  # carries a verdict in place of the reminder; the write replaces that slot
    result, fake = write(row["body"], [RECEIPT, record_comment([FINDING])], tmp_path)
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted", result
    assert fake.edited == []


def test_g2_code_span_opener_the_unclosed_twin_is_stopped_earlier_and_never_written(tmp_path):
    # same as the G1 twin: the open comment makes md_hidden read the marker line hidden, so evaluate refuses write-failed first
    row = BY_ID["f1_div_codespan_unclosed"]
    result, fake = write(row["body"], [RECEIPT, record_comment([FINDING])], tmp_path)
    assert result["ok"] is False and result["reason"] in ("leftover-not-accepted", "write-failed"), result
    assert fake.edited == []


def test_g2_code_span_opener_model_only_an_acceptance_before_the_span_still_counts():
    # model-only (no GitHub render): the order's healthy row
    # #2389 vet 856: was `== []`; the code span holds an entry `<`, a cut, so the item counts as nothing and F-1 reads missing
    assert missing(body("- F-1 The retry loop never backs off; the note quotes `<!--` here\n")) == GAP


def test_g2_code_span_opener_model_only_an_ordinary_code_span_keeps_the_whole_line():
    source = "- F-1 The retry loop never backs off `vet_slot.py` \\* note\n"
    assert la._visible(source) == source
    assert missing(body(source)) == []


# --- G3: a processing instruction, declaration or CDATA section -------------------------------------------------

def hidden_tails(row):
    """{line number: the tokens, from each ``<?`` / ``<!X`` / ``<![CDATA[`` opener to the end of its line, that GitHub's
    shown text does not hold}."""
    shown = set(shown_text(row["html"]).split())
    found = {}
    for n, line in enumerate(md_fence.split_lines(row["body"])):
        for opener in re.finditer(r"<!\[CDATA\[|<\?|<![A-Za-z]", line):
            found.setdefault(n, set()).update(t for t in line[opener.start():].split() if t not in shown)
    return {n: tokens for n, tokens in found.items() if tokens}


def test_g3_pi_declaration_the_class_rows_are_the_eleven_taken_from_the_advisor_renders():
    assert len(CLASS_ROWS) == 11
    assert {row["id"].split("_")[0] for row in CLASS_ROWS} == {"pi", "decl", "cdata"}


@pytest.mark.parametrize("row", CLASS_ROWS, ids=ids(CLASS_ROWS))
def test_g3_pi_declaration_class_oracle_text_github_hides_inside_the_opener_is_not_kept(row):
    hidden = hidden_tails(row)
    assert hidden, "the row must hold text GitHub hides after an opener, else it proves nothing"
    # #2389 redesign: the row is placed under the accepting heading and read as items; no hidden token may survive in any cut item
    kept = set(" ".join(cuts(HEAD + row["body"])).split())
    tokens = set().union(*hidden.values())
    assert not tokens & kept, "%r kept %r" % (row["id"], tokens & kept)


@pytest.mark.parametrize("source, expected", [
    # #2389 catch-up 66130a25: md_hidden now reads a line where a PI, declaration or CDATA section hides text UNSURE, so the leftover
    # check blanks it whole, and the line makes no item at all (was "keep " + terminator)
    ("keep <? hide ?> x\n", ""),
    ("keep <!X hide>\n", ""),
    ("keep <![CDATA[ hide ]]>\n", ""),
    ("keep <!DOCTYPE hide>\n", ""),
    # #2389 catch-up 66130a25: the same cut-from-the-opener rule, on lines md_hidden still reads VISIBLE (the closer is absent, so no
    # text is hidden within the line): the cut still runs and keeps the text before the opener
    # #2389 vet 856: the cut still runs, and now the whole item counts as nothing instead of keeping the text before the opener
    ("keep <? hide x\n", ""),  # #2389 vet 856: was "keep"
    ("keep <!X hide\n", ""),  # #2389 vet 856: was "keep"
    # #2389 catch-up 41e75711: md_hidden now reads this line UNSURE, so the leftover check blanks it whole (was "keep"): stricter,
    # no text of the line counts
    ("keep <![CDATA[ hide ]]\n", ""),
    ("keep <!DOCTYPE hide\n", ""),  # #2389 vet 856: was "keep"
    ("keep <?\n", ""),  # #2389 vet 856: was "keep"
    ("- list <?x hide", ""),  # a last line with no terminator; #2389 vet 856: was "list"
    # #2389 V849-1: a tag, and `<!` followed by anything, are entries now (they were kept whole)
    ("a <b> c < d <3 e\n", ""),  # #2389 vet 856: was "a"
    ("a <!- b <! c <!1 d\n", ""),  # #2389 vet 856: was "a"
    ("a < b <3 <> </> <\n", "a < b <3 <> </> <"),  # a `<` followed by a space, a digit, `>`, `/>` or a line end is no entry
])
def test_g3_pi_declaration_cuts_from_the_opener_and_keeps_what_is_not_one(source, expected):
    assert item_cut(source) == expected
    assert line_count(la._visible(source)) == line_count(source)


def test_g3_pi_declaration_a_plain_comment_stops_the_item_at_the_unclosed_opener_and_at_blanked_lines():
    # #2389 redesign: there is no comment state to carry. The `<!-- a` line is read VISIBLE by md_hidden and its unclosed comment cuts
    # the item; the two lines inside the comment are hidden and blanked, so they stop it too. The last line (a comment that hides text)
    # is blanked whole by md_hidden (#2389 catch-up 66130a25)
    source = "keep\n<!-- a\nhidden\n-->\nafter <!-- b --> c\n"
    # #2389 catch-up 41e75711 (loosened, matches GFM: an HTML comment block interrupts the paragraph and the next line is its own shown block):
    # md_hidden now reads the `<!-- a` line HIDDEN too, so it is blanked with the two lines under it (was kept)
    assert la._visible(source) == "keep\n\n\n\n\n"
    assert cuts(HEAD + source) == ["keep"]
    # #2389 catch-up 66130a25: the same shape with an empty comment, which hides no text, so md_hidden reads the last line VISIBLE. The
    # blanked lines under `keep` are stop points of the item `keep`
    source = "keep\n<!-- a\nhidden\n-->\nafter <!----> c\n"
    # #2389 catch-up 41e75711 (loosened, matches GFM: an HTML comment block interrupts the paragraph and the next line is its own shown block):
    # `<!-- a` is blanked too (was kept), and `after <!----> c` is a block of its own, so it is a second item (its closed empty
    # comment is dropped, the text on both sides kept: "after " and " c" joined)
    assert la._visible(source) == "keep\n\n\n\nafter <!----> c\n"
    assert cuts(HEAD + source) == ["keep", "after " + " c"]


def test_g3_pi_declaration_br684_3_a_processing_instruction_line_is_not_an_acceptance():
    # class evidence: the pi_* and cdata_* rows above (GitHub hides what is inside); this exact body has no render
    assert missing(body("<? F-1 The retry loop never backs off ?>\n")) == GAP


def test_g3_pi_declaration_br684_3_a_declaration_list_item_is_not_an_acceptance():
    # class evidence: the decl_* rows above; this exact body has no render
    assert missing(body("- Accepting <!X F-1 The retry loop never backs off>\n")) == GAP


def test_g3_pi_declaration_br684_3_a_cdata_section_is_not_an_acceptance():
    # class evidence: the cdata_* rows above; this exact body has no render
    assert missing(body("- Accepting <![CDATA[ F-1 The retry loop never backs off ]]>\n")) == GAP


def test_g3_pi_declaration_model_only_an_acceptance_before_the_opener_still_counts():
    # #2389 catch-up 66130a25 (over-refusal, disclosed): a closed PI or declaration that hides text makes md_hidden read the line UNSURE, and
    # the leftover check blanks it whole, so the acceptance written before the opener now reads missing (was []). It fails closed.
    assert missing(body("- F-1 The retry loop never backs off <? a note ?>\n")) == GAP
    assert missing(body("- F-1 The retry loop never backs off <!X a note>\n")) == GAP
    # #2389 catch-up 66130a25: the same acceptance before an opener whose closer is absent: md_hidden reads the line VISIBLE, the cut keeps
    # the text before the opener, and the acceptance still counts
    # #2389 vet 856: was `== []` for both; the unclosed opener is a cut (an entry `<`), so the item counts as nothing and F-1 reads missing
    assert missing(body("- F-1 The retry loop never backs off <? a note\n")) == GAP
    assert missing(body("- F-1 The retry loop never backs off <!X a note\n")) == GAP


# --- G4: a line md_fence calls fenced ---------------------------------------------------------------------------

@pytest.mark.parametrize("source, expected", [
    # #2389 redesign: a fenced line is kept literally and cut at its first entry `<`, and the cut runs to the item's end (the fence's
    # closing line is the item's too). Was: a fenced line holding an opener was blanked whole.
    # #2389 vet 856: an entry `<` on a fenced line makes the whole item count as nothing, so every expected value below is ""
    ("```\nkeep <!-- cut -->\n```\n", ""),  # #2389 vet 856: was "``` keep"
    ("```\nkeep <? cut ?>\n```\n", ""),  # #2389 vet 856: was "``` keep"
    ("~~~\nkeep <!X cut>\n~~~\n", ""),  # #2389 vet 856: was "~~~ keep"
    ("```\nkeep <![CDATA[ cut ]]>\n```\n", ""),  # #2389 vet 856: was "``` keep"
    ("```\n<!-- first --> and <? second ?>\n```\n", ""),  # #2389 vet 856: was "```"
    ("```\nkeep <!-- cut\n```\nafter\n", ""),  # #2389 vet 856: was "``` keep"
    ("```\nkeep <!-- cut", ""),  # #2389 vet 856: was "``` keep"
    ("~~~\nplain <b> text < 3 `x` \\* y\n~~~\n", ""),  # #2389 vet 856: was "~~~ plain"
])
def test_g4_fenced_line_opener_cuts_a_fenced_line_at_its_first_opener(source, expected):
    assert la._visible(source) == source  # md_hidden reads fence content VISIBLE: `_visible` blanks nothing here
    assert item_cut(source) == expected


@pytest.mark.parametrize("source, expected", [
    ("```\n- F-1 The retry loop never backs off\n```\n", ["```", "F-1 The retry loop never backs off ```"]),
    ("~~~\nplain < 3 `x` \\* y </>\n~~~\n", ["~~~ plain < 3 `x` \\* y </> ~~~"]),  # #2389 V849-1: `<b>` replaced by `</>`, which is no entry
    ("```\n\n```\n", ["```", "```"]),  # the walk's grouping: a blank line inside a fence ends a paragraph item (segmentation is unchanged)
])
def test_g4_fenced_line_opener_a_fenced_line_holding_no_opener_is_kept_whole(source, expected):
    assert la._visible(source) == source
    assert cuts(HEAD + source) == expected


def test_g4_fenced_line_opener_model_only_a_real_fenced_block_with_no_opener_is_unchanged_under_the_heading():
    source = "## What we're accepting\n\n```\n- F-1 The retry loop never backs off\n```\n"
    assert la._visible(source) == source


def test_g4_fenced_line_opener_br684_2_a_tilde_line_inside_a_raw_pre_block_is_not_trusted():
    # model-only: this exact body has no render. Layer 1's fixture row `pre_raw_opener`
    # (fixtures/md_hidden_github_renders_2366.json) shows GitHub hiding a `<!--` inside `<pre>`, where md_fence still
    # calls the tilde lines a fence.
    accepting = "<pre>\n~~~\n<!-- F-1 The retry loop never backs off -->\n~~~\n</pre>\n"
    assert missing(body(accepting)) == GAP


# --- the control and the fail-closed edges kept -----------------------------------------------------------------

def test_the_control_row_is_accepted_and_a_ready_write_is_not_refused_for_it(tmp_path):
    row = BY_ID["f1_control_list_item"]
    assert github_shows_f1(row)
    result, fake = write(row["body"], [RECEIPT, record_comment([FINDING])], tmp_path)
    # #2389 vet 856: was `not (ok is False and reason == "leftover-not-accepted")`, which also passed for a write that failed on any
    # other reason before it reached the leftover check. In `vet_slot._run_verb` the leftover check (`check_leftovers`) runs after
    # `evaluate` and before the body re-read, the `gh pr edit` push and the readback, so a write that passed it is `ok` with one edit pushed
    assert result["ok"] is True, result
    assert len(fake.edited) == 1


@pytest.mark.parametrize("source", [
    "", "\\", "\\<", "\\<!", "`", "`<!--", "``<?`", "<", "<!", "<?", "<![", "<!--", "\\<!--", "```\n<!--", "```\n<",
    "a\r\nb <? c\rd `<!--` e\n\u2028<?", "\x00<!X\x0b`<![`", "<!-- superheroes:x --> <?\n",
])
def test_edge_visible_on_a_str_never_raises_and_only_removes_text(source):
    out = la._visible(source)
    assert isinstance(out, str)
    assert len(out) <= len(source)  # text is only ever removed
    assert line_count(out) <= line_count(source)
    # the item readers never raise on a str either, and their answers are lists
    assert isinstance(la._accepting_items(source), list)
    assert isinstance(la._accepting_items(HEAD + source), list)
    assert isinstance(la._cut_items(HEAD + source)[0], list)
    assert la.missing(read_ok(FINDING), HEAD + source) in (GAP, [])


@pytest.mark.parametrize("ending", ["\n", "\r", "\r\n"])
def test_edge_the_output_keeps_the_input_line_count_under_every_line_ending(ending):
    source = ending.join(["a \\<!-- b", "c `<?` d", "e <!X f", "```", "g <![CDATA[ h", "```", "tail", ""])
    assert line_count(la._visible(source)) == line_count(source)


def test_edge_the_whole_line_superheroes_marker_is_kept():
    assert la._visible("<!-- superheroes:build-record -->\n") == "<!-- superheroes:build-record -->\n"


def test_edge_an_internal_md_hidden_error_still_blanks_every_non_marker_line(monkeypatch):
    def fail(_text):
        raise RuntimeError("boom")

    monkeypatch.setattr(la.md_hidden, "_scan", fail)
    source = "keep\n<!-- superheroes:build-record -->\n```\nfenced <?x\n```\nlast"
    assert la._visible(source) == "\n<!-- superheroes:build-record -->\n\n\n\n"


# --- Review fixes (#2389 returning review, scoped finder): G5 tail comment state, G6 fixed-above tail, G7 fence delimiter ---

def test_g5_tail_comment_a_comment_the_cut_tail_opens_still_hides_later_lines():
    # scoped-finder-001: the cut at <!X> must not skip the later unclosed <!--, which hides the next lines in the paragraph
    body = ("## What we're accepting\n\nNote <!X> <!--\nF-1 The retry loop never backs off\n-->\n\n"
            "## How to see it\n\nN/A\n")
    assert "F-1" not in la._visible(body)
    assert missing(body), "F-1 must not count as accepted"


def test_g5_tail_comment_a_tail_comment_that_closes_on_its_line_opens_nothing():
    body = "## What we're accepting\n\nNote <!X> <!-- a -->\n- F-1 The retry loop never backs off\n"
    assert "F-1 The retry loop never backs off" in la._visible(body)
    assert missing(body) == []


# (#2389: the claim-cut tests that pinned the per-block blanking are replaced by the G10 tests at the end of this file)

def test_g6_fixed_above_tail_a_tail_without_a_claim_keeps_the_acceptance():
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off; quoting `<!--`; more text\n"
    # #2389 vet 856: was `== []`; the code span holds an entry `<`, a cut, so the item counts as nothing and F-1 reads missing
    assert missing(body) == GAP


def test_g7_fence_delimiter_a_fenced_line_holding_an_opener_never_closes_the_fence():
    # scoped-finder-003: "``` <!-- note -->" inside a backtick fence is content; the fence stays open and the sample heading below
    # it is not the live acceptance section. #2389 redesign: nothing is shortened, so no cut can make it a closer
    body = ("## What we're accepting\n\nNone.\n\n## How to see it\n\n````\n```\n``` <!-- note -->\n"
            "## What we're accepting\n\n- F-1 The retry loop never backs off\n```\n````\n")
    assert "``` <!-- note -->\n" in la._visible(body)
    assert not f1_counted(body)
    assert missing(body), "the fenced sample acceptance must not count"


# --- Fix-audit round 2 (#2389): the two not-discharged audits ---------------------------------------------------------

def test_g7_fence_delimiter_an_opener_line_holding_an_opener_stays_an_opener():
    # audit of scoped-finder-003: an opener line holding an opener is left whole, so the sample below it stays fenced
    body = ("## What we're accepting\n\nNone.\n\n## How to see it\n\n```md <!-- note -->\n"
            "## What we're accepting\n\n- F-1 The retry loop never backs off\n```\n")
    assert "```md <!-- note -->\n" in la._visible(body)
    assert not f1_counted(body)
    assert missing(body), "the fenced sample acceptance must not count"


def test_g7_fence_delimiter_a_content_line_holding_an_opener_is_cut_at_it_to_the_items_end():
    # #2389 redesign: was `_visible(...) == "````\n\n````\n"`; the item cut keeps the fence run and cuts the content line at the `<`
    assert la._visible("````\n``` <!-- note -->\n````\n") == "````\n``` <!-- note -->\n````\n"
    # #2389 vet 856: was "```` ```"; an entry `<` on a fenced line makes the item count as nothing
    assert item_cut("````\n``` <!-- note -->\n````\n") == ""


def test_g8_comment_state_a_quoted_tail_opener_never_swallows_the_next_heading():
    # round-2 scoped finder (v1): a code-spanned `<!--` in a cut tail over-sets the comment state; it must end at the
    # visible heading that bounds the acceptance section, so text under How to see it never counts as an acceptance
    body = ("## What we're accepting\n\nNote `<?` and `<!--`\n## How to see it\n\n- F-1 The retry loop never backs off\n"
            "-->\n")
    out = la._visible(body)
    assert "## How to see it" in out
    assert missing(body), "text under How to see it must not count as an acceptance"


def test_g8_comment_state_an_inline_comment_never_crosses_a_blank_line():
    body = "## What we're accepting\n\nx <!--\n\n- F-1 The retry loop never backs off -->\n"
    assert "F-1 The retry loop never backs off" in la._visible(body)
    # #2389 redesign: the list item after the blank line is its own item, and the cut of `x <!--` is that paragraph's alone
    assert missing(body) == []


def test_g8_comment_state_a_raw_comment_block_across_a_blank_line_still_hides():
    body = "## What we're accepting\n\n<!--\n\n- F-1 The retry loop never backs off\n-->\n"
    assert "F-1" not in la._visible(body)
    assert missing(body)


# --- #2389 second rework: a removed fixed-above claim voids the body (G10) ---

ACCEPTING = "## What we're accepting\n\n"
HOW = "\n\n## How to see it\n\nN/A\n"


@pytest.mark.parametrize("accepting", [
    # 1. the single-line cut claim
    "- F-1 The retry loop never backs off; quoting `<!--`; fixed-above #99 abcdef0",
    # 2. the claim on a continuation line
    "- F-1 The retry loop never backs off\n  quoting `<!--`; fixed-above #99 abcdef0",
    # 3. the wrapped claim, cut on its first line
    "- F-1 The retry loop never backs off; quoting `<!--`; fixed-above #99\n  abcdef0",
    # 4. removed by the cut of an earlier line of the item
    "- F-1 The retry loop never backs off; quoting `<?` and `<!--`\n  fixed-above #99 abcdef0\n",
    # 5. on an ATX subheading
    "### F-1 The retry loop never backs off; quoting `<!--`; fixed-above #99 abcdef0",
], ids=["single_line", "continuation_line", "wrapped", "inside_comment", "subheading"])
def test_g10_claim_removed_voids_the_body_so_every_leftover_reads_missing(accepting):
    text = ACCEPTING + accepting + HOW
    # #2389 vet 856: was `_cut_items(text)[1] is True`; the body-wide void is retired (the flag is always False), and the item that
    # lost its claim counts as nothing by itself (a cut fired in it, or its claims differ from its source span's)
    assert la._cut_items(text)[1] is False
    assert all(item == "" for item in cuts(text))
    assert missing(text) == GAP
    assert la._accepting_items(text) == []


def test_g10_claim_removed_the_exact_bodies_of_the_order_without_the_section_frame():
    for text in ["- F-1 The retry loop never backs off; quoting `<!--`; fixed-above #99 abcdef0",
                 "- F-1 The retry loop never backs off; quoting `<?` and `<!--`\n  fixed-above #99 abcdef0\n",
                 "### F-1 The retry loop never backs off; quoting `<!--`; fixed-above #99 abcdef0"]:
        text = body(text)
        assert missing(text) == GAP
        assert la._accepting_items(text) == []


def test_g10_claim_removed_control_an_unhidden_claim_keeps_its_acceptance():
    text = body("- F-1 The retry loop never backs off; fixed-above #99 abcdef0\n")
    assert la._cut_items(text)[1] is False
    assert missing(text) == []
    assert [item for item in la._accepting_items(text) if "fixed-above #99 abcdef0" in item]


def test_g10_claim_removed_a_tail_without_a_claim_does_not_void_the_body():
    text = ACCEPTING + "- F-1 The retry loop never backs off; quoting `<!--`; more text" + HOW
    assert la._cut_items(text)[1] is False
    # #2389 vet 856: was `== []`; the code span holds an entry `<`, a cut, so the item counts as nothing and F-1 reads missing
    assert missing(text) == GAP


def test_g10_claim_removed_the_text_and_the_flag_come_from_one_helper():
    source = HEAD + "- F-1 x `<!--` fixed-above #99 abcdef0\n"
    items, removed = la._cut_items(source)
    # #2389 vet 856: was `removed is True and items == ["F-1 x `"]`; the flag is always False and the cut item reads nothing
    assert removed is False and items == [""]
    assert la._accepting_items(source) == []


# --- Review session 3 round 1 (#2389): the structural guard (G12, retired), the per-line claim check (G13), the in-span cut (G2) ---

def test_g12_structure_a_fenced_f1_after_a_quoted_tail_opener_is_accepted_as_shown_code():
    # cr-s1-001: the quoted tail opener sets the comment state, which swallowed the fence opener below it in the old walk
    # #2389 redesign (loosened, BR853-5 ruling): the old answer was a void body (F-1 missing); the new answer is F-1 accepted.
    # GitHub shows the fenced `- F-1 The retry loop never backs off` line as code, and base 66130a25 reads fenced text as acceptance
    # text the same way (accepting_listed counts visible fenced text); the block-role guard that voided it is retired
    body = ("## What we're accepting\n\nNone.\n\nNote `<?` and `<!--`\n```\n## What we're accepting\n"
            "- F-1 The retry loop never backs off\n```\n")
    assert f1_counted(body)
    assert missing(body) == []


def test_g12_structure_a_cut_that_manufactures_a_fence_opener_voids_the_body():
    # seams-check: "```md <? ...`note" is text (a backtick in a backtick fence's info string); cutting at <? would make it a
    # fence opener that fences the How to see it heading into the acceptance section
    # #2389 redesign: the block-role guard is retired and the section is read before any cut, so the cut cannot manufacture the opener.
    # `None.` (with the `\`\`\`md` line, cut at `<?`) is the only item; F-1 sits under How to see it and is not an acceptance
    body = ("## What we're accepting\n\nNone.\n```md <? \u2028`note\n## How to see it\n\n```\n"
            "- F-1 The retry loop never backs off\n```\n")
    assert not f1_counted(body)
    assert missing(body)


def test_g12_structure_an_ordinary_inline_comment_cut_keeps_the_acceptances():
    # #2389 catch-up 66130a25 (over-refusal, disclosed): GitHub shows this acceptance, but md_hidden now reads a line where an inline
    # comment hides text UNSURE and the leftover check blanks it whole, so F-1 reads missing (was []). It fails closed.
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off <!-- a note -->\n"
    assert missing(body) == GAP
    # #2389 catch-up 66130a25: the same cut with an empty comment, which hides no text, so md_hidden reads the line VISIBLE and the
    # acceptance still counts
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off <!---->\n"
    assert missing(body) == []


def test_g13_claim_join_a_claim_joined_from_fragments_cannot_balance_a_removed_one():
    # cr-s1-002 / tr-s1-002: the comment cut joins "fixed-" and "above #99" into a new claim while the cut after `<?` removes
    # the real #98 claim; the counts balance, the whole-text claim comparison does not
    # #2389 review session 8: the joining comment is empty (`<!---->`, it hides no text), so md_hidden keeps the line VISIBLE
    # and the join happens (a `<!-- note -->` comment would make md_hidden blank the line whole); the balance is asserted
    body = ("## What we're accepting\n\n- F-1 The retry loop never backs off; fixed-<!---->above #99 abcdef0; "
            "`<?` fixed-above #98 1234567\n")
    # #2389 vet 856: was a count balance asserted on the cut text and `_cut_items(body)[1] is True`. The summed guards are retired: the
    # item holds a cut (`<?` in a code span), so it counts as nothing whatever claims the cut would have kept or joined
    assert raw_cuts(body) == [""]
    assert cuts(body) == [""]
    assert la._cut_items(body)[1] is False
    assert la._accepting_items(body) == []
    assert missing(body)


def test_g13_claim_join_a_claim_manufactured_by_a_comment_cut_alone_voids_the_body():
    # #2389 fix leg 2: the test above is also voided by the removal guard (the #98 claim is cut on the same line); this one has no removed
    # claim, so only the whole-text comparison (c) voids it. #2389 redesign: the per-line manufacture guard (b) is retired
    # #2389 catch-up 66130a25: the comment here is empty (`<!---->`), which hides no text, so md_hidden reads the line VISIBLE
    # (a `<!-- note -->` comment makes md_hidden read the line UNSURE; see the next test)
    body_ = "## What we're accepting\n\n- F-1 The retry loop never backs off; fixed-<!---->above #99 abcdef0\n"
    # #2389 vet 856: the manufactured claim is still seen before the per-item check (`raw_cuts`); `_cut_items` now blanks the item itself
    # (was `"fixed-above #99 abcdef0" in " ".join(cuts(body_))` and `_cut_items(body_)[1] is True`)
    assert "fixed-above #99 abcdef0" in " ".join(raw_cuts(body_))
    assert cuts(body_) == [""]
    assert la._cut_items(body_)[1] is False
    assert la._accepting_items(body_) == []
    assert missing(body_) == GAP


def test_g13_claim_join_a_claim_joined_by_a_comment_that_hides_text_is_blanked_whole():
    # #2389 catch-up 66130a25 (the old input of the test above): md_hidden now reads the line UNSURE and the leftover check blanks it
    # whole, so no claim is manufactured at all and F-1 still reads missing
    body_ = "## What we're accepting\n\n- F-1 The retry loop never backs off; fixed-<!-- note -->above #99 abcdef0\n"
    assert "fixed-above" not in la._visible(body_)
    assert la._accepting_items(body_) == []
    assert missing(body_) == GAP


def test_g13_claim_join_an_inline_comment_on_a_claim_line_keeps_the_claim():
    # #2389 catch-up 66130a25: the comment is empty (`<!---->`), which hides no text, so md_hidden reads the line VISIBLE and the claim stays
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off <!----> fixed-above #99 abcdef0\n"
    assert la._accepting_items(body) != []
    # #2389 catch-up 66130a25 (over-refusal, disclosed): with a `<!-- a note -->` comment GitHub shows the claim line, but md_hidden now
    # reads it UNSURE, the leftover check blanks it whole, and the acceptance on it is no longer counted (was != [])
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off <!-- a note --> fixed-above #99 abcdef0\n"
    assert la._accepting_items(body) == []


def test_g2_code_span_opener_text_inside_the_span_after_the_opener_never_counts():
    # tr-s1-001: inside a raw HTML line GitHub hides the comment inside the apparent code span
    # #2389 FU8: the `<div>` sits on a line of its own before the `Quoting` line, so the acceptance line reaches the code-span cut
    body = "## What we're accepting\n\n<div>\nQuoting `<!-- F-1 The retry loop never backs off -->`\n</div>\n"
    # #2389 redesign: `_visible` keeps the VISIBLE lines; the `<div>` entry already cuts the item to its end, so no cut item holds F-1
    assert "F-1" not in " ".join(cuts(body))
    assert missing(body)
    # the code-span cut on its own: the span is kept up to its opener, and the rest of the item is cut
    # #2389 vet 856: was "Quoting `"; the code span holds an entry `<`, a cut, so the item counts as nothing
    assert item_cut("Quoting `<!-- F-1 The retry loop never backs off -->`\n</div>\n") == ""


# --- #2389 fix leg 2 (vet 849): G14 the one entry condition, G15 the cut heading, G16 the claim fragment, G12's heading half ---

TITLE = "F-1 The retry loop never backs off"


# model-only (no render of these exact bodies in the repository). Vet receipt
# https://github.com/zwrose/superheroes/pull/2391#issuecomment-6713800197 rendered 36 of these shapes on GitHub: each bogus
# opener below, raw, escaped and code-spanned, on a `<div>` line, hides the rest of the line.
@pytest.mark.parametrize("opener", ["<! ", "<!-x", "<!1", "</ ", "</1"])
@pytest.mark.parametrize("form", ["raw", "escaped", "code_span"])
@pytest.mark.parametrize("lead", ["<div>Accepting ", "Accepting "], ids=["div_line", "plain_line"])
def test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line(opener, form, lead):
    quoted = {"raw": opener, "escaped": "\\" + opener, "code_span": "`" + opener + "`"}[form]
    text = body(lead + quoted + " " + TITLE + "\n</div>\n")
    assert missing(text) == GAP
    assert TITLE not in " ".join(cuts(text))


@pytest.mark.parametrize("item", [
    "- F-1 <The retry loop never backs off>",
    "- Accepting <a F-1 The retry loop never backs off>",
    "- <F-1 The retry loop never backs off>",
    "- <span title=\" F-1 The retry loop never backs off\"></span>",
], ids=["tag_before_title", "tag_before_id", "tag_before_item_text", "attribute_value"])
def test_g14_tag_entry_an_inline_tag_hides_the_acceptance_written_after_it(item):
    assert missing(body(item + "\n")) == GAP


@pytest.mark.parametrize("item", [
    "- F-1 The retry loop never backs off; see a < b",  # a `<` followed by a space is text
    "- F-1 The retry loop never backs off </>",  # an empty end tag is nothing
], ids=["less_than_space", "empty_end_tag"])
def test_g14_tag_entry_controls_a_less_than_that_is_no_entry_still_counts(item):
    text = body(item + "\n")
    assert item in la._visible(text)
    assert missing(text) == []


def test_g14_tag_entry_the_cut_runs_to_the_items_end_whatever_the_tail_holds():
    # #2389 redesign: there is no comment state to set or carry (was: the entry itself sets none but the cut tail is read). Every entry
    # cuts the rest of the item, so the lines under it are cut with it, and a tail comment changes nothing
    # #2389 vet 856: these three were "a"; a cut makes the whole item count as nothing
    assert item_cut("a \\<!-- c\nnext\n") == ""
    assert item_cut("a \\<b> <!-- c\nnext\n") == ""
    assert item_cut("a <b> <!-- c\nnext\n") == ""
    # #2389 catch-up 66130a25: md_hidden now reads the line `a <b> <!-- c --> d` (a comment that hides text) UNSURE, so it is blanked
    # whole (was "a "); `next` is then a paragraph of its own
    assert cuts(HEAD + "a <b> <!-- c --> d\nnext\n") == ["next"]
    # #2389 catch-up 66130a25: the same shape with an empty tail comment, which hides no text, so the line stays VISIBLE and is cut at `<b>`
    assert item_cut("a <b> <!----> d\nnext\n") == ""  # #2389 vet 856: was "a"


# --- G15: a cut heading voids the body (BR684-E-1; the guard is retired, the section is read before any cut) ---

def test_g15_cut_heading_a_cut_in_a_later_heading_voids_the_body():
    text = "## What we're accepting\n\nNone.\n\n## How to see it <kbd>x</kbd>\n- F-1 The retry loop never backs off\n"
    # #2389 redesign: the heading is read from the source, so it ends the section before any cut; F-1 is under it and is no acceptance
    assert la._cut_items(text) == (["None."], False)
    assert la._accepting_items(text) == []


def test_g15_cut_heading_a_cut_in_the_accepting_heading_voids_the_body_and_reports_f1_missing():
    # without the guard the cut heading still reads as the accepting heading, and the item below it counts
    # #2389 redesign: the heading is read from the source, where it is not the accepting heading, so there is no section at all
    text = "## What we're accepting <kbd>example only</kbd>\n- F-1 The retry loop never backs off\n"
    assert la._accepting_items(text) == []
    assert missing(text) == GAP


def test_g15_cut_heading_control_a_heading_with_no_cut_is_not_void():
    text = "## What we're accepting\n\n- F-1 The retry loop never backs off <kbd>x</kbd>\n\n## How to see it\n\nN/A\n"
    assert la._cut_items(text)[1] is False
    # #2389 vet 856: was `== []`; the item holds an entry `<` (`<kbd>`), a cut, so it counts as nothing and F-1 reads missing
    assert missing(text) == GAP


# --- G12, the heading half of the block-role guard (retired) ---

def test_g12_structure_heading_half_a_cut_that_makes_a_line_an_atx_heading_voids_the_body():
    # `#<?x` is no heading in its source (the `#` is followed by `<`); the cut leaves `#`, an ATX heading
    # #2389 redesign (BR853-5 (ii), loosened answer: F-1 was missing, is now accepted): the section is read before the cut, so `#<?x` stays
    # a paragraph and the cut cannot make it a heading. The F-1 item is clean: it starts at its own `- ` marker (a bullet interrupts the
    # paragraph, and md_hidden reads both lines VISIBLE, so GitHub shows it as its own list item), and its span holds one line with
    # no entry `<`, no hidden line and no dropped line, so nothing hidden and no joined words reach it
    text = "## What we're accepting\n\nNone.\n\n#<?x\n- F-1 The retry loop never backs off\n"
    assert item_cut("#<?x\n") == ""  # #2389 vet 856: was "#"; the entry `<?` makes the item count as nothing
    assert la._cut_items(text)[1] is False
    assert missing(text) == []


# --- G16: a claim fragment voids the body (BR684-E-2; the per-line half is retired, the whole-text guards stay) ---

def claim_fragment_body():
    """BR684-E-2's counterexample: the #98 claim wraps across two lines and an inline tag cuts its first line, while a
    comment-joined #99 claim sits below the build-record marker, so the token and claim counts balance.

    #2389 review session 8: the joining comment is empty (`<!---->`, it hides no text), so md_hidden (layer 1 at 66130a25)
    reads its line VISIBLE and the join happens; a non-empty comment would blank the line whole and unbalance the counts."""
    text = body("- F-1 The retry loop never backs off <b>x</b> fixed-above #98\n  1234567\n")
    return text.replace("<details><summary>Build record</summary>\n\n",
                        "<details><summary>Build record</summary>\n\nfixed-<!---->above #99 abcdef0\n\n", 1)


def test_g16_claim_fragment_a_claim_outside_the_section_cannot_balance_the_removed_one_so_the_body_is_void(tmp_path):
    text = claim_fragment_body()
    assert "fixed-<!---->above #99 abcdef0" in text
    # #2389 redesign: the guards compare each cut item with the source lines of its own span, so the #99 claim in the build record (outside
    # the section) cannot balance the #98 claim the cut removed from the item
    assert la.FIXED_ABOVE_RE.findall(" ".join(source_texts(text))) == [("98", "1234567")]
    assert la.FIXED_ABOVE_RE.findall(" ".join(cuts(text))) == []
    assert la._cut_items(text)[1] is False  # #2389 vet 856: was `is True`; the void is retired, the item counts as nothing (a cut fires in it)
    assert cuts(text) == [""]
    assert la._accepting_items(text) == []
    assert missing(text) == GAP
    result, fake = write(text, [RECEIPT, record_comment([FINDING])], tmp_path)
    assert result["ok"] is False and result["reason"] == "leftover-not-accepted", result
    assert fake.edited == []


def test_g16_claim_fragment_control_an_inline_comment_on_a_claim_line_keeps_its_acceptance():
    # #2389 catch-up 66130a25: the comment is empty (`<!---->`), which hides no text, so md_hidden reads the line VISIBLE and the claim stays
    text = body("- F-1 The retry loop never backs off <!----> fixed-above #99 abcdef0\n")
    assert la._cut_items(text)[1] is False
    assert la._accepting_items(text) != []
    assert missing(text) == []
    # #2389 catch-up 66130a25 (over-refusal, disclosed): with a `<!-- a note -->` comment GitHub shows the claim line, but md_hidden now
    # reads it UNSURE, the leftover check blanks it whole, and the line makes no item (was a void body)
    text = body("- F-1 The retry loop never backs off <!-- a note --> fixed-above #99 abcdef0\n")
    assert "fixed-above #99" not in la._visible(text)
    assert la._accepting_items(text) == []
    assert missing(text) == GAP


def test_g16_claim_fragment_a_wrapped_claim_cut_on_its_first_line_voids_though_a_joined_wrapped_one_balances_the_counts():
    # the claim is whole only across two lines of the item, and the inline tag cuts the first
    # #2389 review session 8: the joined claim is the identical wrapped #98 1234567 claim, joined by an empty comment in the build record
    # (`<!---->` hides no text, so md_hidden keeps its line VISIBLE). #2389 redesign: the build record is outside the section, so it cannot
    # balance the item's own removed claim
    text = body("- F-1 The retry loop never backs off <b>x</b> fixed-above #98\n  1234567\n")
    text = text.replace("<details><summary>Build record</summary>\n\n",
                        "<details><summary>Build record</summary>\n\nfixed-<!---->above #98\n1234567\n\n", 1)
    assert "fixed-<!---->above #98\n1234567" in text
    assert la.FIXED_ABOVE_RE.findall(" ".join(source_texts(text))) == [("98", "1234567")]
    assert la.FIXED_ABOVE_RE.findall(" ".join(cuts(text))) == []
    assert la._cut_items(text)[1] is False  # #2389 vet 856: was `is True`; the void is retired, the item counts as nothing (a cut fires in it)
    assert cuts(text) == [""]
    assert la._accepting_items(text) == []
    assert missing(text) == GAP


def test_g21_source_span_claims_a_prose_mention_after_a_cut_does_not_void_the_body():
    # #2389 WO-H3 (the real body of PR #2391): the item's cut removes the bare word "fixed-above" after a code span holding `<`, but the
    # word is not a claim (no PR, no commit), so the guards, which compare whole claims only, do not void the body
    text = body("- F-1 The retry loop never backs off\n"
                "- The check refuses text after an autolink (`<https://x>`), and a\n"
                "  fixed-above bullet whose line holds a comment\n")
    bare = re.compile(r"(?<![A-Za-z0-9_-])fixed-above(?![A-Za-z0-9_])", re.IGNORECASE)
    # the precondition: the cut really removes a bare mention that the source span holds, and neither holds a whole claim
    assert len(bare.findall(" ".join(cuts(text)))) < len(bare.findall(" ".join(source_texts(text))))
    assert la.FIXED_ABOVE_RE.findall(" ".join(source_texts(text))) == []
    assert la._cut_items(text)[1] is False
    assert missing(text) == []


def test_g16_claim_fragment_a_quoted_placeholder_cut_by_rule_1_keeps_the_acceptances():
    # the PR #2348 body quotes the syntax `fixed-above #<layer PR> <commit>` in a code span; rule 1 cuts it at `<layer`, but
    # a placeholder is no claim, so it can neither hide nor manufacture one and the F-1 acceptance still counts
    text = body("- F-1 The retry loop never backs off\n").replace(
        "A change.\n", "A change. Syntax: `fixed-above #<layer PR> <commit>`\n", 1)
    # #2389 redesign: that line is outside the section, so nothing cuts it; the same quoted placeholder inside the item is cut at `<layer`
    assert "Syntax: `fixed-above #<layer PR> <commit>`\n" in la._visible(text)
    assert la._cut_items(text)[1] is False
    assert la._accepting_items(text) != []
    assert missing(text) == []
    inside = body("- F-1 The retry loop never backs off; Syntax: `fixed-above #<layer PR> <commit>`\n")
    # #2389 vet 856: was `(["F-1 The retry loop never backs off; Syntax: `fixed-above #"], False)` and `missing(inside) == []`; the code span
    # holds an entry `<`, a cut, so the item counts as nothing (a disclosed over-refusal: the quoted placeholder sits inside the item)
    assert la._cut_items(inside) == ([""], False)
    assert missing(inside) == GAP


def test_g16_claim_fragment_control_the_plain_words_without_a_claim_do_not_void_the_body():
    text = body("- F-1 The retry loop never backs off; fixed above <b>x</b>\n")
    assert la._cut_items(text)[1] is False
    # #2389 vet 856: was `== []`; the item holds an entry `<` (`<b>`), a cut, so it counts as nothing and F-1 reads missing
    assert missing(text) == GAP


# --- #2389 fix leg 3 (vet 852): G17 the fence reading, G18 the whole-text claim comparison ---
# model-only (no render of these exact bodies in the repository). Vet receipt
# https://github.com/zwrose/superheroes/pull/2391#issuecomment-6715314903 (V852-1, BR852-1, V852-2).
# #2389 redesign (vet 853, receipt https://github.com/zwrose/superheroes/pull/2391#issuecomment-6717053345): the fence guards G17a and G17b
# are retired, because the section reader reads the source structure and no cut can manufacture or move a fence. The void assertions
# became "F-1 is missing", which is the outcome each guard protected.

# #2389 catch-up 66130a25: `<?x?>` is a PI that holds text, so md_hidden reads a line holding it UNSURE and the leftover check blanks
# the line whole (no cut, so no list fence opener is manufactured); `<??>` is a PI that holds no text, so the line stays VISIBLE.
G17_ENTRIES = ["<??>", "<?x?>", "<b>", "<!x>", "\\<b>", "<br>", "</x>"]
G17_BLANKED_ENTRIES = {"<?x?>"}


def assert_f1_missing(text):
    # #2389 redesign: the clean read finds no acceptance naming F-1 (the indented heading ends the section before it)
    assert not f1_counted(text)
    assert missing(text) == GAP


def assert_void_or_blanked_and_missing(entry, text):
    if entry in G17_BLANKED_ENTRIES:
        # #2389 catch-up 66130a25: the line is blanked whole, so no fence opener `- ```md ` is manufactured
        assert "```md" not in la._visible(text)
    assert_f1_missing(text)


@pytest.mark.parametrize("entry", G17_ENTRIES)
def test_g17_fence_shape_nested_item_a_cut_that_manufactures_a_list_fence_opener_voids_the_body(entry):
    # `- ```md <E> `note`` is text (a backtick in a backtick fence's info string); the cut leaves `- ```md `, a list-item fence
    # opener that fences the indented heading and F-1 into the acceptance section
    assert_void_or_blanked_and_missing(entry, HEAD + "None.\n- ```md %s `note`\n  ## How to see it\n  - %s\n" % (entry, TITLE))


@pytest.mark.parametrize("entry", G17_ENTRIES)
def test_g17_fence_shape_column_0_item_a_cut_that_manufactures_a_list_fence_opener_voids_the_body(entry):
    assert_void_or_blanked_and_missing(entry, HEAD + "None.\n- ```md %s `note`\n  ## How to see it\n\n- %s\n" % (entry, TITLE))


@pytest.mark.parametrize("entry", G17_ENTRIES)
def test_g17_fence_shape_ordered_a_cut_that_manufactures_a_list_fence_opener_voids_the_body(entry):
    assert_void_or_blanked_and_missing(entry, HEAD + "None.\n1. ```md %s `note`\n   ## How to see it\n   - %s\n" % (entry, TITLE))


@pytest.mark.parametrize("fence", ["```", "~~~"], ids=["backtick", "tilde"])
def test_g17_fence_shape_closer_a_cut_that_turns_a_content_line_into_the_closer_voids_the_body(fence):
    # `  ``` <b>` is content in the list fence (text after the run); the cut leaves `  ``` `, a closer, and the next run opens
    # a new fence over the heading. md_fence and the opener shape read the delimiter lines alike: only the walk's flags differ
    text = HEAD + "None.\n- %smd\n  %s <b>\n  %s\n  ## How to see it\n  - %s\n" % (fence, fence, fence + fence[0], TITLE)
    assert_f1_missing(text)


def test_g17_fence_shape_only_the_shape_a_manufactured_opener_inside_a_list_fence_voids_the_body():
    # the cut turns `  - ```x <b> `y`` (no fence: a backtick in the info string) into the opener `  - ```x ` while the walk is
    # already inside the list fence, so no fenced flag changes: only the line's fence_line_shape does
    text = HEAD + "None.\n- ```md\n  - ```x <b> `y`\n  ```\n- %s\n" % TITLE
    assert pr_sheet.fence_line_shape("  - ```x <b> `y`") is None
    assert pr_sheet.fence_line_shape("  - ```x ")[0] == "open"
    # #2389 redesign (BR853-5 (i), loosened answer: F-1 was missing, is now accepted). The item holding the cut list fence is
    # `- ```md` through its closing `  ```` and is cut at the `<b>`; the F-1 item after it is clean: it starts at its own `- ` marker at
    # column 0 (not indented to the fence item's content column, so it does not nest in it), md_hidden reads every line VISIBLE, and its
    # span holds one line with no entry `<`, no hidden line and no dropped line, so GitHub shows it as its own list item
    assert cuts(text) == ["None.", "", TITLE]  # #2389 vet 856: the cut item was "```md - ```x"; it now counts as nothing
    assert la._cut_items(text)[1] is False
    assert missing(text) == []


def test_g17_fence_shape_control_a_list_fence_with_no_cut_keeps_the_acceptance():
    text = HEAD + "None.\n- ```md\n  F-1 example\n  ````\n- %s\n" % TITLE
    assert la._cut_items(text)[1] is False
    assert missing(text) == []


def test_g17_fence_shape_control_an_invalid_list_fence_opener_with_no_entry_reads_as_before():
    # no `<`, so no cut and no void; `- ```md `note` opens no fence, so the indented heading ends the section and F-1 below it
    # is missing (the same answer as at fbc879bd)
    text = HEAD + "None.\n- ```md `note`\n  ## How to see it\n  - %s\n" % TITLE
    assert la._cut_items(text)[1] is False
    assert missing(text) == GAP


def test_g17_fence_shape_fence_line_shape_reads_the_walk():
    assert pr_sheet.fence_line_shape("- ```md") == ("open", "`", 3, "- ")
    assert pr_sheet.fence_line_shape("1. ~~~~") == ("open", "~", 4, "1. ")
    assert pr_sheet.fence_line_shape("```") == ("open", "`", 3, None)
    assert pr_sheet.fence_line_shape("    ```") == ("run", "`", 3, None)  # a bare run of any indent is a run (a closer sits past a list column)
    assert pr_sheet.fence_line_shape("  ```   ") == ("open", "`", 3, None)  # within three spaces it matches the opener pattern first
    assert pr_sheet.fence_line_shape("    ``` x") is None  # four columns of indent with text is no opener
    assert pr_sheet.fence_line_shape("- ```md `note") is None
    assert pr_sheet.fence_line_shape("text") is None
    assert pr_sheet.fence_line_shape("") is None
    assert pr_sheet.fence_line_shape(None) is None
    assert hash(pr_sheet.fence_line_shape("- ```md")) == hash(("open", "`", 3, "- "))


def test_g17_fence_shape_br852_1_a_fenced_f1_after_a_separator_comment_is_accepted_as_shown_code():
    # BR852-1: the comment line ends the list item in the source walk, but the cut text had a blank line there, so the old walk
    # read the fence differently in the two texts
    # #2389 redesign (loosened, BR853-5 ruling): the old answer was a void body (F-1 missing); the new answer is F-1 accepted.
    # GitHub shows the fenced `- F-1 The retry loop never backs off` line as code, and base 66130a25 reads fenced text as acceptance
    # text the same way (accepting_listed counts visible fenced text). The section is now read once, from the source, and the
    # fence-shape guard that voided it is retired
    text = ("## What we're accepting\n\n- Example\n\n<!-- separator -->\n\n  ```\n## What we're accepting\n"
            "- F-1 The retry loop never backs off\n  ```\n")
    # #2389 catch-up 41e75711: md_hidden now reads the `<!-- separator -->` line HIDDEN, so it is blanked and its blank line is a stop
    # point inside the `- Example` item that the fence line joins: F-1 under it is cut, so it is no longer counted and is missing
    # (was counted and accepted). Stricter (an over-refusal for text GitHub shows as code, the check's disclosed direction)
    assert not f1_counted(text)
    assert missing(text) == GAP


def test_g17_fence_shape_br852_1_f1_is_accepted_with_the_fence_guard_retired():
    # #2389 redesign (loosened, BR853-5 ruling): the old answer was F-1 missing (a void body); the new answer was F-1 accepted.
    # #2389 catch-up 41e75711: md_hidden now reads the `<!-- separator -->` line HIDDEN, so it is blanked and stops the `- Example` item
    # the fence line joins: F-1 under it is cut and reads missing again (was accepted). Stricter, never looser
    text = ("## What we're accepting\n\n- Example\n\n<!-- separator -->\n\n  ```\n## What we're accepting\n"
            "- F-1 The retry loop never backs off\n  ```\n")
    assert missing(text) == GAP


def test_g17_fence_shape_outside_comments_and_item_spans_read_the_one_walk():
    # #2389 redesign (V853-4): replaces the test that compared `fenced_lines` with the walk; `fenced_lines` is retired. `_outside_comments`
    # is the walk's kept lines, and `accepting_listed` is the join of the item spans of `accepting_item_spans` over every oracle body
    bodies = [row["body"] for row in ROWS]
    bodies.append((pathlib.Path(__file__).parent / "fixtures" / "i2332_pr2348_body.md").read_text(encoding="utf-8"))
    assert len(ROWS) == 18 and len(bodies) == 19
    listed_total = 0
    for text in bodies:
        lines = pr_sheet._markdown_lines(text)
        walked = [(n, line, fenced) for n, line, fenced, keep in pr_sheet._fence_walk(lines) if keep]
        assert pr_sheet._outside_comments(lines) == [(line, fenced) for _n, line, fenced in walked]
        spans = pr_sheet.accepting_item_spans(text)
        joined = []
        for span in spans:
            assert [n for n, _kind in span] == sorted({n for n, _kind in span})
            assert {kind for _n, kind in span} <= {"text", "fenced", "blank", "dropped"}
            assert span[0][1] in ("text", "fenced")
            parts = [lines[n][pr_sheet.item_text_start(lines[n]) if k == 0 else 0:].strip()
                     for k, (n, kind) in enumerate(span) if kind in ("text", "fenced")]
            joined.append(" ".join(part for part in parts if part))
        assert pr_sheet.accepting_listed(text) == pr_sheet.acceptance_texts(joined)
        listed_total += len(pr_sheet.accepting_listed(text))
    assert listed_total > 0, "the oracle bodies list no acceptance, so the join proves nothing"


def test_g18_whole_text_claims_a_cut_across_lines_forms_no_claim_and_f1_is_a_plain_acceptance():
    # V852-2: the source holds no whole claim (`fixed-above #98 <b> #99`); the cut at `<b>` leaves `fixed-above #98 ` and the next
    # line's hex commit, which the old whole-text regex would have joined into a claim
    # #2389 redesign (loosened, BR853-5 ruling): the old answer was a void body (F-1 missing); the new answer is F-1 accepted, with
    # no claim. GitHub shows `- F-1 The retry loop never backs off fixed-above #98` as plain text beside the `<b>` tag, and base
    # 66130a25 reads it the same way; the guard that voided it is retired. The cut runs to the item's end, so the next line is cut
    # with it and no claim is formed: F-1 is a plain acceptance, not a fixed-above one
    text = HEAD + "- %s fixed-above #98 <b> #99\n  `def5678`\n" % TITLE
    assert la.FIXED_ABOVE_RE.findall(text) == []
    # #2389 vet 856: was `f1_counted(text)` and `missing(text) == []`; the item holds an entry `<` (`<b>`), a cut, so it counts as nothing
    assert not f1_counted(text)
    assert missing(text) == GAP
    # the danger V852-2 named, a manufactured claim, stays absent
    assert la.fixed_above(read_ok(FINDING), text) == []
    assert [c for c in la.assigned_fixed_above(read_ok(FINDING), text) if c["id"] == "F-1"] == []


def test_g18_whole_text_claims_control_an_inline_comment_on_a_claim_line_keeps_its_acceptance():
    # #2389 catch-up 66130a25: the comment is empty (`<!---->`), which hides no text, so md_hidden reads the line VISIBLE and the claim stays
    text = HEAD + "- %s <!----> fixed-above #99 abcdef0\n" % TITLE
    assert la._cut_items(text)[1] is False
    assert la._accepting_items(text) != []
    assert missing(text) == []
    # #2389 catch-up 66130a25 (over-refusal, disclosed): with a `<!-- a note -->` comment GitHub shows the claim line, but md_hidden now
    # reads it UNSURE, the leftover check blanks it whole, and the line makes no item (was a void body)
    text = HEAD + "- %s <!-- a note --> fixed-above #99 abcdef0\n" % TITLE
    assert la._accepting_items(text) == []
    assert missing(text) == GAP


def test_g18_whole_text_claims_control_a_quoted_placeholder_keeps_the_acceptances():
    text = body("- F-1 The retry loop never backs off\n").replace(
        "A change.\n", "A change. Syntax: `fixed-above #<layer PR> <commit>`\n", 1)
    assert la._cut_items(text)[1] is False
    assert la._accepting_items(text) != []
    assert missing(text) == []


# --- #2389 vet 853 (segment-first redesign): G19 the cut to the item's end, G20 the stop point and literal fences, G21 the claim guards ---
# model-only (no render of these exact bodies). Vet receipt https://github.com/zwrose/superheroes/pull/2391#issuecomment-6717053345 (V853-1,
# BR853-1 to BR853-4). GFM block rules (https://github.github.com/gfm/): a list item's continuation lines (indented to its content column,
# or lazy paragraph continuation at column 0) belong to the item and to its paragraph, so GitHub shows "The retry loop XYZ never backs off";
# a fenced code block's content is literal (spec 4.5); an HTML comment on its own line is a block that ends a paragraph only where no
# lazy continuation applies. A cut that stopped at the line's end would join "The retry loop" and "never backs off" across the hidden XYZ.

@pytest.mark.parametrize("accepting, cut", [
    # #2389 vet 856: the item counts as nothing, so each expected cut below is "" (was the text before the cut, shown after each row)
    ("- F-1 The retry loop <span>XYZ</span>\n  never backs off\n", ""),  # was "F-1 The retry loop"
    ("- F-1 The retry loop <https://example.com>\n  never backs off\n", ""),  # was "F-1 The retry loop"
    ("- F-1 The retry loop \\<b>XYZ\n  never backs off\n", ""),  # was "F-1 The retry loop"
    ("- F-1 The retry loop `<b>` XYZ\n  never backs off\n", ""),  # was "F-1 The retry loop `"
    ("- F-1 The retry loop <span>XYZ</span>\nnever backs off\n", ""),  # was "F-1 The retry loop"
    ("F-1 The retry loop <em>really</em>\nnever backs off\n", ""),  # was "F-1 The retry loop"
], ids=["inline_tag", "autolink", "escaped_tag", "code_span_tag", "lazy_column_0", "paragraph"])
def test_g19_item_cut_a_cut_runs_to_the_items_end_so_it_cannot_join_the_words_around_it(accepting, cut):
    text = body(accepting)
    assert cuts(text) == [cut]  # the line after the cut is the item's, and the whole item counts as nothing
    assert missing(text) == GAP


@pytest.mark.parametrize("accepting", [
    "- F-1 The retry loop never backs off\n",
    "- F-1 The retry loop\n  never backs off\n",
    "- F-1 The retry loop\nnever backs off\n",
    "F-1 The retry loop\nnever backs off\n",
], ids=["one_line", "wrapped", "lazy_wrapped", "paragraph_wrapped"])
def test_g19_item_cut_controls_an_item_with_no_cut_still_accepts_across_its_lines(accepting):
    text = body(accepting)
    assert missing(text) == []
    assert cuts(text) == ["F-1 The retry loop never backs off"]


def test_g20_stop_a_hidden_line_inside_the_item_stops_it():
    # BR853-1: md_hidden does not read `  XYZ <!-- note -->` VISIBLE (its comment hides text), so it is blanked; it sits inside the item,
    # so it is a stop point, and "never backs off" is not joined to "The retry loop" across the hidden XYZ
    text = body("- F-1 The retry loop\n  XYZ <!-- note -->\n  never backs off\n")
    assert "XYZ" not in la._visible(text)
    assert cuts(text) == ["F-1 The retry loop"]
    assert missing(text) == GAP


def test_g20_stop_a_dropped_line_inside_the_item_stops_it():
    # BR853-2: the whole-line comment stops the item, so the two halves are not joined
    text = body("- F-1 The retry loop\n<!-- separator -->\nnever backs off\n")
    # #2389 catch-up 41e75711 (loosened, matches GFM: an HTML comment block interrupts the paragraph and the next line is its own shown block):
    # md_hidden now reads the `<!-- separator -->` line HIDDEN, so it is blanked (was kept, then dropped by the section reader); "never
    # backs off" is a block of its own, a second item. The split title still reads missing.
    assert "<!-- separator -->" not in la._visible(text)
    assert cuts(text) == ["F-1 The retry loop", "never backs off"]
    assert missing(text) == GAP


def test_g20_fenced_literal_a_fenced_line_is_kept_literally_and_never_dropped_as_a_comment():
    # BR853-3: inside the item's fence, `<!-- XYZ -->` is literal text (a code block shows it), not a comment to drop: the item is
    # cut there, so "never backs off" after the fence is not joined to "The retry loop"
    text = body("- F-1 The retry loop\n  ~~~\n  <!-- XYZ -->\n  ~~~\n  never backs off\n")
    assert cuts(text) == [""]  # #2389 vet 856: was ["F-1 The retry loop ~~~"]; the entry `<` on the fenced line makes the item count as nothing
    assert missing(text) == GAP


def test_g21_source_span_claims_a_claim_on_a_hidden_line_of_the_item_voids_the_body():
    # BR853-4: md_hidden does not read the claim line VISIBLE (its comment hides text), so it is blanked and, in the item's span, is a stop
    # point: the cut item loses the claim. The source span, read before blanking, still holds it, so the claim guards void the body
    text = body("- F-1 The retry loop never backs off\n  fixed-above #99 abcdef0 <!-- note -->\n")
    assert "fixed-above" not in la._visible(text)  # the precondition: the claim line is blanked
    # #2389 vet 856: the item as the cut reads it is unchanged (`raw_cuts`), but the per-item claim check now blanks it (was `cuts(text)` equal to
    # that text and `_cut_items(text)[1] is True`)
    assert raw_cuts(text) == ["F-1 The retry loop never backs off"]
    assert cuts(text) == [""]
    assert la.FIXED_ABOVE_RE.findall(" ".join(source_texts(text))) == [("99", "abcdef0")]
    assert la._cut_items(text)[1] is False
    assert la._accepting_items(text) == []
    assert missing(text) == GAP


# --- #2389 vet 856: G22 an item where a within-line cut fires counts as nothing, G23 claims are compared per item ---
# model-only (no render of these exact bodies). GitHub shows `f-1<span>-other</span>` as `f-1-other`, and a title word cut short by a
# tag as the whole word, so the words before an entry `<` must never read as whole.

BARE = {"id": "F-1", "outcome": "left-for-owner"}  # a finding with no title: checked by its id alone, so the prefix before a cut would satisfy it
SHORT = {"id": "F-1", "title": "The retry loop never back", "outcome": "left-for-owner"}  # a title the cut leaves whole
LOWER = {"id": "f-1", "title": "the retry loop never backs off", "outcome": "left-for-owner"}  # test_vet_slot_leftovers_2280's F1
G22_ID_GLUE = [
    "- f-1<span>-other</span> the retry loop never backs off",
    "- f-1\\<b>-other the retry loop never backs off",
    "- f-1`<b>`-other the retry loop never backs off",
    "- f-1<https://x>-other the retry loop never backs off",
]


@pytest.mark.parametrize("item", G22_ID_GLUE, ids=["inline_tag", "escaped_tag", "code_span_tag", "autolink"])
def test_g22_cut_item_counts_nothing_id_glue_forms_refuse(item):
    text = body(item + "\n")
    assert not any(cuts(text))  # the item reads nothing, never "f-1"
    assert la.missing(read_ok(LOWER), text) == [{"id": "f-1", "title": LOWER["title"]}]
    # a finding with no title is satisfied by the id alone, so only an item that reads nothing refuses it
    assert la.missing(read_ok(dict(BARE, id="f-1")), text) == [{"id": "f-1", "title": None}]


def test_g22_cut_item_counts_nothing_title_glue_tag_form_refuses():
    text = body("- F-1 The retry loop never back<span>wards</span> off\n")
    assert not any(cuts(text))
    assert missing(text) == GAP
    # a title the cut leaves whole ("never back") would be satisfied by the words before the tag, which GitHub shows as "backwards"
    assert la.missing(read_ok(SHORT), text) == [{"id": "F-1", "title": SHORT["title"]}]


G23_CLAIM_ITEM = "- Example syntax: fixed-<!---->above #99 abcdef0\n"  # the empty comment is dropped and joins a claim the source does not hold
G23_CUT_ITEM = "- f-1 the retry loop never backs off <b>fixed-above #99 abcdef0\n"  # the cut removes a claim the source holds
G23_HIDDEN_ITEM = ("- f-1 the retry loop never backs off\n"
                   "  fixed-above #99 abcdef0 <!-- note -->\n")  # md_hidden blanks the claim line: a stop point removes the claim


@pytest.mark.parametrize("items", [
    G23_CLAIM_ITEM + G23_CUT_ITEM,
    G23_CUT_ITEM + G23_CLAIM_ITEM,
], ids=["claim_item_first", "cut_item_first"])
def test_g23_per_item_claims_session_9_claim_cancel_bodies_refuse(items):
    text = body(items)
    assert la.missing(read_ok(LOWER), text) == [{"id": "f-1", "title": LOWER["title"]}]
    assert la.fixed_above(read_ok(LOWER), text) == []


@pytest.mark.parametrize("items", [
    G23_CLAIM_ITEM + G23_HIDDEN_ITEM,
    G23_HIDDEN_ITEM + G23_CLAIM_ITEM,
], ids=["claim_item_first", "hidden_item_first"])
def test_g23_per_item_claims_equal_claims_cancel_with_no_cut_in_the_item_refuse(items):
    # no entry `<` reaches the f-1 item (its claim sits on a hidden line, a stop point), so the per-item claim comparison alone refuses it:
    # summed over both items the whole claims balance (one joined by the comment, one lost to the hidden line)
    text = body(items)
    assert [t for t in raw_cuts(text) if "f-1" in t] == ["f-1 the retry loop never backs off"]
    assert sum(len(la.FIXED_ABOVE_RE.findall(t)) for t in raw_cuts(text)) == sum(
        len(la.FIXED_ABOVE_RE.findall(t)) for t in source_texts(text)) == 1
    assert not any("f-1" in t for t in cuts(text))
    assert la.missing(read_ok(LOWER), text) == [{"id": "f-1", "title": LOWER["title"]}]


@pytest.mark.parametrize("accepting", [
    "- F-1 The retry loop never backs off\n",
    "- F-1 The retry loop\n  never backs off\n",
    "- F-1 The retry loop\nnever backs off\n",
    "F-1 The retry loop\nnever backs off\n",
    "1. F-1 The retry loop never backs off\n",
    "- Another note\n  - F-1 The retry loop never backs off\n",
    "- Another note\n\n- F-1 The retry loop never backs off\n",
    "- F-1 The retry loop never backs off fixed-above #99 abcdef0\n",
    "- F-1 The retry loop never backs off `x`\n",
    "- F-1 The retry loop never backs off <!---->\n",
    "- F-1 The retry loop never backs off\n- Another note\n",
    "- F-1 The retry loop never backs off\n<!-- note -->\n- Another note\n",
], ids=["one_line", "wrapped", "lazy", "paragraph", "ordered", "nested", "loose", "claim", "code_span_no_lt", "empty_inline_comment",
        "two_items", "whole_comment_line_between_items"])
def test_healthy_item_controls_keep_counting(accepting):
    # #2389 vet 856: an item GitHub shows whole, with no entry `<` in it, still counts (the rule removes only items a cut touches)
    assert missing(body(accepting)) == []
