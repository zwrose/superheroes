"""Tests for pilot provisioning journal and partial-failure reports."""
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

import pilot_journal as pj  # noqa: E402

_TS = "2026-08-02T12:00:00Z"
_TS2 = "2026-08-02T12:01:00Z"
_SLOT = "slot-a"
_SLOT_REF = "slot-a@1"
_SLOT_B = "slot-b"
_SLOT_REF_B = "slot-b@1"

_CONCURRENCY_TS = "2026-08-02T12:00:00Z"
_CONCURRENCY_BARRIER_TIMEOUT = 60.0
_CONCURRENCY_JOIN_TIMEOUT = 60.0
_CONCURRENCY_WORKERS = 8
_CONCURRENCY_RECORDS_PER_WORKER = 20
_FLOCK_SHORT_WRITE_WORKERS = 6
_FLOCK_SHORT_WRITE_RECORDS_PER_WORKER = 15
_FLOCK_SHORT_WRITE_DETAIL_BYTES = 400


def _flock_short_write_worker(journal_path, worker_id, barrier):
    import os

    import pilot_journal as pj_module

    _real_write = os.write

    def _short_write(fd, data):
        return _real_write(fd, data[:1])

    os.write = _short_write
    barrier.wait(timeout=_CONCURRENCY_BARRIER_TIMEOUT)
    for seq in range(_FLOCK_SHORT_WRITE_RECORDS_PER_WORKER):
        effect_id = "f%02d-%02d" % (worker_id, seq)
        detail = {
            "worker": worker_id,
            "seq": seq,
            "padding": "x" * _FLOCK_SHORT_WRITE_DETAIL_BYTES,
        }
        result = pj_module.begin_effect(
            journal_path,
            slot_ref="slot-a@1",
            kind=pj_module.KIND_APP_STARTED,
            at=_CONCURRENCY_TS,
            effect_id=effect_id,
            detail=detail,
        )
        if not result["ok"]:
            raise RuntimeError(result["reason"])


def _journal_append_worker(journal_path, worker_id, barrier):
    import pilot_journal as pj_module
    barrier.wait(timeout=_CONCURRENCY_BARRIER_TIMEOUT)
    for seq in range(_CONCURRENCY_RECORDS_PER_WORKER):
        effect_id = "w%02d-%02d" % (worker_id, seq)
        detail = {
            "worker": worker_id,
            "seq": seq,
            "padding": "x" * 1500,
        }
        result = pj_module.begin_effect(
            journal_path,
            slot_ref="slot-a@1",
            kind=pj_module.KIND_APP_STARTED,
            at=_CONCURRENCY_TS,
            effect_id=effect_id,
            detail=detail,
        )
        if not result["ok"]:
            raise RuntimeError(result["reason"])


def _detail_with_encoded_size(target_size):
    padding_len = target_size
    while padding_len >= 0:
        detail = {"padding": "a" * padding_len}
        encoded_size = len(
            json.dumps(detail, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        )
        if encoded_size == target_size:
            return detail
        padding_len -= 1
    raise ValueError("cannot construct detail at encoded size %d" % target_size)


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _journal(tmp_dir, name="journal.jsonl"):
    return os.path.join(tmp_dir, name)


def _write_line(path, obj):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True) + "\n")


def _begin_record(*, effect_id="eff1", kind=pj.KIND_APP_STARTED, slot_ref=_SLOT_REF,
                  at=_TS, detail=None):
    rec = {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": effect_id,
        "slotRef": slot_ref,
        "kind": kind,
        "at": at,
    }
    if detail is not None:
        rec["detail"] = detail
    return rec


def _end_record(*, effect_id="eff1", outcome=pj.OUTCOME_APPLIED, slot_ref=_SLOT_REF,
                at=_TS2, reason=None):
    rec = {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_END,
        "effectId": effect_id,
        "slotRef": slot_ref,
        "outcome": outcome,
        "at": at,
    }
    if reason is not None:
        rec["reason"] = reason
    return rec


def _slot_entry(*, slot=_SLOT, slot_ref=_SLOT_REF, outcome=pj.SLOT_OUTCOME_FAILED,
                replay=None, fencing=None, journal_path=None):
    if journal_path is None:
        journal_path = "/fake/journal.jsonl"
    if replay is None:
        replay = _ok_replay(slot_ref=slot_ref, journal_path=journal_path)
    else:
        replay = dict(replay)
        replay.setdefault("journalPath", journal_path)
        if replay.get("slotRef") is None:
            replay["slotRef"] = slot_ref
    return {
        "slot": slot,
        "slotRef": slot_ref,
        "outcome": outcome,
        "replay": replay,
        "fencing": fencing,
    }


def _ok_replay(*, slot_ref=_SLOT_REF, journal_path="/fake/journal.jsonl", **kwargs):
    base = {
        "ok": True,
        "effects": [],
        "torn": False,
        "anomalies": [],
        "journalPath": journal_path,
        "slotRef": slot_ref,
    }
    base.update(kwargs)
    return base


