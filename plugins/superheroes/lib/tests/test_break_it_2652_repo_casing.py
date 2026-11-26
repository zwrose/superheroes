import json

import pytest

from test_issue_contract import PARENT, SUBS, _build_ready, _in_stack, _Members, _pr_row, _row, _sub, _world


@pytest.mark.parametrize("edge_repo, sibling_repo", [
    ("Acme/Widgets", "acme/widgets"),
    ("acme/widgets", "Acme/Widgets"),
])
def test_same_repo_with_different_case_still_has_an_accepted_layer(tmp_path, capsys, edge_repo, sibling_repo):
    # axis: edge and sibling identity each ignore repository casing while retaining the issue number.
    fake = _world(
        rows=[_row(12, "open", repo=edge_repo)],
        prs=[_pr_row(101, closes=12)],
        responses={
            PARENT: (0, json.dumps(_row(50, "open"))),
            SUBS: (0, json.dumps([_sub(12, sibling_repo), _sub(7, sibling_repo)])),
        },
    )
    result = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert result["ok"] is True
    assert [row["pr"] for row in result["blockers"]["accepted"]] == [101]
