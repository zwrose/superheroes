"""An open PR without a readable branch must refuse before worktree creation.

Only a throwaway repository is written. GitHub page reading and the later
worktree step are replaced; premise validation and continuation detection are real.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from test_launcher import L, _all_checks, _head_sha, _init_repo, _valid_premise
from test_launcher_cloud import _git, _isolated  # noqa: F401 (autouse isolation fixture)


def test_empty_pr_branch_refuses_unread_before_worktree(tmp_path, monkeypatch):
    # axis: an empty PR head.ref is unreadable, so launch refuses row-shape
    # before creating a worktree and preserves existing content and branch heads.
    repo = _init_repo(tmp_path / "repo")
    branch = "work/existing"
    _git(repo, "branch", branch)
    _git(repo, "remote", "add", "origin", "https://github.com/o/r.git")
    head = _head_sha(repo)
    branches_before = _git(repo, "show-ref", "--heads")
    tracked = Path(repo) / "file.txt"
    content_before = tracked.read_bytes()
    answer = SimpleNamespace(
        returncode=0,
        stdout=json.dumps([{
            "number": 7,
            "head": {
                "ref": "",
                "sha": head,
                "repo": {"id": 1, "full_name": "o/r"},
            },
            "base": {"repo": {"id": 1, "full_name": "o/r"}},
        }]),
        stderr="",
    )
    monkeypatch.setattr(L, "_gh_open_pulls_page", lambda *a, **kw: answer)
    reached_worktree = []

    def stop_at_worktree(repo_root, path, base, env=None):
        reached_worktree.append(path)
        return {"ok": False, "reason": "break-it-worktree-reached", "path": path}

    monkeypatch.setattr(L, "create_build_worktree", stop_at_worktree)
    result = L.launch_build(
        repo, 656, _valid_premise(repo, surfaces=["origin/" + branch]),
        _all_checks(), str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == L._CONTINUES_PR_UNREAD, result
    assert result["failedRead"] == "row-shape", result
    assert reached_worktree == []
    assert _head_sha(repo) == head
    assert _git(repo, "show-ref", "--heads") == branches_before
    assert tracked.read_bytes() == content_before
