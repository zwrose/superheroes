"""A fix order delivered after a newer handback still blocks adoption."""
import os
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import cloud_relay
import launch_ledger as ll
import test_adopt_original_session as adoption
from test_cloud_relay import (
    RELAY_ID,
    _check,
    _ensure_alive,
    _send_lines,
    _write_record,
)
from test_launcher_cloud import (
    _cloud_repo,
    _isolated,  # noqa: F401 (_isolated is an autouse fixture)
)


def _stamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _amend_at(monkeypatch, repo, kind, value, epoch):
    # Pin only the ledger writer's clock to establish the event ordering below;
    # actual host clock skew and process scheduling are not exercised.
    with monkeypatch.context() as patched:
        patched.setattr(ll, "time", SimpleNamespace(**{**vars(time), "time": lambda: epoch}))
        result = ll.amend(repo, adoption.LANE_ID, kind, value, "queued relay scenario")
    assert result["ok"], result


def test_delivery_after_a_new_handback_keeps_the_lane(tmp_path, monkeypatch):
    # axis: a queued fix order delivered after the latest handback prevents a second builder.
    repo = _cloud_repo(tmp_path)
    adoption._seed_lane(repo)
    original = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome"
        and record.get("launchId") == adoption.LANE_ID
    )
    config = tmp_path / "builders-config"
    record = config / "projects" / "fixture" / (RELAY_ID + ".jsonl")
    record.parent.mkdir(parents=True)
    world = SimpleNamespace(
        repo=repo, config=str(config), record=str(record), env=dict(os.environ),
    )
    _ensure_alive(world)

    # Establish vet < compose < new handback < delivery deterministically.
    # Real transport delay and concurrent scheduling are unobservable here;
    # delivery itself is checked against a recorded SendMessage/result pair.
    _amend_at(monkeypatch, repo, "vet", "not-ready", original + 60)
    monkeypatch.setattr(cloud_relay, "_now_iso", lambda: _stamp(original + 120))
    composed = cloud_relay.compose(
        repo, str(config), adoption.SESSION_TITLE,
        "Fix the adopted branch %s" % adoption._branch(repo),
        env=world.env, fix_order=True,
    )
    assert composed["ok"], composed
    handback = original + 180
    _amend_at(monkeypatch, repo, "reoutcome", "handback", handback)
    delivered_at = _stamp(original + 240)
    _write_record(world, _send_lines(
        "toolu_delayed_fix", adoption.SESSION_TITLE, composed["forward"], delivered_at,
    ))
    monkeypatch.setattr(cloud_relay, "_now_iso", lambda: delivered_at)
    checked, _ = _check(world, composed["msgId"], wait=0)
    assert checked["delivered"] is True, checked

    # Pin the PR lookup past the allowance to isolate relay ordering;
    # live GitHub behavior and inter-machine clock skew are not exercised.
    monkeypatch.setattr(
        adoption.L, "_adopted_branch_first_pr_fn",
        lambda root, branch, env: handback + 3600,
    )
    result, calls = adoption._adopt(repo, tmp_path)
    assert result["ok"] is False, result
    assert result["reason"] == adoption.TOKEN_UNREAD
    assert result["failedRead"] == "listing-not-given"
    assert result["launchIds"] == [adoption.LANE_ID]
    assert calls == []
