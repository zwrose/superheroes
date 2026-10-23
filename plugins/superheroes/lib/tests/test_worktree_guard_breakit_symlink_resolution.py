import os
from pathlib import Path

import worktree_guard as wg
from test_worktree_guard_merge import _calibrated, _git, _init_repo


def test_regular_file_resolution_of_symlink_conflict_denies_restore(tmp_path, monkeypatch):
    # Engage the guard explicitly; calibration discovery is outside this test.
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    target = Path(repo) / "f.link"

    def commit_link(destination, message):
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(destination)
        _git(repo, "add", "f.link")
        _git(repo, "commit", "-q", "-m", message)

    commit_link("base-target", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    commit_link("feature-target", "feature")
    _git(repo, "checkout", "-q", "main")
    commit_link("main-target", "main")
    _git(repo, "checkout", "-q", "feature")
    merged = _git(repo, "merge", "--no-edit", "main", check=False)
    assert merged.returncode == 1, merged.stdout + merged.stderr
    assert target.is_symlink()
    assert os.readlink(target) == "feature-target"

    target.unlink()
    target.write_bytes(b"feature-target")
    assert target.is_file() and not target.is_symlink()

    # axis: a post-merge symlink-to-regular-file resolution must deny destructive restore.
    command = "git restore --theirs f.link"
    decision, reason = wg.classify(command, repo)
    _git(repo, "restore", "--theirs", "f.link")
    assert target.is_symlink()
    assert os.readlink(target) == "main-target"
    assert decision == "deny", reason
