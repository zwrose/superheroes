import errno
import json
import os
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


def test_acquire_succeeds_when_lock_vanishes_during_not_stale_check(tmp_path, monkeypatch):
    """Finding 1: lock exists at publish but vanishes before not-stale check must retry, not raise."""
    p = str(tmp_path / "engine.lock")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump(
            {"pid": os.getpid(), "host": socket.gethostname(),
             "acquiredAt": "2026-01-01T00:00:00Z", "bootId": None},
            fh,
        )
    real_is_stale = lock.is_stale

    def release_then_is_stale(path, ttl=lock.DEFAULT_TTL, **kwargs):
        lock.release(path)
        return real_is_stale(path, ttl, **kwargs)

    monkeypatch.setattr(lock, "is_stale", release_then_is_stale)
    assert lock.acquire(p) is False
    assert lock.read_holder(p)["pid"] == os.getpid()
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
    assert real_exists(p)
    assert lock.read_holder(p)["pid"] == os.getpid()
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
                print("BARRIER-TIMEOUT")
                sys.exit(1)
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
                outcome = proc.stdout.read().strip()
                if outcome == "BARRIER-TIMEOUT":
                    pytest.fail(
                        f"round {round_idx}: worker {worker_idx} hit barrier timeout; "
                        f"outcomes so far: {outcomes}"
                    )
                outcomes.append(outcome)
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


def test_published_lock_mode_is_owner_only(tmp_path):
    p = str(tmp_path / "engine.lock")
    original_umask = os.umask(0)
    os.umask(original_umask)
    try:
        for trial_umask in (original_umask, 0):
            os.umask(trial_umask)
            lock.acquire(p)
            try:
                mode = os.stat(p).st_mode & 0o777
                assert mode == 0o600
            finally:
                lock.release(p)
    finally:
        os.umask(original_umask)


def test_acquire_and_reclaim_survive_a_restrictive_umask(tmp_path):
    p = str(tmp_path / "engine.lock")
    original_umask = os.umask(0o777)
    try:
        lock.acquire(p)
        assert (os.stat(p).st_mode & 0o777) == 0o600
        lock.release(p)

        with open(p, "w") as fh:
            json.dump(
                {"pid": 999999, "host": socket.gethostname(),
                 "acquiredAt": "1970-01-01T00:00:00Z", "bootId": None},
                fh,
            )
        os.chmod(p, 0o600)
        reclaimed = lock.acquire(p)
        assert reclaimed is True
        assert lock.read_holder(p)["pid"] == os.getpid()
        lock.release(p)
    finally:
        os.umask(original_umask)


def test_read_holder_state_refuses_a_fifo_without_blocking(tmp_path):
    p = str(tmp_path / "engine.lock")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    os.mkfifo(p)
    start = time.monotonic()
    status, holder = lock._read_holder_state(p)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, "_read_holder_state blocked on FIFO"
    assert status == "unusable"
    assert holder is None
    start = time.monotonic()
    assert lock.read_holder(p) == {}
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, "read_holder blocked on FIFO"


def test_symlinked_lock_is_reclaimable_after_grace(tmp_path):
    p = str(tmp_path / "engine.lock")
    target = str(tmp_path / "holder-target.json")
    json.dump(
        {"pid": 999999, "host": socket.gethostname(),
         "acquiredAt": "1970-01-01T00:00:00Z", "bootId": None},
        open(target, "w"),
    )
    os.symlink(target, p)
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old), follow_symlinks=False)
    status, holder = lock._read_holder_state(p)
    assert status == "unusable"
    assert holder is None
    assert lock.is_stale(p) is True
    reclaimed = lock.acquire(p)
    assert reclaimed is True
    assert lock.read_holder(p)["pid"] == os.getpid()
    assert os.path.exists(target)
    assert not os.path.islink(p)
    lock.release(p)


def test_directory_at_lock_path_refuses_instead_of_raising(tmp_path):
    p = str(tmp_path / "engine.lock")
    os.makedirs(p)
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)
    assert os.path.isdir(p)


def test_reclaim_guard_refuses_a_symlinked_guard(tmp_path):
    p = str(tmp_path / "engine.lock")
    open(p, "w").close()
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old))
    sentinel = str(tmp_path / "sentinel")
    open(sentinel, "w").close()
    os.chmod(sentinel, 0o644)
    sentinel_mode_before = os.stat(sentinel).st_mode & 0o777
    os.symlink(sentinel, p + ".reclaim")
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)
    assert (os.stat(sentinel).st_mode & 0o777) == sentinel_mode_before


def test_dangling_symlink_lock_is_reclaimable_after_grace(tmp_path):
    p = str(tmp_path / "engine.lock")
    missing = str(tmp_path / "does-not-exist.json")
    os.symlink(missing, p)
    # Age the link's own mtime (not the target's — there is no target).
    old = time.time() - lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(p, (old, old), follow_symlinks=False)
    assert lock.is_stale(p) is True
    reclaimed = lock.acquire(p)
    assert reclaimed is True
    assert lock.read_holder(p)["pid"] == os.getpid()
    lock.release(p)


def test_acquire_raises_only_lock_held_when_publish_fails(tmp_path, monkeypatch):
    p = str(tmp_path / "engine.lock")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump(
            {"pid": os.getpid(), "host": socket.gethostname(),
             "acquiredAt": "2026-01-01T00:00:00Z", "bootId": None},
            fh,
        )

    def raise_enospc(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "no space")

    original_publish = lock._publish_lock
    monkeypatch.setattr(lock, "_publish_lock", raise_enospc)
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)

    def raise_eacces(*_args, **_kwargs):
        raise OSError(errno.EACCES, "permission denied")

    monkeypatch.setattr(lock, "_publish_lock", original_publish)
    monkeypatch.setattr(lock.os, "makedirs", raise_eacces)
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)


def test_boot_id_is_probed_once(monkeypatch):
    import hostinfo

    calls = 0
    real_open = open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/stat":
            raise FileNotFoundError()
        return real_open(path, *args, **kwargs)

    def fake_run(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        class Result:
            returncode = 0
            stdout = "{ sec = 1, usec = 0 }"
        return Result()

    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.setattr(hostinfo.subprocess, "run", fake_run)
    monkeypatch.setattr(hostinfo, "_boot_id_cache", hostinfo._UNSET)
    monkeypatch.setattr(hostinfo, "_boot_id_fail_until", 0.0)
    assert hostinfo.boot_id() == "boottime:sec:1"
    assert hostinfo.boot_id() == "boottime:sec:1"
    assert calls == 1


def test_boot_id_negative_cache_on_failure(monkeypatch):
    import hostinfo

    calls = 0
    real_open = open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/stat":
            raise FileNotFoundError()
        return real_open(path, *args, **kwargs)

    def fake_run(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        class Result:
            returncode = 1
            stdout = ""
        return Result()

    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.setattr(hostinfo.subprocess, "run", fake_run)
    monkeypatch.setattr(hostinfo, "_boot_id_cache", hostinfo._UNSET)
    monkeypatch.setattr(hostinfo, "_boot_id_fail_until", 0.0)
    assert hostinfo.boot_id() is None
    assert hostinfo.boot_id() is None
    assert calls == 1

    monkeypatch.setattr(hostinfo, "_boot_id_fail_until", 0.0)
    assert hostinfo.boot_id() is None
    assert calls == 2


def test_acquire_gethostname_oserror_raises_lock_held(tmp_path, monkeypatch):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    lock.release(p)

    def raise_gaierror(*_args, **_kwargs):
        raise OSError("gethostname failed")

    monkeypatch.setattr(lock.socket, "gethostname", raise_gaierror)
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)


def test_reclaim_guard_mode_is_owner_only(tmp_path):
    p = str(tmp_path / "engine.lock")
    with open(p, "w") as fh:
        json.dump(
            {"pid": 999999, "host": socket.gethostname(),
             "acquiredAt": "1970-01-01T00:00:00Z", "bootId": None},
            fh,
        )
    lock.acquire(p)
    guard_path = p + ".reclaim"
    assert os.path.exists(guard_path)
    assert (os.stat(guard_path).st_mode & 0o777) == 0o600
    lock.release(p)


# --- #862: confirmed-dead holder reclaim, without the TTL wait ------------------
# axis: what licenses reclaim — holder DEATH, not TTL expiry; a live or unsignalable holder
# is never reclaimed under either setting.


def _now_stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _rewrite_holder(path, **fields):
    h = lock.read_holder(path)
    h.update(fields)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(h, fh)
    return h


def test_dead_holder_inside_ttl_is_stale_only_when_opted_in(tmp_path):
    """A holder that is CONFIRMED dead is reclaimable immediately under the opt-in; the
    default keeps the TTL wait, so locks whose resource outlives the holder are unchanged."""
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, acquiredAt=_now_stamp())   # dead pid, well inside TTL
    assert lock.is_stale(p) is False
    assert lock.is_stale(p, reclaim_dead_holder=True) is True


