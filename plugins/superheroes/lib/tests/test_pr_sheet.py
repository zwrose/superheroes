"""Guards for the PR sheet builder: its facts, where each finding lands, card ids, refusals, the CLI and the samples."""
import contextlib
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
import sheet_prose
from provenance_patterns import PROVENANCE_PATTERNS
from test_sheet_schema import check_sheet_problems, walk_stop
from test_sheet_schema import pr_sheet as schema_pr_sheet

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
COLLECTOR = (["record-small.json"], "input-collector.json")


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def bundle(case):
    records, advisor = case
    return [load(r) for r in records], load(advisor)


def build(records, advisor, previous=None):
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, previous=previous)


def built(case):
    return build(*bundle(case))


def problems_of(records, advisor, previous=None):
    with pytest.raises(pr_sheet.Refusal) as caught:
        build(records, advisor, previous)
    return caught.value.problems


def with_nothing_listed(sheet):
    """The sheet as the command builds it from bodies that list no acceptance: the API's output plus the build's record of that."""
    return {**sheet, "prSheet": {**sheet["prSheet"], "nothingListed": True}}


def leftover_cards(sheet):
    return [c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]


def body_args(records, body="body-none.md"):
    """--pr-body for the PR of each record file, every one naming the body fixture (by default one whose accepting section is None)."""
    args = []
    for r in records:
        with contextlib.suppress(OSError, ValueError, KeyError):
            args += ["--pr-body", f"{json.loads(Path(r).read_text(encoding='utf-8'))['pr']}={FIXTURES / body}"]
    return args


def cli(records, advisor, out, extra=None):
    """A build through the command; extra replaces the default --pr-body arguments, which name body-none.md for every record."""
    args = [sys.executable, "-B", str(LIB / "pr_sheet.py"), "build", "--input", str(advisor), "--out", str(out)]
    for r in records:
        args += ["--record", str(r)]
    return subprocess.run(args + (body_args(records) if extra is None else extra), capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("case", [BIG, SMALL, STACK, CLOSES, COLLECTOR], ids=["big", "small", "stack", "closes", "collector"])
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


def test_options_object_and_none():
    # Axis: an object-form leftover gets the words' three options with only fix-before-merge sending back; none gives no options.
    cards = {c["question"]: c for c in leftover_cards(built(BIG))}
    given = cards["A payment that fails three times ends with no email"]
    assert [{k: v for k, v in o.items() if k != "consequence"} for o in given["options"]] == \
        [{k: v for k, v in o.items() if k != "consequence"} for o in WORDS["leftoverOptions"]]
    assert [o["id"] for o in given["options"] if o["sendsBack"]] == ["fix-before-merge"]
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
    assert no_final_review("a1b2c3d", "commit aaaaaaa") in history


def fill(key, **slots):
    return pr_sheet._fill(WORDS[key], **slots)


def later_rounds(final, earlier):
    return fill("historyLaterRounds", final=final, earlier=earlier)


def no_final_review(final, earlier):
    return fill("historyNoFinalReview", final=final, earlier=earlier)


def coverage_lines(history, prefix=""):
    return [line for line in history if line.startswith(prefix) and (
        "Earlier rounds read" in line or "covers the final commit" in line or "reviewed an earlier commit" in line)]


def with_rows(record, *rows):
    """The record's first reviewer rows, each updated as given; any further row is dropped."""
    record["reviewers"] = [{**v, **row} for v, row in zip(record["reviewers"], rows)]


def test_a_normal_multi_round_review_reads_as_normal():
    # Axis: earlier rows plus a later covering row give one plain line and no warning, and never a per-seat line.
    records, advisor = bundle(BIG)
    with_rows(records[0], {"coversFinalCommit": False, "commit": "aaaaaaa"}, {"coversFinalCommit": False, "commit": "aaaaaaa"},
              {"coversFinalCommit": True})
    history = build(records, advisor)["prSheet"]["history"]
    assert coverage_lines(history) == [later_rounds("a1b2c3d", "commit aaaaaaa")]
    assert not any("reviewed an earlier commit" in line for line in history)
    assert not any(WORDS["historyNoFinalReview"].split("{")[0] in line for line in history)


def test_an_audit_row_covering_the_final_commit_covers_it():
    # Axis: an audit row (planned, covers the final commit) is a covering row like any other.
    records, advisor = bundle(BIG)
    with_rows(records[0], {"coversFinalCommit": False, "commit": "aaaaaaa"}, {"coversFinalCommit": False, "commit": "bbbbbbb"})
    records[0]["reviewers"].append({"name": "audits auditor codex (round 2)", "family": "codex", "ran": "engine-record",
                                    "planned": True, "coversFinalCommit": True})
    history = build(records, advisor)["prSheet"]["history"]
    assert coverage_lines(history) == [later_rounds("a1b2c3d", "commits aaaaaaa, bbbbbbb")]


def test_a_final_commit_no_row_covers_is_the_real_gap_warning():
    # Axis: earlier rows and no covering row give exactly one warning naming the final and the earlier commits.
    records, advisor = bundle(BIG)
    with_rows(records[0], {"coversFinalCommit": False, "commit": "aaaaaaa"}, {"coversFinalCommit": False, "commit": "bbbbbbb"})
    history = build(records, advisor)["prSheet"]["history"]
    assert coverage_lines(history) == [no_final_review("a1b2c3d", "commits aaaaaaa, bbbbbbb")]
    assert "Earlier rounds read" not in " ".join(history)


def test_a_row_that_is_unplanned_or_silent_about_coverage_never_covers():
    # Axis: planned false never covers, and a coverage flag absent (or not literally True) never covers.
    records, advisor = bundle(BIG)
    with_rows(records[0], {"coversFinalCommit": False, "commit": "aaaaaaa"}, {"planned": False, "coversFinalCommit": True})
    history = build(records, advisor)["prSheet"]["history"]
    assert coverage_lines(history) == [no_final_review("a1b2c3d", "commit aaaaaaa")]
    records, advisor = bundle(BIG)
    with_rows(records[0], {"coversFinalCommit": False, "commit": "aaaaaaa"}, {})
    assert "coversFinalCommit" not in records[0]["reviewers"][1]
    assert coverage_lines(build(records, advisor)["prSheet"]["history"]) == [no_final_review("a1b2c3d", "commit aaaaaaa")]
    records[0]["reviewers"][1]["coversFinalCommit"] = "yes"
    assert coverage_lines(build(records, advisor)["prSheet"]["history"]) == [no_final_review("a1b2c3d", "commit aaaaaaa")]


def test_earlier_rows_naming_no_commit_say_an_earlier_commit():
    # Axis: no named earlier commit reads "an earlier commit"; an empty final sha is refused before the history is built.
    records, advisor = bundle(BIG)
    with_rows(records[0], {"coversFinalCommit": False})
    history = build(records, advisor)["prSheet"]["history"]
    assert coverage_lines(history) == [no_final_review("a1b2c3d", "an earlier commit")]
    records[0]["finalCommit"]["sha"] = ""
    assert problems_of(records, advisor) == ["record for PR #214: finalCommit.sha is null or not a commit id"]


def test_no_earlier_rows_give_no_coverage_line():
    # Axis: with no ran row on an earlier commit there is no coverage line, covered or not.
    records, advisor = bundle(BIG)
    assert coverage_lines(build(records, advisor)["prSheet"]["history"]) == []
    with_rows(records[0], {"coversFinalCommit": True}, {"coversFinalCommit": False, "commit": "aaaaaaa", "ran": "not-run"})
    assert coverage_lines(build(records, advisor)["prSheet"]["history"]) == []


def test_leftover_lines_collapse_to_one_count_and_other_gaps_stay_incomplete():
    # Axis: only a line exactly equal to a left-for-owner finding's leftover line of the same record is counted.
    records, advisor = bundle(BIG)
    left = [f for f in records[0]["findings"] if f["outcome"] == "left-for-owner"]
    lines = [review_record.leftover_line(f) for f in left]
    assert len(lines) == 2
    records[0].update(status="not-reviewed", whatIsMissing=list(lines))
    history = build(records, advisor)["prSheet"]["history"]
    assert fill("historyLeftovers", count=2) == "2 findings are left for you below." and history.count("2 findings are left for you below.") == 1
    assert not any("The review record is incomplete" in line or "waits for the owner" in line for line in history)
    records[0]["whatIsMissing"] = lines[:1]
    history = build(records, advisor)["prSheet"]["history"]
    assert history.count(WORDS["historyLeftover"]) == 1 and not any("findings are left" in line for line in history)
    ghost = "finding ghost waits for the owner's decision"
    records[0]["whatIsMissing"] = ["CI is red on abc1234", lines[0], ghost, lines[1]]
    history = build(records, advisor)["prSheet"]["history"]
    incomplete = [line for line in history if "The review record is incomplete" in line]
    assert incomplete == [fill("historyIncomplete", what="CI is red on abc1234"), fill("historyIncomplete", what=ghost)]
    assert history.count("2 findings are left for you below.") == 1
    assert history.index(incomplete[0]) < history.index("2 findings are left for you below.") < history.index(incomplete[1])


def test_leftover_lines_are_replaced_only_when_the_record_is_not_reviewed():
    # Axis: the not-reviewed gate stays; a record with another status, or with no whatIsMissing, adds no gap or count line.
    records, advisor = bundle(BIG)
    lines = [review_record.leftover_line(f) for f in records[0]["findings"] if f["outcome"] == "left-for-owner"]
    records[0].update(status="reviewed", whatIsMissing=lines)
    assert not any("left for you" in line or "incomplete" in line for line in build(records, advisor)["prSheet"]["history"])
    for gone in (None, []):
        records[0].update(status="not-reviewed", whatIsMissing=gone)
        assert not any("left for you" in line or "incomplete" in line for line in build(records, advisor)["prSheet"]["history"])


def test_each_pr_of_a_stack_gets_its_own_coverage_and_leftover_lines():
    # Axis: on a stack the coverage and leftover lines are built per record and prefixed with that record's PR.
    records, advisor = bundle(STACK)
    five, six = records[0], records[1]
    five["reviewers"] = [{**five["reviewers"][0], "coversFinalCommit": False, "commit": "aaaaaaa"},
                         {**five["reviewers"][0], "name": "audits auditor codex (round 2)", "planned": True, "coversFinalCommit": True}]
    with_rows(six, {"coversFinalCommit": False, "commit": "bbbbbbb"}, {})
    six.update(status="not-reviewed", whatIsMissing=[review_record.leftover_line(f) for f in six["findings"] if f["outcome"] == "left-for-owner"])
    history = build(records, advisor)["prSheet"]["history"]
    assert coverage_lines(history, "#5: ") == ["#5: " + later_rounds("1111111", "commit aaaaaaa")]
    assert coverage_lines(history, "#6: ") == ["#6: " + no_final_review("2222222", "commit bbbbbbb")]
    assert coverage_lines(history, "#7: ") == []
    assert history.count("#6: " + WORDS["historyLeftover"]) == 1
    assert not any(line.startswith("#5: ") and "left for you" in line for line in history)


def test_the_leftover_line_is_the_records_own_wording():
    # Axis: the sheet reads the leftover wording from review_record, so the record and the sheet cannot drift.
    assert review_record.leftover_line({"id": "x"}) == "finding x waits for the owner's decision"
    f = {"id": "x", "outcome": "left-for-owner", "reason": "the owner decides"}
    assert review_record._finding_lines([f]) == [review_record.leftover_line(f)]


def test_leftover_overrides_are_keyed_by_finding_key_and_an_ambiguous_id_is_refused():
    # Axis: two left-for-owner findings sharing a reviewer id take separate entries by findingKey; the shared id is refused.
    records, advisor = bundle(BIG)
    left = [f for f in records[0]["findings"] if f["outcome"] == "left-for-owner"]
    left[1]["id"] = left[0]["id"]
    entry = {"why": "w", "context": "c", "options": "none"}
    advisor["leftovers"] = {left[0]["findingKey"]: {**entry, "recommendation": {"text": "A", "reason": "a"}}, left[1]["findingKey"]: entry}
    cards = [c for c in build(records, advisor)["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]
    assert [c.get("recommendation", {}).get("text") for c in cards] == ["A", None]
    advisor["leftovers"] = {left[0]["id"]: entry}
    assert any("names 2 left-for-owner findings" in p for p in problems_of(records, advisor))


def test_a_stack_is_built_in_prs_order_whatever_the_record_order():
    # Axis: records given out of order still give the bottom PR first and the top PR's commit.
    records, advisor = bundle(STACK)
    assert build(records[::-1], advisor) == build(records, advisor)


# --- carrying a verdict forward across a move that is not material ---

NO_PREVIOUS = "no bytes"
CARRY_DATE, CARRY_MOVED, CARRY_WHY = "2026-09-30", "the branch was brought current with main", "main added only a README line"
CARRY_CASES = {
    "pr": (SMALL, {"211": "1" * 40}),
    "pr-with-cards": (BIG, {"214": "2" * 40}),
    "stack": (STACK, {"5": "5" * 40, "6": "6" * 40, "7": "7" * 40}),
}


def sheet_bytes(sheet):
    """A sheet as the builder's command writes it: the exact bytes a digest is taken of."""
    return (json.dumps(sheet, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def carry_input(advisor, heads, **more):
    advisor["carriedForward"] = {"fromSheet": "earlier/sheet.json", "heads": dict(heads), "date": CARRY_DATE, "moved": CARRY_MOVED, "whyNotMaterial": CARRY_WHY, **more}
    return advisor


def carry_with(case, edit):
    """The problems of a carry over `case` after edit(advisor, earlier sheet) changed what it could; edit may return the bytes to give as the earlier sheet."""
    records, advisor = bundle(case)
    earlier = built(case)
    carry_input(advisor, CARRY_CASES[next(k for k, v in CARRY_CASES.items() if v[0] == case)][1])
    given = edit(advisor, earlier)
    previous = None if given == NO_PREVIOUS else given if isinstance(given, bytes) else sheet_bytes(earlier)
    return problems_of(records, advisor, previous)


@pytest.mark.parametrize("name", CARRY_CASES)
def test_a_carry_takes_its_heads_and_digest_and_leaves_everything_else_as_built(name):
    # Bites on: a carried sheet that keeps the records' final commits, forgets previousCommit, records the wrong digest, or changes anything beyond the commits and the carry (the CI line names the commit CI ran on).
    # Axis: previousCommit is the earlier sheet's commit, commit and each prs[].commit come from heads (the top PR's on a stack), carriedForward holds the earlier bytes' digest and the input's words, nothing else moves.
    case, heads = CARRY_CASES[name]
    records, advisor = bundle(case)
    earlier = build(records, advisor)
    previous = sheet_bytes(earlier)
    plain = build(records, advisor)
    carried = build(records, carry_input(advisor, heads), previous)
    part = carried["prSheet"]
    top = str(advisor["prs"][-1]["number"] if advisor["kind"] == "stack" else advisor["number"])
    assert part["previousCommit"] == earlier["prSheet"]["commit"]
    assert part["commit"] == heads[top] != plain["prSheet"]["commit"]
    assert part["carriedForward"] == {"sheets": [hashlib.sha256(previous).hexdigest()], "date": CARRY_DATE, "moved": CARRY_MOVED, "whyNotMaterial": CARRY_WHY}
    if advisor["kind"] == "stack":
        assert [(f["number"], f["commit"]) for f in part["prs"]] == [(f["number"], heads[str(f["number"])]) for f in advisor["prs"]]
    assert part["whatChanged"]["ci"] == plain["prSheet"]["whatChanged"]["ci"] and part["whatChanged"]["ci"]["commit"] != part["commit"]
    moved = ("commit", "previousCommit", "carriedForward", "prs")
    assert {**carried, "prSheet": {k: v for k, v in part.items() if k not in moved}} == {**plain, "prSheet": {k: v for k, v in plain["prSheet"].items() if k not in moved}}
    assert [{k: v for k, v in f.items() if k != "commit"} for f in part.get("prs", [])] == [{k: v for k, v in f.items() if k != "commit"} for f in plain["prSheet"].get("prs", [])]
    assert list(Draft202012Validator(SCHEMA).iter_errors(carried)) == [] and check_sheet_problems(carried) == []


def test_a_previous_commit_beside_a_carry_builds_when_it_is_the_earlier_sheets_commit():
    # Bites on: the carry refusing a previousCommit that agrees with the earlier sheet, or taking it instead of the earlier sheet's.
    records, advisor = bundle(SMALL)
    previous = sheet_bytes(build(records, advisor))
    advisor["previousCommit"] = build(records, advisor)["prSheet"]["commit"]
    carried = build(records, carry_input(advisor, CARRY_CASES["pr"][1]), previous)
    assert carried["prSheet"]["previousCommit"] == advisor["previousCommit"] and "carriedForward" in carried["prSheet"]


def test_a_chain_of_carries_lists_the_earlier_digests_newest_first():
    # Bites on: the chain keeping only the newest digest, listing the oldest first, or dropping the digests the earlier sheet had carried.
    records, advisor = bundle(SMALL)
    first = sheet_bytes(build(records, advisor))
    second = build(records, carry_input(advisor, {"211": "1" * 40}), first)
    second_bytes = sheet_bytes(second)
    third = build(records, carry_input(advisor, {"211": "3" * 40}), second_bytes)
    assert second["prSheet"]["carriedForward"]["sheets"] == [hashlib.sha256(first).hexdigest()]
    assert third["prSheet"]["carriedForward"]["sheets"] == [hashlib.sha256(second_bytes).hexdigest(), hashlib.sha256(first).hexdigest()]
    assert third["prSheet"]["previousCommit"] == "1" * 40 and third["prSheet"]["commit"] == "3" * 40
    assert list(Draft202012Validator(SCHEMA).iter_errors(third)) == [] and check_sheet_problems(third) == []


def three_layer_to_two():
    """The stack's earlier sheet, from the days it had two layers."""
    records, advisor = bundle(STACK)
    advisor["prs"] = advisor["prs"][:2]
    advisor["walk"]["stops"] = [stop for stop in advisor["walk"]["stops"] if stop["pr"] != 7]
    return sheet_bytes(build(records[:2], advisor))


CARRY_REFUSALS = [
    pytest.param(SMALL, lambda a, e: NO_PREVIOUS, "none were given", id="no-earlier-bytes"),
    pytest.param(SMALL, lambda a, e: b"{nope", "is not JSON", id="earlier-not-json"),
    pytest.param(SMALL, lambda a, e: b"[]", "is not a pr or stack sheet", id="earlier-not-an-object"),
    pytest.param(SMALL, lambda a, e: e.__setitem__("kind", "plain"), "is not a pr or stack sheet", id="earlier-of-another-kind-of-sheet"),
    pytest.param(SMALL, lambda a, e: sheet_bytes(built(STACK)), "is a stack sheet, but this one is a pr sheet", id="kind-differs"),
    pytest.param(SMALL, lambda a, e: e["prSheet"].__setitem__("number", 999), "is for number 999, not 211", id="number-differs"),
    pytest.param(STACK, lambda a, e: three_layer_to_two(), "covers PRs [5, 6], but this stack lists PRs [5, 6, 7]", id="stack-gained-a-layer"),
    pytest.param(STACK, lambda a, e: e["prSheet"]["prs"].reverse(), "covers PRs [7, 6, 5], but this stack lists PRs [5, 6, 7]", id="stack-members-in-another-order"),
    pytest.param(SMALL, lambda a, e: a.__setitem__("previousCommit", "abcdef0"), "previousCommit abcdef0 is not the earlier sheet's commit", id="previous-commit-differs"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"]["heads"].clear(), "heads has PRs [], but the sheet covers PRs ['211']", id="heads-empty"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"]["heads"].update({"212": "1" * 40}), "heads has PRs ['211', '212'], but the sheet covers PRs ['211']", id="heads-extra-key"),
    pytest.param(STACK, lambda a, e: a["carriedForward"]["heads"].pop("7"), "heads has PRs ['5', '6'], but the sheet covers PRs ['5', '6', '7']", id="heads-missing-key"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"]["heads"].update({"211": "XYZ"}), "heads 211 must be a commit id", id="heads-value-not-a-commit"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"].update(extra=1), "carriedForward has an unknown key extra", id="carry-unknown-key"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"].pop("whyNotMaterial"), "carriedForward is missing whyNotMaterial", id="carry-missing-key"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"].update(date="30 September"), "date must be a date written YYYY-MM-DD", id="carry-bad-date"),
    pytest.param(SMALL, lambda a, e: a["carriedForward"].update(moved=" "), "moved must be a non-empty string", id="carry-empty-moved"),
    pytest.param(SMALL, lambda a, e: a.__setitem__("carriedForward", "earlier/sheet.json"), "carriedForward must be an object", id="carry-not-an-object"),
    pytest.param(SMALL, lambda a, e: e["prSheet"].pop("whatChanged"), "the earlier sheet (carriedForward fromSheet):", id="earlier-sheet-does-not-fit-the-schema"),
]


@pytest.mark.parametrize("case, edit, expected", CARRY_REFUSALS)
def test_a_carry_that_cannot_be_proved_is_refused(case, edit, expected):
    # Bites on: a carry built on bytes that are missing, not JSON, not a pr or stack sheet, of another kind, number or stack member list, with a previousCommit that disagrees, or with heads that do not name exactly the covered PRs.
    # Axis: each is a collected refusal problem (a Refusal, never a crash) that names its cause; the fail-closed edges of the carry.
    assert any(expected in problem for problem in carry_with(case, edit)), expected


def test_a_carry_refusal_is_collected_with_the_other_problems():
    # Bites on: the carry's checks raising on the first problem instead of listing it with the others.
    records, advisor = bundle(SMALL)
    advisor["summary"] = ""
    problems = problems_of(records, carry_input(advisor, {}), None)
    assert any("summary must be a non-empty string" in p for p in problems) and any("heads has PRs" in p for p in problems)


@pytest.mark.parametrize("case, name", [(STACK, "stack"), (SMALL, "pr")])
def test_a_carry_on_an_input_with_no_number_is_refused_not_a_crash(case, name):
    # Bites on: the earlier-sheet comparison reading advisor["number"] after the input check already found it missing (a KeyError instead of a refusal).
    # Axis: fail-closed edges 1 and 2: a stack or pr carry with no number is a collected Refusal that names the missing number.
    records, advisor = bundle(case)
    advisor.pop("number")
    problems = problems_of(records, carry_input(advisor, CARRY_CASES[name][1]), sheet_bytes(built(case)))
    assert any("number must be an integer, 1 or more" in problem for problem in problems)


def test_the_cli_refuses_a_stack_carry_with_no_number_and_writes_nothing(tmp_path):
    # Bites on: a stack carry with no number crashing the command with a traceback instead of printing the refusal.
    # Axis: fail-closed edge 3: through the command, exit 1, one JSON line with ok false, and no output file.
    (tmp_path / "earlier").mkdir()
    records = [FIXTURES / name for name in STACK[0]]
    assert cli(records, FIXTURES / STACK[1], tmp_path / "earlier" / "sheet.json").returncode == 0
    advisor = carry_input(load(STACK[1]), CARRY_CASES["stack"][1])
    advisor.pop("number")
    source = tmp_path / "in.json"
    source.write_text(json.dumps(advisor), encoding="utf-8")
    out = tmp_path / "out.json"
    done = cli(records, source, out)
    assert done.returncode == 1 and not out.exists()
    assert len(done.stdout.splitlines()) == 1
    result = json.loads(done.stdout)
    assert result["ok"] is False and any("number must be an integer, 1 or more" in problem for problem in result["problems"])


def carry_world(tmp_path, advisor_edit=None):
    """The small PR's earlier sheet written to tmp_path/earlier/sheet.json, and a carried input beside tmp_path/in.json."""
    (tmp_path / "earlier").mkdir()
    done = cli([FIXTURES / "record-small.json"], FIXTURES / "input-small.json", tmp_path / "earlier" / "sheet.json")
    assert done.returncode == 0, done.stdout
    advisor = carry_input(load("input-small.json"), {"211": "1" * 40})
    if advisor_edit:
        advisor_edit(advisor)
    source = tmp_path / "in.json"
    source.write_text(json.dumps(advisor), encoding="utf-8")
    return source


def test_the_cli_reads_the_earlier_sheet_beside_the_input_and_digests_its_exact_bytes(tmp_path):
    # Bites on: the builder digesting a re-serialised copy instead of the file's bytes, or resolving fromSheet against the working folder instead of the input's.
    source = carry_world(tmp_path)
    out = tmp_path / "out.json"
    done = cli([FIXTURES / "record-small.json"], source, out)
    assert done.returncode == 0, done.stdout
    sheet = json.loads(out.read_text(encoding="utf-8"))
    assert sheet["prSheet"]["carriedForward"]["sheets"] == [hashlib.sha256((tmp_path / "earlier" / "sheet.json").read_bytes()).hexdigest()]
    assert sheet["prSheet"]["commit"] == "1" * 40


def test_the_cli_takes_an_absolute_from_sheet_too(tmp_path):
    # Bites on: an absolute fromSheet being joined under the input's folder.
    source = carry_world(tmp_path, lambda advisor: advisor["carriedForward"].update(fromSheet=str(tmp_path / "earlier" / "sheet.json")))
    done = cli([FIXTURES / "record-small.json"], source, tmp_path / "out.json")
    assert done.returncode == 0, done.stdout


def test_the_cli_refuses_an_earlier_sheet_it_cannot_read_and_names_the_file(tmp_path):
    # Bites on: an unreadable fromSheet crashing, being skipped, or built as though there were no carry.
    # Axis: fail-closed edge 1: a carry without readable earlier bytes is a refusal that names the file, and nothing is written.
    source = carry_world(tmp_path, lambda advisor: advisor["carriedForward"].update(fromSheet="earlier/missing.json"))
    out = tmp_path / "out.json"
    done = cli([FIXTURES / "record-small.json"], source, out)
    assert done.returncode == 1 and not out.exists()
    result = json.loads(done.stdout)
    assert result["ok"] is False and any("earlier/missing.json" in problem for problem in result["problems"])


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


def test_a_non_text_pr_body_is_refused_through_build():
    # Axis: a body that is not text is a collected refusal naming the PR; an empty string is still text and builds.
    records, advisor = bundle(SMALL)
    with pytest.raises(pr_sheet.Refusal) as caught:
        pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, bodies={211: None})
    assert caught.value.problems == ["PR #211's body must be text"]
    assert pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, bodies={211: ""})


