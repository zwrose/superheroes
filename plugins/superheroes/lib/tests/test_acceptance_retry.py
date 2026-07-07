# plugins/superheroes/lib/tests/test_acceptance_retry.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_retry as r


def test_environmental_first_attempt_retries():
    res = r.classify({"kind": "check-runner-errored-before-running", "unreadable": False,
                      "attempt": 1})
    assert res["retry"] is True and res["class"] == "environmental"


def test_host_unreachable_first_attempt_retries():
    res = r.classify({"kind": "host-unreachable", "unreadable": False, "attempt": 1})
    assert res["retry"] is True and res["class"] == "environmental"


def test_parked_blocking_review_is_behavioral_no_retry():
    res = r.classify({"kind": "parked-blocking-review", "unreadable": False, "attempt": 1})
    assert res["retry"] is False and res["class"] == "behavioral"


def test_red_check_on_its_change_is_behavioral_no_retry():
    res = r.classify({"kind": "red-check", "unreadable": False, "attempt": 1})
    assert res["retry"] is False and res["class"] == "behavioral"


def test_unclassifiable_defaults_to_behavioral_no_retry():
    res = r.classify({"kind": "unknown", "unreadable": False, "attempt": 1})
    assert res["retry"] is False and res["class"] == "behavioral"


def test_unreadable_fact_never_justifies_retry_fail_closed():
    res = r.classify({"kind": "check-runner-errored-before-running", "unreadable": True,
                      "attempt": 1})
    assert res["retry"] is False


def test_second_attempt_never_retries_again():
    res = r.classify({"kind": "host-unreachable", "unreadable": False, "attempt": 2})
    assert res["retry"] is False
