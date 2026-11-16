#!/usr/bin/env python3
"""The review-loop measures: one fixed-shape row per gardening window, appended to a JSON-lines table in the
project store, mirrored as a table in the gardening record and charted across windows. It gates nothing: the
owner and the advisor read it by hand at the gardening pass, and nothing reads it between passes.

CLI (`python3 -B lib/review_measures.py <verb>`; one JSON object on stdout; exit 0 on ok, 1 on a refusal):
  row --input F --from YYYY-MM-DD --until YYYY-MM-DD --cwd D [--root R] [--dry-run]
      # compute the window's row and write it; a second run for the same window replaces that window's row
  render --cwd D [--root R]   # the latest row as a markdown table, and a text chart across every window

The input file is one JSON object the advisor assembles at the pass; a key it leaves out makes the measures that
read it unmeasured, with that reason, never zero:
  records       every review record written for the window's PRs, all sessions (`review_record.py read`); a record's
                `sessionCost` is the field the review record writer sets (#2307)
  ciRuns        one item per CI run on a window PR: {"pr", "minutes", "suiteMinutes" (the suite job, or null)}
  escapes       the misses log as `review_learning.py tally` reads it; an item may also name its "pr" and "key". A
                leftover cap choice reads `escaped` only when a non-false-claim item names the same pr and key,
                `not-escaped` only when every such item names a pr and none names this one, else `unattributed`
  vetReceipts   one item per vet receipt: {"pr", "at" (the receipt's time), "sentBack" (bool), "body" (its text)}
  capChoicesSince  the day the project adopted the release whose vet receipt records cap choices
  costly        {"lateFindsOnUnchangedCode" | "repeatFindingLocations": {"basis": "monthly"|"sample", "value": n, "source": "where it came from"}}
  releases      one item per plugin release the project ran: {"version": "X.Y.Z", "since": the day (or UTC time) the
                project adopted it}; the four by-release measures read it
  mergedPrs     the window PRs that merged, as PR numbers; owner cards per merged PR reads it

Counting rules (written fresh: the post-0.43 assessment's counting scripts did not reach this build):
  - A PR is in the window when one of its review records is dated (`writtenAt`) inside it; only in-window records count.
  - A session's figures come from its latest record. Rounds per PR sum the sessions' `rounds.count`.
  - Reviewer cost comes only from each session's latest record's `sessionCost`: its tokens only when it is complete,
    its minutes when no run lacks a figure (#2545); `runs: 0` adds zero; a record without a well-formed one reads unmeasured, never zero.
    A seat's tokens are a number only when every in-window session that ran it has a complete `sessionCost` whose `bySeat` names it, and its minutes likewise when every such session's `sessionCost` has no run lacking a figure (an incomplete one's `bySeat` also counts as a run); a finding's lens never blanks a cost, and any other seat reads unmeasured.
    A session with a partial run (#2514: `runsPartial` of one or more, written when a silence-watchdog-ended attempt left no usage total beside a measured one) is never complete, so its PR stays out of the tokens figures; but a partial run's minutes are every attempt's wall time, so a PR whose only shortfall is partial runs counts in the minutes figures. A `sessionCost` that says `complete` with a partial run is not well-formed. A seat unmeasured only because every session that blanks it is partial-only (no run lacking a figure, one or more partial) reads `cost-partial`, which is now only ever a tokens reason in practice (a partial-only session does not blank minutes); any other blanking keeps `cost-not-recorded`.
    The window figures are over the measured PRs, and `prsLeftOut.<k>` counts the rest for that measure (`count`), saying why (`why`) and how many of them hold a session with a partial run (`partial`); a PR left out for `k` only because every session unmeasured for `k` has a latest record with no `sessionCost` key (a hand-written account) counts under `prsLeftOut.<k>.handWritten`, not in `count`, so each left-out PR counts once. Each measure is read on its own, and `partial` counts only the PRs under `count`, so it never exceeds `count`; a PR left out of a measure only by hand-written sessions counts under `handWritten` for it even beside a partial session.
  - Finding outcomes read each PR's latest record, one per finding key, merged members left out, and count for the seats the finding's `raisedBy` names, never its lens; one that names no lens seat, or only a seat that did not run on the PR (in any of its valid records, in the window or not), counts under `unattributed` and credits that seat nothing, and a PR with a counted finding that has no `raisedBy` leaves the outcomes of every seat that ran on it unmeasured (`raising-seat-not-recorded`). An
    undecided finding is `open`. Seats are named through `review_learning._seats`.
  - A loop came back clean when the record a vet read (the PR's latest at or before the vet) is `reviewed` with
    no finding open or left for the owner; a Minor or Nit listed for the merge verdict (`review_record.listed_for_merge`)
    leaves nothing open, and a cap choice's finding settles when no finding of its key is open in that sense.
  - By release (#2498; no target number): a session ran on the release adopted last at or before its first in-window
    record; a PR counts under the release its first in-window session ran on. A session or PR earlier than every
    listed release counts in `unplaced`, never under a release; a PR with any record time that does not parse makes
    all four unmeasured (`incomplete-evidence`), since its first session, and so its release, cannot be read.
    `ownerCardsPerMergedPr` counts, per merged PR, the distinct finding keys any of its in-window sessions' latest
    records hold as owner cards (`review_record.waits_for_owner`: a listed Minor or Nit is no card, a no-outcome Minor
    or Nit card is one, and a repeat whose card another finding holds is none; merged members left out).
    `sessionsPerPrByRelease` counts each PR's in-window sessions. `firstSessionCertification` reads each PR's first
    session among all its records: certified when that session's latest record is `reviewed`. `silentReviewerVoids` reads each in-window session's latest record
    that is not `reviewed` and has a reviewer row that did not run: `voided` when a silence-watchdog end names that
    row, `unresolved` when an end names no row (a forfeited or recovered seat's run dir binds no row, so its end
    carries its role and run dir and cannot be tied to the row that did not run), else neither. `voided` is what the
    held in-session reviewer retry waits on (a session on 0.50.0 or later voided by a silent reviewer); an
    `unresolved` session is read in its record before it counts. A release before 0.48.0, which recorded no watchdog
    ends, reads unmeasured; a status the writer does not record, or a malformed end, makes that release's figure
    unmeasured.
"""
import argparse
import collections
import datetime
import json
import math
import os
import re
import statistics
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import control_plane  # noqa: E402
import mode_registry  # noqa: E402
import review_findings_schema  # noqa: E402
import review_learning  # noqa: E402
import review_record  # noqa: E402
import review_seats  # noqa: E402
import session_contract  # noqa: E402