def _healthy_slot_entry(*, slot="slot-healthy", slot_ref="slot-healthy@1"):
    return {
        "slot": slot,
        "slotRef": slot_ref,
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(slot_ref=slot_ref),
        "fencing": None,
    }


def _begin_unpaired_shared_effect(tmp_dir, kind, *, slot_ref=_SLOT_REF, effect_id="shared-eff"):
    path = _journal(tmp_dir)
    result = pj.begin_effect(
        path, slot_ref=slot_ref, kind=kind, at=_TS, effect_id=effect_id,
    )
    assert result["ok"] is True
    return path


def _begin_end_applied_effect(tmp_dir, kind, *, slot_ref=_SLOT_REF, effect_id="applied-eff"):
    path = _journal(tmp_dir)
    result = pj.begin_effect(
        path, slot_ref=slot_ref, kind=kind, at=_TS, effect_id=effect_id,
    )
    assert result["ok"] is True
    pj.end_effect(
        path, slot_ref=slot_ref, effect_id=effect_id,
        outcome=pj.OUTCOME_APPLIED, at=_TS2,
    )
    return path


def _blocker_reasons(report):
    return [b["reason"] for b in report["blockers"]]


def test_effect_scope_covers_all_kinds():
    assert set(pj.EFFECT_SCOPE) == pj.EFFECT_KINDS


@pytest.mark.parametrize("kind", sorted(pj.EFFECT_KINDS))
def test_write_replay_round_trip_each_kind(tmp_dir, kind):
    path = _journal(tmp_dir)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=kind, at=_TS, effect_id="roundtrip1",
    )
    assert result["ok"] is True
    pj.end_effect(
        path, slot_ref=_SLOT_REF, effect_id="roundtrip1",
        outcome=pj.OUTCOME_APPLIED, at=_TS2,
    )
    replayed = pj.replay(path)
    assert replayed["ok"] is True
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["kind"] == kind
    assert replayed["effects"][0]["state"] == pj.STATE_APPLIED


def test_crash_window_begin_without_end(tmp_dir):
    path = _journal(tmp_dir)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_CREDENTIAL_MINTED,
        at=_TS, effect_id="crash1",
    )
    assert result["ok"] is True
    replayed = pj.replay(path)
    assert replayed["ok"] is True
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED
    assert replayed["effects"][0]["scope"] == pj.SCOPE_SHARED


def test_torn_trailing_line(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _begin_record(effect_id="good1", kind=pj.KIND_APP_STARTED))
    _write_line(path, _end_record(effect_id="good1"))
    with open(path, "ab") as fh:
        fh.write(b'{"partial": true')
    replayed = pj.replay(path)
    assert replayed["ok"] is True
    assert replayed["torn"] is True
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["state"] == pj.STATE_APPLIED


@pytest.mark.parametrize("invalid_line", [
    "{}",
    "[]",
])
def test_invalid_json_shapes(tmp_dir, invalid_line):
    path = _journal(tmp_dir)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(invalid_line + "\n")
    replayed = pj.replay(path)
    assert replayed["ok"] is True
    assert replayed["anomalies"]
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_invalid_unknown_phase(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, {"schemaVersion": 1, "phase": "middle", "effectId": "x",
                       "slotRef": _SLOT_REF, "at": _TS})
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_invalid_unknown_kind(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, {**_begin_record(), "kind": "bogus-kind"})
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_invalid_missing_effect_id(tmp_dir):
    path = _journal(tmp_dir)
    rec = _begin_record()
    del rec["effectId"]
    _write_line(path, rec)
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_invalid_wrong_schema_version(tmp_dir):
    path = _journal(tmp_dir)
    rec = _begin_record()
    rec["schemaVersion"] = 2
    _write_line(path, rec)
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_invalid_non_z_timestamp(tmp_dir):
    path = _journal(tmp_dir)
    rec = _begin_record()
    rec["at"] = "2026-08-02T12:00:00+00:00"
    _write_line(path, rec)
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_orphan_end(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _end_record(effect_id="orphan1"))
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_duplicate_begin(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _begin_record(effect_id="dup1"))
    _write_line(path, _begin_record(effect_id="dup1"))
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert all(e["state"] == pj.STATE_POSSIBLY_APPLIED for e in replayed["effects"])
    assert len(replayed["effects"]) == 2


def test_duplicate_end(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _begin_record(effect_id="dupend1"))
    _write_line(path, _end_record(effect_id="dupend1"))
    _write_line(path, _end_record(effect_id="dupend1"))
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert all(e["state"] == pj.STATE_POSSIBLY_APPLIED for e in replayed["effects"])


def test_end_before_begin(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _end_record(effect_id="order1"))
    _write_line(path, _begin_record(effect_id="order1"))
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert all(e["state"] == pj.STATE_POSSIBLY_APPLIED for e in replayed["effects"])


