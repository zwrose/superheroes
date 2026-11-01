"""Guards for the review sheet data file's schema and its sample."""
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import sheet_prose
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


PR = "properties/prSheet/properties/"

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
    "context sections": "properties/cards/items/properties/context",
    "context section title": "properties/cards/items/properties/context/items/properties/title",
    "context section blocks": "properties/cards/items/properties/context/items/properties/blocks",
    "images": "properties/cards/items/properties/images",
    "options": "properties/cards/items/properties/options",
    "option consequence":
        "properties/cards/items/properties/options/items/properties/consequence",
    "recommendation": "properties/cards/items/properties/recommendation",
    "recommendation reason":
        "properties/cards/items/properties/recommendation/properties/reason",
    "pr sheet": "properties/prSheet",
    "pr number": PR + "number",
    "pr commit": PR + "commit",
    "previous commit": PR + "previousCommit",
    "what changed": PR + "whatChanged",
    "what changed summary": PR + "whatChanged/properties/summary",
    "reviewers": PR + "whatChanged/properties/reviewers",
    "reviewer name": PR + "whatChanged/properties/reviewers/items/properties/name",
    "reviewer family": PR + "whatChanged/properties/reviewers/items/properties/family",
    "reviewer ran": PR + "whatChanged/properties/reviewers/items/properties/ran",
    "reviewer not independent": PR + "whatChanged/properties/reviewers/items/properties/notIndependent",
    "caught": PR + "whatChanged/properties/caught",
    "rounds": PR + "whatChanged/properties/rounds",
    "stopped at cap": PR + "whatChanged/properties/stoppedAtCap",
    "ci": PR + "whatChanged/properties/ci",
    "ci state": PR + "whatChanged/properties/ci/properties/state",
    "ci commit": PR + "whatChanged/properties/ci/properties/commit",
    "lane": PR + "whatChanged/properties/lane",
    "lane reason": PR + "whatChanged/properties/laneReason",
    "craft decisions": PR + "craft",
    "already decided": PR + "alreadyDecided",
    "entry title": PR + "craft/items/properties/title",
    "entry detail": PR + "craft/items/properties/detail",
    "entry pr": PR + "craft/items/properties/pr",
    "review history": PR + "history",
    "walk": PR + "walk",
    "walk stop id": PR + "walk/properties/stops/items/properties/id",
    "walk stop title": PR + "walk/properties/stops/items/properties/title",
    "walk stop pr": PR + "walk/properties/stops/items/properties/pr",
    "stack prs": PR + "prs",
    "stack pr number": PR + "prs/items/properties/number",
    "stack pr title": PR + "prs/items/properties/title",
    "stack pr commit": PR + "prs/items/properties/commit",
    "option sends back": "properties/cards/items/properties/options/items/properties/sendsBack",
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
    assert len(CENSUS) == 57
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
    ("card-section-missing-title", lambda s: s["cards"][2]["context"][0].pop("title")),
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
        "title": "Tool-lending app spec review",
        "final": {
            "history": {"reviewRounds": 4, "fixesMade": 9, "vet": "The vet found nothing to fix."},
            "declinedFindings": [
                {"summary": "Add a late-fee counter.", "reason": "It is outside the app's scope."}
            ],
            "approval": {"approvedBoard": True, "boardSavedWithSpec": False},
        },
        "cards": [card],
    }
    plain = {
        "schema": "superheroes-sheet/1",
        "kind": "plain",
        "title": "Tool-lending app spec review",
        "cards": [card],
    }
    assert errors_for(final) == []
    assert errors_for(plain) == []


@pytest.mark.parametrize("path", [SCHEMA_PATH, SAMPLE_PATH, THEME / "sheet-words.json"], ids=lambda p: p.name)
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
        "title": "Tool-lending app spec review",
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


def with_context(context):
    sheet = copy.deepcopy(load_sample())
    sheet["cards"][2]["context"] = context
    return sheet


def test_card_context_needs_no_fixed_fields():
    # Axis: a card's context is any list of titled sections, with no fixed heading and no required section, so an empty list is accepted by both readers.
    sections = [{"title": "What you're accepting", "blocks": [
        {"paragraph": "You are choosing how same-day returns count."},
        {"bullets": ["Fewer tools", "More repeats"]}]}]
    for context in (sections, []):
        sheet = with_context(context)
        assert errors_for(sheet) == [], context
        assert check_sheet_problems(sheet) == [], context


def test_old_fixed_context_is_refused():
    # Axis: the old context object with now, whyOwner and exactText is no longer a context, in both readers.
    sheet = with_context({"now": "Something.", "whyOwner": "Because.", "exactText": None})
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []


