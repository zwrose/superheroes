"""Guards for the review template page drawing the index: the questions that block work, then the PRs waiting on the owner."""
import copy
import json

import pytest

from test_review_template import (
    WORDS,
    _assert_error_shown,
    _card,
    _run_page,
    _sample_files,
    _sheet,
    _with,
)

IW = WORDS["index"]
PW = WORDS["pr"]
SAD_FACE = "<img src=x onerror=alert(1)> & {title}"

# What a scenario can read of the index: its parts by id, the cards inside the Blocks work part, and each row as the owner reads it.
PRELUDE = r"""
const kids = () => elements["sheet-cards"].children;
const part = (id) => kids().find((node) => node.id === id);
const ids = () => kids().map((node) => node.id);
const cardNode = (id) => t.all(elements["sheet-cards"]).find((node) => node.tagName === "article" && node.id === "card-" + id);
t.card = cardNode;
const rowView = (link) => ({
  label: link.children[0].textContent,
  caption: link.children[1].textContent,
  open: link.children[2].textContent,
  href: link.getAttribute("href"),
  target: link.getAttribute("target"),
  rel: link.getAttribute("rel"),
  tag: link.tagName,
});
const groupView = (node) => ({ id: node.id, heading: node.children[0].textContent, headingTag: node.children[0].tagName, rows: node.children.slice(1).map(rowView) });
"""


def _row(number, state, accepted, total, walked=0, walk_total=0, merges_at=None, kind="pr", title=None, caption=None):
    return {
        "number": number,
        "kind": kind,
        "title": title or "Change %d" % number,
        "link": "https://sheets.example.test/%s-%d" % (kind, number),
        "state": state,
        "accepted": accepted,
        "total": total,
        "walked": walked,
        "walkTotal": walk_total,
        "mergesAt": merges_at,
        "caption": caption or "Caption of %d" % number,
    }


ROWS = [
    _row(214, "needs-you", 2, 3, walked=1, walk_total=5, merges_at=2, title="Checkout drops the cart"),
    _row(211, "needs-you", 0, 0, merges_at=1),
    _row(4, "needs-you", 0, 1, kind="stack", merges_at=12, title="Order history"),
    _row(300, "needs-you", 1, 2),
    _row(220, "being-fixed", 1, 4, walked=2, walk_total=2, merges_at=3),
    _row(230, "ready", 3, 3, merges_at=4),
]


def _question(card_id="old-orders", **overrides):
    return _card(
        card_id,
        callKind=IW["questionKind"],
        warning=True,
        question="Should a disabled account's old orders stay visible to support?",
        images=[{"src": "pictures/cart-empty.png", "alt": "The order list of a disabled account", "caption": "Today it is empty"}],
        options=[
            {"id": "keep-visible", "label": "Keep them visible", "consequence": "Support can still look up an old order."},
            {"id": "hide-them", "label": "Hide them", "consequence": "A refund needs an engineer."},
        ],
        recommendation={"text": "Keep them visible", "reason": "Support needs them for refunds.", "optionId": "keep-visible"},
        **overrides,
    )


def _index(cards=None, rows=None, title="Waiting on you"):
    return _sheet("index", cards=[_question()] if cards is None else cards, index={"rows": ROWS if rows is None else rows}, title=title)


def _page(sheet, scenario="return null;", host=None, words=None):
    files = _sample_files(sheet)
    if words is not None:
        files["sheet-words.json"] = {"status": 200, "body": json.dumps(words)}
    page = _run_page(files, host=host, scenario=PRELUDE + scenario)
    assert page["settled"], "the page never settled: %s" % page
    assert page["errorHidden"] is True, page["errors"]
    return page


