"""Guards for issue 2481: a PR-sheet card never depends on another question's answer.

The builder refuses, with the token dependent-question, a card whose option text (label, consequence) or recommendation text (text,
reason) conditions on, or names, another question; it still builds every healthy card. Row ids carry the guarded element they bite
on (g01 to g12), so a bite-proof run selects one element with -k.
"""
import json

import pytest

from test_pr_sheet import BIG, COLLECTOR, POINTER_PROBLEM, POINTER_TITLE, build, bundle, problems_of, with_pointer_item

LINE = ("dependent-question: {where}: card {question!r} {field} depends on another question ({found!r}); a question must be "
        "answerable on its own: ask the two as one card whose options name each combination, or hold this card until the other "
        "question is ruled and ask it then")

C1435 = ("collectorItems 1435", "Should the receipt page keep the old wording for gift orders?")
C1501 = ("collectorItems 1501", "Should the receipt page show the order total in the thank-you line?")
ITEM = ("items retry-window", "Retry for ten minutes after a failure")


def line(card, field, found):
    return LINE.format(where=card[0], question=card[1], field=field, found=found)


def option_text(card_at, option_at, key, text):
    def edit(advisor):
        advisor["collectorItems"][card_at]["options"][option_at][key] = text
    return edit


def recommendation_text(card_at, key, text):
    def edit(advisor):
        advisor["collectorItems"][card_at]["recommendation"][key] = text
    return edit


def context_text(card_at, text):
    def edit(advisor):
        advisor["collectorItems"][card_at]["context"] = text
    return edit


def item_label(text):
    def edit(advisor):
        advisor["items"][0]["options"][0]["label"] = text
    return edit


def collector_cards(sheet):
    return [c for c in sheet["cards"] if c["id"].startswith("k-")]


# Each row's text matches exactly one pattern alternative; the expected line names the matched text.
REFUSED = [
    pytest.param(option_text(0, 0, "consequence", "Applies only if you pick b for item 12."), C1435, "option a", "only if you pick b for item",
                 id="g04-g02-d1-only-if-you-pick-for-item"),
    pytest.param(option_text(0, 1, "consequence", "Costs less if you chose a for the other card."), C1435, "option b", "if you chose a for the other",
                 id="g04-d1-if-you-chose-for-the-other"),
    pytest.param(option_text(0, 0, "consequence", "Applies only if you pick b for questions 12 and 13."), C1435, "option a",
                 "only if you pick b for questions", id="g04-d1-a-plural-question-target"),
    pytest.param(option_text(0, 0, "consequence", "Costs less if you chose a for cards 3 and 4."), C1435, "option a",
                 "if you chose a for cards", id="g04-d1-a-plural-card-target"),
    pytest.param(option_text(0, 0, "consequence", "Holds only if you pick b on decisions 7 and 8."), C1435, "option a",
                 "only if you pick b on decisions", id="g04-d1-a-plural-decision-target"),
    pytest.param(option_text(0, 0, "consequence", "Ships only if you pick a for items 5 and 6."), C1435, "option a",
                 "only if you pick a for items", id="g04-d1-a-plural-item-target"),
    pytest.param(option_text(0, 0, "consequence", "Cost depends on your answer to the storage question."), C1435, "option a", "depends on your answer",
                 id="g05-d2-depends-on-your-answer"),
    pytest.param(option_text(0, 0, "consequence", "Use the same choice as the receipt card."), C1435, "option a", "same choice as",
                 id="g06-d3-same-choice-as"),
    pytest.param(option_text(0, 2, "consequence", "Whichever option you pick on the gift question wins."), C1435, "option c", "Whichever option you pick on",
                 id="g06-d3-whichever-option-you-pick-on"),
    pytest.param(option_text(0, 0, "consequence", "Do this as decision item 12 says."), C1435, "option a", "decision item 12",
                 id="g07-d4-decision-item-12"),
    pytest.param(option_text(0, 0, "consequence", "Matches card 12 on this sheet."), C1435, "option a", "card 12",
                 id="g07-d4-card-12"),
    pytest.param(option_text(0, 0, "consequence", "Hold it when item 12 is ruled."), C1435, "option a", "when item 12 is",
                 id="g07-d4-when-item-12-is"),
    pytest.param(option_text(0, 0, "consequence", "Answered with collector #12."), C1435, "option a", "collector #12",
                 id="g07-d4-collector-hash-12"),
    pytest.param(option_text(0, 0, "consequence", "Ship b when 1435-1 is fixed."), C1435, "option a", "1435-1",
                 id="g08-d5-bare-dashed-reference"),
    pytest.param(option_text(0, 0, "consequence", "Ask the other question first."), C1435, "option a", "the other question",
                 id="g09-d6-the-other-question"),
    pytest.param(option_text(0, 0, "consequence", "Settle it as the card above says."), C1435, "option a", "card above",
                 id="g09-d6-card-above"),
    pytest.param(option_text(0, 0, "consequence", "Follow 1501: b"), C1435, "option a", "1501",
                 id="g10-d7-another-collector-number"),
    # The same texts in other fields: the label of an items entry's option, and the recommendation's text and reason.
    pytest.param(option_text(0, 0, "label", "Keep it, as decision item 12 says"), C1435, "option a", "decision item 12",
                 id="g02-g07-d4-in-a-collector-option-label"),
    pytest.param(recommendation_text(0, "reason", "Cost depends on your answer to the storage question."), C1435, "recommendation", "depends on your answer",
                 id="g03-g05-d2-in-the-recommendation-reason"),
    pytest.param(recommendation_text(0, "reason", "Matches decision item 12."), C1435, "recommendation", "decision item 12",
                 id="g03-g07-d4-in-the-recommendation-reason"),
    pytest.param(recommendation_text(0, "text", "Follow 1501: b"), C1435, "recommendation", "1501",
                 id="g03-g10-d7-in-the-recommendation-text"),
    pytest.param(recommendation_text(1, "text", "see the previous card"), C1501, "recommendation", "the previous card",
                 id="g03-g09-d6-in-the-recommendation-text-of-the-other-card"),
]


