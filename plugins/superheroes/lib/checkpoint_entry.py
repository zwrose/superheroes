# plugins/superheroes/lib/checkpoint_entry.py
"""Persist the resume cursor: lastGoodStep (+ pr / ready side effects) — written BEFORE the loop
advances (FR-4). --read-pr returns the recorded checkpoint.pr for the ship phase."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--step")
ap.add_argument("--json", dest="side", default=None)   # {pr:{...}} or {ready:true}
ap.add_argument("--read-pr", action="store_true")
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)
cp = ckpt_lib.read(paths["checkpoint"]) or ckpt_lib.new(a.work_item, "")
if a.read_pr:
    print(json.dumps({"pr": cp.get("pr")}))
elif a.step is None:                                   # write path requires a step (fail closed, never int(None))
    print(json.dumps({"ok": False, "error": "--step is required for the write path"}))
    sys.exit(2)
else:
    cp["lastGoodStep"] = int(a.step)
    try:
        side = json.loads(a.side) if a.side else {}
    except ValueError:                                 # malformed --json side effect -> fail closed
        print(json.dumps({"ok": False, "error": "malformed --json side effect"})); sys.exit(2)
    if "pr" in side:
        cp["pr"] = side["pr"]
    if side.get("ready") and isinstance(cp.get("pr"), dict):
        cp["pr"]["isDraft"] = False
    ckpt_lib.write(paths["checkpoint"], cp)
    print(json.dumps({"ok": True, "pr": cp.get("pr")}))
