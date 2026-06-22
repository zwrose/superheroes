# plugins/superheroes/lib/prov_entry.py
"""Record ship-gate provenance over the current HEAD: --step build -> ship_gate.write_build;
--step review -> ship_gate.set_review_covers + a clean review_result. The draft-PR ship-gate
(pr_entry.py) reads these to prove build+review ran over the shipped HEAD before opening a PR."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, review_result, ship_gate

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True, choices=["build", "review"])
ap.add_argument("--work-item", required=True)
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)
_hp = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
head = _hp.stdout.strip()
if _hp.returncode != 0 or not head:
    # No resolvable HEAD -> record NO provenance (an empty head would let two empty-head records
    # satisfy ship_gate's covers==head check). Fail closed; the draft-PR ship-gate then GATEs.
    print(json.dumps({"ok": False, "error": "git rev-parse HEAD failed — provenance not recorded"}))
    sys.exit(0)
if a.step == "build":
    ship_gate.write_build(paths["provenance"], engine="subagent-driven-development", head=head)
else:
    ship_gate.set_review_covers(paths["provenance"], head)
    review_result.write_result(paths["review_result"], "exit_clean", 1, "review-code single-pass clean")
print(json.dumps({"ok": True}))
