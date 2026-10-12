"""Guards for the review template page drawing a pr sheet and a stack sheet as one scrolling page."""
import copy
import json
import re
from pathlib import Path

import pytest

from test_review_template import (
    NO_DIGEST_LINE,
    THEME,
    WORDS,
    _assert_error_shown,
    _card,
    _plain_card,
    _run_page,
    _sample_files,
    _sample_final,
    _sheet,
    _sheet_digest,
    _style_rules,
    _template_text,
    _with,
)

PR_SAMPLE = json.loads((THEME / "sample-pr-sheet.json").read_text(encoding="utf-8"))
STACK_SAMPLE = json.loads((THEME / "sample-stack-sheet.json").read_text(encoding="utf-8"))
SAMPLES = {"pr": PR_SAMPLE, "stack": STACK_SAMPLE}
PW = WORDS["pr"]
PREVIOUS = "9f8e7d6c5b4a39281706f5e4d3c2b1a098765432"

# What a scenario can read of the page: the parts of a pr sheet or a stack sheet by id, in the order they sit on the page.
PRELUDE = r"""
const isCard = (node) => node.tagName === "article" && node.id.startsWith("card-");
const pageNodes = () => [...elements["sheet-cards"].children, ...elements["sheet-final"].children];
const order = () => pageNodes().map((node) => (isCard(node) ? "card" : node.id));
const part = (id) => pageNodes().find((node) => node.id === id);
const shape = (node) => node.children.map((child) => (child.tagName === "ul" || child.tagName === "ol" ? child.children.map((item) => item.textContent) : child.textContent));
const verdict = () => part("sheet-verdict");
const verdictRow = () => verdict().children.find((child) => hasClass(child, "answer-row")).children;
const verdictNote = () => verdict().children.find((child) => child.tagName === "textarea");
const verdictState = () => ({
  labels: verdictRow().map((button) => button.textContent),
  pressed: verdictRow().map((button) => button.getAttribute("aria-pressed")),
  disabled: verdictRow().map((button) => button.disabled).concat([verdictNote().disabled]),
  note: verdictNote().value,
});
const verdictCaptions = () => verdict().children.filter((child) => child.tagName === "p").map((child) => ({ hidden: child.hidden, text: child.textContent }));
const verdictChildren = () => verdict().children.map((child) => child.tagName + (child.className ? "." + child.className.split(/\s+/).join(".") : ""));
"""


def _fill(template, **values):
    return re.sub(r"\{(\w+)\}", lambda match: str(values[match.group(1)]), template)


def _files(sheet, words=None, schema=None):
    files = _sample_files(sheet)
    if words is not None:
        files["sheet-words.json"] = {"status": 200, "body": json.dumps(words)}
    if schema is not None:
        files["sheet.schema.json"] = {"status": 200, "body": json.dumps(schema)}
    return files


def _page(sheet, scenario="return null;", host=None, words=None, schema=None):
    page = _run_page(_files(sheet, words, schema), host=host, scenario=PRELUDE + scenario)
    assert page["settled"], "the page never settled: %s" % page
    assert page["errorHidden"] is True, page["errors"]
    return page


def _plural(count, noun):
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


def _short(commit):
    return commit[:7]


def _entry_lines(entries):
    return [entry["title"] + " — " + entry["detail"] for entry in entries]


def _expected_what_changed(sheet):
    prs = sheet["prSheet"]
    facts = prs["whatChanged"]
    expected = [PW["whatChangedHeading"], facts["summary"]]
    if facts["reviewers"]:
        named = []
        for reviewer in facts["reviewers"]:
            notes = [reviewer["family"] if reviewer["family"] is not None else PW["familyUnknown"]]
            if reviewer.get("notIndependent"):
                notes.append(PW["notIndependentMark"])
            named.append("%s (%s)" % (reviewer["name"], ", ".join(notes)))
        expected.append(_fill(PW["reviewedBy"], reviewers="; ".join(named)))
    if facts["caught"]:
        expected += [PW["caughtHeading"], list(facts["caught"])]
    expected.append(_fill(PW["roundsLine"], rounds=_plural(facts["rounds"], WORDS["roundNoun"])))
    if facts["stoppedAtCap"]:
        expected.append(PW["historyCap"])
    expected.append(_fill(PW["ciLine"], state=facts["ci"]["state"], commit=_short(facts["ci"]["commit"])))
    expected.append(_fill(PW["laneLine"], lane=facts["lane"], reason=facts["laneReason"]))
    expected.append(_fill(PW["describesCommit"], commit=_short(prs["commit"])))
    return expected


def _expected_order(sheet):
    prs = sheet["prSheet"]
    expected = ["pr-what-changed"]
    if "previousCommit" in prs:
        expected.append("pr-changed")
    if prs["walk"]:
        expected.append("pr-walk")
    expected += ["pr-accepting"] + (["card"] * len(sheet["cards"]) or ["pr-nothing"])
    for key, part_id in (("craft", "pr-craft"), ("alreadyDecided", "pr-decided"), ("history", "pr-review")):
        if prs[key]:
            expected.append(part_id)
    if sheet["kind"] == "stack":
        expected.append("pr-prs")
    return expected + ["sheet-verdict"]


def _with_previous(sheet):
    return _with(sheet, lambda clone: clone["prSheet"].__setitem__("previousCommit", PREVIOUS))


def _emptied(sheet):
    def mutate(clone):
        clone["cards"] = []
        for key in ("walk", "craft", "alreadyDecided", "history"):
            clone["prSheet"][key] = []
    return _with(sheet, mutate)


# Bites on: the five parts of a pr sheet or a stack sheet drawn in any other order (What changed, the walk, What you're accepting, the folded parts with the stack's PR list, the merge verdict), a part with nothing in it kept, or the box that says the PR moved drawn anywhere but directly under What changed.
@pytest.mark.parametrize("kind", ["pr", "stack"])
@pytest.mark.parametrize("variant", ["as-is", "moved", "emptied"])
def test_parts_are_drawn_in_order(kind, variant):
    sheet = {"as-is": SAMPLES[kind], "moved": _with_previous(SAMPLES[kind]), "emptied": _emptied(SAMPLES[kind])}[variant]
    page = _page(sheet, "return order();")
    assert page["result"] == _expected_order(sheet)
    if variant == "as-is":
        folded = ["pr-craft", "pr-decided", "pr-review"] + (["pr-prs"] if kind == "stack" else [])
        cards = ["card"] * (3 if kind == "pr" else 1)
        assert page["result"] == ["pr-what-changed", "pr-walk", "pr-accepting"] + cards + folded + ["sheet-verdict"]
    if variant == "emptied":
        assert page["result"] == ["pr-what-changed", "pr-accepting", "pr-nothing"] + (["pr-prs"] if kind == "stack" else []) + ["sheet-verdict"]


# Bites on: a card hidden on a pr sheet or a stack sheet, the stepper, item rows, why box or final-sheet history box shown, the empty side column left at wide widths, or the other kinds changed.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_one_scrolling_page(kind):
    page = _page(SAMPLES[kind], """
      const hidden = (id) => elements[id].hidden;
      return {
        cardsHidden: elements["sheet-cards"].children.filter(isCard).map((card) => card.hidden),
        host: [hidden("sheet-cards"), hidden("sheet-final")],
        gone: ["sheet-stepper", "sheet-stepper-bottom", "sheet-items", "sheet-why", "sheet-history", "sheet-footer"].map(hidden),
        pageClass: t.view.page.className,
      };
    """)
    result = page["result"]
    assert result["cardsHidden"] == [False] * len(SAMPLES[kind]["cards"])
    assert result["host"] == [False, False]
    assert result["gone"] == [True] * 6
    assert result["pageClass"] == "sheet-page is-pr"


