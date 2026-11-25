"""Guards for issue 2636: list-item cards with dashed numbers, and the left-for-owner findings a list-item card carries.

A collectorItems number is an integer 1 or more or a string N or N-M, shown as written and compared through one canonical form. A leftovers
value {"carriedBy": number} gives a finding no card and no decided-for-you entry: the list-item card lists it under its carriedTitle section.
Row ids and test names carry the guarded element (e01 to e14), so a bite-proof run selects one element with -k.
"""
import copy

import pytest

import pr_sheet
from test_pr_sheet import COLLECTOR, FIXTURES, STACK, WORDS, build, bundle, cli, leftover_cards, load, problems_of
from test_review_template_pr import _page

NEEDS_NUMBER = "collectorItems entry 1 needs number, an integer 1 or more or a string N or N-M"
ONE_ENTRY = "give one entry"


def finding(fid, key, title):
    return {"id": fid, "outcome": "left-for-owner", "title": title, "reason": "Only the owner can say.",
            "consequence": "A customer may notice.", "findingKey": key}


GIFT = finding("A1", "shop/gift-tone", "Gift receipts read oddly to the buyer")
TOTAL = finding("A2", "shop/total-line", "The thank-you line may show the total")
FONT = finding("A3", "shop/receipt-font", "The receipt font changes between pages")
GIFT_TWIN = finding("A1", "shop/gift-tone-again", GIFT["title"])  # GIFT's reviewer id and title under another findingKey: only the key differs
CALL = {"why": "Only you can decide the tone.", "context": "It happened on the receipt page.", "options": "none"}
DETERMINATION = {"ground": "A Canon entry answers it", "reason": "The shop's tone is already ruled."}


def kind_of(number):
    return pr_sheet._fill(WORDS["collectorKind"], number=number)


def small(numbers=("2273-1", 1501), findings=(), leftovers=None, determinations=None):
    """The small collector case with its two cards renumbered and these record findings; a finding is named by leftovers or craftDeterminations."""
    records, advisor = bundle(COLLECTOR)
    records[0]["findings"] = [dict(f) for f in findings]
    for entry, number in zip(advisor["collectorItems"], numbers):
        entry["number"] = number
    if leftovers is not None:
        advisor["leftovers"] = leftovers
    if determinations is not None:
        advisor["craftDeterminations"] = determinations
    return records, advisor


def card_for(sheet, number):
    return next(c for c in sheet["cards"] if c["callKind"] == kind_of(number))


def collector_cards(sheet):
    return [c for c in sheet["cards"] if c["id"].startswith("k-")]


def stack():
    """The stack case with two list-item cards (2273-1, 2273-2); findings of PRs 5, 6 and 7 are carried, split across them, and one is a craft determination."""
    records, advisor = bundle(STACK)
    records[0]["findings"].append(finding("K5", "giftcard/number-format", "Gift card numbers print without spaces"))
    records[2]["findings"].append(finding("K7", "giftcard/balance-rounding", "The balance rounds down at checkout"))
    records[2]["findings"].append(finding("L7", "giftcard/balance-copy", "The balance line reads as a promise"))
    cards = copy.deepcopy(bundle(COLLECTOR)[1]["collectorItems"])
    cards[0]["number"], cards[1]["number"] = "2273-1", "2273-2"
    advisor["collectorItems"] = cards
    advisor["leftovers"] = {"5:giftcard/number-format": {"carriedBy": "2273-1"}, "6:giftcard/split-payment": {"carriedBy": "2273-2"},
                            "7:giftcard/balance-rounding": {"carriedBy": "2273-2"}}
    advisor["craftDeterminations"] = {"7:giftcard/balance-copy": DETERMINATION}
    return records, advisor


STACK_LINES = {
    "2273-1": ["#5: Gift card numbers print without spaces"],
    "2273-2": ["#6: A gift card that covers part of an order leaves the rest unpaid", "#7: The balance rounds down at checkout"],
}


