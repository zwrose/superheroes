"""End-to-end guards for the index: the real page writes the store, the builder reads it, and the index and the page must agree.

Each chain runs the page in the harness, takes what it wrote, turns that into a store dump and feeds it to pr_state or the index builder.
The census at the end checks, over a table of store states, that the index's state and counts equal what the page shows for the same store.
"""
import copy
import json
from pathlib import Path

import pytest

import pr_sheet
from test_review_template import WORDS, _sample_files, _sheet_digest, _with
from test_review_template_index import _page as _index_page
from test_review_template_pr import PW, _fill, _page as _pr_page

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
IW = WORDS["index"]
LINK = "https://sheets.example.test/pr-214"
NEW_COMMIT = "b2c3d4e5f60718293a4b5c6d7e8f901234567890"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _build(records, advisor):
    return pr_sheet.build([_load(name) if isinstance(name, str) else name for name in records], advisor, WORDS["pr"])


BIG = _build(["record-big.json"], _load("input-big.json"))
STACK = _build(["record-stack-1.json", "record-stack-2.json", "record-stack-3.json"], _load("input-stack.json"))
QUESTION = dict(_load("index-input.json")["questions"][0], pictures=[])


def _card_id(sheet, text):
    return next(card["id"] for card in sheet["cards"] if text in card["question"])


# The big sheet's three cards: A has no options (Accept / Discuss), B is a leftover (Keep it, Fix in a follow-up, Fix before merge), C is an item whose second option sends the PR back.
A, B, C = _card_id(BIG, "not told a retry"), _card_id(BIG, "no email"), _card_id(BIG, "ten minutes")


def _bytes(sheet):
    """The bytes the page fetches as sheet.json, which are the bytes pr_state hashes."""
    return _sample_files(sheet)["sheet.json"]["body"].encode("utf-8")


# What a scenario can read and do on a pr or stack sheet, beside the page's own PRELUDE.
VIEW = r"""
const A = __A__, B = __B__, C = __C__;
const mergeButton = () => verdictRow()[0];
const sendBackNode = () => verdict().children.find((child) => child.id === "verdict-send-back");
const walkNode = () => {
  const walk = part("pr-walk");
  return walk ? t.all(walk).find((node) => node.id === "walk-count") : undefined;
};
const pageView = () => {
  const walk = walkNode();
  return {
    standing: mergeButton().getAttribute("aria-pressed") === "true" && mergeButton().disabled === false,
    sendBack: sendBackNode().hidden ? null : sendBackNode().textContent,
    count: t.count(),
    walk: walk === undefined || walk.hidden ? "" : t.text(walk).replace(/\s+/g, " ").trim(),
  };
};
const settled = async () => { await t.tick(); await t.tick(); };
const tap = async (id, label) => { t.click(t.button(id, label)); await t.tick(); };
const acceptAll = async () => { await tap(A, "Accept"); await tap(B, "Keep it"); await tap(C, "Ten minutes"); };
const merge = async (note) => {
  if (note) { t.type(verdictNote(), note, "change"); await t.tick(); }
  t.click(mergeButton());
  await t.tick();
};
""".replace("__A__", json.dumps(A)).replace("__B__", json.dumps(B)).replace("__C__", json.dumps(C))


def _empty():
    return {"answers": {}, "verdict": {}, "walk": {}}


def _apply(store, written):
    """The store after a page's writes (path to body, as the harness logs them) land on it, in write order."""
    out = copy.deepcopy(store)
    for path, body in written.items():
        collection, doc_id = path.split("/", 1)
        out[collection][doc_id] = body
    return out


def _host(store):
    """The store as the collections a page opened on it reads."""
    return {"collections": {name: [{"id": doc_id, "data": data} for doc_id, data in docs.items()] for name, docs in store.items()}}


def _run(sheet, steps="", store=None):
    """Opens the real page on the sheet and the store, runs the steps, and returns what it wrote and what it shows."""
    scenario = VIEW + steps + "\nawait settled();\nreturn { written: t.written(), view: pageView() };"
    return _pr_page(sheet, scenario, host=None if store is None else _host(store))["result"]


