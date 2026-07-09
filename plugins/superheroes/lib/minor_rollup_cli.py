# plugins/superheroes/lib/minor_rollup_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, journal, minor_rollup

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--append", default=None)
a = ap.parse_args()
root = os.getcwd()
path = os.path.join(control_plane.paths(root, a.work_item)["issue_dir"], "minor-findings.json")
os.makedirs(os.path.dirname(path), exist_ok=True)


def _disclose_corruption():
    """B4 (#315): the roll-up existed but could not be parsed — carried-forward Minor findings were
    silently lost. Journal a `notify` breadcrumb (run_watch renders it) so the owner learns the
    Minor roll-up was corrupt rather than legitimately empty. Best-effort; never raises."""
    try:
        journal.append(control_plane.paths(root, a.work_item)["events"], "notify",
                       detail=("minor-findings roll-up was corrupt (unparseable) — carried-forward "
                               "Minor findings could not be read and may be lost"),
                       root=root)
    except Exception:
        pass


# read_status distinguishes a corrupt roll-up (existed, unparseable) from a legitimately-absent one.
_before, corrupt = minor_rollup.read_status(path)
if corrupt:
    _disclose_corruption()

if a.append:
    try:
        findings = json.loads(a.append)
    except ValueError:
        findings = []                              # malformed -> append nothing (fail-safe)
    minors = minor_rollup.append(path, findings)
else:
    minors = _before
print(json.dumps({"minors": minors, "corrupt": corrupt}))
