"""Guards for the walk on the PR sheet page: what it draws, how a stop is answered, what it locks, and how it reloads."""
import hashlib
import json
from pathlib import Path

import pytest

import pr_sheet
from test_review_template import (
    _picture_card,
    _run_page,
    _sample_files,
    _sample_final,
    _sheet,
    _sheet_digest,
    _with,
)
from test_review_template_pr import PW, WORDS, _accepted_answers, _entry_lines, _fill, _page

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pr_sheet"
READ_FAILED = "Your saved answers couldn't be loaded."


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _src_of(path):
    return "pictures/" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:pr_sheet.PICTURE_DIGEST] + ".png"


def _place(path):
    """A picture file that exists under the fixtures folder is copied to a fixed pictures/ src of its own; any other path is not."""
    return _src_of(path) if (FIXTURES / path).is_file() else None


def _built(records, advisor):
    return pr_sheet.build([_load(name) for name in records], _load(advisor), WORDS["pr"], place=_place)


WALK_SHEET = _built(["record-big.json"], "input-walk.json")
STACK_SHEET = _built(["record-stack-1.json", "record-stack-2.json", "record-stack-3.json"], "input-stack.json")
DIGEST = _sheet_digest(WALK_SHEET)
ACCEPTED = {"collections": {"answers": _accepted_answers(WALK_SHEET)}}
OPEN_URL = "https://shop.example.test"
ALL_STOPS = ["p1", "p2", "p3", "p4", "f1"]

# What a scenario reads of the walk part and its stops, by stop id, and of the merge verdict's lock.
WALK = r"""
const text = (node) => t.text(node).replace(/\s+/g, " ").trim();
const stop = (id) => t.all(part("pr-walk")).find((node) => node.id === "stop-" + id);
const answerRow = (id) => stop(id).children.find((child) => hasClass(child, "answer-row")).children;
const fixBlock = (id) => stop(id).children.find((child) => child.id === "fix-" + id);
const fixRow = (id) => fixBlock(id).children.find((child) => hasClass(child, "answer-row")).children;
const btn = (id, label) => [...answerRow(id), ...fixRow(id)].find((button) => button.textContent === label);
const noteOf = (id) => stop(id).children.find((child) => child.tagName === "textarea");
const noteLabelOf = (id) => stop(id).children.find((child) => child.tagName === "label");
const saveNode = (id) => stop(id).children.find((child) => hasClass(child, "save-line"));
const saveOf = (id) => (saveNode(id).hidden ? "" : text(saveNode(id)));
const tryAgain = (id) => saveNode(id).children.find((child) => child.tagName === "button");
const shotsOf = (id) => t.all(stop(id)).find((node) => node.id === "shots-" + id);
const pickOf = (id) => shotsOf(id).children[0];
const shotLineOf = (id) => text(shotsOf(id).children[1]);
const inputOf = (id) => shotsOf(id).children[2];
const imagesOf = (id) => t.all(stop(id)).filter((node) => node.tagName === "img");
const stopState = (id) => ({
  pressed: answerRow(id).map((button) => button.getAttribute("aria-pressed")),
  fixPressed: fixRow(id).map((button) => button.getAttribute("aria-pressed")),
  fixHidden: fixBlock(id).hidden,
  noteLabel: noteLabelOf(id).textContent,
  note: noteOf(id).value,
  save: saveOf(id),
  shots: shotLineOf(id),
});
const walkControls = () => t.all(part("pr-walk")).filter((node) => node.tagName === "button" || node.tagName === "textarea");
const countNode = () => t.all(part("pr-walk")).find((node) => node.id === "walk-count");
const walkCount = () => (countNode().hidden ? "" : text(countNode()));
const walkLine = (name) => {
  const node = verdict().children.find((child) => child.id === "verdict-" + name);
  return { hidden: node.hidden, text: node.textContent };
};
const merge = () => {
  const button = verdictRow()[0];
  return { label: button.textContent, disabled: button.disabled, pressed: button.getAttribute("aria-pressed") };
};
const choose = async (id, label) => {
  t.click(btn(id, label));
  await t.tick();
};
// A browser keeps the chosen file in the input until its value is cleared, and fires no change for an unchanged selection.
const shoot = async (id) => {
  const input = inputOf(id);
  if (!input.modeled) {
    Object.defineProperty(input, "value", { get: () => "", set(v) { if (v === "") this.files = []; } });
    input.modeled = true;
  }
  if (input.files && input.files.length > 0) return;
  input.files = [{ name: "shot.png" }];
  t.fire(input, "change");
  await t.tick();
};
"""


_PATHS = {}


def _path(stop_id, sheet=WALK_SHEET):
    """The store path the page gives a stop, read from the write the page makes when the stop's first answer is tapped."""
    key = json.dumps(sheet, sort_keys=True)
    if key not in _PATHS:
        ids = [s["id"] for s in sheet["prSheet"]["walk"]["stops"]]
        written = _page(sheet, WALK + "const out = {}; for (const id of %s) { t.click(answerRow(id)[0]); await t.tick(); } return t.setLog().map((item) => item.path);" % json.dumps(ids))["result"]
        _PATHS[key] = dict(zip(ids, written))
    return _PATHS[key][stop_id]


UNLOCKED = {"label": "Merge #214", "disabled": False, "pressed": "false"}
LOCKED = {"label": "Merge #214 · locked", "disabled": True, "pressed": "false"}
NO_LINE = {"hidden": True, "text": ""}


def _line(key, count):
    return {"hidden": False, "text": PW[key + ("One" if count == 1 else "Many")].replace("{count}", str(count))}


def _body(answer, fix=None, note="", shots=()):
    return {"answer": answer, "fix": fix, "note": note, "shots": list(shots)}


def _expected_stop(stop, stack):
    """The parts of one stop in the order they sit, each as tag, id and class then its words."""
    tag = (_fill(PW["walkStopPr"], pr=stop["pr"]) + " " if stack else "") + stop["id"].upper()
    stop_id = stop["id"]
    is_try = stop["kind"] == "try"
    parts = ["div:" + tag + (" " + PW["optionalBadge"] if stop.get("optional") else ""), "h3.sh-heading:" + stop["title"]]
    if is_try:
        parts.append("ol#steps-%s.sheet-walk-list:%s" % (stop_id, " ".join(stop["steps"])))
    parts.append("p.expect:" + PW["expectLabel" if is_try else "lookForLabel"] + " " + stop["expect"])
    if "notWalked" in stop:
        parts.append("p.sh-caption:" + _fill(PW["notWalkedByAdvisor"], reason=stop["notWalked"]))
    words = []
    for picture in stop["pictures"]:
        if picture.get("missing"):
            words.append(_fill(PW["pictureMissing"], alt=picture["alt"]))
        if "caption" in picture:
            words.append(picture["caption"])
    if stop["pictures"]:
        parts.append("div.sheet-images:" + " ".join(words))
    if any(not picture.get("missing") for picture in stop["pictures"]):
        parts.append("p.sh-caption:" + PW["tapPicture"])
    labels = PW["walkAnswers"]["labels"]
    parts += [
        "div.answer-row:" + " ".join(labels[value] for value in PW["walkAnswers"]["try" if is_try else "look"]),
        "div#fix-%s.sheet-fix:" % stop_id,
        "label.sh-label:Note",
        "textarea#walk-note-%s.sh-field:" % stop_id,
        "div.save-line:",
    ]
    return {"stop": "stop-" + stop_id, "parts": parts}


