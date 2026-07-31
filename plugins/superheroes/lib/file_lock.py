#!/usr/bin/env python3
"""File lock guarding concurrent engine applies (parallel worktree agents).
Stale reclaim: a holder is stale when it is EXPIRED by TTL and its
pid is dead-on-this-boot, OR when its bootId no longer matches (the host
rebooted, so the recorded pid is meaningless). A LIVE holder still raises LockHeld.
"""
import calendar
import fcntl
import json
import os
import socket
import tempfile
import time

import hostinfo

DEFAULT_TTL = 1800   # seconds
MALFORMED_GRACE_SECONDS = 60


class LockHeld(Exception):
    def __init__(self, holder):
        self.holder = holder or {}
        super().__init__(f"engine lock held by {self.holder}")


def _holder_info():
    return {"pid": os.getpid(), "host": socket.gethostname(),
            "acquiredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "bootId": hostinfo.boot_id(), "ttl": DEFAULT_TTL}


def read_holder(lock_path):
    try:
        with open(lock_path) as fh:
            parsed = json.load(fh)
    except (OSError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _read_holder_state(lock_path):
    """Distinguish read failure from successfully read but unusable content."""
    try:
        with open(lock_path) as fh:
            raw = fh.read()
    except OSError:
        return "read_error", None
    except UnicodeError:
        return "unusable", None
    if not raw or not raw.strip():
        return "unusable", None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return "unusable", None
    if not isinstance(parsed, dict):
        return "unusable", None
    return "ok", parsed


def _holder_fields_unusable(holder):
    pid = holder.get("pid")
    if pid is None:
        return True
    if isinstance(pid, bool):
        return True
    try:
        pid_int = int(pid)
    except (TypeError, ValueError, OverflowError):
        return True
    if pid_int <= 0 or pid_int > 2**31 - 1:
        return True
    host = holder.get("host")
    if host is None or not isinstance(host, str):
        return True
    return False


def _malformed_past_grace(lock_path, now=None):
    try:
        st = os.stat(lock_path)
    except OSError:
        return False
    now = time.time() if now is None else now
    return now - st.st_mtime > MALFORMED_GRACE_SECONDS


def _expired(acquired_at, ttl, now=None):
    try:
        t = calendar.timegm(time.strptime(acquired_at, "%Y-%m-%dT%H:%M:%SZ"))  # UTC->epoch (DST-safe)
    except (ValueError, TypeError):
        return True
    return (time.time() if now is None else now) - t > ttl


def is_stale(lock_path, ttl=DEFAULT_TTL, now=None):
    """Stale iff (bootId mismatch) OR (expired by TTL AND pid dead-on-this-host)
    OR (malformed holder past grace window)."""
    if not os.path.exists(lock_path):
        return False
    status, holder = _read_holder_state(lock_path)
    if status == "read_error":
        return False
    if status == "unusable" or _holder_fields_unusable(holder):
        return _malformed_past_grace(lock_path, now)
    h = holder
    if h.get("host") != socket.gethostname():
        return False
    bid, cur = h.get("bootId"), hostinfo.boot_id()
    if bid is not None and cur is not None and bid != cur:
        return True
    if not _expired(h.get("acquiredAt"), ttl, now):
        return False
    try:
        os.kill(int(h["pid"]), 0)
    except ProcessLookupError:
        return True
    except (PermissionError, ValueError, OverflowError):
        return False
    return False


def _publish_lock(lock_path, holder_info):
    directory = os.path.dirname(os.path.abspath(lock_path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".lock-publish-", dir=directory)
    try:
        try:
            with os.fdopen(fd, "w") as fh:
                fd = -1
                json.dump(holder_info, fh)
                fh.flush()
                os.fchmod(fh.fileno(), 0o600)
                os.fsync(fh.fileno())
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        os.link(tmp, lock_path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _reclaim_stale_lock(lock_path, ttl):
    guard_path = lock_path + ".reclaim"
    fd = os.open(guard_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        if not is_stale(lock_path, ttl):
            return False
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass
        try:
            _publish_lock(lock_path, _holder_info())
        except FileExistsError:
            return False
        return True
    finally:
        os.close(fd)


ACQUIRE_RETRY_LIMIT = 3


def acquire(lock_path, ttl=DEFAULT_TTL):
    """Acquire the lock. Returns True if a stale lock was reclaimed, else False."""
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    for _ in range(ACQUIRE_RETRY_LIMIT):
        try:
            _publish_lock(lock_path, _holder_info())
            return False
        except FileExistsError:
            pass
        if not is_stale(lock_path, ttl):
            if not os.path.exists(lock_path):
                continue
            raise LockHeld(read_holder(lock_path)) from None
        if _reclaim_stale_lock(lock_path, ttl):
            return True
        if not os.path.exists(lock_path):
            continue
        raise LockHeld(read_holder(lock_path)) from None
    raise LockHeld(read_holder(lock_path)) from None


def release(lock_path):
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass
