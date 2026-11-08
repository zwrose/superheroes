"""#2352: ``vet_slot.py write`` on a builder body replaces the slot span only when it holds nothing but advisor-owned
content, and every slot it composes is itself advisor-owned (emitter within recogniser).

The advisor's own span, once the builder's reminder comments and the blank lines are removed, is nothing, or a run of
lines that opens with a verdict token, holds no HTML comment, and holds no live heading. Fake-runner units; no real gh,
no network. Every case runs through ``vs.evaluate`` and through ``vs.run_verb``. The edges are numbered E1 to E20 as in
the order; the bite-proof record is bite_proofs/i2352_vet_slot_builder_text.md."""
import pytest

import vet_slot as vs
from test_vet_slot import REMINDER, USER, VIEW, FakeGh, _comment, _pages

PR = 42
REPO = "owner/example"
MARKER = "<!-- superheroes:advisor-vet -->"
RECEIPT_NONE = "<!-- superheroes:vet-receipt -->\n**Vet 1: NOT-READY.**\n<!-- superheroes:dispositions none -->\n"
SLOT = "**Verdict: NOT-READY** · abc\n\nNew owner half.\n"
SLOT_2 = "**Verdict: NOT-READY** · def\n\nA second owner half.\n"
VERDICT = "**Verdict: NOT-READY** · old\n"
HEAD = "## What's changing, and why\n\nThe builder's owner half.\n\n## Advisor vet\n" + MARKER + "\n"
TAIL = ("<!-- superheroes:build-record -->\n<details><summary>Build record</summary>\n\n"
        "<!-- superheroes:followups none -->\n</details>\n\ntrailer\n")
# what a healthy write of SLOT makes of any advisor-owned span: written out, not computed
EXPECTED = HEAD + "\n**Verdict: NOT-READY** · abc\n\nNew owner half.\n\n" + TAIL
EXPECTED_2 = HEAD + "\n**Verdict: NOT-READY** · def\n\nA second owner half.\n\n" + TAIL
CLOSED_REMINDER = "<!-- advisor: BEFORE writing this slot, then replace this comment. -->\n"
# the field case: the builder's heading section after the stamped reminder
TEST_ANSWERS = "## Test answers\n\nThe builder's answers to the owner's questions.\n"


def body_of(span):
    return HEAD + span + TAIL


def evaluate(body, slot=SLOT, **kwargs):
    return vs.evaluate("write", body, [_comment(RECEIPT_NONE)], slot, advisor_login="advisor", **kwargs)


def run(body, tmp_path, slot=SLOT, slot_file=None):
    fake = FakeGh([body], _pages([_comment(RECEIPT_NONE)]))
    path = slot_file
    if path is None:
        path = tmp_path / "slot.md"
        path.write_text(slot, encoding="utf-8")
    return vs.run_verb("write", PR, REPO, slot_file=str(path), run=fake), fake


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def line_of(span, needle):
    """The 1-based line of the span that starts with ``needle``."""
    return next(i for i, line in enumerate(span.splitlines(), 1) if line.startswith(needle))


def assert_refused(result, reason, *details):
    assert result["ok"] is False, result
    assert result["reason"] == reason, result
    for detail in details:
        assert detail in result["detail"], result
    assert "newBody" not in result, result


def assert_refused_both_ways(span, tmp_path, reason, *details, body=None):
    """The same refusal through ``evaluate`` and through ``run_verb``, with nothing written and only the PR read."""
    body = body_of(span) if body is None else body
    assert_refused(evaluate(body), reason, *details)
    result, fake = run(body, tmp_path)
    assert_refused(result, reason, *details)
    assert fake.edit_calls() == [] and fake.edited == []
    return fake


def assert_writes_both_ways(body, tmp_path, expected=EXPECTED, slot=SLOT):
    result = evaluate(body, slot)
    assert result["ok"] is True, result
    assert result["newBody"] == expected
    result, fake = run(body, tmp_path, slot)
    assert result["ok"] is True, result
    assert "newBody" not in result
    assert len(fake.edit_calls()) == 1
    assert fake.edited == [expected]


