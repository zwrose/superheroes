"""Layer 4c certification finish — run-kind and control-probe shape (#1272 WO-A)."""
import pytest
import receipt_disclosures
import round_records as RR
import session_contract

from session_fixture_support import DEFAULT_PANEL_PAYLOAD

_UNKNOWN_DISPATCH_PHASE = "dispatch-future-write"


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        [],
        {"submitted": "yes", "vendors": {}},
        {"submitted": True, "vendors": "claude"},
        {"submitted": True, "vendors": {"claude": 1}},
    ],
)
def test_control_probe_shape_rejects_malformed(malformed):
    assert receipt_disclosures.control_probe_shape(malformed) is False


def test_control_probe_shape_accepts_empty_vendors():
    assert receipt_disclosures.control_probe_shape({"submitted": False, "vendors": {}}) is True


def test_declared_disclosures_omits_malformed_control_probe():
    out = receipt_disclosures.declared_disclosures({"controlProbe": {"submitted": "no"}})
    assert "controlProbe" not in out


def test_execution_evidence_fields_projects_run_kind():
    evidence = {
        "source": "runner",
        "runnerNonce": "n",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
        "observation": {"read": "engaged", "toolCalls": 1},
        "runKind": "review",
    }
    projected = RR.execution_evidence_fields(evidence)
    assert projected is not None
    assert projected["runKind"] == "review"
    payload = DEFAULT_PANEL_PAYLOAD
    payload_digest = RR.payload_sha256(payload)
    review_evidence = {
        "source": "runner",
        "runnerNonce": "n",
        "recordDigest": "d" * 64,
        "resultDigest": payload_digest,
        "resultKind": "findings",
        "observation": {"read": "engaged", "toolCalls": 1},
        "runKind": "review",
    }
    write_evidence = dict(review_evidence, runKind="write")
    assert review_evidence["resultDigest"] == write_evidence["resultDigest"]
    assert RR.execution_evidence_fields(review_evidence) != RR.execution_evidence_fields(
        write_evidence
    )


def test_run_kind_for_phase_refuses_unknown():
    assert session_contract.run_kind_for_phase(_UNKNOWN_DISPATCH_PHASE) is None
    assert session_contract.run_kind_for_phase("dispatch-panell") is None
    assert session_contract.run_kind_for_phase("") is None
    assert session_contract.run_kind_for_phase(None) is None
    assert session_contract.run_kind_for_phase(3) is None
