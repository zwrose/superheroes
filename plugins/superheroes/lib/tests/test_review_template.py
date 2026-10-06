"""Guards for the review template page and its usage doc."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from provenance_patterns import PROVENANCE_PATTERNS

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
    this.disabled = false;
    this.value = "";
    this.attributes = {};
    this.listeners = {};
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  addEventListener(type, listener) {
    (this.listeners[type] = this.listeners[type] || []).push(listener);
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
["sheet-status", "sheet-gate", "sheet-error", "sheet-error-list", "sheet-cards", "sheet-title"].forEach((id) => {
  elements[id] = new Node("div");
  elements[id].id = id;
});
elements["sheet-status"].hidden = false;
elements["sheet-gate"].hidden = true;
elements["sheet-error"].hidden = true;
elements["sheet-title"].textContent = "Review sheet";
const document = {
  title: "Review sheet",
  getElementById: (id) => elements[id],
  createElement: (tag) => new Node(tag),
  createDocumentFragment: () => new Node("#fragment"),
};

// The fake host runtime. Each test says how `use("db")` and `use("user")` behave through `host`, and
// drives the store's calls through the controlled promises logged in `setLog` and `reads`.
const host = __HOST__;
// The page's own timers can be replaced by a clock the scenario advances (`host.fakeTimers`); the
// harness itself always waits on the real ones.
const realSetTimeout = setTimeout;
const fakeTimers = new Map();
let fakeNow = 0;
let fakeNext = 1;
if (host.fakeTimers) {
  globalThis.setTimeout = (fn, ms) => {
    const id = fakeNext;
    fakeNext += 1;
    fakeTimers.set(id, { at: fakeNow + (ms || 0), fn: fn });
    return id;
  };
  globalThis.clearTimeout = (id) => { fakeTimers.delete(id); };
}
const setLog = [];
const reads = [];
const uses = [];
function deferred() {
  const handle = {};
  handle.promise = new Promise((resolve, reject) => {
    handle.resolve = resolve;
    handle.reject = reject;
  });
  return handle;
}
function snapshotOf(docs) {
  return { docs: docs.map((doc) => ({ id: doc.id, exists: true, data: () => doc.data })), size: docs.length, empty: docs.length === 0 };
}
const readModes = Array.isArray(host.read) ? host.read.slice() : [host.read];
const fakeStore = {
  doc: (path) => ({
    set: (body) => {
      const call = deferred();
      call.path = path;
      call.body = JSON.parse(JSON.stringify(body));
      setLog.push(call);
      if (host.set === "ok") call.resolve();
      return call.promise;
    },
  }),
  collection: (name) => ({
    get: () => {
      const read = deferred();
      read.name = name;
      reads.push(read);
      const mode = readModes.length > 1 ? readModes.shift() : readModes[0];
      if (mode === "docs") read.resolve(snapshotOf(host.docs));
      if (mode === "reject") read.reject({ code: "unavailable", message: "the read failed" });
      return read.promise;
    },
  }),
};
const window = {};
if (host.claude !== "missing") {
  window.claude = host.claude === "no-use" ? {} : {
    use: (name) => {
      uses.push(name);
      if (name === "db") {
        if (host.db === "throw") throw new Error("use threw");
        if (host.db === "reject") return Promise.reject(new Error("no db"));
        return Promise.resolve(host.db === "null" ? null : fakeStore);
      }
      if (name === "user") {
        if (host.user === "null") return Promise.resolve(null);
        if (host.user === "reject") return Promise.reject(new Error("no user"));
        return Promise.resolve({
          isOwner: () => {
            if (host.user === "is-owner-throws") throw new Error("isOwner threw");
            if (host.user === "is-owner-rejects") return Promise.reject(new Error("isOwner failed"));
            return Promise.resolve(host.user === "owner");
          },
        });
      }
      return Promise.resolve(null);
    },
  };
}
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

// What a test's scenario can do and see. A disabled control ignores `click` and `type`, as a browser
// would; `fire` ignores the disabled flag so a test can prove the page guards itself too.
function* walk(node) {
  yield node;
  for (const child of node.children) yield* walk(child);
}
const hasClass = (node, name) => node.className.split(/\s+/).includes(name);
const fire = (node, type) => (node.listeners[type] || []).forEach((listener) => listener({ type: type, target: node }));
const tools = {
  sets: setLog,
  reads: reads,
  uses: uses,
  snapshotOf: snapshotOf,
  fire: fire,
  hasClass: hasClass,
  all: (node) => [...walk(node)],
  tick: () => new Promise((resolve) => realSetTimeout(resolve, 0)),
  sleep: (ms) => new Promise((resolve) => realSetTimeout(resolve, ms)),
  advance: async (ms) => {
    const target = fakeNow + ms;
    for (;;) {
      const due = [...fakeTimers.entries()].filter((entry) => entry[1].at <= target).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      fakeTimers.delete(due[0]);
      fakeNow = due[1].at;
      due[1].fn();
      await new Promise((resolve) => realSetTimeout(resolve, 0));
    }
    fakeNow = target;
    await new Promise((resolve) => realSetTimeout(resolve, 0));
  },
  text: (node) => [...walk(node)].filter((item) => item.children.length === 0).map((item) => item.textContent).filter((item) => item !== "").join(" "),
  card: (id) => elements["sheet-cards"].children.find((article) => article.id === "card-" + id),
  buttons: (id) => tools.card(id).children.find((child) => hasClass(child, "answer-row")).children,
  note: (id) => tools.card(id).children.find((child) => child.tagName === "textarea"),
  saveLine: (id) => tools.card(id).children.find((child) => hasClass(child, "save-line")),
  saveText: (id) => tools.text(tools.saveLine(id)),
  tryAgain: (id) => tools.saveLine(id).children.find((child) => child.tagName === "button"),
  click: (node) => {
    if (node.disabled) return false;
    fire(node, "click");
    return true;
  },
  type: (node, value, kind) => {
    if (node.disabled) return false;
    node.value = value;
    fire(node, kind);
    return true;
  },
  button: (id, label) => tools.buttons(id).find((button) => button.textContent === label),
  state: (id) => ({
    labels: tools.buttons(id).map((button) => button.textContent),
    pressed: tools.buttons(id).map((button) => button.getAttribute("aria-pressed")),
    classes: tools.buttons(id).map((button) => button.className),
    disabled: tools.buttons(id).map((button) => button.disabled).concat([tools.note(id).disabled]),
    note: tools.note(id).value,
  }),
  parts: (id) => tools.card(id).children.map((child) => {
    if (hasClass(child, "sh-label")) return "label:" + child.textContent;
    return child.tagName + (child.className ? "." + child.className.split(/\s+/).join(".") : "");
  }),
  gate: () => {
    const line = elements["sheet-gate"];
    const retry = line.children.find((child) => child.tagName === "button");
    return { hidden: line.hidden, message: line.children.length ? line.children[0].textContent : "", retry: retry };
  },
  setLog: () => setLog.map((call) => ({ path: call.path, body: call.body })),
};
const scenario = async (t) => {
__SCENARIO__
};

(async () => {
  const settled = () => elements["sheet-status"].hidden === true || elements["sheet-error"].hidden === false;
  for (let tries = 0; tries < 20 && !settled(); tries += 1) {
    await new Promise((resolve) => realSetTimeout(resolve, 50));
  }
  await tools.tick();
  await tools.tick();
  const cards = elements["sheet-cards"].children.filter((child) => child.tagName === "article").map((article) => ({
    id: article.id,
    className: article.className,
    badgeClass: article.children[0].className,
    question: article.children.find((child) => child.tagName === "h2").textContent,
  }));
  const result = await scenario(tools);
  console.log(JSON.stringify({
    result: result === undefined ? null : result,
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


OWNER_HOST = {"claude": "present", "db": "store", "user": "owner", "read": "docs", "docs": [], "set": "ok"}


def _run_page(files, host=None, scenario="return null;"):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required to run the page and is not on PATH")
    text = _template_text()
    page = re.search(r"<script>(.*?)</script>", text, re.S)
    assert page, "no unnamed <script> in the template"
    program = (
        PAGE_HARNESS.replace("__HOST__", json.dumps(dict(OWNER_HOST, **(host or {}))))
        .replace("__SCENARIO__", scenario)
        .replace("__FILES__", json.dumps(files))
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
    for path in (TEMPLATE, USAGE_DOC):
        text = path.read_text(encoding="utf-8")
        for pattern in PROVENANCE_PATTERNS:
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


def _planted(mutate):
    schema = json.loads((THEME / "sheet.schema.json").read_text(encoding="utf-8"))
    mutate(schema)
    return schema


def _plant_at(*path, **rule):
    def mutate(schema):
        target = schema
        for key in path:
            target = target[key]
        target.update(rule)
    return mutate


def _assert_names(problems, keyword, pointer):
    assert any('"%s"' % keyword in problem and " at %s," % pointer in problem for problem in problems), (
        "no problem names %r at %s: %s" % (keyword, pointer, problems)
    )


# Bites on: the page drawing cards against a schema that carries a rule its reader does not check.
def test_page_refuses_a_schema_with_an_unknown_rule():
    schema = _planted(_plant_at("$defs", "card", "properties", "question", maxLength=200))
    files = _sample_files()
    files["sheet.schema.json"] = {"status": 200, "body": json.dumps(schema)}
    page = _run_page(files)
    _assert_error_shown(page)
    pointer = "#/$defs/card/properties/question"
    assert any('"maxLength"' in error and pointer in error for error in page["errors"]), page["errors"]


def _unsupported_rule_cases():
    def definitions(schema):
        schema["definitions"] = {"spare": {"type": "string", "maxLength": 3}}

    def all_of(schema):
        schema["allOf"].append({"type": "object", "maxLength": 3})

    def any_of(schema):
        schema["allOf"].append({"anyOf": [{"type": "object"}, {"type": "null", "maxLength": 3}]})

    def reached_ref(schema):
        schema["examples"] = [{"type": "string", "maxLength": 0}]
        schema["properties"]["title"] = {"$ref": "#/examples/0"}

    declined = ("properties", "final", "properties", "declinedFindings")
    return [
        ("E1-root", _plant_at(maxLength=3), "maxLength", "#"),
        ("E2-defs-member", _plant_at("$defs", "id", maxLength=3), "maxLength", "#/$defs/id"),
        ("E3-unreferenced-definitions-member", definitions, "maxLength", "#/definitions/spare"),
        ("E4-properties", _plant_at("properties", "title", maxLength=3), "maxLength", "#/properties/title"),
        ("E4-nested-properties", _plant_at("$defs", "card", "properties", "question", maxLength=3), "maxLength", "#/$defs/card/properties/question"),
        ("E5-items", _plant_at(*declined, "items", maxLength=3), "maxLength", "#/properties/final/properties/declinedFindings/items"),
        ("E6-allOf-member", all_of, "maxLength", "#/allOf/3"),
        ("E7-anyOf-member", any_of, "maxLength", "#/allOf/3/anyOf/1"),
        ("E8-if", _plant_at("allOf", 0, "if", maxLength=3), "maxLength", "#/allOf/0/if"),
        ("E9-then", _plant_at("allOf", 0, "then", maxLength=3), "maxLength", "#/allOf/0/then"),
        ("E10-not", _plant_at("allOf", 0, "then", "not", maxLength=3), "maxLength", "#/allOf/0/then/not"),
        ("E11-ref-target-outside-the-walked-containers", reached_ref, "maxLength", "#/examples/0"),
        ("E13-ref-without-hash-slash", _plant_at("properties", "title", **{"$ref": "defs/id"}), "$ref", "#/properties/title"),
        ("E13-ref-with-a-tilde-segment", _plant_at("properties", "title", **{"$ref": "#/$defs/a~1b"}), "$ref", "#/properties/title"),
        ("E13-ref-that-does-not-resolve", _plant_at("properties", "title", **{"$ref": "#/$defs/nowhere"}), "$ref", "#/properties/title"),
        ("E14-boolean-sub-schema", _plant_at("properties", title=True), "properties", "#/properties/title"),
        ("E15-items-as-a-list", _plant_at("properties", "cards", items=[{"type": "object"}]), "items", "#/properties/cards"),
        ("E16-additionalProperties-as-an-object", _plant_at("properties", "remainder", additionalProperties={"type": "string"}), "additionalProperties", "#/properties/remainder"),
        ("E18-root-id", _plant_at(**{"$id": "https://example.test/sheet"}), "$id", "#"),
        ("E18-nested-id", _plant_at("properties", "title", **{"$id": "https://example.test/title"}), "$id", "#/properties/title"),
        ("E17-else", _plant_at("allOf", 0, **{"else": {"type": "object"}}), "else", "#/allOf/0"),
        ("E19-minLength-not-a-number", _plant_at("properties", "title", minLength="1"), "minLength", "#/properties/title"),
        ("E19-uniqueItems-not-a-boolean", _plant_at("properties", "title", uniqueItems="yes"), "uniqueItems", "#/properties/title"),
        ("E19-pattern-not-a-regex", _plant_at("properties", "title", pattern="["), "pattern", "#/properties/title"),
    ]


# Bites on: the reader skipping a rule it does not implement, at any position it walks or a $ref reaches.
@pytest.mark.parametrize(
    "mutate,keyword,pointer",
    [pytest.param(mutate, keyword, pointer, id=name) for name, mutate, keyword, pointer in _unsupported_rule_cases()],
)
def test_check_sheet_refuses_a_schema_rule_it_cannot_check(mutate, keyword, pointer):
    problems = _run_check_sheet([_sheet("plain")], schema=_planted(mutate))[0]
    _assert_names(problems, keyword, pointer)


# Bites on: a $ref cycle sending the reader into endless recursion, or a recursive schema being refused.
def test_check_sheet_ends_on_a_ref_cycle():
    cyclic = {
        "properties": {"node": {"$ref": "#/$defs/a"}},
        "$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"$ref": "#/$defs/a"}},
    }
    refused = _run_check_sheet([{"cards": [], "node": 1}, {"cards": []}], schema=cyclic)
    _assert_names(refused[0], "$ref", "#/$defs/b")
    assert refused[1] == refused[0], "the refusal changed with the data: %s" % refused
    tree = {
        "properties": {"child": {"$ref": "#/$defs/tree"}},
        "$defs": {"tree": {"type": "object", "properties": {"child": {"$ref": "#/$defs/tree"}}}},
    }
    assert _run_check_sheet([{"cards": [], "child": {"child": {}}}], schema=tree) == [[]]


# Bites on: a $ref cycle reached under not, if or anyOf being read as a mismatch, so the sheet is drawn.
@pytest.mark.parametrize("wrap", [
    {"not": {"$ref": "#/$defs/loop"}},
    {"if": {"$ref": "#/$defs/loop"}, "then": {"type": "object"}},
    {"anyOf": [{"$ref": "#/$defs/loop"}, {"type": "integer"}]},
    {"anyOf": [{"type": "integer"}, {"$ref": "#/$defs/loop"}]},
], ids=["not", "if", "anyOf-cycle-first", "anyOf-match-first"])
def test_check_sheet_does_not_draw_on_a_ref_cycle_under_a_condition(wrap):
    schema = {"properties": {"node": wrap}, "$defs": {"loop": {"$ref": "#/$defs/loop"}}}
    problems = _run_check_sheet([{"cards": [], "node": 1}], schema=schema)[0]
    assert problems != [], "a cycle under a condition drew the sheet"
    assert any('"$ref"' in problem and "#/$defs/loop" in problem and "can't check" in problem for problem in problems), problems


# Bites on: a recursive schema that descends through properties or items being refused as a cycle.
def test_check_sheet_accepts_a_recursion_that_descends_through_properties_or_items():
    schema = {
        "properties": {"node": {"$ref": "#/$defs/tree"}},
        "$defs": {"tree": {"type": "object", "properties": {"kids": {"type": "array", "items": {"$ref": "#/$defs/tree"}}}}},
    }
    assert _run_check_sheet([{"cards": [], "node": {"kids": [{"kids": []}]}}], schema=schema) == [[]]


# Bites on: an annotation keyword being refused, or read as a rule, at any position.
def test_check_sheet_allows_annotations_anywhere():
    annotations = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "T", "description": "D",
        "$comment": "C", "examples": [1], "default": 1, "$defs": {}, "definitions": {},
    }

    def mutate(schema):
        schema.update({key: copy.deepcopy(value) for key, value in annotations.items() if key not in ("$defs", "definitions")})
        schema["$defs"]["card"]["properties"]["question"].update(copy.deepcopy(annotations))
        schema["$defs"]["extra"] = {"type": "string"}
        schema["definitions"] = {"spare": {"title": "unused"}}

    valid = [_remainder_sheet(), _final_sheet(), _sheet("plain")]
    for index, problems in enumerate(_run_check_sheet(valid, schema=_planted(mutate))):
        assert problems == [], "valid fixture %d was refused: %s" % (index, problems)


# Bites on: an unfollowable $ref being read from a schema author's prose instead of from the schema's structure.
def test_check_sheet_ignores_schema_prose_that_reads_like_a_reference_failure():
    for ending in (" follows a rule this page can't find.", " follows a rule that leads back to itself."):
        sentinel = "The title" + ending
        branch_first = {"properties": {"title": {"anyOf": [
            {"if": {}, "then": {"const": "other"}, "description": sentinel},
            {"type": "string"},
        ]}}}
        assert _run_check_sheet([{"cards": [], "title": "A title"}], schema=branch_first) == [[]], ending
        failing = {"properties": {"title": {"if": {}, "then": {"const": "other"}, "description": sentinel}}}
        problems = _run_check_sheet([{"cards": [], "title": "A title"}], schema=failing)[0]
        assert problems == [sentinel], problems
        assert not any("can't be checked" in problem for problem in problems), problems


# Bites on: const and enum comparing compound values by identity instead of by content.
def test_check_sheet_compares_compound_const_and_enum_by_content():
    not_const = {"properties": {"tags": {"not": {"const": ["a"]}}}}
    results = _run_check_sheet([{"cards": [], "tags": ["a"]}, {"cards": [], "tags": ["b"]}], schema=not_const)
    assert results[0] != [] and results[1] == [], results
    not_enum = {"properties": {"tags": {"not": {"enum": [["a"], {"k": 1}]}}}}
    results = _run_check_sheet([{"cards": [], "tags": ["a"]}, {"cards": [], "tags": {"k": 1}}, {"cards": [], "tags": ["b"]}], schema=not_enum)
    assert results[0] != [] and results[1] != [] and results[2] == [], results
    object_const = {"properties": {"tags": {"const": {"a": 1, "b": 2}}}}
    results = _run_check_sheet([{"cards": [], "tags": {"b": 2, "a": 1}}, {"cards": [], "tags": {"a": 1}}], schema=object_const)
    assert results[0] == [] and results[1] != [], results


# Bites on: uniqueItems treating two equal objects as different because their keys came in another order.
def test_check_sheet_uniqueitems_ignores_key_order():
    schema = {"properties": {"things": {"type": "array", "uniqueItems": True}}}
    results = _run_check_sheet(
        [{"cards": [], "things": [{"a": 1, "b": 2}, {"b": 2, "a": 1}]}, {"cards": [], "things": [{"a": 1}, {"a": 2}]}],
        schema=schema,
    )
    assert any("repeat" in problem for problem in results[0]), results[0]
    assert results[1] == [], results[1]


# Bites on: minLength counting UTF-16 units, so one character outside the basic plane counts as two.
def test_check_sheet_minlength_counts_characters():
    schema = {"properties": {"word": {"type": "string", "minLength": 2}}}
    results = _run_check_sheet([{"cards": [], "word": "\U0001F600"}, {"cards": [], "word": "ab"}], schema=schema)
    assert any("at least 2 characters" in problem for problem in results[0]), results[0]
    assert results[1] == [], results[1]


# Bites on: a reader message that says "must not be empty" for a field that needs more than one character, or that stops saying so for a field that needs one.
def test_reader_states_a_longer_minlength():
    def plant(schema):
        schema["properties"]["nickname"] = {"type": "string", "minLength": 3}

    fixtures = [
        _with(_sheet(), lambda s: s.update(nickname="ab")),
        _with(_sheet(), lambda s: s.update(nickname="")),
        _with(_sheet(), lambda s: s.update(nickname="abc")),
        _with(_sheet(), lambda s: s.update(title="")),
    ]
    results = _run_check_sheet(fixtures, schema=_planted(plant))
    assert results[0] == ["nickname must be at least 3 characters long."]
    assert results[1] == ["nickname must be at least 3 characters long."]
    assert results[2] == []
    assert results[3] == ["title must not be empty."]


# Bites on: a reader message that calls any failing pattern an id, or that names no rule for a pattern that is not the id rule.
def test_reader_states_a_non_id_pattern():
    def plant(schema):
        props = schema["properties"]
        props["code"] = {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Three capital letters."}
        props["tag"] = {"type": "string", "pattern": "^t-[0-9]+$"}
        props["blank"] = {"type": "string", "pattern": "^b$", "description": ""}

    fixtures = [
        _with(_sheet(), lambda s: s.update(code="abc")),
        _with(_sheet(), lambda s: s.update(tag="x")),
        _with(_sheet(), lambda s: s.update(blank="z")),
        _with(_sheet(), lambda s: s.update(code="ABC", tag="t-1", blank="b")),
        _with(_sheet(), _set(0, "id", "Bad_Id")),
    ]
    results = _run_check_sheet(fixtures, schema=_planted(plant))
    assert results[0] == ['code has the value "abc", which does not fit its rule: Three capital letters.']
    assert results[1] == ['tag has the value "x", which does not fit its rule: it must match the pattern ^t-[0-9]+$']
    assert results[2] == ['blank has the value "z", which does not fit its rule: it must match the pattern ^b$']
    assert results[3] == []
    assert results[4] == [
        'Card "Bad_Id".id has the value "Bad_Id", which is not a valid id (lowercase letters, digits and hyphens).'
    ]


def _answer_page(cards, scenario, host=None):
    page = _run_page(_sample_files(_sheet(cards=cards)), host=host, scenario=scenario)
    assert page["settled"], "the page never settled: %s" % page
    assert len(page["cards"]) == len(cards), page["cards"]
    return page["result"]


def _body(answer, option_id, note):
    return {"answer": answer, "optionId": option_id, "note": note}


def _write(card_id, answer, option_id, note):
    return {"path": "answers/" + card_id, "body": _body(answer, option_id, note)}


def _bare_card(card_id="bare-card"):
    return _card(card_id, options=[], context={"now": "Nothing is fixed yet.", "whyOwner": "It is your call.", "exactText": None})


# Bites on: the order and presence of a card's parts (badge, question, context, images, options, recommendation, answers, note, save line).
def test_card_draws_its_parts_in_order():
    full = _card(
        "full-card",
        images=[
            {"src": "plan.png", "alt": "The plan drawn out", "caption": "The draft plan"},
            {"src": "https://example.test/fridge.png", "alt": "The fridge"},
        ],
        recommendation={"text": "Say yes.", "reason": "It is cheap.", "optionId": "yes"},
    )
    result = _answer_page([full, _bare_card()], """
      const card = t.card("full-card");
      const nodes = t.all(card);
      return {
        full: t.parts("full-card"),
        bare: t.parts("bare-card"),
        images: nodes.filter((node) => node.tagName === "img").map((img) => [img.getAttribute("src"), img.getAttribute("alt")]),
        captions: nodes.filter((node) => node.tagName === "figcaption").map((node) => node.textContent),
        options: nodes.filter((node) => node.tagName === "li").map((item) => item.children.map((child) => child.textContent)),
        recommendation: nodes.find((node) => t.hasClass(node, "sheet-recommendation")).children.map((child) => child.textContent),
        noteLabelFor: card.children.find((child) => child.tagName === "label").getAttribute("for"),
        noteId: t.note("full-card").id,
      };
    """)
    assert result["full"] == [
        "span.sh-badge", "h2",
        "label:What's true now", "p", "label:Why it needs you", "p", "label:The exact text", "blockquote",
        "div.sheet-images",
        "label:Options", "ul",
        "label:Recommendation", "div.sheet-recommendation",
        "div.answer-row",
        "label:Note", "textarea.sh-field",
        "div.save-line",
    ]
    assert result["bare"] == [
        "span.sh-badge", "h2",
        "label:What's true now", "p", "label:Why it needs you", "p",
        "div.answer-row",
        "label:Note", "textarea.sh-field",
        "div.save-line",
    ]
    assert result["images"] == [["plan.png", "The plan drawn out"], ["https://example.test/fridge.png", "The fridge"]]
    assert result["captions"] == ["The draft plan"]
    assert result["options"] == [["Yes", "We go ahead."], ["No", "We stop."]]
    assert result["recommendation"] == ["Say yes.", "It is cheap."]
    assert result["noteLabelFor"] == result["noteId"]


# Bites on: the answer row gaining, losing or renaming a button, or a button losing its pressed state.
def test_answer_row_has_only_the_fixed_buttons():
    result = _answer_page([_card("plan-day"), _bare_card()], """
      const row = (id) => ({
        tags: t.buttons(id).map((button) => button.tagName),
        labels: t.buttons(id).map((button) => button.textContent),
        pressed: t.buttons(id).map((button) => button.getAttribute("aria-pressed")),
        classes: t.buttons(id).map((button) => button.className),
      });
      return { options: row("plan-day"), bare: row("bare-card") };
    """)
    assert result["options"]["labels"] == ["Aligned", "Discuss", "Yes", "No"]
    assert result["bare"]["labels"] == ["Aligned", "Discuss"]
    for row in result.values():
        assert set(row["tags"]) == {"button"}
        assert set(row["pressed"]) == {"false"}
        assert set(row["classes"]) == {"sh-button"}


# Bites on: an answer or note write that is not one whole document at answers/<card id>, or a pressed state that does not follow the last tap.
def test_owner_tap_writes_one_whole_document_per_card():
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      t.click(t.button("plan-day", "Yes"));
      await t.tick();
      t.click(t.button("plan-day", "Aligned"));
      await t.tick();
      const note = t.note("plan-day");
      t.type(note, "Use the blue one", "input");
      const afterInput = t.sets.length;
      t.type(note, "Use the blue one", "change");
      await t.tick();
      t.click(t.button("fridge-check", "No"));
      await t.tick();
      return {
        afterInput: afterInput,
        sets: t.setLog(),
        plan: t.state("plan-day"),
        fridge: t.state("fridge-check"),
        save: t.saveText("plan-day"),
        uses: t.uses,
      };
    """)
    assert result["uses"] == ["db", "user"]
    assert result["afterInput"] == 2, "typing wrote before its pause or its change"
    assert result["sets"] == [
        _write("plan-day", "option", "yes", ""),
        _write("plan-day", "aligned", None, ""),
        _write("plan-day", "aligned", None, "Use the blue one"),
        _write("fridge-check", "option", "no", ""),
    ]
    assert result["plan"]["pressed"] == ["true", "false", "false", "false"]
    assert result["plan"]["classes"][0] == "sh-button sh-button--main"
    assert result["plan"]["note"] == "Use the blue one"
    assert result["fridge"]["pressed"] == ["false", "false", "false", "true"]
    assert result["save"] == "Saved"


