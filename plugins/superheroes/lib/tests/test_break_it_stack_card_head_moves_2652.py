import json
import subprocess

import pytest

import issue_contract
from test_issue_contract import NOT_LINKED, _Members, _card, _pr_row, _world
from test_launcher import L, _all_checks, _head_sha, _init_repo, _ledger_env, _pr_vet_state_ok, _valid_premise


def test_card_dependency_head_move_refuses_before_worktree_creation(tmp_path, monkeypatch):
    # axis: a dependency admitted by its card mark must still be valid when launch rereads its head
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "managed-worktrees"))
    old_head = _head_sha(repo)
    dependency = 701
    card = _card(old_head)
    row = _pr_row(dependency, closes=12, head=old_head, vet=card)
    blockers = issue_contract.read_judged_blockers(
        7, "acme/widgets", _world(prs=[row]),
        premise={"dependency": dependency},
        membership_reader=_Members({dependency: dict(NOT_LINKED, queried={"headRefOid": old_head})}),
    )
    assert blockers["checked"] is True
    assert blockers["held"] == []
    assert blockers["requiredDependency"] == dependency
    assert [(entry["head"], entry["form"]) for entry in blockers["accepted"]] == [(old_head, "stack-card")]

    subprocess.run(
        ["git", "-C", repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "advance dependency"],
        check=True,
    )
    new_head = _head_sha(repo)
    assert new_head != old_head
    reads = []

    def read_current_dependency(pr, slug, **kwargs):
        reads.append((pr, slug))
        return _pr_vet_state_ok(new_head, row["body"], pr_number=dependency), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("stale dependency vet reached worktree creation")

    def unexpected_spawn(*args, **kwargs):
        pytest.fail("stale dependency vet reached worker spawn")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *a, **kw: ("acme/widgets", None))
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {
        "state": "pass", "reason": "", "evidence": json.dumps(blockers["accepted"]),
    }})
    result = L.launch_build(
        repo, 7, _valid_premise(repo, issue=7, baseCommit=old_head, dependency=dependency),
        checks, str(tmp_path / "logs"), pr_vet_reader=read_current_dependency, spawn_fn=unexpected_spawn,
    )
    assert reads == [(dependency, "acme/widgets")]
    assert result["ok"] is False
