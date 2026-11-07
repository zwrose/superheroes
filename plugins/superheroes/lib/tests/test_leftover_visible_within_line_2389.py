"""#2389 V847-1, BR684-2, BR684-3 (fix leg of vet 847): ``leftover_accepting._visible`` never keeps text GitHub hides
within a line. It is the one place the leftover check that guards a READY write reads rendered text, and every cut only
removes text, so a miss fails toward a ``leftover-not-accepted`` refusal.

Oracle: ``fixtures/leftover_visible_github_renders_2389.json`` (GitHub's own render of 18 PR-body shapes, copied from the
advisor's renders). Guards (bite-proof record ``bite_proofs/i2389_leftover_visible_within_line.md``; select one with
``-k test_gN_``):
  G1 test_g1_escaped_opener_*     a backslash before an opener keeps both, then cuts the rest of the line
  G2 test_g2_code_span_opener_*   a code span holding an opener is kept, then the rest of the line is cut
  G3 test_g3_pi_declaration_*     an unescaped, unquoted ``<?``, ``<!X`` or ``<![`` cuts from the ``<``
  G4 test_g4_fenced_line_opener_* a line md_fence calls fenced is cut at its first opener
Rows with no GitHub render ("model-only") say so. No real gh: every call the vet-slot tests make is faked by
test_vet_slot_leftovers_2280's Fake."""
import json
import pathlib
import re
from html.parser import HTMLParser

import pytest

import leftover_accepting as la
import md_fence
from test_vet_slot_leftovers_2280 import (  # noqa: F401
    body, record_comment, read_ok, RECEIPT, write, _gh_on_path)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "leftover_visible_github_renders_2389.json"
ROWS = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
BY_ID = {row["id"]: row for row in ROWS}
F1_ROWS = [row for row in ROWS if row["id"].startswith("f1_")]
CLASS_ROWS = [row for row in ROWS if not row["id"].startswith("f1_")]

FINDING = {"id": "F-1", "title": "The retry loop never backs off", "outcome": "left-for-owner"}
GAP = [{"id": "F-1", "title": "The retry loop never backs off"}]


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


def check_f1_row(row):
    """``missing`` reports F-1 exactly when GitHub hides it."""
    gaps = missing(row["body"])
    if github_shows_f1(row):
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
    ("a \\<!-- tail\n", "a \\<!--\n"),
    ("a \\<? tail\n", "a \\<?\n"),
    ("a \\<!X tail\n", "a \\<!X\n"),
    ("a \\<![CDATA[ tail\n", "a \\<![\n"),
    ("a \\<!-- tail\nnext -->\nz\n", "a \\<!--\nnext -->\nz\n"),  # no comment state carried to the next line
    ("a \\<!-- tail", "a \\<!--"),  # a last line with no terminator
])
def test_g1_escaped_opener_keeps_the_backslash_and_opener_then_cuts_the_line(source, expected):
    out = la._visible(source)
    assert out == expected
    assert line_count(out) == line_count(source)


@pytest.mark.parametrize("source", ["a \\* b \\` c \\< d \\<b> e\n", "a \\<!- not an opener\n", "a \\<! also not\n"])
def test_g1_escaped_opener_an_escape_that_is_not_an_opener_changes_nothing(source):
    assert la._visible(source) == source


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
    assert missing(body("- F-1 The retry loop never backs off; the note shows \\<!-- here\n")) == []


# --- G2: a code span holding an opener --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["f1_details_codespan_closed", "f1_details_codespan_unclosed", "f1_div_codespan_unclosed"])
def test_g2_code_span_opener_github_hides_f1_so_the_check_reports_it_missing(name):
    assert not github_shows_f1(BY_ID[name])
    check_f1_row(BY_ID[name])


@pytest.mark.parametrize("source, expected", [
    # #2389 review (test-role s1): the span is kept only up to its opener, so text inside the span after the opener never counts
    ("a `<!--` tail\n", "a `\n"),
    ("a `<?` tail\n", "a `\n"),
    ("a `<!X` tail\n", "a `\n"),
    ("a `<![` tail\n", "a `\n"),
    ("a `see <?x` tail\n", "a `see \n"),  # the opener is anywhere in the span's content
    ("a ``<!-- ` -->`` tail\n", "a ``\n"),  # a double-backtick span
    ("a `<!--` tail\nnext -->\nz\n", "a `\nnext -->\nz\n"),  # no comment state carried to the next line
    ("a `<!--` tail", "a `"),  # a last line with no terminator
])
def test_g2_code_span_opener_keeps_the_span_then_cuts_the_line(source, expected):
    out = la._visible(source)
    assert out == expected
    assert line_count(out) == line_count(source)


@pytest.mark.parametrize("source", ["a `x` b `y z` c\n", "a ``x ` y`` b\n", "a `<b>` and `<` and `!` c\n", "a ` b\n"])
def test_g2_code_span_opener_a_span_without_an_opener_changes_nothing(source):
    assert la._visible(source) == source


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
    assert missing(body("- F-1 The retry loop never backs off; the note quotes `<!--` here\n")) == []


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
    kept = md_fence.split_lines(la._visible(row["body"]))
    for n, tokens in hidden.items():
        line = kept[n] if n < len(kept) else ""  # a last line cut to nothing leaves no line
        assert not tokens & set(line.split()), "line %d of %r kept %r" % (n, row["id"], tokens & set(line.split()))


@pytest.mark.parametrize("source, expected", [
    ("keep <? hide ?> x\n", "keep \n"),
    ("keep <!X hide>\n", "keep \n"),
    ("keep <![CDATA[ hide ]]>\n", "keep \n"),
    ("keep <!DOCTYPE hide>\n", "keep \n"),
    ("keep <?\n", "keep \n"),
    ("- list <?x hide", "- list "),  # a last line with no terminator
    ("a <b> c < d <3 e\n", "a <b> c < d <3 e\n"),  # a plain `<`, a tag and `<3` are not openers
    ("a <!- b <! c <!1 d\n", "a <!- b <! c <!1 d\n"),  # `<!` not followed by a letter, `-` once, or `[` is not an opener
])
def test_g3_pi_declaration_cuts_from_the_opener_and_keeps_what_is_not_one(source, expected):
    out = la._visible(source)
    assert out == expected
    assert line_count(out) == line_count(source)


def test_g3_pi_declaration_a_plain_comment_still_opens_the_multi_line_state():
    source = "keep\n<!-- a\nhidden\n-->\nafter <!-- b --> c\n"
    assert la._visible(source) == "keep\n\n\n\nafter  c\n"


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
    assert missing(body("- F-1 The retry loop never backs off <? a note ?>\n")) == []
    assert missing(body("- F-1 The retry loop never backs off <!X a note>\n")) == []


# --- G4: a line md_fence calls fenced ---------------------------------------------------------------------------

@pytest.mark.parametrize("source, expected", [
    # #2389 review (scoped-finder-003): a fenced line holding an opener is blanked whole, never shortened
    ("```\nkeep <!-- cut -->\n```\n", "```\n\n```\n"),
    ("```\nkeep <? cut ?>\n```\n", "```\n\n```\n"),
    ("~~~\nkeep <!X cut>\n~~~\n", "~~~\n\n~~~\n"),
    ("```\nkeep <![CDATA[ cut ]]>\n```\n", "```\n\n```\n"),
    ("```\n<!-- first --> and <? second ?>\n```\n", "```\n\n```\n"),
    ("```\nkeep <!-- cut\n```\nafter\n", "```\n\n```\nafter\n"),  # no comment state carried past the fence
    ("```\nkeep <!-- cut", "```\n"),  # a last fenced line with no terminator leaves nothing (the known exception)
])
def test_g4_fenced_line_opener_cuts_a_fenced_line_at_its_first_opener(source, expected):
    out = la._visible(source)
    assert out == expected
    if source.endswith("\n"):
        assert line_count(out) == line_count(source)


@pytest.mark.parametrize("source", [
    "```\n- F-1 The retry loop never backs off\n```\n",
    "~~~\nplain <b> text < 3 `x` \\* y\n~~~\n",
    "```\n\n```\n",
])
def test_g4_fenced_line_opener_a_fenced_line_holding_no_opener_is_kept_whole(source):
    assert la._visible(source) == source


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
    assert not (result["ok"] is False and result["reason"] == "leftover-not-accepted"), result


@pytest.mark.parametrize("source", [
    "", "\\", "\\<", "\\<!", "`", "`<!--", "``<?`", "<", "<!", "<?", "<![", "<!--", "\\<!--", "```\n<!--", "```\n<",
    "a\r\nb <? c\rd `<!--` e\n\u2028<?", "\x00<!X\x0b`<![`", "<!-- superheroes:x --> <?\n",
])
def test_edge_visible_on_a_str_never_raises_and_only_removes_text(source):
    out = la._visible(source)
    assert isinstance(out, str)
    assert len(out) <= len(source)  # text is only ever removed
    assert line_count(out) <= line_count(source)


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
    assert missing(body) == []


def test_g7_fence_delimiter_a_shortened_fenced_line_never_closes_the_fence():
    # scoped-finder-003: "``` <!-- note -->" inside a backtick fence is content; shortening it to "``` " would close the
    # fence and make the sample heading below it the live acceptance section
    body = ("## What we're accepting\n\nNone.\n\n## How to see it\n\n````\n```\n``` <!-- note -->\n"
            "## What we're accepting\n\n- F-1 The retry loop never backs off\n```\n````\n")
    out = la._visible(body)
    assert "``` \n" not in out
    assert missing(body), "the fenced sample acceptance must not count"


