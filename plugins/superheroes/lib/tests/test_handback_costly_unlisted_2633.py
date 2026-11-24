"""#2633: ``vet_slot.py handback`` refuses ``costly-not-accepted`` for a costly or unlabelled degradation that no line
under What we're accepting carries, by the merge sheet build's own comparison (``pr_sheet.costly_unlisted``). No gh, no
network."""
import copy
import json
from pathlib import Path

import pytest

import pr_sheet
import vet_slot as vs

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
        return [p for p in exc.problems if NO_LINE in p]
    return []


REFUSED = {
    "costly": body([], "[costly] %s." % GATE),
    "unlabelled": body([], "%s." % GATE),
    "costly-beside-harmless": body([], "[harmless] The order rode a prompt file.", "[costly] %s." % GATE),
    "line-carries-another-text": body(["Something else entirely, so nothing is unverified."], "[costly] %s." % GATE),
    "two-costly": body([], "[costly] %s." % GATE, "[costly] %s." % LONG),
}
PASSED = {
    "costly-carried": body(["%s, so the last commit's tests are unverified until CI runs." % GATE],
                           "[costly] %s." % GATE),
    "costly-carried-emphasis-and-case": body(["**the verify gate did not run on the final head** until CI runs"],
                                             "[costly] %s." % GATE),
    "harmless-only": body([], "[harmless] The order rode a prompt file."),
    "no-degradations": body([]),
}


@pytest.mark.parametrize("text", list(REFUSED.values()), ids=list(REFUSED))
def test_handback_refuses_a_costly_degradation_missing_from_what_we_are_accepting(text):
    # Bites on: check_handback not calling costly_unlisted, so a body the merge sheet then refuses passes handback.
    # Axis: a costly or unlabelled bullet with no carrying line refuses costly-not-accepted, naming each missing bullet.
    result = vs.check_handback(text)
    assert result["ok"] is False and result["reason"] == "costly-not-accepted"
    missing = pr_sheet.costly_unlisted(text)
    assert missing
    for label, bullet in missing:
        assert pr_sheet.costly_unlisted_problem(label, bullet) in result["detail"]
    assert result["detail"].count(NO_LINE) == len(missing)


@pytest.mark.parametrize("text", list(PASSED.values()), ids=list(PASSED))
def test_handback_passes_once_the_line_carries_the_text_or_the_degradation_is_harmless(text):
    # Bites on: the handback check asking a harmless bullet for a line, or comparing more strictly than the sheet.
    # Axis: a carried costly line, a harmless-only list and an empty list all pass.
    assert vs.check_handback(text) == {"ok": True, "verb": "handback", "followups": []}


def test_the_refusal_names_the_unlabelled_reading_and_the_start_of_a_long_text():
    # Bites on: the handback detail dropping the label reading or the text excerpt the sheet's problem line gives.
    # Axis: the detail reads as the sheet's problem line does: the unlabelled reading named, a long text cut to 80 characters.
    detail = vs.check_handback(body([], LONG + "."))["detail"]
    assert "unlabelled (read as costly) deviation" in detail and LONG[:80] + "…" in detail and LONG not in detail


@pytest.mark.parametrize("text", list(REFUSED.values()) + list(PASSED.values()), ids=list(REFUSED) + list(PASSED))
def test_handback_and_the_merge_sheet_build_agree(text):
    # Bites on: either check gaining a second copy of the rule that drifts from the other.
    # Axis: the sheet build refuses a body for a costly line exactly when handback refuses it costly-not-accepted, and
    # each missing bullet's problem line is the same text after its prefix.
    sheet = sheet_costly_problems(text)
    result = vs.check_handback(text)
    assert bool(sheet) == (result.get("reason") == "costly-not-accepted")
    assert (result["ok"] is True) == (not sheet)
    for problem in sheet:
        assert problem.startswith("PR #%d's " % SHEET_PR)
        assert problem[len("PR #%d's " % SHEET_PR):] in result["detail"]


def test_run_verb_body_file_refuses_costly_not_accepted(tmp_path):
    # Bites on: the --body-file path skipping the costly check the --pr path runs.
    # Axis: handback --body-file returns the same refusal check_handback does.
    path = tmp_path / "body.md"
    path.write_text(REFUSED["costly"], encoding="utf-8")
    assert vs.run_verb("handback", None, None, body_file=str(path))["reason"] == "costly-not-accepted"
