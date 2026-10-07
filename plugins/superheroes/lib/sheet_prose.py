#!/usr/bin/env python3
"""Render a review sheet's data file as numbered chat prose, for a host that can't show the sheet.

Reads the same `sheet.json` the page draws and prints each card as a numbered item with its context,
options and recommendation; a final sheet also prints its history, declined findings and approval. It checks the
file against sheet.schema.json, read at run time by a small reader of the keywords that schema uses, plus the
schema's four cross-field rules. A schema that uses a keyword the reader doesn't enforce is refused whole. It uses
the standard library only, so it runs under a plain python3.
It refuses a data file it can't trust: one problem per line on stderr, nothing on stdout, exit 1.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "theme" / "sheet.schema.json"

ENFORCED = {
    "type", "const", "enum", "minLength", "minimum", "minItems", "uniqueItems", "pattern", "required",
    "properties", "additionalProperties", "items", "$ref", "allOf", "if", "then", "not", "anyOf",
}
ANNOTATIONS = {"$schema", "title", "description", "$comment", "examples", "default", "$defs", "definitions"}

HISTORY = "The review ran %s and fixed %s itself. The vet: %s"
TRACES_BOARD = ("Every statement in the spec traces to your board, your framing, your rulings, your answers, "
                "or craft recorded for your veto.")
TRACES_NO_BOARD = ("Every statement in the spec traces to your framing, your rulings, your answers, "
                   "or craft recorded for your veto.")
BOARD_SAVED = "The approved board is saved with the spec."
BOARD_NOT_SAVED = "The approved board is not saved with the spec."
NEXT = ("The advisor adds the breakdown to the same PR (or, where the project keeps specs outside the repo or "
        "gitignored, to the spec where it is kept) and vets it, then one merge word covers both.")

TYPE_NAMES = ("object", "array", "string", "boolean", "null", "integer", "number")

_MARKDOWN_CHARACTERS = re.compile(r"([\\`*_\[\]<>~|&])")


def _one_line(text):
    return re.sub(r"\s*[\r\n]+\s*", " ", text)


def _text(value):
    """A string from the data file as one line, with its Markdown characters escaped so they print as typed."""
    return _MARKDOWN_CHARACTERS.sub(r"\\\1", _one_line(value))


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def _is(kind, value):
    if kind == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}[kind] is type(value)


def _canonical(value):
    """The value as JSON text, the same for equal data whatever order an object's keys came in; true is never 1."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join("%s:%s" % (json.dumps(key), _canonical(value[key])) for key in sorted(value)) + "}"
    return json.dumps(value)


def _pointer(steps):
    return "#" + "".join("/" + str(step).replace("~", "~0").replace("/", "~1") for step in steps)


def _is_number(item):
    return isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)


def _is_names(item):
    return isinstance(item, list) and all(isinstance(name, str) for name in item)


def _is_pattern(item):
    if not isinstance(item, str):
        return False
    try:
        re.compile(item)
    except re.error:
        return False
    return True


def _is_type(item):
    return item in TYPE_NAMES if isinstance(item, str) else _is_names(item) and all(name in TYPE_NAMES for name in item)


# The form each of these keywords may take for _validate to read it; any other form is refused with the schema.
READABLE_FORMS = {
    "type": _is_type,
    "enum": lambda item: isinstance(item, list),
    "minLength": _is_number,
    "minimum": _is_number,
    "minItems": _is_number,
    "uniqueItems": lambda item: isinstance(item, bool),
    "pattern": _is_pattern,
    "required": _is_names,
}


