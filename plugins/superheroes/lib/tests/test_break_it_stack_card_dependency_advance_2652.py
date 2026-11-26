import subprocess

import pytest

import issue_contract
from test_issue_contract import FEATURE, NOT_LINKED, _Members, _pr_row, _world
from test_launcher import (
    L,
    _all_checks,
    _card_vet_body,
    _dependency_premise,
    _head_sha,
    _init_repo,
    _ledger_env,
    _pr_vet_state_ok,
)


def test_card_dependency_advancing_after_preflight_refuses_before_worktree(tmp_path, monkeypatch):
    # axis: a lower layer accepted at preflight must still cover its current head when launch makes the worktree
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    old_head = _head_sha(repo)
    premise = _dependency_premise(repo, 701, issue=7)
    card_body = _card_vet_body(old_head, parent=FEATURE)
    world = _world(prs=[_pr_row(701, closes=12, head=old_head, vet=card_body)])
    blockers = issue_contract.read_judged_blockers(
        7, "acme/widgets", world, premise={"dependency": 701},
        membership_reader=_Members({701: dict(NOT_LINKED, queried={"headRefOid": old_head})}),
    )
    assert blockers["held"] == []
    assert [row["head"] for row in blockers["accepted"]] == [old_head]

    (tmp_path / "repo" / "file.txt").write_text("lower layer advanced\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=test@test.local", "-c", "user.name=test",
         "commit", "-qam", "Advance lower layer"],
        check=True,
    )
    new_head = _head_sha(repo)
    reads = []

    def read_dependency(pr, slug, **kwargs):
        reads.append((pr, slug))
        return _pr_vet_state_ok(new_head, card_body, pr_number=pr), None

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("launch reached worktree creation after its card-marked dependency advanced")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *a, **k: ("acme/widgets", None))
    monkeypatch.setattr(L, "compose_launch", lambda *a, **k: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    result = L.launch_build(
        repo, 7, premise, _all_checks(), str(tmp_path / "logs"), pr_vet_reader=read_dependency,
    )
    assert reads == [(701, "acme/widgets")]
    assert result["ok"] is False, result
