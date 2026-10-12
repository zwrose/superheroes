"""Guards for the sheet's chat-prose fallback renderer (lib/sheet_prose.py)."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from provenance_patterns import PROVENANCE_PATTERNS

PLUGIN = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN / "lib" / "sheet_prose.py"
SAMPLE = PLUGIN / "theme" / "sample-sheet.json"


def _run(sheet_path, *flags):
    return subprocess.run([sys.executable, "-B", *flags, str(SCRIPT), "render", "--sheet", str(sheet_path)],
                          capture_output=True, text=True)


def _render(tmp_path, sheet):
    """Run the renderer on a sheet dict, on raw file text when given a str, or on a missing file when given None."""
    path = tmp_path / "sheet.json"
    if sheet is not None:
        path.write_text(sheet if isinstance(sheet, str) else json.dumps(sheet), encoding="utf-8")
    return _run(path)


def _card(card_id, **overrides):
    card = {
        "id": card_id,
        "callKind": "Wording to confirm",
        "warning": False,
        "question": "Is this what you meant?",
        "context": [{"title": "Where it stands", "blocks": [{"paragraph": "It reads one way."}]}],
        "images": [],
        "options": [],
    }
    card.update(overrides)
    return card


def _remainder_sheet(rounds, fixes, unsettled_count, card_count=2):
    cards = [_card("card-%d" % n) for n in range(card_count)]
    return {
        "schema": "superheroes-sheet/1",
        "kind": "remainder",
        "title": "Spec review",
        "remainder": {"roundsRun": rounds, "fixesMade": fixes,
                      "unsettled": [card["id"] for card in cards[:unsettled_count]]},
        "cards": cards,
    }


def _valid_sheet():
    sheet = _remainder_sheet(2, 3, 1)
    sheet["cards"][0]["options"] = [
        {"id": "yes", "label": "Yes", "consequence": "We do it."},
        {"id": "no", "label": "No", "consequence": "We don't."},
    ]
    sheet["cards"][0]["recommendation"] = {"text": "Do it.", "reason": "It helps.", "optionId": "yes"}
    return sheet


# Bites on: a card part (context, option, recommendation) that the sheet carries but the prose leaves out.
def test_prose_carries_every_cards_context_options_and_recommendation():
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    result = _run(SAMPLE)
    assert result.returncode == 0, result.stderr
    items = re.split(r"^\d+\. \*\*", result.stdout, flags=re.M)[1:]
    assert len(items) == len(sample["cards"])
    for card, item in zip(sample["cards"], items):
        wanted = [card["question"], card["callKind"]]
        for section in card["context"]:
            wanted.append(section["title"])
            for block in section["blocks"]:
                for kind in ("paragraph", "quote"):
                    if kind in block:
                        wanted.append(block[kind])
                wanted += block.get("bullets", [])
        for option in card["options"]:
            wanted += [option["label"], option["consequence"]]
        if "recommendation" in card:
            wanted += [card["recommendation"]["text"], card["recommendation"]["reason"]]
        for text in wanted:
            assert text in item, "card %s: the prose leaves out %r" % (card["id"], text)


# Bites on: a change to the prose's layout (lines, order, letters, indentation, blank lines) or to which parts show only when present.
def test_prose_matches_the_documented_shape(tmp_path):
    sheet = _remainder_sheet(1, 2, 1)
    sheet["cards"] = [
        _card(
            "plan-day", callKind="Open finding", warning=True, question="Plan the day?",
            context=[{"title": "What you're accepting",
                      "blocks": [{"paragraph": "It is open."}, {"paragraph": "Only you know."}, {"bullets": ["One", "Two"]}]},
                     {"title": "The line", "blocks": [{"quote": "Plan: day"}]}],
            images=[{"src": "img/a.png", "alt": "A chart"}, {"src": "https://x.test/b.png", "alt": "A map"}],
            options=[{"id": "x", "label": "Yes", "consequence": "We plan."},
                     {"id": "y", "label": "No", "consequence": "We skip."}],
            recommendation={"text": "Skip it.", "reason": "It costs a day.", "optionId": "y"},
        ),
        _card("other-call", question="Another call?"),
    ]
    sheet["remainder"]["unsettled"] = ["plan-day"]
    expected = "\n".join([
        "**Spec review**: 2 items for you.",
        "",
        "**Why only these 2.** The review ran 1 round and fixed 2 things itself. "
        "Everything else traces to your board or your rulings, so it isn't here. "
        "1 item here is a finding the review didn't settle.",
        "",
        "1. **Plan the day?**",
        "   - Kind of call: Open finding (warning)",
        "   - What you're accepting:",
        "     It is open.",
        "",
        "     Only you know.",
        "     - One",
        "     - Two",
        "   - The line:",
        '     > "Plan: day"',
        "   - Images: A chart (img/a.png); A map (https://x.test/b.png)",
        "   - Options:",
        "     - a. Yes: We plan.",
        "     - b. No: We skip.",
        "   - Recommendation: Skip it. It costs a day. (option b)",
        "   - Answer: a, b, or Something else",
        "",
        "2. **Another call?**",
        "   - Kind of call: Wording to confirm",
        "   - Where it stands:",
        "     It reads one way.",
        "   - Answer: Aligned or Discuss",
        "",
    ])
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    assert result.stderr == ""
    assert not [line for line in result.stdout.split("\n") if line != line.rstrip()]


# Bites on: the answer line offering Aligned or Discuss on a card with options, or leaving out Something else.
@pytest.mark.parametrize("count, expected", [
    (0, "Aligned or Discuss"),
    (1, "a or Something else"),
    (3, "a, b, c, or Something else"),
])
def test_prose_offers_the_same_answers_as_the_sheet(tmp_path, count, expected):
    sheet = _remainder_sheet(1, 1, 0, card_count=1)
    sheet["cards"][0]["options"] = [{"id": "opt-%d" % n, "label": "Option %d" % n, "consequence": "Happens."} for n in range(count)]
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    answers = [line for line in result.stdout.split("\n") if line.startswith("   - Answer:")]
    assert answers == ["   - Answer: " + expected]
    if count:
        assert "Aligned" not in answers[0] and "Discuss" not in answers[0]


# Bites on: the prose keeping a fixed context heading, dropping a bulleted list, or printing a quote line for a card with no quote.
def test_prose_prints_sender_sections_without_fixed_headings():
    result = _run(SAMPLE)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.split("\n")
    assert "   - What you're accepting:" in lines
    under = lines[lines.index("   - What you're accepting:") + 1:]
    following = under[:next((n for n, line in enumerate(under) if line.startswith("   - ") or not line), len(under))]
    assert any(line.startswith("     - ") for line in following), following
    for fixed in ("What's true now", "Why it needs you", "The exact text"):
        assert fixed not in result.stdout
    items = re.split(r"^\d+\. \*\*", result.stdout, flags=re.M)[1:]
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    quoteless = [card for card in sample["cards"] if card["id"] == "saved-plan-history"]
    assert len(quoteless) == 1 and not any("quote" in b for s in quoteless[0]["context"] for b in s["blocks"])
    position = [card["id"] for card in sample["cards"]].index("saved-plan-history")
    assert not [line for line in items[position].split("\n") if line.lstrip().startswith(">")]


# Bites on: a card with no context sections printing a stray section line or breaking the card's layout.
def test_prose_prints_no_section_lines_for_an_empty_context(tmp_path):
    sheet = _remainder_sheet(1, 1, 0, card_count=1)
    sheet["cards"][0]["context"] = []
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert "\n".join(result.stdout.split("\n")[4:]) == "1. **Is this what you meant?**\n   - Kind of call: Wording to confirm\n   - Answer: Aligned or Discuss\n"


# Bites on: the renderer printing a card whose context is still the old now / whyOwner / exactText object.
def test_prose_refuses_an_old_shape_context(tmp_path):
    sheet = _valid_sheet()
    sheet["cards"][1]["context"] = {"now": "x", "whyOwner": "y", "exactText": None}
    result = _render(tmp_path, sheet)
    assert result.returncode == 1, result.stdout
    assert result.stdout == ""
    assert result.stderr


# Bites on: the why line's wording drifting from the page's box, in its counts, plurals or unsettled sentence.
@pytest.mark.parametrize("rounds, fixes, unsettled, expected", [
    (1, 1, 0, "The review ran 1 round and fixed 1 thing itself. "
              "Everything else traces to your board or your rulings, so it isn't here."),
    (3, 7, 1, "The review ran 3 rounds and fixed 7 things itself. "
              "Everything else traces to your board or your rulings, so it isn't here. "
              "1 item here is a finding the review didn't settle."),
    (2, 0, 2, "The review ran 2 rounds and fixed 0 things itself. "
              "Everything else traces to your board or your rulings, so it isn't here. "
              "2 items here are findings the review didn't settle."),
])
def test_prose_why_line_matches_the_page_wording(tmp_path, rounds, fixes, unsettled, expected):
    result = _render(tmp_path, _remainder_sheet(rounds, fixes, unsettled))
    assert result.returncode == 0, result.stderr
    why = [line for line in result.stdout.split("\n") if line.startswith("**Why only these")]
    assert why == ["**Why only these 2.** " + expected]


# Bites on: the prose dropping an image's caption, or printing a caption an image does not have.
def test_prose_carries_an_images_caption_when_it_has_one(tmp_path):
    sheet = _remainder_sheet(1, 1, 0)
    sheet["cards"][0]["images"] = [{"src": "img/a.png", "alt": "A chart", "caption": "Sales by week"},
                                   {"src": "img/b.png", "alt": "A map"}]
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert "   - Images: A chart: Sales by week (img/a.png); A map (img/b.png)\n" in result.stdout


# Bites on: the why line's wording drifting from the page's box, which the wording table above only compares against fixed text.
@pytest.mark.parametrize("rounds, fixes, unsettled", [(1, 1, 0), (3, 7, 1), (2, 0, 2)])
def test_why_line_is_the_same_on_the_page_and_in_the_prose(tmp_path, rounds, fixes, unsettled):
    from test_review_template import _run_page, _sample_files

    sheet = _remainder_sheet(rounds, fixes, unsettled)
    page = _run_page(_sample_files(sheet), scenario="return t.why();")
    assert page["settled"], "the page never settled: %s" % page
    prose = _render(tmp_path, sheet)
    assert prose.returncode == 0, prose.stderr
    why = [line for line in prose.stdout.split("\n") if line.startswith("**Why only these")]
    assert len(why) == 1
    heading, text = re.fullmatch(r"\*\*(.+)\.\*\* (.+)", why[0]).groups()
    assert (page["result"]["heading"], page["result"]["text"]) == (heading, text)


# Bites on: a final or plain sheet printing the remainder sheet's why line.
@pytest.mark.parametrize("kind", ["plain", "final"])
def test_prose_why_line_is_absent_off_a_remainder_sheet(tmp_path, kind):
    sheet = {"schema": "superheroes-sheet/1", "kind": kind, "title": "Spec review", "cards": [_card("only-one")]}
    if kind == "final":
        sheet["final"] = {
            "history": {"reviewRounds": 1, "fixesMade": 1, "vet": "Clean."},
            "declinedFindings": [],
            "approval": {"approvedBoard": True, "boardSavedWithSpec": True},
        }
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert "Why only" not in result.stdout
    if kind == "final":
        assert result.stdout.startswith("**Spec review**: 1 item for you.\n\n**How the spec got here.** ")
    else:
        assert result.stdout.startswith("**Spec review**: 1 item for you.\n\n1. **")


def _final_sheet(declined=(), approved=True, saved=True, cards=None):
    return {
        "schema": "superheroes-sheet/1",
        "kind": "final",
        "title": "Spec review",
        "final": {
            "history": {"reviewRounds": 3, "fixesMade": 1, "vet": "The vet found nothing."},
            "declinedFindings": [{"summary": summary, "reason": reason} for summary, reason in declined],
            "approval": {"approvedBoard": approved, "boardSavedWithSpec": saved},
        },
        "cards": [_card("card-0"), _card("card-1", question="Another call?")] if cards is None else cards,
    }


def _mutated(change):
    def build():
        sheet = _valid_sheet()
        change(sheet)
        return sheet
    return build


def _mutated_final(change):
    def build():
        sheet = _final_sheet()
        change(sheet)
        return sheet
    return build


def _drop(sheet, *path):
    target = sheet
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]


def _set(sheet, value, *path):
    target = sheet
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


REFUSALS = {
    "unreadable file": (lambda: None, "can't be read"),
    "invalid JSON": (lambda: "{not json", "not valid JSON"),
    "top level not an object": (lambda: "[1, 2]", "The data file must be object."),
    "wrong schema": (_mutated(lambda s: _set(s, "superheroes-sheet/2", "schema")), 'Schema must be "superheroes-sheet/1".'),
    "unknown kind": (_mutated(lambda s: _set(s, "weekly", "kind")), "Kind must be one of remainder, final, plain, pr, stack."),
    "empty title": (_mutated(lambda s: _set(s, "", "title")), "Title must not be empty."),
    "empty cards": (_mutated(lambda s: _set(s, [], "cards")), "Cards must not be empty."),
    "missing section title": (_mutated(lambda s: _drop(s, "cards", 1, "context", 0, "title")), "Cards[1].context[0] has no title."),
    "missing question": (_mutated(lambda s: _drop(s, "cards", 0, "question")), "Cards[0] has no question."),
    "missing warning": (_mutated(lambda s: _drop(s, "cards", 1, "warning")), "Cards[1] has no warning."),
    "wrong-typed warning": (_mutated(lambda s: _set(s, "yes", "cards", 1, "warning")), "Cards[1].warning must be boolean."),
    "wrong-typed option label": (_mutated(lambda s: _set(s, 7, "cards", 0, "options", 0, "label")),
                                 "Cards[0].options[0].label must be string."),
    "wrong-typed paragraph": (_mutated(lambda s: _set(s, 3, "cards", 1, "context", 0, "blocks", 0, "paragraph")),
                              "Cards[1].context[0].blocks[0] fits none of its allowed shapes."),
    "block holding two kinds": (_mutated(lambda s: _set(s, {"paragraph": "a", "quote": "b"}, "cards", 1, "context", 0, "blocks", 0)),
                                "Cards[1].context[0].blocks[0] fits none of its allowed shapes."),
    "image with no alt": (_mutated(lambda s: _set(s, [{"src": "a.png"}], "cards", 1, "images")), "Cards[1].images[0] has no alt."),
    "recommendation with no reason": (_mutated(lambda s: _drop(s, "cards", 0, "recommendation", "reason")),
                                      "Cards[0].recommendation has no reason."),
    "repeated unsettled id": (_mutated(lambda s: _set(s, ["card-0", "card-0"], "remainder", "unsettled")),
                              "Remainder.unsettled must not repeat an item."),
    "bool roundsRun": (_mutated(lambda s: _set(s, True, "remainder", "roundsRun")), "Remainder.roundsRun must be integer."),
    "negative fixesMade": (_mutated(lambda s: _set(s, -1, "remainder", "fixesMade")), "Remainder.fixesMade must be 0 or more."),
    "unsettled not strings": (_mutated(lambda s: _set(s, [4], "remainder", "unsettled")), "Remainder.unsettled[0] must be string."),
    "no remainder block": (_mutated(lambda s: _drop(s, "remainder")), "The data file has no remainder."),
    "plain sheet carrying a remainder block": (_mutated(lambda s: _set(s, "plain", "kind")),
                                               "The data file holds a part this kind of sheet must not have."),
    "card with an unknown property": (_mutated(lambda s: _set(s, 1, "cards", 0, "bogus")),
                                      "Cards[0] has bogus, which the sheet does not use."),
    "board saved with no approved board": (_mutated_final(lambda s: s["final"]["approval"].update(approvedBoard=False)),
                                           "boardSavedWithSpec must be false."),
    "duplicate card id": (_mutated(lambda s: _set(s, "card-0", "cards", 1, "id")), 'Card id "card-0" is used more than once'),
    "duplicate option id": (_mutated(lambda s: _set(s, "yes", "cards", 0, "options", 1, "id")),
                            'Card "card-0" has the option id "yes" more than once'),
    "unknown unsettled id": (_mutated(lambda s: _set(s, ["card-0", "ghost"], "remainder", "unsettled")),
                             'remainder.unsettled names "ghost"'),
    "recommendation names a missing option": (_mutated(lambda s: _set(s, "maybe", "cards", 0, "recommendation", "optionId")),
                                              'Card "card-0" recommends option "maybe"'),
}


# Bites on: the fallback's rules drifting from sheet.schema.json, which it must read rather than copy.
def test_prose_accepts_a_whole_number_written_with_a_decimal_point(tmp_path):
    sheet = json.dumps(_valid_sheet()).replace('"roundsRun": 2', '"roundsRun": 2.0')
    assert '"roundsRun": 2.0' in sheet
    assert _render(tmp_path, sheet).returncode == 0


# Bites on: the renderer printing prose for a data file it can't trust, or a refusal that skips stderr, prints to stdout, or exits 0.
@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_prose_refuses_a_data_file_it_cannot_trust(tmp_path, name):
    build, expected = REFUSALS[name]
    result = _render(tmp_path, build())
    assert result.returncode == 1, result.stdout
    assert result.stdout == ""
    assert expected in result.stderr, result.stderr
    assert all(line.strip() for line in result.stderr.splitlines())


def test_prose_refusal_lists_one_problem_per_line(tmp_path):
    sheet = _valid_sheet()
    _drop(sheet, "cards", 0, "question")
    _drop(sheet, "cards", 1, "context", 0, "title")
    result = _render(tmp_path, sheet)
    assert result.returncode == 1
    assert result.stderr.splitlines() == ["Cards[0] has no question.", "Cards[1].context[0] has no title."]


# Bites on: the renderer needing a third-party package, which a plain python3 on the owner's host may not have.
def test_prose_runs_without_third_party_packages():
    result = subprocess.run([sys.executable, "-I", "-S", "-B", str(SCRIPT), "render", "--sheet", str(SAMPLE)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("**")
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import"
            imported.add(node.module.split(".")[0])
    assert imported, "the script imports nothing, so the check reads nothing"
    assert imported <= set(sys.stdlib_module_names), sorted(imported - set(sys.stdlib_module_names))


# Bites on: spec provenance (requirement, ruling, issue, work-item numbers or handoff references) leaking into the script.
def test_prose_script_carries_no_provenance():
    source = SCRIPT.read_text(encoding="utf-8")
    for pattern in PROVENANCE_PATTERNS:
        assert not re.search(pattern, source), "sheet_prose.py matches %s" % pattern


# Bites on: the page's checkSheet and the prose renderer's check disagreeing about any of the four cross-field rules the schema description lists (or about a valid sheet).
def test_cross_field_rules_agree_between_page_and_prose():
    import importlib.util
    from test_review_template import _run_check_sheet

    spec = importlib.util.spec_from_file_location("sheet_prose_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def mutated(mutate):
        sheet = _valid_sheet()
        mutate(sheet)
        return sheet

    fixtures = [
        ("valid", _valid_sheet(), False),
        ("duplicate card id", mutated(lambda s: s["cards"][1].update(id="card-0")), True),
        ("duplicate option id", mutated(lambda s: s["cards"][0]["options"][1].update(id="yes")), True),
        ("unsettled names a missing card", mutated(lambda s: s["remainder"].update(unsettled=["no-such-card"])), True),
        ("recommendation names a missing option", mutated(lambda s: s["cards"][0]["recommendation"].update(optionId="maybe")), True),
    ]
    page = _run_check_sheet([sheet for _, sheet, _ in fixtures])
    for (name, sheet, refused), page_problems in zip(fixtures, page):
        prose_problems = module.check_sheet(sheet)
        assert bool(page_problems) == bool(prose_problems) == refused, "%s: page %s, prose %s" % (name, page_problems, prose_problems)


SCHEMA_FILE = PLUGIN / "theme" / "sheet.schema.json"


def _load_prose_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("sheet_prose_planted", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _planted_schema(plant):
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    plant(schema)
    return schema


def _plant_title_max_length(schema):
    schema["properties"]["title"]["maxLength"] = 5


def _plant_image_src_format(schema):
    schema["$defs"]["image"]["properties"]["src"]["format"] = "uri"


def _plant_options_max_items(schema):
    schema["$defs"]["card"]["properties"]["options"]["maxItems"] = 3


def _plant_outside_ref(schema):
    schema["properties"]["kind"]["$ref"] = "#/properties/title"


def _plant_option_extra_schema(schema):
    schema["$defs"]["option"]["additionalProperties"] = {"type": "string"}


def _plant_cards_items_list(schema):
    schema["properties"]["cards"]["items"] = [{"$ref": "#/$defs/card"}]


def _plant_option_required_number(schema):
    schema["$defs"]["option"]["required"] = 5


def _plant_id_pattern_not_a_regex(schema):
    schema["$defs"]["id"]["pattern"] = "["


def _plant_kind_enum_string(schema):
    schema["properties"]["kind"]["enum"] = "abc"


def _plant_title_misspelled_type(schema):
    schema["properties"]["title"]["type"] = "nubmer"


def _plant_title_min_length_string(schema):
    schema["properties"]["title"]["minLength"] = "1"


def _plant_cards_unique_items_string(schema):
    schema["properties"]["cards"]["uniqueItems"] = "yes"


def _plant_title_ref_loop(schema):
    schema["$defs"]["loop"] = {"$ref": "#/$defs/loop"}
    schema["properties"]["title"] = {"$ref": "#/$defs/loop"}


UNENFORCED = [
    ("maxLength", _plant_title_max_length, "maxLength", "#/properties/title"),
    ("format", _plant_image_src_format, "format", "#/$defs/image/properties/src"),
    ("maxItems", _plant_options_max_items, "maxItems", "#/$defs/card/properties/options"),
    ("outside-ref", _plant_outside_ref, "$ref", "#/properties/kind"),
    ("additionalProperties-schema", _plant_option_extra_schema, "additionalProperties", "#/$defs/option"),
    ("items-list", _plant_cards_items_list, "items", "#/properties/cards"),
    ("required-not-a-list", _plant_option_required_number, "required", "#/$defs/option"),
    ("pattern-not-a-regex", _plant_id_pattern_not_a_regex, "pattern", "#/$defs/id"),
    ("enum-not-a-list", _plant_kind_enum_string, "enum", "#/properties/kind"),
    ("type-not-a-type", _plant_title_misspelled_type, "type", "#/properties/title"),
    ("minLength-not-a-number", _plant_title_min_length_string, "minLength", "#/properties/title"),
    ("uniqueItems-not-a-boolean", _plant_cards_unique_items_string, "uniqueItems", "#/properties/cards"),
    ("ref-loop", _plant_title_ref_loop, "$ref", "#/$defs/loop"),
]


# Bites on: the renderer checking a sheet against a schema that uses a keyword, or a form of one, it does not enforce, instead of refusing that schema.
@pytest.mark.parametrize("plant, keyword, place", [case[1:] for case in UNENFORCED], ids=[case[0] for case in UNENFORCED])
def test_prose_refuses_a_schema_keyword_it_does_not_enforce(tmp_path, monkeypatch, capsys, plant, keyword, place):
    planted = tmp_path / "planted.schema.json"
    planted.write_text(json.dumps(_planted_schema(plant)), encoding="utf-8")
    module = _load_prose_module()
    monkeypatch.setattr(module, "SCHEMA", planted)
    assert module.main(["render", "--sheet", str(SAMPLE)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert '"%s"' % keyword in captured.err, captured.err
    assert " at %s, " % place in captured.err, captured.err
    assert all(line.strip() for line in captured.err.splitlines())


def _plant_ref_with_sibling(schema):
    schema["properties"]["title"] = {"$ref": "#/$defs/nonEmpty", "minLength": 500}
    schema["$defs"]["nonEmpty"] = {"type": "string", "minLength": 1}


def _plant_standalone_conditional(schema):
    schema["if"] = {"properties": {"kind": {"const": "remainder"},
                                   "title": {"const": "Weekly meal planner spec review"}},
                    "required": ["kind", "title"]}
    schema["then"] = {"properties": {"title": {"const": "x"}}}


# Bites on: the prose reader and the page reading a $ref's sibling keywords, or an if/then outside allOf, differently.
@pytest.mark.parametrize("plant", [_plant_ref_with_sibling, _plant_standalone_conditional], ids=["ref-siblings", "standalone-if-then"])
def test_prose_and_page_agree_on_ref_siblings_and_conditionals(tmp_path, monkeypatch, plant):
    from test_review_template import _run_check_sheet

    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    planted = _planted_schema(plant)
    planted_path = tmp_path / "planted.schema.json"
    planted_path.write_text(json.dumps(planted), encoding="utf-8")
    module = _load_prose_module()

    assert _run_check_sheet([sample]) == [[]]
    assert module.check_sheet(sample) == []

    page_problems = _run_check_sheet([sample], schema=planted)[0]
    monkeypatch.setattr(module, "SCHEMA", planted_path)
    prose_problems = module.check_sheet(sample)
    assert page_problems, "the page accepted the sample under the planted schema"
    assert prose_problems, "the prose reader accepted the sample under the planted schema"


# Bites on: the prose reader accepting a schema the page refuses (any planted case of the page's own refusal list), or raising instead of refusing.
def test_prose_and_page_refuse_the_same_planted_schemas(tmp_path, monkeypatch):
    from test_review_template import _planted, _sheet, _unsupported_rule_cases

    module = _load_prose_module()
    planted_path = tmp_path / "planted.schema.json"
    monkeypatch.setattr(module, "SCHEMA", planted_path)
    accepted = []
    for name, mutate, _keyword, _pointer in _unsupported_rule_cases():
        planted_path.write_text(json.dumps(_planted(mutate)), encoding="utf-8")
        try:
            problems = module.check_sheet(_sheet("plain"))
        except Exception as error:
            pytest.fail("%s: the prose reader raised %r instead of refusing" % (name, error))
        if not problems:
            accepted.append(name)
    assert accepted == [], "the prose reader accepted what the page refuses: %s" % accepted


# Bites on: const or enum comparing by Python equality (true equal to 1, key order mattering) instead of by JSON content and type, as the page does.
def test_prose_const_and_enum_compare_by_type(tmp_path, monkeypatch):
    module = _load_prose_module()
    planted_path = tmp_path / "planted.schema.json"
    monkeypatch.setattr(module, "SCHEMA", planted_path)

    def problems_for(rule, warning):
        schema = _planted_schema(lambda s: s["$defs"]["card"]["properties"].update(warning=rule))
        planted_path.write_text(json.dumps(schema), encoding="utf-8")
        sheet = _valid_sheet()
        for card in sheet["cards"]:
            card["warning"] = warning
        return module.check_sheet(sheet)

    assert problems_for({"const": True}, True) == []
    assert problems_for({"const": True}, 1) != []
    assert problems_for({"enum": [1]}, 1) == []
    assert problems_for({"enum": [1]}, True) != []
    assert problems_for({"enum": [{"a": 1, "b": 2}]}, {"b": 2, "a": 1}) == []


# Bites on: uniqueItems comparing objects by their written key order, so two objects with the same keys in a different order pass as distinct, as the page does not.
def test_prose_uniqueitems_treats_reordered_objects_as_a_repeat(tmp_path, monkeypatch):
    module = _load_prose_module()
    planted_path = tmp_path / "planted.schema.json"
    tags = {"type": "array", "uniqueItems": True, "items": {"type": "object"}}
    schema = _planted_schema(lambda s: s["$defs"]["card"]["properties"].update(tags=tags))
    planted_path.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(module, "SCHEMA", planted_path)

    sheet = _valid_sheet()
    sheet["cards"][0]["tags"] = [{"a": 1, "b": 2}, {"b": 2, "a": 1}]
    problems = module.check_sheet(sheet)
    assert problems != [] and all("must not repeat an item" in problem for problem in problems)

    sheet["cards"][0]["tags"] = [{"a": 1, "b": 2}, {"a": 1, "b": 3}]
    assert module.check_sheet(sheet) == []


# Bites on: a minLength above 1 reading "must not be empty", or minLength 1 reading as a length.
@pytest.mark.parametrize("shortest, expected", [
    (1, "Title must not be empty."),
    (5, "Title must be at least 5 characters long."),
], ids=["one", "five"])
def test_prose_names_the_length_a_minLength_asks_for(tmp_path, monkeypatch, shortest, expected):
    module = _load_prose_module()
    planted_path = tmp_path / "planted.schema.json"
    planted_path.write_text(json.dumps(_planted_schema(lambda s: s["properties"]["title"].update(minLength=shortest))), encoding="utf-8")
    monkeypatch.setattr(module, "SCHEMA", planted_path)
    sheet = _valid_sheet()
    sheet["title"] = ""
    assert module.check_sheet(sheet) == [expected]


# Bites on: Markdown in a sheet's own text (underscores, asterisks, backticks, brackets, angle brackets, tildes, pipes, ampersands, backslashes) printing as formatting, or an escape that loses the original characters.
def test_prose_escapes_markdown_in_sheet_text(tmp_path):
    question = "Rename __init__ to **x**?"
    now = "`code` [link](u) <b> a|b ~c~ & d\\e"
    sheet = _valid_sheet()
    sheet["cards"][0]["question"] = question
    sheet["cards"][0]["context"][0]["blocks"][0]["paragraph"] = now
    sheet["cards"][0]["options"][0]["label"] = "_x_"
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    for escaped in [r"\_\_init\_\_", r"\*\*x\*\*", r"\`code\`", r"\[link\]", r"\<b\>", r"a\|b", r"\~c\~", r"\&", r"d\\e", r"\_x\_"]:
        assert escaped in result.stdout, escaped
    unescaped = re.sub(r"\\([\\`*_\[\]<>~|&])", r"\1", result.stdout)
    for original in [question, now, "_x_"]:
        assert original in unescaped, original


# Bites on: a card with more than 26 options getting a character past z, or the option list, recommendation and answer line lettering differently.
def test_prose_letters_options_past_z(tmp_path):
    sheet = _valid_sheet()
    card = sheet["cards"][0]
    card["options"] = [{"id": "opt-%d" % n, "label": "Option %d" % n, "consequence": "Happens."} for n in range(28)]
    card["recommendation"] = {"text": "Take the last.", "reason": "It is last.", "optionId": "opt-27"}
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    letters = [chr(ord("a") + n) for n in range(26)] + ["aa", "ab"]
    lines = result.stdout.split("\n")
    assert [line for line in lines if line.startswith("     - ")] == ["     - %s. Option %d: Happens." % (letter, n) for n, letter in enumerate(letters)]
    assert "   - Recommendation: Take the last. It is last. (option ab)" in lines
    assert "   - Answer: " + ", ".join(letters) + ", or Something else" in lines
    assert [line for line in lines if line.startswith("   - Answer: a, b, ")][0].endswith(", z, aa, ab, or Something else")


HISTORY_LINE = "**How the spec got here.** The review ran 3 rounds and fixed 1 thing itself. The vet: The vet found nothing."
TRACES_BOARD_LINE = "- Every statement in the spec traces to your board, your framing, your rulings, your answers, or craft recorded for your veto."
TRACES_NO_BOARD_LINE = "- Every statement in the spec traces to your framing, your rulings, your answers, or craft recorded for your veto."
NEXT_LINE = ("**What happens next.** Once you've chosen Approve and said in the chat that you're done, the advisor adds the "
             "breakdown to the same PR (or, where the project keeps specs outside the repo or gitignored, beside the spec where "
             "it is kept) and vets it, and an independent read of the breakdown still runs where it applies. Then one merge word "
             "from you covers both, and the issues are filed as it merges. If another answer here changes the spec, the spec "
             "goes back through its checks, a new vet and a new approval first.")
APPROVE_ANSWER_LINE = "- Answer: Approve or Not yet, with any note."
WORDS = json.loads((PLUGIN / "theme" / "sheet-words.json").read_text(encoding="utf-8"))
DONE_STEP_LINE = "- " + WORDS["doneStepInChat"]
TWO_DECLINES = [("Add a counter.", "It is out of scope."), ("Add a theme.", "It costs too much.")]
DECLINED_LINES = ["**Declined findings (2).**", "- Add a counter. (why declined: It is out of scope.)",
                  "- Add a theme. (why declined: It costs too much.)", ""]
NO_DECLINES_LINES = ["**Declined findings.** No findings were declined.", ""]


def _plain_card_lines(number, question):
    return ["%d. **%s**" % (number, question), "   - Kind of call: Wording to confirm", "   - Where it stands:",
            "     It reads one way.", "   - Answer: Aligned or Discuss", ""]


TWO_CARD_LINES = _plain_card_lines(1, "Is this what you meant?") + _plain_card_lines(2, "Another call?")

FINAL_CASES = {
    "board saved, two declines, two cards": (
        _final_sheet(declined=TWO_DECLINES),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is saved with the spec.", APPROVE_ANSWER_LINE, DONE_STEP_LINE,
           "", NEXT_LINE]),
    "board not saved": (
        _final_sheet(declined=TWO_DECLINES, saved=False),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is not saved with the spec.", APPROVE_ANSWER_LINE, DONE_STEP_LINE,
           "", NEXT_LINE]),
    "no board": (
        _final_sheet(declined=TWO_DECLINES, approved=False, saved=False),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_NO_BOARD_LINE, APPROVE_ANSWER_LINE, DONE_STEP_LINE, "", NEXT_LINE]),
    "no declines": (
        _final_sheet(),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + NO_DECLINES_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is saved with the spec.", APPROVE_ANSWER_LINE, DONE_STEP_LINE,
           "", NEXT_LINE]),
    "zero cards": (
        _final_sheet(declined=TWO_DECLINES, cards=[]),
        ["**Spec review**: 0 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is saved with the spec.", APPROVE_ANSWER_LINE, DONE_STEP_LINE,
           "", NEXT_LINE]),
}


# Bites on: a change to the final sheet's prose (its history, declined findings, board line, approval box or closing line), or to which of them show only when present.
@pytest.mark.parametrize("name", sorted(FINAL_CASES))
def test_prose_renders_a_final_sheet(tmp_path, name):
    sheet, lines = FINAL_CASES[name]
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "\n".join(lines) + "\n"
    assert result.stderr == ""
    assert not [line for line in result.stdout.split("\n") if line != line.rstrip()]


# Bites on: the final tail not printing the chat's version of the done step (read from sheet-words.json) on the line straight after the answer line, printing it anywhere else, or printing the page's version.
@pytest.mark.parametrize("name", sorted(FINAL_CASES))
def test_prose_prints_the_done_step_for_the_chat_straight_after_the_answer_line(tmp_path, name):
    sheet, _ = FINAL_CASES[name]
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.split("\n")
    at = lines.index(APPROVE_ANSWER_LINE)
    assert lines[at + 1] == "- " + WORDS["doneStepInChat"]
    assert lines.count("- " + WORDS["doneStepInChat"]) == 1
    assert WORDS["doneStep"] not in result.stdout, "the prose printed the page's done step"


# Bites on: the "What happens next" words dropping a step that follows approval (the trigger, the hold, the breakdown, its independent read, the one merge word, the filed issues).
def test_the_next_line_says_every_step_after_approval():
    words = WORDS["next"]
    steps = [
        ("chosen Approve", "the Approve choice that starts it"),
        ("said in the chat that you're done", "the owner saying in the chat they're done"),
        ("adds the breakdown to the same PR", "the advisor adding the breakdown to the same PR"),
        ("beside the spec where it is kept", "the breakdown going beside a spec kept outside the PR"),
        ("vets it", "the advisor vetting the breakdown"),
        ("an independent read of the breakdown still runs where it applies", "the independent read of the breakdown"),
        ("one merge word from you covers both", "the one merge word covering both"),
        ("the issues are filed as it merges", "the issues being filed as it merges"),
        ("goes back through its checks, a new vet and a new approval first", "the hold when another answer changes the spec"),
    ]
    for phrase, step in steps:
        assert phrase in words, "the next line leaves out " + step


def _unescaped(text):
    """The prose's Markdown escapes taken out, so a line reads as the sheet's own text."""
    return re.sub(r"\\(.)", r"\1", text)


# Bites on: the final sheet's wording on the page (history line, traces line, board line, declined items, next line) drifting from the prose's, which the prose's own wording table pins only against fixed text.
@pytest.mark.parametrize("declined", [
    pytest.param([], id="no-declines"),
    pytest.param([("Add a *counter* for each_item.", "It's <out> of scope & costly."), ("Use `tabs`.", "It costs too much.")], id="declines"),
])
@pytest.mark.parametrize("approved,saved", [
    pytest.param(True, True, id="board-saved"),
    pytest.param(True, False, id="board-not-saved"),
    pytest.param(False, False, id="no-board"),
])
def test_final_sheet_wording_is_the_same_on_the_page_and_in_the_prose(tmp_path, approved, saved, declined):
    from test_review_template import _run_page, _sample_files

    sheet = _final_sheet(declined=declined, approved=approved, saved=saved)
    page = _run_page(_sample_files(sheet), scenario="""
      return { history: t.history(), approval: t.lastParagraphs(), next: t.nextBox().text };
    """)
    assert page["settled"], "the page never settled: %s" % page
    seen = page["result"]
    prose = _render(tmp_path, sheet)
    assert prose.returncode == 0, prose.stderr
    lines = prose.stdout.split("\n")

    def after(prefix):
        found = [line for line in lines if line.startswith(prefix)]
        assert len(found) == 1, (prefix, found)
        return _unescaped(found[0][len(prefix):])

    assert seen["history"]["paragraphs"][0] == after("**How the spec got here.** ")
    assert seen["next"] == after("**What happens next.** ")

    approval = lines.index("**Approve the spec?**")
    wording = []
    for line in lines[approval + 1:]:
        if not line.startswith("- ") or line.startswith("- Answer:"):
            break
        wording.append(_unescaped(line[2:]))
    assert len(wording) == (2 if approved else 1)
    assert seen["approval"] == wording, "the traces line or the board line differs (or one shows when it should not)"

    if declined:
        start = next(index for index, line in enumerate(lines) if line.startswith("**Declined findings ("))
        items = []
        for line in lines[start + 1:]:
            if not line.startswith("- "):
                break
            items.append(_unescaped(line[2:]))
        assert [text for _, text in seen["history"]["items"]] == items
        assert len(items) == len(declined)
    else:
        assert seen["history"]["paragraphs"][1] == after("**Declined findings.** ")


def _pr_kind_sheet(kind):
    """A valid pr sheet, or a valid stack sheet, with one card whose options all say sendsBack."""
    body = {
        "number": 1724,
        "commit": "662d4487",
        "whatChanged": {
            "summary": "Adds a sheet for one PR.",
            "reviewers": [{"name": "reviewer-one", "family": "claude", "ran": "engine-record", "notIndependent": False}],
            "caught": [],
            "rounds": 2,
            "stoppedAtCap": False,
            "ci": {"state": "green", "commit": None},
            "lane": None,
            "laneReason": None,
        },
        "craft": [],
        "alreadyDecided": [],
        "history": ["2 rounds ran."],
        "walk": [{"id": "schema", "title": "The schema", "pr": 1724}],
    }
    if kind == "stack":
        body["walk"].append({"id": "builder", "title": "The builder", "pr": 1725})
        body["prs"] = [{"number": 1724, "title": "The schema", "commit": "662d4487"},
                       {"number": 1725, "title": "The builder", "commit": "abcdef0"}]
    card = _card("leftover", options=[{"id": "keep-it", "label": "Keep it", "consequence": "Ships.", "sendsBack": False}])
    return {"schema": "superheroes-sheet/1", "kind": kind, "title": "PR 1724", "prSheet": body, "cards": [card]}


# Bites on: the renderer refusing a pr or stack sheet instead of printing its prose, or printing it to stderr, or exiting non-zero.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_prose_renders_a_pr_sheet(tmp_path, kind):
    path = tmp_path / "sheet.json"
    path.write_text(json.dumps(_pr_kind_sheet(kind)), encoding="utf-8")
    result = _run(path)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.startswith("**PR 1724**: 1 item for you.\n")
    assert "1. **Is this what you meant?**" in result.stdout


PR_WORDS = WORDS["pr"]
PR_ANSWER_WORDS = WORDS["prAnswers"]
SAMPLE_PR = PLUGIN / "theme" / "sample-pr-sheet.json"
SAMPLE_STACK = PLUGIN / "theme" / "sample-stack-sheet.json"
SAMPLES = {"pr": SAMPLE_PR, "stack": SAMPLE_STACK}
COMMIT_RULE = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["$defs"]["commit"]["description"]


def _sample(kind):
    return json.loads(SAMPLES[kind].read_text(encoding="utf-8"))


def _prose_of(tmp_path, sheet):
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return result.stdout


def _reviewers_line(reviewers):
    named = []
    for reviewer in reviewers:
        notes = [reviewer["family"] or PR_WORDS["familyUnknown"]] + ([PR_WORDS["notIndependentMark"]] if reviewer.get("notIndependent") else [])
        named.append("%s (%s)" % (reviewer["name"], ", ".join(notes)))
    return PR_WORDS["reviewedBy"].replace("{reviewers}", "; ".join(named))


def _pr_markers(sheet):
    """Every line the sheet's prose must carry, each read from the data file or the words file, in the order it must come."""
    part, facts, stack = sheet["prSheet"], sheet["prSheet"]["whatChanged"], sheet["kind"] == "stack"
    merge = (PR_WORDS["mergeStackLabel"] if stack else PR_WORDS["mergeLabel"]).replace("{number}", str(part["number"]))
    count = "1 item" if len(sheet["cards"]) == 1 else "%d items" % len(sheet["cards"])
    markers = ["**%s**: %s for you." % (sheet["title"], count),
               "**%s**" % PR_WORDS["whatChangedHeading"], facts["summary"], _reviewers_line(facts["reviewers"]),
               "**%s**" % PR_WORDS["caughtHeading"]]
    markers += ["- " + line for line in facts["caught"]]
    markers.append(PR_WORDS["roundsLine"].replace("{rounds}", "%d rounds" % facts["rounds"]))
    markers += [PR_WORDS["historyCap"]] if facts["stoppedAtCap"] else []
    markers += [PR_WORDS["ciLine"].replace("{state}", facts["ci"]["state"]).replace("{commit}", facts["ci"]["commit"][:7]),
                PR_WORDS["laneLine"].replace("{lane}", facts["lane"]).replace("{reason}", facts["laneReason"]),
                PR_WORDS["describesCommit"].replace("{commit}", part["commit"][:7]), "**%s**" % PR_WORDS["walkHeading"]]
    markers += ["- %s%s" % ("#%d " % stop["pr"] if stack else "", stop["title"]) for stop in part["walk"]]
    markers.append("**%s**" % PR_WORDS["acceptingHeading"])
    markers += ["%d. **%s**" % (number, card["question"]) for number, card in enumerate(sheet["cards"], 1)]
    folded = [(PR_WORDS["craftHeading"], ["%s — %s" % (e["title"], e["detail"]) for e in part["craft"]]),
              (PR_WORDS["decidedHeading"], ["%s — %s" % (e["title"], e["detail"]) for e in part["alreadyDecided"]]),
              (PR_WORDS["reviewHeading"], list(part["history"]))]
    if stack:
        folded.append((PR_WORDS["prsHeading"], ["#%d %s · %s" % (p["number"], p["title"], p["commit"][:7]) for p in part["prs"]]))
    for heading, entries in folded:
        markers += ["**%s (%d)**" % (heading, len(entries))] + ["- " + entry for entry in entries]
    markers += ["**%s**" % PR_WORDS["verdictHeading"], PR_WORDS["verdictInChat"].replace("{merge}", merge)]
    return markers


