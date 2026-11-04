"""#2342: ``vet_slot.py write`` and ``check`` accept a PR body no builder made (no build record), and only that body.

A body takes the no-build-record path if and only if it is non-blank and shows no builder sign anywhere; every other
body takes today's path. Fake-runner units; no real gh, no network. The fixtures come from test_vet_slot.py and
test_vet_slot_leftovers_2280.py."""
import json
import re

import pytest

import vet_slot as vs
from test_vet_slot import BODY, RECEIPT, SLOT, VIEW, FakeGh, _comment, _pages
from test_vet_slot_leftovers_2280 import F1, FIXED, record_comment

PR = 42
REPO = "owner/example"
MARKER = "<!-- superheroes:advisor-vet -->"
BOT_BODY = ("Bumps requests from 2.31.0 to 2.32.3.\n\n- [Release notes](https://example.invalid/r)\n\n"
            "Dependabot will resolve any conflicts with this PR.\n")
READY_SLOT = "**Verdict: READY** · abc\n\nNew owner half.\n"
RECEIPT_NONE = "<!-- superheroes:vet-receipt -->\n**Vet 1: READY.**\n<!-- superheroes:dispositions none -->\n"
ACCEPTING = ("\n## What we're accepting\n\n"
             "- f-1 the retry loop never backs off: merging accepts slower recovery.\n")
HEADING = "## What's changing, and why\n\nThe builder's owner half.\n\n"
BUILD_RECORD = BODY[BODY.index("<!-- superheroes:build-record -->"):]
# the build record with every superheroes marker line but the advisor-vet one removed (its wrapper and headings stay)
BUILD_RECORD_NO_MARKERS = re.sub(r"(?m)^<!-- superheroes:(?!advisor-vet).*-->\n?", "", BUILD_RECORD)


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _fake(body, receipt=RECEIPT_NONE, extra=(), **kwargs):
    comments = ([_comment(receipt)] if receipt is not None else []) + list(extra)
    return FakeGh([body], _pages(comments), **kwargs)


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


def _refused(result, fake, reason, detail=None):
    assert result["ok"] is False, result
    assert result["reason"] == reason, result
    if detail is not None:
        assert detail in result["detail"], result
    assert fake.edit_calls() == []


# --- the chokepoint, as a pure function -------------------------------------------------------------------------

CANONICAL_HEADINGS = ["What's changing, and why", "What we’re accepting", "How to see it", "Build record",
                      "Build brief", "Dispatch provenance", "Disclosed degradations", "Follow-ups for the advisor",
                      "Definition of Done", "DoD disposition table", "Size tripwire", "Bite-proof records",
                      "Build record ##"]


@pytest.mark.parametrize("text", CANONICAL_HEADINGS)
def test_each_canonical_builder_heading_is_a_builder_sign(text):
    assert vs.no_build_record(BOT_BODY) is True
    assert vs.no_build_record(BOT_BODY + "\n## " + text + "\n") is False


def test_the_advisor_vet_heading_alone_is_not_a_builder_sign():
    assert vs.no_build_record(BOT_BODY + "\n## Advisor vet\n") is True
    assert vs.no_build_record(BOT_BODY + "\n## Advisor vet\n" + MARKER + "\n") is True


@pytest.mark.parametrize("body", ["", "  \n\t\n", "\n", None, 5, b"x"])
def test_a_blank_or_non_string_body_is_never_no_build_record(body):
    assert vs.no_build_record(body) is False


@pytest.mark.parametrize("line", [
    "\t## Build record", ">## Build record", "> - ## Build record", "1. ### Definition of Done",
    "  #\tBuild brief", "### BUILD   RECORD", "> > ## How to see it",
])
def test_headings_in_tabs_quotes_and_lists_are_builder_signs(line):
    assert vs.no_build_record(BOT_BODY + "\n" + line + "\n") is False


@pytest.mark.parametrize("title", ["Build\trecord", "Definition\tof Done", "Size\t\ttripwire", "What's\tchanging, and why"])
def test_a_tab_inside_a_builder_heading_separates_its_words(title):
    assert vs.no_build_record(BOT_BODY + "\n## " + title + "\n") is False


