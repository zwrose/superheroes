# plugins/superheroes/lib/tests/test_worker_recovery.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import worker_recovery as wr


def test_first_attempt_retries_with_context():
    assert wr.decide(1, "needs_context", max_attempts=3)["action"] == "retry_with_context"


def test_attempt_before_cap_escalates():
    assert wr.decide(2, "needs_context", max_attempts=3)["action"] == "escalate"


def test_at_cap_parks():
    assert wr.decide(3, "needs_context", max_attempts=3)["action"] == "park"


def test_plan_wrong_parks_immediately():
    assert wr.decide(1, "plan_wrong", max_attempts=3)["action"] == "park"


def test_unknown_signal_treated_as_needs_context():
    assert wr.decide(1, "weird", max_attempts=3)["action"] == "retry_with_context"
