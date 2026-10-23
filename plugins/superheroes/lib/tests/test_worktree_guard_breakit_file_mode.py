from pathlib import Path
import stat

import worktree_guard as wg
from test_worktree_guard_merge import _git, _merge_repo


def test_unstaged_executable_bit_on_conflicted_file_denies_restore(tmp_path, monkeypatch):
    # _merge_repo engages the guard; calibration discovery is outside this test.
    repo = _merge_repo(tmp_path, monkeypatch)
    _git(repo, "config", "core.filemode", "true")
    target = Path(repo) / "f.txt"
    command = "git restore --theirs f.txt"
    assert wg.classify(command, repo) == ("allow", "")
    original = target.read_bytes()
    assert not target.stat().st_mode & stat.S_IXUSR
    target.chmod(stat.S_IMODE(target.stat().st_mode) | stat.S_IXUSR)
    assert target.read_bytes() == original
    assert target.stat().st_mode & stat.S_IXUSR

    # axis: an executable-bit edit after the merge must deny destructive restore.
    decision, reason = wg.classify(command, repo)
    _git(repo, "restore", "--theirs", "f.txt")
    assert not target.stat().st_mode & stat.S_IXUSR
    assert decision == "deny", reason
