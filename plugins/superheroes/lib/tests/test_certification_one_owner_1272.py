"""#1272 WO-A2: certification writer one owner, merged projection, execution-only binding."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")
RC = _load("round_certification")
RR = _load("round_records")


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _ctx(state, tmp_path):
    session_dir = str(tmp_path / "sess")
    os.makedirs(session_dir, exist_ok=True)
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    meta = {"sessionId": "s", "headSha": "a" * 40, "baseGuard": RC.BASE_GUARD_CHECKED}
    with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    state.setdefault("config", {})["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["config"]["headSha"] = "a" * 40
    RD.save_state(session_dir, state)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    return ctx


def _ledger_owner_state(**overrides):
    state = {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger",
        "dispositionLedger": [],
        "findings": [],
        "config": {"baseGuard": RC.BASE_GUARD_CHECKED},
    }
    state.update(overrides)
    return state


# --- I1 / E1: ledger owner reads disposition only from ledger -----------------------

def test_E1_live_disposition_without_ledger_entry_refuses(tmp_path):
    key = "orphan.py::live-only@L1"
    state = _ledger_owner_state(
        findings=[{
            SC.FINDING_KEY_FIELD: key,
            "file": "orphan.py",
            "line": 1,
            "title": "live only",
            "severity": "Important",
            "disposition": "refuted",
            "refutedReason": "should not adopt",
        }],
    )
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["detail"] == "live finding carries disposition without a ledger entry"


def test_I1_live_disposition_does_not_override_ledger(tmp_path):
    key = "a.py::bug@L1"
    state = _ledger_owner_state(
        dispositionLedger=[{
            SC.FINDING_KEY_FIELD: key,
            "file": "a.py",
            "line": 1,
            "title": "bug",
            "severity": "Important",
            "disposition": "refuted",
            "refutedReason": "ledger wins",
        }],
        findings=[{
            SC.FINDING_KEY_FIELD: key,
            "file": "a.py",
            "line": 1,
            "title": "bug renamed live",
            "severity": "Critical",
            "disposition": "fixed",
            "dispositionReceipt": {"verifyResult": "pass", "headSha": "a" * 40},
        }],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    merged = by_key[key]
    assert merged["disposition"] == "refuted"
    assert merged["refutedReason"] == "ledger wins"
    assert merged["title"] == "bug renamed live"
    assert merged["severity"] == "Critical"


# --- E2: unknown dispositionLedgerOwner refuses -------------------------------------

def test_E2_unknown_disposition_ledger_owner_refuses(tmp_path):
    state = _ledger_owner_state(dispositionLedgerOwner="hybrid")
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["detail"] == "dispositionLedgerOwner 'hybrid' is not recognized"


# --- I2 / E4: merged row projection -------------------------------------------------

def test_I2_merged_row_projects_resolved_disposition_once():
    rep_key = "m.py::root@L1"
    member_key = "m.py::dup@L2"
    state = _ledger_owner_state(
        dispositionLedger=[
            {
                SC.FINDING_KEY_FIELD: rep_key,
                "file": "m.py",
                "line": 1,
                "title": "root",
                "severity": "Important",
                "raisedRound": 1,
                "disposition": "refuted",
                "refutedReason": "representative reason",
            },
            {
                SC.FINDING_KEY_FIELD: member_key,
                "file": "m.py",
                "line": 2,
                "title": "dup",
                "severity": "Minor",
                "raisedRound": 1,
                "mergedInto": rep_key,
            },
        ],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    projected = RC._project_finding(by_key[member_key], by_key)
    assert projected[SC.FINDING_KEY_FIELD] == member_key
    assert projected["raisedRound"] == 1
    assert projected["mergedInto"] == rep_key
    assert projected["disposition"] == "refuted"
    assert projected["dispositionReceipt"] == "representative reason"
    receipt_rows = [
        RC._project_finding(f, by_key) for f in by_key.values() if isinstance(f, dict)
    ]
    member_rows = [r for r in receipt_rows if r.get(SC.FINDING_KEY_FIELD) == member_key]
    assert len(member_rows) == 1


def test_E4_merged_row_without_representative_disposition_refuses(tmp_path):
    rep_key = "m.py::root@L1"
    member_key = "m.py::dup@L2"
    state = _ledger_owner_state(
        dispositionLedger=[
            {
                SC.FINDING_KEY_FIELD: rep_key,
                "file": "m.py",
                "line": 1,
                "title": "root",
                "severity": "Important",
            },
            {
                SC.FINDING_KEY_FIELD: member_key,
                "file": "m.py",
                "line": 2,
                "title": "dup",
                "severity": "Minor",
                "mergedInto": rep_key,
            },
        ],
    )
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["detail"] == "finding has no disposition recorded"


# --- I3 / E5: execution-only write-run binding --------------------------------------

def _hand_landed_evidence(**overrides):
    evidence = {
        "source": "runner",
        "runnerNonce": "hand-landed-nonce",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    evidence.update(overrides)
    return evidence


def test_I3_write_run_stamp_names_execution_only():
    evidence = _hand_landed_evidence(
        resultKind="evidence",
        resultDigest=SC.payload_sha256({"testFailed": False, "testPassed": True}),
    )
    envelope = {
        "orderSha256": "f" * 64,
        "payload": {"fixes": [{"file": "a.py"}]},
        "executionEvidence": evidence,
    }
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, binding = RC._hand_landed_evidence_qualifies(
        envelope,
        "a" * 40,
        journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is True
    assert binding == "execution-only"


def test_E5_write_run_stamp_does_not_satisfy_payload_bound_proof():
    evidence = _hand_landed_evidence(
        resultKind="evidence",
        resultDigest="0" * 64,
    )
    envelope = {
        "orderSha256": "f" * 64,
        "payload": {"fixes": [{"file": "a.py"}]},
        "executionEvidence": evidence,
    }
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, binding = RC._hand_landed_evidence_qualifies(
        envelope,
        "a" * 40,
        journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is True
    assert binding == "execution-only"

    review_evidence = _hand_landed_evidence(resultKind="findings", resultDigest="0" * 64)
    review_envelope = dict(envelope, executionEvidence=review_evidence)
    review_binding = {field: review_evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok_review, failure_review = RC._hand_landed_evidence_qualifies(
        review_envelope,
        "a" * 40,
        journal_binding=review_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok_review is False
    assert failure_review == "execution-evidence-result-mismatch"