def test_acquire_reclaims_dead_holder_inside_ttl_when_opted_in(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, acquiredAt=_now_stamp())
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)                                          # default: still waits out the TTL
    assert lock.acquire(p, reclaim_dead_holder=True) is True     # opt-in: reclaimed now
    assert lock.read_holder(p)["pid"] == os.getpid()
    lock.release(p)


def test_live_holder_is_never_reclaimed_even_past_ttl(tmp_path):
    """The invariant the short-circuit must not touch: a LIVE holder is never stale, however
    long it has held the lock and whichever setting the caller passes."""
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, acquiredAt="1970-01-01T00:00:00Z")        # ancient, but pid is this process
    try:
        assert lock.is_stale(p, ttl=1) is False
        assert lock.is_stale(p, ttl=1, reclaim_dead_holder=True) is False
        for kwargs in ({"ttl": 1}, {"ttl": 1, "reclaim_dead_holder": True}):
            with pytest.raises(lock.LockHeld) as e:
                lock.acquire(p, **kwargs)
            assert e.value.holder["pid"] == os.getpid()
    finally:
        lock.release(p)


def test_unsignalable_holder_is_not_reclaimed_by_the_short_circuit(tmp_path, monkeypatch):
    """A pid we may not signal is not CONFIRMED dead — the short-circuit fails closed."""
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, acquiredAt="1970-01-01T00:00:00Z")

    def deny(_pid, _sig):
        raise PermissionError(errno.EPERM, "not yours")

    monkeypatch.setattr(lock.os, "kill", deny)
    assert lock.is_stale(p, ttl=1) is False
    assert lock.is_stale(p, ttl=1, reclaim_dead_holder=True) is False


# axis: a terminated-but-unreaped holder is DEAD, not live — checked only on the opt-in path.


def _make_zombie():
    """A forked child that exited and stays unreaped: os.kill(pid, 0) still succeeds."""
    pid = os.fork()
    if pid == 0:                                   # pragma: no cover — child never returns
        os._exit(0)
    deadline = time.time() + 5
    while time.time() < deadline:
        out = subprocess.run(["ps", "-o", "state=", "-p", str(pid)],
                             capture_output=True, text=True)
        if (out.stdout or "").strip().startswith("Z"):
            return pid
        time.sleep(0.05)
    os.waitpid(pid, 0)
    pytest.skip("could not observe a zombie process on this host")


def test_zombie_holder_is_dead_under_the_opt_in(tmp_path):
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    pid = _make_zombie()
    try:
        os.kill(pid, 0)                            # precondition: still signalable
        _rewrite_holder(p, pid=pid, acquiredAt=_now_stamp())
        assert lock.is_stale(p) is False                              # default: unchanged
        assert lock.is_stale(p, reclaim_dead_holder=True) is True     # opt-in: reaps the wait
    finally:
        os.waitpid(pid, 0)


# --- #953: a hostname change must not wedge the lock, and one boot must read as one boot ---