@pytest.mark.parametrize("edit, card, field, found", REFUSED)
def test_a_card_depending_on_another_question_is_refused(edit, card, field, found):
    # Axis: option or recommendation text that conditions on, or names, another question is refused, naming the card's place, its question, the field and the matched text.
    # Bites on: the refusal not raised, a field left out of the scan, or any one of the pattern alternatives missing.
    records, advisor = bundle(COLLECTOR)
    edit(advisor)
    assert problems_of(records, advisor) == [line(card, field, found)]


@pytest.mark.parametrize("text, found", [
    pytest.param("Ten minutes, as decision item 12 says", "decision item 12", id="g02-g07-label"),
    pytest.param("Ten minutes, depending on your answer elsewhere", "depending on your answer", id="g02-g05-label"),
])
def test_an_items_entry_option_label_is_scanned(text, found):
    # Axis: the label of an option on an items entry is scanned, not only a collector card's.
    # Bites on: option labels left out of the scan, or items entries left out.
    records, advisor = bundle(BIG)
    item_label(text)(advisor)
    assert problems_of(records, advisor) == [line(ITEM, "option ten-minutes", found)]


def test_g01_the_field_case_from_the_issue_is_refused():
    # Axis: the recommendation of a collector card that conditions on another collector item's ruling is refused.
    # Bites on: the dependent-question problems not reaching the Refusal, or the recommendation text left out of the scan.
    records, advisor = bundle(COLLECTOR)
    recommendation_text(0, "text", "a if 1435-1 is fix-before-merge, otherwise b")(advisor)
    assert problems_of(records, advisor) == [line(C1435, "recommendation", "1435-1")]


