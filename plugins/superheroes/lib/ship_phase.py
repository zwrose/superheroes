# plugins/superheroes/lib/ship_phase.py
import argparse, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freshness, ci_loop, control_plane, journal, ci_status, checkpoint as ckpt_lib, base_ref
import idempotent_write, ship_reconcile, ship_ci


def _resolve_pr_number(work_item):
    """The run's PR number from the recorded checkpoint, else from `gh pr view`. None on any error."""
    try:
        paths = control_plane.paths(os.getcwd(), work_item)
        cp = ckpt_lib.read(paths["checkpoint"]) or {}
        pr = cp.get("pr")
        if isinstance(pr, dict) and pr.get("number"):
            return str(pr["number"])
    except Exception:
        pass
    try:
        out = subprocess.run(["gh", "pr", "view", "--json", "number", "--jq", ".number"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _git(args, cwd=None):
    """(rc, stdout). A timeout/raise -> (2, '') so callers fail closed."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=60)
        return r.returncode, (r.stdout or "").strip()
    except Exception:
        return 2, ""


def _local_head(cwd=None):
    rc, out = _git(["rev-parse", "HEAD"], cwd=cwd)
    return out if rc == 0 and out else None


def _remote_pr_head(work_item, branch=None, cwd=None):
    """The PR's current remote head SHA via gh, or None on any unreadable read (fail closed).
    Falls back to git ls-remote when branch is given and gh cannot resolve the PR number
    (e.g. in test environments with a local bare origin and no real GitHub PR)."""
    pr = _resolve_pr_number(work_item)
    if pr:
        try:
            r = subprocess.run(["gh", "pr", "view", pr, "--json", "headRefOid", "--jq", ".headRefOid"],
                               capture_output=True, text=True, timeout=30)
        except Exception:
            pass
        else:
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
    # fallback: read the remote branch tip directly when no gh-resolvable PR number is available
    if branch:
        try:
            r = subprocess.run(["git", "ls-remote", "origin", branch],
                               capture_output=True, text=True, timeout=30, cwd=cwd)
        except Exception:
            return None
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split()[0]  # first field is the SHA
    return None


def _replay_push_onto_remote(work_item, branch, wt):
    """After a non-fast-forward push rejection, fetch the advanced remote tip, rebase, repush."""
    remote = _remote_pr_head(work_item, branch, wt)
    if not remote:
        return False, _local_head(wt), False, "push rejected and remote PR head unreadable — park"
    fetch_rc, _ = _git(["fetch", "--quiet", "origin", branch], cwd=wt)
    if fetch_rc != 0:
        return False, _local_head(wt), False, "push rejected and could not fetch the advanced remote head — park"
    rebase_rc, _ = _git(["rebase", "FETCH_HEAD"], cwd=wt)
    if rebase_rc != 0:
        _git(["rebase", "--abort"], cwd=wt)
        return False, _local_head(wt), False, "cannot cleanly replay local-ahead commits onto advanced PR head — park"
    repush_rc, _ = _git(["push", "origin", branch], cwd=wt)
    if repush_rc != 0:
        return False, _local_head(wt), False, "replay push still rejected — park (no force)"
    head = _local_head(wt)
    read_back = _push_read_back(work_item, branch, wt, head)
    reason = "fix replayed onto advanced PR head and pushed" if read_back else "push read-back failed"
    return True, head, read_back, reason


def _push_read_back(work_item, branch, wt, local, attempts=3, delay=2.0):
    """Confirm a just-accepted push is visible on the remote. The branch ref via ls-remote is
    the LOAD-BEARING check and comes first — it updates atomically with the accepted push; the
    PR API head (gh) can lag a pushed ref by seconds, which made a successful push read back as
    failed (run-32 false park). gh is consulted only on the FIRST attempt as corroboration;
    retries are ls-remote-only, keeping the worst case inside the leaf's timeout budget.
    Bounded retries absorb the lag; False only when the remote never shows the head."""
    for i in range(attempts):
        if i:
            time.sleep(delay)
        if branch:
            rc, out = _git(["ls-remote", "origin", branch], cwd=wt)
            if rc == 0 and out and out.split()[0] == local:
                return True
        if i == 0 and _remote_pr_head(work_item, branch, wt) == local:
            return True
    return False


def _fixer_committed_ahead(work_item, branch, wt):
    """(qualifies, park_reason): qualifies is True when the CI fixer committed its own fix
    instead of leaving it uncommitted — the tree is clean and the local HEAD is STRICTLY ahead
    of a READABLE remote PR head (run-31 park — the commit was the fixer's product, but the
    empty staged tree read as "nothing produced"). An unreadable remote, an already-synced
    head, or a diverged/unprovable history stays False — the caller parks fail-closed rather
    than guess-push, with park_reason naming which case it hit."""
    local = _local_head(wt)
    if not local:
        return False, "no change to push — nothing the fixer produced"
    remote = _remote_pr_head(work_item, branch, wt)
    if not remote:
        return False, "clean tree and remote PR head unreadable — park"
    if remote == local:
        return False, "no change to push — nothing the fixer produced"
    rc, _ = _git(["merge-base", "--is-ancestor", remote, local], cwd=wt)
    if rc != 0:
        return False, "clean tree but local and remote PR head have diverged — park (no guess-push)"
    return True, ""


def _fence_check(work_item, generation, root):
    """Inline renew-then-fence; skipped when generation is absent (smoke/test paths)."""
    if generation is None:
        return {"ok": True, "reason": "no generation — fence skipped"}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        checkout_root = os.path.realpath(root)
    except (TypeError, ValueError, OSError):
        return {"ok": False, "reason": "fence unreadable"}
    if not checkout_root or not os.path.isdir(checkout_root):
        return {"ok": False, "reason": "fence unreadable"}
    try:
        r = subprocess.run([sys.executable, os.path.join(script_dir, "fence_cli.py"),
                            "--work-item", work_item, "--generation", str(generation),
                            "--root", checkout_root],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return {"ok": False, "reason": "fence unreadable"}
    try:
        return json.loads((r.stdout or "").strip() or "{}")
    except Exception:
        return {"ok": False, "reason": "fence unreadable"}


def _emit_checks_payload(work_item, worktree):
    """Raw checks array, {stale:...}, or {error:...} for the integrated head."""
    wt = worktree or os.getcwd()
    local = _local_head(wt)
    remote = _remote_pr_head(work_item, cwd=wt)
    if ship_ci.is_stale(local, remote):
        return {"stale": True, "local": local, "remote": remote}
    pr = _resolve_pr_number(work_item)
    if not pr:
        return {"error": "CI status could not be read"}
    try:
        out = subprocess.run(["gh", "pr", "checks", pr, "--json", "name,bucket,state"],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return {"error": "CI status could not be read"}
    raw = out.stdout.strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return {"error": "CI status could not be read"}


def _read_ci(work_item):
    """Real CI read -> {"decision": green|red|none, "reason": text, "failing": [...]}. Fail-CLOSED:
    any read error -> red (never green)."""
    pr = _resolve_pr_number(work_item)
    if not pr:
        return {"decision": "red", "reason": "CI status could not be read"}
    try:
        out = subprocess.run(["gh", "pr", "checks", pr, "--json", "name,bucket,state"],
                             capture_output=True, text=True, timeout=30)
        # `gh pr checks` exits non-zero when checks are failing/pending; the JSON is still on stdout,
        # so parse stdout regardless of returncode and let ci_status classify.
        checks = json.loads(out.stdout) if out.stdout.strip() else []
    except Exception:
        return {"decision": "red", "reason": "CI status could not be read"}
    res = ci_status.classify(checks)
    status = res["status"]
    if status == "green":
        return {"decision": "green", "reason": "all required checks pass", "failing": []}
    if status == "none":
        return {"decision": "none",
                "reason": "no required checks gate this PR — confirm checks before merging",
                "failing": []}
    if status == "pending":
        # Still not-green (fail-closed for every certification consumer of this decision),
        # but say WHY honestly — these checks are running, not failing. The ship loop's
        # settle-wait consumes the classifier's tri-state directly, not this decision.
        return {"decision": "red",
                "reason": "checks still running: %s" % ", ".join(res["pending"]),
                "failing": []}
    return {"decision": "red",
            "reason": "checks not green: %s" % ", ".join(res["failing"]),
            "failing": res["failing"]}

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True,
                choices=["freshness", "ci", "reconcile-head", "freshen", "ci-decide",
                         "ci-record", "fix-push", "revert-draft",
                         "ship-readiness", "prepare-ci-fix", "push-ci-fix-recheck"])
ap.add_argument("--generation", type=int, default=None,
                help="lease generation for inline fence before mutations inside ship-readiness")
ap.add_argument("--checks-only", action="store_true",
                help="ship-readiness: emit checks only (stale re-wait), skip reconcile/catch-up")
ap.add_argument("--work-item", required=True)
ap.add_argument("--emit-checks", action="store_true",
                help="IO-only mode: emit raw checks array (or {error:...}) without classifying")
ap.add_argument("--base", default=None,
                help="configurable base branch name; absent -> default 'main' (current behavior)")
ap.add_argument("--attempt", type=int, default=1,
                help="1-based catch-up attempt threaded into freshness.decide (default 1)")
ap.add_argument("--worktree", default=None,
                help="the build worktree the git mechanics run in; absent -> cwd")
ap.add_argument("--round", type=int, default=None, help="1-based CI-fix round for ci-record")
ap.add_argument("--root", default=None,
                help="checkout root the control-plane store is keyed to (required for fence when --generation is set)")
ap.add_argument("--failing", default=None, help="JSON array of current failing check signatures")
a = ap.parse_args()


def _store_root():
    if not a.root:
        return None
    try:
        root = os.path.realpath(a.root)
    except (TypeError, ValueError, OSError):
        return None
    return root if root and os.path.isdir(root) else None


if a.step == "freshness":

    # is the branch up to date with base = does HEAD contain <base> = is <base> an ancestor of HEAD.
    # (rc 0 = yes/up-to-date, 1 = behind, other = unreadable -> gate.)
    # FR-8: --base is a caller-supplied branch name (e.g. 'live-showrunner-102' or 'main').
    # Default to 'main' when absent so existing behavior is unchanged.
    wt = a.worktree or os.getcwd()
    base_name = a.base if a.base else "main"
    # C-I1: resolve the base via the SHARED resolver (local->origin), rooted in the worktree.
    resolved = base_ref.resolve_configured_base(wt, base_name)
    if resolved is None:
        print(json.dumps({"decision": "gate",
                          "reason": base_ref.unresolvable_reason(base_name, wt)}))
    else:
        try:
            rc = subprocess.run(["git", "merge-base", "--is-ancestor", resolved, "HEAD"],
                                capture_output=True, timeout=10, cwd=wt).returncode
        except subprocess.TimeoutExpired:
            rc = 2                                       # a hung read -> unreadable -> freshness gate
        is_anc = True if rc == 0 else (False if rc == 1 else None)
        decision, _reason = freshness.decide(is_anc, a.attempt)
        print(json.dumps({"decision": decision}))
elif a.step == "reconcile-head":
    # UFR-6: bring the remote PR head into agreement with the reconciled local head by pushing
    # local-ahead. The reader=(remote==local)/applier=push WIRING lives in the pure ship_reconcile
    # decider (testable without gh); this leaf only does the gh/git IO.
    wt = a.worktree or os.getcwd()
    local = _local_head(wt)
    if not local:
        print(json.dumps({"ok": False, "head": None, "reason": "local HEAD unreadable — fail closed"}))
        sys.exit(0)
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""

    def _push():
        rc, _ = _git(["push", "origin", branch], cwd=wt)          # ordinary non-force push (FR-9)
        if rc != 0:
            return False
        return _push_read_back(a.work_item, branch, wt, local)    # read-back-confirm the push landed

    res = ship_reconcile.reconcile_head(local, _remote_pr_head(a.work_item, branch, wt), branch, _push)
    # trust the apply result: _push() already read-back-confirmed with retries; re-probing here
    # (no-sleep single attempt) could flip a just-confirmed push back to false.
    read_back = bool(res.get("ok")) and (
        res.get("already") is True or res.get("applied") is True
    )
    print(json.dumps({"ok": bool(res["ok"]),
                      "head": local if res["ok"] else None,
                      "read_back": bool(read_back),
                      "reason": res["reason"]}))
elif a.step == "freshen":
    # FR-1/UFR-1/FR-9: bring the base into the branch. git's own auto-merge of non-overlapping
    # changes IS the "trivially-correct, high-confidence" resolution (committed + pushed + re-checked,
    # UFR-1 guarantee b). A real overlapping conflict -> `git merge --abort` leaving the head EXACTLY
    # where it was (UFR-1 guarantee a) + park; never a guessed or half-integrated branch.
    wt = a.worktree or os.getcwd()
    base_name = a.base if a.base else "main"
    resolved = base_ref.resolve_configured_base(wt, base_name)
    if resolved is None:
        print(json.dumps({"ok": False, "head": _local_head(wt), "conflict": False,
                          "reason": base_ref.unresolvable_reason(base_name, wt)}))
        sys.exit(0)
    _git(["fetch", "--quiet", "origin"], cwd=wt)                  # best-effort; local resolve still works
    before_head = _local_head(wt)
    rc, _ = _git(["merge", "--no-edit", resolved], cwd=wt)
    if rc != 0:
        # conflict (or merge error) -> abort to the exact prior head, leave a clean tree.
        _git(["merge", "--abort"], cwd=wt)
        print(json.dumps({"ok": False, "head": _local_head(wt), "conflict": True,
                          "reason": "base integration conflicts — aborted (head unchanged), owner must resolve"}))
        sys.exit(0)
    after_head = _local_head(wt)
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""
    if after_head and after_head != before_head and branch:
        push_rc, _ = _git(["push", "origin", branch], cwd=wt)     # ordinary non-force push (FR-9)
        if push_rc != 0:
            print(json.dumps({"ok": False, "head": after_head, "conflict": False,
                              "reason": "merged base but push failed — reconcile on resume"}))
            sys.exit(0)
    print(json.dumps({"ok": True, "head": after_head, "conflict": False,
                      "reason": "base integrated" if after_head != before_head else "already up to date"}))
elif a.step == "ci-decide":
    # FR-3/FR-4/UFR-5: replay the write-ahead round count from the journal (survives a crash),
    # then let ci_loop.decide (parity-locked) choose fix vs revert_and_gate.
    try:
        failing = json.loads(a.failing) if a.failing else []
    except ValueError:
        failing = []
    paths = control_plane.paths(os.getcwd(), a.work_item)
    prior_rounds, history = journal.ci_attempts(paths["events"])
    rnd = prior_rounds + 1
    action, reason = ci_loop.decide(failing, history, rnd)
    print(json.dumps({"action": action, "round": rnd, "reason": reason}))
elif a.step == "ci-record":
    # Write-ahead ONE ci_fix_attempt BEFORE the fixer runs (UFR-5: a crash over-counts, never under).
    try:
        failing = json.loads(a.failing) if a.failing else []
    except ValueError:
        failing = []
    paths = control_plane.paths(os.getcwd(), a.work_item)
    try:
        journal.append(paths["events"], "ci_fix_attempt",
                       payload={"round": a.round, "failing": failing}, root=os.getcwd())
    except journal.DurableWriteError as e:
        print(json.dumps({"ok": False, "read_back": False, "reason": "durable write failed: %s" % e}))
        sys.exit(0)
    rounds, hist = journal.ci_attempts(paths["events"])
    read_back = rounds >= int(a.round or 0) and bool(hist) and list(hist[-1]) == list(failing)
    print(json.dumps({"ok": True, "read_back": bool(read_back)}))
elif a.step == "fix-push":
    # The fixer agent (in the orchestrator) edited the worktree to fix failing checks. This step
    # commits + non-force pushes ONLY a clean worktree carrying exactly that change; a fixer that
    # already committed its own fix (clean tree, local strictly ahead of the remote PR head) counts
    # as that change too. A crashed fixer's residue (conflict markers) or a true no-op (clean tree,
    # nothing local-ahead) parks fail-closed (no push). On a non-fast-forward
    # rejection it replays the fixer commit onto the CURRENT remote PR head — never the base, never a
    # force, never dropping the commit; parks if it cannot cleanly replay.
    wt = a.worktree or os.getcwd()
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""
    if not branch:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "no branch recorded — cannot push"}))
        sys.exit(0)
    # clean-tree precondition: reject leftover conflict markers (a crashed/garbage fixer state).
    marker_rc, _ = _git(["diff", "--check"], cwd=wt)
    if marker_rc != 0:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "worktree carries conflict markers — crashed fixer, park (no push)"}))
        sys.exit(0)
    _git(["add", "-A"], cwd=wt)
    staged_rc, staged = _git(["diff", "--cached", "--name-only"], cwd=wt)
    if staged_rc != 0:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "could not read the staged tree (git index error) — park"}))
        sys.exit(0)
    if staged:
        commit_rc, _ = _git(["commit", "-m", "fix(superheroes): repair failing checks [showrunner]"], cwd=wt)
        if commit_rc != 0:
            print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                              "reason": "commit failed"}))
            sys.exit(0)
    else:
        ahead, park_reason = _fixer_committed_ahead(a.work_item, branch, wt)
        if not ahead:
            print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                              "reason": park_reason}))
            sys.exit(0)
        # the fixer committed its own fix — the local-ahead commit IS the product; push it as-is.
    push_rc, _ = _git(["push", "origin", branch], cwd=wt)         # ordinary non-force push (FR-9)
    if push_rc == 0:
        head = _local_head(wt)
        read_back = _push_read_back(a.work_item, branch, wt, head)
        print(json.dumps({"ok": True, "head": head, "pushed": True, "read_back": bool(read_back),
                          "reason": "fix pushed"}))
        sys.exit(0)
    # non-fast-forward: replay local-ahead onto the current remote PR head (never base, never force).
    # ok requires read_back too — an unconfirmed replay-push must not read as confirmed.
    _ok, head, read_back, reason = _replay_push_onto_remote(a.work_item, branch, wt)
    print(json.dumps({"ok": _ok and bool(read_back), "head": head, "pushed": _ok,
                      "read_back": bool(read_back), "reason": reason}))
elif a.step == "prepare-ci-fix":
    try:
        failing = json.loads(a.failing) if a.failing else []
    except ValueError:
        failing = []
    paths = control_plane.paths(os.getcwd(), a.work_item)
    prior_rounds, history = journal.ci_attempts(paths["events"])
    rnd = prior_rounds + 1
    action, reason = ci_loop.decide(failing, history, rnd)
    read_back = True
    ok = True
    if action == "fix":
        try:
            journal.append(paths["events"], "ci_fix_attempt",
                           payload={"round": rnd, "failing": failing}, root=os.getcwd())
            after_rounds, hist = journal.ci_attempts(paths["events"])
            read_back = after_rounds >= rnd and bool(hist) and list(hist[-1]) == list(failing)
            ok = read_back
        except journal.DurableWriteError as e:
            ok = False
            read_back = False
            reason = "durable write failed: %s" % e
    print(json.dumps({"action": action, "round": rnd, "reason": reason,
                      "ok": ok, "read_back": read_back}))
elif a.step == "push-ci-fix-recheck":
    wt = a.worktree or os.getcwd()
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""
    fail = {"ok": False, "head": _local_head(wt), "pushed": False, "read_back": False,
            "checks": {"error": "CI status could not be read"}}
    if not branch:
        fail["reason"] = "no branch recorded — cannot push"
        print(json.dumps(fail)); sys.exit(0)
    marker_rc, _ = _git(["diff", "--check"], cwd=wt)
    if marker_rc != 0:
        fail["reason"] = "worktree carries conflict markers — crashed fixer, park (no push)"
        print(json.dumps(fail)); sys.exit(0)
    _git(["add", "-A"], cwd=wt)
    staged_rc, staged = _git(["diff", "--cached", "--name-only"], cwd=wt)
    if staged_rc != 0:
        fail["reason"] = "could not read the staged tree (git index error) — park"
        print(json.dumps(fail)); sys.exit(0)
    if staged:
        commit_rc, _ = _git(["commit", "-m", "fix(superheroes): repair failing checks [showrunner]"], cwd=wt)
        if commit_rc != 0:
            fail["reason"] = "commit failed"
            print(json.dumps(fail)); sys.exit(0)
    else:
        ahead, park_reason = _fixer_committed_ahead(a.work_item, branch, wt)
        if not ahead:
            fail["reason"] = park_reason
            print(json.dumps(fail)); sys.exit(0)
        # the fixer committed its own fix — the local-ahead commit IS the product; push it as-is.
    push_rc, _ = _git(["push", "origin", branch], cwd=wt)
    if push_rc != 0:
        _ok, head, read_back, reason = _replay_push_onto_remote(a.work_item, branch, wt)
        if not _ok:
            fail["reason"] = reason
            fail["head"] = head
            print(json.dumps(fail)); sys.exit(0)
    else:
        head = _local_head(wt)
        read_back = _push_read_back(a.work_item, branch, wt, head)
        # the push WAS accepted; an unconfirmed read-back still parks fail-closed (ok/pushed stay
        # derived from read_back) but the narrative must not claim the push itself failed.
        reason = ("fix pushed and rechecked" if read_back
                  else "push accepted; remote head not yet visible — will reconcile on resume")
    checks = _emit_checks_payload(a.work_item, wt)
    print(json.dumps({"ok": bool(read_back), "head": head, "pushed": bool(read_back),
                      "read_back": bool(read_back), "checks": checks, "reason": reason}))
elif a.step == "ship-readiness":
    wt = a.worktree or os.getcwd()
    base_name = a.base if a.base else "main"
    fence = {"ok": True, "reason": "skipped"}
    reconcile = {"ok": False, "head": None, "reason": "unread"}
    freshness_out = {"decision": "gate"}
    integrated = False
    if a.checks_only:
        checks = _emit_checks_payload(a.work_item, wt)
        print(json.dumps({"ok": True, "fence": fence, "reconcile": {"ok": True, "skipped": True},
                          "freshness": {"decision": "skipped"}, "integrated": False, "checks": checks}))
        sys.exit(0)
    fence = _fence_check(a.work_item, a.generation, _store_root())
    if not fence.get("ok"):
        print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                          "freshness": freshness_out, "integrated": False,
                          "checks": {"error": "CI status could not be read"}}))
        sys.exit(0)
    local = _local_head(wt)
    if not local:
        reconcile = {"ok": False, "head": None, "reason": "local HEAD unreadable — fail closed"}
        print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                          "freshness": freshness_out, "integrated": False,
                          "checks": {"error": "CI status could not be read"}}))
        sys.exit(0)
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""

    def _push():
        rc, _ = _git(["push", "origin", branch], cwd=wt)
        if rc != 0:
            return False
        return _push_read_back(a.work_item, branch, wt, local)

    res = ship_reconcile.reconcile_head(local, _remote_pr_head(a.work_item, branch, wt), branch, _push)
    reconcile = {"ok": bool(res["ok"]), "head": local if res["ok"] else None, "reason": res["reason"]}
    if not reconcile["ok"]:
        print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                          "freshness": freshness_out, "integrated": False,
                          "checks": {"error": "CI status could not be read"}}))
        sys.exit(0)
    for attempt in range(1, 5):
        resolved = base_ref.resolve_configured_base(wt, base_name)
        if resolved is None:
            freshness_out = {"decision": "gate", "reason": base_ref.unresolvable_reason(base_name, wt)}
            print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                              "freshness": freshness_out, "integrated": integrated,
                              "checks": {"error": "CI status could not be read"}}))
            sys.exit(0)
        try:
            rc = subprocess.run(["git", "merge-base", "--is-ancestor", resolved, "HEAD"],
                                capture_output=True, timeout=10, cwd=wt).returncode
        except subprocess.TimeoutExpired:
            rc = 2
        is_anc = True if rc == 0 else (False if rc == 1 else None)
        decision, _reason = freshness.decide(is_anc, attempt)
        freshness_out = {"decision": decision}
        if decision == "up_to_date":
            break
        if decision == "give_up_notify":
            print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                              "freshness": freshness_out, "integrated": integrated,
                              "checks": {"error": "CI status could not be read"}}))
            sys.exit(0)
        if decision != "sync":
            print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                              "freshness": freshness_out, "integrated": integrated,
                              "checks": {"error": "CI status could not be read"}}))
            sys.exit(0)
        fence = _fence_check(a.work_item, a.generation, _store_root())
        if not fence.get("ok"):
            print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                              "freshness": freshness_out, "integrated": integrated,
                              "checks": {"error": "CI status could not be read"}}))
            sys.exit(0)
        resolved = base_ref.resolve_configured_base(wt, base_name)
        _git(["fetch", "--quiet", "origin"], cwd=wt)
        before_head = _local_head(wt)
        rc, _ = _git(["merge", "--no-edit", resolved], cwd=wt)
        if rc != 0:
            _git(["merge", "--abort"], cwd=wt)
            freshness_out = {"decision": "conflict", "reason": "base integration conflicts — aborted"}
            print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                              "freshness": freshness_out, "integrated": integrated,
                              "checks": {"error": "CI status could not be read"}}))
            sys.exit(0)
        after_head = _local_head(wt)
        if after_head and after_head != before_head and branch:
            push_rc, _ = _git(["push", "origin", branch], cwd=wt)
            if push_rc != 0:
                print(json.dumps({"ok": False, "fence": fence, "reconcile": reconcile,
                                  "freshness": {"decision": "sync", "reason": "merged base but push failed"},
                                  "integrated": integrated,
                                  "checks": {"error": "CI status could not be read"}}))
                sys.exit(0)
            integrated = True
    checks = _emit_checks_payload(a.work_item, wt)
    print(json.dumps({"ok": True, "fence": fence, "reconcile": reconcile,
                      "freshness": freshness_out, "integrated": integrated, "checks": checks}))
elif a.step == "revert-draft":
    # FR-4: return the PR to draft on terminal CI failure. Idempotent via the primitive: a no-op
    # when the PR is already draft. Draft-flip is call-site 2 of the generic idempotency guard.
    pr = _resolve_pr_number(a.work_item)
    if not pr:
        print(json.dumps({"ok": False, "reason": "no PR to revert — fail closed"}))
        sys.exit(0)

    def _reader():
        try:
            r = subprocess.run(["gh", "pr", "view", pr, "--json", "isDraft", "--jq", ".isDraft"],
                               capture_output=True, text=True, timeout=30)
        except Exception:
            return (None, "isDraft unreadable")
        if r.returncode != 0:
            return (None, "isDraft unreadable")
        v = r.stdout.strip()
        if v == "true":
            return (True, "already draft")
        if v == "false":
            return (False, "ready")
        return (None, "isDraft ambiguous")

    def _apply():
        try:
            rc = subprocess.run(["gh", "pr", "ready", "--undo", pr], capture_output=True, timeout=60).returncode
        except Exception:
            return (False, "gh pr ready --undo raised")
        return (rc == 0, "reverted to draft")

    res = idempotent_write.idempotent_apply("draft:pr=%s" % pr, _reader, _apply)
    print(json.dumps({"ok": bool(res["ok"]), "reason": res["reason"]}))
elif a.emit_checks:
    # FR-5 stale-pass rejection: only judge checks on the INTEGRATED head.
    checks = _emit_checks_payload(a.work_item, a.worktree)
    print(json.dumps(checks))
else:
    # Real CI read: classify the PR's checks (green / red / none) via ci_status. Fail-CLOSED — any
    # read error returns 'red' (never 'green'), so ship never posts a false "merge-ready: CI green".
    print(json.dumps(_read_ci(a.work_item)))
