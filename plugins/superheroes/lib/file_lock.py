#!/usr/bin/env python3
"""File lock guarding concurrent engine applies (parallel worktree agents).
Stale reclaim: a holder is stale when it is EXPIRED by TTL and its
pid is dead-on-this-boot, OR when its bootId no longer matches (the host
rebooted, so the recorded pid is meaningless). A LIVE holder on THIS host still raises
LockHeld; a foreign-host holder's protection is its TTL (next paragraph).

A holder recorded under a different hostname is reclaimable on the TTL leg alone —
never on the dead-holder fast path and never on a bootId mismatch (#953). Treating a
host mismatch as "not stale" wedged locks permanently the first time a laptop renamed
itself mid-run, which is the normal case on a machine that changes networks. The
"never a LIVE holder" guarantee below is therefore exact only for a SAME-HOST holder,
whose pid we can actually probe; for a foreign-host holder the guarantee is its TTL,
and a live one past that TTL can be reclaimed. Nothing shares these lock paths across
machines or pid namespaces today, which is what makes that trade acceptable.

`reclaim_dead_holder=True` (#862) drops the TTL wait for a holder whose pid is
CONFIRMED dead on this host: the TTL only ever delayed reclaim of a holder that was
already gone, and on a lock whose holder is the only worker (engine_dispatch's
`run.lock`) that delay is pure re-attach latency. It is opt-in, not the default,
because some locks guard a resource a child process keeps using after the holder
dies (engine_dispatch's worktree lease) — there, holder death alone is not evidence
the resource is free, and those call sites keep the TTL wait. For a SAME-HOST holder
the refusal to reclaim a LIVE one is unconditional under either setting; a foreign-host
holder's protection is its TTL, per the paragraph above.
"""
import calendar
import errno
import fcntl
import json
import os
import socket
import stat
import subprocess
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


def _pid_is_zombie(pid):
    """A terminated-but-unreaped holder still answers signal 0. Ambiguity is live —
    fail closed. (engine_dispatch._process_alive makes the same distinction; file_lock
    cannot import it — engine_dispatch imports this module.)"""
    try:
        out = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:
        return False
    if out.returncode != 0:
        return False
    return (out.stdout or "").strip().startswith("Z")


def _pid_dead_on_this_host(holder, zombie_is_dead=False):
    """True only when the recorded pid is CONFIRMED dead. A pid we may not signal
    (PermissionError) or cannot read is treated as live — fail closed."""
    try:
        pid = int(holder["pid"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, ValueError, OverflowError):
        return False
    return bool(zombie_is_dead) and _pid_is_zombie(pid)


def is_stale(lock_path, ttl=DEFAULT_TTL, now=None, reclaim_dead_holder=False):
    """Stale iff (bootId mismatch on this host) OR (expired by TTL AND pid
    dead-on-this-host) OR (malformed holder past grace window).

    With `reclaim_dead_holder=True` a pid dead-on-this-host is stale immediately, with
    no TTL wait (#862) — same-host holders only. A LIVE holder on THIS host is never
    stale under either setting; a live holder on a foreign hostname is protected by its
    TTL, not by the pid probe, which cannot reach another machine's pid namespace."""
    if not os.path.lexists(lock_path):
        return False
    status, holder = _read_holder_state(lock_path)
    if status == "read_error":
        return False
    if status == "unusable" or _holder_fields_unusable(holder):
        return _malformed_past_grace(lock_path, now)
    h = holder
    # Two categories from here on (a malformed holder was settled above), and they are not
    # the same. SAME HOST: everything below is grounded —
    # our pid namespace is the holder's, so death is provable and the reboot check means what
    # it says. FOREIGN HOST: `host` is not a machine identity (a laptop changing networks
    # renames itself mid-run, #953), but neither is it evidence of a shared pid namespace —
    # containers on one kernel differ in hostname AND pid namespace while sharing a boot id,
    # so boot equality cannot license a pid probe. Reclaim there rests on TTL expiry alone.
    same_host = h.get("host") == socket.gethostname()
    if same_host and hostinfo.same_boot(h.get("bootId"), hostinfo.boot_id()) is False:
        return True   # this host rebooted: the recorded pid is from a dead boot
    # Two legs stay SAME-HOST-ONLY, both because they read the local pid namespace as if it
    # were the holder's: the reboot check above, and the `reclaim_dead_holder` fast path below
    # — whose whole trade is swapping the TTL wait for CONFIRMED death, a confirmation no
    # foreign-host record can supply. A foreign holder therefore always waits out its TTL.
    if not (reclaim_dead_holder and same_host) and not _expired(h.get("acquiredAt"), ttl, now):
        return False
    # Same host: holder DEATH is what licenses reclaim, never TTL expiry alone, and a live
    # holder is never stale. Foreign host: `_pid_dead_on_this_host` cannot prove a remote
    # holder died — a pid absent here may be alive there — so it stands only as a brake that
    # can refuse reclaim, and TTL expiry is what actually licenses it. That is the ratified
    # cross-host rule (#953) and the only clock both sides share, but it does mean a live
    # foreign holder can lose an expired lock. Accepted and disclosed rather than hidden;
    # reachable only where a lock path is shared between machines or pid namespaces, which
    # neither caller's path is today (a local run dir; a lease under the local tempdir).
    return _pid_dead_on_this_host(h, zombie_is_dead=reclaim_dead_holder)


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
    TTL (#862); a live holder on THIS host still raises LockHeld (a foreign-host holder is
    protected by its TTL instead — see the module docstring).

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
