"""#2514: a run whose first attempt the silence watchdog ended still counts the cost it measured.

A watchdog-ended attempt with no usage total adds its wall time and no tokens when another attempt measured: the run's
`attemptsCost` carries `tokensUnmeasured`, its session's `sessionCost` carries `runsPartial` and is never `complete`, and
the measures row counts the PR as left out (`prsLeftOut.<k>.partial`) and reads a seat only partial sessions blank as
`cost-partial`. A run whose attempts all measured reads as before.

Bite-proof record: i2514_partial_cost
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine_adapter as EA  # noqa: E402
import engine_dispatch as ED  # noqa: E402
import review_measures as RM  # noqa: E402
import review_record as rr  # noqa: E402
import test_review_record as trr  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_review_measures import FROM, UNTIL, U, _full, _rec, _sc, _why  # noqa: E402
from test_review_record_session import GOOD_RUN  # noqa: E402
from test_session_cost_every_attempt_2381 import (  # noqa: E402
    NONCE, TIMED_OUT, attempt, execution_record, journal_run, session_cost, stream)

PROOF = "plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md"
WATCHDOG = {"signalSource": "silence-watchdog",
            "silenceWatchdog": {"silentSeconds": 600.0, "thresholdSeconds": 600, "killAt": 1.0}}
RACE = {"silenceWatchdogRace": {"silentSeconds": 600.0, "thresholdSeconds": 600, "killAt": 1.0}}
RETRY = dict(input_tokens=50, output_tokens=10)  # 60 tokens


def _partial_record(tmp_path):
    """The engine record of a run whose watchdog-ended first attempt left no usage, then a measured retry."""
    return execution_record(tmp_path, [attempt(stream(events=False), 600, **WATCHDOG), attempt(stream(**RETRY), 30)])


def test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run(tmp_path):
    # axis: a watchdog-ended attempt with no usage total leaves its tokens unmeasured, not the whole run, when another attempt measured
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    record = _partial_record(tmp_path)
    assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["minutes"], cost["runs"]) == (60, 10.5, 1)
    assert (cost["runsPartial"], cost["runsWithoutFigure"], cost["complete"]) == (1, 0, False)
    assert cost["bySeat"] == {"code-reviewer": {"tokens": 60, "minutes": 10.5, "runs": 1}}


def test_t1b_every_unmeasured_attempt_is_named_in_ascending_order(tmp_path):
    # axis: every watchdog-ended attempt that left no usage total is named, ascending, and adds its wall time
    record = execution_record(tmp_path, [
        attempt(stream(events=False), 100, **WATCHDOG), attempt(stream(**RETRY), 30),
        attempt(stream(events=False), 200, **WATCHDOG), attempt(stream(**RETRY), 40)])
    assert record["attemptsCost"] == {"tokens": 120, "wallSeconds": 370, "attempts": 4, "tokensUnmeasured": [1, 3]}


def test_t2_a_watchdog_ended_attempt_with_an_empty_usage_is_unmeasured_not_zero(tmp_path):
    # axis: an empty usage on a watchdog-ended attempt is no figure, never a measured zero
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    record = execution_record(tmp_path, [attempt(stream(), 600, **WATCHDOG), attempt(stream(**RETRY), 30)])
    assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["minutes"], cost["runsPartial"], cost["runsWithoutFigure"], cost["complete"]) == (60, 10.5, 1, 0, False)


def test_t3_a_watchdog_ended_attempt_with_only_none_parts_is_unmeasured_not_zero(tmp_path):
    # axis: a usage whose parts are all None on a watchdog-ended attempt is no figure, never a measured zero
    record = execution_record(tmp_path, [
        attempt(stream(input_tokens=None, output_tokens=None), 600, **WATCHDOG), attempt(stream(**RETRY), 30)])
    assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["minutes"], cost["runsPartial"], cost["runsWithoutFigure"], cost["complete"]) == (60, 10.5, 1, 0, False)


def test_t3b_the_explicit_flag_changes_only_what_an_empty_usage_reads_as():
    # axis: codex_usage_tokens reads an empty usage as 0 by default and as no figure only with explicit=True; an explicit 0 part is a figure
    assert EA.codex_usage_tokens(stream()) == 0 and EA.codex_usage_tokens(stream(), explicit=True) is None
    nones = stream(input_tokens=None, output_tokens=None)
    assert EA.codex_usage_tokens(nones) == 0 and EA.codex_usage_tokens(nones, explicit=True) is None
    zero = stream(input_tokens=0, output_tokens=0)
    assert EA.codex_usage_tokens(zero) == 0 and EA.codex_usage_tokens(zero, explicit=True) == 0
    real = stream(input_tokens=50, output_tokens=10)
    assert EA.codex_usage_tokens(real) == 60 and EA.codex_usage_tokens(real, explicit=True) == 60
    assert EA.codex_usage_tokens(stream(events=False), explicit=True) is None and EA.codex_usage_tokens("", explicit=True) is None


def test_t4_a_watchdog_ended_attempt_with_a_real_usage_total_is_summed_as_before(tmp_path):
    # axis: a watchdog-ended attempt that measured adds its tokens like any attempt and leaves the run whole
    record = execution_record(tmp_path, [
        attempt(stream(input_tokens=30, output_tokens=10), 600, **WATCHDOG), attempt(stream(**RETRY), 30)])
    assert record["attemptsCost"] == {"tokens": 100, "wallSeconds": 630, "attempts": 2}
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["minutes"], cost["runsWithoutFigure"], cost["complete"]) == (100, 10.5, 0, True)
    assert "runsPartial" not in cost


def test_t4b_a_watchdog_ended_attempt_with_an_explicit_zero_usage_is_a_measured_zero(tmp_path):
    # axis: an explicit zero usage on a watchdog-ended attempt is a measured figure, so the run is whole
    record = execution_record(tmp_path, [
        attempt(stream(input_tokens=0, cached_input_tokens=0, output_tokens=0), 600, **WATCHDOG), attempt(stream(**RETRY), 30)])
    assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2}


def seam_cost(tmp_path, attempts):
    """`_attempts_cost` read straight off the journaled run: `run_execution_record` refuses (`attempt-not-completed`) a run
    whose last attempt is a watchdog end, so a run with no measured attempt cannot reach `attemptsCost` through it."""
    run_dir = journal_run(tmp_path, attempts)
    assert ED.run_execution_record(run_dir) == (None, "attempt-not-completed")
    records, _ = ED._journal_read(run_dir)
    return ED._attempts_cost(os.path.realpath(run_dir), ED._journal_state(records))


def test_t5_a_single_watchdog_ended_attempt_with_no_usage_has_no_figure(tmp_path):
    # axis: a run with no measured attempt has no figure, however the watchdog ended its attempts
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    assert seam_cost(tmp_path, [attempt(stream(events=False), 600, **WATCHDOG)]) is None


def test_t5b_every_attempt_watchdog_ended_with_no_usage_has_no_figure(tmp_path):
    # axis: a run whose every attempt is an unmeasured watchdog end has no figure
    assert seam_cost(tmp_path, [attempt(stream(events=False), 600, **WATCHDOG), attempt(stream(), 500, **WATCHDOG)]) is None


def test_t5c_one_measured_attempt_among_unmeasured_watchdog_ends_is_enough_for_a_figure(tmp_path):
    # axis: a single measured attempt among unmeasured watchdog ends gives a partial figure at the seam
    got = seam_cost(tmp_path, [attempt(stream(events=False), 600, **WATCHDOG), attempt(stream(**RETRY), 30, **WATCHDOG)])
    assert got == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}


def test_t6_a_timed_out_attempt_that_the_watchdog_did_not_end_keeps_the_all_or_nothing_rule(tmp_path):
    # axis: only a silence-watchdog end may leave its tokens unmeasured; any other attempt without usage leaves the run without a figure
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    record = execution_record(tmp_path, [attempt(stream(events=False), 900, **TIMED_OUT), attempt(stream(**RETRY), 30)])
    assert record["attemptsCost"] is None
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (0, 1, 1, False)
    assert "runsPartial" not in cost


def test_t7_a_watchdog_race_attempt_is_not_a_watchdog_end(tmp_path):
    # axis: an attempt that answered before the watchdog killed it (the race record) keeps today's all-or-nothing rule
    record = execution_record(tmp_path, [attempt(stream(events=False), 600, **RACE), attempt(stream(**RETRY), 30)])
    assert record["attemptsCost"] is None


def test_t8_a_run_whose_attempts_all_measured_reads_exactly_as_before(tmp_path):
    # axis: a run of whole attempts carries exactly the three keys and its session cost carries no runsPartial
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    record = execution_record(tmp_path, [
        attempt(stream(input_tokens=30, output_tokens=10), 900, **TIMED_OUT),
        attempt(stream(input_tokens=50, cached_input_tokens=0, output_tokens=10), 30)])
    assert set(record["attemptsCost"]) == {"tokens", "wallSeconds", "attempts"}
    assert session_cost(tmp_path, record) == {
        "tokens": 100, "minutes": 15.5, "runs": 1, "runsWithoutFigure": 0, "complete": True,
        "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 15.5, "runs": 1}}}


_WHOLE = {"tokens": 100, "wallSeconds": 120, "attempts": 2}


@pytest.mark.parametrize("bad", [[], [0], "1"], ids=["empty-list", "zero-attempt", "string"])
def test_t9_a_malformed_tokens_unmeasured_makes_the_run_one_without_a_figure(tmp_path, bad):
    # axis: a tokensUnmeasured that is not a non-empty list of attempt numbers makes the run one without a figure, never a whole one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    engine_record = dict(GOOD_RUN, runnerNonce=NONCE, attemptsCost=dict(_WHOLE, tokensUnmeasured=bad))
    cost = session_cost(tmp_path, engine_record)
    assert (cost["tokens"], cost["minutes"], cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (0, 0.0, 1, 1, False)
    assert "runsPartial" not in cost


def test_t9b_a_well_formed_tokens_unmeasured_is_a_partial_run_with_its_figure(tmp_path):
    # axis: a tokensUnmeasured that is a non-empty list of attempt numbers makes the run partial and adds its figure
    engine_record = dict(GOOD_RUN, runnerNonce=NONCE, attemptsCost=dict(_WHOLE, tokensUnmeasured=[1]))
    cost = session_cost(tmp_path, engine_record)
    assert (cost["tokens"], cost["minutes"], cost["runs"], cost["runsWithoutFigure"], cost["runsPartial"], cost["complete"]) == (
        100, 2.0, 1, 0, 1, False)


PARTIAL = {"tokens": 10, "minutes": 1.0, "runs": 1, "runsWithoutFigure": 0, "runsPartial": 1, "complete": False,
           "bySeat": {"code-reviewer": {"tokens": 10, "minutes": 1.0, "runs": 1}}}
CHECK_BAD = [
    ("partial-but-complete", dict(PARTIAL, complete=True), "sessionCost.complete"),
    ("partial-zero", dict(PARTIAL, runsPartial=0), "sessionCost.runsPartial"),
    ("partial-bool", dict(PARTIAL, runsPartial=True), "sessionCost.runsPartial"),
    ("partial-negative", dict(PARTIAL, runsPartial=-1), "sessionCost.runsPartial"),
    ("partial-string", dict(PARTIAL, runsPartial="1"), "sessionCost.runsPartial"),
    ("partial-over-the-runs", dict(PARTIAL, runsPartial=2), "sessionCost.runsPartial"),
    ("partial-with-unfigured-over-the-runs",
     dict(PARTIAL, runs=2, runsWithoutFigure=1, runsPartial=2, bySeat={"code-reviewer": {"tokens": 10, "minutes": 1.0, "runs": 2}}),
     "sessionCost.runsPartial"),
]


@pytest.mark.parametrize("cost,detail", [(c, d) for _, c, d in CHECK_BAD], ids=[i for i, _, _ in CHECK_BAD])
def test_t10_the_account_check_refuses_a_malformed_partial_session_cost(tmp_path, cost, detail):
    # axis: a sessionCost whose runsPartial is malformed, out of bound, or beside complete: true is review-account-invalid and nothing is posted
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    fake = trr.Fake()
    out = rr.write(trr.put(tmp_path, trr.account(sessionCost=cost)), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == detail, out
    assert fake.comments == []


def test_t10b_the_account_check_accepts_a_well_formed_partial_session_cost_and_the_writers_own(tmp_path):
    # axis: a partial sessionCost, as given or as the session writer writes it, is accepted and read back whole
    fake = trr.Fake()
    assert rr.write(trr.put(tmp_path, trr.account(sessionCost=PARTIAL)), str(tmp_path), fake.readers())["ok"]
    assert rr.read(7, readers=fake.readers())["sessionCost"] == PARTIAL
    (tmp_path / "w").mkdir()
    written_cost = session_cost(tmp_path / "w", _partial_record(tmp_path / "w"))
    assert written_cost["runsPartial"] == 1 and written_cost["complete"] is False
    again = trr.Fake()
    assert rr.write(trr.put(tmp_path, trr.account(sessionCost=written_cost), name="written.json"), str(tmp_path), again.readers())["ok"]
    assert rr.read(7, readers=again.readers())["sessionCost"] == written_cost


def _psc(tokens, minutes, runs=1, partial=1, without=0, by_seat=None):
    """A record's `sessionCost` with partial runs: never complete."""
    return dict(_sc(tokens, minutes, runs=runs, without=without, by_seat=by_seat), runsPartial=partial, complete=False)


