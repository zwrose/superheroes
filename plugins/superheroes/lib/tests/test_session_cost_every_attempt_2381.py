"""#2381: a review's `sessionCost` counts every attempt of every run.

A run's figure is the engine record's `attemptsCost`: the sum over every attempt its journal shows, and none at all
when any attempt lacks a token figure or a wall-time figure.

Bite-proof record: i2381_every_attempt
"""
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine_adapter as EA  # noqa: E402
import engine_dispatch as ED  # noqa: E402
import review_record_session as rs  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_engine_dispatch import _manual_open_review_run  # noqa: E402
from test_review_record_session import GOOD_RUN, Session  # noqa: E402
from test_review_record_session_cost_2307 import written  # noqa: E402

NONCE = "n1"
PROOF = "plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md"
TIMED_OUT = {"exit": 124, "timedOut": True}


def stream(*, events=True, **usage):
    """A codex JSONL stdout whose last turn.completed carries `usage` (no turn.completed when events is False)."""
    lines = [json.dumps({"type": "thread.started", "thread_id": "t"}), json.dumps({"type": "turn.started"})]
    if events:
        lines.append(json.dumps({"type": "turn.completed", "usage": usage}))
    return "\n".join(lines)


def attempt(stdout, wall, ended=True, **over):
    """One attempt of a run: its stdout (None writes none), its `wallSeconds`, and whether the journal ended it."""
    return {"stdout": stdout, "wall": wall, "ended": ended, "over": over}


def journal_run(tmp_path, attempts, engine="codex"):
    """A real run directory opened without spawning, then one journaled attempt per spec (attempts number from 1)."""
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    records, _ = ED._journal_read(run_dir)
    for rec in records:
        if rec.get("kind") == "run-opened":
            rec["echoNonce"] = NONCE
            rec["engine"] = engine
    with open(ED._journal_path(run_dir), "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    for n, spec in enumerate(attempts, 1):
        if spec["stdout"] is not None:
            with open(os.path.join(run_dir, "attempt-%d.stdout" % n), "w", encoding="utf-8") as fh:
                fh.write(spec["stdout"])
        with open(os.path.join(run_dir, "attempt-%d.stderr" % n), "w", encoding="utf-8") as fh:
            fh.write("")
        ED._journal_append(run_dir, {"kind": "attempt-started", "attempt": n, "childPid": 1, "at": time.time()})
        if spec["ended"]:
            ended = {"kind": "attempt-ended", "attempt": n, "exit": 0, "timedOut": False, "signal": None,
                     "refusal": None, "at": time.time(), "wallSeconds": spec["wall"],
                     "stdoutBytes": len(spec["stdout"] or "")}
            ended.update(spec["over"])
            ED._journal_append(run_dir, ended)
    return run_dir


def execution_record(tmp_path, attempts, **kw):
    record, error = ED.run_execution_record(journal_run(tmp_path, attempts, **kw))
    assert error is None, error
    return record


def session_cost(tmp_path, record):
    """The `sessionCost` of a one-seat session whose only run has `record` as its engine record."""
    s = Session(tmp_path).seat("code-reviewer", nonce=NONCE)
    return written(tmp_path, s.save(), {NONCE: (record, None)})["sessionCost"]


def test_t1_a_timed_out_first_attempt_and_a_clean_retry_are_summed(tmp_path):
    # axis: a run's figure is the sum over every attempt its engine journal shows
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
    record = execution_record(tmp_path, [
        attempt(stream(input_tokens=30, output_tokens=10), 900, **TIMED_OUT),
        attempt(stream(input_tokens=50, cached_input_tokens=0, output_tokens=10), 30)])
    assert record["attemptsCost"] == {"tokens": 100, "wallSeconds": 930, "attempts": 2}
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["minutes"], cost["complete"]) == (100, 15.5, True)


def test_t2_an_attempt_with_no_usage_leaves_the_run_without_a_figure(tmp_path):
    # axis: an attempt whose stdout shows no token usage leaves the run without a figure, never a zero
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
    record = execution_record(tmp_path, [
        attempt(stream(events=False), 900, **TIMED_OUT),
        attempt(stream(input_tokens=50, output_tokens=10), 30)])
    assert record["attemptsCost"] is None
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (0, 1, 1, False)


def test_t3_an_attempt_the_journal_never_ended_leaves_the_run_without_a_figure(tmp_path):
    # axis: an attempt with no attempt-ended record has no wall-time figure and leaves the run without one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
    record = execution_record(tmp_path, [
        attempt(stream(input_tokens=30, output_tokens=10), None, ended=False),
        attempt(stream(input_tokens=50, output_tokens=10), 30)])
    assert record["attemptsCost"] is None


def test_t4_one_clean_attempt_gives_the_figure_its_observation_gives(tmp_path):
    # axis: a run of one clean attempt costs what its single attempt shows
    record = execution_record(tmp_path, [attempt(stream(input_tokens=60, output_tokens=15), 12.0)])
    assert record["attemptsCost"] == {"tokens": 75, "wallSeconds": 12.0, "attempts": 1}
    assert rs._figure(record["observation"]) == (75, 12.0)
    cost = session_cost(tmp_path, record)
    assert (cost["tokens"], cost["minutes"], cost["complete"]) == (75, 0.2, True)


def test_t5_a_negative_usage_part_leaves_the_run_without_a_figure(tmp_path):
    # axis: a token part that is not a non-negative int invalidates its attempt and so the run
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
    bad = stream(input_tokens=-5, output_tokens=10)
    assert EA.codex_usage_tokens(bad) is None
    record = execution_record(tmp_path, [
        attempt(bad, 900, **TIMED_OUT),
        attempt(stream(input_tokens=90, output_tokens=10), 30)])
    assert record["attemptsCost"] is None


def test_t6_an_explicit_zero_usage_is_a_figure(tmp_path):
    # axis: usage reported as zero is a figure of zero, not a missing one
    record = execution_record(tmp_path, [attempt(
        stream(input_tokens=0, cached_input_tokens=0, output_tokens=0, reasoning_output_tokens=0), 5)])
    assert record["attemptsCost"] == {"tokens": 0, "wallSeconds": 5, "attempts": 1}


@pytest.mark.parametrize("engine_record", [
    dict(GOOD_RUN, runnerNonce=NONCE, attemptsCost=None),
    dict(GOOD_RUN, runnerNonce=NONCE),
], ids=["attemptsCost-none", "attemptsCost-absent"])
def test_t7_a_record_with_only_an_observation_gives_no_figure(tmp_path, engine_record):
    # axis: the session figure comes from the every-attempt total, never from the last attempt's observation
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
    assert engine_record["observation"] == {"tokens": 100, "wallSeconds": 120}
    cost = session_cost(tmp_path, engine_record)
    assert (cost["tokens"], cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (0, 1, 1, False)
