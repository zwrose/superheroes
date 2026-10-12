#!/usr/bin/env python3
"""Builds a PR sheet's data file from the PR's review record and the advisor's input.

CLI:
  pr_sheet.py build --record FILE [--record FILE ...] --input FILE --out FILE

On success it writes the data file to --out, prints {"ok": true, "out": ..., "cards": N} and exits 0.
On a refusal it writes nothing, prints {"ok": false, "problems": [...]} (one line each) and exits 1; an
unreadable or non-JSON file is a refusal problem that names the file.

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
  walk           Optional list of {id, title, pr}; id as above and unique, pr equal to number on a pr or
                 one of prs on a stack.
An option is {id, label, consequence, sendsBack}, all required, sendsBack a boolean, ids unique within the
item. A recommendation is {text, reason, optionId?}; optionId must name one of the item's options and is
refused where the options are "none".
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import review_findings_schema as rfs  # noqa: E402
import review_record  # noqa: E402

WORDS_PATH = os.path.join(_LIB_DIR, os.pardir, "theme", "sheet-words.json")
_FIXED, _SHOWN_WRONG, _CRAFT, _, _RULING = rfs.OUTCOMES
_LEFT = rfs.LEFT_FOR_OWNER
SCHEMA_PATH = os.path.join(_LIB_DIR, os.pardir, "theme", "sheet.schema.json")
with open(SCHEMA_PATH, encoding="utf-8") as _fh:
    _SCHEMA = json.load(_fh)
# The identifier and commit patterns and the lane values are read from the sheet schema, their one home.
_ID = re.compile(_SCHEMA["$defs"]["id"]["pattern"])
_COMMIT = re.compile(_SCHEMA["$defs"]["commit"]["pattern"])
_LANES = tuple(_SCHEMA["$defs"]["prSheet"]["properties"]["whatChanged"]["properties"]["lane"]["enum"])
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
            and lane.get("value") in _LANES and isinstance(lane.get("reason"), (str, type(None)))
            and isinstance(rounds.get("count"), int) and rounds["count"] >= 0 and isinstance(rounds.get("stoppedAtCap"), bool)
            and all(isinstance(v, dict) and v.get("ran") in _RAN and _text(v.get("name"))
                    and (v["ran"] == review_record.RAN_NOT_RUN or _text(v.get("family"))) for v in rec["reviewers"])
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
    for stop in _check_list("walk", adv.get("walk", []), ("id", "title", "pr"), (), problems):
        if allowed is not None and stop["pr"] not in allowed:
            problems.append(f"walk stop {stop['id']} is for PR #{stop['pr']}, which is not in this sheet")
    return allowed


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


def build(records, advisor, words):
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
        "craft": craft, "alreadyDecided": decided, "history": history, "walk": copy.deepcopy(advisor.get("walk", []))}
    if advisor.get("previousCommit"):
        sheet["previousCommit"] = advisor["previousCommit"]
    if stack:
        sheet["prs"] = [{"number": p["number"], "title": p["title"], "commit": by_pr[p["number"]]["finalCommit"]["sha"]}
                        for p in advisor["prs"]]
    return {"schema": "superheroes-sheet/1", "kind": kind, "title": advisor["title"], "prSheet": sheet, "cards": cards}


def _load(path, problems):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        problems.append(f"{path} could not be read as JSON: {err}")


def _write_replacing(out, text):
    """Write UTF-8 text to a temp file beside out, then replace out, so a failed write leaves any earlier sheet intact."""
    directory = os.path.dirname(os.path.abspath(out))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".pr-sheet.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a PR sheet's data file.")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--record", action="append", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args, problems = parser.parse_args(argv), []
    try:
        loaded = [_load(p, problems) for p in [*args.record, args.input, WORDS_PATH]]
        if problems:
            raise Refusal(problems)
        sheet = build(loaded[:-2], loaded[-2], loaded[-1]["pr"])
        _write_replacing(args.out, json.dumps(sheet, indent=2, ensure_ascii=False) + "\n")
        result, code = {"ok": True, "out": args.out, "cards": len(sheet["cards"])}, 0
    except (Refusal, OSError) as err:
        result, code = {"ok": False, "problems": err.problems if isinstance(err, Refusal) else [str(err)]}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
