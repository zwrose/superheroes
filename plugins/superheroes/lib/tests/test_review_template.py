"""Guards for the review template page and its usage doc."""
import copy
import hashlib
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
    this.parent = null;
    this.disabled = false;
    this.value = "";
    this.attributes = {};
    this.listeners = {};
    this.listenerOptions = {};
    this.focusCount = 0;
    this.captured = [];
    this.clientWidth = 0;
    this.clientHeight = 0;
    this.scrollLeft = 0;
    this.scrollTop = 0;
    this.naturalWidth = 0;
    this.naturalHeight = 0;
    this.rect = { left: 0, top: 0 };
  }
  focus() {
    this.focusCount += 1;
    document.activeElement = this;
  }
  setPointerCapture(id) {
    this.captured.push(id);
  }
  getBoundingClientRect() {
    return this.rect;
  }
  setAttribute(name, value) {
    // What a card picture already listens for at the moment it is given its src.
    if (name === "src") this.listenersAtSrc = Object.keys(this.listeners).filter((type) => this.listeners[type].length > 0);
    this.attributes[name] = String(value);
  }
  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  addEventListener(type, listener, options) {
    (this.listeners[type] = this.listeners[type] || []).push(listener);
    // The options each listener was registered with, in step with `listeners`.
    (this.listenerOptions[type] = this.listenerOptions[type] || []).push(options);
  }
  appendChild(child) {
    if (child.tagName === "#fragment") {
      child.children.splice(0).forEach((inner) => {
        inner.parent = this;
        this.children.push(inner);
      });
    } else {
      child.parent = this;
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
  "sheet-count", "sheet-why", "sheet-items", "sheet-stepper", "sheet-stepper-bottom", "sheet-footer",
  "sheet-history", "sheet-final"].forEach((id) => {
  elements[id] = new Node("div");
  elements[id].id = id;
});
elements["sheet-status"].hidden = false;
elements["sheet-gate"].hidden = true;
elements["sheet-error"].hidden = true;
elements["sheet-title"].textContent = "Review sheet";
// The sheet's own parts start hidden, with the classes the markup gives them, until a sheet is drawn.
const markupClasses = { "sheet-why": "sh-box", "sheet-items": "sheet-list", "sheet-stepper": "sheet-stepper", "sheet-stepper-bottom": "sheet-stepper", "sheet-footer": "sheet-footer", "sheet-history": "sh-box" };
["sheet-count", "sheet-why", "sheet-items", "sheet-stepper", "sheet-stepper-bottom", "sheet-footer", "sheet-history", "sheet-final"].forEach((id) => {
  elements[id].hidden = true;
  elements[id].className = markupClasses[id] || "";
});
// The sheet page the image view covers, and the view: a bar (the picture's description, the hint, Close) and a frame holding one picture.
// Nested as the template nests them: the sheet's parts under .sheet-page, and the view beside it, not inside it.
const documentRoot = new Node("div");
const sheetPageNode = new Node("div");
sheetPageNode.className = "sheet-page";
documentRoot.appendChild(sheetPageNode);
Object.keys(elements).forEach((id) => sheetPageNode.appendChild(elements[id]));
const viewerNodes = {};
[["sheet-viewer", "div"], ["sheet-viewer-caption", "span"], ["sheet-viewer-close", "button"], ["sheet-viewer-frame", "div"], ["sheet-viewer-picture", "img"]].forEach(([id, tag]) => {
  viewerNodes[id] = new Node(tag);
  viewerNodes[id].id = id;
  elements[id] = viewerNodes[id];
});
viewerNodes["sheet-viewer"].className = "sh-theme sheet-viewer";
viewerNodes["sheet-viewer"].hidden = true;
viewerNodes["sheet-viewer-close"].className = "sh-button";
viewerNodes["sheet-viewer-close"].setAttribute("type", "button");
viewerNodes["sheet-viewer-close"].textContent = "Close";
const viewerBar = new Node("div");
viewerBar.className = "sheet-viewer-bar";
viewerBar.children = [viewerNodes["sheet-viewer-caption"], viewerNodes["sheet-viewer-close"]];
viewerNodes["sheet-viewer-frame"].children = [viewerNodes["sheet-viewer-picture"]];
viewerNodes["sheet-viewer"].children = [viewerBar, viewerNodes["sheet-viewer-frame"]];
documentRoot.appendChild(viewerNodes["sheet-viewer"]);
[viewerBar, viewerNodes["sheet-viewer-frame"]].forEach((node) => { node.parent = viewerNodes["sheet-viewer"]; });
[viewerNodes["sheet-viewer-caption"], viewerNodes["sheet-viewer-close"]].forEach((node) => { node.parent = viewerBar; });
viewerNodes["sheet-viewer-picture"].parent = viewerNodes["sheet-viewer-frame"];
// A frame's scroll size is its own size or the picture's width and height attributes, whichever is larger, so a scroll position can really be clamped.
["Width", "Height"].forEach((side) => {
  Object.defineProperty(viewerNodes["sheet-viewer-frame"], "scroll" + side, {
    get() {
      const picture = this.children.find((child) => child.tagName === "img");
      return Math.max(this["client" + side], picture ? Number(picture.getAttribute(side.toLowerCase())) || 0 : 0);
    },
  });
});
const documentListeners = {};
const document = {
  title: "Review sheet",
  activeElement: null,
  addEventListener: (type, listener) => {
    (documentListeners[type] = documentListeners[type] || []).push(listener);
  },
  getElementById: (id) => elements[id],
  querySelector: (selector) => (selector === ".sheet-page" ? sheetPageNode : null),
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
const readCounts = {};
// `host.later` gives a collection's documents from its second read on, as another open copy of the sheet would have written them in between.
// A collection name may be nested, as the store's paths are: a document path has an even
// number of segments and a collection path an odd number. Documents the page (or a scenario) wrote and the store
// accepted are read back from the collection their path sits directly under, as a real store would give them.
const written = {};
const writtenIn = (name) => Object.keys(written)
  .filter((path) => path.startsWith(name + "/") && !path.slice(name.length + 1).includes("/"))
  .map((path) => ({ id: path.slice(name.length + 1), data: written[path] }));
const docsOf = (name) => {
  readCounts[name] = (readCounts[name] || 0) + 1;
  let base;
  if (readCounts[name] > 1 && host.later && host.later[name]) base = host.later[name];
  else base = host.collections ? host.collections[name] || [] : name === "answers" ? host.docs : [];
  const added = writtenIn(name);
  return base.filter((doc) => !added.some((extra) => extra.id === doc.id)).concat(added);
};
if (host.noCrypto) Object.defineProperty(globalThis, "crypto", { value: undefined, configurable: true });
if (host.noRandom) Object.defineProperty(globalThis, "crypto", { value: { subtle: globalThis.crypto.subtle }, configurable: true });
const fakeStore = {
  doc: (path) => ({
    set: (body) => {
      const call = deferred();
      call.path = path;
      call.body = JSON.parse(JSON.stringify(body));
      setLog.push(call);
      call.promise.then(() => { written[path] = call.body; }, () => {});
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
const windowListeners = {};
const window = {
  addEventListener: (type, listener) => {
    if (type === "beforeunload") unloadListeners.push(listener);
    (windowListeners[type] = windowListeners[type] || []).push(listener);
  },
};
const observers = [];
if (host.resizeObserver) {
  globalThis.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.observed = [];
      this.disconnected = false;
      observers.push(this);
    }
    observe(node) {
      this.observed.push(node);
    }
    disconnect() {
      this.disconnected = true;
    }
  };
}
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
  const bytes = () => Buffer.from(file.body, "utf8");
  return {
    ok: file.status >= 200 && file.status < 300,
    status: file.status,
    // The exact bytes served, as a real response gives them (a byte-order mark included); text() drops that mark, as a browser does.
    arrayBuffer: async () => { const served = bytes(); return served.buffer.slice(served.byteOffset, served.byteOffset + served.length); },
    text: async () => file.body.replace(/^\ufeff/, ""),
  };
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
const fire = (node, type, fields) => {
  // A browser ignores preventDefault from a listener registered passive.
  let passiveNow = false;
  const event = Object.assign({ type: type, target: node, defaultPrevented: false, preventDefault() { if (!passiveNow) this.defaultPrevented = true; } }, fields);
  (node.listeners[type] || []).forEach((listener, index) => {
    const options = (node.listenerOptions[type] || [])[index];
    passiveNow = Boolean(options && typeof options === "object" && options.passive);
    listener(event);
  });
  passiveNow = false;
  return event;
};
const tools = {
  sets: setLog,
  written: () => JSON.parse(JSON.stringify(written)),
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
  // The words a person reads: the open/closed cue is a drawn mark (aria-hidden), not part of a control's words.
  text: (node) => [...walk(node)].filter((item) => item.children.length === 0 && !hasClass(item, "sheet-cue")).map((item) => item.textContent).filter((item) => item !== "").join(" "),
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
      // The label, then each chip: the chips' wrapper is read through, and `chips` says where it sits.
      parts: node.children.filter((child) => !hasClass(child, "sheet-cue")).flatMap((child) => (
        hasClass(child, "sheet-fold-chips") ? child.children.map((chip) => [chip.className, chip.textContent]) : [[child.className, child.textContent]]
      )),
      chips: (() => {
        const index = node.children.findIndex((child) => hasClass(child, "sheet-fold-chips"));
        return index < 0 ? null : { className: node.children[index].className, index };
      })(),
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
  // The Previous and Next pair below the open card, as `stepper` reads the top one.
  bottomStepper: () => {
    const parts = elements["sheet-stepper-bottom"].children;
    const named = (label) => parts.find((child) => child.tagName === "button" && child.textContent === label);
    return {
      hidden: elements["sheet-stepper-bottom"].hidden,
      labels: parts.map((child) => child.textContent),
      prevDisabled: named("‹ Previous").disabled,
      nextDisabled: named("Next ›").disabled,
    };
  },
  why: () => ({
    hidden: elements["sheet-why"].hidden,
    heading: elements["sheet-why"].children.find((child) => child.tagName === "h2").textContent,
    text: elements["sheet-why"].children.find((child) => child.tagName === "p").textContent,
  }),
  // The page's own controls by name, so a scenario can press them as a person would.
  control: (name) => {
    const among = (host, label) => host.children.find((child) => child.tagName === "button" && child.textContent === label);
    return {
      previous: () => among(elements["sheet-stepper"], "‹ Previous"),
      next: () => among(elements["sheet-stepper"], "Next ›"),
      bottomPrevious: () => among(elements["sheet-stepper-bottom"], "‹ Previous"),
      bottomNext: () => among(elements["sheet-stepper-bottom"], "Next ›"),
      fold: () => elements["sheet-items"].children.find((child) => hasClass(child, "sheet-fold")),
      declines: () => elements["sheet-history"].children.find((child) => child.tagName === "button"),
    }[name]();
  },
  footer: () => ({ hidden: elements["sheet-footer"].hidden, caption: elements["sheet-footer"].children[0].textContent, captions: elements["sheet-footer"].children.map((child) => child.textContent) }),
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
      toggle: toggle ? { text: tools.text(toggle), aria: toggle.getAttribute("aria-expanded"), type: toggle.getAttribute("type"), className: toggle.className } : null,
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
  // The card's own paragraphs: the no-digest caption is a caption, kept apart (digestCaption).
  lastParagraphs: () => tools.lastCard().children.filter((child) => child.tagName === "p" && !hasClass(child, "sh-caption")).map((child) => child.textContent),
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
  // The no-digest caption on the last card: shown only when it and the final sheet are both shown.
  digestCaption: () => {
    const node = tools.lastCard().children.find((child) => child.tagName === "p" && hasClass(child, "sh-caption"));
    return node ? { hidden: node.hidden || elements["sheet-final"].hidden, text: node.textContent } : null;
  },
  // What sits directly below the last card, and the box after it.
  afterLast: () => {
    const kids = elements["sheet-final"].children;
    const at = kids.indexOf(tools.lastCard());
    const node = kids[at + 1];
    return node ? { tagName: node.tagName, className: node.className, text: node.textContent, hidden: node.hidden || elements["sheet-final"].hidden } : null;
  },
  nextBox: () => {
    const box = elements["sheet-final"].children.find((child) => hasClass(child, "sh-box"));
    return { className: box.className, label: box.children[0].textContent, labelClass: box.children[0].className, text: box.children[1].textContent };
  },
  // The order of what the final sheet holds, by tag and class.
  finalOrder: () => elements["sheet-final"].children.map((child) => child.tagName + (child.className ? "." + child.className.split(/\s+/).join(".") : "")),
  // Every node anywhere on the page, with its own text, so a scenario can look for words wherever they are drawn.
  everyText: () => Object.values(elements).flatMap((root) => [...walk(root)]).map((node) => node.textContent).filter((text) => text !== ""),
  everyClass: () => Object.values(elements).flatMap((root) => [...walk(root)]).map((node) => node.className),
  // Every control a person could press or type in on the cards and the last card, with whether it is off.
  controls: () => [...walk(elements["sheet-cards"]), ...walk(elements["sheet-final"])]
    .filter((node) => node.tagName === "button" || node.tagName === "textarea")
    .map((node) => ({ text: node.tagName === "textarea" ? "note" : tools.text(node), disabled: node.disabled })),
  // The image view: its parts, what is shown, and the sheet behind it.
  view: {
    root: viewerNodes["sheet-viewer"],
    caption: viewerNodes["sheet-viewer-caption"],
    close: viewerNodes["sheet-viewer-close"],
    frame: viewerNodes["sheet-viewer-frame"],
    picture: viewerNodes["sheet-viewer-picture"],
    page: sheetPageNode,
  },
  focused: () => document.activeElement,
  // A key pressed with focus anywhere: a browser gives it to the focused node and then to the document, so a listener on the document hears it wherever focus is.
  fireDocument: (type, fields) => {
    const event = Object.assign({ type: type, target: document.activeElement, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, fields);
    (documentListeners[type] || []).forEach((listener) => listener(event));
    return event;
  },
  // Focus leaves everything the page drew, as a click on the view's frame leaves it on the page body.
  blur: () => { document.activeElement = null; },
  // A card's pictures, in order (the node that opens the view, or null where the picture is now a missing line).
  pictures: (id) => tools.all(tools.card(id)).filter((node) => node.tagName === "img"),
  figures: (id) => tools.all(tools.card(id)).filter((node) => node.tagName === "figure"),
  // A tap as a browser handles it: nothing under an inert sheet can be activated, and a disabled control ignores it.
  press: (node) => {
    for (let up = node; up; up = up.parent) {
      if (up.getAttribute("inert") !== null) return false;
    }
    return tools.click(node);
  },
  // Loads the view's picture at a natural size, in a frame of a given size, as the browser does once the file arrives.
  loadView: (natural, frame) => {
    viewerNodes["sheet-viewer-frame"].clientWidth = frame[0];
    viewerNodes["sheet-viewer-frame"].clientHeight = frame[1];
    viewerNodes["sheet-viewer-picture"].naturalWidth = natural[0];
    viewerNodes["sheet-viewer-picture"].naturalHeight = natural[1];
    fire(viewerNodes["sheet-viewer-picture"], "load");
  },
  // A pointer event on the frame, with fields a browser gives (pointerId, clientX, clientY, timeStamp).
  pointer: (type, fields) => fire(viewerNodes["sheet-viewer-frame"], type, fields),
  shown: () => ({
    width: Number(viewerNodes["sheet-viewer-picture"].getAttribute("width")),
    height: Number(viewerNodes["sheet-viewer-picture"].getAttribute("height")),
    left: viewerNodes["sheet-viewer-frame"].scrollLeft,
    top: viewerNodes["sheet-viewer-frame"].scrollTop,
  }),
  resizeWindow: () => (windowListeners.resize || []).forEach((listener) => listener({ type: "resize" })),
  observers: observers,
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
        elif re.fullmatch(r"verdict/[0-9a-f]{64}", path):
            VERDICT_VALIDATOR.validate(recorded["body"])
            assert recorded["body"]["sheet"] == path.split("/")[1], "a verdict not stored under its own revision's digest"
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
    assert re.search(r"""fetch(?:Json|File)\(\s*['"]sheet\.json['"]""", text)
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


# Bites on: a final sheet drawn, or the store reached for, when its wording file is missing, not valid JSON or cannot be fetched.
@pytest.mark.parametrize("broken, expected", [
    ({"status": 404, "body": "missing"}, "HTTP 404"),
    ({"status": 200, "body": '{"history": '}, "valid JSON"),
    ({"reject": True}, "could not be loaded"),
], ids=["missing", "invalid-json", "rejected"])
def test_a_final_sheet_without_its_wording_file_shows_the_error_box(broken, expected):
    files = _sample_files(_sample_final())
    files["sheet-words.json"] = broken
    page = _run_page(files, scenario="""
      return { uses: t.uses, reads: t.reads.length, sets: t.sets.length };
    """)
    _assert_error_shown(page)
    assert any("wording file" in error and expected in error for error in page["errors"]), page["errors"]
    assert page["result"] == {"uses": [], "reads": 0, "sets": 0}


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


# The image view. A card with two pictures, the first with a caption; the view is opened from a card picture and shows exactly one.
def _picture_card(card_id="pic-card"):
    return _card(
        card_id,
        images=[
            {"src": "plan.png", "alt": "The plan drawn out", "caption": "The draft plan"},
            {"src": "https://example.test/fridge.png", "alt": "The fridge"},
        ],
        recommendation={"text": "Say yes.", "reason": "It is cheap.", "optionId": "yes"},
    )


# A pointer event on the view's frame, as a browser sends it: p(type, id, x, y, time).
POINTER = 'const p = (type, id, x, y, time, kind) => t.pointer(type, { pointerId: id, clientX: x, clientY: y, timeStamp: time || 0, pointerType: kind || "touch" });'
# A wide picture (800 x 400) in a frame of 400 x 300: it fits at 400 x 200 and sits centred, 50 px from the top and bottom.
OPEN_WIDE = """
  const view = t.view;
  t.click(t.pictures("pic-card")[0]);
  t.loadView([800, 400], [400, 300]);
"""


# Bites on: a card picture that does not open the view by tap, Enter or Space (or opens it with another picture's src or alt), a view holding more than one picture or offering more than Close, the sheet left live behind it, a Close or Escape that leaves the view up, the sheet inert, the src set or the focus lost (including Escape straight after a keyboard open).
def test_a_card_picture_opens_the_view_and_close_returns_to_the_card():
    result = _answer_page([_picture_card()], """
      const view = t.view;
      const [first, second] = t.pictures("pic-card");
      const who = () => (t.focused() === view.close ? "close" : t.focused() === first ? "first" : t.focused() === second ? "second" : "other");
      const state = () => ({
        hidden: view.root.hidden,
        src: view.picture.getAttribute("src"),
        alt: view.picture.getAttribute("alt"),
        caption: view.caption.textContent,
        label: view.root.getAttribute("aria-label"),
        images: t.all(view.root).filter((node) => node.tagName === "img").length,
        controls: t.all(view.root).filter((node) => node.tagName === "button").map((node) => node.textContent),
        inert: view.page.getAttribute("inert"),
        focus: who(),
      });
      const out = {
        before: state(),
        opener: ["tabindex", "role", "aria-label"].map((name) => first.getAttribute(name)),
      };
      t.click(first);
      out.tap = state();
      out.draggable = view.picture.getAttribute("draggable");
      t.click(view.close);
      out.closed = state();
      const enter = t.fire(second, "keydown", { key: "Enter" });
      out.enter = state();
      out.enterPrevented = enter.defaultPrevented;
      t.fireDocument("keydown", { key: "Escape" });
      out.enterEscaped = state();
      t.fire(first, "keydown", { key: " " });
      out.spaceDown = state().hidden;
      t.fire(first, "keyup", { key: " " });
      out.space = state();
      t.fireDocument("keydown", { key: "Escape" });
      out.spaceEscaped = state();
      t.fire(second, "keydown", { key: "a" });
      out.otherKey = state().hidden;
      return out;
    """)
    assert result["before"]["hidden"] is True and result["before"]["inert"] is None
    assert result["opener"] == ["0", "button", "Open picture: The plan drawn out"]

    def opened(src, alt):
        return {"hidden": False, "src": src, "alt": alt, "caption": alt, "label": alt, "images": 1, "controls": ["Close"], "inert": "", "focus": "close"}

    def closed(who):
        return {"hidden": True, "src": None, "inert": None, "focus": who}

    assert result["tap"] == opened("plan.png", "The plan drawn out")
    assert result["draggable"] == "false"
    assert {key: result["closed"][key] for key in ("hidden", "src", "inert", "focus")} == closed("first")
    assert result["enter"] == opened("https://example.test/fridge.png", "The fridge")
    assert result["enterPrevented"] is True
    assert {key: result["enterEscaped"][key] for key in ("hidden", "src", "inert", "focus")} == closed("second")
    assert result["spaceDown"] is True, "Space opened the view before the key came up"
    assert result["space"] == opened("plan.png", "The plan drawn out")
    assert {key: result["spaceEscaped"][key] for key in ("hidden", "src", "inert", "focus")} == closed("first")
    assert result["otherKey"] is True


# Bites on: an Escape heard only by the view itself, so that with focus on the page body (after a click in the view's frame) the view stays up, the sheet stays inert, the src stays set or the focus is not returned to the opener; or an Escape with the view shut that changes anything or throws.
def test_escape_closes_the_view_with_focus_outside_it():
    result = _answer_page([_picture_card()], """
      const view = t.view;
      const [first] = t.pictures("pic-card");
      const state = () => ({
        hidden: view.root.hidden,
        src: view.picture.getAttribute("src"),
        inert: view.page.getAttribute("inert"),
        focus: t.focused() === first ? "first" : t.focused() === view.close ? "close" : t.focused() === null ? "none" : "other",
      });
      t.click(first);
      const opened = state();
      t.blur();
      const blurred = state();
      t.fireDocument("keydown", { key: "Escape" });
      const closed = state();
      let thrown = null;
      try {
        t.fireDocument("keydown", { key: "Escape" });
      } catch (error) {
        thrown = String(error);
      }
      return { opened, blurred, closed, again: state(), thrown };
    """)
    assert result["opened"] == {"hidden": False, "src": "plan.png", "inert": "", "focus": "close"}
    assert result["blurred"] == {"hidden": False, "src": "plan.png", "inert": "", "focus": "none"}, "the focus never left the view, so the test proves nothing"
    assert result["closed"] == {"hidden": True, "src": None, "inert": None, "focus": "first"}
    assert result["again"] == result["closed"]
    assert result["thrown"] is None


# Bites on: the image view in the template losing its hidden start, nesting inside the sheet page (so the sheet's inert would cover it), losing its dialog roles, or losing its Close button or its zoom hint.
def test_the_image_view_in_the_template_is_a_hidden_modal_beside_the_sheet_page():
    text = _template_text()
    view = re.search(r'<div id="sheet-viewer"([^>]*)>', text)
    assert view, "the template has no #sheet-viewer"
    attributes = view.group(1)
    assert re.search(r"\bhidden\b", attributes)
    assert 'role="dialog"' in attributes and 'aria-modal="true"' in attributes
    page = re.search(r'<div class="sheet-page">', text)
    assert page and page.start() < view.start()
    depth = 0
    for tag in re.finditer(r"<(/?)div\b[^>]*>", text[page.start():view.start()]):
        depth += -1 if tag.group(1) else 1
    assert depth == 0, "#sheet-viewer sits inside .sheet-page"
    body = text[view.end():]
    assert "Pinch or double-tap to zoom." in body
    assert re.search(r'<button id="sheet-viewer-close"[^>]*>\s*Close\s*</button>', body)


# Bites on: the sheet behind the view staying live (an answer button that can still be activated and writes an answer while the view covers it), or the view offering an answer control of its own.
def test_the_sheet_behind_the_view_cannot_be_answered_while_it_is_open():
    result = _answer_page([_picture_card()], """
      const view = t.view;
      t.click(t.pictures("pic-card")[0]);
      const answer = t.button("pic-card", "Aligned");
      const out = {
        controls: t.all(view.root).filter((node) => node.tagName === "button" || node.tagName === "textarea").map((node) => t.text(node) || node.tagName),
        answerRows: t.all(view.root).filter((node) => t.hasClass(node, "answer-row")).length,
        inert: view.page.getAttribute("inert"),
        pressed: t.press(answer),
        noteTyped: t.press(t.note("pic-card")),
      };
      await t.tick();
      out.writesWhileOpen = t.setLog().length;
      t.click(view.close);
      out.pressedAfter = t.press(answer);
      await t.tick();
      out.writesAfter = t.setLog();
      out.inertAfter = view.page.getAttribute("inert");
      return out;
    """)
    assert result["controls"] == ["Close"]
    assert result["answerRows"] == 0
    assert result["inert"] == ""
    assert result["pressed"] is False and result["noteTyped"] is False and result["writesWhileOpen"] == 0
    assert result["pressedAfter"] is True, "the answer button was never usable, so the inert check proves nothing"
    assert result["writesAfter"] == [_write("pic-card", "aligned", None, "")]
    assert result["inertAfter"] is None


# Bites on: a pinch that does not scale the picture by the fingers' spread (the width and height attributes), that lets the picture point under the fingers' midpoint slide (the scroll position), that goes past the zoom limits, or that works out the frame point from the screen point instead of the frame's own corner.
def test_a_pinch_zooms_about_the_midpoint():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      view.frame.rect = { left: 10, top: 20 };
      const out = { fit: t.shown() };
      // From fit, fingers 200 px apart come to 50 px apart: the picture stays at fit.
      p("pointerdown", 1, 260, 170);
      p("pointerdown", 2, 460, 170);
      p("pointermove", 2, 310, 170);
      out.floorAtFit = t.shown();
      p("pointerup", 1, 260, 170);
      p("pointerup", 2, 310, 170);
      p("pointerdown", 1, 260, 170);
      p("pointerdown", 2, 360, 170);
      p("pointermove", 1, 160, 170);
      out.pinched = t.shown();
      // The picture point under the midpoint (frame 250, 150), as a share of the picture, before and after.
      const share = (shown) => [(shown.left + 250 - Math.max(0, (400 - shown.width) / 2)) / shown.width, (shown.top + 150 - Math.max(0, (300 - shown.height) / 2)) / shown.height];
      out.shareBefore = share(out.fit);
      out.shareAfter = share(out.pinched);
      p("pointermove", 2, 1260, 170);
      out.limit = t.shown();
      out.captured = view.frame.captured.slice(2);
      // Back down to a zoom of 2 (from 4, the fingers 100 px apart come to 50), then from 2 the fingers 200 px apart come to 50: the ask is for a zoom of 0.5.
      p("pointerup", 1, 160, 170);
      p("pointerup", 2, 1260, 170);
      p("pointerdown", 1, 260, 170);
      p("pointerdown", 2, 360, 170);
      p("pointermove", 1, 310, 170);
      out.backToTwo = t.shown();
      p("pointerup", 1, 310, 170);
      p("pointerup", 2, 360, 170);
      p("pointerdown", 1, 160, 170);
      p("pointerdown", 2, 360, 170);
      p("pointermove", 2, 210, 170);
      out.floorFromTwo = t.shown();
      return out;
    """)
    fit = {"width": 400, "height": 200, "left": 0, "top": 0}
    assert result["fit"] == fit
    assert result["floorAtFit"] == fit, "a pinch inward from fit went below fit"
    assert result["pinched"] == {"width": 800, "height": 400, "left": 250, "top": 50}
    assert result["shareBefore"] == result["shareAfter"] == [0.625, 0.5]
    assert (result["limit"]["width"], result["limit"]["height"]) == (1600, 800)
    assert result["captured"] == [1, 2]
    assert (result["backToTwo"]["width"], result["backToTwo"]["height"]) == (800, 400), "the test did not start the last pinch from a zoom of 2"
    assert result["floorFromTwo"] == fit, "a pinch inward from a zoom of 2 went below fit"


# Bites on: a double-tap window that is not about 300 ms or 24 px, a double-tap that does not zoom to 2.5 about the tap point or back to fit, a second tap after a drag that still counts as a double-tap, or two taps too far apart in time or space that zoom anyway.
def test_double_tap_zooms_in_about_the_tap_and_back_out():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      const tap = (x, y, time) => { p("pointerdown", 1, x, y, time); p("pointerup", 1, x, y, time + 50); };
      const out = { fit: t.shown() };
      tap(300, 100, 1000);
      out.afterOne = t.shown();
      tap(300, 100, 1100);
      out.zoomed = t.shown();
      tap(310, 110, 2000);
      tap(310, 110, 2100);
      out.back = t.shown();
      tap(300, 100, 3000);
      tap(300, 100, 3400);
      out.slow = t.shown();
      tap(300, 100, 4000);
      tap(340, 100, 4100);
      out.far = t.shown();
      tap(300, 100, 5000);
      // A 16 px drag (past the 10 px slop) that ends within 24 px of the first tap, then a tap inside 300 ms of it.
      p("pointerdown", 1, 300, 100, 5100);
      p("pointermove", 1, 316, 100, 5120);
      p("pointerup", 1, 316, 100, 5140);
      tap(300, 100, 5200);
      out.afterDrag = t.shown();
      return out;
    """)
    fit = {"width": 400, "height": 200, "left": 0, "top": 0}
    assert result["fit"] == result["afterOne"] == fit
    assert result["zoomed"] == {"width": 1000, "height": 500, "left": 450, "top": 25}
    assert result["back"] == fit
    assert result["slow"] == fit, "two taps 400 ms apart zoomed"
    assert result["far"] == fit, "two taps 40 px apart zoomed"
    assert result["afterDrag"] == fit, "a tap after a drag counted as a double-tap"


# Bites on: a fit worked out from the frame's width alone, so that a tall picture (400 x 800 in a frame of 400 x 300) is drawn at its full width and overflows the frame, a double-tap zoom that does not scale from that fit, or a resize that does not fit by height again.
def test_a_tall_picture_fits_by_its_height():
    result = _answer_page([_picture_card()], POINTER + """
      const view = t.view;
      t.click(t.pictures("pic-card")[0]);
      t.loadView([400, 800], [400, 300]);
      const out = { fit: t.shown() };
      p("pointerdown", 1, 200, 150, 1000);
      p("pointerup", 1, 200, 150, 1050);
      p("pointerdown", 1, 200, 150, 1100);
      p("pointerup", 1, 200, 150, 1150);
      out.zoomed = t.shown();
      p("pointerdown", 1, 200, 150, 2000);
      p("pointerup", 1, 200, 150, 2050);
      p("pointerdown", 1, 200, 150, 2100);
      p("pointerup", 1, 200, 150, 2150);
      out.back = t.shown();
      view.frame.clientHeight = 400;
      t.resizeWindow();
      out.resized = t.shown();
      return out;
    """)
    size = lambda shown: (shown["width"], shown["height"])
    assert size(result["fit"]) == (150, 300), "a tall picture did not fit by its height"
    assert abs(result["zoomed"]["width"] - 375) <= 1 and abs(result["zoomed"]["height"] - 750) <= 1
    assert size(result["back"]) == (150, 300)
    assert size(result["resized"]) == (200, 400), "a resize did not fit a tall picture by its height again"


# Bites on: a drag that does not pan by the movement (or goes past the edges of the picture), a drag at fit that moves anything, or any gesture (a long sideways swipe included) that shows another picture in the view.
def test_drag_pans_when_zoomed_and_nothing_moves_to_another_picture():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      const src = () => view.picture.getAttribute("src");
      const out = { sources: [src()] };
      p("pointerdown", 1, 300, 150, 0, "mouse");
      p("pointermove", 1, 200, 150, 20, "mouse");
      p("pointermove", 1, 100, 150, 40, "mouse");
      p("pointerup", 1, 100, 150, 60, "mouse");
      out.sideways = t.shown();
      out.sources.push(src());
      p("pointerdown", 1, 200, 150, 1000);
      p("pointerup", 1, 200, 150, 1050);
      p("pointerdown", 1, 200, 150, 1100);
      p("pointerup", 1, 200, 150, 1150);
      out.zoomed = t.shown();
      p("pointerdown", 1, 300, 200, 2000);
      p("pointermove", 1, 260, 180, 2020);
      out.dragged = t.shown();
      p("pointermove", 1, -740, -820, 2040);
      out.farUpLeft = t.shown();
      p("pointermove", 1, 1260, 1180, 2060);
      out.farDownRight = t.shown();
      p("pointerup", 1, 1260, 1180, 2080);
      out.sources.push(src());
      out.controls = t.all(view.root).filter((node) => node.tagName === "button").map((node) => node.textContent);
      out.images = t.all(view.root).filter((node) => node.tagName === "img").length;
      return out;
    """)
    fit = {"width": 400, "height": 200, "left": 0, "top": 0}
    assert result["sideways"] == fit
    assert result["zoomed"] == {"width": 1000, "height": 500, "left": 300, "top": 100}
    assert result["dragged"] == {"width": 1000, "height": 500, "left": 340, "top": 120}
    assert result["farUpLeft"] == {"width": 1000, "height": 500, "left": 600, "top": 200}
    assert result["farDownRight"] == {"width": 1000, "height": 500, "left": 0, "top": 0}
    assert result["sources"] == ["plan.png"] * 3
    assert result["controls"] == ["Close"] and result["images"] == 1


# Bites on: a cancelled pointer left behind (so the next one-finger drag is read as a pinch against it), or a pinch that loses a finger and does not carry on as a plain drag from where the other finger is.
def test_a_cancelled_pointer_never_corrupts_the_next_gesture():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      p("pointerdown", 1, 250, 150);
      p("pointerdown", 2, 350, 150);
      p("pointermove", 1, 150, 150);
      const out = { pinched: t.shown() };
      p("pointercancel", 1, 150, 150);
      p("pointermove", 2, 320, 140);
      out.rebased = t.shown();
      p("pointerup", 2, 320, 140);
      p("pointerdown", 3, 100, 100);
      p("pointermove", 3, 90, 70);
      out.fresh = t.shown();
      p("pointerup", 3, 90, 70);
      return out;
    """)
    assert result["pinched"] == {"width": 800, "height": 400, "left": 250, "top": 50}
    assert result["rebased"] == {"width": 800, "height": 400, "left": 280, "top": 60}, "the remaining finger did not pan by its own movement"
    assert result["fresh"] == {"width": 800, "height": 400, "left": 290, "top": 90}, "the next drag did not pan by exactly its own movement"


# Bites on: the view not working out its fit again when the window or the frame changes size (attributes that stay at the old size, or a zoom that is lost), a scroll position left outside the new size, or a size watcher that is never started or never stopped.
def test_a_resize_with_the_view_open_fits_again_at_the_same_zoom():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      p("pointerdown", 1, 300, 100, 1000);
      p("pointerup", 1, 300, 100, 1050);
      p("pointerdown", 1, 300, 100, 1100);
      p("pointerup", 1, 300, 100, 1150);
      const out = { zoomed: t.shown() };
      view.frame.clientWidth = 600;
      view.frame.clientHeight = 300;
      t.resizeWindow();
      out.bigger = t.shown();
      view.frame.clientWidth = 200;
      view.frame.clientHeight = 100;
      t.resizeWindow();
      out.smaller = t.shown();
      t.click(view.close);
      view.frame.clientWidth = 400;
      t.resizeWindow();
      out.afterClose = t.shown();
      return out;
    """)
    assert result["zoomed"] == {"width": 1000, "height": 500, "left": 450, "top": 25}
    assert result["bigger"] == {"width": 1500, "height": 750, "left": 450, "top": 25}
    assert result["smaller"] == {"width": 500, "height": 250, "left": 300, "top": 25}
    assert (result["afterClose"]["width"], result["afterClose"]["height"]) == (500, 250), "a closed view was resized"

    watched = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      const out = { count: t.observers.length, observed: t.observers[0].observed.map((node) => node === view.frame) };
      view.frame.clientWidth = 200;
      view.frame.clientHeight = 150;
      t.observers[0].callback([]);
      out.resized = t.shown();
      t.click(view.close);
      out.disconnected = t.observers[0].disconnected;
      return out;
    """, host={"resizeObserver": True})
    assert watched["count"] == 1 and watched["observed"] == [True]
    assert (watched["resized"]["width"], watched["resized"]["height"]) == (200, 100)
    assert watched["disconnected"] is True


# Bites on: a picture that cannot load blanking its card (or any other part of it), or leaving the picture in place with no word, or losing its caption, or still opening the view; and another picture on the same card that loaded no longer opening it.
def test_a_missing_picture_leaves_the_card_in_place_and_says_so():
    result = _answer_page([_picture_card("full-card"), _bare_card()], """
      const view = t.view;
      const card = t.card("full-card");
      const [first, second] = t.pictures("full-card");
      const outside = () => {
        const inside = t.all(t.figures("full-card")[0]);
        return t.all(card).filter((node) => !inside.includes(node)).map((node) => [node.tagName, node.className, node.textContent, node.hidden]);
      };
      const out = {
        before: t.parts("full-card"),
        listeners: first.listenersAtSrc,
        outsideBefore: outside(),
      };
      t.fire(first, "error");
      out.after = t.parts("full-card");
      out.outsideAfter = outside();
      out.figure = t.figures("full-card")[0].children.map((child) => [child.tagName, child.className, child.textContent]);
      out.pictures = t.pictures("full-card").length;
      out.cardHidden = card.hidden;
      t.click(first);
      t.fire(first, "keydown", { key: "Enter" });
      out.openedFromMissing = !view.root.hidden;
      t.click(t.button("full-card", "Aligned"));
      await t.tick();
      out.writes = t.setLog();
      out.opens = t.all(t.figures("full-card")[0]).filter((node) => node.getAttribute("role") === "button").length;
      t.click(second);
      out.second = [view.root.hidden, view.picture.getAttribute("src")];
      return out;
    """)
    parts = [
        "span.sh-badge", "h2",
        "label:What's true now", "p", "label:Why it needs you", "p", "label:The exact text", "blockquote",
        "div.sheet-images",
        "label:Options", "ul",
        "label:Recommendation", "div.sheet-recommendation",
        "div.answer-row",
        "label:Note", "textarea.sh-field",
        "div.save-line",
    ]
    assert result["before"] == result["after"] == parts
    assert "error" in result["listeners"], "the picture was given its src before its error listener"
    assert result["outsideAfter"] == result["outsideBefore"]
    assert result["figure"] == [
        ["p", "sh-caption", "This picture is missing: The plan drawn out"],
        ["figcaption", "sh-caption", "The draft plan"],
    ]
    assert result["pictures"] == 1 and result["cardHidden"] is False
    assert result["openedFromMissing"] is False and result["opens"] == 0
    assert result["writes"] == [_write("full-card", "aligned", None, "")]
    assert result["second"] == [False, "https://example.test/fridge.png"]


# Bites on: a view whose picture cannot load showing nothing (or keeping the broken picture), or a Close that stops working then; and the next open not showing its picture again.
def test_a_picture_missing_in_the_view_says_so_and_close_still_works():
    result = _answer_page([_picture_card()], POINTER + """
      const view = t.view;
      const first = t.pictures("pic-card")[0];
      t.click(first);
      t.fire(view.picture, "error");
      const out = {
        frame: view.frame.children.map((child) => [child.tagName, child.className, child.textContent]),
        images: t.all(view.root).filter((node) => node.tagName === "img").length,
        shown: !view.root.hidden,
      };
      p("pointerdown", 1, 100, 100);
      p("pointermove", 1, 80, 80);
      p("pointerup", 1, 80, 80);
      t.click(view.close);
      out.closed = [view.root.hidden, view.page.getAttribute("inert"), view.picture.getAttribute("src"), t.focused() === first];
      t.click(first);
      out.reopened = [view.frame.children.map((child) => child.tagName), view.picture.getAttribute("src")];
      return out;
    """)
    assert result["frame"] == [["p", "sh-caption", "This picture is missing: The plan drawn out"]]
    assert result["images"] == 0 and result["shown"] is True
    assert result["closed"] == [True, None, None, True]
    assert result["reopened"] == [["img"], "plan.png"]


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


# Bites on: tapping the picked answer (a plain answer, an option or Discuss) leaving it pressed or writing it again instead of clearing it, the cleared document losing the note or not fitting the answer schema, a pressed button left after the clear, a save line that does not end on Saved, or the leave-guard staying on once the cleared write resolves.
def test_tapping_the_picked_answer_again_clears_it_and_keeps_the_note():
    result = _answer_page([_card("plan-day")], """
      const out = { cleared: [] };
      const settle = async () => {
        t.sets[t.sets.length - 1].resolve();
        await t.tick();
      };
      t.type(t.note("plan-day"), "keep me", "input");
      await t.advance(1000);
      await settle();
      for (const label of ["Aligned", "Yes", "Discuss"]) {
        t.click(t.button("plan-day", label));
        await settle();
        const picked = t.state("plan-day").pressed;
        t.click(t.button("plan-day", label));
        await settle();
        const log = t.setLog();
        out.cleared.push({ label: label, picked: picked, state: t.state("plan-day"), save: t.saveText("plan-day"), guarded: t.unload(), last: log[log.length - 1] });
      }
      out.writes = t.setLog().length;
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["writes"] == 7, "each pick and each clear is one write after the note's"
    assert [entry["label"] for entry in result["cleared"]] == ["Aligned", "Yes", "Discuss"]
    for entry in result["cleared"]:
        label = entry["label"]
        assert entry["picked"].count("true") == 1, label
        assert entry["last"] == {"path": "answers/plan-day", "body": {"answer": None, "optionId": None, "note": "keep me"}}, label
        ANSWER_VALIDATOR.validate(entry["last"]["body"])
        assert entry["state"]["pressed"] == ["false"] * 4, label
        assert entry["state"]["note"] == "keep me", label
        assert entry["save"] == "Saved", label
        assert entry["guarded"] is False, label


# Bites on: a cleared answer still counting as answered, still showing an Aligned or Discuss pill on its row, still folded, or still counted in the fold's label.
def test_a_cleared_answer_drops_out_of_the_count_the_pill_and_the_fold():
    result = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check", "third-card"), unsettled=["third-card"]), """
      const settle = async (index) => {
        t.sets[index].resolve();
        await t.tick();
      };
      const shape = () => ({ count: t.count(), pills: t.rows().map((row) => row.pill[1]), folded: t.rows().map((row) => row.folded), label: t.fold().parts[0][1] });
      const out = {};
      t.open("plan-day");
      t.click(t.button("plan-day", "Aligned"));
      t.open("fridge-check");
      t.click(t.button("fridge-check", "Discuss"));
      await settle(0);
      await settle(1);
      t.open("third-card");
      out.before = shape();
      t.open("plan-day");
      t.click(t.button("plan-day", "Aligned"));
      await settle(2);
      t.open("third-card");
      out.after = shape();
      return out;
    """, host={"set": "pending"})
    assert result["before"] == {"count": "2 of 3 answered · 1 to discuss", "pills": ["Aligned", "Discuss", "Open"], "folded": [True, True, False], "label": "Answered · 2"}
    assert result["after"]["count"] == "1 of 3 answered · 1 to discuss"
    assert result["after"]["pills"] == ["Open", "Discuss", "Open"]
    assert result["after"]["folded"] == [False, True, False]
    assert result["after"]["label"] == "Answered · 1"


# Bites on: a clear tapped while the pick's write is still in flight being dropped (the store keeping the pick), a second write starting before the first resolved, or the save line not ending on Saved.
def test_a_clear_tapped_while_the_pick_is_saving_ends_cleared():
    result = _answer_page([_card("plan-day")], """
      t.click(t.button("plan-day", "Aligned"));
      t.click(t.button("plan-day", "Aligned"));
      const early = { sets: t.sets.length, save: t.saveText("plan-day"), pressed: t.state("plan-day").pressed };
      t.sets[0].resolve();
      await t.tick();
      const queued = { sets: t.sets.length, save: t.saveText("plan-day") };
      t.sets[1].resolve();
      await t.tick();
      return { early: early, queued: queued, sets: t.setLog(), save: t.saveText("plan-day"), guarded: t.unload() };
    """, host={"set": "pending"})
    assert result["early"] == {"sets": 1, "save": "Saving…", "pressed": ["false"] * 4}
    assert result["queued"] == {"sets": 2, "save": "Saving…"}
    assert result["sets"] == [_write("plan-day", "aligned", None, ""), _write("plan-day", None, None, "")]
    assert result["save"] == "Saved"
    assert result["guarded"] is False


# Bites on: tapping the chosen verdict again leaving it pressed or writing it again, the cleared verdict losing the note, not fitting the verdict schema or not carrying the digest, a pressed button left on the last card, or a save line that does not end on Saved.
def test_tapping_the_chosen_verdict_again_clears_it_and_keeps_the_note():
    result = _sheet_page(_sample_final(), """
      const settle = async () => {
        t.sets[t.sets.length - 1].resolve();
        await t.tick();
      };
      t.click(t.lastButton("Approve"));
      await settle();
      t.type(t.lastNote(), "Looks right", "input");
      await t.advance(1000);
      await settle();
      t.click(t.lastButton("Approve"));
      await settle();
      return { sets: t.setLog(), last: t.lastState(), save: t.lastSaveText(), guarded: t.unload(), count: t.count() };
    """, host={"fakeTimers": True, "set": "pending"})
    digest = _sheet_digest(_sample_final())
    assert result["sets"] == [_verdict_write("approve"), _verdict_write("approve", "Looks right"), _verdict_write(None, "Looks right")]
    cleared = result["sets"][-1]
    assert cleared["path"] == "verdict/" + digest
    assert cleared["body"] == {"verdict": None, "note": "Looks right", "sheet": digest}
    VERDICT_VALIDATOR.validate(cleared["body"])
    assert result["last"]["pressed"] == ["false", "false"] and result["last"]["note"] == "Looks right"
    assert result["save"] == "Saved"
    assert result["guarded"] is False
    assert result["count"] == "0 of 2 answered"


# Bites on: a cleared answer or verdict that comes back pressed after a reopen (as when the second tap writes the pick again), a reopen that loses the note or writes anything, or a restored cleared answer counting as answered.
def test_a_reopen_restores_a_cleared_answer_and_verdict():
    first = _answer_page([_card("plan-day")], """
      const settle = async () => {
        t.sets[t.sets.length - 1].resolve();
        await t.tick();
      };
      t.type(t.note("plan-day"), "keep me", "input");
      await t.advance(1000);
      await settle();
      t.click(t.button("plan-day", "Aligned"));
      await settle();
      t.click(t.button("plan-day", "Aligned"));
      await settle();
      return t.setLog();
    """, host={"set": "pending", "fakeTimers": True})
    answer = [call for call in first if call["path"] == "answers/plan-day"][-1]["body"]
    assert answer == {"answer": None, "optionId": None, "note": "keep me"}

    reopened = _answer_page([_card("plan-day")], """
      await t.advance(200);
      return { state: t.state("plan-day"), sets: t.setLog(), count: t.count(), save: t.saveText("plan-day") };
    """, host={"fakeTimers": True, "docs": [{"id": "plan-day", "data": answer}]})
    assert reopened["state"]["pressed"] == ["false"] * 4
    assert reopened["state"]["note"] == "keep me"
    assert reopened["sets"] == [], "reopening wrote something"
    assert reopened["count"] == "0 of 1 answered"
    assert reopened["save"] == "Saved"

    second = _sheet_page(_sample_final(), """
      const settle = async () => {
        t.sets[t.sets.length - 1].resolve();
        await t.tick();
      };
      t.click(t.lastButton("Approve"));
      await settle();
      t.type(t.lastNote(), "Looks right", "input");
      await t.advance(1000);
      await settle();
      t.click(t.lastButton("Approve"));
      await settle();
      return t.setLog();
    """, host={"fakeTimers": True, "set": "pending"})
    verdict = [call for call in second if call["path"] == "verdict/" + _sheet_digest(_sample_final())][-1]["body"]
    assert verdict == _verdict(None, "Looks right")

    again = _sheet_page(_sample_final(), """
      await t.advance(200);
      return { last: t.lastState(), sets: t.setLog(), count: t.count(), save: t.lastSaveText() };
    """, host={"fakeTimers": True, "collections": {"verdict": [_final_doc(verdict)]}})
    assert again["last"]["pressed"] == ["false", "false"]
    assert again["last"]["note"] == "Looks right"
    assert again["sets"] == [], "reopening wrote something"
    assert again["count"] == "0 of 2 answered"
    assert again["save"] == "Saved"


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


# Bites on: a control the page adds (an item row, the fold, Previous, Next) that is not a theme button, a second desktop breakpoint, a restated outline, or the hidden rule going missing.
def test_new_controls_are_theme_buttons():
    result = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check"), unsettled=["fridge-check"]), """
      const hosts = ["sheet-stepper", "sheet-items", "sheet-footer"];
      const own = hosts.flatMap((id) => t.all(elements[id]).filter((node) => node.tagName === "button"));
      return {
        own: own.map((node) => ({ text: t.text(node), className: node.className, type: node.getAttribute("type") })),
        everything: t.allButtons().map((button) => button.className),
      };
    """, host={"docs": [{"id": "plan-day", "data": _doc("aligned")}]})
    assert len(result["own"]) == 5, result["own"]
    labels = [button["text"] for button in result["own"]]
    for label in ("‹ Previous", "Next ›"):
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

    # A final sheet's controls (the declines toggle and the verdict buttons, with a verdict save's Try again) are theme buttons too.
    final = _sheet_page(_sample_final(), """
      t.click(t.lastButton("Approve"));
      t.sets[0].reject({ code: "unavailable", message: "no" });
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
    assert [control["text"] for control in final["own"]] == ["Declined findings · 2", "Approve", "Not yet", "note", "Try again"], final
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


# The final sheet: its history, its last card, the next-step line and the verdict.
FINAL_SAMPLE = json.loads((THEME / "sample-final-sheet.json").read_text(encoding="utf-8"))
FIRST_CARD, SECOND_CARD = "leftovers-handling", "saved-plan-history"
WORDS = json.loads((THEME / "sheet-words.json").read_text(encoding="utf-8"))
DONE_STEP = WORDS["doneStep"]

HISTORY_TEXT = "The review ran 4 rounds and fixed 9 things itself. The vet: The vet found nothing left to fix and raised two calls for you."
TRACES_BOARD = "Every statement in the spec traces to your board, your framing, your rulings, your answers, or craft recorded for your veto."
TRACES_NO_BOARD = "Every statement in the spec traces to your framing, your rulings, your answers, or craft recorded for your veto."
BOARD_SAVED = "The approved board is saved with the spec."
BOARD_NOT_SAVED = "The approved board is not saved with the spec."
NEXT_TEXT = (
    "Once you've chosen Approve and said in the chat that you're done, the advisor adds the breakdown to the same PR "
    "(or, where the project keeps specs outside the repo or gitignored, beside the spec where it is kept) and vets it, "
    "and an independent read of the breakdown still runs where it applies. Then one merge word from you covers both, "
    "and the issues are filed as it merges. If another answer here changes the spec, the spec goes back through its "
    "checks, a new vet and a new approval first."
)
DECLINED_ITEMS = [
    ["li", "Add a calorie count to every recipe on the plan. (why declined: Nothing in your framing asks for nutrition numbers, so adding them would be new scope.)"],
    ["li", "Let two people edit the same plan at once. (why declined: You said the planner is for one household cook, so sharing a plan is out of scope.)"],
]
NO_DIGEST_LINE = "This browser can't tell which version of the sheet this is, so the verdict can't be saved here."
LEAVING_LINE = "Once every answer shows it is saved, go back to the chat and say you're done."
SAVES_LINE = "Answers save as you tap"


def _sample_final(cards=None, declined=None, approved=True, saved=True):
    sheet = copy.deepcopy(FINAL_SAMPLE)
    if cards is not None:
        sheet["cards"] = cards
    if declined is not None:
        sheet["final"]["declinedFindings"] = declined
    sheet["final"]["approval"] = {"approvedBoard": approved, "boardSavedWithSpec": saved}
    return sheet


def _republished_final():
    """The sample final sheet published again with different bytes (a new title), so its digest is new."""
    sheet = _sample_final()
    sheet["title"] = sheet["title"] + " (second edition)"
    return sheet


def _final_doc(data, doc_id=None):
    """A stored verdict document; keyed by the digest of the sheet on screen unless a test names another id."""
    return {"id": _sheet_digest(_sample_final()) if doc_id is None else doc_id, "data": data}


def _sheet_digest(sheet=None):
    """The SHA-256 the page computes: of the exact bytes the harness serves as sheet.json."""
    return hashlib.sha256(_sample_files(sheet)["sheet.json"]["body"].encode("utf-8")).hexdigest()


OTHER_DIGEST = "0" * 64


def _verdict(verdict, note="", sheet=None):
    return {"verdict": verdict, "note": note, "sheet": _sheet_digest(_sample_final()) if sheet is None else sheet}


def _verdict_write(verdict, note=""):
    return {"path": "verdict/" + _sheet_digest(_sample_final()), "body": _verdict(verdict, note)}


def _all_off(controls):
    return all(control["disabled"] for control in controls)


def _all_on(controls):
    return not any(control["disabled"] for control in controls)


# Bites on: a final sheet missing its history, declined findings (collapsed until toggled), last card (traces line, board line only with an approved board and following whether it is saved, answer row, note, save line, the hidden no-digest caption, no badge, no send row), the next-step line straight below it, or the next box, or any of their words.
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
        caption: t.digestCaption(),
      };
      out.order = t.finalOrder();
      out.step = t.afterLast();
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
        + ["div.answer-row", "label:Note", "textarea.sh-field", "div.save-line", "p.sh-caption"]
    ), "the last card's parts, or a badge or a send row on it"
    assert last["buttons"]["labels"] == ["Approve", "Not yet"]
    assert last["buttons"]["pressed"] == ["false", "false"]
    assert last["caption"] == {"hidden": True, "text": NO_DIGEST_LINE}, "the no-digest caption showed although the browser can tell the digest"
    assert result["order"] == ["article.sh-card", "p.sh-caption", "div.sh-box"]
    assert result["step"]["text"] == DONE_STEP and result["step"]["hidden"] is False
    assert result["next"] == {"className": "sh-box", "label": "What happens next", "labelClass": "sh-label", "text": NEXT_TEXT}
    assert result["parts"] == {"historyHidden": False, "historyChildren": 4 if declines else 3, "finalHidden": False, "finalChildren": 3}
    # The vet's calls are the same cards, count and rows as on any sheet.
    assert result["count"] == "0 of 2 answered"


# Bites on: a remainder or plain sheet drawing the final sheet's history, last card or next line, or reading the verdict collection.
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


# Bites on: any sheet kind drawing a Done for now control or heading, a Back to the sheet control, or the old done box, before or after the answers load or an answer is tapped.
@pytest.mark.parametrize("read", ["docs", "pending"], ids=["loaded", "loading"])
@pytest.mark.parametrize("sheet,card", [
    pytest.param(_sheet(cards=_named_cards("plan-day", "fridge-check")), "plan-day", id="plain"),
    pytest.param(_remainder_of(_named_cards("plan-day", "fridge-check"), unsettled=["fridge-check"]), "plan-day", id="remainder"),
    pytest.param(_sample_final(), FIRST_CARD, id="final"),
])
def test_no_sheet_draws_done_for_now(sheet, card, read):
    result = _sheet_page(sheet, """
      const gone = ["done for now", "back to the sheet"];
      const snapshot = () => ({
        text: t.everyText().filter((text) => gone.some((words) => text.toLowerCase().includes(words))),
        buttons: t.allButtons().map((button) => button.text).filter((text) => gone.some((words) => text.toLowerCase().includes(words))),
      });
      const out = { first: snapshot() };
      t.click(t.buttons("__CARD__")[0]);
      await t.tick();
      out.second = snapshot();
      return out;
    """.replace("__CARD__", card), host={"read": read})
    empty = {"text": [], "buttons": []}
    assert result["first"] == empty and result["second"] == empty, "the page still draws Done for now or Back to the sheet"
    text = _template_text()
    assert "sheet-done" not in text and not re.search(r"(?i)done for now|back to the sheet", text)


# Bites on: a final sheet, or the theme specimen, drawing a Send verdict control or a send row, in any state (loading, loaded, a pick whose save was rejected, or no digest).
@pytest.mark.parametrize("host,tap", [
    pytest.param({"read": "pending"}, False, id="loading"),
    pytest.param({}, False, id="loaded"),
    pytest.param({"set": "pending"}, True, id="picked-and-rejected"),
    pytest.param({"noCrypto": True}, False, id="no-digest"),
])
def test_a_final_sheet_has_no_send_verdict(host, tap):
    result = _sheet_page(_sample_final(), """
      const snapshot = () => ({
        buttons: t.allButtons().map((button) => button.text).filter((text) => text.toLowerCase().includes("send")),
        text: t.everyText().filter((text) => text.toLowerCase().includes("send verdict") || text.toLowerCase().includes("verdict sent")),
        rows: t.everyClass().filter((name) => name.split(/\\s+/).includes("send-row")),
      });
      const out = { first: snapshot() };
      if (__TAP__) {
        t.click(t.lastButton("Approve"));
        out.pending = snapshot();
        t.sets[0].reject({ code: "unavailable", message: "no" });
        await t.tick();
        out.rejected = snapshot();
      }
      return out;
    """.replace("__TAP__", "true" if tap else "false"), host=host)
    empty = {"buttons": [], "text": [], "rows": []}
    assert all(snapshot == empty for snapshot in result.values()), result
    assert "Send verdict" not in _template_text()
    assert "Send verdict" not in (THEME / "specimen.html").read_text(encoding="utf-8"), "the theme specimen shows a Send verdict button"


# Bites on: a verdict tap or its note being written anywhere but verdict/<digest> (a draft path, a sends path, or as an answer), a tap not saving at once, a note not waiting for its pause, a body that does not fit $defs/verdict or whose sheet is not the digest of the served bytes, a save line that says Saved before the write resolved, or the last card feeding the count or the rows.
def test_a_verdict_tap_and_note_save_at_verdict_digest():
    result = _sheet_page(_sample_final(), """
      const out = { before: { count: t.count(), pills: t.rows().map((row) => row.pill[1]) } };
      t.click(t.lastButton("Approve"));
      await t.tick();
      out.saving = t.lastSaveText();
      t.sets[0].resolve();
      await t.tick();
      t.type(t.lastNote(), "Looks right", "input");
      out.early = t.sets.length;
      await t.advance(1000);
      out.noteSaving = t.lastSaveText();
      t.sets[1].resolve();
      await t.tick();
      out.sets = t.setLog();
      out.after = { count: t.count(), pills: t.rows().map((row) => row.pill[1]) };
      out.last = t.lastState();
      out.save = t.lastSaveText();
      return out;
    """, host={"fakeTimers": True, "set": "pending"})
    digest = hashlib.sha256(_sample_files(_sample_final())["sheet.json"]["body"].encode("utf-8")).hexdigest()
    assert result["early"] == 1, "the note was written before its pause ended"
    assert result["saving"] == "Saving…", "the save line said more than it knew before the write resolved"
    assert result["noteSaving"] == "Saving…"
    assert result["sets"] == [_verdict_write("approve"), _verdict_write("approve", "Looks right")]
    for call in result["sets"]:
        assert call["path"] == "verdict/" + digest, "the verdict was not written at verdict/<digest>"
        assert call["body"]["sheet"] == digest, "the document does not carry the digest of the served bytes"
        VERDICT_VALIDATOR.validate(call["body"])
        assert not call["path"].startswith(("draft-verdict", "answers/")) and "/sends" not in call["path"]
    assert result["after"] == result["before"] == {"count": "0 of 2 answered", "pills": ["Open", "Open"]}
    assert result["last"]["pressed"] == ["true", "false"] and result["last"]["note"] == "Looks right"
    assert result["save"] == "Saved"


# Bites on: a saved verdict not coming back on reopen (its pick or note), a stored verdict counting as an answer, a reopen writing anything, a document that does not fit the schema restoring a pick, a null verdict restoring a pick, a note that is not text restoring, or the verdict not being read from the verdict collection alongside the answers.
def test_a_saved_verdict_is_restored_on_reopen_and_counts_as_nothing():
    def reopen(document):
        return _sheet_page(_sample_final(), """
          await t.advance(200);
          return {
            last: t.lastState(), sets: t.setLog(), count: t.count(), save: t.lastSaveText(),
            reads: t.reads.map((read) => read.name).sort(), controls: t.controls(), rows: t.rows().map((row) => row.pill[1]),
          };
        """, host={"fakeTimers": True, "collections": {"verdict": [_final_doc(document)]}})

    picked = reopen(_verdict("not-yet", "Wait for the board"))
    assert picked["last"]["pressed"] == ["false", "true"]
    assert picked["last"]["note"] == "Wait for the board"
    assert picked["sets"] == [], "reopening wrote something"
    assert picked["count"] == "0 of 2 answered" and picked["rows"] == ["Open", "Open"]
    assert picked["save"] == "Saved"
    assert picked["reads"] == ["answers", "verdict"]
    assert _all_on(picked["controls"])

    noted = reopen(_verdict(None, "Only a note"))
    assert noted["last"]["pressed"] == ["false", "false"] and noted["last"]["note"] == "Only a note"
    assert noted["sets"] == [] and _all_on(noted["controls"])

    digest = _sheet_digest(_sample_final())
    for name, bad, note in (
        ("unknown verdict", {"verdict": "maybe", "note": "kept", "sheet": digest}, "kept"),
        ("extra key", {"verdict": "approve", "note": "kept", "sheet": digest, "extra": 1}, "kept"),
        ("note that is not text", {"verdict": "approve", "note": 3, "sheet": digest}, ""),
    ):
        unfit = reopen(bad)
        assert unfit["last"]["pressed"] == ["false", "false"] and unfit["last"]["note"] == note, name
        assert unfit["sets"] == [], name


# Bites on: a restored answer or verdict (or a document restoring only a note) showing no save line after a reopen, a saver with nothing stored showing one, or a reopen writing anything.
def test_a_reopened_sheet_shows_each_restored_answer_and_the_verdict_as_saved():
    sheet = _sample_final()
    third = copy.deepcopy(sheet["cards"][0])
    third["id"] = "third-one"
    sheet["cards"].append(third)
    digest = _sheet_digest(sheet)
    docs = [
        {"id": "leftovers-handling", "data": _doc("option", "allow-leftovers")},
        {"id": "saved-plan-history", "data": _doc("aligned", None, "agreed")},
    ]

    def reopen(verdict):
        return _sheet_page(sheet, """
          await t.advance(200);
          const saves = {};
          for (const id of ["leftovers-handling", "saved-plan-history", "third-one"]) {
            t.open(id);
            saves[id] = t.saveText(id);
          }
          return { saves: saves, last: t.lastSaveText(), sets: t.setLog() };
        """, host={"fakeTimers": True, "collections": {"answers": docs, "verdict": [{"id": digest, "data": verdict}]}})

    signed = reopen(_verdict("approve", "Looks right", sheet=digest))
    assert signed["saves"] == {"leftovers-handling": "Saved", "saved-plan-history": "Saved", "third-one": ""}
    assert signed["last"] == "Saved"
    assert signed["sets"] == [], "reopening wrote something"

    noted = reopen(_verdict(None, "Only a note", sheet=digest))
    assert noted["last"] == "Saved", "a verdict document that restores only a note showed no save line"
    assert noted["sets"] == []


# Bites on: a note typed over and then put back to what the store holds (inside its pause) leaving the save line quiet instead of Saved, a card with nothing stored showing Saved after the same round trip, or that round trip writing anything.
def test_an_edit_undone_inside_the_pause_still_shows_saved():
    sheet = _sample_final()
    third = copy.deepcopy(sheet["cards"][0])
    third["id"] = "third-one"
    sheet["cards"].append(third)
    digest = _sheet_digest(sheet)
    docs = [{"id": "saved-plan-history", "data": _doc("aligned", None, "agreed")}]
    collections = {"answers": docs, "verdict": [{"id": digest, "data": _verdict("approve", "Looks right", sheet=digest)}]}

    result = _sheet_page(sheet, """
      await t.advance(200);
      const out = {};
      t.open("saved-plan-history");
      const note = t.note("saved-plan-history");
      t.type(note, "agreed!", "input");
      out.typedOver = t.saveText("saved-plan-history");
      t.type(note, "agreed", "input");
      await t.advance(1500);
      out.card = t.saveText("saved-plan-history");
      out.cardSets = t.setLog();

      const verdictNote = t.lastNote();
      t.type(verdictNote, "Looks right!", "input");
      t.type(verdictNote, "Looks right", "input");
      await t.advance(1500);
      out.verdict = t.lastSaveText();
      out.verdictSets = t.setLog();

      t.open("third-one");
      const blank = t.note("third-one");
      t.type(blank, "x", "input");
      t.type(blank, "", "input");
      await t.advance(1500);
      out.blank = t.saveText("third-one");
      out.blankSets = t.setLog();
      return out;
    """, host={"fakeTimers": True, "collections": collections})
    assert result["typedOver"] == "Saving…"
    assert result["card"] == "Saved", "an edit undone inside the pause left the restored note's save line quiet"
    assert result["cardSets"] == [], "an edit undone inside the pause was written"
    assert result["verdict"] == "Saved", "an edit undone inside the pause left the restored verdict's save line quiet"
    assert result["verdictSets"] == [], "an edit undone inside the pause was written"
    assert result["blank"] == "", "a card with nothing stored showed Saved after an edit undone"
    assert result["blankSets"] == [], "a card with nothing stored was written after an edit undone"


# Bites on: a verdict written for another revision of the sheet being restored on reopen (by its id or by its sheet field), a republished sheet not starting unsigned, or a page showing one revision writing to another revision's document.
def test_a_republished_sheet_starts_unsigned_and_never_touches_the_old_revisions_verdict():
    new_digest = _sheet_digest(_republished_final())
    old_digest = _sheet_digest(_sample_final())
    assert new_digest != old_digest

    def reopen(collections, scenario="await t.advance(200);"):
        return _sheet_page(_republished_final(), scenario + """
          return { last: t.lastState(), sets: t.setLog(), controls: t.controls(), count: t.count(), reads: t.reads.map((read) => read.name).sort() };
        """, host={"fakeTimers": True, "collections": collections})

    old = reopen({"verdict": [_final_doc(_verdict("approve", "Old sign-off", sheet=old_digest), doc_id=old_digest)]})
    assert old["last"]["pressed"] == ["false", "false"] and old["last"]["note"] == "", "another revision's verdict was restored"
    assert _all_on(old["controls"]) and old["sets"] == []
    assert old["reads"] == ["answers", "verdict"]

    claimed = reopen({"verdict": [_final_doc(_verdict("approve", "Wrong sheet", sheet=old_digest), doc_id=new_digest)]})
    assert claimed["last"]["pressed"] == ["false", "false"] and claimed["last"]["note"] == "", "a document naming another revision was restored"
    assert _all_on(claimed["controls"]) and claimed["sets"] == []

    mine = reopen({"verdict": [
        _final_doc(_verdict("approve", "Old sign-off", sheet=old_digest), doc_id=old_digest),
        _final_doc(_verdict("not-yet", "Mine", sheet=new_digest), doc_id=new_digest),
    ]})
    assert mine["last"]["pressed"] == ["false", "true"] and mine["last"]["note"] == "Mine"

    tapped = reopen({"verdict": [_final_doc(_verdict("approve", "Old sign-off", sheet=old_digest), doc_id=old_digest)]}, scenario="""
      await t.advance(200);
      t.click(t.lastButton("Not yet"));
      await t.advance(200);
    """)
    assert [call["path"] for call in tapped["sets"]] == ["verdict/" + new_digest], "a page showing the new revision wrote somewhere else"
    assert tapped["sets"][0]["body"] == {"verdict": "not-yet", "note": "", "sheet": new_digest}


# Bites on: the next-step line missing, not directly below the last card, retyped in the page instead of read from sheet-words.json, or the next box not following it with its words; on a sheet with cards and on one with none.
@pytest.mark.parametrize("cards", [None, []], ids=["with-cards", "no-cards"])
def test_the_next_step_line_sits_below_the_last_card_and_the_next_box_follows(cards):
    result = _sheet_page(_sample_final(cards=cards), """
      return { order: t.finalOrder(), step: t.afterLast(), next: t.nextBox(), parts: t.finalParts(), caption: t.digestCaption() };
    """)
    assert result["order"] == ["article.sh-card", "p.sh-caption", "div.sh-box"]
    assert result["step"] == {"tagName": "p", "className": "sh-caption", "text": DONE_STEP, "hidden": False}
    assert result["next"]["text"] == NEXT_TEXT == WORDS["next"]
    assert result["next"]["label"] == WORDS["nextHeading"]
    assert result["parts"]["finalHidden"] is False and result["parts"]["finalChildren"] == 3
    assert result["caption"]["hidden"] is True


# Bites on: a browser with no crypto.subtle leaving the last card on, saying nothing about why, writing, or reading the verdict collection; or the no-digest caption showing in any other state (loading, a non-owner, a digest present, a schema with no verdict shape).
def test_without_a_digest_the_last_card_stays_off_and_says_why():
    result = _sheet_page(_sample_final(), """
      await t.advance(1500);
      const fire = (node) => ["click", "input", "change"].forEach((type) => t.fire(node, type));
      t.lastButtons().forEach(fire);
      t.lastNote().value = "sneaky";
      fire(t.lastNote());
      await t.advance(1500);
      return { caption: t.digestCaption(), last: t.lastState(), sets: t.setLog(), reads: t.reads.map((read) => read.name), cards: t.state("leftovers-handling").disabled };
    """, host={"fakeTimers": True, "noCrypto": True})
    assert result["caption"] == {"hidden": False, "text": NO_DIGEST_LINE}
    assert all(result["last"]["disabled"]) and result["last"]["pressed"] == ["false", "false"]
    assert result["sets"] == [], "the last card wrote without a digest"
    assert result["reads"] == ["answers"], "the page read the verdict collection without a digest"
    assert result["cards"] == [False] * 5, "the cards stopped working too"

    for name, host in (
        ("loading", {"read": "pending", "noCrypto": True}),
        ("non-owner", {"user": "viewer", "noCrypto": True}),
        ("digest present", {}),
    ):
        page = _sheet_page(_sample_final(), "await t.advance(200); return t.digestCaption();", host=dict(host, fakeTimers=True))
        assert page == {"hidden": True, "text": NO_DIGEST_LINE}, name


# Bites on: a rejected verdict write showing Saved or no Try again, a Try again that does not send the latest state, a stalled write saying Saved or offering Try again while it may still land, or a late resolve not showing Saved.
def test_a_failed_or_stalled_verdict_write_shows_as_a_cards_does():
    rejected = _sheet_page(_sample_final(), """
      const out = {};
      t.click(t.lastButton("Approve"));
      t.sets[0].reject({ code: "unavailable", message: "no" });
      await t.tick();
      out.failed = { save: t.lastSaveText(), retry: t.lastTryAgain() !== undefined, controls: t.controls() };
      t.click(t.lastButton("Not yet"));
      await t.tick();
      out.sets = t.setLog();
      t.sets[1].resolve();
      await t.tick();
      out.fixed = { save: t.lastSaveText(), retry: t.lastTryAgain() !== undefined };
      t.type(t.lastNote(), "Again", "change");
      t.sets[2].reject({ code: "unavailable", message: "no" });
      await t.tick();
      t.click(t.lastTryAgain());
      await t.tick();
      out.again = t.setLog();
      t.sets[3].resolve();
      await t.tick();
      out.final = t.lastSaveText();
      return out;
    """, host={"set": "pending"})
    assert "Not saved" in rejected["failed"]["save"] and rejected["failed"]["retry"] is True
    assert _all_on(rejected["failed"]["controls"])
    assert rejected["sets"] == [_verdict_write("approve"), _verdict_write("not-yet")]
    assert rejected["fixed"] == {"save": "Saved", "retry": False}
    assert rejected["again"] == [_verdict_write("approve"), _verdict_write("not-yet"), _verdict_write("not-yet", "Again"), _verdict_write("not-yet", "Again")]
    assert rejected["final"] == "Saved"

    for late in ("resolve", "reject"):
        stalled = _sheet_page(_sample_final(), """
          t.click(t.lastButton("Approve"));
          await t.advance(9999);
          const out = { early: t.lastSaveText() };
          await t.advance(1);
          out.stalled = { save: t.lastSaveText(), retry: t.lastTryAgain() !== undefined, guarded: t.unload() };
          t.sets[0].__LATE__(__ARGS__);
          await t.tick();
          out.late = { save: t.lastSaveText(), retry: t.lastTryAgain() !== undefined };
          return out;
        """.replace("__LATE__", late).replace("__ARGS__", "" if late == "resolve" else '{ code: "unavailable", message: "late" }'),
            host={"set": "pending", "fakeTimers": True})
        assert stalled["early"] == "Saving…"
        assert "Not saved" in stalled["stalled"]["save"] and stalled["stalled"]["retry"] is False, "a stalled write offered Try again while it could still land"
        assert stalled["stalled"]["guarded"] is True
        if late == "resolve":
            assert stalled["late"] == {"save": "Saved", "retry": False}
        else:
            assert "Not saved" in stalled["late"]["save"] and stalled["late"]["retry"] is True


# Bites on: the digest hashing text decoded from the response instead of the bytes the file was published with (a byte-order mark is dropped by decoding, so the stored digest would differ from `shasum -a 256 sheet.json`), or the page failing to read a BOM-prefixed sheet.
def test_the_digest_covers_the_served_bytes_including_a_byte_order_mark():
    files = _sample_files(_sample_final())
    files["sheet.json"]["body"] = "﻿" + files["sheet.json"]["body"]
    served = files["sheet.json"]["body"].encode("utf-8")
    assert served.startswith(b"\xef\xbb\xbf")
    page = _run_page(files, host={"fakeTimers": True}, scenario="""
      t.click(t.lastButton("Approve"));
      await t.advance(200);
      return { verdicts: t.setLog().filter((call) => call.path.startsWith("verdict/")), save: t.lastSaveText() };
    """)
    assert page["settled"] and page["errorHidden"] is True, page["errors"]
    digest = hashlib.sha256(served).hexdigest()
    assert digest != hashlib.sha256(served[3:]).hexdigest()
    assert page["result"]["save"] == "Saved"
    assert [(call["path"], call["body"]["sheet"]) for call in page["result"]["verdicts"]] == [("verdict/" + digest, digest)]


# Bites on: a final sheet with no cards drawing a stepper, rows or cards, a count that is not "Nothing left to answer", losing its history, last card, next-step line or next box, or its verdict not saving.
def test_a_final_sheet_with_no_cards():
    result = _sheet_page(_sample_final(cards=[]), """
      const out = {
        count: [t.count(), elements["sheet-count"].hidden],
        stepperHidden: elements["sheet-stepper"].hidden,
        itemsHidden: elements["sheet-items"].hidden,
        rows: t.rowNodes().length,
        cards: elements["sheet-cards"].children.length,
        history: t.history(),
        parts: t.finalParts(),
        step: t.afterLast().text,
        next: t.nextBox().text,
      };
      t.click(t.lastButton("Approve"));
      await t.tick();
      out.save = t.lastSaveText();
      out.sets = t.setLog();
      out.countAfter = t.count();
      return out;
    """, host={"set": "ok"})
    assert result["count"] == ["Nothing left to answer", False]
    assert result["stepperHidden"] is True and result["itemsHidden"] is True
    assert result["rows"] == 0 and result["cards"] == 0
    assert result["history"]["hidden"] is False and result["history"]["paragraphs"][0] == HISTORY_TEXT
    assert result["parts"]["finalHidden"] is False and result["parts"]["finalChildren"] == 3
    assert result["step"] == DONE_STEP
    assert result["next"] == NEXT_TEXT
    digest = _sheet_digest(_sample_final(cards=[]))
    assert result["sets"] == [{"path": "verdict/" + digest, "body": {"verdict": "approve", "note": "", "sheet": digest}}]
    assert result["save"] == "Saved"
    assert result["countAfter"] == "Nothing left to answer"


# Bites on: a failed or stalled read of the verdict (not only of the answers) being taken as an empty collection, so the controls turn on, or its Try again not reading both collections again.
@pytest.mark.parametrize("host,stall", [
    pytest.param({"readByCollection": {"verdict": ["reject", "docs"]}}, False, id="verdict-rejects"),
    pytest.param({"readByCollection": {"verdict": ["pending", "docs"]}, "fakeTimers": True}, True, id="verdict-stalls"),
    pytest.param({"readByCollection": {"answers": ["reject", "docs"]}}, False, id="answers-reject"),
])
def test_a_failed_verdict_read_keeps_the_sheet_off(host, stall):
    result = _sheet_page(_sample_final(), """
      if (__STALL__) await t.advance(10000);
      const snapshot = () => ({ gate: t.gate().message, hidden: t.gate().hidden, retry: t.gate().retry !== undefined, controls: t.controls(), caption: t.digestCaption().hidden, reads: t.reads.map((read) => read.name) });
      const out = { failed: snapshot() };
      t.fire(t.lastButton("Approve"), "click");
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
    assert _all_off(failed["controls"]) and failed["caption"] is True
    assert failed["reads"] == ["answers", "verdict"]
    assert result["writes"] == 0
    assert result["recovered"]["hidden"] is True
    assert result["recovered"]["reads"] == ["answers", "verdict"] * 2, "the retry did not read both again"
    assert _all_on(result["recovered"]["controls"])


NON_OWNER_CASES = [
    pytest.param({"claude": "missing"}, id="no-window-claude"),
    pytest.param({"claude": "no-use"}, id="use-is-not-a-function"),
    pytest.param({"db": "null"}, id="store-is-null"),
    pytest.param({"db": "reject"}, id="use-db-rejects"),
    pytest.param({"user": "null"}, id="user-is-null"),
    pytest.param({"user": "viewer"}, id="is-owner-false"),
    pytest.param({"user": "is-owner-rejects"}, id="is-owner-rejects"),
]


# Bites on: a viewer who is not the owner, or a view with no store, getting a working last card, or any write or read.
@pytest.mark.parametrize("host", NON_OWNER_CASES)
def test_the_last_card_is_off_for_a_non_owner_and_with_no_store(host):
    result = _sheet_page(_sample_final(), """
      const fire = (node) => ["click", "input", "change"].forEach((type) => t.fire(node, type));
      t.lastButtons().forEach(fire);
      t.lastNote().value = "sneaky";
      fire(t.lastNote());
      await t.advance(1500);
      return { controls: t.controls(), sets: t.sets.length, reads: t.reads.length, last: t.lastState(), parts: t.finalParts(), caption: t.digestCaption().hidden };
    """, host=dict(host, fakeTimers=True))
    assert result["parts"]["finalChildren"] == 3, "the last card did not draw"
    assert _all_off(result["controls"])
    assert result["sets"] == 0, "a control wrote although the viewer cannot answer"
    assert result["reads"] == 0
    assert result["last"]["pressed"] == ["false", "false"]
    assert result["caption"] is True


# Bites on: a schema that does not say what a verdict is still giving the last card working buttons, or the no-digest caption showing for a reason that is not the digest.
@pytest.mark.parametrize("mutate", [
    pytest.param(lambda schema: schema["$defs"].pop("verdict"), id="no-verdict-definition"),
    pytest.param(lambda schema: schema["$defs"]["verdict"]["properties"]["verdict"].update(enum=["approve", "not-yet", "maybe", None]), id="a-verdict-with-no-words"),
])
def test_a_schema_without_a_verdict_shape_keeps_the_last_card_off(mutate):
    files = _sample_files(_sample_final())
    files["sheet.schema.json"]["body"] = json.dumps(_schema_without_answers(mutate))
    page = _run_page(files, scenario="""
      await t.advance(200);
      const fire = (node) => ["click", "input", "change"].forEach((type) => t.fire(node, type));
      t.lastButtons().forEach(fire);
      fire(t.lastNote());
      await t.advance(1500);
      return { last: t.lastState(), sets: t.setLog(), cardControls: t.state("leftovers-handling").disabled, gate: t.gate().hidden, caption: t.digestCaption().hidden };
    """, host={"fakeTimers": True})
    assert page["settled"] and page["errors"] == [], page
    result = page["result"]
    assert result["last"]["disabled"][-1] is True and all(result["last"]["disabled"])
    assert result["sets"] == []
    assert result["cardControls"] == [False] * 5, "the cards stopped working too"
    assert result["gate"] is True and result["caption"] is True


# Bites on: leaving a final sheet going unguarded while its verdict (pick or note) is unconfirmed, rejected or stalled, or the guard staying on once the verdict is saved; and a plain, remainder or final footer saying the wrong things (the leaving line belongs to the first two only).
def test_leaving_a_final_sheet_is_guarded_while_the_verdict_is_unconfirmed_and_the_footer_says_what_to_do():
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
      t.click(t.lastButton("Not yet"));
      t.sets[2].reject({ code: "unavailable", message: "no" });
      await t.tick();
      out.failed = { save: t.lastSaveText(), guarded: t.unload() };
      t.click(t.lastTryAgain());
      t.sets[3].resolve();
      await t.tick();
      out.retried = { save: t.lastSaveText(), guarded: t.unload() };
      t.click(t.lastButton("Approve"));
      await t.advance(10000);
      out.stalled = { save: t.lastSaveText(), guarded: t.unload() };
      out.footer = t.footer();
      return out;
    """, host={"set": "pending", "fakeTimers": True})
    assert result["idle"] is False
    assert result["pick"] is True, "an unconfirmed verdict pick was not guarded"
    assert result["pickSaved"] is False
    assert result["note"] is True, "a verdict note waiting to save was not guarded"
    assert result["noteSaved"] is False
    assert "Not saved" in result["failed"]["save"] and result["failed"]["guarded"] is True, "a rejected verdict save was not guarded"
    assert result["retried"] == {"save": "Saved", "guarded": False}
    assert "Not saved" in result["stalled"]["save"] and result["stalled"]["guarded"] is True, "a stalled verdict save was not guarded"
    assert result["footer"] == {"hidden": False, "caption": SAVES_LINE, "captions": [SAVES_LINE]}

    for name, sheet in (
        ("plain", _sheet(cards=_named_cards("plan-day", "fridge-check"))),
        ("remainder", _remainder_of(_named_cards("plan-day", "fridge-check"), unsettled=["fridge-check"])),
    ):
        footer = _sheet_page(sheet, "return t.footer();")
        assert footer == {"hidden": False, "caption": SAVES_LINE, "captions": [SAVES_LINE, LEAVING_LINE]}, name


# Bites on: the final sheet's shared wording being retyped in the page or the prose renderer instead of read from sheet-words.json, or the usage doc leaving that file out of the published files.
def test_final_sheet_wording_has_one_home():
    prose_source = (THEME.parent / "lib" / "sheet_prose.py").read_text(encoding="utf-8")
    for key in ("history", "tracesBoard", "tracesNoBoard", "boardSaved", "boardNotSaved", "next", "noDeclines", "declinedHeading", "declinedItem", "approveHeading", "nextHeading", "historyHeading", "doneStep", "doneStepInChat"):
        for name, text in (("the page", _template_text()), ("sheet_prose.py", prose_source)):
            assert WORDS[key] not in text, "%s retypes the shared wording %r" % (name, key)
    assert re.search(r"""fetchJson\(\s*['"]sheet-words\.json['"]""", _template_text())
    publishing = USAGE_DOC.read_text(encoding="utf-8").split("## Publishing a sheet", 1)[1]
    assert '"sheet-words.json": "<staged sheet-words.json>"' in publishing
    assert "`sheet-words.json`" in publishing


# The open/closed cue on the folded row and the declines toggle, and the Previous and Next pair below the open card.
CUE_SCENARIO = """
  const cueOf = (control) => {
    const first = control.children[0];
    return {
      tag: first.tagName,
      className: first.className,
      text: first.textContent,
      hidden: first.getAttribute("aria-hidden"),
      expanded: control.getAttribute("aria-expanded"),
      classes: control.className.split(/\\s+/),
    };
  };
"""


# Bites on: the folded row's cue not following the toggle (stuck on ▶, or not redrawn on the second click), a closed cue missing its text-presentation selector (U+FE0E), a cue that is not the button's first child, one a screen reader would read (no aria-hidden), one that disagrees with aria-expanded, or the row losing its theme button class.
def test_the_fold_cue_follows_the_toggle():
    docs = [{"id": "plan-day", "data": _doc("aligned")}, {"id": "fridge-check", "data": _doc("discuss")}]
    result = _sheet_page(_remainder_of(_named_cards("plan-day", "fridge-check", "third-card"), unsettled=["third-card"]), CUE_SCENARIO + """
      const fold = t.control("fold");
      const out = { closed: cueOf(fold), hiddenRow: t.fold().hidden };
      t.click(fold);
      out.opened = cueOf(t.control("fold"));
      t.click(t.control("fold"));
      out.closedAgain = cueOf(t.control("fold"));
      return out;
    """, host={"docs": docs})
    assert result["hiddenRow"] is False, "the fold row was hidden, so the test proves nothing"
    classes = ["sh-button", "sheet-fold"]
    assert result["closed"] == {"tag": "span", "className": "sheet-cue", "text": "▶︎", "hidden": "true", "expanded": "false", "classes": classes}
    assert result["opened"] == {"tag": "span", "className": "sheet-cue", "text": "▼", "hidden": "true", "expanded": "true", "classes": classes}
    assert result["closedAgain"] == result["closed"]


# Bites on: the folded row having no block padding or no even gap between its lines, the chips line not sitting in the label's column, the row rule losing to the shared flex rule or beating the rules that hide it, or the chips not being one block after the cue and the label.
def test_the_fold_row_is_padded_and_its_chips_line_up_with_the_label():
    ids = ("plan-day", "fridge-check", "third-card", "fourth-card")
    docs = [
        {"id": "plan-day", "data": _doc("aligned")},
        {"id": "fridge-check", "data": _doc("discuss")},
        {"id": "third-card", "data": _doc("option", "yes")},
    ]
    fold = _sheet_page(_remainder_of(_named_cards(*ids), unsettled=["fourth-card"]), "return t.fold();", host={"docs": docs})
    assert fold["chips"] == {"className": "sheet-fold-chips", "index": 2}, "the chips are not one block after the cue and the label"
    assert fold["parts"] == [
        ["", "Answered · 3"],
        ["sh-pill sh-pill--aligned", "1 Aligned"],
        ["sh-pill sh-pill--discuss", "1 Discuss"],
        ["sh-pill sh-pill--aligned", "1 Picked"],
    ]

    rules = _style_rules(_template_text())
    grid_rules = [i for i, (selector, pairs) in enumerate(rules) if selector == ".sheet-page .sheet-fold" and ("display", "grid") in pairs]
    assert len(grid_rules) == 1, "the folded row is not one grid rule"
    index = grid_rules[0]
    row = dict(rules[index][1])
    assert row.get("gap") == "8px", "the folded row has no even gap between its lines"
    assert row.get("grid-template-columns") == "auto minmax(0, 1fr)", "the folded row is not a cue column and a label column"
    assert row.get("padding-block") == "8px", "the folded row has no block padding"
    assert "flex-wrap" not in row and "justify-content" not in row, "the folded row still carries flex alignment"

    shared = [i for i, (selector, _) in enumerate(rules) if selector == ".sheet-page .sheet-row, .sheet-page .sheet-fold"]
    assert len(shared) == 1 and index > shared[0], "the folded row's rule does not come after the shared flex rule"
    hidden = [i for i, (selector, pairs) in enumerate(rules) if selector == ".sheet-page .sheet-fold" and ("display", "none") in pairs]
    assert len(hidden) == 1 and index < hidden[0], "the folded row's rule comes after the rule that hides it on wide screens"
    hidden_attribute = [i for i, (selector, _) in enumerate(rules) if selector == ".sh-theme [hidden]"]
    assert len(hidden_attribute) == 1 and index < hidden_attribute[0], "the folded row's rule comes after the hidden-attribute rule"

    chips = [dict(pairs) for selector, pairs in rules if selector == ".sheet-page .sheet-fold-chips"]
    assert len(chips) == 1, "the chips line is not one rule"
    assert (chips[0].get("display"), chips[0].get("flex-wrap"), chips[0].get("gap")) == ("flex", "wrap", "8px"), "the chips line is not a wrapping row with even gaps"
    assert chips[0].get("grid-column") == "2", "the chips line does not sit in the label's column"
    assert "flex" not in chips[0], "the chips line still claims a full flex line"


# Bites on: the item row's badge shrinking or wrapping onto broken lines beside the question and its pill.
def test_a_rows_not_saved_badge_never_shrinks_or_wraps():
    rules = _style_rules(_template_text())
    badge = [pairs for selector, pairs in rules if selector == ".sheet-page .sheet-row > .sh-badge"]
    assert len(badge) == 1, "the item row's badge is not one rule"
    declared = dict(badge[0])
    assert declared.get("flex") == "none", "the item row's badge can shrink"
    assert declared.get("white-space") == "nowrap", "the item row's badge can wrap onto broken lines"


# Bites on: the declines toggle's cue not following the list (never redrawn on a click, stuck on ▶), disagreeing with aria-expanded or the list's hidden, not being the button's first child, or having no aria-hidden.
def test_the_declines_cue_follows_the_toggle():
    result = _sheet_page(_sample_final(), CUE_SCENARIO + """
      const state = () => Object.assign(cueOf(t.control("declines")), { listHidden: t.history().listHidden });
      const out = { closed: state() };
      t.click(t.control("declines"));
      out.opened = state();
      t.click(t.control("declines"));
      out.closedAgain = state();
      return out;
    """)
    classes = ["sh-button"]
    assert result["closed"] == {"tag": "span", "className": "sheet-cue", "text": "▶︎", "hidden": "true", "expanded": "false", "classes": classes, "listHidden": True}
    assert result["opened"] == {"tag": "span", "className": "sheet-cue", "text": "▼", "hidden": "true", "expanded": "true", "classes": classes, "listHidden": False}
    assert result["closedAgain"] == result["closed"]


# Bites on: the second Previous and Next missing, not theme buttons, placed anywhere but between the cards and the footer, wired to the wrong step, left enabled at an end when the top pair is off (or the reverse), carrying an item label, or shown on a sheet with no cards.
def test_the_bottom_stepper_steps_like_the_top_one():
    text = _template_text()
    bottom = re.search(r'<div id="sheet-stepper-bottom" class="sheet-stepper" hidden></div>', text)
    assert bottom, "the template has no hidden #sheet-stepper-bottom with the stepper class"
    assert text.index('<main id="sheet-cards"></main>') < bottom.start() < text.index('<div id="sheet-footer"')

    result = _answer_page(_named_cards("plan-day", "fridge-check", "third-card"), """
      const bottom = () => t.bottomStepper();
      const shape = () => ({
        open: t.openCard(),
        label: t.stepper().label,
        top: [t.stepper().prevDisabled, t.stepper().nextDisabled],
        bottom: [bottom().prevDisabled, bottom().nextDisabled],
        hidden: [t.stepper().hidden, bottom().hidden],
      });
      const buttonsOf = (host) => t.all(elements[host]).filter((node) => node.tagName === "button").map((node) => [node.textContent, node.className, node.getAttribute("type")]);
      const out = { first: shape(), labels: bottom().labels, buttons: [buttonsOf("sheet-stepper"), buttonsOf("sheet-stepper-bottom")] };
      out.stepOne = t.click(t.control("bottomNext")) && shape();
      out.stepTwo = t.click(t.control("next")) && shape();
      out.stepThree = t.click(t.control("bottomPrevious")) && shape();
      t.click(t.control("bottomNext"));
      out.last = shape();
      out.pastEnd = [t.click(t.control("bottomNext")), t.click(t.control("next"))];
      t.click(t.control("previous"));
      t.click(t.control("bottomPrevious"));
      out.back = shape();
      out.pastStart = [t.click(t.control("bottomPrevious")), t.click(t.control("previous"))];
      return out;
    """)
    assert result["first"] == {"open": "plan-day", "label": "Item 1 of 3", "top": [True, False], "bottom": [True, False], "hidden": [False, False]}
    assert result["labels"] == ["‹ Previous", "Next ›"], "the bottom stepper carries more than the two buttons"
    pair = [["‹ Previous", "sh-button", "button"], ["Next ›", "sh-button", "button"]]
    assert result["buttons"] == [pair, pair]
    assert result["stepOne"] == {"open": "fridge-check", "label": "Item 2 of 3", "top": [False, False], "bottom": [False, False], "hidden": [False, False]}
    assert result["stepTwo"] == {"open": "third-card", "label": "Item 3 of 3", "top": [False, True], "bottom": [False, True], "hidden": [False, False]}
    assert result["stepThree"] == result["stepOne"]
    assert result["last"]["open"] == "third-card" and result["last"]["bottom"] == result["last"]["top"] == [False, True]
    assert result["pastEnd"] == [False, False]
    assert result["back"] == result["first"]
    assert result["pastStart"] == [False, False]

    # A sheet with one card has nowhere to step, on either pair.
    single = _answer_page(_named_cards("plan-day"), "return { top: t.stepper(), bottom: t.bottomStepper() };")
    assert single["top"] == {"hidden": False, "label": "Item 1 of 1", "prevDisabled": True, "nextDisabled": True}
    assert single["bottom"] == {"hidden": False, "labels": ["‹ Previous", "Next ›"], "prevDisabled": True, "nextDisabled": True}

    # A final sheet with no cards shows neither.
    empty = _sheet_page(_sample_final(cards=[]), "return { top: t.stepper().hidden, bottom: t.bottomStepper().hidden };")
    assert empty == {"top": True, "bottom": True}


# A picture's share at the frame point (250, 150), for the zoom tests: how far across and down the picture that point sits.
SHARE = """
  const share = (shown) => [
    (shown.left + 250 - Math.max(0, (400 - shown.width) / 2)) / shown.width,
    (shown.top + 150 - Math.max(0, (300 - shown.height) / 2)) / shown.height,
  ];
"""
# A ctrl wheel (a trackpad pinch) at the frame point (250, 150), the frame's corner being at (10, 20).
WHEEL = """
  view.frame.rect = { left: 10, top: 20 };
  const wheel = (fields) => t.fire(view.frame, "wheel", Object.assign({ ctrlKey: true, deltaMode: 0, deltaY: 0, clientX: 260, clientY: 170 }, fields));
"""
FIT = {"width": 400, "height": 200, "left": 0, "top": 0}


# Bites on: a wheel listener that is passive (so the browser's own page zoom cannot be cancelled), a ctrl wheel that is not cancelled, a zoom that is not exp(-deltaY / 100) of the current size (capped at one step an event), one that slides the picture point under the pointer (including zooming about the frame's corner), that passes the 1 to 4 limits, that reads a line or page delta as pixels, or that acts while the view is shut or the picture has no size.
def test_a_ctrl_wheel_zooms_about_the_pointer():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + SHARE + WHEEL + """
      const out = { options: view.frame.listenerOptions.wheel.map((options) => (options ? options.passive : null)), fit: t.shown() };
      // One event moves the zoom one capped step, so reaching a limit takes a run of large events.
      const run = (deltaY) => { for (let i = 0; i < 20; i++) wheel({ deltaY: deltaY }); };
      const zoom = wheel({ deltaY: -100 });
      out.prevented = zoom.defaultPrevented;
      out.zoomed = t.shown();
      out.shareBefore = share(out.fit);
      out.shareAfter = share(out.zoomed);
      run(-100000);
      out.top = t.shown();
      run(100000);
      out.bottom = t.shown();
      // A line delta counts 16 px a line, and a page delta the frame's height (300 px); both stay under the step cap.
      const lines = wheel({ deltaMode: 1, deltaY: -1 });
      out.lines = [lines.defaultPrevented, t.shown()];
      run(100000);
      wheel({ deltaY: -16 });
      out.pixels = t.shown();
      run(100000);
      wheel({ deltaMode: 2, deltaY: -0.05 });
      out.pages = t.shown();
      run(100000);
      wheel({ deltaY: -15 });
      out.pagePixels = t.shown();
      run(100000);
      const none = wheel({ deltaY: 0 });
      out.none = [none.defaultPrevented, t.shown()];
      // With the view shut, or open with no picture sized, a wheel is left alone.
      t.click(view.close);
      const shut = wheel({ deltaY: -100 });
      t.click(t.pictures("pic-card")[0]);
      const unsized = wheel({ deltaY: -100 });
      out.left = [shut.defaultPrevented, unsized.defaultPrevented, t.shown().width];
      return out;
    """)
    assert result["options"] == [False], "the wheel listener is not registered with passive: false"
    assert result["fit"] == FIT
    assert result["prevented"] is True
    assert abs(result["zoomed"]["width"] - 500) <= 1 and abs(result["zoomed"]["height"] - 250) <= 1
    assert result["shareBefore"] == [0.625, 0.5]
    assert all(abs(after - before) < 0.005 for after, before in zip(result["shareAfter"], result["shareBefore"])), result["shareAfter"]
    assert (result["top"]["width"], result["top"]["height"]) == (1600, 800), "a run of large pinches out went past the zoom limit"
    assert result["bottom"] == FIT, "a run of large pinches in went below fit"
    assert result["lines"][0] is True and result["lines"][1]["width"] > 400 and result["lines"][1] == result["pixels"], "a line delta did not count as 16 px"
    assert result["pages"]["width"] > 400 and result["pages"] == result["pagePixels"], "a page delta did not count as the frame's height"
    assert result["none"] == [True, FIT]
    assert result["left"] == [False, False, 0]


# Bites on: one large wheel event (a mouse notch) zooming by more than one 1.25 step in either direction (a missing upper or lower per-event cap), or the cap changing how a small trackpad-pinch event zooms (a changed small-delta curve, exp(-deltaY / 100)). The zoom-out checks start at the 4x ceiling so none lands on fit or the ceiling.
def test_one_wheel_notch_zooms_one_step_and_a_trackpad_pinch_is_unchanged():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + SHARE + WHEEL + """
      const out = { fit: t.shown() };
      const run = (deltaY) => { for (let i = 0; i < 20; i++) wheel({ deltaY: deltaY }); };
      wheel({ deltaY: -100000 });
      out.notchIn = t.shown().width;
      run(100000);
      out.backToFit = t.shown();
      wheel({ deltaY: -10 });
      out.pinchIn = t.shown().width;
      run(-100000);
      out.ceiling = t.shown().width;
      wheel({ deltaY: 100000 });
      out.notchOut = t.shown().width;
      wheel({ deltaY: 10 });
      out.pinchOut = t.shown().width;
      return out;
    """)
    assert result["fit"] == FIT
    assert abs(result["notchIn"] - 500) <= 1, "one large wheel event zoomed by more than one step"
    assert result["backToFit"] == FIT, "the run back to fit did not reach fit, so the pinch check does not start there"
    assert abs(result["pinchIn"] - 400 * 2.718281828 ** 0.1) <= 1, "a small pinch event no longer follows exp(-deltaY / 100)"
    assert result["ceiling"] == 1600, "the run of large events in did not reach the ceiling, so the zoom-out checks do not start there"
    assert abs(result["notchOut"] - 1600 / 1.25) <= 1, "one large wheel event out was not one step back from the ceiling"
    assert abs(result["pinchOut"] - 1280 * 2.718281828 ** -0.1) <= 1, "a small pinch out event no longer follows exp(-deltaY / 100)"