SCHEMA = "review-loop-measures/2"
TABLE = "review-loop-measures.jsonl"
UNMEASURED = review_learning.UNMEASURED
BY_RELEASE = ("ownerCardsPerMergedPr", "sessionsPerPrByRelease", "firstSessionCertification", "silentReviewerVoids")
MEASURES_V1 = ("roundsPerPr", "sessionsPerPr", "reviewerCostPerPr", "seats", "ci", "panels",
               "vetSendBacksOnCleanLoops", "escapes", "capChoices", "lateFindsOnUnchangedCode", "repeatFindingLocations")
MEASURES = MEASURES_V1 + BY_RELEASE
_SCHEMA_MEASURES = {"review-loop-measures/1": MEASURES_V1, SCHEMA: MEASURES}  # a row written before #2498 still renders
WATCHDOG_ENDS_SINCE = (0, 48, 0)  # the first release whose records list silence-watchdog ends
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
ROW_KEYS =("schema", "window", "writtenAt", "prs", "measures", "seatingRow", "leftOut", "unmeasured")
CAP_CHOICES = ("extra-audit-round", "leftover", "rethink")
COSTLY = ("lateFindsOnUnchangedCode", "repeatFindingLocations")
COSTLY_BASES = ("monthly", "sample")
MEASURE_KEYS = {"roundsPerPr": ("median", "p90"), "sessionsPerPr": ("median", "p90", "shareOverOne"),
                "reviewerCostPerPr": ("tokens", "minutes", "prsLeftOut"), "ci": ("runsPerPr", "minutesPerPr", "suiteMedianMinutes"),
                "panels": ("sizes", "sessions"), "vetSendBacksOnCleanLoops": ("sentBack", "cleanLoopsVetted"),
                "escapes": ("missed", "seenAndLeft", "falsePrClaims"), "capChoices": CAP_CHOICES,
                **dict.fromkeys(COSTLY, ("basis", "value", "source")), **dict.fromkeys(BY_RELEASE, ("byRelease", "unplaced"))}
LEFT_OUT_WHY = "a review session has no complete sessionCost"
HAND_WRITTEN_WHY = "cost not measured (hand-written)"
_CAP_RE = re.compile(r"<!-- superheroes:cap-choice choice=(\S+) vet=\S+ record=\S+ key=(.+?) -->")
_OPEN = (None, review_findings_schema.LEFT_FOR_OWNER)
_day = review_learning._day


def _open(f):
    """True when `f` is undecided or left for the owner and is not listed for the merge verdict: a listed Minor or Nit
    (`review_record.listed_for_merge`) is one the merge accepts, so it leaves nothing open."""
    # axis: a listed Minor or Nit is not open, so it spoils no clean loop and settles its cap choice — see bite-proof record i2531_cards
    return f.get("outcome") in _OPEN and not review_record.listed_for_merge(f)


def _num(v):
    """A finite number of zero or more, else None (a bool is not a number)."""
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
    return v if ok else None


def _pr_ok(pr):
    return isinstance(pr, (str, int)) and not isinstance(pr, bool) and str(pr) != ""


def _rec_ok(r):
    """A review record whole enough to count: identity, date, rounds, and every reviewer row and finding sound, and not
    marked incomplete by its producer (`ok` false, or `unreadFiles` naming files; the rule of `review_learning.tally`)."""
    return (isinstance(r, dict) and r.get("ok") is not False and r.get("unreadFiles") in (None, []) and _pr_ok(r.get("pr")) and isinstance(r.get("sessionId"), str) and r["sessionId"].strip()
            and _day(r.get("writtenAt"), whole=False) is not None and isinstance(r.get("rounds"), dict)
            and _num(r["rounds"].get("count")) is not None and isinstance(r["rounds"]["count"], int)
            and isinstance(r.get("reviewers"), list) and isinstance(r.get("findings"), list)
            and all(isinstance(x, dict) and x.get("ran") in review_record.RAN_STATES and isinstance(x.get("name"), str)
                    for x in r["reviewers"])
            and all(review_learning._finding_ok(f) for f in r["findings"]))


def _spread(xs):
    s = sorted(xs)
    return {"median": statistics.median(s), "p90": s[max(0, math.ceil(0.9 * len(s)) - 1)]}


def _latest(recs):
    return max(recs, key=lambda r: r["writtenAt"])