# --- E1 to E4: the advisor's own spans write, byte for byte -------------------------------------------------------

def test_e1_marker_with_the_reminder_only_writes(tmp_path):
    body = body_of(REMINDER)
    assert_writes_both_ways(body, tmp_path)
    assert "advisor: BEFORE" not in evaluate(body)["newBody"]


def test_e1_the_reminder_with_irregular_whitespace_and_indent_still_writes(tmp_path):
    span = "   <!--   advisor:\tBEFORE   writing this slot, read\n   the charter -->  \n"
    assert_writes_both_ways(body_of(span), tmp_path)


def test_e2_an_earlier_verdict_only_writes(tmp_path):
    assert_writes_both_ways(body_of(VERDICT), tmp_path)
    assert_writes_both_ways(body_of("\n" + VERDICT + "\nAn earlier owner half.\n\n"), tmp_path)


@pytest.mark.parametrize("span", [
    VERDICT + "\n" + REMINDER,
    REMINDER + "\n" + VERDICT,
    VERDICT + "\n" + REMINDER + "\nAn earlier owner half.\n",
    REMINDER + REMINDER + VERDICT,
    VERDICT + CLOSED_REMINDER + "more of the owner half\n" + CLOSED_REMINDER,
])
def test_e3_a_verdict_and_a_reminder_in_either_order_write_and_the_reminder_goes(span, tmp_path):
    assert_writes_both_ways(body_of(span), tmp_path)


@pytest.mark.parametrize("span", ["", "\n", "   \n\t\n\n", "\r\n\r\n"])
def test_e4_an_empty_or_whitespace_span_writes(span, tmp_path):
    assert_writes_both_ways(body_of(span), tmp_path)


# --- E5 to E12: builder text in the span refuses, nothing written -----------------------------------------------------

def test_e5_a_builder_heading_section_after_the_reminder_refuses(tmp_path):
    """The field case: the builder's ``## Test answers`` stamped under the marker would be deleted by the write."""
    span = REMINDER + "\n" + TEST_ANSWERS
    n = line_of(span, "## Test answers")
    fake = assert_refused_both_ways(span, tmp_path, "slot-span-builder-text",
                                    "line %d of the span" % n, "## Test answers", "sign (a)",
                                    "move that text above the ## Advisor vet heading or below the build-record marker")
    assert fake.calls == [list(VIEW)]  # only the PR read: no login, no comments, no edit


def test_e5_the_pr_body_is_left_as_it_was(tmp_path):
    body = body_of(REMINDER + "\n" + TEST_ANSWERS)
    result, fake = run(body, tmp_path)
    assert result["ok"] is False
    assert fake.bodies == [body]


def test_e5_run_verb_refuses_before_the_slot_file_is_read(tmp_path):
    body = body_of(REMINDER + "\n" + TEST_ANSWERS)
    fake = FakeGh([body], _pages([_comment(RECEIPT_NONE)]))
    result = vs.run_verb("write", PR, REPO, slot_file=str(tmp_path / "no-such-slot.md"), run=fake)
    assert_refused(result, "slot-span-builder-text", "## Test answers")
    assert fake.calls == [list(VIEW)]
    assert list(USER) not in fake.calls


@pytest.mark.parametrize("ending", ["\r", " "])
def test_e5_builder_text_after_a_lone_cr_or_u2028_on_the_marker_line_refuses(ending, tmp_path):
    """The checked span is the span the write replaces: it starts after the marker's own splitlines() line. A marker
    line ended by a lone CR or U+2028 holds builder text before the next newline; the write would replace it, so the
    check reads it, and refuses, with nothing pushed."""
    body = HEAD[:-1] + ending + "Builder note: keep this.\n" + VERDICT + "\n" + TAIL
    # #2389: the marker finder reads Markdown lines, so a U+2028 after the marker leaves no standalone marker; the write still refuses with no edit
    if ending == "\r":
        fake = assert_refused_both_ways("", tmp_path, "slot-span-builder-text", "Builder note: keep this.", "sign (a)",
                                        body=body)
    else:
        fake = assert_refused_both_ways("", tmp_path, "markers-invalid", "advisor-vet marker appears 0 times",
                                        body=body)
    assert fake.calls == [list(VIEW)]
    assert fake.bodies == [body]


