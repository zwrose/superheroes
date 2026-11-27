"""Cleanup must keep the branch when the pull's default base cannot be read."""

from test_cloud_cleanup import BRANCH, CC, PR, REPO, _as_layer, _lane, w  # noqa: F401 (w is a fixture)


# axis: a blank default branch in a closed layer's pull response refuses cleanup before any DELETE.
def test_cleanup_keeps_the_branch_when_pull_default_branch_is_blank(w):
    _lane(w, "l-1", 101)
    _as_layer(w, PR, 101)
    plan = CC.plan(w.repo, REPO, PR, env=w.env, run=w.gh)
    assert plan["ok"] and plan["linkSource"] == "timeline", plan

    w.gh.pulls[PR]["base"]["repo"]["default_branch"] = ""
    result = CC.branch(w.repo, REPO, PR, env=w.env, run=w.gh)
    assert (result, w.gh.deletes, w.gh.branches.get(BRANCH)) == (
        {"ok": False, "reason": "pr-links-unreadable"}, [], w.head,
    )
