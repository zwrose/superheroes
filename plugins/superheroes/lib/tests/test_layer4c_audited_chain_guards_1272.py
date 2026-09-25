"""Layer 4c audited-chain guards — confirmation panel (v1), panel contract drift (v5), hand-landed scoped (v9)."""
import json
import os

import round_certification as RC
import round_records as RR
import session_contract

from round_certification_fixtures import (
    ANCHOR_SHA,
    DEFAULT_PANEL_PAYLOAD,
    JOURNAL_FILE,
    PANEL_PHASE,
    SCOPED_PHASE,
    SCOPED_SEAT,
    _binding_fields,
    _dispatch_envelope_for,
    _execution_evidence,
    _orders_manifest_for_seat,
    _recorded_row_from_envelope,
    _slot_nonce,
    _write_envelope,
    _write_orders_manifest,
    case07_audited_chain,
    case07_audited_chain_missing_audit,
)

_CONFIRMATION_ROUND = 3


def _certify(session_dir):
    return RC.certify(session_dir)


def _certified_head(session_dir):
    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    return meta.get(session_contract.FIX_FOLD_HEAD_KEY) or meta["headSha"]


def _drop_dispatch_scoped_records(session_dir):
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    kept = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("phase") == SCOPED_PHASE and row.get("outcome") == "recorded":
                continue
            kept.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in kept:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _append_round3_confirmation_panel(session_dir):
    certified_head = _certified_head(session_dir)
    panel_envelope = _dispatch_envelope_for(
        "code-reviewer", PANEL_PHASE, _CONFIRMATION_ROUND, payload=DEFAULT_PANEL_PAYLOAD)
    manifest = _orders_manifest_for_seat(
        "code-reviewer", rnd=_CONFIRMATION_ROUND, attempt=0, phase=PANEL_PHASE)
    manifest_sha = _write_orders_manifest(session_dir, manifest)
    orders_row = {
        "cmd": "advance",
        "outcome": "orders-emitted",
        "phase": PANEL_PHASE,
        "round": _CONFIRMATION_ROUND,
        "attempt": 0,
        "manifestSha256": manifest_sha,
    }
    panel_row = _recorded_row_from_envelope(
        panel_envelope,
        "code-reviewer",
        PANEL_PHASE,
        _CONFIRMATION_ROUND,
        head_sha=certified_head,
    )
    _write_envelope(
        session_dir,
        {
            "seat": "code-reviewer",
            "phase": PANEL_PHASE,
            "round": _CONFIRMATION_ROUND,
            "envelope": panel_envelope,
        },
    )
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            lines.append(json.loads(line))
    lines.extend([orders_row, panel_row])
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    state["round"] = _CONFIRMATION_ROUND
    state["rounds"][str(_CONFIRMATION_ROUND)] = {
        "roundKind": "full-panel",
        "seatStatus": {"code-reviewer": "run"},
        "blockingCount": 0,
        "verifyResult": "pass",
        "verifyPasses": [],
        "verifiedHead": certified_head,
    }
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _round3_scoped_recorded_rows(session_dir):
    rows = []
    with open(os.path.join(session_dir, JOURNAL_FILE), encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if (
                row.get("phase") == SCOPED_PHASE
                and row.get("round") == _CONFIRMATION_ROUND
                and row.get("outcome") == "recorded"
            ):
                rows.append(row)
    return rows


def _mutate_round3_panel_missing_configured_dimension(session_dir):
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    state.setdefault("config", {})["dimensions"] = ["code-reviewer", "security-reviewer"]
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _hand_landed_scoped_evidence(*, read="engaged", tool_calls=None):
    findings = []
    result_digest = RR.payload_sha256(findings)
    observation = {
        "read": read,
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
        "tokens": None,
        "toolCalls": tool_calls,
    }
    binding = _binding_fields(
        _slot_nonce(SCOPED_SEAT, SCOPED_PHASE, 0),
        result_digest=result_digest,
    )
    evidence = _execution_evidence(binding, phase=SCOPED_PHASE, read=read)
    evidence["resultDigest"] = result_digest
    evidence["observation"] = observation
    return evidence


def _install_hand_landed_scoped_finder(session_dir, *, read="engaged", tool_calls=None):
    certified_head = _certified_head(session_dir)
    _drop_dispatch_scoped_records(session_dir)
    evidence = _hand_landed_scoped_evidence(read=read, tool_calls=tool_calls)
    payload = DEFAULT_PANEL_PAYLOAD
    envelope = _dispatch_envelope_for(SCOPED_SEAT, SCOPED_PHASE, 2, payload=payload)
    envelope = dict(envelope)
    envelope["provenance"] = RC.PROVENANCE_HAND_LANDED
    envelope["executionEvidence"] = evidence
    envelope["manifestSha256"] = ANCHOR_SHA
    envelope["orderSha256"] = ANCHOR_SHA
    envelope["envelopeSha256"] = RR.envelope_sha256(payload, evidence)
    journal_row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": SCOPED_PHASE,
        "round": 2,
        "attempt": 0,
        "seat": SCOPED_SEAT,
        "occurrence": 0,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": envelope["payloadSha256"],
        "headSha": certified_head,
        "citedHead": certified_head,
        "executionEvidence": {
            field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        },
        "recordIdentity": {
            "phase": SCOPED_PHASE,
            "seat": SCOPED_SEAT,
            "occurrence": 0,
            "attempt": 0,
        },
    }
    _write_envelope(
        session_dir,
        {"seat": SCOPED_SEAT, "phase": SCOPED_PHASE, "round": 2, "envelope": envelope},
    )
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            lines.append(json.loads(line))
    lines.append(journal_row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    round2 = state.setdefault("rounds", {}).setdefault("2", {})
    round2.pop("scopedFinder", None)
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def test_v1a_confirmation_panel_at_tip_certifies_without_round3_scoped(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _append_round3_confirmation_panel(session_dir)
    assert _round3_scoped_recorded_rows(session_dir) == []
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


def test_v1b_confirmation_panel_missing_dimension_refuses_panel_gap(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _append_round3_confirmation_panel(session_dir)
    _mutate_round3_panel_missing_configured_dimension(session_dir)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:panel" in refusal["detail"]


def test_v1c_confirmation_panel_still_requires_fix_receipt_audit(tmp_path):
    session_dir = case07_audited_chain_missing_audit(tmp_path)
    _append_round3_confirmation_panel(session_dir)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:fix-receipt" in refusal["detail"]


def test_v9d_hand_landed_scoped_finder_engaged_certifies(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _install_hand_landed_scoped_finder(session_dir, read="engaged", tool_calls=None)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


def test_v9e_hand_landed_scoped_finder_non_engaged_read_refuses(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _install_hand_landed_scoped_finder(session_dir, read="unknown", tool_calls=None)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:scoped-finder" in refusal["detail"]