def test_cli_writes_the_sheet_and_prints_the_receipt(tmp_path):
    # Axis: a good run exits 0, prints ok and the card count, and writes the data file.
    out = tmp_path / "sheet.json"
    done = cli([FIXTURES / "record-big.json"], FIXTURES / "input-big.json", out)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"ok": True, "out": str(out), "cards": 3, "pictures": []}
    assert json.loads(out.read_text(encoding="utf-8")) == with_nothing_listed(built(BIG))


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


def test_a_leftover_with_no_entry_is_refused():
    # Axis: a left-for-owner finding with no leftovers entry is refused by title and key, never given the words' generic options.
    records, advisor = bundle(BIG)
    advisor["leftovers"].pop("F6")
    assert problems_of(records, advisor) == ["left-for-owner finding 'Customers are not told a retry happened' on PR #214 "
                                             "has no leftovers entry (key 'retry/no-notice'); give it why, context and options, or a craft determination"]


def test_a_leftover_card_carries_the_spine_in_order():
    # Axis: a leftover's context is Why it's yours, What happened, If left in that order, the third being ifLeft when given, else the finding's consequence.
    records, advisor = bundle(BIG)
    titles = [WORDS["whyYours"], WORDS["whatHappened"], WORDS["ifLeft"]]
    for key, finding in zip(("F6", "F7"), records[0]["findings"][5:7]):
        entry = advisor["leftovers"][key]
        card = next(c for c in leftover_cards(build(records, advisor)) if c["question"] == finding["title"])
        assert [s["title"] for s in card["context"]] == titles
        assert [s["blocks"] for s in card["context"]] == [[{"paragraph": entry["why"]}], [{"paragraph": entry["context"]}],
                                                          [{"paragraph": finding["consequence"]}]]
    advisor["leftovers"]["F7"]["ifLeft"] = ("The email is now sent by the shop's mail service.")
    card = next(c for c in leftover_cards(build(records, advisor)) if c["question"] == records[0]["findings"][6]["title"])
    assert card["context"][2] == {"title": WORDS["ifLeft"], "blocks": [{"paragraph": "The email is now sent by the shop's mail service."}]}


def no_why(advisor):
    advisor["leftovers"]["F7"].pop("why")


def no_context(advisor):
    advisor["leftovers"]["F7"].pop("context")


def bare_leftover(advisor):
    advisor["leftovers"]["F7"]["options"] = "leftover"


def object_missing_an_id(advisor):
    advisor["leftovers"]["F7"]["options"].pop("keep-it")


def object_with_an_extra_key(advisor):
    advisor["leftovers"]["F7"]["options"]["ship-it"] = "Ships."


@pytest.mark.parametrize("edit, text", [
    pytest.param(no_why, "leftovers F7 is missing why", id="no-why"),
    pytest.param(no_context, "leftovers F7 is missing context", id="no-context"),
    pytest.param(bare_leftover, 'leftovers F7: options "leftover" is refused; give each option\'s consequence for this leftover', id="bare-leftover"),
    pytest.param(object_missing_an_id, "leftovers F7: options must be none, a list of options or an object giving", id="object-missing-an-id"),
    pytest.param(object_with_an_extra_key, "leftovers F7: options must be none, a list of options or an object giving", id="object-extra-key"),
])
def test_a_leftover_without_its_spine_is_refused_naming_the_finding(edit, text):
    # Axis: an entry missing why or context, the bare "leftover" options, or a malformed options object is refused and the problem names the leftover's key.
    records, advisor = bundle(BIG)
    edit(advisor)
    assert any(text in p for p in problems_of(records, advisor))


def test_an_object_form_leftover_carries_the_advisors_consequences():
    # Axis: an object-form entry's card has the advisor's three consequences and none of the words file's generic ones, with the words' ids, labels and sendsBack.
    card = next(c for c in leftover_cards(built(BIG)) if c["question"] == "A payment that fails three times ends with no email")
    given = load("input-big.json")["leftovers"]["F7"]["options"]
    assert [o["consequence"] for o in card["options"]] == [given[o["id"]] for o in WORDS["leftoverOptions"]]
    assert not {o["consequence"] for o in WORDS["leftoverOptions"]} & {o["consequence"] for o in card["options"]}
    assert [{k: o[k] for k in ("id", "label", "sendsBack")} for o in card["options"]] == \
        [{k: o[k] for k in ("id", "label", "sendsBack")} for o in WORDS["leftoverOptions"]]


def test_none_options_build_a_leftover_with_no_options():
    # Axis: options "none" on a leftover builds a card whose options are empty (the page's Accept and Discuss).
    card = next(c for c in leftover_cards(built(BIG)) if c["question"] == "Customers are not told a retry happened")
    assert load("input-big.json")["leftovers"]["F6"]["options"] == "none" and card["options"] == []


@pytest.mark.parametrize("given", [{key: "Ships." for key in ("keep-it", "fix-in-a-follow-up", "fix-before-merge")}, "leftover"],
                         ids=["object", "bare-leftover"])
def test_an_item_keeps_none_or_a_list_for_options(given):
    # Axis: the advisor's own items take only "none" or a list of options; neither the leftover object form nor the bare "leftover" reaches them.
    records, advisor = bundle(BIG)
    advisor["items"][0]["options"] = given
    assert any(p.startswith("items retry-window: options must be none, a list of options") and "object" not in p
               for p in problems_of(records, advisor))


FOLD_NOTES = ["Size: 41 lines against an estimate of 30 to 80.", "Tests only, no app change.", "The nightly audit was already red; ruled last week."]


def test_an_item_with_a_list_if_left_shows_its_notes_as_a_bulleted_list():
    # Axis: a list ifLeft lands as one bullets block, one bullet per note in input order, and the sheet passes the schema and the page check.
    # Bites on: the list rendered as a paragraph, joined into one string, reordered, or a list ifLeft refused.
    records, advisor = bundle(BIG)
    advisor["items"][0]["ifLeft"] = list(FOLD_NOTES)
    sheet = build(records, advisor)
    card = next(c for c in sheet["cards"] if c["question"] == advisor["items"][0]["title"])
    assert card["context"] == [{"title": WORDS["ifLeft"], "blocks": [{"bullets": FOLD_NOTES}]}]
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == []
    assert check_sheet_problems(sheet) == []


def test_a_string_if_left_builds_the_sheet_exactly_as_before():
    # Axis: a string ifLeft stays one paragraph block, and the list form changes that item's block and id and nothing else.
    # Bites on: the string path re-shaped (wrapped in a list, split into bullets), or the list path touching any other part of the sheet.
    records, advisor = bundle(BIG)
    text = advisor["items"][0]["ifLeft"]
    plain = build(records, advisor)
    card = next(c for c in plain["cards"] if c["question"] == advisor["items"][0]["title"])
    assert card["context"] == [{"title": WORDS["ifLeft"], "blocks": [{"paragraph": text}]}]
    advisor["items"][0]["ifLeft"] = [text]
    listed = build(records, advisor)
    at = plain["cards"].index(card)
    swapped = {k: v for k, v in listed["cards"][at].items() if k != "id"}
    swapped["context"] = card["context"]
    listed["cards"][at] = {"id": pr_sheet.card_id("i-", advisor["number"], advisor["items"][0]["id"], swapped), **swapped}
    assert listed["cards"][at]["id"] == card["id"]
    assert json.dumps(listed, sort_keys=True) == json.dumps(plain, sort_keys=True)


@pytest.mark.parametrize("given", ["", "   ", [], [""], ["A note.", "  "], ["A note.", 3], 3, None],
                         ids=["empty-string", "blank-string", "empty-list", "empty-note", "blank-note", "non-string-note", "number", "null"])
def test_an_item_refuses_an_empty_if_left_list_or_note(given):
    # Axis: ifLeft is a non-empty string or a list of at least 1 non-empty strings; anything else is refused, naming the item.
    # Bites on: an empty list or an empty or blank note let through (an empty bullet on the page), or a non-string note accepted.
    records, advisor = bundle(BIG)
    advisor["items"][0]["ifLeft"] = given
    assert "items retry-window: ifLeft must be a non-empty string or a list of at least 1 non-empty strings" in problems_of(records, advisor)


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
    for name in PICTURE_FILES:
        assert (tmp_path / "out" / src_of(name)).read_bytes() == (FIXTURES / "elsewhere" / name).read_bytes(), name
    path = tmp_path / "out" / src_of("cart-paid.png")
    path.write_bytes(b"left alone")
    second = run_walk(tmp_path)
    assert second.returncode == 0, second.stderr
    assert path.read_bytes() == b"left alone"
    for name in PICTURE_FILES:
        if name != "cart-paid.png":
            assert (tmp_path / "out" / src_of(name)).read_bytes() == (FIXTURES / "elsewhere" / name).read_bytes(), name
    assert json.loads(second.stdout)["pictures"] == json.loads(first.stdout)["pictures"]


WORDS_CASES = [(None, "could not be read as JSON"), ("{not json", "could not be read as JSON"), ("[]", "must hold one JSON object"),
               ("null", "must hold one JSON object"), ('{"pr": 1}', "has no pr block")]


@pytest.mark.parametrize("command", ["build", "index"])
@pytest.mark.parametrize("content,said", WORDS_CASES, ids=["missing", "not-json", "array", "null", "no-pr-block"])
def test_a_words_file_that_cannot_be_used_is_a_refusal_that_names_it(tmp_path, monkeypatch, capsys, command, content, said):
    # Axis: a words file that is missing, not JSON, JSON but not an object, or an object without the blocks the command reads, refuses with its path in the problem, exit 1, and writes nothing.
    words = tmp_path / "words.json"
    if content is not None:
        words.write_text(content, encoding="utf-8")
    monkeypatch.setattr(pr_sheet, "WORDS_PATH", str(words))
    out = tmp_path / "out" / "sheet.json"
    out.parent.mkdir()
    args = ["build", "--record", str(FIXTURES / "record-small.json"), "--input", str(FIXTURES / "input-small.json"),
            *body_args([FIXTURES / "record-small.json"])] if command == "build" \
        else ["index", "--input", str(FIXTURES / "index-input.json")]
    code = pr_sheet.main([*args, "--out", str(out)])
    result = json.loads(capsys.readouterr().out)
    assert code == 1 and result["ok"] is False
    assert result["problems"], result
    assert result["problems"][0].startswith(str(words) + " could not be read") and said in result["problems"][0], result["problems"]
    assert list(out.parent.iterdir()) == []


# Bites on: the words check reading only the first block the index command needs, so a words file missing a later block (prAnswers, answers, index) is read as whole and fails later or not at all.
@pytest.mark.parametrize("block", ["prAnswers", "answers", "index"])
def test_a_words_file_missing_an_index_only_block_is_a_refusal_that_names_the_block(tmp_path, monkeypatch, capsys, block):
    # Axis: the index command refuses a words file that lacks any one of the blocks only it reads, with the words path and the block's name in the problem, exit 1, and nothing written.
    words = tmp_path / "words.json"
    words.write_text(json.dumps({name: found for name, found in ALL_WORDS.items() if name != block}), encoding="utf-8")
    monkeypatch.setattr(pr_sheet, "WORDS_PATH", str(words))
    out = tmp_path / "out" / "sheet.json"
    out.parent.mkdir()
    code = pr_sheet.main(["index", "--input", str(FIXTURES / "index-input.json"), "--out", str(out)])
    result = json.loads(capsys.readouterr().out)
    assert code == 1 and result["ok"] is False
    assert result["problems"] == [f"{words} could not be read: it has no {block} block"], result["problems"]
    assert list(out.parent.iterdir()) == []


