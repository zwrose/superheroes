"""Tests for pilot slot lifecycle — state machine, generations, serialized persistence."""
import json
import multiprocessing
import os
import shutil
import stat
import sys
import tempfile
import time

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
_BARRIER_TIMEOUT = 60.0
_JOIN_TIMEOUT = 60.0


def _tmp_dir():
    return tempfile.mkdtemp()


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
    barrier.wait(timeout=_BARRIER_TIMEOUT)
    result = pl.mutate(slots_dir_path, slot, _concurrency_begin_generation)
    with open(os.path.join(results_dir, f"{index}.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh)


def _create_slot_concurrency_worker(slots_dir_path, slot, barrier, index, results_dir):
    barrier.wait(timeout=_BARRIER_TIMEOUT)
    result = pl.create_slot(slots_dir_path, slot, ACCOUNTS, now=_CONCURRENCY_NOW)
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
            if (
                from_state == pl.STATE_RELEASED
                and to_state == pl.STATE_PROVISIONING
            ):
                with _raises(pl.REASON_GENERATION_ALLOCATION_REQUIRED):
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


def test_transition_released_to_provisioning_requires_begin_generation():
    rec = _record_in_state(pl.STATE_RELEASED)
    with _raises(pl.REASON_GENERATION_ALLOCATION_REQUIRED):
        pl.transition(rec, pl.STATE_PROVISIONING, now=NOW)
    out = pl.begin_generation(rec, now=NOW)
    assert out["state"] == pl.STATE_PROVISIONING
    assert out["generation"] == rec["generation"] + 1


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
    tmp = _tmp_dir()
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
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "missing.json")
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_ABSENT,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_read_record_non_json_bytes():
    tmp = _tmp_dir()
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


def test_read_record_invalid_utf8():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        with open(path, "wb") as fh:
            fh.write(b"\xff")
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_mutate_invalid_utf8_record():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, SLOT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"\xff")
        result = pl.mutate(slots_path, SLOT, lambda r: r)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_read_record_history_to_disagrees_with_state():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec = pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
        rec = pl.transition(rec, pl.STATE_OCCUPIED, now=NOW)
        rec = pl.transition(rec, pl.STATE_RELEASED, now=NOW)
        assert rec["state"] == pl.STATE_RELEASED
        rec["history"][-1]["to"] = pl.STATE_PROVISIONING
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_read_record_history_generation_disagrees():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = _released_at_generation(2)
        rec["history"][-1]["generation"] = rec["generation"] - 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_write_record_refuses_history_state_mismatch():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec = pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
        rec["history"][-1]["to"] = pl.STATE_OCCUPIED
        result = pl.write_record(path, rec)
        assert result == {"ok": False, "reason": pl.REASON_RECORD_INVALID}
        assert not os.path.exists(path)
    finally:
        shutil.rmtree(tmp)


def test_write_record_refuses_history_generation_mismatch():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = _released_at_generation(2)
        rec["history"][-1]["generation"] = 1
        result = pl.write_record(path, rec)
        assert result == {"ok": False, "reason": pl.REASON_RECORD_INVALID}
        assert not os.path.exists(path)
    finally:
        shutil.rmtree(tmp)


def test_mutate_refuses_record_slot_mismatch():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, "slot1")
        rec = pl.new_record("slot2", ACCOUNTS, now=NOW)
        assert pl.write_record(path, rec)["ok"]
        original_bytes = open(path, "rb").read()
        callback_ran = []

        def fn(_record):
            callback_ran.append(True)
            return _record

        result = pl.mutate(slots_path, "slot1", fn)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_SLOT_MISMATCH,
            "record": None,
        }
        assert not callback_ran
        assert open(path, "rb").read() == original_bytes
    finally:
        shutil.rmtree(tmp)


def test_slot_lock_refuses_symlinked_slot_dir():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        target = os.path.join(tmp, "target")
        os.makedirs(target)
        marker = os.path.join(target, "marker")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("untouched")
        os.makedirs(slots_path)
        os.symlink(target, os.path.join(slots_path, SLOT))
        with _raises(pl.REASON_SLOT_DIR_UNSAFE):
            with pl.slot_lock(slots_path, SLOT):
                pass
        assert os.path.isfile(marker)
        with open(marker, encoding="utf-8") as fh:
            assert fh.read() == "untouched"
    finally:
        shutil.rmtree(tmp)


