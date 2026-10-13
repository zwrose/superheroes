#!/usr/bin/env python3
"""Builds a PR sheet's data file from the PR's review record and the advisor's input.

CLI:
  pr_sheet.py build --record FILE [--record FILE ...] --input FILE --out FILE
  pr_sheet.py index --input FILE [--answers FILE] --out FILE

On success it writes the data file to --out and each walk picture it could copy to pictures/ beside it, prints
{"ok": true, "out": ..., "cards": N, "pictures": [the sheet's picture paths]} and exits 0.
On a refusal it writes nothing, prints {"ok": false, "problems": [...]} (one line each) and exits 1; an
unreadable or non-JSON file is a refusal problem that names the file. `index` prints
{"ok": true, "out": ..., "cards": N, "pictures": [...], "rows": N} on success and refuses the same way; if
writing fails it removes the pictures that run created. --record is for `build` only, --answers for `index` only.

A record file holds what `review_record.py read --pr N` prints, or the bare record. Every fact is copied
from the records or the advisor's input, and each finding lands where its outcome names: fixed in "caught",
craft in "craft", ruling in "alreadyDecided", shown-wrong in "history", left-for-owner as a card. The words
come from the "pr" block of theme/sheet-words.json.

The advisor's input is one JSON object; any key not listed is refused.
  schema         "pr-sheet-input/1".
  kind           "pr" for one PR, or "stack" for a stack that merges whole.
  number         The PR's number, or the stack's number. An integer, 1 or more.
  title, summary Non-empty strings: the sheet's title, and what changed in one line.
  previousCommit Optional. Null, or a commit id (7 to 40 lowercase hex) when this sheet replaces an earlier one.
  prs            Required on a stack, refused on a pr: at least 2 {number, title}, bottom PR first.
  leftovers      Optional object. A key names a left-for-owner finding by its findingKey, or by its id when
                 no other left-for-owner finding shares it ("<pr number>:<key>" on a stack). A value is {"options": ..., "recommendation": ...}: options is "leftover" (the
                 default, the words' three options), "none", or a list of options.
  items          Optional list. Each is {id, kind, title, ifLeft, options, recommendation?} with options
                 "none" or a list; id matches ^[a-z0-9][a-z0-9-]*$ and is unique among the items.
  closesSpec     Optional. Null, or {"spec": ..., "receipt": ...}.
  walk           Optional object {open, note?, picturesFrom, stops}: open is {label, url?, detail?} with url
                 http(s); stops is at least 1 of {id, title, pr, group, kind, steps?, expect, optional?, notWalked?,
                 pictures?}: id as above and unique, pr equal to number on a pr or one of prs on a stack, kind
                 "try" (steps, at least 1) or "look" (no steps), optional a boolean, pictures a list of
                 {path, alt, caption?}. A path is a file (png, jpg, jpeg, gif or webp), absolute or relative to the
                 input's folder; a picture whose path is a link or cannot be read as one is shown as missing.
An option is {id, label, consequence, sendsBack}, all required, sendsBack a boolean, ids unique within the
item. A recommendation is {text, reason, optionId?}; optionId must name one of the item's options and is
refused where the options are "none".

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


def _fill(text, **slots):
    return re.sub(r"\{(\w+)\}", lambda m: str(slots.get(m.group(1), m.group(0))), text)


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
    """The options a value gives: "none", "leftover" (on a leftover only) or a list; None when it is none of these."""
    if given == "none":
        return []
    if given == "leftover" and leftover:
        return words["leftoverOptions"]
    return given if isinstance(given, list) else None


def _check_call(where, call, words, problems, leftover):
    given = call.get("options", "leftover") if leftover else call["options"]
    opts = _options(given, words, leftover)
    if opts is None:
        problems.append(f'{where}: options must be {"leftover, " if leftover else ""}none or a list of options')
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
        if not (all(_text(e[k]) for k in required if k not in ("pr", "options", "sendsBack")) and _ID.match(e["id"])):
            problems.append(f"{w} needs an id of lowercase letters, digits and hyphens and non-empty text")
        elif e["id"] in ids:
            problems.append(f"{w} repeats the id {e['id']}")
        else:
            good.append(e)
        ids.append(e["id"])
    return good


def _check_input(adv, words, problems):
    """Collects the input's problems; returns the PR numbers the sheet covers, or None when unknown."""
    optional = ("previousCommit", "prs", "leftovers", "items", "closesSpec", "walk")
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
        if _keys(f"leftovers {k}", call, (), ("options", "recommendation"), problems):
            _check_call(f"leftovers {k}", call, words, problems, True)
    for it in _check_list("items", adv.get("items", []), ("id", "kind", "title", "ifLeft", "options"),
                          ("recommendation",), problems):
        _check_call(f"items {it['id']}", it, words, problems, False)
    spec = adv.get("closesSpec")
    if spec is not None and _keys("closesSpec", spec, ("spec", "receipt"), (), problems) \
            and not (_text(spec["spec"]) and _text(spec["receipt"])):
        problems.append("closesSpec needs a spec and a receipt, both non-empty strings")
    if "walk" in adv:
        _check_walk(adv["walk"], allowed, problems)
    return allowed


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