# Bites on: the prose for a pr or stack sheet leaving out a fact of the data file, changing a word of the words file, or printing a part out of the page's order.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_prose_prints_a_pr_sheet_in_the_pages_order_with_the_data_files_facts(tmp_path, kind):
    sheet = _sample(kind)
    out = _prose_of(tmp_path, sheet)
    position = 0
    for marker in _pr_markers(sheet):
        found = out.find(marker, position)
        assert found >= 0, "%r is missing, or comes out of order, after position %d" % (marker, position)
        position = found + len(marker)
    assert out.count("**%s**" % PR_WORDS["verdictHeading"]) == 1
    assert out.endswith(PR_WORDS["verdictInChat"].replace("{merge}", "Merge%s #%d" % (" stack" if kind == "stack" else "", sheet["prSheet"]["number"])) + "\n")


def test_prose_verdict_line_is_the_words_file_line_with_the_merge_word_filled(tmp_path):
    # Axis: the merge word is Merge #<number> on a pr sheet and Merge stack #<number> on a stack sheet, in both places the line names it.
    assert "Answer Merge #214 or Not yet here in the chat, then say you're done. Merge #214 counts only once every item above is accepted;" in _prose_of(tmp_path, _sample("pr"))
    assert "Answer Merge stack #4 or Not yet here in the chat, then say you're done. Merge stack #4 counts only once" in _prose_of(tmp_path, _sample("stack"))


