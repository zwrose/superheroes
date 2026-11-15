"""The merge sheet lists what the record lists for the merge verdict, and cards only what waits for the owner (#2493, #2494).

Built through pr_sheet.build, with the helpers test_pr_sheet.py and test_pr_sheet_fixed_above_2332.py already hold; the
records are made here, small, each finding with an explicit `inRiskArea`."""
import copy
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import pr_sheet
import sheet_prose
from test_pr_sheet import SCHEMA, THEME, WORDS, build, problems_of
from test_pr_sheet_fixed_above_2332 import ACCEPTING, make, pr_input, record, refused
from test_sheet_schema import check_sheet_problems

LIB = Path(__file__).resolve().parents[1]
UNSET = object()
ENTRY = {"why": "Only the owner can say.", "context": "It happened in review.", "options": "none"}


def minor(ident, risk=UNSET, outcome="left-for-owner", severity="Minor", reason="A label reads oddly.", consequence="A label stays odd."):
    """A Minor (by default) finding; inRiskArea is written only when given, so an earlier record's finding can be built."""
    found = {"id": ident, "severity": severity, "outcome": outcome, "title": f"Title of {ident}", "reason": reason,
             "consequence": consequence, "findingKey": f"label/{ident}"}
    if risk is not UNSET:
        found["inRiskArea"] = risk
    return found


def sheet_of(findings, **extra):
    leftovers = {f["findingKey"]: ENTRY for f in findings if f["outcome"] == "left-for-owner" and f.get("inRiskArea") is not False}
    return build([record(10, findings)], pr_input(leftovers=leftovers, **extra))


def cards_of(sheet):
    return [c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]


def test_s_card_a_listed_minor_is_in_the_listed_part_and_only_the_waiting_minor_is_a_card():
    """axis: E-card, E-listed: the card loop cards exactly what waits, and the listed part holds exactly what the record lists."""
    listed, waiting = minor("L1", False), minor("W1", True)
    sheet = build([record(10, [listed, waiting])], pr_input(leftovers={waiting["findingKey"]: ENTRY}))
    assert [c["question"] for c in cards_of(sheet)] == ["Title of W1"]
    assert sheet["prSheet"]["listed"] == [{"title": "Title of L1", "detail": "Minor: A label reads oddly."}]
    assert sheet["prSheet"]["craft"] == [] and sheet["prSheet"]["alreadyDecided"] == []


def test_s_old_a_minor_with_no_risk_stamp_is_a_card_and_nothing_is_listed():
    """axis: E-listed: an earlier record's finding, with no inRiskArea, is a card, as before."""
    old = minor("O1")
    sheet = sheet_of([old])
    assert [c["question"] for c in cards_of(sheet)] == ["Title of O1"]
    assert "listed" not in sheet["prSheet"]


@pytest.mark.parametrize("shape", ["null", "absent"])
def test_s_null_listed_a_no_outcome_minor_outside_every_risk_area_builds_and_is_listed(shape):
    """axis: E-null: a null outcome on a listed Minor is admitted by the validator and shown with the no-outcome word."""
    found = minor("N1", False, outcome=None, reason=None, consequence=None)
    if shape == "absent":
        del found["outcome"]
    sheet = build([record(10, [found])], pr_input())
    assert sheet["prSheet"]["listed"] == [{"title": "Title of N1", "detail": "Minor: " + WORDS["listedNoOutcome"]}]
    assert cards_of(sheet) == []


def test_s_null_card_a_no_outcome_minor_in_a_risk_area_is_a_card_and_needs_a_consequence():
    """axis: E-consequence: a waiting finding needs a consequence whatever its outcome; a null-outcome one in a risk area is a card."""
    found = minor("R1", True, outcome=None, reason=None)
    sheet = build([record(10, [found])], pr_input(leftovers={found["findingKey"]: ENTRY}))
    assert [c["question"] for c in cards_of(sheet)] == ["Title of R1"] and "listed" not in sheet["prSheet"]
    bare = minor("R1", True, outcome=None, reason=None, consequence=None)
    problems = problems_of([record(10, [bare])], pr_input(leftovers={bare["findingKey"]: ENTRY}))
    assert "record for PR #10: left-for-owner finding 'Title of R1' has no consequence" in problems, problems


@pytest.mark.parametrize("risk", [True, False, UNSET])
def test_s_null_important_a_no_outcome_important_is_still_refused(risk):
    """axis: E-null-important: only a Minor or Nit may carry no outcome; an Important with none is a missing outcome."""
    found = minor("I1", risk, outcome=None, severity="Important", reason=None, consequence=None)
    problems = problems_of([record(10, [found])], pr_input())
    assert any("finding 'Title of I1' has outcome None, not one of" in p for p in problems), problems


