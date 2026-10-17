"""Exercise checkout movement during the final cloud remote lookup."""
import os

import launch_ledger as ll

from test_launcher import L, _head_sha, _valid_premise
from test_launcher_cloud import (
    _cloud_repo,
    _fake_spawn,
    _git,
    _lanes,
    _launch,
    _local_remote_has,
)
from test_launcher_cloud_checkout import _commit


def test_final_remote_lookup_cannot_accept_a_stale_local_checkout(tmp_path, monkeypatch):
    # axis: movement during the final remote lookup refuses without altering owner work.
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
    monkeypatch.setattr(L, "_base_on_remote_fn", _local_remote_has)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    repo = _cloud_repo(tmp_path)
    base = _head_sha(repo)
    original_branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
    _git(repo, "checkout", "-q", "-b", "owner-work")
    other_head = _commit(repo, "owner.txt")
    assert other_head != base
    _git(repo, "checkout", "-q", original_branch)

    tracked = tmp_path / "repo" / "file.txt"
    untracked = tmp_path / "repo" / "untracked.txt"
    tracked.write_text("staged owner work\n")
    _git(repo, "add", "file.txt")
    tracked.write_text("unstaged owner work\n")
    untracked.write_text("untracked owner work\n")

    def owner_work():
        return (
            tracked.read_bytes(),
            untracked.read_bytes(),
            _git(repo, "diff", "--cached"),
            _git(repo, "diff"),
            _git(repo, "status", "--porcelain"),
        )

    before = owner_work()
    real_remote_head = L._remote_branch_head_fn
    lookups = []
    moved = []

    def remote_head_then_owner_switches(repo_root, branch, env):
        answer = real_remote_head(repo_root, branch, env)
        lookups.append(branch)
        if len(lookups) == 2:
            assert answer == (base, None)
            # Deterministic interleaving: the owner switches while the final lookup is pending.
            _git(repo, "checkout", "-q", "owner-work")
            moved.append(True)
        return answer

    monkeypatch.setattr(L, "_remote_branch_head_fn", remote_head_then_owner_switches)
    calls = []
    result = _launch(
        repo, tmp_path, _fake_spawn(calls=calls),
        premise=_valid_premise(repo, baseCommit=base),
    )

    assert moved, "the final remote-lookup interleaving was not exercised"
    assert _head_sha(repo) == other_head
    assert owner_work() == before
    assert result["ok"] is False, result
    assert result["reason"] == "launch-cloud-checkout-off-base"
    assert result["checkoutHead"] == other_head
    assert calls == []
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True
    assert lane["started"] is False