def test_g01_a_pointer_and_a_dependent_question_are_both_listed_pointer_first():
    # Axis: one refusal carries both lists, the pointer problems first.
    # Bites on: the dependent-question problems dropped when a pointer problem is raised, or listed before the pointers.
    records, advisor = bundle(BIG)
    with_pointer_item("collector #1501")(advisor)
    item_label("Ten minutes, as decision item 12 says")(advisor)
    assert problems_of(records, advisor) == [POINTER_PROBLEM.format(title=POINTER_TITLE, found="collector #1501"),
                                             line(ITEM, "option ten-minutes", "decision item 12")]


def test_the_problems_come_in_card_field_and_match_order():
    # Axis: problems are listed by card, then option (label before consequence), then the recommendation (text before reason), then match order, D7 after the pattern.
    # Bites on: a different order, or one problem for a text holding two matches.
    records, advisor = bundle(COLLECTOR)
    option_text(0, 0, "label", "Wait for decision item 12")(advisor)
    option_text(0, 0, "consequence", "Ask the other question first. Same choice as the receipt card")(advisor)
    option_text(0, 1, "consequence", "Same choice as 1501")(advisor)
    recommendation_text(0, "text", "see the previous card")(advisor)
    recommendation_text(0, "reason", "It depends on the ruling")(advisor)
    option_text(1, 2, "consequence", "Follow 1435: b")(advisor)
    assert problems_of(records, advisor) == [
        line(C1435, "option a", "decision item 12"),
        line(C1435, "option a", "the other question"),
        line(C1435, "option a", "Same choice as"),
        line(C1435, "option b", "Same choice as"),
        line(C1435, "option b", "1501"),
        line(C1435, "recommendation", "the previous card"),
        line(C1435, "recommendation", "depends on the ruling"),
        line(C1501, "option c", "1435"),
    ]


def test_a_leftover_card_with_the_three_option_object_has_its_consequences_scanned():
    # Axis: a leftover whose options are the three-option object (labels from the words file, consequences from the advisor) is scanned.
    # Bites on: leftover cards left out of the scan.
    records, advisor = bundle(BIG)
    advisor["leftovers"]["F7"]["options"]["keep-it"] = "Customers hear nothing, as decision item 12 says."
    clean = next(c for c in build(*bundle(BIG))["cards"] if any(o["id"] == "keep-it" for o in c["options"]))
    assert problems_of(records, advisor) == [line(("leftovers F7", clean["question"]), "option keep-it", "decision item 12")]


def test_a_card_with_no_recommendation_key_is_scanned_for_its_options_only():
    # Axis: a card that carries no recommendation key is scanned over its options and builds when they are clean.
    # Bites on: a missing recommendation key read as an error, or the options left unscanned.
    records, advisor = bundle(BIG)
    del advisor["items"][0]["recommendation"]
    assert any(c["question"] == ITEM[1] for c in build(records, advisor)["cards"])
    advisor["items"][0]["options"][1]["consequence"] = "Ask the other question first."
    assert problems_of(records, advisor) == [line(ITEM, "option one-minute", "the other question")]


def test_a_recommendation_with_no_option_id_is_still_scanned():
    # Axis: a recommendation without optionId is scanned the same.
    # Bites on: the scan keyed on optionId.
    records, advisor = bundle(BIG)
    advisor["items"][0]["recommendation"] = {"text": "Ask the other question first", "reason": "Most card declines clear within that time."}
    assert problems_of(records, advisor) == [line(ITEM, "recommendation", "the other question")]


def test_a_card_with_no_options_and_no_recommendation_is_never_refused_for_its_context():
    # Axis: an option-less card with no recommendation has nothing scanned, whatever its context says.
    # Bites on: the scan reading context blocks or the question of a card with no options.
    records, advisor = bundle(BIG)
    advisor["items"].append({"id": "accepting", "kind": "What you're accepting", "title": "Disclosures", "options": "none",
                             "ifLeft": "Only if you pick b on the other card, the retry stays."})
    assert any(c["question"] == "Disclosures" for c in build(records, advisor)["cards"])