_OTHER_HOST = "Mac-204.lan"          # the name this machine carried before it renamed itself
_LEGACY_BOOT_ID = "boottime:{ sec = 1786231679, usec = 113088 } Sat Aug  8 19:27:59 2026"


def _assert_other_host_differs():
    assert _OTHER_HOST != socket.gethostname(), "test fixture must name a DIFFERENT host"


def test_field_wedge_dead_holder_under_a_changed_hostname_is_stale(tmp_path):
    """The scenario observed live on 2026-08-09: the machine renamed itself mid-run
    (`Mac-204.lan` -> `ZWRMPB.local`), so every later reader saw a host mismatch and
    short-circuited to 'not stale' — the holder was dead and its TTL long gone, but the
    lock could never be reclaimed and `dispatch-abandon` could not release it."""
    _assert_other_host_differs()
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST,
                    acquiredAt="1970-01-01T00:00:00Z")     # dead pid + expired TTL + changed host
    assert lock.is_stale(p) is True


def test_acquire_reclaims_the_changed_hostname_wedge(tmp_path):
    _assert_other_host_differs()
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST, acquiredAt="1970-01-01T00:00:00Z")
    assert lock.acquire(p) is True                          # reclaimed, not wedged
    assert lock.read_holder(p)["pid"] == os.getpid()
    lock.release(p)


def test_cross_host_holder_inside_ttl_stays_protected(tmp_path):
    """The conservative direction the widening must keep: while the TTL is still live, a
    holder under another hostname is not reclaimable."""
    _assert_other_host_differs()
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST, acquiredAt=_now_stamp())
    assert lock.is_stale(p) is False
    with pytest.raises(lock.LockHeld):
        lock.acquire(p)


def test_cross_host_live_local_pid_brakes_reclaim_even_past_ttl(tmp_path):
    """The pid probe is kept across a host mismatch as a brake: a recorded pid that IS live
    in our namespace refuses reclaim however long the TTL has been up.

    What this does NOT prove — and cannot, since the probe reads only our own namespace — is
    that an arbitrary live foreign holder is protected past its TTL. It is not; see
    `test_expired_foreign_holder_reclaims_on_the_ttl_alone` for that accepted trade."""
    _assert_other_host_differs()
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, host=_OTHER_HOST, acquiredAt="1970-01-01T00:00:00Z")   # pid = this process
    try:
        assert lock.is_stale(p) is False
        assert lock.is_stale(p, reclaim_dead_holder=True) is False
        with pytest.raises(lock.LockHeld):
            lock.acquire(p, reclaim_dead_holder=True)
    finally:
        lock.release(p)


def test_cross_host_ignores_the_fast_path_however_the_boot_ids_compare(tmp_path, monkeypatch):
    """`reclaim_dead_holder` trades the TTL wait for CONFIRMED holder death — a
    confirmation no foreign-host record can supply, because `_pid_dead_on_this_host` reads
    OUR pid namespace and not the holder's. A matching boot id does not change that: it is
    not evidence of a shared pid namespace (containers on one kernel share the host's
    `btime` while differing in hostname AND pid namespace; two hosts can boot in the same
    second). Across a host mismatch the TTL wait is mandatory whatever the boot ids say."""
    _assert_other_host_differs()
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:1786231679")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST, acquiredAt=_now_stamp())
    # pinned, not assumed: an environment where boot_id() is None would leave both sides
    # uncorroborated and the equal-id branch below would pass without exercising anything.
    assert lock.read_holder(p)["bootId"] == "boottime:sec:1786231679"
    assert lock.is_stale(p, reclaim_dead_holder=True) is False        # boot ids EQUAL
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:2000000000")
    assert lock.is_stale(p, reclaim_dead_holder=True) is False        # boot ids DIFFERENT