# --- Fix-audit round 2 (#2389): the two not-discharged audits ---------------------------------------------------------

def test_g7_fence_delimiter_an_opener_line_holding_an_opener_stays_an_opener():
    # audit of scoped-finder-003: blanking an opener line would unfence the sample below it; it is shortened instead
    body = ("## What we're accepting\n\nNone.\n\n## How to see it\n\n```md <!-- note -->\n"
            "## What we're accepting\n\n- F-1 The retry loop never backs off\n```\n")
    out = la._visible(body)
    assert "```md \n" in out
    assert missing(body), "the fenced sample acceptance must not count"


def test_g7_fence_delimiter_a_content_line_holding_an_opener_is_blanked_whole():
    assert la._visible("````\n``` <!-- note -->\n````\n") == "````\n\n````\n"


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
    # 4. removed by the inside-comment branch, not by a tail cut
    "- F-1 The retry loop never backs off; quoting `<?` and `<!--`\n  fixed-above #99 abcdef0\n",
    # 5. on an ATX subheading
    "### F-1 The retry loop never backs off; quoting `<!--`; fixed-above #99 abcdef0",
], ids=["single_line", "continuation_line", "wrapped", "inside_comment", "subheading"])
def test_g10_claim_removed_voids_the_body_so_every_leftover_reads_missing(accepting):
    text = ACCEPTING + accepting + HOW
    assert la._visible_claim(text)[1] is True
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
    assert la._visible_claim(text)[1] is False
    assert missing(text) == []
    assert [item for item in la._accepting_items(text) if "fixed-above #99 abcdef0" in item]


def test_g10_claim_removed_a_tail_without_a_claim_does_not_void_the_body():
    text = ACCEPTING + "- F-1 The retry loop never backs off; quoting `<!--`; more text" + HOW
    assert la._visible_claim(text)[1] is False
    assert missing(text) == []


def test_g10_claim_removed_the_text_and_the_flag_come_from_one_helper():
    source = "- F-1 x `<!--` fixed-above #99 abcdef0\n"
    text, removed = la._visible_claim(source)
    assert removed is True and text == la._visible(source) == "- F-1 x `\n"




# --- Review session 3 round 1 (#2389): the structural guard (G12), the per-line claim check (G13), the in-span cut (G2) ---

def test_g12_structure_a_fence_opener_swallowed_by_a_tail_comment_voids_the_body():
    # cr-s1-001: the quoted tail opener sets the comment state, which swallows the fence opener below it; the fenced sample
    # heading would then read as the live acceptance section, so a cut that changes a visible line's fence kind accepts nothing
    body = ("## What we're accepting\n\nNone.\n\nNote `<?` and `<!--`\n```\n## What we're accepting\n"
            "- F-1 The retry loop never backs off\n```\n")
    assert la._accepting_items(body) == []
    assert missing(body)


def test_g12_structure_a_cut_that_manufactures_a_fence_opener_voids_the_body():
    # seams-check: "```md <? ...`note" is text (a backtick in a backtick fence's info string); cutting at <? would make it a
    # fence opener that fences the How to see it heading into the acceptance section
    body = ("## What we're accepting\n\nNone.\n```md <?  `note\n## How to see it\n\n```\n"
            "- F-1 The retry loop never backs off\n```\n")
    assert la._accepting_items(body) == []
    assert missing(body)


def test_g12_structure_an_ordinary_inline_comment_cut_keeps_the_acceptances():
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off <!-- a note -->\n"
    assert missing(body) == []


def test_g13_claim_join_a_claim_joined_from_fragments_cannot_balance_a_removed_one():
    # cr-s1-002 / tr-s1-002: the comment cut joins "fixed-" and "above #99" into a new claim while the cut after `<?` removes
    # the real #98 claim; the counts balance, the per-line claim comparison does not
    body = ("## What we're accepting\n\n- F-1 The retry loop never backs off; fixed-<!-- note -->above #99 abcdef0; "
            "`<?` fixed-above #98 1234567\n")
    assert la._accepting_items(body) == []
    assert missing(body)


def test_g13_claim_join_an_inline_comment_on_a_claim_line_keeps_the_claim():
    body = "## What we're accepting\n\n- F-1 The retry loop never backs off <!-- a note --> fixed-above #99 abcdef0\n"
    assert la._accepting_items(body) != []


def test_g2_code_span_opener_text_inside_the_span_after_the_opener_never_counts():
    # tr-s1-001: inside a raw HTML line GitHub hides the comment inside the apparent code span
    body = "## What we're accepting\n\n<div>Quoting `<!-- F-1 The retry loop never backs off -->`\n</div>\n"
    assert "F-1" not in la._visible(body)
    assert missing(body)
