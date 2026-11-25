import pytest

from pr_sheet import Refusal
from test_pr_sheet import build
from test_pr_sheet_carry_any_card_2636 import ITEM, with_item
from test_pr_sheet_collector_2636 import GIFT, small


def test_an_optionless_carrier_cannot_send_the_owner_to_a_dashed_list_item():
    # Axis: an advisor-written pointer to an off-sheet dashed list item is refused on an optionless carrier.
    # Bites on: the item-on-your-list pattern recognizing only plain numbers.
    leftovers = {GIFT["findingKey"]: {"carriedBy": {"item": ITEM["id"]}}}
    records, advisor = with_item(*small(("2273-2", 1501), [GIFT], leftovers))
    advisor["items"][0]["ifLeft"] = "See item 2273-1 on your list for the wording."
    with pytest.raises(Refusal) as caught:
        build(records, advisor)
    assert any(
        problem.startswith(f"items {ITEM['id']}: ") and "item 2273-1 on your list" in problem
        for problem in caught.value.problems
    )
