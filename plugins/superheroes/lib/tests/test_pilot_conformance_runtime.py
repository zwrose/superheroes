"""Tests for pilot_conformance_runtime.py — headless wave, reclaim, and mint exercises."""
import os
import shutil
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_conformance as pc  # noqa: E402
import pilot_conformance_runtime as pcr  # noqa: E402
import pilot_mint as pm  # noqa: E402

EXERCISED_AT = "2026-08-07T12:00:00Z"
_SLOT_REF = "slot-a@1"
_SWEEP_AT = "2026-08-05T16:00:00Z"


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _slots_dir(tmp_dir):
    path = os.path.join(tmp_dir, "slots")
    os.makedirs(path)
    return path


def _wave_inputs(tmp_dir):
    return {
        "wave": {
            "slots_dir": _slots_dir(tmp_dir),
            "slot_ref": _SLOT_REF,
        },
    }


def _reclaim_inputs(tmp_dir):
    return {
        "reclaim": {
            "slots_dir": _slots_dir(tmp_dir),
        },
    }


def _mint_inputs(tmp_dir):
    return {
        "mint": {
            "envelope": {
                "enablingFlagEnvVar": "PILOT_MINT_ENABLED",
                "enabledScopes": ["ci"],
                "forbiddenScopes": ["prod"],
                "gateOffTestCommand": [sys.executable, "-c", "import sys; sys.exit(0)"],
            },
            "run_cwd": tmp_dir,
            "environment": {"PILOT_MINT_ENABLED": "1"},
        },
    }


def _failing_mint_inputs(tmp_dir):
    inputs = _mint_inputs(tmp_dir)
    inputs["mint"]["envelope"] = dict(inputs["mint"]["envelope"])
    inputs["mint"]["envelope"]["gateOffTestCommand"] = [
        sys.executable, "-c", "import sys; sys.exit(1)",
    ]
    return inputs


# --- pass paths ---------------------------------------------------------------