def _expected_walk(sheet):
    walk = sheet["prSheet"]["walk"]
    stack = sheet["kind"] == "stack"
    opened = walk["open"]
    box = opened["label"] + (" ↗" if "url" in opened else "") + (" " + opened["detail"] if "detail" in opened else "")
    expected = [
        "div#pr-walk-head.sheet-stepper:%s %s" % (PW["walkHeading"], _fill(PW["walkCount"], walked=0, total=len(walk["stops"]))),
        "div#pr-walk-open.sh-box:" + box,
    ]
    if "note" in walk:
        expected.append("p:" + walk["note"])
    expected.append("p.sh-caption:" + _fill(PW["advisorWalked"], **{"from": walk["picturesFrom"]}))
    for group in dict.fromkeys(stop["group"] for stop in walk["stops"]):
        expected.append("p.sh-label:" + group)
        expected += [_expected_stop(stop, stack) for stop in walk["stops"] if stop["group"] == group]
    return expected


# Axis: the walk part's header and count, open link, note, advisor line, group labels and each stop's parts are drawn in order with the data file's words, and a stack's stops carry their PR.
@pytest.mark.parametrize("kind,sheet", [("pr", WALK_SHEET), ("stack", STACK_SHEET)])
def test_the_walk_is_drawn_part_by_part_in_order(kind, sheet):
    page = _page(sheet, WALK + """
      const brief = (node) => node.tagName + (node.id ? "#" + node.id : "") + (node.className ? "." + node.className.split(/\\s+/).join(".") : "");
      const line = (node) => brief(node) + ":" + (node.id.startsWith("fix-") ? "" : text(node));
      return {
        parts: part("pr-walk").children.map((child) => (child.tagName === "article" ? { stop: child.id, parts: child.children.map(line) } : line(child))),
        links: t.links(part("pr-walk")),
        anchors: t.all(part("pr-walk")).filter((node) => node.tagName === "a").length,
      };
    """)
    assert page["result"]["parts"] == _expected_walk(sheet)
    if kind == "pr":
        assert page["result"]["links"] == [["Open the test shop ↗", OPEN_URL, "_blank", "noopener"]]
        stops = {item["stop"]: item["parts"] for item in page["result"]["parts"] if isinstance(item, dict)}
        assert stops["stop-p1"][0] == "div:P1" and stops["stop-p3"][0] == "div:P3 Optional"
        assert stops["stop-p1"][3] == "p.expect:Expect: The second try goes through and the order is placed."
        assert stops["stop-p4"][4] == "p.sh-caption:The advisor didn't walk this stop: It needs your own sign-in to the bank's test dashboard."
        assert stops["stop-f1"][2] == "p.expect:Look for: A plain message and a way back to the cart."
        assert stops["stop-f1"][5] == "div.answer-row:Looks right Problem Skip"
        assert not any(part.startswith("ol#") for part in stops["stop-f1"])
        assert [part for part in stops["stop-p1"] if part.startswith("div.answer-row")] == ["div.answer-row:Works Problem Skip"]
        assert not any("Tap a picture" in part for part in stops["stop-p2"])
    else:
        assert page["result"]["links"] == [] and page["result"]["anchors"] == 0
        tags = [item["parts"][0] for item in page["result"]["parts"] if isinstance(item, dict)]
        assert tags == ["div:#5 GIFT-CARD-TABLE", "div:#6 CHECKOUT-REDEEM"]


# Axis: tapping Problem opens the fix question with both fixes, their consequences, both fix buttons and Add a screenshot, and relabels the note; Works hides the block again; every write is a whole walk answer.
def test_problem_shows_the_fix_block_and_works_hides_it():
    page = _page(WALK_SHEET, WALK + """
      const out = { start: stopState("p1") };
      out.startShots = { pick: pickOf("p1").textContent, pickDisabled: pickOf("p1").disabled };
      await choose("p1", "Problem");
      out.problem = stopState("p1");
      out.block = {
        question: text(fixBlock("p1").children[0]),
        fixes: fixBlock("p1").children.find((child) => child.id === "fixes-p1").children.map(text),
        buttons: fixRow("p1").map((button) => button.textContent),
        pick: pickOf("p1").textContent,
        pickDisabled: pickOf("p1").disabled,
      };
      await choose("p1", "Fix before merge");
      out.chosen = stopState("p1");
      t.type(noteOf("p1"), "It hung", "change");
      await t.tick();
      await choose("p1", "Works");
      out.works = stopState("p1");
      await choose("f1", "Looks right");
      out.look = stopState("f1");
      await choose("f1", "Problem");
      out.lookProblem = stopState("f1");
      out.sets = t.setLog();
      return out;
    """)
    result = page["result"]
    assert result["start"] == {"pressed": ["false"] * 3, "fixPressed": ["false"] * 2, "fixHidden": True, "noteLabel": "Note", "note": "", "save": "", "shots": ""}
    assert result["startShots"] == {"pick": PW["addScreenshot"], "pickDisabled": False}
    assert result["problem"] == {"pressed": ["false", "true", "false"], "fixPressed": ["false", "false"], "fixHidden": False, "noteLabel": PW["problemNote"], "note": "", "save": "Saved", "shots": ""}
    assert PW["problemNote"] == "What did you see?"
    assert result["block"] == {
        "question": PW["fixQuestion"],
        "fixes": [fix["label"] + ": " + fix["consequence"] for fix in PW["walkFixes"]],
        "buttons": [fix["label"] for fix in PW["walkFixes"]],
        "pick": "Add a screenshot",
        "pickDisabled": False,
    }
    assert result["chosen"]["pressed"] == ["false", "true", "false"] and result["chosen"]["fixPressed"] == ["true", "false"] and result["chosen"]["fixHidden"] is False
    assert result["works"] == {"pressed": ["true", "false", "false"], "fixPressed": ["false", "false"], "fixHidden": True, "noteLabel": "Note", "note": "It hung", "save": "Saved", "shots": ""}
    assert result["look"]["pressed"] == ["true", "false", "false"] and result["look"]["fixHidden"] is True
    assert result["lookProblem"]["pressed"] == ["false", "true", "false"] and result["lookProblem"]["fixHidden"] is False
    assert [(item["path"], item["body"]) for item in result["sets"]] == [
        (_path("p1"), _body("problem")),
        (_path("p1"), _body("problem", "before-merge")),
        (_path("p1"), _body("problem", "before-merge", "It hung")),
        (_path("p1"), _body("works", None, "It hung")),
        (_path("f1"), _body("looks-right")),
        (_path("f1"), _body("problem")),
    ]


LOCK = """
  const lock = () => ({ merge: merge(), problems: walkLine("walk-problems"), followUps: walkLine("follow-ups") });
"""


