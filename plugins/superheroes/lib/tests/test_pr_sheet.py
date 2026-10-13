"""Guards for the PR sheet builder: its facts, where each finding lands, card ids, refusals, the CLI and the samples."""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import pr_sheet
import review_record
from provenance_patterns import PROVENANCE_PATTERNS
from test_sheet_schema import check_sheet_problems

LIB = Path(__file__).resolve().parents[1]
THEME = LIB.parent / "theme"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
SCHEMA = json.loads((THEME / "sheet.schema.json").read_text(encoding="utf-8"))
ALL_WORDS = json.loads((THEME / "sheet-words.json").read_text(encoding="utf-8"))
WORDS = ALL_WORDS["pr"]

BIG = (["record-big.json"], "input-big.json")
SMALL = (["record-small.json"], "input-small.json")
STACK = (["record-stack-1.json", "record-stack-2.json", "record-stack-3.json"], "input-stack.json")
CLOSES = (["record-big.json"], "input-closes.json")
WALK = (["record-big.json"], "input-walk.json")
TWIN = (["record-twin-a.json", "record-twin-b.json"], "input-twin.json")


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def bundle(case):
    records, advisor = case
    return [load(r) for r in records], load(advisor)


def build(records, advisor):
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS)


def built(case):
    return build(*bundle(case))


def problems_of(records, advisor):
    with pytest.raises(pr_sheet.Refusal) as caught:
        build(records, advisor)
    return caught.value.problems


def leftover_cards(sheet):
    return [c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]


def cli(records, advisor, out):
    args = [sys.executable, "-B", str(LIB / "pr_sheet.py"), "build", "--input", str(advisor), "--out", str(out)]
    for r in records:
        args += ["--record", str(r)]
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("case", [BIG, SMALL, STACK, CLOSES], ids=["big", "small", "stack", "closes"])
def test_outputs_pass_the_schema_and_the_page_check(case):
    # Axis: every output is accepted by the shipped schema and by the shipped page's checkSheet.
    sheet = built(case)
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == []
    assert check_sheet_problems(sheet) == []


def test_every_fact_matches_the_record():
    # Axis: each fact in whatChanged is copied from the record.
    rec, sheet = load("record-big.json"), built(BIG)["prSheet"]
    changed = sheet["whatChanged"]
    assert changed["rounds"] == rec["rounds"]["count"] and changed["stoppedAtCap"] is rec["rounds"]["stoppedAtCap"]
    assert changed["ci"] == {"state": rec["ci"]["state"], "commit": rec["ci"]["sha"]}
    assert (changed["lane"], changed["laneReason"]) == (rec["lane"]["value"], rec["lane"]["reason"])
    assert sheet["commit"] == rec["finalCommit"]["sha"] and sheet["number"] == 214
    assert changed["reviewers"] == [
        {k: v[k] for k in ("name", "family", "ran", "notIndependent") if k in v}
        for v in rec["reviewers"] if v["ran"] != "not-run"]
    assert [v["name"] for v in changed["reviewers"]] == ["code-reviewer", "test-reviewer", "design-reviewer"]
    assert changed["caught"] == [f["title"] for f in rec["findings"] if f["outcome"] == "fixed"]
    assert changed["summary"] == load("input-big.json")["summary"]


def test_each_finding_lands_in_its_outcomes_part():
    # Axis: a finding appears in exactly the one place its outcome names.
    rec, sheet = load("record-big.json"), built(BIG)
    places = {
        "fixed": sheet["prSheet"]["whatChanged"]["caught"],
        "craft": [e["title"] for e in sheet["prSheet"]["craft"]],
        "ruling": [e["title"] for e in sheet["prSheet"]["alreadyDecided"]],
        "shown-wrong": sheet["prSheet"]["history"],
        "left-for-owner": [c["question"] for c in leftover_cards(sheet)],
    }
    for f in rec["findings"]:
        assert [part for part, texts in places.items() if any(f["title"] in t for t in texts)] == [f["outcome"]], f["title"]
    assert len(places["left-for-owner"]) == 2 and len(places["craft"]) == 3 and len(places["ruling"]) == 1
    craft = {e["title"]: e["detail"] for e in sheet["prSheet"]["craft"]}
    assert craft["Log lines name the order, not the card"] == "Card details never reach the logs."
    assert sheet["prSheet"]["history"] == [
        "3 rounds ran.",
        "Shown wrong: The retry loop never stops. It stops after three tries; the reviewer misread the counter.",
        "security-reviewer did not run. No owner's word or standing ruling lets the PR go ahead without it.",
        "design-reviewer is from a maker's model family, so its review was not independent.",
    ]


def test_a_go_ahead_is_shown_in_the_history():
    # Axis: a missing review's go-ahead, from a standing ruling or the owner's words, is named in its history line.
    records, advisor = bundle(BIG)
    records[0]["missingReviews"][0]["goAhead"] = {"kind": "standing-ruling", "canonId": "R12"}
    assert "security-reviewer did not run. Go-ahead to merge without it: R12." in build(records, advisor)["prSheet"]["history"]
    records[0]["missingReviews"][0]["goAhead"] = {"kind": "owner-words", "words": "Skip it", "where": "the chat"}
    assert 'Go-ahead to merge without it: "Skip it" (the chat).' in build(records, advisor)["prSheet"]["history"][2]


def test_an_empty_record_gives_an_empty_sheet():
    # Axis: a record with no findings gives no cards and empty parts, and the words say nothing is left to accept.
    sheet = built(SMALL)
    assert sheet["cards"] == []
    part = sheet["prSheet"]
    assert part["craft"] == [] and part["alreadyDecided"] == [] and "walk" not in part
    assert part["whatChanged"]["caught"] == [] and part["history"] == ["1 rounds ran."]
    assert WORDS["nothingToAccept"] == "Nothing. The review left nothing for you."


