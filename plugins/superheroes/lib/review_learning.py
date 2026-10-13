#!/usr/bin/env python3
"""The review learning loop's code (#1718, review C10): the adoption day, the owner-approved
calibration change, and the seat tally that starts counting at the adoption day.

CLI (`python3 -B lib/review_learning.py <verb>`; one JSON object on stdout; exit 0 on ok, 1 on a refusal):
  adopt --cwd D [--root R] --date YYYY-MM-DD      # record the adoption day once
  since --cwd D [--root R]                        # read it back
  apply --cwd D [--root R] --canon-root R --session-id S --proposal F --approval F
  tally --records F --escapes F (--since YYYY-MM-DD | --cwd D [--root R]) [--until D] [--window-days N]
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import canon  # noqa: E402
import core_md  # noqa: E402
import project_config  # noqa: E402
import review_record  # noqa: E402

SINCE_KEY = "reviewLearningSince"
PROPOSAL_SCHEMA = "calibration-proposal/1"
COMMIT_MESSAGE = "docs: record an approved calibration change in Canon"
HALVES = ("riskAreas", "threatModel")
_KEYS = {"risk-and-trust": {"schema", "kind", "half", "value", "ruling"},
         "standing-ruling": {"schema", "kind", "ruling"}}
DIMENSION_SEAT = {"code": "code-reviewer", "test": "test-role", "architecture": "architecture-reviewer",
                  "security": "security-reviewer", "failure-mode": "premortem-reviewer"}
_KNOWN = set(DIMENSION_SEAT) | set(DIMENSION_SEAT.values())


def _result(ok, outcome, reason=None, detail=None, **extra):
    return {"ok": ok, "outcome": outcome, "reason": reason, "detail": detail, **extra}


def _day(value, whole=True):
    """The date a string is (or, when not `whole`, starts with), or None."""
    match = re.fullmatch if whole else re.match
    if not isinstance(value, str) or not match(r"\d{4}-\d{2}-\d{2}" + ("" if whole else r"(?=$|[T ])"), value):
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        return None


# --- the adoption day (I3) ---

def adoption_day(cwd, root=None):
    facts = core_md.read(cwd, root)
    mapping = facts.get("projectConfiguration") if facts else None
    if not isinstance(mapping, dict) or SINCE_KEY not in mapping:
        return {"since": None, "reason": "not-recorded"}
    stored = mapping[SINCE_KEY]
    return {"since": stored, "reason": None} if _day(stored) else {"since": None, "reason": "malformed"}


def record_adoption_day(cwd, day, root=None):
    if _day(day) is None:
        return _result(False, "refused", "bad-date", "%r is not an ISO date (YYYY-MM-DD)" % (day,))
    cur = adoption_day(cwd, root)
    if cur["since"] == day:
        return _result(True, "unchanged", since=day)
    # axis: the adoption day is set once; a different day never overwrites the stored one — see bite-proof record wo_a_1718_adopt-set-once
    wrote = core_md.write_project_config_item_if(cwd, SINCE_KEY, day, expected=None, root=root)
    if wrote.get("reason") == "item-changed":
        return _result(False, "refused", "adoption-day-already-recorded", wrote.get("observed"),
                       since=wrote.get("observed"))
    if wrote.get("action") not in ("written", "noop"):
        return _result(False, "refused", wrote.get("reason") or wrote.get("action"), wrote)
    return _result(True, "recorded", since=day)


# --- the owner-approved calibration change (I1, I2) ---

def _owner_yes(approval):
    return (isinstance(approval, dict) and approval.get("answer") == "yes"
            and all(isinstance(approval.get(k), str) and approval[k].strip() for k in ("words", "where"))
            and _day(approval.get("date")) is not None)


def _proposal_problem(p):
    """What is wrong with the whole proposal, or None. Nothing is written before this is None."""
    keys = _KEYS.get(p.get("kind")) if isinstance(p, dict) else None
    if keys is None:
        return "kind must be 'risk-and-trust' or 'standing-ruling'"
    if set(p) != keys or p["schema"] != PROPOSAL_SCHEMA:
        return "a %s proposal is exactly %s with schema %s" % (p["kind"], sorted(keys), PROPOSAL_SCHEMA)
    try:
        canon._field("ruling", p["ruling"] if isinstance(p["ruling"], str) else "")
    except canon.Refusal as exc:
        return exc.payload["detail"]
    if p["kind"] == "risk-and-trust":
        item = project_config._item_by_slug("riskAndTrust")
        if p["half"] not in HALVES or project_config.validate_item_value(item, {p["half"]: p["value"]}):
            return "half must be riskAreas or threatModel, and value must be that half's valid value"
    return None


def _append_canon(canon_root, session_id, proposal, approval):
    argv = ["append", "--root=" + canon_root, "--session-id=" + str(session_id), "--ground=owner-call",
            "--scope=standing", "--ruling=" + proposal["ruling"], "--owners-words=" + approval["words"],
            "--where=" + approval["where"], "--date=" + approval["date"]]
    return canon.cmd_append(canon._parser().parse_args(argv))


def _commit_canon(res, line):
    """Canon's write procedure steps 7-8: commit only Canon's paths, then see the line in HEAD."""
    git_root = res["gitRoot"]
    rel = os.path.relpath(res["path"], git_root).replace(os.sep, "/")
    for args in (("add", "--", *res["commitPaths"]), ("commit", "-m", COMMIT_MESSAGE, "--", *res["commitPaths"])):
        got = canon._git(git_root, *args)
        if got.returncode != 0:
            return None, "git %s failed: %s" % (args[0], (got.stderr or got.stdout).strip())
    shown = canon._git(git_root, "show", "HEAD:" + rel)
    if shown.returncode != 0 or line not in shown.stdout.splitlines():
        return None, "HEAD:%s does not hold the appended line" % rel
    return canon._git(git_root, "rev-parse", "HEAD").stdout.strip(), None


def apply(cwd, proposal, approval, *, canon_root, session_id, root=None):
    # axis: a calibration change is written only on the owner's exact yes, with their words, place and date — see bite-proof record wo_a_1718_no-owner-yes
    if not _owner_yes(approval):
        return _result(False, "refused", "no-owner-yes", "no approval with answer 'yes', words, where and an ISO date")
    problem = _proposal_problem(proposal)
    if problem:
        return _result(False, "refused", "proposal-invalid", problem)
    try:
        res = _append_canon(canon_root, session_id, proposal, approval)
    except canon.Refusal as exc:
        reason = "proposal-invalid" if exc.payload["reason"] == "canon-stays-out" else "canon-refused"
        return _result(False, "refused", reason, "%s: %s" % (exc.payload["reason"], exc.payload["detail"]))
    except OSError as exc:
        return _result(False, "canon-not-committed", "canon-write-failed", "%s: %s" % (type(exc).__name__, exc))
    line = res["appended"][0]
    commit, failure = _commit_canon(res, line)
    if failure:
        return _result(False, "canon-not-committed", "canon-commit-failed", failure, canonEntry=line)
    if proposal["kind"] == "standing-ruling":
        return _result(True, "applied", canonEntry=line, canonCommit=commit, calibration="canon-only")
    half = proposal["half"]
    wrote = project_config.set_item(cwd, "riskAndTrust", {half: proposal["value"]}, root=root)
    if wrote.get("action") not in ("written", "noop"):
        return _result(False, "partial", "calibration-not-written",
                       "Canon holds %s (commit %s); the calibration write returned %s"
                       % (line, commit, wrote.get("reason") or wrote.get("action")),
                       canonEntry=line, canonCommit=commit, set=wrote)
    return _result(True, "applied", canonEntry=line, canonCommit=commit, calibration="risk-and-trust", set=wrote)


# --- the tally (I4) ---

def _seats(name):
    """The seats a reviewer row name or finding `reviewer` string names (rule 3)."""
    out = []
    for part in name.split(",") if isinstance(name, str) else []:
        part = re.sub(r"\s*\(round \d+\)$", "", part.strip()).strip().lower()
        tokens = part.split()
        if len(tokens) > 1 and tokens[-1] in _KNOWN:
            part = tokens[-1]
        seat = DIMENSION_SEAT.get(part, part)
        if seat and seat not in out:
            out.append(seat)
    return out


def tally(records, escapes, since, *, until=None, window_days=None):
    end = _day(until) if until is not None else datetime.datetime.now(datetime.timezone.utc).date()
    left = {"beforeWindow": 0, "afterWindow": 0, "undated": 0, "malformed": 0}
    out = {"since": since, "window": {"from": None, "until": end.isoformat() if end else until},
           "measured": False, "reason": None, "seats": {}, "unattributedCatches": None,
           "escapes": {"missed": None, "seenAndLeft": None}, "leftOut": dict.fromkeys(left)}
    if since is None:
        return dict(out, reason="no-adoption-day")
    start = _day(since)
    bad_window = window_days is not None and not (isinstance(window_days, int) and window_days > 0)
    if start is None or end is None or bad_window:
        return dict(out, reason="bad-input")
    first = end - datetime.timedelta(days=window_days - 1) if window_days else start
    low = max(first, start)  # nothing dated before the adoption day ever counts (rule 1, 7)
    out.update(measured=first >= start, reason=None if first >= start else "short-of-window")
    out["window"]["from"] = first.isoformat()

    def outside(d):
        # axis: a review event dated before the adoption day never counts — see bite-proof record wo_a_1718_tally-before-adoption
        return "beforeWindow" if d < low else "afterWindow" if d > end else None

    reviews, caught = collections.defaultdict(set), collections.Counter()
    seen, unattributed = {}, 0
    for rec in records if isinstance(records, list) else []:
        day = _day(rec.get("writtenAt"), whole=False) if isinstance(rec, dict) else None
        if not isinstance(rec, dict):
            left["malformed"] += 1
            continue
        if day is None:
            left["undated"] += 1
            continue
        if outside(day):
            left[outside(day)] += 1
        for row in rec.get("reviewers") or []:
            if (not outside(day) and isinstance(row, dict) and row.get("ran") in review_record.RAN_STATES
                    and row["ran"] != review_record.RAN_NOT_RUN):
                for seat in _seats(row.get("name")):
                    reviews[seat].add((rec.get("pr"), rec.get("sessionId")))
        for f in rec.get("findings") or []:
            key = f.get("findingKey") or f.get("id") if isinstance(f, dict) else None
            if key is not None:
                hit = seen.setdefault((rec.get("pr"), key), {"fixed": False, "days": {}})
                hit["fixed"] = hit["fixed"] or f.get("outcome") == "fixed"
                hit["days"].setdefault(day, set()).update(_seats(f.get("reviewer")))
    for hit in seen.values():  # a catch is dated by the earliest record that carries it, and counts once
        earliest = min(hit["days"])
        if hit["fixed"] and not outside(earliest):
            unattributed += not hit["days"][earliest]
            caught.update(hit["days"][earliest])
    counts = {"missed": 0, "seenAndLeft": 0}
    for esc in escapes if isinstance(escapes, list) else []:
        day = _day(esc.get("reviewedAt")) if isinstance(esc, dict) else None
        label = {"missed": "missed", "seen-and-left": "seenAndLeft"}.get(esc.get("call")) if isinstance(esc, dict) else None
        if day is None and isinstance(esc, dict):
            left["undated"] += 1
        elif label is None:
            left["malformed"] += 1
        elif outside(day):
            left[outside(day)] += 1
        else:
            counts[label] += 1
    out.update(seats={s: {"reviews": len(reviews[s]), "caught": caught[s]} for s in sorted(set(reviews) | set(caught))},
               unattributedCatches=unattributed, escapes=counts, leftOut=left)
    return out


# --- the CLI ---

def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _parser():
    p = argparse.ArgumentParser(prog="review_learning.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for name in ("adopt", "since", "apply", "tally"):
        s = sub.add_parser(name)
        s.add_argument("--root")
        if name != "tally":
            s.add_argument("--cwd", required=True)
    sub.choices["adopt"].add_argument("--date", required=True)
    for f in ("canon-root", "session-id", "proposal", "approval"):
        sub.choices["apply"].add_argument("--" + f, required=True)
    t = sub.choices["tally"]
    t.add_argument("--records", required=True)
    t.add_argument("--escapes", required=True)
    t.add_argument("--cwd")
    t.add_argument("--since")
    t.add_argument("--until")
    t.add_argument("--window-days", type=int)
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] not in ("adopt", "since", "apply", "tally"):
        argv = argv[1:]  # a full sys.argv, program name first
    a = _parser().parse_args(argv)
    if a.verb == "adopt":
        out = record_adoption_day(a.cwd, a.date, a.root)
    elif a.verb == "since":
        got = adoption_day(a.cwd, a.root)
        out = _result(got["reason"] != "malformed", None, got["reason"], None, since=got["since"])
    elif a.verb == "apply":
        out = apply(a.cwd, _load(a.proposal), _load(a.approval), canon_root=a.canon_root,
                    session_id=a.session_id, root=a.root)
    else:
        records, escapes = _load(a.records), _load(a.escapes)
        if not isinstance(records, list) or not isinstance(escapes, list) or bool(a.since) == bool(a.cwd):
            out = _result(False, "refused", "bad-input", "--records and --escapes are JSON lists; give --since or --cwd")
        else:
            out = tally(records, escapes, a.since or adoption_day(a.cwd, a.root)["since"],
                        until=a.until, window_days=a.window_days)
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
