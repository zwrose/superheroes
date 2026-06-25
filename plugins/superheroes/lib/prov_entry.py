# plugins/superheroes/lib/prov_entry.py
"""Record ship-gate provenance over the current HEAD: --step build -> ship_gate.write_build;
--step review -> ship_gate.set_review_covers + a clean review_result. The draft-PR ship-gate
(pr_entry.py) reads these to prove build+review ran over the shipped HEAD before opening a PR."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane, review_result, ship_gate

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True, choices=["build", "review"])
ap.add_argument("--work-item", required=True)
ap.add_argument("--round", type=int, default=1, help="the review loop's terminal round (review step)")
ap.add_argument("--reason", default="review-code clean", help="review_result reason (review step)")
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)
# The SHIPPED HEAD is the build branch's tip (the PR ships that branch), not the ambient cwd HEAD —
# resolve it from the recorded checkpoint.branch so provenance.head == the HEAD the PR actually ships
# (otherwise a build that happens on a separate branch/worktree records a mismatched HEAD).
cp = ckpt_lib.read(paths["checkpoint"]) or {}
ref = cp.get("branch") or "HEAD"
try:
    _hp = subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True, timeout=10)
except subprocess.TimeoutExpired:
    print(json.dumps({"ok": False, "error": "git rev-parse timed out — provenance not recorded"})); sys.exit(0)
head = _hp.stdout.strip()
if _hp.returncode != 0 or not head:
    # No resolvable HEAD -> record NO provenance (an empty head would let two empty-head records
    # satisfy ship_gate's covers==head check). Fail closed; the draft-PR ship-gate then GATEs.
    print(json.dumps({"ok": False, "error": "git rev-parse %s failed — provenance not recorded" % ref}))
    sys.exit(0)
try:
    if a.step == "build":
        ship_gate.write_build(paths["provenance"], engine="subagent-driven-development", head=head)
    else:
        ship_gate.set_review_covers(paths["provenance"], head)
        review_result.write_result(paths["review_result"], "exit_clean", a.round, a.reason)
except (ship_gate.ProvenanceError, OSError) as e:   # corrupt provenance.json / disk -> fail closed
    print(json.dumps({"ok": False, "error": "provenance write failed: %s" % e}))
    sys.exit(0)
print(json.dumps({"ok": True}))