def test_prose_says_the_pr_moved_between_what_changed_and_the_walk(tmp_path):
    # Axis: a sheet with a previousCommit prints the changed heading and its paragraph, with the first 7 of that commit, after What changed and before the walk.
    sheet = _sample("pr")
    sheet["prSheet"]["previousCommit"] = "0123456789abcdef"
    out = _prose_of(tmp_path, sheet)
    paragraph = PR_WORDS["changed"].replace("{previous}", "0123456")
    heading = "**%s**" % PR_WORDS["changedHeading"]
    assert out.index("Describes commit") < out.index(heading) < out.index(paragraph) < out.index("**%s**" % PR_WORDS["walkHeading"])
    assert "0123456789" not in out
    assert PR_WORDS["changedHeading"] not in _prose_of(tmp_path, _sample("pr"))


# Bites on: a pr or stack card offering the discovery answers (Aligned) instead of the PR answers (Accept), or a discovery sheet offering Accept.
@pytest.mark.parametrize("kind", ["pr", "stack"])
def test_prose_offers_a_pr_card_the_pr_answers(tmp_path, kind):
    sheet = _sample(kind)
    out = _prose_of(tmp_path, sheet)
    labels = PR_ANSWER_WORDS["labels"]
    for card in sheet["cards"]:
        offered = ("a, b, c, or %s" % labels["something-else"]) if len(card["options"]) == 3 else (
            "a, b, or %s" % labels["something-else"] if card["options"] else "%s or %s" % (labels["accept"], labels["discuss"]))
        assert "   - Answer: %s\n" % offered in out, card["id"]
    assert "Aligned" not in out
    discovery = _prose_of(tmp_path, json.loads(SAMPLE.read_text(encoding="utf-8")))
    assert "Accept" not in discovery
    assert "Aligned" in discovery