@pytest.mark.parametrize("number", ["2273-1", "2273", 5, 1, "9" * 18, "9" * 18 + "-" + "9" * 18], ids=lambda n: f"e01-builds-{n!r}")
def test_e01_a_list_number_builds_and_is_shown_as_written(number):
    # Axis: a list-item number written as an integer 1 or more, or a string N or N-M, builds, and the card's label shows it exactly as written.
    # Bites on: a valid spelling refused, or the label changed from the number as written.
    records, advisor = small((number, 1501))
    assert card_for(build(records, advisor), number)["callKind"] == kind_of(number)
    assert str(number) in kind_of(number)  # the label shows the number as written


@pytest.mark.parametrize("number", ["02273", "2273-01", "2273-0", "0", 0, True, "2273-1-2", "a-1", 2273.0, "1" * 19, "2273-" + "1" * 19, "1" * 4301],
                         ids=lambda n: f"e01-refused-{n!r}" if len(repr(n)) < 20 else f"e01-refused-{len(str(n))}-chars")
def test_e01_a_malformed_list_number_is_refused(number):
    # Axis: a list-item number with a leading zero, a zero part, a third part, a letter, a bool or a float is refused: every number has exactly one spelling.
    # Bites on: the pattern accepting leading zeros or zero parts, or the check taking a bool or a float for an integer.
    records, advisor = small((number, 1501))
    assert problems_of(records, advisor) == [NEEDS_NUMBER]


def test_e02_the_same_number_in_two_spellings_repeats():
    # Axis: 2273 and "2273" are one item, so listing both is a repeat; the comparison is by the canonical key.
    # Bites on: duplicates compared as written.
    records, advisor = small((2273, "2273"))
    assert problems_of(records, advisor) == ["collectorItems 2273 repeats the number 2273"]


OWN_FORMS = ["2273-1", "collector item 2273-1", "collector #2273-1", "collector number 2273-1", "if you pick a on 2273-1", "card 2273-1",
             "if you pick a on card 2273-1", "if you pick a on collector item 2273-1", "only if you pick b on card #2273-1",
             "if you pick a on collector card 2273-1", "if you pick a on card 2273-1, 12 gift receipts change and"]


@pytest.mark.parametrize("field", ["reason", "consequence"])
@pytest.mark.parametrize("form", OWN_FORMS, ids=lambda f: f"e03-{f.replace(' ', '-')}")
def test_e03_a_cards_own_dashed_number_is_not_another_question(form, field):
    # Axis: a card's own collector number, dashed, in any of the scanned forms, is not another question.
    # Bites on: the own-number exemption dropped, so a card cannot name itself.
    records, advisor = small(("2273-1", 1501))
    card = advisor["collectorItems"][0]
    if field == "reason":
        card["recommendation"]["reason"] = f"See {form} here."
    else:
        card["options"][0]["consequence"] = f"See {form} here."
    assert card_for(build(records, advisor), "2273-1")["question"] == card["title"]


def with_text(numbers, at, text, field="reason"):
    records, advisor = small(numbers)
    card = advisor["collectorItems"][at]
    if field == "reason":
        card["recommendation"]["reason"] = text
    else:
        card["options"][0]["consequence"] = text
    return records, advisor


@pytest.mark.parametrize("text", ["2273-2", "2273-10", "collector #2273-2", "if you pick a on 2273-2", "if you pick a on card 2273-2",
                                  "if you pick a on collector item 2273-2", "if you pick a on the other card"],
                         ids=lambda t: "e04-other-" + t.replace(" ", "-"))
def test_e04_another_dashed_item_is_still_another_question(text):
    # Axis: another dashed number on a card whose own number shares its base is another question, in each scanned form.
    # Bites on: the own-number exemption reading only the base digits of the number, so a sibling item passes as the card's own.
    problems = problems_of(*with_text(("2273-1", "2273-2"), 0, f"See {text} here."))
    assert problems and all(p.startswith("dependent-question: collectorItems 2273-1: ") for p in problems)


