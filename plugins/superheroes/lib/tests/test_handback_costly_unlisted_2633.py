"""#2633: ``vet_slot.py handback`` refuses ``costly-not-accepted`` for a costly or unlabelled degradation that no line
under What we're accepting carries, by the merge sheet build's own comparison (``pr_sheet.costly_unlisted``). No gh, no
network."""
import copy
import json
from pathlib import Path

import pytest

import pr_sheet
import vet_slot as vs
from test_calibration_disclosure_2364 import CODE1, PR, REPO, Fake, mark, record_comment, row

LIB = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
WORDS = json.loads((LIB.parent / "theme" / "sheet-words.json").read_text(encoding="utf-8"))["pr"]
SHEET_PR = 211  # the PR record-small.json names

GATE = "The verify gate did not run on the final head"
LONG = ("The engine review seat forfeited on every rung of the retry ladder, so one specialist lens never read this "
        "diff at all")
NO_LINE = "has no line under What we're accepting"


def body(accepting, *degradations):
    """A handback body the marker read passes: What we're accepting holds the given lines (None when there are none),
    and the build record's Disclosed degradations lists the given bullets (None when there are none)."""
    accepting_lines = "".join("- %s\n" % line for line in accepting) or "None\n"
    bullets = "".join("- %s\n" % b for b in degradations) or "None\n"
    return ("Closes #100.\n\n## What's changing, and why\n\nThe export lists newest first.\n\n"
            "## What we're accepting\n\n" + accepting_lines + "\n## How to see it\n\nN/A, nothing to see.\n\n"
            "## Advisor vet\n<!-- superheroes:advisor-vet -->\nslot text\n\n"
            "<!-- superheroes:build-record -->\n<details><summary>Build record</summary>\n\n"
            "### Follow-ups for the advisor\n\nFollow-ups: none\n<!-- superheroes:followups none -->\n\n"
            "<!-- superheroes:degradations -->\n### Disclosed degradations\n\n" + bullets + "\n</details>\n")


def sheet_costly_problems(text):
    """The costly-line problems the real merge sheet build raises over this body as PR 211's (other problems, such as an
    unaccounted acceptance, are not this rule's and are dropped)."""
    records = [json.loads((FIXTURES / "record-small.json").read_text(encoding="utf-8"))]
    advisor = json.loads((FIXTURES / "input-small.json").read_text(encoding="utf-8"))
    try:
        pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, bodies={SHEET_PR: text})
    except pr_sheet.Refusal as exc:
        return [p for p in exc.problems if "deviation" in p and "What we're accepting" in p]
    return []


GATE_PROBLEM = 'costly deviation ("%s.") %s' % (GATE, NO_LINE)
LONG_PROBLEM = 'costly deviation ("%s…") %s' % (LONG[:80], NO_LINE)
EMPTY_PROBLEM = 'costly deviation ("") %s' % NO_LINE

# name -> (body, the problem texts the refusal must name, written out here and never derived from costly_unlisted)
REFUSALS = {
    "costly": (body([], "[costly] %s." % GATE), [GATE_PROBLEM]),
    "unlabelled": (body([], "%s." % GATE), ['unlabelled (read as costly) deviation ("%s.") %s' % (GATE, NO_LINE)]),
    "costly-beside-harmless": (body([], "[harmless] The order rode a prompt file.", "[costly] %s." % GATE),
                               [GATE_PROBLEM]),
    "line-carries-another-text": (body(["Something else entirely, so nothing is unverified."], "[costly] %s." % GATE),
                                  [GATE_PROBLEM]),
    "two-costly": (body([], "[costly] %s." % GATE, "[costly] %s." % LONG), [GATE_PROBLEM, LONG_PROBLEM]),
    "carried-then-missing": (body(["%s, so CI is the receipt." % GATE], "[costly] %s." % GATE, "[costly] %s." % LONG),
                             [LONG_PROBLEM]),
    "empty-costly-bullet": (body(["%s, so CI is the receipt." % GATE], "[costly]"), [EMPTY_PROBLEM]),
}
REFUSED = {name: text for name, (text, _problems) in REFUSALS.items()}
PASSED = {
    "costly-carried": body(["%s, so the last commit's tests are unverified until CI runs." % GATE],
                           "[costly] %s." % GATE),
    "costly-carried-emphasis-and-case": body(["**the verify gate did not run on the final head** until CI runs"],
                                             "[costly] %s." % GATE),
    "harmless-only": body([], "[harmless] The order rode a prompt file."),
    "no-degradations": body([]),
}


@pytest.mark.parametrize("name", list(REFUSALS))
def test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting(name):
    # Bites on: check_costly_accepted not calling costly_unlisted, or a comparison that stops after the first carried bullet.
    # Axis: a costly or unlabelled bullet with no carrying line refuses costly-not-accepted, naming exactly the bullets the
    # case lists and no carried one.
    text, problems = REFUSALS[name]
    result = vs.handback_body(text)
    assert result["ok"] is False and result["reason"] == vs.REASON_COSTLY_NOT_ACCEPTED
    for problem in problems:
        assert "the " + problem in result["detail"]
    assert result["detail"].count("deviation") == len(problems)