BAD_CONTEXT_PIECES = [
    {"blocks": [{"paragraph": "x", "bullets": ["y"]}], "title": "T"},
    {"blocks": [{"heading": "x"}], "title": "T"},
    {"blocks": [{"bullets": []}], "title": "T"},
    {"blocks": [{"paragraph": ""}], "title": "T"},
    {"blocks": [{"quote": ""}], "title": "T"},
    {"blocks": [], "title": "T"},
    {"blocks": [{"paragraph": "x"}]},
    {"blocks": [{"paragraph": "x"}], "title": ""},
]
BAD_CONTEXT_IDS = ["two-kinds", "unknown-key", "empty-bullets", "empty-paragraph", "empty-quote",
                   "no-blocks", "no-title", "empty-title"]


@pytest.mark.parametrize("section", BAD_CONTEXT_PIECES, ids=BAD_CONTEXT_IDS)
def test_block_holds_exactly_one_kind(section):
    # Axis: a block with two kinds or an unknown key, an empty list or string, and a section with no blocks or no title are each refused by both readers.
    sheet = with_context([section])
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []


def test_something_else_answer_document():
    # Axis: the stored answer may be something-else, and then it names no option.
    assert document_errors("answer", {"answer": "something-else", "optionId": None, "note": ""}) == []
    assert document_errors("answer", {"answer": "something-else", "optionId": "x", "note": ""}) != []


def test_the_retired_verdict_definitions_are_gone():
    # Axis: the schema has one verdict document, so no draft definition and no sent-answer definition remain, and nothing points at them.
    schema = load_schema()
    assert "draftVerdict" not in schema["$defs"] and "sentAnswer" not in schema["$defs"]
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "draftVerdict" not in text and "sentAnswer" not in text and "/sends" not in text and "draft-verdict" not in text


BASE_COMMIT = "662d4487027238eadb0f63825ec0a7fd7bbcbf92"
SCHEMA_IN_REPO = "plugins/superheroes/theme/sheet.schema.json"


def pr_card(card_id, options):
    return {
        "id": card_id,
        "callKind": "Leftover",
        "warning": False,
        "question": "What happens to this leftover?",
        "context": [{"title": "Where it stands", "blocks": [{"paragraph": "It reads one way."}]}],
        "images": [],
        "options": options,
    }


def pr_options():
    return [
        {"id": "keep-it", "label": "Keep it", "consequence": "Ships as is.", "sendsBack": False},
        {"id": "fix-before-merge", "label": "Fix before merge", "consequence": "The PR goes back.", "sendsBack": True},
    ]


def walk_stop(stop_id, pr, **more):
    return {"id": stop_id, "key": stop_id + "-0123456789ab", "title": "The " + stop_id, "pr": pr, "group": "On your phone", "kind": "try", "steps": ["Open it"],
            "expect": "It works.", "pictures": [], **more}


def walk_body(stops):
    return {"open": {"label": "Open the test shop"}, "picturesFrom": "the advisor's own account", "stops": stops}


def pr_body():
    return {
        "number": 1724,
        "commit": "662d4487",
        "whatChanged": {
            "summary": "Adds a sheet for one PR.",
            "reviewers": [{"name": "reviewer-one", "family": "claude", "ran": "engine-record", "notIndependent": False}],
            "caught": ["A missing edge."],
            "rounds": 2,
            "stoppedAtCap": False,
            "ci": {"state": "green", "commit": "662d4487"},
            "lane": "full",
            "laneReason": "It changes a schema.",
        },
        "craft": [{"title": "Kept the words in one file", "detail": "Both readers share it."}],
        "alreadyDecided": [{"title": "One sheet per PR", "detail": "The owner ruled so."}],
        "history": ["2 rounds ran."],
        "walk": walk_body([walk_stop("schema", 1724)]),
    }


def pr_sheet():
    return {
        "schema": "superheroes-sheet/1",
        "kind": "pr",
        "title": "PR 1724",
        "prSheet": pr_body(),
        "cards": [pr_card("leftover", pr_options()), pr_card("closure", [])],
    }


def stack_sheet():
    body = pr_body()
    body["number"] = 1700
    body["walk"] = walk_body([walk_stop("schema", 1724), walk_stop("builder", 1725)])
    body["prs"] = [{"number": 1724, "title": "The schema", "commit": "662d4487"},
                   {"number": 1725, "title": "The builder", "commit": "abcdef0"}]
    sheet = pr_sheet()
    sheet["kind"] = "stack"
    sheet["prSheet"] = body
    return sheet


def pr_mutated(change, build):
    sheet = build()
    change(sheet)
    return sheet


def test_pr_and_stack_sheets_validate_on_both_readers():
    # Axis: a well-formed pr sheet and stack sheet, with options that all say sendsBack and a card with none, are accepted by the schema and the page's check.
    for sheet in (pr_sheet(), stack_sheet()):
        assert errors_for(sheet) == [], sheet["kind"]
        assert check_sheet_problems(sheet) == [], sheet["kind"]


def pr_sheet_without_pr_sheet(sheet):
    del sheet["prSheet"]


def stack_without_prs(sheet):
    del sheet["prSheet"]["prs"]


