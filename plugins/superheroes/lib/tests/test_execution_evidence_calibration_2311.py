"""#2311 WO-F1: the runner-only `observation.calibration` stays out of the journal's evidence.

The runner's engine record carries `observation.calibration` (the review record reads it from there).
`round_records.runner_record_evidence_fields` drops ONLY that key when a runner record becomes
execution evidence; the shared projection and the ingest validator stay closed and unchanged.
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_dispatch  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402

ANCHOR_HEAD = "a" * 40
PANEL_FINDING = [{"dimension": "d", "taxonomy": "t", "title": "x"}]


def _observation():
    return {
        "tokens": 10,
        "toolCalls": 2,
        "stdoutBytes": 100,
        "wallSeconds": 1.5,
        "source": "codex-events",
        "read": "engaged",
        "telemetry": "tool-calls",
    }


def _calibration():
    return [{"label": "core", "file": "core.md", "sha256": "0" * 64,
             "policyVersion": None, "read": "read"}]


def _record(**obs_extra):
    record = {field: "v-" + field for field in RR.EXECUTION_EVIDENCE_FIELDS if field != "observation"}
    record["recordDigest"] = "d" * 64
    record["resultDigest"] = "e" * 64
    observation = _observation()
    observation.update(obs_extra)
    record["observation"] = observation
    return record


def test_a_projection_drops_only_calibration_and_never_mutates_input():
    record = _record(calibration=_calibration())
    before = copy.deepcopy(record)
    observation_before = record["observation"]
    out = RR.runner_record_evidence_fields(record)
    assert out is not None
    assert out["observation"] == _observation()
    assert set(out["observation"]) == RR.EXECUTION_EVIDENCE_OBSERVATION_FIELDS
    assert record == before
    assert record["observation"] is observation_before
    assert record["observation"]["calibration"] == _calibration()
    assert out["observation"] is not record["observation"]


def test_b_projected_evidence_passes_the_validator():
    out = RR.runner_record_evidence_fields(_record(calibration=_calibration()))
    assert RR._validate_execution_evidence(out) is None


def test_c1_shared_projection_keeps_calibration_and_validator_refuses_pointer():
    out = RR.execution_evidence_fields(_record(calibration=_calibration()))
    assert out["observation"]["calibration"] == _calibration()
    reason, _extra = RR._validate_execution_evidence(out)
    assert reason == "execution-evidence-not-inline"


def test_c2_shared_projection_keeps_calibration_and_validator_refuses_unknown_field():
    calibration = [{"label": "core", "read": "read"}]
    out = RR.execution_evidence_fields(_record(calibration=calibration))
    assert out["observation"]["calibration"] == calibration
    reason, extra = RR._validate_execution_evidence(out)
    assert reason == "execution-evidence-unknown-field"
    assert extra["location"] == "observation"
    assert extra["field"] == "calibration"


def test_d_other_extra_observation_key_survives_and_is_refused():
    out = RR.runner_record_evidence_fields(_record(calibration=_calibration(), bogus=1))
    assert out["observation"]["bogus"] == 1
    assert "calibration" not in out["observation"]
    reason, extra = RR._validate_execution_evidence(out)
    assert reason == "execution-evidence-unknown-field"
    assert extra == {"field": "bogus", "location": "observation"}


@pytest.mark.parametrize("record", [None, "x", [], 7])
def test_e1_non_dict_record_defers_to_shared_projection(record):
    assert RR.runner_record_evidence_fields(record) is None
    assert RR.execution_evidence_fields(record) is None


@pytest.mark.parametrize("observation", [None, "x", [], 7])
def test_e1_non_dict_observation_left_for_the_validator(observation):
    record = _record()
    record["observation"] = observation
    out = RR.runner_record_evidence_fields(record)
    assert out == RR.execution_evidence_fields(record)
    assert out["observation"] == observation
    assert RR._validate_execution_evidence(out)[0] == "execution-evidence-malformed"


def test_e2_missing_mandatory_field_still_none():
    for field in RR.EXECUTION_EVIDENCE_FIELDS:
        record = _record(calibration=_calibration())
        del record[field]
        assert RR.runner_record_evidence_fields(record) is None


def test_e5_stored_envelope_paths_do_not_strip_calibration():
    stored = {
        "schema": RR.SEAT_RESULT_SCHEMA_V2,
        "executionEvidence": RR.execution_evidence_fields(_record(calibration=_calibration())),
    }
    row = RR.recorded_row_fields(stored, "a" * 40, RR.CITED_HEAD_SOURCE_ORDER_ANCHOR)
    assert row["executionEvidence"]["observation"]["calibration"] == _calibration()
    assert RR._validate_execution_evidence(stored["executionEvidence"])[0] == (
        "execution-evidence-not-inline")


def test_e_seam_assemble_dispatch_evidence_uses_runner_projection(tmp_path, monkeypatch):
    """`_assemble_dispatch_evidence` journals the runner record without `observation.calibration`."""
    record = {
        "orderPromptSha256": "a" * 64,
        "source": "codex",
        "runnerNonce": "nonce-2311",
        "recordDigest": "d" * 64,
        "observation": dict(_observation(), calibration=_calibration()),
        "resultDigest": RR.payload_sha256(PANEL_FINDING),
        "resultKind": "findings",
        "runKind": engine_dispatch.RUN_KIND_REVIEW,
        "viewHeadSha": ANCHOR_HEAD,
    }
    before = copy.deepcopy(record)
    monkeypatch.setattr(engine_dispatch, "run_execution_record", lambda _run_dir: (record, None))
    envelope = {"phase": RD.P_PANEL, "orderSha256": "a" * 64, "payload": {"findings": PANEL_FINDING}}
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    assembled, refusal, extra, _source = RD._assemble_dispatch_evidence(
        session_dir, envelope, "fake-run", ANCHOR_HEAD, RD.P_PANEL)
    assert refusal is None, (refusal, extra)
    evidence = assembled["executionEvidence"]
    assert evidence["observation"] == _observation()
    assert RR._validate_execution_evidence(evidence) is None
    assert record == before