def _unchecked_rules(schema):
    """Every place the schema uses a keyword, or a form of one, that _validate does not enforce; empty when none.

    It walks the root and every sub-schema a keyword holds. A $ref is only ever followed into $defs, which the
    walk reaches on its own, so it is not followed there. A second pass refuses a $ref chain that comes back to
    itself without descending into a property or an item, since checking a value against it would never end.
    """
    problems = []
    reached = []
    defs = schema.get("$defs") if isinstance(schema, dict) else None

    def refuse(what, steps):
        problems.append("The sheet's schema uses %s at %s, which this renderer can't check." % (what, _pointer(steps)))

    def walk(node, steps, holder):
        if not isinstance(node, dict):
            refuse('"%s" with something that is not a schema' % holder, steps)
            return
        reached.append((node, steps))
        for key, value in node.items():
            if key in ("properties", "$defs", "definitions"):
                if not isinstance(value, dict):
                    refuse('"%s" as something other than a map of schemas' % key, steps)
                else:
                    for name, sub in value.items():
                        walk(sub, steps + [key, name], key)
            elif key in ("allOf", "anyOf"):
                if not isinstance(value, list):
                    refuse('"%s" as something other than a list of schemas' % key, steps)
                else:
                    for index, sub in enumerate(value):
                        walk(sub, steps + [key, index], key)
            elif key in ("if", "then", "not"):
                walk(value, steps + [key], key)
            elif key == "items":
                if isinstance(value, list):
                    refuse('"items" as a list', steps)
                else:
                    walk(value, steps + [key], key)
            elif key == "additionalProperties":
                if not isinstance(value, bool):
                    refuse('"additionalProperties" as something other than true or false', steps)
            elif key == "$ref":
                named = re.fullmatch(r"#/\$defs/([^/~%]+)", value) if isinstance(value, str) else None
                if not named or not isinstance(defs, dict) or named.group(1) not in defs:
                    refuse('"$ref" with %s (it must name an entry under #/$defs/)' % json.dumps(value), steps)
            elif key in READABLE_FORMS:
                if not READABLE_FORMS[key](value):
                    refuse('"%s" with a value this renderer does not read' % key, steps)
            elif key not in ENFORCED and key not in ANNOTATIONS:
                refuse('the rule "%s"' % key, steps)

    def target(node):
        """The $defs entry a node's $ref names, with its place; None when it names none."""
        ref = node.get("$ref")
        named = re.fullmatch(r"#/\$defs/([^/~%]+)", ref) if isinstance(ref, str) else None
        if named and isinstance(defs, dict) and isinstance(defs.get(named.group(1)), dict):
            return defs[named.group(1)], ["$defs", named.group(1)]
        return None

    state = {}

    def same_value(node, steps):
        if state.get(id(node)) == 2:
            return
        state[id(node)] = 1

        def follow(sub, at):
            if not isinstance(sub, dict):
                return
            if state.get(id(sub)) == 1:
                refuse('"$ref" that leads back to itself without reading anything', steps)
            else:
                same_value(sub, at)

        if target(node):
            follow(*target(node))
        for key in ("allOf", "anyOf"):
            if isinstance(node.get(key), list):
                for index, sub in enumerate(node[key]):
                    follow(sub, steps + [key, index])
        for key in ("not", "if", "then"):
            follow(node.get(key), steps + [key])
        state[id(node)] = 2

    walk(schema, [], "schema")
    for node, steps in reached:
        same_value(node, steps)
    return problems


def _validate(schema, value, path, defs):
    """Problems from checking value against the schema keywords sheet.schema.json uses; empty when it fits."""
    where = path or "the data file"
    problems = _validate(defs[schema["$ref"].rsplit("/", 1)[1]], value, path, defs) if "$ref" in schema else []
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    if kinds and not any(_is(kind, value) for kind in kinds):
        return problems + ["%s must be %s." % (where, " or ".join(kinds))]
    if "const" in schema and _canonical(value) != _canonical(schema["const"]):
        return problems + ["%s must be %s." % (where, json.dumps(schema["const"]))]
    if "enum" in schema and not any(_canonical(option) == _canonical(value) for option in schema["enum"]):
        return problems + ["%s must be one of %s." % (where, ", ".join(map(str, schema["enum"])))]
    if isinstance(value, str):
        shortest = schema.get("minLength", 0)
        if len(value) < shortest:
            problems.append("%s must be at least %s characters long." % (where, shortest) if shortest > 1 else "%s must not be empty." % where)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append('%s ("%s") is not a lowercase id of letters, digits and hyphens.' % (where, value))
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value < schema.get("minimum", value):
        problems.append("%s must be %s or more." % (where, schema["minimum"]))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append("%s must not be empty." % where)
        if schema.get("uniqueItems") and len({_canonical(item) for item in value}) < len(value):
            problems.append("%s must not repeat an item." % where)
        for position, item in enumerate(value):
            problems += _validate(schema.get("items", {}), item, "%s[%d]" % (path, position), defs)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        problems += ["%s has no %s." % (where, key) for key in schema.get("required", []) if key not in value]
        for key, item in value.items():
            if key in properties:
                problems += _validate(properties[key], item, "%s.%s" % (path, key) if path else key, defs)
            elif schema.get("additionalProperties") is False:
                problems.append("%s has %s, which the sheet does not use." % (where, key))
    for part in schema.get("allOf", []):
        problems += _validate(part, value, path, defs)
    if "if" in schema and "then" in schema and not _validate(schema["if"], value, path, defs):
        problems += _validate(schema["then"], value, path, defs)
    if "not" in schema and not _validate(schema["not"], value, path, defs):
        problems.append("%s holds a part this kind of sheet must not have." % where)
    if "anyOf" in schema and all(_validate(option, value, path, defs) for option in schema["anyOf"]):
        problems.append("%s fits none of its allowed shapes." % where)
    return problems


