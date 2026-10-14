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
import contextlib
import datetime
import json
import os
import re
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import canon  # noqa: E402
import control_plane  # noqa: E402
import core_md  # noqa: E402
import definition_doc  # noqa: E402
import project_config  # noqa: E402
import review_findings_schema  # noqa: E402
import review_record  # noqa: E402
import review_record_session  # noqa: E402
import review_seats  # noqa: E402
import session_contract  # noqa: E402

SINCE_KEY = "reviewLearningSince"
PROPOSAL_SCHEMA = "calibration-proposal/1"
COMMIT_MESSAGE = "docs: record an approved calibration change in Canon"
GIT_TIMEOUT_SECONDS = 60  # a stalled signer or commit hook must not hang apply after Canon is appended
_FIXED = review_findings_schema.OUTCOMES[0]
_KEYS = {"risk-and-trust": {"schema", "kind", "half", "value", "ruling"},
         "standing-ruling": {"schema", "kind", "ruling"}}
SUPERSEDES_KEY = "supersedes"  # optional on either kind: the Canon entry id a replacement retires
DIMENSION_SEAT = review_seats.DIMENSION_SEAT
_KNOWN = set(DIMENSION_SEAT) | set(DIMENSION_SEAT.values())


def _canon_id(value):
    """Whether the whole string is one Canon entry id, by Canon's own grammar (canon.ids_in)."""
    return isinstance(value, str) and canon.ids_in("- **%s**" % value) == {value}


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
    if wrote.get("reason") == project_config.REASON_SET_MISMATCH:  # the write precedes its read-back: the setting may have landed
        return _result(False, "partial", "calibration-unconfirmed",
                       "Canon holds %s (commit %s); the calibration write may have landed but its read-back failed, "
                       "so the setting must be read back before anyone relies on it" % (line, commit),
                       canonEntry=line, canonCommit=commit, set=wrote)
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
    kind = p.get("kind") if isinstance(p, dict) else None
    keys = _KEYS.get(kind) if isinstance(kind, str) else None
    if keys is None:
        return "kind must be 'risk-and-trust' or 'standing-ruling'"
    if set(p) - {SUPERSEDES_KEY} != keys or p.get("schema") != PROPOSAL_SCHEMA:
        return "a %s proposal is exactly %s (plus an optional %s) with schema %s" % (
            p["kind"], sorted(keys), SUPERSEDES_KEY, PROPOSAL_SCHEMA)
    if SUPERSEDES_KEY in p and not (_canon_id(p[SUPERSEDES_KEY])):
        return "supersedes must be the id of the Canon entry being replaced (YYYY-MM-DD-xxxxxxxx-N)"
    try:
        canon._field("ruling", p["ruling"] if isinstance(p["ruling"], str) else "")
    except canon.Refusal as exc:
        return exc.payload["detail"]
    if p["kind"] == "risk-and-trust":
        item = project_config._item_by_slug("riskAndTrust")
        if not isinstance(p["half"], str) or project_config.validate_item_value(item, {p["half"]: p["value"]}):
            return "half must name one riskAndTrust half, and value must be that half's valid value"
    return None


def _append_canon(canon_root, session_id, proposal, approval):
    argv = ["append", "--root=" + canon_root, "--session-id=" + str(session_id), "--ground=owner-call",
            "--scope=standing", "--ruling=" + proposal["ruling"], "--owners-words=" + approval["words"],
            "--where=" + approval["where"], "--date=" + approval["date"]]
    if proposal.get(SUPERSEDES_KEY):
        argv.append("--supersedes=" + proposal[SUPERSEDES_KEY])
    return canon.cmd_append(canon._parser().parse_args(argv))


def _run_git(cwd, *args):
    """Canon's git, bounded: the same invocation as canon._git plus a timeout (canon.py stays untouched)."""
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                          timeout=GIT_TIMEOUT_SECONDS, env=definition_doc._scrubbed_git_env())


