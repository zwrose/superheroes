"""A cloud adoption must reject checkout drift during its final session read."""
import launch_ledger as ll

from test_adopt_original_session import LANE_ID, _adopt, _seed_lane
from test_launcher import L, _head_sha
from test_launcher_cloud import (  # noqa: F401 (_isolated is an autouse fixture)
    _cloud_repo,
    _git,
    _isolated,
    _lanes,
)
from test_launcher_cloud_checkout import _commit


def test_checkout_movement_during_final_session_read_prevents_cloud_spawn(
    tmp_path, monkeypatch,
):
    # axis: checkout movement during the pre-spawn original-session lookup
    # refuses the cloud launch without changing the owner's checkout.
    repo = _cloud_repo(tmp_path)
    original_branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
    original_head = _head_sha(repo)
    _git(repo, "checkout", "-q", "-b", "owner-work")
    other_head = _commit(repo, "owner-work.txt")
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/owner-work")
    _git(repo, "checkout", "-q", original_branch)
    assert other_head != original_head
    _seed_lane(repo)
    handback = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome"
        and record.get("launchId") == LANE_ID
    )
    reads = []
    moved = []

    def first_pr_then_owner_switches(root, branch, env):
        reads.append(branch)
        if len(reads) == 2:
            # Fix the interleaving at the pre-spawn remote read. Real network
            # latency and concurrent process scheduling are not exercised.
            _git(repo, "checkout", "-q", "owner-work")
            moved.append(other_head)
        # Pin PR creation after the old lane's handback to isolate checkout
        # drift. Real GitHub timestamps and clock skew are not observable.
        return handback + 3600

    monkeypatch.setattr(
        L, "_adopted_branch_first_pr_fn", first_pr_then_owner_switches,
    )
    result, calls = _adopt(repo, tmp_path)
    assert moved, "the pre-spawn session lookup was not exercised"
    assert _head_sha(repo) == other_head
    assert result["ok"] is False, result
    assert result["reason"] == "launch-cloud-checkout-off-base", result
    assert calls == []
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True
    assert lane["started"] is False