# Bites on: a typed note saving before its pause ends, or saving more than once for a burst of typing.
def test_typing_saves_once_after_a_pause():
    result = _answer_page([_card("plan-day")], """
      const note = t.note("plan-day");
      t.type(note, "a", "input");
      await t.sleep(600);
      t.type(note, "ab", "input");
      await t.sleep(600);
      const early = t.sets.length;
      const during = t.saveText("plan-day");
      await t.sleep(800);
      return { early: early, during: during, sets: t.setLog(), after: t.saveText("plan-day") };
    """)
    assert result["early"] == 0, "the pause timer was not reset by the second input"
    assert result["during"] == "Saving…"
    assert result["sets"] == [_write("plan-day", None, None, "ab")]
    assert result["after"] == "Saved"


# Bites on: "Saved" showing for a state that is not the latest, a second write in flight, or the older state being sent last.
def test_saved_shows_only_for_the_latest_state():
    result = _answer_page([_card("plan-day")], """
      t.click(t.button("plan-day", "Aligned"));
      const first = { sets: t.sets.length, save: t.saveText("plan-day") };
      t.click(t.button("plan-day", "Discuss"));
      const queued = { sets: t.sets.length, save: t.saveText("plan-day") };
      t.sets[0].resolve();
      await t.tick();
      const afterFirst = { sets: t.sets.length, save: t.saveText("plan-day"), body: t.sets[1] && t.sets[1].body };
      t.sets[1].resolve();
      await t.tick();
      const afterSecond = t.saveText("plan-day");
      t.click(t.button("plan-day", "Aligned"));
      return { first: first, queued: queued, afterFirst: afterFirst, afterSecond: afterSecond, cleared: t.saveText("plan-day") };
    """, host={"set": "pending"})
    assert result["first"] == {"sets": 1, "save": "Saving…"}
    assert result["queued"] == {"sets": 1, "save": "Saving…"}, "a second write started while the first was in flight"
    assert result["afterFirst"] == {"sets": 2, "save": "Saving…", "body": _body("discuss", None, "")}
    assert result["afterSecond"] == "Saved"
    assert result["cleared"] == "Saving…", "a new tap left Saved on screen"


