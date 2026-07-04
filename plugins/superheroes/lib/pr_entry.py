# plugins/superheroes/lib/pr_entry.py
"""draft-PR / mark-ready leaf. draft: recover.pr_action(world) -> adopt an open PR or create one
after ship_gate.decide proves build+review; returns {pr}. mark-ready: pr_phase.mark_ready_action on
a gh isDraft read -> flip if needed. Fail-closed: any 'gate' decision returns ok:false."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane, pr_phase, recover, ship_gate, test_pilot_status
import idempotent_write


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


def push_branch(branch, run=None, timeout=120):
    """Push the build branch to origin BEFORE PR creation. `gh pr create --head <branch>` requires
    the branch to exist on the remote, but nothing upstream pushes it — every push (reconcile-head /
    freshen / fix-push) lives in ship_phase, which runs AFTER draft-PR. Ordinary non-force push
    (FR-9, never --force / --force-with-lease); refs are shared with the build worktree, so pushing
    from the repo root reaches the branch. Idempotent: an already-pushed, up-to-date branch is a
    no-op success. Returns None on success, else a park reason string (fail-closed — the same
    park contract as the other draft failure exits)."""
    run = run or subprocess.run
    try:
        r = run(["git", "push", "origin", branch], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Unlike a `gh pr create` timeout, a push timeout leaves NO PR to adopt on resume (the PR
        # does not exist yet) — so "will adopt on resume" does NOT apply; a plain park is correct.
        return "branch push timed out before PR create"
    if r.returncode != 0:
        return "branch push failed before PR create: %s" % (r.stderr or "")[-300:]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True, choices=["draft", "mark-ready"])
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--emit-world", action="store_true",
                    help="IO-only mode: world-read the PR and emit {pr} without judgment or creation")
    ap.add_argument("--base", default=None,
                    help="configurable PR target base branch; absent -> gh uses remote default (current behavior)")
    a = ap.parse_args(argv)
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
            print(json.dumps({"ok": False, "read_back": False,
                              "reason": "PR read transient/merged — not creating a 2nd PR"})); sys.exit(0)
        if act == "adopt":
            current = _gh_pr(branch)
            read_back = isinstance(current, dict) and isinstance(world["pr"], dict) and current.get("number") == world["pr"].get("number")
            print(json.dumps({"ok": True, "pr": world["pr"], "read_back": bool(read_back)})); sys.exit(0)
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
        # Push the build branch before creating the PR (see push_branch): `gh pr create --head` needs
        # the branch on origin, but every ship_phase push runs AFTER this step. On any failure, park
        # fail-closed — on resume recover.pr_action re-pushes (no-op) then creates (exactly-once holds).
        _push_park = push_branch(branch)
        if _push_park is not None:
            print(json.dumps({"ok": False, "read_back": False, "reason": _push_park})); sys.exit(0)
        # Build the gh pr create command. When --base is supplied, pass it explicitly so the
        # PR targets the configured base (not the remote default). Absent -> omit (default behavior).
        # --fill-first (not --fill): derive the title from the FIRST commit's subject. `--fill` uses the
        # branch NAME as the title for a multi-commit branch, which is not a Conventional Commit and fails
        # a conventional-title CI check (blocking ship); the build's first commit subject IS conventional.
        _gh_create_cmd = ["gh", "pr", "create", "--draft", "--fill-first", "--head", branch]
        if a.base:
            _gh_create_cmd.extend(["--base", a.base])
        try:
            out = subprocess.run(_gh_create_cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            # the create may have landed server-side -> park; recover.pr_action adopts it on resume.
            print(json.dumps({"ok": False, "read_back": False, "reason": "gh pr create timed out — will adopt on resume"})); sys.exit(0)
        if out.returncode != 0:
            # Surface a bounded tail of gh's stderr so a parked create is diagnosable (not a bare
            # "gh pr create failed" with no cause).
            print(json.dumps({"ok": False, "read_back": False,
                              "reason": "gh pr create failed: %s" % (out.stderr or "")[-300:]})); sys.exit(0)
        # Read the just-created PR back. A transient read failure must NOT be recorded as ok:true with
        # pr=null (that loses the PR for ship/mark-ready, and the readout never reaches the PR thread).
        # Park instead — on resume recover.pr_action adopts the now-existing PR (exactly-once preserved).
        pr = _gh_pr(branch)
        if not isinstance(pr, dict):
            print(json.dumps({"ok": False, "read_back": False,
                              "reason": "PR created but read-back failed transiently — will adopt on resume"}))
            sys.exit(0)
        current = _gh_pr(branch)
        read_back = isinstance(current, dict) and current.get("number") == pr.get("number")
        print(json.dumps({"ok": True, "pr": pr, "read_back": bool(read_back)}))
    else:  # mark-ready
        pr = _gh_pr(branch)
        decision = pr_phase.mark_ready_action(pr)
        if decision == "gate":
            print(json.dumps({"ok": False, "read_back": False, "reason": "PR isDraft unreadable — not flipping blind"})); sys.exit(0)
        try:
            _hp = subprocess.run(["git", "rev-parse", branch or "HEAD"], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            print(json.dumps({"ok": False, "reason": "git rev-parse timed out"})); sys.exit(0)
        head = _hp.stdout.strip()
        if _hp.returncode != 0 or not head:
            print(json.dumps({"ok": False, "read_back": False, "reason": "cannot resolve branch HEAD for test-pilot status"})); sys.exit(0)
        status_result = test_pilot_status.assert_current(test_pilot_status.status_path(root, a.work_item), head)
        status_decision = pr_phase.mark_ready_status_action(status_result)
        if status_decision["action"] == "gate":
            print(json.dumps({"ok": False, "read_back": False, "reason": status_decision["reason"]})); sys.exit(0)
        if decision == "flip":
            n = str(pr["number"])

            def _reader():
                cur = _gh_pr(branch)
                if not isinstance(cur, dict):
                    return (None, "PR isDraft unreadable")
                d = cur.get("isDraft")
                if d is False:
                    return (True, "already ready")
                if d is True:
                    return (False, "draft")
                return (None, "isDraft ambiguous")

            def _apply():
                try:
                    rc = subprocess.run(["gh", "pr", "ready", n], capture_output=True, timeout=60).returncode
                except subprocess.TimeoutExpired:
                    return (False, "gh pr ready timed out — PR still draft")
                return (rc == 0, "flipped to ready")

            res = idempotent_write.idempotent_apply("ready:pr=%s" % n, _reader, _apply)
            if not res["ok"]:
                print(json.dumps({"ok": False, "read_back": False, "reason": res["reason"] or "gh pr ready failed — PR still draft"}))
                sys.exit(0)
        current = _gh_pr(branch)
        read_back = isinstance(current, dict) and current.get("isDraft") is False
        print(json.dumps({"ok": True, "read_back": bool(read_back)}))


if __name__ == "__main__":
    main()
