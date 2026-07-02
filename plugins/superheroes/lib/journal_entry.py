# plugins/superheroes/lib/journal_entry.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, journal

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--payload", required=True)   # JSON event payload
ap.add_argument("--event-type", default="phase_record")   # #38: JS seam may write external_dispatch
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)
try:
    payload = json.loads(a.payload)
except ValueError:                                 # malformed payload -> fail closed
    print(json.dumps({"ok": False, "error": "malformed --payload JSON"}))
    sys.exit(0)
try:
    journal.append(paths["events"], a.event_type, payload=payload, root=os.getcwd())
    print(json.dumps({"ok": True}))
except journal.DurableWriteError as e:
    print(json.dumps({"ok": False, "error": str(e)}))
