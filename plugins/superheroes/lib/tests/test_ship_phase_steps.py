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
