# plugins/superheroes/lib/build_state_cli.py
"""IO leaf for build_state: gather the reconcile state from git + the store, or record a per-task
review / final-review. Git + store IO live here; build_state.py stays pure."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_state, control_plane, ship_gate, base_ref
import idempotent_write
from engine_adapter import TASK_ID_TRAILER


def _git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


class _BaseUnresolvable(Exception):
    """Raised by _gather when a caller-supplied --base resolves to nothing. Carried up to main so
    the unresolvable-base case can be emitted as a STRUCTURED stdout error (C-I3) instead of a
    stderr SystemExit the exec dumb-pipe discards (which collapsed to a generic 'could not gather'
    park, misdirecting the owner)."""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


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


def _gather(root, work_item, valid_ids, worktree=None, base_branch=None):
    # Git reads run in the BUILD WORKTREE (where the build branch is checked out); the STORE reads
    # below stay on `root` (the main checkout the showrunner runs in, where the store is keyed).
    git_root = worktree or root
    if base_branch:
        # Caller-supplied base: resolve it via the SHARED resolver (local->origin) so this gather
        # and ship_phase's freshness gate measure against the SAME ref (C-I1). Fail closed on an
        # unresolvable ref so UFR-7 is never opened by a misconfigured base silently treating
        # everything as unmapped — raise so main can emit a structured stdout error (C-I3).
        base = base_ref.resolve_configured_base(git_root, base_branch)
        if base is None:
            raise _BaseUnresolvable(base_ref.unresolvable_reason(base_branch, git_root))
    else:
        base = _base(git_root)
    mb = _git(git_root, "merge-base", "HEAD", base).stdout.strip() or base
    log = _git(git_root, "log",
               "--format=%H%x1f%(trailers:key=" + TASK_ID_TRAILER + ",valueonly)",
               "%s..HEAD" % mb)
    rows = []
    for line in (log.stdout or "").splitlines():
        sha, _sep, tid = line.partition("\x1f")
        if not sha.strip():  # spurious empty row from the trailers' trailing newline — not a commit
            continue
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
    rb = sub.add_parser("record-built"); rb.add_argument("--work-item", required=True)
    rb.add_argument("--task", required=True)
    rr = sub.add_parser("record-reviewed"); rr.add_argument("--work-item", required=True)
    rr.add_argument("--task", required=True)
    rf = sub.add_parser("record-final-review"); rf.add_argument("--work-item", required=True)
    rf.add_argument("--clean", required=True, choices=["true", "false"])
    a = ap.parse_args(argv[1:])
    root = os.getcwd()
    if a.cmd == "gather":
        valid = [x for x in a.valid_ids.split(",") if x]
        try:
            state = _gather(root, a.work_item, valid, a.worktree, a.base)
        except _BaseUnresolvable as e:
            # Emit the SPECIFIC base-resolution reason on STDOUT (exit 0) so the exec dumb-pipe
            # captures it and gatherState can park with THAT reason — not the generic "could not
            # gather authoritative git state" (C-I3). Still fail-closed: the spine treats the
            # presence of an `error` key as a park signal, never as a usable state.
            print(json.dumps({"error": e.reason}))
            return 0
        print(json.dumps(state))
        return 0
    sp = build_state.state_path(root, a.work_item)
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    if a.cmd == "record-final-review":
        clean = a.clean == "true"

        def _read_final():
            st = build_state.read_state(sp)
            fr = st.get("final_review") or {}
            return fr.get("clean") is clean

        def _apply_final():
            build_state.set_final_review(sp, clean)
            return _read_final(), {"read_back": _read_final(), "clean": clean}

        result = idempotent_write.idempotent_apply(
            f"build-state:{a.work_item}:final-review:{clean}",
            lambda: (_read_final(), {"read_back": _read_final(), "clean": clean}),
            _apply_final,
        )
        detail = result.get("detail") or {}
        print(json.dumps({
            "ok": bool(result.get("ok")),
            "already": bool(result.get("already")),
            "read_back": bool(detail.get("read_back")),
            "clean": bool(detail.get("clean")),
        }))
        return 0

    task = str(a.task)

    def _read_state():
        return build_state.read_state(sp)

    def _read_back(kind):
        st = _read_state()
        if kind == "built":
            return task in (st.get("built") or {})
        return (st.get("reviewed") or {}).get(task) == "passed"

    def _apply_built():
        st = _read_state()
        st.setdefault("built", {})
        st["built"][task] = "passed"
        control_plane.atomic_write(sp, json.dumps(st))
        return _read_back("built"), {"read_back": _read_back("built"), "task": task}

    def _apply_reviewed():
        build_state.set_reviewed(sp, task)
        return _read_back("reviewed"), {"read_back": _read_back("reviewed"), "task": task}

    if a.cmd == "record-built":
        key = f"build-state:{a.work_item}:built:{task}"
        result = idempotent_write.idempotent_apply(
            key,
            lambda: (_read_back("built"), {"read_back": _read_back("built"), "task": task}),
            _apply_built,
        )
    else:
        key = f"build-state:{a.work_item}:reviewed:{task}"
        result = idempotent_write.idempotent_apply(
            key,
            lambda: (_read_back("reviewed"), {"read_back": _read_back("reviewed"), "task": task}),
            _apply_reviewed,
        )
    detail = result.get("detail") or {}
    print(json.dumps({
        "ok": bool(result.get("ok")),
        "already": bool(result.get("already")),
        "read_back": bool(detail.get("read_back")),
        "task": detail.get("task") or task,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
