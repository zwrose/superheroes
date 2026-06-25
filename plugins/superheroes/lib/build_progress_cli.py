# plugins/superheroes/lib/build_progress_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_progress

ap = argparse.ArgumentParser()
ap.add_argument("--state", required=True)
a = ap.parse_args()
try:
    s = json.loads(a.state)
except ValueError:
    print(json.dumps({"action": "park", "reason": "malformed --state JSON"}))
    sys.exit(0)
print(json.dumps(build_progress.reconcile(
    s.get("task_list"), s.get("committed_task_ids"), s.get("unmapped_commits"),
    s.get("review_records"), s.get("worktree_dirty"), s.get("final_review"),
    s.get("provenance"))))
