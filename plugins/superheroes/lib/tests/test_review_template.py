"""Guards for the review template page and its usage doc."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

THEME = Path(__file__).resolve().parents[2] / "theme"
TEMPLATE = THEME / "review-template.html"
USAGE_DOC = THEME / "review-template.md"

FORBIDDEN_PROPERTIES = (
    "font-family", "font-weight", "box-shadow", "letter-spacing", "text-transform", "color",
)


def _template_text():
    return TEMPLATE.read_text(encoding="utf-8")


def _style_blocks(text):
    return re.findall(r"<style[^>]*>(.*?)</style>", text, re.S | re.I)


def _style_rules(text):
    """(selector, [(property, value), ...]) for every rule in every style block."""
    rules = []
    for block in _style_blocks(text):
        block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
            pairs = re.findall(r"([a-zA-Z-]+)\s*:\s*([^;]+)", body)
            rules.append((selector.strip(), [(p.lower(), v.strip()) for p, v in pairs]))
    return rules


def _style_attribute_declarations(text):
    pairs = []
    for attribute in re.findall(r"""\bstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", text, re.I):
        body = attribute[0] or attribute[1]
        pairs += [(p.lower(), v.strip()) for p, v in re.findall(r"([a-zA-Z-]+)\s*:\s*([^;]+)", body)]
    return pairs


def _script_by_id(text, script_id):
    match = re.search(r'<script id="%s">(.*?)</script>' % re.escape(script_id), text, re.S)
    assert match, "no <script id=%s> in the template" % script_id
    return match.group(1)


def _card(card_id, **overrides):
    card = {
        "id": card_id,
        "callKind": "Plan check",
        "warning": False,
        "question": "Is this the right plan?",
        "context": {"now": "The plan is drafted.", "whyOwner": "Only you can pick.", "exactText": "Do the thing."},
        "images": [],
        "options": [
            {"id": "yes", "label": "Yes", "consequence": "We go ahead."},
            {"id": "no", "label": "No", "consequence": "We stop."},
        ],
    }
    card.update(overrides)
    return card


def _sheet(kind="plain", cards=None, **extra):
    sheet = {
        "schema": "superheroes-sheet/1",
        "kind": kind,
        "title": "Weekly plan",
        "cards": cards if cards is not None else [_card("plan-day"), _card("fridge-check")],
    }
    sheet.update(extra)
    return sheet


def _remainder_sheet():
    return _sheet("remainder", remainder={"roundsRun": 2, "fixesMade": 3, "unsettled": ["fridge-check"]})


def _final_sheet():
    return _sheet("final", final={
        "history": {"reviewRounds": 2, "fixesMade": 3, "vet": "The vet found nothing new."},
        "declinedFindings": [{"summary": "Rename the file", "reason": "The name is already used elsewhere."}],
        "approval": {"approvedBoard": True, "boardSavedWithSpec": True},
    })


def _with(sheet, mutate):
    clone = copy.deepcopy(sheet)
    mutate(clone)
    return clone


def _drop(card_index, *path):
    def mutate(sheet):
        target = sheet["cards"][card_index]
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]
    return mutate


def _set(card_index, *path_and_value):
    *path, value = path_and_value

    def mutate(sheet):
        target = sheet["cards"][card_index]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return mutate


