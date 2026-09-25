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
    _audit_dispatch_envelope,
    _recorded_row_from_envelope,
    case07_audited_chain,
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


def test_hand_landed_stale_head_outside_chain_refuses(tmp_path):
    stale_head = "b" * 40
    seat = "code-reviewer"
    evidence = _execution_evidence_for_hand_landed(seat, PANEL_PHASE)
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    journal_row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": 0,
        "seat": seat,
        "occurrence": 0,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": payload_sha,
        "headSha": stale_head,
        "citedHead": stale_head,
        "executionEvidence": {
            field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        },
        "recordIdentity": {
            "phase": PANEL_PHASE,
            "seat": seat,
            "occurrence": 0,
            "attempt": 0,
        },
    }
    session_dir = write_session(
        tmp_path,
        journal_lines=[journal_row],
        envelopes=[
            {
                "seat": seat,
                "phase": PANEL_PHASE,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "payloadSha256": payload_sha,
                "payload": DEFAULT_PANEL_PAYLOAD,
                "executionEvidence": evidence,
            }
        ],
    )
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:" in refusal["detail"]
    assert "hand-landed seat cited head is stale" in refusal["detail"]


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


def _panel_hand_landed_case07(session_dir):
    import json
    import os

    import record_paths

    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("seat") == "code-reviewer" and row.get("outcome") == "recorded":
                row["provenance"] = RC.PROVENANCE_HAND_LANDED
                evidence = row.get("executionEvidence") or {}
                row["executionEvidence"] = {
                    field: evidence[field]
                    for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
                    if field in evidence
                }
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    path = record_paths.store_path(
        session_dir,
        1,
        PANEL_PHASE,
        record_paths.storage_key("code-reviewer", 0),
        0,
    )
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    envelope["provenance"] = RC.PROVENANCE_HAND_LANDED
    envelope["manifestSha256"] = ANCHOR_SHA
    envelope["orderSha256"] = ANCHOR_SHA
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, sort_keys=True)


def test_hand_landed_stale_head_inside_chain_certifies(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _panel_hand_landed_case07(session_dir)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"
    panel_rows = [
        row for row in receipt["seats"] if row["seat"] == "code-reviewer"
    ]
    assert len(panel_rows) == 1
    assert panel_rows[0]["provenance"] == RC.PROVENANCE_HAND_LANDED


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


def _assert_fix_receipt_audited_chain_refusal(refusal):
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:fix-receipt" in refusal["detail"]


def _case07_audit_target_id(session_dir):
    state = json.load(open(os.path.join(session_dir, RC.STATE_FILE), encoding="utf-8"))
    finding = state["findings"][0]
    return finding[session_contract.FINDING_KEY_FIELD]


def _append_duplicate_audit_record(session_dir, target_id, certified_head):
    import record_paths

    dup = _audit_dispatch_envelope(target_id, 2)
    dup["attempt"] = 1
    dup["envelopeSha256"] = RR.envelope_sha256(
        dup["payload"], dup["executionEvidence"])
    row = _recorded_row_from_envelope(
        dup, target_id, AUDIT_PHASE, 2, head_sha=certified_head, attempt=1)
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    path = record_paths.store_path(
        session_dir, 2, AUDIT_PHASE, record_paths.storage_key(target_id, 0), 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(dup, fh, sort_keys=True)


def test_audit_fold_duplicate_rulings_refuse_fix_receipt(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    target_id = _case07_audit_target_id(session_dir)
    _append_duplicate_audit_record(
        session_dir, target_id, meta[session_contract.FIX_FOLD_HEAD_KEY])
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    _assert_fix_receipt_audited_chain_refusal(refusal)


def _mutate_audit_runner_source(session_dir, source):
    import record_paths

    target_id = _case07_audit_target_id(session_dir)
    path = record_paths.store_path(
        session_dir, 2, AUDIT_PHASE, record_paths.storage_key(target_id, 0), 0)
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    evidence = dict(envelope["executionEvidence"])
    evidence["source"] = source
    envelope["executionEvidence"] = evidence
    envelope["envelopeSha256"] = RR.envelope_sha256(
        envelope["payload"], envelope["executionEvidence"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, sort_keys=True)
    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    head = meta[session_contract.FIX_FOLD_HEAD_KEY]
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if (
                row.get("outcome") == "recorded"
                and row.get("phase") == AUDIT_PHASE
                and row.get("seat") == target_id
                and row.get("attempt") == 0
            ):
                row = _recorded_row_from_envelope(
                    envelope, target_id, AUDIT_PHASE, 2, head_sha=head, attempt=0)
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _mutate_audit_selected_vendor(session_dir, vendor):
    rnd, phase, attempt = 2, AUDIT_PHASE, 0
    manifest_path = RC._orders_manifest_path(session_dir, rnd, phase, attempt)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    for entry in manifest.get("seats", {}).values():
        if isinstance(entry, dict):
            entry["vendor"] = vendor
    text = session_contract.canonical(manifest)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    new_sha = session_contract.sha256_text(text)
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if (
                row.get("outcome") == "orders-emitted"
                and row.get("phase") == phase
                and row.get("round") == rnd
                and row.get("attempt") == attempt
            ):
                row["manifestSha256"] = new_sha
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def test_audit_fold_missing_manifest_entry_refuses_fix_receipt(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _mutate_audit_runner_source(session_dir, "not-a-vendor")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    _assert_fix_receipt_audited_chain_refusal(refusal)


def test_audit_fold_manifest_vendor_mismatch_refuses_fix_receipt(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _mutate_audit_selected_vendor(session_dir, "claude")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    _assert_fix_receipt_audited_chain_refusal(refusal)


def test_audit_fold_selected_auditor_differs_from_runner_refuses_fix_receipt(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _mutate_audit_selected_vendor(session_dir, "claude")
    _mutate_audit_runner_source(session_dir, "codex")
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    _assert_fix_receipt_audited_chain_refusal(refusal)


def test_audited_chain_certifies_despite_stale_audit_targets_in_state(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    state["round"] = 3
    state["_auditTargets"] = [
        {
            "id": "other-finding::src/other.py::9",
            "auditorVendor": "claude",
            "file": "src/other.py",
            "line": 9,
            "title": "unrelated",
            "severity": "Important",
        },
    ]
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


def test_audited_chain_refuses_when_dispatch_audit_manifest_tampered(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    manifest_path = RC._orders_manifest_path(session_dir, 2, AUDIT_PHASE, 0)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    for entry in manifest.get("seats", {}).values():
        if isinstance(entry, dict):
            entry["vendor"] = "tampered-vendor"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, sort_keys=True)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert "orders manifest sha256 does not match event manifestSha256" in refusal["detail"]


def test_audited_chain_certifies_when_display_id_differs_from_canonical_key(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    finding = state["findings"][0]
    assert finding["id"] != finding[session_contract.FINDING_KEY_FIELD]
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


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


def _panel_hand_landed_session(tmp_path, phase, seat, *, run_kind):
    evidence = _execution_evidence_for_hand_landed(seat, phase)
    evidence["runKind"] = run_kind
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
