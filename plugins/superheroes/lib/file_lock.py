#!/usr/bin/env python3
"""File lock guarding concurrent engine applies (parallel worktree agents).
Stale reclaim: a holder is stale when it is EXPIRED by TTL and its
pid is dead-on-this-boot, OR when its bootId no longer matches (the host
rebooted, so the recorded pid is meaningless). A LIVE holder still raises LockHeld.

`reclaim_dead_holder=True` (#862) drops the TTL wait for a holder whose pid is
CONFIRMED dead on this host: the TTL only ever delayed reclaim of a holder that was
already gone, and on a lock whose holder is the only worker (engine_dispatch's
`run.lock`) that delay is pure re-attach latency. It is opt-in, not the default,
because some locks guard a resource a child process keeps using after the holder
dies (engine_dispatch's worktree lease) — there, holder death alone is not evidence
the resource is free, and those call sites keep the TTL wait. The refusal to reclaim
a LIVE holder is unconditional either way.
"""
import calendar
import errno
import fcntl
import json
import os
import socket
import stat
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
    status, holder = _read_holder_state(lock_path)
    return holder if status == "ok" else {}


def _read_holder_state(lock_path):
    """Distinguish read failure from successfully read but unusable content."""
    fd = -1
    try:
        fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return "unusable", None
        with os.fdopen(fd) as fh:
            fd = -1
            raw = fh.read()
    except OSError as e:
        # ELOOP: symlink refused by O_NOFOLLOW — unlink removes the link, not its
        # target, so reclaim is safe. EACCES/EPERM: cannot read a real lock file
        # we may be obliged to respect; fail closed as held, not malformed.
        if e.errno in (errno.ELOOP, errno.ENXIO):
            return "unusable", None
        return "read_error", None
    except UnicodeError:
        return "unusable", None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
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
        st = os.lstat(lock_path)
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


def _pid_dead_on_this_host(holder):
    """True only when the recorded pid is CONFIRMED dead. A pid we may not signal
    (PermissionError) or cannot read is treated as live — fail closed."""
    try:
        os.kill(int(holder["pid"]), 0)
    except ProcessLookupError:
        return True
    except (PermissionError, ValueError, OverflowError, KeyError, TypeError):
        return False
    return False


def is_stale(lock_path, ttl=DEFAULT_TTL, now=None, reclaim_dead_holder=False):
    """Stale iff (bootId mismatch) OR (expired by TTL AND pid dead-on-this-host)
    OR (malformed holder past grace window).

    With `reclaim_dead_holder=True` a pid dead-on-this-host is stale immediately, with
    no TTL wait (#862). A LIVE holder is never stale under either setting."""
    if not os.path.lexists(lock_path):
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
    if not reclaim_dead_holder and not _expired(h.get("acquiredAt"), ttl, now):
        return False
    return _pid_dead_on_this_host(h)


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


def _reclaim_stale_lock(lock_path, ttl, reclaim_dead_holder=False):
    guard_path = lock_path + ".reclaim"
    try:
        fd = os.open(guard_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        return False
    try:
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return False
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
        except OSError:
            return False
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        if not is_stale(lock_path, ttl, reclaim_dead_holder=reclaim_dead_holder):
            return False
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass
        except OSError:
            return False
        try:
            _publish_lock(lock_path, _holder_info())
        except OSError:
            return False
        return True
    finally:
        os.close(fd)


ACQUIRE_RETRY_LIMIT = 3


def acquire(lock_path, ttl=DEFAULT_TTL, reclaim_dead_holder=False):
    """Acquire the lock. Returns True if a stale lock was reclaimed, else False.

    `reclaim_dead_holder=True` reclaims a confirmed-dead holder without waiting out the
    TTL (#862); a live holder still raises LockHeld.

    Raises only LockHeld — never propagates OSError from publish or directory setup."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    except OSError:
        raise LockHeld({}) from None
    for _ in range(ACQUIRE_RETRY_LIMIT):
        try:
            try:
                _publish_lock(lock_path, _holder_info())
                return False
            except OSError:
                pass
            if not is_stale(lock_path, ttl, reclaim_dead_holder=reclaim_dead_holder):
                if not os.path.lexists(lock_path):
                    continue
                raise LockHeld(read_holder(lock_path)) from None
            if _reclaim_stale_lock(lock_path, ttl, reclaim_dead_holder=reclaim_dead_holder):
                return True
            if not os.path.lexists(lock_path):
                continue
            raise LockHeld(read_holder(lock_path)) from None
        except OSError:
            raise LockHeld(read_holder(lock_path)) from None
    raise LockHeld(read_holder(lock_path)) from None


def release(lock_path):
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass
