"""Plain path surfaces remain exempt when their names contain the word branch.

Only temporary repositories are written. GitHub pages and worktree creation
are replaced; premise validation and branch detection remain real.
"""
import json
import subprocess
from types import SimpleNamespace

import pytest

from test_launcher import L, _all_checks, _head_sha, _init_repo, _valid_premise
from test_launcher_cloud import _isolated  # noqa: F401 (autouse isolation fixture)


@pytest.mark.parametrize("surface", ["branch", "docs/branch", "branch.py"])
def test_plain_path_with_branch_in_its_name_reaches_worktree(
    tmp_path, monkeypatch, surface,
):
    # axis: a bare path matching an open PR branch stays exempt even when
    # the matched name itself contains the word branch.
    repo = _init_repo(tmp_path / "repo")
    subprocess.run(
        ["git", "-C", repo, "remote", "add", "origin", "https://github.com/o/r.git"],
        check=True, capture_output=True, text=True,
    )
    answer = SimpleNamespace(
        returncode=0,
        stdout=json.dumps([{
            "number": 7,
            "head": {
                "ref": surface,
                "sha": _head_sha(repo),
                "repo": {"id": 1, "full_name": "o/r"},
            },
            "base": {"repo": {"id": 1, "full_name": "o/r"}},
        }]),
        stderr="",
    )
    monkeypatch.setattr(L, "_gh_open_pulls_page", lambda *args, **kwargs: answer)
    reached_worktree = []

    def stop_at_worktree(repo_root, path, base, env=None):
        reached_worktree.append(path)
        return {"ok": False, "reason": "break-it-worktree-reached", "path": path}

    monkeypatch.setattr(L, "create_build_worktree", stop_at_worktree)
    result = L.launch_build(
        repo, 656, _valid_premise(repo, surfaces=[surface]),
        _all_checks(), str(tmp_path / "logs"),
    )
    assert len(reached_worktree) == 1, result
    assert result["reason"] == "break-it-worktree-reached", result
