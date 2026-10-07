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
        "context": {"now": "It reads one way.", "whyOwner": "Only you know.", "exactText": None},
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
        wanted = [card["question"], card["callKind"], card["context"]["now"], card["context"]["whyOwner"]]
        if card["context"]["exactText"] is not None:
            wanted.append(card["context"]["exactText"])
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
            context={"now": "It is open.", "whyOwner": "Only you know.", "exactText": "Plan: day"},
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
        "   - What's true now: It is open.",
        "   - Why it needs you: Only you know.",
        '   - The exact text: "Plan: day"',
        "   - Images: A chart (img/a.png); A map (https://x.test/b.png)",
        "   - Options:",
        "     - a. Yes: We plan.",
        "     - b. No: We skip.",
        "   - Recommendation: Skip it. It costs a day. (option b)",
        "   - Answer: Aligned, Discuss, or a, b",
        "",
        "2. **Another call?**",
        "   - Kind of call: Wording to confirm",
        "   - What's true now: It reads one way.",
        "   - Why it needs you: Only you know.",
        "   - Answer: Aligned, Discuss",
        "",
    ])
    result = _render(tmp_path, sheet)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    assert result.stderr == ""
    assert not [line for line in result.stdout.split("\n") if line != line.rstrip()]


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
    "unknown kind": (_mutated(lambda s: _set(s, "weekly", "kind")), "Kind must be one of remainder, final, plain."),
    "empty title": (_mutated(lambda s: _set(s, "", "title")), "Title must not be empty."),
    "empty cards": (_mutated(lambda s: _set(s, [], "cards")), "Cards must not be empty."),
    "missing context.now": (_mutated(lambda s: _drop(s, "cards", 1, "context", "now")), "Cards[1].context has no now."),
    "missing question": (_mutated(lambda s: _drop(s, "cards", 0, "question")), "Cards[0] has no question."),
    "missing warning": (_mutated(lambda s: _drop(s, "cards", 1, "warning")), "Cards[1] has no warning."),
    "wrong-typed warning": (_mutated(lambda s: _set(s, "yes", "cards", 1, "warning")), "Cards[1].warning must be boolean."),
    "wrong-typed option label": (_mutated(lambda s: _set(s, 7, "cards", 0, "options", 0, "label")),
                                 "Cards[0].options[0].label must be string."),
    "wrong-typed exactText": (_mutated(lambda s: _set(s, 3, "cards", 1, "context", "exactText")),
                              "Cards[1].context.exactText must be string or null."),
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
    _drop(sheet, "cards", 1, "context", "now")
    result = _render(tmp_path, sheet)
    assert result.returncode == 1
    assert result.stderr.splitlines() == ["Cards[0] has no question.", "Cards[1].context has no now."]


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
    sheet["cards"][0]["context"]["now"] = now
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
    assert "   - Answer: Aligned, Discuss, or " + ", ".join(letters) in lines
    assert [line for line in lines if line.startswith("   - Answer: Aligned, Discuss, or ")][0].endswith(", z, aa, ab")


HISTORY_LINE = "**How the spec got here.** The review ran 3 rounds and fixed 1 thing itself. The vet: The vet found nothing."
TRACES_BOARD_LINE = "- Every statement in the spec traces to your board, your framing, your rulings, your answers, or craft recorded for your veto."
TRACES_NO_BOARD_LINE = "- Every statement in the spec traces to your framing, your rulings, your answers, or craft recorded for your veto."
NEXT_LINE = ("**What happens next.** The advisor adds the breakdown to the same PR (or, where the project keeps specs outside "
             "the repo or gitignored, to the spec where it is kept) and vets it, then one merge word covers both.")
APPROVE_ANSWER_LINE = "- Answer: Approve or Not yet, with any note."
TWO_DECLINES = [("Add a counter.", "It is out of scope."), ("Add a theme.", "It costs too much.")]
DECLINED_LINES = ["**Declined findings (2).**", "- Add a counter. (why declined: It is out of scope.)",
                  "- Add a theme. (why declined: It costs too much.)", ""]
NO_DECLINES_LINES = ["**Declined findings.** No findings were declined.", ""]


def _plain_card_lines(number, question):
    return ["%d. **%s**" % (number, question), "   - Kind of call: Wording to confirm", "   - What's true now: It reads one way.",
            "   - Why it needs you: Only you know.", "   - Answer: Aligned, Discuss", ""]


TWO_CARD_LINES = _plain_card_lines(1, "Is this what you meant?") + _plain_card_lines(2, "Another call?")

FINAL_CASES = {
    "board saved, two declines, two cards": (
        _final_sheet(declined=TWO_DECLINES),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is saved with the spec.", APPROVE_ANSWER_LINE,
           "", NEXT_LINE]),
    "board not saved": (
        _final_sheet(declined=TWO_DECLINES, saved=False),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is not saved with the spec.", APPROVE_ANSWER_LINE,
           "", NEXT_LINE]),
    "no board": (
        _final_sheet(declined=TWO_DECLINES, approved=False, saved=False),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_NO_BOARD_LINE, APPROVE_ANSWER_LINE, "", NEXT_LINE]),
    "no declines": (
        _final_sheet(),
        ["**Spec review**: 2 items for you.", "", HISTORY_LINE, ""] + NO_DECLINES_LINES + TWO_CARD_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is saved with the spec.", APPROVE_ANSWER_LINE,
           "", NEXT_LINE]),
    "zero cards": (
        _final_sheet(declined=TWO_DECLINES, cards=[]),
        ["**Spec review**: 0 items for you.", "", HISTORY_LINE, ""] + DECLINED_LINES
        + ["**Approve the spec?**", TRACES_BOARD_LINE, "- The approved board is saved with the spec.", APPROVE_ANSWER_LINE,
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