def _answers(sheet, picks=None):
    """A stored answer for every card, each with its own revision: accepted unless picks gives (answer, optionId) for the card."""
    picks = picks or {}
    docs = {}
    for position, card in enumerate(sheet["cards"]):
        if card["id"] in picks:
            answer, option = picks[card["id"]]
        elif card["options"]:
            answer, option = "option", next(o["id"] for o in card["options"] if o["sendsBack"] is False)
        else:
            answer, option = "accept", None
        docs[card["id"]] = {"answer": answer, "optionId": option, "note": "", "revision": "%016x" % (0xC9130 + position)}
    return docs


def _covers(answers):
    return sorted("answers/%s@%s" % (card_id, doc["revision"]) for card_id, doc in answers.items())


def _merge_doc(digest, covers, note="go ahead"):
    return {"verdict": "merge", "note": note, "sheet": digest, "covers": covers}


def _stop_key(sheet, stop_id):
    return next(stop["key"] for stop in sheet["prSheet"]["walk"]["stops"] if stop["id"] == stop_id)


def _walk_doc(answer, fix=None):
    return {"answer": answer, "fix": fix, "note": "", "shots": []}


def _store(answers=None, verdict=None, walk=None):
    return {"answers": answers or {}, "verdict": verdict or {}, "walk": walk or {}}


def _state(sheet, store):
    return pr_sheet.pr_state(_bytes(sheet), store)


def _entry(folder, number, sheet, store, link=LINK):
    """Publishes the sheet and its store dump under the folder; returns the index input's entry for the PR."""
    (folder / ("pr-%d" % number)).mkdir(exist_ok=True)
    (folder / ("pr-%d" % number) / "sheet.json").write_bytes(_bytes(sheet))
    (folder / ("pr-%d" % number) / "store.json").write_text(json.dumps(store), encoding="utf-8")
    return {"number": number, "link": link, "sheet": "pr-%d/sheet.json" % number, "store": "pr-%d/store.json" % number}


def _build_index(folder, capsys, prs, questions=(), answers=None, merge_order=()):
    """Runs `pr_sheet.py index` through main on files under the folder; returns the index sheet it wrote."""
    capsys.readouterr()
    advisor = {"schema": "index-input/1", "questions": list(questions), "mergeOrder": list(merge_order), "prs": prs}
    (folder / "index-input.json").write_text(json.dumps(advisor), encoding="utf-8")
    argv = ["index", "--input", str(folder / "index-input.json"), "--out", str(folder / "index.json")]
    if answers is not None:
        (folder / "index-answers.json").write_text(json.dumps(answers), encoding="utf-8")
        argv += ["--answers", str(folder / "index-answers.json")]
    code = pr_sheet.main(argv)
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["ok"] is True, result
    return json.loads((folder / "index.json").read_text(encoding="utf-8"))


def _row(index, number):
    return next(row for row in index["index"]["rows"] if row["number"] == number)


def _groups(index):
    """The groups the index page draws: id to the links of its rows."""
    page = _index_page(index, "return kids().filter((node) => node.id.startsWith('index-group-')).map(groupView);")
    return {group["id"]: [row["href"] for row in group["rows"]] for group in page["result"]}


def _republished(sheet):
    """The sheet published again for a new commit, naming the old one, so its digest is new and every card id is unchanged."""
    def mutate(clone):
        clone["prSheet"]["previousCommit"] = clone["prSheet"]["commit"]
        clone["prSheet"]["commit"] = NEW_COMMIT
    return _with(sheet, mutate)