# Bites on: a rejected write being hidden, a retry that does not send the latest state, or an older write's failure speaking for a newer one.
def test_failed_save_offers_retry_of_the_latest():
    result = _answer_page([_card("plan-day"), _card("fridge-check"), _card("third-card")], """
      const out = {};
      const failure = { code: "unavailable", message: "try later" };
      const badgeOf = (id) => t.saveLine(id).children.find((child) => t.hasClass(child, "sh-badge"));

      t.click(t.button("plan-day", "Aligned"));
      t.sets[0].reject(failure);
      await t.tick();
      const described = (node) => (node ? [node.className, node.textContent] : null);
      out.failed = { text: t.saveText("plan-day"), badge: described(badgeOf("plan-day")), retry: described(t.tryAgain("plan-day")) };
      if (!t.tryAgain("plan-day")) return out;
      t.click(t.tryAgain("plan-day"));
      out.retried = { sets: t.sets.length, body: t.sets[1].body, path: t.sets[1].path, save: t.saveText("plan-day") };
      t.sets[1].resolve();
      await t.tick();
      out.recovered = { save: t.saveText("plan-day"), retry: t.tryAgain("plan-day") !== undefined };

      // A held handle to the Try again button that a later change has already removed: its handler
      // must still send the latest state, not the one that failed.
      t.click(t.button("fridge-check", "Aligned"));
      t.sets[2].reject({ code: "invalid_argument", message: "no" });
      await t.tick();
      const held = t.tryAgain("fridge-check");
      t.type(t.note("fridge-check"), "later", "input");
      out.moved = { save: t.saveText("fridge-check"), retry: t.tryAgain("fridge-check") !== undefined };
      t.fire(held, "click");
      out.heldRetry = { sets: t.sets.length, write: t.setLog()[3] };
      t.sets[3].resolve();
      await t.tick();

      t.click(t.button("third-card", "Aligned"));
      t.click(t.button("third-card", "Discuss"));
      t.sets[4].reject(failure);
      await t.tick();
      out.afterOlder = { sets: t.sets.length, write: t.setLog()[5], save: t.saveText("third-card") };
      t.sets[5].reject({ code: "revoked", message: "gone" });
      await t.tick();
      out.afterNewer = { save: t.saveText("third-card"), retry: t.tryAgain("third-card") !== undefined };
      t.click(t.tryAgain("third-card"));
      out.thirdRetry = { sets: t.sets.length, write: t.setLog()[6] };
      return out;
    """, host={"set": "pending"})
    assert result["failed"]["text"].startswith("Not saved")
    assert result["failed"]["badge"] == ["sh-badge sh-badge--warning", "Not saved"]
    assert result["failed"]["retry"] == ["sh-button", "Try again"]
    assert "didn't reach the sheet" in result["failed"]["text"]
    assert result["retried"] == {"sets": 2, "body": _body("aligned", None, ""), "path": "answers/plan-day", "save": "Saving…"}
    assert result["recovered"] == {"save": "Saved", "retry": False}
    assert result["moved"] == {"save": "Saving…", "retry": False}
    assert result["heldRetry"] == {"sets": 4, "write": _write("fridge-check", "aligned", None, "later")}
    assert result["afterOlder"] == {"sets": 6, "write": _write("third-card", "discuss", None, ""), "save": "Saving…"}
    assert result["afterNewer"] == {"save": result["failed"]["text"], "retry": True}
    assert result["thirdRetry"] == {"sets": 7, "write": _write("third-card", "discuss", None, "")}


