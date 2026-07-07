# plugins/superheroes/lib/prov_entry.py
"""Record ship-gate provenance over the current HEAD: --step build -> ship_gate.write_build;
--step review -> ship_gate.set_review_covers + a clean review_result; --step build-denial ->
ship_gate.record_build_denial (UFR-6/UFR-8: a substantive build step the 15-min timeout denied
taints the build evidence so the draft-PR ship-gate holds the PR a draft). The draft-PR ship-gate
(pr_entry.py) reads these to prove build+review ran over the shipped HEAD before opening a PR."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane, review_result, ship_gate

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True, choices=["build", "review", "build-denial"])
ap.add_argument("--work-item", required=True)
ap.add_argument("--round", type=int, default=1, help="the review loop's terminal round (review step)")
ap.add_argument("--reason", default="review-code clean", help="review_result reason (review step)")
ap.add_argument("--worktree", default=None, help="explicit worktree for a targetable review step")
ap.add_argument("--head", default=None, help="explicit expected head for a targetable review step")
ap.add_argument("--denied-step", default=None, help="the build-denial step label (build-denial step)")
ap.add_argument("--denied-command", default=None, help="the denied command/action (build-denial step)")
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)

# build-denial needs no HEAD resolution (the denial isn't head-scoped — ship_gate.decide checks
# buildDenials BEFORE the covers/head freshness check), so record it up front and exit. Resolving
# HEAD first would let a flaky `git rev-parse` fail-closed-skip a denial that must ALWAYS land.
if a.step == "build-denial":
    try:
        ship_gate.record_build_denial(paths["provenance"], step=(a.denied_step or "unknown"),
                                       command=a.denied_command or "")
    except (ship_gate.ProvenanceError, OSError) as e:   # corrupt provenance.json / disk -> fail closed
        print(json.dumps({"ok": False, "error": "build-denial write failed: %s" % e}))
        sys.exit(0)
    print(json.dumps({"ok": True}))
    sys.exit(0)

# The SHIPPED HEAD is the build branch's tip (the PR ships that branch), not the ambient cwd HEAD —
# resolve it from the recorded checkpoint.branch so provenance.head == the HEAD the PR actually ships
# (otherwise a build that happens on a separate branch/worktree records a mismatched HEAD).
cp = ckpt_lib.read(paths["checkpoint"])
if isinstance(cp, dict) and cp.get("_incompatible"):
    # A durable-but-incompatible checkpoint must NOT silently fall back to ambient HEAD
    # (that would stamp provenance over whatever cwd happens to point at). Fail closed.
    print(json.dumps({"ok": False,
                      "error": "checkpoint incompatible: %s — provenance not recorded" % cp.get("reason", "unknown reason")}))
    sys.exit(0)
cp = cp or {}
ref = a.head or cp.get("branch") or "HEAD"
try:
    cmd = ["git"]
    if a.worktree:
        cmd.extend(["-C", a.worktree])
    cmd.extend(["rev-parse", ref])
    _hp = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
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