def test_prose_offers_a_pr_card_without_options_accept_or_discuss(tmp_path):
    # Axis: a pr card with no options is offered exactly the words' accept and discuss labels, not the discovery pair.
    out = _prose_of(tmp_path, _sample("pr"))
    assert "   - Answer: Accept or Discuss\n" in out
    assert "Aligned or Discuss" not in out


def test_prose_of_a_pr_sheet_with_no_cards_says_nothing_is_to_be_accepted(tmp_path):
    # Axis: with zero cards the accepting heading is followed by the nothing-to-accept line, no item is numbered, and the verdict line is still printed.
    for kind in ("pr", "stack"):
        sheet = _sample(kind)
        sheet["cards"] = []
        out = _prose_of(tmp_path, sheet)
        assert "**%s**\n\n%s\n" % (PR_WORDS["acceptingHeading"], PR_WORDS["nothingToAccept"]) in out, kind
        assert not re.search(r"^1\. ", out, re.M), kind
        assert out.index(PR_WORDS["nothingToAccept"]) < out.index("**%s**" % PR_WORDS["verdictHeading"]) < out.index("Answer Merge"), kind


def test_prose_leaves_out_each_empty_part(tmp_path):
    # Axis: an empty caught list, walk, craft list, decided list and history leave out their headings; a stack still lists its PRs.
    for kind in ("pr", "stack"):
        sheet = _sample(kind)
        part = sheet["prSheet"]
        part["whatChanged"]["caught"], part["walk"], part["craft"], part["alreadyDecided"], part["history"] = [], [], [], [], []
        out = _prose_of(tmp_path, sheet)
        for heading in ("caughtHeading", "walkHeading", "craftHeading", "decidedHeading", "reviewHeading"):
            assert PR_WORDS[heading] not in out, (kind, heading)
        assert (PR_WORDS["prsHeading"] in out) == (kind == "stack")
        assert "**%s**" % PR_WORDS["whatChangedHeading"] in out and "**%s**" % PR_WORDS["verdictHeading"] in out