# Axis: with every item accepted and saved, a stop left at Problem with no fix locks Merge and shows the walk-problems line; a follow-up fix saved unlocks it with the follow-ups line; tapping the chosen fix again leaves Problem with no fix and locks it again.
def test_a_problem_with_no_fix_locks_the_merge_until_a_follow_up_is_saved():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const out = { start: lock() };
      await choose("p1", "Problem");
      out.noFix = lock();
      await choose("p1", "Fix in a follow-up");
      out.followUp = lock();
      await choose("p1", "Fix in a follow-up");
      out.retapped = { ...lock(), stop: stopState("p1") };
      await choose("p1", "Fix in a follow-up");
      out.again = lock();
      out.sets = t.setLog();
      return out;
    """, host=ACCEPTED)
    result = page["result"]
    assert result["start"] == {"merge": UNLOCKED, "problems": NO_LINE, "followUps": NO_LINE}
    assert result["noFix"] == {"merge": LOCKED, "problems": _line("walkProblems", 1), "followUps": NO_LINE}
    assert result["followUp"] == {"merge": UNLOCKED, "problems": NO_LINE, "followUps": _line("followUps", 1)}
    assert result["retapped"]["merge"] == LOCKED and result["retapped"]["problems"] == _line("walkProblems", 1) and result["retapped"]["followUps"] == NO_LINE
    assert result["retapped"]["stop"]["pressed"] == ["false", "true", "false"] and result["retapped"]["stop"]["fixPressed"] == ["false", "false"]
    assert result["again"] == result["followUp"]
    assert [item["body"] for item in result["sets"]] == [_body("problem"), _body("problem", "follow-up"), _body("problem"), _body("problem", "follow-up")]


# Axis: a Problem whose fix choice is still being saved, or whose save failed, keeps Merge locked; once the save lands the follow-ups line shows and Merge unlocks.
def test_a_fix_in_flight_or_failed_keeps_the_merge_locked():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const out = {};
      await choose("p1", "Problem");
      t.sets[0].resolve();
      await t.tick();
      out.problemSaved = lock();
      await choose("p1", "Fix in a follow-up");
      out.inFlight = { ...lock(), save: saveOf("p1") };
      t.sets[1].resolve();
      await t.tick();
      out.landed = { ...lock(), save: saveOf("p1") };
      await choose("p2", "Problem");
      t.sets[2].resolve();
      await t.tick();
      await choose("p2", "Fix in a follow-up");
      t.sets[3].reject({ code: "unavailable" });
      await t.tick();
      out.failed = { ...lock(), save: saveOf("p2"), retry: tryAgain("p2") !== undefined };
      t.click(tryAgain("p2"));
      await t.tick();
      t.sets[4].resolve();
      await t.tick();
      out.retried = { ...lock(), save: saveOf("p2") };
      out.sets = t.setLog();
      return out;
    """, host=dict(ACCEPTED, set="hold"))
    result = page["result"]
    assert result["problemSaved"] == {"merge": LOCKED, "problems": _line("walkProblems", 1), "followUps": NO_LINE}
    assert result["inFlight"] == {"merge": LOCKED, "problems": _line("walkProblems", 1), "followUps": NO_LINE, "save": "Saving…"}
    assert result["landed"] == {"merge": UNLOCKED, "problems": NO_LINE, "followUps": _line("followUps", 1), "save": "Saved"}
    assert result["failed"]["merge"] == LOCKED and result["failed"]["problems"] == _line("walkProblems", 1) and result["failed"]["followUps"] == _line("followUps", 1)
    assert "Not saved" in result["failed"]["save"] and result["failed"]["retry"] is True
    assert result["retried"] == {"merge": UNLOCKED, "problems": NO_LINE, "followUps": _line("followUps", 2), "save": "Saved"}
    assert [item["body"] for item in result["sets"]] == [
        _body("problem"), _body("problem", "follow-up"), _body("problem"), _body("problem", "follow-up"), _body("problem", "follow-up")]