def _row_views(rows):
    return [
        {"label": label, "caption": caption, "open": IW["open"], "href": row["link"], "target": "_blank", "rel": "noopener", "tag": "a"}
        for row, (label, caption) in zip(rows, [
            ("#214 · Checkout drops the cart", "Caption of 214"),
            ("#211 · Change 211", "Caption of 211"),
            ("Stack #4 · Order history", "Caption of 4"),
            ("#300 · Change 300", "Caption of 300"),
            ("#220 · Change 220", "Caption of 220"),
            ("#230 · Change 230", "Caption of 230"),
        ])
    ]


# Bites on: the Blocks work part missing, out of order, or without its heading, the question's caption, or the card parts a question shows (badge in the warning style, context, picture, options with Something else, recommendation, note, save line).
def test_the_blocks_work_part_holds_the_question_as_a_card():
    page = _page(_index(), """
      const blocks = part("index-blocks");
      return {
        ids: ids(),
        children: blocks.children.map((node) => node.tagName + (node.className ? "." + node.className.split(/\\s+/).join(".") : "")),
        heading: blocks.children[0].textContent,
        caption: blocks.children[blocks.children.length - 1].textContent,
        card: t.parts("old-orders"),
        badge: [t.card("old-orders").children[0].textContent, t.card("old-orders").children[0].className],
        labels: t.state("old-orders").labels,
        options: t.all(t.card("old-orders")).filter((node) => node.tagName === "li").map((item) => item.children.map((child) => child.textContent)),
        picture: t.pictures("old-orders").map((img) => [img.getAttribute("src"), img.getAttribute("alt")]),
        pictureCaption: t.all(t.card("old-orders")).filter((node) => node.tagName === "figcaption").map((node) => node.textContent),
        disabled: t.state("old-orders").disabled,
      };
    """)
    result = page["result"]
    assert result["ids"] == ["index-blocks", "index-group-needs-you", "index-group-being-fixed", "index-group-ready"]
    assert result["children"] == ["h2", "article.sh-card", "p.sh-caption"]
    assert result["heading"] == "Blocks work" == IW["blocksHeading"]
    assert result["caption"] == IW["firstAnswerCounts"]
    assert result["card"][0] == "span.sh-badge.sh-badge--warning" and result["card"][1] == "h2"
    assert result["card"][-4:] == ["div.answer-row", "label:Note", "textarea.sh-field", "div.save-line"]
    assert "div.sheet-images" in result["card"] and "label:Options" in result["card"] and "div.sheet-recommendation" in result["card"]
    assert result["badge"] == ["Blocks work", "sh-badge sh-badge--warning"]
    assert result["labels"] == ["Keep them visible", "Hide them", "Something else"]
    assert result["options"] == [["Keep them visible", "Support can still look up an old order."], ["Hide them", "A refund needs an engineer."]]
    assert result["picture"] == [["pictures/cart-empty.png", "The order list of a disabled account"]]
    assert result["pictureCaption"] == ["Today it is empty"]
    assert not any(result["disabled"])


# Bites on: the nothing-blocking line missing when no question is left, the caption drawn without a question to explain, or a question's part left over.
def test_with_no_question_the_blocks_work_part_says_nothing_is_blocking():
    page = _page(_index(cards=[]), """
      const blocks = part("index-blocks");
      return { children: blocks.children.map((node) => [node.tagName, node.textContent]), all: t.everyText() };
    """)
    assert page["result"]["children"] == [["h2", "Blocks work"], ["p", IW["nothingBlocking"]]]
    assert IW["firstAnswerCounts"] not in page["result"]["all"]
    assert IW["nothingBlocking"] == "Nothing is blocking work right now."


# Bites on: a group drawn out of the order needs-you, being-fixed, ready, a heading that is not the word for its state, a row out of data order, or a row missing; a row's caption not drawn as the row carries it.
def test_each_group_lists_its_rows_in_data_order_with_the_caption_rule():
    page = _page(_index(), "return { groups: kids().filter((node) => node.id.startsWith('index-group-')).map(groupView) };")
    groups = page["result"]["groups"]
    assert [group["id"] for group in groups] == ["index-group-needs-you", "index-group-being-fixed", "index-group-ready"]
    assert [group["heading"] for group in groups] == ["Needs you", "Being fixed", "Ready"]
    assert all(group["headingTag"] == "h2" for group in groups)
    views = _row_views(ROWS)
    assert [group["rows"] for group in groups] == [views[:4], views[4:5], views[5:]]
    assert groups[0]["rows"][1]["caption"] == "Caption of 211"


