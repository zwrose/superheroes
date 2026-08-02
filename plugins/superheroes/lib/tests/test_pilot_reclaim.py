"""Tests for pilot slot reclaim — quarantine, sweep, deletion authorization."""
import errno
import json
import os
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timedelta
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_reclaim as pr  # noqa: E402

_NOW = "2026-08-02T15:45:00Z"
_NOW_EARLY = "2026-08-02T12:00:00Z"
_NOW_LATE = "2026-08-05T16:00:00Z"
_SLOT = "slot-a"
_SLOT_REF = "slot-a@1"
_REASON = "stale-occupant"


def _reason_constants():
    return {
        getattr(pr, name)
        for name in dir(pr)
        if name.startswith("REASON_") and isinstance(getattr(pr, name), str)
    }


def _occupant(**kwargs):
    base = {
        "pid": 12345,
        "processInstance": "inst-abc",
        "livenessSource": "mtime",
        "observedAt": _NOW_EARLY,
    }
    base.update(kwargs)
    return base


def _slots_dir(tmp_path):
    path = os.path.join(str(tmp_path), "slots")
    os.makedirs(path)
    return path


def _payload_dir(parent):
    path = os.path.join(parent, "occupant-payload")
    os.makedirs(path)
    marker = os.path.join(path, "work.txt")
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write("payload")
    return path


def _quarantine(slots_dir, source_path=None, *, now=_NOW, occupant=None):
    if source_path is None:
        source_path = _payload_dir(os.path.dirname(slots_dir))
    if occupant is None:
        occupant = _occupant()
    return pr.quarantine_entry(
        slots_dir, source_path,
        slot_ref=_SLOT_REF, reason=_REASON, occupant=occupant, now=now,
    )


def _receipt_for(sidecar, *, observed_at=_NOW_LATE, wait_status=0):
    return pr.terminal_receipt(
        pid=sidecar["occupant"]["pid"],
        process_instance=sidecar["occupant"]["processInstance"],
        wait_status=wait_status,
        entry_name=sidecar["entryName"],
        slot_ref=sidecar["slotRef"],
        observed_at=observed_at,
    )["receipt"]