def _duplicates(ids):
    return sorted({i for i in ids if ids.count(i) > 1})


def _check_cross_fields(sheet):
    """The rules the schema cannot express, over a sheet that already fits it.

    Their one home is the top-level "description" of theme/sheet.schema.json; the page's checkSheet
    implements the same list. test_cross_field_rules_agree_between_page_and_prose (test_sheet_prose.py)
    runs both readers over shared fixtures and is the guard against drift.
    """
    problems = []
    card_ids = [card["id"] for card in sheet["cards"]]
    problems += ['Card id "%s" is used more than once.' % i for i in _duplicates(card_ids)]
    for card in sheet["cards"]:
        option_ids = [option["id"] for option in card["options"]]
        problems += ['Card "%s" has the option id "%s" more than once.' % (card["id"], i) for i in _duplicates(option_ids)]
        picked = card.get("recommendation", {}).get("optionId")
        if picked is not None and picked not in option_ids:
            problems.append('Card "%s" recommends option "%s", which is not one of its options.' % (card["id"], picked))
    unsettled = sheet.get("remainder", {}).get("unsettled", [])
    return problems + ['remainder.unsettled names "%s", which is not a card.' % i for i in unsettled if i not in card_ids]


def check_sheet(sheet):
    """Every problem that makes the data file untrustworthy for rendering; empty when it is fine."""
    with open(SCHEMA, encoding="utf-8") as handle:
        schema = json.load(handle)
    problems = _unchecked_rules(schema)
    if problems:
        return problems
    problems = _validate(schema, sheet, "", schema.get("$defs", {}))
    return [p[0].upper() + p[1:] for p in problems] or _check_cross_fields(sheet)


def _why_line(sheet):
    remainder = sheet["remainder"]
    rounds, fixes = remainder["roundsRun"], remainder["fixesMade"]
    unsettled = len(remainder["unsettled"])
    body = ("The review ran %s and fixed %s itself. "
            "Everything else traces to your board or your rulings, so it isn't here."
            % (_plural(rounds, "round"), _plural(fixes, "thing")))
    if unsettled == 1:
        body += " 1 item here is a finding the review didn't settle."
    elif unsettled > 1:
        body += " %d items here are findings the review didn't settle." % unsettled
    return "**Why only these %d.** %s" % (len(sheet["cards"]), body)


def _letter(position):
    """a to z, then aa, ab and on, so any number of options has its own letter."""
    number, letters = position + 1, ""
    while number:
        number, rest = divmod(number - 1, 26)
        letters = chr(ord("a") + rest) + letters
    return letters


