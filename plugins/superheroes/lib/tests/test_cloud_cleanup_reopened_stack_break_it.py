"""A stale cleanup plan cannot archive a stack with newly reopened work."""
import os

import pytest

from test_cloud_cleanup import (
    _layers, _plan_n, _record_n, _stack, _state_file, w,
)


@pytest.mark.parametrize("explicit", [False, True])
def test_reopened_layer_invalidates_archive_plan_before_reservation(w, explicit):
    # axis: reopening a sibling after planning must revoke permission to reserve the archive send.
    _stack(w)
    planned = _plan_n(w, 501)
    assert planned["ok"] and planned["archiveText"]
    assert "archiveHeld" not in planned

    _layers(w, i202="open")
    selection = {"launch_id": planned["launchId"]} if explicit else {}
    result = _record_n(w, 501, "stale-archive-request", "pending", **selection)

    assert result == {"ok": False, "reason": "archive-held"}
    assert not os.path.exists(_state_file(w))
    assert w.gh.deletes == []
    refreshed = _plan_n(w, 501, **selection)
    assert refreshed["archiveText"] is None
    assert refreshed["archiveHeld"] == "stack-open"
    assert refreshed["openLayers"] == [202]
