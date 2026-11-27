import json

import pytest

import issue_contract
from test_issue_contract import NOT_LINKED, _Members, _pr_row, _world
from test_launcher import (
    L,
    _all_checks,
    _dependency_premise,
    _head_sha,
    _init_repo,
    _ledger_env,
    _pr_vet_state_ok,
)


def test_accepted_dependency_that_advances_and_merges_cannot_launch_on_old_base(tmp_path, monkeypatch):
    # axis: a merge after acceptance cannot authorize worktree creation at the outdated preflight base
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    dependency = 701
    old_head = _head_sha(repo)
    new_head = ("1" if old_head[0] == "0" else "0") + old_head[1:]
    listed = _pr_row(dependency, closes=12, head=old_head)
    blockers = issue_contract.read_judged_blockers(
        7, "acme/widgets", _world(prs=[listed]),
        premise={"dependency": dependency},
        membership_reader=_Members({dependency: NOT_LINKED}),
    )
    assert blockers["held"] == []
    assert [(row["pr"], row["head"]) for row in blockers["accepted"]] == [(dependency, old_head)]
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": json.dumps(blockers["accepted"]),
    }})
    reads = []

    def read_dependency(pr, slug, **kwargs):
        reads.append((pr, slug))
        return _pr_vet_state_ok(new_head, listed["body"], state="MERGED", pr_number=pr), None

    def unexpected_worktree(repo_root, path, base_commit, **kwargs):
        pytest.fail(f"launch reached worktree creation at {base_commit} after the dependency advanced and merged")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    result = L.launch_build(
        repo, 7, _dependency_premise(repo, dependency, issue=7, baseCommit=old_head),
        checks, str(tmp_path / "logs"), pr_vet_reader=read_dependency,
    )
    assert reads == [(dependency, "acme/widgets")]
    assert result["ok"] is False, result