# Axis: a saved Fix before merge replaces the merge verdict with the send-back message and hides the walk lines; taking it away brings the verdict back.
def test_fix_before_merge_replaces_the_verdict_with_the_send_back_message():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const shown = () => ({
        row: verdict().children.find((child) => hasClass(child, "answer-row")).hidden,
        note: verdictNote().hidden,
        sendBack: { hidden: part("sheet-verdict").children.find((child) => child.id === "verdict-send-back").hidden, text: part("sheet-verdict").children.find((child) => child.id === "verdict-send-back").textContent },
        unlock: part("sheet-verdict").children.find((child) => child.id === "verdict-unlocks").hidden,
        lines: ["walk-problems", "follow-ups", "not-walked"].map(walkLine).map((line) => line.hidden),
      });
      const out = { start: shown() };
      await choose("p1", "Problem");
      await choose("p1", "Fix before merge");
      out.sentBack = shown();
      await choose("p2", "Problem");
      out.withOpen = shown();
      await choose("p1", "Works");
      await choose("p2", "Works");
      out.back = shown();
      return out;
    """, host=ACCEPTED)
    result = page["result"]
    assert result["start"]["sendBack"]["hidden"] is True and result["start"]["row"] is False and result["start"]["note"] is False
    assert result["sentBack"] == {"row": True, "note": True, "sendBack": {"hidden": False, "text": PW["sendBack"]}, "unlock": True, "lines": [True, True, True]}
    assert result["withOpen"]["lines"] == [True, True, True] and result["withOpen"]["row"] is True
    assert result["back"]["row"] is False and result["back"]["note"] is False and result["back"]["sendBack"]["hidden"] is True
    assert result["back"]["lines"][0] is True


# Axis: with every item accepted and no stop answered Merge is unlocked and the not-walked line counts only the non-optional stops; Skip counts as not walked, and Works or Looks right on every non-optional stop hides the line.
def test_unwalked_stops_are_counted_but_never_lock_the_merge():
    page = _page(WALK_SHEET, WALK + """
      const now = () => ({ merge: merge(), line: walkLine("not-walked"), count: walkCount() });
      const out = { start: now() };
      await choose("p1", "Skip");
      out.skip = now();
      await choose("p3", "Works");
      out.optional = now();
      await choose("p1", "Works");
      out.one = now();
      await choose("p2", "Works");
      out.two = now();
      await choose("p4", "Works");
      out.three = now();
      await choose("f1", "Looks right");
      out.all = now();
      return out;
    """, host=ACCEPTED)
    result = page["result"]
    for key in ("start", "skip", "optional", "one", "two", "three", "all"):
        assert result[key]["merge"] == UNLOCKED, key
    total = len(ALL_STOPS)
    assert result["start"]["line"] == _line("notWalked", 4) and result["start"]["count"] == _fill(PW["walkCount"], walked=0, total=total)
    assert result["skip"]["line"] == _line("notWalked", 4) and result["skip"]["count"] == _fill(PW["walkCount"], walked=0, total=total)
    assert result["optional"]["line"] == _line("notWalked", 4) and result["optional"]["count"] == _fill(PW["walkCount"], walked=1, total=total)
    assert result["one"]["line"] == _line("notWalked", 3) and result["one"]["count"] == _fill(PW["walkCount"], walked=2, total=total)
    assert result["two"]["line"] == _line("notWalked", 2) and result["two"]["count"] == _fill(PW["walkCount"], walked=3, total=total)
    assert result["three"]["line"] == _line("notWalked", 1) and result["three"]["count"] == _fill(PW["walkCount"], walked=4, total=total)
    assert result["all"]["line"] == NO_LINE and result["all"]["count"] == _fill(PW["walkCount"], walked=5, total=total)


MERGED = {"collections": dict(ACCEPTED["collections"], verdict=[{"id": DIGEST, "data": {"verdict": "merge", "note": "", "sheet": DIGEST}}])}


# Axis: with a saved Merge, tapping Problem writes the verdict clear first and the walk document only after that clear resolves.
def test_a_problem_write_waits_for_the_merge_clear_to_land():
    page = _page(WALK_SHEET, WALK + """
      const out = { before: { merge: merge(), sets: t.setLog() } };
      t.click(btn("p1", "Problem"));
      out.tapped = { sets: t.setLog(), save: saveOf("p1"), merge: merge() };
      t.sets[0].resolve();
      await t.tick();
      out.cleared = { sets: t.setLog(), merge: merge() };
      t.sets[1].resolve();
      await t.tick();
      out.end = { save: saveOf("p1"), merge: merge() };
      return out;
    """, host=dict(MERGED, set="hold"))
    result = page["result"]
    clear = {"path": "verdict/" + DIGEST, "body": {"verdict": None, "note": "", "sheet": DIGEST}}
    assert result["before"] == {"merge": dict(UNLOCKED, pressed="true"), "sets": []}
    assert result["tapped"]["sets"] == [clear] and result["tapped"]["save"] == "Saving…"
    assert result["cleared"]["sets"] == [clear, {"path": _path("p1"), "body": _body("problem")}]
    assert result["cleared"]["merge"] == LOCKED
    assert result["end"] == {"save": "Saved", "merge": LOCKED}


# Axis: with a saved Merge, Works on a stop is written at once and the Merge stays.
def test_works_is_written_at_once_and_the_saved_merge_stays():
    page = _page(WALK_SHEET, WALK + """
      t.click(btn("p1", "Works"));
      const tapped = t.setLog();
      t.sets[0].resolve();
      await t.tick();
      return { tapped: tapped, merge: merge(), sets: t.setLog(), save: saveOf("p1") };
    """, host=dict(MERGED, set="hold"))
    result = page["result"]
    assert result["tapped"] == [{"path": _path("p1"), "body": _body("works")}]
    assert result["sets"] == result["tapped"]
    assert result["merge"] == dict(UNLOCKED, pressed="true") and result["save"] == "Saved"


def _walk_docs(written):
    return [{"id": path.split("/", 1)[1], "data": body} for path, body in written.items() if path.startswith("walk/")]


# Axis: a follow-up fix chosen while the Problem's write is still held keeps Merge locked until that fix is saved.
def test_a_follow_up_chosen_over_a_held_problem_keeps_the_merge_locked():
    page = _page(WALK_SHEET, WALK + """
      t.click(btn("p1", "Problem"));
      await t.tick();
      await choose("p1", "Fix in a follow-up");
      return merge();
    """, host=dict(MERGED, set="hold"))
    assert page["result"]["disabled"] is True


# Axis: beside a saved Merge, a follow-up Problem's note edit and a screenshot are both written at once and the Merge stays, since a follow-up never blocks Merge.
def test_a_follow_up_problem_note_and_screenshot_are_written_beside_a_saved_merge():
    held = _walk_docs({_path("p1"): _body("problem", "follow-up")})
    page = _page(WALK_SHEET, WALK + """
      t.type(noteOf("p1"), "Also slow", "change");
      await t.tick();
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      return { sets: t.setLog().map((call) => call.body), merge: merge(), save: saveOf("p1") };
    """, host={"collections": dict(MERGED["collections"], walk=held), "assets": "ok"})
    result = page["result"]
    assert [(body["note"], len(body["shots"])) for body in result["sets"]] == [("Also slow", 0), ("Also slow", 1)]
    assert result["merge"] == dict(UNLOCKED, pressed="true") and result["save"] == "Saved"


# Axis: every stop answered (each check answer, a Problem with each fix, notes, a screenshot) comes back from the store on a reopened page with its answers, notes, screenshots and the right walked count.
def test_answered_stops_come_back_when_the_page_is_reopened():
    first = _page(WALK_SHEET, WALK + """
      await choose("p1", "Problem");
      await choose("p1", "Fix before merge");
      t.type(noteOf("p1"), "Declined twice", "change");
      await t.tick();
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      await choose("p2", "Works");
      t.type(noteOf("p2"), "Sent at once", "change");
      await t.tick();
      await choose("p3", "Skip");
      await choose("p4", "Problem");
      await choose("p4", "Fix in a follow-up");
      t.type(noteOf("p4"), "Two charges", "change");
      await t.tick();
      await choose("f1", "Looks right");
      return { written: t.written() };
    """, host={"assets": "ok"})
    written = first["result"]["written"]
    assert written == {
        _path("p1"): _body("problem", "before-merge", "Declined twice", ["asset-1"]),
        _path("p2"): _body("works", None, "Sent at once"),
        _path("p3"): _body("skip"),
        _path("p4"): _body("problem", "follow-up", "Two charges"),
        _path("f1"): _body("looks-right"),
    }
    page = _page(WALK_SHEET, WALK + """
      const out = { count: walkCount(), stops: {} };
      ["p1", "p2", "p3", "p4", "f1"].forEach((id) => { out.stops[id] = stopState(id); });
      out.controlsOff = walkControls().some((node) => node.disabled);
      return out;
    """, host={"collections": {"walk": _walk_docs(written)}})
    result = page["result"]
    assert result["count"] == _fill(PW["walkCount"], walked=4, total=5)
    assert result["controlsOff"] is False
    assert result["stops"]["p1"] == {"pressed": ["false", "true", "false"], "fixPressed": ["true", "false"], "fixHidden": False, "noteLabel": PW["problemNote"], "note": "Declined twice", "save": "Saved", "shots": _fill(PW["screenshotsAdded"], count=1)}
    assert result["stops"]["p2"] == {"pressed": ["true", "false", "false"], "fixPressed": ["false", "false"], "fixHidden": True, "noteLabel": "Note", "note": "Sent at once", "save": "Saved", "shots": ""}
    assert result["stops"]["p3"]["pressed"] == ["false", "false", "true"] and result["stops"]["p3"]["save"] == "Saved"
    assert result["stops"]["p4"] == {"pressed": ["false", "true", "false"], "fixPressed": ["false", "true"], "fixHidden": False, "noteLabel": PW["problemNote"], "note": "Two charges", "save": "Saved", "shots": ""}
    assert result["stops"]["f1"]["pressed"] == ["true", "false", "false"]


# Axis: a stored Problem with no fix beside a stored Merge leaves the sheet locked and clears that Merge.
def test_a_stored_problem_without_a_fix_beside_a_stored_merge_clears_the_merge():
    docs = dict(MERGED["collections"], walk=[{"id": _path("p1")[5:], "data": _body("problem", None, "It hung")}])
    page = _page(WALK_SHEET, WALK + LOCK + """
      await t.tick();
      return { ...lock(), sets: t.setLog(), stop: stopState("p1") };
    """, host={"collections": docs})
    result = page["result"]
    assert result["merge"] == LOCKED and result["problems"] == _line("walkProblems", 1)
    assert result["sets"] == [{"path": "verdict/" + DIGEST, "body": {"verdict": None, "note": "", "sheet": DIGEST}}]
    assert result["stop"]["pressed"] == ["false", "true", "false"] and result["stop"]["note"] == "It hung"


# Axis: a stored walk document that does not fit (a fix on Works, Looks right on a try stop) restores only its note, a Problem with a fix the page does not offer restores as a Problem with no fix, while one that fits is restored whole.
def test_a_stored_document_that_does_not_fit_restores_only_its_note():
    docs = [
        {"id": _path("p1")[5:], "data": _body("works", "follow-up", "kept 1")},
        {"id": _path("p2")[5:], "data": _body("looks-right", None, "kept 2")},
        {"id": _path("p3")[5:], "data": _body("problem", "someone-else", "kept 3")},
        {"id": _path("p4")[5:], "data": _body("skip", None, "kept 4", ["asset-9"])},
        {"id": _path("f1")[5:], "data": _body("works", None, "kept 5")},
    ]
    page = _page(WALK_SHEET, WALK + """
      const out = {};
      ["p1", "p2", "p3", "p4", "f1"].forEach((id) => { out[id] = stopState(id); });
      out.count = walkCount();
      return out;
    """, host={"collections": {"walk": docs}})
    result = page["result"]
    for stop_id, note in (("p1", "kept 1"), ("p2", "kept 2"), ("f1", "kept 5")):
        assert result[stop_id] == {"pressed": ["false"] * 3, "fixPressed": ["false"] * 2, "fixHidden": True, "noteLabel": "Note", "note": note, "save": "Saved", "shots": ""}, stop_id
    # A fix the page does not offer is the one exception: the recorded Problem stays, with no fix, so it keeps blocking Merge.
    assert result["p3"]["pressed"] == ["false", "true", "false"] and result["p3"]["fixPressed"] == ["false"] * 2 and result["p3"]["note"] == "kept 3"
    assert result["p4"]["pressed"] == ["false", "false", "true"] and result["p4"]["note"] == "kept 4"
    assert result["p4"]["shots"] == _fill(PW["screenshotsAdded"], count=1)
    assert result["count"] == _fill(PW["walkCount"], walked=1, total=5)


# Axis: a walk read that rejects leaves every control off with the retry line, and the retry that succeeds turns them on and restores what it read.
def test_a_walk_read_that_rejects_leaves_the_controls_off_until_the_retry_succeeds():
    page = _page(WALK_SHEET, WALK + """
      await t.tick();
      await t.tick();
      const out = { gate: t.gate().message, hidden: t.gate().hidden, retry: t.gate().retry !== undefined };
      out.off = { walk: walkControls().map((node) => node.disabled), verdict: verdictState().disabled };
      t.click(btn("p1", "Works"));
      out.writes = t.setLog().length;
      if (t.gate().retry) t.click(t.gate().retry);
      await t.tick();
      await t.tick();
      out.after = { hidden: t.gate().hidden, walk: walkControls().map((node) => node.disabled), p2: stopState("p2").pressed };
      return out;
    """, host={"readByCollection": {"walk": ["reject", "docs"]}, "collections": {"walk": [{"id": _path("p2")[5:], "data": _body("works")}]}})
    result = page["result"]
    assert result["gate"] == READ_FAILED and result["hidden"] is False and result["retry"] is True
    assert set(result["off"]["walk"]) == {True} and set(result["off"]["verdict"]) == {True} and result["writes"] == 0
    assert result["after"]["hidden"] is True and set(result["after"]["walk"]) == {False}
    assert result["after"]["p2"] == ["true", "false", "false"]


# Axis: a walk read that never answers shows the retry line after the wait with every control off, and the retry that succeeds turns them on.
def test_a_walk_read_that_stalls_leaves_the_controls_off_until_the_retry_succeeds():
    page = _page(WALK_SHEET, WALK + """
      const out = {};
      await t.advance(10000);
      out.gate = { message: t.gate().message, hidden: t.gate().hidden, retry: t.gate().retry !== undefined };
      out.off = walkControls().map((node) => node.disabled);
      if (t.gate().retry) t.click(t.gate().retry);
      await t.advance(10);
      out.after = { hidden: t.gate().hidden, walk: walkControls().map((node) => node.disabled) };
      return out;
    """, host={"fakeTimers": True, "readByCollection": {"walk": ["hold", "docs"]}})
    result = page["result"]
    assert result["gate"] == {"message": READ_FAILED, "hidden": False, "retry": True}
    assert set(result["off"]) == {True}
    assert result["after"]["hidden"] is True and set(result["after"]["walk"]) == {False}


# Axis: a pr sheet with no walk has no walk part, reads no walk answers and shows no walk lines, and its merge works as before.
def test_a_sheet_with_no_walk_reads_nothing_and_shows_no_walk_lines():
    sheet = _with(WALK_SHEET, lambda clone: clone["prSheet"].pop("walk"))
    page = _page(sheet, WALK + """
      const out = { order: order(), reads: t.reads.map((read) => read.name).sort() };
      out.lines = ["walk-problems", "follow-ups", "not-walked"].map(walkLine);
      out.merge = merge();
      return out;
    """, host=ACCEPTED)
    result = page["result"]
    assert "pr-walk" not in result["order"] and result["reads"] == ["answers", "verdict"]
    assert result["lines"] == [NO_LINE] * 3 and result["merge"] == UNLOCKED


def _with_links(sheet):
    def mutate(clone):
        stops = clone["prSheet"]["walk"]["stops"]
        stops[0]["pictures"][0].update(alt="Cart at https://shop.example.test/cart", caption="Taken at https://shop.example.test/cart (the test shop)")
        stops[4]["pictures"][1].update(alt="Small phone at https://shop.example.test/small", caption="See https://shop.example.test/small for it")
    return _with(sheet, mutate)


# Axis: each copied picture is an image with its own pictures/ src and alt in a figure with its caption; none is wrapped in a link.
def test_copied_pictures_are_images_with_their_own_src():
    page = _page(WALK_SHEET, WALK + """
      const describe = (id) => imagesOf(id).map((img) => [img.getAttribute("src"), img.getAttribute("alt"), img.parent.tagName, img.parent.parent.className]);
      return { p1: describe("p1"), f1: describe("f1"), p2: describe("p2") };
    """)
    pictures = {stop["id"]: stop["pictures"] for stop in WALK_SHEET["prSheet"]["walk"]["stops"]}
    assert page["result"]["p1"] == [[_src_of(p), pictures["p1"][i]["alt"], "figure", "sheet-images"] for i, p in enumerate(["elsewhere/cart-empty.png", "elsewhere/cart-paid.png"])]
    assert page["result"]["f1"] == [[_src_of("elsewhere/declined-screen.png"), "The gave-up screen", "figure", "sheet-images"]]
    assert page["result"]["p2"] == []
    assert all(src.startswith("pictures/") for src, *_ in page["result"]["p1"] + page["result"]["f1"])


# Axis: no element in the walk is an anchor except the open link, even when a caption and an alt hold https:// addresses.
def test_a_walk_picture_caption_and_alt_are_plain_text_never_links():
    sheet = _with_links(WALK_SHEET)
    page = _page(sheet, WALK + """
      const anchors = t.all(part("pr-walk")).filter((node) => node.tagName === "a");
      return {
        anchors: anchors.map((node) => [node.textContent, node.getAttribute("href")]),
        captions: t.all(part("pr-walk")).filter((node) => node.tagName === "figcaption").map((node) => [node.textContent, node.children.length]),
        alts: imagesOf("p1").map((img) => img.getAttribute("alt")),
        missing: stop("f1").children.find((child) => hasClass(child, "sheet-images")).children[1].children.map((node) => [node.tagName, node.textContent]),
      };
    """)
    result = page["result"]
    assert result["anchors"] == [["Open the test shop ↗", OPEN_URL]]
    assert result["captions"] == [["Taken at https://shop.example.test/cart (the test shop)", 0], ["After three failures", 0], ["See https://shop.example.test/small for it", 0]]
    assert result["alts"][0] == "Cart at https://shop.example.test/cart"
    assert result["missing"] == [["p", _fill(PW["pictureMissing"], alt="Small phone at https://shop.example.test/small")], ["figcaption", "See https://shop.example.test/small for it"]]


# Axis: a picture that was not copied draws the missing line with no image and keeps its caption, a stop with only missing pictures has no tap-a-picture line, and the stop still saves an answer.
def test_a_missing_picture_is_a_line_and_its_stop_still_saves():
    only_missing = _with(WALK_SHEET, lambda clone: clone["prSheet"]["walk"]["stops"][4]["pictures"].__setitem__(0, {"missing": True, "alt": "The gave-up screen", "caption": "After three failures"}))
    page = _page(only_missing, WALK + """
      const wrap = stop("f1").children.find((child) => hasClass(child, "sheet-images"));
      const out = {
        figures: wrap.children.map((figure) => figure.children.map((node) => [node.tagName, node.textContent])),
        images: imagesOf("f1").length,
        tap: stop("f1").children.some((child) => child.textContent === "Tap a picture to see it full size."),
      };
      await choose("f1", "Looks right");
      out.state = stopState("f1");
      out.sets = t.setLog();
      return out;
    """)
    result = page["result"]
    assert result["figures"] == [[["p", _fill(PW["pictureMissing"], alt="The gave-up screen")], ["figcaption", "After three failures"]],
                                 [["p", _fill(PW["pictureMissing"], alt="The gave-up screen on a small phone")]]]
    assert result["images"] == 0 and result["tap"] is False
    assert result["state"]["pressed"] == ["true", "false", "false"] and result["state"]["save"] == "Saved"
    assert result["sets"] == [{"path": _path("f1", only_missing), "body": _body("looks-right")}]


# Axis: an image that errors becomes the missing line in its figure, its caption stays, and the stop still saves an answer.
def test_an_image_that_fails_to_load_becomes_the_missing_line():
    page = _page(WALK_SHEET, WALK + """
      const wrap = () => stop("f1").children.find((child) => hasClass(child, "sheet-images"));
      const out = { before: imagesOf("f1").length };
      t.fire(imagesOf("f1")[0], "error");
      out.figures = wrap().children.map((figure) => figure.children.map((node) => [node.tagName, node.textContent]));
      out.after = imagesOf("f1").length;
      out.p1Images = imagesOf("p1").length;
      await choose("f1", "Problem");
      out.state = stopState("f1");
      return out;
    """)
    result = page["result"]
    assert result["before"] == 1 and result["after"] == 0 and result["p1Images"] == 2
    assert result["figures"] == [[["p", _fill(PW["pictureMissing"], alt="The gave-up screen")], ["figcaption", "After three failures"]],
                                 [["p", _fill(PW["pictureMissing"], alt="The gave-up screen on a small phone")]]]
    assert result["state"]["pressed"] == ["false", "true", "false"] and result["state"]["save"] == "Saved"


ZOOM = """
  const zoom = elements["sheet-viewer-zoom"];
  const size = () => [t.shown().width, t.shown().height];
  const p = (type, id, x, y) => t.pointer(type, { pointerId: id, clientX: x, clientY: y, timeStamp: 0, pointerType: "touch" });
  const labels = () => zoom.children.map((node) => node.textContent);
  const press = (label) => t.click(zoom.children.find((node) => node.textContent === label));
"""


# Axis: on a pr sheet an opened picture shows the zoom buttons, + grows the drawn size, − shrinks it, Fit returns to the fitted size after + and after a pinch, and Close closes.
def test_the_pr_sheet_viewer_zooms_with_buttons_and_fit_goes_back():
    page = _page(WALK_SHEET, WALK + ZOOM + """
      const out = {};
      t.click(imagesOf("p1")[0]);
      t.loadView([800, 600], [400, 300]);
      out.labels = labels();
      out.fitted = size();
      press("+");
      out.plus = size();
      press(labels()[0]);
      out.minus = size();
      press("+");
      press("+");
      out.twice = size();
      press("Fit");
      out.fitAfterPlus = size();
      p("pointerdown", 1, 100, 150);
      p("pointerdown", 2, 200, 150);
      p("pointermove", 2, 300, 150);
      out.pinched = size();
      press("Fit");
      out.fitAfterPinch = size();
      p("pointerup", 2, 300, 150);
      p("pointerup", 1, 100, 150);
      out.open = t.view.root.hidden;
      t.click(t.view.close);
      out.closed = t.view.root.hidden;
      return out;
    """)
    result = page["result"]
    assert result["labels"] == [PW["zoomOut"], PW["zoomIn"], PW["zoomFit"]] == ["−", "+", "Fit"]
    assert result["fitted"] == [400, 300]
    assert result["plus"] == [500, 375] and result["minus"] == [400, 300]
    assert result["twice"][0] > result["plus"][0] and result["twice"] == [625, 469]
    assert result["fitAfterPlus"] == [400, 300]
    assert result["pinched"] == [800, 600] and result["fitAfterPinch"] == [400, 300]
    assert result["open"] is False and result["closed"] is True


# Axis: the image view of a final sheet and of a plain sheet has no zoom buttons.
@pytest.mark.parametrize("sheet", [_sheet(cards=[_picture_card("pic-card")]), _sample_final(cards=[_picture_card("pic-card")])], ids=["plain", "final"])
def test_the_other_kinds_have_no_zoom_buttons(sheet):
    page = _run_page(_sample_files(sheet), scenario="""
      const zoom = elements["sheet-viewer-zoom"];
      t.click(t.pictures("pic-card")[0]);
      t.loadView([800, 600], [400, 300]);
      return { shown: t.view.root.hidden, buttons: zoom.children.length };
    """)
    assert page["settled"] and page["result"] == {"shown": False, "buttons": 0}


# Axis: with no picture store the page asks for none at load, and a tap on Add a screenshot says screenshots can't be added and turns the button off.
@pytest.mark.parametrize("host", [{}, {"assets": "use-rejects"}, {"assets": "no-upload"}], ids=["absent", "use-rejects", "no-upload"])
def test_without_a_picture_store_add_a_screenshot_says_so_and_turns_off(host):
    page = _page(WALK_SHEET, WALK + """
      const out = { usesAtLoad: t.uses.slice() };
      await choose("p1", "Problem");
      t.click(pickOf("p1"));
      await t.tick();
      out.line = shotLineOf("p1");
      out.disabled = pickOf("p1").disabled;
      out.picked = inputOf("p1").clicks || 0;
      out.uploads = t.uploads.length;
      out.sets = t.setLog();
      return out;
    """, host=host)
    result = page["result"]
    assert result["usesAtLoad"] == ["db", "user"]
    assert result["line"] == PW["screenshotUnavailable"] and result["disabled"] is True
    assert result["picked"] == 0 and result["uploads"] == 0
    assert result["sets"] == [{"path": _path("p1"), "body": _body("problem")}]


# Axis: two uploaded screenshots are written as the document's shots in order and the line counts 2.
def test_two_screenshots_are_saved_in_order_and_counted():
    page = _page(WALK_SHEET, WALK + """
      await choose("p1", "Problem");
      t.click(pickOf("p1"));
      await t.tick();
      const out = { picked: inputOf("p1").clicks || 0 };
      await shoot("p1");
      out.one = shotLineOf("p1");
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      out.two = { line: shotLineOf("p1"), pick: pickOf("p1").disabled, save: saveOf("p1") };
      out.uploads = t.uploads.map((call) => call.file.name);
      out.sets = t.setLog();
      return out;
    """, host={"assets": "ok"})
    result = page["result"]
    assert result["picked"] == 1 and result["uploads"] == ["shot.png", "shot.png"]
    assert result["one"] == _fill(PW["screenshotsAdded"], count=1)
    assert result["two"] == {"line": _fill(PW["screenshotsAdded"], count=2), "pick": False, "save": "Saved"}
    assert [item["body"] for item in result["sets"]] == [_body("problem"), _body("problem", None, "", ["asset-1"]), _body("problem", None, "", ["asset-1", "asset-2"])]
    assert result["sets"][-1]["body"]["shots"] == ["asset-1", "asset-2"]


# Axis: an upload the store rejects says the screenshot didn't upload, writes nothing, and leaves the button on.
def test_a_rejected_upload_says_so_and_writes_nothing():
    page = _page(WALK_SHEET, WALK + """
      await choose("p1", "Problem");
      const before = t.setLog().length;
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      return { before: before, sets: t.setLog().length, line: shotLineOf("p1"), pick: pickOf("p1").disabled, save: saveOf("p1"), uploads: t.uploads.length };
    """, host={"assets": "reject"})
    assert page["result"] == {"before": 1, "sets": 1, "line": PW["screenshotFailed"], "pick": False, "save": "Saved", "uploads": 1}


# Axis: after a rejected upload the same screenshot can be chosen again and uploads again, because the page resets the file input.
def test_the_same_screenshot_uploads_again_after_a_rejected_upload():
    page = _page(WALK_SHEET, WALK + """
      await choose("p1", "Problem");
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      const first = { uploads: t.uploads.length, files: inputOf("p1").files.length };
      await shoot("p1");
      return { first: first, uploads: t.uploads.length, line: shotLineOf("p1"), pick: pickOf("p1").disabled };
    """, host={"assets": "reject"})
    assert page["result"] == {"first": {"uploads": 1, "files": 0}, "uploads": 2, "line": PW["screenshotFailed"], "pick": False}


# Axis: a save of the shots that the store rejects shows Not saved with Try again, and the retry that lands shows Saved with the screenshot kept.
def test_a_rejected_save_of_the_shots_shows_not_saved_with_try_again():
    page = _page(WALK_SHEET, WALK + """
      await choose("p1", "Problem");
      t.sets[0].resolve();
      await t.tick();
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      t.sets[1].reject({ code: "unavailable" });
      await t.tick();
      const out = { failed: { save: saveOf("p1"), retry: tryAgain("p1") !== undefined, line: shotLineOf("p1") } };
      t.click(tryAgain("p1"));
      await t.tick();
      t.sets[2].resolve();
      await t.tick();
      out.retried = { save: saveOf("p1"), line: shotLineOf("p1") };
      out.sets = t.setLog();
      return out;
    """, host={"assets": "ok", "set": "hold"})
    result = page["result"]
    assert "Not saved" in result["failed"]["save"] and result["failed"]["retry"] is True
    assert result["failed"]["line"] == _fill(PW["screenshotsAdded"], count=1)
    assert result["retried"] == {"save": "Saved", "line": _fill(PW["screenshotsAdded"], count=1)}
    assert [item["body"] for item in result["sets"]] == [_body("problem"), _body("problem", None, "", ["asset-1"]), _body("problem", None, "", ["asset-1"])]


# Axis: the app bar's accepted count leaves out an Accept that is in flight or failed and counts it once the store has saved it.
def test_the_app_bar_counts_only_saved_acceptances():
    card = WALK_SHEET["cards"][0]["id"]
    page = _page(WALK_SHEET, WALK + """
      const out = { start: t.count() };
      t.click(t.button(%s, "Accept"));
      await t.tick();
      out.inFlight = { count: t.count(), save: t.saveText(%s) };
      t.sets[0].reject({ code: "unavailable" });
      await t.tick();
      out.failed = { count: t.count(), save: t.saveText(%s) };
      t.click(t.tryAgain(%s));
      await t.tick();
      out.retrying = t.count();
      t.sets[1].resolve();
      await t.tick();
      out.saved = { count: t.count(), save: t.saveText(%s) };
      return out;
    """ % ((json.dumps(card),) * 5), host={"set": "hold"})
    result = page["result"]
    total = len(WALK_SHEET["cards"])

    def accepted(count):
        return _fill(PW["acceptedCount"], accepted=count, total=total)

    assert result["start"] == accepted(0)
    assert result["inFlight"] == {"count": accepted(0), "save": "Saving…"}
    assert result["failed"]["count"] == accepted(0) and "Not saved" in result["failed"]["save"]
    assert result["retrying"] == accepted(0)
    assert result["saved"] == {"count": accepted(1), "save": "Saved"}


# Axis: a stack's craft and already-decided entries are prefixed with their PR, and a pr sheet's are not.
@pytest.mark.parametrize("kind,sheet", [("pr", WALK_SHEET), ("stack", STACK_SHEET)])
def test_craft_and_decided_entries_name_their_pr_only_on_a_stack(kind, sheet):
    page = _page(sheet, """
      const lines = (id) => part(id).children[1].children.map((item) => item.textContent);
      return { craft: lines("pr-craft"), decided: lines("pr-decided") };
    """)
    prs = sheet["prSheet"]
    assert prs["craft"] and prs["alreadyDecided"]
    assert page["result"] == {"craft": _entry_lines(prs["craft"], kind), "decided": _entry_lines(prs["alreadyDecided"], kind)}
    if kind == "stack":
        assert page["result"]["craft"][0].startswith("#7: ") and page["result"]["decided"][0].startswith("#7: ")
    else:
        assert not any(line.startswith("#") for line in page["result"]["craft"] + page["result"]["decided"])


# Axis: a Problem tapped while Works is still in flight waits for the Merge clear, even though the queued state goes out when Works settles.
def test_a_problem_queued_behind_an_inflight_works_still_waits_for_the_merge_clear():
    page = _page(WALK_SHEET, WALK + """
      t.click(btn("p1", "Works"));
      t.click(btn("p1", "Problem"));
      const out = { start: t.setLog().map((item) => item.path) };
      t.sets[0].resolve();
      await t.tick();
      out.settled = t.setLog().map((item) => item.path);
      t.sets[1].reject({ code: "unavailable" });
      await t.tick();
      out.rejected = t.setLog().map((item) => item.path);
      return out;
    """, host=dict(MERGED, set="hold"))
    result = page["result"]
    assert result["start"] == [_path("p1"), "verdict/" + DIGEST]
    assert result["settled"] == result["start"] and result["rejected"] == result["start"]


# Axis: a saved Problem with no fix keeps Merge locked while its replacement is in flight or failed.
def test_a_saved_problem_stays_blocking_until_its_replacement_is_saved():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const out = { start: lock().merge };
      await choose("p1", "Works");
      out.pending = lock().merge;
      t.sets[0].reject({ code: "unavailable" });
      await t.tick();
      out.failed = lock().merge;
      t.click(tryAgain("p1"));
      await t.tick();
      t.sets[1].resolve();
      await t.tick();
      out.landed = lock().merge;
      return out;
    """, host=dict(ACCEPTED, set="hold", collections=dict(ACCEPTED["collections"], walk=[{"id": _path("p1")[5:], "data": _body("problem")}])))
    result = page["result"]
    assert result == {"start": LOCKED, "pending": LOCKED, "failed": LOCKED, "landed": UNLOCKED}