def test_e6_a_builder_heading_section_after_an_earlier_verdict_refuses(tmp_path):
    span = VERDICT + "\n" + TEST_ANSWERS
    n = line_of(span, "## Test answers")
    fake = assert_refused_both_ways(span, tmp_path, "slot-span-builder-text",
                                    "line %d of the span" % n, "## Test answers", "sign (c)")
    assert fake.calls == [list(VIEW)]


def test_e7_a_tab_separated_heading_after_a_verdict_refuses(tmp_path):
    span = VERDICT + "\n##\tDefinition of Done\n\nthe bullets\n"
    n = line_of(span, "##")
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line %d of the span" % n, "sign (c)")


@pytest.mark.parametrize("heading", ["#", "######", "   ## indented three", "# One"])
def test_e7_a_bare_or_indented_heading_after_a_verdict_refuses(heading, tmp_path):
    assert_refused_both_ways(VERDICT + heading + "\n", tmp_path, "slot-span-builder-text", "sign (c)")


@pytest.mark.parametrize("span, sign", [
    ("The builder's note on how to test this.\n" + VERDICT, "sign (a)"),
    ("Only prose, no verdict at all.\n", "sign (a)"),
    ("    " + VERDICT, "sign (a)"),
])
def test_e8_prose_before_the_verdict_or_no_verdict_refuses(span, sign, tmp_path):
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 1 of the span", sign)


def test_e8_prose_after_the_reminder_and_before_the_verdict_refuses(tmp_path):
    span = REMINDER + "Prose after the reminder.\n" + VERDICT
    n = line_of(span, "Prose after")
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line %d of the span" % n, "sign (a)")


def test_e8_the_detail_quotes_the_first_sixty_characters_of_the_offending_line(tmp_path):
    prose = "x" * 59 + "ABCDEFG"
    result = evaluate(body_of(prose + "\n" + VERDICT))
    assert "x" * 59 + "A" in result["detail"] and "ABCDEFG" not in result["detail"]


def test_e9_a_non_reminder_advisor_comment_alone_refuses(tmp_path):
    span = "<!-- advisor: Hold this PR until the migration lands. -->\n"
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 1 of the span",
                             "<!-- advisor: Hold this PR")


@pytest.mark.parametrize("span", [
    "<!-- advisor: before writing this slot, check -->\n",
    "<!-- advisor: BEFORE writing the slot -->\n",
    "<!-- note: BEFORE writing this slot -->\n",
    "x <!-- advisor: BEFORE writing this slot -->\n",
])
def test_e9_only_the_exact_reminder_opener_is_the_reminder(span, tmp_path):
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 1 of the span")


@pytest.mark.parametrize("comment", ["<!-- a note for the owner -->", "<!-- todo\nmore\n-->", "text --> after"])
def test_e10_any_other_comment_after_a_verdict_refuses(comment, tmp_path):
    span = VERDICT + "\n" + comment + "\n"
    n = line_of(span, comment.splitlines()[0])
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line %d of the span" % n, "sign (b)")


def test_e10_a_comment_inside_a_fence_still_refuses(tmp_path):
    span = VERDICT + "\n```\n<!-- fenced note -->\n```\n"
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 4 of the span", "sign (b)")


def test_e11_an_unclosed_reminder_refuses(tmp_path):
    span = VERDICT + "\n<!-- advisor: BEFORE writing this slot, read the reference\nand keep reading\n"
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 3 of the span", "sign (b)",
                             "never closed")


