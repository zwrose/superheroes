# plugins/superheroes/lib/tests/test_task_review.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import task_review as tr

OK = {"spec_compliance": "pass", "code_quality": "pass"}


def test_missing_verdict_re_requests():
    out = tr.decide({"spec_compliance": "pass"}, [], 1, 3, [])
    assert out["action"] == "re_request"


def test_clean_completes():
    out = tr.decide(OK, [], 1, 3, [])
    assert out["action"] == "complete"


def test_minor_only_completes_and_carries():
    out = tr.decide(OK, [{"severity": "Minor", "file": "a.py", "title": "nit"}], 1, 3, [])
    assert out["action"] == "complete"
    assert len(out["minors"]) == 1 and out["blocking"] == []


def test_blocking_triggers_review():
    out = tr.decide(OK, [{"severity": "Important", "file": "a.py", "title": "bug"}], 1, 3, [])
    assert out["action"] == "review"
    assert len(out["blocking"]) == 1


def test_cannot_verify_blocks_completion():
    out = tr.decide(OK, [{"severity": "Minor", "file": "a.py", "title": "x",
                          "cannot_verify_from_diff": True}], 1, 3, [])
    assert out["action"] == "review"
    assert len(out["cannot_verify"]) == 1


def test_cap_reached_with_blocker_parks():
    hist = [{"round": 1, "findings": [{"severity": "Important", "file": "a.py", "title": "bug"}]},
            {"round": 2, "findings": [{"severity": "Important", "file": "a.py", "title": "bug"}]}]
    out = tr.decide(OK, [{"severity": "Important", "file": "a.py", "title": "bug"}], 3, 3, hist)
    assert out["action"] == "park"