def test_the_other_kinds_are_drawn_as_before():
    other = {
        "plain": _sheet("plain"),
        "remainder": _sheet("remainder", remainder={"roundsRun": 2, "fixesMade": 3, "unsettled": ["fridge-check"]}),
        "final": _sample_final(),
    }
    for kind, sheet in other.items():
        page = _run_page(_files(sheet), scenario="""
          return { pageClass: t.view.page.className, stepperHidden: t.stepper().hidden, itemsHidden: elements["sheet-items"].hidden, footerHidden: elements["sheet-footer"].hidden };
        """)
        assert page["result"]["pageClass"] == "sheet-page", kind
        if kind != "final" or page["cards"]:
            assert page["result"]["stepperHidden"] is False, kind
            assert page["result"]["itemsHidden"] is False, kind
        assert page["result"]["footerHidden"] is False, kind


def test_wide_screens_get_one_column_for_the_one_page_kinds():
    text = _template_text()
    rules = [(selector, dict(pairs)) for selector, pairs in _style_rules(text)]
    wide = [pairs for selector, pairs in rules if selector == ".sheet-page.is-pr .sheet-layout"]
    assert wide and wide[0]["grid-template-columns"] == "minmax(0, 1fr)"
    assert text.index("@media (min-width: 900px)") < text.index(".sheet-page.is-pr .sheet-layout")


# Bites on: a What changed fact missing, changed, or taken from anywhere but prSheet.whatChanged; a null family not shown as family unknown; a missing not-independent mark; the caught list kept when empty; the stack's block not following the same rule.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_what_changed_shows_the_facts_of_the_data_file(kind):
    page = _page(SAMPLES[kind], 'return shape(part("pr-what-changed"));')
    assert page["result"] == _expected_what_changed(SAMPLES[kind])
    text = json.dumps(page["result"])
    assert ("not independent" in text) and "family unknown" not in text
    assert ("stopped at its round cap" in text) == SAMPLES[kind]["prSheet"]["whatChanged"]["stoppedAtCap"]


def test_what_changed_leaves_out_an_empty_caught_list_and_names_an_unknown_family():
    def mutate(clone):
        facts = clone["prSheet"]["whatChanged"]
        facts["caught"] = []
        facts["reviewers"][0]["family"] = None
    sheet = _with(PR_SAMPLE, mutate)
    page = _page(sheet, 'return shape(part("pr-what-changed"));')
    assert page["result"] == _expected_what_changed(sheet)
    assert PW["caughtHeading"] not in json.dumps(page["result"])
    assert "code-reviewer (family unknown)" in json.dumps(page["result"])


# Bites on: the box that says the PR moved missing when previousCommit is present, drawn when it is absent, or its commit not the first 7 characters of previousCommit.
def test_this_pr_changed_shows_only_with_a_previous_commit():
    without = _page(PR_SAMPLE, 'return order();')
    assert "pr-changed" not in without["result"]
    sheet = _with_previous(PR_SAMPLE)
    page = _page(sheet, 'return { order: order(), box: shape(part("pr-changed")), className: part("pr-changed").className };')
    assert page["result"]["order"][:2] == ["pr-what-changed", "pr-changed"]
    assert page["result"]["box"] == [PW["changedHeading"], _fill(PW["changed"], previous=PREVIOUS[:7])]
    assert "9f8e7d6" in page["result"]["box"][1] and PREVIOUS not in page["result"]["box"][1]
    assert page["result"]["className"] == "sh-box"


# Bites on: the walk out of order, a stop's PR not named on a stack (or named on a pr sheet), or an answer control on a stop.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_the_walk_lists_the_stops_and_names_their_prs_on_a_stack(kind):
    page = _page(SAMPLES[kind], """
      const node = part("pr-walk");
      return { shape: shape(node), controls: t.all(node).filter((item) => item.tagName === "button" || item.tagName === "textarea").length };
    """)
    stops = SAMPLES[kind]["prSheet"]["walk"]
    titles = [(_fill(PW["walkStopPr"], pr=stop["pr"]) + " " if kind == "stack" else "") + stop["title"] for stop in stops]
    assert page["result"]["shape"] == [PW["walkHeading"], titles]
    assert page["result"]["controls"] == 0
    if kind == "stack":
        assert titles[0] == "#5 The gift-card table"


# Bites on: a card's parts out of order or one dropped; the options list drawn on a card with none; the Accept/Discuss pair or the options with Something else swapped.
def test_cards_keep_their_parts_and_offer_accept_discuss_or_the_options():
    page = _page(PR_SAMPLE, """
      const ids = elements["sheet-cards"].children.filter(isCard).map((card) => card.id.replace("card-", ""));
      return ids.map((id) => ({ id: id, parts: t.parts(id), labels: t.state(id).labels, disabled: t.state(id).disabled }));
    """)
    cards = page["result"]
    none, options, picked = cards
    note_and_save = ["div.answer-row", "label:Note", "textarea.sh-field", "div.save-line"]
    assert none["parts"] == ["span.sh-badge", "h2", "label:If left", "p", "label:Recommendation", "div.sheet-recommendation"] + note_and_save
    assert none["labels"] == ["Accept", "Discuss"]
    assert options["parts"] == ["span.sh-badge", "h2", "label:If left", "p", "label:Options", "ul", "label:Recommendation", "div.sheet-recommendation"] + note_and_save
    assert options["labels"] == ["Keep it", "Fix in a follow-up", "Fix before merge", "Something else"]
    assert picked["labels"][-1] == "Something else" and len(picked["labels"]) == 3
    assert all(not any(card["disabled"]) for card in cards)


# Bites on: a PR card offering the discovery words (Aligned) instead of the prAnswers words, or those words typed in the page instead of read from sheet-words.json.
def test_pr_cards_take_their_answer_words_from_prAnswers():
    words = copy.deepcopy(WORDS)
    words["prAnswers"]["labels"].update({"accept": "Take it", "discuss": "Talk", "something-else": "Other"})
    page = _page(PR_SAMPLE, """
      const ids = elements["sheet-cards"].children.filter(isCard).map((card) => card.id.replace("card-", ""));
      return ids.map((id) => t.state(id).labels);
    """, words=words)
    assert page["result"][0] == ["Take it", "Talk"]
    assert page["result"][1][-1] == "Other"


# Bites on: a card that cannot be answered with its note empty, or an Accept that writes anything but the whole answer document.
def test_accept_saves_with_an_empty_note_and_an_option_saves_its_id():
    page = _page(PR_SAMPLE, """
      t.click(t.button("f-e490915872bd", "Accept"));
      await t.tick();
      t.click(t.button("f-a5cb88b79507", "Fix in a follow-up"));
      await t.tick();
      t.click(t.button("i-6f4a068f1373", "Something else"));
      await t.tick();
      return { sets: t.setLog(), save: t.saveText("f-e490915872bd"), pressed: t.state("f-e490915872bd").pressed };
    """)
    bodies = [(item["path"], item["body"]) for item in page["result"]["sets"]]
    assert bodies == [
        ("answers/f-e490915872bd", {"answer": "accept", "optionId": None, "note": ""}),
        ("answers/f-a5cb88b79507", {"answer": "option", "optionId": "fix-in-a-follow-up", "note": ""}),
        ("answers/i-6f4a068f1373", {"answer": "something-else", "optionId": None, "note": ""}),
    ]
    assert page["result"]["save"] == "Saved" and page["result"]["pressed"] == ["true", "false"]


