"""Tests for pilot wave deadline runtime and wave-end teardown."""
import json
import math
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
import pilot_wave as pw  # noqa: E402

_TS = "2026-08-02T12:00:00Z"
_TS2 = "2026-08-02T12:01:00Z"
_SLOT = "slot-a"
_SLOT_REF = "slot-a@1"


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _slots_dir(tmp_dir):
    path = os.path.join(tmp_dir, "slots")
    os.makedirs(path, exist_ok=True)
    return path


def _journal(tmp_dir):
    path = os.path.join(tmp_dir, "journal.jsonl")
    open(path, "a", encoding="utf-8").close()
    return path


def _receipt(*, step, slot_ref=_SLOT_REF, observed_at=_TS2, evidence="stopped"):
    return {
        "step": step,
        "slotRef": slot_ref,
        "observedAt": observed_at,
        "evidence": evidence,
    }


def _applied(step, **kwargs):
    return {
        "outcome": pj.OUTCOME_APPLIED,
        "receipt": _receipt(step=step, **kwargs),
        "reason": None,
    }


def _all_handlers():
    return {
        pw.STEP_APP: lambda ctx: _applied(pw.STEP_APP),
        pw.STEP_AUTOMATION: lambda ctx: _applied(pw.STEP_AUTOMATION),
        pw.STEP_CLEANUP: lambda ctx: _applied(pw.STEP_CLEANUP),
        pw.STEP_RECLAIM: lambda ctx: _applied(pw.STEP_RECLAIM),
    }


def _entry(**kwargs):
    base = {
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "intent": pw.INTENT_COMPLETE,
        "instance": None,
        "allocation": None,
        "stepTimeoutSeconds": None,
    }
    base.update(kwargs)
    return base


def _mono_sequence(values):
    seq = iter(values)

    def _fn():
        try:
            return next(seq)
        except StopIteration:
            return values[-1]

    return _fn


def _now_fn():
    return _TS2


# --- wave_anchor fail-closed edges ---


@pytest.mark.parametrize("launched_at", [None, "", "not-a-date", "2026-01-01T00:00:00"])
def test_wave_anchor_rejects_invalid_launched_at(launched_at):
    result = pw.wave_anchor(
        launched_at=launched_at,
        deadline_seconds=10,
        margin_seconds=5,
        monotonic=lambda: 0.0,
    )
    assert result == {"ok": False, "reason": pw.REASON_ANCHOR_INVALID, "anchor": None}


@pytest.mark.parametrize("deadline", [-1, "x", float("nan"), float("inf"), True])
def test_wave_anchor_rejects_invalid_deadline(deadline):
    result = pw.wave_anchor(
        launched_at=_TS,
        deadline_seconds=deadline,
        margin_seconds=5,
        monotonic=lambda: 0.0,
    )
    assert result == {"ok": False, "reason": pw.REASON_DEADLINE_INVALID, "anchor": None}


@pytest.mark.parametrize("margin", [-1, "x", float("nan"), float("inf"), True])
def test_wave_anchor_rejects_invalid_margin(margin):
    result = pw.wave_anchor(
        launched_at=_TS,
        deadline_seconds=10,
        margin_seconds=margin,
        monotonic=lambda: 0.0,
    )
    assert result == {"ok": False, "reason": pw.REASON_MARGIN_INVALID, "anchor": None}


def test_wave_anchor_accepts_zero_margin():
    result = pw.wave_anchor(
        launched_at=_TS,
        deadline_seconds=10,
        margin_seconds=0,
        monotonic=lambda: 100.0,
    )
    assert result["ok"] is True
    assert result["anchor"]["marginSeconds"] == 0


def test_wave_anchor_success():
    result = pw.wave_anchor(
        launched_at=_TS,
        deadline_seconds=60,
        margin_seconds=10,
        monotonic=lambda: 42.0,
    )
    assert result["ok"] is True
    assert result["anchor"] == {
        "schemaVersion": pw.SCHEMA,
        "launchedAt": _TS,
        "launchedAtMono": 42.0,
        "deadlineSeconds": 60,
        "marginSeconds": 10,
    }


# --- wave_phase fail-closed edges ---


