from types import SimpleNamespace

import pytest

import stack_check as sc
from test_issue_contract import _head, _judge_cli, _pr_row, _world
from test_stack_check import _graphql_ok, _member, _pull_request, _rest_resp


@pytest.mark.parametrize("transport", ["graphql", "rest"])
def test_unlink_during_verification_does_not_clear_the_blocker(
    tmp_path, capsys, monkeypatch, transport,
):
    # axis: linked membership that disappears on replay at the same head leaves the blocker unreadable.
    # Pin gh discovery because the fixture supplies transport responses. Executable discovery is outside this test.
    monkeypatch.setattr(sc.shutil, "which", lambda name: "/fixture/gh" if name == "gh" else None)
    pr = 101
    head = _head(pr)
    world = _world(prs=[_pr_row(pr, closes=12, head=head)])
    pull_path = "repos/acme/widgets/pulls/101"
    stack_path = "repos/acme/widgets/stacks/900"

    if transport == "graphql":
        linked = _pull_request(
            pr_number=pr, position=2, stack_number=900, stack_size=2,
            base_ref_name="layer-base", head_ref_oid=head,
            nodes=[_member(1, number=100), _member(2, number=pr, headRefOid=head, baseRefName="layer-base")],
        )
        responses = [
            ("graphql", _graphql_ok(linked)),
            ("graphql", _graphql_ok(dict(linked, stackEntry=None))),
        ]
    else:
        member = {
            "number": pr, "state": "open", "draft": False,
            "head": {"ref": "branch-2", "sha": head}, "base": {"ref": "layer-base"},
        }
        first = dict(member, number=100, head={"ref": "layer-base", "sha": _head(100)}, base={"ref": "main"})
        linked = dict(member, stack={"number": 900, "position": 2, "size": 2, "base": {"ref": "main"}})
        stack = {"number": 900, "base": {"ref": "main"}, "pull_requests": [first, member]}
        responses = [
            ("graphql", SimpleNamespace(returncode=1, stdout="", stderr="gh: use the REST API (HTTP 403)")),
            (pull_path, _rest_resp(linked)),
            (stack_path, _rest_resp(stack)),
            (pull_path, _rest_resp(dict(member, stack=None))),
        ]

    pending = iter(responses)

    def run(argv, **kwargs):
        if argv[2] in ("graphql", pull_path, stack_path):
            endpoint, response = next(pending)
            assert argv[2] == endpoint
            return response
        return world(argv, **kwargs)

    result = _judge_cli(capsys, run, None, tmp_path, {"dependency": pr})
    assert next(pending, None) is None
    assert result["ok"] is False
    assert result["reason"] == "blockers-unreadable"
    assert result["blockers"]["accepted"] == []
