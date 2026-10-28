#!/usr/bin/env python3
"""Builds a PR sheet's data file from the PR's review record and the advisor's input.

CLI:
  pr_sheet.py build --record FILE [--record FILE ...] --pr-body N=FILE [--pr-body N=FILE ...] --input FILE --out FILE
  pr_sheet.py index --input FILE [--answers FILE] --out FILE

On success it writes the data file to --out and each walk picture it could copy to pictures/ beside it, prints
{"ok": true, "out": ..., "cards": N, "pictures": [the sheet's picture paths]} and exits 0.
On a refusal it writes nothing, prints {"ok": false, "problems": [...]} (one line each) and exits 1; an
unreadable or non-JSON file, the words file included, is a refusal problem that names the file. `index` prints
{"ok": true, "out": ..., "cards": N, "pictures": [...], "rows": N} on success and refuses the same way; if
writing fails it removes the pictures that run created. --record and --pr-body are for `build` only, --answers for `index` only.

--pr-body N=FILE names the body of covered PR N (gh api repos/<owner>/<repo>/pulls/N --jq .body, read as UTF-8), and `build`
needs one for every covered PR (number on a pr sheet, every prs[].number on a stack), no more and no fewer; a missing, extra or
repeated one, a value that is not <PR number>=<file>, and a file that cannot be read are refusal problems. No acceptance a body
lists under its "What we're accepting" heading (accepting_listed) becomes a card on its own (the reader stops at the first
build-record marker line at column 0 after that heading; a marker above the heading, indented, fenced or inside a comment is
plain text, so a deviation listed only in the build record, a harmless one, is never an acceptance and needs no card, while a
costly one, listed under What we're accepting above the marker, must still be accounted for): the advisor decides which are
Accept items, which fold into one item and which a leftover card or a Canon ruling already carries, and the input's "accounting"
says so for every one. Each acceptance has a bullet id, "<PR number>:<10 hex>" (listed_bullets), made from the PR, the
acceptance's text and its place among identical ones, so a bullet added above the others leaves every other id as it was and
the accounting already written stays right. The build refuses a sheet that leaves a listed acceptance out, counts one twice, or
points at something that is not on the sheet, and each refusal names the bullet by id and the start of its text. A first build
with no accounting therefore lists every bullet's id. A zero-card sheet says one of three things about the bodies: prSheet.nothingListed
is true only when every covered body was read and lists none, and the page, the prose and the index row say "nothing to accept" only
then; prSheet.canonAccounted lists the Canon entry ids (sorted, distinct) when every covered body was read, they list at least one
acceptance and every listed acceptance is accounted to a Canon ruling, and those surfaces say it was checked and all covered by
Canon rulings; with neither field (a sheet built through the API with no bodies, or an earlier one) they say the sheet was not
checked against the bodies. The two fields never come together. The build also reads the body's degradations list
(degradations_listed) and refuses a [costly] or unlabelled deviation whose text (after its label) appears in no What we're
accepting line, naming the bullet; a [harmless] one never needs a line.

A record file holds what `review_record.py read --pr N` prints, or the bare record. Every fact is copied
from the records or the advisor's input, and each finding lands where its outcome names: fixed in "caught",
craft in "craft", ruling in "alreadyDecided", shown-wrong in "history", left-for-owner as a card (one with a craft
determination lands in "decidedForYou" instead, and is no card). The words
come from the "pr" block of theme/sheet-words.json.

The advisor's input is one JSON object; any key not listed is refused.
  schema         "pr-sheet-input/1".
  kind           "pr" for one PR, or "stack" for a stack that merges whole.
  number         The PR's number, or the stack's number. An integer, 1 or more.
  title, summary Non-empty strings: the sheet's title, and what changed in one line.
  previousCommit Optional. Null, or a commit id (7 to 40 lowercase hex) when this sheet replaces an earlier one.
  carriedForward Optional. Present when the move to the new head is not material, so the earlier sheet's answers and Merge
                 carry forward: {fromSheet, heads, date, moved, whyNotMaterial}, all required. fromSheet is the path (absolute,
                 or relative to the input's folder) of the earlier published sheet.json of this same PR or stack; heads maps
                 each covered PR number (a decimal string: number on a pr, every prs[].number on a stack, no more and no
                 fewer) to that PR's new head commit; date is YYYY-MM-DD; moved and whyNotMaterial are non-empty strings. The
                 sheet then takes previousCommit and its commits from the earlier sheet and heads, and records the earlier
                 sheet's digest (and the digests it carried) in prSheet.carriedForward. previousCommit, when also given,
                 must equal the earlier sheet's commit. A sheet republished with previousCommit alone starts unsigned.
  prs            Required on a stack, refused on a pr: at least 2 {number, title}, bottom PR first.
  leftovers      An object with an entry for every left-for-owner finding that has no craft determination (one with neither is
                 refused, and one with both). A key names a
                 finding by its findingKey, or by its id when no other left-for-owner finding shares it ("<pr number>:<key>"
                 on a stack). A value is {why, context, options, ifLeft?, recommendation?}: why (why the call is the owner's)
                 and context (what happened) are non-empty strings, and ifLeft, when given, is a non-empty string shown
                 instead of the reviewer's consequence. The card shows Why it's yours, What happened and If left, in that
                 order. options is "none" (nothing is left to decide: the page's Accept and Discuss), a list of options, or
                 an object giving each of keep-it, fix-in-a-follow-up and fix-before-merge, and no other key, a non-empty
                 string: this finding's consequence for that option (the words' three options carry them). The bare string
                 "leftover" is refused.
  craftDeterminations
                 Optional. An object that re-grades left-for-owner findings as craft: a key names a finding as a leftovers key
                 does, and a value is {ground, reason}, both non-empty strings (the owner-vs-craft line's ground, and one line
                 of why). Each lands in prSheet.decidedForYou with an id from its PR and finding alone, and is no card. A key
                 naming no finding or an ambiguous one is refused. A carried sheet keeps the earlier sheet's decidedForYou
                 entries as they stand (an entry whose finding the input does not name is inherited), and refuses a changed or
                 added determination, or a leftovers entry over an earlier one.
  items          Optional list. Each is {id, kind, title, ifLeft, options, recommendation?} with options
                 "none" or a list; id matches ^[a-z0-9][a-z0-9-]*$ and is unique among the items. ifLeft is a non-empty
                 string, shown as one paragraph, or a list of at least 1 non-empty strings, shown as a bulleted list, one
                 bullet each (the "What you're accepting" fold's routine notes).
  collectorItems Optional list. A decision from the owner's list that concerns this one PR, answered on this PR's sheet.
                 Each is {number, title, why, context, options, ifLeft, recommendation}, all required: number the collector
                 item's number (an integer, 1 or more, unique among the entries); title, why, context and ifLeft non-empty
                 strings (the question, why it is the owner's, what happened, and what leaving it costs); options a list of
                 at least 1 option, whose ids are a, b, c, ... in that order ("none" and an empty list are refused);
                 recommendation {text, reason, optionId} with optionId required and naming one of the options. Each lands as
                 one option card after the items, showing its collector number, Why it's yours, What happened, If left, the
                 lettered options and the recommendation naming its letter.
  closesSpec     Optional. Null, or {"spec": ..., "receipt": ...}.
  accounting     Optional, and read only when --pr-body gives the bodies. An object of bullet id (listed_bullets) to where that
                 acceptance is accounted for, with exactly one of these: {"item": "<id>"} (an entry of items, its own Accept
                 item); {"fold": "<id>", "line": n} (line n, from 1, of that item's ifLeft list; n an integer); {"leftover":
                 "<key>"} (the leftover card it restates: a key of leftovers that names exactly one left-for-owner finding);
                 {"canon": "<entry id>"} (a Canon entry id, YYYY-MM-DD-xxxxxxxx-N, that the summary cites; the acceptance then
                 gets no item). Every listed acceptance needs an entry and each key must name a listed one. A fold line that no
                 acceptance names is allowed.
  walk           Optional object {open, note?, picturesFrom, stops}: open is {label, url?, detail?} with url
                 http(s); stops is at least 1 of {id, title, pr, group, kind, steps?, expect, optional?, notWalked?,
                 pictures?}: id as above and unique, pr equal to number on a pr or one of prs on a stack, kind
                 "try" (steps, at least 1) or "look" (no steps), optional a boolean, pictures a list of
                 {path, alt, caption?}. A path is a file (png, jpg, jpeg, gif or webp), absolute or relative to the
                 input's folder; a picture whose path is a link or cannot be read as one is shown as missing.
An option is {id, label, consequence, sendsBack}, all required, sendsBack a boolean, ids unique within the
item. A recommendation is {text, reason, optionId?}; optionId must name one of the item's options and is
refused where the options are "none".

A card that has no options and whose shown text sends the owner to a list item by number is refused: the decision belongs
on this sheet as a collectorItems card, or the card needs its own options. This is a best-effort pattern scan over the shown
text of each option-less card (its question, its context blocks and its recommendation), so it catches the wordings it
knows and no others. It recognizes three shapes, each ending in a number: "decision item 12" (also "collector item" and
"list item"), "item 12 on your list" (also in or from, the list or the collector), and "collector" followed by a hash and
the number, or by "number" or "entry" and the number. A card that carries its own options is never scanned.

`index` builds the index sheet: the questions that block work, then a row for each PR with a sheet. Its input is one
JSON object; any key not listed is refused.
  schema         "index-input/1".
  questions      A list, which may be empty, of {id, question, context, options, recommendation?, pictures}: id as
                 above and unique; question a non-empty string; context a list of sections in the shape of a
                 card's context; options at least 1 of {id, label, consequence}, ids unique, with no sendsBack;
                 recommendation as above; pictures a list of {path, alt, caption?}, copied beside the data file
                 like a walk's. A question's picture whose path is a link, or cannot be read as a picture file,
                 is refused, never shown as missing.
  mergeOrder     A list of PR numbers with no repeat, each one a number in prs: the order the PRs merge in.
  prs            A list, which may be empty, of {number, link, sheet, store}: number unique; link an https link
                 that opens the PR's sheet; sheet the path to that PR's published sheet.json; store the path to
                 that sheet's store dump. A path is absolute or relative to the input's folder. The sheet must be
                 a pr or stack sheet whose prSheet.number is the entry's number.
A store dump is one JSON object, {"answers": {"<card id>": doc}, "verdict": {"<digest>": doc}, "walk": {"<stop
key>": doc}}, where each doc is a stored document as the page writes it (the shapes are $defs/answer,
$defs/verdict and $defs/walkAnswer in theme/sheet.schema.json). A key that is missing means an empty
collection; any other top-level key is refused. The advisor assembles it from the sheet's store. --answers
names a file in the same shape that holds the answers to the index's own questions; only "answers" is read.
A question that --answers answers (an option the question offers, or Something else) is left out of the index.

Each row's counts and state come from pr_state() below, its title and kind from the PR's own sheet, and its
place in the merge order from mergeOrder; its caption is composed here once, and the page and the chat prose show it as it is. Rows are listed by place in the merge order, then the rest in the
order of prs.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
import pathlib
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import canon  # noqa: E402
import md_fence  # noqa: E402
import review_findings_schema as rfs  # noqa: E402
import review_record  # noqa: E402
import sheet_prose  # noqa: E402

WORDS_PATH = os.path.join(_LIB_DIR, os.pardir, "theme", "sheet-words.json")
_FIXED, _SHOWN_WRONG, _CRAFT, _, _RULING = rfs.OUTCOMES
_LEFT = rfs.LEFT_FOR_OWNER
SCHEMA_PATH = os.path.join(_LIB_DIR, os.pardir, "theme", "sheet.schema.json")
with open(SCHEMA_PATH, encoding="utf-8") as _fh:
    _SCHEMA = json.load(_fh)
# The identifier and commit patterns are read from the sheet schema, their one home.
_ID = re.compile(_SCHEMA["$defs"]["id"]["pattern"])
_COMMIT = re.compile(_SCHEMA["$defs"]["commit"]["pattern"])
_CARRY = _SCHEMA["$defs"]["prSheet"]["properties"]["carriedForward"]
_DATE = re.compile(_CARRY["properties"]["date"]["pattern"])
_URL = re.compile(_SCHEMA["$defs"]["walk"]["properties"]["open"]["properties"]["url"]["pattern"])
_PICTURE = re.compile(_SCHEMA["$defs"]["walkPicture"]["anyOf"][0]["properties"]["src"]["pattern"])
# The picture filename's digest length is read from that same pattern, so the schema alone sets it.
PICTURE_DIGEST = int(re.search(r"\{(\d+)\}", _PICTURE.pattern).group(1))
# The walk's keys, stop kinds and per-kind step rules come from the same schema; only the input's own
# `path` picture key has no schema twin (the sheet carries src or missing instead).
_WALK, _STOP = _SCHEMA["$defs"]["walk"], _SCHEMA["$defs"]["walkStop"]
STOP_DIGEST = int(re.search(r"\{(\d+)\}", _STOP["properties"]["key"]["pattern"]).group(1))  # the stop key's digest width, from its schema pattern
_KINDS = tuple(_STOP["properties"]["kind"]["enum"])
_STEPS = {a["if"]["properties"]["kind"]["const"]: a["then"]["properties"]["steps"] for a in _STOP["allOf"]}
# The stored documents (answer, walkAnswer, verdict) pr_state reads are checked against their schema definitions by sheet_prose.fits_definition.
_DEFS = _SCHEMA["$defs"]
_LINK = re.compile(_DEFS["indexRow"]["properties"]["link"]["pattern"])
_STORE_KEYS = ("answers", "verdict", "walk")
# Axis: an option-less card that sends the owner to a list item by number, in any of three wordings.
_POINTER = re.compile(r"\b(?:decision|collector|list)\s+item\s+#?\d+"
                      r"|\bitem\s+#?\d+\s+(?:on|in|from)\s+(?:your|the)\s+(?:list|collector)\b"
                      r"|\bcollector\s+(?:#\d+|(?:number|entry)\s+#?\d+)", re.IGNORECASE)


def _shape(d, inferred=()):
    """The (required, optional) key tuples of a schema object; inferred keys are optional in the input."""
    req = tuple(k for k in d["required"] if k not in inferred)
    return req, tuple(k for k in d["properties"] if k not in req)


_LANES = review_record.LANES
_RAN = review_record.RAN_STATES
_RECORD_TYPES = (("lane", dict), ("finalCommit", dict), ("ci", dict), ("reviewers", list), ("findings", list),
                 ("missingReviews", list), ("rounds", dict))


class Refusal(Exception):
    def __init__(self, problems):
        super().__init__(problems)
        self.problems = problems


def _text(v):
    return isinstance(v, str) and bool(v.strip())


def _num(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def _commit(v):
    return isinstance(v, str) and _COMMIT.search(v) is not None


_ACCEPTING = re.compile(r"^ {0,3}(#{1,6})[ \t]+What we(?:'|’)re accepting[ \t]*#*[ \t]*$", re.IGNORECASE)
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]")
# A backtick fence's info string holds no backtick, so ```x``` opens none; group 1 is a list marker the fence may open behind
# (a fence in a list item), group 2 the fence itself.
_FENCE = re.compile(r"^ {0,3}((?:[-*+]|\d{1,9}[.)])[ \t]+)?(`{3,}(?=[^`]*$)|~{3,})")
_ITEM = re.compile(r"^( {0,3})([-*+]|\d{1,9}[.)])([ \t]+)(.*)")
_NO_ACCEPTANCE = ("none", "n/a", "na", "nothing")


_WHOLE_COMMENT = re.compile(r"^\s*<!--(?:(?!-->).)*-->\s*$")  # one comment, through its first `-->`, and nothing after it
_BUILD_RECORD_MARKER = "<!-- superheroes:build-record -->"  # the line that opens the body's build record, below the owner half


def _outside_comments(lines):
    """(line, fenced) for each line of a body that is not inside an HTML comment, tracking code fences as it goes.

    Only two shapes are dropped: a line that is wholly a comment, and a block that opens on a line starting with `<!--`
    and holding no `-->`, through the first later line holding `-->`, and only when such a line exists in the same section
    (before a heading at or above the What we're accepting level); otherwise the opener and what follows are plain text.
    A closing line with text after its `-->` is kept whole. Any other `<!--` is plain text and stays. Comments are read
    outside fences only. The first build-record marker line at column 0 after the What we're accepting heading ends the body
    (a marker above the heading, indented, fenced or inside a comment is plain text): nothing after it is kept."""
    kept, fence, column, inside, level, item_column = [], None, 0, False, None, 0
    for n, line in enumerate(lines):
        if fence is not None:
            spaced = line.expandtabs(4)  # a tab reaches the next multiple of four columns
            lead = len(spaced) - len(spaced.lstrip(" "))
            if column and line.strip() and lead < column:
                fence = None  # a fence opened in a list item ends where the item does: this line is outside it
            else:
                kept.append((line, True))
                # the closing fence sits 0-3 columns past the container's content column (column 0 outside a list)
                closing = lead - column <= 3 and re.match(" *" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$", spaced)
                fence = None if closing else fence
                continue
        if inside:
            inside = "-->" not in line
            if not inside and line.split("-->", 1)[1].strip():
                kept.append((line, False))
            continue
        # bite-axis: build-record boundary — an unindented marker line after the accepting heading ends the body.
        if level is not None and line.rstrip() == _BUILD_RECORD_MARKER:
            break
        spaced = line.expandtabs(4)
        if line.strip() and len(spaced) - len(spaced.lstrip(" ")) < item_column and not _ITEM.match(line):
            item_column = 0  # a non-blank line left of the item's content ends the item, comments included
        if _WHOLE_COMMENT.match(line):
            continue
        if line.lstrip(" ").startswith("<!--") and "-->" not in line and _closes(lines[n + 1:], level):
            inside = True
            continue
        opening = _FENCE.match(line)
        fence = opening.group(2) if opening else None
        spaced = line.expandtabs(4)
        lead = len(spaced) - len(spaced.lstrip(" "))
        if opening and opening.group(1):
            column = len(line[:opening.start(2)].expandtabs(4))
        else:
            # a fence on a continuation line sits in the enclosing list item's content: measure its closer from that column
            column = item_column if opening and lead >= item_column else 0
        if not opening and line.strip():
            item = _ITEM.match(line)
            if item:
                gap = len(item.group(3))
                item_column = len(item.group(1)) + len(item.group(2)) + (gap if gap <= 4 else 1)
            elif lead < item_column:
                item_column = 0  # a non-blank line left of the item's content ends the item
        accepting = None if opening else _ACCEPTING.match(line)
        level = len(accepting.group(1)) if accepting else level
        kept.append((line, opening is not None))
    return kept


def _closes(rest, level):
    """Whether a `-->` comes in the lines after an opener before its section ends (no bound before the heading is seen)."""
    for line in rest:
        if "-->" in line:
            return True
        heading = _HEADING.match(line)
        if level is not None and heading and len(heading.group(1)) <= level:
            return False
    return False


def accepting_listed(body):
    """The acceptances a PR body lists under its What we're accepting heading, in order; [] for no such heading, no
    acceptance, or anything that is not a string. An item is a top-level list item with its nested lines, or a paragraph;
    one that reads None, N/A, NA or Nothing is no acceptance. A line that is none of these is an acceptance, never dropped.
    The reader stops at the first build-record marker line at column 0 after the What we're accepting heading (a marker above
    the heading, indented, fenced or inside a comment is plain text): a deviation listed only in the build record (a harmless
    one) is never an acceptance and needs no card, while a costly one, listed under What we're accepting, must still be accounted for."""
    if not isinstance(body, str):
        return []
    lines = _outside_comments(body.splitlines())
    start = next((n for n, (line, fenced) in enumerate(lines) if not fenced and _ACCEPTING.match(line)), None)
    if start is None:
        return []
    level = len(_ACCEPTING.match(lines[start][0]).group(1))
    section = []
    for line, fenced in lines[start + 1:]:
        heading = None if fenced else _HEADING.match(line)
        if heading and len(heading.group(1)) <= level:
            break
        section.append(line)
    items, open_item, is_list, blank, column = [], None, False, False, 0
    for line in section:
        if not line.strip():
            blank = True
            continue
        started = _ITEM.match(line)
        if started and is_list and len(started.group(1)) >= column:
            started = None  # indented to the open item's content column: it nests in that item
        indented = line.startswith(("  ", "\t"))
        if started:
            gap = len(started.group(3))
            # CommonMark: the content column is indent + marker + the spaces after it (one when five or more).
            column = len(started.group(1)) + len(started.group(2)) + (gap if gap <= 4 else 1)
            open_item, is_list = [started.group(4)], True
            items.append(open_item)
        elif open_item is not None and not (blank and (not is_list or not indented)):
            open_item.append(line)
        else:
            open_item, is_list = [line], False
            items.append(open_item)
        blank = False
    texts = (" ".join(part for part in (line.strip() for line in item) if part) for item in items)
    return [t for t in texts if t and (t[:-1] if t.endswith(".") else t).strip().lower() not in _NO_ACCEPTANCE]


