"""#2342 fix round: ``_comment_scan`` ignores a comment opener inside inline code or after a backslash escape.

``_comment_scan`` reports a line as starting inside an HTML comment exactly when the rendered Markdown would hide it
(the model of ``leftover_accepting._visible``). Its two callers share the scan: the no-build-record write path
(``_unrendered_slot``) and the emptied-description guard (``check_not_emptied``). Fake-runner units; no real gh, no
network. The fixtures come from test_vet_slot.py, test_vet_slot_leftovers_2280.py and
test_vet_slot_no_build_record_2342.py."""
import pytest

import vet_slot as vs
from test_vet_slot import BODY, RECEIPT, SLOT, VIEW, FakeGh, _comment, _pages
from test_vet_slot_leftovers_2280 import FIXED, record_comment
from test_vet_slot_no_build_record_2342 import BOT_BODY, READY_SLOT, RECEIPT_NONE
from test_vet_slot_emptied_2323 import BUILD_RECORD

PR = 42
REPO = "owner/example"
MARKER = "<!-- superheroes:advisor-vet -->"
CODE_SPAN_LINE = "Bumps parser; handles `<!--` literally.\n"
NOTE_LINE = "Release notes quote `<!--` verbatim.\n"


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _fake(body, receipt=RECEIPT_NONE, extra=()):
    comments = ([_comment(receipt)] if receipt is not None else []) + list(extra)
    return FakeGh([body], _pages(comments))


def _write(fake, tmp_path, slot=SLOT):
    path = tmp_path / "slot.md"
    path.write_text(slot, encoding="utf-8")
    return vs.run_verb("write", PR, REPO, slot_file=str(path), run=fake)


def _appended(body, slot):
    """The marker-absent formula."""
    return body.rstrip("\r\n") + "\n\n## Advisor vet\n" + MARKER + "\n\n" + slot.strip("\n") + "\n"


def _replaced(body, slot):
    """The marker-present formula: the slot runs from the line after the marker to the end."""
    a = body.index("\n", body.index(MARKER)) + 1
    return body[:a] + "\n" + slot.strip("\n") + "\n"


def _builder_new_body(body, slot=SLOT):
    """A builder body keeps its build record: the slot replaces the span between the marker and the record."""
    a = body.index(MARKER + "\n") + len(MARKER + "\n")
    b = body.index("<!-- superheroes:build-record -->")
    return body[:a] + "\n" + slot.strip("\n") + "\n\n" + body[b:]


def _refused(result, fake, reason, detail=None):
    assert result["ok"] is False, result
    assert result["reason"] == reason, result
    if detail is not None:
        assert detail in result["detail"], result
    assert fake.edit_calls() == []


# --- C1: a bot description quoting the opener in inline code writes ------------------------------------------------

def test_c1_run_verb_writes_a_bot_body_that_quotes_the_opener_in_inline_code(tmp_path):
    body = CODE_SPAN_LINE
    fake = _fake(body, extra=[record_comment([FIXED])])
    result = _write(fake, tmp_path, READY_SLOT)
    assert result == {"ok": True, "verb": "write", "followups": [], "receipt": "https://x/c/1"}
    assert len(fake.edit_calls()) == 1
    assert fake.edited == [body.rstrip("\r\n") + "\n\n## Advisor vet\n<!-- superheroes:advisor-vet -->\n\n"
                           + READY_SLOT.strip("\n") + "\n"]


def test_c1_evaluate_composes_the_same_body():
    result = vs.evaluate("write", CODE_SPAN_LINE, [_comment(RECEIPT_NONE), record_comment([FIXED])], READY_SLOT,
                         advisor_login="advisor")
    assert result["ok"] is True, result
    assert result["newBody"] == _appended(CODE_SPAN_LINE, READY_SLOT)


# --- C2: a builder description quoting the opener above its heading is not body-emptied ----------------------------

def test_c2_run_verb_refuses_body_emptied_for_an_inline_code_opener_above_the_heading(tmp_path):
    # vet 816: BODY carries the <details><summary>Build record line, which could open an HTML block, so the exemption
    # is off and the quoted opener opens a comment over the owner half: body-emptied, as on main
    body = NOTE_LINE + BODY
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")


def test_c2_evaluate_refuses_body_emptied():
    # vet 816: the body has a line that could open an HTML block, so the exemption is off, as on main
    body = NOTE_LINE + BODY
    result = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied", result


