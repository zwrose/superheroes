# plugins/superheroes/lib/tests/test_build_progress_cli.py
import json, os, subprocess, sys
CLI = os.path.join(os.path.dirname(__file__), "..", "build_progress_cli.py")


def test_cli_build_task():
    state = {"task_list": [{"id": "1", "title": "A"}], "committed_task_ids": [],
             "unmapped_commits": 0, "review_records": {}, "worktree_dirty": False,
             "final_review": None, "provenance": "absent"}
    out = subprocess.run([sys.executable, CLI, "--state", json.dumps(state)],
                         capture_output=True, text=True)
    assert json.loads(out.stdout)["action"] == "build_task"


def test_cli_bad_state_parks():
    out = subprocess.run([sys.executable, CLI, "--state", "{bad"],
                         capture_output=True, text=True)
    assert json.loads(out.stdout)["action"] == "park"