# Bites on: controls turning on before the saved answers are read and applied, or a restore that drops the saved note.
def test_controls_stay_disabled_until_answers_are_restored():
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      const states = () => t.state("plan-day").disabled.concat(t.state("fridge-check").disabled);
      const before = { gate: t.gate().message, disabled: states(), reads: t.reads.length, names: t.reads.map((read) => read.name) };
      t.fire(t.button("plan-day", "Aligned"), "click");
      t.note("plan-day").value = "sneaky";
      t.fire(t.note("plan-day"), "input");
      t.fire(t.note("plan-day"), "change");
      const forced = t.sets.length;
      const clicked = t.click(t.button("plan-day", "Aligned"));
      t.reads[0].resolve(t.snapshotOf([{ id: "plan-day", data: { answer: "option", optionId: "no", note: "Saved earlier" } }]));
      await t.tick();
      const after = { gate: t.gate().hidden, disabled: states(), plan: t.state("plan-day"), fridge: t.state("fridge-check") };
      t.click(t.button("plan-day", "Aligned"));
      await t.tick();
      return { before: before, forced: forced, clicked: clicked, after: after, sets: t.setLog() };
    """, host={"read": "pending"})
    assert result["before"]["gate"] == "Loading your saved answers…"
    assert result["before"]["disabled"] == [True] * 10
    assert result["before"]["reads"] == 1
    assert result["before"]["names"] == ["answers"], "the saved answers were read from another collection"
    assert result["forced"] == 0, "a control wrote while the saved answers were still loading"
    assert result["clicked"] is False
    assert result["after"]["gate"] is True
    assert result["after"]["disabled"] == [False] * 10
    assert result["after"]["plan"]["pressed"] == ["false", "false", "false", "true"]
    assert result["after"]["plan"]["note"] == "Saved earlier"
    assert result["after"]["fridge"]["pressed"] == ["false"] * 4
    assert result["sets"] == [_write("plan-day", "aligned", None, "Saved earlier")]


# Bites on: a failed read of the saved answers being treated as an empty collection, or its retry not re-reading.
def test_failed_restore_is_not_an_empty_sheet():
    docs = [{"id": "plan-day", "data": {"answer": "discuss", "optionId": None, "note": "n"}}]
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      const states = () => t.state("plan-day").disabled.concat(t.state("fridge-check").disabled);
      const gate = t.gate();
      const failed = { message: gate.message, hidden: gate.hidden, retry: gate.retry !== undefined, disabled: states(), reads: t.reads.length };
      t.fire(t.button("plan-day", "Aligned"), "click");
      const forced = t.sets.length;
      t.click(t.gate().retry);
      await t.tick();
      const recovered = { hidden: t.gate().hidden, reads: t.reads.length, names: t.reads.map((read) => read.name), disabled: states(), plan: t.state("plan-day") };
      return { failed: failed, forced: forced, recovered: recovered };
    """, host={"read": ["reject", "docs"], "docs": docs})
    assert result["failed"] == {
        "message": "Your saved answers couldn't be loaded.", "hidden": False, "retry": True, "disabled": [True] * 10, "reads": 1,
    }
    assert result["forced"] == 0
    assert result["recovered"]["hidden"] is True
    assert result["recovered"]["reads"] == 2
    assert result["recovered"]["names"] == ["answers", "answers"], "a read, or its retry, used another collection"
    assert result["recovered"]["disabled"] == [False] * 10
    assert result["recovered"]["plan"]["pressed"] == ["false", "true", "false", "false"]


