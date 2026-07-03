# plugins/superheroes/lib/fence_cli.py
"""Renew-then-fence at a branch-mutating boundary (UFR-10), the /workhorse per-boundary pattern.
ok:true only when this run still holds the given lease generation; else fail-closed (the JS parks
before any commit/reset). With --release: CAS-delete the lease at a terminal park / hand-back
exit (a parked run must not cost the next launch a DEFAULT_TTL wait); best-effort — ok:false
just leaves the TTL as the backstop."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, ref_lock

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--generation", required=True)
ap.add_argument("--root", required=True,
                help="checkout root the control-plane store is keyed to (acquire authority)")
ap.add_argument("--release", action="store_true",
                help="delete the lease iff this generation still holds it (terminal exit)")
a = ap.parse_args()
try:
    gen = int(a.generation)
except (TypeError, ValueError):
    print(json.dumps({"ok": False, "reason": "malformed --generation"}))
    sys.exit(0)
try:
    root = os.path.realpath(a.root)
except (TypeError, ValueError, OSError):
    root = ""
if not root or not os.path.isdir(root):
    print(json.dumps({"ok": False, "reason": "control-plane store unusable"}))
    sys.exit(0)
store = control_plane.ensure_store(root)
if store is None:
    print(json.dumps({"ok": False, "reason": "control-plane store unusable"}))
    sys.exit(0)
if a.release:
    released = ref_lock.release(store, a.work_item, gen)
    print(json.dumps({"ok": bool(released),
                      "reason": "lease released" if released else "lease not held at this generation"}))
    sys.exit(0)
renewed = ref_lock.renew(store, a.work_item, gen)
fenced = ref_lock.fence_ok(store, a.work_item, gen)
ok = bool(renewed) and bool(fenced)
print(json.dumps({"ok": ok,
                  "reason": "lease still held" if ok else "lease lost/stolen — park before write"}))
