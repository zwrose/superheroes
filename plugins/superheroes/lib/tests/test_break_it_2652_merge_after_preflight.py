import pytest

from test_issue_contract import NOT_LINKED, _Members, _head, _in_stack, _pr_row, _world
from test_launcher import (
    L, _all_checks, _head_sha, _init_repo, _ledger_env, _membership_ok, _never_spawn,
    _pr_lookup_ok, _pr_vet_state_ok, _stack_premise,
)


def test_lower_layer_merged_at_new_head_refuses_before_worktree(tmp_path, monkeypatch):
    # axis: a merge at a different head invalidates the lower layer accepted by preflight
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    slug = "acme/widgets"
    base = _head_sha(repo)
    blocker_pr, entry_pr = 701, 702
    old_head, merged_head = _head(701), _head(703)
    pull = _pr_row(blocker_pr, closes=12, head=old_head)
    blockers = L.issue_contract.read_judged_blockers(
        7, slug, _world(prs=[pull]), premise={"stack": 900, "layerPosition": 3},
        membership_reader=_Members({blocker_pr: _in_stack(900, 1)}),
    )
    assert blockers["held"] == []
    assert [(row["pr"], row["head"]) for row in blockers["accepted"]] == [(blocker_pr, old_head)]

    def read_vet(pr, repo_name, **kwargs):
        assert (pr, repo_name) == (blocker_pr, slug)
        return _pr_vet_state_ok(merged_head, state="MERGED", pr_number=pr), None

    def read_membership(*, pr, repo, **kwargs):
        assert repo == slug
        if pr == blocker_pr:
            return dict(NOT_LINKED, queried={"headRefOid": merged_head})
        assert pr == entry_pr
        return _membership_ok(2, base, pr_number=pr) | {"stack": {"number": 900}}

    def unexpected_worktree(*args, **kwargs):
        pytest.fail("a lower layer merged at a different head and the stale base reached worktree creation")

    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: (slug, None))
    monkeypatch.setattr(L, "compose_launch", lambda *args, **kwargs: {"ok": True, "doctrine": {}, "argv": []})
    monkeypatch.setattr(L, "create_build_worktree", unexpected_worktree)
    checks = _all_checks(**{"base-state": {"state": "pass", "reason": "", "evidence": blockers["accepted"]}})
    result = L.launch_build(
        repo, 7, _stack_premise(repo, issue=7, stack=900, layerPosition=3),
        checks, str(tmp_path / "logs"), pr_vet_reader=read_vet, membership_reader=read_membership,
        pr_lookup=lambda *args, **kwargs: _pr_lookup_ok(entry_pr, slug), spawn_fn=_never_spawn,
    )
    assert result["ok"] is False, result
