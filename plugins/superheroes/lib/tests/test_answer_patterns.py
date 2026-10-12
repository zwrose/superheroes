"""Census of the answer buttons a PR sheet offers: every one belongs to one of the four answer patterns."""
import copy
import re

import pytest

import pr_sheet
from test_pr_sheet import BIG, STACK, bundle
from test_review_template import THEME, WORDS, _template_text
from test_review_template_pr import SAMPLES, _fill, _page

PW = WORDS["pr"]
DOC = (THEME / "review-template.md").read_text(encoding="utf-8")

# Every button inside every answer row on the page, with the part that holds the row.
COLLECT = r"""
const found = [];
for (const node of pageNodes()) {
  for (const row of t.all(node).filter((item) => hasClass(item, "answer-row"))) {
    found.push({ part: isCard(node) ? node.id.replace("card-", "") : node.id, labels: row.children.filter((child) => child.tagName === "button").map((button) => button.textContent) });
  }
}
return found;
"""


def _verdict_labels(sheet, words):
    pw = words["pr"]
    merge = _fill(pw["mergeStackLabel" if sheet["kind"] == "stack" else "mergeLabel"], number=sheet["prSheet"]["number"])
    labels = {merge, pw["notYetLabel"]}
    if "mergeLocked" in pw:
        labels.add(_fill(pw["mergeLocked"], merge=merge))
    return labels


# Bites on: an answer button on a PR sheet outside its card's option labels, the prAnswers labels, the merge verdict (locked or not) and Not yet; a card without options offering anything but Accept and Discuss; a card with options not ending in Something else.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_every_answer_button_is_one_of_the_four_patterns(kind):
    sheet = SAMPLES[kind]
    page = _page(sheet, COLLECT)
    cards = {card["id"]: card for card in sheet["cards"]}
    pick = set(WORDS["prAnswers"]["labels"].values())
    sign_off = _verdict_labels(sheet, WORDS)
    rows = page["result"]
    assert [row["part"] for row in rows] == [card["id"] for card in sheet["cards"]] + ["sheet-verdict"]
    for row in rows:
        allowed = sign_off if row["part"] == "sheet-verdict" else pick | {option["label"] for option in cards[row["part"]].get("options", [])}
        outside = [label for label in row["labels"] if label not in allowed]
        assert outside == [], "%s offers %s outside the four answer patterns" % (row["part"], outside)
        if row["part"] == "sheet-verdict":
            assert len(row["labels"]) == 2 and row["labels"][1] == PW["notYetLabel"]
            continue
        options = [option["label"] for option in cards[row["part"]].get("options", [])]
        expected = options + ["Something else"] if options else ["Accept", "Discuss"]
        assert row["labels"] == expected, row["part"]


# Bites on: a new answer word added to prAnswers, a second place in the template that creates an answer row, a default leftover option outside the words file's leftoverOptions.
def test_the_answer_words_and_the_one_place_that_makes_buttons():
    assert WORDS["prAnswers"]["labels"] == {"accept": "Accept", "discuss": "Discuss", "something-else": "Something else"}
    assert len(re.findall(r'className\s*=\s*"answer-row"', _template_text())) == 1


@pytest.mark.parametrize("case", [BIG, STACK], ids=["pr", "stack"])
def test_default_leftover_options_are_the_words_files(case):
    records, advisor = bundle(case)
    for key in ("leftovers", "items", "closesSpec"):
        advisor.pop(key, None)
    sheet = pr_sheet.build(copy.deepcopy(records), advisor, PW)
    leftovers = [card for card in sheet["cards"] if card["callKind"].startswith(PW["leftoverKind"])]
    assert leftovers, "the fixture has no leftover to carry default options"
    for card in leftovers:
        assert card["options"] == PW["leftoverOptions"], card["id"]


# Bites on: a word the doc quotes for PR sheets reworded in sheet-words.json while the doc still carries the old one.
@pytest.mark.parametrize("key", ["nothingToAccept", "craftHeading", "decidedHeading", "reviewHeading", "prsHeading", "acceptingHeading", "changedHeading"])
def test_the_doc_quotes_the_words_files_words(key):
    assert PW[key] in DOC, "review-template.md does not quote pr.%s: %r" % (key, PW[key])