def test_prose_names_a_reviewer_with_no_family_as_family_unknown(tmp_path):
    # Axis: a null family reads as the words' family-unknown note, and a reviewer that is not independent adds its mark after it.
    sheet = _sample("pr")
    sheet["prSheet"]["whatChanged"]["reviewers"] = [{"name": "code-reviewer", "family": None, "ran": "engine-record"},
                                                    {"name": "design-reviewer", "family": None, "ran": "engine-record", "notIndependent": True}]
    out = _prose_of(tmp_path, sheet)
    assert "Reviewed by code-reviewer (%s); design-reviewer (%s, %s)." % (
        PR_WORDS["familyUnknown"], PR_WORDS["familyUnknown"], PR_WORDS["notIndependentMark"]) in out


def test_prose_shows_checks_on_no_commit_and_no_lane_as_the_page_does(tmp_path):
    # Axis: checks on no commit print their state alone, a null lane prints no lane line, and a lane with no reason prints without its colon.
    sheet = _sample("pr")
    facts = sheet["prSheet"]["whatChanged"]
    facts["ci"], facts["lane"], facts["laneReason"] = {"state": "none ran", "commit": None}, None, None
    out = _prose_of(tmp_path, sheet)
    assert "\nnone ran\n" in out and " lane" not in out and "CI " not in out
    facts["lane"] = "light"
    assert "\nlight lane\n" in _prose_of(tmp_path, sheet)