# Each accepted row builds, and its text is on the card.
ACCEPTED = [
    pytest.param("consequence", "PR 2465 already shipped this fix; this keeps it", id="ok-a-pr-named-without-conditioning"),
    pytest.param("consequence", "same fix as #2465", id="ok-a-pr-written-with-a-hash"),
    pytest.param("consequence", "Revisit on 2026-11-14", id="ok-a-date"),
    pytest.param("consequence", "Trim it to 60-160 lines", id="ok-an-ascending-range"),
    pytest.param("consequence", "Extra storage costs apply only if you pick this option", id="ok-only-if-you-pick-this-option"),
    pytest.param("consequence", "if you pick a to ship now, CI cost doubles", id="ok-if-you-pick-a-to-ship-now"),
    pytest.param("consequence", "About 15010 receipts a day, 21501 on sale days", id="ok-a-longer-number"),
    pytest.param("consequence", "If you choose a for itemized receipts, buyers see the new wording.", id="ok-a-target-word-inside-a-longer-word"),
    pytest.param("consequence", "The receipt keeps SKU1501.", id="ok-another-collector-number-inside-an-identifier"),
    pytest.param("consequence", "Batch 1501b ships with the receipt.", id="ok-another-collector-number-before-a-letter"),
    pytest.param("recommendation", "For collector item 1435, choose b", id="g12-ok-the-cards-own-number"),
    pytest.param("consequence", "Card 1435 keeps its own wording", id="g12-ok-the-cards-own-number-after-card"),
    pytest.param("consequence", "PR 1501 shipped the same fix", id="g11-ok-another-collector-number-written-as-a-pr"),
    pytest.param("consequence", "PR #1501 shipped the same fix", id="g11-ok-another-collector-number-written-as-a-pr-hash"),
    pytest.param("consequence", "Same fix as #1501", id="g11-ok-another-collector-number-with-a-hash"),
    pytest.param("context", "Only if you pick b on the other card; this is decision item 12 and depends on your answer there.",
                 id="ok-context-is-never-scanned"),
]


@pytest.mark.parametrize("field, text", ACCEPTED)
def test_a_healthy_card_still_builds(field, text):
    # Axis: a card that mentions another PR, names its own collector number, writes another collector number as a PR, or holds a date or range builds.
    # Bites on: a pattern wide enough to refuse healthy text, or the PR and own-number exemptions missing.
    records, advisor = bundle(COLLECTOR)
    edit = {"consequence": option_text(0, 0, "consequence", text), "recommendation": recommendation_text(0, "text", text),
            "context": context_text(0, text)}[field]
    edit(advisor)
    cards = collector_cards(build(records, advisor))
    assert len(cards) == 2
    assert text in json.dumps(cards[0], ensure_ascii=False)


def test_a_question_title_and_context_may_mention_an_earlier_decision():
    # Axis: the question title and the context blocks are never scanned.
    # Bites on: the scan reading the question or a context block of a card with options.
    records, advisor = bundle(COLLECTOR)
    advisor["collectorItems"][0]["title"] = "After decision item 12, should the receipt keep the old wording?"
    for key in ("why", "ifLeft"):
        advisor["collectorItems"][0][key] = "Only if you pick b on the other card does this matter; depending on your answer to 1501-1."
    cards = collector_cards(build(records, advisor))
    assert cards[0]["question"].startswith("After decision item 12")


def test_a_combined_question_whose_options_name_each_combination_builds():
    # Axis: one card whose options name each combination of two decisions is the shape the refusal asks for, and builds.
    # Bites on: the scan refusing option labels that name combinations.
    records, advisor = bundle(COLLECTOR)
    for at, label in enumerate(("Ship both now", "Ship the receipt fix, hold gift wording", "Hold both")):
        option_text(0, at, "label", label)(advisor)
    labels = [o["label"] for o in collector_cards(build(records, advisor))[0]["options"]]
    assert labels == ["a. Ship both now", "b. Ship the receipt fix, hold gift wording", "c. Hold both"]