_DEGRADATIONS_MARKER = "<!-- superheroes:degradations -->"  # the line that opens the body's degradations list, in the build record
_DEGRADATIONS_HEADING = "### Disclosed degradations"
_TOP_ITEM = re.compile(r"^( {0,3})([-*+])([ \t]+)(.*)")
_LABEL = re.compile(r"\[(costly|harmless)\][ \t]*", re.IGNORECASE)


def degradations_listed(body):
    """(label, text) for each degradation a PR body lists after its degradations marker line, in order; [] for a body that
    is not a string, has no marker, or lists only the word None (as the one item or the one paragraph, any case, with or
    without a period). An item is a top-level list item with its continuation lines joined by one space, or a paragraph;
    a list item indented to the open item's content column is part of that item; a nested item that opens with a label
    starts its own degradation; a line inside a code fence never ends the list or starts an item (it joins the open item,
    or is skipped when none is open).
    The list ends at the next heading, a line starting `</details>` or another `<!-- superheroes:` marker; the `### Disclosed
    degradations` heading itself is skipped. label is "costly" or "harmless" when the text starts with that label
    (case-insensitive; the label and the spaces after it are dropped from text), else None."""
    if not isinstance(body, str):
        return []
    lines = body.splitlines()
    inert = md_fence.scan(lines).inert  # a marker inside a code fence is an example, not the section
    start = next((n for n, line in enumerate(lines) if not inert[n] and line.rstrip() == _DEGRADATIONS_MARKER), None)
    if start is None:
        return []
    entries, open_entry, blank, column = [], None, False, 0
    for n in range(start + 1, len(lines)):
        line = lines[n]
        if inert[n]:
            if open_entry is not None:
                open_entry.append(line)
                blank = False
            continue
        stripped = line.strip()
        if not stripped:
            blank = True
            continue
        if stripped == _DEGRADATIONS_HEADING:
            continue
        if _HEADING.match(line) or stripped.startswith(("</details>", "<!-- superheroes:")):
            break
        item = _TOP_ITEM.match(line)
        if item and open_entry is not None and len(item.group(1)) >= column and not _LABEL.match(item.group(4)):
            item = None  # indented to the open item's content column: it nests in that item
        if item:
            gap = len(item.group(3))
            column = len(item.group(1)) + len(item.group(2)) + (gap if gap <= 4 else 1)
            open_entry = [item.group(4)]
            entries.append(open_entry)
        elif open_entry is not None and not (blank and not line.startswith(("  ", "\t"))):
            open_entry.append(line)  # a continuation line (lazy, or indented after a blank line)
        else:
            open_entry, column = [line], 4  # a paragraph has no content column: a top-level bullet after it starts a new item
            entries.append(open_entry)
        blank = False
    texts = [t for t in (" ".join(part for part in (line.strip() for line in entry) if part) for entry in entries) if t]
    if len(texts) == 1 and (texts[0][:-1] if texts[0].endswith(".") else texts[0]).strip().lower() == "none":
        return []
    listed = []
    for text in texts:
        label = _LABEL.match(text)
        listed.append((label.group(1).lower(), text[label.end():]) if label else (None, text))
    return listed