# Bites on: an answered question kept on the index when the advisor rebuilds, or the Blocks work part not saying nothing is blocking once the last question is gone.
def test_the_only_question_answered_leaves_the_index(tmp_path, capsys):
    pr = _entry(tmp_path, 214, BIG, _empty())
    sheet = _build_index(tmp_path, capsys, [pr], questions=[QUESTION])
    assert [card["id"] for card in sheet["cards"]] == ["old-orders"] and len(sheet["index"]["rows"]) == 1
    tapped = _index_page(sheet, "t.click(t.button('old-orders', 'Keep them visible')); await t.tick(); return t.written();")["result"]
    assert list(tapped) == ["answers/old-orders"] and tapped["answers/old-orders"]["optionId"] == "keep-visible"
    rebuilt = _build_index(tmp_path, capsys, [pr], questions=[QUESTION], answers=_apply(_empty(), tapped))
    assert rebuilt["cards"] == [] and [row["number"] for row in rebuilt["index"]["rows"]] == [214]
    again = _index_page(rebuilt, "return part('index-blocks').children.map((node) => [node.tagName, node.textContent]);")
    assert again["result"] == [["h2", IW["blocksHeading"]], ["p", IW["nothingBlocking"]]]


# Bites on: a PR sent back for a fix not landing under Being fixed (pr_state's sends-back test), a republished sheet still shown as being fixed, or the republished row losing its link or showing the old sheet's counts.
def test_fix_before_merge_sends_the_pr_to_being_fixed_and_a_republished_sheet_replaces_it(tmp_path, capsys):
    run = _run(BIG, "await tap(B, 'Fix before merge');")
    assert run["view"]["sendBack"] == PW["sendBack"] and run["view"]["standing"] is False
    assert list(run["written"]) == ["answers/" + B] and run["written"]["answers/" + B]["optionId"] == "fix-before-merge"
    store = _apply(_empty(), run["written"])
    pr = _entry(tmp_path, 214, BIG, store)
    index = _build_index(tmp_path, capsys, [pr])
    row = _row(index, 214)
    assert row["state"] == "being-fixed" and row["link"] == LINK and (row["accepted"], row["total"]) == (0, 3)
    assert _groups(index) == {"index-group-being-fixed": [LINK]}

    record, advisor = _load("record-big.json"), _load("input-big.json")
    for finding in record["findings"]:
        if finding["id"] == "F7":
            finding.update(outcome="fixed", reason="Fixed: the final email now goes out.", consequence=None)
    record["finalCommit"]["sha"] = record["ci"]["sha"] = NEW_COMMIT
    advisor["previousCommit"] = _load("record-big.json")["finalCommit"]["sha"]
    del advisor["leftovers"]["F7"]
    fixed = _build([record], advisor)
    assert B not in [card["id"] for card in fixed["cards"]] and len(fixed["cards"]) == 2
    assert _entry(tmp_path, 214, fixed, store) == pr
    rebuilt = _build_index(tmp_path, capsys, [pr])
    row = _row(rebuilt, 214)
    assert row["state"] == "needs-you" and row["link"] == LINK and (row["accepted"], row["total"]) == (0, 2)
    assert _groups(rebuilt) == {"index-group-needs-you": [LINK]}


# Bites on: a Merge staying on the index after an accepted item was un-accepted (the Merge not cleared, or pr_state not reading the cleared verdict), or a Merge the page saved not reading as Ready.
def test_un_accepting_after_a_merge_leaves_ready(tmp_path, capsys):
    first = _run(BIG, "await acceptAll(); await merge('go ahead');")
    assert first["view"]["standing"] is True and first["view"]["count"] == "3 of 3 accepted"
    store = _apply(_empty(), first["written"])
    assert _row(_build_index(tmp_path, capsys, [_entry(tmp_path, 214, BIG, store)]), 214)["state"] == "ready"
    second = _run(BIG, "await tap(A, 'Discuss');", store)
    digest = _sheet_digest(BIG)
    assert second["written"]["answers/" + A]["answer"] == "discuss"
    cleared = second["written"]["verdict/" + digest]
    assert cleared["verdict"] is None and cleared["note"] == "go ahead" and cleared["sheet"] == digest
    assert second["view"]["standing"] is False
    after = _apply(store, second["written"])
    row = _row(_build_index(tmp_path, capsys, [_entry(tmp_path, 214, BIG, after)]), 214)
    assert row["state"] == "needs-you" and (row["accepted"], row["total"]) == (2, 3)