def test_prose_escapes_markdown_in_a_pr_sheets_text(tmp_path):
    # Axis: every string of a pr sheet's data file is escaped so it prints as typed.
    sheet = _sample("pr")
    sheet["prSheet"]["whatChanged"]["summary"] = "Adds *bold* and `code`"
    sheet["prSheet"]["craft"][0]["title"] = "A_b_c"
    sheet["prSheet"]["walk"][0]["title"] = "[link](x)"
    out = _prose_of(tmp_path, sheet)
    assert "Adds \\*bold\\* and \\`code\\`" in out and "A\\_b\\_c — " in out and "- \\[link\\](x)" in out


# Bites on: the CLI refusing a pr sheet, or printing nothing for it.
def test_cli_exits_zero_and_prints_the_prose_for_a_pr_sheet():
    for kind in ("pr", "stack"):
        result = _run(SAMPLES[kind])
        assert result.returncode == 0 and result.stderr == "", kind
        assert result.stdout.startswith("**%s**: " % _sample(kind)["title"]), kind
        assert result.stdout.endswith("\n") and not result.stdout.endswith("\n\n"), kind


# Bites on: a refusal for a malformed commit that is worded as the id rule, which names the wrong rule.
def test_a_malformed_commit_is_refused_by_the_commit_rule_not_the_id_rule(tmp_path):
    sheet = _sample("pr")
    sheet["prSheet"]["commit"] = "NOT-A-COMMIT"
    result = _render(tmp_path, sheet)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == 'PrSheet.commit has the value "NOT-A-COMMIT", which does not fit its rule: %s\n' % COMMIT_RULE
    assert "lowercase id" not in result.stderr