def _docs_for(card_id, answer, option_id=None, note="kept note"):
    return [{"id": card_id, "data": {"answer": answer, "optionId": option_id, "note": note}}]


def _accepted_answers(sheet):
    """The stored answers that leave a pr or stack sheet unlocked: accept on a card without options, else an option that does not send the PR back."""
    docs = []
    for card in sheet["cards"]:
        options = [option for option in card.get("options", []) if not option.get("sendsBack")]
        data = {"answer": "option", "optionId": options[0]["id"], "note": ""} if card.get("options") else {"answer": "accept", "optionId": None, "note": ""}
        docs.append({"id": card["id"], "data": data})
    return docs


# Bites on: a stored answer restored although the card does not offer it now (accept on a discovery card, aligned on a PR card), or a card that offers it not restoring it.
def test_a_stored_answer_restores_only_when_the_card_offers_it():
    discovery = _sheet(cards=[_plain_card("plan-day")])
    stored_accept = _page(discovery, "return t.state('plan-day');", host={"docs": _docs_for("plan-day", "accept")})
    assert stored_accept["result"]["pressed"] == ["false", "false"] and stored_accept["result"]["note"] == "kept note"
    stored_aligned = _page(PR_SAMPLE, "return t.state('f-e490915872bd');", host={"docs": _docs_for("f-e490915872bd", "aligned")})
    assert stored_aligned["result"]["pressed"] == ["false", "false"] and stored_aligned["result"]["note"] == "kept note"
    restored = _page(PR_SAMPLE, "return t.state('f-e490915872bd');", host={"docs": _docs_for("f-e490915872bd", "accept")})
    assert restored["result"]["pressed"] == ["true", "false"] and restored["result"]["note"] == "kept note"
    restored = _page(discovery, "return t.state('plan-day');", host={"docs": _docs_for("plan-day", "aligned")})
    assert restored["result"]["pressed"] == ["true", "false"]


# Bites on: a discovery card losing its answer controls because the schema's answer enum now lists accept while the discovery words have no label for it, and on a value neither block labels no longer switching the controls off.
def test_discovery_controls_stay_on_with_the_pr_schema_and_an_unlabelled_value_still_turns_them_off():
    discovery = _sheet(cards=[_card("with-options"), _plain_card("plain-card")])
    on = _run_page(_sample_files(discovery), scenario="return { a: t.state('with-options'), b: t.state('plain-card') };")
    assert on["result"]["a"]["labels"] == ["Yes", "No", "Something else"]
    assert on["result"]["b"]["labels"] == ["Aligned", "Discuss"]
    assert not any(on["result"]["a"]["disabled"]) and not any(on["result"]["b"]["disabled"])

    schema = json.loads((THEME / "sheet.schema.json").read_text(encoding="utf-8"))
    schema["$defs"]["answer"]["properties"]["answer"]["enum"].append("bogus-answer")
    files = _sample_files(discovery)
    files["sheet.schema.json"] = {"status": 200, "body": json.dumps(schema)}
    off = _run_page(files, scenario="return { a: t.state('with-options'), b: t.state('plain-card'), gate: t.gate().message };")
    assert all(off["result"]["a"]["disabled"]) and all(off["result"]["b"]["disabled"])
    pr_files = _sample_files(PR_SAMPLE)
    pr_files["sheet.schema.json"] = files["sheet.schema.json"]
    pr_off = _run_page(pr_files, scenario=PRELUDE + "return t.state('f-e490915872bd').disabled;")
    assert all(pr_off["result"])


# Bites on: the final sheet's Approve / Not yet changed, or its verdict controls going off now that the verdict enum lists merge.
def test_a_final_sheet_still_offers_approve_and_not_yet():
    sheet = _sample_final()
    digest = _sheet_digest(sheet)
    page = _run_page(_files(sheet), scenario="""
      const before = t.lastState();
      t.click(t.lastButton("Approve"));
      await t.tick();
      return { before: before, sets: t.setLog() };
    """)
    assert page["result"]["before"]["labels"] == ["Approve", "Not yet"]
    assert not any(page["result"]["before"]["disabled"])
    assert page["result"]["sets"] == [{"path": "verdict/" + digest, "body": {"verdict": "approve", "note": "", "sheet": digest}}]


@pytest.mark.parametrize("kind,label", [("pr", "Merge #214"), ("stack", "Merge stack #4")])
def test_the_merge_button_names_the_pr_or_the_stack_and_saves_like_the_final_verdict(kind, label):
    sheet = SAMPLES[kind]
    digest = _sheet_digest(sheet)
    page = _page(sheet, """
      const before = verdictState();
      t.click(verdictRow()[0]);
      await t.tick();
      const merged = verdictState();
      t.click(verdictRow()[0]);
      await t.tick();
      t.click(verdictRow()[1]);
      await t.tick();
      return { before: before, merged: merged, after: verdictState(), sets: t.setLog().filter((item) => item.path.startsWith("verdict/")), captions: verdictCaptions(), children: verdictChildren() };
    """, host={"collections": {"answers": _accepted_answers(sheet)}})
    result = page["result"]
    assert result["before"]["labels"] == [label, "Not yet"]
    assert not any(result["before"]["disabled"])
    assert result["merged"]["pressed"] == ["true", "false"]
    assert result["after"]["pressed"] == ["false", "true"]
    assert [item["path"] for item in result["sets"]] == ["verdict/" + digest] * 3
    assert [item["body"] for item in result["sets"]] == [
        {"verdict": "merge", "note": "", "sheet": digest},
        {"verdict": None, "note": "", "sheet": digest},
        {"verdict": "not-yet", "note": "", "sheet": digest},
    ]
    assert result["children"][:2] == ["h2", "div.answer-row"]
    assert result["captions"][-1] == {"hidden": False, "text": PW["verdictCaption"]}
    assert result["captions"][0]["hidden"] is True and result["captions"][0]["text"] == NO_DIGEST_LINE
    assert result["children"][-1] == "p.sh-caption" and result["children"].index("div.save-line") < len(result["children"]) - 1


EDIT_THE_NOTE = """
  const restored = verdictState();
  t.type(verdictNote(), "edited", "change");
  await t.tick();
  return { restored: restored, sets: t.setLog().filter((item) => item.path.startsWith("verdict/")) };
"""


def _verdict_doc(sheet, verdict, note="my verdict note"):
    digest = _sheet_digest(sheet)
    return {"id": digest, "data": {"verdict": verdict, "note": note, "sheet": digest}}


