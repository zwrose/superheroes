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
