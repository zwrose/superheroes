import pytest

from test_issue_contract import FEATURE, NOT_LINKED, _Members, _card, _pr_row, _world
from test_launcher import L, _all_checks, _dependency_premise, _head_sha, _init_repo, _ledger_env, _pr_vet_state_ok


def test_boolean_feature_cannot_authorize_a_card_for_issue_one(tmp_path, monkeypatch):
    # axis: a boolean in accepted blocker evidence is unreadable and cannot authorize a worktree for a different feature
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    dependency = 701
    head = _head_sha(repo)
    pull = _pr_row(dependency, closes=12, head=head, vet=_card(head, FEATURE))
    blockers = L.issue_contract.read_judged_blockers(
        7, "acme/widgets", _world(prs=[pull]), premise={"dependency": dependency},
        membership_reader=_Members({dependency: NOT_LINKED}),
    )
    assert blockers["held"] == []
    [accepted] = blockers["accepted"]
    assert accepted["feature"] == FEATURE

    def read_dependency(pr, slug, **kwargs):
        assert (pr, slug) == (dependency, "acme/widgets")
        return _pr_vet_state_ok(head, _card(head, 1), pr_number=pr), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("invalid feature evidence reached worktree creation")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": [dict(accepted, feature=True)],
    }})
    result = L.launch_build(
        repo, 7, _dependency_premise(repo, dependency, issue=7), checks,
        str(tmp_path / "logs"), pr_vet_reader=read_dependency,
    )
    assert result["ok"] is False, result
    assert result["reason"] == "dependency-acceptance-unreadable"
