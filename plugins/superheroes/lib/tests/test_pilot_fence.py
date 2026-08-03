"""Tests for pilot_fence reassignment acceptance probe."""
import itertools
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_fence as pf  # noqa: E402
import pilot_lifecycle as pl  # noqa: E402
import pilot_slot  # noqa: E402

NOW = "2026-01-01T00:00:00Z"
ACCOUNTS = [{"account": "owner", "role": "resource-owner"}]
SLOT = "slot1"
SLOT_REF = "slot1@1"


def _all_unreachable():
    return {
        pf.CHECK_BROWSER: pf.ANSWER_UNREACHABLE,
        pf.CHECK_PORT: pf.ANSWER_UNREACHABLE,
        pf.CHECK_WORKTREE: pf.ANSWER_UNREACHABLE,
        pf.CHECK_DATASTORE: pf.ANSWER_UNREACHABLE,
    }


def _trusted_probe(slot_ref=SLOT_REF):
    return pf.reassignment_probe_result(slot_ref, _all_unreachable())


def _create_slot(slots_dir):
    result = pl.create_slot(slots_dir, SLOT, ACCOUNTS, now=NOW)
    assert result["ok"]
    return result["record"]


def _advance_to_failed(slots_dir):
    """Drive slot to failed state (legal edge to retired)."""
    def _to_failed(record):
        return pl.transition(record, pl.STATE_PROVISIONED, now=NOW)

    r1 = pl.mutate(slots_dir, SLOT, _to_failed)
    assert r1["ok"]

    def _to_failed_state(record):
        return pl.transition(record, pl.STATE_FAILED, now=NOW)

    r2 = pl.mutate(slots_dir, SLOT, _to_failed_state)
    assert r2["ok"]
    return r2["record"]


def _reason_constants():
    return {
        getattr(pf, name)
        for name in dir(pf)
        if name.startswith("REASON_")
        and isinstance(getattr(pf, name), str)
    }


EXPECTED_REASON_TOKENS = {
    pf.REASON_FENCE_SLOT_REF_INVALID,
    pf.REASON_FENCE_CHECKS_INVALID,
    pf.REASON_FENCE_CHECK_UNKNOWN,
    pf.REASON_FENCE_CHECK_MISSING,
    pf.REASON_FENCE_ANSWER_INVALID,
    pf.REASON_FENCE_CHECK_FAILED,
    pf.REASON_FENCE_RESULT_INVALID,
    pf.REASON_FENCE_RESULT_SLOT_MISMATCH,
    pf.REASON_FENCE_NOW_INVALID,
    pf.REASON_FENCE_SLOTS_DIR_INVALID,
    pf.REASON_FENCE_VERDICT_NOT_APPLICABLE,
}


def test_reason_census():
    assert _reason_constants() == EXPECTED_REASON_TOKENS


def test_all_unreachable_trusted():
    result = _trusted_probe()
    assert result == {
        "ok": True,
        "reason": None,
        "slotRef": SLOT_REF,
        "verdict": pf.VERDICT_TRUSTED,
        "checks": _all_unreachable(),
        "failed": [],
    }
    assert result["checks"] is not _all_unreachable()


def test_exhaustive_grading_cartesian():
    answers = (pf.ANSWER_UNREACHABLE, pf.ANSWER_REACHABLE, pf.ANSWER_INDETERMINATE)
    trusted_count = 0
    for combo in itertools.product(answers, repeat=4):
        checks = dict(zip(pf.REQUIRED_CHECKS, combo))
        result = pf.reassignment_probe_result(SLOT_REF, checks)
        if result["verdict"] == pf.VERDICT_TRUSTED:
            trusted_count += 1
            assert combo == (pf.ANSWER_UNREACHABLE,) * 4
    assert trusted_count == 1


@pytest.mark.parametrize(
    "checks",
    [
        None,
        [],
        "browser",
        (("browser", pf.ANSWER_UNREACHABLE),),
    ],
)
def test_checks_not_mapping_refuses(checks):
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_CHECKS_INVALID
    assert result["verdict"] == pf.VERDICT_RETIRE
    assert result["checks"] == {}


