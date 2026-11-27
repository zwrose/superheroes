import pytest

from test_issue_contract import _head, _in_stack, _Members, _pr_row, _world
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


def test_stack_acceptance_cannot_be_reused_after_retargeting(tmp_path, monkeypatch):
    # axis: a blocker accepted for one stack cannot authorize worktree creation for a different stack
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    slug = "acme/widgets"
    blocker_pr = 701
    blocker_head = _head(blocker_pr)
    base_head = _head_sha(repo)
    pull = _pr_row(blocker_pr, closes=12, head=blocker_head)
    blockers = L.issue_contract.read_judged_blockers(
        7, slug, _world(prs=[pull]),
        premise={"stack": 900, "layerPosition": 2},
        membership_reader=_Members({blocker_pr: _in_stack(900, 1)}),
    )
    assert blockers["held"] == []
    assert [(row["pr"], row["stack"]) for row in blockers["accepted"]] == [(blocker_pr, 900)]

    def read_vet(pr, repo_name, **kwargs):
        assert (pr, repo_name) == (blocker_pr, slug)
        return _pr_vet_state_ok(blocker_head, pull["body"], pr_number=pr), None

    def read_membership(*, pr, repo, expect_stack=None, **kwargs):
        assert repo == slug
        if pr == blocker_pr:
            return _membership_ok(1, blocker_head, pr_number=pr) | {"stack": {"number": 900}}
        assert (pr, expect_stack) == (702, 901)
        return _membership_ok(1, base_head, pr_number=pr) | {"stack": {"number": 901}}

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("an acceptance from another stack reached worktree creation")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: (slug, None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": blockers["accepted"],
    }})
    result = L.launch_build(
        repo, 7, _stack_premise(repo, issue=7, stack=901, layerPosition=2),
        checks, str(tmp_path / "logs"), pr_vet_reader=read_vet,
        membership_reader=read_membership,
        pr_lookup=lambda *args, **kwargs: _pr_lookup_ok(pr=702, repo=slug),
    )
    assert result["ok"] is False, result