# Axis: a saved Fix before merge keeps Merge locked while its replacement is in flight or failed, and only the landed replacement unlocks it.
def test_a_saved_fix_before_merge_stays_blocking_until_its_replacement_is_saved():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const out = {};
      await choose("p1", "Works");
      out.pending = lock().merge;
      t.sets[0].reject({ code: "unavailable" });
      await t.tick();
      out.failed = lock().merge;
      t.click(tryAgain("p1"));
      await t.tick();
      t.sets[1].resolve();
      await t.tick();
      out.landed = lock().merge;
      return out;
    """, host=dict(ACCEPTED, set="hold", collections=dict(ACCEPTED["collections"], walk=[{"id": _path("p1")[5:], "data": _body("problem", "before-merge")}])))
    assert page["result"] == {"pending": LOCKED, "failed": LOCKED, "landed": UNLOCKED}


# Axis: a Problem whose write is still in flight keeps Merge locked when Works replaces it, until the Works lands.
def test_a_problem_in_flight_stays_blocking_when_works_replaces_it():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const out = {};
      await choose("p1", "Problem");
      await choose("p1", "Works");
      out.pending = lock().merge;
      t.sets[0].resolve();
      await t.tick();
      t.sets[1].resolve();
      await t.tick();
      out.landed = lock().merge;
      return out;
    """, host=dict(ACCEPTED, set="hold"))
    assert page["result"] == {"pending": LOCKED, "landed": UNLOCKED}