def _clean(rec):
    return review_record.cleared(rec.get("status")) and not any(_open(f) for f in rec["findings"])


def _by_session(rs):
    by = collections.defaultdict(list)
    for r in rs:
        by[r["sessionId"]].append(r)
    return list(by.values())


def _nat(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _session_cost(rec):
    """The record's `sessionCost` when well-formed (the shape #2307 writes), else None: that session's cost is then
    unmeasured, and nothing else about the record is. An optional `runsPartial` (#2514) must be an int of one or more
    that with `runsWithoutFigure` fits within `runs`; `complete` is true only when no run lacks a figure and none is
    partial. A record without `runsPartial` reads as before."""
    sc = rec.get("sessionCost")
    ok = (isinstance(sc, dict) and _nat(sc.get("tokens")) and _nat(sc.get("runs")) and _nat(sc.get("runsWithoutFigure"))
          and _num(sc.get("minutes")) is not None and isinstance(sc.get("complete"), bool)
          # axis: a `runsPartial` that is not an int of one or more within the runs makes the record's cost unmeasured — see bite-proof record i2514_partial_cost
          and ("runsPartial" not in sc or (isinstance(sc["runsPartial"], int) and not isinstance(sc["runsPartial"], bool)
                                           and sc["runsPartial"] >= 1 and sc["runsWithoutFigure"] + sc["runsPartial"] <= sc["runs"]))
          # axis: a session with a partial run is never complete, so a record that says it is reads unmeasured — see bite-proof record i2514_partial_cost
          and sc["complete"] == (sc["runsWithoutFigure"] == 0 and sc.get("runsPartial", 0) == 0) and isinstance(sc.get("bySeat"), dict)
          and all(isinstance(v, dict) and _nat(v.get("tokens")) and _num(v.get("minutes")) is not None and _nat(v.get("runs"))
                  for v in sc["bySeat"].values()))
    return sc if ok else None


def _partial_session(rec):
    """True when the record's well-formed `sessionCost` carries `runsPartial` of one or more."""
    sc = _session_cost(rec)
    return sc is not None and sc.get("runsPartial", 0) >= 1


def _whole(sc, k):
    """True when the well-formed `sessionCost` `sc` gives a whole figure for `k`: its tokens only when complete, its
    minutes when no run lacks a figure (#2545: a partial run's minutes are every attempt's wall time, only its tokens
    are short)."""
    # axis: tokens need a complete session, minutes need none of its runs to lack a figure — see bite-proof record i2545_partial_minutes
    return sc is not None and (sc["complete"] if k == "tokens" else sc["runsWithoutFigure"] == 0)


_raiser = review_learning._raiser  # the one raiser rule lives in review_learning


def _ran_seats(rows):
    """The lens seats the reviewer rows show ran: not `not-run`, and not carried from an earlier head."""
    return {s for x in rows if x["ran"] != review_record.RAN_NOT_RUN and "carried" not in x
            for s in review_learning._seats(x["name"])}


def _sum(vals, k, exact=False):
    """The sum, or None when any value is unmeasured (or there is none to sum); minutes round to one decimal."""
    if not vals or any(v is None for v in vals):
        return None
    return round(sum(vals), 1) if k == "minutes" and not exact else sum(vals)


def _r1(spread):
    """A minute figure's median, p90 and total, each rounded to one decimal."""
    return {**spread, **{x: round(spread[x], 1) for x in ("median", "p90", "total") if x in spread}}


def _pr_cost(rs, k):
    """A PR's reviewer cost for `k`, the sum of its sessions' (`rs` is its in-window records), each read from the
    session's latest record's `sessionCost`: zero when it ran nothing, its figure when whole for `k`, else unmeasured.
    Tokens are whole only for a complete `sessionCost`; minutes for one with no run lacking a figure (#2545), so a PR
    whose only shortfall is partial runs has minutes and no tokens."""
    figures = []
    for recs in _by_session(rs):
        sc = _session_cost(_latest(recs))
        if sc is not None and sc["runs"] == 0:
            figures.append(0.0 if k == "minutes" else 0)
        else:
            # axis: a session gives its figure for `k` only when whole for `k`, else the PR is unmeasured for `k` — see bite-proof record i2545_partial_minutes
            figures.append(sc[k] if _whole(sc, k) else None)
    return _sum(figures, k, exact=True)


def _hand_written_only(rs, k):
    """True when a PR left out of the `k` cost figure is left out only because it was hand-written: every in-window
    session whose figure is unmeasured for `k` (by `_pr_cost`, which reads `_whole(sc, k)`, so each measure is judged on its own
    (a partial session is unmeasured for tokens only)) has a latest record with no `sessionCost` key at all (the session writer
    writes one on every record). A `sessionCost` that is present but malformed or incomplete is incomplete, never hand-written."""
    unmeasured = [_latest(recs) for recs in _by_session(rs) if _pr_cost(recs, k) is None]
    # axis: a session counts hand-written only when its latest record carries no sessionCost key, and a PR only when every unmeasured session does — see bite-proof record i2515_hand_cost
    return bool(unmeasured) and all("sessionCost" not in r for r in unmeasured)


def _cap_outcome(choice, key, pr, later, escapes, before=frozenset()):
    """What happened next. `later` is every valid record of the PR written after the vet, in or out of the window;
    `before` is the sessionIds of its records written at or before the vet; `escapes` is the misses log, already known
    to be a list."""
    if choice == "leftover":
        items = [e for e in escapes if isinstance(e, dict) and e.get("marker") != review_learning.FALSE_CLAIM_MARKER]
        if any(_pr_ok(e.get("pr")) and str(e["pr"]) == pr and e.get("key") == key for e in items):
            return "escaped"
        if all(_pr_ok(e.get("pr")) and str(e["pr"]) != pr for e in items):
            return "not-escaped"
        return "unattributed"
    later = sorted(later, key=lambda r: r["writtenAt"])
    if choice == "extra-audit-round":
        later = [r for r in later if "extraAudit" in r["rounds"]]  # the follow-up R9 names: a record of the audit round
    else:  # the rethink: the first session that had not written before the vet, at its latest
        later = [r for r in later if r["sessionId"] not in before]
        later = [r for r in later if r["sessionId"] == later[0]["sessionId"]] if later else later
    if not later:
        return "pending"
    if choice == "rethink":
        return "converged" if _clean(later[-1]) else "not-converged"
    found = [f for f in later[0]["findings"] if (f.get(session_contract.FINDING_KEY_FIELD) or f.get("id")) == key]
    return "settled" if found and all(not _open(f) for f in found) else "not-settled"


def _when(value):
    """A day or a UTC time as an aware datetime (a day is its first moment), or None."""
    if not isinstance(value, str) or _day(value, whole=False) is None:
        return None
    try:
        got = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=datetime.timezone.utc)


