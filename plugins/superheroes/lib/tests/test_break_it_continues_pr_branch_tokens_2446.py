"""Explicit references to Git-valid PR branches must require adoption.

Only throwaway repositories are written. GitHub pages and the later worktree
creation seam are replaced; launch preflight and branch detection remain real.
"""
import json
import subprocess
from types import SimpleNamespace

import pytest

from test_launcher import L, _all_checks, _head_sha, _init_repo, _valid_premise
from test_launcher_cloud import _isolated  # noqa: F401 (autouse isolation fixture)


@pytest.mark.parametrize("branch", [
    "feature/fix+followup", "feature/part@2", "feature/next=step",
])
@pytest.mark.parametrize("template", [
    "origin/{branch}", "branch:{branch}", "continue branch {branch}",
])
def test_explicit_git_branch_reference_refuses_before_worktree(
    tmp_path, monkeypatch, branch, template,
):
    # axis: launch_build refuses all three explicit naming forms for a matching
    # Git-valid PR branch containing +, @ or = before worktree creation.
    repo = _init_repo(tmp_path / "repo")
    for args in (
        ("branch", branch),
        ("remote", "add", "origin", "https://github.com/o/r.git"),
    ):
        subprocess.run(
            ["git", "-C", repo, *args],
            check=True, capture_output=True, text=True,
        )
    head = _head_sha(repo)
    surface = template.format(branch=branch)
    answer = SimpleNamespace(
        returncode=0,
        stdout=json.dumps([{
            "number": 7,
            "head": {
                "ref": branch, "sha": head,
                "repo": {"full_name": "o/r"},
            },
        }]),
        stderr="",
    )
    monkeypatch.setattr(
        L, "_gh_open_pulls_page", lambda *args, **kwargs: answer,
    )
    reached_worktree = []

    def stop_at_worktree(repo_root, path, base, env=None):
        reached_worktree.append(path)
        return {"ok": False, "reason": "break-it-worktree-reached", "path": path}

    monkeypatch.setattr(L, "create_build_worktree", stop_at_worktree)
    result = L.launch_build(
        repo, 656, _valid_premise(repo, surfaces=[surface]),
        _all_checks(), str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == L._CONTINUES_PR_WITHOUT_ADOPTION, result
    assert result["continuedPulls"] == [{
        "number": 7, "branch": branch, "head": head, "matchedIn": surface,
    }]
    assert reached_worktree == []