def _line_key(text):
    """A line of text as the degradation check compares it: emphasis marks dropped, whitespace collapsed, case folded, one
    trailing full stop removed."""
    key = re.sub(r"\s+", " ", text.replace("*", "").replace("_", "")).strip().casefold()
    return key[:-1] if key.endswith(".") else key


def costly_unlisted(body):
    """The (label, text) degradations of a PR body (degradations_listed) that are labelled costly or carry no label and whose
    text appears in no line under What we're accepting (accepting_listed), compared by _line_key. A harmless one is never
    returned; an empty text after the label is never matched."""
    accepted = [_line_key(line) for line in accepting_listed(body)]
    missing = []
    for label, text in degradations_listed(body):
        key = _line_key(text)
        # bite-axis: a costly or unlabelled deviation must have a line under What we're accepting, and an empty text is never carried
        if label != "harmless" and (not key or not any(key in line for line in accepted)):
            missing.append((label, text))
    return missing


def listed_bullets(pr, body):
    """(bullet id, text) for each acceptance a PR body lists, in body order.

    The id is made from the PR, the text and its place among bullets with identical text, so a bullet inserted above others leaves every other id unchanged."""
    seen, bullets = {}, []
    for text in accepting_listed(body):
        ordinal = seen[text] = seen.get(text, -1) + 1
        digest = hashlib.sha256(json.dumps([pr, ordinal, text], ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        bullets.append((f"{pr}:{digest[:10]}", text))
    return bullets


def _fill(text, /, **slots):
    return re.sub(r"\{(\w+)\}", lambda m: str(slots.get(m.group(1), m.group(0))), text)


def _short(sha):
    """A commit as its first 7 characters, empty when it names none."""
    return sha[:7] if isinstance(sha, str) else ""


def _title(finding):
    return finding.get("title") or finding.get("summary") or finding.get("id")


def card_id(prefix, pr, identity, card):
    return prefix + hashlib.sha256(json.dumps([pr, identity, card], sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _keys(where, obj, required, optional, problems):
    if not isinstance(obj, dict):
        problems.append(f"{where} must be an object")
        return False
    bad = [f"{where} is missing {k}" for k in required if k not in obj]
    bad += [f"{where} has an unknown key {k}" for k in obj if k not in required and k not in optional]
    problems.extend(bad)
    return not bad


def _go_ahead(g):
    """The words a go-ahead is shown as, or None when it is not a go-ahead."""
    if not isinstance(g, dict):
        return None
    if g.get("kind") == "standing-ruling" and _text(g.get("canonId")):
        return g["canonId"]
    if g.get("kind") == "owner-words" and _text(g.get("words")) and _text(g.get("where")):
        return f'"{g["words"]}" ({g["where"]})'
    return None


def _record(raw, n, problems):
    where = f"record {n}"
    if not isinstance(raw, dict):
        problems.append(f"{where} is not a JSON object")
        return None
    if "ok" in raw and raw["ok"] is not True:
        problems.append(f"{where} is a failed read (ok is not true)")
        return None
    rec = {k: v for k, v in raw.items() if k not in ("ok", "url", "earlierRecords")}
    if rec.get("schema") != review_record.RECORD_SCHEMA:
        problems.append(f"{where} is not a review record (its schema is not {review_record.RECORD_SCHEMA})")
        return None
    bad = [k for k, t in _RECORD_TYPES if not isinstance(rec.get(k), t)] + ([] if _num(rec.get("pr")) else ["pr"])
    if bad:
        problems.append(f"{where} has a missing or malformed field: {', '.join(bad)}")
        return None
    where = f"record for PR #{rec['pr']}"
    ci, lane, rounds = rec["ci"], rec["lane"], rec["rounds"]
    if not _commit(rec["finalCommit"].get("sha")):
        problems.append(f"{where}: finalCommit.sha is null or not a commit id")
    if not (_text(ci.get("state")) and (ci.get("sha") is None or _commit(ci["sha"]))
            and lane.get("value") in (*_LANES, None) and isinstance(lane.get("reason"), (str, type(None)))
            and isinstance(rounds.get("count"), int) and rounds["count"] >= 0 and isinstance(rounds.get("stoppedAtCap"), bool)
            and all(isinstance(v, dict) and v.get("ran") in _RAN and _text(v.get("name"))
                    and ("family" in v and (v["family"] is None or _text(v["family"]))) for v in rec["reviewers"])
            and all(isinstance(m, dict) and _text(m.get("name")) and (m.get("goAhead") is None or _go_ahead(m["goAhead"]))
                    for m in rec["missingReviews"])):
        problems.append(f"{where}: its ci, lane, rounds, reviewers or missing reviews are malformed")
    # An earlier record may carry this key: it is validated so the record still reads, and it is never shown.
    if "seatsNotRun" in rec and not (isinstance(rec["seatsNotRun"], list) and all(
            isinstance(s, dict) and _text(s.get("name")) and _text(s.get("why")) for s in rec["seatsNotRun"])):
        problems.append(f"{where}: its seats not run are malformed")
    for f in rec["findings"]:
        out, name = (f.get("outcome"), _title(f)) if isinstance(f, dict) else (None, None)
        if not _text(name):
            problems.append(f"{where}: a finding has no title, summary or id")
        elif out not in rfs.OUTCOMES:
            problems.append(f"{where}: finding {name!r} has outcome {out!r}, not one of {', '.join(rfs.OUTCOMES)}")
        elif out == _LEFT and not _text(f.get("consequence")):
            problems.append(f"{where}: left-for-owner finding {name!r} has no consequence")
        elif out in (_CRAFT, _RULING, _SHOWN_WRONG) and not _text(f.get("reason")):
            problems.append(f"{where}: {out} finding {name!r} has no reason")
        if _text(name) and out == _LEFT and not (f.get("findingKey") or f.get("id")):
            problems.append(f"{where}: left-for-owner finding {name!r} has no findingKey or id, so the advisor's input cannot name it")
    return rec


def _options(given, words, leftover):
    """The options a value gives: "none", a list or (on a leftover only) an object of consequences by option id; None when it is none of these."""
    if given == "none":
        return []
    if leftover and isinstance(given, dict):
        base = words["leftoverOptions"]
        ok = set(given) == {o["id"] for o in base} and all(_text(v) for v in given.values())
        return [{**o, "consequence": given[o["id"]]} for o in base] if ok else None
    return given if isinstance(given, list) else None


def _check_call(where, call, words, problems, leftover):
    given = call["options"]
    opts = _options(given, words, leftover)
    ids = ", ".join(o["id"] for o in words["leftoverOptions"])
    if given == "leftover" and leftover:
        problems.append(f'{where}: options "leftover" is refused; give each option\'s consequence for this leftover '
                        f'(an object with {ids}) or "none"')
    elif opts is None:
        problems.append(f'{where}: options must be none, a list of options'
                        + (f' or an object giving {ids} a non-empty consequence each' if leftover else ""))
    opts = _check_list(f"{where}: options", opts or [], ("id", "label", "consequence", "sendsBack"), (), problems)
    problems.extend(f"{where}: option {o['id']} needs sendsBack to be true or false"
                    for o in opts if "sendsBack" in o and not isinstance(o["sendsBack"], bool))
    rec = call.get("recommendation")
    if "recommendation" in call and _keys(f"{where}: recommendation", rec, ("text", "reason"), ("optionId",), problems):
        if not (_text(rec["text"]) and _text(rec["reason"])):
            problems.append(f"{where}: recommendation needs a text and a reason")
        if "optionId" in rec and rec["optionId"] not in [o["id"] for o in opts]:
            problems.append(f"{where}: recommendation optionId {rec['optionId']!r} is not one of its options")


def _check_list(name, entries, required, optional, problems):
    """Checks a list of objects with unique ids and non-empty text; returns the entries that are sound."""
    if not isinstance(entries, list):
        problems.append(f"{name} must be a list")
        return []
    good, ids = [], []
    for n, e in enumerate(entries, 1):
        w = f"{name} entry {n}"
        if not _keys(w, e, required, optional, problems):
            continue
        if not (all(_text(e[k]) for k in required if k not in ("pr", "options", "sendsBack", "ifLeft")) and _ID.match(e["id"])):
            problems.append(f"{w} needs an id of lowercase letters, digits and hyphens and non-empty text")
        elif e["id"] in ids:
            problems.append(f"{w} repeats the id {e['id']}")
        else:
            good.append(e)
        ids.append(e["id"])
    return good


def _check_input(adv, words, problems):
    """Collects the input's problems; returns the PR numbers the sheet covers, or None when unknown."""
    optional = ("previousCommit", "carriedForward", "prs", "leftovers", "craftDeterminations", "items", "collectorItems", "closesSpec",
                "accounting", "walk")
    _keys("the advisor's input", adv, ("schema", "kind", "number", "title", "summary"), optional, problems)
    kind, number, prs = adv.get("kind"), adv.get("number"), adv.get("prs")
    if adv.get("schema") != "pr-sheet-input/1":
        problems.append("the advisor's input schema must be pr-sheet-input/1")
    if kind not in ("pr", "stack"):
        problems.append('kind must be "pr" or "stack"')
    if not _num(number):
        problems.append("number must be an integer, 1 or more")
    problems.extend(f"{k} must be a non-empty string" for k in ("title", "summary") if k in adv and not _text(adv[k]))
    if adv.get("previousCommit") is not None and not _commit(adv["previousCommit"]):
        problems.append("previousCommit must be null or a commit id of 7 to 40 lowercase hex characters")
    allowed = [number] if kind == "pr" and _num(number) else None
    if kind == "pr" and "prs" in adv:
        problems.append("prs is refused on a pr sheet")
    if kind == "stack":
        if isinstance(prs, list) and len(prs) >= 2 and all([_keys(f"prs entry {n}", p, ("number", "title"), (), problems)
                                                            and _num(p["number"]) and _text(p["title"])
                                                            for n, p in enumerate(prs, 1)]) \
                and len({p["number"] for p in prs}) == len(prs):
            allowed = [p["number"] for p in prs]
        else:
            problems.append("a stack needs prs: at least 2 PRs, each with its own number and a title")
    leftovers = adv.get("leftovers", {})
    if not isinstance(leftovers, dict):
        problems.append("leftovers must be an object")
    for k, call in (leftovers.items() if isinstance(leftovers, dict) else ()):
        if _keys(f"leftovers {k}", call, ("why", "context", "options"), ("ifLeft", "recommendation"), problems):
            problems.extend(f"leftovers {k}: {t} must be a non-empty string" for t in ("why", "context", "ifLeft")
                            if t in call and not _text(call[t]))
            _check_call(f"leftovers {k}", call, words, problems, True)
    determined = adv.get("craftDeterminations", {})
    if not isinstance(determined, dict):
        problems.append("craftDeterminations must be an object")
    for k, call in (determined.items() if isinstance(determined, dict) else ()):
        _keys(f"craftDeterminations {k}", call, ("ground", "reason"), (), problems)
        if isinstance(call, dict):
            if not _text(call.get("ground")):
                problems.append(f"craftDeterminations {k}: ground must be a non-empty string; a re-grade names the owner-vs-craft line's ground")
            if "reason" in call and not _text(call["reason"]):
                problems.append(f"craftDeterminations {k}: reason must be a non-empty string")
    for it in _check_list("items", adv.get("items", []), ("id", "kind", "title", "ifLeft", "options"),
                          ("recommendation",), problems):
        notes = it["ifLeft"]
        if not (_text(notes) or isinstance(notes, list) and notes and all(_text(n) for n in notes)):
            problems.append(f"items {it['id']}: ifLeft must be a non-empty string or a list of at least 1 non-empty strings")
        _check_call(f"items {it['id']}", it, words, problems, False)
    _check_collector(adv.get("collectorItems", []), words, problems)
    spec = adv.get("closesSpec")
    if spec is not None and _keys("closesSpec", spec, ("spec", "receipt"), (), problems) \
            and not (_text(spec["spec"]) and _text(spec["receipt"])):
        problems.append("closesSpec needs a spec and a receipt, both non-empty strings")
    if "walk" in adv:
        _check_walk(adv["walk"], allowed, problems)
    return allowed


def _check_collector(entries, words, problems):
    """Collects the collectorItems problems: each entry's spine, its lettered options and its keyed recommendation."""
    if not isinstance(entries, list):
        problems.append("collectorItems must be a list")
        return
    seen = []
    for n, e in enumerate(entries, 1):
        number = e.get("number") if isinstance(e, dict) else None
        where = f"collectorItems {number}" if _num(number) else f"collectorItems entry {n}"
        if not _keys(where, e, ("number", "title", "why", "context", "options", "ifLeft", "recommendation"), (), problems):
            continue
        if not _num(number):
            problems.append(f"{where} needs number, an integer 1 or more")
        elif number in seen:
            problems.append(f"{where} repeats the number {number}")
        seen.append(number)
        problems.extend(f"{where}: {k} must be a non-empty string" for k in ("title", "why", "context", "ifLeft") if not _text(e[k]))
        opts = e["options"]
        if not (isinstance(opts, list) and opts):
            problems.append(f"{where}: options must be a list of at least 1 option; a collector item is a decision, so \"none\" and an empty list are refused")
        else:
            _check_call(where, e, words, problems, False)
            problems.extend(f"{where}: option {i} must have the id {chr(ord('a') + i - 1)!r}, the letter of its place; ids run a, b, c in order"
                            for i, o in enumerate(opts, 1) if isinstance(o, dict) and o.get("id") != chr(ord("a") + i - 1))
        rec = e["recommendation"]
        if not (isinstance(opts, list) and opts):
            _keys(f"{where}: recommendation", rec, ("text", "reason"), ("optionId",), problems)
        if isinstance(rec, dict) and "optionId" not in rec:
            problems.append(f"{where}: recommendation needs an optionId naming one of the options")


def _check_walk(walk, allowed, problems):
    if not _keys("walk", walk, *_shape(_WALK), problems):
        return
    problems.extend(f"walk {k} must be a non-empty string" for k in ("note", "picturesFrom") if k in walk and not _text(walk[k]))
    opened = walk["open"]
    if _keys("walk open", opened, *_shape(_WALK["properties"]["open"]), problems):
        problems.extend(f"walk open {k} must be a non-empty string" for k in ("label", "detail") if k in opened and not _text(opened[k]))
        if "url" in opened and not (isinstance(opened["url"], str) and _URL.match(opened["url"])):
            problems.append("walk open url must be an http or https link")
    if not (isinstance(walk["stops"], list) and walk["stops"]):
        problems.append("walk needs at least one stop")
        return
    for stop in _check_list("walk stops", walk["stops"], *_shape(_STOP, ("key", "steps", "pictures")), problems):
        w, steps, pictures = f"walk stop {stop['id']}", stop.get("steps", []), stop.get("pictures", [])
        if not _num(stop["pr"]):
            problems.append(f"{w} needs pr, an integer 1 or more")
        elif allowed is not None and stop["pr"] not in allowed:
            problems.append(f"{w} is for PR #{stop['pr']}, which is not in this sheet")
        kind = stop["kind"]
        rule = _STEPS.get(kind, {}) if kind in _KINDS else {}
        if kind not in _KINDS:
            problems.append(f"{w} needs kind to be " + " or ".join(f'"{k}"' for k in _KINDS))
        if not (isinstance(steps, list) and all(_text(t) for t in steps)):
            problems.append(f"{w} needs steps to be a list of non-empty strings")
        elif len(steps) < rule.get("minItems", 0) or steps != rule.get("const", steps):
            problems.append(f"{w} is a {kind} stop, so it {'needs at least one step' if 'minItems' in rule else 'takes no steps'}")
        if "optional" in stop and not isinstance(stop["optional"], bool):
            problems.append(f"{w} needs optional to be true or false")
        if "notWalked" in stop and not _text(stop["notWalked"]):
            problems.append(f"{w} needs notWalked to be a non-empty string")
        if not isinstance(pictures, list):
            problems.append(f"{w} needs pictures to be a list")
        for n, pic in enumerate(pictures if isinstance(pictures, list) else [], 1):
            if _keys(f"{w} picture {n}", pic, ("path", "alt"), ("caption",), problems) \
                    and not all(_text(pic[k]) for k in pic):
                problems.append(f"{w} picture {n} needs a non-empty path and alt, and a non-empty caption when it has one")


def _check_carry_input(carry, allowed, problems):
    """Collects the carriedForward input's problems; True when it is sound, so the earlier sheet can be checked against it."""
    found = len(problems)
    if not _keys("carriedForward", carry, ("fromSheet", "heads", "date", "moved", "whyNotMaterial"), (), problems):
        return False
    problems.extend(f"carriedForward {k} must be a non-empty string" for k in ("fromSheet", "moved", "whyNotMaterial") if not _text(carry[k]))
    if not (isinstance(carry["date"], str) and _DATE.match(carry["date"])):
        problems.append("carriedForward date must be a date written YYYY-MM-DD")
    heads = carry["heads"]
    if not isinstance(heads, dict):
        problems.append("carriedForward heads must be an object of PR number to head commit")
    else:
        problems.extend(f"carriedForward heads {k} must be a commit id of 7 to 40 lowercase hex characters" for k, v in heads.items() if not _commit(v))
        if allowed is not None and set(heads) != {str(n) for n in allowed}:
            problems.append(f"carriedForward heads has PRs {sorted(heads)}, but the sheet covers PRs {sorted(str(n) for n in allowed)}")
    return len(problems) == found


def _check_previous(advisor, previous, problems):
    """The earlier sheet as a dict when it is this PR's or stack's own sheet and the carry may stand on it; else None after naming why."""
    if previous is None:
        problems.append("carriedForward needs the bytes of the earlier sheet (fromSheet), and none were given")
        return None
    try:
        sheet = json.loads(previous)
    except ValueError as err:
        problems.append(f"the earlier sheet (carriedForward fromSheet) is not JSON: {err}")
        return None
    if not isinstance(sheet, dict) or sheet.get("kind") not in sheet_prose.PR_KINDS:
        problems.append("the earlier sheet (carriedForward fromSheet) is not a pr or stack sheet")
        return None
    found = sheet_prose.check_sheet(sheet)
    if found:
        problems.extend(f"the earlier sheet (carriedForward fromSheet): {p}" for p in found)
        return None
    before, part = len(problems), sheet["prSheet"]
    if sheet["kind"] != advisor["kind"]:
        problems.append(f"the earlier sheet is a {sheet['kind']} sheet, but this one is a {advisor['kind']} sheet")
    if part["number"] != advisor["number"]:
        problems.append(f"the earlier sheet is for number {part['number']}, not {advisor['number']}")
    if advisor["kind"] == "stack" and [p["number"] for p in part.get("prs", [])] != [p["number"] for p in advisor["prs"]]:
        problems.append(f"the earlier sheet covers PRs {[p['number'] for p in part.get('prs', [])]}, but this stack lists PRs {[p['number'] for p in advisor['prs']]}, in that order")
    if advisor.get("previousCommit") and advisor["previousCommit"] != part["commit"]:
        problems.append(f"previousCommit {advisor['previousCommit']} is not the earlier sheet's commit {part['commit']}")
    return sheet if len(problems) == before else None


def _lookups(kind, pr, finding):
    """The leftovers keys that can name a finding: its findingKey first, then its reviewer id."""
    names = [finding.get("findingKey"), finding.get("id")]
    return [n if kind == "pr" else f"{pr}:{n}" for n in dict.fromkeys(str(n) for n in names if n)]


def _leftover_call(kind, pr, finding, leftovers):
    return next((leftovers[k] for k in _lookups(kind, pr, finding) if k in leftovers), {})


def _section(title, block, text):
    return {"title": title, "blocks": [{block: text}]}


def _card(prefix, pr, identity, call_kind, question, context, options, recommendation):
    card = {"callKind": call_kind, "warning": False, "question": question, "context": context, "images": [],
            "options": copy.deepcopy(options)}
    if recommendation is not None:
        card["recommendation"] = copy.deepcopy(recommendation)
    return {"id": card_id(prefix, pr, identity, card), **card}


def _shown(card):
    """The strings a card shows the owner: its question, every context block's text, and its recommendation's text and reason."""
    blocks = [b for section in card["context"] for b in section["blocks"]]
    texts = [card["question"], *(t for b in blocks for v in b.values() for t in ([v] if isinstance(v, str) else v))]
    return texts + [card["recommendation"][k] for k in ("text", "reason") if k in card.get("recommendation", {})]


def _walk(walk, place):
    """The walk as the sheet carries it; place(path) is a picture's sheet src, or None when it cannot be copied."""
    def picture(pic):
        src = place(pic["path"]) if place else None
        return {**({"src": src} if src else {"missing": True}), "alt": pic["alt"],
                **({"caption": pic["caption"]} if "caption" in pic else {})}
    stops = [{"id": s["id"], "title": s["title"], "pr": s["pr"], "group": s["group"], "kind": s["kind"],
              "steps": list(s.get("steps", [])), "expect": s["expect"], "pictures": [picture(p) for p in s.get("pictures", [])],
              **{k: s[k] for k in ("optional", "notWalked") if k in s}} for s in walk["stops"]]
    head = {"open": dict(walk["open"]), **({"note": walk["note"]} if "note" in walk else {})}
    keyed = []
    for s in stops:  # the key names the stop's stored answer and changes when anything the stop shows does
        shown = json.dumps([s, head], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        keyed.append({"id": s["id"], "key": s["id"] + "-" + hashlib.sha256(shown.encode("utf-8")).hexdigest()[:STOP_DIGEST], **{k: v for k, v in s.items() if k != "id"}})
    return {**head, "picturesFrom": walk["picturesFrom"], "stops": keyed}


def _check_bodies(bodies, allowed, problems):
    """Collects the problems of the PR bodies given: one for each covered PR with none, each key that names a PR the sheet does not cover."""
    if not isinstance(bodies, dict):
        problems.append("the PR bodies must be an object of PR number to body text")
        return
    for n in allowed:
        if n not in bodies:
            problems.append(f"PR #{n} has no body: give --pr-body {n}=<file> with the PR's body (gh api repos/<owner>/<repo>/pulls/{n} --jq .body), "
                            "so the build can check that the input accounts for its What we're accepting")
        elif not isinstance(bodies[n], str):
            problems.append(f"PR #{n}'s body must be text")
    problems.extend(f"--pr-body names PR #{n}, which the sheet does not cover" for n in sorted(bodies, key=str) if n not in allowed)


_TARGETS = ("item", "fold", "leftover", "canon")


def _excerpt(text):
    """The first 80 characters of an acceptance, with … when it is cut."""
    return text if len(text) <= 80 else text[:80] + "…"


def _check_accounting(accounting, listed, advisor, leftovers, named, problems):
    """Collects the problems of the input's accounting against the acceptances the bodies list (listed: PR number to
    listed_bullets): each bullet needs exactly one target that exists on the sheet, and each key must name a bullet."""
    if not isinstance(accounting, dict):
        problems.append("accounting must be an object of bullet id to where that acceptance is accounted for")
        accounting = {}
    given_items = advisor.get("items")
    items = {it["id"]: it for it in (given_items if isinstance(given_items, list) else []) if isinstance(it, dict) and isinstance(it.get("id"), str)}
    summary = advisor["summary"] if isinstance(advisor.get("summary"), str) else ""
    known = set()
    for pr, bullets in listed.items():
        for bullet, text in bullets:
            known.add(bullet)
            shown = f'accounting "{bullet}" (PR #{pr}: "{_excerpt(text)}")'
            if bullet not in accounting:
                problems.append(f"PR #{pr}'s acceptance {bullet} (\"{_excerpt(text)}\") is not accounted for: "
                                f'give accounting "{bullet}" one of item, fold with line, leftover, or canon')
                continue
            value = accounting[bullet]
            targets = [t for t in _TARGETS if isinstance(value, dict) and t in value]
            if len(targets) > 1:
                problems.append(f"{shown} is accounted for more than once: give exactly one of item, fold, leftover or canon")
            elif not (len(targets) == 1 and set(value) == {*targets, *(["line"] if targets[0] == "fold" else [])}):
                problems.append(f"{shown} must be an object with exactly one of item, fold with line, leftover or canon")
            elif targets[0] == "item" and not (isinstance(value["item"], str) and value["item"] in items):
                problems.append(f'{shown} names item "{value["item"]}", which is not in items')
            elif targets[0] == "fold":
                folded = items.get(value["fold"]) if isinstance(value["fold"], str) else None
                notes = folded.get("ifLeft") if folded is not None else None
                if not (isinstance(notes, list) and _num(value["line"]) and value["line"] <= len(notes)):
                    problems.append(f'{shown} names fold "{value["fold"]}" line {value["line"]}, which is not a line of that item\'s ifLeft list')
            elif targets[0] == "leftover" and not (isinstance(value["leftover"], str) and value["leftover"] in leftovers
                                                   and named.get(value["leftover"], 0) == 1):
                problems.append(f'{shown} names leftover "{value["leftover"]}", which names no one left-for-owner finding in leftovers')
            elif targets[0] == "canon" and not (canon.is_entry_id(value["canon"]) and value["canon"] in canon.cited_entry_ids(summary)):
                problems.append(f'{shown} names canon "{value["canon"]}", which is not a Canon entry id (YYYY-MM-DD-xxxxxxxx-N) cited in the summary')
    problems.extend(f'accounting key "{k}" names no acceptance in the covered PR bodies' for k in accounting if k not in known)


def build(records, advisor, words, place=None, previous=None, bodies=None):
    """Returns the sheet's data file as a dict, or raises Refusal with every problem found.

    previous is the exact bytes of the earlier sheet the input's carriedForward.fromSheet names, None when there is no carry
    (a carry given None is refused). bodies is None (the caller reads no PR body: no accounting check is made, the input's
    accounting is accepted and ignored, and the sheet gets neither nothingListed nor canonAccounted) or a dict of each covered
    PR's number to its body text, whose keys must be exactly the covered PRs. With bodies, once they raise no problem of their
    own, the input's accounting must account for every acceptance they list, exactly once, to something on the sheet
    (_check_accounting); no listed acceptance becomes a card. The sheet then records one of three states about them: no
    acceptance is listed (nothingListed), at least one is listed and every one is accounted to a Canon ruling (canonAccounted:
    the ruling ids, sorted and distinct), or neither (some acceptance rests on an item, a fold or a leftover card).
    """
    problems = []
    if not isinstance(advisor, dict):
        raise Refusal(["the advisor's input must be an object"])
    allowed = _check_input(advisor, words, problems)
    bodies_sound = False
    if bodies is not None and allowed is not None:
        found = len(problems)
        _check_bodies(bodies, allowed, problems)
        bodies_sound = len(problems) == found
    earlier = None
    if "carriedForward" in advisor and _check_carry_input(advisor["carriedForward"], allowed, problems) and allowed is not None \
            and _num(advisor.get("number")):  # a stack without a number is refused above, and the earlier sheet cannot be compared to it
        earlier = _check_previous(advisor, previous, problems)
    recs = [r for r in (_record(raw, n, problems) for n, raw in enumerate(records, 1)) if r]
    kind, number, have = advisor.get("kind"), advisor.get("number"), [r["pr"] for r in recs]
    if allowed is not None and len(recs) == len(records):
        if kind == "pr" and len(recs) != 1:
            problems.append(f"a pr sheet takes exactly one record, got {len(recs)}")
        elif kind == "pr" and have[0] != number:
            problems.append(f"the record is for PR #{have[0]}, not PR #{number}")
        elif kind == "stack":
            problems.extend(f"PR #{n} has more than one record" for n in sorted({n for n in have if have.count(n) > 1}))
            if set(have) != set(allowed):
                problems.append(f"the records are for PRs {sorted(set(have))}, but the stack lists PRs {sorted(allowed)}")
    leftovers, determined = advisor.get("leftovers", {}), advisor.get("craftDeterminations", {})
    leftovers, determined = (x if isinstance(x, dict) else {} for x in (leftovers, determined))
    # The earlier sheet's decided-for-you entries by finding: a carried sheet keeps them as they stand.
    before = {e["finding"]: e for e in earlier["prSheet"].get("decidedForYou", [])} if earlier is not None else {}
    named, decisions = {}, {}
    for r in recs:
        for n, f in enumerate(r["findings"]):
            if isinstance(f, dict) and f.get("outcome") == _LEFT:
                keys = _lookups(kind, r["pr"], f)
                for k in keys:
                    named[k] = named.get(k, 0) + 1
                if not keys:
                    continue
                call_at, det_at = next((k for k in keys if k in leftovers), None), next((k for k in keys if k in determined), None)
                prior = before.get(keys[0])
                det = determined[det_at] if det_at is not None else prior if prior is not None and call_at is None else None
                if earlier is not None and det_at is not None:
                    if prior is None:
                        problems.append(f"craftDeterminations {det_at}: a carried sheet cannot add a determination; add it on an unsigned republish")
                    elif not (isinstance(det, dict) and (det.get("ground"), det.get("reason")) == (prior["ground"], prior["reason"])):
                        problems.append(f"craftDeterminations {det_at}: a carried sheet keeps the earlier sheet's determination unchanged; change it on an unsigned republish")
                if prior is not None and call_at is not None:
                    problems.append(f"leftovers {call_at}: a carried sheet cannot turn a decided-for-you entry back into a card; do that on an unsigned republish")
                if det is not None:
                    decisions[(r["pr"], n)] = det
                if det is not None and call_at is not None:
                    problems.append(f"left-for-owner finding {_title(f)!r} on PR #{r['pr']} has both a leftovers entry and a craft determination; give one")
                elif det is None and call_at is None:
                    problems.append(f"left-for-owner finding {_title(f)!r} on PR #{r['pr']} has no leftovers entry (key {keys[0]!r}); "
                                    "give it why, context and options, or a craft determination")
    for name, given in (("leftovers", leftovers), ("craftDeterminations", determined)):
        problems.extend(f"{name} key {k!r} names no left-for-owner finding" for k in given if k not in named)
        problems.extend(f"{name} key {k!r} names {named[k]} left-for-owner findings; use a finding's findingKey"
                        for k in given if named.get(k, 0) > 1)
    listed = {pr: listed_bullets(pr, bodies[pr]) for pr in allowed} if bodies_sound else {}
    if bodies_sound:
        _check_accounting(advisor.get("accounting", {}), listed, advisor, leftovers, named, problems)
        for pr in allowed:
            for label, text in costly_unlisted(bodies[pr]):
                problems.append(f'PR #{pr}\'s {"costly" if label else "unlabelled (read as costly)"} deviation ("{_excerpt(text)}") has no line under '
                                "What we're accepting: carry its text, after the label, into a line there")
    if problems:
        raise Refusal(problems)
    stack = kind == "stack"
    by_pr = {r["pr"]: r for r in recs}
    recs = [by_pr[n] for n in allowed] if stack else recs
    top, tag = recs[-1], (lambda r: f"#{r['pr']}: " if stack else "")
    cards, decided_for_you, places = [], [], []
    for r in recs:
        for n, f in enumerate(r["findings"]):
            if f["outcome"] != _LEFT:
                continue
            if (r["pr"], n) in decisions:
                det = decisions[(r["pr"], n)]
                decided_for_you.append({"id": card_id("d-", r["pr"], f.get("findingKey") or f["id"], "decided-for-you"),
                                        "finding": _lookups(kind, r["pr"], f)[0], "title": _title(f),
                                        "ground": det["ground"], "reason": det["reason"], **({"pr": r["pr"]} if stack else {})})
                continue
            call = _leftover_call(kind, r["pr"], f, leftovers)
            options = _options(call["options"], words, True)
            cards.append(_card("f-", r["pr"], f.get("findingKey") or f["id"],
                               words["leftoverKind"] + (f" · #{r['pr']}" if stack else ""), _title(f),
                               [_section(words["whyYours"], "paragraph", call["why"]),
                                _section(words["whatHappened"], "paragraph", call["context"]),
                                _section(words["ifLeft"], "paragraph", call.get("ifLeft", f["consequence"]))],
                               options, call.get("recommendation")))
            places.append("leftovers " + next(k for k in _lookups(kind, r["pr"], f) if k in leftovers))
    for it in advisor.get("items", []):
        block = "bullets" if isinstance(it["ifLeft"], list) else "paragraph"
        cards.append(_card("i-", number, it["id"], it["kind"], it["title"], [_section(words["ifLeft"], block, it["ifLeft"])],
                           _options(it["options"], words, False), it.get("recommendation")))
        places.append(f"items {it['id']}")
    for it in advisor.get("collectorItems", []):
        rec = it["recommendation"]
        cards.append(_card("k-", number, it["number"], _fill(words["collectorKind"], number=it["number"]), it["title"],
                           [_section(words["whyYours"], "paragraph", it["why"]),
                            _section(words["whatHappened"], "paragraph", it["context"]),
                            _section(words["ifLeft"], "paragraph", it["ifLeft"])],
                           [{**o, "label": _fill(words["collectorOption"], letter=o["id"], label=o["label"])} for o in it["options"]],
                           {"text": _fill(words["collectorRecommendation"], letter=rec["optionId"], text=rec["text"]),
                            "reason": rec["reason"], "optionId": rec["optionId"]}))
        places.append(f"collectorItems {it['number']}")
    spec = advisor.get("closesSpec")
    if spec:
        context = [_section(words["ifLeft"], "paragraph", words["closureIfLeft"]),
                   _section(words["closureReceipt"], "quote", spec["receipt"])]
        cards.append(_card("c-", number, spec["spec"], words["closureKind"],
                           _fill(words["closureQuestion"], spec=spec["spec"]), context, [], None))
        places.append("closesSpec")
    pointing = [f"{where}: card {card['question']!r} sends the owner to a list item ({found.group(0)!r}) instead of carrying that "
                "decision's options; put the decision on this sheet as a collectorItems card, or give this card its own options"
                for where, card in zip(places, cards) if where is not None and not card["options"] for text in _shown(card) for found in _POINTER.finditer(text)]
    if pointing:
        raise Refusal(pointing)
    if len({c["id"] for c in [*cards, *decided_for_you]}) != len(cards) + len(decided_for_you):
        raise Refusal(["two cards would share an id: the same finding or item appears twice"])
    reviewers, caught, craft, decided, history = [], [], [], [], []
    for r in recs:
        lines = [_fill(words["historyRounds"], rounds=r["rounds"]["count"])]
        if r["rounds"]["stoppedAtCap"]:
            lines.append(words["historyCap"])
        for f in r["findings"]:
            entries = {_CRAFT: craft, _RULING: decided}.get(f["outcome"])
            if f["outcome"] == _FIXED:
                caught.append(tag(r) + _title(f))
            elif entries is not None:
                entries.append({"title": _title(f), "detail": f["reason"], **({"pr": r["pr"]} if stack else {})})
            elif f["outcome"] == _SHOWN_WRONG:
                lines.append(_fill(words["historyShownWrong"], title=_title(f), reason=f["reason"]))
        for m in r["missingReviews"]:
            said = _go_ahead(m.get("goAhead"))
            lines.append(_fill(words["historyMissing"], name=m["name"],
                               goAhead=_fill(words["historyGoAhead"], goAhead=said) if said else words["historyNoGoAhead"]))
        gaps =(r.get("whatIsMissing") or []) if not review_record.cleared(r.get("status")) else []
        owned = [review_record.leftover_line(f) for f in r["findings"] if f.get("outcome") == _LEFT]
        count, counted = sum(1 for m in gaps if m in owned), False
        for m in gaps:
            if m not in owned:
                lines.append(_fill(words["historyIncomplete"], what=m))
            elif not counted:
                counted = True
                lines.append(_fill(words["historyLeftovers"], count=count) if count > 1 else words["historyLeftover"])
        if stack:
            lines.append(_fill(words["historyChecks"], state=r["ci"]["state"], commit=r["ci"].get("sha") or "no commit"))
        ran = [v for v in r["reviewers"] if v["ran"] != review_record.RAN_NOT_RUN]
        behind = [v for v in ran if v.get("coversFinalCommit") is False]
        if behind:
            # Axis: a normal multi-round review reads as normal; only a final commit no planned reviewer's run covers is the warning.
            covered = any(v.get("coversFinalCommit") is True and v.get("planned") is not False for v in ran)
            commits = list(dict.fromkeys(c for c in (_short(v.get("commit")) for v in behind) if c))
            noun = ("commit " if len(commits) == 1 else "commits ") + ", ".join(commits) if commits else "an earlier commit"
            lines.append(_fill(words["historyLaterRounds" if covered else "historyNoFinalReview"], earlier=noun,
                               final=_short(r["finalCommit"]["sha"]) or "unknown"))
        for v in r["reviewers"]:
            shown = {"name": v["name"], "family": v["family"], "ran": v["ran"]}
            # The record's independence fact is carried as it stands: absent stays absent, never read as false.
            if isinstance(v.get("notIndependent"), bool):
                shown["notIndependent"] = v["notIndependent"]
            if v["ran"] != review_record.RAN_NOT_RUN and shown not in reviewers:
                reviewers.append(shown)
            if v.get("notIndependent"):
                lines.append(_fill(words["historyNotIndependent"], name=v["name"]))
        history += [tag(r) + line for line in lines]
    sheet = {
        "number": number, "commit": top["finalCommit"]["sha"],
        "whatChanged": {
            "summary": advisor["summary"], "reviewers": reviewers, "caught": caught,
            "rounds": sum(r["rounds"]["count"] for r in recs), "stoppedAtCap": any(r["rounds"]["stoppedAtCap"] for r in recs),
            "ci": {"state": top["ci"]["state"], "commit": top["ci"].get("sha")},
            "lane": top["lane"].get("value"), "laneReason": top["lane"].get("reason")},
        "craft": craft, "alreadyDecided": decided, **({"decidedForYou": decided_for_you} if decided_for_you else {}), "history": history}
    if bodies is not None and not any(listed.values()):  # every covered body was read and none lists an acceptance
        sheet["nothingListed"] = True
    elif bodies is not None:  # at least one is listed: Canon alone covers them all when every bullet is accounted to a Canon ruling
        accounting = advisor.get("accounting", {})
        rulings = [accounting[bullet].get("canon") for bullets in listed.values() for bullet, _ in bullets]
        if all(isinstance(ruling, str) for ruling in rulings):
            sheet["canonAccounted"] = sorted(set(rulings))
    if "walk" in advisor:
        sheet["walk"] = _walk(advisor["walk"], place)
    if advisor.get("previousCommit"):
        sheet["previousCommit"] = advisor["previousCommit"]
    if stack:
        sheet["prs"] = [{"number": p["number"], "title": p["title"], "commit": by_pr[p["number"]]["finalCommit"]["sha"]}
                        for p in advisor["prs"]]
    if earlier is not None:
        # The carry: the heads the advisor names replace the records' final commits, and the chain of earlier digests grows by the sheet carried from.
        # whatChanged.ci stays as the record gives it, because it names the commit CI ran on.
        carry = advisor["carriedForward"]
        heads = carry["heads"]
        sheet["previousCommit"] = earlier["prSheet"]["commit"]
        sheet["commit"] = heads[str(allowed[-1] if stack else number)]
        for found in sheet.get("prs", []):
            found["commit"] = heads[str(found["number"])]
        sheet["carriedForward"] = {"sheets": [hashlib.sha256(previous).hexdigest(), *earlier["prSheet"].get("carriedForward", {}).get("sheets", [])],
                                   "date": carry["date"], "moved": carry["moved"], "whyNotMaterial": carry["whyNotMaterial"]}
    return {"schema": "superheroes-sheet/1", "kind": kind, "title": advisor["title"], "prSheet": sheet, "cards": cards}


def _earlier_sheet(advisor, base):
    """The exact bytes of the earlier sheet the input's carriedForward.fromSheet names, None when there is no carry to read;
    an unreadable file is a refusal that names it."""
    carry = advisor.get("carriedForward") if isinstance(advisor, dict) else None
    if not (isinstance(carry, dict) and _text(carry.get("fromSheet"))):
        return None
    try:
        return pathlib.Path(base, carry["fromSheet"]).read_bytes()
    except OSError as err:
        raise Refusal([f"{carry['fromSheet']} could not be read as the earlier sheet: {err}"])


def _pr_words():
    with open(WORDS_PATH, encoding="utf-8") as handle:
        return json.load(handle)["pr"]


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _pr_answer_words():
    with open(WORDS_PATH, encoding="utf-8") as handle:
        return json.load(handle)["prAnswers"]


def _counted_answer(card, doc, answer_words):
    """doc when it is a stored answer this pr or stack sheet's card offers now, else None (the card is unanswered).

    What a card offers is read from answer_words (the prAnswers block of sheet-words.json), as the page reads it: the
    plain answers listed for a card with options or without, and an option only when it is one of the card's own.
    """
    if not sheet_prose.fits_definition("answer", doc):
        return None
    if card["options"]:
        offered = doc["answer"] in answer_words["withOptions"] or (doc["answer"] == "option" and doc["optionId"] in [o["id"] for o in card["options"]])
    else:
        offered = doc["answer"] in answer_words["withoutOptions"]
    return doc if offered else None


def _collection(store, key):
    found = store.get(key) if isinstance(store, dict) else None
    return found if isinstance(found, dict) else {}


def pr_state(sheet_bytes, store, words=None, answer_words=None):
    """Where one PR's published sheet stands, from the sheet's exact bytes and its store dump.

    Returns {"state", "accepted", "total", "walked", "walkTotal"}. The state is being-fixed when a counted answer
    sends the PR back, else needs-you when the owner took back a decided-for-you entry, else ready when a Merge verdict
    stands, else needs-you. An entry is taken back (reclaimed) when the store holds a document at answers/<its id> that is
    not a well-formed answer of null; a malformed document counts as taking it back. Decided entries are no cards: they
    never count in accepted or total and never enter covers. A Merge stands only on this exact sheet, with every item
    accepted, no walk Problem left without a follow-up fix, and a covers that names exactly the answers the store holds now. words is the "pr" block of sheet-words.json and answer_words its "prAnswers" block,
    each read from the file when not given.
    """
    words = words or _pr_words()
    answer_words = answer_words or _pr_answer_words()
    digest, sheet = hashlib.sha256(sheet_bytes).hexdigest(), json.loads(sheet_bytes)
    cards, stops = sheet["cards"], sheet["prSheet"].get("walk", {}).get("stops", [])
    fixes = {f["id"]: f for f in words["walkFixes"]}
    answers, walks = _collection(store, "answers"), _collection(store, "walk")
    counted = {card["id"]: _counted_answer(card, answers.get(card["id"]), answer_words) for card in cards}
    accepted, sends_back, blocking, walked = 0, False, False, 0
    for card in cards:
        doc = counted[card["id"]]
        if doc is None:
            continue
        picked = next((o for o in card["options"] if o["id"] == doc["optionId"]), None)
        accepted += doc["answer"] == "accept" or (picked is not None and picked.get("sendsBack") is False)
        sends_back = sends_back or (picked is not None and picked.get("sendsBack") is True)
    for stop in stops:
        doc = walks.get(stop["key"])
        if not (sheet_prose.fits_definition("walkAnswer", doc) and doc["answer"] in sheet_prose.offered_walk_answers(stop["kind"]) and (doc["fix"] is None or doc["fix"] in fixes)):
            # As the page restores it: a stored Problem whose fix is no longer offered, or whose document is malformed, stays a Problem with no fix and keeps blocking.
            if isinstance(doc, dict) and doc.get("answer") == "problem":
                walked, blocking = walked + 1, True
            continue
        walked += doc["answer"] in words["walkedAnswers"]
        if doc["answer"] == "problem":
            fix = fixes.get(doc["fix"])
            blocking = blocking or fix is None or fix.get("sendsBack") is not False
            sends_back = sends_back or (fix is not None and fix.get("sendsBack") is True)
    # A stored document under a decided entry's id that is not a well-formed null answer is the owner taking the finding back; malformed fails closed.
    reclaimed = any(entry["id"] in answers and not (sheet_prose.fits_definition("answer", answers[entry["id"]]) and answers[entry["id"]]["answer"] is None)
                    for entry in sheet["prSheet"].get("decidedForYou", []))
    revisions = [counted[card["id"]] and counted[card["id"]].get("revision") for card in cards]
    covered = None if not all(revisions) else {f"answers/{card['id']}@{rev}" for card, rev in zip(cards, revisions)}
    # The verdict is the document of the first revision in the chain (this sheet, then each sheet it carried a verdict forward from) that has one;
    # that document must be a verdict of that revision, or there is none: an older revision's Merge never stands past a document in between.
    verdicts = _collection(store, "verdict")
    chain = [digest, *sheet["prSheet"].get("carriedForward", {}).get("sheets", [])]
    held = next((revision for revision in chain if revision in verdicts), None)
    verdict = verdicts.get(held)
    stands = (held is not None and sheet_prose.fits_definition("verdict", verdict) and verdict["sheet"] == held and verdict["verdict"] == "merge"
              and accepted == len(cards) and not blocking
              and covered is not None and set(verdict["covers"]) == covered)
    state = "being-fixed" if sends_back else "needs-you" if reclaimed else "ready" if stands else "needs-you"
    return {"state": state, "accepted": accepted, "total": len(cards), "walked": walked, "walkTotal": len(stops)}


_WORD_BLOCKS = {"build": ("pr",), "index": ("pr", "prAnswers", "answers", "index")}


def _load_words(command, problems):
    """The words file as an object holding the blocks this command reads, or None after naming what is wrong with it."""
    found = []
    words = _load(WORDS_PATH, found)
    if not found and not isinstance(words, dict):
        found.append(f"{WORDS_PATH} could not be read: it must hold one JSON object")
    elif not found:
        found.extend(f"{WORDS_PATH} could not be read: it has no {name} block" for name in _WORD_BLOCKS[command] if not isinstance(words.get(name), dict))
    problems.extend(found)
    return None if found else words


def _store(raw, where, problems):
    """The store dump's collections, each an object ({} when the key is missing); None after naming what is wrong."""
    if not _keys(where, raw, (), _STORE_KEYS, problems):
        return None
    wrong = [f"{where} {k} must be an object" for k in _STORE_KEYS if k in raw and not isinstance(raw[k], dict)]
    problems.extend(wrong)
    return None if wrong else {k: raw.get(k, {}) for k in _STORE_KEYS}


def _check_index_input(adv, problems):
    """Collects the index input's problems."""
    _keys("the index input", adv, ("schema", "questions", "mergeOrder", "prs"), (), problems)
    if adv.get("schema") != "index-input/1":
        problems.append("the index input schema must be index-input/1")
    questions, ids = adv.get("questions"), []
    if not isinstance(questions, list):
        problems.append("questions must be a list")
    for n, q in enumerate(questions if isinstance(questions, list) else [], 1):
        where = f"questions entry {n}"
        if not _keys(where, q, ("id", "question", "context", "options", "pictures"), ("recommendation",), problems):
            continue
        if not _matches(_ID, q["id"]):
            problems.append(f"{where} needs an id of lowercase letters, digits and hyphens")
        elif q["id"] in ids:
            problems.append(f"{where} repeats the id {q['id']}")
        ids.append(q["id"])
        where = f"question {q['id']}"
        if not _text(q["question"]):
            problems.append(f"{where} needs a non-empty question")
        if not isinstance(q["context"], list):
            problems.append(f"{where} needs context to be a list of sections")
        options = _check_list(f"{where}: options", q["options"], ("id", "label", "consequence"), (), problems)
        if isinstance(q["options"], list) and not q["options"]:
            problems.append(f"{where} needs at least one option")
        rec = q.get("recommendation")
        if "recommendation" in q and _keys(f"{where}: recommendation", rec, ("text", "reason"), ("optionId",), problems):
            if not (_text(rec["text"]) and _text(rec["reason"])):
                problems.append(f"{where}: recommendation needs a text and a reason")
            if "optionId" in rec and rec["optionId"] not in [o["id"] for o in options]:
                problems.append(f"{where}: recommendation optionId {rec['optionId']!r} is not one of its options")
        if not isinstance(q["pictures"], list):
            problems.append(f"{where} needs pictures to be a list")
        for m, pic in enumerate(q["pictures"] if isinstance(q["pictures"], list) else [], 1):
            if _keys(f"{where} picture {m}", pic, ("path", "alt"), ("caption",), problems) and not all(_text(pic[k]) for k in pic):
                problems.append(f"{where} picture {m} needs a non-empty path and alt, and a non-empty caption when it has one")
    prs, numbers = adv.get("prs"), []
    if not isinstance(prs, list):
        problems.append("prs must be a list")
    for n, p in enumerate(prs if isinstance(prs, list) else [], 1):
        where = f"prs entry {n}"
        if not _keys(where, p, ("number", "link", "sheet", "store"), (), problems):
            continue
        if not _num(p["number"]):
            problems.append(f"{where} needs number, an integer 1 or more")
        elif p["number"] in numbers:
            problems.append(f"{where} repeats the number {p['number']}")
        numbers.append(p["number"])
        if not _matches(_LINK, p["link"]):
            problems.append(f"{where} needs link to be an https link")
        problems.extend(f"{where} needs {k} to be a path" for k in ("sheet", "store") if not _text(p[k]))
    order = adv.get("mergeOrder")
    if not isinstance(order, list):
        problems.append("mergeOrder must be a list")
    for n in order if isinstance(order, list) else []:
        if not _num(n):
            problems.append(f"mergeOrder entry {n!r} must be an integer 1 or more")
        elif n not in numbers:
            problems.append(f"mergeOrder names PR #{n}, which is not in prs")
    if isinstance(order, list) and len(set(map(repr, order))) != len(order):
        problems.append("mergeOrder names a PR more than once")


def _accepting_state(sheet):
    """What a PR or stack sheet recorded about its PR bodies: "nothing" (prSheet.nothingListed), "canon" (prSheet.canonAccounted) or "unchecked"."""
    if sheet["prSheet"].get("nothingListed") is True:
        return "nothing"
    return "canon" if "canonAccounted" in sheet["prSheet"] else "unchecked"


def _row_caption(row, words, accepting="unchecked"):
    """The line under an index row's name, the one home of the rule: what is accepted (or, with no item, what the row's sheet
    recorded about its PR bodies: accepting is "nothing" when they list none, "canon" when every acceptance they list is
    covered by a Canon ruling, else "unchecked", that it was not checked against them), what is walked
    when the PR has a walk, then where the PR stands, with the merge place on a PR that needs the owner, joined with " · "."""
    none = {"nothing": words["nothingToAccept"], "canon": words["acceptingCanon"], "unchecked": words["acceptingUnchecked"]}[accepting]
    parts = [_fill(words["accepted"], accepted=row["accepted"], total=row["total"]) if row["total"] else none]
    if row["walkTotal"] > 0:
        parts.append(_fill(words["walked"], walked=row["walked"], total=row["walkTotal"]))
    if row["state"] == "being-fixed":
        parts.append(words["beingFixed"])
    elif row["state"] == "ready":
        parts.append(words["ready"])
    elif row["mergesAt"] is not None:
        place, ordinals = int(row["mergesAt"]), words["ordinals"]
        parts.append(_fill(words["mergesAt"], ordinal=ordinals[place - 1]) if place <= len(ordinals) else _fill(words["mergesAtNumber"], place=place))
    return " · ".join(parts)


def _index_row(entry, base, order, words, problems):
    """The index row for one PR entry, read from its sheet and store files; None after naming what is wrong."""
    where = f"PR #{entry['number']}"
    try:
        sheet_bytes = pathlib.Path(base, entry["sheet"]).read_bytes()
        sheet = json.loads(sheet_bytes)
    except (OSError, ValueError) as err:
        problems.append(f"{where}: {entry['sheet']} could not be read as JSON: {err}")
        return None
    found = sheet_prose.check_sheet(sheet)
    if not found and sheet["kind"] not in sheet_prose.PR_KINDS:
        found = [f"it is a {sheet['kind']} sheet, not a pr or stack sheet"]
    elif not found and sheet["prSheet"]["number"] != entry["number"]:
        found = [f"its prSheet.number is {sheet['prSheet']['number']}, not {entry['number']}"]
    problems.extend(f"{where}: {entry['sheet']}: {p}" for p in found)
    store_problems = []
    raw = _load(pathlib.Path(base, entry["store"]), store_problems)
    store = None if store_problems else _store(raw, f"{where} store {entry['store']}", store_problems)
    problems.extend(store_problems)
    if found or store is None:
        return None
    row = {"number": entry["number"], "kind": sheet["kind"], "title": sheet["title"], "link": entry["link"],
           **pr_state(sheet_bytes, store, words["pr"], words["prAnswers"]),
           "mergesAt": order.index(entry["number"]) + 1 if entry["number"] in order else None}
    return {**row, "caption": _row_caption(row, words["index"], _accepting_state(sheet))}


def build_index(advisor, base, answers, words, place):
    """Returns the index sheet as a dict, or raises Refusal with every problem found.

    base is the folder the input's paths are relative to; answers is the --answers file's parsed content ({} when
    there is none); words is the whole words file; place is the picture stager for the questions left on the index.
    """
    problems = []
    if not isinstance(advisor, dict):
        raise Refusal(["the index input must be an object"])
    _check_index_input(advisor, problems)
    given = _store(answers, "the answers file", problems)
    if problems:
        raise Refusal(problems)
    rows = [_index_row(p, base, advisor["mergeOrder"], words, problems) for p in advisor["prs"]]
    probe, cards = _stager(base, {}), []
    for q in advisor["questions"]:
        kept = _counted_answer(q, given["answers"].get(q["id"]), words["answers"]) is None
        images = []
        for n, pic in enumerate(q["pictures"], 1):
            src = (place if kept else probe)(pic["path"])
            if src is None:
                problems.append(f"question {q['id']} picture {n} ({pic['path']}) is a link, or cannot be read as a png, jpg, jpeg, gif or webp file")
            images.append({"src": src, "alt": pic["alt"], **({"caption": pic["caption"]} if "caption" in pic else {})})
        if kept:
            card = {"id": q["id"], "callKind": words["index"]["questionKind"], "warning": True, "question": q["question"],
                    "context": copy.deepcopy(q["context"]), "images": images,
                    "options": [{k: o[k] for k in ("id", "label", "consequence")} for o in q["options"]]}
            cards.append({**card, **({"recommendation": copy.deepcopy(q["recommendation"])} if "recommendation" in q else {})})
    if problems:
        raise Refusal(problems)
    rows.sort(key=lambda r: (r["mergesAt"] is None, r["mergesAt"] or 0))
    sheet = {"schema": "superheroes-sheet/1", "kind": "index", "title": words["index"]["title"], "index": {"rows": rows}, "cards": cards}
    found = sheet_prose.check_sheet(sheet)
    if found:
        raise Refusal(found)
    return sheet


def _load(path, problems, repeats=False):
    """The JSON in a file; None after naming what is wrong. With repeats, a key an object writes twice is a problem too,
    since the later one would silently replace the earlier."""
    again = []

    def pairs(found):
        keys = [k for k, _ in found]
        again.extend(k for k in dict.fromkeys(keys) if keys.count(k) > 1)
        return dict(found)
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs if repeats else None)
    except (OSError, ValueError) as err:
        problems.append(f"{path} could not be read as JSON: {err}")
        return None
    problems.extend(f'the input repeats key "{k}"' for k in dict.fromkeys(again))
    return value


def _write_replacing(out, text):
    """Write beside out, then replace it, so a failed write leaves an earlier sheet intact."""
    tmp = f"{out}.{os.getpid()}.tmp"
    try:
        pathlib.Path(tmp).write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _stager(base, staged):
    """The place() for build: remembers each picture file's bytes in staged by its sheet src; None when it cannot be copied."""
    def place(path):
        if not path or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
            return None
        file = pathlib.Path(base, path)
        try:
            data = file.read_bytes() if file.is_file() else b""
        except OSError:
            data = b""
        if not data:
            return None
        src = f"pictures/{hashlib.sha256(data).hexdigest()[:PICTURE_DIGEST]}{file.suffix.lower()}"
        if not _PICTURE.match(src):
            return None
        staged[src] = data
        return src
    return place


def _write_pictures(folder, staged, created):
    """Writes each staged picture beside the data file unless one is already there; lists what this run created."""
    for src, data in sorted(staged.items()):
        if not (folder / src).exists():
            (folder / src).parent.mkdir(exist_ok=True)
            created.append(folder / src)
            _write_replacing(str(folder / src), data)


def _read_bodies(values, problems):
    """The --pr-body values as a dict of PR number to the body file's text; what is wrong with a value is a problem, never a parser error."""
    bodies, named, repeated = {}, set(), set()
    for value in values or []:
        number, equals, file = value.partition("=")
        if not (equals and re.fullmatch(r"[0-9]+", number) and int(number) >= 1):
            problems.append(f"--pr-body '{value}' must be <PR number>=<file>")
            continue
        n = int(number)
        if n in named:
            if n not in repeated:
                problems.append(f"--pr-body names PR #{n} more than once")
            repeated.add(n)
            continue
        named.add(n)
        try:
            bodies[n] = pathlib.Path(file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            problems.append(f"{file} could not be read as PR #{n}'s body: {err}")
    return bodies


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a PR sheet's data file, or the index's.")
    parser.add_argument("command", choices=["build", "index"])
    parser.add_argument("--record", action="append")
    parser.add_argument("--pr-body", action="append")
    parser.add_argument("--answers")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args, problems = parser.parse_args(argv), []
    if args.command == "build" and not args.record:
        parser.error("the following arguments are required: --record")
    if args.command == "build" and args.answers:
        parser.error("--answers is only for index")
    if args.command == "index" and args.record:
        parser.error("--record is only for build")
    if args.command == "index" and args.pr_body:
        parser.error("--pr-body is only for build")
    try:
        bodies = _read_bodies(args.pr_body, problems) if args.command == "build" else None
        paths = [*args.record, args.input, WORDS_PATH] if args.command == "build" else [args.input, WORDS_PATH, *([args.answers] if args.answers else [])]
        words_at = len(args.record) + 1 if args.command == "build" else 1
        input_at = words_at - 1  # the --input file sits just before the words file in paths
        loaded = [_load_words(args.command, problems) if n == words_at else _load(p, problems, repeats=n == input_at) for n, p in enumerate(paths)]
        if problems:
            raise Refusal(problems)
        staged, created, folder, base = {}, [], pathlib.Path(args.out).parent, pathlib.Path(args.input).parent
        if args.command == "build":
            sheet, extra = build(loaded[:-2], loaded[-2], loaded[-1]["pr"], _stager(base, staged), _earlier_sheet(loaded[-2], base), bodies), {}
        else:
            sheet = build_index(loaded[0], base, loaded[2] if args.answers else {}, loaded[1], _stager(base, staged))
            extra = {"rows": len(sheet["index"]["rows"])}
        fresh = not (folder / "pictures").exists()
        try:
            _write_pictures(folder, staged, created)
            _write_replacing(args.out, json.dumps(sheet, indent=2, ensure_ascii=False) + "\n")
        except BaseException:
            for file in created:
                file.unlink(missing_ok=True)
            if fresh:
                with contextlib.suppress(OSError):
                    (folder / "pictures").rmdir()
            raise
        result, code = {"ok": True, "out": args.out, "cards": len(sheet["cards"]), "pictures": sorted(staged), **extra}, 0
    except (Refusal, OSError) as err:
        result, code = {"ok": False, "problems": err.problems if isinstance(err, Refusal) else [str(err)]}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