def test_a_builder_section_with_a_tab_in_its_heading_below_the_marker_is_never_written_over(tmp_path):
    body = "Bumps x.\n\n" + MARKER + "\n\n## Build\trecord\n\nKeep this.\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    assert fake.calls == [list(VIEW)]


def test_the_accepting_exemption_is_below_a_live_marker_only():
    below = BOT_BODY + "\n## Advisor vet\n" + MARKER + "\n\nslot\n" + ACCEPTING
    above = BOT_BODY + ACCEPTING + "\n## Advisor vet\n" + MARKER + "\n"
    fenced = BOT_BODY + "\n```\n" + MARKER + "\n```\n" + ACCEPTING
    assert vs.no_build_record(below) is True
    assert vs.no_build_record(above) is False
    assert vs.no_build_record(BOT_BODY + ACCEPTING) is False
    assert vs.no_build_record(fenced) is False


@pytest.mark.parametrize("body", [
    BOT_BODY + MARKER + " <!-- superheroes:build-record -->\n",
    BOT_BODY + "text <!-- superheroes:followups none --> text\n",
    BOT_BODY + "```\n<!-- superheroes:followups none -->\n```\n",
    BOT_BODY + "<!--superheroes:dod-table -->\n",
    BOT_BODY + "<details><summary class='x'> Build  record</summary>\n",
    BOT_BODY + "<SUMMARY>\nBuild record</SUMMARY>\n",
])
def test_the_other_builder_signs(body):
    assert vs.no_build_record(body) is False


# --- E1: a blank body is never no-build-record -----------------------------------------------------------------------

@pytest.mark.parametrize("body", ["", "   \n\t\n", "\n"])
def test_e1_blank_body_on_write_refuses_body_emptied(body, tmp_path):
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "body-emptied", "PR body is empty")
    assert fake.calls == [list(VIEW)]


def test_e1_null_rest_body_on_write_refuses_body_emptied(tmp_path):
    fake = _fake(BOT_BODY, view_raw=json.dumps({"body": None}))
    _refused(_write(fake, tmp_path), fake, "body-emptied", "PR body is empty")


@pytest.mark.parametrize("verb", ["write", "check"])
def test_e1_evaluate_keeps_the_blank_body_reasons(verb):
    result = vs.evaluate(verb, "  \n", [_comment(RECEIPT_NONE)], SLOT, advisor_login="advisor")
    assert result["reason"] == ("body-emptied" if verb == "write" else "read-failed")


def test_e1_check_on_a_blank_body_is_read_failed():
    fake = _fake("")
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is False and result["reason"] == "read-failed"


# --- E2: the bot body, a READY verdict ---------------------------------------------------------------------------------

def test_e2_a_bot_body_takes_a_ready_slot_appended_under_a_new_advisor_vet_heading(tmp_path):
    fake = _fake(BOT_BODY, extra=[record_comment([FIXED])])
    result = _write(fake, tmp_path, READY_SLOT)
    assert result == {"ok": True, "verb": "write", "followups": [], "receipt": "https://x/c/1"}
    assert len(fake.edit_calls()) == 1
    assert fake.edited == [BOT_BODY.rstrip("\r\n") + "\n\n## Advisor vet\n<!-- superheroes:advisor-vet -->\n\n"
                           + READY_SLOT.strip("\n") + "\n"]


def test_e2_evaluate_composes_the_same_body():
    result = vs.evaluate("write", BOT_BODY, [_comment(RECEIPT_NONE)], SLOT, advisor_login="advisor")
    assert result["ok"] is True and result["followups"] == []
    assert result["newBody"] == _appended(BOT_BODY, SLOT)


def test_e2_a_bot_body_with_the_marker_present_has_the_slot_replaced_to_the_end(tmp_path):
    body = BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nold slot\n\nmore old slot\n"
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [_replaced(body, SLOT)]