# Bites on: a row that is not a link, one that opens in this tab, loses rel="noopener", links anywhere but the row's own link, or holds its text as markup.
def test_every_row_is_a_link_that_opens_in_a_new_tab_and_its_text_is_data_not_markup():
    rows = ROWS[:1] + [_row(7, "ready", 1, 1, title=SAD_FACE)]
    page = _page(_index(rows=rows), """
      const links = t.all(elements["sheet-cards"]).filter((node) => node.tagName === "a");
      return { links: links.map(rowView), inside: links.map((link) => t.all(link).filter((node) => node.tagName === "button" || node.tagName === "a").length), tags: t.all(elements["sheet-cards"]).filter((node) => node.tagName === "img" && node.getAttribute("onerror") !== null).length };
    """)
    result = page["result"]
    assert [(link["href"], link["target"], link["rel"], link["tag"]) for link in result["links"]] == [
        ("https://sheets.example.test/pr-214", "_blank", "noopener", "a"),
        ("https://sheets.example.test/pr-7", "_blank", "noopener", "a"),
    ]
    assert result["links"][1]["label"] == "#7 · " + SAD_FACE
    assert result["inside"] == [1, 1] and result["tags"] == 0
    assert [link["open"] for link in result["links"]] == ["Open ›"] * 2


# Bites on: the app bar count not following the questions (one, many), the PRs that need the owner when no question is left, or the nothing-needs-you words when none does.
def test_the_app_bar_counts_the_questions_else_the_prs_that_need_you():
    cases = [
        (_index(cards=[_question()]), "1 question"),
        (_index(cards=[_question("one"), _question("two")]), "2 questions"),
        (_index(cards=[]), "4 need you"),
        (_index(cards=[], rows=[ROWS[4], ROWS[5]]), "Nothing needs you"),
        (_index(cards=[], rows=[ROWS[0]]), "1 need you"),
    ]
    for sheet, expected in cases:
        page = _page(sheet, "return { count: t.count(), hidden: elements['sheet-count'].hidden };")
        assert page["result"] == {"count": expected, "hidden": False}, expected
        assert page["appBar"] == "Waiting on you"
    waiting = _page(_index(), "return t.count();", host={"read": "pending"})
    assert waiting["result"] == "1 question"


# Bites on: a group with no row still drawn (an empty heading), the Blocks work part dropped with no question, or a sheet with nothing in it failing to draw.
def test_empty_groups_are_left_out():
    only_ready = _page(_index(cards=[], rows=[ROWS[5]]), "return ids();")
    assert only_ready["result"] == ["index-blocks", "index-group-ready"]
    two = _page(_index(rows=[ROWS[4], ROWS[0]]), "return ids();")
    assert two["result"] == ["index-blocks", "index-group-needs-you", "index-group-being-fixed"]
    nothing = _page(_index(cards=[], rows=[]), """
      return { ids: ids(), count: t.count(), footer: t.footer(), text: part("index-blocks").children.map((node) => node.textContent) };
    """)
    assert nothing["result"]["ids"] == ["index-blocks"] and nothing["result"]["count"] == IW["nothingNeedsYou"]
    assert nothing["result"]["text"] == [IW["blocksHeading"], IW["nothingBlocking"]]
    assert nothing["result"]["footer"]["caption"] == IW["done"]


