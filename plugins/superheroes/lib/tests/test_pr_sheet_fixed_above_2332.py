"""A stack sheet shows a left-for-owner finding its PR body marks `fixed-above #<PR> <commit>` in caught as fixed above (#2332).

Built through pr_sheet.build with bodies, as test_pr_sheet.py does; the records and the input are made here, small."""
import copy

import pytest
from jsonschema import Draft202012Validator

import pr_sheet
from test_pr_sheet import WORDS, SCHEMA, load
from test_sheet_schema import check_sheet_problems

TITLE = "The old balance is rounded twice"
COMMIT = "1a2b3c4"
CANON_ID = "2026-10-22-abcdefgh-1"
ACCEPTING = "## What we're accepting\n\n"
FIXED_LINE = f"- f-2 {TITLE} — fixed-above #11 {COMMIT}: the layer above removes it.\n"
NONE_BODY = ACCEPTING + "None\n"


def finding(ident="f-2", outcome="left-for-owner", title=TITLE):
    return {"id": ident, "outcome": outcome, "title": title, "reason": "Only the owner can say.",
            "consequence": "A balance may be off by a cent.", "findingKey": "balance/" + ident}


def record(pr, findings):
    return {**load("record-stack-1.json"), "pr": pr, "findings": findings}


def stack_input(**extra):
    return {"schema": "pr-sheet-input/1", "kind": "stack", "number": 9, "title": "Balances", "summary": "Balances are rounded once.",
            "prs": [{"number": 10, "title": "Round the balance"}, {"number": 11, "title": "Show the balance"}], **extra}


def pr_input(**extra):
    return {"schema": "pr-sheet-input/1", "kind": "pr", "number": 10, "title": "Round the balance", "summary": "Balances are rounded once.", **extra}


def stack_records(low=None, high=None):
    return [record(10, [finding()] if low is None else low), record(11, [] if high is None else high)]


def make(records, advisor, bodies):
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, bodies=copy.deepcopy(bodies))


def refused(records, advisor, bodies):
    with pytest.raises(pr_sheet.Refusal) as caught:
        make(records, advisor, bodies)
    return caught.value.problems


def fixed_bodies(layer=11):
    return {10: ACCEPTING + FIXED_LINE.replace("#11", f"#{layer}"), 11: NONE_BODY}