def _releases(given):
    """The `releases` input as [(since, version tuple, version)] in adoption order, or None when any item is not whole."""
    out = []
    for r in given:
        v = r.get("version") if isinstance(r, dict) else None
        mt = _VERSION_RE.fullmatch(v) if isinstance(v, str) else None
        since = _when(r.get("since")) if isinstance(r, dict) else None
        if mt is None or since is None:
            return None
        out.append((since, tuple(int(x) for x in mt.groups()), v))
    return sorted(out)


def _release_measures(inp, prs, every, sessions, reason, miss):
    """The four by-release measures (#2498). `prs` holds each window PR's in-window records, `every` all its valid
    records, `sessions` each in-window session's latest in-window record."""
    given, merged = inp.get("releases"), inp.get("mergedPrs")
    rel = _releases(given) if isinstance(given, list) else None
    why = reason or ("no-releases-input" if not isinstance(given, list) else "incomplete-evidence" if rel is None else None)
    # axis: with no whole release list, all four read unmeasured with the reason, never zero — see bite-proof record i2498_by_release
    if why:
        return {k: miss(k, why) for k in BY_RELEASE}

    def release_of(recs):  # the release adopted last at or before the session's first record, else None
        t = _when(min(r["writtenAt"] for r in recs))  # every time parses: the PR loop checked them first
        # axis: a session runs on the release adopted last at or before its first record, to the second — see bite-proof record i2498_by_release
        got = [x for x in rel if x[0] <= t]
        return got[-1] if got else None

    def first(recs):
        return min(_by_session(recs), key=lambda rs: min(r["writtenAt"] for r in rs))

    by = {k: collections.defaultdict(list) for k in BY_RELEASE}
    unplaced, versions, damaged = collections.Counter(), {}, set()

    def put(k, release, value):
        # axis: an item earlier than every release is counted unplaced, never under a release — see bite-proof record i2498_by_release
        if release is None:
            unplaced[k] += 1
        else:
            versions[release[2]] = release[1]
            by[k][release[2]].append(value)

    merged_ok = isinstance(merged, list) and all(_pr_ok(p) for p in merged)
    merged_set = {str(p) for p in merged} if merged_ok else set()
    for pr, rs in prs.items():
        # axis: a PR with any record time that does not parse cannot say which session came first, so all four read unmeasured — see bite-proof record i2498_by_release
        if any(_when(r["writtenAt"]) is None for r in every[pr]):
            damaged.update(BY_RELEASE)
            continue
        # axis: a PR counts under the release its first in-window session ran on — see bite-proof record i2498_by_release
        pr_release = release_of(first(rs))
        put("sessionsPerPrByRelease", pr_release, len(sessions[pr]))
        # axis: certification reads the PR's first session among all its records, in the window or not — see bite-proof record i2498_by_release
        opening = first(every[pr])
        status = _latest(opening).get("status")
        # axis: a first session whose status is not one the writer records reads unmeasured, never uncertified — see bite-proof record i2498_by_release
        put("firstSessionCertification", release_of(opening),
            review_record.cleared(status) if status in review_record.STATUSES else None)
        if pr in merged_set:
            # axis: a merged PR's cards are its distinct finding keys that hold owner cards, merged members out — see bite-proof record i2498_by_release
            # axis: a repeat whose card another finding of the record holds is no card of its own (inside `waits_for_owner`) — see bite-proof record i2498_by_release
            # axis: a card is a finding that reaches the owner as one (`review_record.waits_for_owner`): a listed Minor is none, a no-outcome Minor card is one — see bite-proof record i2531_cards
            cards = {f.get(session_contract.FINDING_KEY_FIELD) or f.get("id") for r in sessions[pr].values()
                     for f in r["findings"] if review_record.waits_for_owner(f, r["findings"])
                     and not review_learning._merged_member(f)}
            put("ownerCardsPerMergedPr", pr_release, len(cards))
        for sid, last in sessions[pr].items():
            ends = last.get("silenceWatchdogEnds", [])
            # axis: a silence end that is not a dict naming a seat, or a status the writer does not record, reads unmeasured — see bite-proof record i2498_by_release
            whole = (isinstance(ends, list) and last.get("status") in review_record.STATUSES
                     and all(isinstance(e, dict) and isinstance(e.get("seat"), str) and e["seat"].strip() for e in ends))
            answered = {x["name"] for x in last["reviewers"] if x["ran"] != review_record.RAN_NOT_RUN}
            not_run = {x["name"] for x in last["reviewers"] if x["ran"] == review_record.RAN_NOT_RUN}
            silent = [e["seat"] for e in ends if e["seat"] not in answered] if whole else []
            if not whole:
                state = None
            elif review_record.cleared(last.get("status")) or not not_run or not silent:
                # axis: a session that certified, or whose every silent seat answered, or with no reviewer row that did not run, is no void — see bite-proof record i2498_by_release
                state = "clear"
            elif any(s in not_run for s in silent):
                # axis: voided only when a silence end names a reviewer row that did not run — see bite-proof record i2498_by_release
                state = "voided"
            else:
                # axis: an end naming no row (a forfeited or a recovered seat's run dir binds none) beside a row that did not run is unresolved, never a void — see bite-proof record i2498_by_release
                state = "unresolved"
            put("silentReviewerVoids", release_of([r for r in rs if r["sessionId"] == sid]), state)

    def shown(k, ver, vals):
        if k == "ownerCardsPerMergedPr":
            return dict(_spread(vals), total=sum(vals))
        if k == "sessionsPerPrByRelease":
            return _spread(vals)
        if k == "firstSessionCertification":
            if None in vals:
                return miss("%s.byRelease.%s" % (k, ver), "incomplete-evidence")
            return {"certified": sum(vals), "prs": len(vals), "share": round(sum(vals) / len(vals), 3)}
        # axis: a release before watchdog ends were recorded reads unmeasured, never zero — see bite-proof record i2498_by_release
        if versions[ver] < WATCHDOG_ENDS_SINCE:
            return miss("%s.byRelease.%s" % (k, ver), "watchdog-ends-not-recorded")
        if None in vals:
            return miss("%s.byRelease.%s" % (k, ver), "incomplete-evidence")
        return {"voided": vals.count("voided"), "unresolved": vals.count("unresolved"), "sessions": len(vals)}

    out = {k: {"byRelease": {v: shown(k, v, by[k][v]) for v in sorted(by[k], key=versions.get)},
               "unplaced": unplaced[k]} for k in BY_RELEASE}
    # axis: owner cards with no whole merged list read unmeasured, never zero — see bite-proof record i2498_by_release
    if not merged_ok:
        out["ownerCardsPerMergedPr"] = miss("ownerCardsPerMergedPr",
                                            "no-merged-input" if merged is None else "incomplete-evidence")
    for k in damaged:  # a PR that could not be placed could belong to any release, so no release's figure stands
        out[k] = miss(k, "incomplete-evidence")
    return out


