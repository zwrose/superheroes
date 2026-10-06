#!/usr/bin/env python3
"""Render a review sheet's data file as numbered chat prose, for a host that can't show the sheet.

Reads the same `sheet.json` the page draws and prints each card as a numbered item with its context,
options and recommendation. It checks only the fields it reads, plus the page's four cross-field rules;
full schema checking stays the page's. It uses the standard library only, so it runs under a plain python3.
It refuses a data file it can't trust: one problem per line on stderr, nothing on stdout, exit 1.
"""
import argparse
import json
import re
import sys

SCHEMA_NAME = "superheroes-sheet/1"
KINDS = ("remainder", "final", "plain")


def _is_text(value):
    return isinstance(value, str) and value != ""


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _one_line(text):
    return re.sub(r"\s*[\r\n]+\s*", " ", text)


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def _card_name(card, index):
    if isinstance(card, dict) and _is_text(card.get("id")):
        return 'Card "%s"' % card["id"]
    return "Card %d" % (index + 1)


def _check_text(problems, name, owner, key, label):
    """Require owner[key] to be a non-empty string; owner is a dict."""
    if key not in owner:
        problems.append("%s has no %s." % (name, label))
    elif not _is_text(owner[key]):
        problems.append("%s has a %s that is not a non-empty string." % (name, label))


def _check_list_of_objects(problems, name, card, key, check_item):
    if key not in card:
        problems.append("%s has no %s." % (name, key))
        return
    items = card[key]
    if not isinstance(items, list):
        problems.append("%s has %s that is not a list." % (name, key))
        return
    for position, item in enumerate(items, 1):
        label = "%s %d" % (key, position)
        if not isinstance(item, dict):
            problems.append("%s has %s that is not an object." % (name, label))
        else:
            check_item(problems, name, label, item)


def _check_image(problems, name, label, image):
    for key in ("src", "alt"):
        if key not in image:
            problems.append("%s has %s with no %s." % (name, label, key))
        elif not isinstance(image[key], str):
            problems.append("%s has %s with a %s that is not a string." % (name, label, key))


def _check_option(problems, name, label, option):
    for key in ("id", "label", "consequence"):
        _check_text(problems, name, option, key, "%s %s" % (label, key))


def _check_card(problems, card, index):
    name = _card_name(card, index)
    if not isinstance(card, dict):
        problems.append("%s is not an object." % name)
        return
    for key in ("id", "callKind", "question"):
        _check_text(problems, name, card, key, key)
    if "warning" not in card:
        problems.append("%s has no warning." % name)
    elif not isinstance(card["warning"], bool):
        problems.append("%s has a warning that is not true or false." % name)
    context = card.get("context")
    if "context" not in card:
        problems.append("%s has no context." % name)
    elif not isinstance(context, dict):
        problems.append("%s has a context that is not an object." % name)
    else:
        for key in ("now", "whyOwner"):
            _check_text(problems, name, context, key, "context.%s" % key)
        if "exactText" not in context:
            problems.append("%s has no context.exactText." % name)
        elif context["exactText"] is not None and not isinstance(context["exactText"], str):
            problems.append("%s has a context.exactText that is not a string or null." % name)
    _check_list_of_objects(problems, name, card, "images", _check_image)
    _check_list_of_objects(problems, name, card, "options", _check_option)
    if "recommendation" in card:
        _check_recommendation(problems, name, card["recommendation"])


def _check_recommendation(problems, name, recommendation):
    if not isinstance(recommendation, dict):
        problems.append("%s has a recommendation that is not an object." % name)
        return
    for key in ("text", "reason"):
        _check_text(problems, name, recommendation, key, "recommendation.%s" % key)
    if "optionId" in recommendation and not isinstance(recommendation["optionId"], str):
        problems.append("%s has a recommendation.optionId that is not a string." % name)


def _check_remainder(problems, sheet):
    remainder = sheet.get("remainder")
    if "remainder" not in sheet:
        problems.append("The sheet has no remainder block.")
        return
    if not isinstance(remainder, dict):
        problems.append("The sheet has a remainder block that is not an object.")
        return
    for key in ("roundsRun", "fixesMade"):
        if key not in remainder:
            problems.append("The remainder block has no %s." % key)
        elif not _is_count(remainder[key]):
            problems.append("The remainder block has a %s that is not a whole number of 0 or more." % key)
    unsettled = remainder.get("unsettled")
    if "unsettled" not in remainder:
        problems.append("The remainder block has no unsettled list.")
    elif not isinstance(unsettled, list) or not all(isinstance(item, str) for item in unsettled):
        problems.append("The remainder block has an unsettled list that is not a list of strings.")


def _check_cross_fields(problems, sheet):
    """The page's four cross-field rules, over the cards that are well-formed enough to name."""
    cards = [card for card in sheet["cards"] if isinstance(card, dict)]
    seen = set()
    for card in cards:
        card_id = card.get("id")
        if not _is_text(card_id):
            continue
        if card_id in seen:
            problems.append('Card id "%s" is used more than once.' % card_id)
        seen.add(card_id)
    for index, card in enumerate(sheet["cards"]):
        if not isinstance(card, dict):
            continue
        name = _card_name(card, index)
        options = card.get("options")
        option_ids = []
        if isinstance(options, list):
            option_ids = [o["id"] for o in options if isinstance(o, dict) and _is_text(o.get("id"))]
        for option_id in sorted({i for i in option_ids if option_ids.count(i) > 1}):
            problems.append('%s has the option id "%s" more than once.' % (name, option_id))
        recommendation = card.get("recommendation")
        if isinstance(recommendation, dict) and isinstance(recommendation.get("optionId"), str):
            if recommendation["optionId"] not in option_ids:
                problems.append('%s recommends option "%s", which is not one of its options.'
                                % (name, recommendation["optionId"]))
    remainder = sheet.get("remainder")
    if sheet["kind"] == "remainder" and isinstance(remainder, dict) and isinstance(remainder.get("unsettled"), list):
        for card_id in remainder["unsettled"]:
            if isinstance(card_id, str) and card_id not in seen:
                problems.append('remainder.unsettled names "%s", which is not a card.' % card_id)


def check_sheet(sheet):
    """Every problem that makes the data file untrustworthy for rendering; empty when it is fine."""
    if not isinstance(sheet, dict):
        return ["The data file's top level is not an object."]
    problems = []
    if sheet.get("schema") != SCHEMA_NAME:
        problems.append('The data file\'s schema is not "%s".' % SCHEMA_NAME)
    if sheet.get("kind") not in KINDS:
        problems.append("The data file's kind is not one of remainder, final or plain.")
    if not _is_text(sheet.get("title")):
        problems.append("The data file has no title that is a non-empty string.")
    cards = sheet.get("cards")
    if not isinstance(cards, list) or not cards:
        problems.append("The data file's cards is not a non-empty list.")
        return problems
    for index, card in enumerate(cards):
        _check_card(problems, card, index)
    if sheet.get("kind") == "remainder":
        _check_remainder(problems, sheet)
    if sheet.get("kind") in KINDS:
        _check_cross_fields(problems, sheet)
    return problems


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