def test_equal_boot_ids_do_not_expose_a_foreign_namespace_holder(tmp_path, monkeypatch):
    """The round-2 review case: hostname differs, boot ids are equal, and the recorded pid
    is absent in the reader's namespace — two containers on one kernel sharing a lock path.
    Inside its TTL that holder stays protected; equal boot ids must not be read as proof
    that the reader may probe the holder's pid."""
    _assert_other_host_differs()
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:1786231679")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST, acquiredAt=_now_stamp())
    # the equality this regression turns on is pinned, not inherited from the environment:
    # boot_id() may legitimately return None, and None never corroborates.
    assert lock.read_holder(p)["bootId"] == "boottime:sec:1786231679"
    assert lock.is_stale(p) is False
    assert lock.is_stale(p, reclaim_dead_holder=True) is False
    with pytest.raises(lock.LockHeld):
        lock.acquire(p, reclaim_dead_holder=True)


def test_expired_foreign_holder_reclaims_on_the_ttl_alone(tmp_path, monkeypatch):
    """The accepted residual, pinned rather than hidden (review finding, #953).

    A holder on a foreign hostname cannot be probed for liveness: `_pid_dead_on_this_host`
    reads OUR pid namespace, so a pid absent here is not evidence that a remote holder
    died. Past its TTL such a holder is reclaimed anyway — TTL expiry is the only clock
    both sides share, and it is the cross-host rule the issue ratified. A genuinely live
    remote holder can therefore lose an expired lock. That is reachable only where a lock
    path is shared between machines or pid namespaces, which neither caller's path is (a
    local run dir; a lease under the local tempdir). Change this assertion only with that
    trade re-decided."""
    _assert_other_host_differs()
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:2000000000")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST,          # a pid absent on this machine
                    acquiredAt="1970-01-01T00:00:00Z", bootId="boottime:sec:1786231679")
    assert lock.is_stale(p) is True


def test_cross_host_boot_id_mismatch_alone_is_not_stale(tmp_path, monkeypatch):
    """A genuinely different machine mismatches on bootId every read. Letting that leg
    fire across a host mismatch would reclaim a live remote holder on sight."""
    _assert_other_host_differs()
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:2000000000")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST,
                    acquiredAt=_now_stamp(), bootId="boottime:sec:1786231679")
    assert lock.is_stale(p) is False


def test_same_host_reboot_still_reclaims_on_sight(tmp_path, monkeypatch):
    """Unchanged behaviour: on THIS host a bootId mismatch means the recorded pid belongs
    to a previous boot and is meaningless, so the holder is stale with no TTL wait."""
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:2000000000")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)                                        # holder pid is this LIVE process
    _rewrite_holder(p, acquiredAt=_now_stamp(), bootId="boottime:sec:1786231679")
    assert lock.is_stale(p) is True


def test_boottime_usec_jitter_does_not_read_as_a_reboot(tmp_path, monkeypatch):
    """macOS `kern.boottime` renders a `usec` leg that has been observed to shift between
    reads of one boot. Compared raw, that read as 'the host rebooted' and made a LIVE
    holder stale — reclaiming a lock out from under a running process."""
    monkeypatch.setattr(
        lock.hostinfo, "boot_id",
        lambda: "boottime:{ sec = 1786231679, usec = 990001 } Sat Aug  8 19:27:59 2026")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)                                        # holder pid is this LIVE process
    _rewrite_holder(p, acquiredAt=_now_stamp(), bootId=_LEGACY_BOOT_ID)
    try:
        assert lock.is_stale(p) is False
    finally:
        lock.release(p)


def test_legacy_boot_id_still_matches_the_recorded_form(tmp_path, monkeypatch):
    """Upgrade path: lock files written before this change carry the full rendered
    boottime. A reader recording the truncated form must still see them as the same boot,
    or every pre-existing lock reads as rebooted the moment the new code lands."""
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: "boottime:sec:1786231679")
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, acquiredAt=_now_stamp(), bootId=_LEGACY_BOOT_ID)
    try:
        assert lock.is_stale(p) is False
    finally:
        lock.release(p)