def build(records, advisor, words, place=None):
    """Returns the sheet's data file as a dict, or raises Refusal with every problem found."""
    problems = []
    if not isinstance(advisor, dict):
        raise Refusal(["the advisor's input must be an object"])
    allowed = _check_input(advisor, words, problems)
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
    leftovers = advisor.get("leftovers", {})
    named = {}
    for r in recs:
        for f in r["findings"]:
            if isinstance(f, dict) and f.get("outcome") == _LEFT:
                for k in _lookups(kind, r["pr"], f):
                    named[k] = named.get(k, 0) + 1
    if isinstance(leftovers, dict):
        problems.extend(f"leftovers key {k!r} names no left-for-owner finding" for k in leftovers if k not in named)
        problems.extend(f"leftovers key {k!r} names {named[k]} left-for-owner findings; use a finding's findingKey"
                        for k in leftovers if named.get(k, 0) > 1)
    if problems:
        raise Refusal(problems)
    stack = kind == "stack"
    by_pr = {r["pr"]: r for r in recs}
    recs = [by_pr[n] for n in allowed] if stack else recs
    top, tag = recs[-1], (lambda r: f"#{r['pr']}: " if stack else "")
    cards = []
    for r in recs:
        for f in (f for f in r["findings"] if f["outcome"] == _LEFT):
            call = _leftover_call(kind, r["pr"], f, leftovers)
            options = _options(call.get("options", "leftover"), words, True)
            cards.append(_card("f-", r["pr"], f.get("findingKey") or f["id"],
                               words["leftoverKind"] + (f" · #{r['pr']}" if stack else ""), _title(f),
                               [_section(words["ifLeft"], "paragraph", f["consequence"])], options, call.get("recommendation")))
    for it in advisor.get("items", []):
        cards.append(_card("i-", number, it["id"], it["kind"], it["title"], [_section(words["ifLeft"], "paragraph", it["ifLeft"])],
                           _options(it["options"], words, False), it.get("recommendation")))
    spec = advisor.get("closesSpec")
    if spec:
        context = [_section(words["ifLeft"], "paragraph", words["closureIfLeft"]),
                   _section(words["closureReceipt"], "quote", spec["receipt"])]
        cards.append(_card("c-", number, spec["spec"], words["closureKind"],
                           _fill(words["closureQuestion"], spec=spec["spec"]), context, [], None))
    if len({c["id"] for c in cards}) != len(cards):
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
        for m in (r.get("whatIsMissing") or []) if r.get("status") == "not-reviewed" else []:
            lines.append(_fill(words["historyIncomplete"], what=m))
        if stack:
            lines.append(_fill(words["historyChecks"], state=r["ci"]["state"], commit=r["ci"].get("sha") or "no commit"))
        for v in r["reviewers"]:
            if v["ran"] != review_record.RAN_NOT_RUN and v.get("coversFinalCommit") is False:
                lines.append(_fill(words["historyEarlierCommit"], name=v["name"], commit=v.get("commit") or "unknown"))
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
        "craft": craft, "alreadyDecided": decided, "history": history}
    if "walk" in advisor:
        sheet["walk"] = _walk(advisor["walk"], place)
    if advisor.get("previousCommit"):
        sheet["previousCommit"] = advisor["previousCommit"]
    if stack:
        sheet["prs"] = [{"number": p["number"], "title": p["title"], "commit": by_pr[p["number"]]["finalCommit"]["sha"]}
                        for p in advisor["prs"]]
    return {"schema": "superheroes-sheet/1", "kind": kind, "title": advisor["title"], "prSheet": sheet, "cards": cards}


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
    sends the PR back, else ready when a Merge verdict stands, else needs-you. A Merge stands only on this exact
    sheet, with every item accepted, no walk Problem left without a follow-up fix, and a covers that names exactly
    the answers the store holds now. words is the "pr" block of sheet-words.json and answer_words its "prAnswers" block,
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
        if not (sheet_prose.fits_definition("walkAnswer", doc) and doc["answer"] in words["walkAnswers"][stop["kind"]] and (doc["fix"] is None or doc["fix"] in fixes)):
            # As the page restores it: a stored Problem whose fix is no longer offered, or whose document is malformed, stays a Problem with no fix and keeps blocking.
            if isinstance(doc, dict) and doc.get("answer") == "problem":
                walked, blocking = walked + 1, True
            continue
        walked += doc["answer"] in words["walkedAnswers"]
        if doc["answer"] == "problem":
            fix = fixes.get(doc["fix"])
            blocking = blocking or fix is None or fix.get("sendsBack") is not False
            sends_back = sends_back or (fix is not None and fix.get("sendsBack") is True)
    revisions = [counted[card["id"]] and counted[card["id"]].get("revision") for card in cards]
    covered = None if not all(revisions) else {f"answers/{card['id']}@{rev}" for card, rev in zip(cards, revisions)}
    verdict = _collection(store, "verdict").get(digest)
    stands = (sheet_prose.fits_definition("verdict", verdict) and verdict["sheet"] == digest and verdict["verdict"] == "merge"
              and accepted == len(cards) and not blocking
              and covered is not None and set(verdict["covers"]) == covered)
    state = "being-fixed" if sends_back else "ready" if stands else "needs-you"
    return {"state": state, "accepted": accepted, "total": len(cards), "walked": walked, "walkTotal": len(stops)}


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


def _row_caption(row, words):
    """The line under an index row's name, the one home of the rule: what is accepted (or nothing to accept), what is walked
    when the PR has a walk, then where the PR stands, with the merge place on a PR that needs the owner, joined with " · "."""
    parts = [_fill(words["accepted"], accepted=row["accepted"], total=row["total"]) if row["total"] else words["nothingToAccept"]]
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
    return {**row, "caption": _row_caption(row, words["index"])}


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


def _load(path, problems):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        problems.append(f"{path} could not be read as JSON: {err}")


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a PR sheet's data file, or the index's.")
    parser.add_argument("command", choices=["build", "index"])
    parser.add_argument("--record", action="append")
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
    try:
        paths = [*args.record, args.input, WORDS_PATH] if args.command == "build" else [args.input, WORDS_PATH, *([args.answers] if args.answers else [])]
        loaded = [_load(p, problems) for p in paths]
        if problems:
            raise Refusal(problems)
        staged, created, folder, base = {}, [], pathlib.Path(args.out).parent, pathlib.Path(args.input).parent
        if args.command == "build":
            sheet, extra = build(loaded[:-2], loaded[-2], loaded[-1]["pr"], _stager(base, staged)), {}
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
