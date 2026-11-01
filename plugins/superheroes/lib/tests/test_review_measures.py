"""Tests for lib/review_measures.py (#2189): the review-loop measures row, one fixed-shape row per gardening window."""
import datetime
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import review_findings_schema  # noqa: E402
import review_learning  # noqa: E402
import review_measures as RM  # noqa: E402

D = datetime.date.fromisoformat
FROM, UNTIL = D("2026-10-01"), D("2026-10-07")
U = RM.UNMEASURED
SRC = "gardening pass sample of 12 PRs"


def _row(name, commit="c1", ran="engine-record", tokens=100, minutes=1.5):
    return {"name": name, "ran": ran, "commit": commit, "cost": {"tokens": tokens, "minutes": minutes}}


def _sc(tokens, minutes, runs=1, without=0, by_seat=None):
    """A record's `sessionCost` (#2307): the session's own runs, summed over all its rounds."""
    return {"tokens": tokens, "minutes": minutes, "runs": runs, "runsWithoutFigure": without,
            "complete": without == 0, "bySeat": by_seat if by_seat is not None else {}}


def _by(tokens, minutes, runs=1):
    return {"tokens": tokens, "minutes": minutes, "runs": runs}


_DEFAULT = object()


def _rec(pr, session="s1", at="2026-10-03T10:00:00Z", rows=None, findings=(), count=2, status="reviewed", sc=_DEFAULT):
    """A review record. `sc` is its `sessionCost`: by default one security-reviewer run of 100 tokens and 1.5 minutes, None for none."""
    rec = {"pr": pr, "sessionId": session, "writtenAt": at, "status": status, "rounds": {"count": count},
           "reviewers": rows if rows is not None else [_row("security-reviewer (round 1)")],
           "findings": list(findings)}
    sc = _sc(100, 1.5, by_seat={"security-reviewer": _by(100, 1.5)}) if sc is _DEFAULT else sc
    if sc is not None:
        rec["sessionCost"] = sc
    return rec


def _f(key, outcome="fixed", reviewer="Security"):
    return {"id": key, "findingKey": key, "outcome": outcome, "reviewer": reviewer}


def _full(**over):
    inp = {"records": [_rec(1)], "ciRuns": [{"pr": 1, "minutes": 4, "suiteMinutes": 3}], "escapes": [],
           "vetReceipts": [], "capChoicesSince": "2026-09-01",
           "costly": {"lateFindsOnUnchangedCode": {"basis": "monthly", "value": 0, "source": SRC}}}
    inp.update(over)
    return inp


def _why(row):
    return {u["measure"]: u["reason"] for u in row["unmeasured"]}


def _filled(**counts):
    """A seat's outcomes as the row shows them: every outcome in schema order, then open, 0 where none."""
    return {**dict.fromkeys((*review_findings_schema.OUTCOMES, "open"), 0), **counts}


def test_the_row_shape_is_pinned():
    assert RM.MEASURES == ("roundsPerPr", "sessionsPerPr", "reviewerCostPerPr", "seats", "ci", "panels",
                           "vetSendBacksOnCleanLoops", "escapes", "capChoices", "lateFindsOnUnchangedCode",
                           "repeatFindingLocations")
    assert RM.ROW_KEYS == ("schema", "window", "writtenAt", "prs", "measures", "seatingRow", "leftOut", "unmeasured")
    row = RM.compute(_full(), FROM, UNTIL)
    assert tuple(row) == RM.ROW_KEYS and tuple(row["measures"]) == RM.MEASURES and RM.problems(row) == []
    assert RM.MEASURE_KEYS["reviewerCostPerPr"] == ("tokens", "minutes", "prsLeftOut")
    none_left = {"count": 0, "why": "a review session has no complete sessionCost"}
    assert row["measures"]["reviewerCostPerPr"]["prsLeftOut"] == {"tokens": none_left, "minutes": none_left}


@pytest.mark.parametrize("damage", [lambda r: r.pop("seatingRow"), lambda r: r["measures"].pop("ci"),
                                    lambda r: r.update(unmeasured=[]), lambda r: r["measures"].update(ci=0)])
def test_a_row_off_its_shape_is_named(damage):
    row = RM.compute(_full(), FROM, UNTIL)  # repeatFindingLocations reads unmeasured, so clearing the reasons is a fault
    damage(row)
    assert RM.problems(row)


def test_every_input_missing_reads_unmeasured_with_its_reason_never_zero():
    row = RM.compute({}, FROM, UNTIL)
    assert all(v == U for v in row["measures"].values())
    assert row["prs"] == U
    why = _why(row)
    assert why["roundsPerPr"] == "no-records-input" and why["escapes"] == "no-misses-log-input"
    assert why["capChoices"] == "no-cap-choices-since" and why["repeatFindingLocations"] == "not-run-this-pass"
    assert set(why) == set(RM.MEASURES)


