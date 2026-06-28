# plugins/superheroes/lib/pr_entry.py
"""draft-PR / mark-ready leaf. draft: recover.pr_action(world) -> adopt an open PR or create one
after ship_gate.decide proves build+review; returns {pr}. mark-ready: pr_phase.mark_ready_action on
a gh isDraft read -> flip if needed. Fail-closed: any 'gate' decision returns ok:false."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane, pr_phase, recover, ship_gate, test_pilot_status

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True, choices=["draft", "mark-ready"])
ap.add_argument("--work-item", required=True)
ap.add_argument("--emit-world", action="store_true",
                help="IO-only mode: world-read the PR and emit {pr} without judgment or creation")
a = ap.parse_args()
root = os.getcwd()
paths = control_plane.paths(root, a.work_item)
cp = ckpt_lib.read(paths["checkpoint"])
if isinstance(cp, dict) and cp.get("_incompatible"):
    # A durable-but-incompatible checkpoint must NOT fall back to an empty branch (that
    # lists/creates PRs against the ambient HEAD). Fail closed before any PR action.
    print(json.dumps({"ok": False,
                      "reason": "checkpoint incompatible: %s" % cp.get("reason", "unknown reason")}))
    sys.exit(0)
cp = cp or {}
branch = cp.get("branch", "")


def _gh_pr(branch):
    try:
        r = subprocess.run(["gh", "pr", "list", "--head", branch, "--state", "all",
                            "--json", "number,url,isDraft,state"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "unknown"                                 # a hung gh read -> transient
    if r.returncode != 0:
        return "unknown"
    try:
        arr = json.loads(r.stdout or "[]")
    except ValueError:
        return "unknown"                                 # malformed gh output -> fail closed
    return arr[0] if arr else None


if a.step == "draft" and a.emit_world:
    # IO-only emit mode: world-read the PR and emit {pr} — no judgment, no creation. The JS twin
    # (recover.prAction) decides adopt/create/gate in-process.
    world = {"pr": _gh_pr(branch)}
    print(json.dumps(world))
    sys.exit(0)

if a.step == "draft":
    world = {"pr": _gh_pr(branch)}
    act = recover.pr_action(world)                       # adopt | create | gate (exactly-once)
    if act == "gate":
        print(json.dumps({"ok": False, "reason": "PR read transient/merged — not creating a 2nd PR"})); sys.exit(0)
    if act == "adopt":
        print(json.dumps({"ok": True, "pr": world["pr"]})); sys.exit(0)
    # create: only after the ship-gate proves SDD build + review-code ran over the SHIPPED HEAD —
    # the build branch's tip (what the PR ships), resolved from checkpoint.branch, not the cwd HEAD.
    try:
        _hp = subprocess.run(["git", "rev-parse", branch or "HEAD"], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "reason": "git rev-parse timed out"})); sys.exit(0)
    head = _hp.stdout.strip()
    if _hp.returncode != 0 or not head:
        print(json.dumps({"ok": False, "reason": "cannot resolve branch HEAD for the ship-gate"})); sys.exit(0)
    try:
        prov = ship_gate.read_provenance(paths["provenance"])
    except ship_gate.ProvenanceError as e:           # corrupt provenance.json -> gate (fail closed)
        print(json.dumps({"ok": False, "reason": "provenance unreadable: %s" % e})); sys.exit(0)
    from review_result import read_result
    decision = ship_gate.decide(prov, read_result(paths["review_result"]), head)
    if decision["action"] != "proceed":
        print(json.dumps({"ok": False, "reason": decision["reason"]})); sys.exit(0)
    try:
        out = subprocess.run(["gh", "pr", "create", "--draft", "--fill", "--head", branch],
                             capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        # the create may have landed server-side -> park; recover.pr_action adopts it on resume.
        print(json.dumps({"ok": False, "reason": "gh pr create timed out — will adopt on resume"})); sys.exit(0)
    if out.returncode != 0:
        print(json.dumps({"ok": False, "reason": "gh pr create failed"})); sys.exit(0)
    # Read the just-created PR back. A transient read failure must NOT be recorded as ok:true with
    # pr=null (that loses the PR for ship/mark-ready, and the readout never reaches the PR thread).
    # Park instead — on resume recover.pr_action adopts the now-existing PR (exactly-once preserved).
    pr = _gh_pr(branch)
    if not isinstance(pr, dict):
        print(json.dumps({"ok": False,
                          "reason": "PR created but read-back failed transiently — will adopt on resume"}))
        sys.exit(0)
    print(json.dumps({"ok": True, "pr": pr}))
else:  # mark-ready
    pr = _gh_pr(branch)
    decision = pr_phase.mark_ready_action(pr)
    if decision == "gate":
        print(json.dumps({"ok": False, "reason": "PR isDraft unreadable — not flipping blind"})); sys.exit(0)
    try:
        _hp = subprocess.run(["git", "rev-parse", branch or "HEAD"], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "reason": "git rev-parse timed out"})); sys.exit(0)
    head = _hp.stdout.strip()
    if _hp.returncode != 0 or not head:
        print(json.dumps({"ok": False, "reason": "cannot resolve branch HEAD for test-pilot status"})); sys.exit(0)
    status_result = test_pilot_status.assert_current(test_pilot_status.status_path(root, a.work_item), head)
    status_decision = pr_phase.mark_ready_status_action(status_result)
    if status_decision["action"] == "gate":
        print(json.dumps({"ok": False, "reason": status_decision["reason"]})); sys.exit(0)
    if decision == "flip":
        try:                                             # capture: gh's success line must not pollute our stdout
            rc = subprocess.run(["gh", "pr", "ready", str(pr["number"])], capture_output=True, timeout=60).returncode
        except subprocess.TimeoutExpired:
            print(json.dumps({"ok": False, "reason": "gh pr ready timed out — PR still draft"})); sys.exit(0)
        if rc != 0:
            print(json.dumps({"ok": False, "reason": "gh pr ready failed — PR still draft"})); sys.exit(0)
    print(json.dumps({"ok": True}))