def test_s_advisor_entry_a_leftovers_entry_naming_a_listed_finding_is_refused():
    """axis: the advisor's entry check: a listed finding is no left-for-owner finding, so an entry naming it names none."""
    listed = minor("L1", False)
    problems = problems_of([record(10, [listed])], pr_input(leftovers={listed["findingKey"]: ENTRY}))
    assert f"leftovers key {listed['findingKey']!r} names no left-for-owner finding" in problems, problems


def accounting_world(key):
    listed, waiting = minor("L1", False), minor("W1", True)
    records = [record(10, [listed, waiting])]
    body = ACCEPTING + "- Minor label wording is accepted.\n"
    bullet = pr_sheet.listed_bullets(10, body)[0][0]
    advisor = pr_input(leftovers={waiting["findingKey"]: ENTRY}, accounting={bullet: key(listed, waiting)})
    return records, advisor, {10: body}, bullet


def test_s_accounting_a_bullet_accounted_to_a_listed_finding_builds():
    """axis: E-account: {"listed": key} naming one listed finding accounts the acceptance."""
    records, advisor, bodies, _ = accounting_world(lambda listed, waiting: {"listed": listed["findingKey"]})
    sheet = make(records, advisor, bodies)
    assert [e["title"] for e in sheet["prSheet"]["listed"]] == ["Title of L1"]
    assert len(cards_of(sheet)) == 1


@pytest.mark.parametrize("name,key", [("waiting", lambda listed, waiting: {"listed": waiting["findingKey"]}),
                                      ("nope", lambda listed, waiting: {"listed": "nope"})])
def test_s_accounting_a_listed_target_naming_no_listed_finding_is_refused(name, key):
    """axis: E-account: a listed target needs a key that names exactly one listed finding; a waiting finding's key and a stranger's do not."""
    records, advisor, bodies, bullet = accounting_world(key)
    problems = refused(records, advisor, bodies)
    wanted = next(iter(advisor["accounting"].values()))["listed"]
    assert any(f'names listed "{wanted}", which names no one finding listed for the merge verdict' in p for p in problems), problems


def test_s_accounting_the_old_leftover_target_no_longer_names_a_listed_finding():
    """axis: E-account: a listed finding is not in leftovers, so a leftover target naming it is refused."""
    records, advisor, bodies, bullet = accounting_world(lambda listed, waiting: {"leftover": listed["findingKey"]})
    problems = refused(records, advisor, bodies)
    assert any('names leftover "label/L1", which names no one left-for-owner finding in leftovers' in p for p in problems), problems


def test_s_history_a_listed_minor_adds_no_history_leftover_line():
    """axis: the history's owned leftovers are the waiting findings only; a listed one adds no leftover line."""
    listed = minor("L1", False)
    rec = {**record(10, [listed]), "status": "reviewed", "whatIsMissing": []}
    sheet = build([rec], pr_input())
    history = sheet["prSheet"]["history"]
    assert WORDS["historyLeftover"] not in history
    assert not any(line.endswith("findings are left for you below.") for line in history), history


def test_s_schema_a_sheet_with_a_listed_part_validates_and_an_empty_one_does_not():
    """axis: the schema's listed part is an optional, non-empty array of entries."""
    sheet = sheet_of([minor("L1", False)])
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []
    empty = copy.deepcopy(sheet)
    empty["prSheet"]["listed"] = []
    assert list(Draft202012Validator(SCHEMA).iter_errors(empty)) != []


def test_s_prose_a_listed_part_is_a_folded_part_headed_with_the_words_heading():
    """axis: sheet_prose prints the listed part, after already decided and before the review history, and prints none without it."""
    with_listed = sheet_of([minor("L1", False)])
    out = sheet_prose.render(with_listed)
    heading = f"**{WORDS['listedHeading']} (1)**"
    assert heading in out and "- Title of L1 — Minor: A label reads oddly." in out
    assert out.index(heading) < out.index(f"**{WORDS['reviewHeading']} (")
    without = sheet_prose.render(sheet_of([minor("O1")]))
    assert WORDS["listedHeading"] not in without


def test_s_page_the_template_knows_the_listed_heading_and_builds_the_listed_part():
    """axis: the page reads the listed heading word and builds a pr-listed folded part."""
    source = (THEME / "review-template.html").read_text(encoding="utf-8")
    keys = re.search(r"const PR_WORD_KEYS = \[(.*?)\];", source, re.S)
    assert keys and '"listedHeading"' in keys.group(1)
    assert 'buildFolded("pr-listed"' in source


def test_s_census_the_sheet_never_asks_its_own_outcome_plus_repeat_question():
    """axis: E-census: no left-for-owner outcome comparison in pr_sheet.py is followed within 120 characters by repeat_held_elsewhere."""
    source = (LIB / "pr_sheet.py").read_text(encoding="utf-8")
    copies = re.findall(r"(?:==|!=)\s*_LEFT\b[\s\S]{0,120}?repeat_held_elsewhere", source)
    assert copies == [], f"{len(copies)} copies of the outcome-plus-repeat question remain in pr_sheet.py"
