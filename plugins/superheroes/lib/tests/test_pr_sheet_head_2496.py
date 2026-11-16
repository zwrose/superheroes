"""Guards for issue 2496's sheet consequences: the sheet shows the PR's head and its CI as read when it is built (headNow),
carries no history note, and can be held (taken down) after a material move."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

import pr_sheet
import sheet_prose
from test_pr_sheet import A_ID, B_ID, SHEET_B, SHEET_C, merge_doc, sheet_bytes, state_of, verdicts_of
from test_pr_sheet_spec import world  # noqa: F401  (the spec-PR fixture)
from test_pr_sheet_spec import WORDS as SPEC_WORDS

LIB = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
WORDS = json.loads((LIB.parent / "theme" / "sheet-words.json").read_text(encoding="utf-8"))["pr"]

SMALL = (["record-small.json"], "input-small.json")
BIG = (["record-big.json"], "input-big.json")
STACK = (["record-stack-1.json", "record-stack-2.json", "record-stack-3.json"], "input-stack.json")
OLD = "0f1e2d3c4b5a69788796a5b4c3d2e1f001122334"  # record-small's final commit (commit A)
NEW = "b" * 40  # the PR's head as the vet reads it when the sheet is built (commit B)
LAYERS = {"5": "5" * 40, "6": "6" * 40, "7": "7" * 40}  # the stack's heads now
CARRY = {"date": "2026-09-30", "moved": "the branch was brought current with main", "whyNotMaterial": "main added only a README line"}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def bundle(case):
    records, advisor = case
    return [load(r) for r in records], load(advisor)


def build(records, advisor, previous=None):
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, previous=previous)


def problems_of(records, advisor, previous=None):
    with pytest.raises(pr_sheet.Refusal) as caught:
        build(records, advisor, previous)
    return caught.value.problems


def carried(advisor, heads):
    return {**copy.deepcopy(advisor), "carriedForward": {"fromSheet": "earlier/sheet.json", "heads": dict(heads), **CARRY}}


# --- (a) the sheet's commit and CI are the head's, read when the sheet is built ---

# Bites on: whatChanged.ci or the sheet's commit read from the record (a record written before CI finished keeps showing CI pending on a green head).
def test_a_pr_sheet_shows_the_ci_and_commit_of_the_head_it_is_built_for_not_the_records():
    # Axis: a record that stored ci pending on commit A, with headNow naming head B green, builds a sheet whose commit is B and whose CI line is green on B.
    records, advisor = bundle(SMALL)
    records[0]["ci"] = {"state": "pending", "sha": OLD, "source": "GitHub checks"}
    assert records[0]["finalCommit"]["sha"] == OLD
    advisor["headNow"] = {"211": {"commit": NEW, "ci": "green"}}
    sheet = build(records, advisor)
    assert sheet["prSheet"]["commit"] == NEW
    assert sheet["prSheet"]["whatChanged"]["ci"] == {"state": "green", "commit": NEW}
    assert "pending" not in json.dumps(sheet) and OLD not in json.dumps(sheet)


# Bites on: a stack layer's "Checks were" line or prs[].commit read from the layer's record, or the top layer's commit and CI taken from a lower layer.
def test_a_stack_sheet_reads_every_layers_head_and_ci_from_head_now():
    # Axis: on a stack, each layer's history line, each prs[].commit, the sheet's commit and its CI line are that layer's headNow entry, whatever its record stored.
    records, advisor = bundle(STACK)
    for record in records:
        record["ci"] = {"state": "pending", "sha": record["finalCommit"]["sha"], "source": "GitHub checks"}
    advisor["headNow"] = {"5": {"commit": LAYERS["5"], "ci": "red"}, "6": {"commit": LAYERS["6"], "ci": "pending"}, "7": {"commit": LAYERS["7"], "ci": "green"}}
    sheet = build(records, advisor)
    part = sheet["prSheet"]
    assert [(p["number"], p["commit"]) for p in part["prs"]] == [(5, LAYERS["5"]), (6, LAYERS["6"]), (7, LAYERS["7"])]
    assert part["commit"] == LAYERS["7"] and part["whatChanged"]["ci"] == {"state": "green", "commit": LAYERS["7"]}
    expected = {"5": "red", "6": "pending", "7": "green"}
    for number, state in expected.items():
        line = "#%s: " % number + WORDS["historyChecks"].replace("{state}", state).replace("{commit}", LAYERS[number])
        assert line in part["history"], line
    for record in records:
        assert record["finalCommit"]["sha"] not in json.dumps(sheet)


# --- (b) a headNow that is missing, partial or malformed is refused, naming it ---

ENTRY = {"commit": NEW, "ci": "green"}
REFUSED_HEAD_NOW = [
    pytest.param(SMALL, lambda r, a: a.pop("headNow"), "headNow is required", id="missing-on-a-pr"),
    pytest.param(STACK, lambda r, a: a.pop("headNow"), "headNow is required", id="missing-on-a-stack"),
    pytest.param(SMALL, lambda r, a: a["headNow"].update({"212": dict(ENTRY)}), "headNow has PR 212", id="extra-pr"),
    pytest.param(STACK, lambda r, a: a["headNow"].update({"8": dict(ENTRY)}), "headNow has PR 8", id="extra-layer"),
    pytest.param(STACK, lambda r, a: a["headNow"].pop("6"), "headNow is missing PR 6", id="missing-layer"),
    pytest.param(SMALL, lambda r, a: a.__setitem__("headNow", {}), "headNow is missing PR 211", id="empty"),
    pytest.param(SMALL, lambda r, a: a.__setitem__("headNow", [dict(ENTRY)]), "headNow must be an object", id="not-an-object"),
    pytest.param(SMALL, lambda r, a: a["headNow"].update({"211": "green"}), "headNow 211 must be an object", id="entry-not-an-object"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].pop("ci"), "headNow 211 is missing ci", id="entry-without-ci"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].pop("commit"), "headNow 211 is missing commit", id="entry-without-commit"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(sha=OLD), "headNow 211 has an unknown key sha", id="entry-unknown-key"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(commit="abc1234"), "headNow 211 commit must be a commit id of 40 lowercase hex", id="short-commit"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(commit="B" * 40), "headNow 211 commit must be a commit id of 40 lowercase hex", id="uppercase-commit"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(commit=NEW + "\n"), "headNow 211 commit must be a commit id of 40 lowercase hex", id="commit-with-a-newline"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(commit=7), "headNow 211 commit must be a commit id of 40 lowercase hex", id="commit-not-a-string"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(ci=""), "headNow 211 ci must be a non-empty string", id="empty-ci"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(ci="  "), "headNow 211 ci must be a non-empty string", id="blank-ci"),
    pytest.param(SMALL, lambda r, a: a["headNow"]["211"].update(ci=None), "headNow 211 ci must be a non-empty string", id="ci-not-a-string"),
    pytest.param(SMALL, lambda r, a: a.__setitem__("headNow", {"PR-211": dict(ENTRY)}), "headNow key 'PR-211' must be a PR number", id="key-not-a-number"),
]


@pytest.mark.parametrize("case, mutate, expected", REFUSED_HEAD_NOW)
def test_a_head_now_that_is_missing_partial_or_malformed_is_refused_naming_it(case, mutate, expected):
    # Bites on: a sheet built with no headNow (a silent fall-back to the record's ci and commit), or with one that misses a covered PR, names one it does not cover, or holds a value that is no head commit or no CI state.
    # Axis: fail-closed edge: no headNow on a records-built sheet is a Refusal, never a fall-back; every malformed shape names the key and what is wrong.
    records, advisor = bundle(case)
    advisor["headNow"] = {n: {**ENTRY, "commit": NEW} for n in (advisor["headNow"] if "headNow" in advisor else {})}
    mutate(records, advisor)
    assert any(expected in problem for problem in problems_of(records, advisor)), expected


def test_the_input_fixtures_name_the_head_the_record_certified():
    # Axis: the shipped input fixtures keep their sheets as they were: each headNow commit is its record's final commit and its CI is the one the record stored.
    for records, name in (SMALL, BIG, STACK, ("record-twin-a.json record-twin-b.json".split(), "input-twin.json"), (["record-2075.json"], "input-2075.json")):
        recs, advisor = bundle((records, name))
        assert {str(r["pr"]): {"commit": r["finalCommit"]["sha"], "ci": r["ci"]["state"]} for r in recs} == advisor["headNow"], name


def test_headnow_is_refused_in_the_spec_pr_mode(world):  # noqa: F811
    # Bites on: a spec PR sheet accepting headNow beside its own spec.ci, so two CI facts disagree on one sheet.
    # Axis: spec mode keeps spec.ci and refuses headNow, naming it.
    base, _, advisor = world
    given = {**advisor, "headNow": {"41": dict(ENTRY)}}
    with pytest.raises(pr_sheet.Refusal) as caught:
        pr_sheet.build([], copy.deepcopy(given), SPEC_WORDS, spec_base=base)
    assert any("headNow is refused on a spec-PR sheet" in p for p in caught.value.problems)
    built = pr_sheet.build([], copy.deepcopy(advisor), SPEC_WORDS, spec_base=base)
    assert built["prSheet"]["whatChanged"]["ci"] == {"state": "passing", "commit": "3" * 40}


@pytest.mark.parametrize("case, heads, wrong", [(SMALL, {"211": "1" * 40}, "211"), (STACK, {"5": LAYERS["5"], "6": "9" * 40, "7": LAYERS["7"]}, "6")], ids=["pr", "stack"])
def test_a_carry_whose_head_disagrees_with_head_now_is_refused_naming_the_pr(case, heads, wrong):
    # Bites on: a carry whose heads name a commit other than the one headNow says the PR is at, which would show one head and certify another.
    # Axis: each carriedForward.heads[n] must equal headNow[n].commit; a disagreement is refused, naming the carry's heads and the PR.
    records, advisor = bundle(case)
    previous = sheet_bytes(build(records, advisor))
    advisor["headNow"] = {n: {"commit": c, "ci": "green"} for n, c in heads.items()}
    advisor["headNow"][wrong] = {"commit": NEW, "ci": "green"}  # headNow says the PR is at NEW; the carry says it is at heads[wrong]
    assert heads[wrong] != NEW
    found = problems_of(records, carried(advisor, heads), previous)
    assert any(f"carriedForward heads {wrong} is {heads[wrong]}" in p and f"headNow {wrong} commit is" in p for p in found), found


def test_a_carry_whose_heads_agree_with_head_now_builds_with_them():
    # Axis: the agreeing case builds, so the refusal above is the disagreement and nothing else.
    records, advisor = bundle(SMALL)
    previous = sheet_bytes(build(records, advisor))
    advisor["headNow"] = {"211": {"commit": "1" * 40, "ci": "green"}}
    sheet = build(records, carried(advisor, {"211": "1" * 40}), previous)
    assert sheet["prSheet"]["commit"] == "1" * 40 and sheet["prSheet"]["whatChanged"]["ci"] == {"state": "green", "commit": "1" * 40}


# --- (c) a carried sheet's prose shows no note of the carry ---

CARRIED_WORDS = ["Carried forward", "carry forward", "not a material change", CARRY["moved"], CARRY["whyNotMaterial"], CARRY["date"]]


@pytest.mark.parametrize("case", [SMALL, STACK], ids=["pr", "stack"])
def test_a_carried_sheets_prose_carries_none_of_the_carried_words(case):
    # Bites on: the chat prose drawing the carried heading or its text, or the carry's date, what moved or why it is not material, or drawing the changed box in its place.
    # Axis: a sheet republished after a non-material move keeps its answers and verdict but shows no "carried forward" or "moved past" note; the carry's date, moved and whyNotMaterial are shown nowhere.
    records, advisor = bundle(case)
    previous = sheet_bytes(build(records, advisor))
    heads = {"211": "1" * 40} if case is SMALL else dict(LAYERS)
    advisor["headNow"] = {n: {"commit": c, "ci": "green"} for n, c in heads.items()}
    sheet = build(records, carried(advisor, heads), previous)
    assert "carriedForward" in sheet["prSheet"] and sheet_prose.check_sheet(sheet) == []
    prose = sheet_prose.render(sheet)
    for word in CARRIED_WORDS:
        assert word not in prose, word
    for key in ("carriedHeading", "carried", "changedHeading"):
        assert WORDS.get(key, "\0") not in prose, key
    assert WORDS["changed"].split("{previous}")[0] not in prose
    top = heads["211"] if case is SMALL else heads["7"]
    assert WORDS["verdictHeading"] in prose and WORDS["describesCommit"].replace("{commit}", top[:7]) in prose


def test_an_uncarried_republish_with_a_previous_commit_keeps_the_changed_box_in_the_prose():
    # Bites on: the changed box dropped with the carried one, so a material republish (previousCommit alone) says nothing of the move.
    records, advisor = bundle(SMALL)
    advisor["previousCommit"] = OLD
    prose = sheet_prose.render(build(records, advisor))
    assert "**%s**" % WORDS["changedHeading"] in prose and WORDS["changed"].replace("{previous}", OLD[:7]) in prose


# --- (d) hold ---

def write(path, value):
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def hold_cli(capsys, sheet, tmp_path, name="held.json"):
    code = pr_sheet.main(["hold", "--sheet", str(sheet), "--out", str(tmp_path / name)])
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("case", [BIG, STACK], ids=["pr", "stack"])
def test_hold_writes_the_same_sheet_held_with_no_cards(case, capsys, tmp_path):
    # Bites on: hold changing anything but prSheet.held and cards, leaving a card on the held sheet, or writing a sheet the schema or the page's check refuses.
    # Axis: hold takes a published pr or stack sheet.json and writes it with prSheet.held true and cards emptied, and prints {ok, out}.
    records, advisor = bundle(case)
    sheet = build(records, advisor)
    assert sheet["cards"], "the fixture has cards to take down"
    source = write(tmp_path / "sheet.json", sheet)
    code, said = hold_cli(capsys, source, tmp_path)
    assert code == 0 and said == {"ok": True, "out": str(tmp_path / "held.json")}
    held = json.loads((tmp_path / "held.json").read_text(encoding="utf-8"))
    assert held["prSheet"]["held"] is True and held["cards"] == []
    assert {**held, "prSheet": {k: v for k, v in held["prSheet"].items() if k != "held"}, "cards": sheet["cards"]} == sheet
    assert sheet_prose.check_sheet(held) == []


@pytest.mark.parametrize("sheet", [
    {"schema": "superheroes-sheet/1", "kind": "final", "title": "T", "final": {}, "cards": []},
    {"schema": "superheroes-sheet/1", "kind": "index", "title": "T", "index": {}, "cards": []},
    {"schema": "superheroes-sheet/1", "kind": "remainder", "title": "T", "cards": []},
    [],
    "{not json",
], ids=["final", "index", "remainder", "not-an-object", "not-json"])
def test_hold_refuses_any_sheet_that_is_not_a_pr_or_stack_sheet(sheet, capsys, tmp_path):
    # Bites on: hold taking down a final, remainder or index sheet (or a file that is no sheet), or writing a file when it refuses.
    # Axis: hold refuses any other kind: exit 1, {"ok": false, "problems": [...]}, and nothing written.
    source = write(tmp_path / "sheet.json", sheet)
    code, said = hold_cli(capsys, source, tmp_path)
    assert code == 1 and said["ok"] is False and said["problems"] and not (tmp_path / "held.json").exists()


def test_hold_refuses_a_missing_file_and_a_pr_sheet_that_does_not_fit_the_schema(capsys, tmp_path):
    # Axis: a sheet that cannot be read, or is a pr sheet the schema refuses, is a refusal that writes nothing.
    code, said = hold_cli(capsys, tmp_path / "absent.json", tmp_path)
    assert code == 1 and said["ok"] is False and not (tmp_path / "held.json").exists()
    records, advisor = bundle(SMALL)
    broken = build(records, advisor)
    broken["prSheet"].pop("whatChanged")
    code, said = hold_cli(capsys, write(tmp_path / "broken.json", broken), tmp_path)
    assert code == 1 and said["ok"] is False and not (tmp_path / "held.json").exists()


# --- (e) a held sheet reads no verdict ---

def held_bytes(raw):
    """The bytes of the sheet `raw` (a published sheet's exact bytes) taken down."""
    return sheet_bytes(pr_sheet.hold(raw))


@pytest.mark.parametrize("sheet, stored_under", [(SHEET_B, A_ID), (SHEET_C, A_ID), (SHEET_C, B_ID), (SHEET_B, B_ID)],
                         ids=["one-hop-earliest", "two-hops-earliest", "two-hops-middle", "own-digest"])
def test_a_held_sheet_that_had_a_standing_merge_reads_being_fixed(sheet, stored_under):
    # Bites on: pr_state looking up a verdict for a held sheet, under its own digest or any digest of its carry chain, so a taken-down sheet still lists as ready.
    # Axis: fail-closed edge: a held sheet's verdict is never read, through any revision in its chain; it reads being-fixed whatever the store holds.
    store = verdicts_of((stored_under, merge_doc(digest=stored_under)))
    assert state_of(sheet, store) == "ready", "the sheet stood before it was held"
    held = held_bytes(sheet)
    assert state_of(held, store) == "being-fixed"
    held_digest = hashlib.sha256(held).hexdigest()
    assert pr_sheet.pr_state(held, verdicts_of((held_digest, merge_doc(digest=held_digest)))) == {
        "state": "being-fixed", "accepted": 0, "total": 0, "walked": 0, "walkTotal": 0}


# --- (f) a held sheet's prose is the notice alone ---

@pytest.mark.parametrize("emptied", [True, False], ids=["emptied", "cards-left-on-it"])
@pytest.mark.parametrize("case", [BIG, STACK], ids=["pr", "stack"])
def test_a_held_sheets_prose_is_the_title_line_the_held_heading_and_the_notice_and_nothing_else(case, emptied):
    # Bites on: the held prose still carrying what changed, a card, a folded part or the verdict line.
    # Axis: a held sheet's prose is the title line, the held heading and the held notice, whatever else the sheet holds.
    records, advisor = bundle(case)
    sheet = build(records, advisor)
    sheet["title"] = "Plain title"
    sheet["prSheet"]["held"] = True
    if emptied:
        sheet["cards"] = []
    assert sheet_prose.check_sheet(sheet) == []
    prose = sheet_prose.render(sheet)
    count = len(sheet["cards"])
    assert prose == "**Plain title**: %d item%s for you.\n\n**%s**\n\n%s\n" % (count, "" if count == 1 else "s", WORDS["heldHeading"], WORDS["held"])
    for heading in ("whatChangedHeading", "acceptingHeading", "verdictHeading", "reviewHeading", "walkHeading"):
        assert WORDS[heading] not in prose, heading


# --- (g) the advisor's republish when the PR is READY again ---

def test_after_a_hold_an_unsigned_republish_keeps_the_card_ids_and_shows_the_changed_box():
    # Bites on: the republish after a take-down starting from nothing (new card ids that lose the owner's answers), or carrying the earlier sheet's note, or dropping previousCommit.
    # Axis: the existing changed path: the same input with previousCommit builds an unsigned sheet (no carriedForward, not held) whose cards keep their ids, and its prose shows the changed words.
    records, advisor = bundle(BIG)
    first = build(records, advisor)
    held = json.loads(held_bytes(sheet_bytes(first)))
    assert held["prSheet"]["held"] is True and held["cards"] == []
    again_input = {**advisor, "previousCommit": held["prSheet"]["commit"], "headNow": {"214": {"commit": NEW, "ci": "green"}}}
    again = build(records, again_input)
    part = again["prSheet"]
    assert part["previousCommit"] == held["prSheet"]["commit"] and part["commit"] == NEW
    assert "carriedForward" not in part and "held" not in part
    assert [c["id"] for c in again["cards"]] == [c["id"] for c in first["cards"]] and again["cards"]
    prose = sheet_prose.render(again)
    assert "**%s**" % WORDS["changedHeading"] in prose and WORDS["changed"].replace("{previous}", held["prSheet"]["commit"][:7]) in prose