def test_a_full_window_is_measured():
    row = RM.compute(_full(), FROM, UNTIL)
    m = row["measures"]
    assert m["roundsPerPr"] == {"median": 2, "p90": 2}
    assert m["sessionsPerPr"]["shareOverOne"] == 0
    assert m["ci"] == {"runsPerPr": {"median": 1, "p90": 1}, "minutesPerPr": {"median": 4, "p90": 4},
                       "suiteMedianMinutes": 3}
    assert m["escapes"] == {"missed": 0, "seenAndLeft": 0, "falsePrClaims": 0}
    assert m["lateFindsOnUnchangedCode"] == {"basis": "monthly", "value": 0, "source": SRC}
    assert m["panels"] == {"sizes": {"1": 1}, "sessions": 1}
    assert set(_why(row)) == {"repeatFindingLocations"}


def test_a_malformed_record_makes_the_record_measures_unmeasured_not_zero():
    row = RM.compute(_full(records=[_rec(1), {"pr": 2}]), FROM, UNTIL)
    assert row["measures"]["roundsPerPr"] == U and _why(row)["roundsPerPr"] == "incomplete-evidence"
    assert row["leftOut"]["malformed"] == 1 and row["prs"] == U


def test_records_outside_the_window_are_left_out():
    recs = [_rec(1), _rec(2, at="2026-09-30T23:00:00Z"), _rec(3, at="2026-10-08T00:00:00Z")]
    row = RM.compute(_full(records=recs), FROM, UNTIL)
    assert row["prs"] == 1 and row["leftOut"]["outsideWindow"] == 2