# Axis: a Problem write that was rejected may still be stored, so Merge stays locked while its Works replacement is pending or failed, until a replacement lands.
def test_a_rejected_problem_write_keeps_merge_locked_until_a_replacement_lands():
    page = _page(WALK_SHEET, WALK + LOCK + """
      const out = {};
      await choose("p1", "Problem");
      await choose("p1", "Works");
      t.sets[0].reject({ code: "unavailable" });
      await t.tick();
      out.pending = lock().merge;
      t.sets[1].reject({ code: "unavailable" });
      await t.tick();
      out.failed = lock().merge;
      t.click(tryAgain("p1"));
      await t.tick();
      t.sets[2].resolve();
      await t.tick();
      out.landed = lock().merge;
      return out;
    """, host=dict(ACCEPTED, set="hold"))
    assert page["result"] == {"pending": LOCKED, "failed": LOCKED, "landed": UNLOCKED}


_CLEAR = {"path": "verdict/" + DIGEST, "body": {"verdict": None, "note": "", "sheet": DIGEST}}


# Axis: a restored Problem with Fix before merge beside a restored Merge clears that Merge.
def test_a_restored_fix_before_merge_clears_a_restored_merge():
    page = _page(WALK_SHEET, WALK + LOCK + """
      await t.tick();
      return { merge: lock().merge, sets: t.setLog() };
    """, host=dict(MERGED, collections=dict(MERGED["collections"], walk=[{"id": _path("p1")[5:], "data": _body("problem", "before-merge")}])))
    assert page["result"]["merge"] == LOCKED and page["result"]["sets"] == [_CLEAR]