@contextlib.contextmanager
def _scrubbed_environ():
    """The ambient environment minus the git routing variables `_run_git` removes, for the span of the
    block, so a shared probe that cannot take an env acts on the repository it was given."""
    scrubbed = definition_doc._scrubbed_git_env()
    gone = {k: v for k, v in os.environ.items() if k not in scrubbed}
    for k in gone:
        del os.environ[k]
    try:
        yield
    finally:
        os.environ.update(gone)


def _commit_canon(res, line):
    """Canon's write procedure steps 7-8: commit only Canon's paths, then see the line in HEAD."""
    git_root = res["gitRoot"]
    rel = os.path.relpath(res["path"], git_root).replace(os.sep, "/")
    try:
        before = _run_git(git_root, "rev-parse", "HEAD")
        before_head = before.stdout.strip() if before.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        before_head = None
    failure = None
    try:
        for args in (("add", "--", *res["commitPaths"]), ("commit", "-m", COMMIT_MESSAGE, "--", *res["commitPaths"])):
            got = _run_git(git_root, *args)
            if got.returncode != 0:
                failure = "git %s failed: %s" % (args[0], (got.stderr or got.stdout).strip())
                break
    except subprocess.TimeoutExpired as exc:
        failure = "git %s timed out after %ss" % (exc.cmd[3] if len(exc.cmd) > 3 else "command", GIT_TIMEOUT_SECONDS)
    except OSError as exc:
        failure = "git could not be run (%s: %s)" % (type(exc).__name__, exc)
    if failure:
        # a commit that errored or timed out continues only when HEAD shows it landed (the one shared proof)
        with _scrubbed_environ():
            landed = project_config._commit_landed(git_root, rel, before_head, [line])
        if landed is not True:
            return None, failure + ("; git could not say whether the commit landed" if landed is None else "")
    try:
        shown = _run_git(git_root, "show", "HEAD:" + rel)
        if shown.returncode != 0 or line not in shown.stdout.splitlines():
            return None, "HEAD:%s does not hold the appended line" % rel
        return _run_git(git_root, "rev-parse", "HEAD").stdout.strip(), None
    except subprocess.TimeoutExpired as exc:
        return None, "git %s timed out after %ss" % (exc.cmd[3] if len(exc.cmd) > 3 else "command", GIT_TIMEOUT_SECONDS)
    except OSError as exc:
        return None, "git could not be run (%s: %s)" % (type(exc).__name__, exc)


def apply(cwd, proposal, approval, *, canon_root, session_id, root=None):
    """Record an owner-approved calibration change. The caller applies between reviews: the command
    does not check for a running review, so the advisor runs it only when no review loop is in flight.

    Canon's append path cannot carry a store root (`canon._locate` resolves the ambient store), so a
    `root` naming any other store is refused (`store-override-unsupported`) before anything is written,
    rather than recording the approval in one store and the calibration in another."""
    # axis: a calibration change is written only on the owner's exact yes, with their words, place and date — see bite-proof record wo_a_1718_no-owner-yes
    if not _owner_yes(approval):
        return _result(False, "refused", "no-owner-yes", "no approval with answer 'yes', words, where and an ISO date")
    problem = _proposal_problem(proposal)
    if problem:
        return _result(False, "refused", "proposal-invalid", problem)
    if root is not None and os.path.realpath(os.path.expanduser(root)) != control_plane.store_root():
        return _result(False, "refused", "store-override-unsupported",
                       "Canon's append cannot take a store root; --root %s is not the ambient store" % root)
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
    if wrote.get("reason") == project_config.REASON_SET_MISMATCH:  # the write precedes its read-back: the setting may have landed
        return _result(False, "partial", "calibration-unconfirmed",
                       "Canon holds %s (commit %s); the calibration write may have landed but its read-back failed, "
                       "so the setting must be read back before anyone relies on it" % (line, commit),
                       canonEntry=line, canonCommit=commit, set=wrote)
    if wrote.get("action") not in ("written", "noop"):
        return _result(False, "partial", "calibration-not-written",
                       "Canon holds %s (commit %s); the calibration write returned %s"
                       % (line, commit, wrote.get("reason") or wrote.get("action")),
                       canonEntry=line, canonCommit=commit, set=wrote)
    return _result(True, "applied", canonEntry=line, canonCommit=commit, calibration="risk-and-trust", set=wrote)


