"""#2545: the gardening pass reads minutes from a session whose only shortfall is partial runs.

A partial run's minutes are every attempt's wall time; only its tokens are short. So a session's tokens are read only
when its `sessionCost` is complete, and its minutes when no run lacks a figure (complete, or partial-only). That one
reading governs the per-PR reviewer cost (`reviewerCostPerPr.<k>`, `prsLeftOut.<k>`) and the per-seat cost
(`seats.<s>.<k>`). A session with a run lacking a figure, or with no well-formed `sessionCost`, still leaves its PR and
its seats unmeasured for both.

Bite-proof record: i2545_partial_minutes
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_measures as RM  # noqa: E402
from test_partial_cost_2514 import _SEC, _psc  # noqa: E402,F401
from test_review_measures import FROM, UNTIL, U, _by, _full, _rec, _row, _sc, _why  # noqa: E402

PROOF = "plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md"
_CODE = [_row("code-reviewer (round 1)")]
_PREM = [_row("premortem-reviewer (round 1)")]


def _ci(*prs):
    return [{"pr": n, "minutes": 1} for n in prs]


def test_t1_a_pr_whose_only_shortfall_is_partial_runs_counts_in_the_minutes_figures_only():
    # axis: a PR whose only shortfall is partial runs counts in the minutes figures and stays out of the tokens figures, for the PR cost and the seat cost
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
    partial = _psc(40, 2.5, by_seat={"code-reviewer": _by(40, 2.5)})
    row = RM.compute(_full(records=[_rec(1), _rec(2, rows=_CODE, sc=partial)], ciRuns=_ci(1, 2)), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["minutes"]["total"] == 4.0 and cost["minutes"]["median"] == 2.0
    assert cost["tokens"]["total"] == 100 and cost["tokens"]["median"] == 100
    assert cost["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 1, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    assert cost["prsLeftOut"]["minutes"] == {"count": 0, "why": RM.LEFT_OUT_WHY, "partial": 0, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    seats, why = row["measures"]["seats"], _why(row)
    assert seats["security-reviewer"]["tokens"] == 100 and seats["security-reviewer"]["minutes"] == 1.5
    assert seats["code-reviewer"]["minutes"] == 2.5 and "seats.code-reviewer.minutes" not in why
    assert seats["code-reviewer"]["tokens"] == U and why["seats.code-reviewer.tokens"] == "cost-partial"
    assert "reviewerCostPerPr.minutes" not in why and "reviewerCostPerPr.tokens" not in why
    assert RM.problems(row) == []
    # a window holding only the partial PR: its minutes are measured, its tokens are not
    row = RM.compute(_full(records=[_rec(2, rows=_CODE, sc=partial)], ciRuns=_ci(2)), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["minutes"]["total"] == 2.5 and cost["minutes"]["median"] == 2.5
    assert cost["tokens"] == U and _why(row)["reviewerCostPerPr.tokens"] == "no-measured-pr"
    assert "reviewerCostPerPr.minutes" not in _why(row)
    assert cost["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 1, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    assert cost["prsLeftOut"]["minutes"] == {"count": 0, "why": RM.LEFT_OUT_WHY, "partial": 0, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    assert RM.problems(row) == []


def test_t2_a_session_with_a_run_lacking_a_figure_leaves_the_pr_out_of_both():
    # axis: a session with a run lacking a figure, a partial run beside it or not, leaves its PR and its seats unmeasured for tokens and minutes
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
    beside = _psc(30, 3.0, runs=2, partial=1, without=1, by_seat={"code-reviewer": _by(30, 3.0, runs=2)})
    alone = _sc(30, 3.0, runs=2, without=1, by_seat={"premortem-reviewer": _by(30, 3.0, runs=2)})
    records = [_rec(1), _rec(2, rows=_CODE, sc=beside), _rec(3, rows=_PREM, sc=alone)]
    row = RM.compute(_full(records=records, ciRuns=_ci(1, 2, 3)), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
    for k in ("tokens", "minutes"):
        assert cost["prsLeftOut"][k] == {"count": 2, "why": RM.LEFT_OUT_WHY, "partial": 1, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}, k
    seats, why = row["measures"]["seats"], _why(row)
    assert seats["security-reviewer"]["tokens"] == 100 and seats["security-reviewer"]["minutes"] == 1.5
    for seat in ("code-reviewer", "premortem-reviewer"):
        for k in ("tokens", "minutes"):
            assert seats[seat][k] == U and why["seats.%s.%s" % (seat, k)] == "cost-not-recorded", (seat, k)
    assert RM.problems(row) == []
    # a window holding only the one with a partial run beside a run lacking a figure: nothing measured for either
    row = RM.compute(_full(records=[_rec(2, rows=_CODE, sc=beside)], ciRuns=_ci(2)), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"] == U and cost["minutes"] == U
    assert _why(row)["reviewerCostPerPr.tokens"] == "no-measured-pr" and _why(row)["reviewerCostPerPr.minutes"] == "no-measured-pr"


def test_t3_a_pr_whose_sessions_are_all_complete_reads_as_today():
    # axis: a window of complete sessions reads exactly as before: both figures measured, nothing left out, no seat reason
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
    second = _sc(50, 2.0, by_seat={"security-reviewer": _by(50, 2.0)})
    row = RM.compute(_full(records=[_rec(1, "a"), _rec(1, "b", sc=second)]), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"] == {"median": 150, "p90": 150, "total": 150, "topTenthShare": 1.0}
    assert cost["minutes"] == {"median": 3.5, "p90": 3.5, "total": 3.5, "topTenthShare": 1.0}
    none_left = {"count": 0, "why": RM.LEFT_OUT_WHY, "partial": 0, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    assert cost["prsLeftOut"] == {"tokens": none_left, "minutes": none_left}
    seats = row["measures"]["seats"]
    assert seats["security-reviewer"]["tokens"] == 150 and seats["security-reviewer"]["minutes"] == 3.5
    assert not [r for r in _why(row) if r.startswith(("seats.", "reviewerCostPerPr"))]
    assert RM.problems(row) == []
    row = RM.compute(_full(), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
    assert cost["prsLeftOut"] == {"tokens": none_left, "minutes": none_left}
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == 100 and row["measures"]["seats"]["security-reviewer"]["minutes"] == 1.5


def test_t4_census_every_seat_reads_tokens_and_minutes_through_their_own_rule():
    # axis: each seat reads its tokens through the complete rule and its minutes through the no-run-lacking-a-figure rule, never one measure's blanking for the other
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2545_partial_minutes.md
    complete = _sc(120, 2.0, by_seat={"security-reviewer": _by(100, 1.5), "code-reviewer": _by(20, 0.5)})
    partial = _psc(50, 3.0, by_seat={"premortem-reviewer": _by(40, 2.5), "security-reviewer": _by(10, 0.5)})
    lacking = _sc(7, 0.9, runs=2, without=1, by_seat={"code-reviewer": _by(7, 0.9, runs=2)})
    records = [
        _rec(1, rows=[_row("security-reviewer (round 1)"), _row("code-reviewer (round 1)")], sc=complete),
        _rec(2, rows=[_row("premortem-reviewer (round 1)"), _row("security-reviewer (round 1)")], sc=partial),
        _rec(3, rows=_CODE, sc=lacking)]
    row = RM.compute(_full(records=records, ciRuns=_ci(1, 2, 3)), FROM, UNTIL)
    seats, why = row["measures"]["seats"], _why(row)
    assert set(seats) == {"security-reviewer", "code-reviewer", "premortem-reviewer"}
    expected = {  # seat: (tokens, tokens reason, minutes, minutes reason)
        "security-reviewer": (U, "cost-partial", 2.0, None),  # the partial session blanks its tokens only
        "premortem-reviewer": (U, "cost-partial", 2.5, None),  # named only by the partial session
        "code-reviewer": (U, "cost-not-recorded", U, "cost-not-recorded"),  # the lacking session blanks both
    }
    for seat, (tokens, tokens_why, minutes, minutes_why) in expected.items():
        assert seats[seat]["tokens"] == tokens, seat
        assert seats[seat]["minutes"] == minutes, seat
        assert why.get("seats.%s.tokens" % seat) == tokens_why, seat
        assert why.get("seats.%s.minutes" % seat) == minutes_why, seat
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 120 and cost["minutes"]["total"] == 5.0
    assert cost["prsLeftOut"]["tokens"] == {"count": 2, "why": RM.LEFT_OUT_WHY, "partial": 1, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    assert cost["prsLeftOut"]["minutes"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 0, "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}
    assert RM.problems(row) == []
