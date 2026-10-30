"""A fix order recorded during a later lane's branch read blocks adoption."""
import cloud_relay
import launch_ledger as ll
import test_adopt_original_session as adoption
from test_launcher_cloud import (
    _isolated,  # noqa: F401 (_isolated is an autouse fixture)
)


def test_fix_order_during_later_branch_read_blocks_adoption(tmp_path, monkeypatch):
    # axis: a fix order recorded during a bound lane's branch lookup must retain
    # an earlier handed-back lane and prevent another builder from spawning.
    repo = adoption._adopted_repo(tmp_path)
    adoption._seed_lane(repo)
    adoption._seed_lane(
        repo, "lane-bound", session_id="session_" + "B" * 26,
        title="issue-656-fixturelane00000b",
        premise_extra={"adoptsBranch": adoption.ADOPTED},
    )
    adoption._delete_remote_branch(repo)
    handback = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome"
        and record.get("launchId") == adoption.LANE_ID
    )

    # Pin the first-PR timestamp beyond the allowance to isolate the subsequent
    # branch-read interleaving; live GitHub and real clock skew are unobservable.
    monkeypatch.setattr(
        adoption.L, "_adopted_branch_first_pr_fn",
        lambda root, branch, env: handback + 3600,
    )
    actual_branch_read = adoption.L._adopted_branch_absent
    queued = []

    def branch_read_with_fix_order(root, branch, env):
        absent = actual_branch_read(root, branch, env)
        assert absent is True
        if not queued:
            composed = cloud_relay.compose(
                root, "/cfg/acct", adoption.SESSION_TITLE,
                "Continue fixing adopted branch %s" % branch,
                env=env, fix_order=True,
            )
            assert composed["ok"], composed
            queued.append(composed["msgId"])
        return absent

    # Inject the write before the owned branch-read seam returns, using a real
    # local bare remote and persisted relay state. Real network latency and
    # concurrent process scheduling are not exercised.
    monkeypatch.setattr(
        adoption.L, "_adopted_branch_absent", branch_read_with_fix_order,
    )
    result, calls = adoption._adopt(repo, tmp_path, branch=adoption.ADOPTED)
    assert queued
    assert result["ok"] is False, result
    assert result["reason"] == adoption.TOKEN_UNREAD, result
    assert result["failedRead"] == "listing-not-given"
    assert result["launchIds"] == [adoption.LANE_ID]
    assert calls == []
