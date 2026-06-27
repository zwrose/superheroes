import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ci_status

def test_all_pass_is_green():
    out = ci_status.classify([{"name": "ci", "bucket": "pass"}, {"name": "lint", "bucket": "skipping"}])
    assert out == {"status": "green", "failing": []}

def test_any_fail_is_red():
    out = ci_status.classify([{"name": "ci", "bucket": "pass"}, {"name": "test", "bucket": "fail"}])
    assert out["status"] == "red" and out["failing"] == ["test"]

def test_pending_is_not_green():
    out = ci_status.classify([{"name": "ci", "bucket": "pending"}])
    assert out["status"] == "red" and out["failing"] == ["ci"]

def test_cancel_is_red():
    out = ci_status.classify([{"name": "ci", "bucket": "pass"}, {"name": "e2e", "bucket": "cancel"}])
    assert out["status"] == "red" and out["failing"] == ["e2e"]

def test_all_skipping_is_none():
    assert ci_status.classify([{"name": "a", "bucket": "skipping"}, {"name": "b", "bucket": "skipped"}]) \
        == {"status": "none", "failing": []}

def test_empty_is_none():
    assert ci_status.classify([]) == {"status": "none", "failing": []}

def test_non_list_is_none_failclosed():
    assert ci_status.classify(None) == {"status": "none", "failing": []}
