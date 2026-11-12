"""File transports in launcher.py must not require a GitHub PR read."""
import subprocess

import pytest

from test_launcher import L, _all_checks, _init_repo, _valid_premise
from test_launcher_cloud import _isolated  # noqa: F401 (autouse isolation fixture)


@pytest.mark.parametrize("host", ["github.com", "www.github.com", "ssh.github.com"])
def test_file_origin_skips_github_even_with_a_github_authority(
    tmp_path, monkeypatch, host,
):
    # axis: file:// origins skip the GitHub reader regardless of their authority
    # and reach the local worktree boundary without needing GitHub authentication.
    repo = _init_repo(tmp_path / "repo")
    subprocess.run(
        ["git", "-C", repo, "remote", "add", "origin",
         "file://%s/o/r.git" % host],
        check=True, capture_output=True, text=True,
    )
    reads = []

    def unavailable_reader(repo_root, owner, repo_name, env):
        reads.append((owner, repo_name))
        return [], "gh-unrunnable"

    # The owned reader is pinned unavailable; live GitHub behavior is unobserved.
    # This test requires file origins never to reach that boundary.
    monkeypatch.setattr(L, "_open_pulls_fn", unavailable_reader)
    worktrees = []

    def stop_at_worktree(repo_root, path, base, env=None):
        worktrees.append(path)
        return {"ok": False, "reason": "break-it-worktree-reached", "path": path}

    monkeypatch.setattr(L, "create_build_worktree", stop_at_worktree)

    def unexpected_spawn(*args, **kwargs):
        pytest.fail("the worktree boundary must stop this probe before spawning")

    result = L.launch_build(
        repo, 656, _valid_premise(repo, surfaces=["docs"]),
        _all_checks(), str(tmp_path / "logs"), spawn_fn=unexpected_spawn,
    )
    assert reads == [], result
    assert len(worktrees) == 1, result
    assert result["ok"] is False
    assert result["reason"] == "break-it-worktree-reached", result