@pytest.mark.parametrize("anchor", [None, {}, {"schemaVersion": 2}, {"schemaVersion": 1}])
def test_wave_phase_rejects_invalid_anchor(anchor):
    result = pw.wave_phase(anchor, monotonic=lambda: 0.0)
    assert result["ok"] is False
    assert result["reason"] == pw.REASON_CLOCK_INVALID


def test_wave_phase_rejects_bool_launched_at_mono():
    anchor = {
        "schemaVersion": 1,
        "launchedAt": _TS,
        "launchedAtMono": True,
        "deadlineSeconds": 10,
        "marginSeconds": 5,
    }
    result = pw.wave_phase(anchor, monotonic=lambda: 2.0)
    assert result["ok"] is False
    assert result["reason"] == pw.REASON_CLOCK_INVALID


def test_wave_phase_rejects_backwards_monotonic():
    anchor = {
        "schemaVersion": 1,
        "launchedAt": _TS,
        "launchedAtMono": 100.0,
        "deadlineSeconds": 10,
        "marginSeconds": 5,
    }
    result = pw.wave_phase(anchor, monotonic=lambda: 50.0)
    assert result["ok"] is False
    assert result["reason"] == pw.REASON_CLOCK_INVALID


# --- phase boundaries ---


def test_wave_phase_running():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=5, monotonic=lambda: 0.0
    )["anchor"]
    result = pw.wave_phase(anchor, monotonic=lambda: 9.999)
    assert result["phase"] == pw.PHASE_RUNNING


def test_wave_phase_winding_down_at_deadline_boundary():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=5, monotonic=lambda: 0.0
    )["anchor"]
    result = pw.wave_phase(anchor, monotonic=lambda: 10.0)
    assert result["phase"] == pw.PHASE_WINDING_DOWN


def test_wave_phase_expired_at_terminus_boundary():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=5, monotonic=lambda: 0.0
    )["anchor"]
    result = pw.wave_phase(anchor, monotonic=lambda: 15.0)
    assert result["phase"] == pw.PHASE_EXPIRED


def test_wave_phase_zero_margin_collapses_winding_down():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=0, monotonic=lambda: 0.0
    )["anchor"]
    winding = pw.wave_phase(anchor, monotonic=lambda: 10.0)
    assert winding["phase"] == pw.PHASE_EXPIRED


# --- admit_work ---


def test_admit_work_allows_running_only():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=5, monotonic=lambda: 0.0
    )["anchor"]
    assert pw.admit_work(anchor, monotonic=lambda: 5.0)["ok"] is True


def test_admit_work_refuses_winding_down():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=5, monotonic=lambda: 0.0
    )["anchor"]
    result = pw.admit_work(anchor, monotonic=lambda: 12.0)
    assert result["ok"] is False
    assert result["phase"] == pw.PHASE_WINDING_DOWN


def test_admit_work_refuses_expired():
    anchor = pw.wave_anchor(
        launched_at=_TS, deadline_seconds=10, margin_seconds=5, monotonic=lambda: 0.0
    )["anchor"]
    result = pw.admit_work(anchor, monotonic=lambda: 20.0)
    assert result["ok"] is False
    assert result["phase"] == pw.PHASE_EXPIRED


# --- park latch ---


def test_latch_park_writes_and_rereads_real_filesystem(tmp_dir):
    slots = _slots_dir(tmp_dir)
    first = pw.latch_park(
        slots, _SLOT, slot_ref=_SLOT_REF, now=_TS, reason="expired"
    )
    assert first["ok"] is True
    assert first["latch"]["latchedAt"] == _TS
    second = pw.read_park_latch(slots, _SLOT)
    assert second["ok"] is True
    assert second["latched"] is True
    assert second["latch"] == first["latch"]


def test_latch_park_idempotent(tmp_dir):
    slots = _slots_dir(tmp_dir)
    first = pw.latch_park(
        slots, _SLOT, slot_ref=_SLOT_REF, now=_TS, reason="expired"
    )
    second = pw.latch_park(
        slots, _SLOT, slot_ref=_SLOT_REF, now=_TS2, reason="again"
    )
    assert second["ok"] is True
    assert second["latch"]["latchedAt"] == first["latch"]["latchedAt"]


def test_read_park_latch_enoent_not_latched(tmp_dir):
    slots = _slots_dir(tmp_dir)
    result = pw.read_park_latch(slots, _SLOT)
    assert result == {"ok": True, "reason": None, "latched": False, "latch": None}


