import pytest

from test_issue_contract import _Members, _in_stack, _pr_row, _world
from test_launcher import L, _all_checks, _head_sha, _init_repo, _ledger_env, _pr_vet_state_ok, _stack_premise


def test_acceptance_from_another_stack_refuses_before_the_stack_gate(tmp_path, monkeypatch):
    # axis: an earlier preflight pass cannot clear a blocker for a different launch stack
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    head = _head_sha(repo)
    slug = "acme/widgets"
    pr = 701
    pull = _pr_row(pr, closes=12, head=head)
    live_membership = _in_stack(901, 1)
    live_membership["queried"]["headRefOid"] = head
    blockers = L.issue_contract.read_judged_blockers(
        7, slug, _world(prs=[pull]), premise={"stack": 901, "layerPosition": 2},
        membership_reader=_Members({pr: live_membership}),
    )
    assert blockers["held"] == []
    assert [(row["pr"], row["stack"]) for row in blockers["accepted"]] == [(pr, 901)]

    def unexpected_base_lookup(*args, **kwargs):
        pytest.fail("acceptance from stack 901 reached the base lookup for stack 900")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: (slug, None))
    checks = _all_checks(**{"base-state": {"state": "pass", "reason": "", "evidence": blockers["accepted"]}})
    result = L.launch_build(
        repo, 7, _stack_premise(repo, issue=7, stack=900, layerPosition=2),
        checks, str(tmp_path / "logs"), pr_lookup=unexpected_base_lookup,
        pr_vet_reader=lambda number, repo_name, **kwargs: (
            _pr_vet_state_ok(head, pull["body"], pr_number=number), None,
        ),
        membership_reader=lambda **kwargs: live_membership,
    )
    assert result["ok"] is False, result