# Bites on: a PR sheet restoring a stored approve (or a final sheet a stored merge) as a pick; the verdict of the right kind not restoring; the verdict collection not read for a PR sheet.
def test_a_verdict_outside_the_sheets_kind_restores_only_its_note():
    for kind in ("pr", "stack"):
        sheet = SAMPLES[kind]
        approve = _page(sheet, EDIT_THE_NOTE, host={"collections": {"verdict": [_verdict_doc(sheet, "approve")]}})
        assert approve["result"]["restored"]["pressed"] == ["false", "false"] and approve["result"]["restored"]["note"] == "my verdict note"
        # A pick that was not restored is not saved back either: the next save carries no verdict.
        assert [item["body"]["verdict"] for item in approve["result"]["sets"]] == [None]
        merge = _page(sheet, "return verdictState();", host={"collections": {"answers": _accepted_answers(sheet), "verdict": [_verdict_doc(sheet, "merge")]}})
        assert merge["result"]["pressed"] == ["true", "false"] and merge["result"]["note"] == "my verdict note"
        not_yet = _page(sheet, "return verdictState();", host={"collections": {"verdict": [_verdict_doc(sheet, "not-yet")]}})
        assert not_yet["result"]["pressed"] == ["false", "true"]
    final = _sample_final()
    stored = _run_page(_files(final), scenario="""
      const restored = t.lastState();
      t.type(t.lastNote(), "edited", "change");
      await t.tick();
      return { restored: restored, sets: t.setLog() };
    """, host={"collections": {"verdict": [_verdict_doc(final, "merge")]}})
    assert stored["result"]["restored"]["pressed"] == ["false", "false"] and stored["result"]["restored"]["note"] == "my verdict note"
    assert [item["body"]["verdict"] for item in stored["result"]["sets"]] == [None]
    stored = _run_page(_files(final), scenario="return t.lastState();", host={"collections": {"verdict": [_verdict_doc(final, "approve")]}})
    assert stored["result"]["pressed"] == ["true", "false"]


# Bites on: a PR sheet's verdict controls left on when the browser cannot compute the digest, or the no-digest caption not shown.
def test_without_a_digest_the_verdict_controls_are_off_and_the_caption_says_why():
    page = _page(PR_SAMPLE, "return { verdict: verdictState(), captions: verdictCaptions(), card: t.state('f-e490915872bd').disabled };", host={"noCrypto": True})
    assert all(page["result"]["verdict"]["disabled"])
    assert page["result"]["captions"][0] == {"hidden": False, "text": NO_DIGEST_LINE}
    assert not any(page["result"]["card"])


# Bites on: the app bar count not following the cards' current picks (Accept or an option that does not send the PR back), the zero-card wording, or the count shown before the saved answers are read.
def test_the_count_line():
    page = _page(PR_SAMPLE, """
      const counts = [t.count()];
      t.click(t.button("f-e490915872bd", "Accept"));
      await t.tick();
      counts.push(t.count());
      t.click(t.button("f-a5cb88b79507", "Keep it"));
      await t.tick();
      counts.push(t.count());
      t.click(t.button("i-6f4a068f1373", "Something else"));
      await t.tick();
      counts.push(t.count());
      t.click(t.button("f-e490915872bd", "Discuss"));
      await t.tick();
      counts.push(t.count());
      t.click(t.button("f-a5cb88b79507", "Fix before merge"));
      await t.tick();
      counts.push(t.count());
      return counts;
    """)
    assert page["result"] == [
        "0 of 3 accepted", "1 of 3 accepted", "2 of 3 accepted", "2 of 3 accepted", "1 of 3 accepted", "0 of 3 accepted",
    ]
    waiting = _page(PR_SAMPLE, "return t.count();", host={"read": "pending"})
    assert waiting["result"] == "3 items · answers not loaded"
    empty = _page(_emptied(PR_SAMPLE), "return t.count();")
    assert empty["result"] == PW["nothingToAcceptCount"] == "Nothing to accept"
    one = _page(_with(PR_SAMPLE, lambda clone: clone.__setitem__("cards", clone["cards"][:1])), "return t.count();", host={"docs": _docs_for("f-e490915872bd", "accept", note="")})
    assert one["result"] == "1 of 1 accepted"


# Bites on: a PR sheet with no cards leaving out the nothing-to-accept words, or the verdict going missing with no cards.
def test_no_cards_reads_the_nothing_to_accept_words_and_still_draws_the_verdict():
    page = _page(_emptied(PR_SAMPLE), """
      return { order: order(), accepting: elements["sheet-cards"].children.map((node) => node.textContent), verdict: verdictState() };
    """)
    assert PW["nothingToAccept"] == "Nothing. The review left nothing for you."
    assert page["result"]["accepting"][-2:] == [PW["acceptingHeading"], PW["nothingToAccept"]]
    assert page["result"]["order"] == ["pr-what-changed", "pr-accepting", "pr-nothing", "sheet-verdict"]
    assert page["result"]["verdict"]["labels"] == ["Merge #214", "Not yet"]
    with_cards = _page(PR_SAMPLE, "return elements['sheet-cards'].children.map((node) => node.textContent);")
    assert PW["nothingToAccept"] not in with_cards["result"]


# Bites on: a folded part drawn open, a wrong count or order or cue, a part that does not open on a tap, an entry not read "title — detail", a stack PR list line not "#number title · first 7", or an empty list's toggle kept.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_folded_parts_open_on_a_tap(kind):
    sheet = SAMPLES[kind]
    ids = ["pr-craft", "pr-decided", "pr-review"] + (["pr-prs"] if kind == "stack" else [])
    page = _page(sheet, """
      const ids = %s;
      const read = () => ids.map((id) => {
        const wrap = part(id);
        return { toggle: t.text(wrap.children[0]), aria: wrap.children[0].getAttribute("aria-expanded"), cue: wrap.children[0].children[0].textContent, hidden: wrap.children[1].hidden, lines: wrap.children[1].children.map((item) => item.textContent) };
      });
      const closed = read();
      ids.forEach((id) => t.click(part(id).children[0]));
      return { closed: closed, open: read() };
    """ % json.dumps(ids))
    prs = sheet["prSheet"]
    headings = [PW["craftHeading"], PW["decidedHeading"], PW["reviewHeading"]] + ([PW["prsHeading"]] if kind == "stack" else [])
    lines = [_entry_lines(prs["craft"]), _entry_lines(prs["alreadyDecided"]), list(prs["history"])]
    if kind == "stack":
        lines.append(["#%d %s · %s" % (pr["number"], pr["title"], _short(pr["commit"])) for pr in prs["prs"]])
    assert [item["toggle"] for item in page["result"]["closed"]] == ["%s (%d)" % (heading, len(rows)) for heading, rows in zip(headings, lines)]
    assert [item["aria"] for item in page["result"]["closed"]] == ["false"] * len(ids)
    assert [item["hidden"] for item in page["result"]["closed"]] == [True] * len(ids)
    assert [item["aria"] for item in page["result"]["open"]] == ["true"] * len(ids)
    assert [item["hidden"] for item in page["result"]["open"]] == [False] * len(ids)
    assert [item["lines"] for item in page["result"]["open"]] == lines
    assert page["result"]["closed"][0]["cue"] != page["result"]["open"][0]["cue"]


def test_an_empty_folded_list_leaves_its_toggle_out():
    sheet = _with(STACK_SAMPLE, lambda clone: clone["prSheet"].__setitem__("craft", []))
    page = _page(sheet, "return order();")
    assert page["result"] == _expected_order(sheet) and "pr-craft" not in page["result"]


