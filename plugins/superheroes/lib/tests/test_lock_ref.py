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


# --- release-on-park (a parked run must not cost a 30-min lockout before relaunch) ---
# The lease's recorded pid belongs to the short-lived recover_entry.py process, NOT the run
# (verified live 2026-07-02: the pid was gone seconds after acquire while the run continued),
# so pid-liveness CANNOT distinguish a parked run from a live one on the same host. A live
# lease refuses a second acquire until TTL; terminal parks RELEASE the lease instead.
import hostinfo


def _fresh_lease(pid, host, boot_id, generation=1):
    # acquiredAt = now (NOT expired).
    return {"pid": pid, "host": host, "acquiredAt": lock._stamp(),
            "bootId": boot_id, "generation": generation, "ttl": lock.DEFAULT_TTL}


def test_dead_pid_same_host_boot_still_held_until_ttl(tmp_path):
    # The acquiring pid exits seconds after acquire on a LIVE run too — a dead pid on this
    # host+boot proves nothing. An unexpired lease must refuse a second acquire (UFR-3);
    # a double-launch must never steal a live run's lease.
    s = _store(tmp_path)
    lock._force_lease(s, "wi", _fresh_lease(999999, lock._host(), hostinfo.boot_id()))
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is False and reason == "held"


def test_dead_pid_other_host_still_held_until_ttl(tmp_path):
    s = _store(tmp_path)
    lock._force_lease(s, "wi", _fresh_lease(999999, "some-other-host", "other-boot"))
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is False and reason == "held"


def test_release_deletes_held_lease_and_unblocks_relaunch(tmp_path):
    # The park path: release with OUR generation deletes the ref; the next acquire creates fresh.
    s = _store(tmp_path)
    ok, gen, _ = lock.acquire(s, "wi")
    assert ok
    assert lock.release(s, "wi", gen) is True
    sha, lease = lock.read_lease(s, "wi")
    assert sha is None and lease is None, "release must delete the lease ref"
    ok2, gen2, reason2 = lock.acquire(s, "wi")
    assert ok2 is True and reason2 == "created", "a relaunch after park acquires immediately"


def test_release_with_stale_generation_noops(tmp_path):
    # A superseded holder must never delete the current holder's lease.
    s = _store(tmp_path)
    lock._force_lease(s, "wi", _fresh_lease(999999, lock._host(), None, generation=5))
    assert lock.release(s, "wi", 3) is False
    sha, lease = lock.read_lease(s, "wi")
    assert lease is not None and lease["generation"] == 5, "stale release must leave the lease"


def test_release_absent_lease_noops(tmp_path):
    s = _store(tmp_path)
    assert lock.release(s, "wi", 1) is False


def test_ttl_expiry_still_reclaims(tmp_path):
    # The TTL + dead-pid path stays the crash backstop (a run that never reached its release).
    s = _store(tmp_path)
    lock._force_lease(s, "wi", {"pid": 999999, "host": lock._host(),
                                "acquiredAt": "1970-01-01T00:00:00Z",
                                "bootId": None, "generation": 1, "ttl": 1})
    ok, gen, reason = lock.acquire(s, "wi")
    assert ok is True and gen == 2 and reason == "stolen"


# --- #379: the lease records the owning session's launch cwd (sessionCwd) so allowance
# journaling can attribute an event to a run ONLY when the triggering session IS the run's
# session. Backward-compatible: acquire WITHOUT session_cwd leaves the field absent (legacy).


def test_acquire_records_session_cwd(tmp_path):
    # #379: acquire stamps the owning session's launch cwd onto the lease so a later hook can
    # tell whether a triggering session owns this run.
    s = _store(tmp_path)
    ok, gen, _ = lock.acquire(s, "wi", session_cwd="/some/session/dir")
    assert ok and gen == 1
    _sha, lease = lock.read_lease(s, "wi")
    assert lease["sessionCwd"] == "/some/session/dir"


def test_acquire_without_session_cwd_omits_field(tmp_path):
    # Backward compatibility: a caller that does not pass session_cwd (pre-#379 or a non-run
    # acquire) leaves the field ABSENT — attribution then falls back to today's behavior.
    s = _store(tmp_path)
    ok, _gen, _ = lock.acquire(s, "wi")
    assert ok
    _sha, lease = lock.read_lease(s, "wi")
    assert "sessionCwd" not in lease


def test_renew_preserves_session_cwd(tmp_path):
    # A heartbeat re-stamps acquiredAt but MUST carry the sessionCwd forward — else attribution
    # would break the moment the first fence/renew fires mid-run.
    s = _store(tmp_path)
    ok, gen, _ = lock.acquire(s, "wi", session_cwd="/session/A")
    assert ok
    assert lock.renew(s, "wi", gen) is True
    _sha, lease = lock.read_lease(s, "wi")
    assert lease["sessionCwd"] == "/session/A", "renew must not drop the owning session cwd"


def test_stale_steal_records_new_session_cwd(tmp_path):
    # Stealing a stale lease records the STEALING session's cwd (the new owner), not the old.
    s = _store(tmp_path)
    lock._force_lease(s, "wi", {"pid": 999999, "host": lock._host(),
                                "acquiredAt": "1970-01-01T00:00:00Z",
                                "bootId": None, "generation": 1, "ttl": 1,
                                "sessionCwd": "/old/session"})
    ok, gen, reason = lock.acquire(s, "wi", session_cwd="/new/session")
    assert ok and reason == "stolen" and gen == 2
    _sha, lease = lock.read_lease(s, "wi")
    assert lease["sessionCwd"] == "/new/session"
