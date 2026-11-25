from test_pr_sheet import COLLECTOR, build, bundle


def test_a_condition_can_name_the_cards_own_dashed_collector_item():
    # Axis: an option can refer to its own numbered collector item in a conditional phrase.
    # Bites on: the dependency scan stopping at 'collector' and treating the self-reference as another question.
    records, advisor = bundle(COLLECTOR)
    item = advisor['collectorItems'][0]
    item['number'] = '2273-1'
    text = 'If you pick a on collector item 2273-1, gift buyers see the new wording.'
    item['options'][0]['consequence'] = text

    sheet = build(records, advisor)
    card = next(card for card in sheet['cards'] if card['question'] == item['title'])
    assert card['options'][0]['consequence'] == text
