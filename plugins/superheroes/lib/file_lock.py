#!/usr/bin/env python3
"""File lock guarding concurrent engine applies (parallel worktree agents).
Stale reclaim (CONVENTIONS §4.4): a holder is stale when it is EXPIRED by TTL and its
pid is dead-on-this-boot, OR when its recorded bootId no longer matches (the host
rebooted, so the recorded pid is meaningless). A LIVE holder still raises LockHeld.
"""
import calendar
import json
import os
import socket
import time

import hostinfo

DEFAULT_TTL = 1800   # seconds


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
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _expired(acquired_at, ttl, now=None):
    try:
        t = calendar.timegm(time.strptime(acquired_at, "%Y-%m-%dT%H:%M:%SZ"))  # UTC->epoch (DST-safe)
    except (ValueError, TypeError):
        return True
    return (time.time() if now is None else now) - t > ttl


def is_stale(lock_path, ttl=DEFAULT_TTL, now=None):
    """Stale iff (bootId mismatch) OR (expired by TTL AND pid dead-on-this-host)."""
    h = read_holder(lock_path)
    if not h or h.get("host") != socket.gethostname() or not h.get("pid"):
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


def acquire(lock_path, ttl=DEFAULT_TTL):
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if not is_stale(lock_path, ttl):
            raise LockHeld(read_holder(lock_path)) from None
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise LockHeld(read_holder(lock_path)) from None
    with os.fdopen(fd, "w") as fh:
        json.dump(_holder_info(), fh)


def release(lock_path):
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass
