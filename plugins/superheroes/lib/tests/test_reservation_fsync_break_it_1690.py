"""A readable reservation does not erase a reported storage failure."""
import errno
import os

import launch_ledger as ll
from test_launcher import (
    L,
    _all_checks,
    _init_repo,
    _ledger_env,
    _valid_premise,
    _worktree_root,
)


def test_readable_reservation_with_failed_fsync_never_spawns(tmp_path, monkeypatch):
    # axis: a reservation whose real fsync fails must not reach the builder boundary.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    # Run outside the Claude host gate; this excludes instance-pin behavior,
    # which is independent of the storage guarantee exercised here.
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    ledger_file = ll.ledger_path(repo)["path"]
    real_fsync = ll.os.fsync
    failed_syncs = []

    def failing_ledger_fsync(fd):
        try:
            target = os.stat(ledger_file)
        except FileNotFoundError:
            return real_fsync(fd)
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) == (target.st_dev, target.st_ino):
            failed_syncs.append(fd)
            raise OSError(errno.EIO, "injected ledger sync failure")
        return real_fsync(fd)

    monkeypatch.setattr(ll.os, "fsync", failing_ledger_fsync)
    spawn_calls = []

    def observe_spawn(argv, cwd, out_fh, err_fh, child_env):
        # Observe the boundary without creating a builder process.
        spawn_calls.append(tuple(argv))
        raise OSError(errno.ECANCELED, "test creates no builder process")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=observe_spawn,
        max_attempts=1,
    )
    assert failed_syncs, "the test did not reach the ledger fsync"
    read_back = ll.read(repo)
    assert read_back["state"] == "ok"
    assert any(
        record.get("event") == "reserved"
        and record.get("launchId") == result["launchId"]
        for record in read_back["records"]
    )
    assert spawn_calls == [], "builder reached despite the reservation's failed fsync"
    assert result["ok"] is False, result
    assert result["reason"] == "ledger-append-failed", result
