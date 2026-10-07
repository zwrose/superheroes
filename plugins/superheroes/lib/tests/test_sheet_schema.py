"""Guards for the review sheet data file's schema and its sample."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from provenance_patterns import PROVENANCE_PATTERNS

THEME = Path(__file__).resolve().parents[2] / "theme"
SCHEMA_PATH = THEME / "sheet.schema.json"
SAMPLE_PATH = THEME / "sample-sheet.json"
TEMPLATE_PATH = THEME / "review-template.html"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sample():
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def errors_for(sheet):
    return list(Draft202012Validator(load_schema()).iter_errors(sheet))


def check_sheet_problems(sheet):
    """Run the shipped page's checkSheet under node; returns its problem lines."""
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required to run checkSheet and is not on PATH")
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    match = re.search(r'<script id="sheet-check">(.*?)</script>', html, re.S)
    assert match, "no <script id=sheet-check> in the template"
    program = match.group(1) + "\nconsole.log(JSON.stringify(checkSheet(%s, %s)));\n" % (
        json.dumps(sheet), SCHEMA_PATH.read_text(encoding="utf-8"))
    result = subprocess.run([node], input=program, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def mutated(change):
    sheet = copy.deepcopy(load_sample())
    change(sheet)
    return sheet


def test_schema_is_valid_draft_2020_12():
    # Axis: the schema file is itself a well-formed draft 2020-12 schema.
    Draft202012Validator.check_schema(load_schema())


def test_sample_validates():
    # Axis: the shipped sample is accepted by the shipped schema.
    assert errors_for(load_sample()) == []


def test_sample_meets_integrity_rules():
    # Axis: the shipped sample passes the shipped page's check.
    assert check_sheet_problems(load_sample()) == []


CENSUS = {
    "sheet kind": "properties/kind",
    "title": "properties/title",
    "rounds run": "properties/remainder/properties/roundsRun",
    "fixes made": "properties/remainder/properties/fixesMade",
    "unsettled findings": "properties/remainder/properties/unsettled",
    "history review rounds": "properties/final/properties/history/properties/reviewRounds",
    "history fixes": "properties/final/properties/history/properties/fixesMade",
    "history vet": "properties/final/properties/history/properties/vet",
    "declined findings": "properties/final/properties/declinedFindings",
    "approved board": "properties/final/properties/approval/properties/approvedBoard",
    "board saved with spec": "properties/final/properties/approval/properties/boardSavedWithSpec",
    "card id": "properties/cards/items/properties/id",
    "kind of call": "properties/cards/items/properties/callKind",
    "warning badge": "properties/cards/items/properties/warning",
    "question": "properties/cards/items/properties/question",
    "context now": "properties/cards/items/properties/context/properties/now",
    "context why owner": "properties/cards/items/properties/context/properties/whyOwner",
    "context exact text": "properties/cards/items/properties/context/properties/exactText",
    "images": "properties/cards/items/properties/images",
    "options": "properties/cards/items/properties/options",
    "option consequence":
        "properties/cards/items/properties/options/items/properties/consequence",
    "recommendation": "properties/cards/items/properties/recommendation",
    "recommendation reason":
        "properties/cards/items/properties/recommendation/properties/reason",
}


def resolve_schema_path(schema, path):
    """Walk a slash path through the schema, following each $ref into $defs."""
    node = schema
    for step in path.split("/"):
        while "$ref" in node and step not in node:
            node = resolve_ref(schema, node["$ref"])
        node = node[step]
    while "$ref" in node and "type" not in node:
        node = resolve_ref(schema, node["$ref"])
    return node


def resolve_ref(schema, ref):
    node = schema
    for step in ref.removeprefix("#/").split("/"):
        node = node[step]
    return node


def test_every_sheet_item_has_a_schema_path():
    # Axis: each item the data file must carry has a property definition at a named schema path.
    assert len(CENSUS) == 23
    schema = load_schema()
    for item, path in CENSUS.items():
        try:
            node = resolve_schema_path(schema, path)
        except KeyError as missing:
            pytest.fail(f"{item}: no schema property at {path} (missing {missing})")
        assert isinstance(node, dict) and "type" in node, f"{item}: {path} is not a property"


def drop(key):
    return lambda sheet: sheet.pop(key)


def set_top(key, value):
    return lambda sheet: sheet.__setitem__(key, value)


def final_without_final(sheet):
    del sheet["remainder"]
    sheet["kind"] = "final"


RED_FIXTURES = [
    ("kind-other", set_top("kind", "other")),
    ("empty-title", set_top("title", "")),
    ("empty-cards", set_top("cards", [])),
    ("remainder-missing-block", drop("remainder")),
    ("final-without-final", final_without_final),
    ("plain-carrying-remainder", set_top("kind", "plain")),
    ("card-missing-exact-text", lambda s: s["cards"][2]["context"].pop("exactText")),
    ("card-id-bad", lambda s: s["cards"][0].__setitem__("id", "Bad Id")),
    ("unknown-top-level-field", set_top("extra", 1)),
    ("option-missing-consequence", lambda s: s["cards"][0]["options"][0].pop("consequence")),
    ("recommendation-missing-reason", lambda s: s["cards"][0]["recommendation"].pop("reason")),
    ("schema-version-2", set_top("schema", "superheroes-sheet/2")),
    ("warning-string", lambda s: s["cards"][0].__setitem__("warning", "yes")),
]


@pytest.mark.parametrize("change", [c for _, c in RED_FIXTURES], ids=[n for n, _ in RED_FIXTURES])
def test_rejects_invalid_sheets(change):
    # Axis: each way of breaking the shape, from kind to field types, draws at least one error.
    assert errors_for(mutated(change)) != []


KIND_FIXTURE_NAMES = ("remainder-missing-block", "final-without-final", "plain-carrying-remainder")
KIND_FIXTURES = [(n, c) for n, c in RED_FIXTURES if n in KIND_FIXTURE_NAMES]


@pytest.mark.parametrize("change", [c for _, c in KIND_FIXTURES], ids=[n for n, _ in KIND_FIXTURES])
def test_page_check_rejects_kind_fixtures(change):
    # Axis: the page's own check, not only the Python validator, refuses a sheet whose kind and block disagree.
    assert check_sheet_problems(mutated(change)) != []


def duplicate_card_id(sheet):
    sheet["cards"][1]["id"] = sheet["cards"][0]["id"]


def duplicate_option_id(sheet):
    sheet["cards"][0]["options"][1]["id"] = sheet["cards"][0]["options"][0]["id"]


def unsettled_names_missing_card(sheet):
    sheet["remainder"]["unsettled"].append("no-such-card")


def option_id_names_missing_option(sheet):
    sheet["cards"][0]["recommendation"]["optionId"] = "no-such-option"


INTEGRITY_FIXTURES = [
    ("duplicate-card-id", duplicate_card_id),
    ("duplicate-option-id", duplicate_option_id),
    ("unsettled-missing-card", unsettled_names_missing_card),
    ("option-id-missing-option", option_id_names_missing_option),
]


@pytest.mark.parametrize(
    "change", [c for _, c in INTEGRITY_FIXTURES], ids=[n for n, _ in INTEGRITY_FIXTURES])
def test_integrity_rules_reject(change):
    # Axis: each of the four integrity rules reports a problem when broken.
    assert check_sheet_problems(mutated(change)) != []


def test_final_and_plain_sheets_validate():
    # Axis: the kind conditionals accept a well-formed final sheet and plain sheet.
    card = copy.deepcopy(load_sample()["cards"][2])
    final = {
        "schema": "superheroes-sheet/1",
        "kind": "final",
        "title": "Weekly meal planner spec review",
        "final": {
            "history": {"reviewRounds": 4, "fixesMade": 9, "vet": "The vet found nothing to fix."},
            "declinedFindings": [
                {"summary": "Add a calorie counter.", "reason": "It is outside the planner's scope."}
            ],
            "approval": {"approvedBoard": True, "boardSavedWithSpec": False},
        },
        "cards": [card],
    }
    plain = {
        "schema": "superheroes-sheet/1",
        "kind": "plain",
        "title": "Weekly meal planner spec review",
        "cards": [card],
    }
    assert errors_for(final) == []
    assert errors_for(plain) == []


@pytest.mark.parametrize("path", [SCHEMA_PATH, SAMPLE_PATH], ids=lambda p: p.name)
def test_shipped_files_carry_no_provenance(path):
    # Axis: shipped text names no requirement, ruling, issue, handoff or work-item tokens.
    text = path.read_text(encoding="utf-8")
    for pattern in PROVENANCE_PATTERNS:
        assert re.search(pattern, text) is None, f"{path.name} matches {pattern}"


def final_sheet(cards=None, approved=True, saved=False):
    card = copy.deepcopy(load_sample()["cards"][2])
    return {
        "schema": "superheroes-sheet/1",
        "kind": "final",
        "title": "Weekly meal planner spec review",
        "final": {
            "history": {"reviewRounds": 4, "fixesMade": 9, "vet": "The vet found nothing to fix."},
            "declinedFindings": [],
            "approval": {"approvedBoard": approved, "boardSavedWithSpec": saved},
        },
        "cards": [card] if cards is None else cards,
    }


def test_final_sheet_may_have_no_cards():
    # Axis: a final sheet whose review left no calls is accepted by the schema and by the page's check.
    sheet = final_sheet(cards=[])
    assert errors_for(sheet) == []
    assert check_sheet_problems(sheet) == []


@pytest.mark.parametrize("kind", ["remainder", "plain"])
def test_remainder_and_plain_sheets_need_a_card(kind):
    # Axis: only a final sheet may have empty cards; a remainder or plain sheet with none is refused by both readers.
    sheet = copy.deepcopy(load_sample())
    sheet["kind"] = kind
    sheet["cards"] = []
    if kind == "plain":
        del sheet["remainder"]
    else:
        sheet["remainder"]["unsettled"] = []
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []


@pytest.mark.parametrize("approved, saved, accepted", [
    (False, True, False),
    (False, False, True),
    (True, False, True),
    (True, True, True),
])
def test_board_is_saved_with_the_spec_only_when_there_is_an_approved_board(approved, saved, accepted):
    # Axis: a final sheet cannot say the board is saved with the spec when it has no approved board, in both readers.
    sheet = final_sheet(approved=approved, saved=saved)
    assert (errors_for(sheet) == []) is accepted
    assert (check_sheet_problems(sheet) == []) is accepted


def document_errors(name, document):
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": load_schema()["$defs"],
              "$ref": "#/$defs/" + name}
    return list(Draft202012Validator(schema).iter_errors(document))


