"""Tests for pilot slot lifecycle — state machine, generations, serialized persistence."""
import json
import multiprocessing
import os
import shutil
import stat
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_lifecycle as pl  # noqa: E402
import pilot_slot  # noqa: E402

NOW = "2026-01-01T00:00:00Z"
ACCOUNTS = [{"account": "owner", "role": "resource-owner"}]
SLOT = "slot1"

_CONCURRENCY_NOW = "2026-08-02T12:00:00Z"


def _tmp_private():
    return tempfile.mkdtemp(dir="/private/tmp")


def _raises(reason):
    return pytest.raises(pl.PilotLifecycleError, match=reason)


def _record_in_state(state):
    rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
    if state == pl.STATE_PROVISIONING:
        return rec
    if state == pl.STATE_PROVISIONED:
        return pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
    if state == pl.STATE_OCCUPIED:
        return pl.transition(
            pl.transition(rec, pl.STATE_PROVISIONED, now=NOW),
            pl.STATE_OCCUPIED,
            now=NOW,
        )
    if state == pl.STATE_RELEASED:
        return pl.transition(
            pl.transition(
                pl.transition(rec, pl.STATE_PROVISIONED, now=NOW),
                pl.STATE_OCCUPIED,
                now=NOW,
            ),
            pl.STATE_RELEASED,
            now=NOW,
        )
    if state == pl.STATE_FAILED:
        return pl.transition(rec, pl.STATE_FAILED, now=NOW)
    if state == pl.STATE_RETIRED:
        return pl.transition(
            pl.transition(rec, pl.STATE_FAILED, now=NOW),
            pl.STATE_RETIRED,
            now=NOW,
        )
    raise AssertionError(f"unknown state {state!r}")


def _released_at_generation(generation):
    rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
    for _ in range(generation - 1):
        rec = pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
        rec = pl.transition(rec, pl.STATE_OCCUPIED, now=NOW)
        rec = pl.transition(rec, pl.STATE_RELEASED, now=NOW)
        rec = pl.begin_generation(rec, now=NOW)
    rec = pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
    rec = pl.transition(rec, pl.STATE_OCCUPIED, now=NOW)
    rec = pl.transition(rec, pl.STATE_RELEASED, now=NOW)
    assert rec["generation"] == generation
    return rec


def _concurrency_begin_generation(record):
    return pl.begin_generation(record, now=_CONCURRENCY_NOW)


