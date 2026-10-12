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
    assert WORDS["prAnswers"] == {
        "labels": {"accept": "Accept", "discuss": "Discuss", "something-else": "Something else"},
        "withOptions": ["something-else"],
        "withoutOptions": ["accept", "discuss"],
    }


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
    """)
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
        merge = _page(sheet, "return verdictState();", host={"collections": {"verdict": [_verdict_doc(sheet, "merge")]}})
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
