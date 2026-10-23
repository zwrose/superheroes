from pathlib import Path

import pytest
import worktree_guard as wg
from test_worktree_guard_merge import _calibrated, _commit_file, _git, _init_repo


@pytest.mark.parametrize("style", ["diff3", "zdiff3"])
def test_ours_side_literal_base_marker_edit_denies_checkout(tmp_path, monkeypatch, style):
    # Engage the guard explicitly; calibration discovery is outside this test.
    _calibrated(monkeypatch)
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "config", "merge.conflictStyle", style)
    _commit_file(repo, "f.txt", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit_file(repo, "f.txt", "feature\n||||||| original-example\n", "feature")
    _git(repo, "checkout", "-q", "main")
    _commit_file(repo, "f.txt", "main\n", "main")
    _git(repo, "checkout", "-q", "feature")
    merged = _git(repo, "merge", "--no-edit", "main", check=False)
    assert merged.returncode == 1, merged.stdout + merged.stderr

    target = Path(repo) / "f.txt"
    original = target.read_bytes()
    literal = b"||||||| original-example\n"
    assert original.count(literal) == 1
    assert original.index(literal) < original.index(b"=======\n")
    command = "git checkout --theirs f.txt"
    assert wg.classify(command, repo) == ("allow", "")
    target.write_bytes(original.replace(literal, b"||||||| OWNER-ONLY-DRAFT\n"))

    # axis: editing ordinary ours-side content must deny a checkout that destroys it.
    decision, reason = wg.classify(command, repo)
    _git(repo, "checkout", "--theirs", "f.txt")
    assert b"OWNER-ONLY-DRAFT" not in target.read_bytes()
    assert decision == "deny", reason