def compute(inp, start, end, written_at=None):
    """The window's row from the input object. Every measure is a value or "unmeasured", and each unmeasured one is
    listed in `unmeasured` with its reason."""
    m, why, left = {}, {}, {"outsideWindow": 0, "malformed": 0}

    def miss(name, reason):
        why[name] = reason
        return UNMEASURED

    recs, prs, sessions = inp.get("records"), collections.defaultdict(list), collections.defaultdict(dict)
    every, whole = collections.defaultdict(list), isinstance(recs, list)  # every: valid records by PR, in the window or not
    for r in recs if whole else []:
        if not _rec_ok(r):
            left["malformed"] += 1
            whole = False
            continue
        every[str(r["pr"])].append(r)
        if not start <= _day(r["writtenAt"], whole=False) <= end:
            left["outsideWindow"] += 1
            continue
        pr = str(r["pr"])
        prs[pr].append(r)
        held = sessions[pr].get(r["sessionId"])
        if held is None or r["writtenAt"] >= held["writtenAt"]:
            sessions[pr][r["sessionId"]] = r
    reason = ("no-records-input" if not isinstance(recs, list) else "incomplete-evidence" if not whole
              else "no-prs-in-window" if not prs else None)
    if reason:
        for k in ("roundsPerPr", "sessionsPerPr", "reviewerCostPerPr", "seats", "panels"):
            m[k] = miss(k, reason)
    else:
        per = [list(s.values()) for s in sessions.values()]
        m["roundsPerPr"] = _spread([sum(r["rounds"]["count"] for r in ss) for ss in per])
        n = [len(ss) for ss in per]
        m["sessionsPerPr"] = dict(_spread(n), shareOverOne=round(sum(x > 1 for x in n) / len(n), 3))
        m["reviewerCostPerPr"], out = {}, {}
        for k in ("tokens", "minutes"):
            totals = [_pr_cost(rs, k) for rs in prs.values()]
            measured = [t for t in totals if t is not None]
            hands = [t is None and _hand_written_only(rs, k) for rs, t in zip(prs.values(), totals)]
            hand = sum(hands)
            # axis: `partial` counts the left-out PRs holding a session whose cost is partial, never more than `count` — see bite-proof record i2514_partial_cost
            # axis: partial counts only left-out PRs under count, so a PR left out for k only by a hand-written session is never partial for k — see bite-proof record i2515_hand_cost
            out[k] = {"count": len(totals) - len(measured) - hand, "why": LEFT_OUT_WHY,
                      "partial": sum(any(_partial_session(_latest(recs)) for recs in _by_session(rs))
                                     for rs, t, h in zip(prs.values(), totals, hands) if t is None and not h),
                      "handWritten": {"count": hand, "why": HAND_WRITTEN_WHY}}
            if not measured:
                m["reviewerCostPerPr"][k] = miss("reviewerCostPerPr." + k, "no-measured-pr")
                continue
            top, total = sorted(measured, reverse=True)[:math.ceil(len(measured) / 10)], sum(measured)
            shown = dict(_spread(measured), total=total, topTenthShare=round(sum(top) / total, 3) if total else 0)
            m["reviewerCostPerPr"][k] = _r1(shown) if k == "minutes" else shown
        m["reviewerCostPerPr"]["prsLeftOut"] = out
        outcomes, costs = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
        measured_ks = ("tokens", "minutes")
        # blanked: per measure, the seats a session could have run without a sessionCost whole for it that names them; costed: per measure, the seats a whole session's bySeat names; ran: every seat that ran
        blanked, costed = {k: set() for k in measured_ks}, {k: set() for k in measured_ks}
        ran = set()
        part_blank, other_blank = {k: set() for k in measured_ks}, {k: set() for k in measured_ks}  # blanked split by cause: a partial-only session (no run lacks a figure, one or more partial) vs every other
        unread = set()  # the seats that ran on a PR whose counted finding names no raiser: their outcomes are unmeasured
        for pr, rs in prs.items():
            keyed, lacking = {}, False
            ran_on_pr = _ran_seats(x for r in every[pr] for x in r["reviewers"])  # the seats that ran on this PR, from every valid record of it
            for f in _latest(rs)["findings"]:
                if not review_learning._merged_member(f):
                    got = keyed.setdefault(f.get(session_contract.FINDING_KEY_FIELD) or f.get("id"),
                                           [f.get("outcome") or "open", set(), True])
                    raiser = _raiser(f)
                    got[1].update(review_learning._seats(raiser))
                    got[2] = got[2] and raiser is not None
            for outcome, seats, named in keyed.values():
                if not named:
                    lacking = True  # the raiser is not recorded: the finding counts for no seat, never for its lens
                    continue
                for s in (seats & ran_on_pr) or ("unattributed",):  # a seat that did not run on this PR is credited nothing
                    outcomes[s][outcome] += 1
            if lacking:
                unread |= _ran_seats(x for r in every[pr] for x in r["reviewers"])
            for recs in _by_session(rs):
                last = _latest(recs)
                sc = _session_cost(last)
                ran_seats = _ran_seats(last["reviewers"])
                ran |= ran_seats
                named_seats = {s for name in (sc["bySeat"] if sc else ()) for s in review_learning._seats(name)}
                for k in measured_ks:
                    # axis: each measure is blanked by a session that is not whole for that measure, through its own sets — see bite-proof record i2545_partial_minutes
                    if not _whole(sc, k):
                        blanked[k] |= ran_seats | named_seats
                        if sc is not None and sc["runsWithoutFigure"] == 0 and sc.get("runsPartial", 0) >= 1:
                            part_blank[k] |= ran_seats | named_seats
                        else:
                            other_blank[k] |= ran_seats | named_seats
                    else:
                        costed[k] |= named_seats
                        blanked[k] |= ran_seats - named_seats  # a whole cost that leaves out a seat that ran does not cost it
                        other_blank[k] |= ran_seats - named_seats
                for name, by in sc["bySeat"].items() if sc else ():
                    for s in review_learning._seats(name):
                        for k in measured_ks:
                            # axis: a seat's sum adds a session's figure for `k` only when the session is whole for `k` — see bite-proof record i2545_partial_minutes
                            costs[s][k] += by[k] if _whole(sc, k) else 0  # a session not whole for `k` still names its seats
        m["seats"] = {}
        for s in sorted(set(outcomes) | set(costs) | ran | unread):
            shown = {"outcomes": (miss("seats.%s.outcomes" % s, "raising-seat-not-recorded") if s in unread
                                  else {o: outcomes[s][o] for o in (*review_findings_schema.OUTCOMES, "open")})}
            for k in ("tokens", "minutes"):
                known = s in costed[k] and s not in blanked[k] and s != "unattributed"  # no seat to record a cost against
                # axis: a seat blanked only by partial-only sessions reads `cost-partial`; any other blanking keeps `cost-not-recorded` — see bite-proof record i2514_partial_cost
                why_not = "cost-partial" if s in part_blank[k] and s not in other_blank[k] and s != "unattributed" else "cost-not-recorded"
                shown[k] = ((round(costs[s][k], 1) if k == "minutes" else costs[s][k]) if known
                            else miss("seats.%s.%s" % (s, k), why_not))
            m["seats"][s] = shown
        sizes = collections.Counter()
        for ss in per:
            for r in ss:
                ran = [x for x in r["reviewers"] if x["ran"] != review_record.RAN_NOT_RUN and "carried" not in x]
                sizes[str(len({s for x in ran for s in review_learning._seats(x["name"])}))] += 1
        m["panels"] = {"sizes": dict(sizes), "sessions": sum(n)}
    m.update(_release_measures(inp, prs, every, sessions, reason, miss))

    ci = inp.get("ciRuns")
    if not isinstance(ci, list) or reason:
        m["ci"] = miss("ci", reason or "no-ci-input")
    else:
        runs, suite, bad = {pr: [] for pr in prs}, [], False
        for c in ci:
            if not (isinstance(c, dict) and _pr_ok(c.get("pr")) and _num(c.get("minutes")) is not None
                    and (c.get("suiteMinutes") is None or _num(c["suiteMinutes"]) is not None)):
                bad = True
            elif str(c["pr"]) in runs:
                runs[str(c["pr"])].append(c["minutes"])
                suite += [c["suiteMinutes"]] if c.get("suiteMinutes") is not None else []
        if bad or not all(runs.values()):
            m["ci"] = miss("ci", "incomplete-evidence" if bad else "pr-without-ci-receipt")
        else:
            m["ci"] = {"runsPerPr": _spread([len(v) for v in runs.values()]),
                       "minutesPerPr": _r1(_spread([round(sum(v), 1) for v in runs.values()])),
                       "suiteMedianMinutes": (round(statistics.median(suite), 1) if suite
                                              else miss("ci.suiteMedianMinutes", "no-suite-time"))}

    esc = inp.get("escapes")
    t = review_learning.tally([], esc, start.isoformat(), until=end.isoformat()) if isinstance(esc, list) else None
    if t is None or t["falsePrClaims"] is None:
        m["escapes"] = miss("escapes", "no-misses-log-input" if t is None else "incomplete-evidence")
    else:
        m["escapes"] = dict(t["escapes"], falsePrClaims=t["falsePrClaims"])

    vets, in_window, bad_vet = inp.get("vetReceipts"), [], False
    for v in vets if isinstance(vets, list) else []:
        if not (isinstance(v, dict) and _pr_ok(v.get("pr")) and isinstance(v.get("sentBack"), bool)
                and isinstance(v.get("at"), str) and _day(v["at"], whole=False) is not None
                and isinstance(v.get("body"), str)):
            bad_vet = True
        elif start <= _day(v["at"], whole=False) <= end:
            in_window.append(v)
    vet_reason = reason or ("no-vet-input" if not isinstance(vets, list) else "incomplete-evidence" if bad_vet else None)
    if vet_reason:
        m["vetSendBacksOnCleanLoops"] = miss("vetSendBacksOnCleanLoops", vet_reason)
    else:
        clean = sent = 0
        for v in in_window:
            read = [r for r in every.get(str(v["pr"]), []) if r["writtenAt"] <= v["at"]] if str(v["pr"]) in prs else []
            if read and _clean(_latest(read)):
                clean, sent = clean + 1, sent + v["sentBack"]
        m["vetSendBacksOnCleanLoops"] = {"sentBack": sent, "cleanLoopsVetted": clean}

    since = _day(inp.get("capChoicesSince"))
    cap_reason = ("no-cap-choices-since" if since is None else "before-cap-choice-recording" if start < since
                  else vet_reason)
    found = [(v, mt.group(1), mt.group(2)) for v in in_window for mt in _CAP_RE.finditer(v["body"])]
    torn = any("<!-- superheroes:cap-choice" in ln and not _CAP_RE.search(ln) for v in in_window for ln in v["body"].splitlines())
    if not cap_reason and (torn or any(choice not in CAP_CHOICES for _, choice, _ in found)):
        cap_reason = "incomplete-evidence"
    if not cap_reason and m["escapes"] == UNMEASURED:  # a leftover's outcome reads the misses log
        cap_reason = why["escapes"]
    if cap_reason:
        m["capChoices"] = miss("capChoices", cap_reason)
    else:
        m["capChoices"] = {c: {"count": 0, "outcomes": {}} for c in CAP_CHOICES}
        for v, choice, key in found:
            pr = str(v["pr"])
            got = _cap_outcome(choice, key, pr, [r for r in every.get(pr, []) if r["writtenAt"] > v["at"]], esc,
                               {r["sessionId"] for r in every.get(pr, []) if r["writtenAt"] <= v["at"]})
            m["capChoices"][choice]["count"] += 1
            m["capChoices"][choice]["outcomes"][got] = m["capChoices"][choice]["outcomes"].get(got, 0) + 1

    costly = inp.get("costly") if isinstance(inp.get("costly"), dict) else {}
    for name in COSTLY:
        c = costly.get(name)
        if (isinstance(c, dict) and c.get("basis") in COSTLY_BASES and _num(c.get("value")) is not None
                and isinstance(c.get("source"), str) and c["source"].strip()):
            m[name] = {"basis": c["basis"], "value": c["value"], "source": c["source"]}
        else:
            m[name] = miss(name, "not-run-this-pass")

    seats = m["seats"] if isinstance(m["seats"], dict) else {}
    seating_row = {short: seats[full] for full, short in review_seats.AGENT_SUFFIX.items()
                   if short in review_learning.SEATING_SEATS and full in seats}
    return {"schema": SCHEMA, "window": {"from": start.isoformat(), "until": end.isoformat()},
            "writtenAt": written_at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prs": len(prs) if whole and isinstance(recs, list) else UNMEASURED,
            "measures": {k: m[k] for k in MEASURES}, "seatingRow": seating_row, "leftOut": left,
            "unmeasured": [{"measure": k, "reason": why[k]} for k in sorted(why)]}


