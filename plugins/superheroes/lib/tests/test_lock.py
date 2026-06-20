import json
import os
import socket

import pytest

import file_lock as lock


def test_acquire_release(tmp_path):
    p = str(tmp_path / "state" / "engine.lock")
    lock.acquire(p)
    assert os.path.exists(p)
    holder = lock.read_holder(p)
    assert holder["pid"] == os.getpid()
    lock.release(p)
    assert not os.path.exists(p)


def test_contention_raises_with_holder_info(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    with pytest.raises(lock.LockHeld) as e:
        lock.acquire(p)
    assert e.value.holder["pid"] == os.getpid()
    lock.release(p)


def test_live_lock_is_not_stale(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)        # held by THIS live pid
    assert lock.is_stale(p) is False
    lock.release(p)


def test_dead_pid_lock_is_stale(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    h = lock.read_holder(p)
    h["pid"] = 99999999     # not a live pid
    h["acquiredAt"] = "1970-01-01T00:00:00Z"   # ancient -> expired by TTL (new stale = expired AND dead)
    json.dump(h, open(p, "w"))
    assert lock.is_stale(p) is True


def test_release_missing_is_noop(tmp_path):
    lock.release(str(tmp_path / "nope.lock"))  # must not raise


def test_acquire_steals_stale_dead_pid_holder(tmp_path):
    p = str(tmp_path / "engine.lock")
    with open(p, "w") as fh:
        json.dump({"pid": 999999, "host": socket.gethostname(),
                   "acquiredAt": "1970-01-01T00:00:00Z", "bootId": None}, fh)
    lock.acquire(p)                                     # stale -> stolen, no raise
    assert json.load(open(p))["pid"] == os.getpid()


def test_acquire_steals_on_bootid_mismatch(tmp_path, monkeypatch):
    p = str(tmp_path / "engine.lock")
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boot-A")
    with open(p, "w") as fh:
        json.dump({"pid": os.getpid(), "host": socket.gethostname(),
                   "acquiredAt": "1970-01-01T00:00:00Z", "bootId": "boot-OLD"}, fh)
    lock.acquire(p)                                     # rebooted -> stale -> stolen
    assert json.load(open(p))["bootId"] == "boot-A"


def test_live_holder_still_raises(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)                                     # we hold it, freshly, live pid
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)
