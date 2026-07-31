import json
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time

import pytest

import file_lock as lock

_LIB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def test_crash_during_holder_write_leaves_no_incomplete_lock(tmp_path):
    p = str(tmp_path / "engine.lock")
    script = textwrap.dedent(f"""
        import json, os, signal, sys
        sys.path.insert(0, {repr(_LIB_DIR)})
        import file_lock as lock

        def kill_at_dump(obj, fp, *args, **kwargs):
            os.kill(os.getpid(), signal.SIGKILL)

        json.dump = kill_at_dump
        lock.acquire({repr(p)})
    """)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        timeout=5,
    )
    assert proc.returncode != 0
    if os.path.exists(p):
        holder = lock.read_holder(p)
        assert isinstance(holder.get("pid"), int), (
            "crash during holder-write published an INCOMPLETE lock file"
        )
        assert isinstance(holder.get("host"), str), (
            "crash during holder-write published an INCOMPLETE lock file"
        )
    lock.acquire(p)
    assert lock.read_holder(p)["pid"] == os.getpid()
    lock.release(p)


def test_stranded_empty_lock_reclaimable_after_grace(tmp_path):
    p = str(tmp_path / "engine.lock")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    assert lock.is_stale(p) is True
    reclaimed = lock.acquire(p)
    assert reclaimed is True
    assert lock.read_holder(p)["pid"] == os.getpid()
    lock.release(p)


def test_fresh_malformed_lock_is_held_not_stolen(tmp_path):
    p = str(tmp_path / "engine.lock")
    open(p, "w").close()
    assert lock.is_stale(p) is False
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses chmod 000")
def test_read_failure_is_not_stale_chmod(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    h = lock.read_holder(p)
    h["acquiredAt"] = "1970-01-01T00:00:00Z"
    json.dump(h, open(p, "w"))
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    os.chmod(p, 0o000)
    try:
        assert lock.is_stale(p) is False
    finally:
        os.chmod(p, 0o600)


def test_read_failure_is_not_stale_monkeypatch(tmp_path, monkeypatch):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    h = lock.read_holder(p)
    h["acquiredAt"] = "1970-01-01T00:00:00Z"
    json.dump(h, open(p, "w"))
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    monkeypatch.setattr(lock, "_read_holder_state", lambda _path: ("read_error", None))
    assert lock.is_stale(p) is False


def test_non_dict_json_holder_past_grace_is_stale(tmp_path):
    p = str(tmp_path / "engine.lock")
    json.dump([], open(p, "w"))
    assert lock.read_holder(p) == {}
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    assert lock.is_stale(p) is True


def test_pid_not_int_coercible_past_grace_is_stale(tmp_path):
    p = str(tmp_path / "engine.lock")
    json.dump(
        {"pid": "not-a-pid", "host": socket.gethostname(),
         "acquiredAt": "1970-01-01T00:00:00Z"},
        open(p, "w"),
    )
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    assert lock.is_stale(p) is True


def test_host_not_str_past_grace_is_stale(tmp_path):
    p = str(tmp_path / "engine.lock")
    json.dump(
        {"pid": 999999, "host": [],
         "acquiredAt": "1970-01-01T00:00:00Z"},
        open(p, "w"),
    )
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    assert lock.is_stale(p) is True


def test_nonexistent_lock_path_is_not_stale(tmp_path):
    p = str(tmp_path / "missing.lock")
    assert lock.is_stale(p) is False


def test_fresh_acquire_returns_false(tmp_path):
    p = str(tmp_path / "engine.lock")
    assert lock.acquire(p) is False
    lock.release(p)


def test_acquire_succeeds_when_exists_check_lies_once(tmp_path, monkeypatch):
    """Finding 2: path exists at pre-check but vanishes before is_stale must not raise LockHeld."""
    p = str(tmp_path / "engine.lock")
    calls = 0
    real_exists = os.path.exists

    def fake_exists(path):
        nonlocal calls
        if path == p:
            calls += 1
            return calls == 1
        return real_exists(path)

    monkeypatch.setattr(os.path, "exists", fake_exists)
    assert lock.acquire(p) is False
    assert os.path.exists(p)
    lock.release(p)


def test_invalid_utf8_past_grace_is_stale_not_raised(tmp_path):
    p = str(tmp_path / "engine.lock")
    with open(p, "wb") as fh:
        fh.write(b"\xff\xfe invalid utf8")
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    assert lock.is_stale(p) is True


def test_out_of_range_pid_past_grace_is_stale(tmp_path):
    p = str(tmp_path / "engine.lock")
    cases = [0, -1, True, 1000000000000]
    for pid in cases:
        sub = str(tmp_path / f"pid-{pid!r}.lock")
        json.dump(
            {"pid": pid, "host": socket.gethostname(),
             "acquiredAt": "1970-01-01T00:00:00Z"},
            open(sub, "w"),
        )
        old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
        os.utime(sub, (old, old))
        assert lock.is_stale(sub) is True, f"pid={pid!r}"


def test_reclaim_blocked_while_guard_held_raises_lock_held(tmp_path):
    import fcntl

    p = str(tmp_path / "engine.lock")
    open(p, "w").close()
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    guard_path = p + ".reclaim"
    fd = os.open(guard_path, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        script = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {repr(_LIB_DIR)})
            import file_lock as lock
            try:
                lock.acquire({repr(p)})
                print("OK")
            except lock.LockHeld:
                print("HELD")
        """)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert proc.stdout.strip() == "HELD"
    finally:
        os.close(fd)


def test_concurrent_reclaim_grants_exactly_one_holder(tmp_path):
    p = str(tmp_path / "engine.lock")
    gate_dir = str(tmp_path / "gate")
    os.makedirs(gate_dir, exist_ok=True)
    n_workers = 16
    script = textwrap.dedent(f"""
        import os, sys, time
        sys.path.insert(0, {repr(_LIB_DIR)})
        import file_lock as lock
        _real_open = os.open
        def slow_open(path, flags, mode=0o666):
            if str(path).endswith(".reclaim"):
                time.sleep(0.02)
            return _real_open(path, flags, mode)
        if os.getpid() % 3 == 0:
            os.open = slow_open
        gate = {repr(gate_dir)}
        open(os.path.join(gate, str(os.getpid())), "w").close()
        deadline = time.time() + 5
        while len(os.listdir(gate)) < {n_workers}:
            if time.time() >= deadline:
                break
            time.sleep(0.001)
        try:
            lock.acquire({repr(p)})
            print("OK")
        except lock.LockHeld:
            print("HELD")
    """)

    n_rounds = 8
    for round_idx in range(n_rounds):
        for f in os.listdir(gate_dir):
            os.unlink(os.path.join(gate_dir, f))
        open(p, "w").close()
        old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
        os.utime(p, (old, old))
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", script],
                stdout=subprocess.PIPE,
                text=True,
            )
            for _ in range(n_workers)
        ]
        outcomes = []
        try:
            for worker_idx, proc in enumerate(procs):
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pytest.fail(
                        f"round {round_idx}: worker {worker_idx} timed out; "
                        f"outcomes so far: {outcomes}"
                    )
                outcomes.append(proc.stdout.read().strip())
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
        assert outcomes.count("OK") == 1, outcomes
        assert outcomes.count("HELD") == n_workers - 1, outcomes


def test_published_lock_mode_matches_umask(tmp_path):
    p = str(tmp_path / "engine.lock")
    umask = os.umask(0)
    os.umask(umask)
    try:
        lock.acquire(p)
        mode = os.stat(p).st_mode & 0o777
        assert mode == (0o644 & ~umask)
    finally:
        lock.release(p)
