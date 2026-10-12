"""Census of the answer buttons a PR sheet offers: every one belongs to one of the four answer patterns."""
import copy
import re

import pytest

import pr_sheet
from test_pr_sheet import BIG, STACK, bundle
from test_review_template import WORDS, _template_text
from test_review_template_pr import SAMPLES, _fill, _page

PW = WORDS["pr"]

# Every button inside every answer row on the page, with the part that holds the row: a card, the verdict, or a walk stop (which holds two rows).
COLLECT = r"""
const found = [];
const collect = (part, node) => {
  for (const row of t.all(node).filter((item) => hasClass(item, "answer-row"))) {
    found.push({ part: part, labels: row.children.filter((child) => child.tagName === "button").map((button) => button.textContent) });
  }
};
for (const node of pageNodes()) {
  if (node.id === "pr-walk") t.all(node).filter((item) => item.tagName === "article").forEach((stop) => collect(stop.id, stop));
  else collect(isCard(node) ? node.id.replace("card-", "") : node.id, node);
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


# Bites on: an answer button on a PR sheet outside its card's option labels, the prAnswers labels, the merge verdict (locked or not) and Not yet, or a walk stop's check labels and fix labels; a card without options offering anything but Accept and Discuss; a card with options not ending in Something else; a stop offering a check its kind does not, or a fix the words do not give.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_every_answer_button_is_one_of_the_four_patterns(kind):
    sheet = SAMPLES[kind]
    page = _page(sheet, COLLECT)
    cards = {card["id"]: card for card in sheet["cards"]}
    pick = set(WORDS["prAnswers"]["labels"].values())
    sign_off = _verdict_labels(sheet, WORDS)
    stop_rows = [row for row in page["result"] if row["part"].startswith("stop-")]
    rows = [row for row in page["result"] if not row["part"].startswith("stop-")]
    assert [row["part"] for row in rows] == [card["id"] for card in sheet["cards"]] + ["sheet-verdict"]
    walk = PW["walkAnswers"]
    stops = sheet["prSheet"]["walk"]["stops"]
    groups = list(dict.fromkeys(stop["group"] for stop in stops))
    ordered = [stop for group in groups for stop in stops if stop["group"] == group]
    # A stop holds its check row (the kind's own checks) and then its fix row (the words' fixes).
    assert stop_rows == [
        {"part": "stop-" + stop["id"], "labels": labels}
        for stop in ordered
        for labels in ([walk["labels"][value] for value in walk[stop["kind"]]], [fix["label"] for fix in PW["walkFixes"]])
    ]
    assert {tuple(row["labels"]) for row in stop_rows} == {("Works", "Problem", "Skip"), ("Looks right", "Problem", "Skip"), ("Fix before merge", "Fix in a follow-up")}
    for row in rows:
        allowed = sign_off if row["part"] == "sheet-verdict" else pick | {option["label"] for option in cards[row["part"]].get("options", [])}
        outside = [label for label in row["labels"] if label not in allowed]
        assert outside == [], "%s offers %s outside the four answer patterns" % (row["part"], outside)
        if row["part"] == "sheet-verdict":
            assert len(row["labels"]) == 2 and row["labels"][1] == PW["notYetLabel"]
            continue
        options = [option["label"] for option in cards[row["part"]].get("options", [])]
        labels = WORDS["prAnswers"]["labels"]
        expected = options + [labels["something-else"]] if options else [labels["accept"], labels["discuss"]]
        assert row["labels"] == expected, row["part"]


# Bites on: a new answer word added to prAnswers, a second place in the template that creates an answer row, a default leftover option outside the words file's leftoverOptions.
def test_the_answer_words_and_the_one_place_that_makes_buttons():
    answers = WORDS["prAnswers"]
    assert set(answers["labels"]) == set(answers["withOptions"]) | set(answers["withoutOptions"])
    # The values a PR card can offer are exactly the agree and pick patterns' answers (the identities the schema's answer enum defines).
    assert set(answers["withOptions"]) == {"something-else"}
    assert set(answers["withoutOptions"]) == {"accept", "discuss"}
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