def pr_with_prs(sheet):
    sheet["prSheet"]["prs"] = stack_sheet()["prSheet"]["prs"]


def plain_with_pr_sheet(sheet):
    sheet["kind"] = "plain"


def pr_with_final(sheet):
    sheet["final"] = final_sheet()["final"]


PR_RED_FIXTURES = [
    ("pr-without-pr-sheet", pr_sheet, pr_sheet_without_pr_sheet),
    ("stack-without-prs", stack_sheet, stack_without_prs),
    ("pr-carrying-prs", pr_sheet, pr_with_prs),
    ("plain-carrying-pr-sheet", pr_sheet, plain_with_pr_sheet),
    ("pr-carrying-final", pr_sheet, pr_with_final),
    ("option-missing-sends-back", pr_sheet, lambda s: s["cards"][0]["options"][0].pop("sendsBack")),
    ("commit-not-hex", pr_sheet, lambda s: s["prSheet"].__setitem__("commit", "XYZ")),
    ("unknown-pr-sheet-field", pr_sheet, lambda s: s["prSheet"].__setitem__("extra", 1)),
    ("ci-commit-not-hex", pr_sheet, lambda s: s["prSheet"]["whatChanged"]["ci"].__setitem__("commit", "XYZ")),
]


@pytest.mark.parametrize("build, change", [(b, c) for _, b, c in PR_RED_FIXTURES], ids=[n for n, _, _ in PR_RED_FIXTURES])
def test_pr_sheet_red_fixtures_are_refused_by_both_readers(build, change):
    # Axis: each way of breaking the pr or stack sheet's kind rules or field shapes is refused by the schema and by the page's check.
    sheet = pr_mutated(change, build)
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []


def carried_pr_sheet(build=pr_sheet):
    sheet = build()
    sheet["prSheet"]["previousCommit"] = "abcdef0"
    sheet["prSheet"]["carriedForward"] = {"sheets": ["a" * 64, "b" * 64], "date": "2026-09-30", "moved": "The branch was brought current with main.",
                                          "whyNotMaterial": "Main added only a README line."}
    return sheet


def test_a_pr_or_stack_sheet_with_a_carried_forward_verdict_validates_on_both_readers():
    # Axis: a pr sheet and a stack sheet that carry a verdict forward (with previousCommit) are accepted by the schema and the page's check.
    for build in (pr_sheet, stack_sheet):
        sheet = carried_pr_sheet(build)
        assert errors_for(sheet) == [], sheet["kind"]
        assert check_sheet_problems(sheet) == [], sheet["kind"]


CARRIED_RED_FIXTURES = [
    ("carried-without-previous-commit", lambda s: s["prSheet"].pop("previousCommit")),
    ("carried-with-no-digests", lambda s: s["prSheet"]["carriedForward"].__setitem__("sheets", [])),
    ("carried-digest-not-hex", lambda s: s["prSheet"]["carriedForward"].__setitem__("sheets", ["XYZ"])),
    ("carried-digest-repeated", lambda s: s["prSheet"]["carriedForward"].__setitem__("sheets", ["a" * 64, "a" * 64])),
    ("carried-date-not-a-date", lambda s: s["prSheet"]["carriedForward"].__setitem__("date", "30 September")),
    ("carried-moved-empty", lambda s: s["prSheet"]["carriedForward"].__setitem__("moved", "")),
    ("carried-why-missing", lambda s: s["prSheet"]["carriedForward"].pop("whyNotMaterial")),
    ("carried-unknown-key", lambda s: s["prSheet"]["carriedForward"].__setitem__("extra", 1)),
]


@pytest.mark.parametrize("change", [c for _, c in CARRIED_RED_FIXTURES], ids=[n for n, _ in CARRIED_RED_FIXTURES])
def test_a_carried_forward_block_that_breaks_its_rules_is_refused_by_both_readers(change):
    # Axis: carriedForward without previousCommit, with no digest, a repeated or non-hex digest, a date that is not YYYY-MM-DD, an empty or missing text, or an unknown key is refused by the schema and by the page's check.
    sheet = carried_pr_sheet()
    change(sheet)
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []


def test_pr_sheet_accepts_no_cards_a_null_ci_commit_and_a_null_lane():
    # Axis: a pr or stack sheet with no cards, a null ci commit, and a null lane and lane reason is accepted by both readers.
    for build in (pr_sheet, stack_sheet):
        sheet = build()
        sheet["cards"] = []
        sheet["prSheet"]["whatChanged"]["ci"]["commit"] = None
        sheet["prSheet"]["whatChanged"]["lane"] = None
        sheet["prSheet"]["whatChanged"]["laneReason"] = None
        assert errors_for(sheet) == [], sheet["kind"]
        assert check_sheet_problems(sheet) == [], sheet["kind"]


