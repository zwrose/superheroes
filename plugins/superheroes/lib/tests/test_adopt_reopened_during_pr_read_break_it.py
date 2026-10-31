"""A fix order composed during the PR lookup still prevents another builder."""
import cloud_relay
import launch_ledger as ll
import test_adopt_original_session as adoption
from test_launcher_cloud import (
    _cloud_repo,
    _isolated,  # noqa: F401 (_isolated is an autouse fixture)
)


def test_fix_order_composed_during_first_pr_read_blocks_adoption(tmp_path, monkeypatch):
    # axis: a fix order persisted during the remote read must prevent a second builder.
    repo = _cloud_repo(tmp_path)
    adoption._seed_lane(repo)
    handback = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome"
        and record.get("launchId") == adoption.LANE_ID
    )
    queued = []

    def read_first_pr(root, branch, env):
        if not queued:
            composed = cloud_relay.compose(
                root, "/cfg/acct", adoption.SESSION_TITLE,
                "Continue fixing adopted branch %s" % branch,
                env=env, fix_order=True,
            )
            assert composed["ok"], composed
            queued.append(composed["msgId"])
        return handback + 3600

    # Pin the PR age and inject the write at the owned lookup seam to reproduce
    # the interleaving deterministically. Live GitHub transport, real concurrent
    # scheduling, and inter-machine clock skew are not exercised.
    monkeypatch.setattr(adoption.L, "_adopted_branch_first_pr_fn", read_first_pr)
    result, calls = adoption._adopt(repo, tmp_path)
    assert len(queued) == 1
    assert result["ok"] is False, result
    assert result["reason"] == adoption.TOKEN_UNREAD, result
    assert result["failedRead"] == "listing-not-given"
    assert result["launchIds"] == [adoption.LANE_ID]
    assert calls == []
