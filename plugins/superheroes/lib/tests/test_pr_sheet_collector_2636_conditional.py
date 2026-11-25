from test_pr_sheet import COLLECTOR, build, bundle


def test_conditional_can_name_its_own_dashed_card():
    # Axis: a conditional naming the current dashed collector card is allowed.
    # Bites on: the dependency scan dropping the target number from the conditional.
    records, advisor = bundle(COLLECTOR)
    item = advisor["collectorItems"][0]
    item["number"] = "2273-1"
    reason = "If you pick a on card 2273-1, gift receipts keep the proposed wording."
    item["recommendation"]["reason"] = reason

    sheet = build(records, advisor)

    assert sheet["cards"][0]["recommendation"]["reason"] == reason
