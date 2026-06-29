# plugins/superheroes/lib/build_entry.py
"""Build-setup leaf: content-address the work branch from the approved tasks doc, create/reclaim
the managed build worktree, and record checkpoint.branch — the same content-hash + worktree setup
workhorse step 1 does (skills/workhorse/SKILL.md step 1)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildtree, checkpoint as ckpt_lib, control_plane, docload

ap = argparse.ArgumentParser(); ap.add_argument("--work-item", required=True)
ap.add_argument("--generation", type=int, default=None)
a = ap.parse_args()
root = os.getcwd()
try:
    ch = docload.content_hash_for(a.work_item, root)             # §6.3, shared with recover_entry
except (OSError, ValueError) as e:                               # missing/malformed tasks doc -> fail closed
    print(json.dumps({"error": "cannot content-hash tasks doc: %s" % e}))
    sys.exit(0)   # exit 0 so the fail-closed JSON is reliably consumed (buildPhase parks on no branch)
branch = buildtree.branch_name(a.work_item, ch)                  # canonical helper (no inline duplicate)
res = buildtree.reclaim_or_create(root, a.work_item, ch)          # -> REUSED/CREATED/PRESERVE_NOTIFY/GATE_FAILCLOSED
outcome = res.get("outcome") if isinstance(res, dict) else res    # reclaim_or_create returns {"outcome": ...}
if outcome in ("gate_failclosed", "preserve_notify"):            # no clean usable worktree -> fail closed
    print(json.dumps({"error": "buildtree %s — cannot build cleanly" % outcome}))
    sys.exit(0)   # exit 0 so the fail-closed JSON is reliably consumed (buildPhase parks on no branch)
paths = control_plane.paths(root, a.work_item)
cp = ckpt_lib.read(paths["checkpoint"])
if isinstance(cp, dict) and cp.get("_incompatible"):
    # Don't overwrite a durable-but-incompatible checkpoint with a fresh one (that
    # would discard the fail-closed signal and propagate the marker dict to disk). Park.
    print(json.dumps({"error": "checkpoint incompatible: %s — cannot build cleanly" % cp.get("reason", "unknown reason")}))
    sys.exit(0)   # exit 0 so the fail-closed JSON is reliably consumed (buildPhase parks on no branch)
cp = cp or ckpt_lib.new(a.work_item, branch)
cp["branch"] = branch
if a.generation is not None:
    cp["lockGeneration"] = a.generation     # UFR-10: thread this run's generation (mint or reuse)
try:
    ckpt_lib.write(paths["checkpoint"], cp)
except OSError as e:                                              # disk -> fail closed (no branch emitted)
    print(json.dumps({"error": "checkpoint write failed: %s" % e}))
    sys.exit(0)   # exit 0 so the fail-closed JSON is reliably consumed (buildPhase parks on no branch)
# `outcome` ('reused'/'created') is emitted so a side-effect-safe resolver (resolveBuildTarget, run
# WITHOUT --generation at review-code/test-pilot time) can fail-closed on 'created': a fresh worktree
# at that stage means the build artifact is gone, and certifying its empty tree would be a fail-open.
# Additive — the build phase consumer reads branch/path and ignores outcome (CREATED is expected there).
print(json.dumps({"branch": branch, "path": res.get("path"), "outcome": outcome}))