def test_a_broken_words_file_does_not_stop_the_builder_at_import(tmp_path):
    # Axis: the builder in a copy of the plugin whose words file is not JSON still starts and refuses in JSON, rather than ending in a traceback at import.
    plugin = tmp_path / "plugin"
    (plugin / "lib").mkdir(parents=True)
    for source in LIB.glob("*.py"):
        shutil.copy(source, plugin / "lib" / source.name)
    shutil.copytree(THEME, plugin / "theme")
    (plugin / "theme" / "sheet-words.json").write_text("{not json", encoding="utf-8")
    out = tmp_path / "out" / "sheet.json"
    out.parent.mkdir()
    done = subprocess.run([sys.executable, "-B", str(plugin / "lib" / "pr_sheet.py"), "build", "--record", str(FIXTURES / "record-small.json"),
                           "--input", str(FIXTURES / "input-small.json"), "--out", str(out), *body_args([FIXTURES / "record-small.json"])],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 1 and "Traceback" not in done.stderr, done.stderr
    result = json.loads(done.stdout)
    assert result["ok"] is False and len(result["problems"]) == 1 and "sheet-words.json could not be read as JSON" in result["problems"][0]
    assert list(out.parent.iterdir()) == []


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
    code = pr_sheet.main(["build", "--record", str(FIXTURES / "record-big.json"), "--input", str(FIXTURES / "input-walk.json"), "--out", str(out),
                          *body_args([FIXTURES / "record-big.json"])])
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


# --- the index: pr_state and the index builder ---

REV_A, REV_B = "a" * 16, "b" * 16
INDEX_WORDS = ALL_WORDS["index"]


def state_sheet():
    """A pr sheet with a leftover card (one option sends back), a closure card with no options, a try stop and a look stop."""
    sheet = schema_pr_sheet()
    sheet["prSheet"]["walk"]["stops"] = [walk_stop("t1", 1724), walk_stop("l1", 1724, kind="look", steps=[])]
    return sheet


STATE_SHEET = json.dumps(state_sheet(), indent=2).encode("utf-8")
STATE_DIGEST = hashlib.sha256(STATE_SHEET).hexdigest()
T1, L1 = "t1-0123456789ab", "l1-0123456789ab"
MATCHING = [f"answers/leftover@{REV_A}", f"answers/closure@{REV_A}"]


def card_doc(answer, option=None, revision=REV_A, **more):
    return {"answer": answer, "optionId": option, "note": "", **({"revision": revision} if revision else {}), **more}


def walk_doc(answer, fix=None, **more):
    return {"answer": answer, "fix": fix, "note": "", "shots": [], **more}


def merge_doc(covers=None, digest=STATE_DIGEST, **more):
    doc = {"verdict": "merge", "note": "", "sheet": digest, "covers": MATCHING if covers is None else covers}
    return {**doc, **more}


KEEP, SEND_BACK, ACCEPT = card_doc("option", "keep-it"), card_doc("option", "fix-before-merge"), card_doc("accept")
ACCEPTED = {"leftover": KEEP, "closure": ACCEPT}


def store_of(answers=None, walk=None, verdict=None, digest=STATE_DIGEST):
    return {"answers": answers or {}, "walk": walk or {}, "verdict": {} if verdict is None else {digest: verdict}}


# Each row: the store, then (state, accepted, total, walked, walkTotal). The sheet always has 2 cards and 2 stops.
STATE_TABLE = {
    "no-answers": ({}, ("needs-you", 0, 2, 0, 2)),
    "all-accepted-no-merge": (store_of(ACCEPTED), ("needs-you", 2, 2, 0, 2)),
    "merge-with-matching-covers": (store_of(ACCEPTED, verdict=merge_doc()), ("ready", 2, 2, 0, 2)),
    "merge-with-a-stale-revision": (
        store_of(ACCEPTED, verdict=merge_doc([f"answers/leftover@{REV_B}", f"answers/closure@{REV_A}"])), ("needs-you", 2, 2, 0, 2)),
    "merge-covers-missing-a-card": (store_of(ACCEPTED, verdict=merge_doc([f"answers/leftover@{REV_A}"])), ("needs-you", 2, 2, 0, 2)),
    "merge-covers-an-extra-entry": (
        store_of(ACCEPTED, verdict=merge_doc(MATCHING + [f"answers/ghost@{REV_A}"])), ("needs-you", 2, 2, 0, 2)),
    "merge-with-no-covers": (store_of(ACCEPTED, verdict={k: v for k, v in merge_doc().items() if k != "covers"}), ("needs-you", 2, 2, 0, 2)),
    "merge-on-an-old-digest": (
        {**store_of(ACCEPTED), "verdict": {"f" * 64: merge_doc(digest="f" * 64)}}, ("needs-you", 2, 2, 0, 2)),
    "merge-whose-sheet-is-another-digest": (
        {**store_of(ACCEPTED), "verdict": {STATE_DIGEST: merge_doc(digest="f" * 64)}}, ("needs-you", 2, 2, 0, 2)),
    "merge-while-a-card-is-discuss": (
        store_of({"leftover": KEEP, "closure": card_doc("discuss")}, verdict=merge_doc()), ("needs-you", 1, 2, 0, 2)),
    "not-yet": (store_of(ACCEPTED, verdict={"verdict": "not-yet", "note": "", "sheet": STATE_DIGEST}), ("needs-you", 2, 2, 0, 2)),
    "a-card-answered-without-a-revision": (
        store_of({"leftover": KEEP, "closure": card_doc("accept", revision=None)}, verdict=merge_doc()), ("needs-you", 2, 2, 0, 2)),
    "sends-back-option": (store_of({"leftover": SEND_BACK, "closure": ACCEPT}), ("being-fixed", 1, 2, 0, 2)),
    "sends-back-option-and-a-merge": (
        store_of({"leftover": SEND_BACK, "closure": ACCEPT}, verdict=merge_doc()), ("being-fixed", 1, 2, 0, 2)),
    "walk-problem-fix-before-merge": (
        store_of(ACCEPTED, {T1: walk_doc("problem", "before-merge")}), ("being-fixed", 2, 2, 1, 2)),
    "walk-problem-no-fix-and-a-merge": (
        store_of(ACCEPTED, {T1: walk_doc("problem")}, merge_doc()), ("needs-you", 2, 2, 1, 2)),
    "walk-problem-follow-up-and-a-merge": (
        store_of(ACCEPTED, {T1: walk_doc("problem", "follow-up")}, merge_doc()), ("ready", 2, 2, 1, 2)),
    "walk-works-and-looks-right-count": (
        store_of(walk={T1: walk_doc("works"), L1: walk_doc("looks-right")}), ("needs-you", 0, 2, 2, 2)),
    "walk-skip-is-not-walked": (store_of(walk={T1: walk_doc("skip")}), ("needs-you", 0, 2, 0, 2)),
    "works-on-a-look-stop-is-not-offered": (store_of(walk={L1: walk_doc("works")}), ("needs-you", 0, 2, 0, 2)),
    "looks-right-on-a-try-stop-is-not-offered": (store_of(walk={T1: walk_doc("looks-right")}), ("needs-you", 0, 2, 0, 2)),
    "walk-fix-no-longer-offered": (store_of(walk={T1: walk_doc("problem", "later")}), ("needs-you", 0, 2, 1, 2)),
    "walk-problem-with-a-retired-fix-keeps-a-merge-from-standing": (
        store_of(ACCEPTED, {T1: walk_doc("problem", "retired-fix")}, merge_doc()), ("needs-you", 2, 2, 1, 2)),
    "walk-problem-document-missing-shots-keeps-a-merge-from-standing": (
        store_of(ACCEPTED, {T1: {"answer": "problem", "fix": "follow-up", "note": ""}}, merge_doc()), ("needs-you", 2, 2, 1, 2)),
    "option-no-longer-offered": (store_of({"leftover": card_doc("option", "gone"), "closure": ACCEPT}), ("needs-you", 1, 2, 0, 2)),
    "accept-on-a-card-with-options-is-not-offered": (store_of({"leftover": ACCEPT, "closure": ACCEPT}), ("needs-you", 1, 2, 0, 2)),
    "a-null-answer": (store_of({"leftover": card_doc(None), "closure": card_doc(None)}), ("needs-you", 0, 2, 0, 2)),
    "wrong-shape-documents-are-ignored": (
        {"answers": {"leftover": dict(KEEP, extra=1), "closure": "accept"},
         "walk": {T1: {"answer": "works", "fix": None, "note": ""}, L1: dict(walk_doc("looks-right"), extra=1)},
         "verdict": {STATE_DIGEST: dict(merge_doc(), extra=1)}}, ("needs-you", 0, 2, 0, 2)),
    "a-bad-revision-is-ignored": (
        store_of({"leftover": card_doc("option", "keep-it", revision="XYZ"), "closure": ACCEPT}), ("needs-you", 1, 2, 0, 2)),
}


# The same rule on a stack sheet: one card (the leftover, whose third option sends back), a look stop and a try stop.
STACK_SHEET = json.dumps(built(STACK), indent=2).encode("utf-8")
STACK_DIGEST = hashlib.sha256(STACK_SHEET).hexdigest()
STACK_CARD, STACK_LOOK, STACK_TRY = "f-8bd7e2d907ef", "gift-card-table-18668f855294", "checkout-redeem-449ec5af939f"
STACK_TABLE = {
    "stack-ready": (store_of({STACK_CARD: KEEP}, {STACK_LOOK: walk_doc("looks-right"), STACK_TRY: walk_doc("works")},
                             merge_doc([f"answers/{STACK_CARD}@{REV_A}"], STACK_DIGEST), STACK_DIGEST), ("ready", 1, 1, 2, 2)),
    "stack-being-fixed": (store_of({STACK_CARD: card_doc("option", "fix-before-merge")}, verdict=merge_doc([f"answers/{STACK_CARD}@{REV_A}"], STACK_DIGEST),
                                   digest=STACK_DIGEST), ("being-fixed", 0, 1, 0, 2)),
}
SHEET_TABLE = [(STATE_SHEET, store, expected) for store, expected in STATE_TABLE.values()] + [(STACK_SHEET, *row) for row in STACK_TABLE.values()]


@pytest.mark.parametrize("sheet, store, expected", SHEET_TABLE, ids=[*STATE_TABLE, *STACK_TABLE])
def test_pr_state_truth_table(sheet, store, expected):
    # Axis: the state and the counts for every combination of answers, walk results and verdict the rule reads, on a pr sheet and on a stack sheet.
    state = pr_sheet.pr_state(sheet, store, WORDS)
    assert (state["state"], state["accepted"], state["total"], state["walked"], state["walkTotal"]) == expected
    assert list(state) == ["state", "accepted", "total", "walked", "walkTotal"]


def test_pr_state_reads_the_offered_answers_from_the_answer_words():
    # Axis: what a card offers comes from the prAnswers block given, so retiring Discuss there leaves a stored Discuss unanswered, as on the page.
    words = json.loads(json.dumps(ALL_WORDS["prAnswers"]))
    store = store_of({"leftover": KEEP, "closure": card_doc("discuss")})
    assert pr_sheet.pr_state(STATE_SHEET, store, WORDS, words)["accepted"] == 1
    words["withoutOptions"] = ["accept"]
    store = store_of({"leftover": KEEP, "closure": ACCEPT}, verdict=merge_doc())
    assert pr_sheet.pr_state(STATE_SHEET, store, WORDS, words)["state"] == "ready"
    words["withoutOptions"] = ["discuss"]
    state = pr_sheet.pr_state(STATE_SHEET, store, WORDS, words)
    assert (state["state"], state["accepted"]) == ("needs-you", 1)


def test_pr_state_reads_the_words_file_when_given_none():
    # Axis: with no words given, the walk fixes come from the words file, so a follow-up fix still lets a Merge stand.
    store = store_of(ACCEPTED, {T1: walk_doc("problem", "follow-up")}, merge_doc())
    assert pr_sheet.pr_state(STATE_SHEET, store)["state"] == "ready"


def test_pr_state_of_a_sheet_with_no_cards_and_no_walk():
    # Axis: with nothing to accept, a Merge that covers nothing stands, and without a Merge the PR needs the owner.
    sheet = json.dumps(built(SMALL), indent=2).encode("utf-8")
    digest = hashlib.sha256(sheet).hexdigest()
    assert pr_sheet.pr_state(sheet, {}, WORDS) == {"state": "needs-you", "accepted": 0, "total": 0, "walked": 0, "walkTotal": 0}
    merge = {"verdict": "merge", "note": "", "sheet": digest, "covers": []}
    assert pr_sheet.pr_state(sheet, {"verdict": {digest: merge}}, WORDS)["state"] == "ready"
    assert pr_sheet.pr_state(sheet, {"verdict": {digest: dict(merge, covers=[f"answers/ghost@{REV_A}"])}}, WORDS)["state"] == "needs-you"


# --- pr_state over a verdict carried forward ---

def carried_bytes(*chain):
    """A state sheet republished with its verdict carried forward from chain (the newest earlier sheet first), as bytes."""
    sheet = state_sheet()
    sheet["prSheet"]["previousCommit"] = "abcdef0"
    sheet["prSheet"]["carriedForward"] = {"sheets": [hashlib.sha256(b).hexdigest() for b in chain], "date": "2026-09-30",
                                          "moved": "The branch was brought current with main.", "whyNotMaterial": "Main added only a README line."}
    return json.dumps(sheet, indent=2).encode("utf-8")


def digest_of(sheet):
    return hashlib.sha256(sheet).hexdigest()


# A -> B -> C: B carried A's verdict, C carried B's (and so A's).
SHEET_A = STATE_SHEET
SHEET_B = carried_bytes(SHEET_A)
SHEET_C = carried_bytes(SHEET_B, SHEET_A)
A_ID, B_ID, C_ID = digest_of(SHEET_A), digest_of(SHEET_B), digest_of(SHEET_C)
NULLED = {"verdict": None, "note": "", "sheet": B_ID}


def verdicts_of(*held):
    """A store holding the accepted answers and these verdict documents, as (digest, document) pairs in the order they were saved."""
    return {"answers": ACCEPTED, "walk": {}, "verdict": dict(held)}


def state_of(sheet, store):
    return pr_sheet.pr_state(sheet, store, WORDS)["state"]


CARRIED_STATES = {
    "carried-merge-stands": (SHEET_B, verdicts_of((A_ID, merge_doc(digest=A_ID))), "ready"),
    "carried-merge-stands-two-revisions-on": (SHEET_C, verdicts_of((A_ID, merge_doc(digest=A_ID))), "ready"),
    "a-merge-on-the-middle-revision-stands": (SHEET_C, verdicts_of((B_ID, merge_doc(digest=B_ID))), "ready"),
    "own-merge-stands": (SHEET_B, verdicts_of((B_ID, merge_doc(digest=B_ID))), "ready"),
    "own-null-overrides": (SHEET_B, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, {"verdict": None, "note": "", "sheet": B_ID})), "needs-you"),
    "own-not-yet-overrides": (SHEET_B, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, {"verdict": "not-yet", "note": "", "sheet": B_ID})), "needs-you"),
    "withdrawal-on-the-middle-revision-saved-first": (SHEET_C, verdicts_of((B_ID, NULLED), (A_ID, merge_doc(digest=A_ID))), "needs-you"),
    "withdrawal-on-the-middle-revision-saved-last": (SHEET_C, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, NULLED)), "needs-you"),
    "not-yet-on-the-middle-revision": (SHEET_C, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, {**NULLED, "verdict": "not-yet"})), "needs-you"),
    "first-candidate-names-another-digest": (SHEET_B, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, merge_doc(digest=A_ID))), "needs-you"),
    "first-candidate-has-an-unknown-field": (SHEET_B, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, merge_doc(digest=B_ID, extra=1))), "needs-you"),
    "first-candidate-is-not-an-object": (SHEET_B, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, "merge")), "needs-you"),
    "the-found-carried-document-names-another-digest": (SHEET_C, verdicts_of((A_ID, merge_doc(digest=A_ID)), (B_ID, merge_doc(digest=A_ID))), "needs-you"),
    "the-found-carried-document-lacks-covers": (SHEET_B, verdicts_of((A_ID, {k: v for k, v in merge_doc(digest=A_ID).items() if k != "covers"})), "needs-you"),
    "changed-answers-end-the-carry": (
        SHEET_B, {**verdicts_of((A_ID, merge_doc(digest=A_ID))), "answers": {"leftover": KEEP, "closure": card_doc("accept", revision=REV_B)}}, "needs-you"),
    "a-card-no-longer-accepted-ends-the-carry": (
        SHEET_B, {**verdicts_of((A_ID, merge_doc(digest=A_ID))), "answers": {"leftover": KEEP, "closure": card_doc("discuss")}}, "needs-you"),
    "a-walk-problem-ends-the-carry": (
        SHEET_B, {**verdicts_of((A_ID, merge_doc(digest=A_ID))), "walk": {T1: walk_doc("problem")}}, "needs-you"),
    "an-older-digest-outside-the-chain-is-never-read": (SHEET_B, verdicts_of(("f" * 64, merge_doc(digest="f" * 64))), "needs-you"),
    "a-send-back-still-wins": (
        SHEET_B, {**verdicts_of((A_ID, merge_doc(digest=A_ID))), "answers": {"leftover": SEND_BACK, "closure": ACCEPT}}, "being-fixed"),
}


@pytest.mark.parametrize("sheet, store, expected", list(CARRIED_STATES.values()), ids=list(CARRIED_STATES))
def test_pr_state_reads_a_carried_verdict_through_the_chain(sheet, store, expected):
    # Bites on: pr_state reading only the sheet's own digest, falling through an intermediate document or a malformed first one to an older Merge, or skipping the stands-conditions for a carried Merge.
    # Axis: the first revision in the chain (own digest, then carriedForward.sheets) with any document decides; that document counts only when it fits and names its own revision; fail-closed edges 4, 5, 6.
    assert state_of(sheet, store) == expected


def test_a_sheet_republished_with_a_previous_commit_alone_never_reads_the_old_digest():
    # Bites on: pr_state reading a chain a sheet does not have (a material republish inheriting the old Merge).
    # Axis: fail-closed edge 7: with no carry the old digests are never read.
    material = state_sheet()
    material["prSheet"]["previousCommit"] = "abcdef0"
    sheet = json.dumps(material, indent=2).encode("utf-8")
    assert state_of(sheet, verdicts_of((A_ID, merge_doc(digest=A_ID)))) == "needs-you"
    assert state_of(sheet, verdicts_of((digest_of(sheet), merge_doc(digest=digest_of(sheet))))) == "ready"
    assert state_of(SHEET_A, verdicts_of((A_ID, merge_doc(digest=A_ID)))) == "ready"