# Bites on: the page composing a caption of its own instead of drawing the row's caption as it is (as text, never markup).
@pytest.mark.parametrize("caption", ["2 of 2 accepted · 1 of 1 walked · merges first", "Whatever the builder wrote", SAD_FACE + " <b>not markup</b>"], ids=["builder-line", "any-text", "text-not-markup"])
def test_the_caption_is_the_rows_own_text(caption):
    row = _row(3, "needs-you", 9, 9, walked=9, walk_total=9, merges_at=1, caption=caption)
    page = _page(_index(cards=[], rows=[row]), "return kids().filter((node) => node.id.startsWith('index-group-')).map(groupView)[0].rows[0].caption;")
    assert page["result"] == caption


# Bites on: an index answer written with a revision or any other document than the whole answer at answers/<card id>, a verdict read or written, or a stored answer not coming back as the pick.
def test_an_index_answer_writes_the_plain_document_and_restores_as_a_pick():
    page = _page(_index(cards=[_question(), _question("old-carts")]), """
      t.click(t.button("old-orders", "Keep them visible"));
      await t.tick();
      t.click(t.button("old-carts", "Something else"));
      await t.tick();
      t.type(t.note("old-carts"), "ask me", "change");
      await t.tick();
      return { sets: t.setLog(), reads: t.reads.map((read) => read.name), save: t.saveText("old-orders"), pressed: t.state("old-orders").pressed };
    """)
    result = page["result"]
    assert result["sets"] == [
        {"path": "answers/old-orders", "body": {"answer": "option", "optionId": "keep-visible", "note": ""}},
        {"path": "answers/old-carts", "body": {"answer": "something-else", "optionId": None, "note": ""}},
        {"path": "answers/old-carts", "body": {"answer": "something-else", "optionId": None, "note": "ask me"}},
    ]
    assert result["reads"] == ["answers"] and result["save"] == "Saved" and result["pressed"] == ["true", "false", "false"]
    again = _page(_index(), "return { state: t.state('old-orders'), sets: t.setLog() };", host={"docs": [
        {"id": "old-orders", "data": {"answer": "option", "optionId": "hide-them", "note": "later"}},
    ]})
    assert again["result"]["state"]["pressed"] == ["false", "true", "false"] and again["result"]["state"]["note"] == "later"
    assert again["result"]["sets"] == []


# Bites on: the index drawn as a stepped sheet or with the pr sheet's parts: a stepper, item rows, the saves footer, the history box, or a verdict.
def test_the_index_is_one_scrolling_page_with_the_done_line_in_the_footer_and_zoom_on_its_pictures():
    page = _page(_index(cards=[_question(), _question("old-carts")]), """
      const zoom = elements["sheet-viewer-zoom"].children.map((node) => node.textContent);
      const picture = t.pictures("old-orders")[0];
      t.click(picture);
      return {
        gone: ["sheet-stepper", "sheet-stepper-bottom", "sheet-items", "sheet-why", "sheet-history", "sheet-final"].map((id) => elements[id].hidden),
        footer: t.footer(),
        cardsHidden: [cardNode("old-orders").hidden, cardNode("old-carts").hidden, elements["sheet-cards"].hidden],
        pageClass: t.view.page.className,
        zoom: zoom,
        opened: t.view.root.hidden,
        zoomAfter: elements["sheet-viewer-zoom"].children.map((node) => node.textContent),
        verdict: t.all(elements["sheet-cards"]).some((node) => node.id === "sheet-verdict" || node.id === "verdict-note"),
      };
    """)
    result = page["result"]
    assert result["gone"] == [True] * 6
    assert result["footer"]["hidden"] is False and result["footer"]["captions"] == [IW["done"]]
    assert result["cardsHidden"] == [False, False, False] and result["pageClass"] == "sheet-page is-pr"
    assert result["zoom"] == result["zoomAfter"] == [PW["zoomOut"], PW["zoomIn"], PW["zoomFit"]] and result["opened"] is False
    assert result["verdict"] is False


# Bites on: the page drawing an index with a wording file that lacks a word it reads (any of the index words, a group, the ordinals, the zoom words), or reading the pr sheet's words for it.
INDEX_WORDS = ["blocksHeading", "nothingBlocking", "firstAnswerCounts", "rowPr", "rowStack", "accepted", "nothingToAccept", "walked", "mergesAt", "mergesAtNumber", "beingFixed", "ready", "open", "questionsOne", "questionsMany", "needYou", "nothingNeedsYou", "done"]