# Bites on: a wheel without ctrlKey being cancelled or zooming the picture, so a plain scroll or two-finger drag no longer pans the frame.
def test_a_plain_wheel_does_not_zoom():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + WHEEL + """
      wheel({ deltaY: -100 });
      const zoomed = t.shown();
      const plain = wheel({ ctrlKey: false, deltaY: -100 });
      const bare = t.fire(view.frame, "wheel", { deltaY: -100, deltaMode: 0, clientX: 260, clientY: 170 });
      return { zoomed: zoomed, afterPlain: t.shown(), plain: plain.defaultPrevented, bare: bare.defaultPrevented };
    """)
    assert result["zoomed"]["width"] > 400, "the ctrl wheel did not zoom, so the test proves nothing"
    assert result["afterPlain"] == result["zoomed"], "a plain wheel zoomed the picture"
    assert result["plain"] is False and result["bare"] is False, "a plain wheel was cancelled"


# Bites on: a Safari pinch that multiplies each change into the current zoom instead of the zoom the gesture began at, that does not zoom about the pointer, that is not cancelled, that carries one gesture's start into the next, that zooms with no gesture begun (also after Close and reopen), or that works while the view is shut.
def test_a_safari_gesture_zooms_from_where_it_began():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + SHARE + """
      view.frame.rect = { left: 10, top: 20 };
      const out = { fit: t.shown(), prevented: [] };
      const gesture = (type, fields) => t.fire(view.frame, type, Object.assign({ clientX: 260, clientY: 170 }, fields));
      const sent = (type, fields) => {
        const event = gesture(type, fields);
        out.prevented.push(event.defaultPrevented);
      };
      sent("gesturestart", { scale: 1 });
      sent("gesturechange", { scale: 1.1 });
      out.first = t.shown();
      sent("gesturechange", { scale: 1.2 });
      out.second = t.shown();
      out.shareAfter = share(out.second);
      sent("gestureend", { scale: 1.2 });
      sent("gesturestart", { scale: 1 });
      sent("gesturechange", { scale: 1.5 });
      out.third = t.shown();
      sent("gestureend", { scale: 1.5 });
      gesture("gesturechange", { scale: 2 });
      out.lone = t.shown();
      // A gesture left unfinished when the view closes does not carry over to the next picture.
      sent("gesturestart", { scale: 1 });
      t.click(view.close);
      t.click(t.pictures("pic-card")[0]);
      t.loadView([800, 400], [400, 300]);
      gesture("gesturechange", { scale: 2 });
      out.reopened = t.shown();
      t.click(view.close);
      out.shut = gesture("gesturestart", { scale: 1 }).defaultPrevented;
      return out;
    """)
    assert result["fit"] == FIT
    assert result["first"]["width"] == 440
    assert result["second"]["width"] == 480, "the second change was counted on top of the first (528)"
    assert result["shareAfter"] == pytest.approx([0.625, 0.5], abs=0.005)
    assert result["third"]["width"] == 720, "a new gesture did not start from the zoom the last one ended at (1.2 x 1.5 = 1.8)"
    assert result["prevented"] == [True] * 8, result["prevented"]
    assert result["lone"] == result["third"], "a gesture change with no gesture begun zoomed"
    assert result["reopened"] == FIT, "a gesture begun before Close zoomed the next picture"
    assert result["shut"] is False


