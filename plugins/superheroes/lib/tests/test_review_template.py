"""Guards for the review template page and its usage doc."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import jsonschema
import pytest

from provenance_patterns import PROVENANCE_PATTERNS

THEME = Path(__file__).resolve().parents[2] / "theme"
TEMPLATE = THEME / "review-template.html"
USAGE_DOC = THEME / "review-template.md"
SHEET_SCHEMA = json.loads((THEME / "sheet.schema.json").read_text(encoding="utf-8"))
# The stored-answer rule lives in the sheet schema's $defs.answer and reaches the identifier rule by a pointer into the same file, so the validator is given the whole sheet schema and pointed at that definition.
ANSWER_SCHEMA = {"$schema": SHEET_SCHEMA["$schema"], "$defs": SHEET_SCHEMA["$defs"], "$ref": "#/$defs/answer"}
ANSWER_VALIDATOR = jsonschema.Draft202012Validator(ANSWER_SCHEMA)


def _validator_for(definition):
    return jsonschema.Draft202012Validator({"$schema": SHEET_SCHEMA["$schema"], "$defs": SHEET_SCHEMA["$defs"], "$ref": "#/$defs/" + definition})


# Every document the page may write, by where it goes. A write anywhere else fails the test that made it.
DRAFT_VERDICT_VALIDATOR = _validator_for("draftVerdict")
VERDICT_VALIDATOR = _validator_for("verdict")

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
["sheet-status", "sheet-gate", "sheet-error", "sheet-error-list", "sheet-cards", "sheet-title",
  "sheet-count", "sheet-why", "sheet-items", "sheet-stepper", "sheet-footer", "sheet-done",
  "sheet-history", "sheet-final"].forEach((id) => {
  elements[id] = new Node("div");
  elements[id].id = id;
});
elements["sheet-status"].hidden = false;
elements["sheet-gate"].hidden = true;
elements["sheet-error"].hidden = true;
elements["sheet-title"].textContent = "Review sheet";
// The sheet's own parts start hidden, with the classes the markup gives them, until a sheet is drawn.
const markupClasses = { "sheet-why": "sh-box", "sheet-items": "sheet-list", "sheet-stepper": "sheet-stepper", "sheet-footer": "sheet-footer", "sheet-done": "sh-box", "sheet-history": "sh-box" };
["sheet-count", "sheet-why", "sheet-items", "sheet-stepper", "sheet-footer", "sheet-done", "sheet-history", "sheet-final"].forEach((id) => {
  elements[id].hidden = true;
  elements[id].className = markupClasses[id] || "";
});
const document = {
  title: "Review sheet",
  getElementById: (id) => elements[id],
  createElement: (tag) => new Node(tag),
  createDocumentFragment: () => new Node("#fragment"),
};

// The fake host runtime. Each test says how `use("db")` and `use("user")` behave through `host`, and
// drives the store's calls through the controlled promises logged in `setLog` and `reads`. A collection's
// documents come from `host.collections` (collection name to its docs), or, when a test gives none, from
// `host.docs` for `answers` and nothing for any other collection. A read's mode is `host.read`, or the one
// `host.readByCollection` gives that collection; either may be a list, used one read at a time.
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
const ownerChecks = [];
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
const modeQueue = (given) => (Array.isArray(given) ? given.slice() : [given]);
const sharedModes = modeQueue(host.read);
const namedModes = {};
Object.keys(host.readByCollection || {}).forEach((name) => { namedModes[name] = modeQueue(host.readByCollection[name]); });
const nextMode = (queue) => (queue.length > 1 ? queue.shift() : queue[0]);
const docsOf = (name) => (host.collections ? host.collections[name] || [] : name === "answers" ? host.docs : []);
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
      const mode = nextMode(namedModes[name] || sharedModes);
      if (mode === "docs") read.resolve(snapshotOf(docsOf(name)));
      if (mode === "reject") read.reject({ code: "unavailable", message: "the read failed" });
      return read.promise;
    },
  }),
};
const unloadListeners = [];
const window = { addEventListener: (type, listener) => { if (type === "beforeunload") unloadListeners.push(listener); } };
if (host.claude !== "missing") {
  window.claude = host.claude === "no-use" ? {} : {
    use: (name) => {
      uses.push(name);
      if (name === "db") {
        if (host.db === "throw") throw new Error("use threw");
        if (host.db === "reject") return Promise.reject(new Error("no db"));
        if (host.hang === "db") return new Promise(() => {});
        return Promise.resolve(host.db === "null" ? null : fakeStore);
      }
      if (name === "user") {
        if (host.user === "null") return Promise.resolve(null);
        if (host.user === "reject") return Promise.reject(new Error("no user"));
        if (host.hang === "user") return new Promise(() => {});
        return Promise.resolve({
          isOwner: () => {
            ownerChecks.push("isOwner");
            if (host.user === "is-owner-throws") throw new Error("isOwner threw");
            if (host.user === "is-owner-rejects") return Promise.reject(new Error("isOwner failed"));
            if (host.hang === "isOwner") return new Promise(() => {});
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
  ownerChecks: ownerChecks,
  snapshotOf: snapshotOf,
  fire: fire,
  unload: () => {
    const event = { type: "beforeunload", defaultPrevented: false, returnValue: undefined, preventDefault() { this.defaultPrevented = true; } };
    unloadListeners.forEach((listener) => listener(event));
    return event.defaultPrevented;
  },
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
  // Nothing hidden is ever read as shown: a card's save line counts only while the card list, the card and the line are all shown.
  visible: (id, node) => [elements["sheet-cards"], tools.card(id), tools.saveLine(id)].some((item) => item.hidden) ? null : node,
  saveText: (id) => [elements["sheet-cards"], tools.card(id), tools.saveLine(id)].some((node) => node.hidden) ? "" : tools.text(tools.saveLine(id)),
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
  rowNodes: () => elements["sheet-items"].children.filter((child) => hasClass(child, "sheet-row")),
  open: (id) => {
    const index = elements["sheet-cards"].children.findIndex((article) => article.id === "card-" + id);
    const row = tools.rowNodes()[index];
    return row === undefined ? false : tools.click(row);
  },
  rows: () => tools.rowNodes().map((row) => {
    const described = (node) => (node ? [node.className, node.textContent] : null);
    const text = row.children.find((child) => hasClass(child, "sheet-row-text"));
    return {
      text: text ? text.textContent : null,
      pill: described(row.children.find((child) => hasClass(child, "sh-pill"))),
      badge: described(row.children.find((child) => hasClass(child, "sh-badge"))),
      current: row.getAttribute("aria-current") === "true" && hasClass(row, "is-current"),
      ariaCurrent: row.getAttribute("aria-current"),
      folded: hasClass(row, "is-folded"),
      className: row.className,
    };
  }),
  fold: () => {
    const node = elements["sheet-items"].children.find((child) => hasClass(child, "sheet-fold"));
    return {
      hidden: node.hidden,
      expanded: node.getAttribute("aria-expanded") === "true",
      aria: node.getAttribute("aria-expanded"),
      listExpanded: hasClass(elements["sheet-items"], "is-expanded"),
      first: elements["sheet-items"].children[0] === node,
      type: node.getAttribute("type"),
      className: node.className,
      text: tools.text(node),
      parts: node.children.map((child) => [child.className, child.textContent]),
    };
  },
  count: () => elements["sheet-count"].textContent,
  openCard: () => {
    const shown = elements["sheet-cards"].children.filter((article) => article.tagName === "article" && !article.hidden).map((article) => article.id.replace("card-", ""));
    return shown.length === 1 ? shown[0] : shown;
  },
  stepper: () => {
    const parts = elements["sheet-stepper"].children;
    const named = (label) => parts.find((child) => child.tagName === "button" && child.textContent === label);
    return {
      hidden: elements["sheet-stepper"].hidden,
      label: parts[0].textContent,
      prevDisabled: named("‹ Previous").disabled,
      nextDisabled: named("Next ›").disabled,
    };
  },
  why: () => ({
    hidden: elements["sheet-why"].hidden,
    heading: elements["sheet-why"].children.find((child) => child.tagName === "h2").textContent,
    text: elements["sheet-why"].children.find((child) => child.tagName === "p").textContent,
  }),
  done: () => ({
    hidden: elements["sheet-done"].hidden,
    message: elements["sheet-done"].children.find((child) => child.tagName === "p").textContent,
    body: {
      stepper: elements["sheet-stepper"].hidden,
      items: elements["sheet-items"].hidden,
      cards: elements["sheet-cards"].hidden,
      why: elements["sheet-why"].hidden,
      footer: elements["sheet-footer"].hidden,
    },
  }),
  // The page's own controls by name, so a scenario can press them as a person would.
  control: (name) => {
    const among = (host, label) => host.children.find((child) => child.tagName === "button" && child.textContent === label);
    return {
      previous: () => among(elements["sheet-stepper"], "‹ Previous"),
      next: () => among(elements["sheet-stepper"], "Next ›"),
      fold: () => elements["sheet-items"].children.find((child) => hasClass(child, "sheet-fold")),
      done: () => among(elements["sheet-footer"], "Done for now"),
      back: () => among(elements["sheet-done"], "Back to the sheet"),
      declines: () => elements["sheet-history"].children.find((child) => child.tagName === "button"),
    }[name]();
  },
  footer: () => ({ hidden: elements["sheet-footer"].hidden, caption: elements["sheet-footer"].children[0].textContent }),
  // The final sheet's parts: the history box (heading, paragraphs, the declines toggle and its list) and the last card.
  history: () => {
    const box = elements["sheet-history"];
    const kids = box.children;
    const toggle = kids.find((child) => child.tagName === "button");
    const list = kids.find((child) => child.tagName === "ul");
    const heading = kids.find((child) => child.tagName === "h2");
    return {
      hidden: box.hidden,
      className: box.className,
      heading: heading ? heading.textContent : null,
      paragraphs: kids.filter((child) => child.tagName === "p").map((child) => child.textContent),
      toggle: toggle ? { text: toggle.textContent, aria: toggle.getAttribute("aria-expanded"), type: toggle.getAttribute("type"), className: toggle.className } : null,
      listHidden: list ? list.hidden : null,
      items: list ? list.children.map((item) => [item.tagName, item.textContent]) : [],
    };
  },
  finalParts: () => ({
    historyHidden: elements["sheet-history"].hidden,
    historyChildren: elements["sheet-history"].children.length,
    finalHidden: elements["sheet-final"].hidden,
    finalChildren: elements["sheet-final"].children.length,
  }),
  lastCard: () => elements["sheet-final"].children.find((child) => child.id === "sheet-approval"),
  lastParts: () => tools.lastCard().children.map((child) => {
    if (hasClass(child, "sh-label")) return "label:" + child.textContent;
    return child.tagName + (child.className ? "." + child.className.split(/\s+/).join(".") : "");
  }),
  lastParagraphs: () => tools.lastCard().children.filter((child) => child.tagName === "p").map((child) => child.textContent),
  lastHeading: () => tools.lastCard().children.find((child) => child.tagName === "h2").textContent,
  lastButtons: () => tools.lastCard().children.find((child) => hasClass(child, "answer-row")).children,
  lastButton: (label) => tools.lastButtons().find((button) => button.textContent === label),
  lastNote: () => tools.lastCard().children.find((child) => child.tagName === "textarea"),
  lastSaveLine: () => tools.lastCard().children.find((child) => hasClass(child, "save-line")),
  lastSaveText: () => [elements["sheet-final"], tools.lastCard(), tools.lastSaveLine()].some((node) => node.hidden) ? "" : tools.text(tools.lastSaveLine()),
  lastTryAgain: () => tools.lastSaveLine().children.find((child) => child.tagName === "button"),
  lastState: () => ({
    labels: tools.lastButtons().map((button) => button.textContent),
    pressed: tools.lastButtons().map((button) => button.getAttribute("aria-pressed")),
    classes: tools.lastButtons().map((button) => button.className),
    disabled: tools.lastButtons().map((button) => button.disabled).concat([tools.lastNote().disabled]),
    note: tools.lastNote().value,
  }),
  sendRow: () => tools.lastCard().children.find((child) => hasClass(child, "send-row")),
  sendButton: () => tools.sendRow().children.find((child) => child.tagName === "button" && child.textContent === "Send verdict"),
  sendStatus: () => {
    const status = tools.sendRow().children.find((child) => child.tagName === "span" && hasClass(child, "sh-caption"));
    return status ? status.textContent : null;
  },
  sendTryAgain: () => tools.sendRow().children.find((child) => child.tagName === "button" && child.textContent === "Try again"),
  nextBox: () => {
    const box = elements["sheet-final"].children.find((child) => child !== tools.lastCard());
    return { className: box.className, label: box.children[0].textContent, labelClass: box.children[0].className, text: box.children[1].textContent };
  },
  // Every control a person could press or type in on the cards and the last card, with whether it is off.
  controls: () => [...walk(elements["sheet-cards"]), ...walk(elements["sheet-final"])]
    .filter((node) => node.tagName === "button" || node.tagName === "textarea")
    .map((node) => ({ text: node.tagName === "textarea" ? "note" : tools.text(node), disabled: node.disabled })),
  // Every button node anywhere on the page, for the checks on what a control wears.
  allButtons: () => [...new Set(Object.values(elements).flatMap((root) => [...walk(root)]).filter((node) => node.tagName === "button"))].map((node) => ({
    text: tools.text(node),
    className: node.className,
    type: node.getAttribute("type"),
  })),
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
    recordedSets: tools.setLog(),
    count: elements["sheet-count"].textContent,
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
    page = json.loads(result.stdout)
    for recorded in page["recordedSets"]:
        path = recorded["path"]
        if re.fullmatch(r"answers/[a-z0-9][a-z0-9-]*", path):
            ANSWER_VALIDATOR.validate(recorded["body"])
        elif path == "draft-verdict/final":
            DRAFT_VERDICT_VALIDATOR.validate(recorded["body"])
        elif path == "verdict/final":
            VERDICT_VALIDATOR.validate(recorded["body"])
        else:
            pytest.fail("the page wrote to %s, which is not a document it may write" % path)
    return page


# Bites on: the stored-answer schema accepting a document the page must never write (an option pick with no option, an option on a non-option answer, a missing note, an extra property, an option id outside the sheet's identifier rule), or refusing one it should keep.
def test_answer_schema_rejects_bad_documents():
    jsonschema.Draft202012Validator.check_schema(ANSWER_SCHEMA)
    good = [
        {"answer": None, "optionId": None, "note": ""},
        {"answer": "aligned", "optionId": None, "note": "n"},
        {"answer": "discuss", "optionId": None, "note": ""},
        {"answer": "option", "optionId": "yes", "note": ""},
        {"answer": None, "optionId": None, "note": "only a note"},
    ]
    for document in good:
        assert ANSWER_VALIDATOR.is_valid(document), document
    bad = [
        {"answer": "option", "optionId": None, "note": ""},
        {"answer": "aligned", "optionId": "yes", "note": ""},
        {"answer": None, "optionId": "yes", "note": ""},
        {"answer": "aligned", "optionId": None},
        {"answer": "aligned", "optionId": None, "note": "", "extra": 1},
        {"answer": "option", "optionId": "Not Valid", "note": ""},
        {"answer": "option", "optionId": "", "note": ""},
        {"answer": "maybe", "optionId": None, "note": ""},
    ]
    for document in bad:
        assert not ANSWER_VALIDATOR.is_valid(document), document


def _sample_files(sheet=None):
    sheet_text = (THEME / "sample-sheet.json").read_text(encoding="utf-8") if sheet is None else json.dumps(sheet)
    return {
        "sheet.json": {"status": 200, "body": sheet_text},
        "sheet.schema.json": {"status": 200, "body": (THEME / "sheet.schema.json").read_text(encoding="utf-8")},
        "sheet-words.json": {"status": 200, "body": (THEME / "sheet-words.json").read_text(encoding="utf-8")},
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
    for path in (TEMPLATE, USAGE_DOC, THEME / "sheet.schema.json"):
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
    planted_index = len(SHEET_SCHEMA["allOf"])
    return [
        ("E1-root", _plant_at(maxLength=3), "maxLength", "#"),
        ("E2-defs-member", _plant_at("$defs", "id", maxLength=3), "maxLength", "#/$defs/id"),
        ("E3-unreferenced-definitions-member", definitions, "maxLength", "#/definitions/spare"),
        ("E4-properties", _plant_at("properties", "title", maxLength=3), "maxLength", "#/properties/title"),
        ("E4-nested-properties", _plant_at("$defs", "card", "properties", "question", maxLength=3), "maxLength", "#/$defs/card/properties/question"),
        ("E5-items", _plant_at(*declined, "items", maxLength=3), "maxLength", "#/properties/final/properties/declinedFindings/items"),
        ("E6-allOf-member", all_of, "maxLength", "#/allOf/%d" % planted_index),
        ("E7-anyOf-member", any_of, "maxLength", "#/allOf/%d/anyOf/1" % planted_index),
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


# Bites on: a typed note saving before its one-second pause ends or a millisecond late, saving more than once for a burst of typing, or a keystroke during a pending pause not restarting it.
def test_typing_saves_once_after_a_pause():
    result = _answer_page([_card("plan-day")], """
      const out = {};
      const note = t.note("plan-day");
      t.type(note, "x", "input");
      await t.advance(500);
      t.type(note, "xy", "input");
      await t.advance(999);
      out.burstBefore = { sets: t.setLog(), save: t.saveText("plan-day") };
      await t.advance(1);
      out.burstAt = { sets: t.setLog(), save: t.saveText("plan-day") };
      t.sets[0].resolve();
      await t.tick();
      out.burstSaved = t.saveText("plan-day");
      t.type(note, "xya", "input");
      await t.advance(999);
      out.beforePause = { sets: t.setLog().length, save: t.saveText("plan-day") };
      await t.advance(1);
      out.atPause = { sets: t.setLog(), save: t.saveText("plan-day") };
      t.sets[1].resolve();
      await t.tick();
      out.firstSaved = t.saveText("plan-day");
      t.type(note, "xyab", "input");
      await t.advance(999);
      out.restartedBefore = { sets: t.setLog().length, save: t.saveText("plan-day") };
      await t.advance(1);
      out.restartedAt = { sets: t.setLog(), save: t.saveText("plan-day") };
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["burstBefore"] == {"sets": [], "save": "Saving…"}
    assert result["burstAt"] == {"sets": [_write("plan-day", None, None, "xy")], "save": "Saving…"}
    assert result["burstSaved"] == "Saved"
    assert result["beforePause"] == {"sets": 1, "save": "Saving…"}
    assert result["atPause"] == {
        "sets": [_write("plan-day", None, None, "xy"), _write("plan-day", None, None, "xya")],
        "save": "Saving…",
    }
    assert result["firstSaved"] == "Saved"
    assert result["restartedBefore"] == {"sets": 2, "save": "Saving…"}
    assert result["restartedAt"] == {
        "sets": [
            _write("plan-day", None, None, "xy"),
            _write("plan-day", None, None, "xya"),
            _write("plan-day", None, None, "xyab"),
        ],
        "save": "Saving…",
    }


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