def test_read_park_latch_malformed_reads_as_latched(tmp_dir):
    slots = _slots_dir(tmp_dir)
    slot_dir = os.path.join(slots, _SLOT)
    os.makedirs(slot_dir, exist_ok=True)
    path = pw.park_latch_path(slots, _SLOT)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    result = pw.read_park_latch(slots, _SLOT)
    assert result["ok"] is False
    assert result["reason"] == pw.REASON_PARK_LATCH_UNREADABLE
    assert result["latched"] is True


def test_latch_park_refuses_symlink(tmp_dir):
    slots = _slots_dir(tmp_dir)
    slot_dir = os.path.join(slots, _SLOT)
    os.makedirs(slot_dir, exist_ok=True)
    path = pw.park_latch_path(slots, _SLOT)
    os.symlink("/tmp/outside", path)
    result = pw.latch_park(
        slots, _SLOT, slot_ref=_SLOT_REF, now=_TS, reason="expired"
    )
    assert result["ok"] is False
    assert result["reason"] == pw.REASON_PARK_LATCH_WRITE_FAILED


# --- validate_step_result / receipt binding ---


def test_validate_step_result_no_receipt_is_indeterminate():
    result = pw.validate_step_result(
        {"outcome": pj.OUTCOME_APPLIED, "receipt": None},
        step=pw.STEP_APP,
        slot_ref=_SLOT_REF,
    )
    assert result["status"] == pw.STATUS_INDETERMINATE
    assert result["reason"] == pw.REASON_STEP_RECEIPT_MISSING


@pytest.mark.parametrize(
    "receipt",
    [
        _receipt(step=pw.STEP_AUTOMATION),
        _receipt(step=pw.STEP_APP, slot_ref="other@1"),
        _receipt(step=pw.STEP_APP, observed_at="bad"),
        _receipt(step=pw.STEP_APP, evidence=""),
    ],
)
def test_validate_step_result_invalid_receipt(receipt):
    result = pw.validate_step_result(
        {"outcome": pj.OUTCOME_APPLIED, "receipt": receipt},
        step=pw.STEP_APP,
        slot_ref=_SLOT_REF,
    )
    assert result["status"] == pw.STATUS_INDETERMINATE
    assert result["reason"] == pw.REASON_STEP_RECEIPT_MISSING


# --- teardown behaviour ---


def test_park_path_never_calls_destructive_handlers(tmp_dir):
    calls = []

    def _spy(step):
        def _handler(ctx):
            calls.append(step)
            return _applied(step)
        return _handler

    handlers = {
        pw.STEP_APP: _spy(pw.STEP_APP),
        pw.STEP_AUTOMATION: _spy(pw.STEP_AUTOMATION),
        pw.STEP_CLEANUP: _spy(pw.STEP_CLEANUP),
        pw.STEP_RECLAIM: _spy(pw.STEP_RECLAIM),
    }
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_PARK),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0]),
    )
    assert pw.STEP_CLEANUP not in calls
    assert pw.STEP_RECLAIM not in calls
    assert result["disposition"] == pw.DISPOSITION_PARKED


def test_latch_between_phases_blocks_cleanup(tmp_dir):
    slots = _slots_dir(tmp_dir)
    calls = []

    def automation_handler(ctx):
        pw.latch_park(
            slots, _SLOT, slot_ref=_SLOT_REF, now=_TS, reason="race"
        )
        return _applied(pw.STEP_AUTOMATION)

    handlers = _all_handlers()
    handlers[pw.STEP_AUTOMATION] = automation_handler
    handlers[pw.STEP_CLEANUP] = lambda ctx: calls.append(pw.STEP_CLEANUP) or _applied(
        pw.STEP_CLEANUP
    )
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=slots,
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0]),
    )
    assert calls == []
    assert result["steps"][pw.STEP_CLEANUP]["status"] == pw.STATUS_REFUSED_PARK


