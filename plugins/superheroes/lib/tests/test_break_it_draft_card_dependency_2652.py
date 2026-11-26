import json

import pytest

import issue_contract
from test_issue_contract import NOT_LINKED, _Members, _card, _head, _pr_row, _world
from test_launcher import L, _all_checks, _dependency_premise, _head_sha, _init_repo, _ledger_env, _pr_vet_state_ok


def test_accepted_card_dependency_that_advances_and_becomes_draft_refuses(tmp_path, monkeypatch):
    # axis: a return to draft cannot bypass the stale-card gate after preflight accepted the dependency
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    dependency = 701
    old_head = _head_sha(repo)
    new_head = _head(999)
    assert new_head != old_head
    listed = _pr_row(dependency, closes=12, head=old_head, vet=_card(old_head))
    blockers = issue_contract.read_judged_blockers(
        7, "acme/widgets", _world(prs=[listed]),
        premise={"dependency": dependency},
        membership_reader=_Members({dependency: NOT_LINKED}),
    )
    assert blockers["held"] == []
    assert [(row["pr"], row["head"], row["form"]) for row in blockers["accepted"]] == [
        (dependency, old_head, "stack-card"),
    ]

    def read_dependency(pr, slug, **kwargs):
        assert (pr, slug) == (dependency, "acme/widgets")
        return _pr_vet_state_ok(new_head, listed["body"], pr_number=pr, is_draft=True), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("a stale card-marked dependency reached worktree creation after returning to draft")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": json.dumps(blockers["accepted"]),
    }})
    result = L.launch_build(
        repo, 7, _dependency_premise(repo, dependency, issue=7, baseCommit=old_head),
        checks, str(tmp_path / "logs"), pr_vet_reader=read_dependency,
    )
    assert result["ok"] is False
    assert result["reason"] == "dependency-card-stale"
    assert result["detail"] == new_head