def problems(row):
    """What makes a row not the fixed shape; empty when it is."""
    if (not isinstance(row, dict) or tuple(row) != ROW_KEYS or row.get("schema") not in _SCHEMA_MEASURES
            or not isinstance(row["measures"], dict) or not isinstance(row["unmeasured"], list)):
        return ["the row's keys are not %s" % (ROW_KEYS,)]
    # axis: a row keeps the measures of the schema it was written under, so a /1 row still renders — see bite-proof record i2498_by_release
    m, w, measures = row["measures"], row.get("window"), _SCHEMA_MEASURES[row["schema"]]
    out = [] if tuple(m) == measures else ["the measures are not %s" % (measures,)]
    a, b = (_day(w.get(k)) if isinstance(w, dict) else None for k in ("from", "until"))
    if a is None or b is None or b < a:
        out.append("the window is not two ISO dates in order")
    out += ["%s does not hold exactly %s" % (k, keys) for k, keys in MEASURE_KEYS.items()
            if isinstance(m.get(k), dict) and set(m[k]) != set(keys)]
    if isinstance(m.get("seats"), dict) and not all(isinstance(s, dict) for s in m["seats"].values()):
        out.append("a seat is not a dict")
    # axis: a by-release measure holds a value or unmeasured per release, and a count of unplaced — see bite-proof record i2498_by_release
    out += ["%s is not releases of values with an unplaced count" % k for k in BY_RELEASE
            if isinstance(m.get(k), dict) and set(m[k]) == {"byRelease", "unplaced"}
            and not (isinstance(m[k]["byRelease"], dict) and _nat(m[k]["unplaced"])
                     and all(isinstance(v, dict) or v == UNMEASURED for v in m[k]["byRelease"].values()))]
    named = {u.get("measure") for u in row["unmeasured"] if isinstance(u, dict) and u.get("reason")}
    out += ["%s reads unmeasured with no reason" % path for path, v in _flat(m)
            if v == UNMEASURED and not any(path == n or path.startswith("%s." % n) for n in named)]
    if not all(isinstance(v, dict) or v == UNMEASURED for v in m.values()):
        out.append("a measure is neither a value nor unmeasured")
    return out


