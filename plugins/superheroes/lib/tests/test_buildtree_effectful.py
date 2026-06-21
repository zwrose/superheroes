# plugins/superheroes/lib/tests/test_buildtree_effectful.py
import os
import subprocess
import buildtree


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], check=True,
                   capture_output=True, text=True)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo), "init", "-q")
    _git(str(repo), "config", "user.email", "t@t")
    _git(str(repo), "config", "user.name", "t")
    (repo / "f").write_text("x")
    _git(str(repo), "add", "f")
    _git(str(repo), "commit", "-qm", "init")
    return str(repo)


def test_list_worktrees_parses_and_none_on_failure(tmp_path):
    repo = _repo(tmp_path)
    wt = str(tmp_path / "wt-a")
    _git(repo, "worktree", "add", "-q", "-b", "superheroes/a-h1", wt)
    rows = buildtree.list_worktrees(repo)
    paths = {r["path"]: r for r in rows}
    assert os.path.realpath(wt) in paths
    assert paths[os.path.realpath(wt)]["branch"] == "superheroes/a-h1"
    # a non-repo dir -> None (fail-closed signal)
    assert buildtree.list_worktrees(str(tmp_path / "not-a-repo")) is None


def test_is_dirty_and_leaf_helpers(tmp_path):
    repo = _repo(tmp_path)
    assert buildtree.is_dirty(repo) is False
    (tmp_path / "repo" / "f").write_text("changed")
    assert buildtree.is_dirty(repo) is True
    assert buildtree.is_dirty(str(tmp_path / "gone")) is True          # unreadable -> dirty
    assert buildtree.leaf_empty_or_absent(str(tmp_path / "absent")) is True
    empty = tmp_path / "empty"; empty.mkdir()
    assert buildtree.leaf_empty_or_absent(str(empty)) is True
    assert buildtree.leaf_empty_or_absent(repo) is False              # non-empty


def test_split_leaf_keeps_hyphenated_work_item():
    wi, ch = buildtree.split_leaf("/x/managed-build-worktree-lifecycle-97eb06-deadbeefdeadbeef")
    assert wi == "managed-build-worktree-lifecycle-97eb06"
    assert ch == "deadbeefdeadbeef"


def _setup(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt"))
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "state"))  # isolate control-plane store
    return repo


