"""#1272 layer 2f: ledger-exclusive disposition read, merged projection, write-run binding."""
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


SC = _load("session_contract")
RC = _load("round_certification")
RD = _load("round_driver")
RR = _load("round_records")


def _ledger_owned_state(**over):
    base = {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger",
        "dispositionLedger": [],
        "findings": [],
        "_records": [],
    }
    base.update(over)
    return base


def _family_slice(row):
    if not isinstance(row, dict):
        return {}
    return {f: row[f] for f in SC.DISPOSITION_FAMILY_FIELDS if f in row}


def _content_slice(row):
    if not isinstance(row, dict):
        return {}
    return {f: row[f] for f in RC.CERTIFICATION_LIVE_CONTENT_FIELDS if f in row}


def _hand_landed_evidence_binding(**overrides):
    evidence = {
        "source": "runner",
        "runnerNonce": "hand-landed-nonce",
        "recordDigest": "a" * 64,
        "resultDigest": "b" * 64,
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


def _hand_landed_envelope(evidence, payload, *, order_sha="f" * 64):
    return {
        "orderSha256": order_sha,
        "payload": payload,
        "executionEvidence": evidence,
    }


HEAD = "c" * 40


# --- exclusive read: _records is not a source -----------------------------------------

def test_exclusive_read_records_disposition_not_seen():
    """Ledger-owned: disposition only in _records does not reach certification."""
    key = "k-records-only"
    record_finding = {
        "file": "r.py", "line": 1, "title": "from-records", "severity": "Minor",
        SC.FINDING_KEY_FIELD: key,
        "disposition": "refuted", "dispositionRound": 1, "refutedReason": "stale",
    }
    state = _ledger_owned_state(
        dispositionLedger=[{
            "file": "r.py", "line": 1, "title": "from-records", "severity": "Minor",
            SC.FINDING_KEY_FIELD: key,
        }],
        _records=[{"findings": [record_finding]}],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert key in by_key
    assert by_key[key].get("disposition") is None


def test_exclusive_read_ledger_family_live_content():
    """Ledger-owned: disposition family from ledger, live content fields from live row."""
    key = "k-split"
    ledger_entry = {
        "file": "old.py", "line": 1, "title": "old-title", "severity": "Minor",
        SC.FINDING_KEY_FIELD: key,
        "disposition": "fixed", "dispositionRound": 2,
        "dispositionReceipt": {"headSha": HEAD, "verifyResult": "pass"},
    }
    live_row = {
        "file": "new.py", "line": 9, "title": "new-title", "severity": "Critical",
        SC.FINDING_KEY_FIELD: key, "id": "live-id", "verdict": "CONFIRMED",
    }
    state = _ledger_owned_state(
        dispositionLedger=[ledger_entry],
        findings=[live_row],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    merged = by_key[key]
    assert _family_slice(merged) == _family_slice(ledger_entry)
    assert _content_slice(merged) == _content_slice(live_row)


def test_live_merged_into_without_ledger_seat_refuses():
    """Biting case: live mergedInto without ledger seat refuses disposition-without-receipt."""
    rep_key = "rep-key"
    member_key = "member-key"
    state = _ledger_owned_state(
        dispositionLedger=[{
            SC.FINDING_KEY_FIELD: rep_key,
            "file": "r.py", "line": 1, "title": "rep", "severity": "Minor",
            "disposition": "fixed", "dispositionRound": 2,
        }],
        findings=[{
            SC.FINDING_KEY_FIELD: member_key,
            "file": "m.py", "line": 5, "title": "member", "severity": "Important",
            SC.MERGED_INTO_FIELD: rep_key,
        }],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == member_key


def test_exclusive_read_live_disposition_without_ledger_refuses():
    """Biting case: live disposition with no ledger entry refuses disposition-without-receipt."""
    key = "k-no-receipt"
    live_row = {
        "file": "x.py", "line": 3, "title": "orphan", "severity": "Important",
        SC.FINDING_KEY_FIELD: key,
        "disposition": "refuted", "dispositionRound": 1, "refutedReason": "no seat",
    }
    state = _ledger_owned_state(findings=[live_row])
    by_key, refusal = RC._certification_findings_by_key(state)
    assert by_key == {}
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == key


# --- merged-row projection ------------------------------------------------------------

def test_merged_row_projection_reports_representative_family():
    """Member row keeps identity; disposition family comes from representative."""
    rep_key = "rep-key"
    member_key = "member-key"
    receipt = {"headSha": HEAD, "verifyResult": "pass"}
    rep = {
        "id": "rep-id", "file": "r.py", "line": 1, "title": "rep", "severity": "Minor",
        SC.FINDING_KEY_FIELD: rep_key, SC.RAISED_ROUND_FIELD: 1,
        "disposition": "fixed", "dispositionRound": 2, "dispositionReceipt": receipt,
    }
    member = {
        "id": "member-id", "file": "m.py", "line": 5, "title": "member", "severity": "Important",
        SC.FINDING_KEY_FIELD: member_key, SC.RAISED_ROUND_FIELD: 2,
        SC.MERGED_INTO_FIELD: rep_key,
    }
    by_key = {rep_key: rep, member_key: member}
    row = RC._project_finding(member, by_key)
    assert row["id"] == "member-id"
    assert row["file"] == "m.py"
    assert row["line"] == 5
    assert row["title"] == "member"
    assert row["severity"] == "Important"
    assert row[SC.FINDING_KEY_FIELD] == member_key
    assert row[SC.RAISED_ROUND_FIELD] == 2
    assert row[SC.MERGED_INTO_FIELD] == rep_key
    assert row["disposition"] == "fixed"
    assert row["dispositionReceipt"] == receipt


def test_merged_row_unresolvable_chain_not_reported_dispositioned():
    """Dangling mergedInto or cycle — member is not reported as dispositioned."""
    member_key = "member-key"
    member_dangling = {
        "file": "m.py", "line": 1, "title": "dangling", "severity": "Minor",
        SC.FINDING_KEY_FIELD: member_key,
        SC.MERGED_INTO_FIELD: "missing-rep",
    }
    by_key = {member_key: member_dangling}
    row = RC._project_finding(member_dangling, by_key)
    assert row.get("disposition") is None
    assert "dispositionReceipt" not in row

    cycle_a_key = "cycle-a"
    cycle_b_key = "cycle-b"
    cycle_a = {
        "file": "a.py", "line": 1, "title": "a", "severity": "Minor",
        SC.FINDING_KEY_FIELD: cycle_a_key, SC.MERGED_INTO_FIELD: cycle_b_key,
    }
    cycle_b = {
        "file": "b.py", "line": 2, "title": "b", "severity": "Minor",
        SC.FINDING_KEY_FIELD: cycle_b_key, SC.MERGED_INTO_FIELD: cycle_a_key,
    }
    by_key_cycle = {cycle_a_key: cycle_a, cycle_b_key: cycle_b}
    row_cycle = RC._project_finding(cycle_a, by_key_cycle)
    assert row_cycle.get("disposition") is None
    assert "dispositionReceipt" not in row_cycle


# --- write-run execution-only binding -------------------------------------------------

def test_write_run_stamp_qualifies_execution_only_despite_digest_mismatch():
    """WRITE_RESULT_KIND qualifies with execution-only even when resultDigest mismatches payload."""
    wrong_digest = "0" * 64
    evidence = _hand_landed_evidence_binding(
        resultKind=SC.WRITE_RESULT_KIND,
        resultDigest=wrong_digest,
    )
    payload = {"fixes": [{"file": "a.py", "description": "fixed"}]}
    envelope = _hand_landed_envelope(evidence, payload)
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, binding = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is True
    assert binding == RC.EXECUTION_ONLY_BINDING


def test_review_kind_digest_mismatch_still_refuses():
    """Non-write result kinds still refuse on digest mismatch."""
    fixes = [{"file": "a.py", "description": "fixed"}]
    evidence = _hand_landed_evidence_binding(
        resultKind="fixes",
        resultDigest="0" * 64,
    )
    envelope = _hand_landed_envelope(evidence, {"fixes": fixes})
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, binding = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is False
    assert binding == "execution-evidence-result-mismatch"


# --- bite-proof detectors (axis lines live at guarded production sites) -----------------

def test_bite_bp2f_e_live_disposition_without_ledger_refuses():
    """axis: live disposition without a ledger seat refuses — disposition-without-receipt."""
    key = "bite-e-key"
    state = _ledger_owned_state(findings=[{
        SC.FINDING_KEY_FIELD: key, "disposition": "refuted",
        "file": "e.py", "line": 1, "title": "e", "severity": "Minor",
    }])
    _, refusal = RC._certification_findings_by_key(state)
    assert refusal is not None
    assert refusal["artifact"] == key


def test_bite_bp2f_f_records_not_a_source():
    """axis: ledger-owned reads take disposition family from the ledger only — _records is not a source."""
    key = "bite-f-key"
    state = _ledger_owned_state(
        dispositionLedger=[{SC.FINDING_KEY_FIELD: key, "file": "f.py", "line": 1,
                              "title": "f", "severity": "Minor"}],
        _records=[{"findings": [{
            SC.FINDING_KEY_FIELD: key, "disposition": "refuted",
            "file": "f.py", "line": 1, "title": "f", "severity": "Minor",
        }]}],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert by_key[key].get("disposition") is None


def test_bite_bp2f_g_merged_projection():
    """axis: merged-away members report the representative's disposition family, not their own."""
    rep_key = "bite-g-rep"
    member_key = "bite-g-member"
    rep = {
        SC.FINDING_KEY_FIELD: rep_key, "disposition": "fixed",
        "dispositionReceipt": {"headSha": HEAD, "verifyResult": "pass"},
        "file": "r.py", "line": 1, "title": "r", "severity": "Minor",
    }
    member = {
        SC.FINDING_KEY_FIELD: member_key, SC.MERGED_INTO_FIELD: rep_key,
        "file": "m.py", "line": 2, "title": "m", "severity": "Important",
    }
    row = RC._project_finding(member, {rep_key: rep, member_key: member})
    assert row["disposition"] == "fixed"
    assert row["title"] == "m"


def test_ledger_owned_merge_preserves_identity_from_ledger_seat():
    """Ledger-owned merge copies findingKey and raisedRound from the ledger seat."""
    key = "explicit-ledger-key"
    raised = 3
    ledger_entry = {
        SC.FINDING_KEY_FIELD: key,
        SC.RAISED_ROUND_FIELD: raised,
        "file": "l.py", "line": 1, "title": "ledger-title", "severity": "Minor",
        "disposition": "refuted", "dispositionRound": 2, "refutedReason": "stale",
    }
    live_row = {
        SC.FINDING_KEY_FIELD: "different-live-key",
        "file": "v.py", "line": 9, "title": "live-title", "severity": "Critical",
    }
    state = _ledger_owned_state(
        dispositionLedger=[ledger_entry],
        findings=[{**live_row, SC.FINDING_KEY_FIELD: key}],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    merged = by_key[key]
    assert merged[SC.FINDING_KEY_FIELD] == key
    assert merged[SC.RAISED_ROUND_FIELD] == raised
    assert SC.finding_identity_key(merged) == SC.finding_identity_key(ledger_entry)


def test_receipt_row_carries_identity_through_merge_path():
    """Receipt projection through the real merge path carries findingKey and raisedRound."""
    key = "receipt-merge-key"
    raised = 4
    ledger_entry = {
        SC.FINDING_KEY_FIELD: key,
        SC.RAISED_ROUND_FIELD: raised,
        "file": "r.py", "line": 2, "title": "receipt", "severity": "Important",
        "disposition": "refuted", "dispositionRound": 1, "refutedReason": "gone",
    }
    live_row = {
        SC.FINDING_KEY_FIELD: key,
        "file": "r.py", "line": 2, "title": "receipt", "severity": "Important",
        "id": "live-receipt-id",
    }
    state = _ledger_owned_state(
        dispositionLedger=[ledger_entry],
        findings=[live_row],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    rows = [RC._project_finding(f, by_key) for f in by_key.values()]
    assert len(rows) == 1
    row = rows[0]
    assert row[SC.FINDING_KEY_FIELD] == key
    assert row[SC.RAISED_ROUND_FIELD] == raised


def test_bite_bp2f_r_ledger_identity_survives_merge():
    """axis: ledger-owned merge copies identity fields from the ledger seat, not live."""
    key = "bite-r-key"
    raised = 5
    ledger_entry = {
        SC.FINDING_KEY_FIELD: key,
        SC.RAISED_ROUND_FIELD: raised,
        "file": "b.py", "line": 1, "title": "bite", "severity": "Minor",
        "disposition": "refuted", "dispositionRound": 1, "refutedReason": "x",
    }
    state = _ledger_owned_state(
        dispositionLedger=[ledger_entry],
        findings=[{SC.FINDING_KEY_FIELD: key, "file": "b.py", "line": 1,
                     "title": "bite", "severity": "Minor"}],
    )
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    merged = by_key[key]
    assert merged.get(SC.RAISED_ROUND_FIELD) == raised
    assert SC.finding_identity_key(merged) == key


def test_bite_bp2f_h_write_run_execution_only():
    """axis: write-run stamp proves the run happened — binds no payload (execution-only)."""
    evidence = _hand_landed_evidence_binding(
        resultKind=SC.WRITE_RESULT_KIND, resultDigest="0" * 64,
    )
    envelope = _hand_landed_envelope(evidence, {"fixes": []})
    journal_binding = {field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS}
    ok, binding = RC._hand_landed_evidence_qualifies(
        envelope, HEAD, journal_binding=journal_binding,
        recorded_nonces={"hand-landed-nonce"},
    )
    assert ok is True
    assert binding == RC.EXECUTION_ONLY_BINDING
