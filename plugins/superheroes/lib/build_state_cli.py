# plugins/superheroes/lib/build_state_cli.py
"""IO leaf for build_state: gather the reconcile state from git + the store, or record a per-task
review / final-review. Git + store IO live here; build_state.py stays pure."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_state, control_plane, ship_gate


def _git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def _base(git_root):
    # Prefer the remote's ACTUAL default branch (a non-standard default must not fall through to
    # the root commit, which would read the whole branch as unmapped).
    sr = _git(git_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if sr.returncode == 0:
        ref = sr.stdout.strip()
        if ref.startswith("refs/remotes/"):
            ref = ref[len("refs/remotes/"):]          # -> e.g. "origin/main"
        if ref and _git(git_root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    for ref in ("origin/main", "main", "master"):
        if _git(git_root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    r = _git(git_root, "rev-list", "--max-parents=0", "HEAD")
    return (r.stdout.split() or ["HEAD"])[0]


def _resolve_configured_base(git_root, branch_name):
    """Resolve a caller-supplied base branch name to a ref that git can use.

    Tries <branch_name> first (a local ref like 'live-showrunner-102'), then
    'origin/<branch_name>' (its remote-tracking counterpart). Returns the resolved
    ref string on success, or None on failure (caller must fail closed).
    """
    for ref in (branch_name, "origin/" + branch_name):
        r = _git(git_root, "rev-parse", "--verify", "--quiet", ref)
        if r.returncode == 0:
            return ref
    return None


def _gather(root, work_item, valid_ids, worktree=None, base_branch=None):
    # Git reads run in the BUILD WORKTREE (where the build branch is checked out); the STORE reads
    # below stay on `root` (the main checkout the showrunner runs in, where the store is keyed).
    git_root = worktree or root
    if base_branch:
        # Caller-supplied base: resolve it; fail closed on an unresolvable ref so UFR-7
        # is never opened by a misconfigured base silently treating everything as unmapped.
        base = _resolve_configured_base(git_root, base_branch)
        if base is None:
            raise SystemExit(
                "error: --base %r could not be resolved in %s "
                "(tried local and origin/<branch>) — failing closed" % (base_branch, git_root))
    else:
        base = _base(git_root)
    mb = _git(git_root, "merge-base", "HEAD", base).stdout.strip() or base
    log = _git(git_root, "log", "--format=%H%x1f%(trailers:key=Task-Id,valueonly)", "%s..HEAD" % mb)
    rows = []
    for line in (log.stdout or "").splitlines():
        sha, _sep, tid = line.partition("\x1f")
        rows.append((sha, tid.strip()))
    committed, unmapped = build_state.parse_trailers(rows, valid_ids)
    dirty = bool(_git(git_root, "status", "--porcelain").stdout.strip())
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
    g.add_argument("--worktree", default=None)   # the build worktree to read git from (else ambient root)
    g.add_argument("--base", default=None)       # configurable base branch; absent -> _base() detection
    rr = sub.add_parser("record-reviewed"); rr.add_argument("--work-item", required=True)
    rr.add_argument("--task", required=True)
    rf = sub.add_parser("record-final-review"); rf.add_argument("--work-item", required=True)
    rf.add_argument("--clean", required=True, choices=["true", "false"])
    a = ap.parse_args(argv[1:])
    root = os.getcwd()
    if a.cmd == "gather":
        valid = [x for x in a.valid_ids.split(",") if x]
        print(json.dumps(_gather(root, a.work_item, valid, a.worktree, a.base)))
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