# --- the tally (I4) ---

def _stamp(value, day):
    """The full instant a `writtenAt` names (naive reads as UTC); the day's midnight when only the date parses."""
    try:
        at = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00").replace(" ", "T", 1))
        return at if at.tzinfo else at.replace(tzinfo=datetime.timezone.utc)
    except (ValueError, AttributeError):
        return datetime.datetime.combine(day, datetime.time(), datetime.timezone.utc)


def _seats(name):
    """The seats a reviewer row name or finding `reviewer` string names (rule 3)."""
    out = []
    # a merged finding label joins its dimensions with " + " (panel_tally._merge_dims, verification._union_dimensions)
    for part in re.split(r"[,+]", name) if isinstance(name, str) else []:
        part = re.sub(r"\s*\(round \d+\)$", "", part.strip()).strip().lower()
        tokens = part.split()
        if len(tokens) > 1 and tokens[-1] in _KNOWN:
            part = tokens[-1]
        seat = DIMENSION_SEAT.get(part, part)
        if seat and seat not in out:
            out.append(seat)
    return out


def _id_ok(value):
    """An identity field that is absent or hashable (a string or int)."""
    return value is None or isinstance(value, (str, int))


def _finding_ok(f):
    """A finding row with a hashable identity and an outcome that is null (undecided) or a known one."""
    if not isinstance(f, dict):
        return False
    key = f.get(session_contract.FINDING_KEY_FIELD) or f.get("id")
    return isinstance(key, (str, int)) and _id_ok(f.get("id")) and _id_ok(f.get(session_contract.FINDING_KEY_FIELD)) and (f.get("outcome") is None or (
        isinstance(f["outcome"], str) and f["outcome"] in review_findings_schema.OUTCOME_SET))


def _merged_member(f):
    """True for a member row folded into a representative; the representative carries the catch."""
    return review_record_session.merged_into(f.get("reason")) is not None