def test_phase_a_independence_app_failure_still_runs_automation(tmp_dir):
    calls = []

    handlers = {
        pw.STEP_APP: lambda ctx: {
            "outcome": pj.OUTCOME_NOT_APPLIED,
            "receipt": None,
            "reason": "stop-failed",
        },
        pw.STEP_AUTOMATION: lambda ctx: calls.append(pw.STEP_AUTOMATION) or _applied(
            pw.STEP_AUTOMATION
        ),
    }
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0]),
    )
    assert pw.STEP_AUTOMATION in calls
    assert result["steps"][pw.STEP_APP]["status"] == pw.STATUS_FAILED
    assert result["steps"][pw.STEP_AUTOMATION]["status"] == pw.STATUS_CONFIRMED


def test_phase_b_unconfirmed_fence_leaves_destructive_not_reached(tmp_dir):
    handlers = {
        pw.STEP_APP: lambda ctx: {
            "outcome": pj.OUTCOME_NOT_APPLIED,
            "receipt": None,
            "reason": "failed",
        },
        pw.STEP_AUTOMATION: lambda ctx: _applied(pw.STEP_AUTOMATION),
    }
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0]),
    )
    assert result["steps"][pw.STEP_CLEANUP]["status"] == pw.STATUS_NOT_REACHED
    assert result["steps"][pw.STEP_RECLAIM]["status"] == pw.STATUS_NOT_REACHED
    assert result["steps"][pw.STEP_CLEANUP]["reason"] == pw.REASON_FENCE_UNCONFIRMED


def test_failed_cleanup_leaves_reclaim_not_reached(tmp_dir):
    handlers = _all_handlers()
    handlers[pw.STEP_CLEANUP] = lambda ctx: {
        "outcome": pj.OUTCOME_NOT_APPLIED,
        "receipt": None,
        "reason": "cleanup-failed",
    }
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0]),
    )
    assert result["steps"][pw.STEP_CLEANUP]["status"] == pw.STATUS_FAILED
    assert result["steps"][pw.STEP_RECLAIM]["status"] == pw.STATUS_NOT_REACHED


def test_raising_handler_is_indeterminate_not_failed(tmp_dir):
    def boom(ctx):
        raise ValueError("handler blew up")

    handlers = _all_handlers()
    handlers[pw.STEP_APP] = boom
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0]),
    )
    assert result["steps"][pw.STEP_APP]["status"] == pw.STATUS_INDETERMINATE
    assert result["steps"][pw.STEP_APP]["reason"] == pw.REASON_STEP_INDETERMINATE
    assert result["disposition"] == pw.DISPOSITION_INCOMPLETE


def test_missing_handler_is_unavailable(tmp_dir):
    handlers = _all_handlers()
    del handlers[pw.STEP_APP]
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0]),
    )
    assert result["steps"][pw.STEP_APP]["status"] == pw.STATUS_UNAVAILABLE
    assert result["disposition"] == pw.DISPOSITION_INCOMPLETE


def test_overrunning_handler_downgraded(tmp_dir):
    mono = _mono_sequence([0.0, 2.0])
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE, stepTimeoutSeconds=1.0),
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=mono,
    )
    assert result["steps"][pw.STEP_APP]["status"] == pw.STATUS_INDETERMINATE
    assert result["steps"][pw.STEP_APP]["reason"] == pw.REASON_STEP_OVERRAN


def test_complete_teardown_disposition(tmp_dir):
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
    )
    assert result["disposition"] == pw.DISPOSITION_TORN_DOWN


def test_assert_destructive_allowed_park_intent():
    result = pw.assert_destructive_allowed(
        pw.STEP_CLEANUP, intent=pw.INTENT_PARK, latched=False
    )
    assert result == {"ok": False, "reason": pw.REASON_PARK_DESTRUCTIVE_REFUSED}


def test_run_destructive_step_refuses_park_intent_directly(tmp_dir, monkeypatch):
    """Covers _run_destructive_step's defence-in-depth park guard (not teardown_slot's short-circuit)."""
    monkeypatch.setattr(
        pw,
        "assert_destructive_allowed",
        lambda *args, **kwargs: {"ok": True},
    )
    slots = _slots_dir(tmp_dir)
    journal = _journal(tmp_dir)
    entry = {
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "intent": pw.INTENT_PARK,
    }
    context = {
        "step": pw.STEP_CLEANUP,
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "intent": pw.INTENT_PARK,
        "instance": None,
        "allocation": None,
        "steps": {
            pw.STEP_APP: {"status": pw.STATUS_CONFIRMED},
            pw.STEP_AUTOMATION: {"status": pw.STATUS_CONFIRMED},
        },
    }
    result = pw._run_destructive_step(
        pw.STEP_CLEANUP,
        entry,
        handlers={pw.STEP_CLEANUP: lambda ctx: _applied(pw.STEP_CLEANUP)},
        context=context,
        mono_fn=lambda: 0.0,
        timeout_seconds=None,
        slots_dir_path=slots,
        journal_path=journal,
        now_fn=_now_fn,
        lock_timeout=30.0,
    )
    assert result == {
        "status": pw.STATUS_REFUSED_PARK,
        "reason": pw.REASON_PARK_DESTRUCTIVE_REFUSED,
        "receipt": None,
        "elapsed": None,
    }


