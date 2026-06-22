# plugins/superheroes/lib/readout_post.py
"""Post the parked-PR readout (scrubbed) to the run's PR via pr_comment.upsert (FR-13/FR-14).
Always record a durable 'parked' event; on a failed PR post, also write the readout to the
store and surface the failure — never silently drop it (UFR-4)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, journal, pr_comment, readout

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--reason", required=True)
ap.add_argument("--pr", default=None)             # the run's PR number, when one exists
a = ap.parse_args()
paths = control_plane.paths(os.getcwd(), a.work_item)
text, _ok = readout.scrub(a.reason, root=os.getcwd())
# durable record first (internal events.jsonl) — independent of the PR post.
journal.append(paths["events"], "parked", detail=text, root=os.getcwd())
if not a.pr:                                       # parked before a PR exists (FR-13 no-PR branch)
    control_plane.atomic_write(paths["resume_brief"], text)
    print(json.dumps({"posted": False, "recorded": True}))
else:
    try:
        # upsert(pr, family, key, body) edits-or-creates the marker-managed PR comment.
        pr_comment.upsert(a.pr, "results", a.work_item, text)   # "results" is a valid MARKER_FAMILIES key
        print(json.dumps({"posted": True}))
    except Exception as e:   # noqa: BLE001 — UFR-4: a failed post is recorded, never dropped.
        control_plane.atomic_write(paths["resume_brief"], text)
        print(json.dumps({"posted": False, "recorded": True, "error": str(e)}))
