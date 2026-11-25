"""Guards for issue 2636, the carry widening: a left-for-owner finding may be carried by any card on the sheet that asks its decision.

A leftovers value {"carriedBy": <reference>} names its carrier by a list-item number (a collectorItems card), {"item": "<id>"} (an Accept or
option card from items) or {"finding": "<leftovers key>"} (the card of another left-for-owner finding). The finding is then no card and no
decided-for-you entry; the carrying card lists it as its last section. A carrier is never itself carried.
Row ids and test names carry the guarded element (f01 to f10, and f12), so a bite-proof run selects one element with -k. Row f11 is the
existing byte-identity test, test_e13 in test_pr_sheet_collector_2636.py: it compares an input that uses none of these shapes with the base
capture, and has no test here. The pointer check's carried-title row is the break-it test in test_pr_sheet_carried_title_pointer_2636.py.
"""
import pytest

import pr_sheet
from test_pr_sheet import WORDS, build, leftover_cards, problems_of
from test_pr_sheet_collector_2636 import CALL, DETERMINATION, FONT, GIFT, GIFT_TWIN, TOTAL, small

ITEM = {"id": "gift-wording", "kind": "Behavior change", "title": "Gift receipts keep one wording",
        "ifLeft": "Gift receipts ship with the new wording.", "options": "none"}


def by(finding):
    """The carriedBy value that names a finding's card."""
    return {"carriedBy": {"finding": finding["findingKey"]}}


def carried_section(*titles):
    return {"title": WORDS["carriedTitle"], "blocks": [{"bullets": list(titles)}]}


def leftover_card(sheet, finding):
    return next(c for c in leftover_cards(sheet) if c["question"] == finding["title"])


def item_card(sheet):
    return next(c for c in sheet["cards"] if c["question"] == ITEM["title"])


def with_item(records, advisor):
    advisor["items"] = [dict(ITEM)]
    return records, advisor


def titles_in_decided(sheet):
    return [e["title"] for e in sheet["prSheet"].get("decidedForYou", [])]


def test_f01_a_finding_is_carried_by_another_findings_leftover_card():
    # Axis: a {"finding": key} reference puts the finding on that finding's leftover card as its last section; the carried finding is no
    # card of its own and no decided-for-you entry, so the sheet has ONE leftover card.
    # Bites on: the leftover card builder ignoring what is carried on it (the finding then vanishes from the sheet), or the carried finding
    # falling through to a card of its own. See bite-proof record i2636_collector_cards (F1).
    sheet = build(*small((2273, 1501), [TOTAL, GIFT], {TOTAL["findingKey"]: CALL, GIFT["findingKey"]: by(TOTAL)}))
    assert [c["question"] for c in leftover_cards(sheet)] == [TOTAL["title"]]
    assert leftover_card(sheet, TOTAL)["context"][-1] == carried_section(GIFT["title"])
    assert [s["title"] for s in leftover_card(sheet, TOTAL)["context"]][:3] == [WORDS["whyYours"], WORDS["whatHappened"], WORDS["ifLeft"]]
    assert all(c["question"] != GIFT["title"] for c in sheet["cards"])
    assert GIFT["title"] not in titles_in_decided(sheet)