def test_rounds_and_sessions_per_pr_read_each_sessions_latest_record():
    recs = [_rec(1, "a", "2026-10-02T00:00:00Z", count=1), _rec(1, "a", "2026-10-03T00:00:00Z", count=3),
            _rec(1, "b", "2026-10-04T00:00:00Z", count=1), _rec(2, count=1)]
    m = RM.compute(_full(records=recs, ciRuns=[{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]), FROM, UNTIL)["measures"]
    assert m["roundsPerPr"] == {"median": 2.5, "p90": 4}
    assert m["sessionsPerPr"] == {"median": 1.5, "p90": 2, "shareOverOne": 0.5}


def _pr_cost(*recs, **over):
    return RM.compute(_full(records=list(recs), **over), FROM, UNTIL)["measures"]["reviewerCostPerPr"]


def test_cost_comes_only_from_a_complete_session_cost():
    got = _pr_cost(_rec(1, sc=_sc(250, 3.5)))
    assert got["tokens"]["total"] == 250 and got["minutes"]["total"] == 3.5
    got = _pr_cost(_rec(1, sc=_sc(250, 3.5, runs=2, without=1)))  # the same figures, but `complete` is false
    assert got["tokens"] == U and got["minutes"] == U
    # no sessionCost: the reviewer rows' `cost` and `observation` and the record-level `cost` are never read
    rows = [dict(_row("security-reviewer (round 1)"), observation={"tokens": 100, "wallSeconds": 90})]
    old = dict(_rec(1, rows=rows, sc=None), cost={"tokens": 999, "minutes": 9, "notCounted": []})
    got = _pr_cost(old)
    assert got["tokens"] == U and got["minutes"] == U
    # two sessions sum their latest records' sessionCost, and an earlier record of the same session is not added
    a_early, a_late = _rec(1, "a", "2026-10-02T10:00:00Z", sc=_sc(100, 1.0)), _rec(1, "a", "2026-10-03T10:00:00Z", sc=_sc(300, 2.0))
    b = _rec(1, "b", "2026-10-04T10:00:00Z", sc=_sc(50, 0.5))
    for order in ([a_early, a_late, b], [b, a_late, a_early]):
        got = _pr_cost(*order)
        assert got["tokens"]["total"] == 350 and got["minutes"]["total"] == 2.5


def _malformed(**over):
    """A well-formed sessionCost with some fields made wrong (a value of `...` removes the field)."""
    sc = {**_sc(100, 1.5, by_seat={"security-reviewer": _by(100, 1.5)}), **over}
    return {k: v for k, v in sc.items() if v is not ...}


@pytest.mark.parametrize("bad", [
    _malformed(tokens="x"), _malformed(tokens=True), _malformed(tokens=-1), _malformed(tokens=1.5), _malformed(tokens=...),
    _malformed(minutes="x"), _malformed(minutes=-0.5), _malformed(minutes=float("nan")), _malformed(minutes=True),
    _malformed(runs="1"), _malformed(runs=-1), _malformed(runsWithoutFigure=None), _malformed(complete="yes"),
    _malformed(complete=...), _malformed(runsWithoutFigure=2),  # `complete` true with two runs without a figure
    {**_sc(0, 0, runs=0), "complete": False},  # runs 0 with `complete` false: complete must equal runsWithoutFigure == 0
    _malformed(complete=False), _malformed(bySeat=[]), _malformed(bySeat=...),
    _malformed(bySeat={"security-reviewer": 5}), _malformed(bySeat={"security-reviewer": _by("x", 1.5)}),
    _malformed(bySeat={"security-reviewer": _by(100, "x")}), _malformed(bySeat={"security-reviewer": _by(100, 1.5, runs=True)}),
    _malformed(bySeat={"security-reviewer": {"tokens": 100, "minutes": 1.5}}), "x", [], None])
def test_a_malformed_session_cost_reads_unmeasured_and_leaves_the_record_whole(bad):
    rec = dict(_rec(1, findings=[_f("k1")]), sessionCost=bad)  # the finding names the security seat
    row = RM.compute(_full(records=[rec]), FROM, UNTIL)
    cost, m = row["measures"]["reviewerCostPerPr"], row["measures"]
    assert cost["tokens"] == U and cost["minutes"] == U and m["seats"]["security-reviewer"]["tokens"] == U
    assert m["roundsPerPr"] == {"median": 2, "p90": 2} and m["sessionsPerPr"]["median"] == 1  # the record is still whole
    assert m["panels"] == {"sizes": {"1": 1}, "sessions": 1} and row["prs"] == 1 and row["leftOut"]["malformed"] == 0
    assert m["ci"] != U and m["vetSendBacksOnCleanLoops"] != U and RM.problems(row) == []


def test_a_seat_with_no_cost_recorded_reads_unmeasured_never_zero():
    named = [_f("k1"), _f("k2", "craft", "Failure-Mode")]  # the findings name two seats
    ci = [{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]
    # every session has a complete sessionCost: a seat named by the findings that no session ran reads 0
    seats = RM.compute(_full(records=[_rec(1, findings=named)]), FROM, UNTIL)["measures"]["seats"]
    assert seats["security-reviewer"]["tokens"] == 100 and seats["premortem-reviewer"]["tokens"] == 0
    # one session with no sessionCost blanks every seat's cost, not only its PR's
    row = RM.compute(_full(records=[_rec(1, findings=named), _rec(2, sc=None)], ciRuns=ci), FROM, UNTIL)
    seats, why = row["measures"]["seats"], _why(row)
    assert seats["security-reviewer"]["tokens"] == U and seats["security-reviewer"]["minutes"] == U
    assert seats["premortem-reviewer"]["tokens"] == U and why["seats.premortem-reviewer.tokens"] == "cost-not-recorded"
    assert why["seats.security-reviewer.minutes"] == "cost-not-recorded"
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 100 and cost["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY}
    # an incomplete sessionCost blanks them too, while a session that ran nothing (runs 0) does not
    row = RM.compute(_full(records=[_rec(1), _rec(2, sc=_sc(5, 0.1, runs=2, without=1))], ciRuns=ci), FROM, UNTIL)
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == U
    row = RM.compute(_full(records=[_rec(1), _rec(2, sc=_sc(0, 0.0, runs=0))], ciRuns=ci), FROM, UNTIL)
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == 100
    # no PR measured at all
    row = RM.compute(_full(records=[_rec(1, sc=None), _rec(2, sc=None)], ciRuns=ci), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"] == U and cost["minutes"] == U and _why(row)["reviewerCostPerPr.tokens"] == "no-measured-pr"
    assert cost["prsLeftOut"] == {"tokens": {"count": 2, "why": RM.LEFT_OUT_WHY}, "minutes": {"count": 2, "why": RM.LEFT_OUT_WHY}}


def test_a_session_where_no_reviewer_ran_adds_zero():
    # runs 0 adds zero whatever the sums say: the rule reads `runs`, not the figures
    idle = _rec(1, "b", rows=[{"name": "grounding-seat", "ran": "not-run", "commit": "c1"}], count=0, sc=_sc(7, 0.5, runs=0))
    got = _pr_cost(idle)
    assert got["tokens"]["total"] == 0 and got["minutes"]["total"] == 0.0
    got = _pr_cost(_rec(1, "a"), idle)
    assert got["tokens"]["total"] == 100 and got["minutes"]["total"] == 1.5
    bare = _rec(1, "c", sc=None)
    assert _pr_cost(_rec(1, "a"), bare)["tokens"] == U  # a session without sessionCost still reads unmeasured
    assert _pr_cost(bare)["tokens"] == U


def test_the_window_cost_is_over_measured_prs_and_names_those_left_out():
    ci = [{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]
    bad = _sc(100, 1.5, runs=2, without=1)
    row = RM.compute(_full(records=[_rec(1), _rec(2, sc=bad)], ciRuns=ci), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
    assert cost["prsLeftOut"]["tokens"] == {"count": 1, "why": "a review session has no complete sessionCost"}
    assert cost["prsLeftOut"]["minutes"]["count"] == 1 and RM.problems(row) == []
    row = RM.compute(_full(records=[_rec(1, sc=None), _rec(2, sc=bad)], ciRuns=ci), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"] == U and _why(row)["reviewerCostPerPr.tokens"] == "no-measured-pr"
    assert cost["prsLeftOut"]["tokens"]["count"] == 2 and cost["minutes"] == U and RM.problems(row) == []


def test_minute_medians_and_totals_are_rounded_to_one_decimal():
    recs = [_rec(n, sc=_sc(100, mins)) for n, mins in ((1, 0.1), (2, 0.2), (3, 0.25))]
    ci = [{"pr": n, "minutes": 1} for n in (1, 2, 3)]
    cost = RM.compute(_full(records=recs, ciRuns=ci), FROM, UNTIL)["measures"]["reviewerCostPerPr"]["minutes"]
    assert cost["median"] == 0.2 and cost["p90"] == 0.2 and cost["total"] == 0.6
    runs = [{"pr": 1, "minutes": 1.25, "suiteMinutes": 1.25}, {"pr": 2, "minutes": 1.35, "suiteMinutes": 1.35}]
    shown = RM.compute(_full(records=[_rec(1), _rec(2)], ciRuns=runs), FROM, UNTIL)["measures"]["ci"]
    assert shown["minutesPerPr"] == {"median": 1.3, "p90": 1.4} and shown["suiteMedianMinutes"] == 1.3


def test_the_top_tenth_share_is_the_costliest_tenth_of_prs():
    recs = [_rec(n, sc=_sc(10 if n < 10 else 910, 1.5)) for n in range(1, 11)]
    ci = [{"pr": n, "minutes": 1} for n in range(1, 11)]
    cost = RM.compute(_full(records=recs, ciRuns=ci), FROM, UNTIL)["measures"]["reviewerCostPerPr"]["tokens"]
    assert cost["total"] == 1000 and cost["topTenthShare"] == 0.91


def test_finding_outcomes_by_lens_key_an_undecided_finding_open_and_feed_the_seating_check():
    findings = [_f("k1"), _f("k2", None), _f("k3", "craft", "Failure-Mode"), _f("k4", "fixed", "Nonesuch")]
    rows = [_row("security-reviewer (round 1)"), _row("premortem-reviewer (round 1)", tokens=7, minutes=0.2)]
    by_seat = {"security-reviewer": _by(60, 1.0), "Security": _by(40, 0.5), "premortem-reviewer": _by(7, 0.2),
               "code-reviewer": _by(3, 0.1)}  # two keys land on one seat; code-reviewer is named only here
    sc = _sc(110, 1.8, runs=4, by_seat=by_seat)
    row = RM.compute(_full(records=[_rec(1, rows=rows, findings=findings, sc=sc)]), FROM, UNTIL)
    seats = row["measures"]["seats"]
    assert seats["code-reviewer"] == {"outcomes": _filled(), "tokens": 3, "minutes": 0.1}  # a bySeat-only seat, zero-filled
    assert seats["security-reviewer"]["outcomes"] == _filled(fixed=1, open=1)
    assert seats["premortem-reviewer"]["outcomes"] == _filled(craft=1)
    assert seats["unattributed"] == {"outcomes": _filled(fixed=1), "tokens": U, "minutes": U}
    assert all(list(s["outcomes"]) == [*review_findings_schema.OUTCOMES, "open"] for s in seats.values())
    shown = review_learning.seating(row["seatingRow"])["seats"]
    assert shown["security"]["tokens"] == 100 and shown["premortem"]["minutes"] == 0.2
    assert shown["security"]["outcomes"]["fixed"] == 1
    assert shown["security"]["outcomes"]["craft"] == 0 and shown["premortem"]["outcomes"]["fixed"] == 0  # never had: 0, not unmeasured


def test_ci_reads_unmeasured_when_a_window_pr_has_no_receipt_or_a_receipt_is_damaged():
    recs = [_rec(1), _rec(2)]
    row = RM.compute(_full(records=recs, ciRuns=[{"pr": 1, "minutes": 2}]), FROM, UNTIL)
    assert row["measures"]["ci"] == U and _why(row)["ci"] == "pr-without-ci-receipt"
    row = RM.compute(_full(ciRuns=[{"pr": 1, "minutes": "two"}]), FROM, UNTIL)
    assert _why(row)["ci"] == "incomplete-evidence"
    row = RM.compute(_full(ciRuns=[{"pr": 1, "minutes": 2}]), FROM, UNTIL)
    assert row["measures"]["ci"]["suiteMedianMinutes"] == U


def test_escapes_by_kind_count_the_window_and_keep_false_claims_apart():
    esc = [{"reviewedAt": "2026-10-02", "call": "missed"}, {"reviewedAt": "2026-10-02", "call": "seen-and-left"},
           {"reviewedAt": "2026-10-02", "call": "missed", "marker": "false-pr-claim"},
           {"reviewedAt": "2026-09-01", "call": "missed"}]
    assert RM.compute(_full(escapes=esc), FROM, UNTIL)["measures"]["escapes"] == {
        "missed": 1, "seenAndLeft": 1, "falsePrClaims": 1}
    row = RM.compute(_full(escapes=[{"call": "missed"}]), FROM, UNTIL)
    assert row["measures"]["escapes"] == U and _why(row)["escapes"] == "incomplete-evidence"


def test_vet_send_backs_count_only_loops_that_came_back_clean():
    recs = [_rec(1), _rec(2, findings=[_f("k", "left-for-owner")]), _rec(3)]
    vets = [{"pr": 1, "at": "2026-10-04T00:00:00Z", "sentBack": True, "body": ""},
            {"pr": 2, "at": "2026-10-04T00:00:00Z", "sentBack": True, "body": ""},
            {"pr": 3, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": ""}]
    ci = [{"pr": n, "minutes": 1} for n in (1, 2, 3)]
    m = RM.compute(_full(records=recs, vetReceipts=vets, ciRuns=ci), FROM, UNTIL)["measures"]
    assert m["vetSendBacksOnCleanLoops"] == {"sentBack": 1, "cleanLoopsVetted": 2}


def _cap(choice, key="k1"):
    return "<!-- superheroes:cap-choice choice=%s vet=7 record=https://x/r key=%s -->" % (choice, key)


def test_a_window_with_no_capped_handback_reads_zero_choices():
    m = RM.compute(_full(), FROM, UNTIL)["measures"]
    assert m["capChoices"] == {c: {"count": 0, "outcomes": {}} for c in RM.CAP_CHOICES}


@pytest.mark.parametrize("since", ["2026-10-02", "2026-11-01"])
def test_a_window_before_the_rework_reads_cap_choices_unmeasured(since):
    row = RM.compute(_full(capChoicesSince=since), FROM, UNTIL)
    assert row["measures"]["capChoices"] == U and _why(row)["capChoices"] == "before-cap-choice-recording"


def test_cap_choices_are_counted_with_what_happened_next():
    body = "\n".join([_cap("extra-audit-round", "k a"), _cap("rethink", "k2"), _cap("leftover", "k3")])
    recs = [_rec(1, "a", findings=[_f("k a", None)]),
            dict(_rec(1, "b", "2026-10-05T00:00:00Z", findings=[_f("k a"), _f("k2")], count=2),
                 rounds={"count": 2, "extraAudit": {"why": "cap"}}), _rec(2)]
    vets = [{"pr": 1, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": body},
            {"pr": 2, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": _cap("rethink")}]
    esc = [{"reviewedAt": "2026-10-03", "call": "seen-and-left", "pr": 1, "key": "k3"}]
    ci = [{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]
    cap = RM.compute(_full(records=recs, vetReceipts=vets, escapes=esc, ciRuns=ci), FROM, UNTIL)["measures"]["capChoices"]
    assert cap["extra-audit-round"] == {"count": 1, "outcomes": {"settled": 1}}
    assert cap["rethink"] == {"count": 2, "outcomes": {"converged": 1, "pending": 1}}
    assert cap["leftover"] == {"count": 1, "outcomes": {"escaped": 1}}


def test_an_unknown_cap_choice_spelling_reads_unmeasured():
    vets = [{"pr": 1, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": _cap("redo")}]
    row = RM.compute(_full(vetReceipts=vets), FROM, UNTIL)
    assert row["measures"]["capChoices"] == U and _why(row)["capChoices"] == "incomplete-evidence"


def _vet(body, pr=1, at="2026-10-04T00:00:00Z"):
    return {"pr": pr, "at": at, "sentBack": False, "body": body}


def _audit(at, session, *findings, count=3):
    """A record from an extra audit round: its rounds hold the `extraAudit` key."""
    return dict(_rec(1, session, at, findings=findings, count=count), rounds={"count": count, "extraAudit": {}})


def _caps(choice, recs, key="k1", **over):
    row = RM.compute(_full(records=recs, vetReceipts=[_vet(_cap(choice, key))], **over), FROM, UNTIL)
    return row["measures"]["capChoices"][choice]["outcomes"]


def test_leftover_outcomes_need_the_misses_log_and_a_false_pr_claim_is_no_escape():
    missing = _full(vetReceipts=[_vet(_cap("leftover"))])
    del missing["escapes"]  # never a TypeError and never not-escaped
    damaged = _full(vetReceipts=[_vet(_cap("leftover"))], escapes=[{"call": "missed"}])
    for inp, reason in ((missing, "no-misses-log-input"), (damaged, "incomplete-evidence")):
        row = RM.compute(inp, FROM, UNTIL)
        assert row["measures"]["capChoices"] == U and _why(row)["capChoices"] == reason == _why(row)["escapes"]
    claim = [{"reviewedAt": "2026-10-03", "call": "missed", "pr": 1, "key": "k1", "marker": "false-pr-claim"}]
    assert _caps("leftover", [_rec(1)], escapes=claim) == {"not-escaped": 1}
    plain = [{k: v for k, v in claim[0].items() if k != "marker"}]
    assert _caps("leftover", [_rec(1)], escapes=plain) == {"escaped": 1}  # without the marker it is an escape and counts


def test_a_leftover_outcome_is_escaped_not_escaped_or_unattributed_by_what_the_log_names():
    def log(*items):
        return [dict({"reviewedAt": "2026-10-03", "call": "seen-and-left"}, **i) for i in items]
    two = [_rec(1), _rec(2)]
    ci = [{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]
    got = lambda esc: _caps("leftover", two, escapes=esc, ciRuns=ci)  # noqa: E731
    assert got(log({"pr": 1, "key": "k1"})) == {"escaped": 1}
    assert got(log({"pr": 2, "key": "k1"}, {"pr": "2", "key": "k2"})) == {"not-escaped": 1}
    assert got(log({"pr": 2, "key": "k1"})) == {"not-escaped": 1}
    assert got(log({})) == {"unattributed": 1}  # no pr named
    assert got(log({"pr": 2, "key": "k1"}, {})) == {"unattributed": 1}  # one item names no pr
    assert got(log({"pr": 1})) == {"unattributed": 1}  # this pr, no key
    assert got(log({"pr": 1, "key": "k9"})) == {"unattributed": 1}  # this pr, another key


def test_a_vet_reads_a_clean_record_written_before_the_window():
    recs = [_rec(1, at="2026-09-30T10:00:00Z"),
            _rec(1, "b", "2026-10-02T10:00:00Z", findings=[_f("late", None)], status="not-reviewed")]
    vets = [{"pr": 1, "at": "2026-10-01T10:00:00Z", "sentBack": True, "body": ""}]
    m = RM.compute(_full(records=recs, vetReceipts=vets), FROM, UNTIL)["measures"]
    assert m["vetSendBacksOnCleanLoops"] == {"sentBack": 1, "cleanLoopsVetted": 1}


def test_each_cap_choice_reads_the_follow_up_record_it_names():
    after = lambda session, at, *f: _rec(1, session, at, findings=f)  # noqa: E731
    audit = "extra-audit-round"
    # an extra audit with a later non-audit record only is still pending
    assert _caps(audit, [_rec(1), after("b", "2026-10-05T00:00:00Z", _f("k1"))]) == {"pending": 1}
    # the earliest record holding extraAudit settles it, whatever is written before or after
    recs = [_rec(1), after("b", "2026-10-05T00:00:00Z", _f("k1", None)), _audit("2026-10-06T00:00:00Z", "c", _f("k1")),
            after("b", "2026-10-07T00:00:00Z", _f("k1", None))]
    assert _caps(audit, recs) == {"settled": 1}
    recs = [_audit("2026-10-05T00:00:00Z", "c", _f("k1", None)), _audit("2026-10-06T00:00:00Z", "d", _f("k1"))]
    assert _caps(audit, recs) == {"not-settled": 1}
    # a rethink reads the latest record of the session whose record was written first after the vet
    clean, open_ = after("x", "2026-10-05T00:00:00Z"), after("y", "2026-10-06T00:00:00Z", _f("k1", None))
    assert _caps("rethink", [_rec(1), clean, open_]) == {"converged": 1}
    assert _caps("rethink", [_rec(1), open_ | {"sessionId": "x", "writtenAt": "2026-10-05T00:00:00Z"},
                             clean | {"sessionId": "y", "writtenAt": "2026-10-06T00:00:00Z"}]) == {"not-converged": 1}
    assert _caps("rethink", [_rec(1)]) == {"pending": 1}


def test_a_rethink_reads_the_latest_record_of_the_first_follow_up_session():
    def later(first, second):
        return [_rec(1, "w", "2026-10-03T00:00:00Z"),  # written before the vet: not the follow-up
                _rec(1, "x", "2026-10-05T00:00:00Z", findings=[_f("k1", first)]),
                _rec(1, "x", "2026-10-06T00:00:00Z", findings=[_f("k1", second)]),
                _rec(1, "y", "2026-10-07T00:00:00Z", findings=[_f("k1", None)])]
    assert _caps("rethink", later(None, "fixed")) == {"converged": 1}
    assert _caps("rethink", later("fixed", None)) == {"not-converged": 1}


def test_a_rethink_skips_the_session_that_wrote_before_the_vet():
    a_before = _rec(1, "a", "2026-10-03T00:00:00Z", findings=[_f("k1", None)])
    a_after = _rec(1, "a", "2026-10-05T00:00:00Z", findings=[_f("k1", None)])  # rewritten after the vet, still open
    b = _rec(1, "b", "2026-10-06T00:00:00Z", findings=[_f("k1")])  # the follow-up session: fixed
    assert _caps("rethink", [a_before, a_after, b]) == {"converged": 1}
    assert _caps("rethink", [a_before, a_after]) == {"pending": 1}


def test_the_panel_counts_no_longer_carry_without_grounding():
    row = RM.compute(_full(), FROM, UNTIL)
    assert list(row["measures"]["panels"]) == ["sizes", "sessions"] and RM.MEASURE_KEYS["panels"] == ("sizes", "sessions")
    row["measures"]["panels"]["withoutGrounding"] = 0
    assert RM.problems(row)


def test_a_follow_up_outside_the_window_settles_a_cap_choice_and_nothing_else_reads_it():
    late = _audit("2026-10-09T00:00:00Z", "b", _f("k1"), count=9)
    body = "\n".join([_cap("extra-audit-round"), _cap("rethink", "k2")])
    row = RM.compute(_full(records=[_rec(1), late], vetReceipts=[_vet(body)]), FROM, UNTIL)
    cap = row["measures"]["capChoices"]
    assert cap["extra-audit-round"]["outcomes"] == {"settled": 1} and cap["rethink"]["outcomes"] == {"converged": 1}
    assert row["leftOut"]["outsideWindow"] == 1 and row["prs"] == 1
    assert row["measures"]["roundsPerPr"] == {"median": 2, "p90": 2}
    assert row["measures"]["sessionsPerPr"]["median"] == 1 and row["measures"]["panels"]["sessions"] == 1


@pytest.mark.parametrize("extra", [{"ok": False}, {"unreadFiles": ["a.json"]}, {"unreadFiles": "a.json"}])
def test_a_record_its_producer_marked_incomplete_makes_every_record_measure_unmeasured(extra):
    ci = [{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]
    row = RM.compute(_full(records=[_rec(1), dict(_rec(2), **extra)], ciRuns=ci), FROM, UNTIL)
    gone = ("roundsPerPr", "sessionsPerPr", "reviewerCostPerPr", "seats", "panels", "ci", "vetSendBacksOnCleanLoops", "capChoices")
    assert all(row["measures"][k] == U and _why(row)[k] == "incomplete-evidence" for k in gone)
    assert row["leftOut"]["malformed"] == 1 and row["prs"] == U
    for fine in ({"ok": True}, {"unreadFiles": []}, {"unreadFiles": None}):
        row = RM.compute(_full(records=[_rec(1), dict(_rec(2), **fine)], ciRuns=ci), FROM, UNTIL)
        assert row["prs"] == 2 and row["measures"]["roundsPerPr"] != U


def test_a_costly_measure_counts_only_with_its_source_and_names_it():
    good = {"basis": "sample", "value": 3, "source": SRC}
    row = RM.compute(_full(costly={"lateFindsOnUnchangedCode": good,
                                   "repeatFindingLocations": {"basis": "sample", "value": 3}}), FROM, UNTIL)
    assert row["measures"]["lateFindsOnUnchangedCode"] == good and RM.problems(row) == []
    assert list(row["measures"]["lateFindsOnUnchangedCode"]) == ["basis", "value", "source"]
    assert row["measures"]["repeatFindingLocations"] == U and _why(row)["repeatFindingLocations"] == "not-run-this-pass"
    for bad in ("", None, 7):
        row = RM.compute(_full(costly={"lateFindsOnUnchangedCode": dict(good, source=bad)}), FROM, UNTIL)
        assert row["measures"]["lateFindsOnUnchangedCode"] == U
        assert _why(row)["lateFindsOnUnchangedCode"] == "not-run-this-pass"


def test_a_nested_unmeasured_leaf_needs_its_reason():
    old = [{"name": "code-reviewer (round 1)", "ran": "engine-record", "commit": "c1"}]  # a record from before the cost field
    row = RM.compute(_full(records=[_rec(1, rows=old, sc=None)]), FROM, UNTIL)
    assert row["measures"]["reviewerCostPerPr"]["tokens"] == U and RM.problems(row) == []
    named = list(row["unmeasured"])
    row["unmeasured"] = [u for u in named if "." not in u["measure"]]  # the nested leaves lose their reasons
    assert any("reviewerCostPerPr.tokens" in p for p in RM.problems(row))
    row["unmeasured"] = [u for u in named if not u["measure"].startswith(("reviewerCostPerPr.", "seats."))] + [
        {"measure": "reviewerCostPerPr", "reason": "cost-not-recorded"}, {"measure": "seats", "reason": "cost-not-recorded"}]
    assert RM.problems(row) == []  # a dotted prefix names every leaf under it
    row["unmeasured"] = [dict(u, measure="reviewerCostPer") if u["measure"] == "reviewerCostPerPr" else u
                         for u in row["unmeasured"]]
    assert RM.problems(row)  # a bare string prefix is not a dotted prefix


@pytest.mark.parametrize("damage", [
    lambda r: r.update(window=None),
    lambda r: r.update(window={"from": "2026-10-08", "until": "2026-10-07"}),
    lambda r: r.update(window={"from": "2026-10-01", "until": "soon"}),
    lambda r: r["measures"].update(roundsPerPr={}),
    lambda r: r["measures"].update(roundsPerPr={"median": 2}),
    lambda r: r["measures"]["panels"].update(extra=1),
    lambda r: r["measures"]["capChoices"].pop("rethink"),
    lambda r: r["measures"].update(lateFindsOnUnchangedCode={"basis": "monthly", "value": 0}),
    lambda r: r["measures"].update(seats={"security-reviewer": 1})])
def test_the_row_shape_check_reaches_the_window_and_the_fixed_keys(damage):
    row = RM.compute(_full(), FROM, UNTIL)
    assert RM.problems(row) == []
    damage(row)
    assert RM.problems(row)


def test_a_damaged_cap_receipt_makes_the_cap_choices_unmeasured():
    vet = _vet(_cap("rethink"))
    del vet["body"]  # a receipt with no body is damaged input, not an empty one
    row = RM.compute(_full(vetReceipts=[vet]), FROM, UNTIL)
    assert row["measures"]["vetSendBacksOnCleanLoops"] == U and row["measures"]["capChoices"] == U
    assert _why(row)["vetSendBacksOnCleanLoops"] == _why(row)["capChoices"] == "incomplete-evidence"
    torn = "\n".join([_cap("rethink"), "<!-- superheroes:cap-choice choice=rethink vet=7 -->"])
    row = RM.compute(_full(vetReceipts=[_vet(torn)]), FROM, UNTIL)
    assert row["measures"]["capChoices"] == U and _why(row)["capChoices"] == "incomplete-evidence"
    assert row["measures"]["vetSendBacksOnCleanLoops"] != U  # only the cap choices lose their evidence


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    return str(d)


def _cli(tmp_path, repo, *args):
    out = subprocess.run([sys.executable, "-B", os.path.join(_LIB, "review_measures.py"), *args,
                          "--cwd", repo, "--root", str(tmp_path / "store")], capture_output=True, text=True)
    return out.returncode, json.loads(out.stdout)


def test_one_command_appends_the_row_and_a_second_run_replaces_that_windows_row(tmp_path, repo):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(_full()))
    base = ("row", "--input", str(inp), "--until", "2026-10-07")
    code, got = _cli(tmp_path, repo, *base, "--from", "2026-10-01")
    assert code == 0 and got["outcome"] == "appended"
    inp.write_text(json.dumps(_full(records=[_rec(1, count=5)])))
    code, got = _cli(tmp_path, repo, *base, "--from", "2026-10-01")
    assert code == 0 and got["outcome"] == "replaced"
    inp.write_text(json.dumps(_full(records=[_rec(1, count=7)])))  # the second window is written from other records
    _cli(tmp_path, repo, *base, "--from", "2026-10-02")
    with open(got["table"], encoding="utf-8") as fh:
        rows = [json.loads(x) for x in fh]
    assert [r["window"]["from"] for r in rows] == ["2026-10-01", "2026-10-02"]
    assert [r["measures"]["roundsPerPr"]["median"] for r in rows] == [5, 7] and all(RM.problems(r) == [] for r in rows)
    code, shown = _cli(tmp_path, repo, "render")
    lines = shown["markdown"].splitlines()
    assert code == 0 and "| roundsPerPr.median | 7 |" in lines and "| roundsPerPr.median | 5 |" not in lines
    assert lines[0].startswith("**Review-loop measures, 2026-10-02 to 2026-10-07**")  # the latest window heads the table
    assert "Unmeasured: repeatFindingLocations" in shown["markdown"]
    chart = lines[lines.index("median rounds per PR") + 1:]
    assert [(ln.split()[0], ln.split()[-1]) for ln in chart[:chart.index("```")]] == [("2026-10-01", "5"), ("2026-10-02", "7")]


def test_the_cli_refuses_bad_dates_and_a_non_object_input(tmp_path, repo):
    inp = tmp_path / "in.json"
    inp.write_text("[]")
    code, got = _cli(tmp_path, repo, "row", "--input", str(inp), "--from", "2026-10-01", "--until", "2026-10-07")
    assert code == 1 and got["reason"] == "bad-input"
    inp.write_text("{}")
    code, got = _cli(tmp_path, repo, "row", "--input", str(inp), "--from", "2026-10-08", "--until", "2026-10-07")
    assert code == 1 and got["reason"] == "bad-input"


def test_render_with_no_table_says_so(tmp_path, repo):
    assert _cli(tmp_path, repo, "render")[1]["markdown"] == "No review-loop measures row yet."