def test_s1_a_finding_fixed_by_the_layer_above_is_caught_as_fixed_above_and_needs_no_entry_or_accounting():
    # Bites on: the stack sheet refusing a fixed-above finding for a missing leftovers entry or an unaccounted bullet, or showing it as a card.
    # Axis: I-SHEET: a valid fixed-above disposition lands in caught, takes no card, no decided-for-you entry and no accounting.
    sheet = make(stack_records(), stack_input(), fixed_bodies())
    assert f"#10: {TITLE} (fixed above in #11 at {COMMIT})" in sheet["prSheet"]["whatChanged"]["caught"]
    assert sheet["cards"] == [] and "decidedForYou" not in sheet["prSheet"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_s1_a_long_commit_is_shown_short():
    # Axis: the commit is shown as its first seven characters.
    long = "1a2b3c4d5e6f"
    bodies = {10: ACCEPTING + FIXED_LINE.replace(COMMIT, long), 11: NONE_BODY}
    assert f"(fixed above in #11 at {long[:7]})" in make(stack_records(), stack_input(), bodies)["prSheet"]["whatChanged"]["caught"][0]


def test_s2_a_pr_sheet_covers_no_higher_layer_and_refuses_naming_the_finding_and_the_layer():
    # Bites on: a fixed-above disposition accepted on a pr sheet.
    # Axis: E4: a pr sheet refuses it, the finding is not dropped.
    problems = refused([record(10, [finding()])], pr_input(), {10: ACCEPTING + FIXED_LINE})
    assert any("f-2" in p and "#11" in p and "pr sheet covers no higher layer" in p for p in problems), problems


@pytest.mark.parametrize("layer", [99, 10])
def test_s3_a_layer_that_is_not_in_the_stack_or_is_the_findings_own_pr_refuses(layer):
    # Bites on: the higher-layer check (an unknown PR, or the finding's own PR, taken as the fixing layer).
    # Axis: E4: the layer must be a PR of this stack sheet above the finding's own.
    problems = refused(stack_records(), stack_input(), fixed_bodies(layer))
    assert any("f-2" in p and f"fixed-above #{layer}" in p and "not a higher PR of this stack sheet" in p for p in problems), problems


def test_s3_a_layer_below_the_findings_pr_refuses():
    # Bites on: the index comparison taking a lower layer as higher.
    # Axis: E4: a finding on PR 11 naming PR 10 is refused.
    bodies = {10: NONE_BODY, 11: ACCEPTING + FIXED_LINE.replace("#11", "#10")}
    problems = refused(stack_records(low=[], high=[finding()]), stack_input(), bodies)
    assert any("PR #11" in p and "fixed-above #10" in p and "not a higher PR of this stack sheet" in p for p in problems), problems


def test_s4_a_leftovers_entry_for_a_finding_fixed_above_refuses():
    # Bites on: the refusal of a leftovers entry on a finding the body marks fixed above.
    # Axis: a fixed-above finding takes no leftovers entry.
    entry = {"why": "Only you can say.", "context": "It happened.", "options": "none"}
    problems = refused(stack_records(), stack_input(leftovers={"10:f-2": entry}), fixed_bodies())
    assert any("fixed above in #11" in p and "no leftovers or craftDeterminations entry" in p for p in problems), problems


def test_s4_a_craft_determination_for_a_finding_fixed_above_refuses():
    # Bites on: the refusal of a craftDeterminations entry on a finding the body marks fixed above.
    problems = refused(stack_records(), stack_input(craftDeterminations={"10:f-2": {"ground": "a fix in another layer", "reason": "Fixed above."}}),
                       fixed_bodies())
    assert any("fixed above in #11" in p and "no leftovers or craftDeterminations entry" in p for p in problems), problems


def test_s4_an_accounting_entry_for_the_fixed_above_bullet_refuses():
    # Bites on: an accounting entry accepted for a bullet that is accounted by itself.
    bullet = pr_sheet.listed_bullets(10, fixed_bodies()[10])[0][0]
    problems = refused(stack_records(), stack_input(accounting={bullet: {"item": "x"}}), fixed_bodies())
    assert any(f'accounting "{bullet}" is a fixed-above disposition, accounted by itself; remove it' == p for p in problems), problems


def test_s5_when_the_only_listed_bullet_is_fixed_above_nothing_is_listed():
    # Bites on: a fixed-above bullet counted as a listed acceptance.
    # Axis: the listed state is read over the bullets the build does not account by themselves.
    prsheet = make(stack_records(), stack_input(), fixed_bodies())["prSheet"]
    assert prsheet["nothingListed"] is True and "canonAccounted" not in prsheet


def test_s5_a_fixed_above_bullet_beside_a_canon_accounted_one_leaves_canon_accounted():
    # Bites on: a fixed-above bullet breaking canonAccounted (it has no accounting entry to be a Canon ruling).
    body = ACCEPTING + FIXED_LINE + "- Rounding happens at checkout, as decided.\n"
    bullet = pr_sheet.listed_bullets(10, body)[1][0]
    advisor = stack_input(summary=f"Balances are rounded once. Ruled in {CANON_ID}.", accounting={bullet: {"canon": CANON_ID}})
    prsheet = make(stack_records(), advisor, {10: body, 11: NONE_BODY})["prSheet"]
    assert prsheet["canonAccounted"] == [CANON_ID] and "nothingListed" not in prsheet


def test_s5_another_bullet_still_needs_its_accounting():
    # Axis: only the fixed-above bullet is accounted by itself; a second bullet still needs an entry.
    body = ACCEPTING + FIXED_LINE + "- Rounding happens at checkout, as decided.\n"
    problems = refused(stack_records(), stack_input(), {10: body, 11: NONE_BODY})
    assert len(problems) == 1 and "is not accounted for" in problems[0], problems


def test_s6_a_body_with_no_disposition_still_needs_its_leftovers_entry():
    # Bites on: the fixed-above reading changing a build whose body carries no disposition.
    problems = refused(stack_records(), stack_input(), {10: ACCEPTING + f"- f-2 {TITLE}\n", 11: NONE_BODY})
    assert any("has no leftovers entry" in p for p in problems), problems


def test_s6_without_bodies_a_fixed_above_reading_is_never_made():
    # Axis: E1: a build given no bodies makes no fixed-above reading, so the leftovers entry is still required.
    with pytest.raises(pr_sheet.Refusal) as caught:
        pr_sheet.build(stack_records(), stack_input(), WORDS)
    assert any("has no leftovers entry" in p for p in caught.value.problems)


def test_a_record_the_rule_cannot_read_is_a_problem_naming_the_pr_never_a_pass():
    # Axis: E2: a leftForOwner list that is not a list is unreadable.
    records = stack_records()
    records[0]["leftForOwner"] = "f-2"
    problems = refused(records, stack_input(), fixed_bodies())
    assert any("PR #10's review record cannot be read for its fixed-above dispositions" in p for p in problems), problems


def test_a_claim_naming_no_left_for_owner_finding_is_ignored():
    # Axis: E3: a disposition for an id the record's left-for-owner findings do not hold changes nothing; the leftover is still checked.
    body = ACCEPTING + "- f-9 Some other finding — fixed-above #11 1a2b3c4\n"
    problems = refused(stack_records(), stack_input(), {10: body, 11: NONE_BODY})
    # The complete list: the f-2 leftover is still checked, and the f-9 line is an ordinary acceptance that needs accounting. No
    # problem names fixed-above, #11 as a layer, or f-9 as a finding: the claim is ignored without a word.
    assert problems == [
        "left-for-owner finding 'The old balance is rounded twice' on PR #10 has no leftovers entry (key '10:balance/f-2'); "
        "give it why, context and options, or a craft determination",
        'PR #10\'s acceptance 10:210485cfa6 ("f-9 Some other finding — fixed-above #11 1a2b3c4") is not accounted for: '
        'give accounting "10:210485cfa6" one of item, fold with line, leftover, or canon',
    ], problems


def test_the_waiting_line_of_a_fixed_above_finding_is_neither_counted_nor_incomplete():
    # Axis: the history skips the leftover line of a finding shown as fixed above.
    records = stack_records()
    records[0]["whatIsMissing"] = ["finding f-2 waits for the owner's decision"]
    history = make(records, stack_input(), fixed_bodies())["prSheet"]["history"]
    assert not any(h.startswith("#10") and ("left for you below" in h or "incomplete" in h) for h in history), history


def test_e5_a_carried_sheet_cannot_move_an_earlier_decided_for_you_entry_to_fixed_above():
    # Bites on: a carried sheet that lets a finding the earlier sheet showed as decided for you move into caught as fixed
    # above, keeping the earlier sheet's answers and Merge over a disposition the owner never saw.
    # Axis: E5: on a carry, a fixed-above finding that was a decided-for-you entry on the earlier sheet is a named refusal.
    from test_pr_sheet import carry_input, determination, sheet_bytes
    plain = {10: NONE_BODY, 11: NONE_BODY}
    earlier = make(stack_records(), stack_input(craftDeterminations={"10:f-2": determination()}), plain)
    assert [e["finding"] for e in earlier["prSheet"]["decidedForYou"]] == ["10:balance/f-2"]
    advisor = carry_input(stack_input(), {"10": "a" * 40, "11": "b" * 40})
    with pytest.raises(pr_sheet.Refusal) as caught:
        pr_sheet.build(copy.deepcopy(stack_records()), advisor, WORDS, previous=sheet_bytes(earlier), bodies=fixed_bodies())
    assert any("was a decided-for-you entry on the earlier sheet" in p and "#11" in p
               and "a carried sheet cannot move a decided-for-you entry; republish unsigned" in p
               for p in caught.value.problems), caught.value.problems


def test_a_fixed_above_bullet_with_a_multiline_comment_keeps_its_automatic_accounting():
    # Bites on: matching the assigned acceptance to its bullet by exact text, which a multiline comment inside the bullet
    # breaks (cutting the comment before or after the lines are joined leaves one space or two).
    # Axis: the bullet the whole-body assignment gave a valid claim is accounted by itself whatever comment it carries.
    bodies = {10: ACCEPTING + f"- f-2 {TITLE} <!-- a note\n  that wraps --> — fixed-above #11 {COMMIT}: the layer above removes it.\n",
              11: NONE_BODY}
    sheet = make(stack_records(), stack_input(), bodies)
    assert f"#10: {TITLE} (fixed above in #11 at {COMMIT})" in sheet["prSheet"]["whatChanged"]["caught"]
    assert sheet["cards"] == [] and sheet["prSheet"].get("nothingListed") is True
