"""A stack layer linking its parent must honor the lane's existing archive hold."""
import pytest

from test_cloud_cleanup import (
    PARENT, _OPENED, _plan_n, _pull, _record_n, _sha, _stack, w,
)


@pytest.mark.parametrize("held,reason", [
    ("pending", "request-in-progress"),
    ("uncertain", "request-uncertain"),
    ("delivered", "request-delivered"),
])
@pytest.mark.parametrize("explicit", [False, True])
def test_linking_parent_does_not_grant_another_archive_reservation(w, held, reason, explicit):
    # axis: directly linking the shared parent must not bypass another layer's archive reservation.
    _stack(w)
    w.gh.pulls[503] = _pull(
        issues=(203, PARENT), head_sha=_sha(503), ref="layer-3",
        created_at=_OPENED,
    )
    first = _plan_n(w, 501)
    assert first["ok"] and first["viaParent"] is True
    reserved = _record_n(w, 501, "first-request", "pending", launch_id=first["launchId"])
    assert reserved["ok"]
    if held != "pending":
        settled = _record_n(w, 501, "first-request", held, launch_id=first["launchId"])
        assert settled["ok"]

    selection = {"launch_id": first["launchId"]} if explicit else {}
    later = _plan_n(w, 503, **selection)
    assert later["ok"] and later["launchId"] == first["launchId"]
    result = _record_n(
        w, 503, "second-request", "pending", launch_id=later["launchId"],
    )
    assert result == {"ok": False, "reason": reason}
    assert later["request"]["pr"] == 501
    assert later["request"]["outcome"] == held
    if held == "delivered":
        assert later["archiveText"] is None
        assert later["alreadyDelivered"] is True