def test_e2_a_missing_receipt_still_refuses_receipt_missing(tmp_path):
    fake = _fake(BOT_BODY, receipt=None)
    _refused(_write(fake, tmp_path), fake, "receipt-missing")


# --- E3: a receipt that lists ids over a body with none ---------------------------------------------------------------

def test_e3_a_receipt_listing_followups_refuses_disposition_unknown(tmp_path):
    fake = _fake(BOT_BODY, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "disposition-unknown", "FU1, FU2")


# --- E4: READY needs a readable review record -----------------------------------------------------------------------------

def test_e4_ready_with_no_review_record_refuses_review_record_unreadable(tmp_path):
    fake = _fake(BOT_BODY)
    _refused(_write(fake, tmp_path, READY_SLOT), fake, "review-record-unreadable")


# --- E5: leftovers must be named, and the accepting heading in the slot is the exemption ------------------------------------

def test_e5_a_leftover_the_slot_does_not_name_refuses_leftover_not_accepted(tmp_path):
    fake = _fake(BOT_BODY, extra=[record_comment([F1])])
    _refused(_write(fake, tmp_path, READY_SLOT), fake, "leftover-not-accepted", "f-1")


@pytest.mark.parametrize("apostrophe", ["'", "’"])
def test_e5_a_slot_naming_the_leftover_under_what_were_accepting_writes_and_rewrites(apostrophe, tmp_path):
    slot = READY_SLOT + ACCEPTING.replace("'", apostrophe)
    fake = _fake(BOT_BODY, extra=[record_comment([F1])])
    result = _write(fake, tmp_path, slot)
    assert result["ok"] is True, result
    assert fake.edited == [_appended(BOT_BODY, slot)]
    first = fake.edited[0]
    assert vs.no_build_record(first) is True
    # a second write over the resulting body: the marker is present, the old slot holds the exempt heading
    second_slot = "**Verdict: READY** · def\n\nSecond owner half.\n" + ACCEPTING.replace("'", apostrophe)
    again = _fake(first, extra=[record_comment([F1])])
    result = _write(again, tmp_path, second_slot)
    assert result["ok"] is True, result
    assert again.edited == [_replaced(first, second_slot)]
    assert "New owner half." not in again.edited[0]
    assert again.edited[0].startswith(BOT_BODY)


# --- E6: the advisor-vet marker twice -----------------------------------------------------------------------------------------

def test_e6_the_advisor_vet_marker_twice_refuses_markers_invalid(tmp_path):
    body = BOT_BODY + "\n## Advisor vet\n" + MARKER + "\none\n" + MARKER + "\ntwo\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "markers-invalid", "advisor-vet marker appears 2 times")
    check = vs.run_verb("check", PR, REPO, run=_fake(body))
    assert check["reason"] == "markers-invalid"


# --- E7: a slot that would not render ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tail", ["\n```\nsome code that never ends\n", "\n<!-- a draft note that never closes\n"],
                         ids=["unclosed-fence", "unclosed-comment"])
def test_e7_a_body_ending_inside_a_fence_or_comment_refuses_write_failed(tail, tmp_path):
    body = BOT_BODY + tail
    assert vs.no_build_record(body) is True
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


# --- E8: a builder body with its build record stripped is still refused ------------------------------------------------

STRIPPED_WHOLE = BODY[:BODY.index("<!-- superheroes:build-record -->")]
STRIPPED_MARKERS_ONLY = "".join(line for line in BODY.splitlines(keepends=True)
                                if not line.startswith(("<!-- superheroes:build-record",
                                                        "<!-- superheroes:followups")))


@pytest.mark.parametrize("body", [STRIPPED_WHOLE, STRIPPED_MARKERS_ONLY], ids=["whole-record", "markers-only"])
def test_e8_a_builder_body_with_its_build_record_stripped_is_refused_as_today(body, tmp_path):
    assert vs.no_build_record(body) is False
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "markers-invalid", "build-record marker appears 0 times")
    assert vs.evaluate("write", body, [_comment(RECEIPT_NONE)], SLOT, advisor_login="advisor")["reason"] \
        == "markers-invalid"


