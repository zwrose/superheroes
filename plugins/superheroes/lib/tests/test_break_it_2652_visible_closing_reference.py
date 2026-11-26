from test_issue_contract import _Members, _build_ready, _head, _in_stack, _pr_row, _vet, _world


def test_visible_closing_reference_before_inline_comment_counts(tmp_path, capsys):
    # axis: a trailing HTML comment leaves the preceding first-line closing reference visible.
    body = "Closes #12 <!-- handed back -->\n\n" + _vet("READY", _head(101))
    run = _world(prs=[_pr_row(101, body=body)])

    result = _build_ready(tmp_path, capsys, run, members=_Members({101: _in_stack(900, 1)}))

    assert result["ok"] is True
    assert [row["pr"] for row in result["blockers"]["accepted"]] == [101]