# Bites on: a PR sheet drawn without its wording file (nothing may be drawn, and the store is not reached), or with a wording file that lacks words it needs.
@pytest.mark.parametrize("kind", ["pr", "stack"])
@pytest.mark.parametrize("broken, expected", [
    ({"status": 404, "body": "missing"}, "HTTP 404"),
    ({"status": 200, "body": '{"history": '}, "valid JSON"),
    ({"reject": True}, "could not be loaded"),
], ids=["missing", "invalid-json", "rejected"])
def test_a_pr_sheet_without_its_wording_file_shows_the_error_box(kind, broken, expected):
    files = _files(SAMPLES[kind])
    files["sheet-words.json"] = broken
    page = _run_page(files, scenario="return { uses: t.uses, reads: t.reads.length, sets: t.sets.length };")
    _assert_error_shown(page)
    assert any("wording file" in error and expected in error for error in page["errors"]), page["errors"]
    assert page["result"] == {"uses": [], "reads": 0, "sets": 0}


def test_a_wording_file_missing_a_pr_word_shows_the_error_box():
    words = copy.deepcopy(WORDS)
    del words["pr"]["verdictHeading"]
    page = _run_page(_files(PR_SAMPLE, words), scenario="return { uses: t.uses, sets: t.sets.length };")
    _assert_error_shown(page)
    assert page["result"] == {"uses": [], "sets": 0}


# Bites on: an owner-facing string of a PR sheet typed in the page instead of read from sheet-words.json: every new word is replaced by a marked copy, and each must show up marked.
def test_every_new_word_comes_from_the_words_file():
    new_keys = [
        "whatChangedHeading", "reviewedBy", "familyUnknown", "notIndependentMark", "caughtHeading", "roundsLine", "ciLine",
        "laneLine", "describesCommit", "changedHeading", "changed", "walkHeading", "walkStopPr", "acceptingHeading",
        "craftHeading", "decidedHeading", "reviewHeading", "prsHeading", "verdictHeading", "mergeLabel", "mergeStackLabel",
        "notYetLabel", "verdictCaption", "acceptedCount", "nothingToAcceptCount", "nothingToAccept", "historyCap",
    ]
    words = copy.deepcopy(WORDS)
    for key in new_keys:
        words["pr"][key] = "«%s» %s" % (key, words["pr"][key])
    for key, value in list(words["prAnswers"]["labels"].items()):
        words["prAnswers"]["labels"][key] = "«%s» %s" % (key, value)
    shown = set()

    def collect(sheet, scenario="return t.everyText();"):
        page = _page(sheet, scenario, words=words)
        shown.update(re.findall(r"«([\w-]+)»", "\n".join(page["result"])))

    stack = _with_previous(STACK_SAMPLE)
    stack = _with(stack, lambda clone: clone["prSheet"]["whatChanged"]["reviewers"][0].__setitem__("family", None))
    collect(stack, """
      t.click(t.button("f-a64d7a0d1734", "Keep it"));
      await t.tick();
      return t.everyText();
    """)
    collect(_emptied(PR_SAMPLE))
    collect(PR_SAMPLE)
    missing = set(new_keys) - shown
    assert not missing, "words typed in the page, or never shown: %s" % sorted(missing)
    assert {"accept", "discuss", "something-else"} <= shown


# Bites on: text from the data file drawn as markup, or the link rule of the other cards not applying to the PR parts.
def test_data_text_is_drawn_as_text_and_links_open_in_a_new_tab():
    tag = "<img src=x onerror=alert(1)>"

    def mutate(clone):
        clone["prSheet"]["whatChanged"]["summary"] = tag + " see https://example.com/pr."
        clone["prSheet"]["whatChanged"]["caught"] = [tag]
        clone["prSheet"]["walk"][0]["title"] = tag
        clone["prSheet"]["craft"][0]["title"] = tag
        clone["prSheet"]["history"][0] = tag
    sheet = _with(PR_SAMPLE, mutate)
    page = _page(sheet, """
      const all = pageNodes().flatMap((node) => t.all(node));
      return { tags: all.map((node) => node.tagName), texts: all.map((node) => node.textContent), links: t.links(part("pr-what-changed")) };
    """)
    assert "img" not in page["result"]["tags"] and "b" not in page["result"]["tags"]
    assert tag in page["result"]["texts"]
    assert page["result"]["links"] == [["https://example.com/pr", "https://example.com/pr", "_blank", "noopener noreferrer"]]
    assert "innerHTML" not in _template_text() and "insertAdjacentHTML" not in _template_text()


# Bites on: a new owner-facing string typed in the template instead of the words file.
def test_the_template_types_none_of_the_new_words():
    script = "\n".join(line for line in _template_text().splitlines() if not line.strip().startswith("//"))
    for key in ("whatChangedHeading", "changedHeading", "walkHeading", "acceptingHeading", "craftHeading", "decidedHeading",
                "reviewHeading", "prsHeading", "verdictHeading", "verdictCaption", "nothingToAcceptCount", "familyUnknown",
                "notIndependentMark", "caughtHeading", "changed"):
        assert PW[key] not in script, "the template types the words of %s" % key
    assert '"Accept"' not in script


# ---------------------------------------------------------------------------------------------------------------------
# The merge verdict's lock, send-back and clear (C9 layer 1b).
# ---------------------------------------------------------------------------------------------------------------------

CARD_A, CARD_B, CARD_C = "f-e490915872bd", "f-a5cb88b79507", "i-6f4a068f1373"

# What a lock scenario can read and do: the three cards of the pr sample (A: Accept / Discuss; B: Keep it, Fix in a follow-up,
# Fix before merge; C: Ten minutes, One minute (sends the PR back)), and the verdict card's lock, unlock line and send-back message.
LOCK = r"""
const A = "f-e490915872bd", B = "f-a5cb88b79507", C = "i-6f4a068f1373";
const rowNode = () => verdict().children.find((child) => hasClass(child, "answer-row"));
const unlockLine = () => verdict().children.find((child) => child.id === "verdict-unlocks");
const sendBackLine = () => verdict().children.find((child) => child.id === "verdict-send-back");
const verdictSave = () => verdict().children.find((child) => hasClass(child, "save-line"));
const lockView = () => ({
  label: verdictRow()[0].textContent,
  disabled: verdictRow()[0].disabled,
  notYetDisabled: verdictRow()[1].disabled,
  noteDisabled: verdictNote().disabled,
  line: unlockLine().hidden ? null : unlockLine().textContent,
  sendBack: { row: rowNode().hidden, note: verdictNote().hidden, message: sendBackLine().hidden ? null : sendBackLine().textContent },
  pressed: verdictRow().map((button) => button.getAttribute("aria-pressed")),
  note: verdictNote().value,
  saves: [A, B, C].map((id) => (t.card(id) ? t.saveText(id) : "")),
  verdictSave: t.text(verdictSave()),
});
const acceptAll = async () => {
  t.click(t.button(A, "Accept"));
  t.click(t.button(B, "Keep it"));
  t.click(t.buttons(C)[0]);
  await t.tick();
};
const settle = async (count) => {
  t.sets.slice(0, count).forEach((call) => call.resolve());
  await t.tick();
};
const verdictWrites = () => t.setLog().filter((item) => item.path.startsWith("verdict/")).map((item) => item.body);
const lastVerdictCall = () => t.sets.filter((call) => call.path.startsWith("verdict/")).pop();
const settleNewestFirst = async () => {
  for (let round = 0; round < 8; round += 1) {
    t.sets.slice().reverse().forEach((call) => call.resolve());
    await t.tick();
  }
};
"""

PENDING = {"set": "pending"}
TIMED = {"fakeTimers": True}


def _lock(sheet, scenario, host=None, words=None):
    return _page(sheet, LOCK + scenario, host=host, words=words)


def _locked_label(kind="pr"):
    return _fill(PW["mergeLocked"], merge=_fill(PW["mergeLabel" if kind == "pr" else "mergeStackLabel"], number=214 if kind == "pr" else 4))


