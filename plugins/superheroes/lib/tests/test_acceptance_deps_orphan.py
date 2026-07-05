# plugins/superheroes/lib/tests/test_acceptance_deps_orphan.py
#
# issue #245: after an ungraceful harness death the spawned `claude -p` child GROUP survives
# re-parented with no supervisor. Before this, the lease recorded only the HARNESS pid, so
# the next invocation classified the lease dead, reclaimed, and its discovery teardown deleted
# the orphan's branches/PR WHILE the orphan was still building on them — re-opening the very
# two-concurrent-runs interleaving the O_EXCL lease exists to prevent.
#
# The fix persists the child pgid into the lease at spawn time; on classifying the harness pid
# dead, `_lease_liveness` probes/kills the recorded child group first and treats an unkillable
# group as UNCONFIRMABLE (fail-closed refuse to reclaim). A pgid from a previous boot is
# meaningless and is never probed. Old leases without the pgid field behave exactly as before.
import os
import socket
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as deps
import acceptance_launch
import hostinfo


def _dead_harness(monkeypatch):
    """Make the recorded HARNESS pid classify dead so the orphan-group check runs — without
    touching os.killpg (which the orphan reap uses)."""
    monkeypatch.setattr(os, "kill",
                        lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))


def _isolated(monkeypatch, store):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)


# --- _lease_liveness / _orphan_group_liveness -----------------------------------------


def test_old_schema_lease_without_pgid_dead_harness_is_dead(monkeypatch):
    # Schema compatibility: a lease written before #245 has no childPgid — a dead harness pid
    # must classify "dead" exactly as today, and NO orphan probe is attempted.
    _dead_harness(monkeypatch)
    probed = []
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid",
                        lambda pgid: probed.append(pgid) or True)
    lease = {"pid": 999999, "host": socket.gethostname(), "bootId": hostinfo.boot_id()}
    assert deps._lease_liveness(lease) == "dead"
    assert probed == []


def test_live_orphan_group_unconfirmable_refuses_reclaim(monkeypatch):
    # The crux: harness pid dead, bootId matches, recorded child group cannot be confirmed
    # dead -> "unconfirmable". `acceptance_reclaim.decide` maps that to a fail-closed refuse,
    # so the reclaim never deletes the live orphan's artifacts.
    _dead_harness(monkeypatch)
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid", lambda pgid: False)
    lease = {"pid": 999999, "host": socket.gethostname(),
             "bootId": hostinfo.boot_id(), "childPgid": 4242}
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_orphan_group_confirmed_dead_is_reclaimable(monkeypatch):
    # Harness pid dead, the recorded group reaped-to-confirmed-empty -> "dead": safe to reclaim
    # and clean up the now-dead orphan's artifacts.
    _dead_harness(monkeypatch)
    reaped = []
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid",
                        lambda pgid: reaped.append(pgid) or True)
    lease = {"pid": 999999, "host": socket.gethostname(),
             "bootId": hostinfo.boot_id(), "childPgid": 4242}
    assert deps._lease_liveness(lease) == "dead"
    assert reaped == [4242]   # the recorded group WAS probed/reaped before reclaim


def test_orphan_pgid_from_previous_boot_is_ignored(monkeypatch):
    # A pgid recorded on a PREVIOUS boot names a meaningless (recycled) identity: the lease is
    # "dead" (reclaimable) WITHOUT probing/killing the pgid.
    _dead_harness(monkeypatch)
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid",
                        lambda pgid: (_ for _ in ()).throw(
                            AssertionError("must not probe a previous-boot pgid")))
    monkeypatch.setattr(hostinfo, "boot_id", lambda: "boot-CURRENT")
    lease = {"pid": 999999, "host": socket.gethostname(),
             "bootId": "boot-OLD", "childPgid": 4242}
    assert deps._lease_liveness(lease) == "dead"


def test_orphan_group_liveness_absent_bootid_does_not_probe(monkeypatch):
    # Direct guard: with no confirmed same-boot bootId on either side, the recorded pgid can't
    # be trusted to name the same group -> "dead" as pre-#245, no probe.
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid",
                        lambda pgid: (_ for _ in ()).throw(
                            AssertionError("no probe without a confirmed same-boot bootId")))
    assert deps._orphan_group_liveness({"childPgid": 4242}, None, None) == "dead"