def test_e11_an_unclosed_reminder_with_nothing_after_it_refuses(tmp_path):
    assert_refused_both_ways("<!-- advisor: BEFORE writing this slot\n", tmp_path, "slot-span-builder-text",
                             "line 1 of the span", "never closed")


def test_e12_text_after_a_reminders_closing_marker_refuses(tmp_path):
    span = "<!-- advisor: BEFORE writing this slot --> the builder's note\n"
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 1 of the span", "sign (b)",
                             "text follows")
    span = REMINDER.rstrip("\n") + " Trailing words.\n"
    assert_refused_both_ways(VERDICT + span, tmp_path, "slot-span-builder-text", "text follows")


# --- E13: fence-aware ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_e13_a_heading_looking_line_inside_a_fence_within_the_verdict_writes(fence, tmp_path):
    span = VERDICT + "\n" + fence + "\n## not a heading\n##\talso not\n" + fence + "\n"
    assert_writes_both_ways(body_of(span), tmp_path)


def test_e13_a_fence_mark_inside_the_reminder_hides_no_later_heading(tmp_path):
    span = ("<!-- advisor: BEFORE writing this slot\n```\n-->\n" + VERDICT + "\n## Test answers\n```\n")
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "## Test answers", "sign (c)")


# --- E14: an unreadable verdict form fails closed -----------------------------------------------------------------

@pytest.fixture
def form_unreadable(monkeypatch):
    monkeypatch.setattr(vs.stack_check, "_load_vet_verdict_form", lambda: (None, "vet-verdict-form.json is missing"))


def test_e14_form_unreadable_and_a_non_empty_span_refuses_builder_text(form_unreadable, tmp_path):
    for span in (VERDICT, REMINDER + "\n" + VERDICT):
        assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "verdict form cannot be read",
                                 "vet-verdict-form.json is missing", "sign (a)")


def test_e14_form_unreadable_and_an_empty_span_refuses_write_failed_at_the_round_trip(form_unreadable, tmp_path):
    for span in ("", "\n  \n", REMINDER):
        assert_refused_both_ways(span, tmp_path, "write-failed", "would not read as the advisor's own on the next write",
                                 "verdict form cannot be read", "vet-verdict-form.json is missing")


# --- E15, E16: the earlier refusals keep firing first -------------------------------------------------------------

@pytest.mark.parametrize("span", [
    VERDICT + "\n<!-- superheroes:dod-table -->\nthe table\n",
    "<!-- superheroes:dod-table -->\nprose\n",
    REMINDER + "  <!-- superheroes:degradations -->\nNone\n",
])
def test_e15_a_superheroes_marker_line_in_the_span_is_still_foreign_content(span, tmp_path):
    assert_refused_both_ways(span, tmp_path, "slot-span-foreign-content", "the slot span holds the superheroes:")


def test_e16_an_emptied_body_is_still_body_emptied(tmp_path):
    no_owner_half = ("Closes #1.\n\n## Advisor vet\n" + MARKER + "\n" + REMINDER + "\n" + TEST_ANSWERS + TAIL)
    for body in (no_owner_half, "  \n", ""):
        assert_refused(evaluate(body), "body-emptied")
        result, fake = run(body, tmp_path)
        assert_refused(result, "body-emptied")
        assert fake.edit_calls() == []


# --- E17: the round trip (emitter within recogniser) ----------------------------------------------------------------

@pytest.mark.parametrize("slot, detail", [
    (SLOT + "\n## A heading in the slot\n\nmore\n", "## A heading in the slot"),
    (SLOT + "\n##\tTabbed heading\n", "Tabbed heading"),
    (SLOT + "\n#\n", "sign (c)"),
    ("Prose first.\n\n" + SLOT, "Prose first."),
    ("A slot with no verdict token.\n", "sign (a)"),
    ("  " + SLOT, "sign (a)"),
])
def test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed(slot, detail, tmp_path):
    for span in (REMINDER, VERDICT):
        body = body_of(span)
        assert_refused(evaluate(body, slot), "write-failed", "would not read as the advisor's own on the next write",
                       detail)
        result, fake = run(body, tmp_path, slot)
        assert_refused(result, "write-failed", "would not read as the advisor's own on the next write", detail)
        assert fake.edit_calls() == [] and fake.edited == []


def test_e17_a_fenced_heading_in_the_slot_text_is_fine(tmp_path):
    slot = SLOT + "\n```\n## shown as text\n```\n"
    expected = HEAD + "\n" + slot.strip("\n") + "\n\n" + TAIL
    assert_writes_both_ways(body_of(REMINDER), tmp_path, expected, slot)


# --- E18: write, then write over the result --------------------------------------------------------------------------

def test_e18_a_write_over_the_reminder_and_a_second_write_over_its_result_both_succeed(tmp_path):
    first = evaluate(body_of(REMINDER), SLOT)
    assert first["ok"] is True and first["newBody"] == EXPECTED
    second = evaluate(first["newBody"], SLOT_2)
    assert second["ok"] is True and second["newBody"] == EXPECTED_2


def test_e18_two_run_verb_writes_in_a_row_both_succeed(tmp_path):
    fake = FakeGh([body_of(REMINDER)], _pages([_comment(RECEIPT_NONE)]))
    for slot, expected in ((SLOT, EXPECTED), (SLOT_2, EXPECTED_2)):
        path = tmp_path / "slot.md"
        path.write_text(slot, encoding="utf-8")
        result = vs.run_verb("write", PR, REPO, slot_file=str(path), run=fake)
        assert result["ok"] is True, result
        assert fake.edited[-1] == expected
    assert len(fake.edit_calls()) == 2


# --- E19: check and handback are unchanged ------------------------------------------------------------------------

def test_e19_check_and_handback_do_not_read_the_slot_span(tmp_path):
    body = body_of(REMINDER + "\n" + TEST_ANSWERS)
    assert vs.evaluate("check", body, [_comment(RECEIPT_NONE)], advisor_login="advisor") == {
        "ok": True, "verb": "check", "followups": [], "receipt": "https://x/c/1", "receiptPresent": True}
    handed = vs.check_handback(body)
    assert handed["ok"] is True, handed
    fake = FakeGh([body], _pages([_comment(RECEIPT_NONE)]))
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is True and fake.edit_calls() == []
    fake = FakeGh([body], _pages([_comment(RECEIPT_NONE)]))
    result = vs.run_verb("handback", PR, REPO, run=fake)
    # the body read passed; the verb then stops at the review-record read, which this fake does not serve
    assert result["reason"] == "review-record-unreadable", result


# --- E20: the no-build-record path is unchanged --------------------------------------------------------------------

def test_e20_a_no_build_record_body_with_prose_under_its_marker_still_writes(tmp_path):
    bare = ("Bumps requests from 2.31.0 to 2.32.3.\n\n## Advisor vet\n" + MARKER
            + "\nSome prose under the marker, not a verdict.\n\n## What we're accepting\n\n- nothing\n")
    expected = ("Bumps requests from 2.31.0 to 2.32.3.\n\n## Advisor vet\n" + MARKER + "\n\n"
                "**Verdict: NOT-READY** · abc\n\nNew owner half.\n")
    assert vs.no_build_record(bare) is True
    assert_writes_both_ways(bare, tmp_path, expected)


def test_e20_the_no_build_record_path_is_not_round_tripped(tmp_path):
    bare = "Bumps requests from 2.31.0 to 2.32.3.\n"
    slot = "No verdict token here.\n\n## A heading\n"
    expected = bare.rstrip("\r\n") + "\n\n## Advisor vet\n" + MARKER + "\n\n" + slot.strip("\n") + "\n"
    result = evaluate(bare, slot)
    assert result["ok"] is True and result["newBody"] == expected
