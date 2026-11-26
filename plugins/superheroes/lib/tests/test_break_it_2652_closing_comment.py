from test_issue_contract import _build_ready, _head, _in_stack, _Members, _pr_row, _vet, _world


def test_hidden_first_line_keyword_does_not_clear_the_blocker(tmp_path, capsys):
    # axis: a closing keyword inside an HTML comment cannot establish a handed-back lower layer.
    body = "<!-- Closes #12 -->\n\n" + _vet("READY", _head(101))
    fake = _world(prs=[_pr_row(101, body=body)])
    result = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
    assert result["ok"] is False
    assert result["reason"] == "blocker-open"
    assert result["blockers"]["accepted"] == []
    assert [row["ref"] for row in result["blockers"]["held"]] == ["acme/widgets#12"]
