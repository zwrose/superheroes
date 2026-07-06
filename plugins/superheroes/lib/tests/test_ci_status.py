import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ci_status

def test_all_pass_is_green():
    out = ci_status.classify([{"name": "ci", "bucket": "pass"}, {"name": "lint", "bucket": "skipping"}])
    assert out == {"status": "green", "failing": [], "pending": []}

def test_any_fail_is_red():
    out = ci_status.classify([{"name": "ci", "bucket": "pass"}, {"name": "test", "bucket": "fail"}])
    assert out["status"] == "red" and out["failing"] == ["test"]

def test_pending_is_not_green():
    # 0.10.0 qualification finding: pending is its OWN status — WAIT, not FIX. It still
    # never certifies green, and it never lands in `failing` (a fixer aimed at a running
    # check has nothing to fix).
    out = ci_status.classify([{"name": "ci", "bucket": "pending"}])
    assert out["status"] == "pending" and out["failing"] == [] and out["pending"] == ["ci"]


def test_red_wins_over_pending_and_failing_excludes_running_checks():
    out = ci_status.classify([{"name": "unit", "bucket": "fail"},
                              {"name": "e2e", "bucket": "in_progress"}])
    assert out["status"] == "red"
    assert out["failing"] == ["unit"]      # only the real failure — the fixer's target list
    assert out["pending"] == ["e2e"]


def test_cancel_is_red():
    out = ci_status.classify([{"name": "ci", "bucket": "pass"}, {"name": "e2e", "bucket": "cancel"}])
    assert out["status"] == "red" and out["failing"] == ["e2e"]

def test_all_skipping_is_none():
    assert ci_status.classify([{"name": "a", "bucket": "skipping"}, {"name": "b", "bucket": "skipped"}]) \
        == {"status": "none", "failing": [], "pending": []}

def test_empty_is_none():
    assert ci_status.classify([]) == {"status": "none", "failing": [], "pending": []}

def test_non_list_is_none_failclosed():
    assert ci_status.classify(None) == {"status": "none", "failing": [], "pending": []}

def test_state_and_conclusion_fallback_keys():
    # _bucket falls back from `bucket` to `state` to `conclusion` (gh's two status shapes).
    # A failing `state` -> red; a single passing `conclusion` -> green (it is the only gating check).
    red = ci_status.classify([{"name": "x", "state": "failure"}])
    assert red["status"] == "red" and red["failing"] == ["x"]
    green = ci_status.classify([{"name": "y", "conclusion": "success"}])
    assert green == {"status": "green", "failing": [], "pending": []}
