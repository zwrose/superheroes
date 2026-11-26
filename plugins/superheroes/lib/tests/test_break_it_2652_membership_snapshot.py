from test_issue_contract import _head, _in_stack, _judge_cli, _Members, _pr_row, _world


def test_newer_membership_head_cannot_use_the_vet_from_the_pull_list(tmp_path, capsys):
    # axis: a newer head in the membership result invalidates READY evidence read at an earlier head.
    changed = _in_stack(900, 1)
    changed["queried"].update(number=101, headRefOid=_head(999))
    listed = _pr_row(101, closes=12, head=_head(101))
    result = _judge_cli(
        capsys, _world(prs=[listed]), _Members({101: changed}),
        tmp_path, {"stack": 900, "layerPosition": 2},
    )
    assert result["ok"] is False
    assert result["blockers"]["accepted"] == []