def test_slot_lock_refuses_file_slot_dir():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        os.makedirs(slots_path)
        with open(os.path.join(slots_path, SLOT), "w", encoding="utf-8") as fh:
            fh.write("not-a-directory")
        with _raises(pl.REASON_SLOT_DIR_UNSAFE):
            with pl.slot_lock(slots_path, SLOT):
                pass
    finally:
        shutil.rmtree(tmp)


def test_slot_lock_refuses_symlinked_lock_file():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        slot_dir = os.path.join(slots_path, SLOT)
        os.makedirs(slot_dir)
        lock_target = os.path.join(tmp, "lock-target")
        with open(lock_target, "w", encoding="utf-8") as fh:
            fh.write("")
        os.symlink(lock_target, pl.lock_path(slots_path, SLOT))
        with _raises(pl.REASON_SLOT_DIR_UNSAFE):
            with pl.slot_lock(slots_path, SLOT):
                pass
    finally:
        shutil.rmtree(tmp)


def test_create_slot_persists_first_record():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        result = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        assert result["ok"]
        assert result["record"]["generation"] == pl.INITIAL_GENERATION
        loaded = pl.read_record(pl.record_path(slots_path, SLOT))
        assert loaded["ok"]
        assert loaded["record"] == result["record"]
    finally:
        shutil.rmtree(tmp)


def test_create_slot_twice_refuses_record_exists():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        first = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        assert first["ok"]
        second = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        assert second == {
            "ok": False,
            "reason": pl.REASON_RECORD_EXISTS,
            "record": None,
        }
        loaded = pl.read_record(pl.record_path(slots_path, SLOT))
        assert loaded["record"] == first["record"]
    finally:
        shutil.rmtree(tmp)


def test_mutate_oserror_returns_lock_unavailable():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        os.makedirs(slots_path, mode=0o555)
        try:
            result = pl.mutate(slots_path, SLOT, lambda r: r)
        except OSError:
            pytest.skip(
                "read-only slots directory did not prevent slot subdirectory "
                "creation for this user"
            )
        assert result == {
            "ok": False,
            "reason": pl.REASON_LOCK_UNAVAILABLE,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_read_record_wrong_schema_version():
    tmp = _tmp_dir()
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
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "slot": SLOT}, fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_read_record_json_array():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([], fh)
        result = pl.read_record(path)
        assert result["reason"] == pl.REASON_RECORD_INVALID
    finally:
        shutil.rmtree(tmp)


def test_write_record_invalid_refuses_before_write():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        result = pl.write_record(path, {"schemaVersion": 1})
        assert result == {"ok": False, "reason": pl.REASON_RECORD_INVALID}
        assert not os.path.exists(path)
    finally:
        shutil.rmtree(tmp)


def test_write_record_fsyncs_directory_fd(monkeypatch):
    tmp = _tmp_dir()
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
    tmp = _tmp_dir()
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
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        with pl.slot_lock(slots_path, SLOT):
            with _raises(pl.REASON_LOCK_UNAVAILABLE):
                with pl.slot_lock(slots_path, SLOT, timeout=0.1, poll=0.01):
                    pass
    finally:
        shutil.rmtree(tmp)


def test_mutate_releases_lock_when_fn_raises():
    tmp = _tmp_dir()
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
    tmp = _tmp_dir()
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
            proc.join(timeout=_JOIN_TIMEOUT)
        for proc in processes:
            assert proc.exitcode == 0, f"worker exited with {proc.exitcode}"
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


def _deterministic_lock_holder_worker(
    slots_dir_path,
    slot,
    hold_sentinel,
    release_sentinel,
    done_sentinel,
    result_path,
):
    def hold_and_advance(record):
        with open(hold_sentinel, "w", encoding="utf-8") as fh:
            fh.write("holding")
        deadline = time.monotonic() + 30.0
        while not os.path.exists(release_sentinel):
            if time.monotonic() >= deadline:
                raise RuntimeError("timed out waiting for release sentinel")
            time.sleep(0.05)
        return pl.begin_generation(record, now=_CONCURRENCY_NOW)

    result = pl.mutate(slots_dir_path, slot, hold_and_advance, timeout=30.0)
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    with open(done_sentinel, "w", encoding="utf-8") as fh:
        fh.write("done")