def test_a_sheet_with_no_collector_items_reads_no_collector_number():
    # Axis: with no collector item on the sheet the other-number check has no numbers to read.
    # Bites on: an empty number set matching everything, or failing.
    records, advisor = bundle(BIG)
    advisor["items"][0]["options"][0]["consequence"] = "About 1501 retries a day"
    assert any(c["question"] == ITEM[1] for c in build(records, advisor)["cards"])


def test_a_sheet_whose_only_collector_item_mentions_its_own_number_builds():
    # Axis: the only collector item's own number is not another question, and a number no collector item holds is not read.
    # Bites on: the own number counted as another card's.
    records, advisor = bundle(COLLECTOR)
    del advisor["collectorItems"][1]
    option_text(0, 0, "consequence", "Ship 1435 now; 1501 is not on this sheet")(advisor)
    assert len(collector_cards(build(records, advisor))) == 1


@pytest.mark.parametrize("text, found", [
    pytest.param("Follow 1435-1 here", "1435-1", id="a-dashed-form-of-the-cards-own-number"),
    pytest.param("Follow collector item 1435-1 here", "collector item 1435-1", id="a-dashed-form-after-collector-item"),
])
def test_g12_a_dashed_form_of_the_cards_own_number_is_always_refused(text, found):
    # Axis: collector numbers are whole integers, so a dashed reference is another question even when it starts with the card's own number.
    # Bites on: the own-number exemption applied to a dashed form.
    records, advisor = bundle(COLLECTOR)
    option_text(0, 0, "consequence", text)(advisor)
    assert problems_of(records, advisor) == [line(C1435, "option a", found)]


def test_g13_an_option_less_card_text_no_pointer_matches_is_still_a_dependent_question():
    # Axis: on an option-less card the recommendation is scanned, and a dependent match no pointer match overlaps is reported alone.
    # Bites on: the recommendation of an option-less card left out of the scan, or the overlap skip applied to every match.
    records, advisor = bundle(BIG)
    with_pointer_item("Nothing else.", recommendation={"text": "Accept only if you pick b for item 12", "reason": "It is small."})(advisor)
    assert problems_of(records, advisor) == [line(("items accepting", POINTER_TITLE), "recommendation", "only if you pick b for item")]


def test_g13_text_the_pointer_check_refuses_is_reported_by_it_alone():
    # Axis: on an option-less card a dependent match overlapping a pointer match is left to the pointer problem.
    # Bites on: the overlap skip missing, which adds a dependent-question problem beside the pointer problem.
    records, advisor = bundle(BIG)
    with_pointer_item("Nothing else.", recommendation={"text": "Accept collector item 1435", "reason": "It is small."})(advisor)
    assert problems_of(records, advisor) == [POINTER_PROBLEM.format(title=POINTER_TITLE, found="collector item 1435")]


def test_g13_a_dependent_match_beside_a_pointer_match_is_still_reported_after_it():
    # Axis: the skip drops only the overlapping match; a separate dependent match in the same text is reported, pointer problems first.
    # Bites on: the overlap skip dropping every dependent match of a text that holds a pointer match.
    records, advisor = bundle(BIG)
    with_pointer_item("Nothing else.", recommendation={"text": "Accept", "reason": "Covered by list item 1435, the other question."})(advisor)
    assert problems_of(records, advisor) == [POINTER_PROBLEM.format(title=POINTER_TITLE, found="list item 1435"),
                                             line(("items accepting", POINTER_TITLE), "recommendation", "the other question")]


def test_the_pointer_refusal_is_unchanged():
    # Axis: an option-less card that points to a list item gets exactly the pointer problem and nothing else.
    # Bites on: the pointer problems changed or joined by a dependent-question line.
    records, advisor = bundle(BIG)
    with_pointer_item("Whether to change that is decision item 1435.")(advisor)
    assert problems_of(records, advisor) == [POINTER_PROBLEM.format(title=POINTER_TITLE, found="decision item 1435")]
