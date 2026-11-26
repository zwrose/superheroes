import json

import pytest

from test_issue_contract import FEATURE, NOT_LINKED, _Members, _pr_row, _world
from test_launcher import (
    L,
    _all_checks,
    _card_vet_body,
    _dependency_premise,
    _head_sha,
    _init_repo,
    _ledger_env,
    _parked_vet_body,
    _pr_vet_state_ok,
)


def test_withdrawn_stack_card_refuses_before_worktree_creation(tmp_path, monkeypatch):
    # axis: a dependency accepted by preflight loses its card mark and advances before launch reads it.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    old_head = _head_sha(repo)
    dependency = 701
    card = _card_vet_body(old_head, parent=FEATURE)
    row = _pr_row(dependency, closes=12, head=old_head, vet=card)
    blockers = L.issue_contract.read_judged_blockers(
        7,
        "acme/widgets",
        _world(prs=[row]),
        premise={"dependency": dependency},
        membership_reader=_Members({dependency: NOT_LINKED}),
    )
    assert blockers["held"] == []
    assert [(row["pr"], row["head"], row["form"]) for row in blockers["accepted"]] == [
        (dependency, old_head, "stack-card"),
    ]

    new_head = ("1" if old_head[0] == "0" else "0") + old_head[1:]
    reads = []

    def read_dependency(pr, slug, **kwargs):
        reads.append((pr, slug))
        return _pr_vet_state_ok(new_head, _parked_vet_body(new_head), pr_number=pr), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("launch reached worktree creation after the dependency lost its card mark")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": json.dumps(blockers["accepted"]),
    }})
    result = L.launch_build(
        repo,
        7,
        _dependency_premise(repo, dependency, issue=7),
        checks,
        str(tmp_path / "logs"),
        pr_vet_reader=read_dependency,
    )
    assert reads == [(dependency, "acme/widgets")]
    assert result["ok"] is False, result
