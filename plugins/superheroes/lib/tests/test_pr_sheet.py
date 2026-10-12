"""Guards for the PR sheet builder: its facts, where each finding lands, card ids, refusals, the CLI and the samples."""
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import pr_sheet
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
    assert part["craft"] == [] and part["alreadyDecided"] == [] and part["walk"] == []
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
    assert all(stop["pr"] in [p["number"] for p in part["prs"]] for stop in part["walk"])
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
    pytest.param(STACK, lambda r, a: a["walk"][0].update(pr=999), "which is not in this sheet", id="walk-stop-not-in-stack"),
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
    pytest.param(BIG, lambda r, a: a["walk"].append(copy.deepcopy(a["walk"][0])), "repeats the id", id="walk-repeats-an-id"),
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
    assert json.loads(done.stdout) == {"ok": True, "out": str(out), "cards": 3}
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


def test_the_schema_ran_enum_is_the_record_writers_completed_states():
    # Axis: the sheet schema's ran enum equals the review record's ran states less not-run.
    import review_record
    enum = SCHEMA["$defs"]["prSheet"]["properties"]["whatChanged"]["properties"]["reviewers"]["items"]["properties"]["ran"]["enum"]
    assert tuple(enum) == tuple(x for x in review_record.RAN_STATES if x != review_record.RAN_NOT_RUN)