# (id, sheet, host, scenario, accepted, total, locked, sends back)
LOCK_ROWS = [
    ("all-accepted-and-saved", PR_SAMPLE, {}, "await acceptAll(); return lockView();", 3, 3, False, False),
    ("nothing-answered", PR_SAMPLE, {}, "return lockView();", 0, 3, True, False),
    ("accept-in-flight", PR_SAMPLE, PENDING, "await acceptAll(); await settle(2); return lockView();", 2, 3, True, False),
    ("accept-failed", PR_SAMPLE, PENDING, """
      await acceptAll();
      t.sets[0].resolve(); t.sets[1].resolve(); t.sets[2].reject(new Error("no"));
      await t.tick();
      return lockView();
    """, 2, 3, True, False),
    ("accept-stalled", PR_SAMPLE, dict(PENDING, **TIMED), """
      await acceptAll();
      await settle(2);
      await t.advance(10000);
      return lockView();
    """, 2, 3, True, False),
    ("note-pausing", PR_SAMPLE, TIMED, """
      await acceptAll();
      t.type(t.note(A), "because", "input");
      await t.tick();
      return lockView();
    """, 2, 3, True, False),
    ("discuss", PR_SAMPLE, {}, """
      t.click(t.button(A, "Discuss")); t.click(t.button(B, "Keep it")); t.click(t.buttons(C)[0]);
      await t.tick();
      return lockView();
    """, 2, 3, True, False),
    ("something-else", PR_SAMPLE, {}, """
      t.click(t.button(A, "Accept")); t.click(t.button(B, "Keep it")); t.click(t.button(C, "Something else"));
      await t.tick();
      return lockView();
    """, 2, 3, True, False),
    ("option-that-does-not-send-back", PR_SAMPLE, {}, """
      t.click(t.button(A, "Accept")); t.click(t.button(B, "Fix in a follow-up")); t.click(t.buttons(C)[0]);
      await t.tick();
      return lockView();
    """, 3, 3, False, False),
    ("option-that-sends-back", PR_SAMPLE, {}, """
      t.click(t.button(A, "Accept")); t.click(t.button(B, "Keep it")); t.click(t.buttons(C)[1]);
      await t.tick();
      return lockView();
    """, 2, 3, True, True),
    ("no-cards", _emptied(PR_SAMPLE), {}, "return lockView();", 0, 0, False, False),
]


# Bites on: the lock counting the current pick instead of the answer the store acknowledged (an Accept in flight, failed or stalled, or a note still pausing, reading as accepted); a locked sheet whose Merge button keeps the plain words or stays enabled; Not yet or the note switched off by the lock; the unlock line's counts; a sheet with no cards locked; Discuss, Something else or an option that sends the PR back counting as accepted.
@pytest.mark.parametrize("row", LOCK_ROWS, ids=[row[0] for row in LOCK_ROWS])
def test_the_lock_follows_what_the_store_has_acknowledged(row):
    _, sheet, host, scenario, accepted, total, locked, sends_back = row
    view = _lock(sheet, scenario, host)["result"]
    assert view["label"] == (_locked_label() if locked else "Merge #214")
    assert view["disabled"] is locked
    assert view["notYetDisabled"] is False and view["noteDisabled"] is False
    if sends_back:
        assert view["line"] is None
        assert view["sendBack"] == {"row": True, "note": True, "message": PW["sendBack"]}
    else:
        assert view["line"] == (_fill(PW["unlocks"], accepted=accepted, total=total) if locked else None)
        assert view["sendBack"] == {"row": False, "note": False, "message": None}
    if row[0] in ("accept-failed", "accept-stalled"):
        assert "Not saved" in view["saves"][2]


def test_the_lock_words_are_exactly_the_shared_contract():
    for key in ("mergeLocked", "unlocks", "sendBack"):
        words = copy.deepcopy(WORDS)
        del words["pr"][key]
        page = _run_page(_files(PR_SAMPLE, words), scenario="return { uses: t.uses, sets: t.sets.length };")
        _assert_error_shown(page)
        assert page["result"] == {"uses": [], "sets": 0}


# Bites on: the stack sheet not following the pr sheet's lock, or its locked Merge label naming the PR instead of the stack.
def test_a_stack_sheet_locks_and_unlocks_the_same_way():
    page = _lock(STACK_SAMPLE, """
      const id = elements["sheet-cards"].children.filter(isCard)[0].id.replace("card-", "");
      const before = lockView();
      t.click(t.button(id, "Keep it"));
      await t.tick();
      return { before: before, after: lockView() };
    """)
    assert page["result"]["before"]["label"] == _locked_label("stack") == "Merge stack #4 · locked"
    assert page["result"]["before"]["disabled"] is True
    assert page["result"]["before"]["line"] == _fill(PW["unlocks"], accepted=0, total=1)
    assert page["result"]["after"]["label"] == "Merge stack #4" and page["result"]["after"]["disabled"] is False
    assert page["result"]["after"]["line"] is None


# Bites on: a note typed on an accepted card (E4) leaving the sheet unlocked while its pause runs, or staying locked after it saves.
def test_a_note_pause_locks_until_the_note_is_saved():
    page = _lock(PR_SAMPLE, """
      await acceptAll();
      const saved = lockView();
      t.type(t.note(A), "because", "input");
      await t.tick();
      const pausing = lockView();
      await t.advance(1000);
      return { saved: saved, pausing: pausing, after: lockView(), sets: t.setLog().filter((item) => item.path === "answers/" + A).map((item) => item.body) };
    """, host=TIMED)
    assert page["result"]["saved"]["disabled"] is False
    assert page["result"]["pausing"]["disabled"] is True and page["result"]["pausing"]["line"] == _fill(PW["unlocks"], accepted=2, total=3)
    assert page["result"]["after"]["disabled"] is False and page["result"]["after"]["line"] is None
    assert page["result"]["sets"][-1] == {"answer": "accept", "optionId": None, "note": "because"}


# Bites on: a Merge saved and then lost to a card going to Discuss staying on the page or in the store (E5): the clear missing, or not keeping the note, or not written as the verdict's own document.
def test_a_saved_merge_is_cleared_when_a_card_goes_to_discuss():
    digest = _sheet_digest(PR_SAMPLE)
    page = _lock(PR_SAMPLE, """
      await acceptAll();
      t.type(verdictNote(), "go ahead", "change");
      t.click(verdictRow()[0]);
      await t.tick();
      const merged = lockView();
      t.click(t.button(A, "Discuss"));
      await t.tick();
      return { merged: merged, after: lockView(), writes: verdictWrites(), stored: t.written()["verdict/%s"] };
    """ % digest)
    result = page["result"]
    assert result["merged"]["pressed"] == ["true", "false"]
    assert result["after"]["pressed"] == ["false", "false"] and result["after"]["note"] == "go ahead"
    assert result["after"]["disabled"] is True and result["after"]["label"] == _locked_label()
    cleared = {"verdict": None, "note": "go ahead", "sheet": digest}
    assert result["writes"] == [
        {"verdict": None, "note": "go ahead", "sheet": digest},
        {"verdict": "merge", "note": "go ahead", "sheet": digest},
        cleared,
    ]
    assert result["stored"] == cleared


