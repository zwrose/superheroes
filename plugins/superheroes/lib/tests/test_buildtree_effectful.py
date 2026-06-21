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


import pytest


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
