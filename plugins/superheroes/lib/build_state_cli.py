# plugins/superheroes/lib/build_state_cli.py
"""IO leaf for build_state: gather the reconcile state from git + the store, or record a per-task
review / final-review. Git + store IO live here; build_state.py stays pure."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_state, control_plane, ship_gate


def _git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def _base(root):
    for ref in ("origin/main", "main", "master"):
        if _git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    r = _git(root, "rev-list", "--max-parents=0", "HEAD")
    return (r.stdout.split() or ["HEAD"])[0]


def _gather(root, work_item, valid_ids):
    base = _base(root)
    mb = _git(root, "merge-base", "HEAD", base).stdout.strip() or base
    log = _git(root, "log", "--format=%H%x1f%(trailers:key=Task-Id,valueonly)", "%s..HEAD" % mb)
    rows = []
    for line in (log.stdout or "").splitlines():
        sha, _sep, tid = line.partition("\x1f")
        rows.append((sha, tid.strip()))
    committed, unmapped = build_state.parse_trailers(rows, valid_ids)
    dirty = bool(_git(root, "status", "--porcelain").stdout.strip())
    st = build_state.read_state(build_state.state_path(root, work_item))
    prov_path = control_plane.paths(root, work_item)["provenance"]
    try:
        prov = ship_gate.read_provenance(prov_path)
        prov_state = "present" if prov.get("build") else "absent"
    except ship_gate.ProvenanceError:
        prov_state = "garbled"
    return {"committed_task_ids": committed, "unmapped_commits": unmapped,
            "review_records": st["reviewed"], "worktree_dirty": dirty,
            "final_review": st["final_review"], "provenance": prov_state}


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gather"); g.add_argument("--work-item", required=True)
    g.add_argument("--branch", required=True); g.add_argument("--valid-ids", default="")
    rr = sub.add_parser("record-reviewed"); rr.add_argument("--work-item", required=True)
    rr.add_argument("--task", required=True)
    rf = sub.add_parser("record-final-review"); rf.add_argument("--work-item", required=True)
    rf.add_argument("--clean", required=True, choices=["true", "false"])
    a = ap.parse_args(argv[1:])
    root = os.getcwd()
    if a.cmd == "gather":
        valid = [x for x in a.valid_ids.split(",") if x]
        print(json.dumps(_gather(root, a.work_item, valid)))
        return 0
    sp = build_state.state_path(root, a.work_item)
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    if a.cmd == "record-reviewed":
        build_state.set_reviewed(sp, a.task)
    else:
        build_state.set_final_review(sp, a.clean == "true")
    print(json.dumps({"ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