# --- C3: a double-backtick span closes on a double-backtick run ----------------------------------------------------

def test_c3_a_double_backtick_span_holding_the_opener_writes(tmp_path):
    body = BOT_BODY + "Handles ``a `<!-- b`` literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- C4: a backtick run with no closing run is literal, then a real opener opens a comment -------------------------

def test_c4_an_unclosed_backtick_run_then_a_real_opener_still_refuses_write_failed(tmp_path):
    body = BOT_BODY + "a ` b <!-- hidden\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "HTML comment")


# --- C5: a backslash escape --------------------------------------------------------------------------------------------

def test_c5_an_escaped_opener_writes(tmp_path):
    body = BOT_BODY + "Handles \\<!-- literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c5_an_escaped_backtick_leaves_the_opener_real_and_still_refuses(tmp_path):
    body = BOT_BODY + "\\` <!-- hidden\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "HTML comment")


# --- C6: a real comment opened on a plain line hides the slot ---------------------------------------------------------

C6_HIDING = "Bumps x.\n<!-- note\nmore text\n" + MARKER + "\n\nold slot\n"
C6_CLOSED = "Bumps x.\n<!-- note\nmore text\n-->\n" + MARKER + "\n\nold slot\n"


def test_c6_a_real_comment_closed_on_the_marker_line_still_refuses_write_failed(tmp_path):
    fake = _fake(C6_HIDING)
    _refused(_write(fake, tmp_path), fake, "write-failed", "HTML comment")


def test_c6_a_plain_closer_line_before_the_marker_lets_the_write_succeed(tmp_path):
    fake = _fake(C6_CLOSED)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_replaced(C6_CLOSED, SLOT)]


# --- C7: a real comment hides the owner half ------------------------------------------------------------------------------

C7_BODY = ("<!-- draft\n## What's changing, and why\n-->\n\n## Advisor vet\n" + MARKER + "\n\n" + BUILD_RECORD)