# Bites on: a write that never answers blocking the card for good, a stalled write not showing Not saved, a stale write's outcome speaking for the card, or an older write that lands last leaving the store behind the latest state.
def test_stalled_save_shows_not_saved_and_the_latest_state_lands_last():
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      const out = {};
      t.click(t.button("plan-day", "Aligned"));
      await t.advance(9999);
      out.early = t.saveText("plan-day");
      await t.advance(1);
      out.stalled = { text: t.saveText("plan-day"), retry: t.tryAgain("plan-day") !== undefined };
      t.click(t.button("plan-day", "Discuss"));
      t.type(t.note("plan-day"), "x", "change");
      out.edited = { sets: t.sets.length, text: t.saveText("plan-day"), retry: t.tryAgain("plan-day") !== undefined };
      t.click(t.tryAgain("plan-day"));
      out.retried = { sets: t.sets.length, write: t.setLog()[1], text: t.saveText("plan-day") };
      t.sets[0].resolve();
      await t.tick();
      out.olderDone = { sets: t.sets.length, text: t.saveText("plan-day") };
      t.sets[1].resolve();
      await t.tick();
      out.newerDone = { sets: t.sets.length, write: t.setLog()[2], text: t.saveText("plan-day") };
      t.sets[2].resolve();
      await t.tick();
      out.final = t.saveText("plan-day");

      t.click(t.button("fridge-check", "Aligned"));
      await t.advance(10000);
      t.click(t.tryAgain("fridge-check"));
      t.sets[3].reject({ code: "unavailable", message: "late" });
      await t.tick();
      out.olderFailed = { sets: t.sets.length, text: t.saveText("fridge-check") };
      t.sets[4].resolve();
      await t.tick();
      out.second = t.saveText("fridge-check");
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["early"] == "Saving…"
    assert result["stalled"]["text"].startswith("Not saved") and result["stalled"]["retry"] is True
    assert result["edited"] == {"sets": 1, "text": result["stalled"]["text"], "retry": True}
    assert result["retried"] == {"sets": 2, "write": _write("plan-day", "discuss", None, "x"), "text": "Saving…"}
    assert result["olderDone"] == {"sets": 2, "text": "Saving…"}
    assert result["newerDone"] == {"sets": 3, "write": _write("plan-day", "discuss", None, "x"), "text": "Saving…"}
    assert result["final"] == "Saved"
    assert result["olderFailed"] == {"sets": 5, "text": "Saving…"}
    assert result["second"] == "Saved"