def test_alive_harness_never_probes_the_orphan_group(monkeypatch):
    # When the harness pid is ALIVE the run is genuinely in-flight; the orphan path must not run
    # (the recorded child group is never signalled out from under a live harness).
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid",
                        lambda pgid: (_ for _ in ()).throw(
                            AssertionError("alive harness must not reap the child group")))
    lease = {"pid": os.getpid(), "host": socket.gethostname(),
             "bootId": hostinfo.boot_id(), "childPgid": 4242}
    assert deps._lease_liveness(lease) == "alive"


def test_malformed_child_pgid_falls_back_to_pre_245_dead(monkeypatch):
    _dead_harness(monkeypatch)
    monkeypatch.setattr(acceptance_launch, "reap_group_by_pgid",
                        lambda pgid: (_ for _ in ()).throw(
                            AssertionError("must not probe a malformed pgid")))
    lease = {"pid": 999999, "host": socket.gethostname(),
             "bootId": hostinfo.boot_id(), "childPgid": "not-an-int"}
    assert deps._lease_liveness(lease) == "dead"


# --- _persist_child_pgid: the lease records the child pgid at spawn --------------------


def test_persist_child_pgid_records_pgid_and_bootid_into_lease(monkeypatch):
    store = tempfile.mkdtemp()
    root = tempfile.mkdtemp()
    try:
        _isolated(monkeypatch, store)
        stamp = "accept-harness-pgid0001"
        assert deps._try_acquire_lease(root, stamp) is True
        before = deps._read_lease(root)
        assert "childPgid" not in before          # absent at acquire time (child not spawned yet)

        deps._persist_child_pgid(root, stamp, 5150)

        after = deps._read_lease(root)
        assert after["childPgid"] == 5150
        assert after["bootId"] == hostinfo.boot_id()
        # every pre-existing field is preserved (patched in place, not rewritten from scratch).
        assert after["stamp"] == stamp
        assert after["pid"] == before["pid"]
        assert after["acquiredAt"] == before["acquiredAt"]
    finally:
        shutil.rmtree(store, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def test_persist_child_pgid_noops_on_foreign_stamp(monkeypatch):
    # Never clobber a lease a concurrent winner holds: if the on-disk lease names a different
    # stamp, persistence is a no-op.
    store = tempfile.mkdtemp()
    root = tempfile.mkdtemp()
    try:
        _isolated(monkeypatch, store)
        deps._try_acquire_lease(root, "accept-harness-winner01")
        deps._persist_child_pgid(root, "accept-harness-other002", 5150)
        lease = deps._read_lease(root)
        assert lease["stamp"] == "accept-harness-winner01"
        assert "childPgid" not in lease
    finally:
        shutil.rmtree(store, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def test_persist_child_pgid_noops_without_stamp_or_pgid(monkeypatch):
    store = tempfile.mkdtemp()
    root = tempfile.mkdtemp()
    try:
        _isolated(monkeypatch, store)
        deps._try_acquire_lease(root, "accept-harness-winner01")
        deps._persist_child_pgid(root, None, 5150)                      # no stamp
        deps._persist_child_pgid(root, "accept-harness-winner01", None)  # no pgid
        lease = deps._read_lease(root)
        assert "childPgid" not in lease
    finally:
        shutil.rmtree(store, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def test_real_launcher_persists_child_pgid_at_spawn(monkeypatch):
    # The wiring: real_launcher's child factory must persist the spawned child's pgid into the
    # lease as soon as run() invokes the factory — so an ungraceful death mid-run leaves a lease
    # that already names the orphan group.
    store = tempfile.mkdtemp()
    root = tempfile.mkdtemp()
    try:
        _isolated(monkeypatch, store)
        stamp = "accept-harness-spawn001"
        assert deps._try_acquire_lease(root, stamp) is True

        class _FakeChild:
            def pgid(self):
                return 9182

        monkeypatch.setattr(deps.acceptance_launch, "_default_child_factory",
                            lambda *a, **k: _FakeChild())

        def fake_run(stamped, ceilings, child_factory, *a, **k):
            child_factory()   # run() must actually spawn -> triggers pgid persistence
            return {"outcome": "exited", "terminal_location": "/t.json",
                    "spend_partial": False, "spend": None, "elapsed_sec": 0.0}

        monkeypatch.setattr(deps.acceptance_launch, "run", fake_run)

        deps.real_launcher(root)(
            {"stamp": stamp, "work_item": "accept-harness-spawn001", "paths": []})

        lease = deps._read_lease(root)
        assert lease["childPgid"] == 9182
    finally:
        shutil.rmtree(store, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)