def test_slot_ref_disagreement(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _begin_record(effect_id="mismatch1", slot_ref=_SLOT_REF))
    _write_line(path, _end_record(effect_id="mismatch1", slot_ref="slot-a@2"))
    replayed = pj.replay(path)
    assert replayed["anomalies"]
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_effect_clean_exit_applied(tmp_dir):
    path = _journal(tmp_dir)
    with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
                   effect_id="ctx1"):
        pass
    replayed = pj.replay(path)
    assert replayed["effects"][0]["state"] == pj.STATE_APPLIED


def test_effect_raises_indeterminate_and_reraises(tmp_dir):
    path = _journal(tmp_dir)
    with pytest.raises(ValueError, match="boom"):
        with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
                       effect_id="ctx2"):
            raise ValueError("boom")
    replayed = pj.replay(path)
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED
    assert replayed["effects"][0]["outcome"] == pj.OUTCOME_INDETERMINATE


def test_effect_keyboard_interrupt_indeterminate(tmp_dir):
    path = _journal(tmp_dir)
    with pytest.raises(KeyboardInterrupt):
        with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_CREDENTIAL_MINTED, at=_TS,
                       effect_id="ctx-kb"):
            raise KeyboardInterrupt
    with open(path, encoding="utf-8") as fh:
        lines = [json.loads(ln) for ln in fh if ln.strip()]
    end_record = next(r for r in lines if r["phase"] == pj.PHASE_END)
    assert end_record["outcome"] == pj.OUTCOME_INDETERMINATE
    replayed = pj.replay(path)
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_effect_system_exit_indeterminate(tmp_dir):
    path = _journal(tmp_dir)
    with pytest.raises(SystemExit):
        with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_CREDENTIAL_MINTED, at=_TS,
                       effect_id="ctx-se"):
            raise SystemExit(1)
    with open(path, encoding="utf-8") as fh:
        lines = [json.loads(ln) for ln in fh if ln.strip()]
    end_record = next(r for r in lines if r["phase"] == pj.PHASE_END)
    assert end_record["outcome"] == pj.OUTCOME_INDETERMINATE
    replayed = pj.replay(path)
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_effect_mark_not_applied(tmp_dir):
    path = _journal(tmp_dir)
    with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
                   effect_id="ctx3") as handle:
        handle.mark_not_applied(at=_TS2, reason="cancelled")
    replayed = pj.replay(path)
    assert replayed["effects"][0]["state"] == pj.STATE_NOT_APPLIED


def test_effect_writes_exactly_one_end(tmp_dir):
    path = _journal(tmp_dir)
    with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
                   effect_id="ctx4"):
        pass
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh if ln.strip()]
    assert len(lines) == 2
    end_lines = [json.loads(ln) for ln in lines if json.loads(ln)["phase"] == pj.PHASE_END]
    assert len(end_lines) == 1


def test_begin_write_failure_prevents_body(tmp_dir):
    bad_parent = os.path.join(tmp_dir, "not-a-dir")
    with open(bad_parent, "w", encoding="utf-8") as fh:
        fh.write("blocker")
    journal_path = os.path.join(bad_parent, "subdir", "journal.jsonl")
    with pytest.raises(pj.PilotJournalError) as exc_info:
        with pj.effect(journal_path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS):
            raise AssertionError("body must not run")
    assert exc_info.value.reason == pj.REASON_JOURNAL_WRITE_FAILED


def test_replay_missing_journal(tmp_dir):
    path = _journal(tmp_dir, "missing.jsonl")
    result = pj.replay(path)
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_UNREADABLE


# --- partial_failure_report blocker tests ---

def test_report_block_slots_invalid_none():
    report = pj.partial_failure_report(None)
    assert report["recommendLaunch"] is False
    assert report["blockers"] == [{"reason": pj.BLOCK_SLOTS_INVALID, "slot": None, "slotRef": None, "detail": None}]
    assert report["warnings"] == []
    assert report["failedSlots"] == []
    assert report["healthySlots"] == []


def test_report_block_slots_invalid_dict():
    report = pj.partial_failure_report({})
    assert report["recommendLaunch"] is False
    assert report["blockers"] == [{"reason": pj.BLOCK_SLOTS_INVALID, "slot": None, "slotRef": None, "detail": None}]
    assert report["warnings"] == []
    assert report["failedSlots"] == []
    assert report["healthySlots"] == []


def test_report_block_slots_invalid_string():
    report = pj.partial_failure_report("abc")
    assert report["recommendLaunch"] is False
    assert report["blockers"] == [{"reason": pj.BLOCK_SLOTS_INVALID, "slot": None, "slotRef": None, "detail": None}]
    assert report["warnings"] == []
    assert report["failedSlots"] == []
    assert report["healthySlots"] == []


