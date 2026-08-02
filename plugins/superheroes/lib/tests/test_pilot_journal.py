"""Tests for pilot provisioning journal and partial-failure reports."""
import json
import os
import shutil
import sys
import tempfile

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


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp(dir="/private/tmp")
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
                replay=None, fencing=None):
    return {
        "slot": slot,
        "slotRef": slot_ref,
        "outcome": outcome,
        "replay": replay if replay is not None else {"ok": True, "effects": [], "torn": False, "anomalies": []},
        "fencing": fencing,
    }


def _ok_replay(**kwargs):
    base = {"ok": True, "effects": [], "torn": False, "anomalies": []}
    base.update(kwargs)
    return base


def _healthy_slot_entry(*, slot="slot-healthy", slot_ref="slot-healthy@1"):
    return {
        "slot": slot,
        "slotRef": slot_ref,
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(),
        "fencing": None,
    }


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


def test_report_block_shared_possibly_applied():
    effect = {
        "effectId": "sh1", "kind": pj.KIND_CREDENTIAL_MINTED,
        "scope": pj.SCOPE_SHARED, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    entry = _slot_entry(
        replay=_ok_replay(effects=[effect]),
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
    slot_scoped_effect = {
        "effectId": "slot1", "kind": pj.KIND_APP_STARTED,
        "scope": pj.SCOPE_SLOT, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    healthy1 = {
        "slot": "slot1", "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(),
        "fencing": None,
    }
    healthy2 = {
        "slot": "slot2", "slotRef": "slot2@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(),
        "fencing": None,
    }
    failed = {
        "slot": _SLOT, "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": _ok_replay(effects=[slot_scoped_effect]),
        "fencing": {"slotRef": _SLOT_REF, "fenced": True},
    }
    report = pj.partial_failure_report([healthy1, healthy2, failed])
    assert report["recommendLaunch"] is True
    assert not report["blockers"]
    assert len(report["warnings"]) == 1
    assert report["warnings"][0]["effect"] == slot_scoped_effect


def test_report_failed_shared_possibly_applied_blocks_launch():
    shared_effect = {
        "effectId": "sh2", "kind": pj.KIND_NAMESPACE_TOUCHED,
        "scope": pj.SCOPE_SHARED, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    healthy = {
        "slot": "slot1", "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(),
        "fencing": None,
    }
    failed = {
        "slot": _SLOT, "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": _ok_replay(effects=[shared_effect]),
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
        "replay": _ok_replay(),
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
        "replay": _ok_replay(),
        "fencing": None,
    }
    dup2 = {
        "slot": "slot-dup",
        "slotRef": "slot-dup@2",
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": _ok_replay(),
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


def test_report_provisioned_shared_possibly_applied_blocks():
    shared_effect = {
        "effectId": "sh-prov", "kind": pj.KIND_CREDENTIAL_MINTED,
        "scope": pj.SCOPE_SHARED, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    healthy = {
        "slot": "slot1",
        "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(effects=[shared_effect]),
        "fencing": None,
    }
    report = pj.partial_failure_report([healthy])
    assert report["recommendLaunch"] is False
    assert pj.BLOCK_SHARED_POSSIBLY_APPLIED in _blocker_reasons(report)
    assert len(report["warnings"]) == 1
    assert report["warnings"][0]["effect"] == shared_effect


def test_report_provisioned_slot_possibly_applied_warning_only():
    slot_effect = {
        "effectId": "slot-warn", "kind": pj.KIND_APP_STARTED,
        "scope": pj.SCOPE_SLOT, "state": pj.STATE_POSSIBLY_APPLIED,
    }
    healthy = {
        "slot": "slot1",
        "slotRef": "slot1@1",
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": _ok_replay(effects=[slot_effect]),
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