def _deterministic_lock_contender_worker(
    slots_dir_path,
    slot,
    start_sentinel,
    result_path,
):
    deadline = time.monotonic() + 30.0
    while not os.path.exists(start_sentinel):
        if time.monotonic() >= deadline:
            raise RuntimeError("timed out waiting for start sentinel")
        time.sleep(0.05)
    result = pl.mutate(slots_dir_path, slot, _concurrency_begin_generation, timeout=0.5)
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)


def test_mutate_lock_held_during_callback_blocks_contender():
    multiprocessing.set_start_method("spawn", force=True)
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, SLOT)
        start_gen = 4
        rec = _released_at_generation(start_gen)
        assert pl.write_record(path, rec)["ok"]

        hold_sentinel = os.path.join(tmp, "hold")
        release_sentinel = os.path.join(tmp, "release")
        start_sentinel = os.path.join(tmp, "start")
        holder_result = os.path.join(tmp, "holder.json")
        contender_result = os.path.join(tmp, "contender.json")

        holder = multiprocessing.Process(
            target=_deterministic_lock_holder_worker,
            args=(
                slots_path,
                SLOT,
                hold_sentinel,
                release_sentinel,
                os.path.join(tmp, "done"),
                holder_result,
            ),
        )
        contender = multiprocessing.Process(
            target=_deterministic_lock_contender_worker,
            args=(slots_path, SLOT, start_sentinel, contender_result),
        )
        holder.start()
        contender.start()

        deadline = time.monotonic() + 30.0
        while not os.path.exists(hold_sentinel):
            if time.monotonic() >= deadline:
                raise AssertionError("holder never entered callback")
            time.sleep(0.05)

        with open(start_sentinel, "w", encoding="utf-8") as fh:
            fh.write("go")

        contender.join(timeout=_JOIN_TIMEOUT)
        assert contender.exitcode == 0, f"contender exited with {contender.exitcode}"

        with open(contender_result, encoding="utf-8") as fh:
            contender_out = json.load(fh)
        assert contender_out == {
            "ok": False,
            "reason": pl.REASON_LOCK_UNAVAILABLE,
            "record": None,
        }

        with open(release_sentinel, "w", encoding="utf-8") as fh:
            fh.write("release")

        holder.join(timeout=_JOIN_TIMEOUT)
        assert holder.exitcode == 0, f"holder exited with {holder.exitcode}"

        with open(holder_result, encoding="utf-8") as fh:
            holder_out = json.load(fh)
        assert holder_out["ok"]
        assert holder_out["record"]["generation"] == start_gen + 1

        final = pl.read_record(path)
        assert final["ok"]
        assert final["record"]["generation"] == start_gen + 1
    finally:
        shutil.rmtree(tmp)


def test_concurrent_create_slot():
    multiprocessing.set_start_method("spawn", force=True)
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        n = 8
        results_dir = os.path.join(tmp, "results")
        os.makedirs(results_dir)
        barrier = multiprocessing.Barrier(n)
        processes = []
        for index in range(n):
            proc = multiprocessing.Process(
                target=_create_slot_concurrency_worker,
                args=(slots_path, SLOT, barrier, index, results_dir),
            )
            processes.append(proc)
            proc.start()
        for proc in processes:
            proc.join(timeout=_JOIN_TIMEOUT)
        for proc in processes:
            assert proc.exitcode == 0, f"worker exited with {proc.exitcode}"
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
        assert successes[0]["record"]["generation"] == pl.INITIAL_GENERATION
        for failure in failures:
            assert failure["reason"] in (
                pl.REASON_RECORD_EXISTS,
                pl.REASON_LOCK_UNAVAILABLE,
            )

        final = pl.read_record(pl.record_path(slots_path, SLOT))
        assert final["ok"]
        assert final["record"]["generation"] == pl.INITIAL_GENERATION
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


@pytest.mark.parametrize("bad_state", [[], {}])
def test_read_record_unhashable_state_refuses(bad_state):
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec["state"] = bad_state
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
        slots_path = os.path.join(tmp, "slots")
        slot_path = pl.record_path(slots_path, SLOT)
        os.makedirs(os.path.dirname(slot_path), exist_ok=True)
        shutil.copy(path, slot_path)
        mutate_result = pl.mutate(slots_path, SLOT, lambda r: r)
        assert mutate_result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


