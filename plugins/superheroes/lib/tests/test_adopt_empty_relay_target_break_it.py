"""An empty persisted relay target cannot authorize another builder."""
import json
import os
from datetime import datetime, timezone

import cloud_relay
import launch_ledger as ll
import test_adopt_original_session as adoption
from test_launcher_cloud import (
    _cloud_repo,
    _isolated,  # noqa: F401 (_isolated is an autouse fixture)
)


def test_empty_relay_target_keeps_the_lane(tmp_path, monkeypatch):
    # axis: an invalid empty relay target cannot prove this lane was not reopened.
    repo = _cloud_repo(tmp_path)
    adoption._seed_lane(repo)
    handback = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome"
        and record.get("launchId") == adoption.LANE_ID
    )

    # Pin compose after handback and the PR lookup past the allowance to isolate
    # target validation. Real delivery timing, clock skew, and live GitHub
    # behavior are unobservable under these replacements.
    composed_at = datetime.fromtimestamp(
        handback + 60, timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    monkeypatch.setattr(cloud_relay, "_now_iso", lambda: composed_at)
    monkeypatch.setattr(
        adoption.L, "_adopted_branch_first_pr_fn",
        lambda root, branch, env: handback + 3600,
    )
    composed = cloud_relay.compose(
        repo, "/cfg/acct", adoption.SESSION_TITLE, "fix it", fix_order=True,
    )
    assert composed["ok"], composed
    state_path, reason = cloud_relay._state_path(repo, os.environ)
    assert reason is None
    with open(state_path, encoding="utf-8") as fh:
        state = json.load(fh)
    entry = state["pending"][composed["msgId"]]
    assert entry["session"] == adoption.SESSION_TITLE
    entry["session"] = ""
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)

    result, calls = adoption._adopt(repo, tmp_path)
    assert result["ok"] is False, result
    assert result["reason"] == adoption.TOKEN_UNREAD
    assert result["failedRead"] == "listing-not-given"
    assert result["launchIds"] == [adoption.LANE_ID]
    assert calls == []
