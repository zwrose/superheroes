# plugins/superheroes/lib/pr_entry.py
"""draft-PR / mark-ready leaf. draft: recover.pr_action(world) -> adopt an open PR or create one
after ship_gate.decide proves build+review; returns {pr}. mark-ready: pr_phase.mark_ready_action on
a gh isDraft read -> flip if needed. Fail-closed: any 'gate' decision returns ok:false."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane, pr_phase, recover, ship_gate

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True, choices=["draft", "mark-ready"])
ap.add_argument("--work-item", required=True)
a = ap.parse_args()
root = os.getcwd()
paths = control_plane.paths(root, a.work_item)
cp = ckpt_lib.read(paths["checkpoint"]) or {}
branch = cp.get("branch", "")


def _gh_pr(branch):
    r = subprocess.run(["gh", "pr", "list", "--head", branch, "--state", "all",
                        "--json", "number,url,isDraft,state"], capture_output=True, text=True)
    if r.returncode != 0:
        return "unknown"
    try:
        arr = json.loads(r.stdout or "[]")
    except ValueError:
        return "unknown"                                 # malformed gh output -> fail closed
    return arr[0] if arr else None


if a.step == "draft":
    world = {"pr": _gh_pr(branch)}
    act = recover.pr_action(world)                       # adopt | create | gate (exactly-once)
    if act == "gate":
        print(json.dumps({"ok": False, "reason": "PR read transient/merged — not creating a 2nd PR"})); sys.exit(0)
    if act == "adopt":
        print(json.dumps({"ok": True, "pr": world["pr"]})); sys.exit(0)
    # create: only after the ship-gate proves SDD build + review-code ran over HEAD.
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    prov = ship_gate.read_provenance(paths["provenance"])
    from review_result import read_result
    decision = ship_gate.decide(prov, read_result(paths["review_result"]), head)
    if decision["action"] != "proceed":
        print(json.dumps({"ok": False, "reason": decision["reason"]})); sys.exit(0)
    out = subprocess.run(["gh", "pr", "create", "--draft", "--fill", "--head", branch],
                         capture_output=True, text=True)
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
    if decision == "flip":
        if subprocess.run(["gh", "pr", "ready", str(pr["number"])]).returncode != 0:
            print(json.dumps({"ok": False, "reason": "gh pr ready failed — PR still draft"})); sys.exit(0)
    print(json.dumps({"ok": True}))
