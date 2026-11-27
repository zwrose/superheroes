import json

import pytest

from test_issue_contract import NOT_LINKED, _Members, _in_stack, _pr_row, _world
from test_launcher import L, _all_checks, _dependency_premise, _head_sha, _init_repo, _ledger_env, _pr_vet_state_ok


def test_accepted_dependency_joining_a_stack_refuses_before_worktree(tmp_path, monkeypatch):
    # axis: a dependency-only acceptance lapses if the PR joins a native stack before launch at the same head
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    dep = 701
    slug = "acme/widgets"
    head = _head_sha(repo)
    pull = _pr_row(dep, closes=12, head=head)
    blockers = L.issue_contract.read_judged_blockers(
        7, slug, _world(prs=[pull]), premise={"dependency": dep},
        membership_reader=_Members({dep: NOT_LINKED}),
    )
    assert blockers["checked"] is True
    assert blockers["held"] == []
    assert blockers["requiredDependency"] == dep
    assert [(r["pr"], r["head"], r["stack"]) for r in blockers["accepted"]] == [(dep, head, None)]

    membership = _in_stack(900, 1)
    membership["queried"].update(number=dep, headRefOid=head)
    reads = []

    def read_membership(*, pr, repo, **kwargs):
        reads.append((pr, repo))
        return membership

    def read_vet(pr, repo_name, **kwargs):
        assert (pr, repo_name) == (dep, slug)
        return _pr_vet_state_ok(head, pull["body"], pr_number=dep), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("a dependency already in a stack reached worktree creation without a stack premise")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: (slug, None))
    monkeypatch.setattr(L.stack_check, "read_membership", read_membership)
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": json.dumps(blockers["accepted"]),
    }})
    result = L.launch_build(
        repo, 7, _dependency_premise(repo, dep, issue=7, baseCommit=head), checks,
        str(tmp_path / "logs"), pr_vet_reader=read_vet,
    )
    assert reads == [(dep, slug)]
    assert result["ok"] is False, result
