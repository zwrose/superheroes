"""A PR left out of the reviewer-cost figure only because it was hand-written reads so (issue 2515).

`prsLeftOut.<tokens|minutes>.handWritten` counts a left-out PR whose every unmeasured in-window session has a latest
record with no `sessionCost` key at all; every other left-out PR stays in `count`. No figure changes.

Edges: E6 a `sessionCost` that is present but malformed or incomplete is incomplete, never hand-written.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_measures as RM  # noqa: E402

from test_review_measures import FROM, UNTIL, _full, _rec, _sc  # noqa: E402

CI = [{"pr": n, "minutes": 1} for n in (1, 2, 3)]
LATER = "2026-10-04T10:00:00Z"


def left_out(*records, k="tokens"):
    row = RM.compute(_full(records=list(records), ciRuns=CI), FROM, UNTIL)
    assert RM.problems(row) == []
    return row["measures"]["reviewerCostPerPr"]["prsLeftOut"][k]


def test_a_pr_whose_only_session_has_no_sessionCost_key_reads_hand_written():
    # axis: a session whose latest record carries no sessionCost key at all counts under handWritten, never in count
    want = {"count": 0, "why": RM.LEFT_OUT_WHY, "partial": 0, "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}}
    assert left_out(_rec(1, sc=None)) == want
    assert left_out(_rec(1, sc=None), k="minutes") == want


def test_the_hand_written_reason_is_pinned():
    # axis: the label a reader sees
    assert RM.HAND_WRITTEN_WHY == "cost not measured (hand-written)"


def test_an_incomplete_sessionCost_is_incomplete_never_hand_written():
    # axis: E6, a sessionCost key that is present but incomplete stays in count
    bad = _sc(100, 1.5, runs=2, without=1)
    assert left_out(_rec(1, sc=bad)) == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 0,
                                         "handWritten": {"count": 0, "why": RM.HAND_WRITTEN_WHY}}


def test_a_complete_session_and_a_later_hand_written_one_leave_the_pr_out_as_hand_written():
    # axis: the figure is unmeasured by the hand-written session alone, so the PR reads hand-written
    got = left_out(_rec(1, "s1"), _rec(1, "s2", at=LATER, sc=None))
    assert got["count"] == 0 and got["handWritten"]["count"] == 1


def test_an_incomplete_session_beside_a_hand_written_one_is_incomplete():
    # axis: every unmeasured session must be hand-written; one incomplete session makes the PR incomplete
    bad = _sc(100, 1.5, runs=2, without=1)
    got = left_out(_rec(1, "s1", sc=bad), _rec(1, "s2", at=LATER, sc=None))
    assert got["count"] == 1 and got["handWritten"]["count"] == 0


def test_a_malformed_sessionCost_is_incomplete_never_hand_written():
    # axis: E6, a sessionCost key that is present but malformed stays in count
    for bad in ({"tokens": "x"}, [], 5, {}):
        got = left_out(_rec(1, sc=bad))
        assert got["count"] == 1 and got["handWritten"]["count"] == 0, bad


def test_a_measured_pr_stays_measured_with_the_same_figures():
    # axis: no figure changes, and the two counts sum to the PRs left out
    row = RM.compute(_full(records=[_rec(1), _rec(2, sc=None), _rec(3, sc=_sc(1, 1, runs=2, without=1))], ciRuns=CI), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
    assert cost["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 0,
                                            "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}}
    assert RM.problems(row) == []


def _psc(tokens, minutes, runs=1, partial=1, without=0, by_seat=None):
    """A record's `sessionCost` with partial runs, the shape `test_partial_cost_2514._psc` builds: never complete."""
    return dict(_sc(tokens, minutes, runs=runs, without=without, by_seat=by_seat), runsPartial=partial, complete=False)


def test_partial_and_hand_written_prs_read_together_and_partial_never_exceeds_count():
    # axis: each measure is read on its own and partial counts only PRs under count: PR 4 (a partial session beside one with no sessionCost key) is hand-written for minutes and under count and partial for tokens, a hand-only PR adds nothing to partial, and partial never exceeds count
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2515_hand_cost.md
    records = [
        _rec(1),                                                     # PR 1: one complete session, measured
        _rec(2, sc=_psc(100, 1.5)),                                  # PR 2: one partial session
        _rec(3, sc=None),                                            # PR 3: no sessionCost key, hand-written
        _rec(4, "s1", sc=_psc(100, 1.5)),                            # PR 4: a partial session ...
        _rec(4, "s2", at=LATER, sc=None),                            # ... and a later one with no sessionCost key
    ]
    # a partial session is whole for minutes: PR 2 is measured there, and PR 4 is left out of minutes only by its hand-written session
    want = {"tokens": {"count": 2, "why": RM.LEFT_OUT_WHY, "partial": 2,
                       "handWritten": {"count": 1, "why": RM.HAND_WRITTEN_WHY}},
            "minutes": {"count": 0, "why": RM.LEFT_OUT_WHY, "partial": 0,
                        "handWritten": {"count": 2, "why": RM.HAND_WRITTEN_WHY}}}
    for k in ("tokens", "minutes"):
        got = left_out(*records, k=k)
        assert got == want[k], k
        assert got["partial"] <= got["count"], k
    row = RM.compute(_full(records=records, ciRuns=CI), FROM, UNTIL)
    assert RM.problems(row) == []


def test_a_pr_left_out_for_tokens_only_counts_under_tokens_alone():
    # axis: the counts are read per measure; a partial-only PR is left out of tokens and measured for minutes, a PR with a run lacking a figure is left out of both
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2515_hand_cost.md
    records = [
        _rec(1, sc=_psc(100, 1.5)),                       # PR 1: its only session is partial
        _rec(2, sc=_sc(100, 1.5, runs=2, without=1)),     # PR 2: its only session has a run lacking a figure
    ]
    tokens, minutes = left_out(*records, k="tokens"), left_out(*records, k="minutes")
    assert (tokens["count"], tokens["partial"], tokens["handWritten"]["count"]) == (2, 1, 0)
    assert (minutes["count"], minutes["partial"], minutes["handWritten"]["count"]) == (1, 0, 0)
    for got in (tokens, minutes):
        assert got["partial"] <= got["count"]
