from pathlib import Path

from test_cloud_cleanup import (  # noqa: F401 (w is a fixture)
    BRANCH,
    PR,
    _OPENED,
    _T1,
    _as_layer,
    _branch,
    _lane,
    _plan,
    _pull,
    _record,
    _state_file,
    w,
)


def test_a_closed_stack_layer_with_an_incomplete_timeline_keeps_its_branch(w):
    # axis: a row missing its event invalidates an earlier match before archive reservation or branch deletion
    _lane(w, "l-1", 101, ts=_T1)
    w.gh.pulls[PR] = _pull(head_sha=w.head, created_at=_OPENED)
    _as_layer(w, PR, 101)
    assert _plan(w)["launchId"] == "l-1"

    w.gh.timelines[101].append({})
    want = {"ok": False, "reason": "pr-links-unreadable"}
    results = (_plan(w), _record(w, "m-1", "pending"), _branch(w))
    assert results == (want, want, want)
    assert w.gh.deletes == []
    assert w.gh.branches[BRANCH] == w.head
    assert not Path(_state_file(w)).exists()
