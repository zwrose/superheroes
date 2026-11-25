import pytest

from test_pr_sheet import build
from test_pr_sheet_carry_any_card_2636 import ITEM, by, carried_section, item_card, leftover_card, with_item
from test_pr_sheet_collector_2636 import CALL, GIFT, TOTAL, small


@pytest.mark.parametrize("carrier", ["item", "finding"])
def test_an_optionless_carrier_shows_a_finding_title_that_mentions_a_list_item(carrier):
    # Axis: a carried title mentioning a past list decision remains visible on an optionless carrier.
    # Bites on: scanning an appended finding title as an advisor instruction to go to the list.
    gift = {**GIFT, "title": "Decision item 9191 records the gift receipt wording change"}
    if carrier == "item":
        leftovers = {gift["findingKey"]: {"carriedBy": {"item": ITEM["id"]}}}
        sheet = build(*with_item(*small(findings=[gift], leftovers=leftovers)))
        card = item_card(sheet)
    else:
        holder = {**TOTAL, "title": ITEM["title"]}
        leftovers = {holder["findingKey"]: CALL, gift["findingKey"]: by(holder)}
        sheet = build(*small(findings=[holder, gift], leftovers=leftovers))
        card = leftover_card(sheet, holder)
    assert card["context"][-1] == carried_section(gift["title"])