# Bites on: a read of the saved answers that never answers leaving the page waiting with no way out, a retry that cannot overlap it, or a late read result replacing what was applied.
def test_stalled_restore_offers_retry_and_applies_the_first_read_once():
    first = [{"id": "plan-day", "data": {"answer": "discuss", "optionId": None, "note": "from the retry"}}]
    late = [{"id": "plan-day", "data": {"answer": "aligned", "optionId": None, "note": "too late"}}]
    result = _answer_page([_card("plan-day")], """
      const out = {};
      await t.advance(9999);
      out.early = { message: t.gate().message, disabled: t.state("plan-day").disabled };
      await t.advance(1);
      const gate = t.gate();
      out.stalled = { message: gate.message, hidden: gate.hidden, retry: gate.retry !== undefined, disabled: t.state("plan-day").disabled, reads: t.reads.length };
      t.click(t.gate().retry);
      out.retried = { message: t.gate().message, reads: t.reads.length, names: t.reads.map((read) => read.name) };
      t.reads[1].resolve(t.snapshotOf(__FIRST__));
      await t.tick();
      out.applied = { hidden: t.gate().hidden, state: t.state("plan-day") };
      t.reads[0].resolve(t.snapshotOf(__LATE__));
      await t.tick();
      out.afterLate = t.state("plan-day");
      await t.advance(20000);
      out.afterTimer = { hidden: t.gate().hidden, reads: t.reads.length };
      return out;
    """.replace("__FIRST__", json.dumps(first)).replace("__LATE__", json.dumps(late)), host={"read": "pending", "fakeTimers": True})
    assert result["early"] == {"message": "Loading your saved answers…", "disabled": [True] * 5}
    assert result["stalled"] == {
        "message": "Your saved answers couldn't be loaded.", "hidden": False, "retry": True, "disabled": [True] * 5, "reads": 1,
    }
    assert result["retried"] == {"message": "Loading your saved answers…", "reads": 2, "names": ["answers", "answers"]}
    assert result["applied"]["hidden"] is True
    assert result["applied"]["state"]["disabled"] == [False] * 5
    assert result["applied"]["state"]["note"] == "from the retry"
    assert result["afterLate"] == result["applied"]["state"], "a late read replaced the applied answers"
    assert result["afterTimer"] == {"hidden": True, "reads": 2}