def test_e8_the_whole_builder_body_still_writes_as_before(tmp_path):
    fake = _fake(BODY, receipt=RECEIPT)
    assert _write(fake, tmp_path)["ok"] is True
    assert vs.no_build_record(BODY) is False


# --- E9: below-the-marker builder sections, with no superheroes marker but advisor-vet -----------------------------------------

E9_BODIES = [
    pytest.param("## Advisor vet\n" + MARKER + "\n\n" + HEADING + BUILD_RECORD_NO_MARKERS, id="slot-span"),
    pytest.param("## Advisor vet\n" + MARKER + "\n" + BUILD_RECORD_NO_MARKERS + "\n" + HEADING,
                 id="below-the-build-record"),
    pytest.param(BOT_BODY + "\n## Advisor vet\n" + MARKER + "\n\n" + HEADING, id="bare-slot-span"),
    pytest.param(BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nold slot\n\n" + HEADING, id="bare-below"),
    pytest.param(BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nold slot\n\n## How to see it\n\nx\n",
                 id="bare-how-to-see-it"),
    pytest.param(BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nold slot\n\n### Definition of Done\n\n- x\n",
                 id="bare-definition-of-done"),
]


@pytest.mark.parametrize("body", E9_BODIES)
def test_e9_run_verb_refuses_body_emptied_and_makes_no_edit(body, tmp_path):
    assert vs.no_build_record(body) is False
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "body-emptied")


@pytest.mark.parametrize("body", E9_BODIES)
def test_e9_evaluate_agrees(body):
    result = vs.evaluate("write", body, [_comment(RECEIPT_NONE)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied"
    assert "newBody" not in result


# --- E10: markerless build-record remnants -------------------------------------------------------------------------------------

REMNANTS = [
    pytest.param("<details><summary>Build record</summary>\n\nnotes\n</details>\n", id="wrapper"),
    pytest.param("### DoD disposition table\n\n| a | b |\n", id="dod-heading"),
    pytest.param("### Dispatch provenance\n\nrow\n", id="dispatch-heading"),
    pytest.param("### Disclosed degradations\n\nnone\n", id="degradations-heading"),
    pytest.param("```\n<!-- superheroes:followups none -->\n```\n", id="fenced-followups-marker"),
    pytest.param("<!-- superheroes:dod-table -->\n", id="dod-table-marker"),
    pytest.param("> ### Dispatch provenance\n", id="blockquote-heading"),
    pytest.param("- ## What's changing, and why\n", id="list-heading"),
    pytest.param("<details><summary>\nBuild record</summary>\n", id="wrapper-split-across-lines"),
]


@pytest.mark.parametrize("with_marker", [False, True], ids=["no-marker", "with-marker"])
@pytest.mark.parametrize("remnant", REMNANTS)
def test_e10_a_markerless_remnant_alone_is_refused(remnant, with_marker, tmp_path):
    body = BOT_BODY + "\n" + remnant
    if with_marker:
        body += "\n## Advisor vet\n" + MARKER + "\nold slot\n"
    assert vs.no_build_record(body) is False
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    result = vs.evaluate("write", body, [_comment(RECEIPT_NONE)], SLOT, advisor_login="advisor")
    assert result["ok"] is False and result["reason"] == "body-emptied"


# --- E11: What we're accepting above the marker, or with no marker -----------------------------------------------------------------

@pytest.mark.parametrize("body", [
    BOT_BODY + ACCEPTING + "\n## Advisor vet\n" + MARKER + "\nold slot\n",
    BOT_BODY + ACCEPTING,
], ids=["above-the-marker", "no-marker"])
def test_e11_accepting_above_the_marker_or_with_no_marker_is_refused(body, tmp_path):
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "body-emptied")


# --- E12: check ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("body", [BOT_BODY, BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nsome slot\n"],
                         ids=["no-marker", "with-marker"])
