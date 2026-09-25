import os
import re

import decision_kinds
import receipt_disclosures
import round_certification as RC
import round_driver as RD
import round_phases
import round_records as RR
import session_contract

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_certified_verdicts_match_driver():
    assert set(RC.CERTIFIED_VERDICTS) == set(RD.CERTIFIED_VERDICTS)


def test_attested_verdict_matches_driver():
    assert RC.ATTESTED_VERDICT == RD.ATTESTED_VERDICT


def test_seat_provenance_matches_records():
    assert set(RC.SEAT_PROVENANCE) == set(RR.SEAT_PROVENANCE)


def test_execution_evidence_read_values_match_records():
    assert RC.EXECUTION_EVIDENCE_READ_VALUES == RR.EXECUTION_EVIDENCE_READ_VALUES


def test_base_guard_checked_matches_driver():
    assert RC.BASE_GUARD_CHECKED == RD.BASE_GUARD_CHECKED


def test_supported_state_versions_match_driver():
    assert RC.SUPPORTED_STATE_VERSIONS == RD.SUPPORTED_STATE_VERSIONS


def test_receipt_disclosures_supported_state_versions_match_driver():
    assert receipt_disclosures.SUPPORTED_STATE_VERSIONS == RD.SUPPORTED_STATE_VERSIONS


def test_receipt_disclosures_schema_version_matches_driver():
    assert receipt_disclosures.SCHEMA_VERSION == RD.SCHEMA_VERSION


def test_decision_keys_are_the_leaf():
    # axis: certification writer reads the decision-kind home — no copy
    assert RC._DECISION_KEYS is decision_kinds.DECISION_KINDS


def test_decision_keys_match_driver_census():
    driver_path = os.path.join(_LIB, "round_driver.py")
    with open(driver_path, encoding="utf-8") as fh:
        source = fh.read()
    driver_keys = set(re.findall(r'_decision\(state,\s*"([^"]+)"', source))
    assert set(decision_kinds.DECISION_KINDS) == driver_keys


def test_execution_evidence_telemetry_values_match_records():
    assert RC.EXECUTION_EVIDENCE_TELEMETRY_VALUES == RR.EXECUTION_EVIDENCE_TELEMETRY_VALUES


def test_execution_evidence_binding_fields_match_records():
    base = tuple(
        field for field in RR.EXECUTION_EVIDENCE_FIELDS if field != "observation"
    )
    assert RC.EXECUTION_EVIDENCE_BINDING_FIELDS == base + ("runKind",)


def test_head_content_blobs_file_name():
    assert RC.HEAD_CONTENT_BLOBS_FILE == RD.HEAD_CONTENT_BLOBS_FILE


def test_head_content_blobs_schema_matches_session_contract():
    assert RC.HEAD_CONTENT_BLOBS_SCHEMA == session_contract.HEAD_CONTENT_BLOBS_SCHEMA
    assert RD.HEAD_CONTENT_BLOBS_SCHEMA == session_contract.HEAD_CONTENT_BLOBS_SCHEMA
    assert RD.HEAD_CONTENT_BLOBS_FILE == session_contract.HEAD_CONTENT_BLOBS_FILE


def test_seat_missing_schema_matches_records():
    assert RC.SEAT_MISSING_SCHEMA == RR.SEAT_MISSING_SCHEMA

def test_execution_evidence_observation_fields_match_records():
    assert (
        RC.EXECUTION_EVIDENCE_OBSERVATION_FIELDS
        == RR.EXECUTION_EVIDENCE_OBSERVATION_FIELDS
    )


def test_phase_tokens_match_round_phases():
    assert session_contract.PANEL_PHASE == round_phases.P_PANEL
    assert session_contract.FIXER_PHASE == round_phases.P_FIXER
    assert session_contract.AUDITS_PHASE == round_phases.P_AUDITS