# Bites on: leaving or reloading the sheet while an answer or note is not yet confirmed by the store going unguarded, or the guard staying on once everything is saved.
def test_leaving_the_sheet_is_guarded_only_while_an_answer_is_unconfirmed():
    result = _answer_page([_card("plan-day")], """
      const out = {};
      out.idle = t.unload();
      t.click(t.button("plan-day", "Aligned"));
      out.pending = t.unload();
      t.sets[0].resolve();
      await t.tick();
      out.savedText = t.saveText("plan-day");
      out.saved = t.unload();
      t.type(t.note("plan-day"), "later", "input");
      out.noteTimer = t.unload();
      return out;
    """, host={"set": "pending"})
    assert result["idle"] is False
    assert result["pending"] is True, "closing with a write pending was not guarded"
    assert result["savedText"] == "Saved"
    assert result["saved"] is False, "the guard stayed on after the write was confirmed"
    assert result["noteTimer"] is True, "a note waiting for its pause was not guarded"


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
      out.failed = { text: t.saveText("plan-day"), badge: described(t.visible("plan-day", badgeOf("plan-day"))), retry: described(t.visible("plan-day", t.tryAgain("plan-day"))) };
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
      t.open("fridge-check");
      out.moved = { save: t.saveText("fridge-check"), retry: t.tryAgain("fridge-check") !== undefined };
      t.fire(held, "click");
      out.heldRetry = { sets: t.sets.length, write: t.setLog()[3] };
      t.sets[3].resolve();
      await t.tick();

      t.click(t.button("third-card", "Aligned"));
      t.click(t.button("third-card", "Discuss"));
      t.sets[4].reject(failure);
      await t.tick();
      t.open("third-card");
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


# Bites on: a write that never answers blocking the card for good, a stalled write offering a Try again that would overlap it, a second write in flight, an older write landing after a newer one, or Saved showing before the newest answer was sent and acknowledged.
def test_stalled_save_is_single_flight_and_the_latest_state_lands_last():
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      const out = {};
      t.click(t.button("plan-day", "Aligned"));
      await t.advance(9999);
      out.early = t.saveText("plan-day");
      await t.advance(1);
      out.stalled = { text: t.saveText("plan-day"), retry: t.tryAgain("plan-day") !== undefined };
      t.click(t.button("plan-day", "Discuss"));
      t.type(t.note("plan-day"), "x", "change");
      await t.advance(5000);
      out.edited = { sets: t.sets.length, text: t.saveText("plan-day"), retry: t.tryAgain("plan-day") !== undefined };
      t.sets[0].resolve();
      await t.tick();
      out.olderDone = { sets: t.sets.length, write: t.setLog()[1], text: t.saveText("plan-day") };
      t.sets[1].resolve();
      await t.tick();
      out.final = { sets: t.sets.length, text: t.saveText("plan-day") };

      t.click(t.button("fridge-check", "Aligned"));
      await t.advance(10000);
      t.sets[2].reject({ code: "unavailable", message: "late" });
      await t.tick();
      t.open("fridge-check");
      out.failed = { sets: t.sets.length, text: t.saveText("fridge-check"), retry: t.tryAgain("fridge-check") !== undefined };
      t.click(t.tryAgain("fridge-check"));
      out.retried = { sets: t.sets.length, write: t.setLog()[3] };
      t.sets[3].resolve();
      await t.tick();
      out.second = t.saveText("fridge-check");
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["early"] == "Saving…"
    assert result["stalled"]["text"].startswith("Not saved") and result["stalled"]["retry"] is False
    assert "Keep this page open" in result["stalled"]["text"]
    assert "Reloading shows only what was saved" in result["stalled"]["text"]
    assert "Reloading the page shows what was saved" not in result["stalled"]["text"], "the stalled text still offers a reload as recovery"
    assert result["edited"] == {"sets": 1, "text": result["stalled"]["text"], "retry": False}, "a write started while the first was pending"
    assert result["olderDone"] == {"sets": 2, "write": _write("plan-day", "discuss", None, "x"), "text": "Saving…"}
    assert result["final"] == {"sets": 2, "text": "Saved"}
    assert result["failed"]["sets"] == 3 and result["failed"]["text"].startswith("Not saved") and result["failed"]["retry"] is True
    assert result["retried"] == {"sets": 4, "write": _write("fridge-check", "aligned", None, "")}
    assert result["second"] == "Saved"


# Bites on: a host that never answers use("db"), use("user") or isOwner() leaving the sheet on Loading with no way out, or a retry that does not ask again.
@pytest.mark.parametrize("hang", ["db", "user", "isOwner"])
def test_stalled_host_initialization_offers_retry(hang):
    result = _answer_page([_card("plan-day")], """
      const out = {};
      await t.advance(9999);
      out.early = { message: t.gate().message, retry: t.gate().retry !== undefined };
      await t.advance(1);
      out.stalled = { message: t.gate().message, retry: t.gate().retry !== undefined, disabled: t.state("plan-day").disabled };
      const before = { uses: t.uses.slice(), owner: t.ownerChecks.length };
      t.click(t.gate().retry);
      await t.tick();
      out.retried = { message: t.gate().message, newUses: t.uses.slice(before.uses.length), newOwner: t.ownerChecks.length - before.owner };
      return out;
    """, host={"hang": hang, "fakeTimers": True})
    assert result["early"] == {"message": "Loading your saved answers…", "retry": False}
    assert result["stalled"] == {"message": "The sheet's store isn't answering.", "retry": True, "disabled": [True] * 5}
    assert result["retried"]["message"] == "Loading your saved answers…"
    if hang == "isOwner":
        assert result["retried"]["newOwner"] > 0, "the retry did not ask isOwner() again"
    else:
        assert hang in result["retried"]["newUses"], "the retry did not ask use(%r) again" % hang


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


