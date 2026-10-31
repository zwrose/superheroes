"""A recreated adopted branch invalidates an earlier absence read."""
import time
from types import SimpleNamespace

import launch_ledger as ll
import test_adopt_original_session as adoption
from test_launcher_cloud import (
    _isolated,  # noqa: F401 (_isolated is an autouse fixture)
)


def test_branch_recreated_during_later_pr_read_requires_session_evidence(tmp_path, monkeypatch):
    # axis: a branch recreated during a later remote lookup must retain its
    # earlier builder and prevent another builder from spawning without evidence.
    repo = adoption._adopted_repo(tmp_path)
    bound_id = "lane-bound-first"

    # Pin ledger outcomes to a historical instant so the synthetic first PR can
    # follow both handbacks. Real clock drift and cross-host skew are unobservable.
    epoch = adoption.LANE_STARTED_TS + 120
    with monkeypatch.context() as clock:
        clock.setattr(
            ll, "time", SimpleNamespace(**{**vars(time), "time": lambda: epoch}),
        )
        adoption._seed_lane(
            repo, bound_id, session_id="session_" + "B" * 26,
            title="issue-656-fixturelane00000b",
            premise_extra={"adoptsBranch": adoption.ADOPTED},
        )
        adoption._seed_lane(repo)
    adoption._delete_remote_branch(repo)
    handback = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome"
        and record.get("launchId") == adoption.LANE_ID
    )
    recreated = []

    def read_first_pr(root, branch, env):
        # Simulate the earlier builder pushing while the later lookup is pending.
        adoption._git(root, "push", "-q", "origin", "HEAD:refs/heads/%s" % branch)
        recreated.append(branch)
        return handback + 3600

    # Pin the PR timestamp beyond the allowance and inject the push at the owned
    # lookup seam. Live GitHub transport and real process scheduling are unobservable;
    # branch deletion and recreation use the real local bare remote.
    monkeypatch.setattr(adoption.L, "_adopted_branch_first_pr_fn", read_first_pr)
    result, calls = adoption._adopt(repo, tmp_path, branch=adoption.ADOPTED)
    assert recreated == [adoption.ADOPTED]
    assert result["ok"] is False, result
    assert result["reason"] == adoption.TOKEN_UNREAD, result
    assert result["failedRead"] == "listing-not-given"
    assert bound_id in result["launchIds"]
    assert calls == []