NOT_SAVED_HERE = "Answers can't be saved in this view."
READ_ONLY = "This sheet is read-only for you. Only its owner can answer."


# Bites on: a missing runtime, a missing store, or a viewer who is not the owner getting working controls.
@pytest.mark.parametrize("host,message", [
    pytest.param({"claude": "missing"}, NOT_SAVED_HERE, id="E1-no-window-claude"),
    pytest.param({"claude": "no-use"}, NOT_SAVED_HERE, id="E2-use-is-not-a-function"),
    pytest.param({"db": "null"}, NOT_SAVED_HERE, id="E3-store-is-null"),
    pytest.param({"db": "reject"}, NOT_SAVED_HERE, id="E4-use-db-rejects"),
    pytest.param({"db": "throw"}, NOT_SAVED_HERE, id="E4-use-db-throws"),
    pytest.param({"user": "null"}, READ_ONLY, id="E5-user-is-null"),
    pytest.param({"user": "viewer"}, READ_ONLY, id="E6-is-owner-false"),
    pytest.param({"user": "is-owner-rejects"}, READ_ONLY, id="E7-is-owner-rejects"),
    pytest.param({"user": "is-owner-throws"}, READ_ONLY, id="E7-is-owner-throws"),
    pytest.param({"user": "reject"}, READ_ONLY, id="E7-use-user-rejects"),
])
def test_non_owner_and_missing_store_cannot_answer(host, message):
    result = _answer_page([_card("plan-day"), _bare_card()], """
      const out = { states: [], parts: [] };
      ["plan-day", "bare-card"].forEach((id) => {
        out.states.push(t.state(id));
        out.parts.push(t.parts(id).length);
        t.buttons(id).forEach((button) => t.fire(button, "click"));
        t.note(id).value = "sneaky";
        t.fire(t.note(id), "input");
        t.fire(t.note(id), "change");
      });
      const gate = t.gate();
      out.gate = { hidden: gate.hidden, message: gate.message, retry: gate.retry !== undefined };
      out.sets = t.sets.length;
      out.reads = t.reads.length;
      return out;
    """, host=host)
    assert result["parts"] == [14, 10], "the cards did not draw"
    for state in result["states"]:
        assert all(state["disabled"]), state
    assert result["gate"] == {"hidden": False, "message": message, "retry": False}
    assert result["sets"] == 0, "a control wrote although the viewer cannot answer"
    assert result["reads"] == 0, "the answers were read for a viewer who cannot answer"


