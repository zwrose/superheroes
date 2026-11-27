import json

import pytest

from test_issue_contract import FEATURE, NOT_LINKED, _Members, _pr_row, _world
from test_launcher import (
    L, _all_checks, _card_vet_body, _dependency_premise, _head_sha, _init_repo,
    _ledger_env, _never_spawn, _parked_vet_body, _pr_vet_state_ok,
)


def test_duplicate_pr_keys_refuse_before_creating_a_worktree(tmp_path, monkeypatch):
    # axis: an ambiguous accepted row cannot hide a dependency whose card has been withdrawn.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    head = _head_sha(repo)
    dependency = 701
    row = _pr_row(dependency, closes=12, head=head, vet=_card_vet_body(head, parent=FEATURE))
    blockers = L.issue_contract.read_judged_blockers(
        7, "acme/widgets", _world(prs=[row]), premise={"dependency": dependency},
        membership_reader=_Members({dependency: NOT_LINKED}),
    )
    accepted = blockers["accepted"]
    assert blockers["held"] == []
    assert [(entry["pr"], entry["form"]) for entry in accepted] == [(dependency, "stack-card")]
    evidence = json.dumps(accepted).replace(
        f'"pr": {dependency}', f'"pr": {dependency}, "pr": {dependency + 1}', 1,
    )

    def read_dependency(pr, slug, **kwargs):
        assert (pr, slug) == (dependency, "acme/widgets")
        return _pr_vet_state_ok(head, _parked_vet_body(head), pr_number=pr), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("ambiguous blocker evidence reached worktree creation")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {"state": "pass", "reason": "", "evidence": evidence}})
    result = L.launch_build(
        repo, 7, _dependency_premise(repo, dependency, issue=7), checks,
        str(tmp_path / "logs"), pr_vet_reader=read_dependency, spawn_fn=_never_spawn,
    )
    assert result["ok"] is False
    assert result["reason"] == "dependency-acceptance-unreadable"