# Bites on: the clear writing straight to the store instead of queueing behind the verdict's write in flight (E6): a Merge still pending landing after the clear.
def test_a_clear_queues_behind_a_merge_still_in_flight():
    digest = _sheet_digest(PR_SAMPLE)
    page = _lock(PR_SAMPLE, """
      await acceptAll();
      await settle(3);
      t.click(verdictRow()[0]);
      await t.tick();
      t.click(t.button(A, "Discuss"));
      await t.tick();
      const whileInFlight = verdictWrites();
      t.sets[3].resolve();
      await t.tick();
      await settleNewestFirst();
      return { whileInFlight: whileInFlight, writes: verdictWrites(), stored: t.written()["verdict/%s"], after: lockView() };
    """ % digest, host=PENDING)
    result = page["result"]
    assert result["whileInFlight"] == [{"verdict": "merge", "note": "", "sheet": digest}]
    cleared = {"verdict": None, "note": "", "sheet": digest}
    assert result["writes"] == [{"verdict": "merge", "note": "", "sheet": digest}, cleared]
    assert result["stored"] == cleared
    assert result["after"]["pressed"] == ["false", "false"] and result["after"]["disabled"] is True


# Bites on: a failed clear write not shown as "Not saved" with Try again (E7), the sheet unlocking on it, or Try again not sending the cleared document.
def test_a_failed_clear_shows_not_saved_and_the_sheet_stays_locked():
    digest = _sheet_digest(PR_SAMPLE)
    page = _lock(PR_SAMPLE, """
      await acceptAll();
      await settle(3);
      t.click(verdictRow()[0]);
      await t.tick();
      t.sets[3].resolve();
      await t.tick();
      t.click(t.button(A, "Discuss"));
      await t.tick();
      lastVerdictCall().reject(new Error("no"));
      await t.tick();
      const failed = lockView();
      const retry = verdictSave().children.find((child) => child.tagName === "button");
      t.click(retry);
      await t.tick();
      lastVerdictCall().resolve();
      await t.tick();
      return { failed: failed, retried: verdictWrites(), after: lockView(), retryWas: retry.textContent };
    """, host=PENDING)
    result = page["result"]
    assert "Not saved" in result["failed"]["verdictSave"] and result["retryWas"] == "Try again"
    assert result["failed"]["disabled"] is True and result["failed"]["label"] == _locked_label()
    assert result["failed"]["pressed"] == ["false", "false"]
    cleared = {"verdict": None, "note": "", "sheet": digest}
    assert result["retried"] == [{"verdict": "merge", "note": "", "sheet": digest}, cleared, cleared]
    assert "Saved" in result["after"]["verdictSave"] and result["after"]["disabled"] is True


# Bites on: a card accepted again after its Discuss was acknowledged unlocking Merge while the failed clear still leaves the old Merge in the store, or that stored Merge coming back as a pressed verdict when the sheet is reopened.
def test_re_accepting_after_a_failed_clear_keeps_merge_locked_and_the_stored_merge_does_not_return():
    digest = _sheet_digest(PR_SAMPLE)
    page = _lock(PR_SAMPLE, """
      await acceptAll();
      await settle(3);
      t.click(verdictRow()[0]);
      await t.tick();
      t.sets[3].resolve();
      await t.tick();
      t.click(t.button(A, "Discuss"));
      await t.tick();
      const answerCall = () => t.sets.filter((call) => call.path === "answers/" + A).pop();
      answerCall().resolve();
      await t.tick();
      lastVerdictCall().reject(new Error("no"));
      await t.tick();
      const failed = lockView();
      t.click(t.button(A, "Accept"));
      await t.tick();
      answerCall().resolve();
      await t.tick();
      const reaccepted = lockView();
      const stillStored = t.written()["verdict/%s"];
      t.click(verdictSave().children.find((child) => child.tagName === "button"));
      await t.tick();
      lastVerdictCall().resolve();
      await t.tick();
      return { failed: failed, reaccepted: reaccepted, stillStored: stillStored, after: lockView(), written: t.written() };
    """ % digest, host=PENDING)
    result = page["result"]
    assert result["failed"]["pressed"] == ["false", "false"] and result["failed"]["disabled"] is True
    assert result["stillStored"]["verdict"] == "merge"
    assert result["reaccepted"]["disabled"] is True and result["reaccepted"]["label"] == _locked_label()
    assert result["reaccepted"]["pressed"] == ["false", "false"]
    assert "Not saved" in result["reaccepted"]["verdictSave"]
    assert result["after"]["disabled"] is False and result["after"]["pressed"] == ["false", "false"]
    stored = result["written"]
    assert stored["verdict/" + digest]["verdict"] is None
    reopened = _lock(PR_SAMPLE, "return lockView();", host={"collections": {
        "answers": [{"id": path.split("/", 1)[1], "data": data} for path, data in stored.items() if path.startswith("answers/")],
        "verdict": [{"id": path.split("/", 1)[1], "data": data} for path, data in stored.items() if path.startswith("verdict/")],
    }})
    assert reopened["result"]["pressed"] == ["false", "false"]


# Bites on: a stored Merge restored onto a sheet that is locked once its answers are restored (E8) staying a Merge, or being cleared when the sheet is not locked.
def test_a_stored_merge_is_cleared_after_load_on_a_locked_sheet_and_kept_on_an_open_one():
    digest = _sheet_digest(PR_SAMPLE)
    stored = {"id": digest, "data": {"verdict": "merge", "note": "my verdict note", "sheet": digest}}

    def answers(*rows):
        return [{"id": card, "data": {"answer": answer, "optionId": option, "note": ""}} for card, answer, option in rows]

    locked = _lock(PR_SAMPLE, "return { view: lockView(), writes: verdictWrites() };", host={"collections": {
        "answers": answers((CARD_A, "discuss", None), (CARD_B, "option", "keep-it"), (CARD_C, "option", "ten-minutes")),
        "verdict": [stored],
    }})
    assert locked["result"]["view"]["pressed"] == ["false", "false"] and locked["result"]["view"]["note"] == "my verdict note"
    assert locked["result"]["view"]["disabled"] is True
    assert locked["result"]["writes"] == [{"verdict": None, "note": "my verdict note", "sheet": digest}]
    open_sheet = _lock(PR_SAMPLE, "return { view: lockView(), writes: verdictWrites() };", host={"collections": {
        "answers": answers((CARD_A, "accept", None), (CARD_B, "option", "keep-it"), (CARD_C, "option", "ten-minutes")),
        "verdict": [stored],
    }})
    assert open_sheet["result"]["view"]["pressed"] == ["true", "false"] and open_sheet["result"]["view"]["disabled"] is False
    assert open_sheet["result"]["writes"] == []


