# plugins/superheroes/lib/fence_cli.py
"""Renew-then-fence at a branch-mutating boundary (UFR-10), the /workhorse per-boundary pattern.
ok:true only when this run still holds the given lease generation; else fail-closed (the JS parks
before any commit/reset)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, ref_lock

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--generation", required=True)
a = ap.parse_args()
try:
    gen = int(a.generation)
except (TypeError, ValueError):
    print(json.dumps({"ok": False, "reason": "malformed --generation"}))
    sys.exit(0)
store = control_plane.ensure_store(os.getcwd())
if store is None:
    print(json.dumps({"ok": False, "reason": "control-plane store unusable"}))
    sys.exit(0)
renewed = ref_lock.renew(store, a.work_item, gen)
fenced = ref_lock.fence_ok(store, a.work_item, gen)
ok = bool(renewed) and bool(fenced)
print(json.dumps({"ok": ok,
                  "reason": "lease still held" if ok else "lease lost/stolen — park before write"}))