def test_assert_destructive_allowed_latched():
    result = pw.assert_destructive_allowed(
        pw.STEP_CLEANUP, intent=pw.INTENT_COMPLETE, latched=True
    )
    assert result == {"ok": False, "reason": pw.REASON_PARK_DESTRUCTIVE_REFUSED}


# --- journal mapping for cleanup ---


def _replay_cleanup_effects(journal_path):
    replayed = pj.replay(journal_path, slot_ref=_SLOT_REF)
    assert replayed["ok"] is True
    return [
        e for e in replayed["effects"]
        if e.get("kind") == pj.KIND_NAMESPACE_TOUCHED
    ]


def test_journal_cleanup_confirmed(tmp_dir):
    journal = _journal(tmp_dir)
    pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=journal,
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
    )
    effects = _replay_cleanup_effects(journal)
    assert len(effects) == 1
    assert effects[0]["state"] == pj.STATE_APPLIED


def test_journal_cleanup_failed(tmp_dir):
    journal = _journal(tmp_dir)
    handlers = _all_handlers()
    handlers[pw.STEP_CLEANUP] = lambda ctx: {
        "outcome": pj.OUTCOME_NOT_APPLIED,
        "receipt": None,
        "reason": "nope",
    }
    pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=journal,
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0]),
    )
    effects = _replay_cleanup_effects(journal)
    assert len(effects) == 1
    assert effects[0]["state"] == pj.STATE_NOT_APPLIED


def test_journal_cleanup_indeterminate(tmp_dir):
    journal = _journal(tmp_dir)
    handlers = _all_handlers()
    handlers[pw.STEP_CLEANUP] = lambda ctx: {
        "outcome": pj.OUTCOME_INDETERMINATE,
        "receipt": None,
        "reason": "unknown",
    }
    pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=journal,
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0]),
    )
    effects = _replay_cleanup_effects(journal)
    assert len(effects) == 1
    assert effects[0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_run_destructive_step_cleanup_journal_end_write_failure(tmp_dir, monkeypatch):
    journal = _journal(tmp_dir)
    real_end = pj.end_effect
    receipt = _receipt(step=pw.STEP_CLEANUP, evidence="cleaned")

    def fail_end(*args, **kwargs):
        return {"ok": False, "reason": pj.REASON_JOURNAL_WRITE_FAILED}

    monkeypatch.setattr(pj, "end_effect", fail_end)
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers={
            pw.STEP_APP: lambda ctx: _applied(pw.STEP_APP),
            pw.STEP_AUTOMATION: lambda ctx: _applied(pw.STEP_AUTOMATION),
            pw.STEP_CLEANUP: lambda ctx: {
                "outcome": pj.OUTCOME_APPLIED,
                "receipt": receipt,
                "reason": None,
            },
            pw.STEP_RECLAIM: lambda ctx: _applied(pw.STEP_RECLAIM),
        },
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=journal,
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
    )
    cleanup = result["steps"][pw.STEP_CLEANUP]
    assert cleanup["status"] == pw.STATUS_INDETERMINATE
    assert cleanup["reason"] == pw.REASON_STEP_INDETERMINATE
    assert cleanup["status"] != pw.STATUS_CONFIRMED


