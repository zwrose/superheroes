import json

import pytest

from test_issue_contract import _head, _judge_cli, _pr_row, _world


@pytest.mark.parametrize("membership_head, expected_reason", [
    (_head(101), None),
    (_head(999), "blockers-unreadable"),
])
def test_unstacked_dependency_uses_the_same_head_as_its_vet(
    tmp_path, capsys, membership_head, expected_reason,
):
    # axis: an explicit null stackEntry allows a dependency only at the head covered by its READY vet
    payload = {"data": {"repository": {"pullRequest": {
        "number": 101,
        "baseRefName": "main",
        "headRefName": "layer-12",
        "headRefOid": membership_head,
        "stackEntry": None,
    }}}}
    run = _world(
        prs=[_pr_row(101, closes=12, head=_head(101))],
        responses={"graphql": (0, json.dumps(payload))},
    )
    result = _judge_cli(capsys, run, None, tmp_path, {"dependency": 101})
    assert any(call[:3] == ["gh", "api", "graphql"] for call in run.calls)
    assert result["reason"] == expected_reason
    assert result["blockers"]["checked"] is (expected_reason is None)
    assert [entry["pr"] for entry in result["blockers"]["accepted"]] == (
        [101] if expected_reason is None else []
    )
