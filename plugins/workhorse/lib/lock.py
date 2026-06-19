# plugins/workhorse/lib/lock.py
"""The work-item lock (CONVENTIONS §4.4 / §4.5).

Ref-lease (§4.4): a leased git ref `refs/superheroes/locks/<work-item>` in the
per-checkout control-plane store. The lease JSON is stored as a git BLOB; the ref
points at that blob; reclaim is an atomic compare-and-swap via
`git update-ref <ref> <newblob> <oldblob>` (the oldvalue precondition). `generation`
is the fence token mirrored into checkpoint.lockGeneration.

Startup per-checkout lock (§4.5) lives in lock_startup.py-style helpers added in
Task 4 (same module).
"""
import calendar
import json
import os
import socket
import time

import hostinfo

LOCK_REF_PREFIX = "refs/superheroes/locks/"
DEFAULT_TTL = 1800   # seconds (~30 min, > the longest phase)
_ZERO = "0" * 40


def _host():
    return socket.gethostname()


def _now_epoch(now=None):
    return time.time() if now is None else now


def _stamp(now=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_now_epoch(now)))


def _ref(work_item):
    return LOCK_REF_PREFIX + work_item


def _git(store, *args, stdin=None):
    import subprocess
    try:
        return subprocess.run(["git", "-C", store, *args], capture_output=True,
                              text=True, timeout=10, input=stdin)
    except (OSError, subprocess.SubprocessError):
        class _Fail:
            returncode = 1
            stdout = ""
            stderr = "git invocation failed"
        return _Fail()


def read_lease(store, work_item):
    """(blob_sha, lease_dict) — (None, None) if the ref is absent; (sha, None) if
    the blob is unreadable."""
    r = _git(store, "rev-parse", "--verify", "--quiet", _ref(work_item))
    if r.returncode != 0 or not r.stdout.strip():
        return (None, None)
    sha = r.stdout.strip()
    b = _git(store, "cat-file", "blob", sha)
    if b.returncode != 0:
        return (sha, None)
    try:
        return (sha, json.loads(b.stdout))
    except ValueError:
        return (sha, None)


def _write_blob(store, lease):
    r = _git(store, "hash-object", "-w", "--stdin", stdin=json.dumps(lease))
    return r.stdout.strip() if r.returncode == 0 else None


def _cas(store, work_item, lease, old_sha):
    """Point the ref at a new blob iff it currently equals old_sha (atomic CAS).
    old_sha=None means 'must not exist' (create). Returns True on success."""
    newblob = _write_blob(store, lease)
    if newblob is None:
        return False
    old = _ZERO if old_sha is None else old_sha
    r = _git(store, "update-ref", _ref(work_item), newblob, old)
    return r.returncode == 0


def _force_lease(store, work_item, lease):
    """TEST/recovery helper: unconditionally point the ref at a lease blob."""
    newblob = _write_blob(store, lease)
    _git(store, "update-ref", _ref(work_item), newblob)


def _expired(acquired_at, ttl, now=None):
    try:
        t = calendar.timegm(time.strptime(acquired_at, "%Y-%m-%dT%H:%M:%SZ"))  # UTC->epoch (DST-safe)
    except (ValueError, TypeError):
        return True   # unparseable timestamp -> treat as expired
    return _now_epoch(now) - t > ttl


def _pid_dead(lease):
    """True iff the holder's pid is provably not this-boot-alive."""
    if lease.get("host") != _host():
        return True                              # different host -> can't be our live pid
    bid = lease.get("bootId")
    cur = hostinfo.boot_id()
    if bid is not None and cur is not None and bid != cur:
        return True                              # rebooted -> recorded pid is meaningless
    pid = lease.get("pid")
    if not pid:
        return True
    try:
        os.kill(int(pid), 0)
        return False                             # alive
    except (ProcessLookupError, ValueError, OverflowError):
        return True
    except PermissionError:
        return False                             # alive (owned by another user)


def is_stale(lease, ttl, now=None):
    """Stale iff EXPIRED *and* the holder pid is dead-on-this-boot (§4.4)."""
    if not isinstance(lease, dict):
        return True
    return _expired(lease.get("acquiredAt"), ttl, now) and _pid_dead(lease)


def _lease_obj(generation, ttl, now=None):
    return {"pid": os.getpid(), "host": _host(), "bootId": hostinfo.boot_id(),
            "acquiredAt": _stamp(now), "generation": generation, "ttl": ttl}


def acquire(store, work_item, ttl=DEFAULT_TTL, now=None):
    """(ok, generation, reason). Create-if-absent or CAS-steal-if-stale; a live
    holder -> (False, gen, 'held')."""
    sha, lease = read_lease(store, work_item)
    if sha is None:                               # absent -> create
        if _cas(store, work_item, _lease_obj(1, ttl, now), None):
            return (True, 1, "created")
        return (False, 0, "lost-create-cas")      # someone created concurrently
    if lease is not None and not is_stale(lease, ttl, now):
        return (False, lease.get("generation", 0), "held")
    gen = (lease.get("generation", 0) if lease else 0) + 1
    if _cas(store, work_item, _lease_obj(gen, ttl, now), sha):   # CAS on the stale blob
        return (True, gen, "stolen")
    return (False, gen, "lost-steal-cas")         # concurrent reclaimer won


def renew(store, work_item, generation, ttl=DEFAULT_TTL, now=None):
    """Heartbeat: re-stamp acquiredAt keeping `generation`, via CAS. False if
    superseded (we no longer hold it)."""
    sha, lease = read_lease(store, work_item)
    if not lease or lease.get("generation") != generation:
        return False
    obj = _lease_obj(generation, ttl, now)
    return _cas(store, work_item, obj, sha)


def fence_ok(store, work_item, generation):
    """Our generation still current? (call before any external write — §4.4 fence)."""
    _, lease = read_lease(store, work_item)
    return bool(lease) and lease.get("generation") == generation


# --- §4.5 startup per-checkout lock (append to plugins/workhorse/lib/lock.py) ---

def _startup_path(store):
    return os.path.join(store, "startup.lock")


def _startup_holder(store):
    try:
        with open(_startup_path(store), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _startup_obj():
    return {"pid": os.getpid(), "host": _host(), "bootId": hostinfo.boot_id()}


def acquire_startup(store):
    """One active loop per checkout (§4.5). O_EXCL create; if held, steal iff the
    holder is stale (pid dead-on-this-boot), else fail closed. Returns
    (ok, holder_if_failed)."""
    path = _startup_path(store)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        holder = _startup_holder(store)
        if not _pid_dead(holder):                # reuse §4.4's dead-on-this-boot check
            return (False, holder)               # live holder -> fail closed
        try:
            os.unlink(path)                      # stale -> clear it
        except FileNotFoundError:
            pass
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return (False, _startup_holder(store))   # lost a concurrent steal
    with os.fdopen(fd, "w") as fh:
        json.dump(_startup_obj(), fh)
    return (True, {})


def release_startup(store):
    try:
        os.unlink(_startup_path(store))
    except FileNotFoundError:
        pass