CHANGES = {
    "accepted-to-accepted": "await tap(B, 'Fix in a follow-up');",
    "note-only": "t.type(t.note(B), 'because', 'change'); await t.tick();",
}


# Bites on: a Merge page A saved still standing after page B changed an accepted answer it was not given for (the page's covers check on restore, or pr_state's), for a changed pick and for a changed note alone.
@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_merge_saved_on_one_page_does_not_stand_after_another_page_changed_an_answer(change, tmp_path, capsys):
    base = _store(answers=_answers(BIG))
    page_a = _run(BIG, "await merge('go ahead');", base)
    assert page_a["view"]["standing"] is True
    store_a = _apply(base, page_a["written"])
    assert _state(BIG, store_a)["state"] == "ready" and _run(BIG, "", store_a)["view"]["standing"] is True
    page_b = _run(BIG, CHANGES[change], base)
    assert list(page_b["written"]) == ["answers/" + B]
    assert page_b["written"]["answers/" + B]["revision"] != base["answers"][B]["revision"]
    merged = _apply(store_a, page_b["written"])
    assert _state(BIG, merged)["state"] == "needs-you"
    reopened = _run(BIG, "", merged)
    assert reopened["view"]["standing"] is False and reopened["view"]["sendBack"] is None
    assert _row(_build_index(tmp_path, capsys, [_entry(tmp_path, 214, BIG, merged)]), 214)["state"] == "needs-you"


# Bites on: two pages, each starting from its own fresh state, writing the same revision for different saves (a counter that restarts on every page), so a Merge page A saved stays valid after page B changed the same card.
def test_revisions_written_by_two_pages_for_the_same_card_differ_and_the_earlier_merge_falls(tmp_path, capsys):
    page_a = _run(BIG, "await acceptAll(); await merge('go ahead');")
    assert page_a["view"]["standing"] is True
    store_a = _apply(_empty(), page_a["written"])
    assert _state(BIG, store_a)["state"] == "ready"
    answers_only = {path: body for path, body in page_a["written"].items() if path.startswith("answers/")}
    page_b = _run(BIG, "t.type(t.note(%s), 'because', 'change'); await t.tick();" % json.dumps(A), _apply(_empty(), answers_only))
    assert list(page_b["written"]) == ["answers/" + A]
    assert page_b["written"]["answers/" + A]["revision"] != page_a["written"]["answers/" + A]["revision"]
    merged = _apply(store_a, page_b["written"])
    assert _state(BIG, merged)["state"] == "needs-you"
    assert _run(BIG, "", merged)["view"]["standing"] is False
    assert _row(_build_index(tmp_path, capsys, [_entry(tmp_path, 214, BIG, merged)]), 214)["state"] == "needs-you"


# Bites on: a cleared answer (answer null, written when a pick is tapped again) counted as an answer by pr_state or by the page.
def test_a_cleared_answer_counts_as_unanswered_on_both_sides():
    run = _run(BIG, "await acceptAll(); await merge('go ahead'); await tap(A, 'Accept');")
    assert run["written"]["answers/" + A]["answer"] is None
    store = _apply(_empty(), run["written"])
    assert _state(BIG, store) == {"state": "needs-you", "accepted": 2, "total": 3, "walked": 0, "walkTotal": 2}
    reopened = _run(BIG, "", store)
    assert reopened["view"]["count"] == _fill(PW["acceptedCount"], accepted=2, total=3) and reopened["view"]["standing"] is False


# Bites on: a verdict stored under an older digest standing on a republished sheet, in pr_state or on the page.
def test_a_verdict_for_an_older_digest_is_ignored_on_both_sides():
    answers = _answers(BIG)
    old = _sheet_digest(BIG)
    store = _store(answers, {old: _merge_doc(old, _covers(answers))})
    assert _state(BIG, store)["state"] == "ready" and _run(BIG, "", store)["view"]["standing"] is True
    again = _republished(BIG)
    assert _sheet_digest(again) != old and [card["id"] for card in again["cards"]] == [card["id"] for card in BIG["cards"]]
    assert _state(again, store) == {"state": "needs-you", "accepted": 3, "total": 3, "walked": 0, "walkTotal": 2}
    view = _run(again, "", store)["view"]
    assert view["standing"] is False and view["count"] == _fill(PW["acceptedCount"], accepted=3, total=3)