@pytest.mark.parametrize("text", list(PASSED.values()), ids=list(PASSED))
def test_handback_passes_once_the_line_carries_the_text_or_the_degradation_is_harmless(text):
    # Bites on: the handback check asking a harmless bullet for a line, or comparing more strictly than the sheet.
    # Axis: a carried costly line, a harmless-only list and an empty list all pass.
    assert vs.handback_body(text) == {"ok": True, "verb": "handback", "followups": []}


def test_the_refusal_names_the_unlabelled_reading_and_the_start_of_a_long_text():
    # Bites on: the handback detail dropping the label reading or the text excerpt the sheet's problem line gives.
    # Axis: the detail reads as the sheet's problem line does: the unlabelled reading named, a long text cut to 80 characters.
    detail = vs.handback_body(body([], LONG + "."))["detail"]
    assert "unlabelled (read as costly) deviation" in detail and LONG[:80] + "…" in detail and LONG not in detail


@pytest.mark.parametrize("text", list(REFUSED.values()) + list(PASSED.values()), ids=list(REFUSED) + list(PASSED))
def test_handback_and_the_merge_sheet_build_agree(text):
    # Bites on: either check gaining a second copy of the rule that drifts from the other.
    # Axis: the sheet build refuses a body for a costly line exactly when handback refuses it costly-not-accepted, and
    # handback's whole detail is the sheet's problem lines, each with its prefix swapped, joined in order.
    sheet = sheet_costly_problems(text)
    result = vs.handback_body(text)
    assert bool(sheet) == (result.get("reason") == vs.REASON_COSTLY_NOT_ACCEPTED)
    assert (result["ok"] is True) == (not sheet)
    prefix = "PR #%d's " % SHEET_PR
    assert all(problem.startswith(prefix) for problem in sheet)
    if sheet:
        assert result["detail"] == "; ".join("the " + problem[len(prefix):] for problem in sheet)


def test_run_verb_body_file_refuses_costly_not_accepted(tmp_path):
    # Bites on: the --body-file path skipping the costly check the --pr path runs.
    # Axis: handback --body-file returns the same refusal handback_body does, and passes a carried body.
    path = tmp_path / "body.md"
    path.write_text(REFUSED["costly"], encoding="utf-8")
    assert vs.run_verb("handback", None, None, body_file=str(path))["reason"] == vs.REASON_COSTLY_NOT_ACCEPTED
    path.write_text(PASSED["costly-carried"], encoding="utf-8")
    assert vs.run_verb("handback", None, None, body_file=str(path))["ok"] is True


def test_run_verb_body_file_keeps_the_marker_refusal_ahead_of_the_costly_check(tmp_path):
    # Bites on: the costly check moved ahead of check_handback on the --body-file path.
    # Axis: a body that misses its followups marker and its costly line refuses markers-invalid, naming the marker.
    text = REFUSED["costly"].replace("<!-- superheroes:followups none -->\n", "")
    assert text != REFUSED["costly"] and pr_sheet.costly_unlisted(text)
    path = tmp_path / "body.md"
    path.write_text(text, encoding="utf-8")
    result = vs.run_verb("handback", None, None, body_file=str(path))
    assert result["ok"] is False and result["reason"] == "markers-invalid" and "followups" in result["detail"]


@pytest.mark.parametrize("name, ok", [("costly", False), ("unlabelled", False), ("costly-carried", True),
                                      ("harmless-only", True)])
def test_run_verb_pr_path_refuses_costly_not_accepted_after_its_record_checks(monkeypatch, name, ok):
    # Bites on: the --pr path (the one the ready mark runs) skipping the costly check the --body-file path runs.
    # Axis: over an open PR with a readable review record, a missing costly line refuses costly-not-accepted and a
    # carried or harmless one passes.
    monkeypatch.setattr(vs.shutil, "which", lambda tool: "/usr/bin/gh" if tool == "gh" else None)
    text = {**REFUSED, **PASSED}[name]
    result = vs.run_verb("handback", PR, REPO, run=Fake(text, [record_comment([row(CODE1)])]))
    assert result["ok"] is ok
    if not ok:
        assert result["reason"] == vs.REASON_COSTLY_NOT_ACCEPTED and GATE in result["detail"]


def test_run_verb_pr_path_keeps_earlier_refusals_ahead_of_the_costly_check(monkeypatch):
    # Bites on: the costly check moved ahead of the review-record read or the calibration-disclosure check on the --pr path.
    # Axis: a body that also misses its costly line still refuses review-record-unreadable with no record, and
    # calibration-disclosure-contradicted when the record shows the named file read.
    monkeypatch.setattr(vs.shutil, "which", lambda tool: "/usr/bin/gh" if tool == "gh" else None)
    assert vs.run_verb("handback", PR, REPO, run=Fake(REFUSED["costly"], []))["reason"] == "review-record-unreadable"
    contradicted = body([], "[costly] %s" % mark(CODE1, "core.md"))
    assert pr_sheet.costly_unlisted(contradicted)
    result = vs.run_verb("handback", PR, REPO, run=Fake(contradicted, [record_comment([row(CODE1)])]))
    assert result["reason"] == "calibration-disclosure-contradicted"
