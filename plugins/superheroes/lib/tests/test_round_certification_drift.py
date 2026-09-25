import ast
import os
import re

import decision_kinds
import receipt_disclosures
import round_certification as RC
import round_driver as RD
import round_panel_contract
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
    assert RC.EXECUTION_EVIDENCE_BINDING_FIELDS == tuple(
        field for field in RR.EXECUTION_EVIDENCE_FIELDS if field != "observation"
    )


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


def test_scoped_finder_phase_matches_round_panel_contract():
    assert RC._SCOPED_FINDER_PHASE == round_panel_contract.P_SCOPED_FINDER_PHASE


def test_round_phases_p_scoped_is_panel_contract_token():
    assert round_phases.P_SCOPED == round_panel_contract.P_SCOPED_FINDER_PHASE


def test_round_phases_dimensions_equal_panel_contract_default():
    assert tuple(round_phases.DIMENSIONS) == round_panel_contract.DEFAULT_PANEL_DIMENSIONS


def test_round_phases_panel_dimensions_delegates_to_panel_contract():
    cases = (
        None,
        {},
        {"dimensions": []},
        {"dimensions": ["code-reviewer", 1, None]},
        {"dimensions": ["code-reviewer"]},
    )
    for cfg in cases:
        assert round_phases.panel_dimensions(cfg) == round_panel_contract.panel_dimensions_from_config(
            cfg
        )


def test_round_phases_p_scoped_sourced_from_panel_contract_ast():
    phases_path = os.path.join(_LIB, "round_phases.py")
    with open(phases_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=phases_path)
    p_scoped_assigns = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "P_SCOPED":
                    p_scoped_assigns.append(node.value)
    assert len(p_scoped_assigns) == 1
    value = p_scoped_assigns[0]
    assert isinstance(value, ast.Attribute)
    assert isinstance(value.value, ast.Name) and value.value.id == "round_panel_contract"
    assert value.attr == "P_SCOPED_FINDER_PHASE"
    scoped_literal = '"dispatch-scoped-finder"'
    with open(phases_path, encoding="utf-8") as fh:
        source = fh.read()
    assert scoped_literal not in source


def test_round_phases_panel_dimensions_delegates_via_ast():
    phases_path = os.path.join(_LIB, "round_phases.py")
    with open(phases_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=phases_path)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "panel_dimensions"
    )
    returns = [node for node in fn.body if isinstance(node, ast.Return)]
    assert len(returns) == 1
    ret = returns[0]
    call = ret.value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Attribute)
    assert isinstance(call.func.value, ast.Name) and call.func.value.id == "round_panel_contract"
    assert call.func.attr == "panel_dimensions_from_config"
