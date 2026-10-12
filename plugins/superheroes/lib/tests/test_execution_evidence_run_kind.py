"""The run kind on execution evidence."""
import round_records as RR
import session_contract

from session_fixture_support import DEFAULT_PANEL_PAYLOAD

_UNKNOWN_DISPATCH_PHASE = "dispatch-future-write"


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