def test_e12_check_on_a_bot_body(body):
    result = vs.run_verb("check", PR, REPO, run=_fake(body, receipt=None))
    assert result == {"ok": True, "verb": "check", "followups": [], "receipt": None, "receiptPresent": False}
    result = vs.run_verb("check", PR, REPO, run=_fake(body))
    assert result == {"ok": True, "verb": "check", "followups": [], "receipt": "https://x/c/1",
                      "receiptPresent": True}
    fake = _fake(body, receipt=RECEIPT)
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is False and result["reason"] == "disposition-unknown"
    assert fake.edit_calls() == []


def test_e12_check_on_a_builder_body_missing_its_build_record_is_still_refused():
    result = vs.run_verb("check", PR, REPO, run=_fake(STRIPPED_WHOLE))
    assert result["ok"] is False and result["reason"] == "markers-invalid"


# --- E13: handback is unchanged ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("body", [BOT_BODY, BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nslot\n"],
                         ids=["no-marker", "with-marker"])
def test_e13_handback_on_a_bot_body_is_still_markers_invalid(body, tmp_path):
    assert vs.check_handback(body)["reason"] == "markers-invalid"
    path = tmp_path / "body.md"
    path.write_text(body, encoding="utf-8")
    result = vs.run_verb("handback", None, None, body_file=str(path))
    assert result["ok"] is False and result["reason"] == "markers-invalid"
    fake = _fake(body)
    assert vs.run_verb("handback", PR, REPO, run=fake)["reason"] == "markers-invalid"
    assert fake.edit_calls() == []


# --- E15: the marker as the last line, and a fenced marker ------------------------------------------------------------------------------------

def test_e15_a_marker_as_the_last_line_with_no_newline_takes_the_slot_below_it(tmp_path):
    body = BOT_BODY + "\n## Advisor vet\n" + MARKER
    fake = _fake(body)
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert fake.edited == [body + "\n\n" + SLOT.strip("\n") + "\n"]


def test_e15_a_fenced_marker_then_an_accepting_heading_is_refused(tmp_path):
    body = BOT_BODY + "\n```\n" + MARKER + "\n```\n" + ACCEPTING
    assert vs.no_build_record(body) is False
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "body-emptied")


# --- E16: a comment left open before a present marker ------------------------------------------------------------------------------------

def test_e16_text_before_a_present_marker_that_leaves_a_comment_open_refuses_write_failed(tmp_path):
    body = "Bumps x.\n\n<!-- a note that never closes\n\n## Advisor vet\n" + MARKER + "\nold slot\n"
    assert vs.no_build_record(body) is True
    fake = _fake(body)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


# --- E17: a slot text that carries a builder heading -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("heading", ["## How to see it", "## Definition of Done", "### Build record"])
@pytest.mark.parametrize("body", [BOT_BODY, BOT_BODY + "\n## Advisor vet\n" + MARKER + "\nold slot\n"],
                         ids=["marker-absent", "marker-present"])
def test_e17_a_slot_with_a_builder_heading_refuses_write_failed(heading, body, tmp_path):
    slot = "**Verdict: NOT-READY** · abc\n\n" + heading + "\n\nx\n"
    fake = _fake(body)
    _refused(_write(fake, tmp_path, slot), fake, "write-failed", "the slot text carries a builder heading")


def test_e17_a_slot_with_the_build_record_wrapper_refuses_write_failed(tmp_path):
    slot = "**Verdict: NOT-READY** · abc\n\n<details><summary>Build record</summary>\n"
    fake = _fake(BOT_BODY)
    _refused(_write(fake, tmp_path, slot), fake, "write-failed", "the slot text carries a builder heading")


def test_e17_a_slot_with_the_accepting_heading_is_the_exemption_and_writes(tmp_path):
    slot = "**Verdict: NOT-READY** · abc\n" + ACCEPTING
    fake = _fake(BOT_BODY)
    assert _write(fake, tmp_path, slot)["ok"] is True
    assert fake.edited == [_appended(BOT_BODY, slot)]
