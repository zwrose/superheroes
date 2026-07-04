# plugins/superheroes/lib/readout_post.py
"""Post the parked-PR readout (scrubbed) to the run's PR via pr_comment.upsert (FR-13/FR-14).
Always record a durable 'parked' event; on a failed PR post, also write the readout to the
store and surface the failure — never silently drop it (UFR-4)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, journal, pr_comment, readout

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--reason", default=None)
ap.add_argument("--pr", default=None)             # the run's PR number, when one exists
ap.add_argument("--ctx", default=None, help="JSON context for readout.build_readout (structured hand-back)")
# #130: the run's terminal state. A ready hand-back journals run_completed (not parked — the pre-#130
# bug where every hand-back journaled 'parked', so run_watch/token_trend could not tell them apart);
# every other terminal stays parked. --cost-payload folds ship's cost telemetry into this same leaf.
ap.add_argument("--terminal", choices=["parked", "completed"], default="parked")
ap.add_argument("--cost-payload", default=None, help="#130: JSON phase_cost telemetry (best-effort)")
a = ap.parse_args()

_TERMINAL_EVENT = {"parked": "parked", "completed": "run_completed"}
if not a.ctx and a.reason is None:
    print(json.dumps({"posted": False, "recorded": False,
                      "error": "readout_post requires --ctx or --reason"}))
    sys.exit(2)
paths = control_plane.paths(os.getcwd(), a.work_item)

if a.ctx:
    try:
        ctx = json.loads(a.ctx)
    except ValueError:
        print(json.dumps({"posted": False, "recorded": False,
                          "error": "readout_post: malformed --ctx JSON"}))
        sys.exit(2)
    ctx.setdefault("root", os.getcwd())
    note = ctx.pop("integration_note", None)
    body = readout.build_readout(ctx)                # every free-text field scrubbed inside build_readout
    if note:
        body = body + "\n\n> _" + readout.scrub(note, root=os.getcwd())[0] + "_"
    text = body
else:
    text, _ok = readout.scrub(a.reason, root=os.getcwd())


def _record_brief(t):
    """Best-effort store fallback; never raises (a full disk here must not crash the leaf)."""
    try:
        control_plane.atomic_write(paths["resume_brief"], t)
        return True
    except OSError:
        return False


# durable record first (internal events.jsonl) — independent of the PR post. A failed durable write
# must NOT crash the leaf with empty stdout (cmdRunner fails closed on empty stdout): fall back to the
# store record + a surfaced error, so the readout is never silently dropped (UFR-4).
try:
    journal.append(paths["events"], _TERMINAL_EVENT[a.terminal], detail=text, root=os.getcwd())
except journal.DurableWriteError as e:
    rec = _record_brief(text)
    print(json.dumps({"posted": False, "recorded": rec,
                      "error": "durable journal write failed: %s" % e}))
    sys.exit(0)
# #130: fold ship's phase_cost into this same hand-back leaf (no new courier leaf — #118). Best-effort;
# a malformed or failing cost write never affects the hand-back.
if a.cost_payload:
    try:
        journal.append(paths["events"], "phase_cost", payload=json.loads(a.cost_payload), root=os.getcwd())
    except Exception:   # noqa: BLE001 — telemetry is best-effort
        pass
if not a.pr:                                       # parked before a PR exists (FR-13 no-PR branch)
    rec = _record_brief(text)
    print(json.dumps({"posted": False, "recorded": rec}))
else:
    try:
        # upsert(pr, family, key, body) edits-or-creates the marker-managed PR comment.
        pr_comment.upsert(a.pr, "results", a.work_item, text)   # "results" is a valid MARKER_FAMILIES key
        print(json.dumps({"posted": True}))
    except Exception as e:   # noqa: BLE001 — UFR-4: a failed post is recorded, never dropped.
        rec = _record_brief(text)
        print(json.dumps({"posted": False, "recorded": rec, "error": str(e)}))
