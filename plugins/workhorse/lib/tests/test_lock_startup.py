# plugins/workhorse/lib/tests/test_lock_startup.py
import json
import os
import control_plane
import lock


def _store(tmp_path):
    return control_plane.ensure_store(str(tmp_path), root=str(tmp_path / "store"))


def test_startup_reacquire_same_process_is_reentrant(tmp_path):
    # A compaction-resume re-runs ⓪ in the SAME OS process, which still holds its own
    # startup.lock — that must read as re-entrant success, NOT "another loop holds this".
    s = _store(tmp_path)
    ok, _ = lock.acquire_startup(s)
    assert ok is True
    ok2, _ = lock.acquire_startup(s)            # same live process re-enters
    assert ok2 is True


def test_startup_different_live_process_fails_closed(tmp_path):
    # A DIFFERENT live holder (alive pid that isn't us, same host+boot) still fails closed.
    s = _store(tmp_path)
    with open(lock._startup_path(s), "w") as fh:
        json.dump({"pid": os.getppid(), "host": lock._host(),
                   "bootId": lock.hostinfo.boot_id()}, fh)
    ok, holder = lock.acquire_startup(s)
    assert ok is False and holder.get("pid") == os.getppid()


def test_startup_steals_stale_holder(tmp_path):
    s = _store(tmp_path)
    # plant a dead-pid holder
    with open(lock._startup_path(s), "w") as fh:
        json.dump({"pid": 999999, "host": lock._host(), "bootId": None}, fh)
    ok, _ = lock.acquire_startup(s)
    assert ok is True                            # stale -> stolen
    assert json.load(open(lock._startup_path(s)))["pid"] == os.getpid()


def test_startup_release_is_idempotent(tmp_path):
    s = _store(tmp_path)
    lock.acquire_startup(s)
    lock.release_startup(s)
    lock.release_startup(s)                       # no raise
    assert not os.path.exists(lock._startup_path(s))