def test_e04_a_plain_card_naming_a_dashed_item_is_refused():
    # Axis: a plain number's card naming a dashed item of the same base is another question.
    # Bites on: a dashed number read as its base digits.
    problems = problems_of(*with_text((2273, 1501), 0, "See 2273-1 here."))
    assert problems and all(p.startswith("dependent-question: collectorItems 2273: ") for p in problems)


def test_e04_one_field_holding_the_own_and_another_number_reports_one_problem_naming_the_other():
    # Axis: a field that names its own dashed number and another dashed number is reported once, for the other.
    # Bites on: the own number reported too, or the other reported twice (once by each scan).
    problems = problems_of(*with_text(("2273-1", "2273-2"), 0, "Both 2273-1 and 2273-2 matter."))
    assert len(problems) == 1 and "('2273-2')" in problems[0] and problems[0].startswith("dependent-question: collectorItems 2273-1: ")


def test_e15_a_field_naming_its_own_card_in_a_conditional_beside_another_item_reports_only_the_other():
    # Axis: in one field, a conditional naming the card's own number (on card 2273-1) is exempt while a conditional naming another item (on card 2273-2) is still reported.
    # Bites on: the conditional's target number not read, so the own reference is reported; or the exemption swallowing the other one.
    both = problems_of(*with_text(("2273-1", "2273-2"), 0, "Only if you pick a on card 2273-1, and only if you pick b on card 2273-2."))
    other_only = problems_of(*with_text(("2273-1", "2273-2"), 0, "And only if you pick b on card 2273-2."))
    assert other_only and both == other_only  # the own conditional adds nothing; the other one is reported exactly as it is alone
    assert len(collector_cards(build(*with_text(("2273-1", "2273-2"), 0, "Only if you pick a on card 2273-1.")))) == 2


@pytest.mark.parametrize("text", [
    "Use the answer on the card above 2273-1.",
    "Use the wording chosen on the card below 2273-1.",
    "Use the same answer as card 2273-1's predecessor.",
    "Keep the pricing copy only if the decisions above 2273-1 approve it.",
    "Costs less if you chose a for cards 2273-1 and 12.",
    "Only if you pick a on card 2273-1's twin.",
    "Only if you pick a on card 2273-1 or 12.",
    "Only if you pick a on item 2273-1 or item 12.",
], ids=["e15-card-above", "e15-card-below", "e15-same-answer-possessive", "e15-decisions-above", "e15-a-list-of-cards", "e15-possessive-target",
        "e15-one-of-several-targets", "e15-one-of-several-targets-repeated-noun"])
def test_e15_the_cards_own_number_used_to_describe_another_card_is_still_another_question(text):
    # Axis: the own-number exemption after a choice's target applies only when the number completes the target of a choice
    # (if you pick a on card 2273-1); a positional or possessive reference, or a list of cards, still depends on another question.
    # Bites on: the exemption read after any hit, or a number read as the whole target when it is one of several or a possessive.
    problems = problems_of(*with_text(("2273-1", 1501), 0, text))
    assert problems and all(p.startswith("dependent-question: collectorItems 2273-1: ") for p in problems)


@pytest.mark.parametrize("text", ["Print SKU 2273-1501 on the slip.", "Use the range 1501-2273 for the batch."],
                         ids=["e25-leading-dash-guard", "e26-trailing-dash-guard"])
def test_e25_e26_an_on_sheet_number_inside_a_longer_dashed_token_is_not_another_question(text):
    # Axis: the bare-number scan reads another on-sheet number (1501) only as a whole token: not after "<digit>-" (the leading
    # guard, SKU 2273-1501) and not before "-<digit>" (the trailing guard, range 1501-2273). Neither text is a dashed
    # reference the D5 wording reads, so the card builds.
    # Bites on: either dash guard of the bare-number pattern removed, so the token's tail or head is read as card 1501.
    records, advisor = with_text(("2273-1", 1501), 0, text)
    assert len(collector_cards(build(records, advisor))) == 2