def table_path(cwd, root=None):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "state", TABLE)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return [line.rstrip("\n") for line in fh if line.strip()]
    except FileNotFoundError:
        return []


def _window_of(line):
    try:
        got = json.loads(line)
    except ValueError:
        return None
    return got.get("window") if isinstance(got, dict) else None


def write(row, cwd, root=None):
    """Append the row, or replace the row already there for the same window; other lines are kept as they are."""
    path = table_path(cwd, root)
    lines = _read(path)
    kept = [line for line in lines if _window_of(line) != row["window"]]
    control_plane.atomic_write(path, "".join(x + "\n" for x in kept + [json.dumps(row, ensure_ascii=False)]))
    return {"ok": True, "outcome": "replaced" if len(kept) < len(lines) else "appended", "table": path, "row": row}


def _flat(value, prefix=""):
    if isinstance(value, dict) and value:
        return [kv for k, v in value.items() for kv in _flat(v, "%s.%s" % (prefix, k) if prefix else k)]
    return [(prefix, value)]


def render(rows):
    """The latest row as a two-column markdown table, then a text chart of two headline measures across windows."""
    rows = [r for r in rows if not problems(r)]
    if not rows:
        return "No review-loop measures row yet."
    rows.sort(key=lambda r: r["window"]["from"])
    last = rows[-1]
    out = ["**Review-loop measures, %s to %s** (%s PRs)" % (last["window"]["from"], last["window"]["until"], last["prs"]),
           "", "| Measure | Value |", "|---|---|"]
    out += ["| %s | %s |" % (k, json.dumps(v)) for k, v in _flat(last["measures"])]
    out += ["", "Unmeasured: " + ("; ".join("%(measure)s (%(reason)s)" % u for u in last["unmeasured"]) or "none"), ""]
    for label, get in (("median rounds per PR", lambda m: m["roundsPerPr"]),
                       ("median reviewer minutes per PR", lambda m: m["reviewerCostPerPr"])):
        vals = []
        for r in rows:
            v = get(r["measures"])
            v = v.get("minutes") if isinstance(v, dict) and "minutes" in v else v
            vals.append(v.get("median") if isinstance(v, dict) else None)
        top = max([v for v in vals if v is not None] or [0]) or 1
        out += ["```", label]
        out += ["%s  %-20s %s" % (r["window"]["from"], "#" * round(20 * v / top) if v is not None else "",
                                  v if v is not None else UNMEASURED) for r, v in zip(rows, vals)]
        out += ["```"]
    return "\n".join(out)


def _parser():
    p = argparse.ArgumentParser(prog="review_measures.py")
    sub = p.add_subparsers(dest="verb", required=True)
    r = sub.add_parser("row")
    for f in ("--input", "--from", "--until", "--cwd"):
        r.add_argument(f, required=True)
    r.add_argument("--root")
    r.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("render")
    s.add_argument("--cwd", required=True)
    s.add_argument("--root")
    return p


def main(argv=None):
    a = _parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    if a.verb == "render":
        rows = [json.loads(x) for x in _read(table_path(a.cwd, a.root)) if _window_of(x) is not None]
        out = {"ok": True, "markdown": render(rows)}
    else:
        start, end, inp = _day(getattr(a, "from")), _day(a.until), review_learning._load(a.input)
        if start is None or end is None or end < start or not isinstance(inp, dict):
            out = {"ok": False, "outcome": "refused", "reason": "bad-input",
                   "detail": "--from and --until are ISO dates in order; --input is a JSON object"}
        else:
            row = compute(inp, start, end)
            bad = problems(row)
            out = ({"ok": False, "outcome": "refused", "reason": "row-shape", "detail": bad} if bad
                   else {"ok": True, "outcome": "dry-run", "row": row} if a.dry_run else write(row, a.cwd, a.root))
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