def _render_card(number, card):
    context = card["context"]
    kind = _text(card["callKind"]) + (" (warning)" if card["warning"] else "")
    lines = [
        "%d. **%s**" % (number, _text(card["question"])),
        "   - Kind of call: %s" % kind,
        "   - What's true now: %s" % _text(context["now"]),
        "   - Why it needs you: %s" % _text(context["whyOwner"]),
    ]
    if context["exactText"] is not None:
        lines.append('   - The exact text: "%s"' % _text(context["exactText"]))
    if card["images"]:
        pictures = "; ".join("%s%s (%s)" % (_text(i["alt"]), ": " + _text(i["caption"]) if i.get("caption") else "", _text(i["src"])) for i in card["images"])
        lines.append("   - Images: %s" % pictures)
    options = card["options"]
    if options:
        lines.append("   - Options:")
        for position, option in enumerate(options):
            lines.append("     - %s. %s: %s" % (_letter(position), _text(option["label"]),
                                                _text(option["consequence"])))
    recommendation = card.get("recommendation")
    if recommendation is not None:
        line = "   - Recommendation: %s %s" % (_text(recommendation["text"]), _text(recommendation["reason"]))
        if "optionId" in recommendation:
            ids = [option["id"] for option in options]
            line += " (option %s)" % _letter(ids.index(recommendation["optionId"]))
        lines.append(line)
    answers = "Aligned, Discuss"
    if options:
        answers += ", or " + ", ".join(_letter(position) for position in range(len(options)))
    lines.append("   - Answer: %s" % answers)
    return lines


def _final_head(final):
    """A final sheet's history and declined findings, each part followed by a blank line."""
    history, declined = final["history"], final["declinedFindings"]
    rounds, fixes = _plural(history["reviewRounds"], "round"), _plural(history["fixesMade"], "thing")
    lines = ["**How the spec got here.** " + HISTORY % (rounds, fixes, _text(history["vet"])), ""]
    if not declined:
        return lines + ["**Declined findings.** No findings were declined.", ""]
    lines.append("**Declined findings (%d).**" % len(declined))
    lines += ["- %s (why declined: %s)" % (_text(item["summary"]), _text(item["reason"])) for item in declined]
    return lines + [""]


def _final_tail(final):
    """A final sheet's approval box and what happens next, ending with a blank line."""
    approval = final["approval"]
    lines = ["**Approve the spec?**", "- " + (TRACES_BOARD if approval["approvedBoard"] else TRACES_NO_BOARD)]
    if approval["approvedBoard"]:
        lines.append("- " + (BOARD_SAVED if approval["boardSavedWithSpec"] else BOARD_NOT_SAVED))
    return lines + ["- Answer: Approve or Not yet, with any note.", "", "**What happens next.** " + NEXT, ""]


def render(sheet):
    """The sheet's prose as one string; the sheet must already have passed check_sheet."""
    cards = sheet["cards"]
    lines = ["**%s**: %s for you." % (_text(sheet["title"]), _plural(len(cards), "item")), ""]
    if sheet["kind"] == "remainder":
        lines += [_why_line(sheet), ""]
    if sheet["kind"] == "final":
        lines += _final_head(sheet["final"])
    for number, card in enumerate(cards, 1):
        lines += _render_card(number, card)
        lines.append("")
    if sheet["kind"] == "final":
        lines += _final_tail(sheet["final"])
    return "\n".join(line.rstrip() for line in lines[:-1]) + "\n"


def _load(path):
    """The parsed data file, or None with a problem line when it can't be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as error:
        return None, "The data file can't be read: %s." % (error.strerror or error)
    except UnicodeDecodeError:
        return None, "The data file is not valid text (UTF-8)."
    except (ValueError, RecursionError) as error:
        return None, "The data file is not valid JSON: %s." % error


def _refuse(problems):
    for problem in problems:
        sys.stderr.write(_one_line(problem) + "\n")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a review sheet's data file as numbered chat prose.")
    commands = parser.add_subparsers(dest="command", required=True)
    render_parser = commands.add_parser("render", help="print the sheet as numbered chat prose")
    render_parser.add_argument("--sheet", required=True, help="path to the sheet's data file (sheet.json)")
    args = parser.parse_args(argv)

    sheet, problem = _load(args.sheet)
    if problem:
        return _refuse([problem])
    problems = check_sheet(sheet)
    if problems:
        return _refuse(problems)
    sys.stdout.write(render(sheet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