# Axis: a stored Problem whose fix is not offered, or whose document is malformed, restores as a Problem with no fix that still clears a restored Merge.
@pytest.mark.parametrize("data", [_body("problem", "retired-fix", "Still broken"), {"answer": "problem", "fix": None, "note": "Still broken"}])
def test_a_restored_problem_with_an_unknown_fix_stays_a_blocking_problem(data):
    page = _page(WALK_SHEET, WALK + LOCK + """
      await t.tick();
      return { merge: lock().merge, sets: t.setLog(), p1: stopState("p1") };
    """, host=dict(MERGED, collections=dict(MERGED["collections"], walk=[{"id": _path("p1")[5:], "data": data}])))
    result = page["result"]
    assert result["merge"] == LOCKED and result["sets"] == [_CLEAR]
    assert result["p1"]["pressed"][1] == "true" and result["p1"]["note"] == "Still broken"


# Axis: an upload that never answers stops waiting at the deadline, says so, and gives the button and the leave-page guard back.
def test_a_stalled_upload_gives_the_button_back_and_says_it_failed():
    page = _page(WALK_SHEET, WALK + """
      await choose("p1", "Problem");
      t.click(pickOf("p1"));
      await t.tick();
      await shoot("p1");
      const out = { during: { line: shotLineOf("p1"), pick: pickOf("p1").disabled } };
      await t.advance(30000);
      out.after = { line: shotLineOf("p1"), pick: pickOf("p1").disabled };
      return out;
    """, host={"assets": "hold", "fakeTimers": True})
    result = page["result"]
    assert result["during"]["pick"] is True
    assert result["after"] == {"line": PW["screenshotFailed"], "pick": False}


# Axis: a republished sheet whose stop changed restores nothing for that stop, while an unchanged stop keeps its answer.
def test_a_republished_stop_that_changed_starts_unanswered_and_an_unchanged_one_keeps_its_answer():
    def edited(clone):
        next(s for s in clone["prSheet"]["walk"]["stops"] if s["id"] == "p1")["steps"].append("Pay with a second failing card")
        return clone

    changed = _with(WALK_SHEET, edited)
    docs = [{"id": _path(stop_id)[5:], "data": _body("works", None, "kept " + stop_id)} for stop_id in ("p1", "p2")]
    assert _path("p1", changed) != _path("p1") and _path("p2", changed) == _path("p2")
    page = _page(changed, WALK + """
      return { p1: stopState("p1"), p2: stopState("p2"), count: walkCount() };
    """, host={"collections": {"walk": docs}})
    result = page["result"]
    assert result["p1"]["pressed"] == ["false"] * 3 and result["p1"]["note"] == "" and result["p1"]["save"] == ""
    assert result["p2"]["pressed"] == ["true", "false", "false"] and result["p2"]["note"] == "kept p2"
    assert result["count"] == _fill(PW["walkCount"], walked=1, total=5)


def _stop_edit(change):
    def edited(clone):
        change(next(s for s in clone["prSheet"]["walk"]["stops"] if s["id"] == "p1"))
        return clone
    return _with(WALK_SHEET, edited)


# Axis: a stop's key follows every UTF-16 unit and each picture's caption, so a changed expectation behind many emoji or a changed caption starts unanswered.
def test_a_stop_changed_behind_emoji_or_in_a_caption_starts_unanswered():
    def emoji(clone):
        clone["title"] = "Retry " + "\U0001F4B3" * 6
        clone["pictures"] = []
        clone["expect"] = "Charges: 1"

    def caption(clone):
        clone["pictures"][0]["caption"] = "The expected success state"

    for first in (emoji, caption):
        before = _stop_edit(first)
        after = _stop_edit(lambda clone: (first(clone), clone.update(expect="Charges: 2") if first is emoji else clone["pictures"][0].update(caption="An error state")))
        assert _path("p1", before) != _path("p1", after)
        page = _page(after, WALK + "return stopState('p1');", host={"collections": {"walk": [{"id": _path("p1", before)[5:], "data": _body("works", None, "old")}]}})
        assert page["result"]["pressed"] == ["false"] * 3 and page["result"]["note"] == ""
        saved = _page(before, WALK + "await choose('p1', 'Works'); return t.setLog().map((item) => item.path);")
        assert saved["result"] == [_path("p1", before)]
