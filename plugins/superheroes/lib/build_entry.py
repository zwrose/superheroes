# plugins/superheroes/lib/build_entry.py
"""Build-setup leaf: content-address the work branch from the approved tasks doc, create/reclaim
the managed build worktree, and record checkpoint.branch — the same content-hash + worktree setup
workhorse step 1 does (skills/workhorse/SKILL.md step 1)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildtree, checkpoint as ckpt_lib, control_plane, docload

ap = argparse.ArgumentParser(); ap.add_argument("--work-item", required=True); a = ap.parse_args()
root = os.getcwd()
try:
    ch = docload.content_hash_for(a.work_item, root)             # §6.3, shared with recover_entry
except (OSError, ValueError) as e:                               # missing/malformed tasks doc -> fail closed
    print(json.dumps({"error": "cannot content-hash tasks doc: %s" % e}))
    sys.exit(1)
branch = "superheroes/%s-%s" % (a.work_item, ch)
res = buildtree.reclaim_or_create(root, a.work_item, ch)          # -> REUSED/CREATED/PRESERVE_NOTIFY/GATE_FAILCLOSED
outcome = res.get("outcome") if isinstance(res, dict) else res    # reclaim_or_create returns {"outcome": ...}
if outcome in ("gate_failclosed", "preserve_notify"):            # no clean usable worktree -> fail closed
    print(json.dumps({"error": "buildtree %s — cannot build cleanly" % outcome}))
    sys.exit(1)
paths = control_plane.paths(root, a.work_item)
cp = ckpt_lib.read(paths["checkpoint"]) or ckpt_lib.new(a.work_item, branch)
cp["branch"] = branch
ckpt_lib.write(paths["checkpoint"], cp)
print(json.dumps({"branch": branch}))