def _concurrency_worker(slots_dir_path, slot, barrier, index, results_dir):
    barrier.wait()
    result = pl.mutate(slots_dir_path, slot, _concurrency_begin_generation)
    with open(os.path.join(results_dir, f"{index}.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh)


def test_transition_matrix_exhaustive():
    for from_state in pl.SLOT_STATES:
        for to_state in pl.SLOT_STATES:
            rec = _record_in_state(from_state)
            allowed = to_state in pl.TRANSITIONS[from_state]
            if from_state == pl.STATE_OCCUPIED and to_state == pl.STATE_OCCUPIED:
                with _raises(pl.REASON_OCCUPIED):
                    pl.transition(rec, to_state, now=NOW)
                continue
            if from_state == pl.STATE_RETIRED:
                with _raises(pl.REASON_RETIRED):
                    pl.transition(rec, to_state, now=NOW)
                continue
            if allowed:
                out = pl.transition(rec, to_state, now=NOW)
                assert out["state"] == to_state
                assert out is not rec
            else:
                with _raises(pl.REASON_TRANSITION_ILLEGAL):
                    pl.transition(rec, to_state, now=NOW)


@pytest.mark.parametrize(
    "target",
    [
        pl.STATE_PROVISIONING,
        pl.STATE_PROVISIONED,
        pl.STATE_OCCUPIED,
        pl.STATE_RELEASED,
    ],
)
def test_failed_reopening_refused(target):
    rec = _record_in_state(pl.STATE_FAILED)
    with _raises(pl.REASON_TRANSITION_ILLEGAL):
        pl.transition(rec, target, now=NOW)


def test_transition_occupied_to_occupied_refuses_slot_occupied():
    rec = _record_in_state(pl.STATE_OCCUPIED)
    with _raises(pl.REASON_OCCUPIED):
        pl.transition(rec, pl.STATE_OCCUPIED, now=NOW)


def test_transition_from_retired_refuses_slot_retired():
    rec = _record_in_state(pl.STATE_RETIRED)
    with _raises(pl.REASON_RETIRED):
        pl.transition(rec, pl.STATE_PROVISIONING, now=NOW)


def test_generation_check_match():
    assert pl.generation_check(3, 3) == {"ok": True, "reason": None}


def test_generation_check_stale():
    assert pl.generation_check(2, 3) == {
        "ok": False,
        "reason": pl.REASON_GENERATION_STALE,
    }


def test_generation_check_ahead():
    assert pl.generation_check(4, 3) == {
        "ok": False,
        "reason": pl.REASON_GENERATION_AHEAD,
    }


@pytest.mark.parametrize(
    "carried",
    [0, -1, True, "1", None],
)
def test_generation_check_invalid_carried(carried):
    assert pl.generation_check(carried, 1) == {
        "ok": False,
        "reason": pilot_slot.REFUSAL_GENERATION_INVALID,
    }


@pytest.mark.parametrize(
    "current",
    [0, -1, False, "2", None],
)
def test_generation_check_invalid_current(current):
    assert pl.generation_check(1, current) == {
        "ok": False,
        "reason": pilot_slot.REFUSAL_GENERATION_INVALID,
    }


def test_no_is_stale_helper():
    assert not hasattr(pl, "is_stale")


def test_new_record_write_read_round_trip():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        assert pl.write_record(path, rec)["ok"]
        loaded = pl.read_record(path)
        assert loaded["ok"]
        assert loaded["record"] == rec
    finally:
        shutil.rmtree(tmp)


def test_read_record_missing_file():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "missing.json")
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_UNREADABLE,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_read_record_non_json_bytes():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        with open(path, "wb") as fh:
            fh.write(b"not-json{")
        result = pl.read_record(path)
        assert result["ok"] is False
        assert result["reason"] == pl.REASON_RECORD_INVALID
        assert result["record"] is None
    finally:
        shutil.rmtree(tmp)


def test_read_record_wrong_schema_version():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec["schemaVersion"] = 2
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_read_record_missing_required_field():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "slot": SLOT}, fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_read_record_json_array():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([], fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_write_record_invalid_refuses_before_write():
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        result = pl.write_record(path, {"schemaVersion": 1})
        assert result == {"ok": False, "reason": pl.REASON_RECORD_INVALID}
        assert not os.path.exists(path)
    finally:
        shutil.rmtree(tmp)


def test_write_record_fsyncs_directory_fd(monkeypatch):
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        parent = os.path.dirname(os.path.abspath(path))
        dir_fd = os.open(parent, os.O_RDONLY)
        dir_ino = os.fstat(dir_fd).st_ino
        os.close(dir_fd)

        fsynced = []
        found_dir = False
        real_fsync = os.fsync

        def tracking_fsync(fd):
            nonlocal found_dir
            fsynced.append(fd)
            try:
                st = os.fstat(fd)
                if stat.S_ISDIR(st.st_mode) and st.st_ino == dir_ino:
                    found_dir = True
            except OSError:
                pass
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", tracking_fsync)
        assert pl.write_record(path, rec)["ok"]
        assert found_dir
    finally:
        shutil.rmtree(tmp)


def test_write_record_directory_fsync_failure(monkeypatch):
    tmp = _tmp_private()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        real_fsync = os.fsync

        def failing_fsync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("simulated directory fsync failure")
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", failing_fsync)
        result = pl.write_record(path, rec)
        assert result == {"ok": False, "reason": pl.REASON_RECORD_WRITE_FAILED}
    finally:
        shutil.rmtree(tmp)


def test_slot_lock_timeout():
    tmp = _tmp_private()
    try:
        slots_path = os.path.join(tmp, "slots")
        with pl.slot_lock(slots_path, SLOT):
            with _raises(pl.REASON_LOCK_UNAVAILABLE):
                with pl.slot_lock(slots_path, SLOT, timeout=0.1, poll=0.01):
                    pass
    finally:
        shutil.rmtree(tmp)


def test_mutate_releases_lock_when_fn_raises():
    tmp = _tmp_private()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, SLOT)
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        assert pl.write_record(path, rec)["ok"]

        def boom(_record):
            raise ValueError("boom")

        first = pl.mutate(slots_path, SLOT, boom)
        assert first["ok"] is False
        assert first["reason"] == pl.REASON_MUTATION_FAILED
        assert first["record"] is None

        second = pl.mutate(slots_path, SLOT, lambda r: r)
        assert second["ok"]
    finally:
        shutil.rmtree(tmp)


def test_concurrent_generation_allocation():
    multiprocessing.set_start_method("spawn", force=True)
    tmp = _tmp_private()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, SLOT)
        start_gen = 4
        rec = _released_at_generation(start_gen)
        assert pl.write_record(path, rec)["ok"]

        n = 8
        results_dir = os.path.join(tmp, "results")
        os.makedirs(results_dir)
        barrier = multiprocessing.Barrier(n)
        processes = []
        for index in range(n):
            proc = multiprocessing.Process(
                target=_concurrency_worker,
                args=(slots_path, SLOT, barrier, index, results_dir),
            )
            processes.append(proc)
            proc.start()
        for proc in processes:
            proc.join()
        outcomes = []
        for index in range(n):
            with open(
                os.path.join(results_dir, f"{index}.json"),
                encoding="utf-8",
            ) as fh:
                outcomes.append(json.load(fh))

        successes = [r for r in outcomes if r and r["ok"]]
        failures = [r for r in outcomes if r and not r["ok"]]
        assert len(successes) == 1
        assert len(failures) == n - 1
        assert successes[0]["record"]["generation"] == start_gen + 1
        for failure in failures:
            assert failure["reason"] in (
                pl.REASON_TRANSITION_ILLEGAL,
                pl.REASON_LOCK_UNAVAILABLE,
            )

        final = pl.read_record(path)
        assert final["ok"]
        assert final["record"]["generation"] == start_gen + 1
    finally:
        shutil.rmtree(tmp)


def test_slot_ref_uses_format_slot_ref():
    rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
    assert pl.slot_ref(rec) == pilot_slot.format_slot_ref(SLOT, 1)


def test_provisioning_outcome_mapping():
    assert pl.provisioning_outcome(pl.STATE_PROVISIONING) is None
    assert pl.provisioning_outcome(pl.STATE_PROVISIONED) == "provisioned"
    assert pl.provisioning_outcome(pl.STATE_OCCUPIED) == "provisioned"
    assert pl.provisioning_outcome(pl.STATE_RELEASED) == "provisioned"
    assert pl.provisioning_outcome(pl.STATE_FAILED) == "failed"
    assert pl.provisioning_outcome(pl.STATE_RETIRED) == "failed"
    with _raises(pl.REASON_STATE_INVALID):
        pl.provisioning_outcome("bogus")
