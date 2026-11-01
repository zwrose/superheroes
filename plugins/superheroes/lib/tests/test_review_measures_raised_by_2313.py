"""Tests for #2313: the seating check counts catches by the seat that raised them (`raisedBy`), never by the lens a
finding names, and a seat's cost reads only the sessions that ran it. Records are built with the helpers of
test_review_measures.py."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_learning  # noqa: E402
import review_measures as RM  # noqa: E402
from test_review_measures import FROM, UNTIL, U, _by, _f, _filled, _full, _rec, _row, _sc, _why  # noqa: E402

CODE, PRE, SEC = "code-reviewer (round 1)", "premortem-reviewer (round 1)", "security-reviewer (round 1)"
NO_RAISER = "raising-seat-not-recorded"


def _raised(key, raised_by, lens, outcome="fixed"):
    """A finding in `lens`, raised by the run `raised_by` names."""
    return dict(_f(key, outcome, lens), raisedBy=raised_by)


def _compute(*recs, **over):
    ci = [{"pr": pr, "minutes": 1} for pr in sorted({r["pr"] for r in recs})]
    row = RM.compute(_full(records=list(recs), ciRuns=ci, **over), FROM, UNTIL)
    assert RM.problems(row) == []  # every figure the row shows as unmeasured carries its reason
    return row


def _seats(row):
    return row["measures"]["seats"]


def test_a_finding_raised_by_the_code_seat_in_the_premortem_lens_counts_for_code_not_premortem():
    rec = _rec(1, rows=[_row(CODE), _row(PRE)], findings=[_raised("k1", "code-reviewer", "Failure-Mode")],
               sc=_sc(200, 3.0, runs=2, by_seat={"code-reviewer": _by(100, 1.5), "premortem-reviewer": _by(100, 1.5)}))
    seats = _seats(_compute(rec))
    assert seats["code-reviewer"]["outcomes"] == _filled(fixed=1)
    assert seats["premortem-reviewer"]["outcomes"] == _filled()  # it ran and raised nothing: zero, not the lens's catch
    assert "unattributed" not in seats


def test_a_pr_where_premortem_never_ran_adds_nothing_to_its_catches_even_with_a_premortem_lens_finding():
    no_premortem = _rec(1, rows=[_row(CODE)], findings=[_raised("k1", "code-reviewer", "Failure-Mode")],
                        sc=_sc(100, 1.5, by_seat={"code-reviewer": _by(100, 1.5)}))
    premortem_ran = _rec(2, rows=[_row(PRE)], sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
    row = _compute(no_premortem, premortem_ran)
    seats = _seats(row)
    assert seats["premortem-reviewer"]["outcomes"] == _filled()
    assert seats["code-reviewer"]["outcomes"] == _filled(fixed=1)
    shown = review_learning.seating(row["seatingRow"])["seats"]["premortem"]["outcomes"]
    assert shown["fixed"] == 0  # a measured zero, not unmeasured


def test_a_carried_finding_keeps_the_seat_that_raised_it_across_sessions():
    first = _rec(1, "a", "2026-10-02T10:00:00Z", rows=[_row(CODE), _row(PRE)],
                 findings=[_raised("k1", "premortem-reviewer", "Failure-Mode", None)],
                 sc=_sc(200, 3.0, runs=2, by_seat={"code-reviewer": _by(100, 1.5), "premortem-reviewer": _by(100, 1.5)}))
    carried_row = dict(_row(PRE), carried={"commit": "c0"})  # the premortem seat did not run again in the later session
    later = _rec(1, "b", "2026-10-04T10:00:00Z", rows=[_row(CODE), carried_row],
                 findings=[_raised("k1", "premortem-reviewer", "Code")],  # the lens differs; the raiser is the earlier run's
                 sc=_sc(100, 1.5, by_seat={"code-reviewer": _by(100, 1.5)}))
    for order in ([first, later], [later, first]):
        seats = _seats(_compute(*order))
        assert seats["premortem-reviewer"]["outcomes"] == _filled(fixed=1)
        assert seats["code-reviewer"]["outcomes"] == _filled()


def test_a_record_without_the_field_reads_unmeasured_for_the_seats_that_ran_on_its_pr_only():
    unstamped = {k: v for k, v in _raised("k1", "x", "Security").items() if k != "raisedBy"}
    # PR 1: security ran in the window, code ran in an earlier record of the same PR (outside it); no finding names its raiser
    old_code = _rec(1, "old", "2026-09-20T10:00:00Z", rows=[_row(CODE)], sc=None)
    pr1 = _rec(1, "a", rows=[_row(SEC)], findings=[unstamped, _raised("k2", "security-reviewer", "Security")],
               sc=_sc(100, 1.5, by_seat={"security-reviewer": _by(100, 1.5)}))
    # PR 2: fully stamped; premortem ran only here
    pr2 = _rec(2, rows=[_row(PRE)], findings=[_raised("k3", "premortem-reviewer", "Failure-Mode")],
               sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
    row = _compute(old_code, pr1, pr2)
    seats, why = _seats(row), _why(row)
    for seat in ("security-reviewer", "code-reviewer"):
        assert seats[seat]["outcomes"] == U and why["seats.%s.outcomes" % seat] == NO_RAISER
    assert seats["security-reviewer"]["tokens"] == 100  # the cost is a separate measure and still reads
    assert seats["premortem-reviewer"]["outcomes"] == _filled(fixed=1)
    assert "seats.premortem-reviewer.outcomes" not in why
    shown = review_learning.seating(row["seatingRow"])
    assert all(v == U for v in shown["seats"]["security"]["outcomes"].values())
    assert "security.outcomes.fixed" in shown["unmeasured"] and shown["seats"]["premortem"]["outcomes"]["fixed"] == 1


def test_a_receiptless_review_with_a_premortem_lens_finding_does_not_blank_premortems_cost():
    receiptless = _rec(1, rows=[_row(CODE)], findings=[_raised("k1", "code-reviewer", "Failure-Mode")], sc=None)
    costed = _rec(2, rows=[_row(PRE)], sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
    row = _compute(receiptless, costed)
    seats = _seats(row)
    assert seats["premortem-reviewer"]["tokens"] == 7 and seats["premortem-reviewer"]["minutes"] == 0.2
    assert seats["code-reviewer"]["tokens"] == U and _why(row)["seats.code-reviewer.tokens"] == "cost-not-recorded"
    assert review_learning.seating(row["seatingRow"])["seats"]["premortem"]["tokens"] == 7


def test_a_seat_that_ran_in_a_session_with_an_incomplete_cost_reads_unmeasured():
    incomplete = _rec(1, "a", rows=[_row(PRE)], sc=_sc(5, 0.1, runs=2, without=1, by_seat={"premortem-reviewer": _by(5, 0.1, 2)}))
    complete = _rec(1, "b", rows=[_row(PRE)], sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
    row = _compute(incomplete, complete)
    seats = _seats(row)
    assert seats["premortem-reviewer"]["tokens"] == U and seats["premortem-reviewer"]["minutes"] == U
    assert _why(row)["seats.premortem-reviewer.tokens"] == "cost-not-recorded"
    assert review_learning.seating(row["seatingRow"])["seats"]["premortem"]["tokens"] == U


def test_a_complete_cost_that_leaves_out_a_seat_that_ran_makes_that_seats_cost_unmeasured():
    # S6 v0: session a costs premortem; session b ran premortem too, and its complete cost names only the code seat
    a = _rec(1, "a", rows=[_row(PRE)], sc=_sc(7, 0.2, by_seat={"premortem-reviewer": _by(7, 0.2)}))
    b = _rec(1, "b", rows=[_row(CODE), _row(PRE)], sc=_sc(100, 1.5, by_seat={"code-reviewer": _by(100, 1.5)}))
    row = _compute(a, b)
    seats = _seats(row)
    assert seats["premortem-reviewer"]["tokens"] == U and seats["premortem-reviewer"]["minutes"] == U
    assert _why(row)["seats.premortem-reviewer.tokens"] == "cost-not-recorded"
    assert seats["code-reviewer"]["tokens"] == 100 and seats["code-reviewer"]["minutes"] == 1.5
    # a seat a complete cost names that no row shows ran (a verifier key) still adds its figures
    v = _rec(2, rows=[_row(SEC)], sc=_sc(130, 2.0, runs=2, by_seat={"security-reviewer": _by(100, 1.5),
                                                                    "verifiers code-reviewer": _by(30, 0.5)}))
    got = _seats(_compute(v))
    assert got["security-reviewer"]["tokens"] == 100 and got["code-reviewer"]["tokens"] == 30