def test_report_block_slots_invalid_int():
    report = pj.partial_failure_report(7)
    assert report["recommendLaunch"] is False
    assert report["blockers"] == [{"reason": pj.BLOCK_SLOTS_INVALID, "slot": None, "slotRef": None, "detail": None}]
    assert report["warnings"] == []
    assert report["failedSlots"] == []
    assert report["healthySlots"] == []


def test_report_block_slot_entry_invalid():
    report = pj.partial_failure_report([_healthy_slot_entry(), "not-a-dict"])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SLOT_ENTRY_INVALID in _blocker_reasons(report)


def test_report_block_slot_outcome_invalid():
    entry = _slot_entry(outcome="unknown-outcome",
                        fencing={"slotRef": _SLOT_REF, "fenced": True})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SLOT_OUTCOME_INVALID in _blocker_reasons(report)


def test_report_block_fence_missing():
    entry = _slot_entry(fencing=None)
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_FENCE_MISSING in _blocker_reasons(report)


def test_report_block_fence_invalid_string():
    entry = _slot_entry(fencing={"slotRef": _SLOT_REF, "fenced": "true"})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_FENCE_INVALID in _blocker_reasons(report)


def test_report_block_fence_invalid_int():
    entry = _slot_entry(fencing={"slotRef": _SLOT_REF, "fenced": 1})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_FENCE_INVALID in _blocker_reasons(report)


def test_report_block_fence_invalid_none():
    entry = _slot_entry(fencing={"slotRef": _SLOT_REF, "fenced": None})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_FENCE_INVALID in _blocker_reasons(report)


def test_report_block_not_fenced():
    entry = _slot_entry(fencing={"slotRef": _SLOT_REF, "fenced": False})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_NOT_FENCED in _blocker_reasons(report)


def test_report_block_fence_ref_mismatch():
    entry = _slot_entry(fencing={"slotRef": "slot-a@2", "fenced": True})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_FENCE_REF_MISMATCH in _blocker_reasons(report)


def test_report_block_journal_unreadable():
    entry = _slot_entry(replay={"ok": False, "reason": pj.REASON_JOURNAL_UNREADABLE},
                        fencing={"slotRef": _SLOT_REF, "fenced": True})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_JOURNAL_UNREADABLE in _blocker_reasons(report)


def test_report_block_journal_torn():
    entry = _slot_entry(replay=_ok_replay(torn=True),
                        fencing={"slotRef": _SLOT_REF, "fenced": True})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_JOURNAL_TORN in _blocker_reasons(report)


def test_report_block_journal_anomaly():
    entry = _slot_entry(replay=_ok_replay(anomalies=[{"line": 1}]),
                        fencing={"slotRef": _SLOT_REF, "fenced": True})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_JOURNAL_ANOMALY in _blocker_reasons(report)