def _run_check_sheet(fixtures, schema=None):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required to run checkSheet and is not on PATH")
    source = _script_by_id(_template_text(), "sheet-check")
    if schema is None:
        schema = (THEME / "sheet.schema.json").read_text(encoding="utf-8")
    else:
        schema = json.dumps(schema)
    program = source + "\nconst schema = %s;\nconsole.log(JSON.stringify(%s.map((sheet) => checkSheet(sheet, schema))));\n" % (schema, json.dumps(fixtures))
    result = subprocess.run([node], input=program, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


PAGE_HARNESS = r"""
class Node {
  constructor(tag) {
    this.tagName = tag;
    this.id = "";
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.children = [];
  }
  appendChild(child) {
    if (child.tagName === "#fragment") {
      child.children.splice(0).forEach((inner) => this.children.push(inner));
    } else {
      this.children.push(child);
    }
    return child;
  }
  replaceChildren(...nodes) {
    this.children = [];
    nodes.forEach((node) => this.appendChild(node));
  }
}
const elements = {};
["sheet-status", "sheet-error", "sheet-error-list", "sheet-cards", "sheet-title"].forEach((id) => {
  elements[id] = new Node("div");
  elements[id].id = id;
});
elements["sheet-status"].hidden = false;
elements["sheet-error"].hidden = true;
elements["sheet-title"].textContent = "Review sheet";
const document = {
  title: "Review sheet",
  getElementById: (id) => elements[id],
  createElement: (tag) => new Node(tag),
  createDocumentFragment: () => new Node("#fragment"),
};
const files = __FILES__;
async function fetch(name, options) {
  const file = files[name];
  if (file === undefined) return { ok: false, status: 404, text: async () => "" };
  if (file.reject) throw new Error("network down");
  if (file.hang) await new Promise(() => {});
  return { ok: file.status >= 200 && file.status < 300, status: file.status, text: async () => file.body };
}
__CHECK__
__PAGE__
(async () => {
  const settled = () => elements["sheet-status"].hidden === true || elements["sheet-error"].hidden === false;
  for (let tries = 0; tries < 20 && !settled(); tries += 1) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  const cards = elements["sheet-cards"].children.filter((child) => child.tagName === "article").map((article) => ({
    id: article.id,
    className: article.className,
    badgeClass: article.children[0].className,
    question: article.children.find((child) => child.tagName === "h2").textContent,
  }));
  console.log(JSON.stringify({
    settled: settled(),
    title: document.title,
    appBar: elements["sheet-title"].textContent,
    statusHidden: elements["sheet-status"].hidden,
    errorHidden: elements["sheet-error"].hidden,
    errors: elements["sheet-error-list"].children.map((item) => item.textContent),
    cards: cards,
  }));
  process.exit(0);
})();
"""


def _run_page(files):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required to run the page and is not on PATH")
    text = _template_text()
    page = re.search(r"<script>(.*?)</script>", text, re.S)
    assert page, "no unnamed <script> in the template"
    program = (
        PAGE_HARNESS.replace("__FILES__", json.dumps(files))
        .replace("__CHECK__", _script_by_id(text, "sheet-check"))
        .replace("__PAGE__", page.group(1))
    )
    result = subprocess.run([node], input=program, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _sample_files(sheet=None):
    sheet_text = (THEME / "sample-sheet.json").read_text(encoding="utf-8") if sheet is None else json.dumps(sheet)
    return {
        "sheet.json": {"status": 200, "body": sheet_text},
        "sheet.schema.json": {"status": 200, "body": (THEME / "sheet.schema.json").read_text(encoding="utf-8")},
    }


def _assert_error_shown(page):
    assert page["settled"], "the page never settled: %s" % page
    assert page["cards"] == []
    assert page["statusHidden"] is True
    assert page["errorHidden"] is False
    assert page["errors"], "the error box is empty"


# Bites on: a template carrying its own document skeleton, which the artifact host would nest inside its own.
def test_template_has_no_document_skeleton():
    text = _template_text()
    for tag in (r"<!doctype", r"<html\b", r"<head\b", r"<body\b"):
        assert not re.search(tag, text, re.I), "the template must not carry %s" % tag


# Bites on: the page losing its stylesheet link or its data-file fetch, or loading either from the wrong place.
def test_template_loads_the_stylesheet_and_data_file():
    text = _template_text()
    assert len(re.findall(r'<link rel="stylesheet" href="comic-panel\.css">', text)) == 1
    assert re.search(r"""fetchJson\(\s*['"]sheet\.json['"]""", text)
    assert re.search(r"""fetchJson\(\s*['"]sheet\.schema\.json['"]""", text)
    assert re.search(r"\bfetch\(\s*name\b", text)


# Bites on: the usage doc leaving the schema out of the published files, which the page now fetches at runtime.
def test_usage_doc_lists_the_schema_as_a_published_file():
    doc = USAGE_DOC.read_text(encoding="utf-8")
    assert '"sheet.schema.json": "<staged sheet.schema.json>"' in doc
    assert "`sheet.schema.json`" in doc.split("## Publishing a sheet", 1)[1]


# Bites on: the page restating any theme value (colour, font, border, shadow, spacing of letters, case) the stylesheet owns.
def test_template_restates_no_theme_value():
    text = _template_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text), "a colour literal"
    assert not re.search(r"\b(?:rgb|rgba|hsl|hsla)\(", text, re.I), "a colour function"
    for family in ("Bricolage", "Atkinson", "Plex"):
        assert family not in text, "the font family %s" % family

    rules = _style_rules(text)
    assert rules, "no style rules were parsed"
    declarations = [(sel, p, v) for sel, props in rules for p, v in props]
    declarations += [("style attribute", p, v) for p, v in _style_attribute_declarations(text)]
    for selector, prop, value in declarations:
        assert prop not in FORBIDDEN_PROPERTIES, "%s declares %s: %s" % (selector, prop, value)
        assert prop != "border" and not prop.startswith("border-"), "%s declares %s: %s" % (selector, prop, value)

    whole_file = r"(?<![\w-])(?:%s|border(?:-[a-z-]+)?)\s*:" % "|".join(FORBIDDEN_PROPERTIES)
    assert not re.search(whole_file, text), "a forbidden declaration somewhere in the file"

    backgrounds = [(sel, v) for sel, p, v in declarations if p.startswith("background")]
    assert backgrounds == [("body", "var(--sh-paper)")], backgrounds

    scripts = "".join(re.findall(r"<script[^>]*>(.*?)</script>", text, re.S))
    assert ".style." not in scripts and ".style[" not in scripts, "a script sets a style"
    assert not re.search(r"""setAttribute\(\s*['"]style['"]""", scripts), "a script sets a style attribute"


# Bites on: checkSheet trusting a data file it should reject, or rejecting a sheet that is valid.
def test_check_sheet():
    valid = [_remainder_sheet(), _final_sheet(), _sheet("plain")]
    valid.append(_with(_sheet(), _set(0, "context", "exactText", None)))
    valid.append(_with(_sheet(), _set(0, "recommendation", {"text": "Say yes.", "reason": "It is cheap.", "optionId": "yes"})))
    for index, problems in enumerate(_run_check_sheet(valid)):
        assert problems == [], "valid fixture %d was refused: %s" % (index, problems)

    red = [
        ("missing title", _with(_sheet(), lambda s: s.pop("title")), None),
        ("empty cards", _sheet(cards=[]), None),
        ("missing question", _with(_sheet(), _drop(1, "question")), "fridge-check"),
        ("warning not boolean", _with(_sheet(), _set(1, "warning", "yes")), "fridge-check"),
        ("missing exactText key", _with(_sheet(), _drop(1, "context", "exactText")), "fridge-check"),
        ("exactText empty string", _with(_sheet(), _set(1, "context", "exactText", "")), "fridge-check"),
        ("duplicate card id", _sheet(cards=[_card("plan-day"), _card("plan-day")]), "plan-day"),
        ("duplicate option id", _with(_sheet(), _set(1, "options", [
            {"id": "yes", "label": "Yes", "consequence": "Go."},
            {"id": "yes", "label": "Also yes", "consequence": "Go again."},
        ])), "fridge-check"),
        ("unsettled naming a missing card", _with(_remainder_sheet(), lambda s: s["remainder"].update(unsettled=["no-such-card"])), "no-such-card"),
        ("optionId naming a missing option", _with(_sheet(), _set(1, "recommendation", {"text": "Pick it.", "reason": "Why not.", "optionId": "maybe"})), "fridge-check"),
        ("sheet as an array", [_sheet()], None),
    ]
    results = _run_check_sheet([sheet for _, sheet, _ in red])
    for (name, _, needle), problems in zip(red, results):
        assert len(problems) >= 1, "%s: no problem reported" % name
        if needle:
            assert any(needle in problem for problem in problems), "%s: no problem names %r: %s" % (name, needle, problems)


# Bites on: checkSheet passing a sheet because the fetched schema file is not a schema, or throwing on non-array cards/options.
def test_check_sheet_refuses_a_non_schema_and_malformed_lists():
    sheet = _sheet()
    for name, bad_schema in [("empty object", {}), ("array", []), ("boolean", True), ("string", "x"), ("the sample sheet", sheet)]:
        problems = _run_check_sheet([sheet], schema=bad_schema)[0]
        assert any("isn't a schema" in problem for problem in problems), "%s: %s" % (name, problems)

    shipped = json.loads((THEME / "sheet.schema.json").read_text(encoding="utf-8"))
    loose = {"properties": {}, "additionalProperties": True}
    bad_cards = _with(_sheet(), lambda s: s.update(cards="nope"))
    bad_options = _with(_sheet(), _set(0, "options", "nope"))
    results = _run_check_sheet([bad_cards, bad_options], schema=loose)
    assert any("cards" in problem for problem in results[0]), results[0]
    assert any("options" in problem for problem in results[1]), results[1]
    assert shipped["properties"]


# Bites on: spec provenance (requirement, ruling, issue, work-item numbers or handoff references) leaking into shipped text.
def test_shipped_files_carry_no_provenance():
    patterns = [
        r"\b(?:U?FR|NFR)-?\d", r"\bR\d{1,2}\b", r"\bC\d(?:-L\d)?\b", r"[Rr]uling \d",
        r"#\d{2,}", r"HANDOFF", r"discovery-notes",
    ]
    for path in (TEMPLATE, USAGE_DOC):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            assert not re.search(pattern, text), "%s matches %s" % (path.name, pattern)


# Bites on: the page's startup load or its render step going missing, so a valid sheet is never drawn.
def test_page_draws_the_sample_sheet():
    sample = json.loads((THEME / "sample-sheet.json").read_text(encoding="utf-8"))
    page = _run_page(_sample_files())
    assert page["settled"], "the page never settled: %s" % page
    assert page["title"] == sample["title"]
    assert page["appBar"] == sample["title"]
    assert len(page["cards"]) == len(sample["cards"])
    for drawn, card in zip(page["cards"], sample["cards"]):
        assert drawn["className"] == "sh-card"
        assert drawn["id"] == "card-" + card["id"]
        assert drawn["question"] == card["question"]
        assert ("sh-badge--warning" in drawn["badgeClass"]) == card["warning"]
    assert sample["cards"][0]["warning"] is True
    assert any(not card["warning"] for card in sample["cards"])
    assert page["statusHidden"] is True
    assert page["errorHidden"] is True
    assert page["errors"] == []


# Bites on: the error display (box shown, loading line hidden, no cards) for a data file that is not there.
def test_page_shows_an_error_for_a_missing_data_file():
    files = _sample_files()
    del files["sheet.json"]
    page = _run_page(files)
    _assert_error_shown(page)
    assert any("HTTP 404" in error for error in page["errors"]), page["errors"]
    assert page["appBar"] == "Review sheet"


# Bites on: the page drawing from, or crashing on, a data file that is not valid JSON.
def test_page_shows_an_error_for_invalid_json():
    files = _sample_files()
    files["sheet.json"] = {"status": 200, "body": '{"schema": '}
    page = _run_page(files)
    _assert_error_shown(page)
    assert any("valid JSON" in error for error in page["errors"]), page["errors"]


# Bites on: a failed network request escaping the page's handling instead of showing the error box.
def test_page_shows_an_error_for_a_rejected_fetch():
    files = _sample_files()
    files["sheet.json"] = {"reject": True}
    page = _run_page(files)
    _assert_error_shown(page)
    assert any("data file could not be loaded" in error for error in page["errors"]), page["errors"]


# Bites on: the page drawing a sheet its schema check refuses (here, two cards sharing an id).
def test_page_refuses_a_sheet_the_schema_rejects():
    sheet = json.loads((THEME / "sample-sheet.json").read_text(encoding="utf-8"))
    sheet["cards"][1]["id"] = sheet["cards"][0]["id"]
    page = _run_page(_sample_files(sheet))
    _assert_error_shown(page)
    assert any(sheet["cards"][0]["id"] in error for error in page["errors"]), page["errors"]


# Bites on: the harness's bounded wait, which must end and report an unsettled page rather than hang.
def test_page_that_never_settles_is_reported_unsettled():
    files = _sample_files()
    files["sheet.json"] = {"hang": True}
    page = _run_page(files)
    assert page["settled"] is False
    assert page["cards"] == []