_SEC = {"security-reviewer": {"tokens": 100, "minutes": 1.5, "runs": 1}}


def test_t11a_the_measures_reader_checks_runs_partial_and_the_complete_rule():
    # axis: the measures reader reads a sessionCost as well-formed only when complete is false beside a partial run and runsPartial is an int of one or more within the runs
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    good = _psc(100, 1.5, by_seat=_SEC)
    assert RM._session_cost({"sessionCost": good}) == good
    assert RM._session_cost({"sessionCost": dict(good, complete=True)}) is None
    for bad in (0, True, -1, "1", 1.0, 2):  # 2 is over the runs
        assert RM._session_cost({"sessionCost": dict(good, runsPartial=bad)}) is None, bad
    over = _psc(100, 1.5, runs=2, partial=2, without=1, by_seat=_SEC)
    assert RM._session_cost({"sessionCost": over}) is None
    assert RM._session_cost({"sessionCost": dict(over, runsPartial=1)}) == dict(over, runsPartial=1)
    # a record without runsPartial reads as today
    whole = _sc(100, 1.5, by_seat=_SEC)
    assert RM._session_cost({"sessionCost": whole}) == whole and "runsPartial" not in whole
    assert RM._session_cost({"sessionCost": dict(whole, complete=False)}) is None
    unfigured = _sc(100, 1.5, runs=2, without=1, by_seat=_SEC)
    assert RM._session_cost({"sessionCost": unfigured}) == unfigured