def tally(records, escapes, since, *, until=None, window_days=None):
    """Count seat reviews and catches per PR. A PR is dated by its earliest review record and counts only when
    that date falls inside the counting range (on or after the adoption day and inside the window); a PR first
    reviewed earlier is left out whole. A counted PR's reviews are its records (up to `until`) with a seat row
    that ran, and its catches are read from its latest record alone: each distinct fixed finding that is not a
    merged member, credited to the seat its lens names. `records` is every review record of each PR it covers,
    earliest included: a record whose `previousRecord` is not among them reads `incomplete-evidence`, never a count.
    A catch is credited to the seat whose lens the finding names (the record's finding `reviewer` is its
    dimension, not the dispatch that raised it)."""
    end = _day(until) if until is not None else datetime.datetime.now(datetime.timezone.utc).date()
    left = {"beforeWindow": 0, "afterWindow": 0, "undated": 0, "malformed": 0}
    out = {"since": since, "window": {"from": None, "until": end.isoformat() if end else until},
           "measured": False, "reason": None, "seats": {}, "unattributedCatches": None,
           "escapes": {"missed": None, "seenAndLeft": None}, "leftOut": dict.fromkeys(left)}
    if since is None:
        return dict(out, reason="no-adoption-day")
    start = _day(since)
    bad_window = window_days is not None and not (isinstance(window_days, int) and window_days > 0)
    if start is None or end is None or bad_window or end < start:  # an `until` before the adoption day measures nothing
        return dict(out, reason="bad-input")
    first = end - datetime.timedelta(days=window_days - 1) if window_days else start
    low = max(first, start)  # nothing dated before the adoption day ever counts (rule 1, 7)
    out.update(measured=first >= start, reason=None if first >= start else "short-of-window")
    out["window"]["from"] = first.isoformat()

    def outside(d):
        # axis: a review event dated before the adoption day never counts — see bite-proof record wo_a_1718_tally-before-adoption
        return "beforeWindow" if d < low else "afterWindow" if d > end else None

    reviews, caught = collections.defaultdict(set), collections.Counter()
    unattributed, incomplete = 0, False  # incomplete: evidence went missing, so no count is a zero
    by_pr = {}
    given = {v for r in records if isinstance(r, dict) for v in (r.get("url"), r.get("id")) if isinstance(v, (str, int))} \
        if isinstance(records, list) else set()
    for rec in records if isinstance(records, list) else []:
        day = _day(rec.get("writtenAt"), whole=False) if isinstance(rec, dict) else None
        if not isinstance(rec, dict):
            left["malformed"] += 1
            incomplete = True
            continue
        if day is None:
            left["undated"] += 1
            incomplete = True
            continue
        # a record that lost its reviewers or findings (a refusal body, a partial read) is unknown coverage, not an empty review
        if rec.get("ok") is False or not isinstance(rec.get("reviewers"), list) or not isinstance(rec.get("findings"), list):
            left["malformed"] += 1
            incomplete = True
            continue
        if "previousRecord" not in rec:  # the writer always emits it: absence is unknown ancestry, not a first record
            left["malformed"] += 1
            incomplete = True
            continue
        prev = rec["previousRecord"]  # the link to the record before it, or null for the first
        if prev is not None and not (isinstance(prev, dict) and any(isinstance(prev.get(k), (str, int)) and prev.get(k) in given for k in ("url", "id"))):
            left["malformed"] += 1
            incomplete = True
            continue
        pr, session = rec.get("pr"), rec.get("sessionId")  # the review's identity: without both, reviews and catches collapse together
        if not (isinstance(pr, (str, int)) and not isinstance(pr, bool) and pr != ""
                and isinstance(session, str) and session.strip()):
            left["malformed"] += 1
            incomplete = True
            continue
        if any(not (isinstance(r, dict) and r.get("ran") in review_record.RAN_STATES and isinstance(r.get("name"), str))
               for r in rec["reviewers"]) or any(not _finding_ok(f) for f in rec["findings"]):
            left["malformed"] += 1  # a damaged row is missing evidence, not a review that caught nothing
            incomplete = True
            continue
        if day > end:
            left["afterWindow"] += 1
            continue
        by_pr.setdefault(pr, []).append((_stamp(rec.get("writtenAt"), day), len(by_pr.get(pr, [])), day, rec))
    for recs in by_pr.values():
        recs.sort(key=lambda t: t[:2])
        # a PR first reviewed before the adoption day is left out whole
        if recs[0][2] < low:
            left["beforeWindow"] += len(recs)
            continue
        for _, _, _, rec in recs:
            for row in rec["reviewers"]:
                if row["ran"] != review_record.RAN_NOT_RUN:
                    for seat in _seats(row.get("name")):
                        reviews[seat].add((rec["pr"], rec["sessionId"]))
        fixed = {}  # the latest record's catches, one per findingKey
        for f in recs[-1][3]["findings"]:
            if f.get("outcome") == _FIXED and not _merged_member(f):
                fixed.setdefault(f.get(session_contract.FINDING_KEY_FIELD) or f.get("id"), f)
        for f in fixed.values():
            seats = _seats(f.get("reviewer"))
            unattributed += not seats
            caught.update(seats)
    counts = {"missed": 0, "seenAndLeft": 0}
    for esc in escapes if isinstance(escapes, list) else []:
        day = _day(esc.get("reviewedAt")) if isinstance(esc, dict) else None
        call = esc.get("call") if isinstance(esc, dict) else None
        label = {"missed": "missed", "seen-and-left": "seenAndLeft"}.get(call) if isinstance(call, str) else None
        if day is None and isinstance(esc, dict):
            left["undated"] += 1
            incomplete = True
        elif label is None:
            left["malformed"] += 1
            incomplete = True
        elif outside(day):
            left[outside(day)] += 1
        else:
            counts[label] += 1
    if incomplete:  # missing evidence reads unmeasured, never zero (owner-decisions.md, the gardening pass)
        return dict(out, measured=False, reason=out["reason"] or "incomplete-evidence", leftOut=left)
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