def test_remainder_option_without_sends_back_is_still_accepted():
    # Axis: sendsBack stays optional off a pr or stack sheet, so a remainder sheet's option without it is accepted by both readers.
    sheet = load_sample()
    assert "sendsBack" not in json.dumps(sheet)
    assert sheet["kind"] == "remainder" and sheet["cards"][0]["options"]
    assert errors_for(sheet) == []
    assert check_sheet_problems(sheet) == []


@pytest.mark.parametrize("sample", ["sample-sheet.json", "sample-final-sheet.json"])
def test_discovery_samples_still_validate_on_both_readers(sample):
    # Axis: the discovery samples shipped with the page are accepted by the schema and the page's check.
    sheet = json.loads((THEME / sample).read_text(encoding="utf-8"))
    assert errors_for(sheet) == []
    assert check_sheet_problems(sheet) == []


def canonical(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"))


def without_descriptions(node):
    if isinstance(node, dict):
        return {key: without_descriptions(value) for key, value in node.items() if key != "description"}
    if isinstance(node, list):
        return [without_descriptions(item) for item in node]
    return node


def with_pr_values(name, node):
    """The base copy of an answer or verdict definition with the additions the pr and stack sheets made to it."""
    if name == "answer":
        node["properties"]["answer"]["enum"].insert(-1, "accept")
        for part in node["allOf"]:
            if "enum" in part["if"]["properties"]["answer"]:
                part["if"]["properties"]["answer"]["enum"].insert(-1, "accept")
        node["properties"]["revision"] = {"type": "string", "pattern": "^[0-9a-f]{16}$"}
    else:
        node["properties"]["verdict"]["enum"].insert(node["properties"]["verdict"]["enum"].index("approve") + 1, "merge")
        node["properties"]["covers"] = {"type": "array", "uniqueItems": True,
                                        "items": {"type": "string", "pattern": "^answers/[a-z0-9][a-z0-9-]*@[0-9a-f]{16}$"}}
        node["allOf"] = [{"if": {"properties": {"verdict": {"const": "merge"}}, "required": ["verdict"]}, "then": {"required": ["covers"]}}]
    return node


@pytest.mark.parametrize("name", ["answer", "verdict"])
def test_answer_and_verdict_definitions_differ_from_the_base_only_by_the_pr_values(name):
    # Axis: apart from their descriptions, the answer and verdict documents equal the base commit's with only accept (before null, in both answer enums), the optional revision on an answer, merge (after approve), and on a verdict the optional covers with the rule that a Merge has it added, because the page's readers still own them.
    base = subprocess.run(["git", "show", "%s:%s" % (BASE_COMMIT, SCHEMA_IN_REPO)], cwd=THEME,
                          capture_output=True, text=True, check=True).stdout
    expected = with_pr_values(name, without_descriptions(json.loads(base)["$defs"][name]))
    assert canonical(without_descriptions(load_schema()["$defs"][name])) == canonical(expected)


def test_accept_answer_document_names_no_option():
    # Axis: a pr sheet or a stack sheet card with no options may store accept, and then it names no option.
    assert document_errors("answer", {"answer": "accept", "optionId": None, "note": ""}) == []
    assert document_errors("answer", {"answer": "accept", "optionId": None, "note": "kept"}) == []


def test_accept_answer_with_an_option_is_refused():
    # Axis: accept is an answer other than option, so a document that pairs it with an option id is refused.
    assert document_errors("answer", {"answer": "accept", "optionId": "keep-it", "note": ""}) != []


def test_merge_is_a_valid_verdict():
    # Axis: a pr sheet or a stack sheet stores merge at verdict/<digest> like the final sheet stores approve, and the verdict list is approve, merge, not-yet, null.
    digest = "a" * 64
    assert document_errors("verdict", {"verdict": "merge", "note": "", "sheet": digest, "covers": []}) == []
    assert document_errors("verdict", {"verdict": "merge", "note": "", "sheet": digest}) != []
    assert load_schema()["$defs"]["verdict"]["properties"]["verdict"]["enum"] == ["approve", "merge", "not-yet", None]


PICTURE = {"src": "pictures/0123456789ab.png", "alt": "The cart", "caption": "Where you start"}
LOOK = {"kind": "look", "steps": [], "pictures": [{"missing": True, "alt": "The screen"}]}


def walk_sheet(change=None):
    """A pr sheet whose walk has a try stop with a picture and a look stop with a missing one, after change(walk)."""
    sheet = pr_sheet()
    sheet["prSheet"]["walk"] = walk_body([walk_stop("p1", 1724, pictures=[dict(PICTURE)]), walk_stop("f1", 1724, **copy.deepcopy(LOOK))])
    walk = sheet["prSheet"]["walk"]
    if change:
        change(walk)
    return sheet


def set_in(walk, key, value, stop=0):
    walk["stops"][stop][key] = value


GOOD_WALKS = {
    "try-and-look": lambda w: None,
    "optional": lambda w: set_in(w, "optional", True),
    "not-walked": lambda w: set_in(w, "notWalked", "It needs a sign-in."),
    "note-and-detail": lambda w: (w.update(note="Walk on your phone."), w["open"].update(url="http://shop.test", detail="Sign in.")),
    "jpeg-picture": lambda w: w["stops"][0]["pictures"][0].update(src="pictures/0123456789ab.jpeg"),
    "picture-without-caption": lambda w: w["stops"][0]["pictures"][0].pop("caption"),
    "missing-with-caption": lambda w: w["stops"][1]["pictures"][0].update(caption="Where it ends"),
    "no-pictures": lambda w: set_in(w, "pictures", []),
}
BAD_WALKS = {
    "look-with-steps": lambda w: set_in(w, "steps", ["Open it"], 1),
    "try-without-steps": lambda w: set_in(w, "steps", []),
    "empty-step": lambda w: set_in(w, "steps", [""]),
    "unknown-kind": lambda w: set_in(w, "kind", "scroll"),
    "picture-src-is-a-url": lambda w: w["stops"][0]["pictures"][0].update(src="https://example.com/a.png"),
    "picture-src-is-absolute": lambda w: w["stops"][0]["pictures"][0].update(src="/abs.png"),
    "picture-src-climbs": lambda w: w["stops"][0]["pictures"][0].update(src="pictures/../x.png"),
    "picture-src-not-12-hex": lambda w: w["stops"][0]["pictures"][0].update(src="pictures/abc.png"),
    "picture-src-upper-hex": lambda w: w["stops"][0]["pictures"][0].update(src="pictures/0123456789AB.png"),
    "picture-src-other-type": lambda w: w["stops"][0]["pictures"][0].update(src="pictures/0123456789ab.svg"),
    "picture-src-and-missing": lambda w: w["stops"][0]["pictures"][0].update(missing=True),
    "picture-missing-false": lambda w: w["stops"][1]["pictures"][0].update(missing=False),
    "picture-without-alt": lambda w: w["stops"][0]["pictures"][0].pop("alt"),
    "picture-unknown-key": lambda w: w["stops"][0]["pictures"][0].update(href="https://example.com"),
    "open-url-is-javascript": lambda w: w["open"].update(url="javascript:x"),
    "open-url-is-ftp": lambda w: w["open"].update(url="ftp://example.com"),
    "open-without-label": lambda w: w["open"].pop("label"),
    "walk-unknown-key": lambda w: w.update(extra=1),
    "walk-without-pictures-from": lambda w: w.pop("picturesFrom"),
    "no-stops": lambda w: w.update(stops=[]),
    "stop-unknown-key": lambda w: set_in(w, "extra", 1),
    "stop-without-key": lambda w: w["stops"][0].pop("key"),
    "stop-key-not-hashed": lambda w: set_in(w, "key", "p1"),
    "stop-without-pictures": lambda w: w["stops"][0].pop("pictures"),
    "stop-empty-group": lambda w: set_in(w, "group", ""),
    "stop-optional-not-boolean": lambda w: set_in(w, "optional", "yes"),
    "stop-not-walked-empty": lambda w: set_in(w, "notWalked", ""),
    "stop-pr-zero": lambda w: set_in(w, "pr", 0),
}


def test_walk_sheets_share_no_fixture_state():
    # Axis: a change made to one walk sheet's nested look stop never reaches the next sheet built, so one case cannot leak into another.
    walk_sheet(lambda w: w["stops"][1]["pictures"][0].update(missing=False))
    sheet = walk_sheet()
    assert errors_for(sheet) == [], errors_for(sheet)
    assert check_sheet_problems(sheet) == []
    assert LOOK["pictures"][0]["missing"] is True


def test_a_pr_sheet_may_have_no_walk():
    # Axis: a PR sheet with nothing to try has no walk part, and both readers accept it.
    sheet = pr_sheet()
    del sheet["prSheet"]["walk"]
    assert errors_for(sheet) == [] and check_sheet_problems(sheet) == []


@pytest.mark.parametrize("change", GOOD_WALKS.values(), ids=GOOD_WALKS.keys())
def test_good_walks_are_accepted_by_both_readers(change):
    # Axis: a try stop, a look stop, optional and not-walked marks and pictures that are copied or missing are accepted by the schema and the page's check.
    sheet = walk_sheet(change)
    assert errors_for(sheet) == [], errors_for(sheet)
    assert check_sheet_problems(sheet) == []


@pytest.mark.parametrize("change", BAD_WALKS.values(), ids=BAD_WALKS.keys())
def test_bad_walks_are_refused_by_both_readers(change):
    # Axis: each way of breaking the walk's stops, steps, pictures or open link is refused by the schema and by the page's check.
    baseline = walk_sheet()
    assert errors_for(baseline) == [] and check_sheet_problems(baseline) == []
    sheet = walk_sheet(change)
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []


def test_a_walk_is_an_object_not_a_list():
    # Axis: the old walk, a bare list of stops, is refused by both readers.
    sheet = walk_sheet(lambda w: None)
    sheet["prSheet"]["walk"] = sheet["prSheet"]["walk"]["stops"]
    assert errors_for(sheet) != [] and check_sheet_problems(sheet) != []


GOOD_WALK_ANSWERS = (
    [{"answer": a, "fix": None, "note": "", "shots": []} for a in ("works", "looks-right", "problem", "skip", None)]
    + [{"answer": "problem", "fix": f, "note": "It broke.", "shots": ["a1b2", "c3d4"]} for f in ("before-merge", "follow-up")])
BAD_WALK_ANSWERS = {
    "fix-on-works": {"answer": "works", "fix": "follow-up", "note": "", "shots": []},
    "fix-on-looks-right": {"answer": "looks-right", "fix": "before-merge", "note": "", "shots": []},
    "fix-on-skip": {"answer": "skip", "fix": "follow-up", "note": "", "shots": []},
    "fix-on-null": {"answer": None, "fix": "before-merge", "note": "", "shots": []},
    "unknown-answer": {"answer": "maybe", "fix": None, "note": "", "shots": []},
    "no-shots": {"answer": "works", "fix": None, "note": ""},
    "extra-key": {"answer": "works", "fix": None, "note": "", "shots": [], "extra": 1},
    "empty-shot-id": {"answer": "problem", "fix": None, "note": "", "shots": [""]},
}


@pytest.mark.parametrize("document", GOOD_WALK_ANSWERS, ids=lambda d: "%s-%s-%d-shots" % (d["answer"], d["fix"], len(d["shots"])))
def test_walk_answer_documents_are_accepted(document):
    # Axis: a stored walk answer is any answer with no fix, or a Problem with either fix, with the asset ids of its screenshots.
    assert document_errors("walkAnswer", document) == []


@pytest.mark.parametrize("document", BAD_WALK_ANSWERS.values(), ids=BAD_WALK_ANSWERS.keys())
def test_walk_answer_documents_are_refused(document):
    # Axis: a fix on anything but a Problem, an unknown answer or fix, a missing or extra member and an empty screenshot id are refused.
    assert document_errors("walkAnswer", document) != []


# --- the index, the answer revision and the Merge's covers ---

def index_row(**more):
    return {"number": 214, "kind": "pr", "title": "Retry a failed payment", "link": "https://sheets.example.test/pr-214",
            "state": "needs-you", "accepted": 1, "total": 2, "walked": 0, "walkTotal": 3, "mergesAt": 1, "caption": "1 of 2 accepted · merges first", **more}


def index_sheet():
    options = [{"id": "keep-visible", "label": "Keep them visible", "consequence": "Support can look up an old order."},
               {"id": "hide-them", "label": "Hide them", "consequence": "A refund needs an engineer."}]
    return {"schema": "superheroes-sheet/1", "kind": "index", "title": "Waiting on you",
            "index": {"rows": [index_row(), index_row(number=4, kind="stack", state="ready", mergesAt=None)]},
            "cards": [pr_card("old-orders", options)]}


def test_an_index_validates_on_all_three_readers():
    # Axis: a well-formed index, and one with no questions or no rows, is accepted by the schema, the page's check and the prose renderer's check.
    empty_rows, no_cards = index_sheet(), index_sheet()
    empty_rows["index"]["rows"] = []
    no_cards["cards"] = []
    for sheet in (index_sheet(), empty_rows, no_cards):
        assert errors_for(sheet) == [] and check_sheet_problems(sheet) == [] and sheet_prose.check_sheet(sheet) == []


def with_prs_block(sheet):
    sheet["prSheet"] = pr_body()


def with_remainder_block(sheet):
    sheet["remainder"] = {"roundsRun": 1, "fixesMade": 1, "unsettled": []}


def with_final_block(sheet):
    sheet["final"] = final_sheet()["final"]


def set_row(**more):
    return lambda sheet: sheet["index"]["rows"][0].update(more)


def pr_with_index(sheet):
    sheet["index"] = {"rows": []}


INDEX_RED_FIXTURES = [
    ("index-without-index", index_sheet, lambda s: s.pop("index")),
    ("index-with-pr-sheet", index_sheet, with_prs_block),
    ("index-with-remainder", index_sheet, with_remainder_block),
    ("index-with-final", index_sheet, with_final_block),
    ("pr-sheet-with-index", pr_sheet, pr_with_index),
    ("stack-sheet-with-index", stack_sheet, pr_with_index),
    ("plain-with-index", index_sheet, lambda s: s.__setitem__("kind", "plain")),
    ("index-card-without-options", index_sheet, lambda s: s["cards"][0].__setitem__("options", [])),
    ("index-option-with-sends-back", index_sheet, lambda s: s["cards"][0]["options"][0].__setitem__("sendsBack", False)),
    ("index-unknown-field", index_sheet, lambda s: s["index"].__setitem__("extra", 1)),
    ("index-without-rows", index_sheet, lambda s: s["index"].pop("rows")),
    ("row-bad-state", index_sheet, set_row(state="waiting")),
    ("row-http-link", index_sheet, set_row(link="http://sheets.example.test/pr-214")),
    ("row-link-with-a-space", index_sheet, set_row(link="https://sheets.example.test/a b")),
    ("row-relative-link", index_sheet, set_row(link="sheets/pr-214")),
    ("row-negative-count", index_sheet, set_row(accepted=-1)),
    ("row-negative-walk-total", index_sheet, set_row(walkTotal=-1)),
    ("row-fractional-count", index_sheet, set_row(total=1.5)),
    ("row-number-zero", index_sheet, set_row(number=0)),
    ("row-merges-at-zero", index_sheet, set_row(mergesAt=0)),
    ("row-bad-kind", index_sheet, set_row(kind="plain")),
    ("row-empty-title", index_sheet, set_row(title="")),
    ("row-unknown-field", index_sheet, set_row(extra=1)),
    ("row-missing-field", index_sheet, lambda s: s["index"]["rows"][0].pop("mergesAt")),
    ("row-missing-caption", index_sheet, lambda s: s["index"]["rows"][0].pop("caption")),
    ("row-empty-caption", index_sheet, set_row(caption="")),
    ("row-non-string-caption", index_sheet, set_row(caption=3)),
]


@pytest.mark.parametrize("build, change", [(b, c) for _, b, c in INDEX_RED_FIXTURES], ids=[n for n, _, _ in INDEX_RED_FIXTURES])
def test_index_red_fixtures_are_refused_by_all_three_readers(build, change):
    # Axis: each way of breaking the index's kind rules, its question cards or its rows is refused by the schema, the page's check and the prose renderer's check.
    sheet = pr_mutated(change, build)
    assert errors_for(sheet) != []
    assert check_sheet_problems(sheet) != []
    assert sheet_prose.check_sheet(sheet) != []


def test_the_kind_rules_name_the_index_beside_the_others():
    # Axis: the kind list ends with index, and its description names the index.
    kind = load_schema()["properties"]["kind"]
    assert kind["enum"] == ["remainder", "final", "plain", "pr", "stack", "index"] and "index" in kind["description"]
    assert "index" in load_schema()["properties"]["cards"]["description"]


def test_repeated_index_row_numbers_are_refused_by_the_prose_check():
    # Axis: the rule the schema cannot express is named in its description and refused once the sheet fits it.
    twice = index_sheet()
    twice["index"]["rows"][1]["number"] = 214
    assert errors_for(twice) == []
    assert sheet_prose.check_sheet(twice) == ["Index row number 214 is used more than once."]
    assert "row numbers are unique within the index" in load_schema()["description"]


REVISION = "0123456789abcdef"


@pytest.mark.parametrize("revision", [REVISION, "f" * 16])
def test_an_answer_may_carry_a_revision(revision):
    # Axis: a stored answer may hold a 16-character lowercase-hex revision beside answer, optionId and note.
    assert document_errors("answer", {"answer": "accept", "optionId": None, "note": "", "revision": revision}) == []


@pytest.mark.parametrize("revision", ["", "XYZ", "0123456789ABCDEF", "0123456789abcde", "0123456789abcdef0", "0123456789abcdeg", None, 5])
def test_a_malformed_revision_is_refused(revision):
    # Axis: a revision that is empty, upper case, short, long, non-hex, null or not a string is refused.
    assert document_errors("answer", {"answer": "accept", "optionId": None, "note": "", "revision": revision}) != []


def test_an_answer_without_a_revision_stays_valid():
    # Axis: discovery's stored answers carry no revision and still fit, because revision is optional.
    schema = load_schema()["$defs"]["answer"]
    assert "revision" in schema["properties"] and "revision" not in schema["required"]
    assert document_errors("answer", {"answer": "aligned", "optionId": None, "note": ""}) == []


COVERS = [f"answers/leftover@{REVISION}", f"answers/closure-1@{REVISION}"]


def merge_document(**more):
    return {"verdict": "merge", "note": "", "sheet": "a" * 64, **more}


def test_a_merge_names_the_answers_it_was_given_for():
    # Axis: a Merge needs covers (which may be empty on a sheet with nothing to accept); Not yet, Approve and a cleared verdict need none.
    assert document_errors("verdict", merge_document()) != []
    assert document_errors("verdict", merge_document(covers=COVERS)) == []
    assert document_errors("verdict", merge_document(covers=[])) == []
    for verdict in ("not-yet", "approve", None):
        assert document_errors("verdict", {"verdict": verdict, "note": "", "sheet": "a" * 64}) == []
        assert document_errors("verdict", {"verdict": verdict, "note": "", "sheet": "a" * 64, "covers": COVERS}) == []


@pytest.mark.parametrize("covers", [
    ["leftover@" + REVISION], ["answers/leftover"], ["answers/leftover@" + REVISION[:-1]], ["answers/leftover@" + REVISION.upper()],
    ["answers/Leftover@" + REVISION], ["answers/@" + REVISION], ["answers/leftover@" + REVISION + "0"], [REVISION], [5], [None],
    [COVERS[0], COVERS[0]], "answers/leftover@" + REVISION, None, {"answers/leftover": REVISION},
], ids=["no-prefix", "no-revision", "short", "upper", "upper-id", "no-id", "long", "bare-revision", "number", "null", "repeat", "string", "null-covers", "object"])
def test_malformed_covers_are_refused(covers):
    # Axis: covers that is not a list of unique answers/<card id>@<16 hex> strings is refused.
    assert document_errors("verdict", merge_document(covers=covers)) != []


@pytest.mark.parametrize("sample", sorted(p.name for p in THEME.glob("sample-*.json")))
def test_every_shipped_sample_passes_the_prose_renderers_check(sample):
    # Axis: each sample the plugin ships still fits the schema and the cross-field rules as sheet_prose reads them.
    sheet = json.loads((THEME / sample).read_text(encoding="utf-8"))
    assert sheet_prose.check_sheet(sheet) == []
    assert errors_for(sheet) == []


def test_walk_answers_by_kind_is_the_one_home_of_the_answers_each_stop_kind_offers():
    # Axis: the definition exists, lists a try stop's and a look stop's answers in button order, and says it is the one home of them.
    definition = load_schema()["$defs"]["walkAnswersByKind"]
    assert set(definition["properties"]) == {"try", "look"} and definition["additionalProperties"] is False
    for kind, found in definition["properties"].items():
        assert found["enum"] and len(set(found["enum"])) == len(found["enum"])
        assert sheet_prose.offered_walk_answers(kind) == found["enum"]
    assert "one home" in definition["description"] and "button order" in definition["description"]
    # Every answer a kind offers is one a stored walk answer can hold.
    stored = load_schema()["$defs"]["walkAnswer"]["properties"]["answer"]["enum"]
    assert {answer for found in definition["properties"].values() for answer in found["enum"]} <= set(stored)


def test_prose_follows_a_reordered_walk_answer_list(tmp_path, monkeypatch):
    # Axis: the prose renderer reads the walk answers from the schema, so a reordered list changes what it offers.
    schema = load_schema()
    schema["$defs"]["walkAnswersByKind"]["properties"]["try"]["enum"].reverse()
    path = tmp_path / "sheet.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(sheet_prose, "SCHEMA", path)
    assert sheet_prose.offered_walk_answers("try") == schema["$defs"]["walkAnswersByKind"]["properties"]["try"]["enum"]


# Bites on: the chat walk listing a stop's answers in a fixed order (or from a list of its own) instead of the schema's walkAnswersByKind order for the stop's kind.
def test_the_chat_walk_lists_each_stops_answers_in_the_reordered_schema_order(tmp_path, monkeypatch):
    # Axis: with the try list reversed in the schema, the try stop's Answers line reverses and the look stop's stays as the schema lists it.
    schema = load_schema()
    schema["$defs"]["walkAnswersByKind"]["properties"]["try"]["enum"].reverse()
    path = tmp_path / "schema" / "sheet.schema.json"
    path.parent.mkdir()
    path.write_text(json.dumps(schema), encoding="utf-8")
    fixtures = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
    built = tmp_path / "sheet.json"
    done = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "pr_sheet.py"), "build", "--record", str(fixtures / "record-big.json"),
                           "--pr-body", "214=" + str(fixtures / "body-none.md"), "--input", str(fixtures / "input-walk.json"), "--out", str(built)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
    sheet = json.loads(built.read_text(encoding="utf-8"))
    monkeypatch.setattr(sheet_prose, "SCHEMA", path)
    lines = sheet_prose.render(sheet).splitlines()
    labels = json.loads((Path(sheet_prose.__file__).resolve().parents[1] / "theme" / "sheet-words.json").read_text(encoding="utf-8"))["pr"]["walkAnswers"]["labels"]
    by_kind = load_schema()["$defs"]["walkAnswersByKind"]["properties"]
    stops = {stop["kind"]: stop["id"] for stop in sheet["prSheet"]["walk"]["stops"]}

    def answers_line(stop_id, order):
        return "   Answers: " + " / ".join("%s %s" % (stop_id, labels[a]) for a in order)

    canonical_try = by_kind["try"]["enum"]
    reversed_try = schema["$defs"]["walkAnswersByKind"]["properties"]["try"]["enum"]
    assert reversed_try != canonical_try  # the reorder must change the try stop's line, or this proves nothing
    assert answers_line(stops["try"], reversed_try) in lines
    assert answers_line(stops["look"], by_kind["look"]["enum"]) in lines
    assert answers_line(stops["try"], canonical_try) not in lines