# Bites on: a saved answer that names no pick the card offers, or does not fit the schema's answer rule, still restoring a pick, a note being lost, or an unknown card id breaking the restore.
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
    # A document that does not fit the schema's answer rule (here a note that is not text) restores no pick.
    assert third["pressed"] == ["false"] * 4 and third["note"] == ""
    assert all(not any(state["disabled"]) for state in result["restored"])
    assert result["sets"] == [
        _write("plan-day", None, None, "edited plan-day"),
        _write("fridge-check", None, None, "edited fridge-check"),
        _write("third-card", None, None, "edited third-card"),
    ]


# Bites on: a saved Aligned pick (or its note) not being restored onto the card it was saved for.
def test_a_saved_aligned_pick_is_restored():
    docs = [{"id": "plan-day", "data": {"answer": "aligned", "optionId": None, "note": "agreed"}}]
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      return { plan: t.state("plan-day"), other: t.state("fridge-check") };
    """, host={"docs": docs})
    assert result["plan"]["pressed"] == ["true", "false", "false", "false"]
    assert result["plan"]["note"] == "agreed"
    assert result["other"]["pressed"] == ["false"] * 4


# Bites on: a failed write of a different answer leaving a revert to the acknowledged answer reported Saved without sending it.
def test_a_revert_after_a_failed_write_is_sent_again():
    docs = [{"id": "plan-day", "data": {"answer": "aligned", "optionId": None, "note": ""}}]
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      t.click(t.button("plan-day", "Discuss"));
      t.click(t.button("plan-day", "Aligned"));
      t.sets[0].reject({ code: "unavailable", message: "lost ack" });
      await t.tick();
      t.open("plan-day");
      const during = t.saveText("plan-day");
      t.sets[1].resolve();
      await t.tick();
      return { sets: t.setLog(), during: during, save: t.saveText("plan-day") };
    """, host={"docs": docs, "set": "pending"})
    assert result["sets"] == [
        _write("plan-day", "discuss", None, ""),
        _write("plan-day", "aligned", None, ""),
    ]
    assert result["during"] == "Saving…", result
    assert result["save"] == "Saved", result


# Bites on: a rejected write leaving the acknowledged answer trusted, so a later revert to it was skipped and the failure cleared.
def test_a_revert_after_a_settled_rejection_is_sent_and_saved_only_after_it_resolves():
    docs = [{"id": "plan-day", "data": {"answer": "aligned", "optionId": None, "note": ""}}]
    result = _answer_page([_card("plan-day"), _card("fridge-check")], """
      t.click(t.button("plan-day", "Discuss"));
      t.sets[0].reject({ code: "unavailable", message: "lost ack" });
      await t.tick();
      t.open("plan-day");
      const failed = t.saveText("plan-day");
      t.click(t.button("plan-day", "Aligned"));
      const during = t.saveText("plan-day");
      const sent = t.setLog().length;
      t.sets[1].resolve();
      await t.tick();
      return { sets: t.setLog(), failed: failed, during: during, sent: sent, save: t.saveText("plan-day") };
    """, host={"docs": docs, "set": "pending"})
    assert result["sets"] == [
        _write("plan-day", "discuss", None, ""),
        _write("plan-day", "aligned", None, ""),
    ]
    assert result["sent"] == 2, result
    assert result["during"] == "Saving…", result
    assert result["save"] == "Saved", result


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


def _schema_without_answers(mutate):
    schema = copy.deepcopy(SHEET_SCHEMA)
    mutate(schema)
    return schema


def _drop_answer_definition(schema):
    del schema["$defs"]["answer"]


def _make_answer_enum_malformed(schema):
    # A non-list enum is refused earlier, by the page's schema check, so the malformed form that reaches the answer reader is a list holding a value that is not text.
    schema["$defs"]["answer"]["properties"]["answer"]["enum"] = ["aligned", "discuss", "option", 7]


def _drop_option_carrying_rule(schema):
    answer = schema["$defs"]["answer"]
    answer["allOf"] = [
        entry for entry in answer["allOf"]
        if entry["if"]["properties"]["answer"].get("const") != "option"
    ]


# Bites on: a schema that does not say what an answer is (no answer definition, an answer list holding a non-text value, or no value tied to an option id) still getting answer buttons, a live note, or a connection to the store.
@pytest.mark.parametrize("mutate", [
    pytest.param(_drop_answer_definition, id="E1-no-answer-definition"),
    pytest.param(_make_answer_enum_malformed, id="E2-enum-is-malformed"),
    pytest.param(_drop_option_carrying_rule, id="E3-no-option-carrying-value"),
])
def test_a_schema_without_an_answer_shape_keeps_answers_off(mutate):
    files = _sample_files()
    files["sheet.schema.json"]["body"] = json.dumps(_schema_without_answers(mutate))
    page = _run_page(files, scenario="""
      const ids = t.all(elements["sheet-cards"]).filter((node) => node.tagName === "article").map((node) => node.id.replace("card-", ""));
      return {
        buttons: ids.map((id) => t.buttons(id).length),
        notesDisabled: ids.map((id) => t.note(id).disabled),
        gate: t.gate().message,
        gateHidden: t.gate().hidden,
        uses: t.uses,
      };
    """)
    assert page["settled"], "the page never settled: %s" % page
    assert page["errors"] == [], page["errors"]
    sample_cards = json.loads((THEME / "sample-sheet.json").read_text(encoding="utf-8"))["cards"]
    assert len(page["cards"]) == len(sample_cards) > 0, page["cards"]
    result = page["result"]
    assert result["buttons"] == [0] * len(sample_cards), result
    assert result["notesDisabled"] == [True] * len(sample_cards), result
    assert result["gateHidden"] is False, result
    assert result["gate"] == "Answers can't be saved in this view.", result
    assert result["uses"] == [], "the page reached for the store although the schema names no answer shape"


def _doc(answer, option_id=None, note=""):
    return {"answer": answer, "optionId": option_id, "note": note}


def _named_cards(*ids):
    return [_card(card_id, question="Question %d" % (index + 1)) for index, card_id in enumerate(ids)]


def _remainder_of(cards, rounds=2, fixes=3, unsettled=()):
    return _sheet("remainder", cards=cards, remainder={"roundsRun": rounds, "fixesMade": fixes, "unsettled": list(unsettled)})


def _sheet_page(sheet, scenario, host=None):
    page = _run_page(_sample_files(sheet), host=host, scenario=scenario)
    assert page["settled"], "the page never settled: %s" % page
    assert len(page["cards"]) == len(sheet["cards"]), page["cards"]
    return page["result"]