def test_boot_id_records_the_stable_truncated_form(monkeypatch):
    import hostinfo

    real_open = open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/stat":
            raise FileNotFoundError()
        return real_open(path, *args, **kwargs)

    class Result:
        returncode = 0
        stdout = "{ sec = 1786231679, usec = 113088 } Sat Aug  8 19:27:59 2026\n"

    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.setattr(hostinfo.subprocess, "run", lambda *a, **k: Result())
    monkeypatch.setattr(hostinfo, "_boot_id_cache", hostinfo._UNSET)
    monkeypatch.setattr(hostinfo, "_boot_id_fail_until", 0.0)
    assert hostinfo.boot_id() == "boottime:sec:1786231679"


def test_same_boot_folds_jitter_and_keeps_real_differences():
    import hostinfo

    jittered = "boottime:{ sec = 1786231679, usec = 990001 } Sat Aug  8 19:27:59 2026"
    assert hostinfo.same_boot(_LEGACY_BOOT_ID, jittered) is True
    assert hostinfo.same_boot(_LEGACY_BOOT_ID, "boottime:sec:1786231679") is True
    # a real reboot moves the whole second, and must still read as a different boot
    assert hostinfo.same_boot(_LEGACY_BOOT_ID, "boottime:sec:1786231680") is False
    assert hostinfo.same_boot("btime:1786231679", "btime:1786231680") is False
    assert hostinfo.same_boot("btime:1786231679", "btime:1786231679") is True


def test_same_boot_does_not_read_the_usec_leg_as_the_sec_leg():
    """The `usec` leg is a `sec` substring; folding on it would call two different boots
    the same boot whenever their usec happened to agree."""
    import hostinfo

    a = "boottime:{ sec = 100, usec = 500 } Sat Aug  8 19:27:59 2026"
    b = "boottime:{ sec = 200, usec = 500 } Sat Aug  8 19:28:00 2026"
    assert hostinfo.same_boot(a, b) is False
    assert hostinfo._normalize(a) == "boottime:sec:100"
    assert hostinfo._normalize(b) == "boottime:sec:200"
    # A render carrying ONLY the jittering leg has no sec leg to fold to, and must not
    # borrow the usec digits as one — that would equate two ids the render never claimed
    # were the same boot. (Ordering hides this in a full render, where `sec` is matched
    # first either way; the check has to put `usec` where nothing else can match.)
    assert hostinfo._normalize("boottime:{ usec = 500 }") == "boottime:{ usec = 500 }"
    assert hostinfo.same_boot("boottime:{ usec = 500 }", "boottime:{ sec = 500 }") is False


def test_same_boot_is_none_when_either_side_cannot_corroborate():
    """None means 'cannot corroborate' — callers degrade on it; it is never a match."""
    import hostinfo

    assert hostinfo.same_boot(None, "boottime:sec:1") is None
    assert hostinfo.same_boot("boottime:sec:1", None) is None
    assert hostinfo.same_boot("", "boottime:sec:1") is None
    assert hostinfo.same_boot(12345, "boottime:sec:1") is None
    assert hostinfo.same_boot("boottime:sec:1", "   ") is None


def test_unrecognized_boot_id_render_compares_exactly():
    """Anything the normalizer does not recognize falls through unchanged rather than
    folding to something coarser — an unparsed render must never widen a match."""
    import hostinfo

    assert hostinfo.same_boot("boottime:mystery", "boottime:mystery") is True
    assert hostinfo.same_boot("boottime:mystery", "boottime:other") is False


def test_missing_boot_id_leaves_the_ttl_leg_in_charge(tmp_path, monkeypatch):
    """boot_id() returning None ('cannot corroborate') must not itself make a holder
    stale, on either side of a host mismatch."""
    _assert_other_host_differs()
    monkeypatch.setattr(lock.hostinfo, "boot_id", lambda: None)
    p = str(tmp_path / "engine.lock")
    lock.acquire(p)
    _rewrite_holder(p, acquiredAt=_now_stamp(), bootId=None)      # live pid, inside TTL
    assert lock.is_stale(p) is False
    _rewrite_holder(p, pid=99999999, host=_OTHER_HOST,
                    acquiredAt="1970-01-01T00:00:00Z", bootId=None)
    assert lock.is_stale(p) is True                                # TTL leg still reclaims