# Bites on: a saved answer that names no pick the card offers still restoring a pick, a note being lost, or an unknown card id breaking the restore.
def test_restore_ignores_answers_it_cannot_place():
    docs = [
        {"id": "plan-day", "data": {"answer": "maybe", "optionId": None, "note": "keep my note"}},
        {"id": "fridge-check", "data": {"answer": "option", "optionId": "ghost", "note": "n2"}},
        {"id": "no-such-card", "data": {"answer": "aligned", "optionId": None, "note": "x"}},
        {"id": "third-card", "data": {"answer": "option", "optionId": "yes", "note": 7}},
    ]
    result = _answer_page([_card("plan-day"), _card("fridge-check"), _card("third-card")], """
      const ids = ["plan-day", "fridge-check", "third-card"];
      const restored = ids.map((id) => t.state(id));
      const gateHidden = t.gate().hidden;
      for (const id of ids) {
        t.type(t.note(id), "edited " + id, "change");
        await t.tick();
      }
      return { restored: restored, gateHidden: gateHidden, sets: t.setLog() };
    """, host={"docs": docs})
    plan, fridge, third = result["restored"]
    assert result["gateHidden"] is True
    assert plan["pressed"] == ["false"] * 4 and plan["note"] == "keep my note"
    assert fridge["pressed"] == ["false"] * 4 and fridge["note"] == "n2"
    assert third["pressed"] == ["false", "false", "true", "false"] and third["note"] == ""
    assert all(not any(state["disabled"]) for state in result["restored"])
    assert result["sets"] == [
        _write("plan-day", None, None, "edited plan-day"),
        _write("fridge-check", None, None, "edited fridge-check"),
        _write("third-card", "option", "yes", "edited third-card"),
    ]


# Bites on: a sheet the schema check refuses still reaching for the store, or drawing a gate line.
def test_a_refused_sheet_touches_no_store():
    cards = [_card("plan-day"), _card("plan-day")]
    page = _run_page(_sample_files(_sheet(cards=cards)), scenario="""
      return { uses: t.uses, reads: t.reads.length, sets: t.sets.length, gateHidden: t.gate().hidden };
    """)
    _assert_error_shown(page)
    assert page["result"] == {"uses": [], "reads": 0, "sets": 0, "gateHidden": True}


# Bites on: the note being anything but a labelled textarea that wears the theme's field part.
def test_note_field_is_a_theme_part():
    result = _answer_page([_card("plan-day")], """
      const note = t.note("plan-day");
      return { tag: note.tagName, className: note.className };
    """)
    assert result == {"tag": "textarea", "className": "sh-field"}
    css = (THEME / "comic-panel.css").read_text(encoding="utf-8")
    match = re.search(r"(?m)^\.sh-field\s*\{([^{}]*)\}", css)
    assert match, "comic-panel.css defines no .sh-field part"
    declared = {prop.lower(): value.strip() for prop, value in re.findall(r"([a-zA-Z-]+)\s*:\s*([^;]+);", match.group(1))}
    assert declared.get("min-height") == "var(--sh-touch)", declared
    token = r"var\(--sh-[a-z-]+\)"
    for prop in ("font-family", "background", "color"):
        assert re.fullmatch(token, declared.get(prop, "")), "%s: %s" % (prop, declared.get(prop))
    assert re.sub(token, "", declared.get("border", "")).split() == ["solid"], declared.get("border")
    for name in re.findall(r"var\((--sh-[a-z-]+)\)", match.group(1)):
        assert re.search(r"(?m)^\s*%s\s*:" % re.escape(name), css), "%s is not a theme token" % name
