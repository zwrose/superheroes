import json

import pytest

from test_issue_contract import _Members, _head, _in_stack, _pr_row, _world
from test_launcher import (
    L,
    _all_checks,
    _head_sha,
    _init_repo,
    _ledger_env,
    _membership_ok,
    _pr_lookup_ok,
    _pr_vet_state_ok,
    _stack_premise,
)


def test_acceptance_for_another_stack_refuses_before_worktree_creation(tmp_path, monkeypatch):
    # axis: an accepted blocker must belong to the stack in the launch premise when the worktree is created
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    slug = "acme/widgets"
    issue, blocker_pr, base_pr = 7, 701, 702
    old_stack, launch_stack = 900, 901
    blocker_head, base_head = _head(blocker_pr), _head_sha(repo)
    pull = _pr_row(blocker_pr, closes=12, head=blocker_head)
    blockers = L.issue_contract.read_judged_blockers(
        issue, slug, _world(prs=[pull]),
        premise={"stack": old_stack, "layerPosition": 2},
        membership_reader=_Members({blocker_pr: _in_stack(old_stack, 1)}),
    )
    assert blockers["checked"] is True
    assert blockers["held"] == []
    assert [(row["pr"], row["stack"]) for row in blockers["accepted"]] == [(blocker_pr, old_stack)]
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": json.dumps(blockers["accepted"]),
    }})

    def read_membership(*, pr, repo, **kwargs):
        assert repo == slug
        if pr == blocker_pr:
            return _membership_ok(1, blocker_head, pr_number=pr) | {"stack": {"number": old_stack}}
        assert pr == base_pr
        return _membership_ok(1, base_head, pr_number=pr) | {"stack": {"number": launch_stack}}

    def read_vet(pr, repo_name, **kwargs):
        assert (pr, repo_name) == (blocker_pr, slug)
        return _pr_vet_state_ok(blocker_head, pull["body"], pr_number=pr), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("launch reached worktree creation with a blocker in another stack")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: (slug, None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    result = L.launch_build(
        repo, issue, _stack_premise(repo, issue=issue, stack=launch_stack, layerPosition=2),
        checks, str(tmp_path / "logs"), pr_vet_reader=read_vet, membership_reader=read_membership,
        pr_lookup=lambda *args, **kwargs: _pr_lookup_ok(pr=base_pr, repo=slug),
    )
    assert result["ok"] is False, result
    assert result["reason"] == "dependency-acceptance-lapsed"