def test_checks_empty_dict_refuses():
    result = pf.reassignment_probe_result(SLOT_REF, {})
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_CHECK_MISSING
    assert result["verdict"] == pf.VERDICT_RETIRE


def test_checks_extra_key_refuses():
    checks = dict(_all_unreachable())
    checks["extra"] = pf.ANSWER_UNREACHABLE
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_CHECK_UNKNOWN
    assert result["verdict"] == pf.VERDICT_RETIRE


def test_checks_three_of_four_refuses():
    checks = {
        pf.CHECK_BROWSER: pf.ANSWER_UNREACHABLE,
        pf.CHECK_PORT: pf.ANSWER_UNREACHABLE,
        pf.CHECK_WORKTREE: pf.ANSWER_UNREACHABLE,
    }
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_CHECK_MISSING
    assert result["verdict"] == pf.VERDICT_RETIRE


@pytest.mark.parametrize(
    "bad_answer",
    [True, 1, None, "UNREACHABLE", "ok"],
)
def test_invalid_answer_refuses(bad_answer):
    checks = _all_unreachable()
    checks[pf.CHECK_BROWSER] = bad_answer
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_ANSWER_INVALID
    assert result["verdict"] == pf.VERDICT_RETIRE


def test_one_reachable_retires():
    checks = _all_unreachable()
    checks[pf.CHECK_PORT] = pf.ANSWER_REACHABLE
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is True
    assert result["reason"] == pf.REASON_FENCE_CHECK_FAILED
    assert result["verdict"] == pf.VERDICT_RETIRE
    assert result["failed"] == [pf.CHECK_PORT]


def test_one_indeterminate_retires():
    checks = _all_unreachable()
    checks[pf.CHECK_DATASTORE] = pf.ANSWER_INDETERMINATE
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is True
    assert result["reason"] == pf.REASON_FENCE_CHECK_FAILED
    assert result["verdict"] == pf.VERDICT_RETIRE
    assert result["failed"] == [pf.CHECK_DATASTORE]


def test_all_reachable_retires_in_order():
    checks = {name: pf.ANSWER_REACHABLE for name in pf.REQUIRED_CHECKS}
    result = pf.reassignment_probe_result(SLOT_REF, checks)
    assert result["ok"] is True
    assert result["reason"] == pf.REASON_FENCE_CHECK_FAILED
    assert result["verdict"] == pf.VERDICT_RETIRE
    assert result["failed"] == list(pf.REQUIRED_CHECKS)


@pytest.mark.parametrize(
    "bad_ref",
    [None, 1, "not-a-ref", "slot1@", "@1", "slot1@01"],
)
def test_invalid_slot_ref_refuses(bad_ref):
    result = pf.reassignment_probe_result(bad_ref, _all_unreachable())
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_SLOT_REF_INVALID
    assert result["verdict"] == pf.VERDICT_RETIRE
    assert result["slotRef"] is None
    assert result["checks"] == {}


def test_apply_trusted_does_not_mutate(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    probe = _trusted_probe()
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, probe, now=NOW)
    assert result == {
        "ok": True,
        "reason": pf.REASON_FENCE_VERDICT_NOT_APPLICABLE,
        "applied": False,
        "record": None,
    }
    loaded = pl.read_record(pl.record_path(slots_dir, SLOT))
    assert loaded["ok"]
    assert loaded["record"]["state"] == pl.STATE_PROVISIONING


def test_apply_retire_transitions_failed_to_retired(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    _advance_to_failed(slots_dir)
    checks = _all_unreachable()
    checks[pf.CHECK_BROWSER] = pf.ANSWER_REACHABLE
    probe = pf.reassignment_probe_result(SLOT_REF, checks)
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, probe, now=NOW)
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["applied"] is True
    assert result["record"]["state"] == pl.STATE_RETIRED
    last = result["record"]["history"][-1]
    assert last["detail"]["reason"] == pf.RETIRE_DETAIL_REASON
    assert last["detail"]["failed"] == [pf.CHECK_BROWSER]


def test_apply_result_slot_ref_none_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    probe = pf.reassignment_probe_result("bad", {})
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_RESULT_SLOT_MISMATCH
    assert result["applied"] is False