@pytest.mark.parametrize("mutate", [
    *[(lambda key: lambda words: words["index"].pop(key))(key) for key in INDEX_WORDS],
    lambda words: words["index"]["groups"].pop("being-fixed"),
    lambda words: words["index"].pop("groups"),
    lambda words: words["index"].pop("ordinals"),
    lambda words: words["index"].__setitem__("ordinals", [1, 2]),
    lambda words: words.pop("index"),
    lambda words: words["pr"].pop("zoomFit"),
    lambda words: words.pop("pr"),
], ids=INDEX_WORDS + ["no-being-fixed-group", "no-groups", "no-ordinals", "ordinals-not-words", "no-index-block", "no-zoom-word", "no-pr-block"])
def test_an_index_whose_words_lack_one_the_page_reads_shows_the_error_box(mutate):
    words = copy.deepcopy(WORDS)
    mutate(words)
    files = _sample_files(_index())
    files["sheet-words.json"] = {"status": 200, "body": json.dumps(words)}
    page = _run_page(files, scenario="return { uses: t.uses, sets: t.sets.length };")
    _assert_error_shown(page)
    assert page["result"] == {"uses": [], "sets": 0}


# Bites on: a pr sheet refused for lacking index words it never reads.
def test_a_pr_sheet_is_drawn_without_the_index_words():
    from test_review_template_pr import PR_SAMPLE, _files
    words = copy.deepcopy(WORDS)
    del words["index"]
    page = _run_page(_files(PR_SAMPLE, words), scenario="return null;")
    assert page["settled"] and page["errorHidden"] is True


# Bites on: two rows with one number drawn, or an index sheet the schema rejects drawn.
def test_an_index_with_two_rows_of_one_number_is_refused():
    rows = [_row(214, "needs-you", 0, 1), _row(214, "ready", 1, 1)]
    page = _run_page(_sample_files(_index(rows=rows)), scenario="return null;")
    _assert_error_shown(page)
    assert any("214" in problem for problem in page["errors"])
    with_link = _with(_index(), lambda clone: clone["index"]["rows"][0].__setitem__("link", "http://not-https.example.test/x"))
    _assert_error_shown(_run_page(_sample_files(with_link), scenario="return null;"))


# Bites on: a reader's or a no-store view of the index leaving a question's answer controls on, or writing an answer or a note the view cannot save.
@pytest.mark.parametrize("host,message", [
    ({"user": "viewer"}, "This sheet is read-only for you. Only its owner can answer."),
    ({"db": "null"}, "Answers can't be saved in this view."),
], ids=["non-owner", "no-store"])
def test_a_reader_view_of_the_index_draws_the_questions_with_their_answers_off_and_writes_nothing(host, message):
    page = _page(_index(cards=[_question(), _question("old-carts")]), """
      const asked = ["old-orders", "old-carts"];
      const out = { ids: ids(), labels: asked.map((id) => t.state(id).labels), off: asked.map((id) => t.state(id).disabled), gate: t.gate().message };
      for (const id of asked) {
        t.buttons(id).forEach((button) => t.fire(button, "click"));
        t.note(id).value = "typed";
        t.fire(t.note(id), "input");
        t.fire(t.note(id), "change");
      }
      await t.tick();
      out.sets = t.setLog();
      out.pressed = asked.map((id) => t.state(id).pressed);
      return out;
    """, host=host)
    result = page["result"]
    assert result["ids"] == ["index-blocks", "index-group-needs-you", "index-group-being-fixed", "index-group-ready"]
    assert result["labels"] == [["Keep them visible", "Hide them", "Something else"]] * 2
    assert all(all(flags) for flags in result["off"]) and result["gate"] == message
    assert result["sets"] == [] and result["pressed"] == [["false"] * 3] * 2
