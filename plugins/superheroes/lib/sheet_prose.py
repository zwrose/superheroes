#!/usr/bin/env python3
"""Render a review sheet's data file as numbered chat prose, for a host that can't show the sheet.

Reads the same `sheet.json` the page draws and prints each card as a numbered item with its context,
options and recommendation. It checks the file against sheet.schema.json, read at run time by a small reader of
the keywords that schema uses, plus the schema's four cross-field rules. It uses the standard library only, so it
runs under a plain python3.
It refuses a data file it can't trust: one problem per line on stderr, nothing on stdout, exit 1.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "theme" / "sheet.schema.json"


def _one_line(text):
    return re.sub(r"\s*[\r\n]+\s*", " ", text)


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def _is(kind, value):
    if kind == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())
    return {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}[kind] is type(value)


def _validate(schema, value, path, defs):
    """Problems from checking value against the schema keywords sheet.schema.json uses; empty when it fits."""
    where = path or "the data file"
    if "$ref" in schema:
        return _validate(defs[schema["$ref"].rsplit("/", 1)[1]], value, path, defs)
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    if kinds and not any(_is(kind, value) for kind in kinds):
        return ["%s must be %s." % (where, " or ".join(kinds))]
    if "const" in schema and value != schema["const"]:
        return ['%s must be "%s".' % (where, schema["const"])]
    if "enum" in schema and value not in schema["enum"]:
        return ["%s must be one of %s." % (where, ", ".join(map(str, schema["enum"])))]
    problems = []
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append("%s must not be empty." % where)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append('%s ("%s") is not a lowercase id of letters, digits and hyphens.' % (where, value))
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value < schema.get("minimum", value):
        problems.append("%s must be %s or more." % (where, schema["minimum"]))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append("%s must not be empty." % where)
        if schema.get("uniqueItems") and len({json.dumps(item) for item in value}) < len(value):
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
        if not part.get("if") or not _validate(part["if"], value, path, defs):
            problems += _validate(part.get("then", part), value, path, defs)
    if "not" in schema and not _validate(schema["not"], value, path, defs):
        problems.append("%s holds a part this kind of sheet must not have." % where)
    if "anyOf" in schema and all(_validate(option, value, path, defs) for option in schema["anyOf"]):
        problems.append("%s fits none of its allowed shapes." % where)
    return problems


def _duplicates(ids):
    return sorted({i for i in ids if ids.count(i) > 1})


def _check_cross_fields(sheet):
    """The rules the schema cannot express, over a sheet that already fits it."""
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
    problems = _validate(schema, sheet, "", schema["$defs"])
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
    return chr(ord("a") + position)


def _render_card(number, card):
    context = card["context"]
    kind = card["callKind"] + (" (warning)" if card["warning"] else "")
    lines = [
        "%d. **%s**" % (number, _one_line(card["question"])),
        "   - Kind of call: %s" % _one_line(kind),
        "   - What's true now: %s" % _one_line(context["now"]),
        "   - Why it needs you: %s" % _one_line(context["whyOwner"]),
    ]
    if context["exactText"] is not None:
        lines.append('   - The exact text: "%s"' % _one_line(context["exactText"]))
    if card["images"]:
        pictures = "; ".join("%s (%s)" % (_one_line(i["alt"]), _one_line(i["src"])) for i in card["images"])
        lines.append("   - Images: %s" % pictures)
    options = card["options"]
    if options:
        lines.append("   - Options:")
        for position, option in enumerate(options):
            lines.append("     - %s. %s: %s" % (_letter(position), _one_line(option["label"]),
                                                _one_line(option["consequence"])))
    recommendation = card.get("recommendation")
    if recommendation is not None:
        line = "   - Recommendation: %s %s" % (_one_line(recommendation["text"]), _one_line(recommendation["reason"]))
        if "optionId" in recommendation:
            ids = [option["id"] for option in options]
            line += " (option %s)" % _letter(ids.index(recommendation["optionId"]))
        lines.append(line)
    answers = "Aligned, Discuss"
    if options:
        answers += ", or " + ", ".join(_letter(position) for position in range(len(options)))
    lines.append("   - Answer: %s" % answers)
    return lines


def render(sheet):
    """The sheet's prose as one string; the sheet must already have passed check_sheet."""
    cards = sheet["cards"]
    lines = ["**%s**: %s for you." % (_one_line(sheet["title"]), _plural(len(cards), "item")), ""]
    if sheet["kind"] == "remainder":
        lines += [_why_line(sheet), ""]
    for number, card in enumerate(cards, 1):
        lines += _render_card(number, card)
        lines.append("")
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