# Bites on: the verdict buttons, note or unlock line left up when a card's current pick sends the PR back (E9), the message missing, the verdict not coming back when the pick is cleared or changed, or a saved Merge not cleared.
def test_a_pick_that_sends_the_pr_back_replaces_the_verdict_with_its_message():
    digest = _sheet_digest(PR_SAMPLE)
    page = _lock(PR_SAMPLE, """
      await acceptAll();
      await settle(3);
      t.click(verdictRow()[0]);
      await t.tick();
      t.sets[3].resolve();
      await t.tick();
      const merged = lockView();
      t.click(t.button(B, "Fix before merge"));
      await t.tick();
      const sentBack = lockView();
      await settleNewestFirst();
      const settled = lockView();
      t.click(t.button(B, "Fix before merge"));
      await t.tick();
      const cleared = lockView();
      t.click(t.button(B, "Keep it"));
      await t.tick();
      await settleNewestFirst();
      return { merged: merged, sentBack: sentBack, settled: settled, cleared: cleared, back: lockView(), writes: verdictWrites() };
    """, host=PENDING)
    result = page["result"]
    assert result["merged"]["pressed"] == ["true", "false"] and result["merged"]["sendBack"]["message"] is None
    for name in ("sentBack", "settled"):
        assert result[name]["sendBack"] == {"row": True, "note": True, "message": PW["sendBack"]}, name
        assert result[name]["line"] is None, name
    assert result["settled"]["pressed"] == ["false", "false"]
    assert result["writes"][-1] == {"verdict": None, "note": "", "sheet": digest}
    assert result["cleared"]["sendBack"] == {"row": False, "note": False, "message": None}
    assert result["cleared"]["line"] == _fill(PW["unlocks"], accepted=2, total=3)
    assert result["back"]["line"] is None and result["back"]["disabled"] is False and result["back"]["label"] == "Merge #214"


# Bites on: the send-back waiting for the store to acknowledge the pick (it follows the pick the button shows, even while its write is in flight).
def test_the_send_back_message_follows_the_pick_even_while_its_write_is_in_flight():
    page = _lock(PR_SAMPLE, """
      t.click(t.button(B, "Fix before merge"));
      await t.tick();
      return { view: lockView(), sets: t.setLog().length };
    """, host=PENDING)
    assert page["result"]["sets"] == 1
    assert page["result"]["view"]["sendBack"] == {"row": True, "note": True, "message": PW["sendBack"]}


# Bites on: a sheet with no cards locked, or its Merge enabled before the saved answers are read or without a digest (E10, E11); the lock line missing the count without a digest.
def test_no_cards_unlocks_once_ready_and_a_missing_digest_keeps_the_controls_off_but_the_count_shown():
    empty = _emptied(PR_SAMPLE)
    ready = _lock(empty, "return lockView();")["result"]
    assert ready["label"] == "Merge #214" and ready["disabled"] is False and ready["line"] is None
    waiting = _lock(empty, "return lockView();", host={"read": "pending"})["result"]
    assert waiting["label"] == "Merge #214" and waiting["disabled"] is True
    no_digest_empty = _lock(empty, "return lockView();", host={"noCrypto": True})["result"]
    assert no_digest_empty["label"] == "Merge #214" and no_digest_empty["disabled"] is True and no_digest_empty["line"] is None
    no_digest = _lock(PR_SAMPLE, "return lockView();", host={"noCrypto": True})["result"]
    assert no_digest["disabled"] is True and no_digest["notYetDisabled"] is True and no_digest["noteDisabled"] is True
    assert no_digest["label"] == _locked_label()
    assert no_digest["line"] == _fill(PW["unlocks"], accepted=0, total=3)


# Bites on: a non-owner or a page with no store getting a control, a write or a clear (E12), even with a Merge in the store.
@pytest.mark.parametrize("host", [{"user": "reader"}, {"user": "null"}, {"claude": "missing"}, {"db": "null"}], ids=["non-owner", "no-user", "no-host", "no-store"])
def test_no_store_or_a_non_owner_gets_no_controls_and_no_clear(host):
    digest = _sheet_digest(PR_SAMPLE)
    stored = {"id": digest, "data": {"verdict": "merge", "note": "n", "sheet": digest}}
    answers = [{"id": CARD_A, "data": {"answer": "discuss", "optionId": None, "note": ""}}]
    page = _lock(PR_SAMPLE, """
      const answerControls = [...elements["sheet-cards"].children.filter(isCard), verdict()]
        .flatMap((node) => t.all(node))
        .filter((node) => node.tagName === "button" || node.tagName === "textarea");
      return { view: lockView(), controls: answerControls.map((node) => node.disabled), count: answerControls.length, sets: t.sets.length };
    """, host=dict(host, collections={"answers": answers, "verdict": [stored]}))
    result = page["result"]
    assert result["count"] > 10 and all(result["controls"]) and result["sets"] == 0
    assert result["view"]["pressed"] == ["false", "false"] and result["view"]["disabled"] is True


def _republished(sheet):
    """The sheet published again with one more byte (a new title), so its digest is new and every card id is unchanged."""
    return _with(sheet, lambda clone: clone.__setitem__("title", clone["title"] + " (second edition)"))


# Bites on: a verdict saved under the old digest restored on a republished sheet (UFR-6, R8), or an answer under a card id the new file still has not restored.
def test_a_new_commit_starts_the_verdict_over_and_keeps_the_answers_of_unchanged_cards():
    again = _republished(PR_SAMPLE)
    assert _sheet_digest(again) != _sheet_digest(PR_SAMPLE)
    assert [card["id"] for card in again["cards"]] == [card["id"] for card in PR_SAMPLE["cards"]]
    old = _sheet_digest(PR_SAMPLE)
    host = {"collections": {
        "answers": [{"id": CARD_A, "data": {"answer": "accept", "optionId": None, "note": "still true"}}],
        "verdict": [{"id": old, "data": {"verdict": "not-yet", "note": "old note", "sheet": old}}],
    }}
    same = _lock(PR_SAMPLE, "return { verdict: lockView(), card: t.state(A) };", host=host)["result"]
    assert same["verdict"]["pressed"] == ["false", "true"] and same["verdict"]["note"] == "old note"
    new = _lock(again, "return { verdict: lockView(), card: t.state(A), writes: verdictWrites() };", host=host)["result"]
    assert new["verdict"]["pressed"] == ["false", "false"] and new["verdict"]["note"] == ""
    assert new["card"]["pressed"] == ["true", "false"] and new["card"]["note"] == "still true"
    assert new["writes"] == []


# Bites on: the final sheet picking up the lock, the send-back or the clear (V7): its Approve locked, labelled as locked, or cleared, or an unlock line or send-back message drawn on it.
def test_a_final_sheet_still_saves_approve_with_no_lock():
    sheet = _sample_final()
    digest = _sheet_digest(sheet)
    page = _run_page(_files(sheet), scenario="""
      const card = elements["sheet-cards"].children.find((child) => child.tagName === "article");
      if (card) t.click(t.buttons(card.id.replace("card-", ""))[1]);
      await t.tick();
      const before = t.lastState();
      t.click(t.lastButton("Approve"));
      await t.tick();
      return {
        before: before, after: t.lastState(), sets: t.setLog().filter((item) => item.path.startsWith("verdict/")),
        ids: t.lastCard().children.map((child) => child.id).filter((id) => id !== ""),
      };
    """, host={"collections": {"answers": [], "verdict": []}})
    result = page["result"]
    assert result["before"]["labels"] == ["Approve", "Not yet"] and not any(result["before"]["disabled"])
    assert result["after"]["pressed"] == ["true", "false"] and result["after"]["labels"] == ["Approve", "Not yet"]
    assert result["sets"] == [{"path": "verdict/" + digest, "body": {"verdict": "approve", "note": "", "sheet": digest}}]
    assert "verdict-unlocks" not in result["ids"] and "verdict-send-back" not in result["ids"]
    stored = _run_page(_files(sheet), scenario="return { state: t.lastState(), sets: t.setLog() };", host={"collections": {
        "answers": [], "verdict": [{"id": digest, "data": {"verdict": "approve", "note": "", "sheet": digest}}],
    }})
    assert stored["result"]["state"]["pressed"] == ["true", "false"] and stored["result"]["sets"] == []