def test_c7_a_real_comment_hiding_the_owner_half_still_refuses_body_emptied(tmp_path):
    fake = _fake(C7_BODY, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied", "What's changing, and why")
    result = vs.evaluate("write", C7_BODY, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied", result


# --- C8: inside a real comment a backtick-quoted closer still closes it ----------------------------------------------

def test_c8_a_backtick_quoted_closer_inside_a_comment_closes_it_so_the_heading_is_live(tmp_path):
    body = "<!-- a `-->` b\n" + BODY
    fake = _fake(body, receipt=RECEIPT)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_builder_new_body(body)]
    evaluated = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert evaluated["ok"] is True, evaluated
    assert evaluated["newBody"] == _builder_new_body(body)


# --- C9: a fenced line holding the opener opens no comment ------------------------------------------------------------------

def test_c9_a_fenced_line_holding_the_opener_opens_no_comment(tmp_path):
    body = BOT_BODY + "\n```\n<!-- in a fence\n```\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- the scan itself: the yield shape is unchanged -----------------------------------------------------------------------------

@pytest.mark.parametrize("body, expected", [
    ("a `<!--` b\nnext\n", [False, False]),
    ("a ``x `<!-- y`` z\nnext\n", [False, False]),
    ("a ` b <!-- c\nnext\n", [False, True]),
    ("\\<!-- c\nnext\n", [False, False]),
    ("\\` <!-- c\nnext\n", [False, True]),
    ("<!-- a `-->` b\nnext\n", [False, False]),
    ("a --> `<!--`\nnext\n", [False, False]),
], ids=["span", "double-span", "unclosed-run", "escaped-opener", "escaped-tick", "quoted-closer", "stray-closer"])
def test_comment_scan_starts_in_comment_per_line(body, expected):
    rows = list(vs._comment_scan(body))
    assert [row[3] for row in rows] == expected
    assert all(len(row) == 4 for row in rows)


# --- C11: raw HTML is not Markdown: no escape or code span is read inside it (review finding, scoped finder) ---------

RAW_DIV_OPENER = "<div>\n`<!--`\n\n"


def test_c11_the_findings_example_a_div_then_a_quoted_opener_hides_the_owner_half_body_emptied(tmp_path):
    # the comment opened inside the raw <div> block hides the owner half until the advisor-vet marker closes it
    body = RAW_DIV_OPENER + BODY
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    assert vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")["reason"] == "body-emptied"


def test_c11_a_bot_body_with_a_quoted_opener_inside_a_raw_div_refuses_write_failed(tmp_path):
    body = "Bumps x.\n\n<div>\n`<!--` release notes\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c11_a_blank_line_after_the_raw_block_still_refuses_write_failed_for_a_later_quoted_opener(tmp_path):
    # vet 816: the body has a line that could open an HTML block, so the exemption is off (as on main): write-failed
    body = "Bumps x.\n\n<div>\nsee notes\n</div>\n\n" + CODE_SPAN_LINE
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c11_a_raw_block_under_a_blockquote_is_raw_too(tmp_path):
    body = "Bumps x.\n\n> <details>\n> `<!--` notes\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c11_a_comment_line_does_not_make_the_next_line_raw(tmp_path):
    # a line opening with <!-- is left to the comment state: once it closes, the next line's code span is text
    body = "<!-- dependabot note -->\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


@pytest.mark.parametrize("body, expected", [
    ("<div>\n`<!--`\nnext\n", [False, False, True]),
    # vet 816: the body has a line that could open an HTML block, so the exemption is off (as on main)
    ("<div>\n\n`<!--`\nnext\n", [False, False, False, True]),
    ("> <details>\n> \\<!-- x\nnext\n", [False, False, True]),
    ("<!-- a -->\n`<!--`\nnext\n", [False, False, False]),
], ids=["div-run", "blank-ends-run", "quoted-container-escape", "comment-line-not-raw"])
def test_c11_comment_scan_reads_raw_html_runs(body, expected):
    assert [row[3] for row in vs._comment_scan(body)] == expected


# --- C12: the raw-HTML run starts only at a real tag in live Markdown, and ends at a blank line in its container ----

def test_c12_an_autolink_line_is_not_raw_html_so_a_later_quoted_opener_is_text(tmp_path):
    body = "<https://example.com>\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c12_a_tag_inside_a_comment_still_refuses_write_failed_for_the_quoted_opener(tmp_path):
    # vet 816: the gate reads every line, a tag line inside a comment included: the body has a line that could open an
    # HTML block, so the exemption is off (as on main) and the quoted opener opens a comment
    body = "<!-- note\n<div>\n-->\n" + CODE_SPAN_LINE
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c12_a_quoted_blank_line_raw_run_body_refuses_write_failed(tmp_path):
    # vet 816: the body has a line that could open an HTML block, so the exemption is off (as on main): write-failed
    body = "> <div>\n> </div>\n>\n> Handles `<!--` literally.\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


@pytest.mark.parametrize("body, expected", [
    ("<https://example.com>\n`<!--`\nnext\n", [False, False, False]),
    ("<div class=\"x\">\n`<!--`\nnext\n", [False, False, True]),
    ("<br/>\n`<!--`\nnext\n", [False, False, True]),
    ("</details>\n`<!--`\nnext\n", [False, False, True]),
    # vet 816 (rows tag-in-comment and quoted-blank): the body has a line that could open an HTML block, so the
    # exemption is off (as on main) and the quoted opener opens a comment
    ("<!-- c\n<div>\n-->\n`<!--`\nnext\n", [False, True, True, False, True]),
    ("> <div>\n>\n> `<!--`\nnext\n", [False, False, False, True]),
], ids=["autolink", "tag-with-attribute", "self-closing", "closing-tag", "tag-in-comment", "quoted-blank"])
def test_c12_comment_scan_raw_run_boundaries(body, expected):
    assert [row[3] for row in vs._comment_scan(body)] == expected


# --- C13: a raw run ends only at a line blank inside the blockquote depth it started in ------------------------------

def test_c13_a_literal_gt_line_inside_an_unquoted_div_keeps_the_owner_half_hidden_body_emptied(tmp_path):
    # the finding's example: ">" is raw HTML content at depth 0, so the following opener is a real comment
    body = "<div>\n>\n`<!--`\n\n" + BODY
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    assert vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")["reason"] == "body-emptied"


def test_c13_a_literal_gt_line_inside_an_unquoted_div_still_refuses_a_bot_write(tmp_path):
    body = "Bumps x.\n\n<div>\n>\n`<!--` notes\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


@pytest.mark.parametrize("body, expected", [
    ("<div>\n>\n`<!--`\nnext\n", [False, False, False, True]),
    ("<div>\n> <p>\n>\n`<!--`\nnext\n", [False, False, False, False, True]),
    ("> <div>\n> >\n> `<!--`\nnext\n", [False, False, False, True]),
    # vet 816 (row quoted-blank-ends): the body has a line that could open an HTML block, so the exemption is off
    ("> <div>\n>\n> `<!--`\nnext\n", [False, False, False, True]),
], ids=["gt-in-unquoted-div", "nested-tag-keeps-depth", "deeper-gt-in-quoted-div", "quoted-blank-ends"])
def test_c13_comment_scan_raw_run_depth(body, expected):
    assert [row[3] for row in vs._comment_scan(body)] == expected


# --- C14: a blank line is ASCII spaces and tabs only; a run's quote depth counts list markers and extra spaces -------

NBSP = chr(0xA0)  # built at runtime: str.strip() strips it, a Markdown blank line does not


def test_c14_a_non_breaking_space_line_does_not_end_a_raw_run_body_emptied(tmp_path):
    # the NBSP line is raw HTML text, so the opener after it is a real comment hiding the owner half
    body = "<div>\n" + NBSP + "\n`<!--`\n\n" + BODY
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")


def test_c14_evaluate_also_refuses_body_emptied_for_a_non_breaking_space_line_in_a_raw_run():
    body = "<div>\n" + NBSP + "\n`<!--`\n\n" + BODY
    assert vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")["reason"] == "body-emptied"


def test_c14_a_list_item_quoted_raw_run_body_refuses_write_failed(tmp_path):
    # vet 816: the body has a line that could open an HTML block, so the exemption is off (as on main): write-failed
    body = "Bumps x.\n\n- > <div>\n  > </div>\n  >\n  > Handles `<!--` literally.\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c14_a_double_spaced_quote_prefix_body_refuses_write_failed(tmp_path):
    # vet 816: the body has a line that could open an HTML block, so the exemption is off (as on main): write-failed
    body = "Bumps x.\n\n>  > <div>\n>  > </div>\n>  >\n>  > Handles `<!--` literally.\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c14_a_line_of_ascii_spaces_and_tabs_in_an_html_block_body_leaves_the_quoted_opener_a_comment():
    # vet 816: the body has a line that could open an HTML block, so the exemption is off (as on main)
    assert [row[3] for row in vs._comment_scan("<div>\n \t \n`<!--`\nnext\n")] == [False, False, False, True]


@pytest.mark.parametrize("body, expected", [
    ("<div>\n" + NBSP + "\n`<!--`\nnext\n", [False, False, False, True]),
    # vet 816 (the three rows below): the body has a line that could open an HTML block, so the exemption is off
    ("- > <div>\n  > </div>\n  >\n  > `<!--`\nnext\n", [False, False, False, False, True]),
    (">  > <div>\n>  > </div>\n>  >\n>  > `<!--`\nnext\n", [False, False, False, False, True]),
    ("- > <div>\n- >\n- > `<!--`\nnext\n", [False, False, False, True]),
], ids=["nbsp-is-not-blank", "list-marker-quote-depth", "double-space-quote-depth", "list-marker-quoted-blank"])
def test_c14_comment_scan_raw_run_blankness_and_depth(body, expected):
    assert [row[3] for row in vs._comment_scan(body)] == expected


# --- C15: vet 816: a body with a line that could open an HTML block gets no exemption (the body-level gate) ----------
# A line scanner cannot track CommonMark's HTML blocks (a tag line ending in U+2028, U+0085 or a form feed; a
# declaration, CDATA or processing-instruction block), so the scan does not try: in a body with such a line, every
# <!-- outside a fence opens a comment, as on main.

# A tag line ending in a character that splitlines() breaks on but CommonMark does not, then a real newline: the line
# scanner saw a blank line and ended the HTML block; the renderer sees one tag line that carries on.
LINE_BREAK_OPENERS = [("u2028", "<div>  \n"), ("u0085", "<div> \u0085\n"), ("formfeed", "<div> \x0c\n")]
BLOCK_OPENERS = [("doctype", "<!DOCTYPE html>\n"), ("cdata", "<![CDATA[ x ]]>\n"), ("pi", "<?xml x?>\n")]
ALL_OPENERS = LINE_BREAK_OPENERS + BLOCK_OPENERS


@pytest.mark.parametrize("opener", [o for _, o in ALL_OPENERS], ids=[i for i, _ in ALL_OPENERS])
def test_c15_a_builder_body_with_an_html_block_opener_then_a_quoted_opener_refuses_body_emptied(tmp_path, opener):
    # V1/V2: the quoted opener opens a real comment that hides the owner half until the advisor-vet marker
    body = opener + "`<!--`\n\n" + BODY
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    result = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied", result


@pytest.mark.parametrize("opener", [o for _, o in ALL_OPENERS], ids=[i for i, _ in ALL_OPENERS])
def test_c15_a_bot_body_with_an_html_block_opener_then_a_quoted_opener_refuses_write_failed(tmp_path, opener):
    # V3
    body = "Bumps x.\n\n" + opener + "`<!--` notes\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c15_a_comment_closing_mid_line_then_a_quoted_opener_refuses_write_failed(tmp_path):
    # V5: the rest of a line on which a comment closes is matched plainly, even in an exempt body
    body = "<!-- a --> `<!--` b\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


@pytest.mark.parametrize("lead", ["﻿", "​"], ids=["bom", "zwsp"])
def test_c15_a_format_character_before_a_tag_still_gates_the_body(tmp_path, lead):
    # V6: a byte-order mark or a zero-width space before the tag is skipped, so the line still counts
    body = lead + "<div>\n`<!--` x\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c15_the_exemption_survives_in_a_body_without_such_a_line_after_a_closing_comment_line(tmp_path):
    # the tail rule reaches only the rest of the closing line: the next line's code span is text
    body = "<!-- a --> x\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


@pytest.mark.parametrize("body, expected", [
    ("<div>  \n`<!--`\nnext\n", [False, False, False, True]),
    ("<div> \u0085\n`<!--`\nnext\n", [False, False, False, True]),
    ("<div> \x0c\n`<!--`\nnext\n", [False, False, False, True]),
    ("<div>  `<!--`\nnext\n", [False, False, True]),
    ("<!DOCTYPE html>\n`<!--`\nnext\n", [False, False, True]),
    ("<![CDATA[ x ]]>\n`<!--`\nnext\n", [False, False, True]),
    ("<?xml x?>\n`<!--`\nnext\n", [False, False, True]),
    ("﻿<div>\n`<!--`\nnext\n", [False, False, True]),
    ("​<div>\n`<!--`\nnext\n", [False, False, True]),
    ("<!-- a --> `<!--` b\nnext\n", [False, True]),
    ("<!-- a --> x\n`<!--`\nnext\n", [False, False, False]),
    ("<https://example.com>\n`<!--`\nnext\n", [False, False, False]),
], ids=["u2028", "u0085", "formfeed", "u2028-inline", "doctype", "cdata", "pi", "bom", "zwsp", "comment-tail",
        "comment-tail-exempt", "autolink"])
def test_c15_comment_scan_gate_rows(body, expected):
    assert [row[3] for row in vs._comment_scan(body)] == expected


@pytest.mark.parametrize("body, expected", [
    ("plain text `<!--` here\n", False),
    ("<div>\n", True),
    ("x\n> - 1. <p>\n", True),
    ("</details>\n", True),
    ("<br/>\n", True),
    ("<?php x\n", True),
    ("<!DOCTYPE html>\n", True),
    ("<!-- a comment -->\n", False),
    ("  > <!-- a comment\n", False),
    ("<https://example.com>\n", False),
    ("- <mailto:a@b.c>\n", False),
    ("a < b and <3\n", False),
    ("x <div> mid-line\n", False),
    (" <div>\n", True),
    ("﻿<div>\n", True),
    ("​<div>\n", True),
    ("x <div>\n", True),
], ids=["plain", "div", "marks", "closing", "self-closing", "pi", "doctype", "comment", "quoted-comment", "autolink",
        "mailto-autolink", "lt-signs", "mid-line-tag", "nbsp", "bom", "zwsp", "after-u2028"])
def test_c15_could_open_html_block(body, expected):
    assert vs._could_open_html_block(body) is expected


# --- J: review session 7 (test-s4-001): a splitlines-only line break turns the exemption off --------------------------
# After a comment closes, the rest of its line is matched plainly, but that state resets at every str.splitlines()
# boundary. U+2028, U+0085, a form feed and the other splitlines-only separators are not Markdown line endings, so a
# quoted opener after one stays on the comment's closing line, where a browser opens a comment over the owner heading.
# The body has no HTML-block line, so only the splitlines-only clause at the gate can switch the exemption off.

J_NOT_READY_SLOT = "**Verdict: NOT-READY** · " + "a" * 40 + "\n\nNew owner half.\n"
# the eight characters str.splitlines() breaks on and Markdown does not, written as escapes
J_SEPARATORS = [("u2028", "\N{LINE SEPARATOR}"), ("u2029", "\N{PARAGRAPH SEPARATOR}"), ("nel", "\x85"), ("vt", "\x0b"), ("ff", "\x0c"),
                ("fs", "\x1c"), ("gs", "\x1d"), ("rs", "\x1e")]
J_SEEN = ("u2028", "nel", "ff")  # the three the seat reproduced


def _j_body(sep):
    return ("<!-- done --> " + sep + "`<!--` note\n## What's changing, and why\n\nOwner-facing scope.\n\n"
            "## Advisor vet\n<!-- superheroes:advisor-vet -->\n**Verdict: NOT-READY** · old\n\nold slot\n\n"
            "<!-- superheroes:build-record -->\n"
            "<!-- superheroes:followups none -->\n")


def _j_evaluate(body):
    return vs.evaluate("write", body, [_comment(RECEIPT_NONE)], J_NOT_READY_SLOT, advisor_login="advisor")


@pytest.mark.parametrize("entry", ["evaluate", "run_verb"])
@pytest.mark.parametrize("sep", [s for i, s in J_SEPARATORS if i in J_SEEN], ids=[i for i, _ in J_SEPARATORS if i in J_SEEN])
def test_j1_a_quoted_opener_after_a_splitlines_only_break_refuses_body_emptied(tmp_path, sep, entry):
    # J1: the seat's break-it shapes, a NOT-READY slot and a receipt with dispositions none; nothing is pushed
    body = _j_body(sep)
    if entry == "evaluate":
        result = _j_evaluate(body)
        assert result["ok"] is False and result["reason"] == "body-emptied", result
    else:
        fake = _fake(body)
        _refused(_write(fake, tmp_path, J_NOT_READY_SLOT), fake, "body-emptied")


@pytest.mark.parametrize("entry", ["evaluate", "run_verb"])
def test_j2_the_lf_control_still_writes(tmp_path, entry):
    # J2: with a real newline the quoted opener sits on its own line, where the exemption reads it as inline code
    body = _j_body("\n")
    if entry == "evaluate":
        result = _j_evaluate(body)
        assert result["ok"] is True, result
        assert "New owner half." in result["newBody"]
    else:
        fake = _fake(body)
        result = _write(fake, tmp_path, J_NOT_READY_SLOT)
        assert result["ok"] is True, result
        assert len(fake.edit_calls()) == 1


@pytest.mark.parametrize("sep", [s for _, s in J_SEPARATORS], ids=[i for i, _ in J_SEPARATORS])
def test_j3_each_of_the_eight_splitlines_only_breaks_turns_the_exemption_off(sep):
    # J3: dropping any one character from _SPLITLINES_ONLY_BREAKS turns its own case red
    result = _j_evaluate(_j_body(sep))
    assert result["ok"] is False and result["reason"] == "body-emptied", result


def test_j3_the_eight_characters_are_all_splitlines_breaks_and_none_is_a_markdown_line_ending():
    # the constant's premise, read off the language: each one splits a line, none is CR or LF
    for _, sep in J_SEPARATORS:
        assert len(("a" + sep + "b").splitlines()) == 2
        assert sep not in "\r\n"
    assert len(J_SEPARATORS) == 8


def test_j4_a_body_without_a_splitlines_only_break_keeps_the_exemption():
    # J4: an inline-code opener, no HTML-block line, no splitlines-only break: the exemption stays on
    assert [row[3] for row in vs._comment_scan("a `<!--` b\nnext\n")] == [False, False]
    assert [row[3] for row in vs._comment_scan("a \N{LINE SEPARATOR} `<!--` b\nnext\n")] == [False, False, True]
