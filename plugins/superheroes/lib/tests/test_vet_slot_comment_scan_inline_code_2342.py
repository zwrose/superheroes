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

def test_c2_run_verb_does_not_refuse_body_emptied_for_an_inline_code_opener_above_the_heading(tmp_path):
    body = NOTE_LINE + BODY
    fake = _fake(body, receipt=RECEIPT)
    result = _write(fake, tmp_path)
    assert result == {"ok": True, "verb": "write", "followups": ["FU1", "FU2"], "receipt": "https://x/c/1"}
    assert len(fake.edit_calls()) == 1
    assert fake.edited == [_builder_new_body(body)]


def test_c2_evaluate_does_not_refuse_body_emptied():
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


def test_c11_a_blank_line_ends_the_raw_block_so_a_later_quoted_opener_is_text_again(tmp_path):
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


@pytest.mark.parametrize("body, expected", [
    ("<div>\n`<!--`\nnext\n", [False, False, True]),
    ("<div>\n\n`<!--`\nnext\n", [False, False, False, False]),
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


def test_c12_a_tag_inside_a_comment_starts_no_raw_run(tmp_path):
    body = "<!-- note\n<div>\n-->\n" + CODE_SPAN_LINE
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


def test_c12_a_quoted_blank_line_ends_a_quoted_raw_run(tmp_path):
    body = "> <div>\n> </div>\n>\n> Handles `<!--` literally.\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(body, SLOT)]


@pytest.mark.parametrize("body, expected", [
    ("<https://example.com>\n`<!--`\nnext\n", [False, False, False]),
    ("<div class=\"x\">\n`<!--`\nnext\n", [False, False, True]),
    ("<br/>\n`<!--`\nnext\n", [False, False, True]),
    ("</details>\n`<!--`\nnext\n", [False, False, True]),
    ("<!-- c\n<div>\n-->\n`<!--`\nnext\n", [False, True, True, False, False]),
    ("> <div>\n>\n> `<!--`\nnext\n", [False, False, False, False]),
], ids=["autolink", "tag-with-attribute", "self-closing", "closing-tag", "tag-in-comment", "quoted-blank"])
def test_c12_comment_scan_raw_run_boundaries(body, expected):
    assert [row[3] for row in vs._comment_scan(body)] == expected
