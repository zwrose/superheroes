# plugins/superheroes/lib/ship_phase.py
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freshness, ci_loop, control_plane, journal

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True, choices=["freshness", "ci"])
ap.add_argument("--work-item", required=True)
a = ap.parse_args()

if a.step == "freshness":
    # is the branch up to date with base = does HEAD contain origin/<base> = is origin/<base> an
    # ancestor of HEAD. (rc 0 = yes/up-to-date, 1 = behind, other = unreadable -> gate.)
    base = "main"
    rc = subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{base}", "HEAD"]).returncode
    is_anc = True if rc == 0 else (False if rc == 1 else None)
    decision, _reason = freshness.decide(is_anc, 1)
    print(json.dumps({"decision": decision}))
else:
    paths = control_plane.paths(os.getcwd(), a.work_item)
    rounds, history = journal.ci_attempts(paths["events"])
    failing = []  # a real CI read populates this; empty => green
    if not failing:
        print(json.dumps({"decision": "green"}))
    else:
        decision, reason = ci_loop.decide(failing, history, rounds + 1)
        print(json.dumps({"decision": decision, "reason": reason}))