# Bites on: a walk answer under a stop key the republished sheet no longer has blocking the Merge or being counted, in pr_state or on the page.
def test_a_walk_answer_for_a_stop_key_the_sheet_no_longer_has_is_ignored_on_both_sides():
    advisor = _load("input-big.json")
    advisor["walk"]["stops"][0]["expect"] += " Twice."
    again = _build(["record-big.json"], advisor)
    old_key, new_key = _stop_key(BIG, "retry-loop"), _stop_key(again, "retry-loop")
    assert old_key != new_key and _stop_key(BIG, "payment-tests") == _stop_key(again, "payment-tests")
    answers = _answers(again)
    digest = _sheet_digest(again)
    verdict = {digest: _merge_doc(digest, _covers(answers))}
    gone = _store(answers, verdict, {old_key: _walk_doc("problem")})
    assert _state(again, gone) == {"state": "ready", "accepted": 3, "total": 3, "walked": 0, "walkTotal": 2}
    view = _run(again, "", gone)["view"]
    assert view["standing"] is True and view["walk"] == _fill(PW["walkCount"], walked=0, total=2)
    held = _store(answers, verdict, {new_key: _walk_doc("problem")})
    assert _state(again, held) == {"state": "needs-you", "accepted": 3, "total": 3, "walked": 1, "walkTotal": 2}
    view = _run(again, "", held)["view"]
    assert view["standing"] is False and view["walk"] == _fill(PW["walkCount"], walked=1, total=2)


def _carried(previous, head):
    """The sheet republished for a new head with its answers and Merge carried forward from the previous sheet, so its chain names that sheet and every one it carried from."""
    advisor = dict(_load("input-big.json"), carriedForward={"fromSheet": "previous/sheet.json", "heads": {"214": head}, "date": "2026-10-01",
                                                          "moved": "the base moved", "whyNotMaterial": "the merge was clean and the behavior is the same"})
    return pr_sheet.build([_load("record-big.json")], advisor, WORDS["pr"], previous=_bytes(previous))


CARRY_1 = _carried(BIG, "c" * 40)
CARRY_2 = _carried(CARRY_1, "d" * 40)
CHAIN = [_sheet_digest(CARRY_2), _sheet_digest(CARRY_1), _sheet_digest(BIG)]


def _chain_store(documents):
    """A store whose verdict documents sit under the chain positions given (0 newest); each is (verdict, sheet position it names, or None for a foreign digest)."""
    answers = _answers(CARRY_2)
    verdicts = {}
    for position, (verdict, names) in documents.items():
        digest = CHAIN[position]
        verdicts[digest] = {"verdict": verdict, "note": "", "sheet": "0" * 64 if names is None else CHAIN[names],
                            **({"covers": _covers(answers)} if verdict == "merge" else {})}
    return _store(answers, verdicts)


def _stale(covers):
    return [covers[0].split("@")[0] + "@" + "0" * 16] + covers[1:]


def _with_merge(sheet, answers, walk=None, covers=_covers, key=None):
    digest = _sheet_digest(sheet)
    return _store(answers, {key or digest: _merge_doc(key or digest, covers(answers))}, walk)


def _problem(fix):
    return {_stop_key(BIG, "retry-loop"): _walk_doc("problem", fix)}


