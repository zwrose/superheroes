import json

from test_issue_contract import _head, _judge_cli, _pr_row, _world


def test_unlinked_membership_at_a_new_head_cannot_use_the_old_vet(tmp_path, capsys):
    # axis: an explicit null stackEntry at a new head cannot validate an unlinked dependency at an old head.
    listed = _pr_row(101, closes=12, head=_head(101))
    pull = {
        "number": 101,
        "baseRefName": "main",
        "headRefName": "lower-layer",
        "headRefOid": _head(102),
        "stackEntry": None,
    }
    graph = {"data": {"repository": {"pullRequest": pull}}}
    run = _world(prs=[listed], responses={"graphql": (0, json.dumps(graph))})

    result = _judge_cli(capsys, run, None, tmp_path, {"dependency": 101})

    assert result["ok"] is False
    assert result["reason"] == "blockers-unreadable"
    assert result["blockers"]["accepted"] == []