def test_the_index_row_of_a_carried_sheet_is_ready_on_the_earlier_merge(tmp_path):
    # Bites on: the index reading a different rule from pr_state for a carried sheet.
    root = tmp_path / "in"
    (root / "pr").mkdir(parents=True)
    (root / "pr" / "sheet.json").write_bytes(SHEET_B)
    write_json(root / "pr" / "store.json", verdicts_of((A_ID, merge_doc(digest=A_ID))))
    source = write_json(root / "index.json", {"schema": "index-input/1", "questions": [], "mergeOrder": [1724],
                                              "prs": [{"number": 1724, "link": "https://sheets.example.test/pr-1724", "sheet": "pr/sheet.json", "store": "pr/store.json"}]})
    (tmp_path / "out").mkdir()
    done = index_cli(source, tmp_path / "out" / "index.json")
    assert done.returncode == 0, done.stdout
    rows = json.loads((tmp_path / "out" / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
    assert [(row["number"], row["state"]) for row in rows] == [(1724, "ready")]


# --- the index builder ---

def index_cli(source, out, answers=None, extra=()):
    args = [sys.executable, "-B", str(LIB / "pr_sheet.py"), "index", "--input", str(source), "--out", str(out), *extra]
    if answers is not None:
        args += ["--answers", str(answers)]
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def index_world(tmp_path):
    """The index fixture in tmp_path/in, with its three PRs' sheets built beside it: the small PR is ready, the big one
    is being fixed and the stack needs the owner. Returns the input's path and the folder to write the index into."""
    root = tmp_path / "in"
    shutil.copytree(FIXTURES / "elsewhere", root / "elsewhere")
    shutil.copy(FIXTURES / "index-input.json", root / "index-input.json")
    for folder, case in (("small", SMALL), ("big", BIG), ("stack", STACK)):
        (root / folder).mkdir()
        done = cli([FIXTURES / r for r in case[0]], FIXTURES / case[1], root / folder / "sheet.json")
        assert done.returncode == 0, done.stdout
        write_json(root / folder / "store.json", {})
    small = (root / "small" / "sheet.json").read_bytes()
    digest = hashlib.sha256(small).hexdigest()
    write_json(root / "small" / "store.json", {"verdict": {digest: {"verdict": "merge", "note": "", "sheet": digest, "covers": []}}})
    big = json.loads((root / "big" / "sheet.json").read_text(encoding="utf-8"))
    card = next(c for c in big["cards"] if any(o["sendsBack"] for o in c["options"]))
    sends_back = next(o["id"] for o in card["options"] if o["sendsBack"])
    write_json(root / "big" / "store.json", {"answers": {card["id"]: {"answer": "option", "optionId": sends_back, "note": "", "revision": REV_A}}})
    (tmp_path / "out").mkdir()
    return root / "index-input.json", tmp_path / "out"


def run_index(tmp_path, mutate=None, answers=None):
    source, out = index_world(tmp_path)
    if mutate:
        advisor = json.loads(source.read_text(encoding="utf-8"))
        mutate(advisor, source.parent)
        write_json(source, advisor)
    return index_cli(source, out / "index.json", answers), out


_INDEX_ROW_KEYS = ("number", "kind", "title", "link", "state", "accepted", "total", "walked", "walkTotal", "mergesAt", "caption")


def test_the_index_is_built_from_the_input_and_each_prs_sheet_and_store(tmp_path):
    # Axis: one row per PR from its own sheet and store, grouped by pr_state and ordered by the merge order, plus the unanswered question with its copied picture.
    done, out = run_index(tmp_path)
    assert done.returncode == 0, done.stdout
    sheet = json.loads((out / "index.json").read_text(encoding="utf-8"))
    picture = "pictures/" + hashlib.sha256((FIXTURES / "elsewhere" / "cart-empty.png").read_bytes()).hexdigest()[:pr_sheet.PICTURE_DIGEST] + ".png"
    assert json.loads(done.stdout) == {"ok": True, "out": str(out / "index.json"), "cards": 1, "pictures": [picture], "rows": 3}
    assert list(sheet) == ["schema", "kind", "title", "index", "cards"]
    assert (sheet["kind"], sheet["title"]) == ("index", INDEX_WORDS["title"])
    assert [(r["number"], r["kind"], r["title"], r["state"], r["mergesAt"]) for r in sheet["index"]["rows"]] == [
        (211, "pr", "Reword the receipt page", "ready", 1),
        (214, "pr", "Retry a failed payment", "being-fixed", 2),
        (4, "stack", "Gift cards", "needs-you", None)]
    small, big, stack = sheet["index"]["rows"]
    assert (small["accepted"], small["total"], small["walked"], small["walkTotal"]) == (0, 0, 0, 0)
    assert (big["accepted"], big["total"], big["walked"], big["walkTotal"]) == (0, 3, 0, 2)
    assert (stack["total"], stack["walkTotal"], stack["link"]) == (1, 2, "https://sheets.example.test/stack-4")
    assert list(small) == list(_INDEX_ROW_KEYS)
    (question,) = sheet["cards"]
    assert question["callKind"] == INDEX_WORDS["questionKind"] and question["warning"] is True
    assert question["images"] == [{"src": picture, "alt": "The order list of a disabled account", "caption": "Today it is empty"}]
    assert [o["id"] for o in question["options"]] == ["keep-visible", "hide-them"] and all("sendsBack" not in o for o in question["options"])
    assert question["recommendation"]["optionId"] == "keep-visible"
    assert (out / picture).read_bytes() == (FIXTURES / "elsewhere" / "cart-empty.png").read_bytes()
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def _caption_row(state, accepted=0, total=0, walked=0, walk_total=0, merges_at=None):
    return {"state": state, "accepted": accepted, "total": total, "walked": walked, "walkTotal": walk_total, "mergesAt": merges_at}


CAPTION_CASES = [
    (_caption_row("needs-you"), "Nothing to accept"),
    (_caption_row("needs-you", merges_at=1), "Nothing to accept · merges first"),
    (_caption_row("needs-you", 0, 2, 0, 4, merges_at=2), "0 of 2 accepted · 0 of 4 walked · merges second"),
    (_caption_row("needs-you", 1, 1, 0, 0, merges_at=10), "1 of 1 accepted · merges tenth"),
    (_caption_row("needs-you", 1, 1, 0, 0, merges_at=11), "1 of 1 accepted · merges at place 11"),
    (_caption_row("needs-you", 0, 0, 3, 3), "Nothing to accept · 3 of 3 walked"),
    (_caption_row("needs-you", 1, 2, merges_at=1.0), "1 of 2 accepted · merges first"),
    (_caption_row("being-fixed", 1, 2, merges_at=1), "1 of 2 accepted · Going back for a fix · a new sheet comes after it"),
    (_caption_row("ready", 2, 2, 1, 1, merges_at=1), "2 of 2 accepted · 1 of 1 walked · Merge verdict given"),
]


@pytest.mark.parametrize("row, caption", CAPTION_CASES, ids=[c for _, c in CAPTION_CASES])
def test_an_index_rows_caption(row, caption):
    # Axis: the caption is the accepted part (or Nothing to accept), the walked part when the PR has a walk, then the state part
    # (with the merge place on needs-you, a whole-number place read as an int), joined with " · ".
    assert pr_sheet._row_caption(row, INDEX_WORDS, accepting="nothing" if row["total"] == 0 else "unchecked") == caption


@pytest.mark.parametrize("walk_total, said", [(0, ""), (3, " · 3 of 3 walked")])
def test_a_zero_card_rows_caption_says_nothing_only_when_its_sheet_recorded_it(walk_total, said):
    # Bites on: the caption saying "Nothing to accept" of a row whose sheet never recorded that the PR bodies list none.
    # Axis: with no card, the caption reads nothingToAccept with the flag and acceptingUnchecked without it, whatever the walk.
    row = _caption_row("needs-you", 0, 0, 3 if walk_total else 0, walk_total)
    assert pr_sheet._row_caption(row, INDEX_WORDS, accepting="nothing") == INDEX_WORDS["nothingToAccept"] + said
    assert pr_sheet._row_caption(row, INDEX_WORDS, accepting="unchecked") == INDEX_WORDS["acceptingUnchecked"] + said
    assert pr_sheet._row_caption(row, INDEX_WORDS, accepting="canon") == INDEX_WORDS["acceptingCanon"] + said
    assert pr_sheet._row_caption(row, INDEX_WORDS) == INDEX_WORDS["acceptingUnchecked"] + said
    assert INDEX_WORDS["nothingToAccept"] != INDEX_WORDS["acceptingUnchecked"]
    assert pr_sheet._row_caption(dict(row, total=1), INDEX_WORDS) == "0 of 1 accepted" + said


def test_the_built_index_carries_each_rows_caption(tmp_path):
    # Axis: the builder stores the caption on every row, so the page and the chat prose have nothing to compose.
    done, out = run_index(tmp_path)
    assert done.returncode == 0, done.stdout
    rows = json.loads((out / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
    assert all(r["caption"] == pr_sheet._row_caption(r, INDEX_WORDS, accepting="nothing") and r["caption"] for r in rows)


def test_an_index_with_no_questions_and_no_prs_is_built(tmp_path):
    # Axis: empty questions, mergeOrder and prs are an index with no cards and no rows, not a refusal.
    done, out = run_index(tmp_path, lambda adv, _: adv.update(questions=[], mergeOrder=[], prs=[]))
    assert done.returncode == 0, done.stdout
    sheet = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert sheet["cards"] == [] and sheet["index"] == {"rows": []} and json.loads(done.stdout)["pictures"] == []
    assert check_sheet_problems(sheet) == []


def test_rows_beyond_the_merge_order_keep_the_order_of_prs(tmp_path):
    # Axis: with an empty merge order every row has no place and the rows stay in the order of prs; the order is by place otherwise.
    done, out = run_index(tmp_path, lambda adv, _: adv.update(mergeOrder=[]))
    assert done.returncode == 0, done.stdout
    rows = json.loads((out / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
    assert [(r["number"], r["mergesAt"]) for r in rows] == [(4, None), (214, None), (211, None)]
    done, out = run_index(tmp_path / "again", lambda adv, _: adv.update(mergeOrder=[214, 211]))
    rows = json.loads((out / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
    assert [(r["number"], r["mergesAt"]) for r in rows] == [(214, 1), (211, 2), (4, None)]


def drop_key(key):
    return lambda adv, _: adv.pop(key)


def edit_question(change):
    return lambda adv, _: change(adv["questions"][0])


def edit_pr(change, n=0):
    return lambda adv, root: change(adv["prs"][n], root)


def point_at(key, text=None, content=None, source=None):
    """Changes the stack entry to name a new file in its folder: text as it is, content as JSON, or a copy of source."""
    def change(entry, root):
        target = root / "stack" / "other.json"
        if source is not None:
            shutil.copy(source, target)
        elif text is not None:
            target.write_text(text, encoding="utf-8")
        elif content is not None:
            write_json(target, content)
        entry[key] = "stack/other.json"
    return edit_pr(change)


INDEX_REFUSALS = {
    "unknown-key": (lambda adv, _: adv.update(extra=1), "the index input has an unknown key extra"),
    "missing-questions": (drop_key("questions"), "the index input is missing questions"),
    "missing-prs": (drop_key("prs"), "the index input is missing prs"),
    "wrong-schema": (lambda adv, _: adv.update(schema="index-input/2"), "the index input schema must be index-input/1"),
    "duplicate-question-id": (lambda adv, _: adv["questions"].append(dict(adv["questions"][0])), "repeats the id old-orders"),
    "option-with-sends-back": (edit_question(lambda q: q["options"][0].update(sendsBack=False)), "has an unknown key sendsBack"),
    "no-options": (edit_question(lambda q: q.update(options=[])), "question old-orders needs at least one option"),
    "duplicate-option-id": (edit_question(lambda q: q["options"][1].update(id="keep-visible")), "repeats the id keep-visible"),
    "recommendation-names-no-option": (edit_question(lambda q: q["recommendation"].update(optionId="ghost")), "is not one of its options"),
    "question-picture-missing": (edit_question(lambda q: q["pictures"][0].update(path="elsewhere/nothing.png")),
                                 "question old-orders picture 1 (elsewhere/nothing.png) is a link, or cannot be read"),
    "question-picture-a-link": (edit_question(lambda q: q["pictures"][0].update(path="https://example.com/a.png")),
                                "question old-orders picture 1 (https://example.com/a.png) is a link, or cannot be read"),
    "question-picture-wrong-suffix": (edit_question(lambda q: q["pictures"][0].update(path="index-input.json")), "cannot be read"),
    "merge-order-names-a-missing-pr": (lambda adv, _: adv.update(mergeOrder=[211, 999]), "mergeOrder names PR #999, which is not in prs"),
    "merge-order-repeats": (lambda adv, _: adv.update(mergeOrder=[211, 211]), "mergeOrder names a PR more than once"),
    "merge-order-not-a-list": (lambda adv, _: adv.update(mergeOrder=211), "mergeOrder must be a list"),
    "duplicate-pr-number": (lambda adv, _: adv["prs"].append(dict(adv["prs"][0])), "repeats the number 4"),
    "http-link": (edit_pr(lambda pr, _: pr.update(link="http://sheets.example.test/stack-4")), "needs link to be an https link"),
    "link-with-a-space": (edit_pr(lambda pr, _: pr.update(link="https://sheets.example.test/a b")), "needs link to be an https link"),
    "number-mismatch": (lambda adv, _: (adv["prs"][1].update(number=215), adv.update(mergeOrder=[211, 215])),
                        "its prSheet.number is 214, not 215"),
    "sheet-missing": (edit_pr(lambda pr, _: pr.update(sheet="stack/nothing.json")), "stack/nothing.json could not be read as JSON"),
    "sheet-not-json": (point_at("sheet", text="{not json"), "stack/other.json could not be read as JSON"),
    "sheet-not-a-pr-sheet": (point_at("sheet", source=THEME / "sample-sheet.json"), "it is a remainder sheet, not a pr or stack sheet"),
    "sheet-fails-the-check": (point_at("sheet", content={"schema": "superheroes-sheet/1"}), "PR #4: stack/other.json: "),
    "store-missing": (edit_pr(lambda pr, _: pr.update(store="stack/nothing.json")), "stack/nothing.json could not be read as JSON"),
    "store-not-json": (point_at("store", text="{not json"), "stack/other.json could not be read as JSON"),
    "store-unknown-key": (point_at("store", content={"extra": {}}), "has an unknown key extra"),
    "store-collection-not-an-object": (point_at("store", content={"answers": []}), "answers must be an object"),
    "store-not-an-object": (point_at("store", content=[]), "must be an object"),
}


@pytest.mark.parametrize("mutate, expected", INDEX_REFUSALS.values(), ids=INDEX_REFUSALS.keys())
def test_the_index_refuses_what_it_cannot_trust_and_writes_nothing(tmp_path, mutate, expected):
    # Axis: each fail-closed edge of the index input, a PR's sheet and a PR's store is one refusal problem that names it, exit 1, no data file and no pictures folder.
    done, out = run_index(tmp_path, mutate)
    result = json.loads(done.stdout)
    assert done.returncode == 1 and result["ok"] is False
    assert [p for p in result["problems"] if expected in p], result["problems"]
    assert list(out.iterdir()) == []


def test_a_refusal_after_a_question_picture_was_found_leaves_no_picture_behind(tmp_path):
    # Axis: a question with a good picture and a PR whose sheet is unreadable is refused with the pictures folder never created.
    done, out = run_index(tmp_path, edit_pr(lambda pr, _: pr.update(sheet="stack/nothing.json")))
    assert done.returncode == 1 and not (out / "pictures").exists() and not (out / "index.json").exists()


def test_a_failed_write_removes_the_question_pictures_this_run_created(tmp_path, monkeypatch, capsys):
    # Axis: when the index cannot be written after its question picture was, the run exits 1 and removes the picture and the folder it created.
    source, out = index_world(tmp_path)
    real = os.replace

    def replace(src, dst):
        if str(dst) == str(out / "index.json"):
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(pr_sheet.os, "replace", replace)
    code = pr_sheet.main(["index", "--input", str(source), "--out", str(out / "index.json")])
    assert code == 1 and json.loads(capsys.readouterr().out) == {"ok": False, "problems": ["disk full"]}
    assert list(out.iterdir()) == []


ANSWER_OF_OLD_ORDERS = {"answer": "option", "optionId": "hide-them", "note": "", "revision": REV_A}


def answers_file(tmp_path, doc, key="old-orders"):
    return write_json(tmp_path / "answers.json", {"answers": {key: doc}})


@pytest.mark.parametrize("doc", [ANSWER_OF_OLD_ORDERS, {"answer": "something-else", "optionId": None, "note": "Ask support first"}],
                         ids=["an-option", "something-else"])
def test_an_answered_question_leaves_the_index(tmp_path, doc):
    # Axis: --answers holding an offered option, or Something else, for the question drops it, with its picture, and the rows stay.
    done, out = run_index(tmp_path, answers=answers_file(tmp_path, doc))
    assert done.returncode == 0, done.stdout
    result = json.loads(done.stdout)
    assert result["cards"] == 0 and result["pictures"] == [] and result["rows"] == 3
    assert json.loads((out / "index.json").read_text(encoding="utf-8"))["cards"] == []
    assert not (out / "pictures").exists()


@pytest.mark.parametrize("doc, key", [
    ({"answer": None, "optionId": None, "note": "", "revision": REV_A}, "old-orders"),
    (dict(ANSWER_OF_OLD_ORDERS, extra=1), "old-orders"),
    ({"answer": "option", "optionId": "gone", "note": ""}, "old-orders"),
    ({"answer": "option", "optionId": None, "note": ""}, "old-orders"),
    ({"answer": "accept", "optionId": None, "note": ""}, "old-orders"),
    ("hide-them", "old-orders"),
    (ANSWER_OF_OLD_ORDERS, "another-question"),
], ids=["null-answer", "wrong-shape", "option-no-longer-offered", "option-without-id", "accept", "not-an-object", "answer-for-another-id"])
def test_an_answer_that_does_not_fit_leaves_the_question_in(tmp_path, doc, key):
    # Axis: a null answer, a wrong-shape document, an option the question no longer has and an answer for another id each leave the question on the index.
    done, out = run_index(tmp_path, answers=answers_file(tmp_path, doc, key))
    assert done.returncode == 0, done.stdout
    assert json.loads(done.stdout)["cards"] == 1 and len(json.loads(done.stdout)["pictures"]) == 1


def test_an_empty_answers_store_keeps_the_question_and_other_keys_are_refused(tmp_path):
    # Axis: --answers holding {} keeps the question; a key outside answers, verdict and walk, a file that is not JSON and a missing file are refused.
    done, _ = run_index(tmp_path / "a", answers=write_json(tmp_path / "empty.json", {}))
    assert done.returncode == 0 and json.loads(done.stdout)["cards"] == 1
    for name, content, expected in (("extra", {"extra": {}}, "the answers file has an unknown key extra"),
                                    ("list", [], "the answers file must be an object")):
        done, _ = run_index(tmp_path / name, answers=write_json(tmp_path / (name + ".json"), content))
        assert done.returncode == 1 and expected in json.loads(done.stdout)["problems"][0]
    (tmp_path / "bad.json").write_text("", encoding="utf-8")
    for name in ("bad", "missing"):
        done, _ = run_index(tmp_path / name, answers=tmp_path / (name + ".json"))
        assert done.returncode == 1 and "could not be read as JSON" in json.loads(done.stdout)["problems"][0]


def test_index_takes_no_record_and_build_takes_no_answers(tmp_path):
    # Axis: --record is refused on index and --answers on build with a usage error (exit 2) that writes nothing; build still needs --record.
    source, out = index_world(tmp_path)
    done = index_cli(source, out / "index.json", extra=("--record", str(FIXTURES / "record-big.json")))
    assert done.returncode == 2 and "--record is only for build" in done.stderr and list(out.iterdir()) == []
    base = [sys.executable, "-B", str(LIB / "pr_sheet.py"), "build", "--input", str(FIXTURES / "input-big.json"), "--out", str(out / "sheet.json"),
            *body_args([FIXTURES / "record-big.json"])]
    done = subprocess.run([*base, "--record", str(FIXTURES / "record-big.json"), "--answers", str(source)], capture_output=True, text=True)
    assert done.returncode == 2 and "--answers is only for index" in done.stderr
    done = subprocess.run(base, capture_output=True, text=True)
    assert done.returncode == 2 and "--record" in done.stderr and list(out.iterdir()) == []


def test_the_input_fixture_is_the_documented_shape():
    # Axis: the fixture names exactly the keys the builder's docstring lists for the index input.
    advisor = load("index-input.json")
    assert list(advisor) == ["schema", "questions", "mergeOrder", "prs"]
    assert list(advisor["questions"][0]) == ["id", "question", "context", "options", "recommendation", "pictures"]
    assert list(advisor["prs"][0]) == ["number", "link", "sheet", "store"]
    for key in ("index-input/1", "mergeOrder", "{number, link, sheet, store}"):
        assert key in pr_sheet.__doc__


# --- craft determinations: a left-for-owner finding the advisor re-graded as craft at vet ---

GROUND, WHY = "fail-direction is always craft", "The retry fails closed either way, so there is nothing for the owner to weigh."
MINE = {"answer": "option", "optionId": WORDS["mineOption"]["id"], "note": "", "revision": REV_A}
CLEARED = {"answer": None, "optionId": None, "note": ""}
THIRD = "Nobody can see which orders were retried"


def determination(ground=GROUND, reason=WHY):
    return {"ground": ground, "reason": reason}


def regrade(advisor, *keys, **more):
    """Moves each leftovers entry named to the craft determinations."""
    for key in keys:
        advisor["leftovers"].pop(key)
        advisor.setdefault("craftDeterminations", {})[key] = determination(**more)
    return advisor


def three_left():
    """The big record with a third left-for-owner finding, F9, and its leftovers entry."""
    records, advisor = bundle(BIG)
    extra = copy.deepcopy(records[0]["findings"][6])
    extra.update(id="F9", findingKey="retry/no-audit-trail", title=THIRD)
    records[0]["findings"].append(extra)
    advisor["leftovers"]["F9"] = copy.deepcopy(advisor["leftovers"]["F7"])
    return records, advisor


def test_a_regraded_finding_is_no_card_and_is_listed_as_decided_for_you():
    # Bites on: a determined left-for-owner finding still becoming a card, being listed out of record order, or losing its ground or reason.
    # Axis: the invariant, every left-for-owner finding is a card or a decidedForYou entry; three findings with two determined give one card and two entries.
    records, advisor = three_left()
    full = build(records, advisor)
    assert len(leftover_cards(full)) == 3 and "decidedForYou" not in full["prSheet"]
    regrade(advisor, "F6", "F7")
    sheet = build(records, advisor)
    assert [c["question"] for c in leftover_cards(sheet)] == [THIRD]
    assert sheet["cards"] == [c for c in full["cards"] if c["question"] not in ("Customers are not told a retry happened", "A payment that fails three times ends with no email")]
    decided = sheet["prSheet"]["decidedForYou"]
    assert [(e["finding"], e["title"], e["ground"], e["reason"]) for e in decided] == [
        ("retry/no-notice", "Customers are not told a retry happened", GROUND, WHY),
        ("retry/no-final-email", "A payment that fails three times ends with no email", GROUND, WHY)]
    assert all(set(e) == {"id", "finding", "title", "ground", "reason"} and re.fullmatch(r"d-[0-9a-f]{12}", e["id"]) for e in decided)
    assert {**sheet, "cards": None, "prSheet": {k: v for k, v in sheet["prSheet"].items() if k != "decidedForYou"}} == {**full, "cards": None}
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_a_sheet_with_no_determination_has_no_decided_for_you():
    # Axis: the field is emitted only when non-empty, so every existing sheet stays as it was.
    assert all("decidedForYou" not in built(case)["prSheet"] for case in (BIG, SMALL, STACK, CLOSES, WALK, TWIN))


def _ambiguous(records, advisor):
    left = [f for f in records[0]["findings"] if f["outcome"] == "left-for-owner"]
    left[1]["id"] = left[0]["id"]
    entry = {"why": "w", "context": "c", "options": "none"}
    advisor["leftovers"] = {left[0]["findingKey"]: entry, left[1]["findingKey"]: entry}
    advisor["craftDeterminations"] = {left[0]["id"]: determination()}


GROUND_LINE = "craftDeterminations F6: ground must be a non-empty string; a re-grade names the owner-vs-craft line's ground"
DETERMINATION_REFUSALS = [
    pytest.param(lambda r, a: a["craftDeterminations"]["F6"].update(ground=""), GROUND_LINE, id="E1-empty-ground"),
    pytest.param(lambda r, a: a["craftDeterminations"]["F6"].pop("ground"), GROUND_LINE, id="E2-missing-ground"),
    pytest.param(lambda r, a: a["craftDeterminations"]["F6"].update(ground=5), GROUND_LINE, id="E3-non-string-ground"),
    pytest.param(lambda r, a: a["craftDeterminations"]["F6"].update(reason=" "), "craftDeterminations F6: reason must be a non-empty string", id="E4-empty-reason"),
    pytest.param(lambda r, a: a["craftDeterminations"]["F6"].update(extra=1), "craftDeterminations F6 has an unknown key extra", id="E5-unknown-value-key"),
    pytest.param(lambda r, a: a["craftDeterminations"].update(F99=determination()), "craftDeterminations key 'F99' names no left-for-owner finding", id="E6-names-no-finding"),
    pytest.param(_ambiguous, "craftDeterminations key 'F6' names 2 left-for-owner findings; use a finding's findingKey", id="E7-ambiguous-key"),
    pytest.param(lambda r, a: a["craftDeterminations"].update(F7=determination()),
                 "left-for-owner finding 'A payment that fails three times ends with no email' on PR #214 has both a leftovers entry and a craft determination; give one",
                 id="E8-both-entries"),
    pytest.param(lambda r, a: a["craftDeterminations"].pop("F6"),
                 "left-for-owner finding 'Customers are not told a retry happened' on PR #214 has no leftovers entry (key 'retry/no-notice'); "
                 "give it why, context and options, or a craft determination", id="E9-neither-entry"),
    pytest.param(lambda r, a: a.__setitem__("craftDeterminations", []), "craftDeterminations must be an object", id="E10-not-an-object"),
]


@pytest.mark.parametrize("mutate, expected", DETERMINATION_REFUSALS)
def test_a_regrade_that_is_not_given_whole_is_refused(mutate, expected):
    # Bites on: a re-grade with no ground, no reason, a stray key, a key naming no finding or several, both a card and a determination, neither, or the wrong shape being built into a sheet.
    # Axis: no silent re-grade, each fail-closed edge of the input is a named refusal line.
    records, advisor = bundle(BIG)
    regrade(advisor, "F6")
    mutate(records, advisor)
    assert expected in problems_of(records, advisor)


def test_a_refusal_lists_every_determination_problem_together():
    # Axis: the determination problems are collected with the others, never raised one at a time.
    records, advisor = bundle(BIG)
    regrade(advisor, "F6")
    advisor["craftDeterminations"]["F6"]["ground"] = ""
    advisor["craftDeterminations"]["F99"] = determination()
    advisor["summary"] = ""
    problems = problems_of(records, advisor)
    assert {GROUND_LINE, "craftDeterminations key 'F99' names no left-for-owner finding", "summary must be a non-empty string"} <= set(problems)


def test_a_determination_id_depends_on_the_pr_and_the_finding_only():
    # Bites on: the entry id hashing the ground, the reason or the title, so a republish that rewords loses a saved reclaim; or two findings sharing an id.
    records, advisor = three_left()
    regrade(advisor, "F6", "F7")
    first = [e["id"] for e in build(records, advisor)["prSheet"]["decidedForYou"]]
    advisor["craftDeterminations"]["F6"] = determination("a different ground", "a reworded reason")
    records[0]["findings"][5]["title"] = "Customers are never told"
    assert [e["id"] for e in build(records, advisor)["prSheet"]["decidedForYou"]] == first
    assert len(set(first)) == 2
    assert first[0] == pr_sheet.card_id("d-", 214, "retry/no-notice", "decided-for-you")


def test_twin_stack_findings_decided_get_different_ids_and_carry_their_pr():
    # Axis: on a stack the finding key is "<pr>:<key>", each entry names its PR, and the same finding on two PRs gives two ids.
    records, advisor = bundle(TWIN)
    advisor["craftDeterminations"] = {key: determination() for key in advisor["leftovers"]}
    advisor["leftovers"] = {}
    sheet = build(records, advisor)
    decided = sheet["prSheet"]["decidedForYou"]
    assert sheet["cards"] == []
    assert [(e["pr"], e["finding"]) for e in decided] == [(241, "241:cards/kept-after-close"), (242, "242:cards/kept-after-close")]
    assert decided[0]["id"] != decided[1]["id"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def decided_world(*keys):
    """Records, input and the sheet built with `keys` re-graded, as the earlier sheet of a carry."""
    records, advisor = three_left()
    regrade(advisor, *keys)
    return records, advisor, build(records, advisor)


def carry_decided(records, advisor, earlier):
    carry_input(advisor, {"214": "2" * 40})
    return records, advisor, sheet_bytes(earlier)


def test_a_carried_sheet_inherits_the_earlier_determinations_with_no_input_entry():
    # Bites on: a carry that drops the earlier sheet's decided entries (turning them into missing cards), or rewrites them.
    # Axis: the carried sheet's decidedForYou equals the earlier one's when the input omits craftDeterminations.
    records, advisor, earlier = decided_world("F6", "F7")
    advisor.pop("craftDeterminations")
    carried = build(*carry_decided(records, advisor, earlier))
    assert carried["prSheet"]["decidedForYou"] == earlier["prSheet"]["decidedForYou"] and len(carried["prSheet"]["decidedForYou"]) == 2
    assert carried["cards"] == earlier["cards"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(carried)) == [] and check_sheet_problems(carried) == []


def test_a_carry_that_restates_the_determinations_unchanged_builds():
    # Axis: an input determination equal to the earlier entry is accepted.
    records, advisor, earlier = decided_world("F6", "F7")
    carried = build(*carry_decided(records, advisor, earlier))
    assert carried["prSheet"]["decidedForYou"] == earlier["prSheet"]["decidedForYou"]


def test_a_carry_drops_an_earlier_entry_whose_finding_is_no_longer_left_for_owner():
    # Axis: an earlier entry whose finding the record no longer leaves for the owner is dropped with no problem.
    records, advisor, earlier = decided_world("F6", "F7")
    advisor.pop("craftDeterminations")
    records[0]["findings"][5].update(outcome="craft", reason="settled")
    carried = build(*carry_decided(records, advisor, earlier))
    assert [e["finding"] for e in carried["prSheet"]["decidedForYou"]] == ["retry/no-final-email"]


CARRY_DECIDED_REFUSALS = [
    pytest.param(lambda a: a["craftDeterminations"].update(F6=determination(reason="reworded")),
                 "craftDeterminations F6: a carried sheet keeps the earlier sheet's determination unchanged; change it on an unsigned republish", id="E11-changed"),
    pytest.param(lambda a: (a["leftovers"].pop("F9"), a["craftDeterminations"].update(F9=determination())),
                 "craftDeterminations F9: a carried sheet cannot add a determination; add it on an unsigned republish", id="E12-added"),
    pytest.param(lambda a: a["leftovers"].update(F6=copy.deepcopy(a["leftovers"]["F9"])),
                 "leftovers F6: a carried sheet cannot turn a decided-for-you entry back into a card; do that on an unsigned republish", id="E13-leftovers-over-decided"),
]


@pytest.mark.parametrize("edit, expected", CARRY_DECIDED_REFUSALS)
def test_a_carry_cannot_change_what_was_decided(edit, expected):
    # Bites on: a carried sheet that changes, adds or reverses a determination, which would carry a Merge over a call the owner never saw.
    # Axis: each is a named refusal that points to an unsigned republish.
    records, advisor, earlier = decided_world("F6", "F7")
    advisor["craftDeterminations"] = {"F6": determination(), "F7": determination()}
    edit(advisor)
    assert expected in problems_of(*carry_decided(records, advisor, earlier))


def reclaim_input():
    """The big case without its items and walk, so the leftovers are its only cards."""
    records, advisor = bundle(BIG)
    del advisor["items"], advisor["walk"]
    return records, advisor


def reclaim_world():
    """A pr sheet with one card (F7, kept) and F6 decided for the owner; returns the sheet bytes, the decided id and a store maker."""
    records, advisor = reclaim_input()
    regrade(advisor, "F6")
    sheet = build(records, advisor)
    raw = sheet_bytes(sheet)
    digest, card, entry = hashlib.sha256(raw).hexdigest(), sheet["cards"][0]["id"], sheet["prSheet"]["decidedForYou"][0]["id"]

    def store(*, mine=None, picked=None, merge=True):
        answers = {card: card_doc("option", picked or "keep-it")}
        if mine is not None:
            answers[entry] = mine
        verdict = {digest: merge_doc([f"answers/{card}@{REV_A}"], digest)} if merge else {}
        return {"answers": answers, "walk": {}, "verdict": verdict}
    return raw, entry, store


def test_taking_a_decided_finding_back_keeps_the_pr_out_of_ready_and_the_card_comes_back_on_rebuild():
    # Bites on: pr_state ignoring a stored mine answer so a Merge stands over a finding the owner took back; a rebuild that keeps the entry or loses the card.
    # Axis: the reversal sequence, decided -> owner takes it back -> advisor moves it to leftovers -> it is a card and no longer decided.
    raw, entry, store = reclaim_world()
    assert pr_sheet.pr_state(raw, store(), WORDS)["state"] == "ready"
    taken = pr_sheet.pr_state(raw, store(mine=MINE), WORDS)
    assert (taken["state"], taken["accepted"], taken["total"]) == ("needs-you", 1, 1)
    records, advisor = reclaim_input()
    again = build(records, advisor)
    assert len(again["cards"]) == 2 and "decidedForYou" not in again["prSheet"]


@pytest.mark.parametrize("mine, picked, merge, expected", [
    pytest.param(None, None, True, "ready", id="E15-no-document"),
    pytest.param(CLEARED, None, True, "ready", id="E16-cleared-null-document"),
    pytest.param(MINE, None, True, "needs-you", id="E17-mine-document"),
    pytest.param({"answer": "option", "optionId": WORDS["mineOption"]["id"]}, None, True, "needs-you", id="E18-malformed-no-note"),
    pytest.param("make-this-mine", None, True, "needs-you", id="E18-malformed-bare-string"),
    pytest.param(None, None, False, "needs-you", id="no-merge-no-reclaim"),
    pytest.param(MINE, None, False, "needs-you", id="E19-reclaim-and-no-merge"),
    pytest.param(MINE, "fix-before-merge", True, "being-fixed", id="E20-reclaim-beside-a-send-back"),
])
def test_pr_state_reads_a_decided_entrys_stored_document(mine, picked, merge, expected):
    # Bites on: a stored reclaim, malformed ones included, leaving the PR ready; a cleared one blocking it; a reclaim hiding a send-back.
    # Axis: absent and well-formed null are not a reclaim; any other present value is; a send-back still wins over needs-you.
    raw, entry, store = reclaim_world()
    state = pr_sheet.pr_state(raw, store(mine=mine, picked=picked, merge=merge), WORDS)
    assert state["state"] == expected
    assert list(state) == ["state", "accepted", "total", "walked", "walkTotal"] and state["total"] == 1


# --- collector items: a decision tied to one PR rides that PR's sheet as an option card ---


def collector_sheet():
    return built(COLLECTOR)


def test_a_collector_item_is_built_as_an_option_card_with_the_spine_and_lettered_options():
    # Axis: each collector item is one card, in input order, with its collector number, the spine in the leftover's order, lettered option labels and a recommendation that names its letter.
    # Bites on: a label shown without its letter, a recommendation without its letter, a kind that omits the number, a spine out of order, or items built out of input order.
    advisor, cards = load("input-collector.json"), collector_sheet()["cards"]
    assert len(cards) == len(advisor["collectorItems"]) == 2
    for card, item in zip(cards, advisor["collectorItems"]):
        assert card["id"].startswith("k-")
        assert card["callKind"] == fill("collectorKind", number=item["number"]) and str(item["number"]) in card["callKind"]
        assert card["question"] == item["title"]
        assert [s["title"] for s in card["context"]] == [WORDS["whyYours"], WORDS["whatHappened"], WORDS["ifLeft"]]
        assert [s["blocks"] for s in card["context"]] == [[{"paragraph": item[k]}] for k in ("why", "context", "ifLeft")]
        assert [o["id"] for o in card["options"]] == ["a", "b", "c"]
        assert [o["label"] for o in card["options"]] == [fill("collectorOption", letter=o["id"], label=o["label"]) for o in item["options"]]
        assert all(o["label"].startswith(f"{o['id']}. ") for o in card["options"])
        assert [(o["consequence"], o["sendsBack"]) for o in card["options"]] == [(o["consequence"], o["sendsBack"]) for o in item["options"]]
        rec = item["recommendation"]
        assert card["recommendation"] == {"text": fill("collectorRecommendation", letter=rec["optionId"], text=rec["text"]),
                                          "reason": rec["reason"], "optionId": rec["optionId"]}
        assert card["recommendation"]["text"].startswith(rec["optionId"])
        assert all(not o["label"].startswith(o["id"]) for o in item["options"]) and not rec["text"].startswith(rec["optionId"])


def test_collector_cards_follow_the_input_order_not_the_number_order():
    # Axis: collector cards come out in the order the input lists them, whatever the item numbers are.
    # Bites on: collectorItems sorted by number (the fixture lists them ascending, so only a reversed input can tell).
    records, advisor = bundle(COLLECTOR)
    advisor["collectorItems"].reverse()
    assert [i["number"] for i in advisor["collectorItems"]] == [1501, 1435]
    cards = [c for c in build(records, advisor)["cards"] if c["id"].startswith("k-")]
    assert [c["question"] for c in cards] == [i["title"] for i in advisor["collectorItems"]]
    assert [c["callKind"] for c in cards] == [fill("collectorKind", number=i["number"]) for i in advisor["collectorItems"]]


def test_the_prose_of_a_collector_card_shows_each_option_letter_once():
    # Axis: in the chat prose an option line shows its letter once, and an ordinary card's option line keeps its shape.
    # Bites on: the prose renderer prefixing a letter to a label that already opens with it ("a. a. ...").
    sheet = collector_sheet()
    assert sheet_prose.check_sheet(sheet) == []
    lines = sheet_prose.render(sheet).splitlines()
    assert not any(doubled in line for line in lines for doubled in ("a. a. ", "b. b. ", "c. c. "))
    for item in load("input-collector.json")["collectorItems"]:
        for letter, option in zip("abc", item["options"]):
            assert "     - %s. %s: %s" % (letter, option["label"], option["consequence"]) in lines
    big = sheet_prose.render(built(BIG)).splitlines()
    assert "     - a. Ten minutes: Orders wait up to ten minutes for a payment to clear." in big


@pytest.mark.parametrize("label, shown", [
    pytest.param("b. x", "a. b. x", id="E1-another-letter-still-prefixed"),
    pytest.param("a thing", "a. a thing", id="E3-letter-without-dot-space-still-prefixed"),
    pytest.param("a. x", "a. x", id="own-letter-shown-once"),
])
def test_the_prose_prefixes_a_label_unless_it_already_opens_with_its_own_letter(label, shown):
    # Axis: only a label opening with exactly its own position's letter and ". " is shown as given.
    # Bites on: a looser test (any letter, or the letter alone) leaving a label without its own letter.
    card = {"callKind": "k", "warning": False, "question": "q", "context": [], "images": [],
            "options": [{"id": "a", "label": label, "consequence": "c"}]}
    assert "     - %s: c" % shown in sheet_prose._render_card(1, card)


def test_collector_cards_sit_after_the_items_and_before_the_closure_card():
    # Axis: the cards run leftovers, items, collector items, then the closure card.
    # Bites on: collector cards appended after the closure card or before the items.
    records, advisor = bundle(CLOSES)
    advisor["collectorItems"] = load("input-collector.json")["collectorItems"]
    rank = {"f-": 0, "i-": 1, "k-": 2, "c-": 3}
    prefixes = [c["id"][:2] for c in build(records, advisor)["cards"]]
    assert [rank[p] for p in prefixes] == sorted(rank[p] for p in prefixes)
    assert prefixes.count("k-") == 2 and prefixes[-1] == "c-"


def collector_store(sheet, picks, covers=None, verdict="merge"):
    ids = [c["id"] for c in sheet["cards"]]
    answers = {i: card_doc("option", pick) for i, pick in zip(ids, picks) if pick}
    raw = json.dumps(sheet, indent=2).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    covered = [f"answers/{i}@{REV_A}" for i in (ids if covers is None else covers)]
    return raw, {"answers": answers, "walk": {}, "verdict": {digest: merge_doc(covered, digest)} if verdict else {}}


def test_collector_cards_are_answered_and_covered_like_any_card():
    # Axis: the PR's state counts the collector cards, a Merge covering exactly their answers makes it ready, and a pick that sends back makes it being-fixed.
    # Bites on: collector cards missing from the total, a Merge standing over an unanswered collector card, or a send-back option not read.
    sheet = collector_sheet()
    ids = [c["id"] for c in sheet["cards"]]
    send_back = next(o["id"] for o in sheet["cards"][0]["options"] if o["sendsBack"])
    keep = next(o["id"] for o in sheet["cards"][0]["options"] if not o["sendsBack"])
    raw, store = collector_store(sheet, [None, None], verdict=None)
    assert pr_sheet.pr_state(raw, store, WORDS) == {"state": "needs-you", "accepted": 0, "total": 2, "walked": 0, "walkTotal": 0}
    raw, store = collector_store(sheet, [keep, keep])
    assert pr_sheet.pr_state(raw, store, WORDS) == {"state": "ready", "accepted": 2, "total": 2, "walked": 0, "walkTotal": 0}
    raw, store = collector_store(sheet, [keep, None])
    assert pr_sheet.pr_state(raw, store, WORDS)["state"] == "needs-you"
    raw, store = collector_store(sheet, [keep, keep], covers=ids[:1])
    assert pr_sheet.pr_state(raw, store, WORDS)["state"] == "needs-you"
    raw, store = collector_store(sheet, [keep, send_back])
    assert pr_sheet.pr_state(raw, store, WORDS)["state"] == "being-fixed"


def test_a_collector_card_naming_its_own_number_is_not_refused():
    # Axis: a card that carries its own options is never refused for mentioning a list item by number.
    # Bites on: the pointer scan reading cards that have options.
    advisor = load("input-collector.json")
    assert "item 1435 on your list" in advisor["collectorItems"][0]["context"]
    assert "item 1435 on your list" in json.dumps(collector_sheet()["cards"][0]["context"])


POINTER_TITLE = "Disclosures"
POINTER_ITEM = {"id": "accepting", "kind": "What you're accepting", "title": POINTER_TITLE, "options": "none"}
POINTER_PROBLEM = ("items accepting: card {title!r} sends the owner to a list item ({found!r}) instead of carrying that decision's options; "
                   "put the decision on this sheet as a collectorItems card, or give this card its own options")


def with_pointer_item(text, **more):
    def edit(advisor):
        advisor["items"].append({**POINTER_ITEM, "ifLeft": text, **more})
    return edit


def with_pointer_on_retry(text):
    def edit(advisor):
        advisor["items"][0]["ifLeft"] = text
    return edit


def with_pointer_on_f7(text):
    def edit(advisor):
        advisor["leftovers"]["F7"]["context"] = text
    return edit


# Each refused row's text matches exactly one pattern alternative, except the field case, which matches two.
REFUSED_POINTERS = [
    pytest.param("Whether to change that is decision item 1435.", "decision item 1435", id="refused-decision-item"),
    pytest.param("see item 1435 on your list", "item 1435 on your list", id="refused-item-on-your-list"),
    pytest.param("collector #1435", "collector #1435", id="refused-collector-number"),
    pytest.param("Whether to change that is decision item 1435 on your list", "decision item 1435", id="refused-field-case"),
]


@pytest.mark.parametrize("text, found", REFUSED_POINTERS)
def test_an_option_less_card_that_points_to_a_list_item_is_refused(text, found):
    # Axis: an option-less card whose shown text sends the owner to a list item by number is refused, naming the card's input location, its title and the matched text.
    # Bites on: the refusal not raised, or any one of the three pattern shapes missing.
    records, advisor = bundle(BIG)
    with_pointer_item(text)(advisor)
    assert problems_of(records, advisor) == [POINTER_PROBLEM.format(title=POINTER_TITLE, found=found)]


@pytest.mark.parametrize("text", [row.values[0] for row in REFUSED_POINTERS], ids=[row.id.replace("refused", "allowed-with-options") for row in REFUSED_POINTERS])
def test_a_card_with_options_is_never_refused_for_mentioning_a_list_item(text):
    # Axis: the same text on a card that carries a list of options builds.
    # Bites on: the pointer scan reading cards that have options.
    records, advisor = bundle(BIG)
    with_pointer_on_retry(text)(advisor)
    assert build(records, advisor)["cards"][2]["context"][0]["blocks"] == [{"paragraph": text}]


def test_a_leftover_with_the_three_option_object_is_never_refused_for_a_list_item():
    # Axis: a leftover whose options are the three-option object carries options, so its context may name a list item.
    # Bites on: the pointer scan reading leftover cards that have options.
    records, advisor = bundle(BIG)
    with_pointer_on_f7("Whether to change that is decision item 1435.")(advisor)
    assert any("decision item 1435" in json.dumps(c["context"]) for c in build(records, advisor)["cards"])


@pytest.mark.parametrize("text", ["configure item 18 is set", "item 3 of the DoD", "Item 12 is done and item 14 follows"])
def test_a_number_with_no_list_word_beside_it_is_not_a_pointer(text):
    # Axis: a bare item number with no list, collector or decision word adjacent is not a pointer.
    # Bites on: a pattern wide enough to refuse every mention of an item number.
    records, advisor = bundle(BIG)
    with_pointer_item(text)(advisor)
    assert any(c["question"] == POINTER_TITLE for c in build(records, advisor)["cards"])


def test_a_leftover_with_no_options_that_points_away_is_refused_naming_its_key():
    # Axis: an option-less leftover is scanned too, and the problem names the key the leftover was found under.
    # Bites on: the leftover cards left out of the scan, or the location label wrong.
    records, advisor = bundle(BIG)
    advisor["leftovers"]["F6"]["context"] = "see item 1435 on your list"
    problems = problems_of(records, advisor)
    assert len(problems) == 1 and problems[0].startswith("leftovers F6: card 'Customers are not told a retry happened' sends the owner to a list item ('item 1435 on your list')")


POINTER_PLACES = [
    pytest.param(lambda a: a["items"].append({**POINTER_ITEM, "title": "Decision item 1435", "ifLeft": "Nothing else."}), "items accepting", "Decision item 1435", id="in-the-question"),
    pytest.param(with_pointer_item("Nothing else.", recommendation={"text": "Accept collector item 1435", "reason": "It is small."}), "items accepting", "collector item 1435", id="in-the-recommendation-text"),
    pytest.param(with_pointer_item("Nothing else.", recommendation={"text": "Accept", "reason": "Covered by list item 1435."}), "items accepting", "list item 1435", id="in-the-recommendation-reason"),
    pytest.param(lambda a: a.update(closesSpec={"spec": "decision item 1435", "receipt": "It shipped."}), "closesSpec", "decision item 1435", id="in-the-closure-spec-name"),
    pytest.param(lambda a: a.update(closesSpec={"spec": "the receipt spec", "receipt": "Answered as collector number 1435."}), "closesSpec", "collector number 1435", id="in-the-closure-receipt"),
    pytest.param(lambda a: a["leftovers"]["F6"].update(ifLeft="Answered as list item 1435."), "leftovers F6", "list item 1435", id="in-a-leftovers-if-left"),
]


@pytest.mark.parametrize("edit, where, found", POINTER_PLACES)
def test_a_pointer_is_found_wherever_an_option_less_card_shows_text(edit, where, found):
    # Axis: the scan covers the question, every context block, the recommendation's text and reason, and the closure card built from the words file and the spec name.
    # Bites on: a shown field left out of the scan.
    records, advisor = bundle(BIG)
    edit(advisor)
    problems = problems_of(records, advisor)
    assert len(problems) == 1 and problems[0].startswith(where + ": card ") and f"({found!r})" in problems[0]


def test_every_pointer_in_every_option_less_card_is_listed_in_one_refusal():
    # Axis: one refusal carries a problem for each pointing card, not just the first.
    # Bites on: the refusal raised on the first pointing card.
    records, advisor = bundle(BIG)
    advisor["leftovers"]["F6"]["context"] = "see item 1435 on your list"
    with_pointer_item("collector #1501")(advisor)
    problems = problems_of(records, advisor)
    assert [p.split(":")[0] for p in problems] == ["leftovers F6", "items accepting"]


def collector_edit(change):
    def edit(advisor):
        change(advisor["collectorItems"])
    return edit


COLLECTOR_REFUSALS = [
    pytest.param(lambda a: a.update(collectorItems={}), "collectorItems must be a list", id="not-a-list"),
    pytest.param(collector_edit(lambda c: c.__setitem__(0, "item")), "collectorItems entry 1 must be an object", id="entry-not-an-object"),
    pytest.param(collector_edit(lambda c: c[0].pop("ifLeft")), "collectorItems 1435 is missing ifLeft", id="missing-key"),
    pytest.param(collector_edit(lambda c: c[0].update(extra=1)), "collectorItems 1435 has an unknown key extra", id="unknown-key"),
    pytest.param(collector_edit(lambda c: c[0].update(number=0)), "collectorItems entry 1 needs number, an integer 1 or more", id="number-zero"),
    pytest.param(collector_edit(lambda c: c[0].update(number=True)), "collectorItems entry 1 needs number, an integer 1 or more", id="number-a-bool"),
    pytest.param(collector_edit(lambda c: c[1].update(number=1435)), "collectorItems 1435 repeats the number 1435", id="duplicate-number"),
    pytest.param(collector_edit(lambda c: c[0].update(title="")), "collectorItems 1435: title must be a non-empty string", id="empty-title"),
    pytest.param(collector_edit(lambda c: c[0].update(why=" ")), "collectorItems 1435: why must be a non-empty string", id="empty-why"),
    pytest.param(collector_edit(lambda c: c[0].update(context="")), "collectorItems 1435: context must be a non-empty string", id="empty-context"),
    pytest.param(collector_edit(lambda c: c[0].update(ifLeft="")), "collectorItems 1435: ifLeft must be a non-empty string", id="empty-if-left"),
    pytest.param(collector_edit(lambda c: c[0].update(options="none")), "collectorItems 1435: options must be a list of at least 1 option", id="options-none"),
    pytest.param(collector_edit(lambda c: c[0].update(options=[])), "collectorItems 1435: options must be a list of at least 1 option", id="options-empty"),
    pytest.param(collector_edit(lambda c: c[0].update(options="a")), "collectorItems 1435: options must be a list of at least 1 option", id="options-a-string"),
    pytest.param(collector_edit(lambda c: c[0].update(options={"a": "x"})), "collectorItems 1435: options must be a list of at least 1 option", id="options-a-dict"),
    pytest.param(collector_edit(lambda c: c[0]["options"].reverse()), "option 1 must have the id 'a'", id="option-ids-out-of-order"),
    pytest.param(collector_edit(lambda c: c[0]["options"][1].update(id="x")), "option 2 must have the id 'b'", id="option-id-not-the-next-letter"),
    pytest.param(collector_edit(lambda c: c[0].pop("recommendation")), "collectorItems 1435 is missing recommendation", id="recommendation-missing"),
    pytest.param(collector_edit(lambda c: c[0]["recommendation"].pop("optionId")), "collectorItems 1435: recommendation needs an optionId", id="recommendation-without-option-id"),
    pytest.param(collector_edit(lambda c: c[0]["recommendation"].update(optionId="z")), "optionId 'z' is not one of its options", id="recommendation-option-id-unknown"),
]


@pytest.mark.parametrize("edit, expected", COLLECTOR_REFUSALS)
def test_a_collector_input_that_breaks_a_rule_is_refused(edit, expected):
    # Axis: each collectorItems shape the builder cannot trust is refused with a problem that names the entry and the cause.
    # Bites on: letter order unchecked, the recommendation or its optionId made optional, "none" or an empty list accepted, a duplicate number or an unknown key let through.
    records, advisor = bundle(COLLECTOR)
    edit(advisor)
    assert any(expected in p for p in problems_of(records, advisor))


# --- the PR body's What we're accepting: the advisor's input accounts for every listed acceptance, and none becomes a card on its own ---

VET_SLOT = Path(__file__).resolve().parent / "fixtures" / "vet_slot"
BODY_TWIN = {241: FIXTURES / "body-twin-241.md", 242: FIXTURES / "body-twin-242.md"}
NONE_BODY = FIXTURES / "body-none.md"
BODY_2075 = FIXTURES / "body-2075-labelled.md"
BODY_2075_REAL = FIXTURES / "body-2075.md"
CASE_2075 = (["record-2075.json"], "input-2075.json")
BODIES_2075 = {2075: BODY_2075.read_text(encoding="utf-8")}
BULLETS_2075 = [bullet for bullet, _ in pr_sheet.listed_bullets(2075, BODIES_2075[2075])]
ACCEPTING = "## What we're accepting\n"
BUILD_RECORD = "<!-- superheroes:build-record -->\n"
BODY_COSTLY = FIXTURES / "body-costly-shaped.md"
BODY_COSTLY_NO_HEADING = FIXTURES / "body-costly-no-heading.md"
BODY_COSTLY_HARMLESS_ONLY = FIXTURES / "body-costly-harmless-only.md"
COSTLY_LINE = "The verify gate did not run on the final head, so the last commit's tests are unverified until CI runs."
HARMLESS_LINE = "The order rode a prompt file, not inline"
CANON_ID = "2026-10-22-abcdefgh-1"
NOT_ONE_OF = "must be an object with exactly one of item, fold with line, leftover or canon"


def run_main(capsys, *argv):
    """The command through main; returns its exit code and the one JSON line it printed."""
    code = pr_sheet.main([str(arg) for arg in argv])
    return code, json.loads(capsys.readouterr().out)


def main_build(capsys, case, out, bodies, advisor=None):
    """A build of case through main with a --pr-body N=FILE for each of bodies; advisor is the input file when it is not the case's own."""
    argv = ["build", "--input", advisor or FIXTURES / case[1], "--out", out]
    for record in case[0]:
        argv += ["--record", FIXTURES / record]
    for number, file in bodies.items():
        argv += ["--pr-body", f"{number}={file}"]
    return run_main(capsys, *argv)


def read_bodies(files):
    """PR number to body text for a dict of PR number to body file."""
    return {number: Path(file).read_text(encoding="utf-8") for number, file in files.items()}


def with_bodies(case, bodies, edit=None):
    """The case's build given bodies (PR number to body text); edit(advisor), when given, changes the input first."""
    records, advisor = bundle(case)
    if edit:
        edit(advisor)
    return pr_sheet.build(records, advisor, WORDS, bodies=bodies)


def refused_with_bodies(case, bodies, edit=None):
    """The problems of a with_bodies build, which must be refused."""
    with pytest.raises(pr_sheet.Refusal) as caught:
        with_bodies(case, bodies, edit)
    return caught.value.problems


def a_cards(sheet):
    """The cards whose id starts with the retired body-card prefix; a sheet has none."""
    return [c for c in sheet["cards"] if c["id"][:2] == "a-"]


def card_ids(sheet):
    return [c["id"] for c in sheet["cards"]]


def written_input(tmp_path, case, edit, name="input.json"):
    """The case's input file with edit(advisor) applied, written in tmp_path; returns its path."""
    advisor = load(case[1])
    edit(advisor)
    return write_json(tmp_path / name, advisor)


def fold_all(bodies):
    """An edit that gives the input one fold item and accounts for every acceptance the bodies list as a line of it."""
    def edit(advisor):
        bullets = [bullet for pr in sorted(bodies) for bullet, _ in pr_sheet.listed_bullets(pr, bodies[pr])]
        if bullets:
            advisor["items"] = [{"id": "everything", "kind": "Accept", "title": "What you're accepting",
                                 "ifLeft": [f"Line {n}." for n in range(1, len(bullets) + 1)], "options": "none"}]
        advisor["accounting"] = {bullet: {"fold": "everything", "line": n} for n, bullet in enumerate(bullets, 1)}
    return edit


def set_accounting(bullet, value):
    """An edit that gives one bullet of the 2075 input's accounting this value."""
    return lambda advisor: advisor["accounting"].__setitem__(bullet, value)


def test_pr_2075s_real_body_is_accounted_for_and_makes_only_the_advisors_cards(tmp_path, capsys):
    # Bites on: a listed acceptance becoming a card of its own, a leftover, item or fold line that the accounting names being refused, or nothingListed set on a sheet whose body lists acceptances.
    # Axis: PR #2075's 8 acceptances, accounted to 1 leftover card, 3 own items and 4 lines of 1 fold item, give exactly 5 cards (1 f-, 4 i-), no a- card, no nothingListed.
    assert list(load("input-2075.json")["accounting"]) == BULLETS_2075 and len(BULLETS_2075) == 8
    out = tmp_path / "sheet.json"
    code, said = main_build(capsys, CASE_2075, out, {2075: BODY_2075})
    assert code == 0 and said["cards"] == 5, said
    sheet = json.loads(out.read_text(encoding="utf-8"))
    assert [c["id"][:2] for c in sheet["cards"]] == ["f-"] + ["i-"] * 4 and a_cards(sheet) == []
    assert "nothingListed" not in sheet["prSheet"]
    assert len(sheet["cards"][4]["context"][0]["blocks"][0]["bullets"]) == 4
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_a_bullet_left_out_of_the_accounting_is_refused_naming_it_and_nothing_is_written(tmp_path, capsys):
    # Bites on: an acceptance a body lists being left off the sheet without a word, or the refusal not naming which one.
    # Axis: G1: with bullet 5's entry removed there is exactly one problem, it holds that bullet's id and the start of its text, and no file is written.
    left_out = BULLETS_2075[5]
    source = written_input(tmp_path, CASE_2075, lambda advisor: advisor["accounting"].pop(left_out))
    out = tmp_path / "sheet.json"
    code, said = main_build(capsys, CASE_2075, out, {2075: BODY_2075}, advisor=source)
    assert code == 1 and said["ok"] is False and not out.exists()
    (problem,) = said["problems"]
    assert left_out in problem and "A line past 2,000 characters" in problem
    assert problem.startswith(f"PR #2075's acceptance {left_out} (\"")
    assert problem.endswith(f'is not accounted for: give accounting "{left_out}" one of item, fold with line, leftover, or canon')


def test_a_bullet_whose_value_names_two_targets_is_refused_as_accounted_for_more_than_once():
    # Bites on: a bullet with two targets being counted for the first, or refused in other words than the more-than-once text.
    # Axis: G2: a value with both fold and canon is one problem, in the more-than-once words, naming the bullet and the start of its text.
    twice = set_accounting(BULLETS_2075[5], {"fold": "accepting", "line": 2, "canon": CANON_ID})
    (problem,) = refused_with_bodies(CASE_2075, BODIES_2075, twice)
    assert problem.startswith(f'accounting "{BULLETS_2075[5]}" (PR #2075: "') and "A line past 2,000 characters" in problem
    assert problem.endswith("is accounted for more than once: give exactly one of item, fold, leftover or canon")


def test_an_input_that_repeats_an_accounting_key_is_refused_through_main(tmp_path, capsys):
    # Bites on: a key written twice in the input silently keeping the later one, so the bullet is counted for what the first entry said.
    # Axis: G8 and E8: the input file with bullet 5's key written twice is refused with the repeated-key problem and nothing is written.
    line = f'    "{BULLETS_2075[5]}": {{"fold": "accepting", "line": 2}},\n'
    text = (FIXTURES / "input-2075.json").read_text(encoding="utf-8")
    assert text.count(line) == 1
    repeated = tmp_path / "input.json"
    repeated.write_text(text.replace(line, line + line), encoding="utf-8")
    out = tmp_path / "sheet.json"
    code, said = main_build(capsys, CASE_2075, out, {2075: BODY_2075}, advisor=repeated)
    assert code == 1 and said["problems"] == [f'the input repeats key "{BULLETS_2075[5]}"'] and not out.exists()


def test_two_targets_of_any_kind_are_refused_as_more_than_once():
    # Bites on: only the fold-and-canon pair being counted, so another pair of targets slips through as though it named one.
    # Axis: E3: item with leftover, and item with fold, are each refused with the more-than-once text.
    for value in ({"item": "no-retry", "leftover": "caps/test-too-small"}, {"item": "no-retry", "fold": "accepting", "line": 1}):
        (problem,) = refused_with_bodies(CASE_2075, BODIES_2075, set_accounting(BULLETS_2075[3], value))
        assert problem.endswith("is accounted for more than once: give exactly one of item, fold, leftover or canon"), value


# Bites on: an unindented HTML comment that ends a list leaving the list's content column set, so a later root fence is read as a list-item fence and ends early.
def test_an_unindented_comment_ending_a_list_clears_its_content_column():
    body = ("- Example\n\n<!-- separator -->\n\n  ```\n## What we're accepting\n\n## Example\n  ```\n\n"
            "## What we're accepting\n\n- A breaking change\n")
    assert pr_sheet.accepting_listed(body) == ["A breaking change"]


def test_a_canon_entry_accounts_for_a_bullet_only_as_a_real_id_the_summary_cites():
    # Bites on: a canon target accepted with no id, a made-up id, a malformed one, or one the summary does not cite; or a canon bullet still needing an item.
    # Axis: G6: "" and an id absent from the summary and a malformed id that is cited are each one problem; with a well-formed id the summary cites the sheet builds the same 5 cards, its fold keeping 4 lines though no bullet names line 3.
    bullet = BULLETS_2075[6]

    def canon(value, cited=""):
        def edit(advisor):
            advisor["accounting"][bullet] = {"canon": value}
            advisor["summary"] += cited
        return edit
    for value, cited in (("", ""), (CANON_ID, ""), ("2026-10-22-abc-1", " Ruled in 2026-10-22-abc-1."),
                         (CANON_ID, f" Ruled in {CANON_ID}0.")):  # a longer id cited is not a citation of its prefix
        (problem,) = refused_with_bodies(CASE_2075, BODIES_2075, canon(value, cited))
        assert problem.startswith(f'accounting "{bullet}" (PR #2075: "')
        assert problem.endswith(f'names canon "{value}", which is not a Canon entry id (YYYY-MM-DD-xxxxxxxx-N) cited in the summary')
    sheet = with_bodies(CASE_2075, BODIES_2075, canon(CANON_ID, f" Ruled in {CANON_ID}."))
    assert card_ids(sheet) == card_ids(with_bodies(CASE_2075, BODIES_2075)) and len(sheet["cards"]) == 5
    assert len(sheet["cards"][4]["context"][0]["blocks"][0]["bullets"]) == 4


MISSING_TARGETS = [
    pytest.param(1, {"item": "no-such-item"}, 'names item "no-such-item", which is not in items', id="item-not-in-items"),
    pytest.param(4, {"fold": "no-such-item", "line": 1}, 'names fold "no-such-item" line 1, which is not a line of that item\'s ifLeft list', id="fold-item-not-in-items"),
    pytest.param(4, {"fold": "codex-config", "line": 1}, 'names fold "codex-config" line 1, which is not a line of that item\'s ifLeft list', id="fold-names-a-string-ifleft"),
    pytest.param(4, {"fold": "accepting", "line": 5}, 'names fold "accepting" line 5, which is not a line of that item\'s ifLeft list', id="fold-line-past-the-end"),
    pytest.param(4, {"fold": "accepting", "line": 0}, 'names fold "accepting" line 0, which is not a line of that item\'s ifLeft list', id="fold-line-zero"),
    pytest.param(4, {"fold": "accepting", "line": -1}, 'names fold "accepting" line -1, which is not a line of that item\'s ifLeft list', id="fold-line-negative"),
    pytest.param(4, {"fold": "accepting", "line": True}, 'names fold "accepting" line True, which is not a line of that item\'s ifLeft list', id="fold-line-a-bool"),
    pytest.param(4, {"fold": "accepting", "line": 1.0}, 'names fold "accepting" line 1.0, which is not a line of that item\'s ifLeft list', id="fold-line-a-float"),
    pytest.param(0, {"leftover": "no-such-key"}, 'names leftover "no-such-key", which names no one left-for-owner finding in leftovers', id="leftover-key-not-in-leftovers"),
    pytest.param(1, {}, NOT_ONE_OF, id="no-target-at-all"),
    pytest.param(4, {"line": 1}, NOT_ONE_OF, id="line-without-fold"),
    pytest.param(4, {"fold": "accepting"}, NOT_ONE_OF, id="fold-without-line"),
    pytest.param(1, {"item": "codex-config", "line": 1}, NOT_ONE_OF, id="line-beside-item"),
    pytest.param(1, {"item": "codex-config", "why": "x"}, NOT_ONE_OF, id="unknown-key-beside-item"),
    pytest.param(1, "codex-config", NOT_ONE_OF, id="value-not-an-object"),
]


@pytest.mark.parametrize("index, value, tail", MISSING_TARGETS)
def test_an_accounting_entry_that_points_at_nothing_on_the_sheet_is_refused(index, value, tail):
    # Bites on: an entry naming an item, fold line, leftover or canon that the sheet does not have being accepted, or an entry of the wrong shape being read as one target.
    # Axis: G3, G4, G5 and E2, E4, E5: each is exactly one problem, naming the bullet and its text and ending with the cause.
    (problem,) = refused_with_bodies(CASE_2075, BODIES_2075, set_accounting(BULLETS_2075[index], value))
    assert problem.startswith(f'accounting "{BULLETS_2075[index]}" (PR #2075: "') and problem.endswith(tail)


def test_an_accounting_key_naming_no_listed_acceptance_is_refused():
    # Bites on: an accounting entry for a bullet no body lists (a typo, or a bullet whose text was edited) being ignored.
    # Axis: G7: one problem, which names the key.
    stray = "2075:ffffffffff"
    assert stray not in BULLETS_2075
    assert refused_with_bodies(CASE_2075, BODIES_2075, set_accounting(stray, {"item": "no-retry"})) == [
        f'accounting key "{stray}" names no acceptance in the covered PR bodies']


@pytest.mark.parametrize("value", [[], "no-retry", 5, None, True])
def test_an_accounting_that_is_not_an_object_is_refused(value):
    # Bites on: a list, a string or null accounting being read as no accounting, or crashing the build.
    # Axis: E1: the build is refused with the not-an-object problem first, and every listed acceptance is then reported as not accounted for.
    problems = refused_with_bodies(CASE_2075, BODIES_2075, lambda advisor: advisor.update(accounting=value))
    assert problems[0] == "accounting must be an object of bullet id to where that acceptance is accounted for"
    assert len(problems) == 1 + len(BULLETS_2075) and all("is not accounted for" in p for p in problems[1:])


def test_a_leftover_key_shared_by_two_findings_accounts_for_nothing():
    # Bites on: a leftover target that names several findings being accepted as the card it restates.
    # Axis: E7: with two left-for-owner findings under one findingKey, the accounting's leftover target is refused as naming no one finding.
    records, advisor = bundle(CASE_2075)
    records[0]["findings"].append({**records[0]["findings"][0], "id": "F2"})
    with pytest.raises(pr_sheet.Refusal) as caught:
        pr_sheet.build(records, advisor, WORDS, bodies=BODIES_2075)
    assert any(p.startswith(f'accounting "{BULLETS_2075[0]}"') and p.endswith(
        'names leftover "caps/test-too-small", which names no one left-for-owner finding in leftovers') for p in caught.value.problems)


def test_a_leftover_key_the_input_regrades_to_a_craft_determination_accounts_for_nothing():
    # Bites on: a leftover target being accepted because its key names one left-for-owner finding, though that finding is decided for the owner and has no card on the sheet.
    # Axis: E1: with the key moved from leftovers to craftDeterminations, the leftover target is refused as naming no one finding in leftovers, with one problem naming the bullet.
    problems = refused_with_bodies(CASE_2075, BODIES_2075, lambda advisor: regrade(advisor, "caps/test-too-small"))
    (problem,) = [p for p in problems if BULLETS_2075[0] in p]
    assert problem.endswith('which names no one left-for-owner finding in leftovers')


def test_a_bullet_inserted_above_the_others_costs_one_entry_and_moves_no_card_id(tmp_path, capsys):
    # Bites on: a bullet's id depending on its place in the body, so an insertion above re-keys the accounting already written and moves cards.
    # Axis: FU1: the 8 original bullets keep their ids; the unchanged input is refused with one problem naming the new bullet; with its one entry added the sheet builds with the same card ids.
    lead = ACCEPTING + "\n"
    assert BODIES_2075[2075].count(lead) == 1
    grown = tmp_path / "body-grown.md"
    grown.write_text(BODIES_2075[2075].replace(lead, lead + "- **A new acceptance.** Added by the author above the others.\n"), encoding="utf-8")
    before, after = pr_sheet.listed_bullets(2075, BODIES_2075[2075]), pr_sheet.listed_bullets(2075, grown.read_text(encoding="utf-8"))
    assert [i for i, _ in before] == BULLETS_2075 and len(after) == 9 and after[1:] == before
    new = after[0][0]
    out = tmp_path / "base.json"
    code, said = main_build(capsys, CASE_2075, out, {2075: BODY_2075})
    assert code == 0, said
    base_ids = card_ids(json.loads(out.read_text(encoding="utf-8")))
    out = tmp_path / "sheet.json"
    code, said = main_build(capsys, CASE_2075, out, {2075: grown})
    assert code == 1 and not out.exists()
    (problem,) = said["problems"]
    assert new in problem and "A new acceptance." in problem and "is not accounted for" in problem
    source = written_input(tmp_path, CASE_2075, set_accounting(new, {"leftover": "caps/test-too-small"}))
    code, said = main_build(capsys, CASE_2075, out, {2075: grown}, advisor=source)
    assert code == 0 and said["cards"] == 5, said
    assert card_ids(json.loads(out.read_text(encoding="utf-8"))) == base_ids


def test_a_stacks_bodies_are_refused_without_accounting_and_build_with_no_card_of_their_own():
    # Bites on: a stack's listed acceptances being built with no accounting, or turned into cards of their own, or the refusal missing a PR's acceptances.
    # Axis: the two-PR stack's bodies list 3 and 2 acceptances: with no accounting there is one not-accounted-for problem for each; folded into one item the sheet has no a- card and no nothingListed.
    bodies = read_bodies(BODY_TWIN)
    problems = refused_with_bodies(TWIN, bodies)
    assert [p.split(" acceptance ")[0] for p in problems] == ["PR #241's"] * 3 + ["PR #242's"] * 2
    assert all("is not accounted for: give accounting " in p for p in problems)
    sheet = with_bodies(TWIN, bodies, fold_all(bodies))
    assert [c["id"][:2] for c in sheet["cards"]] == ["f-"] * 2 + ["i-"] and a_cards(sheet) == []
    assert len(sheet["cards"][2]["context"][0]["blocks"][0]["bullets"]) == 5 and "nothingListed" not in sheet["prSheet"]


def test_a_stack_built_with_a_covered_prs_body_missing_is_refused_naming_that_pr(tmp_path, capsys):
    # Bites on: a covered PR with no --pr-body being built as though it listed nothing, or the problem not naming the PR.
    # Axis: E7: with no --pr-body one problem names #241 and one names #242; with only #241's body one names #242 alone; nothing is written.
    out = tmp_path / "sheet.json"
    code, said = main_build(capsys, TWIN, out, {})
    assert code == 1 and said["ok"] is False and not out.exists()
    assert len(said["problems"]) == 2
    assert said["problems"][0].startswith("PR #241 has no body: give --pr-body 241=<file>")
    assert said["problems"][1].startswith("PR #242 has no body: give --pr-body 242=<file>")
    code, said = main_build(capsys, TWIN, out, {241: BODY_TWIN[241]})
    assert code == 1 and not out.exists()
    assert len(said["problems"]) == 1 and said["problems"][0].startswith("PR #242 has no body: give --pr-body 242=<file>")


@pytest.mark.parametrize("first, second, said", [
    pytest.param(BODY_TWIN[241], NONE_BODY, False, id="first-lists-some"),
    pytest.param(NONE_BODY, BODY_TWIN[242], False, id="second-lists-some"),
    pytest.param(NONE_BODY, NONE_BODY, True, id="both-list-none"),
])
def test_a_stack_says_nothing_listed_only_when_every_covered_body_lists_none(tmp_path, capsys, first, second, said):
    # Bites on: nothingListed set while one covered PR lists acceptances (the invariant: no sheet says nothing to accept while a PR it covers lists some).
    # Axis: the flag is true exactly when no covered body lists an acceptance, and then the sheet has only its 2 leftover cards; the fold item that accounts for what is listed makes the third.
    out = tmp_path / "sheet.json"
    source = written_input(tmp_path, TWIN, fold_all(read_bodies({241: first, 242: second})))
    code, result = main_build(capsys, TWIN, out, {241: first, 242: second}, advisor=source)
    assert code == 0, result
    sheet = json.loads(out.read_text(encoding="utf-8"))
    assert sheet["prSheet"].get("nothingListed") is (True if said else None)
    assert (len(sheet["cards"]) == 2) is said and a_cards(sheet) == []


@pytest.mark.parametrize("path, count", [
    pytest.param(BODY_TWIN[241], 3, id="twin-241"),
    pytest.param(BODY_TWIN[242], 2, id="twin-242"),
    pytest.param(VET_SLOT / "pr1442_body.md", 5, id="pr1442"),
    pytest.param(VET_SLOT / "pr1437_body_legacy.md", 8, id="pr1437-legacy"),
    pytest.param(NONE_BODY, 0, id="none"),
    pytest.param(FIXTURES / "body-absent.md", 0, id="absent"),
])
def test_the_reader_counts_the_acceptances_of_a_body_file(path, count):
    # Bites on: the reader missing, inventing or dropping an acceptance in a real body (counts measured with awk over the section's top-level bullets).
    # Axis: E1 (no heading) and E3 (None) read as none; the twin, the live and the legacy bodies read as their bullet counts.
    assert len(pr_sheet.accepting_listed(path.read_text(encoding="utf-8"))) == count


@pytest.mark.parametrize("body", ["", None, 5, ["- an acceptance"], b"## What we're accepting\n- bytes\n"])
def test_the_reader_gives_nothing_for_an_empty_or_non_text_body(body):
    # Axis: E1: an empty string, None or anything that is not a string lists no acceptance.
    assert pr_sheet.accepting_listed(body) == []


READER_CASES = [
    pytest.param("```\n## What we're accepting\n- fenced\n```\n", [], id="E4-heading-in-a-fence-is-not-the-section"),
    pytest.param("~~~\n## What we're accepting\n- fenced\n~~~\n\n## What we're accepting\n- real\n", ["real"], id="E4-the-real-heading-after-a-fence"),
    pytest.param(ACCEPTING + "- first\n  ```\n  ## Not a heading\n  ```\n- second\n", ["first ``` ## Not a heading ```", "second"], id="E4-heading-in-a-fence-in-the-section"),
    pytest.param(ACCEPTING + "- one\n# Top\n- two\n", ["one"], id="a-heading-outside-a-fence-ends-it"),
    pytest.param("## Something else\n- not mine\n", [], id="E1-other-headings-only"),
    pytest.param(ACCEPTING + "\n## Next\n- not mine\n", [], id="E2-empty-section"),
    pytest.param(ACCEPTING, [], id="E2-heading-and-nothing-after"),
    pytest.param(ACCEPTING + "<!-- fill this in -->\n\n## Next\n", [], id="E2-only-a-comment"),
    pytest.param(ACCEPTING + "- None.\n", [], id="E3-none-bullet-with-a-dot"),
    pytest.param(ACCEPTING + "- None.\n- A real one.\n", ["A real one."], id="E3-none-bullet-dropped-beside-a-real-one"),
    pytest.param(ACCEPTING + "- N/A\n", [], id="E3-n-a-bullet"),
    pytest.param(ACCEPTING + "- n/a.\n", [], id="E3-lowercase-n-a-bullet-with-a-dot"),
    pytest.param(ACCEPTING + "- NA\n", [], id="E3-na-bullet"),
    pytest.param(ACCEPTING + "- Nothing\n", [], id="E3-nothing-bullet"),
    pytest.param(ACCEPTING + "None\n", [], id="E3-none-paragraph"),
    pytest.param(ACCEPTING + "N/A.\n", [], id="E3-n-a-paragraph-with-a-dot"),
    pytest.param(ACCEPTING + "The schema is wider now.\n", ["The schema is wider now."], id="E5-an-unrecognised-paragraph-counts"),
    pytest.param(ACCEPTING + "- text <!-- note -->\n", ["text <!-- note -->"], id="a-comment-beside-text-is-kept"),
    pytest.param(ACCEPTING + "  - First.\n   - Second.\n", ["First.", "Second."], id="two-then-three-space-bullets-stay-separate"),
    pytest.param(ACCEPTING + "  - First.\n- Second.\n  - nested\n", ["First.", "Second. - nested"], id="a-flush-bullet-after-an-indented-one-is-new"),
    pytest.param(ACCEPTING + "- A `code <!-- span\n- B` end.\n- Next.\n", ["A `code <!-- span", "B` end.", "Next."], id="a-code-span-crossing-a-comment-marker-keeps-both-acceptances"),
    pytest.param(ACCEPTING + "- esc \\` x <!-- y\n- Next.\n", ["esc \\` x <!-- y", "Next."], id="an-escaped-backtick-before-a-marker-keeps-the-bullet"),
    pytest.param(ACCEPTING + "- One.\n<!-- gone -->\n- Two.\n<!-- multi\nline\n-->\n- Three.\n", ["One.", "Two.", "Three."], id="whole-line-and-block-comments-between-bullets-are-dropped"),
    pytest.param(ACCEPTING + "- Same words.\n- Same words.\n", ["Same words.", "Same words."], id="E6-identical-bullets-are-two"),
    pytest.param(ACCEPTING + "  - First.\n  - Second.\n", ["First.", "Second."], id="two-space-top-level-bullets-stay-separate"),
    pytest.param(ACCEPTING + "   - First.\n   - Second.\n", ["First.", "Second."], id="three-space-top-level-bullets-stay-separate"),
    pytest.param(ACCEPTING + "  - First.\n      - nested\n  - Second.\n", ["First. - nested", "Second."], id="deeper-lines-join-their-indented-parent"),
    pytest.param(ACCEPTING + "- First.\n  - nested\n- Second.\n", ["First. - nested", "Second."], id="deeper-lines-join-their-flush-parent"),
    pytest.param(ACCEPTING + "- Keep `<!--` literally.\n- A second acceptance.\n", ["Keep `<!--` literally.", "A second acceptance."], id="an-inline-code-comment-marker-keeps-the-acceptance-and-the-rest"),
    pytest.param(ACCEPTING + "- Keep ``a `<!--` b`` here.\n- Next.\n", ["Keep ``a `<!--` b`` here.", "Next."], id="a-double-backtick-span-hides-the-marker"),
    pytest.param(ACCEPTING + "- text `unclosed <!-- note -->\n- Next.\n", ["text `unclosed <!-- note -->", "Next."], id="an-unclosed-backtick-beside-a-trailing-comment-keeps-the-text"),
    pytest.param(ACCEPTING + "- Keep `the literal\n  <!-- in the parser.\n- A second acceptance.\n", ["Keep `the literal <!-- in the parser.", "A second acceptance."], id="an-opener-with-no-closing-marker-is-plain-text"),
    pytest.param(ACCEPTING + "<!--\nhidden\n--> Visible disclosure.\n", ["--> Visible disclosure."], id="a-closing-line-with-text-after-the-marker-is-kept-whole"),
    pytest.param(ACCEPTING + "- One.\n<!--\nhidden\n-->\n- Two.\n\n## Next\n- not mine\n<!-- elsewhere -->\n", ["One.", "Two."], id="a-closed-block-between-bullets-is-dropped"),
    pytest.param(ACCEPTING + "- One.\n<!-- open\n- Two.\n## Next\n-->\n", ["One. <!-- open", "Two."], id="a-closing-marker-in-a-later-section-does-not-close-the-block"),
    pytest.param(ACCEPTING + "<!-- begin --> Cold starts now take a minute. <!-- end -->\n", ["<!-- begin --> Cold starts now take a minute. <!-- end -->"], id="visible-text-between-two-comments-is-kept"),
    pytest.param("## What's changing\n\n- ```python\n  print('example')\n  ```\n\n" + ACCEPTING + "- The cache is cleared on every upgrade.\n", ["The cache is cleared on every upgrade."], id="a-fence-opened-in-a-list-item-does-not-hide-the-section"),
    pytest.param("- ```python\n\tpass\n\t```\n\n" + ACCEPTING + "- Cold starts now take a minute.\n", ["Cold starts now take a minute."], id="a-tab-indented-closing-fence-in-a-list-item-closes-it"),
    pytest.param("10. ```python\n\tpass\n\t```\n\n" + ACCEPTING + "- Cold starts now take a minute.\n", ["Cold starts now take a minute."], id="a-tab-indented-closing-fence-in-an-ordered-item-closes-it"),
    pytest.param("- ```python\n  print(1)\n\n" + ACCEPTING + "\n- Cold starts now take a minute.\n", ["Cold starts now take a minute."], id="an-unclosed-list-fence-ends-with-its-list-item"),
    pytest.param("- ```python\n  print(1)\n\n  ## What we're accepting\n- Hidden.\n", [], id="a-heading-inside-the-list-item-stays-fenced"),
    pytest.param("- ```python\n  print(1)\n      ```\n  ## What we're accepting\n- Hidden.\n", [], id="a-list-fence-closer-four-columns-past-the-content-column-does-not-close"),
    pytest.param("- ```python\n  print(1)\n     ```\n  ## What we're accepting\n- Listed.\n", ["Listed."], id="a-list-fence-closer-three-columns-past-the-content-column-closes"),
    pytest.param(ACCEPTING + "- One.\n" + BUILD_RECORD + "- Below.\n", ["One."], id="a-build-record-marker-line-ends-the-section"),
    pytest.param(ACCEPTING + "- One.\n```\n<!-- superheroes:build-record -->\n```\n- Two.\n", ["One. ``` <!-- superheroes:build-record --> ```", "Two."], id="a-fenced-build-record-marker-does-not-end-the-section"),
    pytest.param(ACCEPTING + "- Keep `<!-- superheroes:build-record -->` as text.\n- Next.\n", ["Keep `<!-- superheroes:build-record -->` as text.", "Next."], id="an-inline-build-record-marker-does-not-end-the-section"),
    pytest.param(ACCEPTING + "- One.\n<!--\n<!-- superheroes:build-record -->\n-->\n- Two.\n", ["One. -->", "Two."], id="a-build-record-marker-inside-a-comment-block-does-not-end-the-section"),
    pytest.param(ACCEPTING + "- One.\n    " + BUILD_RECORD + "- Two.\n", ["One.", "Two."], id="an-indented-build-record-marker-in-a-list-item-does-not-end-the-section"),
    pytest.param(BUILD_RECORD + ACCEPTING + "- A costly one.\n", ["A costly one."], id="a-build-record-marker-above-the-heading-does-not-end-the-body"),
]


@pytest.mark.parametrize("body, expected", READER_CASES)
def test_the_reader_fails_closed_on_the_edges_of_a_body(body, expected):
    # Bites on: a fenced heading read as the section, a fenced heading ending it, None or N/A kept, an unrecognised line dropped, a comment's text kept, or a repeated bullet merged.
    # Axis: E1, E2, E3, E4, E5 and E6: an unrecognised line is an acceptance (never dropped), and only the listed none-words are not.
    assert pr_sheet.accepting_listed(body) == expected


def test_two_identical_bullets_have_different_ids_and_each_needs_its_own_entry():
    # Bites on: two identical acceptances sharing one bullet id, so one accounting entry covers both, or an id that moves on a rebuild.
    # Axis: E6: the place among identical bullets is part of the bullet's identity: one entry leaves exactly the second one unaccounted for, and both entries build the same sheet twice.
    body = ACCEPTING + "\n- Same words.\n- Same words.\n"
    first, second = (bullet for bullet, _ in pr_sheet.listed_bullets(211, body))
    assert first != second and [bullet for bullet, _ in pr_sheet.listed_bullets(211, body)] == [first, second]

    def fold(*entries):
        def edit(advisor):
            advisor["items"] = [{"id": "same", "kind": "Accept", "title": "Same words", "ifLeft": ["One.", "Two."], "options": "none"}]
            advisor["accounting"] = {bullet: {"fold": "same", "line": n} for n, bullet in entries}
        return edit
    (problem,) = refused_with_bodies(SMALL, {211: body}, fold((1, first)))
    assert second in problem and first not in problem and "is not accounted for" in problem
    sheet = with_bodies(SMALL, {211: body}, fold((1, first), (2, second)))
    assert card_ids(sheet) == card_ids(with_bodies(SMALL, {211: body}, fold((1, first), (2, second)))) and a_cards(sheet) == []
    assert "nothingListed" not in sheet["prSheet"]


def test_a_fold_naming_an_item_with_no_ifleft_is_refused_not_a_key_error():
    # Bites on: the accounting check reading ifLeft with a subscript, so a fold onto an item missing it raises KeyError past the Refusal.
    # Axis: E6: a malformed item is a refusal naming the missing field, never a traceback.
    body = ACCEPTING + "\n- Routine note.\n"
    ((bullet, _),) = pr_sheet.listed_bullets(211, body)

    def edit(advisor):
        advisor["items"] = [{"id": "fold", "kind": "Accept", "title": "Notes", "options": "none"}]
        advisor["accounting"] = {bullet: {"fold": "fold", "line": 1}}
    problems = refused_with_bodies(SMALL, {211: body}, edit)
    assert any("ifLeft" in p for p in problems)


@pytest.mark.parametrize("path", [BODY_COSTLY, BODY_COSTLY_NO_HEADING], ids=["shaped", "no-heading"])
def test_the_build_record_below_the_accepting_section_is_never_read_as_an_acceptance(path):
    # Bites on: the reader running on past the build-record marker, so the build record's [harmless] and [costly] degradation bullets read as acceptances (the no-heading body has no later heading to stop it).
    # Axis: nothing at or below the build-record marker is an acceptance: only the costly bullet under What we're accepting is listed.
    assert pr_sheet.accepting_listed(path.read_text(encoding="utf-8")) == [COSTLY_LINE]


def test_a_body_whose_only_degradation_is_harmless_lists_nothing_and_makes_no_card():
    # Bites on: a [harmless] build-record bullet becoming an acceptance, a card, or a body that lists none being left without nothingListed.
    # Axis: a harmless degradation under the build-record marker stays off the sheet: no acceptance, no a- card, no card naming it, nothingListed set.
    text = BODY_COSTLY_HARMLESS_ONLY.read_text(encoding="utf-8")
    assert pr_sheet.accepting_listed(text) == []
    sheet = with_bodies(SMALL, {211: text})
    assert a_cards(sheet) == [] and sheet["prSheet"]["nothingListed"] is True
    assert not any(HARMLESS_LINE in json.dumps(card) for card in sheet["cards"])
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_a_costly_acceptance_left_out_of_the_accounting_is_refused_naming_it():
    # Bites on: a costly acceptance listed under What we're accepting being left off the sheet without a word.
    # Axis: a costly acceptance must be accounted for: with an empty accounting there is exactly one problem, it names the bullet and says it is not accounted for.
    text = BODY_COSTLY.read_text(encoding="utf-8")
    ((bullet, _),) = pr_sheet.listed_bullets(211, text)
    (problem,) = refused_with_bodies(SMALL, {211: text}, lambda advisor: advisor.update(accounting={}))
    assert bullet in problem and "is not accounted for" in problem


def test_a_costly_acceptance_accounted_to_an_item_gets_its_card_and_the_harmless_one_gets_none():
    # Bites on: a costly acceptance that the accounting names producing no card, a harmless build-record bullet reaching the sheet, or nothingListed set on a body that lists one.
    # Axis: the costly bullet is accounted to its own item and shows as that one i- card; the harmless bullet is on no card; no a- card; no nothingListed.
    text = BODY_COSTLY.read_text(encoding="utf-8")
    ((bullet, _),) = pr_sheet.listed_bullets(211, text)

    def edit(advisor):
        advisor.setdefault("items", []).append({
            "id": "verify-gate", "kind": "Accept", "title": "The verify gate did not run on the final head",
            "ifLeft": "The last commit's tests are unverified until CI runs.", "options": "none"})
        advisor["accounting"] = {bullet: {"item": "verify-gate"}}
    sheet = with_bodies(SMALL, {211: text}, edit)
    assert [c["id"][:2] for c in sheet["cards"]] == ["i-"] and sheet["cards"][0]["question"] == "The verify gate did not run on the final head"
    assert not any(HARMLESS_LINE in json.dumps(card) for card in sheet["cards"])
    assert a_cards(sheet) == [] and "nothingListed" not in sheet["prSheet"]


DEGRADATIONS = "<!-- superheroes:degradations -->\n### Disclosed degradations\n\n"
VERIFY_GATE = "The verify gate did not run on the final head"


def degraded(*bullets):
    """A body that accepts nothing and lists the bullets under its degradations marker."""
    return ACCEPTING + "None.\n\n" + BUILD_RECORD + DEGRADATIONS + "".join(f"- {bullet}\n" for bullet in bullets)


def test_a_costly_deviation_with_no_line_under_what_we_are_accepting_is_refused_naming_it():
    # Bites on: the build reading the degradations list and not refusing a [costly] bullet that no What we're accepting line carries.
    # Axis: K1 and K4: a costly deviation must have a line under What we're accepting; exactly one problem, naming the PR, the bullet and the missing line.
    (problem,) = refused_with_bodies(SMALL, {211: degraded(f"[costly] {VERIFY_GATE}.")})
    assert "PR #211's costly deviation" in problem and VERIFY_GATE in problem and "has no line under What we're accepting" in problem


def test_an_unlabelled_deviation_with_no_line_under_what_we_are_accepting_is_refused_as_costly():
    # Bites on: a bullet with no label being read as harmless (so a body written before the labels is let through).
    # Axis: K2: an unlabelled deviation reads costly; exactly one problem, saying it is unlabelled.
    (problem,) = refused_with_bodies(SMALL, {211: degraded(f"{VERIFY_GATE}.")})
    assert "unlabelled (read as costly)" in problem and VERIFY_GATE in problem


def test_a_harmless_deviation_needs_no_line_under_what_we_are_accepting():
    # Bites on: a [harmless] bullet being asked for a line under What we're accepting, or becoming a card.
    # Axis: K3: a harmless deviation never needs a line: the build succeeds, lists nothing and makes no card.
    sheet = with_bodies(SMALL, {211: degraded("[harmless] The order rode a prompt file.")})
    assert sheet["prSheet"]["nothingListed"] is True and sheet["cards"] == []


def test_a_nested_bullet_under_a_harmless_deviation_is_part_of_it_and_needs_no_line():
    # Bites on: a two-space nested bullet under a [harmless] bullet being read as its own unlabelled (costly) deviation, so the build refuses a valid body.
    # Axis: a nested bullet stays with its degradation: the build succeeds, lists nothing and makes no card.
    text = BODY_COSTLY_HARMLESS_ONLY.read_text(encoding="utf-8")
    harmless_line = next(line for line in text.splitlines(keepends=True) if line.startswith("- [harmless]"))
    nested = text.replace(harmless_line, harmless_line + "  - The builder read the file before starting.\n")
    assert nested != text
    sheet = with_bodies(SMALL, {211: nested})
    assert sheet["prSheet"]["nothingListed"] is True and sheet["cards"] == []


def test_a_fenced_comment_line_in_a_degradation_does_not_end_the_list():
    # Bites on: a `# ` line inside a code fence in a degradation matching the heading test and ending the list, so a later costly bullet is never checked.
    # Axis: a fenced line never ends the degradations list: the costly bullet after the fence is refused, exactly one problem naming the PR and the bullet.
    body = (ACCEPTING + "None.\n\n" + BUILD_RECORD + DEGRADATIONS
            + "- [harmless] The order rode a prompt file:\n\n  ```sh\n  # read the order from the file\n  cat order.md\n  ```\n\n- [costly] " + VERIFY_GATE + ".\n")
    (problem,) = refused_with_bodies(SMALL, {211: body})
    assert "PR #211's costly deviation" in problem and VERIFY_GATE in problem


def test_a_fenced_list_line_in_a_degradation_is_not_a_deviation():
    # Bites on: a `- example` line inside a code fence in a degradation starting its own unlabelled (costly) item, so the build refuses a valid body.
    # Axis: a fenced line never starts an item: the build succeeds, lists nothing and makes no card, and the one degradation read is the harmless one.
    body = ACCEPTING + "None.\n\n" + BUILD_RECORD + DEGRADATIONS + "- [harmless] The order rode a prompt file, for example:\n\n```md\n- example\n```\n"
    sheet = with_bodies(SMALL, {211: body})
    assert sheet["prSheet"]["nothingListed"] is True and a_cards(sheet) == [] and sheet["cards"] == []
    listed = pr_sheet.degradations_listed(body)
    assert len(listed) == 1 and listed[0][0] == "harmless"


def test_a_labelled_nested_bullet_is_its_own_degradation():
    # Bites on: a labelled nested bullet under a [harmless] bullet being joined onto it, so its costly text is never checked.
    # Axis: a nested item that opens with a label starts its own degradation: read as harmless then costly, and the costly one is refused.
    body = ACCEPTING + "None.\n\n" + BUILD_RECORD + DEGRADATIONS + "- [harmless] A classifier stop.\n  - [costly] " + VERIFY_GATE + ".\n"
    (problem,) = refused_with_bodies(SMALL, {211: body})
    assert "PR #211's costly deviation" in problem and VERIFY_GATE in problem
    assert [label for label, _ in pr_sheet.degradations_listed(body)] == ["harmless", "costly"]


def test_an_empty_costly_text_is_never_carried():
    # Bites on: a bare `- [costly]` (empty text) matching any acceptance line, because the empty string is a substring of everything.
    # Axis: an empty costly text is always returned by costly_unlisted: exactly one problem, naming the PR and the empty bullet.
    body = ACCEPTING + "- " + VERIFY_GATE + ".\n\n" + BUILD_RECORD + DEGRADATIONS + "- [costly]\n"
    ((bullet, _),) = pr_sheet.listed_bullets(211, body)

    def edit(advisor):
        advisor.setdefault("items", []).append({"id": "verify-gate", "kind": "Accept", "title": VERIFY_GATE, "ifLeft": "The last commit is unverified until CI runs.", "options": "none"})
        advisor["accounting"] = {bullet: {"item": "verify-gate"}}
    (problem,) = refused_with_bodies(SMALL, {211: body}, edit)
    assert "PR #211's costly deviation (\"\")" in problem


def test_a_stacks_later_layer_is_checked_for_costly_lines():
    # Bites on: the build checking only the first covered PR's body for a costly deviation with no line.
    # Axis: every covered PR's body is checked: a stack whose second PR carries the costly deviation is refused, exactly one problem, naming PR #242.
    # NONE_BODY carries no build-record marker, so its text is followed by a newline and then BUILD_RECORD + DEGRADATIONS + the costly bullet.
    none_text = NONE_BODY.read_text(encoding="utf-8")
    costly = none_text + "\n" + BUILD_RECORD + DEGRADATIONS + "- [costly] " + VERIFY_GATE + ".\n"
    (problem,) = refused_with_bodies(TWIN, {241: none_text, 242: costly})
    assert problem.startswith("PR #242's costly deviation")


def test_a_costly_deviation_carried_into_what_we_are_accepting_builds_whatever_the_emphasis_or_full_stop():
    # Bites on: the match being exact (emphasis or the trailing full stop breaking it), or the check adding a card or changing what the sheet records.
    # Axis: K5 and the cards edge: the text after the label found inside an accepting line builds; the acceptance's own item is the only card; no nothingListed.
    text = (ACCEPTING + "\n- The **verify gate** did not run on the final head, so the last commit is unverified until CI runs.\n\n" + BUILD_RECORD + DEGRADATIONS
            + f"- [costly] {VERIFY_GATE}.\n")
    ((bullet, _),) = pr_sheet.listed_bullets(211, text)

    def edit(advisor):
        advisor.setdefault("items", []).append({"id": "verify-gate", "kind": "Accept", "title": VERIFY_GATE, "ifLeft": "The last commit is unverified until CI runs.", "options": "none"})
        advisor["accounting"] = {bullet: {"item": "verify-gate"}}
    sheet = with_bodies(SMALL, {211: text}, edit)
    assert [c["id"][:2] for c in sheet["cards"]] == ["i-"] and a_cards(sheet) == [] and "nothingListed" not in sheet["prSheet"]


@pytest.mark.parametrize("listing", ["- None\n", "None\n"], ids=["bullet", "paragraph"])
def test_a_degradations_list_that_reads_none_is_not_checked(listing):
    # Bites on: the word None being read as a costly deviation with no line.
    # Axis: K6: a list that is the single word None is no deviation: the build succeeds with nothingListed.
    sheet = with_bodies(SMALL, {211: ACCEPTING + "None.\n\n" + BUILD_RECORD + DEGRADATIONS + listing})
    assert sheet["prSheet"]["nothingListed"] is True and sheet["cards"] == []


def test_the_real_2075_body_with_unlabelled_deviations_is_refused_for_each_of_its_nine():
    # Bites on: a body written before the labels slipping through, or the check naming the wrong PR or missing a bullet.
    # Axis: K7: all nine unlabelled bullets of the real body are refused, each naming PR #2075, and nothing else is wrong with its accounting.
    problems = refused_with_bodies(CASE_2075, {2075: BODY_2075_REAL.read_text(encoding="utf-8")})
    assert len(problems) == 9
    assert all("unlabelled (read as costly)" in p and "PR #2075" in p for p in problems)


DEGRADATIONS_CASES = [
    pytest.param(BODY_COSTLY.read_text(encoding="utf-8"), [
        ("harmless", "The order rode a prompt file, not inline: the builder was pointed at the file and read it there."),
        ("costly", COSTLY_LINE)], id="shaped-fixture"),
    pytest.param(ACCEPTING + "- One.\n", [], id="no-marker"),
    pytest.param(None, [], id="not-a-string"),
    pytest.param(DEGRADATIONS + "- [Costly]  One,\n  and two.\n</details>\n- Three.\n", [("costly", "One, and two.")], id="stops-at-details"),
    pytest.param(DEGRADATIONS + "- One.\n\n### Next\n- Two.\n", [(None, "One.")], id="stops-at-a-heading"),
    pytest.param(DEGRADATIONS + "- [harmless] The order rode a prompt file.\n  - The builder read the file before starting.\n",
                 [("harmless", "The order rode a prompt file. - The builder read the file before starting.")],
                 id="a-nested-bullet-joins-its-labelled-degradation"),
    pytest.param("<!-- superheroes:degradations -->\n\n- [harmless] One.\n- Two.\n", [("harmless", "One."), (None, "Two.")],
                 id="a-flush-bullet-after-a-labelled-one-is-its-own-degradation"),
    pytest.param("```md\n<!-- superheroes:degradations -->\n- [costly] Example.\n```\n\n<!-- superheroes:degradations -->\n\nNone\n", [],
                 id="a-fenced-example-marker-is-not-the-section"),
]


@pytest.mark.parametrize("body, expected", DEGRADATIONS_CASES)
def test_degradations_listed_reads_the_labelled_items_and_stops_where_the_list_ends(body, expected):
    # Bites on: a label kept in the text or misread, an item past the list's end read, or a body with no marker (or none at all) listing items.
    # Axis: K1: the degradations the build checks are exactly the list under the marker, label split from text.
    assert pr_sheet.degradations_listed(body) == expected


def test_a_build_given_no_bodies_makes_no_accounting_check_and_has_no_nothing_listed():
    # Bites on: the API checking an accounting, or recording nothingListed, from bodies it was never given.
    # Axis: E10: bodies=None is a sheet that was not checked against the bodies: no a- card and no nothingListed, on a sheet with no cards and on one with, and an accounting it is given is ignored, however malformed.
    for case in (SMALL, TWIN, BIG):
        sheet = built(case)
        assert a_cards(sheet) == [] and "nothingListed" not in sheet["prSheet"] and "canonAccounted" not in sheet["prSheet"], case
    records, advisor = bundle(TWIN)
    advisor["accounting"] = ["not", "an", "object"]
    sheet = build(records, advisor)
    assert sheet == built(TWIN)


@pytest.mark.parametrize("body", ["body-none.md", "body-absent.md"])
def test_a_pr_whose_body_lists_nothing_is_built_with_nothing_listed_and_no_card(tmp_path, capsys, body):
    # Bites on: a body with no acceptance (None, or no heading at all) leaving nothingListed off, or inventing a card.
    # Axis: E1 and E3 through the command: the sheet records that the body was read and lists none.
    out = tmp_path / "sheet.json"
    code, said = main_build(capsys, SMALL, out, {211: FIXTURES / body})
    assert code == 0, said
    sheet = json.loads(out.read_text(encoding="utf-8"))
    assert sheet["cards"] == [] and sheet["prSheet"]["nothingListed"] is True and "canonAccounted" not in sheet["prSheet"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_an_empty_accounting_beside_bodies_that_list_nothing_builds_and_a_stray_key_does_not():
    # Bites on: an empty accounting being refused when nothing is listed, or a key that names no acceptance being let through because no body lists one.
    # Axis: E9: bodies that list nothing with accounting {} build with nothingListed; the same with one key are refused for that key.
    nothing = {211: NONE_BODY.read_text(encoding="utf-8")}
    sheet = with_bodies(SMALL, nothing, lambda advisor: advisor.update(accounting={}))
    assert sheet["prSheet"]["nothingListed"] is True and sheet["cards"] == []
    assert refused_with_bodies(SMALL, nothing, lambda advisor: advisor.update(accounting={"211:0123456789": {"item": "x"}})) == [
        'accounting key "211:0123456789" names no acceptance in the covered PR bodies']


@pytest.mark.parametrize("recorded, said, other", [
    pytest.param(True, INDEX_WORDS["nothingToAccept"], INDEX_WORDS["acceptingUnchecked"], id="recorded"),
    pytest.param(False, INDEX_WORDS["acceptingUnchecked"], INDEX_WORDS["nothingToAccept"], id="not-recorded"),
])
def test_the_built_index_row_of_a_zero_card_sheet_says_nothing_only_when_the_sheet_recorded_it(tmp_path, recorded, said, other):
    # Bites on: the index row's caption saying "Nothing to accept" of a sheet that never recorded that its PR bodies list none.
    # Axis: through the built index, a zero-card sheet's first caption part is index.nothingToAccept with nothingListed and index.acceptingUnchecked without it.
    sheet = built(SMALL)
    assert sheet["cards"] == [] and "nothingListed" not in sheet["prSheet"]
    root = tmp_path / "in"
    (root / "s").mkdir(parents=True)
    (root / "s" / "sheet.json").write_bytes(sheet_bytes(with_nothing_listed(sheet) if recorded else sheet))
    write_json(root / "s" / "store.json", {})
    source = write_json(root / "index.json", {"schema": "index-input/1", "questions": [], "mergeOrder": [211], "prs": [
        {"number": 211, "link": "https://sheets.example.test/pr-211", "sheet": "s/sheet.json", "store": "s/store.json"}]})
    (tmp_path / "out").mkdir()
    done = index_cli(source, tmp_path / "out" / "index.json")
    assert done.returncode == 0, done.stdout
    (row,) = json.loads((tmp_path / "out" / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
    assert row["total"] == 0 and row["caption"].split(" · ")[0] == said and other not in row["caption"]


CANON_ID_2 = "2026-10-22-abcdefgh-2"
THREE_ACCEPTANCES = {211: ACCEPTING + "\n- **The receipt says Thank you.** Customers see the new words.\n"
                          "- **The page title is unchanged.** Only the heading moved.\n"
                          "- **The old words stay in the email.** Receipts sent by email keep them.\n"}


def all_canon(bodies, ids, extra=None):
    """An edit that accounts every acceptance the bodies list to a Canon ruling (the n-th to ids[n % len(ids)]) and has the summary cite each id; extra(advisor) then adds to the input."""
    def edit(advisor):
        bullets = [bullet for pr in sorted(bodies) for bullet, _ in pr_sheet.listed_bullets(pr, bodies[pr])]
        advisor["accounting"] = {bullet: {"canon": ids[n % len(ids)]} for n, bullet in enumerate(bullets)}
        advisor["summary"] += " Ruled in " + " and ".join(dict.fromkeys(ids)) + "."
        if extra:
            extra(advisor)
    return edit


def index_row_of(tmp_path, sheet):
    """The row the built index gives a PR sheet that has no answers stored."""
    number = sheet["prSheet"]["number"]
    root = tmp_path / "in"
    (root / "s").mkdir(parents=True)
    (root / "s" / "sheet.json").write_bytes(sheet_bytes(sheet))
    write_json(root / "s" / "store.json", {})
    source = write_json(root / "index.json", {"schema": "index-input/1", "questions": [], "mergeOrder": [number], "prs": [
        {"number": number, "link": f"https://sheets.example.test/pr-{number}", "sheet": "s/sheet.json", "store": "s/store.json"}]})
    (tmp_path / "out").mkdir()
    done = index_cli(source, tmp_path / "out" / "index.json")
    assert done.returncode == 0, done.stdout
    (row,) = json.loads((tmp_path / "out" / "index.json").read_text(encoding="utf-8"))["index"]["rows"]
    return row


def test_a_sheet_whose_every_acceptance_is_a_canon_ruling_is_built_with_canon_accounted_and_says_so_on_every_surface(tmp_path):
    # Bites on: the build leaving a Canon-only sheet to read "not checked" (or "nothing to accept"), the ids unsorted or repeated, or the prose or the index row not reading the field.
    # Axis: E3: 3 acceptances over 2 ids (one repeated, written out of order) build with no card, canonAccounted the 2 ids sorted, no nothingListed;
    # the one sheet then reads pr.acceptingCanon with the ids in the prose and index.acceptingCanon on the index row, never the nothing or unchecked words.
    bodies = THREE_ACCEPTANCES
    sheet = with_bodies(SMALL, bodies, all_canon(bodies, [CANON_ID_2, CANON_ID, CANON_ID_2]))
    assert sheet["cards"] == [] and sheet["prSheet"]["canonAccounted"] == [CANON_ID, CANON_ID_2] and "nothingListed" not in sheet["prSheet"]
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []
    prose = sheet_prose.render(sheet)
    line = WORDS["acceptingCanon"].replace("{ids}", f"{CANON_ID}, {CANON_ID_2}")
    assert f"**{WORDS['acceptingHeading']}**\n\n{line}\n" in prose
    assert WORDS["nothingToAccept"] not in prose and WORDS["acceptingUnchecked"] not in prose
    caption = index_row_of(tmp_path, sheet)["caption"]
    assert caption.split(" · ")[0] == INDEX_WORDS["acceptingCanon"]
    assert INDEX_WORDS["nothingToAccept"] not in caption and INDEX_WORDS["acceptingUnchecked"] not in caption


def test_a_stack_whose_every_acceptance_over_two_prs_is_a_canon_ruling_records_one_sorted_distinct_list():
    # Bites on: the stack's list being per PR, repeating an id two PRs share, or left unsorted.
    # Axis: E10: the twin stack's 5 acceptances (3 on #241, 2 on #242) accounted to 2 ids written out of order give one list of the 2 ids, sorted; its 2 leftover cards stay.
    bodies = read_bodies(BODY_TWIN)
    sheet = with_bodies(TWIN, bodies, all_canon(bodies, [CANON_ID_2, CANON_ID, CANON_ID_2, CANON_ID, CANON_ID_2]))
    assert sheet["prSheet"]["canonAccounted"] == [CANON_ID, CANON_ID_2] and "nothingListed" not in sheet["prSheet"]
    assert len(sheet["cards"]) == 2 and a_cards(sheet) == []
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []


def test_a_canon_only_sheet_that_carries_another_card_records_canon_accounted_and_keeps_its_card(tmp_path):
    # Bites on: canonAccounted being left off, or the surfaces taking over from the card, when a Canon-only sheet also has an advisor card.
    # Axis: E9: every acceptance Canon plus one advisor item: the field is recorded, there is exactly one card, and the prose and index row read as a sheet with a card (no Canon line).
    bodies = THREE_ACCEPTANCES
    item = {"id": "heads-up", "kind": "Accept", "title": "A heads-up", "ifLeft": "Something to know.", "options": "none"}
    sheet = with_bodies(SMALL, bodies, all_canon(bodies, [CANON_ID, CANON_ID, CANON_ID_2], lambda advisor: advisor.update(items=[item])))
    assert sheet["prSheet"]["canonAccounted"] == [CANON_ID, CANON_ID_2] and len(sheet["cards"]) == 1
    assert list(Draft202012Validator(SCHEMA).iter_errors(sheet)) == [] and check_sheet_problems(sheet) == []
    assert "Checked against the PR body" not in sheet_prose.render(sheet)
    assert index_row_of(tmp_path, sheet)["caption"].split(" · ")[0] == "0 of 1 accepted"


def test_a_sheet_with_one_acceptance_not_accounted_to_canon_records_no_canon_accounted():
    # Bites on: canonAccounted being set when only some acceptances are Canon rulings (the all-Canon condition loosened to any).
    # Axis: E4: PR #2075 with one acceptance moved to Canon (the rest an item, a fold line or a leftover), and a small PR with two Canon and one item acceptance, record no canonAccounted; their cards are those of the build without it.
    def one_canon(advisor):
        advisor["accounting"][BULLETS_2075[6]] = {"canon": CANON_ID}
        advisor["summary"] += f" Ruled in {CANON_ID}."
    sheet = with_bodies(CASE_2075, BODIES_2075, one_canon)
    assert "canonAccounted" not in sheet["prSheet"] and "nothingListed" not in sheet["prSheet"] and len(sheet["cards"]) == 5

    def two_canon_one_item(advisor):
        bullets = [bullet for bullet, _ in pr_sheet.listed_bullets(211, THREE_ACCEPTANCES[211])]
        advisor["items"] = [{"id": "heads-up", "kind": "Accept", "title": "A heads-up", "ifLeft": "Something to know.", "options": "none"}]
        advisor["accounting"] = {bullets[0]: {"canon": CANON_ID}, bullets[1]: {"canon": CANON_ID}, bullets[2]: {"item": "heads-up"}}
        advisor["summary"] += f" Ruled in {CANON_ID}."
    sheet = with_bodies(SMALL, THREE_ACCEPTANCES, two_canon_one_item)
    assert "canonAccounted" not in sheet["prSheet"] and "nothingListed" not in sheet["prSheet"] and len(sheet["cards"]) == 1


def accounted_twin():
    """The twin stack's input with its 5 listed acceptances folded into one item."""
    advisor = load("input-twin.json")
    fold_all(read_bodies(BODY_TWIN))(advisor)
    return advisor


def twin_world(tmp_path, capsys):
    """The twin stack's first sheet at tmp_path/earlier/sheet.json, and the store of an owner who accepted every card and gave a Merge on it.

    Returns the sheet's bytes, the store and the card ids. Every card here has no options, so Accept is the answer to each."""
    (tmp_path / "earlier").mkdir()
    first = tmp_path / "earlier" / "sheet.json"
    code, said = main_build(capsys, TWIN, first, BODY_TWIN, advisor=write_json(tmp_path / "first.json", accounted_twin()))
    assert code == 0, said
    raw = first.read_bytes()
    ids = [c["id"] for c in json.loads(raw)["cards"]]
    digest = hashlib.sha256(raw).hexdigest()
    store = store_of({i: card_doc("accept") for i in ids}, verdict=merge_doc([f"answers/{i}@{REV_A}" for i in ids], digest), digest=digest)
    return raw, store, ids


def carried_twin(tmp_path, capsys, bodies, name):
    """The twin stack carried forward from twin_world's sheet, its accounting unchanged, built from `bodies`; returns main's exit code and result."""
    source = write_json(tmp_path / "in.json", carry_input(accounted_twin(), {"241": "1" * 40, "242": "2" * 40}))
    return main_build(capsys, TWIN, tmp_path / name, bodies, advisor=source)


def test_a_carry_over_unchanged_bodies_and_accounting_keeps_every_id_and_the_merge_and_an_edited_bullet_must_be_accounted_again(tmp_path, capsys):
    # Bites on: a card's id moving across a carry (the saved answers and the Merge are lost), or a bullet edited after the accounting was written being built as though it were still accounted for.
    # Axis: ids are the PR, the input's own item and the card's words, nothing about the bodies: the carry keeps 3 of 3 answers and the Merge; an edit to one bullet's text re-keys it, so its old entry names no acceptance and the new text is unaccounted for.
    raw, store, ids = twin_world(tmp_path, capsys)
    assert len(ids) == 3 and len(set(ids)) == 3 and [i[:2] for i in ids] == ["f-", "f-", "i-"]
    before = pr_sheet.pr_state(raw, store)
    assert (before["state"], before["accepted"], before["total"]) == ("ready", 3, 3)
    code, said = carried_twin(tmp_path, capsys, BODY_TWIN, "carried.json")
    assert code == 0, said
    carried = (tmp_path / "carried.json").read_bytes()
    sheet = json.loads(carried)
    assert sheet["prSheet"]["carriedForward"]["sheets"] == [hashlib.sha256(raw).hexdigest()] and sheet["prSheet"]["commit"] == "2" * 40
    assert [c["id"] for c in sheet["cards"]] == ids and a_cards(sheet) == []
    after = pr_sheet.pr_state(carried, store)
    assert (after["state"], after["accepted"], after["total"]) == ("ready", 3, 3)
    edited = tmp_path / "body-242-edited.md"
    text = BODY_TWIN[242].read_text(encoding="utf-8")
    edited.write_text(text.replace("a large file takes about twice as long", "a large file takes about three times as long"), encoding="utf-8")
    assert edited.read_text(encoding="utf-8") != text
    code, said = carried_twin(tmp_path, capsys, {241: BODY_TWIN[241], 242: edited}, "edited.json")
    assert code == 1 and not (tmp_path / "edited.json").exists()
    old = {bullet for bullet, _ in pr_sheet.listed_bullets(242, text)} - {bullet for bullet, _ in pr_sheet.listed_bullets(242, edited.read_text(encoding="utf-8"))}
    (gone,) = old
    assert len(said["problems"]) == 2
    assert said["problems"][0].startswith("PR #242's acceptance 242:") and "is not accounted for" in said["problems"][0]
    assert said["problems"][1] == f'accounting key "{gone}" names no acceptance in the covered PR bodies'


def refused_small(capsys, tmp_path, *values):
    """The small PR's build through main with these --pr-body values, which must be refused with nothing written; returns the problems."""
    out = tmp_path / "sheet.json"
    argv = ["build", "--record", FIXTURES / "record-small.json", "--input", FIXTURES / "input-small.json", "--out", out]
    for value in values:
        argv += ["--pr-body", value]
    code, said = run_main(capsys, *argv)
    assert code == 1 and said["ok"] is False and not out.exists()
    return said["problems"]


@pytest.mark.parametrize("value", ["x", "0=f", "abc=f", "211"])
def test_a_pr_body_value_that_is_not_a_number_and_a_file_is_refused(tmp_path, capsys, value):
    # Bites on: a malformed --pr-body crashing, being skipped, or raising a parser error instead of a refusal problem.
    # Axis: E8: the problem is exactly the one line, the command exits 1 and nothing is written.
    assert refused_small(capsys, tmp_path, value) == [f"--pr-body '{value}' must be <PR number>=<file>"]


def test_a_repeated_pr_body_is_refused_once_however_often_it_repeats(tmp_path, capsys):
    # Bites on: a repeated --pr-body silently taking the first or last, or the refusal repeated for every repeat.
    # Axis: E8: one problem naming the PR.
    body = f"211={NONE_BODY}"
    assert refused_small(capsys, tmp_path, body, body) == ["--pr-body names PR #211 more than once"]
    assert refused_small(capsys, tmp_path, body, body, body) == ["--pr-body names PR #211 more than once"]


def test_a_pr_body_naming_a_pr_the_sheet_does_not_cover_is_refused(tmp_path, capsys):
    # Bites on: a body for a PR outside the sheet being ignored.
    # Axis: E8: the extra --pr-body is one problem that names the PR, on a pr sheet and on a stack.
    assert refused_small(capsys, tmp_path, f"211={NONE_BODY}", f"999={NONE_BODY}") == ["--pr-body names PR #999, which the sheet does not cover"]
    out = tmp_path / "stack.json"
    code, said = main_build(capsys, TWIN, out, {**BODY_TWIN, 243: NONE_BODY})
    assert code == 1 and said["problems"] == ["--pr-body names PR #243, which the sheet does not cover"] and not out.exists()


def test_a_pr_body_file_that_cannot_be_read_is_refused_naming_the_file(tmp_path, capsys):
    # Bites on: an unreadable body crashing, or being read as an empty body that lists nothing.
    # Axis: E9: one problem that names the file and the PR; nothing is written.
    missing = tmp_path / "missing.md"
    (problem,) = refused_small(capsys, tmp_path, f"211={missing}")
    assert problem.startswith(f"{missing} could not be read as PR #211's body: ")


def test_a_pr_body_file_that_is_not_utf_8_is_refused_naming_the_file(tmp_path, capsys):
    # Bites on: a body that is not UTF-8 being decoded with replacement characters, so a sheet is built from a body that was not read.
    # Axis: E9: one problem that names the file and the PR; nothing is written.
    binary = tmp_path / "binary.md"
    binary.write_bytes(ACCEPTING.encode("utf-8") + b"- caf\xe9 \xff\xfe\n")
    (problem,) = refused_small(capsys, tmp_path, f"211={binary}")
    assert problem.startswith(f"{binary} could not be read as PR #211's body: 'utf-8' codec can't decode byte")


def test_pr_body_on_the_index_command_is_a_parser_error(tmp_path, capsys):
    # Bites on: `index` taking --pr-body and ignoring it.
    # Axis: E8: the parser refuses it before anything is read, exit status 2 and the words on stderr.
    with pytest.raises(SystemExit) as caught:
        pr_sheet.main(["index", "--input", str(tmp_path / "in.json"), "--out", str(tmp_path / "out.json"), "--pr-body", f"211={NONE_BODY}"])
    assert caught.value.code == 2
    assert "--pr-body is only for build" in capsys.readouterr().err



# Bites on: a fence opened on a list item's continuation line being measured from column 0, so its valid indented closer leaves it open.
def test_a_continuation_line_fence_closes_at_the_list_items_content_column():
    body = "Intro\n\n1. Example:\n   ```\n    code\n    ```\n\n## What we're accepting\n\n- A breaking change\n"
    assert pr_sheet.accepting_listed(body) == ["A breaking change"]