@pytest.mark.parametrize("field,value", [("to", []), ("from", {})])
def test_read_record_unhashable_history_refuses(field, value):
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec["history"][-1][field] = value
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
        slots_path = os.path.join(tmp, "slots")
        slot_path = pl.record_path(slots_path, SLOT)
        os.makedirs(os.path.dirname(slot_path), exist_ok=True)
        shutil.copy(path, slot_path)
        mutate_result = pl.mutate(slots_path, SLOT, lambda r: r)
        assert mutate_result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_create_slot_refuses_unreadable_existing_record():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, SLOT)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        original_ino = os.stat(path).st_ino
        original_bytes = open(path, "rb").read()
        os.chmod(path, 0o000)
        try:
            result = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        except PermissionError:
            pytest.skip(
                "mode 0o000 record file did not prevent read for this user"
            )
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_UNREADABLE,
            "record": None,
        }
        os.chmod(path, 0o644)
        assert os.stat(path).st_ino == original_ino
        assert open(path, "rb").read() == original_bytes
    finally:
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
        shutil.rmtree(tmp)


def test_create_slot_refuses_dangling_record_symlink():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        slot_dir = os.path.join(slots_path, SLOT)
        os.makedirs(slot_dir)
        record = pl.record_path(slots_path, SLOT)
        os.symlink(os.path.join(tmp, "nowhere"), record)
        result = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_UNREADABLE,
            "record": None,
        }
        assert os.path.islink(record)
    finally:
        shutil.rmtree(tmp)


def test_create_slot_succeeds_when_record_absent():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        result = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        assert result["ok"]
        assert result["record"]["generation"] == pl.INITIAL_GENERATION
    finally:
        shutil.rmtree(tmp)


def test_transition_refuses_non_serialisable_detail():
    rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
    with _raises(pl.REASON_RECORD_INVALID):
        pl.transition(rec, pl.STATE_PROVISIONED, now=NOW, detail={"a": {1, 2}})


def test_read_record_refuses_non_serialisable_detail():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec["history"][-1]["detail"] = {"a": float("nan")}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_write_record_refuses_non_serialisable_detail():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec["history"][-1]["detail"] = {"a": {1, 2}}
        result = pl.write_record(path, rec)
        assert result == {"ok": False, "reason": pl.REASON_RECORD_INVALID}
        assert not os.path.exists(path)
    finally:
        shutil.rmtree(tmp)


def test_mutate_refuses_callback_returning_wrong_slot():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, "slot1")
        rec = pl.new_record("slot1", ACCOUNTS, now=NOW)
        assert pl.write_record(path, rec)["ok"]
        original_bytes = open(path, "rb").read()

        def fn(_record):
            return pl.new_record("slot2", ACCOUNTS, now=NOW)

        result = pl.mutate(slots_path, "slot1", fn)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_SLOT_MISMATCH,
            "record": None,
        }
        assert open(path, "rb").read() == original_bytes
    finally:
        shutil.rmtree(tmp)


def test_slot_lock_refuses_dangling_slot_dir_symlink():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        os.makedirs(slots_path)
        os.symlink(os.path.join(tmp, "nowhere"), os.path.join(slots_path, SLOT))
        with _raises(pl.REASON_SLOT_DIR_UNSAFE):
            with pl.slot_lock(slots_path, SLOT):
                pass
    finally:
        shutil.rmtree(tmp)


