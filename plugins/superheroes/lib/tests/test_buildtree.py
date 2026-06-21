# plugins/superheroes/lib/tests/test_buildtree.py
import os
import buildtree


def test_managed_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt"))
    assert buildtree.managed_root() == os.path.realpath(str(tmp_path / "wt"))


def test_managed_root_default(monkeypatch):
    monkeypatch.delenv("SUPERHEROES_WORKTREES_ROOT", raising=False)
    assert buildtree.managed_root().endswith("/.superheroes-worktrees")


def test_branch_name():
    assert buildtree.branch_name("wi-abc123", "deadbeefdeadbeef") == \
        "superheroes/wi-abc123-deadbeefdeadbeef"


def test_worktree_path_deterministic_and_namespaced(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt"))
    monkeypatch.setattr(buildtree.control_plane, "checkout_key", lambda cwd: "KEY")
    p = buildtree.worktree_path("/repo", "wi-abc123", "deadbeefdeadbeef")
    assert p == os.path.join(os.path.realpath(str(tmp_path / "wt")),
                             "KEY", "wi-abc123-deadbeefdeadbeef")
    # distinct checkout-key -> distinct path (FR-1 no-collision)
    monkeypatch.setattr(buildtree.control_plane, "checkout_key", lambda cwd: "KEY2")
    assert buildtree.worktree_path("/repo", "wi-abc123", "deadbeefdeadbeef") != p