def test_f02_a_finding_is_carried_by_an_accept_item_card():
    # Axis: an {"item": id} reference puts the finding on that items card as its last section (after If left); the finding has no leftover
    # card of its own.
    # Bites on: the item card builder ignoring what is carried on it. See bite-proof record i2636_collector_cards (F2).
    sheet = build(*with_item(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": {"item": ITEM["id"]}}})))
    assert item_card(sheet)["context"] == [{"title": WORDS["ifLeft"], "blocks": [{"paragraph": ITEM["ifLeft"]}]}, carried_section(GIFT["title"])]
    assert leftover_cards(sheet) == [] and all(c["question"] != GIFT["title"] for c in sheet["cards"])
    assert titles_in_decided(sheet) == []


def test_f02_the_item_cards_id_changes_with_the_finding_it_carries():
    # Axis: an item card's id changes with the finding it carries (its key, not only its title) and is stable across builds, so a republish
    # whose item now carries a different finding of the same title never reuses the owner's saved answer.
    # Bites on: the item card's identity left as the item id alone when it carries. See bite-proof record i2636_collector_cards (F2).
    def sheet_carrying(f):
        return build(*with_item(*small((2273, 1501), [f], {f["findingKey"]: {"carriedBy": {"item": ITEM["id"]}}})))
    gift, twin, again = sheet_carrying(GIFT), sheet_carrying(GIFT_TWIN), sheet_carrying(GIFT)
    assert item_card(gift)["context"] == item_card(twin)["context"]
    assert item_card(gift)["id"] != item_card(twin)["id"]
    assert item_card(gift)["id"] == item_card(again)["id"]


def test_f03_a_finding_reference_naming_no_finding_is_refused():
    # Axis: {"finding": key} must name a left-for-owner finding on this sheet; a key that names none is refused, never dropped.
    # Bites on: the unresolved key accepted, so the carried finding is listed on no card. See bite-proof record i2636_collector_cards (F3).
    records, advisor = small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": {"finding": "shop/no-such-finding"}}})
    assert problems_of(records, advisor) == [f"leftovers {GIFT['findingKey']}: carriedBy finding shop/no-such-finding names no card on this sheet"]


def test_f12_a_carrying_cards_own_text_is_still_read_by_the_pointer_check():
    # Axis: leaving the copied carried section out of the list-item pointer check never leaves out the carrier's own text: an Accept item
    # that carries a finding and whose own If left sends the owner to a list item is still refused.
    # Bites on: the whole context of a carrying card skipped by the pointer check. The carried title itself is the break-it test in
    # test_pr_sheet_carried_title_pointer_2636.py. See bite-proof record i2636_collector_cards (F12).
    records, advisor = with_item(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": {"item": ITEM["id"]}}}))
    advisor["items"][0]["ifLeft"] = "See decision item 9191 for the wording."
    problems = problems_of(records, advisor)
    assert len(problems) == 1 and problems[0].startswith(f"items {ITEM['id']}: card {ITEM['title']!r} sends the owner to a list item ('decision item 9191')")


def test_f03_a_finding_reference_naming_two_findings_is_refused():
    # Axis: {"finding": key} must name exactly one left-for-owner finding; a reviewer id two findings share is refused, never resolved to the
    # first of them, even when each of the two has its own card by its findingKey.
    # Bites on: the target count checked only for zero, so the finding is listed under whichever matching card comes first in the record.
    # See bite-proof record i2636_collector_cards (F3).
    total, font = {**TOTAL, "id": "A2"}, {**FONT, "id": "A2"}
    records, advisor = small((2273, 1501), [total, font, GIFT],
                             {total["findingKey"]: CALL, font["findingKey"]: CALL, GIFT["findingKey"]: {"carriedBy": {"finding": "A2"}}})
    assert problems_of(records, advisor) == [
        f"leftovers {GIFT['findingKey']}: carriedBy finding A2 names no card on this sheet; the key names 2 findings, use a findingKey"]


def test_f04_a_finding_reference_naming_a_craft_determined_finding_is_refused():
    # Axis: the finding named must have a card of its own; a craft-determined one is a decided-for-you entry, no card, so it cannot carry.
    # Bites on: only existence checked, so a finding is carried by a finding that has no card. See bite-proof record i2636_collector_cards (F4).
    records, advisor = small((2273, 1501), [GIFT, TOTAL], {GIFT["findingKey"]: by(TOTAL)}, {TOTAL["findingKey"]: DETERMINATION})
    assert problems_of(records, advisor) == [f"leftovers {GIFT['findingKey']}: carriedBy finding {TOTAL['findingKey']} names no card on this sheet"]


def test_f05_an_item_reference_naming_no_item_is_refused():
    # Axis: {"item": id} must name an items entry on this input; an id that is no item is refused.
    # Bites on: the item id not looked up, so the carried finding is listed on no card. See bite-proof record i2636_collector_cards (F5).
    records, advisor = with_item(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": {"item": "no-such-item"}}}))
    assert problems_of(records, advisor) == [f"leftovers {GIFT['findingKey']}: carriedBy item no-such-item names no card on this sheet"]


@pytest.mark.parametrize("entry, target", [(GIFT["findingKey"], GIFT["findingKey"]), (GIFT["findingKey"], GIFT["id"]), (GIFT["id"], GIFT["findingKey"])],
                         ids=["f06-key-by-key", "f06-key-by-id", "f06-id-by-key"])
def test_f06_a_finding_carrying_itself_is_refused(entry, target):
    # Axis: a finding cannot carry itself; the target is compared by the finding it resolves to, so its findingKey and its id are one finding.
    # Bites on: the self check dropped (the finding is then refused as carried by a carried finding, or lost), or the target compared by the
    # key as written, so the id of the same finding passes. See bite-proof record i2636_collector_cards (F6).
    records, advisor = small((2273, 1501), [GIFT], {entry: {"carriedBy": {"finding": target}}})
    assert problems_of(records, advisor) == [f"leftovers {entry}: carriedBy names this finding itself; a finding cannot carry itself"]


def test_f07_a_chain_is_refused():
    # Axis: a carrier is never itself carried: GIFT carried by TOTAL while TOTAL is carried by a list-item card is refused, naming GIFT's key.
    # Bites on: the chain check dropped, so GIFT is listed under a card that is itself no card. See bite-proof record i2636_collector_cards (F7).
    records, advisor = small((2273, 1501), [GIFT, TOTAL], {TOTAL["findingKey"]: {"carriedBy": 2273}, GIFT["findingKey"]: by(TOTAL)})
    assert problems_of(records, advisor) == [
        f"leftovers {GIFT['findingKey']}: carriedBy finding {TOTAL['findingKey']} is itself carried; carry both on the card that carries it"]


@pytest.mark.parametrize("ref", [{"item": "x", "finding": "y"}, {"card": "x"}, {}, {"item": ""}, {"finding": 5}, {"item": None}],
                         ids=["f08-two-keys", "f08-unknown-key", "f08-empty", "f08-blank-id", "f08-non-string-key", "f08-null-id"])
def test_f08_a_malformed_reference_is_refused(ref):
    # Axis: a carriedBy object has exactly one key, item or finding, whose value is a non-empty string; any other object is refused.
    # Bites on: a second key or an unknown key accepted, or a blank or non-string value taken for a name.
    # See bite-proof record i2636_collector_cards (F8).
    records, advisor = with_item(*small((2273, 1501), [GIFT], {GIFT["findingKey"]: {"carriedBy": ref}}))
    problems = problems_of(records, advisor)
    assert len(problems) == 1 and problems[0].startswith(f"leftovers {GIFT['findingKey']}: carriedBy must be a list-item number")


def test_f09_a_finding_carried_by_a_later_findings_card_lands():
    # Axis: every carried finding is collected before any card is built, so one carried by a finding that comes later in the record lands on
    # that card, with the lines in record order.
    # Bites on: the carried lines collected as the cards are built, so a carrier that comes later in the record has its lines dropped.
    # See bite-proof record i2636_collector_cards (F9).
    sheet = build(*small((2273, 1501), [GIFT, FONT, TOTAL], {GIFT["findingKey"]: by(TOTAL), FONT["findingKey"]: by(TOTAL), TOTAL["findingKey"]: CALL}))
    assert [c["question"] for c in leftover_cards(sheet)] == [TOTAL["title"]]
    assert leftover_card(sheet, TOTAL)["context"][-1] == carried_section(GIFT["title"], FONT["title"])


def test_f10_the_carrying_cards_id_changes_with_what_it_carries_and_a_card_carrying_nothing_keeps_its_id():
    # Axis: a leftover card's id changes with what it carries (the finding's key, not only its title) and is stable across builds; a card that
    # carries nothing keeps the id of the base formula, the finding's key as its identity, however the other cards on the sheet are carried.
    # Bites on: the id left as the finding's key alone for a card that carries, or the carried identity added to a card that carries nothing.
    # See bite-proof record i2636_collector_cards (F10).
    gift = build(*small((2273, 1501), [TOTAL, GIFT], {TOTAL["findingKey"]: CALL, GIFT["findingKey"]: by(TOTAL)}))
    twin = build(*small((2273, 1501), [TOTAL, GIFT_TWIN], {TOTAL["findingKey"]: CALL, GIFT_TWIN["findingKey"]: by(TOTAL)}))
    again = build(*small((2273, 1501), [TOTAL, GIFT], {TOTAL["findingKey"]: CALL, GIFT["findingKey"]: by(TOTAL)}))
    assert leftover_card(gift, TOTAL)["id"] != leftover_card(twin, TOTAL)["id"]
    assert leftover_card(gift, TOTAL)["id"] == leftover_card(again, TOTAL)["id"]
    # The same input with nothing carried on TOTAL (GIFT carried by FONT instead): TOTAL's card is the one the base formula gives.
    plain = build(*small((2273, 1501), [TOTAL, GIFT, FONT], {TOTAL["findingKey"]: CALL, GIFT["findingKey"]: by(FONT), FONT["findingKey"]: CALL}))
    card = {k: v for k, v in leftover_card(plain, TOTAL).items() if k != "id"}
    assert leftover_card(plain, TOTAL)["id"] == pr_sheet.card_id("f-", 211, TOTAL["findingKey"], card) != leftover_card(gift, TOTAL)["id"]
    assert [s["title"] for s in leftover_card(plain, TOTAL)["context"]] == [WORDS["whyYours"], WORDS["whatHappened"], WORDS["ifLeft"]]
    assert leftover_card(plain, FONT)["context"][-1] == carried_section(GIFT["title"])