def test_report_block_shared_possibly_applied(tmp_dir):
    path = _begin_unpaired_shared_effect(tmp_dir, pj.KIND_CREDENTIAL_MINTED)
    replay_result = pj.replay(path, slot_ref=_SLOT_REF)
    entry = _slot_entry(
        replay=replay_result,
        fencing={"slotRef": _SLOT_REF, "fenced": True},
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SHARED_POSSIBLY_APPLIED in _blocker_reasons(report)


def test_report_block_no_healthy_slots():
    failed = _slot_entry(fencing={"slotRef": _SLOT_REF, "fenced": True})
    report = pj.partial_failure_report([failed])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_NO_HEALTHY_SLOTS in _blocker_reasons(report)


def test_report_happy_path(tmp_dir):
    healthy_path = _begin_end_applied_effect(
        tmp_dir, pj.KIND_APP_STARTED, slot_ref="slot1@1", effect_id="slot1-eff",
    )
    healthy1 = {
        "slot": "slot1", "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": pj.replay(healthy_path, slot_ref="slot1@1"),
        "fencing": None,
    }
    healthy2 = {
        "slot": "slot2", "slotRef": "slot2@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(slot_ref="slot2@1"),
        "fencing": None,
    }
    failed_path = _begin_unpaired_shared_effect(
        tmp_dir, pj.KIND_APP_STARTED, slot_ref=_SLOT_REF, effect_id="failed-slot-eff",
    )
    failed = {
        "slot": _SLOT, "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": pj.replay(failed_path, slot_ref=_SLOT_REF),
        "fencing": {"slotRef": _SLOT_REF, "fenced": True},
    }
    report = pj.partial_failure_report([healthy1, healthy2, failed])
    assert report["recommendLaunch"] is True
    assert not report["blockers"]
    assert len(report["warnings"]) == 1
    assert report["warnings"][0]["effect"]["effectId"] == "failed-slot-eff"


@pytest.mark.parametrize("kind", [
    pj.KIND_CREDENTIAL_MINTED,
    pj.KIND_CREDENTIAL_SEEDED,
    pj.KIND_NAMESPACE_TOUCHED,
    pj.KIND_PROJECT_DECLARED,
])
def test_report_failed_shared_possibly_applied_blocks_launch(tmp_dir, kind):
    path = _begin_unpaired_shared_effect(tmp_dir, kind, effect_id=f"shared-{kind}")
    healthy = {
        "slot": "slot1", "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(slot_ref="slot1@1"),
        "fencing": None,
    }
    failed = {
        "slot": _SLOT, "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": pj.replay(path, slot_ref=_SLOT_REF),
        "fencing": {"slotRef": _SLOT_REF, "fenced": True},
    }
    report = pj.partial_failure_report([healthy, failed])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SHARED_POSSIBLY_APPLIED in _blocker_reasons(report)


def test_report_enumerates_multiple_blockers():
    entry = _slot_entry(
        outcome="bogus",
        replay={"ok": False, "reason": pj.REASON_JOURNAL_UNREADABLE},
        fencing=None,
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    reasons = _blocker_reasons(report)
    assert pj.BLOCK_SLOT_OUTCOME_INVALID in reasons
    assert pj.BLOCK_FENCE_MISSING in reasons
    assert pj.BLOCK_JOURNAL_UNREADABLE in reasons
    assert report["recommendLaunch"] is False


# --- WO-6 review fixes ---

_SLOT1 = "slot1"
_SLOT_REF1 = "slot1@1"


def _filtered_replay_effect(path, slot_ref=_SLOT_REF1):
    return pj.replay(path, slot_ref=slot_ref)


def test_replay_filtered_retains_invalid_no_slot_ref(tmp_dir):
    path = _journal(tmp_dir)
    rec = _begin_record(effect_id="bad1")
    del rec["slotRef"]
    _write_line(path, rec)
    replayed = _filtered_replay_effect(path)
    assert replayed["anomalies"]
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_replay_filtered_retains_unparseable_slot_ref(tmp_dir):
    path = _journal(tmp_dir)
    rec = _begin_record(effect_id="bad2")
    rec["slotRef"] = "not-a-valid-ref"
    _write_line(path, rec)
    replayed = _filtered_replay_effect(path)
    assert replayed["anomalies"]
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_replay_filtered_retains_json_array_line(tmp_dir):
    path = _journal(tmp_dir)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("[]\n")
    replayed = _filtered_replay_effect(path)
    assert replayed["anomalies"]
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_replay_filtered_retains_empty_object(tmp_dir):
    path = _journal(tmp_dir)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    replayed = _filtered_replay_effect(path)
    assert replayed["anomalies"]
    assert len(replayed["effects"]) == 1
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_replay_filtered_slot_ref_mismatch_anomaly(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _begin_record(effect_id="mismatch-f", slot_ref=_SLOT_REF1))
    _write_line(path, _end_record(effect_id="mismatch-f", slot_ref="slot1@2"))
    replayed = _filtered_replay_effect(path)
    assert any(a.get("reason") == "slot-ref-mismatch" for a in replayed["anomalies"])
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_replay_filtered_duplicate_effect_across_slots(tmp_dir):
    path = _journal(tmp_dir)
    _write_line(path, _begin_record(effect_id="dup-cross", slot_ref=_SLOT_REF1))
    _write_line(path, _begin_record(effect_id="dup-cross", slot_ref="slot2@1"))
    replayed = _filtered_replay_effect(path)
    assert replayed["anomalies"]


@pytest.mark.parametrize("bad_replay", [
    {"ok": True},
    {"ok": True, "torn": False},
    {"ok": True, "torn": False, "anomalies": []},
    {"ok": True, "torn": False, "anomalies": [], "effects": "bad"},
    {"ok": True, "torn": False, "anomalies": [], "effects": [42]},
    {"ok": True, "torn": False, "anomalies": [], "effects": [{"state": "weird", "scope": pj.SCOPE_SLOT}]},
    {"ok": True, "torn": False, "anomalies": [], "effects": [{"state": pj.STATE_APPLIED, "scope": "weird"}]},
])
def test_report_block_replay_shape_invalid(bad_replay):
    entry = _slot_entry(replay=bad_replay, fencing={"slotRef": _SLOT_REF, "fenced": True})
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SHAPE_INVALID in _blocker_reasons(report)


def test_report_block_slot_ref_mismatch_with_slot():
    entry = {
        "slot": "slot2",
        "slotRef": _SLOT_REF1,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": _ok_replay(slot_ref=_SLOT_REF1),
        "fencing": {"slotRef": _SLOT_REF1, "fenced": True},
    }
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SLOT_ENTRY_INVALID in _blocker_reasons(report)


def test_report_block_slot_duplicate():
    dup1 = {
        "slot": "slot-dup",
        "slotRef": "slot-dup@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(slot_ref="slot-dup@1"),
        "fencing": None,
    }
    dup2 = {
        "slot": "slot-dup",
        "slotRef": "slot-dup@2",
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": _ok_replay(slot_ref="slot-dup@2"),
        "fencing": {"slotRef": "slot-dup@2", "fenced": True},
    }
    report = pj.partial_failure_report([_healthy_slot_entry(), dup1, dup2])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SLOT_DUPLICATE in _blocker_reasons(report)


def test_report_provisioned_no_replay_healthy(tmp_dir):
    healthy = {
        "slot": "slot1",
        "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "fencing": None,
    }
    report = pj.partial_failure_report([healthy])
    assert report["recommendLaunch"] is True
    assert not report["blockers"]


@pytest.mark.parametrize("kind", [
    pj.KIND_CREDENTIAL_MINTED,
    pj.KIND_CREDENTIAL_SEEDED,
    pj.KIND_NAMESPACE_TOUCHED,
    pj.KIND_PROJECT_DECLARED,
])
def test_report_provisioned_shared_possibly_applied_blocks(tmp_dir, kind):
    path = _begin_unpaired_shared_effect(
        tmp_dir, kind, slot_ref="slot1@1", effect_id=f"prov-{kind}",
    )
    healthy = {
        "slot": "slot1",
        "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": pj.replay(path, slot_ref="slot1@1"),
        "fencing": None,
    }
    report = pj.partial_failure_report([healthy])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SHARED_POSSIBLY_APPLIED in _blocker_reasons(report)
    assert len(report["warnings"]) == 1
    assert report["warnings"][0]["effect"]["kind"] == kind


def test_report_provisioned_slot_possibly_applied_warning_only():
    slot_effect = {
        "effectId": "slot-warn", "kind": pj.KIND_APP_STARTED,
        "scope": pj.SCOPE_SLOT, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    healthy = {
        "slot": "slot1",
        "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(slot_ref="slot1@1", effects=[slot_effect]),
        "fencing": None,
    }
    report = pj.partial_failure_report([healthy])
    assert report["recommendLaunch"] is True
    assert not report["blockers"]
    assert len(report["warnings"]) == 1


def test_effect_end_write_failure_raises(tmp_dir, monkeypatch):
    path = _journal(tmp_dir)
    call_count = 0
    real_write = pj._write_record

    def failing_write(journal_path, record):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return real_write(journal_path, record)
        return {"ok": False, "reason": pj.REASON_JOURNAL_WRITE_FAILED}

    monkeypatch.setattr(pj, "_write_record", failing_write)
    with pytest.raises(pj.PilotJournalError) as exc_info:
        with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
                       effect_id="end-fail"):
            pass
    assert exc_info.value.reason == pj.REASON_JOURNAL_WRITE_FAILED


def test_effect_body_raises_end_write_failure_propagates_body(tmp_dir, monkeypatch):
    path = _journal(tmp_dir)
    call_count = 0
    real_write = pj._write_record

    def failing_write(journal_path, record):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return real_write(journal_path, record)
        return {"ok": False, "reason": pj.REASON_JOURNAL_WRITE_FAILED}

    monkeypatch.setattr(pj, "_write_record", failing_write)
    with pytest.raises(ValueError, match="body-boom"):
        with pj.effect(path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
                       effect_id="body-end-fail"):
            raise ValueError("body-boom")


def test_replay_invalid_utf8(tmp_dir):
    path = _journal(tmp_dir)
    with open(path, "wb") as fh:
        fh.write(b"\xff\n")
    result = pj.replay(path)
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_UNREADABLE


def test_write_record_refuses_symlink(tmp_dir):
    target = os.path.join(tmp_dir, "real.jsonl")
    journal = os.path.join(tmp_dir, "journal.jsonl")
    os.symlink(target, journal)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("seed\n")
    result = pj.begin_effect(
        journal, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="sym1",
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED
    with open(target, encoding="utf-8") as fh:
        assert fh.read() == "seed\n"


def test_write_record_refuses_directory(tmp_dir):
    journal = os.path.join(tmp_dir, "journal.jsonl")
    os.mkdir(journal)
    result = pj.begin_effect(
        journal, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="dir1",
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED


# --- WO-9 round-2 review fixes ---


def test_replay_stamps_journal_path_and_slot_ref(tmp_dir):
    path = _journal(tmp_dir)
    result = pj.replay(path, slot_ref=_SLOT_REF)
    assert result["journalPath"] == path
    assert result["slotRef"] == _SLOT_REF


def test_replay_stamps_failure_returns(tmp_dir):
    result = pj.replay(os.path.join(tmp_dir, "missing.jsonl"))
    assert result["journalPath"] == os.path.join(tmp_dir, "missing.jsonl")
    assert result["slotRef"] is None
    assert result["ok"] is False


def test_report_block_replay_slot_mismatch(tmp_dir):
    path = _begin_unpaired_shared_effect(tmp_dir, pj.KIND_CREDENTIAL_MINTED, slot_ref=_SLOT_REF1)
    replay_for_slot1 = pj.replay(path, slot_ref=_SLOT_REF1)
    entry = _slot_entry(
        slot=_SLOT_B,
        slot_ref=_SLOT_REF_B,
        replay=replay_for_slot1,
        fencing={"slotRef": _SLOT_REF_B, "fenced": True},
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SLOT_MISMATCH in _blocker_reasons(report)


def test_report_block_replay_missing_slot_ref_stamp():
    entry = {
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": {"ok": True, "effects": [], "torn": False, "anomalies": [],
                   "journalPath": "/fake/journal.jsonl"},
        "fencing": {"slotRef": _SLOT_REF, "fenced": True},
    }
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SLOT_MISMATCH in _blocker_reasons(report)


def test_report_block_replay_scope_mismatch_credential_minted():
    effect = {
        "effectId": "cm1", "kind": pj.KIND_CREDENTIAL_MINTED,
        "scope": pj.SCOPE_SLOT, "state": pj.STATE_APPLIED,
    }
    entry = _slot_entry(
        replay=_ok_replay(slot_ref=_SLOT_REF, effects=[effect]),
        fencing={"slotRef": _SLOT_REF, "fenced": True},
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SHAPE_INVALID in _blocker_reasons(report)


def test_report_block_replay_scope_mismatch_unknown_kind():
    effect = {
        "effectId": "unk1", "kind": pj.KIND_UNKNOWN,
        "scope": pj.SCOPE_SLOT, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    entry = _slot_entry(
        replay=_ok_replay(slot_ref=_SLOT_REF, effects=[effect]),
        fencing={"slotRef": _SLOT_REF, "fenced": True},
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SHAPE_INVALID in _blocker_reasons(report)


@pytest.mark.parametrize("bad_kind", [[], {}])
def test_replay_begin_non_string_kind(tmp_dir, bad_kind):
    path = _journal(tmp_dir)
    rec = _begin_record()
    rec["kind"] = bad_kind
    _write_line(path, rec)
    replayed = pj.replay(path)
    assert replayed["ok"] is True
    assert replayed["anomalies"]
    assert replayed["effects"][0]["kind"] == pj.KIND_UNKNOWN


def test_replay_end_non_string_outcome(tmp_dir):
    path = _journal(tmp_dir)
    rec = _end_record()
    rec["outcome"] = []
    _write_line(path, rec)
    replayed = pj.replay(path)
    assert replayed["ok"] is True
    assert replayed["anomalies"]
    assert replayed["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_report_block_non_string_outcome():
    entry = {
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "outcome": [],
        "replay": _ok_replay(slot_ref=_SLOT_REF),
        "fencing": {"slotRef": _SLOT_REF, "fenced": True},
    }
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SLOT_OUTCOME_INVALID in _blocker_reasons(report)


def test_report_block_replay_non_string_state():
    effect = {
        "effectId": "st1", "kind": pj.KIND_APP_STARTED,
        "scope": pj.SCOPE_SLOT, "state": [],
    }
    entry = _slot_entry(
        replay=_ok_replay(slot_ref=_SLOT_REF, effects=[effect]),
        fencing={"slotRef": _SLOT_REF, "fenced": True},
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SHAPE_INVALID in _blocker_reasons(report)


def test_report_block_replay_non_string_scope():
    effect = {
        "effectId": "sc1", "kind": pj.KIND_APP_STARTED,
        "scope": {}, "state": pj.STATE_APPLIED,
    }
    entry = _slot_entry(
        replay=_ok_replay(slot_ref=_SLOT_REF, effects=[effect]),
        fencing={"slotRef": _SLOT_REF, "fenced": True},
    )
    report = pj.partial_failure_report([_healthy_slot_entry(), entry])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_REPLAY_SHAPE_INVALID in _blocker_reasons(report)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="os.mkfifo not available on this platform")
def test_write_record_refuses_fifo(tmp_dir):
    journal = _journal(tmp_dir)
    os.mkfifo(journal)
    result = pj.begin_effect(
        journal, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="fifo1",
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="os.mkfifo not available on this platform")
def test_replay_refuses_fifo(tmp_dir):
    journal = _journal(tmp_dir)
    os.mkfifo(journal)
    result = pj.replay(journal)
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_UNREADABLE


def test_replay_refuses_symlink(tmp_dir):
    target = os.path.join(tmp_dir, "real.jsonl")
    journal = os.path.join(tmp_dir, "journal.jsonl")
    os.symlink(target, journal)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    result = pj.replay(journal)
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_UNREADABLE


def test_write_record_partial_write_still_completes(tmp_dir, monkeypatch):
    path = _journal(tmp_dir)
    real_write = os.write
    calls = {"count": 0}

    def partial_write(fd, data):
        calls["count"] += 1
        if calls["count"] == 1 and len(data) > 1:
            return real_write(fd, data[: len(data) // 2])
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", partial_write)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="partial1",
    )
    assert result["ok"] is True
    with open(path, encoding="utf-8") as fh:
        line = fh.readline()
    record = json.loads(line)
    assert record["effectId"] == "partial1"
    assert record["phase"] == pj.PHASE_BEGIN


def test_write_record_directory_fsync_failure(tmp_dir, monkeypatch):
    path = _journal(tmp_dir)
    real_fsync = os.fsync

    def failing_fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("simulated directory fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", failing_fsync)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="dirfsync1",
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED


def test_concurrent_append_all_lines_parse(tmp_dir):
    multiprocessing.set_start_method("spawn", force=True)
    path = _journal(tmp_dir)
    n = _CONCURRENCY_WORKERS
    barrier = multiprocessing.Barrier(n)
    processes = []
    for worker_id in range(n):
        proc = multiprocessing.Process(
            target=_journal_append_worker,
            args=(path, worker_id, barrier),
        )
        processes.append(proc)
        proc.start()
    for proc in processes:
        proc.join(timeout=_CONCURRENCY_JOIN_TIMEOUT)
    for proc in processes:
        assert proc.exitcode == 0, "worker exited with %s" % proc.exitcode
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh if ln.strip()]
    assert len(lines) == n * _CONCURRENCY_RECORDS_PER_WORKER
    for line in lines:
        json.loads(line)


def test_journal_lock_symlink_refuses_write(tmp_dir):
    path = _journal(tmp_dir)
    lock_target = os.path.join(tmp_dir, "real.lock")
    lock_path = path + ".lock"
    os.symlink(lock_target, lock_path)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="locksym1",
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED


def test_journal_lock_directory_refuses_write(tmp_dir):
    path = _journal(tmp_dir)
    os.mkdir(path + ".lock")
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS, effect_id="lockdir1",
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED


def test_detail_at_max_bytes_passes(tmp_dir):
    detail = _detail_with_encoded_size(pj.DETAIL_MAX_BYTES)
    path = _journal(tmp_dir)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
        effect_id="maxdetail1", detail=detail,
    )
    assert result["ok"] is True


def test_detail_one_byte_over_max_refuses(tmp_dir):
    at_limit = _detail_with_encoded_size(pj.DETAIL_MAX_BYTES)
    over_detail = {"padding": at_limit["padding"] + "x"}
    encoded_size = len(
        json.dumps(over_detail, sort_keys=True, ensure_ascii=False).encode("utf-8"),
    )
    assert encoded_size == pj.DETAIL_MAX_BYTES + 1
    path = _journal(tmp_dir)
    result = pj.begin_effect(
        path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
        effect_id="overdetail1", detail=over_detail,
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_RECORD_INVALID


def test_refused_write_empty_path_leaves_no_lock():
    result = pj.begin_effect(
        "", slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
    )
    assert result == {"ok": False, "reason": pj.REASON_JOURNAL_WRITE_FAILED}
    assert not os.path.exists(".lock")


def test_refused_write_bad_parent_leaves_no_lock(tmp_dir):
    bad_parent = os.path.join(tmp_dir, "not-a-dir")
    with open(bad_parent, "w", encoding="utf-8") as fh:
        fh.write("blocker")
    journal_path = os.path.join(bad_parent, "subdir", "journal.jsonl")
    lock_path = journal_path + ".lock"
    result = pj.begin_effect(
        journal_path, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED, at=_TS,
    )
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_WRITE_FAILED
    assert not os.path.exists(lock_path)


def test_bare_filename_writes_lock_beside_journal(tmp_dir):
    cwd = os.getcwd()
    os.chdir(tmp_dir)
    try:
        journal_name = "journal.jsonl"
        result = pj.begin_effect(
            journal_name, slot_ref=_SLOT_REF, kind=pj.KIND_APP_STARTED,
            at=_TS, effect_id="bare1",
        )
        assert result["ok"] is True
        assert os.path.isfile(journal_name)
        assert os.path.isfile(journal_name + ".lock")
    finally:
        os.chdir(cwd)


def test_concurrent_append_flock_short_write_all_lines_parse(tmp_dir):
    multiprocessing.set_start_method("spawn", force=True)
    path = _journal(tmp_dir)
    n = _FLOCK_SHORT_WRITE_WORKERS
    expected = n * _FLOCK_SHORT_WRITE_RECORDS_PER_WORKER
    barrier = multiprocessing.Barrier(n)
    processes = []
    for worker_id in range(n):
        proc = multiprocessing.Process(
            target=_flock_short_write_worker,
            args=(path, worker_id, barrier),
        )
        processes.append(proc)
        proc.start()
    for proc in processes:
        proc.join(timeout=_CONCURRENCY_JOIN_TIMEOUT)
    for proc in processes:
        assert proc.exitcode == 0, "worker exited with %s" % proc.exitcode
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh if ln.strip()]
    assert len(lines) == expected
    for line in lines:
        json.loads(line)
