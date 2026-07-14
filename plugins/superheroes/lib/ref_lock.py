# plugins/superheroes/lib/ref_lock.py
"""The work-item lock (CONVENTIONS §4.4).

Ref-lease (§4.4): a leased git ref `refs/superheroes/locks/<work-item>` in the
per-clone control-plane store. The lease JSON is stored as a git BLOB; the ref
points at that blob; reclaim is an atomic compare-and-swap via
`git update-ref <ref> <newblob> <oldblob>` (the oldvalue precondition). `generation`
is the fence token mirrored into checkpoint.lockGeneration.

This per-work-item lease is the sole mutex for "one live run per work item per clone":
because the store is keyed off the git common dir, the same lease ref is visible
identically from every worktree of a clone. (The old §4.5 per-checkout `startup.lock`
was removed in #170 — it never serialized anything: its recorded holder pid was the
ephemeral recover_entry leaf, dead seconds after acquire, so every subsequent launch
stole it, and release_startup had zero callers.)
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
    """Stale iff EXPIRED *and* the holder pid is dead-on-this-boot (§4.4). Pid liveness must
    never SHORTEN the wait: the recorded pid belongs to the short-lived acquiring process
    (recover_entry.py), which exits seconds into a healthy run — a dead pid cannot distinguish
    a parked run from a live one. Parked runs release the lease at exit instead (release())."""
    if not isinstance(lease, dict):
        return True
    return _expired(lease.get("acquiredAt"), ttl, now) and _pid_dead(lease)


def _lease_obj(generation, ttl, now=None, session_cwd=None):
    obj = {"pid": os.getpid(), "host": _host(), "bootId": hostinfo.boot_id(),
           "acquiredAt": _stamp(now), "generation": generation, "ttl": ttl}
    # #379: the owning session's launch cwd — the honest "which session started this run"
    # signal used to attribute allowance audit events to the run whose session triggered them
    # (Claude Code does not expose session_id to a subprocess, so the acquiring leaf records its
    # own os.getcwd(), which equals the payload cwd the hook reports for that session's tool
    # calls). Absent on a pre-#379 (legacy) lease, or any acquire that passes no session_cwd —
    # attribution then falls back to today's cwd-resolved run. Never load-bearing for the mutex.
    if session_cwd:
        obj["sessionCwd"] = session_cwd
    return obj


def acquire(store, work_item, ttl=DEFAULT_TTL, now=None, session_cwd=None):
    """(ok, generation, reason). Create-if-absent or CAS-steal-if-stale; a live
    holder -> (False, gen, 'held'). `session_cwd` (#379), when given, records the acquiring
    session's launch cwd on the lease for allowance-event attribution — optional and
    backward-compatible (an omitted value leaves the field absent)."""
    sha, lease = read_lease(store, work_item)
    if sha is None:                               # absent -> create
        if _cas(store, work_item, _lease_obj(1, ttl, now, session_cwd), None):
            return (True, 1, "created")
        return (False, 0, "lost-create-cas")      # someone created concurrently
    if lease is not None and not is_stale(lease, ttl, now):
        return (False, lease.get("generation", 0), "held")
    gen = (lease.get("generation", 0) if lease else 0) + 1
    if _cas(store, work_item, _lease_obj(gen, ttl, now, session_cwd), sha):   # CAS on the stale blob
        return (True, gen, "stolen")
    return (False, gen, "lost-steal-cas")         # concurrent reclaimer won


def release(store, work_item, generation):
    """Delete the lease ref iff we still hold `generation` — atomic via `git update-ref -d
    <ref> <oldsha>` (the oldvalue precondition). Terminal parks and hand-backs release at
    exit so a relaunch never waits out the TTL; a superseded holder (stale generation)
    no-ops False and never deletes the current holder's lease. A crash that skips this
    still expires via the TTL + dead-pid path."""
    sha, lease = read_lease(store, work_item)
    if sha is None or not isinstance(lease, dict) or lease.get("generation") != generation:
        return False
    r = _git(store, "update-ref", "-d", _ref(work_item), sha)
    return r.returncode == 0


def renew(store, work_item, generation, ttl=DEFAULT_TTL, now=None):
    """Heartbeat: re-stamp acquiredAt keeping `generation`, via CAS. False if
    superseded (we no longer hold it)."""
    sha, lease = read_lease(store, work_item)
    if not lease or lease.get("generation") != generation:
        return False
    # #379: carry the owning session's cwd forward across the heartbeat — else the first renew
    # would silently drop it and mid-run allowance events would lose their attribution.
    obj = _lease_obj(generation, ttl, now, session_cwd=lease.get("sessionCwd"))
    return _cas(store, work_item, obj, sha)


def fence_ok(store, work_item, generation):
    """Our generation still current? (call before any external write — §4.4 fence)."""
    _, lease = read_lease(store, work_item)
    return bool(lease) and lease.get("generation") == generation


def list_leases(store):
    """(work_item, lease_dict_or_None) for every lock ref in the store. Never raises:
    an unreadable store / no refs -> []. The work item is the ref suffix after the
    §4.4 prefix."""
    r = _git(store, "for-each-ref", "--format=%(refname)", LOCK_REF_PREFIX)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    out = []
    for line in r.stdout.splitlines():
        ref = line.strip()
        if not ref.startswith(LOCK_REF_PREFIX):
            continue
        out.append((ref[len(LOCK_REF_PREFIX):], read_lease(store, ref[len(LOCK_REF_PREFIX):])[1]))
    return out


def active_work_items(store, ttl=DEFAULT_TTL, now=None):
    """Work items in `store` holding a LIVE (non-stale) lease — the honest "what is running
    in this clone" signal that replaced the vacuous current.json pointer (#170). Sorted for
    determinism. Never raises."""
    return sorted(wi for (wi, lease) in list_leases(store)
                  if isinstance(lease, dict) and not is_stale(lease, ttl, now))
