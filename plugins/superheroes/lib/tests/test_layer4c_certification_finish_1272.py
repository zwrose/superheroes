"""Layer 4c certification finish — run-kind gate and control-probe shape (#1272 WO-A)."""
import json
import os

import model_registry
import pytest
import receipt_disclosures
import round_certification as RC
import round_records as RR
import session_contract

from round_certification_fixtures import (
    ANCHOR_SHA,
    AUDIT_PHASE,
    DEFAULT_PANEL_PAYLOAD,
    DEFAULT_PANEL_PAYLOAD_SHA,
    HEAD_SHA,
    JOURNAL_FILE,
    PANEL_PHASE,
    write_certifiable_session,
    write_session,
)
from test_seat_independence_1272 import (
    AUDIT_PHASE,
    AUDIT_SEAT,
    FIXER_PHASE,
    FIXER_SEAT,
    _envelope_spec,
    _independence_session,
    _journal_row,
)


def _certify(session_dir):
    return RC.certify(session_dir)


def _panel_session(tmp_path, *, evidence_extra=None):
    journal = []
    envelopes = []
    row = _journal_row("code-reviewer", PANEL_PHASE, source="codex")
    if evidence_extra:
        row["executionEvidence"] = {**row["executionEvidence"], **evidence_extra}
    journal.append(row)
    spec = _envelope_spec("code-reviewer", PANEL_PHASE, source="codex")
    if evidence_extra:
        spec["executionEvidence"] = {
            **spec["executionEvidence"],
            **evidence_extra,
        }
    envelopes.append(spec)
    return write_session(
        tmp_path,
        journal_lines=journal,
        envelopes=envelopes,
    )


def test_run_kind_panel_write_refuses(tmp_path):
    session_dir = _panel_session(tmp_path, evidence_extra={"runKind": "write"})
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def test_run_kind_fixer_review_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            _journal_row("code-reviewer", PANEL_PHASE, source="codex"),
            _journal_row(FIXER_SEAT, FIXER_PHASE, source="cursor", payload_sha=DEFAULT_PANEL_PAYLOAD_SHA),
        ],
        envelopes=[
            _envelope_spec("code-reviewer", PANEL_PHASE, source="codex"),
            _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="cursor"),
        ],
    )
    path = __import__("os").path.join(session_dir, RC.JOURNAL_FILE)
    lines = []
    import json

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("seat") == FIXER_SEAT:
                row["executionEvidence"]["runKind"] = "review"
            lines.append(row)
    with open(path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def test_run_kind_absent_refuses(tmp_path):
    session_dir = _panel_session(tmp_path)
    path = __import__("os").path.join(session_dir, RC.JOURNAL_FILE)
    import json

    lines = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("seat") == "code-reviewer":
                ev = dict(row["executionEvidence"])
                ev.pop("runKind", None)
                row["executionEvidence"] = ev
            lines.append(row)
    with open(path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def test_auditor_family_discriminator_follows_auditor_role(tmp_path, monkeypatch):
    real_family_for = model_registry.family_for

    def _fake_family(role, vendor):
        if role == "auditor" and vendor == "claude":
            return "auditor-family"
        if role == "verifier" and vendor == "claude":
            return "verifier-family"
        return real_family_for(role, vendor)

    monkeypatch.setattr(model_registry, "family_for", _fake_family)
    session_dir = _independence_session(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    audit = receipt["independence"]["auditSeats"][0]
    assert audit["family"] == "auditor-family"
    assert audit["family"] != "verifier-family"


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


def _execution_evidence_for_hand_landed(seat, phase):
    result_digest = RR.payload_sha256(DEFAULT_PANEL_PAYLOAD["findings"])
    return {
        "source": "runner",
        "runnerNonce": "nonce-%s-%s" % (seat, phase),
        "recordDigest": "d" * 64,
        "resultDigest": result_digest,
        "resultKind": "findings",
        "runKind": "review",
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
            "tokens": None,
            "toolCalls": 1,
        },
    }


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


def test_hand_landed_panel_run_kind_write_refuses(tmp_path):
    session_dir = _panel_hand_landed_session(
        tmp_path, PANEL_PHASE, "code-reviewer", run_kind="write")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def test_hand_landed_fixer_run_kind_review_refuses(tmp_path):
    session_dir = _panel_hand_landed_session(
        tmp_path, FIXER_PHASE, FIXER_SEAT, run_kind="review")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def test_hand_landed_panel_run_kind_absent_refuses(tmp_path):
    session_dir = _panel_hand_landed_session(
        tmp_path, PANEL_PHASE, "code-reviewer", run_kind="review", include_run_kind=False)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def test_hand_landed_fixer_run_kind_absent_refuses(tmp_path):
    session_dir = _panel_hand_landed_session(
        tmp_path, FIXER_PHASE, FIXER_SEAT, run_kind="write", include_run_kind=False)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["bindingFailure"] == "evidence-run-kind-mismatch"


def _panel_hand_landed_session(tmp_path, phase, seat, *, run_kind, include_run_kind=True):
    evidence = _execution_evidence_for_hand_landed(seat, phase)
    if include_run_kind:
        evidence["runKind"] = run_kind
    else:
        evidence.pop("runKind", None)
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    journal_row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": 1,
        "attempt": 0,
        "seat": seat,
        "occurrence": 0,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": payload_sha,
        "headSha": HEAD_SHA,
        "citedHead": HEAD_SHA,
        "executionEvidence": {
            field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        },
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": 0,
            "attempt": 0,
        },
    }
    return write_session(
        tmp_path,
        journal_lines=[journal_row],
        envelopes=[
            {
                "seat": seat,
                "phase": phase,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "payloadSha256": payload_sha,
                "payload": DEFAULT_PANEL_PAYLOAD,
                "executionEvidence": evidence,
            }
        ],
    )
