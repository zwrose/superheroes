# plugins/superheroes/lib/tests/test_ship_phase_steps.py
import json, os, subprocess, sys
LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(step, *extra, cwd=None):
    cmd = [sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", step,
           "--work-item", "wi", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or LIB, timeout=30)
    return r


def test_freshness_accepts_attempt_and_gives_up_past_cap(tmp_path):
    # A behind branch on attempt 4 (> DEFAULT_MAX_SYNCS=3) must return give_up_notify, proving
    # --attempt is threaded into freshness.decide (default 1 keeps current behavior).
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a").write_text("1")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "a").write_text("2")               # main advances; feat is now behind
    subprocess.run(["git", "commit", "-qam", "advance"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    r = _run("freshness", "--base", "main", "--attempt", "4", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["decision"] == "give_up_notify"


def test_reconcile_head_no_pr_fails_closed(tmp_path, monkeypatch):
    # Run from a NON-git dir with an isolated store → local HEAD unreadable → fail closed (ok False),
    # deterministically (never claim ready; never depend on the ambient repo's branch/gh PR state).
    # (The in-sync no-op and local-ahead apply WIRING is covered with teeth by
    #  test_reconcile_head_helper_paths below, which drives the pure ship_reconcile.reconcile_head.)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    r = _run("reconcile-head", cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "ok" in out and out["ok"] is False
    assert out["reason"]


def test_reconcile_head_helper_paths():
    # Teeth for the reconcile-head BRANCH wiring (UFR-6 call-site 1): drive the pure decider with an
    # injected push_fn + remote, covering in-sync no-op, local-ahead apply-once, unreadable fail-closed,
    # and no-branch. The gh/git IO stays in the leaf; this is exactly the wiring the branch delegates to.
    sys.path.insert(0, LIB)
    import ship_reconcile
    pushed = []
    r1 = ship_reconcile.reconcile_head("abc", "abc", "feat", lambda: pushed.append(1) or True)
    assert r1["already"] is True and r1["ok"] is True and pushed == []            # in sync -> no push
    r2 = ship_reconcile.reconcile_head("abc", "old", "feat", lambda: (pushed.append(1), True)[1])
    assert r2["applied"] is True and r2["ok"] is True and pushed == [1]            # ahead -> push once
    r3 = ship_reconcile.reconcile_head("abc", None, "feat", lambda: pushed.append(1) or True)
    assert r3["ok"] is False and pushed == [1]                                     # unreadable -> fail closed, no push
    r4 = ship_reconcile.reconcile_head("abc", "old", "", lambda: True)
    assert r4["ok"] is False                                                       # no branch -> cannot push
    assert pushed == [1]


def _init_repo(tmp_path):
    repo = tmp_path / "r"; repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def test_freshen_conflict_aborts_head_unchanged(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "f").write_text("main-change\n")                       # main edits line 1
    subprocess.run(["git", "commit", "-qam", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    (repo / "f").write_text("feat-change\n")                       # feat edits the SAME line -> conflict
    subprocess.run(["git", "commit", "-qam", "feat"], cwd=repo, check=True)
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    r = _run("freshen", "--base", "main", "--worktree", str(repo), cwd=repo)
    out = json.loads(r.stdout)
    assert out["conflict"] is True
    assert out["ok"] is False
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert before == after                                         # UFR-1(a): aborted -> head unchanged
    # the tree is clean after abort (no conflict markers left behind)
    st = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert st.strip() == ""


def test_freshen_clean_automerge_commits(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "g").write_text("new-on-main\n")                       # main adds a DIFFERENT file -> auto-merges
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    r = _run("freshen", "--base", "main", "--worktree", str(repo), cwd=repo)
    out = json.loads(r.stdout)
    assert out["conflict"] is False
    after = out["head"]
    assert after and after != before                              # branch advanced to contain base
    assert (repo / "g").exists()                                  # base change integrated


def test_freshness_reads_the_worktree_not_cwd(tmp_path):
    # CRITICAL (the catch-up loop must converge): --step freshness must judge the BUILD WORKTREE's
    # branch HEAD, not the process cwd. Run from a NEUTRAL cwd (LIB) with --worktree pointed at a
    # behind-base repo and assert it sees 'sync' (behind) — a cwd-rooted read would see LIB and mis-judge.
    repo = tmp_path / "r"; repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a").write_text("1")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "a").write_text("2")
    subprocess.run(["git", "commit", "-qam", "advance"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    r = _run("freshness", "--base", "main", "--worktree", str(repo), "--attempt", "1", cwd=LIB)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["decision"] == "sync"   # behind base, attempt 1 -> sync (not gate/up_to_date)


def test_ci_decide_respects_cap_after_replayed_rounds(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    import importlib
    sys.path.insert(0, LIB)
    cp = importlib.import_module("control_plane")
    jr = importlib.import_module("journal")
    paths = cp.paths(str(tmp_path), "wi")
    # seed 4 prior ci_fix_attempt rounds -> the next decide is round 5 = the cap -> revert_and_gate.
    for i in range(1, 5):
        jr.append(paths["events"], "ci_fix_attempt", payload={"round": i, "failing": ["x"]}, root=str(tmp_path))
    r = _run("ci-decide", "--failing", json.dumps(["x"]), cwd=str(tmp_path))
    out = json.loads(r.stdout)
    assert out["action"] == "revert_and_gate"
    assert out["round"] == 5


def test_ci_decide_first_round_fixes(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    r = _run("ci-decide", "--failing", json.dumps(["build"]), cwd=str(tmp_path))
    out = json.loads(r.stdout)
    assert out["action"] == "fix"
    assert out["round"] == 1


def test_ci_record_appends_round(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    import importlib
    sys.path.insert(0, LIB)
    cp = importlib.import_module("control_plane"); jr = importlib.import_module("journal")
    paths = cp.paths(str(tmp_path), "wi")
    r = _run("ci-record", "--round", "1", "--failing", json.dumps(["build"]), cwd=str(tmp_path))
    assert json.loads(r.stdout)["ok"] is True
    rounds, hist = jr.ci_attempts(paths["events"])
    assert rounds == 1 and hist == [["build"]]


def _seed_branch_checkpoint(store_root, worktree, work_item, branch):
    """Seed a checkpoint with a branch name so fix-push can reach past the no-branch guard."""
    import importlib
    sys.path.insert(0, LIB)
    cp_mod = importlib.import_module("control_plane"); ckpt = importlib.import_module("checkpoint")
    old_store = os.environ.get("SUPERHEROES_STORE_ROOT")
    os.environ["SUPERHEROES_STORE_ROOT"] = store_root
    try:
        paths = cp_mod.paths(str(worktree), work_item)
        ckpt.write(paths["checkpoint"], ckpt.new(work_item, branch, lock_generation=1))
    finally:
        if old_store is None:
            os.environ.pop("SUPERHEROES_STORE_ROOT", None)
        else:
            os.environ["SUPERHEROES_STORE_ROOT"] = old_store


def test_fix_push_dirty_conflict_marker_parks_no_push(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    # seed a branch so the no-branch guard passes; the conflict marker must be the thing that parks
    store_root = str(tmp_path / "store")
    _seed_branch_checkpoint(store_root, repo, "wi", "feat")
    # leave a conflict marker in the worktree (a crashed fixer's residue)
    (repo / "f").write_text("<<<<<<< HEAD\na\n=======\nb\n>>>>>>> x\n")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", "fix-push",
                        "--work-item", "wi", "--worktree", str(repo)],
                       capture_output=True, text=True, cwd=str(repo), env=monkey, timeout=30)
    out = json.loads(r.stdout)
    assert out["pushed"] is False
    assert out["ok"] is False
    assert "conflict" in out["reason"] or "marker" in out["reason"]


def test_fix_push_no_change_parks(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    # seed a branch so the no-branch guard passes; the clean tree must be the thing that parks
    store_root = str(tmp_path / "store")
    _seed_branch_checkpoint(store_root, repo, "wi", "feat")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", "fix-push",
                        "--work-item", "wi", "--worktree", str(repo)],
                       capture_output=True, text=True, cwd=str(repo), env=monkey, timeout=30)
    out = json.loads(r.stdout)
    assert out["pushed"] is False
    assert out["ok"] is False
    assert "no change" in out["reason"] or "nothing" in out["reason"]


def test_revert_draft_no_pr_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))  # isolated store; non-git cwd
    r = _run("revert-draft", cwd=str(tmp_path))                   # no checkpoint PR, no gh PR -> fail closed
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["reason"]


def test_pr_entry_and_ship_phase_use_idempotent_primitive():
    pe = open(os.path.join(LIB, "pr_entry.py")).read()
    sp = open(os.path.join(LIB, "ship_phase.py")).read()
    sr = open(os.path.join(LIB, "ship_reconcile.py")).read()
    assert "idempotent_write" in pe and "ready:pr=" in pe        # call-site 3: ready-flip
    assert "idempotent_write" in sp and "draft:pr=" in sp        # call-site 2: draft-flip
    assert "idempotent_write" in sr and "head=" in sr            # call-site 1: push-reconcile (pure decider)
    assert "ship_reconcile.reconcile_head" in sp                 # ship_phase delegates the reconcile wiring


def test_ship_phase_pushes_are_non_force_to_the_branch():
    # FR-9: every push the back-half makes is an ordinary non-force push to the work-item's OWN branch
    # — never a force-push, never a push to a literal default branch. (FR-8's never-merge twin is the
    # guard smoke; this is FR-9's structural assertion.)
    import re
    sp = open(os.path.join(LIB, "ship_phase.py")).read()
    pushes = re.findall(r'\["push"[^\]]*\]', sp)
    assert pushes, "expected git push calls in ship_phase.py"
    for p in pushes:
        assert "force" not in p.lower(), "force-push found: %s" % p
        assert '"-f"' not in p and '"+' not in p, "force/forced-refspec push found: %s" % p
        assert '"origin"' in p, "push not to origin: %s" % p
    # never a push to a hardcoded default branch (pushes target the checkpoint `branch` variable)
    assert '"push", "origin", "main"' not in sp and '"push", "origin", "master"' not in sp


def test_emit_checks_is_stale():
    # FR-5: a confirmed head MISMATCH is stale (rollup is for an earlier commit); a match is judgeable;
    # an unreadable head is NOT 'stale' here (the leaf's own fail-closed paths handle those).
    sys.path.insert(0, LIB)
    import ship_ci
    assert ship_ci.is_stale("abc", "old") is True       # mismatch -> stale (reject the rollup)
    assert ship_ci.is_stale("abc", "abc") is False      # match -> judge the rollup
    assert ship_ci.is_stale("abc", None) is False       # unreadable remote -> not stale
    assert ship_ci.is_stale(None, "abc") is False       # unreadable local -> not stale


def test_fix_push_nff_two_ahead_replays_both_commits(tmp_path):
    # NFF recovery: local has 2 unpushed commits and the remote branch advanced; the push is rejected,
    # then fetch + rebase FETCH_HEAD must replay BOTH local commits onto the advanced remote (never drop one).
    import importlib
    origin = tmp_path / "origin.git"; subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    def g(*a, cwd=work): subprocess.run(["git", *a], cwd=cwd, check=True)
    g("config", "user.email", "t@t"); g("config", "user.name", "t")
    (work / "f").write_text("base\n"); g("add", "-A"); g("commit", "-qm", "base")
    g("branch", "-M", "feat"); g("push", "-q", "origin", "feat")
    # a second clone advances origin/feat (the "remote advanced" case)
    other = tmp_path / "other"; subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True)
    subprocess.run(["git", "config", "user.email", "o@o"], cwd=other, check=True); subprocess.run(["git", "config", "user.name", "o"], cwd=other, check=True)
    # bare repo HEAD may not auto-track feat; check it out explicitly so the commit lands on the right branch
    subprocess.run(["git", "checkout", "-q", "-b", "feat", "origin/feat"], cwd=other, check=True)
    (other / "remote_file").write_text("from remote\n")
    subprocess.run(["git", "add", "-A"], cwd=other, check=True); subprocess.run(["git", "commit", "-qm", "remote advance"], cwd=other, check=True)
    subprocess.run(["git", "push", "-q", "origin", "feat"], cwd=other, check=True)
    # local makes a freshen-style commit + the fixer's dirty change (2 commits' worth: one committed, one staged-by-fix-push)
    (work / "freshen_file").write_text("freshen\n"); g("add", "-A"); g("commit", "-qm", "freshen merge (unpushed)")
    (work / "fix_file").write_text("the fix\n")   # the fixer's change, left dirty for fix-push to commit
    # seed a checkpoint with branch=feat in an isolated store, then run fix-push from the work clone
    store_root = str(tmp_path / "store")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    sys.path.insert(0, LIB)
    cp_mod = importlib.import_module("control_plane"); ckpt = importlib.import_module("checkpoint")
    # seed the checkpoint using the same isolated store the subprocess will use
    old_store = os.environ.get("SUPERHEROES_STORE_ROOT")
    os.environ["SUPERHEROES_STORE_ROOT"] = store_root
    try:
        paths = cp_mod.paths(str(work), "wi")
        ckpt.write(paths["checkpoint"], ckpt.new("wi", "feat", lock_generation=1))
    finally:
        if old_store is None:
            os.environ.pop("SUPERHEROES_STORE_ROOT", None)
        else:
            os.environ["SUPERHEROES_STORE_ROOT"] = old_store
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", "fix-push",
                "--work-item", "wi", "--worktree", str(work)],
               capture_output=True, text=True, cwd=str(work), env=monkey, timeout=60)
    out = json.loads(r.stdout)
    assert out["ok"] is True and out["pushed"] is True, r.stdout + r.stderr
    # BOTH local-ahead commits (freshen + fix) AND the remote advance are now on origin/feat — none dropped
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=work, check=True)
    log = subprocess.run(["git", "log", "--format=%s", "origin/feat"], cwd=work, capture_output=True, text=True).stdout
    assert "freshen merge (unpushed)" in log and "remote advance" in log, log   # neither dropped


def _origin_and_work(tmp_path):
    """Bare origin + a work clone with feat pushed — the committed-fixer scenarios' shared setup."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=work, check=True)
    (work / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=work, check=True)
    subprocess.run(["git", "branch", "-M", "feat"], cwd=work, check=True)
    subprocess.run(["git", "push", "-q", "origin", "feat"], cwd=work, check=True)
    return origin, work


def test_fix_push_fixer_committed_own_fix_pushes(tmp_path):
    # Run-31 park: the fixer COMMITTED its fix itself (clean tree, local one ahead of the remote
    # PR head). fix-push must recognize the local-ahead commit as the fixer's product and push it
    # — not park with "nothing the fixer produced" while the fix sits unpushed.
    _origin, work = _origin_and_work(tmp_path)
    (work / "fix_file").write_text("the fix\n")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "fixer's own commit"], cwd=work, check=True)
    store_root = str(tmp_path / "store")
    _seed_branch_checkpoint(store_root, work, "wi", "feat")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", "fix-push",
                        "--work-item", "wi", "--worktree", str(work)],
                       capture_output=True, text=True, cwd=str(work), env=monkey, timeout=60)
    out = json.loads(r.stdout)
    assert out["ok"] is True and out["pushed"] is True and out["read_back"] is True, r.stdout + r.stderr
    log = subprocess.run(["git", "log", "--format=%s", "origin/feat"], cwd=work,
                         capture_output=True, text=True).stdout
    assert "fixer's own commit" in log, log


def test_push_ci_fix_recheck_fixer_committed_own_fix_pushes(tmp_path):
    # The same committed-fixer shape through the step the bundle actually calls.
    _origin, work = _origin_and_work(tmp_path)
    (work / "fix_file").write_text("the fix\n")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "fixer's own commit"], cwd=work, check=True)
    store_root = str(tmp_path / "store")
    _seed_branch_checkpoint(store_root, work, "wi", "feat")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"),
                        "--step", "push-ci-fix-recheck", "--work-item", "wi", "--worktree", str(work)],
                       capture_output=True, text=True, cwd=str(work), env=monkey, timeout=60)
    out = json.loads(r.stdout)
    assert out["pushed"] is True and out["read_back"] is True, r.stdout + r.stderr
    log = subprocess.run(["git", "log", "--format=%s", "origin/feat"], cwd=work,
                         capture_output=True, text=True).stdout
    assert "fixer's own commit" in log, log


def test_fix_push_clean_tree_in_sync_still_parks(tmp_path):
    # A clean tree with local == remote is a TRUE no-op (the fixer really produced nothing):
    # the committed-fixer tolerance must not turn it into a push or a false ok.
    _origin, work = _origin_and_work(tmp_path)
    store_root = str(tmp_path / "store")
    _seed_branch_checkpoint(store_root, work, "wi", "feat")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", "fix-push",
                        "--work-item", "wi", "--worktree", str(work)],
                       capture_output=True, text=True, cwd=str(work), env=monkey, timeout=60)
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["pushed"] is False
    assert "no change" in out["reason"] or "nothing" in out["reason"]


def test_fix_push_clean_tree_diverged_remote_still_parks(tmp_path):
    # Clean tree but the histories DIVERGED (remote advanced past the shared base while local
    # carries its own commit): not the committed-fixer shape — park fail-closed, no guess-push.
    _origin, work = _origin_and_work(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(_origin), str(other)], check=True)
    subprocess.run(["git", "config", "user.email", "o@o"], cwd=other, check=True)
    subprocess.run(["git", "config", "user.name", "o"], cwd=other, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feat", "origin/feat"], cwd=other, check=True)
    (other / "remote_file").write_text("from remote\n")
    subprocess.run(["git", "add", "-A"], cwd=other, check=True)
    subprocess.run(["git", "commit", "-qm", "remote advance"], cwd=other, check=True)
    subprocess.run(["git", "push", "-q", "origin", "feat"], cwd=other, check=True)
    (work / "local_file").write_text("local\n")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "local commit"], cwd=work, check=True)
    store_root = str(tmp_path / "store")
    _seed_branch_checkpoint(store_root, work, "wi", "feat")
    monkey = {**os.environ, "SUPERHEROES_STORE_ROOT": store_root}
    r = subprocess.run([sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", "fix-push",
                        "--work-item", "wi", "--worktree", str(work)],
                       capture_output=True, text=True, cwd=str(work), env=monkey, timeout=60)
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["pushed"] is False, r.stdout
    assert "no change" in out["reason"] or "nothing" in out["reason"]


def test_post_push_read_back_checks_branch_ref_before_pr_api():
    # Run-32 false park: gh's PR head can lag a just-accepted push by seconds, so a SUCCESSFUL
    # push read back as failed. Every post-push confirm must go through _push_read_back, which
    # consults the branch ref (ls-remote — atomic with the push) before the PR API.
    sp = open(os.path.join(LIB, "ship_phase.py")).read()
    body = sp.split("def _push_read_back", 1)[1].split("\ndef ", 1)[0]
    assert "ls-remote" in body and "_remote_pr_head" in body
    assert body.index("ls-remote") < body.index("_remote_pr_head")
    # no post-push confirm bypasses the helper with a bare PR-API comparison
    after_pushes = [chunk for chunk in sp.split('["push", "origin", branch]')[1:]]
    for chunk in after_pushes:
        head_cmp = chunk.find("_remote_pr_head(")
        helper = chunk.find("_push_read_back(")
        if head_cmp != -1 and (helper == -1 or head_cmp < helper):
            # a raw PR-API read-back before the helper would reintroduce the lag race
            raise AssertionError("post-push read-back not routed through _push_read_back")