# Bites on: the answered count reading anything but each card's latest answer (an unconfirmed pick left out, a note counted as an answer, a discuss pick not counted separately, a restored answer missed, or a restored document that does not fit counted).
def test_sheet_count_follows_the_latest_answers():
    result = _answer_page(_named_cards("plan-day", "fridge-check", "third-card", "fourth-card"), """
      const out = {};
      const failure = { code: "unavailable", message: "try later" };
      out.start = t.count();
      t.type(t.note("plan-day"), "just a note", "input");
      out.noteOnly = t.count();
      t.click(t.button("plan-day", "Aligned"));
      out.aligned = t.count();
      t.click(t.button("plan-day", "Discuss"));
      out.changed = t.count();
      t.click(t.button("fridge-check", "Yes"));
      out.picked = t.count();
      t.click(t.button("plan-day", "Aligned"));
      out.changedBack = t.count();
      t.sets[1].reject(failure);
      await t.tick();
      out.failed = t.count();
      t.click(t.button("third-card", "Discuss"));
      await t.advance(10000);
      out.stalled = t.count();
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["start"] == "0 of 4 answered"
    assert result["noteOnly"] == "0 of 4 answered", "a note alone was counted as an answer"
    assert result["aligned"] == "1 of 4 answered", "an unconfirmed pick was left out of the count"
    assert result["changed"] == "1 of 4 answered · 1 to discuss"
    assert result["picked"] == "2 of 4 answered · 1 to discuss"
    assert result["changedBack"] == "2 of 4 answered"
    assert result["failed"] == "2 of 4 answered"
    assert result["stalled"] == "3 of 4 answered · 1 to discuss"

    docs = [
        {"id": "plan-day", "data": _doc("aligned")},
        {"id": "fridge-check", "data": _doc("discuss")},
        {"id": "third-card", "data": _doc("option", "yes")},
        {"id": "fourth-card", "data": _doc("maybe", None, "kept")},
    ]
    restored = _answer_page(_named_cards("plan-day", "fridge-check", "third-card", "fourth-card"), "return t.count();", host={"docs": docs})
    assert restored == "3 of 4 answered · 1 to discuss"


# Bites on: the sheet claiming "0 of N answered" or "Open" while the saved answers are not known (loading, a failed or stalled read, no store, a non-owner, no answer shape), or a retried read that succeeds not turning the count and pills on.
@pytest.mark.parametrize("host,advance,drop_shape,retry,card_ids", [
    pytest.param({"read": "pending"}, 0, False, False, ["plan-day", "fridge-check"], id="loading"),
    pytest.param({"read": ["reject", "docs"], "docs": [{"id": "plan-day", "data": _doc("aligned")}]}, 0, False, True, ["plan-day", "fridge-check"], id="failed-read"),
    pytest.param({"read": "pending", "fakeTimers": True}, 10000, False, False, ["plan-day", "fridge-check"], id="stalled-read"),
    pytest.param({"claude": "missing"}, 0, False, False, ["plan-day", "fridge-check"], id="no-runtime"),
    pytest.param({"db": "null"}, 0, False, False, ["plan-day", "fridge-check"], id="no-store"),
    pytest.param({"user": "viewer"}, 0, False, False, ["plan-day", "fridge-check"], id="non-owner"),
    pytest.param({}, 0, True, False, ["plan-day", "fridge-check"], id="no-answer-shape"),
    pytest.param({"read": "pending"}, 0, False, False, ["plan-day"], id="one-card"),
])
def test_sheet_makes_no_answer_claim_until_answers_are_read(host, advance, drop_shape, retry, card_ids):
    files = _sample_files(_remainder_of(_named_cards(*card_ids), unsettled=card_ids[-1:]))
    if drop_shape:
        files["sheet.schema.json"]["body"] = json.dumps(_schema_without_answers(_drop_answer_definition))
    page = _run_page(files, host=host, scenario="""
      if (__ADVANCE__ > 0) await t.advance(__ADVANCE__);
      const snapshot = () => ({ count: t.count(), rows: t.rows(), fold: t.fold() });
      const out = { before: snapshot() };
      if (__RETRY__) {
        t.click(t.gate().retry);
        await t.tick();
        out.after = snapshot();
      }
      return out;
    """.replace("__ADVANCE__", str(advance)).replace("__RETRY__", "true" if retry else "false"))
    assert page["settled"], "the page never settled: %s" % page
    before = page["result"]["before"]
    assert before["count"] == "%d item%s · answers not loaded" % (len(card_ids), "" if len(card_ids) == 1 else "s")
    assert [row["pill"] for row in before["rows"]] == [None] * len(card_ids), "a row claimed a state before the answers were known"
    assert before["fold"]["hidden"] is True
    if retry:
        after = page["result"]["after"]
        assert after["count"] == "1 of 2 answered"
        assert [row["pill"] for row in after["rows"]] == [
            ["sh-pill sh-pill--aligned", "Aligned"], ["sh-pill sh-pill--open", "Open"],
        ]


# Bites on: a row that is not a button, is out of card order, or shows the wrong text, pill or open-card marks, a row click that does not open its card, or a card with only a note reading as answered.
def test_rows_show_each_cards_state():
    docs = [
        {"id": "plan-day", "data": _doc("aligned")},
        {"id": "fridge-check", "data": _doc("discuss")},
        {"id": "third-card", "data": _doc("option", "yes")},
        {"id": "fourth-card", "data": _doc("maybe", None, "only a note")},
    ]
    result = _answer_page(_named_cards("plan-day", "fridge-check", "third-card", "fourth-card"), """
      const out = { nodes: t.rowNodes().map((row) => [row.tagName, row.getAttribute("type")]), rows: t.rows(), open: t.openCard() };
      t.click(t.control("next"));
      out.stepped = t.openCard();
      out.clicked = t.open("fridge-check");
      out.afterClick = { open: t.openCard(), current: t.rows().map((row) => row.current), aria: t.rows().map((row) => row.ariaCurrent) };
      return out;
    """, host={"docs": docs})
    assert result["nodes"] == [["button", "button"]] * 4
    assert [row["text"] for row in result["rows"]] == ["1 · Question 1", "2 · Question 2", "3 · Question 3", "4 · Question 4"]
    assert [row["pill"] for row in result["rows"]] == [
        ["sh-pill sh-pill--aligned", "Aligned"],
        ["sh-pill sh-pill--discuss", "Discuss"],
        ["sh-pill sh-pill--aligned", "Picked"],
        ["sh-pill sh-pill--open", "Open"],
    ]
    assert [row["badge"] for row in result["rows"]] == [None] * 4
    assert [row["folded"] for row in result["rows"]] == [False] * 4, "a plain sheet folded a row"
    assert result["open"] == "fourth-card"
    assert [row["current"] for row in result["rows"]] == [False, False, False, True]
    assert result["rows"][3]["className"] == "sh-button sh-button--main sheet-row is-current"
    assert result["rows"][0]["className"] == "sh-button sheet-row"
    assert result["clicked"] is True
    assert result["afterClick"] == {"open": "fridge-check", "current": [False, True, False, False], "aria": ["false", "true", "false", "false"]}


# Bites on: a card whose save failed or stalled not showing "Not saved" on its row, a saved or untouched card showing it, or the mark staying after a retry lands.
def test_row_shows_not_saved_for_a_failed_or_stalled_save():
    result = _answer_page(_named_cards("plan-day", "fridge-check", "third-card"), """
      const out = {};
      const failure = { code: "unavailable", message: "try later" };
      const badges = () => t.rows().map((row) => row.badge);
      t.click(t.button("plan-day", "Aligned"));
      t.click(t.button("fridge-check", "Yes"));
      t.click(t.button("third-card", "Discuss"));
      t.sets[2].resolve();
      t.sets[0].reject(failure);
      await t.tick();
      out.failed = { badges: badges(), pills: t.rows().map((row) => row.pill) };
      await t.advance(10000);
      out.stalled = badges();
      t.open("plan-day");
      t.click(t.tryAgain("plan-day"));
      t.sets[3].resolve();
      await t.tick();
      out.recovered = badges();
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    warning = ["sh-badge sh-badge--warning", "Not saved"]
    assert result["failed"]["badges"] == [warning, None, None]
    assert result["failed"]["pills"][0] == ["sh-pill sh-pill--aligned", "Aligned"]
    assert result["stalled"] == [warning, warning, None]
    assert result["recovered"] == [None, warning, None]


# Bites on: more or fewer than one card shown, the first draw or a restore not landing on the right card, Previous or Next stepping wrongly or staying enabled at an end, the stepper label, or the open row's class.
def test_one_card_is_open_and_previous_next_step_through():
    result = _answer_page(_named_cards("plan-day", "fridge-check", "third-card"), """
      const out = { first: { open: t.openCard(), stepper: t.stepper() } };
      const shape = () => ({ open: t.openCard(), stepper: t.stepper(), classes: t.rows().map((row) => row.className), aria: t.rows().map((row) => row.ariaCurrent) });
      out.firstRows = shape();
      t.click(t.control("next"));
      out.second = shape();
      t.click(t.control("next"));
      out.third = shape();
      out.pastEnd = t.click(t.control("next"));
      t.click(t.control("previous"));
      t.click(t.control("previous"));
      out.back = { open: t.openCard(), pastStart: t.click(t.control("previous")) };
      t.open("third-card");
      out.viaRow = t.openCard();
      return out;
    """)
    assert result["first"] == {"open": "plan-day", "stepper": {"hidden": False, "label": "Item 1 of 3", "prevDisabled": True, "nextDisabled": False}}
    current = "sh-button sh-button--main sheet-row is-current"
    plain = "sh-button sheet-row"
    assert result["firstRows"]["classes"] == [current, plain, plain]
    assert result["firstRows"]["aria"] == ["true", "false", "false"]
    assert result["second"]["open"] == "fridge-check"
    assert result["second"]["stepper"] == {"hidden": False, "label": "Item 2 of 3", "prevDisabled": False, "nextDisabled": False}
    assert result["second"]["classes"] == [plain, current, plain]
    assert result["second"]["aria"] == ["false", "true", "false"]
    assert result["third"]["open"] == "third-card"
    assert result["third"]["stepper"] == {"hidden": False, "label": "Item 3 of 3", "prevDisabled": False, "nextDisabled": True}
    assert result["pastEnd"] is False
    assert result["back"] == {"open": "plan-day", "pastStart": False}
    assert result["viaRow"] == "third-card"

    # While the answers are still loading the first card is open.
    loading = _answer_page(_named_cards("plan-day", "fridge-check"), "return t.openCard();", host={"read": "pending"})
    assert loading == "plan-day"

    # A restore lands on the first card still waiting for an answer, or on the first when every card is answered.
    ids = ("plan-day", "fridge-check", "third-card")
    partly = [{"id": "plan-day", "data": _doc("aligned")}, {"id": "fridge-check", "data": _doc("discuss")}]
    landed = _answer_page(_named_cards(*ids), "return { open: t.openCard(), label: t.stepper().label };", host={"docs": partly})
    assert landed == {"open": "third-card", "label": "Item 3 of 3"}
    everything = partly + [{"id": "third-card", "data": _doc("option", "no")}]
    landed = _answer_page(_named_cards(*ids), "return { open: t.openCard(), label: t.stepper().label };", host={"docs": everything})
    assert landed == {"open": "plan-day", "label": "Item 1 of 3"}

    # A sheet with one card has nowhere to step.
    single = _answer_page(_named_cards("plan-day"), "return { open: t.openCard(), stepper: t.stepper(), fold: t.fold().hidden };")
    assert single == {"open": "plan-day", "stepper": {"hidden": False, "label": "Item 1 of 1", "prevDisabled": True, "nextDisabled": True}, "fold": True}


# Bites on: the fold missing an answered item, miscounting its pills, showing a Picked pill when none was picked, folding the open card, folding on a plain or final sheet, or its toggle not flipping aria-expanded and the list's expanded class.
def test_remainder_fold_counts_answered_items():
    ids = ("plan-day", "fridge-check", "third-card", "fourth-card")
    docs = [
        {"id": "plan-day", "data": _doc("aligned")},
        {"id": "fridge-check", "data": _doc("discuss")},
        {"id": "third-card", "data": _doc("option", "yes")},
    ]
    scenario = """
      const out = { rows: t.rows().map((row) => row.folded), fold: t.fold(), open: t.openCard() };
      t.click(t.control("fold"));
      out.expanded = { aria: t.fold().aria, list: t.fold().listExpanded };
      t.click(t.control("fold"));
      out.collapsed = { aria: t.fold().aria, list: t.fold().listExpanded };
      return out;
    """
    result = _sheet_page(_remainder_of(_named_cards(*ids), unsettled=["fourth-card"]), scenario, host={"docs": docs})
    assert result["open"] == "fourth-card"
    assert result["rows"] == [True, True, True, False]
    fold = result["fold"]
    assert (fold["hidden"], fold["first"], fold["type"], fold["aria"]) == (False, True, "button", "false")
    assert fold["className"] == "sh-button sheet-fold"
    assert fold["parts"] == [
        ["", "Answered · 3"],
        ["sh-pill sh-pill--aligned", "1 Aligned"],
        ["sh-pill sh-pill--discuss", "1 Discuss"],
        ["sh-pill sh-pill--aligned", "1 Picked"],
    ]
    assert result["expanded"] == {"aria": "true", "list": True}
    assert result["collapsed"] == {"aria": "false", "list": False}

    # No pick, no Picked pill.
    two = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check"), unsettled=["fridge-check"]), scenario, host={"docs": docs[:1]})
    assert [part[1] for part in two["fold"]["parts"]] == ["Answered · 1", "1 Aligned", "0 Discuss"]

    # The open card is never folded or counted, even when every card is answered.
    everything = docs + [{"id": "fourth-card", "data": _doc("aligned")}]
    full = _sheet_page(_remainder_of(_named_cards(*ids), unsettled=["fourth-card"]), scenario, host={"docs": everything})
    assert full["open"] == "plan-day"
    assert full["rows"] == [False, True, True, True]
    assert full["fold"]["parts"][0] == ["", "Answered · 3"]

    # Plain and final sheets never fold.
    for sheet in (_sheet(cards=_named_cards("plan-day", "fridge-check")), _final_sheet()):
        plain = _sheet_page(sheet, scenario, host={"docs": docs[:1]})
        assert plain["rows"] == [False, False]
        assert plain["fold"]["hidden"] is True


# Bites on: an answer whose save failed or stalled folding away with the rest, losing its Not saved mark, going missing from the fold's "not saved" count, or the open card (already in full view) being counted in that number.
def test_an_unsaved_answer_never_folds():
    result = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check", "third-card"), unsettled=["third-card"]), """
      const out = {};
      const failure = { code: "unavailable", message: "try later" };
      const shape = () => ({ folded: t.rows().map((row) => row.folded), badges: t.rows().map((row) => row.badge), fold: t.fold() });
      t.click(t.button("plan-day", "Aligned"));
      t.open("fridge-check");
      t.click(t.button("fridge-check", "Discuss"));
      t.sets[1].resolve();
      await t.tick();
      t.open("third-card");
      out.saving = shape();
      t.sets[0].reject(failure);
      await t.tick();
      out.failed = shape();
      t.open("plan-day");
      out.openFailed = shape();
      t.click(t.tryAgain("plan-day"));
      t.sets[2].resolve();
      await t.tick();
      t.open("third-card");
      out.recovered = shape();
      return out;
    """, host={"set": "pending"})
    warning = ["sh-badge sh-badge--warning", "Not saved"]
    # An answer still being written folds; one whose write failed does not, though the owner has moved on.
    assert result["saving"]["folded"] == [True, True, False]
    assert [part[1] for part in result["saving"]["fold"]["parts"]] == ["Answered · 2", "1 Aligned", "1 Discuss"]
    assert result["failed"]["folded"] == [False, True, False]
    assert result["failed"]["badges"] == [warning, None, None]
    assert result["failed"]["fold"]["hidden"] is False
    assert result["failed"]["fold"]["parts"] == [
        ["", "Answered · 1"],
        ["sh-pill sh-pill--aligned", "0 Aligned"],
        ["sh-pill sh-pill--discuss", "1 Discuss"],
        ["sh-badge sh-badge--warning", "1 not saved"],
    ]
    # The open card is in full view with its own save line, so the fold does not count it.
    assert result["openFailed"]["folded"] == [False, True, False]
    assert [part[1] for part in result["openFailed"]["fold"]["parts"]] == ["Answered · 1", "0 Aligned", "1 Discuss"]
    assert result["recovered"]["folded"] == [True, True, False]
    assert result["recovered"]["badges"] == [None, None, None]


# Bites on: an answer whose write stalled folding away with the rest, losing its Not saved mark, or going missing from the fold's "not saved" count.
def test_a_stalled_answer_never_folds():
    result = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check", "third-card"), unsettled=["third-card"]), """
      t.click(t.button("plan-day", "Aligned"));
      t.open("fridge-check");
      t.click(t.button("fridge-check", "Discuss"));
      t.sets[1].resolve();
      await t.tick();
      t.open("third-card");
      await t.advance(10000);
      return { folded: t.rows().map((row) => row.folded), badges: t.rows().map((row) => row.badge), fold: t.fold() };
    """, host={"set": "pending", "fakeTimers": True})
    assert result["folded"] == [False, True, False]
    assert result["badges"] == [["sh-badge sh-badge--warning", "Not saved"], None, None]
    assert [part[1] for part in result["fold"]["parts"]] == ["Answered · 1", "0 Aligned", "1 Discuss", "1 not saved"]


# Bites on: the "why only these" line built from anything but the review's own rounds, fixes and unsettled count, the card count, or shown on a plain or final sheet.
def test_why_only_these_is_built_from_the_remainder_facts():
    ending = " Everything else traces to your board or your rulings, so it isn't here."
    cases = [
        (2, 3, ["fridge-check"], ["plan-day", "fridge-check"],
         "The review ran 2 rounds and fixed 3 things itself." + ending + " 1 item here is a finding the review didn't settle."),
        (1, 1, [], ["plan-day", "fridge-check", "third-card"], "The review ran 1 round and fixed 1 thing itself." + ending),
        (4, 0, ["plan-day", "third-card"], ["plan-day", "fridge-check", "third-card"],
         "The review ran 4 rounds and fixed 0 things itself." + ending + " 2 items here are findings the review didn't settle."),
    ]
    for rounds, fixes, unsettled, ids, text in cases:
        why = _sheet_page(_remainder_of(_named_cards(*ids), rounds, fixes, unsettled), "return t.why();")
        assert why == {"hidden": False, "heading": "Why only these %d" % len(ids), "text": text}
    for sheet in (_sheet(), _final_sheet()):
        assert _sheet_page(sheet, "return t.why().hidden;") is True


# Bites on: Done for now not saving a pending note at once, the message not counting unsaved answers (a write in flight or a stalled one) or claiming a save with no store, the sheet body staying visible, or Back to the sheet not returning to the same open card.
def test_done_for_now_flushes_and_reports_unsaved():
    saved = "Your answers are saved as drafts. Open this link again any time to carry on, and tell the session when the sheet is done."
    result = _answer_page(_named_cards("plan-day", "fridge-check"), """
      const out = {};
      t.open("fridge-check");
      t.type(t.note("plan-day"), "later", "input");
      out.pending = t.sets.length;
      t.click(t.control("done"));
      out.flushed = { sets: t.setLog(), done: t.done(), count: t.count(), countHidden: elements["sheet-count"].hidden, footer: t.footer() };
      t.sets.forEach((call) => call.resolve());
      await t.tick();
      out.saved = t.done().message;
      t.click(t.control("back"));
      out.back = { done: t.done(), open: t.openCard(), footer: t.footer() };
      t.click(t.button("fridge-check", "Aligned"));
      await t.advance(10000);
      t.type(t.note("plan-day"), "again", "input");
      t.click(t.control("done"));
      out.two = { sets: t.sets.length, message: t.done().message };
      t.sets.forEach((call) => call.resolve());
      await t.tick();
      out.settled = t.done().message;
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["pending"] == 0
    assert result["flushed"]["sets"] == [_write("plan-day", None, None, "later")], "Done for now left a pending note unwritten"
    done = result["flushed"]["done"]
    assert done["hidden"] is False
    assert done["message"] == "1 answer isn't saved yet. Keep this page open until this says they're saved."
    assert done["body"] == {"stepper": True, "items": True, "cards": True, "why": True, "footer": True}
    assert result["flushed"]["countHidden"] is False and result["flushed"]["count"] == "0 of 2 answered"
    assert result["saved"] == saved
    assert result["back"]["done"]["hidden"] is True
    assert result["back"]["done"]["body"] == {"stepper": False, "items": False, "cards": False, "why": True, "footer": False}
    assert result["back"]["open"] == "fridge-check"
    assert result["flushed"]["footer"]["caption"] == "Answers save as you tap"
    assert result["two"] == {"sets": 3, "message": "2 answers aren't saved yet. Keep this page open until this says they're saved."}
    assert result["settled"] == saved

    # With no store nothing is written and the message says so.
    unsaved = _answer_page(_named_cards("plan-day"), """
      t.click(t.control("done"));
      const message = t.done().message;
      t.click(t.control("back"));
      return { message: message, sets: t.sets.length, hidden: t.done().hidden };
    """, host={"db": "null"})
    assert unsaved == {"message": "Answers can't be saved in this view, so nothing here was saved.", "sets": 0, "hidden": True}

    # While the saved answers are loading, or the read failed or stalled, the store is attached: say so, not "can't save".
    cannot = "Answers can't be saved in this view, so nothing here was saved."
    loading = "Your saved answers haven't loaded yet, so nothing new was saved here. Answers saved earlier are kept; open this link again to carry on."
    scenario = "t.click(t.control(\"done\")); return t.done().message;"
    for name, host, expected in [
        ("loading", {"read": "pending"}, loading),
        ("failed read", {"read": ["reject", "docs"]}, loading),
        ("non-owner", {"user": "viewer"}, cannot),
        ("no runtime", {"claude": "missing"}, cannot),
    ]:
        page = _run_page(_sample_files(_remainder_of(_named_cards("plan-day"), unsettled=["plan-day"])), host=host, scenario=scenario)
        assert page["result"] == expected, "%s: %s" % (name, page["result"])


# Bites on: Done for now telling the owner to wait after a write was rejected, or Back to the sheet not opening the first card whose save failed so its Try again is in view.
def test_done_for_now_after_a_rejected_save_points_to_try_again():
    result = _answer_page(_named_cards("plan-day", "fridge-check", "garage"), """
      const out = {};
      t.click(t.button("plan-day", "Aligned"));
      t.click(t.button("garage", "Aligned"));
      t.sets[0].resolve();
      t.sets[1].reject({ code: "unavailable", message: "no" });
      await t.tick();
      t.open("fridge-check");
      t.click(t.control("done"));
      out.one = t.done().message;
      t.click(t.control("back"));
      out.open = t.openCard();
      out.retry = t.saveText("garage");
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["one"] == "1 answer didn't save. Go back to the sheet and tap Try again on each."
    assert result["open"] == "garage"
    assert "Try again" in result["retry"]


# Bites on: an earlier write settling cutting a note's one-second pause short, so a half-typed note is written early.
def test_an_earlier_save_settling_keeps_the_note_pause():
    result = _answer_page([_card("plan-day")], """
      const out = {};
      t.click(t.button("plan-day", "Aligned"));
      t.type(t.note("plan-day"), "the note", "input");
      t.sets[0].resolve();
      await t.tick();
      out.afterSettle = { sets: t.sets.length, save: t.saveText("plan-day") };
      await t.advance(999);
      out.beforePause = t.sets.length;
      await t.advance(1);
      out.atPause = { sets: t.setLog(), save: t.saveText("plan-day") };
      t.sets[1].resolve();
      await t.tick();
      out.final = { sets: t.sets.length, save: t.saveText("plan-day") };
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["afterSettle"] == {"sets": 1, "save": "Saving…"}, "an earlier write settling sent the note before its pause ended"
    assert result["beforePause"] == 1
    assert result["atPause"] == {
        "sets": [_write("plan-day", "aligned", None, ""), _write("plan-day", "aligned", None, "the note")],
        "save": "Saving…",
    }
    assert result["final"] == {"sets": 2, "save": "Saved"}


# Bites on: a control the page adds (an item row, the fold, Previous, Next, Done for now, Back to the sheet) that is not a theme button, a second desktop breakpoint, a restated outline, or the hidden rule going missing.
def test_new_controls_are_theme_buttons():
    result = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check"), unsettled=["fridge-check"]), """
      const hosts = ["sheet-stepper", "sheet-items", "sheet-footer", "sheet-done"];
      const own = hosts.flatMap((id) => t.all(elements[id]).filter((node) => node.tagName === "button"));
      return {
        own: own.map((node) => ({ text: t.text(node), className: node.className, type: node.getAttribute("type") })),
        everything: t.allButtons().map((button) => button.className),
      };
    """, host={"docs": [{"id": "plan-day", "data": _doc("aligned")}]})
    assert len(result["own"]) == 7, result["own"]
    labels = [button["text"] for button in result["own"]]
    for label in ("‹ Previous", "Next ›", "Done for now", "Back to the sheet"):
        assert label in labels, labels
    for button in result["own"]:
        assert "sh-button" in button["className"].split(), button
        assert button["type"] == "button", button
    assert all("sh-button" in name.split() for name in result["everything"]), result["everything"]

    text = _template_text()
    queries = [query.strip() for block in _style_blocks(text) for query in re.findall(r"@media([^{]*)\{", block)]
    assert queries == ["(min-width: 900px)"], queries
    assert not re.search(r"(?<![\w-])outline(?:-[a-z-]+)?\s*:", text), "the template declares an outline"
    assert ".sh-theme [hidden] { display: none; }" in text

    # A final sheet's controls (the declines toggle, the verdict buttons, Send verdict, and a Send's Try again) are theme buttons too.
    final = _sheet_page(_sample_final(), """
      t.click(t.lastButton("Approve"));
      t.sets[0].resolve();
      await t.tick();
      t.click(t.sendButton());
      await t.tick();
      await t.tick();
      t.sets[1].reject({ code: "unavailable", message: "no" });
      await t.tick();
      const hosts = ["sheet-history", "sheet-final"];
      return {
        own: hosts.flatMap((id) => t.all(elements[id]).filter((node) => node.tagName === "button" || node.tagName === "textarea")).map((node) => ({
          text: node.tagName === "textarea" ? "note" : t.text(node), tag: node.tagName, className: node.className, type: node.getAttribute("type"),
        })),
        everything: t.allButtons().map((button) => button.className),
      };
    """, host={"set": "pending"})
    assert all("sh-button" in name.split() for name in final["everything"]), final["everything"]
    assert [control["text"] for control in final["own"]] == ["Declined findings · 2", "Approve", "Not yet", "note", "Send verdict", "Try again"], final
    for control in final["own"]:
        if control["tag"] == "button":
            assert "sh-button" in control["className"].split() and control["type"] == "button", control
        else:
            assert control["className"] == "sh-field", control


# Bites on: JavaScript or other non-markup text sitting outside the page's script and style blocks.
def test_template_outside_script_and_style_is_only_markup():
    text = _template_text()
    assert text.lstrip().startswith('<meta charset="utf-8">'), text.lstrip()[:60]
    outside = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", "", text)
    prose = re.sub(r"(?s)<!--.*?-->", "", outside)
    prose = re.sub(r"(?s)<[^>]*>", "", prose)
    for pattern in (r"\bconst\s", r"\bfunction\b", r"=>", r";[ \t]*$"):
        assert not re.search(pattern, prose, re.M), "stray script text outside script/style (%s): %r" % (pattern, prose[:200])


# The final sheet: its history, its last card, the draft verdict and the verdict.
FINAL_SAMPLE = json.loads((THEME / "sample-final-sheet.json").read_text(encoding="utf-8"))
FIRST_CARD, SECOND_CARD = "leftovers-handling", "saved-plan-history"

HISTORY_TEXT = "The review ran 4 rounds and fixed 9 things itself. The vet: The vet found nothing left to fix and raised two calls for you."
TRACES_BOARD = "Every statement in the spec traces to your board, your framing, your rulings, your answers, or craft recorded for your veto."
TRACES_NO_BOARD = "Every statement in the spec traces to your framing, your rulings, your answers, or craft recorded for your veto."
BOARD_SAVED = "The approved board is saved with the spec."
BOARD_NOT_SAVED = "The approved board is not saved with the spec."
NEXT_TEXT = (
    "The advisor adds the breakdown to the same PR (or, where the project keeps specs outside the repo or gitignored, "
    "to the spec where it is kept) and vets it, then one merge word covers both."
)
DECLINED_ITEMS = [
    ["li", "Add a calorie count to every recipe on the plan. (why declined: Nothing in your framing asks for nutrition numbers, so adding them would be new scope.)"],
    ["li", "Let two people edit the same plan at once. (why declined: You said the planner is for one household cook, so sharing a plan is out of scope.)"],
]
DRAFT_LINE = "Your verdict is a draft until you send it."
PICK_FIRST_LINE = "Tap Approve or Not yet first."
FAILED_SEND_LINE = "The verdict didn't send."
SLOW_SEND_LINE = "Sending is taking longer than it should. Keep this page open."
CHECKING_LINE = "Making sure your answers are saved…"

# In a scenario: the verdict writes so far, and every control's off state.
VERDICT_WRITES = 'const verdicts = () => t.setLog().filter((call) => call.path === "verdict/final");'


def _sample_final(cards=None, declined=None, approved=True, saved=True):
    sheet = copy.deepcopy(FINAL_SAMPLE)
    if cards is not None:
        sheet["cards"] = cards
    if declined is not None:
        sheet["final"]["declinedFindings"] = declined
    sheet["final"]["approval"] = {"approvedBoard": approved, "boardSavedWithSpec": saved}
    return sheet


def _final_doc(data):
    return {"id": "final", "data": data}


def _draft(verdict, note=""):
    return {"verdict": verdict, "note": note}


def _verdict_write(verdict, note=""):
    return {"path": "verdict/final", "body": _draft(verdict, note)}


def _draft_write(verdict, note=""):
    return {"path": "draft-verdict/final", "body": _draft(verdict, note)}


def _all_off(controls):
    return all(control["disabled"] for control in controls)


def _all_on(controls):
    return not any(control["disabled"] for control in controls)


# Bites on: a final sheet missing its history, declined findings (collapsed until toggled), last card (traces line, board line only with an approved board and following whether it is saved, answer row, note, save line, send row, no badge) or next line, or any of their words.
@pytest.mark.parametrize("declines", [True, False], ids=["with-declines", "no-declines"])
@pytest.mark.parametrize("approved,saved,lines", [
    pytest.param(True, True, [TRACES_BOARD, BOARD_SAVED], id="board-saved"),
    pytest.param(True, False, [TRACES_BOARD, BOARD_NOT_SAVED], id="board-not-saved"),
    pytest.param(False, False, [TRACES_NO_BOARD], id="no-board"),
])
def test_final_sheet_draws_its_history_declines_last_card_and_next_line(approved, saved, lines, declines):
    declined = None if declines else []
    result = _sheet_page(_sample_final(declined=declined, approved=approved, saved=saved), """
      const out = { history: t.history(), count: t.count() };
      out.last = {
        card: [t.lastCard().tagName, t.lastCard().className, t.lastCard().id],
        heading: t.lastHeading(),
        parts: t.lastParts(),
        paragraphs: t.lastParagraphs(),
        buttons: t.lastState(),
        send: [t.sendButton().textContent, t.sendButton().className, t.sendButton().getAttribute("type"), t.sendButton().disabled],
        status: t.sendStatus(),
      };
      out.next = t.nextBox();
      out.parts = t.finalParts();
      if (t.control("declines")) {
        t.click(t.control("declines"));
        out.expanded = t.history();
        t.click(t.control("declines"));
        out.collapsed = t.history();
      }
      return out;
    """)
    history = result["history"]
    assert history["hidden"] is False and history["className"] == "sh-box"
    assert history["heading"] == "How the spec got here"
    assert history["paragraphs"][0] == HISTORY_TEXT
    if declines:
        assert history["paragraphs"] == [HISTORY_TEXT]
        assert history["toggle"] == {"text": "Declined findings · 2", "aria": "false", "type": "button", "className": "sh-button"}
        assert history["listHidden"] is True, "the declined findings were not collapsed"
        assert history["items"] == DECLINED_ITEMS
        assert result["expanded"]["toggle"]["aria"] == "true" and result["expanded"]["listHidden"] is False
        assert result["collapsed"]["toggle"]["aria"] == "false" and result["collapsed"]["listHidden"] is True
    else:
        assert history["paragraphs"] == [HISTORY_TEXT, "No findings were declined."]
        assert history["toggle"] is None and history["items"] == []
        assert "expanded" not in result
    last = result["last"]
    assert last["card"] == ["article", "sh-card", "sheet-approval"]
    assert last["heading"] == "Approve the spec?"
    assert last["paragraphs"] == lines
    assert last["parts"] == (
        ["h2"] + ["p"] * len(lines)
        + ["div.answer-row", "label:Note", "textarea.sh-field", "div.save-line", "div.send-row"]
    ), "the last card's parts, or a badge on it"
    assert last["buttons"]["labels"] == ["Approve", "Not yet"]
    assert last["buttons"]["pressed"] == ["false", "false"]
    assert last["send"] == ["Send verdict", "sh-button sh-button--main", "button", True]
    assert last["status"] == PICK_FIRST_LINE
    assert result["next"] == {"className": "sh-box", "label": "What happens next", "labelClass": "sh-label", "text": NEXT_TEXT}
    assert result["parts"] == {"historyHidden": False, "historyChildren": 4 if declines else 3, "finalHidden": False, "finalChildren": 2}
    # The vet's calls are the same cards, count and rows as on any sheet.
    assert result["count"] == "0 of 2 answered"


# Bites on: a remainder or plain sheet drawing the final sheet's history, last card, Send or next line, or reading the verdict collections.
@pytest.mark.parametrize("sheet", [
    pytest.param(_remainder_of(_named_cards("plan-day", "fridge-check"), unsettled=["fridge-check"]), id="remainder"),
    pytest.param(_sheet(cards=_named_cards("plan-day", "fridge-check")), id="plain"),
])
def test_final_parts_absent_off_a_final_sheet(sheet):
    result = _sheet_page(sheet, """
      return { parts: t.finalParts(), reads: t.reads.map((read) => read.name), controls: t.controls().length };
    """)
    assert result["parts"] == {"historyHidden": True, "historyChildren": 0, "finalHidden": True, "finalChildren": 0}
    assert result["reads"] == ["answers"]
    assert result["controls"] == 2 * (4 + 1)


# Bites on: a verdict tap or its note being written anywhere but draft-verdict/final (as a verdict, or as an answer), a tap not saving at once, a note not waiting for its pause, or the last card feeding the count or the rows.
def test_a_verdict_tap_saves_a_draft_and_never_a_verdict():
    result = _sheet_page(_sample_final(), """
      const out = { before: { count: t.count(), pills: t.rows().map((row) => row.pill[1]) } };
      t.click(t.lastButton("Approve"));
      await t.tick();
      t.type(t.lastNote(), "Looks right", "input");
      out.early = t.sets.length;
      await t.advance(1000);
      t.click(t.lastButton("Not yet"));
      await t.tick();
      out.sets = t.setLog();
      out.after = { count: t.count(), pills: t.rows().map((row) => row.pill[1]) };
      out.last = t.lastState();
      out.save = t.lastSaveText();
      out.status = t.sendStatus();
      return out;
    """, host={"fakeTimers": True})
    assert result["early"] == 1, "the note was written before its pause ended"
    assert result["sets"] == [
        _draft_write("approve"),
        _draft_write("approve", "Looks right"),
        _draft_write("not-yet", "Looks right"),
    ]
    assert result["sets"][-1]["body"] == {"verdict": "not-yet", "note": "Looks right"}
    assert not [call for call in result["sets"] if call["path"].startswith(("verdict/", "answers/"))]
    assert result["after"] == result["before"] == {"count": "0 of 2 answered", "pills": ["Open", "Open"]}
    assert result["last"]["pressed"] == ["false", "true"] and result["last"]["note"] == "Looks right"
    assert result["save"] == "Saved"
    assert result["status"] == DRAFT_LINE


# Bites on: a saved draft verdict not coming back on reopen (its pick or note), a draft counting as a verdict or an answer, a reopen writing anything, a draft that does not fit the schema restoring a pick, or the draft not being read from its own collection.
def test_a_draft_verdict_is_restored_on_reopen_and_counts_as_nothing():
    def reopen(draft):
        return _sheet_page(_sample_final(), """
          await t.advance(200);
          return {
            last: t.lastState(), status: t.sendStatus(), send: t.sendButton().disabled, sets: t.setLog(), count: t.count(),
            reads: t.reads.map((read) => read.name).sort(), controls: t.controls(),
          };
        """, host={"fakeTimers": True, "collections": {"draft-verdict": [_final_doc(draft)]}})

    picked = reopen(_draft("not-yet", "Wait for the board"))
    assert picked["last"]["pressed"] == ["false", "true"]
    assert picked["last"]["note"] == "Wait for the board"
    assert picked["status"] == DRAFT_LINE
    assert picked["send"] is False
    assert picked["sets"] == [], "reopening wrote something"
    assert picked["count"] == "0 of 2 answered"
    assert picked["reads"] == ["answers", "draft-verdict", "verdict"]
    assert _all_on(picked["controls"])

    noted = reopen(_draft(None, "Only a note"))
    assert noted["last"]["pressed"] == ["false", "false"] and noted["last"]["note"] == "Only a note"
    assert noted["status"] == PICK_FIRST_LINE and noted["send"] is True

    for bad in ({"verdict": "maybe", "note": "kept"}, {"verdict": "approve", "note": "kept", "extra": 1}):
        unfit = reopen(bad)
        assert unfit["last"]["pressed"] == ["false", "false"] and unfit["last"]["note"] == "kept"
        assert unfit["send"] is True and unfit["sets"] == []


# Bites on: Send verdict not writing the verdict once (with the pick and note), writing it anywhere else or also writing an answer, saying "sent" before the write resolved, or leaving a control on after it resolved.
def test_send_verdict_writes_one_verdict_and_shows_sent():
    result = _sheet_page(_sample_final(), """
      t.click(t.lastButton("Approve"));
      t.sets[0].resolve();
      await t.tick();
      t.type(t.lastNote(), "Ship it", "change");
      t.sets[1].resolve();
      await t.tick();
      ${VERDICTS}
      const out = { before: { writes: t.sets.length, status: t.sendStatus(), disabled: t.sendButton().disabled } };
      t.click(t.sendButton());
      await t.tick();
      await t.tick();
      out.during = { verdicts: verdicts(), status: t.sendStatus(), controls: t.controls(), send: t.sendButton().disabled, last: t.sets[t.sets.length - 1].path };
      t.sets[t.sets.length - 1].resolve();
      await t.tick();
      out.after = { verdicts: verdicts(), status: t.sendStatus(), controls: t.controls(), send: t.sendButton().disabled, last: t.lastState(), retry: t.sendTryAgain() !== undefined };
      out.paths = t.setLog().map((call) => call.path);
      return out;
    """.replace("${VERDICTS}", VERDICT_WRITES), host={"set": "pending"})
    assert result["before"] == {"writes": 2, "status": DRAFT_LINE, "disabled": False}
    assert result["during"]["last"] == "verdict/final"
    assert result["during"]["verdicts"] == [_verdict_write("approve", "Ship it")]
    assert result["during"]["status"] == "Sending…", "the page said more than it knew before the write resolved"
    assert result["during"]["send"] is True and _all_off(result["during"]["controls"])
    assert result["after"]["verdicts"] == [_verdict_write("approve", "Ship it")], "the verdict was not written exactly once"
    assert result["after"]["status"] == "Verdict sent: Approve"
    assert result["after"]["send"] is True and _all_off(result["after"]["controls"])
    assert result["after"]["last"]["pressed"] == ["true", "false"] and result["after"]["last"]["note"] == "Ship it"
    assert result["after"]["retry"] is False
    assert result["paths"] == ["draft-verdict/final", "draft-verdict/final", "verdict/final"]


# Bites on: Send verdict writing while an answer is rejected or still unsaved at the deadline (or sooner than that), saying anything but how many answers and what to do, or leaving the sheet frozen after refusing.
@pytest.mark.parametrize("count,failed,stalled", [
    pytest.param(1, "1 answer didn't save. Go back to it and tap Try again, then send again.",
                 "1 answer isn't saved yet. Keep this page open until it says Saved, then send again.", id="one-answer"),
    pytest.param(2, "2 answers didn't save. Go back to them and tap Try again, then send again.",
                 "2 answers aren't saved yet. Keep this page open until they say Saved, then send again.", id="two-answers"),
])
def test_send_refuses_while_an_answer_is_unsaved(count, failed, stalled):
    setup = """
      const ids = [__IDS__][0];
      ids.forEach((id) => t.click(t.button(id, "Aligned")));
      t.click(t.lastButton("Approve"));
      t.sets[ids.length].resolve();
      await t.tick();
      ${VERDICTS}
    """.replace("${VERDICTS}", VERDICT_WRITES).replace("__IDS__", json.dumps([FIRST_CARD, SECOND_CARD][:count]))
    rejected = _sheet_page(_sample_final(), setup + """
      ids.forEach((id, index) => t.sets[index].reject({ code: "unavailable", message: "no" }));
      await t.tick();
      t.click(t.sendButton());
      await t.tick();
      await t.tick();
      await t.advance(30000);
      return { status: t.sendStatus(), verdicts: verdicts(), controls: t.controls(), retry: t.sendTryAgain() !== undefined, open: t.openCard(), send: t.sendButton().disabled };
    """, host={"set": "pending", "fakeTimers": True})
    assert rejected["status"] == failed
    assert rejected["verdicts"] == [], "a verdict was written while an answer was rejected"
    assert _all_on(rejected["controls"]) and rejected["send"] is False, "the sheet stayed frozen"
    assert rejected["retry"] is False
    assert rejected["open"] == FIRST_CARD

    unsaved = _sheet_page(_sample_final(), setup + """
      t.click(t.sendButton());
      await t.tick();
      await t.advance(9800);
      const waiting = { status: t.sendStatus(), verdicts: verdicts(), controls: t.controls() };
      await t.advance(200);
      const out = { waiting: waiting, status: t.sendStatus(), verdicts: verdicts(), controls: t.controls(), send: t.sendButton().disabled };
      await t.advance(30000);
      out.later = { status: t.sendStatus(), verdicts: verdicts() };
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert unsaved["waiting"]["status"] == CHECKING_LINE
    assert unsaved["waiting"]["verdicts"] == [] and _all_off(unsaved["waiting"]["controls"])
    assert unsaved["status"] == stalled
    assert unsaved["verdicts"] == [], "a verdict was written while an answer was still unsaved"
    assert _all_on(unsaved["controls"]) and unsaved["send"] is False, "the sheet stayed frozen"
    assert unsaved["later"] == {"status": stalled, "verdicts": []}


# Bites on: the sheet changing, or a second write starting, while Send verdict waits for the answers or waits for the verdict write (a card tap, a note, Not yet, a second Send), or the guard living only in a control's disabled flag.
def test_the_sheet_is_frozen_while_sending():
    result = _sheet_page(_sample_final(), """
      t.click(t.button("leftovers-handling", "Aligned"));
      t.click(t.lastButton("Approve"));
      t.sets[1].resolve();
      await t.tick();
      ${VERDICTS}
      const snapshot = () => ({
        sets: t.sets.length,
        first: t.state("leftovers-handling").pressed,
        second: t.state("saved-plan-history").pressed,
        last: t.lastState().pressed,
        status: t.sendStatus(),
        count: t.count(),
        saves: [t.saveText("leftovers-handling"), t.lastSaveText()],
        controls: t.controls(),
        doneScreen: t.done().hidden,
        doneOff: t.control("done").disabled,
      });
      const attempt = () => {
        t.fire(t.control("done"), "click");
        t.buttons("leftovers-handling").forEach((button) => t.fire(button, "click"));
        t.buttons("saved-plan-history").forEach((button) => t.fire(button, "click"));
        for (const note of [t.note("leftovers-handling"), t.note("saved-plan-history"), t.lastNote()]) {
          const kept = note.value;
          note.value = "sneaky";
          t.fire(note, "input");
          t.fire(note, "change");
          note.value = kept;
        }
        t.lastButtons().forEach((button) => t.fire(button, "click"));
        t.fire(t.sendButton(), "click");
      };
      const out = {};
      t.click(t.sendButton());
      await t.tick();
      out.waiting = snapshot();
      attempt();
      await t.advance(1500);
      out.waitingAfter = snapshot();
      t.sets[0].resolve();
      await t.tick();
      await t.advance(200);
      out.writing = snapshot();
      out.writing.verdicts = verdicts();
      attempt();
      await t.advance(1500);
      out.writingAfter = snapshot();
      out.writingAfter.verdicts = verdicts();
      t.sets[t.sets.length - 1].resolve();
      await t.tick();
      out.sent = snapshot();
      attempt();
      await t.advance(1500);
      out.sentAfter = snapshot();
      out.sentAfter.verdicts = verdicts();
      return out;
    """.replace("${VERDICTS}", VERDICT_WRITES), host={"set": "pending", "fakeTimers": True})
    assert result["waiting"]["status"] == CHECKING_LINE and _all_off(result["waiting"]["controls"])
    assert result["waitingAfter"] == result["waiting"], "the sheet changed while Send verdict waited for the answers"
    assert result["writing"]["status"] == "Sending…" and _all_off(result["writing"]["controls"])
    assert result["writing"]["verdicts"] == [_verdict_write("approve")]
    assert result["writingAfter"] == result["writing"], "the sheet changed, or a second write started, while the verdict write was pending"
    assert result["sent"]["status"] == "Verdict sent: Approve" and _all_off(result["sent"]["controls"])
    assert _all_off(result["sentAfter"]["controls"])
    assert result["sentAfter"]["sets"] == result["sent"]["sets"] == result["writing"]["sets"]
    assert result["sentAfter"]["verdicts"] == [_verdict_write("approve")]
    assert result["sentAfter"]["status"] == result["sent"]["status"]
    for stage in ("waiting", "waitingAfter", "writing", "writingAfter", "sent", "sentAfter"):
        assert result[stage]["doneScreen"] is True and result[stage]["doneOff"] is True, \
            "Done for now was live (or its screen showed) at the %s stage of a Send" % stage


# Bites on: a rejected verdict write showing sent or offering no Try again, a Try again that does not run the whole Send again from the current state, a stalled write saying sent or offering Try again, a late resolve not showing sent, or a late rejection not showing the rejected state.
def test_a_failed_or_stalled_verdict_send():
    for late in ("resolve", "reject"):
        stalled = _sheet_page(_sample_final(), """
          t.click(t.lastButton("Approve"));
          t.sets[0].resolve();
          await t.tick();
          t.click(t.sendButton());
          await t.tick();
          await t.advance(9999);
          const out = { early: t.sendStatus() };
          await t.advance(1);
          const snapshot = () => ({ status: t.sendStatus(), retry: t.sendTryAgain() !== undefined, controls: t.controls(), send: t.sendButton().disabled });
          out.stalled = snapshot();
          t.sets[1].__LATE__({ code: "unavailable", message: "late" });
          await t.tick();
          out.late = snapshot();
          return out;
        """.replace("__LATE__", late), host={"set": "pending", "fakeTimers": True})
        assert stalled["early"] == "Sending…"
        assert stalled["stalled"]["status"] == SLOW_SEND_LINE
        assert stalled["stalled"]["retry"] is False, "a stalled write offered Try again while it could still land"
        assert _all_off(stalled["stalled"]["controls"]) and stalled["stalled"]["send"] is True
        if late == "resolve":
            assert stalled["late"]["status"] == "Verdict sent: Approve"
            assert stalled["late"]["retry"] is False and _all_off(stalled["late"]["controls"])
        else:
            assert stalled["late"]["status"] == FAILED_SEND_LINE
            assert stalled["late"]["retry"] is True and _all_on(stalled["late"]["controls"])

    rejected = _sheet_page(_sample_final(), """
      ${VERDICTS}
      t.click(t.lastButton("Approve"));
      t.sets[0].resolve();
      await t.tick();
      t.click(t.sendButton());
      await t.tick();
      await t.tick();
      t.sets[1].reject({ code: "unavailable", message: "no" });
      await t.tick();
      const out = { rejected: { status: t.sendStatus(), retry: t.sendTryAgain() !== undefined, controls: t.controls(), send: t.sendButton().disabled, verdicts: verdicts() } };
      t.click(t.lastButton("Not yet"));
      t.sets[2].resolve();
      await t.tick();
      t.click(t.sendTryAgain());
      await t.tick();
      await t.tick();
      out.again = { status: t.sendStatus(), retry: t.sendTryAgain() !== undefined, controls: t.controls(), verdicts: verdicts() };
      t.sets[3].resolve();
      await t.tick();
      out.sent = { status: t.sendStatus(), controls: t.controls() };
      return out;
    """.replace("${VERDICTS}", VERDICT_WRITES), host={"set": "pending"})
    assert rejected["rejected"]["status"] == FAILED_SEND_LINE
    assert rejected["rejected"]["retry"] is True and rejected["rejected"]["send"] is False
    assert _all_on(rejected["rejected"]["controls"]), "the sheet stayed frozen after a failed send"
    assert rejected["rejected"]["verdicts"] == [_verdict_write("approve")]
    assert rejected["again"]["status"] == "Sending…" and rejected["again"]["retry"] is False
    assert _all_off(rejected["again"]["controls"])
    assert rejected["again"]["verdicts"] == [_verdict_write("approve"), _verdict_write("not-yet")]
    assert rejected["sent"]["status"] == "Verdict sent: Not yet" and _all_off(rejected["sent"]["controls"])


# Bites on: a sent verdict not coming back on reopen (its status, pressed verdict or note), a reopened sent sheet leaving a control on or writing, a verdict that does not fit the schema counting as sent, or a draft being shown over a sent verdict.
def test_a_sent_verdict_is_shown_on_reopen():
    def reopen(collections, poke=False):
        return _sheet_page(_sample_final(), """
          await t.advance(200);
          const fire = (node) => ["click", "input", "change"].forEach((type) => t.fire(node, type));
          if (__POKE__) {
            t.lastButtons().forEach(fire);
            fire(t.lastNote());
            t.buttons("leftovers-handling").forEach(fire);
            t.fire(t.sendButton(), "click");
          }
          await t.advance(1500);
          return { last: t.lastState(), status: t.sendStatus(), send: t.sendButton().disabled, sets: t.setLog(), controls: t.controls() };
        """.replace("__POKE__", "true" if poke else "false"), host={"fakeTimers": True, "collections": collections})

    sent = reopen({"verdict": [_final_doc(_draft("approve", "Good to go"))], "draft-verdict": [_final_doc(_draft("not-yet", "An older draft"))]}, poke=True)
    assert sent["status"] == "Verdict sent: Approve"
    assert sent["last"]["pressed"] == ["true", "false"] and sent["last"]["note"] == "Good to go"
    assert sent["send"] is True and _all_off(sent["controls"])
    assert sent["sets"] == [], "a sent sheet wrote after reopening"
    assert reopen({"verdict": [_final_doc(_draft("not-yet"))]})["status"] == "Verdict sent: Not yet"

    for name, bad in (
        ("unknown verdict", {"verdict": "maybe", "note": ""}),
        ("no verdict", {"verdict": None, "note": ""}),
        ("extra key", {"verdict": "approve", "note": "", "extra": 1}),
        ("note that is not text", {"verdict": "approve", "note": 3}),
    ):
        ignored = reopen({"verdict": [_final_doc(bad)], "draft-verdict": [_final_doc(_draft("not-yet", "Still a draft"))]})
        assert ignored["status"] == DRAFT_LINE, name
        assert ignored["last"]["pressed"] == ["false", "true"] and ignored["last"]["note"] == "Still a draft", name
        assert ignored["send"] is False and ignored["sets"] == [], name
    only_bad = reopen({"verdict": [_final_doc({"verdict": "maybe", "note": ""})]})
    assert only_bad["status"] == PICK_FIRST_LINE and only_bad["send"] is True


# Bites on: a final sheet with no cards drawing a stepper, rows or cards, a count that is not "Nothing left to answer", or losing its history, last card, Send or next line.
def test_a_final_sheet_with_no_cards():
    result = _sheet_page(_sample_final(cards=[]), """
      ${VERDICTS}
      const out = {
        count: [t.count(), elements["sheet-count"].hidden],
        stepperHidden: elements["sheet-stepper"].hidden,
        itemsHidden: elements["sheet-items"].hidden,
        rows: t.rowNodes().length,
        cards: elements["sheet-cards"].children.length,
        history: t.history(),
        parts: t.finalParts(),
        next: t.nextBox().text,
        status: t.sendStatus(),
      };
      t.click(t.lastButton("Approve"));
      t.sets[0].resolve();
      await t.tick();
      t.click(t.sendButton());
      await t.tick();
      await t.tick();
      out.verdicts = verdicts();
      t.sets[1].resolve();
      await t.tick();
      out.sent = t.sendStatus();
      out.countAfter = t.count();
      return out;
    """.replace("${VERDICTS}", VERDICT_WRITES), host={"set": "pending"})
    assert result["count"] == ["Nothing left to answer", False]
    assert result["stepperHidden"] is True and result["itemsHidden"] is True
    assert result["rows"] == 0 and result["cards"] == 0
    assert result["history"]["hidden"] is False and result["history"]["paragraphs"][0] == HISTORY_TEXT
    assert result["parts"]["finalHidden"] is False and result["parts"]["finalChildren"] == 2
    assert result["next"] == NEXT_TEXT
    assert result["status"] == PICK_FIRST_LINE
    assert result["verdicts"] == [_verdict_write("approve")]
    assert result["sent"] == "Verdict sent: Approve"
    assert result["countAfter"] == "Nothing left to answer"


# Bites on: a failed or stalled read of the draft verdict or of the verdict (not only of the answers) being taken as an empty collection, so the controls turn on, or its Try again not reading all three collections again.
@pytest.mark.parametrize("host,stall", [
    pytest.param({"readByCollection": {"draft-verdict": ["reject", "docs"]}}, False, id="draft-verdict-rejects"),
    pytest.param({"readByCollection": {"verdict": ["reject", "docs"]}}, False, id="verdict-rejects"),
    pytest.param({"readByCollection": {"verdict": ["pending", "docs"]}, "fakeTimers": True}, True, id="verdict-stalls"),
    pytest.param({"readByCollection": {"answers": ["reject", "docs"]}}, False, id="answers-reject"),
])
def test_a_failed_verdict_read_keeps_the_sheet_off(host, stall):
    result = _sheet_page(_sample_final(), """
      if (__STALL__) await t.advance(10000);
      const snapshot = () => ({ gate: t.gate().message, hidden: t.gate().hidden, retry: t.gate().retry !== undefined, controls: t.controls(), send: t.sendButton().disabled, status: t.sendStatus(), reads: t.reads.map((read) => read.name) });
      const out = { failed: snapshot() };
      t.fire(t.lastButton("Approve"), "click");
      t.fire(t.sendButton(), "click");
      out.writes = t.sets.length;
      if (t.gate().retry) {
        t.click(t.gate().retry);
        await t.tick();
        await t.tick();
      }
      out.recovered = snapshot();
      return out;
    """.replace("__STALL__", "true" if stall else "false"), host=host)
    failed = result["failed"]
    assert failed["gate"] == "Your saved answers couldn't be loaded."
    assert failed["hidden"] is False and failed["retry"] is True
    assert _all_off(failed["controls"]) and failed["send"] is True
    assert failed["status"] == ""
    assert failed["reads"] == ["answers", "draft-verdict", "verdict"]
    assert result["writes"] == 0
    assert result["recovered"]["hidden"] is True
    assert result["recovered"]["reads"] == ["answers", "draft-verdict", "verdict"] * 2, "the retry did not read all three again"
    assert _all_on([control for control in result["recovered"]["controls"] if control["text"] != "Send verdict"])
    assert result["recovered"]["send"] is True and result["recovered"]["status"] == PICK_FIRST_LINE


NON_OWNER_CASES = [
    pytest.param({"claude": "missing"}, id="no-window-claude"),
    pytest.param({"claude": "no-use"}, id="use-is-not-a-function"),
    pytest.param({"db": "null"}, id="store-is-null"),
    pytest.param({"db": "reject"}, id="use-db-rejects"),
    pytest.param({"user": "null"}, id="user-is-null"),
    pytest.param({"user": "viewer"}, id="is-owner-false"),
    pytest.param({"user": "is-owner-rejects"}, id="is-owner-rejects"),
]


# Bites on: a viewer who is not the owner, or a view with no store, getting a working last card or Send verdict, or any write or read.
@pytest.mark.parametrize("host", NON_OWNER_CASES)
def test_the_last_card_and_send_are_off_for_a_non_owner_and_with_no_store(host):
    result = _sheet_page(_sample_final(), """
      const fire = (node) => ["click", "input", "change"].forEach((type) => t.fire(node, type));
      t.lastButtons().forEach(fire);
      t.lastNote().value = "sneaky";
      fire(t.lastNote());
      fire(t.sendButton());
      await t.advance(1500);
      return { controls: t.controls(), send: t.sendButton().disabled, sets: t.sets.length, reads: t.reads.length, last: t.lastState(), parts: t.finalParts() };
    """, host=dict(host, fakeTimers=True))
    assert result["parts"]["finalChildren"] == 2, "the last card did not draw"
    assert _all_off(result["controls"]) and result["send"] is True
    assert result["sets"] == 0, "a control wrote although the viewer cannot answer"
    assert result["reads"] == 0
    assert result["last"]["pressed"] == ["false", "false"]


# Bites on: a schema that does not say what a verdict is still giving the last card working buttons, or Send verdict.
@pytest.mark.parametrize("mutate", [
    pytest.param(lambda schema: schema["$defs"].pop("draftVerdict"), id="no-draft-verdict-definition"),
    pytest.param(lambda schema: schema["$defs"].pop("verdict"), id="no-verdict-definition"),
    pytest.param(lambda schema: schema["$defs"]["draftVerdict"]["properties"]["verdict"].update(enum=["approve", "not-yet", "maybe", None]), id="a-verdict-with-no-words"),
])
def test_a_schema_without_a_verdict_shape_keeps_the_last_card_off(mutate):
    files = _sample_files(_sample_final())
    files["sheet.schema.json"]["body"] = json.dumps(_schema_without_answers(mutate))
    page = _run_page(files, scenario="""
      await t.advance(200);
      const fire = (node) => ["click", "input", "change"].forEach((type) => t.fire(node, type));
      t.lastButtons().forEach(fire);
      fire(t.lastNote());
      fire(t.sendButton());
      await t.advance(1500);
      return { last: t.lastState(), send: t.sendButton().disabled, sets: t.setLog(), cardControls: t.state("leftovers-handling").disabled, gate: t.gate().hidden };
    """, host={"fakeTimers": True})
    assert page["settled"] and page["errors"] == [], page
    result = page["result"]
    assert result["last"]["disabled"][-1] is True and all(result["last"]["disabled"])
    assert result["send"] is True and result["sets"] == []
    assert result["cardControls"] == [False] * 5, "the cards stopped working too"
    assert result["gate"] is True


# Bites on: Done for now on a final sheet not saying the verdict counts only after Send verdict (or saying it elsewhere), not saving a pending verdict note, or changing its message on a remainder sheet.
def test_done_for_now_on_a_final_sheet_names_send_verdict():
    final = _sheet_page(_sample_final(), """
      t.type(t.lastNote(), "A thought", "input");
      const pending = t.sets.length;
      t.click(t.control("done"));
      const writes = t.setLog();
      t.sets.forEach((call) => call.resolve());
      await t.tick();
      return { pending: pending, writes: writes, message: t.done().message, parts: t.finalParts() };
    """, host={"set": "pending", "fakeTimers": True})
    assert final["pending"] == 0
    assert final["writes"] == [_draft_write(None, "A thought")], "Done for now left the pending verdict note unwritten"
    assert final["message"] == "Your answers are saved as drafts. Open this link again any time to carry on. Your verdict counts only once you tap Send verdict."
    assert final["parts"]["historyHidden"] is True and final["parts"]["finalHidden"] is True

    remainder = _sheet_page(_remainder_of(_named_cards("plan-day"), unsettled=["plan-day"]), "t.click(t.control(\"done\")); return t.done().message;")
    assert remainder == "Your answers are saved as drafts. Open this link again any time to carry on, and tell the session when the sheet is done."


# Bites on: the usage doc leaving out the final sheet, the draft verdict's and the verdict's paths, Send verdict, or that a draft never counts.
def test_usage_doc_describes_the_final_sheet():
    doc = USAGE_DOC.read_text(encoding="utf-8")
    assert "## A final sheet" in doc
    section = doc.split("## A final sheet", 1)[1].split("\n## ", 1)[0]
    for needle in ("`draft-verdict/final`", "`verdict/final`", "`$defs/draftVerdict`", "`$defs/verdict`", "Send verdict"):
        assert needle in section, needle
    squeezed = " ".join(section.split())
    assert "never counts" in squeezed
    assert "no cards" in squeezed
    assert doc.index("## How a sheet is laid out") < doc.index("## A final sheet") < doc.index("## How answers come back")
    answers = doc.split("## How answers come back", 1)[1].split("\n## ", 1)[0]
    assert "Send verdict" in answers and "`verdict/final`" in answers
    assert "never acts on a draft" in " ".join(answers.split())


# Bites on: a draft verdict that is pending or rejected being reported as saved on the Done screen (the last card is hidden there), or Done for now not sending the owner back to the last card's Try again.
def test_done_for_now_counts_an_unsaved_verdict_draft():
    result = _sheet_page(_sample_final(), """
      const out = {};
      t.click(t.lastButton("Approve"));
      t.click(t.control("done"));
      out.pending = t.done().message;
      t.sets[0].reject({ code: "unavailable", message: "try later" });
      await t.tick();
      out.failed = t.done().message;
      t.click(t.control("back"));
      out.back = { done: t.done().hidden, final: t.finalParts().finalHidden, retry: t.lastSaveText() };
      return out;
    """, host={"set": "pending"})
    assert result["pending"] == "1 answer isn't saved yet. Keep this page open until this says they're saved."
    assert result["failed"] == "1 answer didn't save. Go back to the sheet and tap Try again on each."
    assert result["back"]["done"] is True and result["back"]["final"] is False


# Bites on: leaving a final sheet going unguarded while its draft verdict (pick or note) is unconfirmed or a Send is in flight, or the guard staying on once the verdict is sent.
def test_leaving_a_final_sheet_is_guarded_while_the_verdict_is_unconfirmed_or_sending():
    result = _sheet_page(_sample_final(), """
      const out = {};
      out.idle = t.unload();
      t.click(t.lastButton("Approve"));
      out.pick = t.unload();
      t.sets[0].resolve();
      await t.tick();
      out.pickSaved = t.unload();
      t.type(t.lastNote(), "Ship it", "input");
      out.note = t.unload();
      t.type(t.lastNote(), "Ship it", "change");
      t.sets[1].resolve();
      await t.tick();
      out.noteSaved = t.unload();
      t.click(t.sendButton());
      await t.tick();
      await t.tick();
      out.sending = { status: t.sendStatus(), guarded: t.unload() };
      t.sets[t.sets.length - 1].resolve();
      await t.tick();
      out.sent = { status: t.sendStatus(), guarded: t.unload() };
      return out;
    """, host={"set": "pending"})
    assert result["idle"] is False
    assert result["pick"] is True, "an unconfirmed draft verdict pick was not guarded"
    assert result["pickSaved"] is False
    assert result["note"] is True, "a draft verdict note waiting to save was not guarded"
    assert result["noteSaved"] is False
    assert result["sending"] == {"status": "Sending…", "guarded": True}, "a Send in flight was not guarded"
    assert result["sent"] == {"status": "Verdict sent: Approve", "guarded": False}


# Bites on: the final sheet's shared wording being retyped in the page or the prose renderer instead of read from sheet-words.json, or the usage doc leaving that file out of the published files.
def test_final_sheet_wording_has_one_home():
    words = json.loads((THEME / "sheet-words.json").read_text(encoding="utf-8"))
    prose_source = (THEME.parent / "lib" / "sheet_prose.py").read_text(encoding="utf-8")
    for key in ("history", "tracesBoard", "tracesNoBoard", "boardSaved", "boardNotSaved", "next", "noDeclines", "approveHeading", "nextHeading"):
        for name, text in (("the page", _template_text()), ("sheet_prose.py", prose_source)):
            assert words[key] not in text, "%s retypes the shared wording %r" % (name, key)
    assert re.search(r"""fetchJson\(\s*['"]sheet-words\.json['"]""", _template_text())
    publishing = USAGE_DOC.read_text(encoding="utf-8").split("## Publishing a sheet", 1)[1]
    assert '"sheet-words.json": "<staged sheet-words.json>"' in publishing
    assert "`sheet-words.json`" in publishing