def test_wave_headless_pass(tmp_dir):
    record = pcr.wave_headless_exercise(inputs=_wave_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_PASS
    assert record["reason"] is None
    assert set(record["surfaces"]) == set(pcr._WAVE_SURFACES)


def test_reclaim_sweep_pass(tmp_dir):
    record = pcr.reclaim_sweep_exercise(
        inputs=_reclaim_inputs(tmp_dir),
        now=_SWEEP_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert record["warnings"]
    assert all("entryName" in warning and "reason" in warning for warning in record["warnings"])
    assert all("exercise" not in warning for warning in record["warnings"])
    for warning in record["warnings"]:
        for value in warning.values():
            assert os.path.sep not in value or value == os.path.basename(value)


def test_mint_gate_off_pass(tmp_dir):
    record = pcr.mint_gate_off_exercise(inputs=_mint_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_PASS
    assert "stdout" not in record["evidence"]


# --- fail paths ---------------------------------------------------------------


def test_wave_headless_fail_on_unmet_expectation(monkeypatch, tmp_dir):
    monkeypatch.setattr(
        pcr,
        "_check_appctl_fencing",
        lambda: pcr.REASON_EXPECTATION_UNMET,
    )
    record = pcr.wave_headless_exercise(inputs=_wave_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_EXPECTATION_UNMET


def test_reclaim_sweep_fail_when_warned_empty(monkeypatch, tmp_dir):
    monkeypatch.setattr(
        pcr.pilot_reclaim,
        "sweep",
        lambda slots_dir, now: {
            "ok": True,
            "reason": None,
            "warned": [],
            "retained": [],
            "deleted": [],
        },
    )
    monkeypatch.setattr(
        pcr.pilot_reclaim,
        "quarantine_entry",
        lambda *args, **kwargs: {
            "ok": True,
            "reason": None,
            "entryName": "slot-a-gen1-20260802120000",
            "entryPath": "/tmp/x",
            "sidecarPath": "/tmp/x.json",
        },
    )
    record = pcr.reclaim_sweep_exercise(
        inputs=_reclaim_inputs(tmp_dir),
        now=_SWEEP_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_SWEEP_WARNINGS_EMPTY


def test_mint_gate_off_fail_on_nonzero_exit(tmp_dir):
    record = pcr.mint_gate_off_exercise(
        inputs=_failing_mint_inputs(tmp_dir),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pm.REFUSAL_GATE_OFF_TEST_FAILED


# --- fail-closed edges by name ------------------------------------------------


def test_edge1_inputs_not_dict_skips_wave():
    record = pcr.wave_headless_exercise(inputs=[], now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MISSING


def test_edge1_exercise_key_absent_skips_reclaim():
    record = pcr.reclaim_sweep_exercise(inputs={}, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MISSING


def test_edge2_required_key_missing_skips_mint(tmp_dir):
    inputs = _mint_inputs(tmp_dir)
    del inputs["mint"]["envelope"]
    record = pcr.mint_gate_off_exercise(inputs=inputs, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MALFORMED


def test_edge2_wrong_typed_exercise_dict_skips_wave():
    record = pcr.wave_headless_exercise(inputs={"wave": "bad"}, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MALFORMED


def test_edge3_slots_dir_missing_skips_wave():
    record = pcr.wave_headless_exercise(
        inputs={"wave": {"slots_dir": "/no/such/dir", "slot_ref": _SLOT_REF}},
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_SLOTS_DIR_INVALID


def test_edge3_slots_dir_not_directory_skips_reclaim(tmp_dir):
    file_path = os.path.join(tmp_dir, "not-a-dir")
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write("x")
    record = pcr.reclaim_sweep_exercise(
        inputs={"reclaim": {"slots_dir": file_path}},
        now=_SWEEP_AT,
    )
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_SLOTS_DIR_INVALID


def test_edge4_surface_raise_normalized_by_run(monkeypatch, tmp_dir):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(pcr.pilot_appctl, "assert_unique_endpoints", boom)
    result = pc.run(
        [pcr.wave_headless_exercise],
        inputs=_wave_inputs(tmp_dir),
        now=EXERCISED_AT,
    )
    record = result["exercises"][0]
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pc.REASON_EXERCISE_RAISED


def test_edge5_refusal_when_success_expected_fails_wave(monkeypatch, tmp_dir):
    monkeypatch.setattr(
        pcr.pilot_appctl,
        "assert_unique_endpoints",
        lambda allocations: {
            "ok": False,
            "reason": pcr.pilot_appctl.REASON_ENDPOINT_DUPLICATE,
            "duplicates": [],
        },
    )
    record = pcr.wave_headless_exercise(inputs=_wave_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_EXPECTATION_UNMET


def test_edge6_success_when_refusal_expected_fails_fencing(monkeypatch, tmp_dir):
    monkeypatch.setattr(
        pcr.pilot_appctl,
        "assert_unique_endpoints",
        lambda allocations: {"ok": True, "reason": None, "duplicates": []},
    )
    record = pcr.wave_headless_exercise(inputs=_wave_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_EXPECTATION_UNMET


def test_edge7_empty_warned_after_seed_fails_reclaim(tmp_dir):
    record = pcr.reclaim_sweep_exercise(
        inputs=_reclaim_inputs(tmp_dir),
        now=pcr._QUARANTINE_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_SWEEP_WARNINGS_EMPTY


def test_edge8_mint_gate_off_nonzero_exit_fails(tmp_dir):
    record = pcr.mint_gate_off_exercise(
        inputs=_failing_mint_inputs(tmp_dir),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pm.REFUSAL_GATE_OFF_TEST_FAILED


def test_edge9_evidence_truncated_before_record():
    long_text = "x" * 600
    normalized = pcr._normalize_evidence(long_text)
    assert len(normalized) == pcr._EVIDENCE_MAX_LEN
    pc.exercise_record(
        exercise="wave-headless",
        surfaces=[pcr._WAVE_SURFACES[0]],
        result=pc.RESULT_PASS,
        reason=None,
        evidence=normalized,
        exercised_at=EXERCISED_AT,
    )


def test_edge10_warning_value_truncated():
    folded = pcr._fold_warned([
        {
            "entryName": "n" * 300,
            "reason": "r" * 300,
        },
    ])
    assert len(folded[0]["entryName"]) == pcr._WARNING_VALUE_MAX_LEN
    assert len(folded[0]["reason"]) == pcr._WARNING_VALUE_MAX_LEN


# --- coverage honesty ---------------------------------------------------------


def test_skipped_record_surfaces_not_in_report_surfaces(tmp_dir):
    record = pcr.wave_headless_exercise(inputs={}, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    report = pc.report([record])
    assert report["surfaces"] == []
    for surface in pcr._WAVE_SURFACES:
        assert surface in report["unexercised"]


def test_skipped_never_passes(tmp_dir):
    record = pcr.mint_gate_off_exercise(inputs={}, now=EXERCISED_AT)
    assert record["result"] != pc.RESULT_PASS


# --- bite-proof axis tests (committed guards) ---------------------------------


def test_bite_axis_class_a_missing_input_skips_not_passes():
    record = pcr.wave_headless_exercise(inputs=None, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED


def test_bite_axis_class_b_duplicate_endpoint_must_refuse(tmp_dir):
    record = pcr.wave_headless_exercise(inputs=_wave_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_PASS


def test_bite_axis_class_c_past_grace_seed_must_warn(tmp_dir):
    record = pcr.reclaim_sweep_exercise(
        inputs=_reclaim_inputs(tmp_dir),
        now=_SWEEP_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert record["warnings"]


def test_bite_axis_class_d_gate_off_receipt_required(tmp_dir):
    record = pcr.mint_gate_off_exercise(inputs=_mint_inputs(tmp_dir), now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_PASS