def test_verdict_document_holds_a_pick_or_none_a_note_and_the_digest():
    # Axis: the stored verdict is approve, not-yet or null (a note saved before any pick) with a note and the sheet digest it answers, and nothing else.
    digest = "a" * 64
    for verdict in ("approve", "not-yet", None):
        for note in ("", "a note"):
            good = {"verdict": verdict, "note": note, "sheet": digest}
            assert document_errors("verdict", good) == [], good


def test_verdict_document_refuses_what_is_not_a_verdict_on_one_revision():
    # Axis: a missing note or sheet, an extra key, an upper-case, short, long or non-hex digest, and an unknown verdict are all refused.
    digest = "a" * 64
    full = {"verdict": "approve", "note": "n", "sheet": digest}
    bad = [{key: value for key, value in full.items() if key != "note"},
           {key: value for key, value in full.items() if key != "sheet"},
           {key: value for key, value in full.items() if key != "verdict"},
           dict(full, extra=1), dict(full, answers=[]),
           dict(full, sheet="A" * 64), dict(full, sheet="a" * 63), dict(full, sheet="a" * 65), dict(full, sheet="g" * 64),
           dict(full, sheet=None), dict(full, sheet=5),
           dict(full, verdict="maybe"), dict(full, verdict="Approve"), dict(full, note=None), dict(full, note=3)]
    for document in bad:
        assert document_errors("verdict", document) != [], document


def test_the_retired_verdict_definitions_are_gone():
    # Axis: the schema has one verdict document, so no draft definition and no sent-answer definition remain, and nothing points at them.
    schema = load_schema()
    assert "draftVerdict" not in schema["$defs"] and "sentAnswer" not in schema["$defs"]
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "draftVerdict" not in text and "sentAnswer" not in text and "/sends" not in text and "draft-verdict" not in text