def test_null_lane_and_ci_commit_are_copied_and_a_previous_commit_is_optional():
    # Axis: a null lane and a null CI commit are copied as null; previousCommit is left out when null and copied when set.
    records, advisor = bundle(SMALL)
    records[0]["lane"] = {"value": None, "reason": None}
    records[0]["ci"] = {"state": "none", "sha": None}
    sheet = build(records, advisor)
    assert sheet["prSheet"]["whatChanged"]["lane"] is None and sheet["prSheet"]["whatChanged"]["laneReason"] is None
    assert sheet["prSheet"]["whatChanged"]["ci"] == {"state": "none", "commit": None}
    assert "previousCommit" not in sheet["prSheet"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []
    advisor["previousCommit"] = "abcdef1"
    assert build(records, advisor)["prSheet"]["previousCommit"] == "abcdef1"


def test_a_finding_title_falls_back_to_summary_then_id():
    # Axis: a finding without a title is shown by its summary, then by its id.
    records, advisor = bundle(BIG)
    records[0]["findings"][5].pop("title")
    records[0]["findings"][5]["summary"] = "Customers hear nothing about a retry"
    records[0]["findings"][6].pop("title")
    assert [c["question"] for c in leftover_cards(build(records, advisor))] == ["Customers hear nothing about a retry", "F7"]


def test_the_closure_receipt_is_one_card_and_only_when_asked_for():
    # Axis: closesSpec gives exactly one closure-receipt card with the receipt quoted; no closesSpec gives none.
    cards = [c for c in built(CLOSES)["cards"] if c["callKind"] == "Closure receipt"]
    assert len(cards) == 1 and cards[0]["options"] == [] and "recommendation" not in cards[0]
    assert cards[0]["question"] == "Close the spec retry-failed-payments with this merge"
    assert cards[0]["context"][1] == {"title": "The closure receipt", "blocks": [{"quote": load("input-closes.json")["closesSpec"]["receipt"]}]}
    assert [c for c in built(BIG)["cards"] if c["callKind"] == "Closure receipt"] == []


def test_options_default_none_and_custom():
    # Axis: a default leftover gets the words' options with only fix-before-merge sending back; none gives no options.
    cards = {c["question"]: c for c in leftover_cards(built(BIG))}
    default = cards["A payment that fails three times ends with no email"]
    assert default["options"] == WORDS["leftoverOptions"]
    assert [o["id"] for o in default["options"] if o["sendsBack"]] == ["fix-before-merge"]
    assert cards["Customers are not told a retry happened"]["options"] == []


def test_an_option_without_sends_back_is_refused():
    # Axis: an advisor option that does not say whether it sends the PR back is refused.
    records, advisor = bundle(BIG)
    del advisor["items"][0]["options"][0]["sendsBack"]
    assert any("sendsBack" in p for p in problems_of(records, advisor))


def test_card_ids_are_stable_for_an_unchanged_item_and_differ_for_a_changed_one():
    # Axis: a new commit keeps every card id; a changed consequence changes that card's id only.
    records, advisor = bundle(BIG)
    before = [c["id"] for c in build(records, advisor)["cards"]]
    records[0]["finalCommit"]["sha"] = records[0]["ci"]["sha"] = "ffffffffffffffffffffffffffffffffffffffff"
    advisor["previousCommit"] = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    assert [c["id"] for c in build(records, advisor)["cards"]] == before
    records[0]["findings"][5]["consequence"] = "A customer sees a second attempt and is told nothing."
    after = [c["id"] for c in build(records, advisor)["cards"]]
    assert [a == b for a, b in zip(before, after)] == [False, True, True]
    assert len(set(before)) == len(before)


def test_twin_stack_cards_get_different_ids():
    # Axis: the same finding on two PRs of a stack gives two cards with different ids.
    cards = built(TWIN)["cards"]
    assert len(cards) == 2 and cards[0]["id"] != cards[1]["id"]
    assert [c["callKind"] for c in cards] == ["Leftover · #241", "Leftover · #242"]


def test_card_id_hashes_the_pr_number():
    # Axis: the PR number is part of a card id.
    card = {"callKind": "Leftover", "question": "Q"}
    assert pr_sheet.card_id("f-", 5, "k", card) != pr_sheet.card_id("f-", 6, "k", card)
    assert re.fullmatch(r"f-[0-9a-f]{12}", pr_sheet.card_id("f-", 5, "k", card))


def test_a_stack_gets_one_sheet_from_all_its_records():
    # Axis: a stack sheet lists every PR with its own commit, takes the top PR's commit, and has one list of cards.
    sheet = built(STACK)
    part = sheet["prSheet"]
    assert sheet["kind"] == "stack" and part["number"] == 4
    assert part["prs"] == [{"number": n, "title": t, "commit": load(f"record-stack-{n - 4}.json")["finalCommit"]["sha"]}
                           for n, t in [(5, "Add the gift-card table"), (6, "Redeem a gift card at checkout"),
                                        (7, "Show the gift-card balance")]]
    assert part["commit"] == load("record-stack-3.json")["finalCommit"]["sha"]
    assert all(stop["pr"] in [p["number"] for p in part["prs"]] for stop in part["walk"]["stops"])
    assert [c["callKind"] for c in sheet["cards"]] == ["Leftover · #6"]
    assert part["whatChanged"]["rounds"] == 7 and part["whatChanged"]["stoppedAtCap"] is True
    assert part["whatChanged"]["caught"] == ["#5: A gift card could be created with a negative balance"]
    assert [v["name"] for v in part["whatChanged"]["reviewers"]] == ["code-reviewer", "design-reviewer"]
    assert [e["pr"] for e in part["craft"] + part["alreadyDecided"]] == [7, 7]
    assert "#5: 2 rounds ran." in part["history"] and "#6: 4 rounds ran." in part["history"]
    assert "#6: The loop stopped at its round cap." in part["history"]
    assert '#6: security-reviewer did not run. Go-ahead to merge without it: "Merge without the security read" (the chat on 2026-03-02).' in part["history"]


def test_a_lower_pr_check_result_is_kept_in_the_stack_history():
    # Axis: a red check on a lower PR of a stack shows in the history though the top PR is green.
    records, advisor = bundle(STACK)
    records[0]["ci"]["state"] = "red"
    history = build(records, advisor)["prSheet"]["history"]
    assert any(line.startswith("#5: Checks were red") for line in history)


def test_incomplete_review_evidence_is_kept_in_the_history():
    # Axis: a record's own warnings and a reviewer's earlier-commit coverage are carried into the history.
    records, advisor = bundle(BIG)
    records[0].update(status="not-reviewed", whatIsMissing=["no planned reviewer's run covers the final commit bbbbbbb"])
    records[0]["reviewers"][0].update(coversFinalCommit=False, commit="aaaaaaa")
    history = build(records, advisor)["prSheet"]["history"]
    assert "The review record is incomplete: no planned reviewer's run covers the final commit bbbbbbb." in history
    assert any("reviewed an earlier commit (aaaaaaa)" in line for line in history)


def test_leftover_overrides_are_keyed_by_finding_key_and_an_ambiguous_id_is_refused():
    # Axis: two left-for-owner findings sharing a reviewer id take separate overrides by findingKey; the shared id is refused.
    records, advisor = bundle(BIG)
    left = [f for f in records[0]["findings"] if f["outcome"] == "left-for-owner"]
    left[1]["id"] = left[0]["id"]
    advisor["leftovers"] = {left[0]["findingKey"]: {"options": "none", "recommendation": {"text": "A", "reason": "a"}}}
    cards = [c for c in build(records, advisor)["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]
    assert [c.get("recommendation", {}).get("text") for c in cards] == ["A", None]
    advisor["leftovers"] = {left[0]["id"]: {"options": "none"}}
    assert any("names 2 left-for-owner findings" in p for p in problems_of(records, advisor))


def test_a_stack_is_built_in_prs_order_whatever_the_record_order():
    # Axis: records given out of order still give the bottom PR first and the top PR's commit.
    records, advisor = bundle(STACK)
    assert build(records[::-1], advisor) == build(records, advisor)


REFUSALS = [
    pytest.param(BIG, lambda r, a: r[0]["findings"][0].update(outcome=None), "outcome None", id="null-outcome"),
    pytest.param(BIG, lambda r, a: r[0]["findings"][5].update(consequence=""), "has no consequence", id="no-consequence"),
    pytest.param(BIG, lambda r, a: a["leftovers"].update({"F99": {}}), "names no left-for-owner finding", id="unknown-leftovers-key"),
    pytest.param(STACK, lambda r, a: r.pop(), "the records are for PRs", id="stack-mismatch"),
    pytest.param(BIG, lambda r, a: a.update(number=215), "not PR #215", id="pr-number-differs"),
    pytest.param(STACK, lambda r, a: a["walk"]["stops"][0].update(pr=999), "which is not in this sheet", id="walk-stop-not-in-stack"),
    pytest.param(BIG, lambda r, a: a["items"][0]["recommendation"].update(optionId="nope"), "optionId 'nope' is not one of its options", id="option-id-unknown"),
    pytest.param(BIG, lambda r, a: a["items"][0].update(options="none"), "is not one of its options", id="option-id-on-none"),
    pytest.param(BIG, lambda r, a: a.update(extra=1), "unknown key extra", id="unknown-top-level-key"),
    pytest.param(BIG, lambda r, a: a.update(schema="pr-sheet-input/2"), "schema must be pr-sheet-input/1", id="wrong-input-schema"),
    pytest.param(BIG, lambda r, a: r[0].update(ok=False), "failed read", id="record-wrapper-not-ok"),
    pytest.param(BIG, lambda r, a: r[0]["finalCommit"].update(sha=None), "finalCommit.sha is null", id="null-final-commit"),
    pytest.param(BIG, lambda r, a: r[0].update(schema="something/1"), "not a review record", id="not-a-record"),
    pytest.param(STACK, lambda r, a: r.append(copy.deepcopy(r[0])), "has more than one record", id="stack-duplicate-record"),
    pytest.param(BIG, lambda r, a: a.update(prs=[{"number": 1, "title": "x"}]), "prs is refused", id="prs-on-a-pr-sheet"),
    pytest.param(STACK, lambda r, a: a.pop("prs"), "a stack needs prs", id="stack-without-prs"),
    pytest.param(BIG, lambda r, a: a["walk"]["stops"].append(copy.deepcopy(a["walk"]["stops"][0])), "repeats the id", id="walk-repeats-an-id"),
]


@pytest.mark.parametrize("case, mutate, expected", REFUSALS)
def test_refuses(case, mutate, expected):
    # Axis: each input the builder cannot trust is refused with a problem line that names the cause.
    records, advisor = bundle(case)
    mutate(records, advisor)
    assert any(expected in p for p in problems_of(records, advisor))


def test_a_refusal_lists_every_problem():
    # Axis: a refusal carries all the problems found, one line each, not just the first.
    records, advisor = bundle(BIG)
    records[0]["findings"][0]["outcome"] = None
    records[0]["finalCommit"]["sha"] = None
    advisor["extra"] = 1
    assert len(problems_of(records, advisor)) == 3


def test_cli_writes_the_sheet_and_prints_the_receipt(tmp_path):
    # Axis: a good run exits 0, prints ok and the card count, and writes the data file.
    out = tmp_path / "sheet.json"
    done = cli([FIXTURES / "record-big.json"], FIXTURES / "input-big.json", out)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"ok": True, "out": str(out), "cards": 3, "pictures": []}
    assert json.loads(out.read_text(encoding="utf-8")) == built(BIG)


def test_a_failed_write_leaves_the_earlier_sheet_intact(tmp_path, monkeypatch):
    # Axis: when the replace fails, an earlier sheet at --out is untouched and no temp file is left behind.
    path = tmp_path / "sheet.json"
    path.write_text("earlier sheet", encoding="utf-8")

    def boom(*_args):
        raise OSError("boom")

    monkeypatch.setattr(pr_sheet.os, "replace", boom)
    with pytest.raises(OSError):
        pr_sheet._write_replacing(str(path), "new")
    assert path.read_text(encoding="utf-8") == "earlier sheet"
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize("what", ["bad-input", "missing-record"])
def test_cli_refuses_and_writes_nothing(tmp_path, what):
    # Axis: a refusal exits 1, prints ok false with its problems, and leaves --out absent.
    out, advisor, record = tmp_path / "sheet.json", tmp_path / "input.json", FIXTURES / "record-big.json"
    advisor.write_text(json.dumps(dict(load("input-big.json"), extra=1)), encoding="utf-8")
    if what == "missing-record":
        record = tmp_path / "no-such-record.json"
        advisor = FIXTURES / "input-big.json"
    done = cli([record], advisor, out)
    result = json.loads(done.stdout)
    assert done.returncode == 1 and result["ok"] is False and result["problems"]
    assert not out.exists()
    if what == "missing-record":
        assert "no-such-record.json" in result["problems"][0]


@pytest.mark.parametrize("sample, case", [("sample-pr-sheet.json", BIG), ("sample-stack-sheet.json", STACK)])
def test_samples_are_the_builders_output(tmp_path, sample, case):
    # Axis: each shipped sample equals the CLI's output for its fixtures byte for byte, and passes both readers.
    out = tmp_path / sample
    done = cli([FIXTURES / r for r in case[0]], FIXTURES / case[1], out)
    assert done.returncode == 0, done.stderr
    shipped = (THEME / sample).read_bytes()
    assert shipped == out.read_bytes()
    sheet = json.loads(shipped)
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


@pytest.mark.parametrize("path", [LIB / "pr_sheet.py", THEME / "sample-pr-sheet.json", THEME / "sample-stack-sheet.json"],
                         ids=lambda p: p.name)
def test_shipped_files_carry_no_provenance(path):
    # Axis: the builder and both samples name no requirement, ruling, issue, handoff or work-item tokens.
    text = path.read_text(encoding="utf-8")
    for pattern in PROVENANCE_PATTERNS:
        assert re.search(pattern, text) is None, f"{path.name} matches {pattern}"


def test_an_unstated_independence_stays_unstated():
    # Axis: a reviewer whose record omits notIndependent is carried without it, never as false.
    rec = load("record-small.json")
    assert all("notIndependent" not in v for v in rec["reviewers"])
    shown = built(SMALL)["prSheet"]["whatChanged"]["reviewers"]
    assert shown and all("notIndependent" not in v for v in shown)


def test_the_schema_holds_no_copy_of_the_ran_vocabulary():
    # Axis: the ran vocabulary has one home (review_record.RAN_STATES); the schema carries no enum of it.
    ran = SCHEMA["$defs"]["prSheet"]["properties"]["whatChanged"]["properties"]["reviewers"]["items"]["properties"]["ran"]
    assert "enum" not in ran and ran["type"] == "string"


def test_the_schema_holds_no_copy_of_the_lane_vocabulary():
    # Axis: the lane vocabulary has one home (review_record.LANES); the schema carries no enum of it.
    lane = SCHEMA["$defs"]["prSheet"]["properties"]["whatChanged"]["properties"]["lane"]
    assert "enum" not in lane
    assert pr_sheet._LANES is review_record.LANES


def test_a_record_lane_outside_the_vocabulary_is_refused_by_the_builder():
    # Axis: with no enum in the schema, the builder is what refuses a lane that review_record.LANES does not name.
    records, advisor = bundle(SMALL)
    records[0]["lane"] = {"value": "medium", "reason": None}
    with pytest.raises(pr_sheet.Refusal):
        build(records, advisor)


WALK_STOP = "walk stop retry-loop needs pr, an integer 1 or more"
NO_IDENTITY = ("record for PR #214: left-for-owner finding 'Customers are not told a retry happened' "
               "has no findingKey or id, so the advisor's input cannot name it")


def without_identity(records, advisor, position=5):
    """The big record with one left-for-owner finding stripped of its findingKey and id, and no override aimed at it."""
    finding = records[0]["findings"][position]
    finding.pop("findingKey")
    finding.pop("id")
    advisor["leftovers"].pop("F6")


@pytest.mark.parametrize("bad", [True, 0, "5", 2.0], ids=["bool", "zero", "string", "float"])
def test_a_walk_stop_pr_must_be_an_integer_one_or_more(bad):
    # Axis: a walk stop's pr is refused by name unless it is an int, not a bool, of 1 or more; true is never PR #1.
    records, advisor = bundle(BIG)
    records[0]["pr"] = advisor["number"] = 1
    advisor["walk"]["stops"][0]["pr"] = bad
    assert WALK_STOP in problems_of(records, advisor)


def test_a_walk_stop_for_pr_one_still_builds():
    # Axis: the integer 1 is a good walk stop pr, so the bool check refuses true and not the number it equals.
    records, advisor = bundle(BIG)
    records[0]["pr"] = advisor["number"] = 1
    for stop in advisor["walk"]["stops"]:
        stop["pr"] = 1
    assert [stop["pr"] for stop in build(records, advisor)["prSheet"]["walk"]["stops"]] == [1, 1]


def test_a_leftover_with_no_identity_is_refused_up_front():
    # Axis: a left-for-owner finding with neither a findingKey nor an id is refused with a message that names it, not a crash while building.
    records, advisor = bundle(BIG)
    without_identity(records, advisor)
    assert problems_of(records, advisor) == [NO_IDENTITY]


def test_a_leftover_with_an_id_only_still_builds():
    # Axis: a left-for-owner finding with an id and no findingKey is named by its id and builds, with the same card as before.
    records, advisor = bundle(BIG)
    before = [c["id"] for c in build(records, advisor)["cards"]]
    records[0]["findings"][6].pop("findingKey")
    sheet = build(records, advisor)
    assert len(leftover_cards(sheet)) == 2
    assert [c["id"] for c in sheet["cards"]][0] == before[0]
    assert leftover_cards(sheet)[1]["recommendation"]["optionId"] == "fix-in-a-follow-up"


def test_a_reviewer_with_no_family_builds_and_shows_null():
    # Axis: a reviewer record whose family is null is carried as null, and the sheet still passes the schema and the page check.
    records, advisor = bundle(BIG)
    records[0]["reviewers"][0]["family"] = None
    sheet = build(records, advisor)
    assert sheet["prSheet"]["whatChanged"]["reviewers"][0]["family"] is None
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


@pytest.mark.parametrize("mutate, expected", [
    pytest.param(lambda r: r.update(reviewers=["code-reviewer"]), "its ci, lane, rounds, reviewers or missing reviews are malformed", id="reviewer-not-an-object"),
    pytest.param(lambda r: r.update(missingReviews=[{"goAhead": None}]), "its ci, lane, rounds, reviewers or missing reviews are malformed", id="missing-review-without-a-name"),
    pytest.param(lambda r: r.update(findings=["not an object"]), "a finding has no title, summary or id", id="finding-not-an-object"),
])
def test_a_malformed_nested_record_is_refused(mutate, expected):
    # Axis: a reviewer, a missing review or a finding of the wrong shape is refused with a problem line, not a crash.
    records, advisor = bundle(BIG)
    mutate(records[0])
    assert any(expected in p for p in problems_of(records, advisor))


def test_one_input_with_several_problems_is_refused_with_all_of_them():
    # Axis: problems from the advisor's input, a walk stop, a finding's identity and a reviewer all come back in one refusal.
    records, advisor = bundle(BIG)
    advisor["extra"] = 1
    advisor["walk"]["stops"][0]["pr"] = True
    without_identity(records, advisor)
    records[0]["reviewers"][1]["family"] = 5
    problems = problems_of(records, advisor)
    assert len(problems) == 4
    assert {WALK_STOP, NO_IDENTITY, "the advisor's input has an unknown key extra",
            "record for PR #214: its ci, lane, rounds, reviewers or missing reviews are malformed"} == set(problems)


def test_a_leftover_with_no_override_gets_the_words_three_options():
    # Axis: a left-for-owner finding the advisor says nothing about gets the words' leftover options, and only fix-before-merge sends back.
    records, advisor = bundle(BIG)
    advisor["leftovers"].pop("F6")
    card = next(c for c in leftover_cards(build(records, advisor)) if c["question"] == "Customers are not told a retry happened")
    assert card["options"] == WORDS["leftoverOptions"] and len(card["options"]) == 3
    assert [o["sendsBack"] for o in card["options"]] == [False, False, True]
    assert "recommendation" not in card


PICTURE_FILES = ["cart-empty.png", "cart-paid.png", "declined-screen.png"]
FIXED_SRC = "pictures/0123456789ab.png"


def src_of(name):
    return "pictures/" + hashlib.sha256((FIXTURES / "elsewhere" / name).read_bytes()).hexdigest()[:pr_sheet.PICTURE_DIGEST] + ".png"


def test_the_full_walk_is_carried_through():
    # Axis: the open box, note, source of pictures, groups, steps, expectations and marks come through, each stop in the schema's key order.
    records, advisor = bundle(WALK)
    sheet = pr_sheet.build(records, advisor, WORDS, place=lambda path: FIXED_SRC)
    walk = sheet["prSheet"]["walk"]
    assert list(walk) == ["open", "note", "picturesFrom", "stops"]
    assert walk["open"] == advisor["walk"]["open"] and walk["note"] == "Walk on your phone."
    assert walk["picturesFrom"] == advisor["walk"]["picturesFrom"]
    p1, p2, p3, p4, f1 = walk["stops"]
    assert [s["id"] for s in walk["stops"]] == ["p1", "p2", "p3", "p4", "f1"]
    assert list(p1) == ["id", "key", "title", "pr", "group", "kind", "steps", "expect", "pictures"]
    assert p1["steps"] == advisor["walk"]["stops"][0]["steps"] and p1["group"] == "On your phone"
    assert p1["pictures"] == [{"src": FIXED_SRC, "alt": "The empty cart", "caption": "Where you start"},
                              {"src": FIXED_SRC, "alt": "The paid order"}]
    assert p2["pictures"] == [] and p3["pictures"] == [] and p3["optional"] is True and p3["steps"] == ["Pay with a second test card"]
    assert p4["notWalked"] == "It needs your own sign-in to the bank's test dashboard." and "optional" not in p4
    assert f1["kind"] == "look" and f1["steps"] == [] and f1["group"] == "Failure screens · look only"
    assert "optional" not in p1 and "notWalked" not in p1
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_a_stack_walks_stops_keep_their_pr():
    # Axis: on a stack each stop is carried with the PR it belongs to, and a stop without steps gets an empty list.
    stops = built(STACK)["prSheet"]["walk"]["stops"]
    assert [(s["id"], s["pr"], s["steps"]) for s in stops] == [("gift-card-table", 5, []), ("checkout-redeem", 6, ["Pay with a gift card"])]


def test_a_sheet_without_a_walk_has_no_walk_key():
    # Axis: an input with no walk gives a sheet with no walk key at all, not an empty one.
    assert "walk" not in built(SMALL)["prSheet"]


def test_without_a_place_every_picture_is_missing():
    # Axis: with no place to copy pictures to, each picture is carried as missing, with no src.
    records, advisor = bundle(WALK)
    stops = pr_sheet.build(records, advisor, WORDS)["prSheet"]["walk"]["stops"]
    pictures = [p for s in stops for p in s["pictures"]]
    assert len(pictures) == 4 and all(p["missing"] is True and "src" not in p for p in pictures)
    assert pictures[0] == {"missing": True, "alt": "The empty cart", "caption": "Where you start"}


def test_a_place_that_cannot_copy_gives_a_missing_picture():
    # Axis: a place that answers None for one picture marks that one missing and leaves the others copied.
    records, advisor = bundle(WALK)
    sheet = pr_sheet.build(records, advisor, WORDS, place=lambda path: None if "paid" in path else FIXED_SRC)
    first = sheet["prSheet"]["walk"]["stops"][0]["pictures"]
    assert first[0]["src"] == FIXED_SRC and first[1] == {"missing": True, "alt": "The paid order"}


def set_walk(key, value):
    return lambda a: a["walk"].__setitem__(key, value)


def set_stop(stop, key, value):
    return lambda a: a["walk"]["stops"][stop].__setitem__(key, value)


def set_picture(key, value, stop=0, picture=0):
    return lambda a: a["walk"]["stops"][stop]["pictures"][picture].__setitem__(key, value)


WALK_REFUSALS = [
    pytest.param(lambda a: a.__setitem__("walk", []), "walk must be an object", id="walk-not-an-object"),
    pytest.param(set_walk("extra", 1), "walk has an unknown key extra", id="walk-unknown-key"),
    pytest.param(lambda a: a["walk"].pop("picturesFrom"), "walk is missing picturesFrom", id="no-pictures-from"),
    pytest.param(set_walk("picturesFrom", " "), "walk picturesFrom must be a non-empty string", id="empty-pictures-from"),
    pytest.param(set_walk("note", ""), "walk note must be a non-empty string", id="empty-note"),
    pytest.param(lambda a: a["walk"]["open"].update(extra=1), "walk open has an unknown key extra", id="open-unknown-key"),
    pytest.param(lambda a: a["walk"]["open"].update(label=""), "walk open label must be a non-empty string", id="open-empty-label"),
    pytest.param(lambda a: a["walk"]["open"].update(detail=""), "walk open detail must be a non-empty string", id="open-empty-detail"),
    pytest.param(lambda a: a["walk"]["open"].update(url="javascript:x"), "walk open url must be an http or https link", id="open-url-not-http"),
    pytest.param(lambda a: a["walk"]["open"].update(url="https://"), "walk open url must be an http or https link", id="open-url-empty-host"),
    pytest.param(set_walk("stops", []), "walk needs at least one stop", id="no-stops"),
    pytest.param(set_walk("stops", "p1"), "walk needs at least one stop", id="stops-not-a-list"),
    pytest.param(set_stop(0, "extra", 1), "walk stops entry 1 has an unknown key extra", id="stop-unknown-key"),
    pytest.param(lambda a: a["walk"]["stops"][0].pop("group"), "walk stops entry 1 is missing group", id="stop-no-group"),
    pytest.param(set_stop(0, "group", ""), "walk stops entry 1 needs an id", id="stop-empty-group"),
    pytest.param(set_stop(0, "expect", ""), "walk stops entry 1 needs an id", id="stop-empty-expect"),
    pytest.param(set_stop(0, "id", "Bad Id"), "walk stops entry 1 needs an id", id="stop-bad-id"),
    pytest.param(set_stop(1, "id", "p1"), "walk stops entry 2 repeats the id p1", id="stop-repeats-an-id"),
    pytest.param(set_stop(0, "pr", 999), "walk stop p1 is for PR #999", id="stop-pr-not-in-sheet"),
    pytest.param(set_stop(0, "kind", "scroll"), 'walk stop p1 needs kind to be "try" or "look"', id="stop-unknown-kind"),
    pytest.param(set_stop(0, "steps", []), "walk stop p1 is a try stop, so it needs at least one step", id="try-without-steps"),
    pytest.param(lambda a: a["walk"]["stops"][0].pop("steps"), "walk stop p1 is a try stop, so it needs at least one step", id="try-with-no-steps-key"),
    pytest.param(set_stop(4, "steps", ["Look"]), "walk stop f1 is a look stop, so it takes no steps", id="look-with-steps"),
    pytest.param(set_stop(0, "steps", ["ok", ""]), "walk stop p1 needs steps to be a list of non-empty strings", id="empty-step"),
    pytest.param(set_stop(0, "steps", "Open it"), "walk stop p1 needs steps to be a list of non-empty strings", id="steps-not-a-list"),
    pytest.param(set_stop(2, "optional", "yes"), "walk stop p3 needs optional to be true or false", id="optional-not-a-boolean"),
    pytest.param(set_stop(3, "notWalked", ""), "walk stop p4 needs notWalked to be a non-empty string", id="empty-not-walked"),
    pytest.param(set_stop(0, "pictures", "a.png"), "walk stop p1 needs pictures to be a list", id="pictures-not-a-list"),
    pytest.param(lambda a: a["walk"]["stops"][0]["pictures"][0].pop("alt"), "walk stop p1 picture 1 is missing alt", id="picture-without-alt"),
    pytest.param(lambda a: a["walk"]["stops"][0]["pictures"][0].pop("path"), "walk stop p1 picture 1 is missing path", id="picture-without-path"),
    pytest.param(set_picture("path", ""), "walk stop p1 picture 1 needs a non-empty path and alt", id="picture-empty-path"),
    pytest.param(set_picture("alt", ""), "walk stop p1 picture 1 needs a non-empty path and alt", id="picture-empty-alt"),
    pytest.param(set_picture("caption", ""), "walk stop p1 picture 1 needs a non-empty path and alt", id="picture-empty-caption"),
    pytest.param(set_picture("src", "pictures/a.png"), "walk stop p1 picture 1 has an unknown key src", id="picture-unknown-key"),
]


@pytest.mark.parametrize("mutate, expected", WALK_REFUSALS)
def test_refuses_a_walk_that_breaks_a_rule(mutate, expected):
    # Axis: each rule of the advisor's walk is refused with one problem line that names the stop or field it is about.
    records, advisor = bundle(WALK)
    mutate(advisor)
    problems = problems_of(records, advisor)
    assert [p for p in problems if expected in p], problems


def test_a_stack_walk_stop_for_a_pr_outside_the_stack_is_refused():
    # Axis: on a stack the stop's PR must be one of the stack's PRs.
    records, advisor = bundle(STACK)
    advisor["walk"]["stops"][1]["pr"] = 4
    assert any("walk stop checkout-redeem is for PR #4" in p for p in problems_of(records, advisor))


def run_walk(tmp_path, advisor=None):
    """The CLI over the walk fixture and the big record, writing into tmp_path/out; an altered input is written
    into tmp_path/in beside a copy of the fixture's pictures, so its relative paths still resolve."""
    source = FIXTURES / "input-walk.json"
    if advisor is not None:
        shutil.copytree(FIXTURES / "elsewhere", tmp_path / "in" / "elsewhere")
        source = tmp_path / "in" / "input.json"
        source.write_text(json.dumps(advisor), encoding="utf-8")
    (tmp_path / "out").mkdir(exist_ok=True)
    return cli([FIXTURES / "record-big.json"], source, tmp_path / "out" / "sheet.json")


def picture_names(folder):
    return sorted(p.name for p in (folder / "pictures").iterdir()) if (folder / "pictures").is_dir() else []


def test_the_cli_copies_each_picture_beside_the_data_file(tmp_path):
    # Axis: each copyable picture is written to pictures/<hash>.png byte for byte, listed in the result, and the sheet names no path or link for it.
    done = run_walk(tmp_path)
    out = tmp_path / "out"
    assert done.returncode == 0, done.stderr
    expected = sorted(src_of(n) for n in PICTURE_FILES)
    assert json.loads(done.stdout)["pictures"] == expected
    for name in PICTURE_FILES:
        assert (out / src_of(name)).read_bytes() == (FIXTURES / "elsewhere" / name).read_bytes()
    assert picture_names(out) == sorted(e.split("/")[1] for e in expected)
    text = (out / "sheet.json").read_text(encoding="utf-8")
    sheet = json.loads(text)
    shown = json.dumps(sheet["prSheet"]["walk"]["stops"])
    assert "http" not in shown and "://" not in shown and "elsewhere" not in text
    assert text.count("://") == 1 and sheet["prSheet"]["walk"]["open"]["url"] == "https://shop.example.test"
    assert [p["src"] for s in sheet["prSheet"]["walk"]["stops"] for p in s["pictures"] if "src" in p] == [
        src_of("cart-empty.png"), src_of("cart-paid.png"), src_of("declined-screen.png")]


def test_the_picture_that_cannot_be_found_is_missing_with_no_src(tmp_path):
    # Axis: a picture whose file does not exist is carried as missing with its alt and no src, and the sheet still builds.
    done = run_walk(tmp_path)
    assert done.returncode == 0, done.stderr
    look = json.loads((tmp_path / "out" / "sheet.json").read_text(encoding="utf-8"))["prSheet"]["walk"]["stops"][4]
    assert look["pictures"][1] == {"missing": True, "alt": "The gave-up screen on a small phone"}


def test_a_link_is_never_a_picture(tmp_path):
    # Axis: a picture path with a URL scheme, a file: link included, becomes a missing picture; nothing is fetched or copied.
    real = (FIXTURES / "elsewhere" / "cart-empty.png").resolve()
    advisor = load("input-walk.json")
    paths = ["https://example.com/a.png", "HTTP://example.com/a.png", real.as_uri(), "file:" + str(real), "data:image/png;base64,AAAA"]
    advisor["walk"]["stops"] = [dict(advisor["walk"]["stops"][1], pictures=[{"path": p, "alt": "A link"} for p in paths])]
    # A real picture sits in the input's folder at the path each link would map to, so only the scheme guard keeps it out.
    for path in paths:
        planted = Path(tmp_path / "in", path)
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_bytes(real.read_bytes())
    done = run_walk(tmp_path, advisor)
    assert done.returncode == 0, done.stderr
    sheet = json.loads((tmp_path / "out" / "sheet.json").read_text(encoding="utf-8"))
    assert sheet["prSheet"]["walk"]["stops"][0]["pictures"] == [{"missing": True, "alt": "A link"}] * len(paths)
    assert json.loads(done.stdout)["pictures"] == [] and not (tmp_path / "out" / "pictures").exists()


def test_a_picture_file_that_cannot_be_copied_is_missing(tmp_path, monkeypatch):
    # Axis: a directory, an empty file, a wrong suffix, a dangling link and an unreadable file are each missing; a good file beside them is copied.
    (tmp_path / "folder.png").mkdir()
    (tmp_path / "empty.png").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"not a picture")
    (tmp_path / "dangling.png").symlink_to(tmp_path / "gone.png")
    (tmp_path / "locked.png").write_bytes(b"locked")
    good = tmp_path / "good.PNG"
    good.write_bytes((FIXTURES / "elsewhere" / "cart-empty.png").read_bytes())
    staged = {}
    place = pr_sheet._stager(tmp_path, staged)
    real = Path.read_bytes

    def read_bytes(self):
        if self.name == "locked.png":
            raise PermissionError("locked")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    names = ["folder.png", "empty.png", "notes.txt", "dangling.png", "locked.png", "nothing", "", "gone.png", "C:\\x.png"]
    assert [place(n) for n in names] == [None] * len(names)
    assert staged == {}
    assert place("good.PNG") == src_of("cart-empty.png") and place(str(good)) == src_of("cart-empty.png")
    assert list(staged) == [src_of("cart-empty.png")]


def test_two_stops_naming_the_same_file_share_one_copy(tmp_path):
    # Axis: the same picture used twice, under one path or two, is copied once and both pictures carry the same src.
    advisor = load("input-walk.json")
    pictures = [{"path": "elsewhere/cart-empty.png", "alt": "One"}, {"path": "./elsewhere/../elsewhere/cart-empty.png", "alt": "Two"}]
    advisor["walk"]["stops"] = [dict(advisor["walk"]["stops"][1], pictures=pictures)]
    done = run_walk(tmp_path, advisor)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["pictures"] == [src_of("cart-empty.png")] and len(picture_names(tmp_path / "out")) == 1


def test_an_absolute_path_is_copied_too(tmp_path):
    # Axis: a picture path may be absolute as well as relative to the input's folder.
    advisor = load("input-walk.json")
    path = str((FIXTURES / "elsewhere" / "cart-paid.png").resolve())
    advisor["walk"]["stops"] = [dict(advisor["walk"]["stops"][1], pictures=[{"path": path, "alt": "Paid"}])]
    done = run_walk(tmp_path, advisor)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["pictures"] == [src_of("cart-paid.png")]


def test_a_refused_input_writes_nothing_not_even_pictures(tmp_path):
    # Axis: an input with pictures that is refused leaves no data file, no pictures folder and no temp file.
    advisor = load("input-walk.json")
    advisor["extra"] = 1
    done = run_walk(tmp_path, advisor)
    assert done.returncode == 1 and json.loads(done.stdout)["ok"] is False
    assert list((tmp_path / "out").iterdir()) == []


def test_a_rerun_over_an_existing_folder_leaves_the_pictures_untouched(tmp_path):
    # Axis: a picture file already at its content-addressed name is not rewritten, and a second run succeeds.
    first = run_walk(tmp_path)
    assert first.returncode == 0, first.stderr
    path = tmp_path / "out" / src_of("cart-paid.png")
    path.write_bytes(b"left alone")
    second = run_walk(tmp_path)
    assert second.returncode == 0, second.stderr
    assert path.read_bytes() == b"left alone"
    assert json.loads(second.stdout)["pictures"] == json.loads(first.stdout)["pictures"]


@pytest.mark.parametrize("existing", [False, True], ids=["fresh-folder", "one-picture-already-there"])
def test_a_failed_write_removes_the_pictures_this_run_created(tmp_path, monkeypatch, capsys, existing):
    # Axis: when the data file cannot be written after the pictures were, the run exits 1 and removes every picture it created, keeping one that was already there.
    out = tmp_path / "sheet.json"
    kept = tmp_path / src_of("cart-paid.png")
    if existing:
        kept.parent.mkdir()
        kept.write_bytes((FIXTURES / "elsewhere" / "cart-paid.png").read_bytes())
    real = os.replace

    def replace(src, dst):
        if str(dst) == str(out):
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(pr_sheet.os, "replace", replace)
    code = pr_sheet.main(["build", "--record", str(FIXTURES / "record-big.json"), "--input", str(FIXTURES / "input-walk.json"), "--out", str(out)])
    result = json.loads(capsys.readouterr().out)
    assert code == 1 and result == {"ok": False, "problems": ["disk full"]}
    assert not out.exists() and list(tmp_path.glob("**/*.tmp")) == []
    assert picture_names(tmp_path) == ([kept.name] if existing else [])
    assert (tmp_path / "pictures").exists() is existing


def _keys_of(advisor):
    return {s["id"]: s["key"] for s in build(bundle(WALK)[0], advisor)["prSheet"]["walk"]["stops"]}


def test_a_walk_stop_key_is_stable_under_reordered_open_fields_and_matches_the_schema_pattern():
    # Axis: the key is a pure function of what the stop shows, whatever order the advisor wrote the open fields in.
    advisor = bundle(WALK)[1]
    before = _keys_of(advisor)
    advisor["walk"]["open"] = dict(reversed(list(advisor["walk"]["open"].items())))
    assert _keys_of(advisor) == before
    pattern = SCHEMA["$defs"]["walkStop"]["properties"]["key"]["pattern"]
    assert all(re.fullmatch(pattern, k) and k.startswith(i + "-") for i, k in before.items())
    assert len(set(before.values())) == len(before)


def _edits():
    def stop(**kw):
        return lambda a: a["walk"]["stops"][0].update(kw)
    return [stop(title="Pay twice"), stop(steps=["Only one step"]), stop(expect="Something else."),
            stop(group="Elsewhere"), stop(kind="look", steps=[]), stop(optional=True), stop(notWalked="No access."),
            stop(pictures=[]), lambda a: a["walk"]["stops"][0]["pictures"][0].update(alt="Another alt"),
            lambda a: a["walk"]["stops"][0]["pictures"][0].update(caption="Another caption"),
            lambda a: a["walk"]["stops"][0]["pictures"].pop(0),
            lambda a: a["walk"]["open"].update(url="https://other.example.test"),
            lambda a: a["walk"].update(note="Walk at your desk.")]


@pytest.mark.parametrize("edit", _edits())
def test_a_walk_stop_key_changes_when_anything_it_shows_changes(edit):
    # Axis: any shown field, or the walk's open or note, gives the stop a new key; the id prefix stays.
    advisor = bundle(WALK)[1]
    before = _keys_of(advisor)["p1"]
    edit(advisor)
    after = _keys_of(advisor)["p1"]
    assert after != before and after.startswith("p1-")


def test_a_walk_stop_key_digest_length_is_the_width_the_schema_pattern_names():
    width = int(re.search(r"\{(\d+)\}", SCHEMA["$defs"]["walkStop"]["properties"]["key"]["pattern"]).group(1))
    assert all(len(k.rsplit("-", 1)[1]) == width == pr_sheet.STOP_DIGEST for k in _keys_of(bundle(WALK)[1]).values())


def _placed_key(advisor, place):
    sheet = pr_sheet.build(bundle(WALK)[0], copy.deepcopy(advisor), WORDS, place=place)
    return {s["id"]: s["key"] for s in sheet["prSheet"]["walk"]["stops"]}


def test_a_walk_stop_key_changes_when_a_copied_picture_changes():
    # Axis: with pictures copied, a different file (a different src) or a picture that became missing gives the stop a new key; other stops keep theirs.
    advisor = bundle(WALK)[1]
    before = _placed_key(advisor, lambda path: "pictures/aaaaaaaaaaaa.png")
    other_file = _placed_key(advisor, lambda path: "pictures/bbbbbbbbbbbb.png")
    missing = _placed_key(advisor, lambda path: None)
    pictured = [s["id"] for s in advisor["walk"]["stops"] if s.get("pictures")]
    assert pictured
    for stop_id in pictured:
        assert len({before[stop_id], other_file[stop_id], missing[stop_id]}) == 3
    for stop_id in set(before) - set(pictured):
        assert before[stop_id] == other_file[stop_id] == missing[stop_id]


def test_a_walk_stop_key_changes_when_only_one_of_the_stops_pictures_changes_src():
    # Axis: changing the src of just one picture on a stop is enough to change the stop's key.
    advisor = bundle(WALK)[1]
    first = advisor["walk"]["stops"][0]["pictures"][0]["path"]
    before = _placed_key(advisor, lambda path: "pictures/aaaaaaaaaaaa.png")
    after = _placed_key(advisor, lambda path: "pictures/bbbbbbbbbbbb.png" if path == first else "pictures/aaaaaaaaaaaa.png")
    assert after["p1"] != before["p1"]


@pytest.mark.parametrize("edit", [lambda p: p.update(alt="Another alt"), lambda p: p.update(caption="Another caption")], ids=["alt", "caption"])
def test_a_walk_stop_key_changes_when_a_copied_pictures_alt_or_caption_changes(edit):
    # Axis: with the picture copied, a changed alt or caption still gives the stop a new key.
    advisor = bundle(WALK)[1]
    place = lambda path: "pictures/aaaaaaaaaaaa.png"  # noqa: E731
    before = _placed_key(advisor, place)["p1"]
    edit(advisor["walk"]["stops"][0]["pictures"][0])
    assert _placed_key(advisor, place)["p1"] != before
