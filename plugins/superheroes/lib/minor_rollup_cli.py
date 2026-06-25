# plugins/superheroes/lib/minor_rollup_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane, minor_rollup

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
ap.add_argument("--append", default=None)
a = ap.parse_args()
root = os.getcwd()
path = os.path.join(control_plane.paths(root, a.work_item)["issue_dir"], "minor-findings.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
if a.append:
    try:
        findings = json.loads(a.append)
    except ValueError:
        findings = []                              # malformed -> append nothing (fail-safe)
    minors = minor_rollup.append(path, findings)
else:
    minors = minor_rollup.read(path)
print(json.dumps({"minors": minors}))