# Bites on: a Safari gesture that zooms (or records a start) while a two-finger pointer pinch is down, so one pinch is applied by two formulas; or a ctrl wheel that zooms while a gesture is in flight, so one trackpad pinch is applied by the wheel and the gesture both.
def test_one_pinch_is_zoomed_by_one_source_only():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      view.frame.rect = { left: 10, top: 20 };
      const out = { fit: t.shown(), prevented: [] };
      const gesture = (type, fields) => {
        const event = t.fire(view.frame, type, Object.assign({ clientX: 260, clientY: 170 }, fields));
        out.prevented.push(event.defaultPrevented);
      };
      // A pointer pinch (fingers 100 px apart come to 200) with gesture events in flight: the pointer formula alone, a zoom of 2.
      p("pointerdown", 1, 260, 170);
      p("pointerdown", 2, 360, 170);
      gesture("gesturestart", { scale: 1 });
      p("pointermove", 2, 460, 170);
      gesture("gesturechange", { scale: 3 });
      out.pointerPinch = t.shown();
      p("pointerup", 1, 260, 170);
      p("pointerup", 2, 460, 170);
      // The gesture that began under the pinch recorded no start, so a change after the fingers lift zooms nothing.
      gesture("gesturechange", { scale: 3 });
      out.afterLift = t.shown();
      gesture("gestureend", { scale: 3 });
      // A ctrl wheel during a gesture: the gesture's formula alone, from where it began (2 x 1.5 = 3).
      gesture("gesturestart", { scale: 1 });
      t.fire(view.frame, "wheel", { ctrlKey: true, deltaMode: 0, deltaY: -100, clientX: 260, clientY: 170 });
      gesture("gesturechange", { scale: 1.5 });
      out.gesture = t.shown();
      const wheel = t.fire(view.frame, "wheel", { ctrlKey: true, deltaMode: 0, deltaY: -100, clientX: 260, clientY: 170 });
      out.wheelPrevented = wheel.defaultPrevented;
      out.afterWheel = t.shown();
      return out;
    """)
    assert result["pointerPinch"]["width"] == 800, "the pointer pinch was zoomed by the gesture as well"
    assert result["afterLift"] == result["pointerPinch"], "a gesture under a pointer pinch recorded a start"
    assert result["gesture"]["width"] == 1200, "the ctrl wheel zoomed during a gesture"
    assert result["wheelPrevented"] is True
    assert result["afterWheel"] == result["gesture"], "a ctrl wheel zoomed while a gesture was in flight"
    assert all(result["prevented"]), result["prevented"]


# Bites on: a Safari gesture that began before any finger was down zooming a two-finger pointer pinch as well, so one pinch is applied by two formulas.
def test_a_gesture_begun_before_the_fingers_never_zooms_with_the_pinch():
    result = _answer_page([_picture_card()], POINTER + OPEN_WIDE + """
      view.frame.rect = { left: 10, top: 20 };
      const out = { prevented: [] };
      const gesture = (type, fields) => {
        const event = t.fire(view.frame, type, Object.assign({ clientX: 260, clientY: 170 }, fields));
        out.prevented.push(event.defaultPrevented);
      };
      // The gesture starts with no finger down, so it records a start; the fingers then come down and spread (100 px apart to 200).
      gesture("gesturestart", { scale: 1 });
      p("pointerdown", 1, 260, 170);
      p("pointerdown", 2, 360, 170);
      p("pointermove", 2, 460, 170);
      // The pointer formula alone is a zoom of 2; a gesture change under the pinch zooms nothing more.
      gesture("gesturechange", { scale: 3 });
      out.pinch = t.shown();
      return out;
    """)
    assert result["pinch"]["width"] == 800, "a gesture begun before the fingers zoomed the pinch as well"
    assert len(result["prevented"]) == 2 and all(result["prevented"]), result["prevented"]
