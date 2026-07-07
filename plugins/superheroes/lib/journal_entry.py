# plugins/superheroes/lib/journal_entry.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, journal

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--payload")   # JSON event payload (optional; a step/detail-only event may omit it)
ap.add_argument("--event-type", default="phase_record")   # #38: JS seam may write external_dispatch
# code-001 (UFR-3): top-level step/detail so a build-side permission_denied event carries the same
# shape the reviewer-side recorder writes (run_readout._permission_denials reads ev["step"]/["detail"],
# NOT payload). Both default to None -> the legacy payload-only event shape is byte-unchanged. `detail`
# is scrubbed by journal.append's secret-scrub seam.
ap.add_argument("--step")
ap.add_argument("--detail")
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)
payload = None
if a.payload is not None:
    try:
        payload = json.loads(a.payload)
    except ValueError:                                 # malformed payload -> fail closed
        print(json.dumps({"ok": False, "error": "malformed --payload JSON"}))
        sys.exit(0)
try:
    journal.append(paths["events"], a.event_type, step=a.step, detail=a.detail,
                   payload=payload, root=os.getcwd())
    print(json.dumps({"ok": True}))
except journal.DurableWriteError as e:
    print(json.dumps({"ok": False, "error": str(e)}))