def test_t11b_a_pr_whose_only_session_is_partial_is_left_out_and_counted_partial():
    # axis: a PR holding a partial session stays unmeasured and prsLeftOut.<k>.partial counts the left-out PRs that hold one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    ci = [{"pr": n, "minutes": 1} for n in (1, 2, 3, 4)]
    partial = _psc(100, 1.5, by_seat=_SEC)
    row = RM.compute(_full(records=[_rec(1), _rec(2, sc=partial)], ciRuns=ci[:2]), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
    assert cost["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 1}
    assert cost["prsLeftOut"]["minutes"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 1} and RM.problems(row) == []
    # a PR left out for a run without a figure is not partial; a PR with one whole session and one partial session is
    lacking = _sc(100, 1.5, runs=2, without=1)
    records = [_rec(1), _rec(2, sc=partial), _rec(3, sc=lacking), _rec(4, "a"), _rec(4, "b", sc=partial)]
    row = RM.compute(_full(records=records, ciRuns=ci), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["prsLeftOut"]["tokens"] == {"count": 3, "why": RM.LEFT_OUT_WHY, "partial": 2}
    assert cost["prsLeftOut"]["minutes"] == {"count": 3, "why": RM.LEFT_OUT_WHY, "partial": 2} and RM.problems(row) == []
    # no PR measured at all
    row = RM.compute(_full(records=[_rec(2, sc=partial)], ciRuns=ci[1:2]), FROM, UNTIL)
    assert row["measures"]["reviewerCostPerPr"]["tokens"] == U and _why(row)["reviewerCostPerPr.tokens"] == "no-measured-pr"
    assert row["measures"]["reviewerCostPerPr"]["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 1}


def test_t11c_a_seat_only_partial_sessions_blank_reads_cost_partial_and_any_other_blanking_does_not():
    # axis: a seat unmeasured only because every session that blanks it is partial-only reads cost-partial; any other blanking reads cost-not-recorded
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    partial = _psc(100, 1.5, by_seat=_SEC)
    row = RM.compute(_full(records=[_rec(1, sc=partial)]), FROM, UNTIL)
    seats, why = row["measures"]["seats"], _why(row)
    assert seats["security-reviewer"]["tokens"] == U and seats["security-reviewer"]["minutes"] == U
    assert why["seats.security-reviewer.tokens"] == "cost-partial" and why["seats.security-reviewer.minutes"] == "cost-partial"
    # a complete session beside the partial one: the partial one alone blanks the seat
    row = RM.compute(_full(records=[_rec(1, "a"), _rec(1, "b", sc=partial)]), FROM, UNTIL)
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == U and _why(row)["seats.security-reviewer.tokens"] == "cost-partial"
    # a run without a figure blanks it as it always did
    lacking = _sc(5, 0.1, runs=1, without=1, by_seat=_SEC)
    row = RM.compute(_full(records=[_rec(1, sc=lacking)]), FROM, UNTIL)
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == U and _why(row)["seats.security-reviewer.tokens"] == "cost-not-recorded"
    # a partial session and a session with a run lacking a figure both blank the seat: not partial-only
    row = RM.compute(_full(records=[_rec(1, "a", sc=partial), _rec(1, "b", sc=lacking)]), FROM, UNTIL)
    assert _why(row)["seats.security-reviewer.tokens"] == "cost-not-recorded"
    # a partial session and a session with no sessionCost: not partial-only
    row = RM.compute(_full(records=[_rec(1, "a", sc=partial), _rec(1, "b", sc=None)]), FROM, UNTIL)
    assert _why(row)["seats.security-reviewer.tokens"] == "cost-not-recorded"
    # a partial session with a malformed sessionCost reads as no sessionCost
    row = RM.compute(_full(records=[_rec(1, sc=dict(partial, complete=True))]), FROM, UNTIL)
    assert _why(row)["seats.security-reviewer.tokens"] == "cost-not-recorded"
    # a seat a partial session ran but a complete session left out: the complete session's blanking is not partial
    other = {"code-reviewer": {"tokens": 7, "minutes": 0.2, "runs": 1}}
    row = RM.compute(_full(records=[_rec(1, "a", sc=partial), _rec(1, "b", sc=_sc(7, 0.2, by_seat=other))]), FROM, UNTIL)
    assert _why(row)["seats.security-reviewer.tokens"] == "cost-not-recorded"
    # a whole window of complete sessions has no reason at all
    row = RM.compute(_full(), FROM, UNTIL)
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == 100 and "seats.security-reviewer.tokens" not in _why(row)


def _journal_without_first_wall_time(tmp_path, attempts):
    """`journal_run`'s run, then attempt 1's `attempt-ended` record rewritten without its `wallSeconds` key."""
    run_dir = journal_run(tmp_path, attempts)
    records, _ = ED._journal_read(run_dir)
    for rec in records:
        if rec.get("kind") == "attempt-ended" and rec.get("attempt") == 1:
            assert "wallSeconds" in rec
            del rec["wallSeconds"]
    with open(ED._journal_path(run_dir), "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return run_dir


@pytest.mark.parametrize("over", [{}, WATCHDOG], ids=["plain", "watchdog"])
def test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure(tmp_path, over):
    # axis: an ended attempt with no wall time leaves the run without a figure, a usage total and a watchdog end notwithstanding
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
    run_dir = _journal_without_first_wall_time(tmp_path, [
        attempt(stream(input_tokens=30, output_tokens=10), 600, **over), attempt(stream(**RETRY), 30)])
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    assert "wallSeconds" not in state["attempts"][1]["ended"] and state["attempts"][2]["ended"]["wallSeconds"] == 30
    assert (ED._silence_watchdog_end(state["attempts"][1]["ended"])) is bool(over)
    assert ED._attempts_cost(os.path.realpath(run_dir), state) is None