def _write_sidecar_raw(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


# --- quarantine_dir ---


def test_quarantine_dir_ok(tmp_path):
    slots = _slots_dir(tmp_path)
    result = pr.quarantine_dir(slots)
    assert result == {
        "ok": True,
        "reason": None,
        "path": os.path.join(slots, pr.QUARANTINE_DIR_NAME),
    }


@pytest.mark.parametrize("bad", [None, "", 0, [], b"x"])
def test_quarantine_dir_refuses_invalid_slots_dir(bad):
    result = pr.quarantine_dir(bad)
    assert result["ok"] is False
    assert result["reason"] == pr.REASON_SLOTS_DIR_INVALID


# --- validate_occupant ---


def test_validate_occupant_ok():
    occ = _occupant()
    result = pr.validate_occupant(occ)
    assert result["ok"] is True
    assert result["occupant"] == occ
    assert result["occupant"] is not occ


@pytest.mark.parametrize("bad_pid", [0, True, 1.0, "1"])
def test_validate_occupant_refuses_bad_pid(bad_pid):
    result = pr.validate_occupant(_occupant(pid=bad_pid))
    assert result["reason"] == pr.REASON_OCCUPANT_INVALID


def test_validate_occupant_allows_none_pid():
    result = pr.validate_occupant(_occupant(pid=None))
    assert result["ok"] is True


@pytest.mark.parametrize("bad_pi", ["", "x" * 201])
def test_validate_occupant_refuses_bad_process_instance(bad_pi):
    result = pr.validate_occupant(_occupant(processInstance=bad_pi))
    assert result["reason"] == pr.REASON_OCCUPANT_INVALID


def test_validate_occupant_refuses_unknown_liveness_source():
    result = pr.validate_occupant(_occupant(livenessSource="bogus"))
    assert result["reason"] == pr.REASON_OCCUPANT_INVALID


def test_validate_occupant_refuses_bad_observed_at():
    result = pr.validate_occupant(_occupant(observedAt="not-iso"))
    assert result["reason"] == pr.REASON_OCCUPANT_INVALID


def test_validate_occupant_refuses_extra_keys():
    occ = _occupant()
    occ["extra"] = True
    result = pr.validate_occupant(occ)
    assert result["reason"] == pr.REASON_OCCUPANT_INVALID


# --- terminal_receipt ---


def test_terminal_receipt_ok():
    result = pr.terminal_receipt(
        pid=99, process_instance="pi", wait_status=0,
        entry_name="e1", slot_ref=_SLOT_REF, observed_at=_NOW,
    )
    assert result["ok"] is True
    assert result["receipt"]["source"] == "process-exit-status"
    assert result["receipt"]["schemaVersion"] == 1


@pytest.mark.parametrize("bad_pid", [0, True, None, 1.0])
def test_terminal_receipt_refuses_bad_pid(bad_pid):
    result = pr.terminal_receipt(
        pid=bad_pid, process_instance="pi", wait_status=0,
        entry_name="e1", slot_ref=_SLOT_REF, observed_at=_NOW,
    )
    assert result["reason"] == pr.REASON_RECEIPT_INVALID


def test_terminal_receipt_refuses_bool_wait_status():
    result = pr.terminal_receipt(
        pid=1, process_instance="pi", wait_status=True,
        entry_name="e1", slot_ref=_SLOT_REF, observed_at=_NOW,
    )
    assert result["reason"] == pr.REASON_RECEIPT_INVALID


def test_terminal_receipt_allows_negative_wait_status():
    result = pr.terminal_receipt(
        pid=1, process_instance="pi", wait_status=-1,
        entry_name="e1", slot_ref=_SLOT_REF, observed_at=_NOW,
    )
    assert result["ok"] is True


def test_terminal_receipt_refuses_bad_slot_ref():
    result = pr.terminal_receipt(
        pid=1, process_instance="pi", wait_status=0,
        entry_name="e1", slot_ref="bad", observed_at=_NOW,
    )
    assert result["reason"] == pr.REASON_RECEIPT_INVALID


# --- quarantine_entry round trip ---


def test_quarantine_entry_round_trip(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    result = _quarantine(slots, source)
    assert result["ok"] is True
    assert not os.path.exists(source)
    assert os.path.isdir(result["entryPath"])
    assert os.path.isfile(result["sidecarPath"])
    assert os.path.isfile(os.path.join(result["entryPath"], "work.txt"))
    loaded = pr.read_sidecar(result["sidecarPath"])
    assert loaded["ok"] is True
    assert loaded["sidecar"]["move"] == pr.MOVE_MOVED
    assert loaded["sidecar"]["status"] == pr.STATUS_QUARANTINED


# --- quarantine_entry refusals ---


@pytest.mark.parametrize("bad", [None, "", 0])
def test_quarantine_entry_refuses_invalid_slots_dir(tmp_path, bad):
    source = _payload_dir(str(tmp_path))
    result = pr.quarantine_entry(
        bad, source, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SLOTS_DIR_INVALID


@pytest.mark.parametrize("bad", [None, "relative/path", "/nonexistent-x", b"x"])
def test_quarantine_entry_refuses_invalid_source(tmp_path, bad):
    slots = _slots_dir(tmp_path)
    if bad == "relative/path":
        bad = os.path.join("relative", "path")
    result = pr.quarantine_entry(
        slots, bad, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INVALID


def test_quarantine_entry_refuses_symlink_source(tmp_path):
    slots = _slots_dir(tmp_path)
    real = _payload_dir(str(tmp_path))
    link = os.path.join(str(tmp_path), "link")
    os.symlink(real, link)
    result = pr.quarantine_entry(
        slots, link, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INVALID


def test_quarantine_entry_refuses_file_source(tmp_path):
    slots = _slots_dir(tmp_path)
    fpath = os.path.join(str(tmp_path), "file.txt")
    with open(fpath, "w") as fh:
        fh.write("x")
    result = pr.quarantine_entry(
        slots, fpath, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INVALID


def test_quarantine_entry_refuses_source_inside_slots_dir(tmp_path):
    slots = _slots_dir(tmp_path)
    inside = os.path.join(slots, "inner")
    os.makedirs(inside)
    result = pr.quarantine_entry(
        slots, inside, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INSIDE_SLOT_STORE


def test_quarantine_entry_refuses_source_equal_slots_dir(tmp_path):
    slots = _slots_dir(tmp_path)
    result = pr.quarantine_entry(
        slots, slots, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INSIDE_SLOT_STORE


def test_quarantine_entry_refuses_source_ancestor_of_slots_dir(tmp_path):
    parent = os.path.join(str(tmp_path), "parent")
    slots = os.path.join(parent, "slots")
    os.makedirs(slots)
    result = pr.quarantine_entry(
        slots, parent, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INSIDE_SLOT_STORE


def test_quarantine_entry_containment_near_miss(tmp_path, private_tmp):
    """/a/bc must not be treated as inside /a/b."""
    a = os.path.join(private_tmp, "a")
    b = os.path.join(a, "b")
    bc = os.path.join(a, "bc")
    os.makedirs(b)
    os.makedirs(bc)
    source = _payload_dir(bc)
    result = pr.quarantine_entry(
        b, source, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["ok"] is True


def test_quarantine_entry_refuses_bad_slot_ref(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    result = pr.quarantine_entry(
        slots, source, slot_ref="bad", reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SLOT_REF_INVALID


@pytest.mark.parametrize("bad", ["", "x" * 501])
def test_quarantine_entry_refuses_bad_reason(tmp_path, bad):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    result = pr.quarantine_entry(
        slots, source, slot_ref=_SLOT_REF, reason=bad,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_REASON_INVALID


def test_quarantine_entry_refuses_bad_now(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    result = pr.quarantine_entry(
        slots, source, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now="2026-01-01",
    )
    assert result["reason"] == pr.REASON_NOW_INVALID


def test_quarantine_entry_refuses_entry_exists(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    first = _quarantine(slots, source)
    assert first["ok"] is True
    source2 = _payload_dir(str(tmp_path))
    result = pr.quarantine_entry(
        slots, source2, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_ENTRY_EXISTS


def test_quarantine_entry_refuses_cross_device(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    with mock.patch("os.rename", side_effect=OSError(errno.EXDEV, "cross")):
        result = pr.quarantine_entry(
            slots, source, slot_ref=_SLOT_REF, reason=_REASON,
            occupant=_occupant(), now=_NOW,
        )
    assert result["reason"] == pr.REASON_CROSS_DEVICE
    assert os.path.isdir(source)


def test_quarantine_entry_refuses_rename_failed(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    with mock.patch("os.rename", side_effect=OSError(errno.EACCES, "denied")):
        result = pr.quarantine_entry(
            slots, source, slot_ref=_SLOT_REF, reason=_REASON,
            occupant=_occupant(), now=_NOW,
        )
    assert result["reason"] == pr.REASON_RENAME_FAILED
    assert os.path.isdir(source)


def test_quarantine_entry_sidecar_write_failed_before_rename(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    with mock.patch.object(pr.store_core, "atomic_write", side_effect=OSError("fail")):
        result = pr.quarantine_entry(
            slots, source, slot_ref=_SLOT_REF, reason=_REASON,
            occupant=_occupant(), now=_NOW,
        )
    assert result["reason"] == pr.REASON_SIDECAR_WRITE_FAILED
    assert result["entryName"] is None
    assert os.path.isdir(source)


def test_quarantine_entry_sidecar_write_failed_after_rename(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    original = pr.store_core.atomic_write
    calls = {"n": 0}

    def flaky_write(path, text, tmp_prefix=".store-core."):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("fail second write")
        return original(path, text, tmp_prefix=tmp_prefix)

    with mock.patch.object(pr.store_core, "atomic_write", side_effect=flaky_write):
        result = pr.quarantine_entry(
            slots, source, slot_ref=_SLOT_REF, reason=_REASON,
            occupant=_occupant(), now=_NOW,
        )
    assert result["reason"] == pr.REASON_SIDECAR_WRITE_FAILED
    assert result["entryName"] is not None
    assert not os.path.exists(source)
    assert os.path.isdir(result["entryPath"])


# --- read_sidecar ---


def test_read_sidecar_absent(tmp_path):
    result = pr.read_sidecar("/nonexistent/sidecar.quarantine.json")
    assert result["reason"] == pr.REASON_SIDECAR_ABSENT


def test_read_sidecar_unreadable(tmp_path):
    slots = _slots_dir(tmp_path)
    q = pr.quarantine_dir(slots)["path"]
    os.makedirs(q)
    path = os.path.join(q, "x.quarantine.json")
    os.makedirs(path)
    result = pr.read_sidecar(path)
    assert result["reason"] == pr.REASON_SIDECAR_UNREADABLE


def test_read_sidecar_invalid_json(tmp_path):
    slots = _slots_dir(tmp_path)
    q = pr.quarantine_dir(slots)["path"]
    os.makedirs(q)
    path = os.path.join(q, "x.quarantine.json")
    with open(path, "w") as fh:
        fh.write("not json")
    result = pr.read_sidecar(path)
    assert result["reason"] == pr.REASON_SIDECAR_INVALID


def test_read_sidecar_slot_ref_mismatch(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots)
    loaded = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    loaded["slotRef"] = "slot-b@2"
    _write_sidecar_raw(result["sidecarPath"], loaded)
    reread = pr.read_sidecar(result["sidecarPath"])
    assert reread["reason"] == pr.REASON_SIDECAR_INVALID


# --- authorize_deletion ---


def _sidecar_for_auth(**kwargs):
    base = {
        "schemaVersion": 1,
        "entryName": "slot-a-gen1-ts",
        "originalPath": "/tmp/x",
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "generation": 1,
        "reason": _REASON,
        "quarantinedAt": _NOW_EARLY,
        "expiresAt": _NOW_LATE,
        "move": pr.MOVE_MOVED,
        "status": pr.STATUS_QUARANTINED,
        "occupant": _occupant(),
    }
    base.update(kwargs)
    return base


def test_authorize_deletion_ok():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["ok"] is True


def test_authorize_deletion_grace_not_elapsed():
    sidecar = _sidecar_for_auth(quarantinedAt=_NOW)
    receipt = _receipt_for(sidecar, observed_at=_NOW_LATE)
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW)
    assert result["reason"] == pr.REASON_GRACE_NOT_ELAPSED


def test_authorize_deletion_receipt_invalid():
    sidecar = _sidecar_for_auth()
    result = pr.authorize_deletion(sidecar, {"bad": True}, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_INVALID


def test_authorize_deletion_source_not_terminal():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["source"] = "mtime"
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_SOURCE_NOT_TERMINAL


def test_validate_occupant_allows_none_process_instance():
    result = pr.validate_occupant(_occupant(processInstance=None))
    assert result["ok"] is True


def test_authorize_deletion_not_independent():
    sidecar = _sidecar_for_auth(occupant=_occupant(livenessSource="mtime"))
    receipt = _receipt_for(sidecar)
    sidecar["occupant"]["livenessSource"] = "process-exit-status"
    with mock.patch.object(pr, "_validate_sidecar_dict", return_value=True):
        result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_NOT_INDEPENDENT


def test_liveness_and_terminal_sources_disjoint():
    """The independence branch is unreachable via real call shape when sets are disjoint."""
    assert pr.LIVENESS_SOURCES.isdisjoint(pr.TERMINAL_SOURCES)


def test_independence_branch_refuses_when_reached_defensive():
    """Defensive branch only — unreachable via real call shape today.

    LIVENESS_SOURCES and TERMINAL_SOURCES are disjoint; test_liveness_and_terminal_sources_disjoint
    is the live guarantee. This test pins the defensive branch's behaviour if they ever overlap.
    """
    sidecar = _sidecar_for_auth(occupant=_occupant(livenessSource="mtime"))
    receipt = _receipt_for(sidecar)
    sidecar["occupant"]["livenessSource"] = "process-exit-status"
    with mock.patch.object(pr, "_validate_sidecar_dict", return_value=True):
        result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_NOT_INDEPENDENT


def test_authorize_deletion_occupant_unbound():
    sidecar = _sidecar_for_auth(occupant=_occupant(pid=None))
    receipt = pr.terminal_receipt(
        pid=12345, process_instance="inst-abc", wait_status=0,
        entry_name=sidecar["entryName"], slot_ref=sidecar["slotRef"],
        observed_at=_NOW_LATE,
    )["receipt"]
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_OCCUPANT_UNBOUND


def test_authorize_deletion_binding_mismatch_entry_name():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["entryName"] = "wrong"
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_BINDING_MISMATCH


def test_authorize_deletion_binding_mismatch_process_instance():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["processInstance"] = "wrong-instance"
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_BINDING_MISMATCH


def test_authorize_deletion_binding_mismatch_slot_ref():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["slotRef"] = "slot-b@2"
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_BINDING_MISMATCH


def test_authorize_deletion_binding_mismatch():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["pid"] = 99999
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_BINDING_MISMATCH


def test_authorize_deletion_predates_liveness():
    sidecar = _sidecar_for_auth(occupant=_occupant(observedAt=_NOW_LATE))
    receipt = _receipt_for(sidecar, observed_at=_NOW_EARLY)
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_RECEIPT_PREDATES_LIVENESS


def test_authorize_deletion_entry_not_moved():
    sidecar = _sidecar_for_auth(move=pr.MOVE_PENDING)
    receipt = _receipt_for(sidecar)
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_ENTRY_NOT_MOVED


def test_authorize_deletion_status_not_deletable():
    sidecar = _sidecar_for_auth(status=pr.STATUS_DELETED)
    receipt = _receipt_for(sidecar)
    sidecar["terminalReceipt"] = receipt
    result = pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_STATUS_NOT_DELETABLE


def test_authorize_deletion_sidecar_invalid():
    result = pr.authorize_deletion({}, {}, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_SIDECAR_INVALID


def test_authorize_deletion_now_invalid():
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    result = pr.authorize_deletion(sidecar, receipt, now="bad")
    assert result["reason"] == pr.REASON_NOW_INVALID


# --- sweep ---


def test_sweep_empty_quarantine(tmp_path):
    slots = _slots_dir(tmp_path)
    result = pr.sweep(slots, now=_NOW_LATE)
    assert result["ok"] is True
    assert result["deleted"] == []
    assert result["warned"] == []
    assert result["retained"] == []


def test_sweep_absent_quarantine(tmp_path):
    slots = _slots_dir(tmp_path)
    result = pr.sweep(slots, now=_NOW_LATE)
    assert result["ok"] is True


def test_sweep_grace_elapsed_no_receipt_warns_and_retains(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert sweep["ok"] is True
    assert len(sweep["retained"]) == 1
    assert len(sweep["warned"]) == 1
    assert sweep["deleted"] == []
    assert os.path.isdir(result["entryPath"])


def test_sweep_deletes_with_receipt_after_grace(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    sweep = pr.sweep(slots, now=_NOW_LATE, receipts={sidecar["entryName"]: receipt})
    assert sweep["ok"] is True
    assert len(sweep["deleted"]) == 1
    assert not os.path.exists(result["entryPath"])
    tombstone = pr.read_sidecar(result["sidecarPath"])
    assert tombstone["sidecar"]["status"] == pr.STATUS_DELETED


def test_sweep_tombstone_retained_not_warned(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    pr.sweep(slots, now=_NOW_LATE, receipts={sidecar["entryName"]: receipt})
    sweep2 = pr.sweep(slots, now=_NOW_LATE)
    assert len(sweep2["retained"]) == 1
    assert sweep2["warned"] == []


def test_sweep_pending_repair(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots)
    sidecar_path = result["sidecarPath"]
    loaded = pr.read_sidecar(sidecar_path)["sidecar"]
    loaded["move"] = pr.MOVE_PENDING
    _write_sidecar_raw(sidecar_path, loaded)
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert len(sweep["warned"]) >= 1
    assert len(sweep["retained"]) >= 1
    repaired = pr.read_sidecar(sidecar_path)
    assert repaired["sidecar"]["move"] == pr.MOVE_MOVED


def test_sweep_pending_no_entry_warns(tmp_path):
    slots = _slots_dir(tmp_path)
    q = pr.quarantine_dir(slots)["path"]
    os.makedirs(q)
    sidecar_path = os.path.join(q, "orphan.quarantine.json")
    sidecar = _sidecar_for_auth(entryName="orphan", move=pr.MOVE_PENDING)
    _write_sidecar_raw(sidecar_path, sidecar)
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert len(sweep["warned"]) >= 1
    assert len(sweep["retained"]) >= 1


def test_sweep_payload_without_sidecar(tmp_path):
    slots = _slots_dir(tmp_path)
    q = pr.quarantine_dir(slots)["path"]
    os.makedirs(q)
    os.makedirs(os.path.join(q, "lonely-payload"))
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert any(w["reason"] == pr.REASON_SIDECAR_ABSENT for w in sweep["warned"])


def test_sweep_resumes_deletion_authorized(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    auth_sidecar = dict(sidecar)
    auth_sidecar["status"] = pr.STATUS_DELETION_AUTHORIZED
    auth_sidecar["terminalReceipt"] = receipt
    auth_sidecar["deletionAuthorizedAt"] = _NOW_LATE
    _write_sidecar_raw(result["sidecarPath"], auth_sidecar)
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert len(sweep["deleted"]) == 1
    assert sweep["deleted"][0]["kind"] == "entry"


def test_sweep_refuses_deletion_authorized_without_receipt(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    auth_sidecar = dict(sidecar)
    auth_sidecar["status"] = pr.STATUS_DELETION_AUTHORIZED
    auth_sidecar["deletionAuthorizedAt"] = _NOW_LATE
    _write_sidecar_raw(result["sidecarPath"], auth_sidecar)
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert sweep["deleted"] == []
    assert os.path.isdir(result["entryPath"])
    assert any(
        w["reason"] == pr.REASON_SIDECAR_STATUS_UNBACKED for w in sweep["warned"]
    )


def test_sweep_refuses_sidecar_entry_name_mismatch(tmp_path):
    slots = _slots_dir(tmp_path)
    result_a = _quarantine(slots, now=_NOW_EARLY)
    loaded = pr.read_sidecar(result_a["sidecarPath"])["sidecar"]
    loaded["entryName"] = "wrong-entry-name"
    _write_sidecar_raw(result_a["sidecarPath"], loaded)
    receipt = _receipt_for(loaded)
    sweep = pr.sweep(
        slots, now=_NOW_LATE,
        receipts={loaded["entryName"]: receipt},
    )
    assert sweep["deleted"] == []
    assert os.path.isdir(result_a["entryPath"])
    assert any(
        w["reason"] == pr.REASON_SIDECAR_ENTRY_NAME_MISMATCH for w in sweep["warned"]
    )


def test_sweep_partial_rmtree_then_resume(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    entry_path = result["entryPath"]
    child = os.path.join(entry_path, "subdir")
    os.makedirs(child)
    with open(os.path.join(child, "x.txt"), "w") as fh:
        fh.write("x")
    calls = {"n": 0}
    original_rmtree = pr.shutil.rmtree

    def partial_rmtree(path, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            os.remove(os.path.join(path, "work.txt"))
            raise OSError("partial")
        return original_rmtree(path, *args, **kwargs)

    with mock.patch.object(pr.shutil, "rmtree", side_effect=partial_rmtree):
        sweep1 = pr.sweep(
            slots, now=_NOW_LATE,
            receipts={sidecar["entryName"]: receipt},
        )
    assert any(e["reason"] == pr.REASON_DELETE_FAILED for e in sweep1["warned"])
    assert os.path.lexists(entry_path)
    sweep2 = pr.sweep(slots, now=_NOW_LATE)
    assert len(sweep2["deleted"]) == 1
    assert not os.path.exists(entry_path)
    tombstone = pr.read_sidecar(result["sidecarPath"])
    assert tombstone["sidecar"]["status"] == pr.STATUS_DELETED


def test_sweep_resume_payload_gone_tombstone_write(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    auth_sidecar = dict(sidecar)
    auth_sidecar["status"] = pr.STATUS_DELETION_AUTHORIZED
    auth_sidecar["terminalReceipt"] = receipt
    auth_sidecar["deletionAuthorizedAt"] = _NOW_LATE
    _write_sidecar_raw(result["sidecarPath"], auth_sidecar)
    shutil.rmtree(result["entryPath"])
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert len(sweep["retained"]) == 1
    tombstone = pr.read_sidecar(result["sidecarPath"])
    assert tombstone["sidecar"]["status"] == pr.STATUS_DELETED


def test_sweep_pending_move_not_applied(tmp_path):
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    q = pr.quarantine_dir(slots)["path"]
    os.makedirs(q)
    sidecar_path = os.path.join(q, "stale.quarantine.json")
    sidecar = _sidecar_for_auth(
        entryName="stale",
        originalPath=source,
        move=pr.MOVE_PENDING,
    )
    _write_sidecar_raw(sidecar_path, sidecar)
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert any(
        w["reason"] == pr.REASON_PENDING_MOVE_NOT_APPLIED for w in sweep["warned"]
    )
    assert os.path.isdir(source)


def test_sweep_refuses_symlinked_quarantine(tmp_path):
    slots = _slots_dir(tmp_path)
    real_q = os.path.join(str(tmp_path), "real-quarantine")
    os.makedirs(real_q)
    link_q = os.path.join(slots, pr.QUARANTINE_DIR_NAME)
    os.symlink(real_q, link_q)
    result = pr.sweep(slots, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_QUARANTINE_DIR_UNSAFE


def test_quarantine_entry_refuses_symlinked_quarantine(tmp_path):
    slots = _slots_dir(tmp_path)
    real_q = os.path.join(str(tmp_path), "real-quarantine")
    os.makedirs(real_q)
    link_q = os.path.join(slots, pr.QUARANTINE_DIR_NAME)
    os.symlink(real_q, link_q)
    source = _payload_dir(str(tmp_path))
    result = pr.quarantine_entry(
        slots, source, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_QUARANTINE_DIR_UNSAFE
    assert os.path.isdir(source)


def test_sweep_warned_retained_deleted_have_kind(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    sweep = pr.sweep(slots, now=_NOW_LATE, receipts={sidecar["entryName"]: receipt})
    for entry in sweep["deleted"] + sweep["retained"] + sweep["warned"]:
        assert entry["kind"] == "entry"
    slot_dir = os.path.join(slots, _SLOT)
    os.makedirs(slot_dir)
    open(os.path.join(slot_dir, "journal.ndjson"), "w").close()
    for i in range(pr.SEGMENT_WARN_COUNT):
        open(os.path.join(slot_dir, "journal.%04d.ndjson" % (i + 1)), "w").close()
    sweep2 = pr.sweep(slots, now=_NOW_LATE)
    journal_warns = [w for w in sweep2["warned"] if w.get("reason") == pr.REASON_JOURNAL_SEGMENTS_HIGH]
    assert len(journal_warns) >= 1
    assert journal_warns[0]["kind"] == "journal-segments"


def test_sweep_non_default_journal_segments_counted(tmp_path):
    slots = _slots_dir(tmp_path)
    slot_dir = os.path.join(slots, _SLOT)
    os.makedirs(slot_dir)
    for i in range(pr.SEGMENT_WARN_COUNT):
        open(os.path.join(slot_dir, "events.%04d.ndjson" % (i + 1)), "w").close()
    open(os.path.join(slot_dir, "events.ndjson"), "w").close()
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert any(
        w.get("reason") == pr.REASON_JOURNAL_SEGMENTS_HIGH for w in sweep["warned"]
    )


def test_read_sidecar_refuses_bool_schema_version(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots)
    loaded = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    loaded["schemaVersion"] = True
    _write_sidecar_raw(result["sidecarPath"], loaded)
    reread = pr.read_sidecar(result["sidecarPath"])
    assert reread["reason"] == pr.REASON_SIDECAR_INVALID


def test_sweep_delete_failed_retained(tmp_path):
    slots = _slots_dir(tmp_path)
    result = _quarantine(slots, now=_NOW_EARLY)
    sidecar = pr.read_sidecar(result["sidecarPath"])["sidecar"]
    receipt = _receipt_for(sidecar)
    with mock.patch.object(pr.shutil, "rmtree", side_effect=OSError("fail")):
        sweep = pr.sweep(
            slots, now=_NOW_LATE,
            receipts={sidecar["entryName"]: receipt},
        )
    assert any(
        e["reason"] == pr.REASON_DELETE_FAILED for e in sweep["warned"]
    )
    assert os.path.isdir(result["entryPath"])


def test_sweep_quarantine_dir_unreadable(tmp_path):
    slots = _slots_dir(tmp_path)
    q = pr.quarantine_dir(slots)["path"]
    os.makedirs(q)
    with mock.patch("os.listdir", side_effect=OSError("fail")):
        result = pr.sweep(slots, now=_NOW_LATE)
    assert result["reason"] == pr.REASON_QUARANTINE_DIR_UNREADABLE


def test_sweep_receipts_not_mapping(tmp_path):
    slots = _slots_dir(tmp_path)
    result = pr.sweep(slots, now=_NOW_LATE, receipts=[])
    assert result["reason"] == pr.REASON_RECEIPT_INVALID


def test_sweep_journal_segments_high(tmp_path):
    slots = _slots_dir(tmp_path)
    slot_dir = os.path.join(slots, _SLOT)
    os.makedirs(slot_dir)
    open(os.path.join(slot_dir, "journal.ndjson"), "w").close()
    for i in range(pr.SEGMENT_WARN_COUNT):
        open(os.path.join(slot_dir, "journal.%04d.ndjson" % (i + 1)), "w").close()
    sweep = pr.sweep(slots, now=_NOW_LATE)
    assert any(
        w.get("reason") == pr.REASON_JOURNAL_SEGMENTS_HIGH for w in sweep["warned"]
    )


def test_all_reason_constants_discoverable():
    """Every refusal token has a REASON_* constant discoverable via dir(module)."""
    expected = {
        pr.REASON_SLOTS_DIR_INVALID,
        pr.REASON_SOURCE_INVALID,
        pr.REASON_SOURCE_INSIDE_SLOT_STORE,
        pr.REASON_SLOT_REF_INVALID,
        pr.REASON_REASON_INVALID,
        pr.REASON_OCCUPANT_INVALID,
        pr.REASON_NOW_INVALID,
        pr.REASON_ENTRY_EXISTS,
        pr.REASON_CROSS_DEVICE,
        pr.REASON_RENAME_FAILED,
        pr.REASON_SIDECAR_WRITE_FAILED,
        pr.REASON_SIDECAR_ABSENT,
        pr.REASON_SIDECAR_UNREADABLE,
        pr.REASON_SIDECAR_INVALID,
        pr.REASON_SIDECAR_STATUS_UNBACKED,
        pr.REASON_SIDECAR_ENTRY_NAME_MISMATCH,
        pr.REASON_QUARANTINE_DIR_UNSAFE,
        pr.REASON_PENDING_MOVE_NOT_APPLIED,
        pr.REASON_GRACE_NOT_ELAPSED,
        pr.REASON_RECEIPT_INVALID,
        pr.REASON_RECEIPT_SOURCE_NOT_TERMINAL,
        pr.REASON_RECEIPT_NOT_INDEPENDENT,
        pr.REASON_OCCUPANT_UNBOUND,
        pr.REASON_RECEIPT_BINDING_MISMATCH,
        pr.REASON_RECEIPT_PREDATES_LIVENESS,
        pr.REASON_ENTRY_NOT_MOVED,
        pr.REASON_STATUS_NOT_DELETABLE,
        pr.REASON_DELETE_FAILED,
        pr.REASON_QUARANTINE_DIR_UNREADABLE,
        pr.REASON_JOURNAL_SEGMENTS_HIGH,
    }
    assert expected <= _reason_constants()
    import re
    for token in _reason_constants():
        assert isinstance(token, str)
        assert token
        assert token.startswith("reclaim-")
        assert re.match(r"^[a-z0-9]+(-[a-z0-9]+)*\Z", token)


# --- bite-proof anchor tests (guards exercised by authorize_deletion / quarantine_entry) ---


def test_bite_grace_elapsed_required_for_deletion():
    """Guard: grace-elapsed condition in authorize_deletion."""
    sidecar = _sidecar_for_auth(quarantinedAt=_NOW)
    receipt = _receipt_for(sidecar, observed_at=_NOW_LATE)
    assert pr.authorize_deletion(sidecar, receipt, now=_NOW)["ok"] is False


def test_bite_terminal_source_required():
    """Guard: terminal-source condition in authorize_deletion."""
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["source"] = "heartbeat-record"
    assert pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)["ok"] is False


def test_bite_independence_required():
    """Guard: independence condition in authorize_deletion (defensive branch only)."""
    sidecar = _sidecar_for_auth(occupant=_occupant(livenessSource="lock-probe"))
    receipt = _receipt_for(sidecar)
    sidecar["occupant"]["livenessSource"] = "process-exit-status"
    with mock.patch.object(pr, "_validate_sidecar_dict", return_value=True):
        assert pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)["ok"] is False


def test_bite_occupant_bound_required():
    """Guard: occupant-bound condition in authorize_deletion."""
    sidecar = _sidecar_for_auth(occupant=_occupant(processInstance=None, pid=None))
    receipt = pr.terminal_receipt(
        pid=12345, process_instance="inst-abc", wait_status=0,
        entry_name=sidecar["entryName"], slot_ref=sidecar["slotRef"],
        observed_at=_NOW_LATE,
    )["receipt"]
    assert pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)["ok"] is False


def test_bite_receipt_binding_required():
    """Guard: receipt-binding condition in authorize_deletion."""
    sidecar = _sidecar_for_auth()
    receipt = _receipt_for(sidecar)
    receipt["entryName"] = "wrong"
    assert pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)["ok"] is False


def test_bite_chronology_required():
    """Guard: chronology condition in authorize_deletion."""
    sidecar = _sidecar_for_auth(occupant=_occupant(observedAt="2026-08-05T20:00:00Z"))
    receipt = _receipt_for(sidecar, observed_at=_NOW_LATE)
    assert pr.authorize_deletion(sidecar, receipt, now=_NOW_LATE)["ok"] is False


def test_bite_containment_refusal(tmp_path):
    """Guard: containment refusal in quarantine_entry."""
    slots = _slots_dir(tmp_path)
    inside = os.path.join(slots, "nested")
    os.makedirs(inside)
    result = pr.quarantine_entry(
        slots, inside, slot_ref=_SLOT_REF, reason=_REASON,
        occupant=_occupant(), now=_NOW,
    )
    assert result["reason"] == pr.REASON_SOURCE_INSIDE_SLOT_STORE


def test_bite_sidecar_first_ordering(tmp_path):
    """Guard: sidecar is written before rename (pending sidecar exists if rename fails)."""
    slots = _slots_dir(tmp_path)
    source = _payload_dir(str(tmp_path))
    with mock.patch("os.rename", side_effect=OSError(errno.EACCES, "denied")):
        result = pr.quarantine_entry(
            slots, source, slot_ref=_SLOT_REF, reason=_REASON,
            occupant=_occupant(), now=_NOW,
        )
    assert result["reason"] == pr.REASON_RENAME_FAILED
    q = pr.quarantine_dir(slots)["path"]
    sidecars = [f for f in os.listdir(q) if f.endswith(pr.SIDECAR_SUFFIX)]
    assert len(sidecars) == 1
    loaded = pr.read_sidecar(os.path.join(q, sidecars[0]))
    assert loaded["sidecar"]["move"] == pr.MOVE_PENDING