def test_create_then_reuse_clean(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    r1 = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r1["outcome"] == buildtree.CREATED and os.path.isdir(r1["path"])
    r2 = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r2["outcome"] == buildtree.REUSED and r2["path"] == r1["path"]


def test_dirty_worktree_is_preserved_never_clobbered(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    (open(os.path.join(r["path"], "scratch"), "w")).write("uncommitted")
    r2 = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r2["outcome"] == buildtree.PRESERVE_NOTIFY
    assert os.path.exists(os.path.join(r["path"], "scratch"))     # not clobbered


def test_non_empty_non_worktree_leaf_is_surfaced_not_deleted(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    p = buildtree.worktree_path(repo, "wi-a", "h1")
    os.makedirs(p)
    open(os.path.join(p, "owner-file"), "w").write("precious")
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r["outcome"] == buildtree.PRESERVE_NOTIFY
    assert os.path.exists(os.path.join(p, "owner-file"))          # never raw-deleted


def test_leaf_missing_prunable_is_pruned_and_recreated(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    import shutil
    shutil.rmtree(r["path"])                                       # owner hand-deletes the leaf
    r2 = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r2["outcome"] == buildtree.CREATED and os.path.isdir(r2["path"])
    # the branch survived the prune+recreate
    assert buildtree.branch_exists(repo, buildtree.branch_name("wi-a", "h1"))


def test_create_gate_failclosed_on_add_failure(tmp_path, monkeypatch):
    # `git worktree add` itself fails (e.g. a stale/locked registry entry) -> GATE,
    # never raises, never builds over.
    repo = _setup(tmp_path, monkeypatch)
    real_git = buildtree._git
    monkeypatch.setattr(buildtree, "_git", lambda cwd, *a:
                        (1, "") if a[:2] == ("worktree", "add") else real_git(cwd, *a))
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r["outcome"] == buildtree.GATE_FAILCLOSED


def test_teardown_merged_removes_worktree_and_branch(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    res = buildtree.teardown(repo, r["path"], r["branch"], buildtree.REMOVE_AND_DELETE)
    assert res["removed"] and res["branch_deleted"] and not res["incomplete"]
    assert not os.path.isdir(r["path"])
    assert not buildtree.branch_exists(repo, r["branch"])


def test_teardown_closed_keeps_branch(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    res = buildtree.teardown(repo, r["path"], r["branch"], buildtree.REMOVE_KEEP_BRANCH)
    assert res["removed"] and not res["branch_deleted"]
    assert not os.path.isdir(r["path"])
    assert buildtree.branch_exists(repo, r["branch"])             # FR-7 branch preserved


def test_teardown_non_remove_decision_is_noop(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    res = buildtree.teardown(repo, r["path"], r["branch"], buildtree.PRESERVE_NOTIFY)
    assert res["removed"] is False and os.path.isdir(r["path"])


def test_teardown_incomplete_on_branch_delete_failure(tmp_path, monkeypatch):
    # UFR-5: worktree removed but `git branch -D` fails -> incomplete (the dangling
    # branch must be reported, never silently dropped).
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    real_git = buildtree._git
    monkeypatch.setattr(buildtree, "_git", lambda cwd, *a:
                        (1, "") if a[:2] == ("branch", "-D") else real_git(cwd, *a))
    res = buildtree.teardown(repo, r["path"], r["branch"], buildtree.REMOVE_AND_DELETE)
    assert res["removed"] and not res["branch_deleted"] and res["incomplete"]
    assert not os.path.isdir(r["path"])                          # worktree-before-branch


def test_plan_sweep_lists_terminal_excludes_active_and_fail_closes(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")     # merged -> candidate
    b = buildtree.reclaim_or_create(repo, "wi-b", "h2")     # active -> excluded by path
    pr_info = {a["branch"]: {"pr_state": "merged", "pr_head_oid": buildtree.rev_parse(repo, a["branch"])},
               b["branch"]: {"pr_state": "merged", "pr_head_oid": buildtree.rev_parse(repo, b["branch"])}}
    # structural exclusion by active_path (slug intentionally non-matching to isolate it)
    cands = buildtree.plan_sweep(repo, pr_info, active_work_item="none", active_path=b["path"])
    paths = {c["path"] for c in cands}
    assert a["path"] in paths and b["path"] not in paths    # active excluded (structural)
    # fail-closed: an unreadable worktree list -> no candidates
    monkeypatch.setattr(buildtree, "list_worktrees", lambda cwd: None)
    assert buildtree.plan_sweep(repo, pr_info, active_work_item="wi-b") == []


def test_reap_one_revalidates_dirty_at_reap_time(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    head = buildtree.rev_parse(repo, a["branch"])
    open(os.path.join(a["path"], "scratch"), "w").write("became dirty after listing")
    out = buildtree.reap_one(repo, a["path"], a["branch"], "merged", head)
    assert out["decision"] == buildtree.PRESERVE_NOTIFY     # FR-11: re-validated, not reaped
    assert os.path.isdir(a["path"])                          # preserved


def test_reap_one_clears_record_on_full_reap(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    head = buildtree.rev_parse(repo, a["branch"])
    out = buildtree.reap_one(repo, a["path"], a["branch"], "merged", head)
    assert out["decision"] == buildtree.REMOVE_AND_DELETE
    rec = buildtree.record_read(buildtree.record_path(repo))
    assert all(e["path"] != a["path"] for e in rec)          # record cleared


def test_reap_one_retains_record_on_incomplete_teardown(tmp_path, monkeypatch):
    # UFR-5: a partial teardown (branch delete fails) must KEEP the entry on the
    # record (never silently orphan the dangling branch).
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    head = buildtree.rev_parse(repo, a["branch"])
    real_git = buildtree._git
    monkeypatch.setattr(buildtree, "_git", lambda cwd, *ar:
                        (1, "") if ar[:2] == ("branch", "-D") else real_git(cwd, *ar))
    out = buildtree.reap_one(repo, a["path"], a["branch"], "merged", head)
    assert out["result"]["incomplete"] is True
    rec = buildtree.record_read(buildtree.record_path(repo))
    assert any(e["path"] == a["path"] for e in rec)          # retained, not orphaned


def test_reap_one_committed_ahead_keeps_branch(tmp_path, monkeypatch):
    # UFR-6 end-to-end on the merged tier: local tip ahead of the merged PR head ->
    # remove the worktree but PRESERVE the branch.
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    merged_head = buildtree.rev_parse(repo, a["branch"])
    open(os.path.join(a["path"], "ahead"), "w").write("local-only work")
    _git(a["path"], "add", "ahead")
    _git(a["path"], "commit", "-qm", "ahead")                 # local tip now != merged_head
    out = buildtree.reap_one(repo, a["path"], a["branch"], "merged", merged_head)
    assert out["decision"] == buildtree.REMOVE_KEEP_BRANCH
    assert buildtree.branch_exists(repo, a["branch"])        # branch preserved (UFR-6)


def test_plan_sweep_excludes_open_and_unknown(tmp_path, monkeypatch):
    # UFR-3 (open) / UFR-2 (unknown) worktrees are never reap candidates.
    repo = _setup(tmp_path, monkeypatch)
    o = buildtree.reclaim_or_create(repo, "wi-open", "h1")
    u = buildtree.reclaim_or_create(repo, "wi-unk", "h2")
    pr_info = {o["branch"]: {"pr_state": "open", "pr_head_oid": buildtree.rev_parse(repo, o["branch"])},
               u["branch"]: {"pr_state": "unknown", "pr_head_oid": None}}
    cands = buildtree.plan_sweep(repo, pr_info, active_work_item="none")
    assert cands == []


def test_teardown_incomplete_when_worktree_remove_fails(tmp_path, monkeypatch):
    # UFR-5: `git worktree remove` itself fails and the leaf is still present -> incomplete
    # (removed=False); the dangling worktree must be reported, never silently dropped.
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    real_git = buildtree._git
    monkeypatch.setattr(buildtree, "_git", lambda cwd, *a:
                        (1, "") if a[:1] == ("worktree",) else real_git(cwd, *a))
    res = buildtree.teardown(repo, r["path"], r["branch"], buildtree.REMOVE_AND_DELETE)
    assert res["removed"] is False and res["incomplete"] is True and res["ok"] is False
    assert os.path.isdir(r["path"])          # preserved, not silently dropped


def test_plan_sweep_skips_branchless_worktree(tmp_path, monkeypatch):
    # A managed-root worktree with no branch (e.g. detached HEAD) is skipped by the
    # `if not branch: continue` guard, never reaching the reap decision. The record is
    # cleared so the candidate's branch comes ONLY from the patched branch-less disk
    # listing (plan_reconcile would otherwise carry the recorded real branch); pr_info
    # keyed by None as merged means that WITHOUT the guard the worktree would become a
    # REMOVE_KEEP_BRANCH candidate, so an empty result proves the guard fired.
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    buildtree.record_write(buildtree.record_path(repo), [])
    real_list = buildtree.list_worktrees
    def fake_list(cwd):
        rows = real_list(cwd)
        for row in rows:
            if row["path"] == a["path"]:
                row["branch"] = None
        return rows
    monkeypatch.setattr(buildtree, "list_worktrees", fake_list)
    pr_info = {None: {"pr_state": "merged", "pr_head_oid": "deadbeef"}}
    assert buildtree.plan_sweep(repo, pr_info, active_work_item="none") == []


def test_reclaim_create_survives_record_write_failure(tmp_path, monkeypatch):
    # premortem-001: a failed record write (OSError) must NOT break create's never-raises
    # contract -> still CREATED; the worktree is git-registered and the record self-heals.
    repo = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(buildtree, "record_add",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r["outcome"] == buildtree.CREATED and os.path.isdir(r["path"])


def test_reap_one_survives_record_remove_failure(tmp_path, monkeypatch):
    # premortem-002: a failed record cleanup (OSError) after a successful teardown must NOT
    # raise -> reap_one still returns the decision/result dict.
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    head = buildtree.rev_parse(repo, a["branch"])
    monkeypatch.setattr(buildtree, "record_remove",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    out = buildtree.reap_one(repo, a["path"], a["branch"], "merged", head)
    assert out["decision"] == buildtree.REMOVE_AND_DELETE
    assert out["result"]["removed"] and not out["result"]["incomplete"]


def test_plan_sweep_excludes_active_by_slug(tmp_path, monkeypatch):
    # test-002: reach the slug-exclusion clause (wi == active_work_item) with real data.
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    pr_info = {a["branch"]: {"pr_state": "merged",
                            "pr_head_oid": buildtree.rev_parse(repo, a["branch"])}}
    assert buildtree.plan_sweep(repo, pr_info, active_work_item="wi-a") == []


def test_split_leaf_no_hyphen():
    # test-003: the no-hyphen branch returns (leaf, "").
    assert buildtree.split_leaf("/x/plainleaf") == ("plainleaf", "")


def test_plan_sweep_failcloses_on_forward_version_record(tmp_path, monkeypatch):
    # test-001: a forward-version worktrees.json makes record_read raise RecordSchemaError;
    # plan_sweep must fail closed with [] BEFORE building candidates — even when pr_info would
    # otherwise make the worktree a terminal (merged) reap candidate.
    repo = _setup(tmp_path, monkeypatch)
    a = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    pr_info = {a["branch"]: {"pr_state": "merged",
                            "pr_head_oid": buildtree.rev_parse(repo, a["branch"])}}
    rec_file = buildtree.record_path(repo)
    os.makedirs(os.path.dirname(rec_file), exist_ok=True)
    with open(rec_file, "w") as fh:
        fh.write('{"schemaVersion": 999, "worktrees": []}')
    assert buildtree.plan_sweep(repo, pr_info, active_work_item="none") == []


def test_create_makedirs_failure_gate_failclosed(tmp_path, monkeypatch):
    # test-002: an OSError creating the leaf's parent dir -> GATE_FAILCLOSED, never raises.
    repo = _setup(tmp_path, monkeypatch)
    def _boom(*a, **k):
        raise OSError("no mkdir")
    monkeypatch.setattr(buildtree.os, "makedirs", _boom)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    assert r["outcome"] == buildtree.GATE_FAILCLOSED


def test_teardown_remove_and_delete_with_none_branch_is_clean(tmp_path, monkeypatch):
    # code-001: teardown must never raise on a branch-less worktree even under
    # REMOVE_AND_DELETE — no branch to delete -> clean removal, not a TypeError.
    repo = _setup(tmp_path, monkeypatch)
    r = buildtree.reclaim_or_create(repo, "wi-a", "h1")
    res = buildtree.teardown(repo, r["path"], None, buildtree.REMOVE_AND_DELETE)
    assert res["removed"] is True and res["branch_deleted"] is False and res["incomplete"] is False
    assert not os.path.isdir(r["path"])
