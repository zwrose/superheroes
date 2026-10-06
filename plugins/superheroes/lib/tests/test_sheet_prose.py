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
    assert result.stdout.startswith("**Spec review**: 1 item for you.\n\n1. **")


def _mutated(change):
    def build():
        sheet = _valid_sheet()
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