# (id, sheet, the store as data, the state both sides must reach)
CENSUS = [
    ("no-answers", BIG, _store(), "needs-you"),
    ("all-accepted-no-verdict", BIG, _store(_answers(BIG)), "needs-you"),
    ("all-accepted-merge", BIG, _with_merge(BIG, _answers(BIG)), "ready"),
    ("stale-revision", BIG, _with_merge(BIG, _answers(BIG), covers=lambda a: _stale(_covers(a))), "needs-you"),
    ("covers-missing-a-card", BIG, _with_merge(BIG, _answers(BIG), covers=lambda a: _covers(a)[:-1]), "needs-you"),
    ("merge-on-another-digest", BIG, _with_merge(BIG, _answers(BIG), key="0" * 64), "needs-you"),
    ("one-item-discuss-plus-merge", BIG, _with_merge(BIG, _answers(BIG, {A: ("discuss", None)})), "needs-you"),
    ("sends-back-option", BIG, _store(_answers(BIG, {C: ("option", "one-minute")})), "being-fixed"),
    ("sends-back-option-plus-merge", BIG, _with_merge(BIG, _answers(BIG, {C: ("option", "one-minute")})), "being-fixed"),
    ("walk-problem-no-fix-plus-merge", BIG, _with_merge(BIG, _answers(BIG), _problem(None)), "needs-you"),
    ("walk-problem-follow-up-plus-merge", BIG, _with_merge(BIG, _answers(BIG), _problem("follow-up")), "ready"),
    ("walk-problem-before-merge", BIG, _with_merge(BIG, _answers(BIG), _problem("before-merge")), "being-fixed"),
    ("stack-all-accepted-merge", STACK, _with_merge(STACK, _answers(STACK)), "ready"),
    ("stack-no-answers", STACK, _store(), "needs-you"),
    # The carry chain: a sheet carried twice reads its own digest, then the sheet it came from, then the one before; the first revision holding a document decides.
    ("carried-merge-stands", CARRY_2, _chain_store({2: ("merge", 2)}), "ready"),
    ("carried-merge-from-the-middle-stands", CARRY_2, _chain_store({1: ("merge", 1)}), "ready"),
    ("own-null-verdict-overrides-a-carried-merge", CARRY_2, _chain_store({0: (None, 0), 2: ("merge", 2)}), "needs-you"),
    ("own-not-yet-overrides-a-carried-merge", CARRY_2, _chain_store({0: ("not-yet", 0), 1: ("merge", 1)}), "needs-you"),
    ("withdrawal-on-a-middle-revision-overrides-an-older-merge", CARRY_2, _chain_store({1: ("not-yet", 1), 2: ("merge", 2)}), "needs-you"),
    ("own-merge-wins-over-a-middle-withdrawal", CARRY_2, _chain_store({0: ("merge", 0), 1: ("not-yet", 1)}), "ready"),
    ("carried-document-naming-another-digest-does-not-stand", CARRY_2, _chain_store({2: ("merge", None)}), "needs-you"),
    ("carried-document-naming-a-neighbour-digest-does-not-stand", CARRY_2, _chain_store({2: ("merge", 1)}), "needs-you"),
    ("own-document-naming-another-digest-blocks-a-carried-merge", CARRY_2, _chain_store({0: ("merge", None), 2: ("merge", 2)}), "needs-you"),
]


# Bites on: pr_state and the page disagreeing about one store: a Merge standing on one side only (the covers comparison, the digest, the accepted count, a walk Problem's fix), a send-back seen on one side only, or the accepted and walked counts differing. The carry-chain rows bite on: the verdict chain read differently by the two sides (a carried Merge not standing, a newer null or Not yet document not overriding an older Merge, a withdrawal on a middle revision read past, or a document whose sheet field names another digest standing).
@pytest.mark.parametrize("sheet,store,expected", [row[1:] for row in CENSUS], ids=[row[0] for row in CENSUS])
def test_the_index_and_the_page_agree_about_the_same_store(sheet, store, expected):
    state = _state(sheet, store)
    view = _run(sheet, "", store)["view"]
    assert state["state"] == expected
    assert (state["state"] == "ready") is view["standing"]
    assert (state["state"] == "being-fixed") is (view["sendBack"] is not None)
    assert view["sendBack"] in (None, PW["sendBack"])
    assert view["count"] == _fill(PW["acceptedCount"], accepted=state["accepted"], total=state["total"])
    assert view["walk"] == _fill(PW["walkCount"], walked=state["walked"], total=state["walkTotal"])