def test_e04_a_bare_reference_to_another_on_sheet_card_outside_the_dash_widths_is_refused():
    # Axis: another on-sheet number, written bare and dashed in a width the dashed-reference wording does not read (7-123), is another question.
    # Bites on: the bare scan reading only plain numbers, or its alternation not escaping the dash.
    records, advisor = small(("2273-1", "2273-2"))
    advisor["collectorItems"].append(copy.deepcopy(advisor["collectorItems"][0]))
    advisor["collectorItems"][2]["number"] = "7-123"
    advisor["collectorItems"][1]["recommendation"]["reason"] = "See 7-123 here."
    problems = problems_of(records, advisor)
    assert len(problems) == 1 and "('7-123')" in problems[0] and problems[0].startswith("dependent-question: collectorItems 2273-2: ")
    advisor["collectorItems"][1]["recommendation"]["reason"] = "Nothing else to read."
    advisor["collectorItems"][2]["recommendation"]["reason"] = "See 7-123 here."  # its own number
    assert len(collector_cards(build(records, advisor))) == 3


def test_e05_a_carriedBy_naming_no_card_is_refused():
    # Axis: a carriedBy must name a collectorItems card on this sheet.
    # Bites on: the names-no-card check skipped, so the finding would vanish from the sheet.
    records, advisor = small(("2273", 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": 9999}})
    assert problems_of(records, advisor) == [
        f"leftovers {GIFT['findingKey']}: carriedBy 9999 names no list-item card on this sheet; give a collectorItems entry with that number"]


@pytest.mark.parametrize("value, expected", [
    pytest.param({"carriedBy": "02273"}, "carriedBy must be a list-item number, an integer 1 or more or a string N or N-M", id="e06-leading-zero"),
    pytest.param({"carriedBy": 2273, "why": "x"}, "carriedBy takes no other key", id="e06-another-key"),
    pytest.param({"carriedBy": None}, "carriedBy must be a list-item number, an integer 1 or more or a string N or N-M", id="e06-null"),
])
def test_e06_a_malformed_carriedBy_is_refused(value, expected):
    # Axis: carriedBy is exactly one list-item number and stands alone in its entry.
    # Bites on: extra keys accepted beside carriedBy, or a malformed number accepted.
    records, advisor = small((2273, 1501), [GIFT], {GIFT["findingKey"]: value})
    assert problems_of(records, advisor) == [f"leftovers {GIFT['findingKey']}: {expected}"]


def test_e07_a_carriedBy_beside_a_second_entry_for_the_same_finding_is_refused():
    # Axis: a finding has one disposition: an entry under its findingKey and a carriedBy under its id are two.
    # Bites on: the alias-conflict check skipped, so the first entry silently wins.
    records, advisor = small((2273, 1501), [GIFT], {GIFT["findingKey"]: CALL, GIFT["id"]: {"carriedBy": 2273}})
    problems = problems_of(records, advisor)
    assert len(problems) == 1 and repr(GIFT["title"]) in problems[0] and ONE_ENTRY in problems[0]


@pytest.mark.parametrize("card, by", [(2273, "2273"), ("2273", 2273), ("2273-1", "2273-1")], ids=["e08-int-card", "e08-string-card", "e08-dashed-card"])
def test_e08_a_carried_finding_makes_no_card_of_its_own(card, by):
    # Axis: a finding carried by a list-item card has no leftover card; the list-item cards are all the sheet's cards.
    # Bites on: a carried finding falling through to a card of its own.
    sheet = build(*small((card, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": by}}))
    assert leftover_cards(sheet) == [] and len(sheet["cards"]) == 2 and all(c["question"] != GIFT["title"] for c in sheet["cards"])
    # ...and it lands on the carrying card, whichever spelling carriedBy and the card's number use.
    assert card_for(sheet, card)["context"][-1] == {"title": WORDS["carriedTitle"], "blocks": [{"bullets": [GIFT["title"]]}]}


def test_e09_a_carried_finding_is_not_a_decided_for_you_entry():
    # Axis: a carried finding is in no decided-for-you entry; a real craft determination for another finding still is.
    # Bites on: a carried finding also written to decidedForYou.
    sheet = build(*small((2273, 1501), [GIFT, TOTAL], {GIFT["findingKey"]: {"carriedBy": 2273}}, {TOTAL["findingKey"]: DETERMINATION}))
    assert [e["title"] for e in sheet["prSheet"]["decidedForYou"]] == [TOTAL["title"]]


def test_e10_the_carrying_card_lists_each_carried_finding_last_and_a_card_carrying_none_has_no_section():
    # Axis: the card that carries findings ends with a section titled by the words' carriedTitle, a bullets block of each carried finding's title in record order; any other card has none.
    # Bites on: the section not appended, or its title, block kind or order wrong.
    leftovers = {k["findingKey"]: {"carriedBy": 2273} for k in (GIFT, TOTAL, FONT)}
    sheet = build(*small((2273, 1501), [GIFT, TOTAL, FONT], leftovers))
    assert card_for(sheet, 2273)["context"][-1] == {"title": WORDS["carriedTitle"], "blocks": [{"bullets": [GIFT["title"], TOTAL["title"], FONT["title"]]}]}
    assert [s["title"] for s in card_for(sheet, 1501)["context"]] == [WORDS["whyYours"], WORDS["whatHappened"], WORDS["ifLeft"]]
    assert [s["title"] for s in card_for(sheet, 2273)["context"]][:3] == [WORDS["whyYours"], WORDS["whatHappened"], WORDS["ifLeft"]]


def test_e10_on_a_stack_each_carried_line_starts_with_its_pr():
    # Axis: on a stack each carried line starts with #<pr>: and the lines are in record order, split across the cards they name.
    # Bites on: the PR tag left off, or the lines not under the card each names.
    sheet = build(*stack())
    for number, lines in STACK_LINES.items():
        assert card_for(sheet, number)["context"][-1] == {"title": WORDS["carriedTitle"], "blocks": [{"bullets": lines}]}


def test_e11_the_carried_identity_is_in_the_card_id():
    # Axis: a card's id changes with what it carries (the finding's key, not only its title), is stable across builds, and a card carrying nothing keeps its id.
    # Bites on: the id left as the number alone, so two different carried findings share it.
    gift = build(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": 2273}}))
    twin = build(*small((2273, 1501), [GIFT_TWIN], {GIFT_TWIN["findingKey"]: {"carriedBy": 2273}}))
    again = build(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": 2273}}))
    nothing = build(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": 1501}}))
    assert card_for(gift, 2273)["context"] == card_for(twin, 2273)["context"]
    assert card_for(gift, 2273)["id"] != card_for(twin, 2273)["id"]
    assert card_for(gift, 2273)["id"] == card_for(again, 2273)["id"]
    plain = build(*small((2273, 1501)))  # the same sheet with no finding at all: the card that carries nothing keeps this id
    assert card_for(nothing, 2273)["id"] == card_for(plain, 2273)["id"] != card_for(gift, 2273)["id"]
    assert card_for(nothing, 1501)["id"] != card_for(plain, 1501)["id"]


def test_e16_a_plain_number_keeps_one_card_id_in_either_spelling():
    # Axis: 2273 and "2273" are one item, so a republish that changes only the number's JSON type keeps the card id, with and without a carried finding.
    # Bites on: the card id hashing the raw number, so the saved answer is lost on a type change.
    for carried in (None, {GIFT["findingKey"]: {"carriedBy": 2273}}):
        findings = [GIFT] if carried else []
        as_int = build(*small((2273, 1501), findings, carried))
        as_str = build(*small(("2273", 1501), findings, carried))
        assert card_for(as_int, 2273)["id"] == card_for(as_str, "2273")["id"]
    dashed = build(*small(("2273-1", 1501)))
    assert card_for(dashed, "2273-1")["id"] != card_for(build(*small((2273, 1501))), 2273)["id"]


def test_e11_a_card_carrying_nothing_has_its_id_from_base():
    # Axis: a card that carries nothing has the id the builder gave it before this change (captured at base commit af6cfd27).
    # Bites on: the card id's identity changing for a card that carries nothing.
    sheet = build(*bundle(COLLECTOR))
    assert [c["id"] for c in sheet["cards"]] == ["k-42f04a278896", "k-3fb4fe9f3b5f"]
    assert [c["id"] for c in sheet["cards"]] == [c["id"] for c in load("expected-collector-2636.json")["cards"]]


def test_e12_a_missing_or_blank_carriedTitle_is_a_refusal_naming_it_when_a_finding_is_carried():
    # Axis: a carried finding needs the words' carriedTitle; its absence or a blank one is a refusal naming it, never a crash.
    # Bites on: the check skipped (the build then fails with a KeyError, not a refusal).
    records, advisor = small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": 2273}})
    for shown in (..., "", "   ", None):
        words = copy.deepcopy(WORDS)
        if shown is ...:
            del words["carriedTitle"]
        else:
            words["carriedTitle"] = shown
        with pytest.raises(pr_sheet.Refusal) as caught:
            pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), words)
        assert len(caught.value.problems) == 1 and "carriedTitle" in caught.value.problems[0], shown


def test_e12_a_sheet_that_carries_nothing_needs_no_carriedTitle():
    # Axis: the carriedTitle is read only when a finding is carried.
    # Bites on: the check made unconditional.
    words = copy.deepcopy(WORDS)
    del words["carriedTitle"]
    records, advisor = bundle(COLLECTOR)
    assert len(pr_sheet.build(records, advisor, words)["cards"]) == 2


def test_e13_an_input_that_uses_neither_feature_builds_the_bytes_the_base_built(tmp_path):
    # Axis: the command's output for an input with neither dashed numbers nor carried findings is byte for byte what the base commit (af6cfd27) built.
    # Bites on: any change to a card's section list, its id or its label for an integer number.
    out = tmp_path / "sheet.json"
    done = cli([FIXTURES / "record-small.json"], FIXTURES / "input-collector.json", out)
    assert done.returncode == 0, done.stderr
    assert out.read_bytes() == (FIXTURES / "expected-collector-2636.json").read_bytes()


def test_e14_the_page_shows_each_carried_finding_on_its_own_card_and_the_answers_unlock_merge():
    # Axis: the page shows the dashed number on the badge and each carried finding inside its own card, none in decided for you; answering the cards unlocks Merge.
    # Bites on: the carried section missing from the data (the cards would show nothing), or carried findings counted as cards that must be answered.
    sheet = build(*stack())
    page = _page(sheet, """
      const cards = elements["sheet-cards"].children.filter(isCard);
      const decided = part("pr-decided-for-you");
      const view = () => ({ label: verdictRow()[0].textContent, disabled: verdictRow()[0].disabled });
      const out = {
        cards: cards.map((card) => ({ id: card.id, badge: card.children.find((child) => hasClass(child, "sh-badge")).textContent, text: t.text(card) })),
        decided: decided ? t.text(decided) : null,
        before: view(),
      };
      cards.forEach((card) => t.click(t.buttons(card.id.replace("card-", ""))[0]));
      await t.tick();
      out.after = view();
      return out;
    """)
    result = page["result"]
    shown = {c["badge"]: c["text"] for c in result["cards"]}
    assert sorted(shown) == [kind_of("2273-1"), kind_of("2273-2")]
    for number, lines in STACK_LINES.items():
        mine, other = shown[kind_of(number)], shown[kind_of("2273-2" if number == "2273-1" else "2273-1")]
        for line in lines:
            assert line in mine and line not in other
        assert WORDS["carriedTitle"] in mine
    assert "The balance line reads as a promise" in result["decided"]
    assert not any(line in result["decided"] for lines in STACK_LINES.values() for line in lines)
    assert result["before"]["disabled"] is True and result["after"] == {"label": pr_sheet._fill(WORDS["mergeStackLabel"], number=sheet["prSheet"]["number"]), "disabled": False}
