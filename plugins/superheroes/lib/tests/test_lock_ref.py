# plugins/superheroes/lib/tests/test_lock_ref.py
import subprocess
import control_plane
import ref_lock as lock


def _store(tmp_path):
    s = control_plane.ensure_store(str(tmp_path), root=str(tmp_path / "store"))
    assert s is not None
    return s


def test_acquire_creates_ref_gen1(tmp_path):
    s = _store(tmp_path)
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok and gen == 1
    sha, lease = lock.read_lease(s, "wi")
    assert lease["generation"] == 1 and lease["pid"] == __import__("os").getpid()


def test_second_acquire_on_live_holder_fails(tmp_path):
    s = _store(tmp_path)
    assert lock.acquire(s, "wi")[0] is True
    ok, gen, reason = lock.acquire(s, "wi")     # same store, still-live holder
    assert ok is False and reason == "held"


def test_stale_lease_is_reclaimed_with_gen_bump(tmp_path):
    s = _store(tmp_path)
    # acquire with a tiny ttl and a now far in the past, so it is already expired,
    # and a dead pid so liveness says dead -> stale -> reclaim bumps generation.
    lock.acquire(s, "wi", ttl=1, now=0)
    # craft a stale lease (dead pid 999999, ancient acquiredAt) by writing directly
    lock._force_lease(s, "wi", {"pid": 999999, "host": lock._host(),
                                "acquiredAt": "1970-01-01T00:00:00Z",
                                "bootId": None, "generation": 1, "ttl": 1})
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok and gen == 2 and reason == "stolen"


def test_cas_reclaim_fails_on_concurrent_move(tmp_path):
    # The deterministic CAS oracle (review test-004): pre-move the ref out from under
    # us, then a steal with the now-stale oldvalue MUST fail closed (no double-win).
    s = _store(tmp_path)
    lock._force_lease(s, "wi", {"pid": 999999, "host": lock._host(),
                                "acquiredAt": "1970-01-01T00:00:00Z",
                                "bootId": None, "generation": 1, "ttl": 1})
    stale_sha, _ = lock.read_lease(s, "wi")
    # a concurrent reclaimer moves the ref to a new blob:
    lock._force_lease(s, "wi", {"pid": 999998, "host": lock._host(),
                                "acquiredAt": "1970-01-01T00:00:00Z",
                                "bootId": None, "generation": 2, "ttl": 1})
    # our CAS with the now-stale oldvalue fails:
    assert lock._cas(s, "wi", {"generation": 99}, stale_sha) is False


def test_fence_ok_detects_supersession(tmp_path):
    s = _store(tmp_path)
    ok, gen, _ = lock.acquire(s, "wi")
    assert lock.fence_ok(s, "wi", gen) is True
    lock._force_lease(s, "wi", {"pid": 1, "host": lock._host(), "acquiredAt": "x",
                                "bootId": None, "generation": gen + 5, "ttl": 1})
    assert lock.fence_ok(s, "wi", gen) is False   # superseded -> abort external write


def test_renew_keeps_lease_but_fails_when_superseded(tmp_path):
    s = _store(tmp_path)
    ok, gen, _ = lock.acquire(s, "wi")
    assert lock.renew(s, "wi", gen) is True                 # heartbeat keeps the lease
    lock._force_lease(s, "wi", {"pid": 1, "host": lock._host(), "acquiredAt": "x",
                                "bootId": None, "generation": gen + 1, "ttl": 1})
    assert lock.renew(s, "wi", gen) is False                # superseded -> cannot renew


# --- dead-pid reclaim BEFORE ttl expiry (a parked run must not cost a 30-min lockout) ---
import pytest
import hostinfo


def _fresh_lease(pid, host, boot_id):
    # acquiredAt = now (NOT expired) — only the provably-dead-here path can reclaim this.
    return {"pid": pid, "host": host, "acquiredAt": lock._stamp(),
            "bootId": boot_id, "generation": 1, "ttl": lock.DEFAULT_TTL}


@pytest.mark.skipif(hostinfo.boot_id() is None, reason="no boot id on this platform")
def test_dead_pid_same_host_boot_reclaims_before_ttl(tmp_path):
    # The holder pid is provably dead on THIS host+boot: reclaim immediately (gen bump via CAS),
    # even though the lease has not TTL-expired. Live 2026-07-02: every park cost 30 minutes.
    s = _store(tmp_path)
    lock._force_lease(s, "wi", _fresh_lease(999999, lock._host(), hostinfo.boot_id()))
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is True and gen == 2 and reason == "stolen"


def test_dead_pid_other_host_still_held_until_ttl(tmp_path):
    # A different host's pid is NOT provable from here — TTL stays the only safety net
    # (a live run elsewhere must never be stolen early).
    s = _store(tmp_path)
    lock._force_lease(s, "wi", _fresh_lease(999999, "some-other-host", "other-boot"))
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is False and reason == "held"


def test_dead_pid_unknown_boot_still_held_until_ttl(tmp_path):
    # Same host but no recorded bootId: liveness is not PROVABLE (the pid may simply have been
    # recycled across a reboot) — keep the TTL guard for the unexpired lease.
    s = _store(tmp_path)
    lock._force_lease(s, "wi", _fresh_lease(999999, lock._host(), None))
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is False and reason == "held"


@pytest.mark.skipif(hostinfo.boot_id() is None, reason="no boot id on this platform")
def test_live_pid_same_host_boot_still_held(tmp_path):
    # Our own (alive) pid on this host+boot: NOT reclaimable.
    s = _store(tmp_path)
    import os
    lock._force_lease(s, "wi", _fresh_lease(os.getpid(), lock._host(), hostinfo.boot_id()))
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is False and reason == "held"
