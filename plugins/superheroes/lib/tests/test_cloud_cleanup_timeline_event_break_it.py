"""A malformed timeline row cannot turn ambiguous cleanup into a deletion."""

from test_cloud_cleanup import BRANCH, PR, _T1, _T2, _as_layer, _branch, _lane, _plan, _pull
from test_cloud_cleanup import w  # noqa: F401  (fixture used by pytest)


def test_cleanup_keeps_the_branch_when_a_timeline_row_has_no_event(w):
    # axis: a row whose event type cannot be read must block cleanup even when another issue has a confirmed link.
    _lane(w, "l-first", 101, ts=_T1)
    _lane(w, "l-second", 202, session="session-b", ts=_T2)
    w.gh.pulls[PR] = _pull(issues=(101, 202), head_sha=w.head)
    _as_layer(w, PR, 101, extra=(202,))
    assert _plan(w) == {"ok": False, "reason": "lane-ambiguous"}

    del w.gh.timelines[202][0]["event"]
    result = _branch(w)

    assert w.gh.deletes == [] and BRANCH in w.gh.branches, result
    assert result == {"ok": False, "reason": "pr-links-unreadable"}