def test_mutate_refuses_dangling_slot_dir_symlink():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        os.makedirs(slots_path)
        os.symlink(os.path.join(tmp, "nowhere"), os.path.join(slots_path, SLOT))
        result = pl.mutate(slots_path, SLOT, lambda r: r)
        assert result == {
            "ok": False,
            "reason": pl.REASON_SLOT_DIR_UNSAFE,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_create_slot_refuses_dangling_slot_dir_symlink():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        os.makedirs(slots_path)
        os.symlink(os.path.join(tmp, "nowhere"), os.path.join(slots_path, SLOT))
        result = pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW)
        assert result == {
            "ok": False,
            "reason": pl.REASON_SLOT_DIR_UNSAFE,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_read_record_refuses_symlinked_record():
    tmp = _tmp_dir()
    try:
        target = os.path.join(tmp, "target.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        path = os.path.join(tmp, "slot.json")
        os.symlink(target, path)
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_UNREADABLE,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def test_mutate_refuses_symlinked_record():
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        slot_dir = os.path.join(slots_path, SLOT)
        os.makedirs(slot_dir)
        target = os.path.join(tmp, "target.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        path = pl.record_path(slots_path, SLOT)
        os.symlink(target, path)
        callback_ran = []

        def fn(_record):
            callback_ran.append(True)
            return _record

        result = pl.mutate(slots_path, SLOT, fn)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_UNREADABLE,
            "record": None,
        }
        assert not callback_ran
    finally:
        shutil.rmtree(tmp)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no os.mkfifo on this platform")
def test_read_record_refuses_fifo_without_blocking():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        os.mkfifo(path)
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_UNREADABLE,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp)


def _create_slot_lock_holder_worker(
    slots_dir_path,
    slot,
    hold_sentinel,
    release_sentinel,
    done_sentinel,
    result_path,
):
    with pl.slot_lock(slots_dir_path, slot, timeout=30.0):
        with open(hold_sentinel, "w", encoding="utf-8") as fh:
            fh.write("holding")
        deadline = time.monotonic() + 30.0
        while not os.path.exists(release_sentinel):
            if time.monotonic() >= deadline:
                raise RuntimeError("timed out waiting for release sentinel")
            time.sleep(0.05)
    result = pl.create_slot(
        slots_dir_path, slot, ACCOUNTS, now=_CONCURRENCY_NOW
    )
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    with open(done_sentinel, "w", encoding="utf-8") as fh:
        fh.write("done")


def _create_slot_lock_contender_worker(
    slots_dir_path,
    slot,
    start_sentinel,
    result_path,
):
    deadline = time.monotonic() + 30.0
    while not os.path.exists(start_sentinel):
        if time.monotonic() >= deadline:
            raise RuntimeError("timed out waiting for start sentinel")
        time.sleep(0.05)
    result = pl.create_slot(
        slots_dir_path, slot, ACCOUNTS, now=_CONCURRENCY_NOW, timeout=0.5
    )
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)


def test_create_slot_lock_held_blocks_contender():
    multiprocessing.set_start_method("spawn", force=True)
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        hold_sentinel = os.path.join(tmp, "hold")
        release_sentinel = os.path.join(tmp, "release")
        start_sentinel = os.path.join(tmp, "start")
        done_sentinel = os.path.join(tmp, "done")
        contender_result = os.path.join(tmp, "contender.json")

        holder = multiprocessing.Process(
            target=_create_slot_lock_holder_worker,
            args=(
                slots_path,
                SLOT,
                hold_sentinel,
                release_sentinel,
                done_sentinel,
                os.path.join(tmp, "holder.json"),
            ),
        )
        contender = multiprocessing.Process(
            target=_create_slot_lock_contender_worker,
            args=(slots_path, SLOT, start_sentinel, contender_result),
        )
        holder.start()
        contender.start()

        deadline = time.monotonic() + 30.0
        while not os.path.exists(hold_sentinel):
            if time.monotonic() >= deadline:
                raise AssertionError("holder never acquired lock")
            time.sleep(0.05)

        with open(start_sentinel, "w", encoding="utf-8") as fh:
            fh.write("go")

        contender.join(timeout=_JOIN_TIMEOUT)
        assert contender.exitcode == 0, f"contender exited with {contender.exitcode}"

        with open(contender_result, encoding="utf-8") as fh:
            contender_out = json.load(fh)
        assert contender_out == {
            "ok": False,
            "reason": pl.REASON_LOCK_UNAVAILABLE,
            "record": None,
        }

        with open(release_sentinel, "w", encoding="utf-8") as fh:
            fh.write("release")

        holder.join(timeout=_JOIN_TIMEOUT)
        assert holder.exitcode == 0, f"holder exited with {holder.exitcode}"

        final = pl.read_record(pl.record_path(slots_path, SLOT))
        assert final["ok"]
        assert final["record"]["generation"] == pl.INITIAL_GENERATION
    finally:
        shutil.rmtree(tmp)
