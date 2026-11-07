"""#2342 fix round: a comment opener inside inline code or after a backslash escape hides nothing.

Since #2389 the verdict is ``md_hidden.scan``'s (a CommonMark parse of the body; ``_comment_scan``,
``_could_open_html_block`` and ``_SPLITLINES_ONLY_BREAKS`` are gone, so the tests that called them are gone too). The
behaviour tests below stay, through ``_run_verb`` and ``evaluate``: the no-build-record write path
(``_unrendered_slot``) and the emptied-description guard (``check_not_emptied``) both read ``md_hidden``. Where a
body's outcome differs from the old line scanner's, the test says so with a ``# #2389:`` comment. Fake-runner units; no
real gh, no network. The fixtures come from test_vet_slot.py, test_vet_slot_leftovers_2280.py and
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

def test_c2_run_verb_writes_for_an_inline_code_opener_above_the_heading(tmp_path):
    # #2389: GitHub renders this heading visible (md_hidden: visible): the opener is inline code, the build record's
    # <details> line no longer switches a whole-body exemption off. It was body-emptied before.
    body = NOTE_LINE + BODY
    fake = _fake(body, receipt=RECEIPT)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_builder_new_body(body)]


def test_c2_evaluate_writes_for_an_inline_code_opener_above_the_heading():
    # #2389: GitHub renders this heading visible (md_hidden: visible); it was body-emptied before
    body = NOTE_LINE + BODY
    result = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is True, result
    assert result["newBody"] == _builder_new_body(body)


# --- C3: a double-backtick span closes on a double-backtick run ----------------------------------------------------

def test_c3_a_double_backtick_span_holding_the_opener_writes(tmp_path):
    body = BOT_BODY + "Handles ``a `<!-- b`` literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- C4: a backtick run with no closing run is literal, then a real opener opens a comment -------------------------

def test_c4_an_unclosed_backtick_run_then_an_unclosed_opener_writes(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): an inline <!-- with no --> in its paragraph is literal
    # text, not a comment. It was write-failed before.
    body = BOT_BODY + "a ` b <!-- hidden\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- C5: a backslash escape --------------------------------------------------------------------------------------------

def test_c5_an_escaped_opener_writes(tmp_path):
    body = BOT_BODY + "Handles \\<!-- literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c5_an_escaped_backtick_then_an_unclosed_opener_writes(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): an inline <!-- with no --> in its paragraph is literal
    # text, not a comment. It was write-failed before.
    body = BOT_BODY + "\\` <!-- hidden\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- C6: a real comment opened on a plain line hides the slot ---------------------------------------------------------

C6_HIDING = "Bumps x.\n<!-- note\nmore text\n" + MARKER + "\n\nold slot\n"
C6_CLOSED = "Bumps x.\n<!-- note\nmore text\n-->\n" + MARKER + "\n\nold slot\n"


def test_c6_a_real_comment_closed_on_the_marker_line_still_refuses_write_failed(tmp_path):
    fake = _fake(C6_HIDING)
    # #2389: still a refusal; the detail is now md_hidden's sentence (the marker line reads hidden), not "HTML comment"
    _refused(_write(fake, tmp_path), fake, "write-failed", "marker line reads hidden")


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


def test_c11_a_blank_line_after_the_raw_block_ends_it_so_a_later_quoted_opener_is_text(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): the blank line ends the <div> block, so the code span
    # after it is Markdown. It was write-failed before.
    body = "Bumps x.\n\n<div>\nsee notes\n</div>\n\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


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


# --- C12: the raw-HTML run starts only at a real tag in live Markdown, and ends at a blank line in its container ----

def test_c12_an_autolink_line_is_not_raw_html_so_a_later_quoted_opener_is_text(tmp_path):
    body = "<https://example.com>\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c12_a_tag_inside_a_closed_comment_does_not_hide_a_later_quoted_opener(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): the comment closes on its --> line and the code span
    # after it is Markdown. It was write-failed before.
    body = "<!-- note\n<div>\n-->\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c12_a_quoted_blank_line_ends_the_raw_run_so_the_quoted_opener_is_text(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): the blank quoted line ends the <div> block inside the
    # quote. It was write-failed before.
    body = "> <div>\n> </div>\n>\n> Handles `<!--` literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


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


def test_c14_a_list_item_quoted_raw_run_ends_at_its_blank_line_and_writes(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): the blank quoted line ends the <div> block in the list
    # item's quote. It was write-failed before.
    body = "Bumps x.\n\n- > <div>\n  > </div>\n  >\n  > Handles `<!--` literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c14_a_double_spaced_quote_prefix_raw_run_ends_at_its_blank_line_and_writes(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible), as above with a nested quote. It was write-failed before.
    body = "Bumps x.\n\n>  > <div>\n>  > </div>\n>  >\n>  > Handles `<!--` literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- C15: HTML-block openers (a tag line ending in U+2028, U+0085 or a form feed; a declaration, CDATA or processing-
# instruction block). Since #2389 md_hidden parses them: a tag line that carries on past a splitlines-only break keeps
# its block open (the quoted opener after it is a real comment); a one-line declaration, CDATA or PI block closes on its line.

# A tag line ending in a character that splitlines() breaks on but CommonMark does not, then a real newline: the renderer
# sees one tag line that carries on, so the HTML block stays open.
LINE_BREAK_OPENERS = [("u2028", "<div>  \n"), ("u0085", "<div> \u0085\n"), ("formfeed", "<div> \x0c\n")]
BLOCK_OPENERS = [("doctype", "<!DOCTYPE html>\n"), ("cdata", "<![CDATA[ x ]]>\n"), ("pi", "<?xml x?>\n")]


@pytest.mark.parametrize("opener", [o for _, o in LINE_BREAK_OPENERS], ids=[i for i, _ in LINE_BREAK_OPENERS])
def test_c15_a_builder_body_with_an_html_block_opener_then_a_quoted_opener_refuses_body_emptied(tmp_path, opener):
    # V1/V2: the quoted opener opens a real comment that hides the owner half until the advisor-vet marker
    body = opener + "`<!--`\n\n" + BODY
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    result = vs.evaluate("write", body, [_comment(RECEIPT)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied", result


@pytest.mark.parametrize("opener", [o for _, o in LINE_BREAK_OPENERS], ids=[i for i, _ in LINE_BREAK_OPENERS])
def test_c15_a_bot_body_with_an_html_block_opener_then_a_quoted_opener_refuses_write_failed(tmp_path, opener):
    # V3
    body = "Bumps x.\n\n" + opener + "`<!--` notes\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


@pytest.mark.parametrize("opener", [o for _, o in BLOCK_OPENERS], ids=[i for i, _ in BLOCK_OPENERS])
def test_c15_a_one_line_declaration_cdata_or_pi_block_ends_on_its_line_so_the_quoted_opener_is_text(tmp_path, opener):
    # #2389: GitHub renders these visible (md_hidden: visible): a declaration, CDATA or processing-instruction HTML block
    # ends on the line that closes it, so the code span after it is Markdown. Builder and bot, both write; both were
    # refused (body-emptied, write-failed) before.
    body = opener + "`<!--`\n\n" + BODY
    fake = _fake(body, receipt=RECEIPT)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_builder_new_body(body)]
    bot = "Bumps x.\n\n" + opener + "`<!--` notes\n"
    fake = _fake(bot)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(bot, SLOT)]


def test_c15_a_comment_closing_mid_line_then_a_quoted_opener_refuses_write_failed(tmp_path):
    # V5: the rest of a line on which a comment closes is matched plainly, even in an exempt body
    body = "<!-- a --> `<!--` b\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c15_a_byte_order_mark_before_a_tag_still_refuses(tmp_path):
    # V6: unchanged under md_hidden (the write still refuses; no #2389 expectation change)
    body = "﻿<div>\n`<!--` x\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_c15_a_zero_width_space_before_a_tag_is_text_and_writes(tmp_path):
    # #2389: GitHub renders this visible (md_hidden: visible): a zero-width space is not whitespace to CommonMark, so
    # the line is a paragraph with an inline tag and the code span after it is Markdown. It was write-failed before.
    body = "​<div>\n`<!--` x\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c15_the_exemption_survives_in_a_body_without_such_a_line_after_a_closing_comment_line(tmp_path):
    # the tail rule reaches only the rest of the closing line: the next line's code span is text
    body = "<!-- a --> x\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


# --- J: review session 7 (test-s4-001): a splitlines-only line break is no Markdown line end ----------------------------
# After a comment closes, the rest of its line is raw HTML. U+2028, U+0085, a form feed and the other splitlines-only
# separators are not Markdown line endings (md_fence.split_lines), so a quoted opener after one stays on the comment's
# closing line, where GitHub opens a comment over the owner heading. md_hidden reads the lines Markdown does.

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
    # J3: Markdown does not break a line on any of the eight, so the quoted opener stays inside the comment's line
    result = _j_evaluate(_j_body(sep))
    assert result["ok"] is False and result["reason"] == "body-emptied", result


def test_j3_the_eight_characters_are_all_splitlines_breaks_and_none_is_a_markdown_line_ending():
    # the premise, read off the language: each one splits a line for str.splitlines(), none is CR or LF
    for _, sep in J_SEPARATORS:
        assert len(("a" + sep + "b").splitlines()) == 2
        assert sep not in "\r\n"
    assert len(J_SEPARATORS) == 8