def test_run_destructive_step_preserves_evidence_when_bookkeeping_raises(
    tmp_dir, monkeypatch,
):
    journal = _journal(tmp_dir)
    receipt = _receipt(step=pw.STEP_CLEANUP, evidence="cleaned")
    calls = {"n": 0}

    def flaky_now():
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("bookkeeping blew up")
        return _TS2

    result = pw._run_destructive_step(
        pw.STEP_CLEANUP,
        _entry(intent=pw.INTENT_COMPLETE),
        {
            pw.STEP_CLEANUP: lambda ctx: {
                "outcome": pj.OUTCOME_APPLIED,
                "receipt": receipt,
                "reason": None,
            },
        },
        {"steps": {pw.STEP_APP: {"status": pw.STATUS_CONFIRMED},
                   pw.STEP_AUTOMATION: {"status": pw.STATUS_CONFIRMED}}},
        lambda: 1.0,
        30.0,
        _slots_dir(tmp_dir),
        journal,
        flaky_now,
        30.0,
    )
    assert result["status"] == pw.STATUS_INDETERMINATE
    assert result["reason"] == pw.REASON_STEP_INDETERMINATE
    assert result["receipt"] == receipt


def test_journal_no_record_when_cleanup_refused_park(tmp_dir):
    journal = _journal(tmp_dir)
    pw.teardown_slot(
        _entry(intent=pw.INTENT_PARK),
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=journal,
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0]),
    )
    effects = _replay_cleanup_effects(journal)
    assert effects == []


def test_journal_no_record_when_cleanup_not_reached(tmp_dir):
    journal = _journal(tmp_dir)
    handlers = _all_handlers()
    handlers[pw.STEP_APP] = lambda ctx: {
        "outcome": pj.OUTCOME_NOT_APPLIED,
        "receipt": None,
        "reason": "failed",
    }
    pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE),
        handlers=handlers,
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=journal,
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0]),
    )
    effects = _replay_cleanup_effects(journal)
    assert effects == []


# --- run_teardown / wave_report ---


def test_run_teardown_rejects_non_list():
    report = pw.run_teardown(
        "not-a-list",
        handlers={},
        slots_dir_path="/tmp/slots",
        journal_path="/tmp/journal.jsonl",
        now_fn=_now_fn,
    )
    assert report["complete"] is False
    assert report["blockers"][0]["reason"] == pw.REASON_SLOTS_INVALID


def test_run_teardown_rejects_duplicate_slot(tmp_dir):
    slots = [_entry(), _entry()]
    report = pw.run_teardown(
        slots,
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0] * 20),
    )
    assert report["complete"] is False
    assert any(
        b["reason"] == pw.REASON_SLOT_ENTRY_INVALID for b in report["blockers"]
    )


def test_wave_report_empty_not_complete():
    report = pw.wave_report({
        "schemaVersion": 1,
        "complete": False,
        "slots": [],
        "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
        "blockers": [],
    })
    assert report["complete"] is False


def test_wave_report_all_parked_is_complete(tmp_dir):
    result = pw.teardown_slot(
        _entry(intent=pw.INTENT_PARK),
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0]),
    )
    report = pw.wave_report({
        "schemaVersion": 1,
        "complete": False,
        "slots": [result],
        "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
        "blockers": [],
    })
    assert report["complete"] is True
    assert report["counts"]["parked"] == 1


def test_wave_report_one_incomplete_makes_whole_incomplete(tmp_dir):
    good = pw.teardown_slot(
        _entry(intent=pw.INTENT_PARK),
        handlers=_all_handlers(),
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0, 1.0, 2.0]),
    )
    bad = pw.teardown_slot(
        _entry(intent=pw.INTENT_COMPLETE, slot="slot-b", slotRef="slot-b@1"),
        handlers={},
        slots_dir_path=_slots_dir(tmp_dir),
        journal_path=_journal(tmp_dir),
        now_fn=_now_fn,
        monotonic=_mono_sequence([0.0]),
    )
    report = pw.wave_report({
        "schemaVersion": 1,
        "complete": False,
        "slots": [good, bad],
        "counts": {"torn-down": 0, "parked": 0, "incomplete": 0},
        "blockers": [],
    })
    assert report["complete"] is False
    assert report["counts"]["incomplete"] == 1


# --- real default monotonic ---


def test_wave_anchor_real_monotonic_default():
    result = pw.wave_anchor(
        launched_at=_TS,
        deadline_seconds=0,
        margin_seconds=0,
    )
    assert result["ok"] is True
    phase = pw.wave_phase(result["anchor"])
    assert phase["ok"] is True
    assert phase["phase"] in (pw.PHASE_WINDING_DOWN, pw.PHASE_EXPIRED)