def test_apply_result_different_slot_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    other_probe = pf.reassignment_probe_result("slot2@1", _all_unreachable())
    other_probe["verdict"] = pf.VERDICT_RETIRE
    other_probe["failed"] = [pf.CHECK_BROWSER]
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, other_probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_RESULT_SLOT_MISMATCH
    assert result["applied"] is False


def test_apply_stale_generation_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)

    def _to_released(record):
        record = pl.transition(record, pl.STATE_PROVISIONED, now=NOW)
        record = pl.transition(record, pl.STATE_OCCUPIED, now=NOW)
        return pl.transition(record, pl.STATE_RELEASED, now=NOW)

    pl.mutate(slots_dir, SLOT, _to_released)
    pl.mutate(slots_dir, SLOT, lambda r: pl.begin_generation(r, now=NOW))
    stale_probe = pf.reassignment_probe_result(SLOT_REF, _all_unreachable())
    stale_probe["verdict"] = pf.VERDICT_RETIRE
    stale_probe["failed"] = [pf.CHECK_BROWSER]
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, stale_probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pl.REASON_GENERATION_STALE
    assert result["applied"] is False


def test_apply_ahead_generation_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    ahead_probe = pf.reassignment_probe_result("slot1@3", _all_unreachable())
    ahead_probe["verdict"] = pf.VERDICT_RETIRE
    ahead_probe["failed"] = [pf.CHECK_BROWSER]
    result = pf.apply_probe_verdict(slots_dir, "slot1@3", ahead_probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pl.REASON_GENERATION_AHEAD
    assert result["applied"] is False


def test_apply_already_retired_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    _advance_to_failed(slots_dir)

    def _retire(record):
        return pl.transition(record, pl.STATE_RETIRED, now=NOW)

    pl.mutate(slots_dir, SLOT, _retire)
    probe = pf.reassignment_probe_result(SLOT_REF, {n: pf.ANSWER_REACHABLE for n in pf.REQUIRED_CHECKS})
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pl.REASON_RETIRED
    assert result["applied"] is False


def test_apply_missing_record_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    probe = pf.reassignment_probe_result(SLOT_REF, {n: pf.ANSWER_REACHABLE for n in pf.REQUIRED_CHECKS})
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pl.REASON_RECORD_ABSENT
    assert result["applied"] is False


@pytest.mark.parametrize(
    "bad_now",
    [None, "", "2026-01-01T00:00:00", "not-a-time"],
)
def test_apply_now_invalid_refuses(private_tmp, bad_now):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    probe = _trusted_probe()
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, probe, now=bad_now)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_NOW_INVALID
    assert result["applied"] is False


@pytest.mark.parametrize(
    "bad_dir",
    [None, "", 1],
)
def test_apply_slots_dir_invalid_refuses(private_tmp, bad_dir):
    probe = _trusted_probe()
    result = pf.apply_probe_verdict(bad_dir, SLOT_REF, probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_SLOTS_DIR_INVALID
    assert result["applied"] is False


@pytest.mark.parametrize(
    "bad_ref",
    [None, "bad", 1],
)
def test_apply_slot_ref_invalid_refuses(private_tmp, bad_ref):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    probe = _trusted_probe()
    result = pf.apply_probe_verdict(slots_dir, bad_ref, probe, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_SLOT_REF_INVALID
    assert result["applied"] is False


@pytest.mark.parametrize(
    "bad_result",
    [None, [], "probe", {"verdict": "bogus"}, {"verdict": pf.VERDICT_TRUSTED, "slotRef": "bad@"}],
)
def test_apply_result_invalid_refuses(private_tmp, bad_result):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, bad_result, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_RESULT_INVALID
    assert result["applied"] is False


def test_apply_result_slot_ref_malformed_refuses(private_tmp):
    slots_dir = os.path.join(private_tmp, "pilot-slots")
    os.makedirs(slots_dir)
    _create_slot(slots_dir)
    bad = {
        "verdict": pf.VERDICT_RETIRE,
        "slotRef": "not-valid",
        "failed": [],
    }
    result = pf.apply_probe_verdict(slots_dir, SLOT_REF, bad, now=NOW)
    assert result["ok"] is False
    assert result["reason"] == pf.REASON_FENCE_RESULT_INVALID
    assert result["applied"] is False