def test_a_malformed_card_id_keeps_the_id_wording(tmp_path):
    # Axis: a card id that breaks the schema's own id rule is still refused as an id.
    sheet = _sample("pr")
    sheet["cards"][0]["id"] = "Bad Id"
    result = _render(tmp_path, sheet)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == 'Cards[0].id ("Bad Id") is not a lowercase id of letters, digits and hyphens.\n'


def test_a_pattern_with_no_description_is_named_by_the_pattern(tmp_path, monkeypatch, capsys):
    # Axis: a pattern that is not the id rule and whose node has no description is worded "it must match the pattern <pattern>".
    schema = _planted_schema(lambda planted: planted["$defs"]["commit"].pop("description"))
    planted = tmp_path / "planted.schema.json"
    planted.write_text(json.dumps(schema), encoding="utf-8")
    sheet = _sample("pr")
    sheet["prSheet"]["commit"] = "xyz"
    (tmp_path / "sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
    module = _load_prose_module()
    monkeypatch.setattr(module, "SCHEMA", planted)
    assert module.main(["render", "--sheet", str(tmp_path / "sheet.json")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == 'PrSheet.commit has the value "xyz", which does not fit its rule: it must match the pattern ^[0-9a-f]{7,40}$\n'


def test_a_data_file_that_fails_the_check_is_still_refused_before_rendering(tmp_path):
    # Axis: a pr sheet that breaks a rule of the schema prints nothing on stdout and the problem on stderr, with exit 1.
    sheet = _sample("pr")
    del sheet["prSheet"]["walk"]
    result = _render(tmp_path, sheet)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == "PrSheet has no walk.\n"
