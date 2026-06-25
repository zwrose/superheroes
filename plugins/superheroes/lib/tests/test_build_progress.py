# plugins/superheroes/lib/tests/test_build_progress.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_progress as bp

TASKS = [{"id": "1", "title": "A"}, {"id": "2", "title": "B"}]


def _r(committed=(), unmapped=0, reviews=None, dirty=False, final=None, prov="absent"):
    return bp.reconcile(TASKS, list(committed), unmapped, reviews or {}, dirty, final, prov)


def test_unmapped_commit_parks():
    assert _r(unmapped=1)["action"] == "park"


def test_garbled_provenance_parks():
    assert _r(committed=["1", "2"], reviews={"1": "passed", "2": "passed"},
              final={"clean": True}, prov="garbled")["action"] == "park"


def test_uncommitted_leftover_resets():
    assert _r(dirty=True)["action"] == "reset_uncommitted"


def test_first_unbuilt_task_builds():
    assert _r()["action"] == "build_task"


def test_committed_but_unreviewed_takes_review():
    out = _r(committed=["1"])
    assert out["action"] == "review_task" and out["resume_at"]["id"] == "1"


def test_multi_commit_task_counts_as_implemented():
    # committed_task_ids may repeat for a multi-commit task; set membership handles it.
    out = _r(committed=["1", "1", "2"], reviews={"1": "passed"})
    assert out["action"] == "review_task" and out["resume_at"]["id"] == "2"


def test_all_complete_runs_final_review():
    assert _r(committed=["1", "2"], reviews={"1": "passed", "2": "passed"},
              final=None)["action"] == "final_review"


def test_mid_final_review_resumes():
    assert _r(committed=["1", "2"], reviews={"1": "passed", "2": "passed"},
              final={"clean": False})["action"] == "final_review"


def test_clean_final_review_absent_provenance_writes():
    assert _r(committed=["1", "2"], reviews={"1": "passed", "2": "passed"},
              final={"clean": True}, prov="absent")["action"] == "write_provenance"


def test_clean_final_review_present_provenance_completes():
    assert _r(committed=["1", "2"], reviews={"1": "passed", "2": "passed"},
              final={"clean": True}, prov="present")["action"] == "complete"
