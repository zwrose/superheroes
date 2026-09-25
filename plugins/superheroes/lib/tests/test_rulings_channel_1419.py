"""#1419 WO-A — declared rulings channel (rule verb)."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_certification as RC
import round_driver as RD
import round_orders
import round_phases as RP
import round_records as RR
import session_contract as SC
from round_certification_fixtures import (
    _default_case08_new_issues,
    case08_new_issue_audit,
    write_session,
)

_WELL_FORMED_FOLLOW_UP = {
    "item": "track in backlog",
    "revisitTrigger": "next release",
    "classClosure": "tracked in issue-42",
}
_PROVENANCE = {
    "ruledBy": "owner",
    "ruledAt": "2026-09-25T12:00:00Z",
    "records": ["https://github.com/zwrose/superheroes/issues/1419#issuecomment-1"],
}


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _write_ruling_file(path, body):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, sort_keys=True)


def _minimal_ruling_file(tmp_path, **overrides):
    path = str(tmp_path / "rulings.json")
    body = {
        "rulings": [{
            "id": "k1",
            "ruling": "out-of-scope",
            "reason": "not this change",
            "followUp": dict(_WELL_FORMED_FOLLOW_UP),
        }],
        "_provenance": dict(_PROVENANCE),
    }
    body.update(overrides)
    _write_ruling_file(path, body)
    return path


def _session_with_fix_batch(tmp_path):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    key = "f.py::mechanical finding@L1"
    state = {
        "schemaVersion": RD.STATE_SCHEMA_VERSION,
        "round": 2,
        "step": RP.P_FIXER,
        "decisions": [],
        "findings": [],
        "rounds": {"2": {"roundKind": "fix"}},
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none", "fixerVendor": "claude"},
        "_fixBatch": [{
            SC.FINDING_KEY_FIELD: key,
            "id": key,
            "file": "f.py",
            "line": 1,
            "title": "mechanical finding",
            "severity": "Important",
        }],
        SC.DISPOSITION_LEDGER_KEY: [{
            SC.FINDING_KEY_FIELD: key,
            "file": "f.py",
            "line": 1,
            "title": "mechanical finding",
            "severity": "Important",
            SC.RAISED_ROUND_FIELD: 1,
            SC.RAISED_SEQ_FIELD: 1,
        }],
        "pending": {
            "phase": RP.P_FIXER,
            "round": 2,
            "attempt": 0,
            "payload": {},
        },
        "terminal": None,
        "certification": None,
    }
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = SC.DISPOSITION_LEDGER_OWNER_VALUE
    with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
        json.dump({"repoRoot": str(tmp_path), "sessionId": "test-session-001"}, fh)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    RD.save_state(session_dir, state)
    return session_dir, key


def _save_state(session_dir, state):
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def test_t1_refusal_leaves_state_unchanged(tmp_path):
    """T1 — refused rule does not mutate loop state."""
    session_dir, key = _session_with_fix_batch(tmp_path)
    before = _state_bytes(session_dir)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0].pop("reason")
    _write_ruling_file(path, doc)
    out = RD.cmd_rule(session_dir, path, "advisor")
    assert out["ok"] is False
    assert out["reason"] == RD.RULING_REASON_MISSING
    assert _state_bytes(session_dir) == before


def test_t2_out_of_scope_ruling_excludes_fix_batch_row(tmp_path):
    """T2 — out-of-scope ruling removes the key from the fix batch."""
    session_dir, key = _session_with_fix_batch(tmp_path)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0]["id"] = key
    _write_ruling_file(path, doc)
    out = RD.cmd_rule(session_dir, path, "owner")
    assert out["ok"] is True, out
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    assert state.get("_fixBatch") in (None, [])
    assert key in RD._live_out_of_scope_ruling_keys(state)


def test_t3_rulings_block_in_hashed_fixer_order(tmp_path):
    """T3 — rulings render inside the fixer order (evidence binding surface)."""
    session_dir, key = _session_with_fix_batch(tmp_path)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0]["id"] = key
    _write_ruling_file(path, doc)
    assert RD.cmd_rule(session_dir, path, "owner")["ok"] is True
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    context = {
        "rulings": RD._rulings_for_order_context(state, RP.P_FIXER),
        "fix_batch_sha256": "abc123deadbeef",
    }
    block = round_orders._format_rulings_block(context)
    assert "Owner and advisor rulings" in block
    assert "not this change" in block
    assert "abc123deadbeef" in block


def test_t4_audit_new_issue_certifies_after_ruling(tmp_path):
    """T4 — ruling seeds disposition for a ledger-absent audit new issue."""
    session_dir = case08_new_issue_audit(tmp_path)
    cand = dict(_default_case08_new_issues()[0])
    key = SC.minted_identity_key(cand)
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    state.pop("terminal", None)
    state["step"] = RP.P_SCOPED
    _save_state(session_dir, state)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0]["id"] = key
    _write_ruling_file(path, doc)
    out = RD.cmd_rule(session_dir, path, "owner")
    assert out["ok"] is True, out
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    row = next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if r.get(SC.FINDING_KEY_FIELD) == key)
    assert row.get("disposition") == "out-of-scope"
    assert row.get(SC.RAISED_SEQ_FIELD) is not None
    assert row.get(SC.DISPOSITION_SEQ_FIELD) is not None


def test_t5_restamp_raised_row_on_re_raise(tmp_path):
    """T5 — re-raised audit new issue gets raisedRound re-stamped before disposition."""
    session_dir = case08_new_issue_audit(tmp_path)
    cand = dict(_default_case08_new_issues()[0])
    key = SC.minted_identity_key(cand)
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    state.pop("terminal", None)
    state["step"] = RP.P_SCOPED
    state[SC.DISPOSITION_LEDGER_KEY] = [{
        SC.FINDING_KEY_FIELD: key,
        "file": cand["file"],
        "line": cand["line"],
        "title": cand["title"],
        "severity": cand["severity"],
        SC.RAISED_ROUND_FIELD: 1,
        SC.RAISED_SEQ_FIELD: 1,
    }]
    _save_state(session_dir, state)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0]["id"] = key
    _write_ruling_file(path, doc)
    assert RD.cmd_rule(session_dir, path, "owner")["ok"] is True
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    row = next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if r.get(SC.FINDING_KEY_FIELD) == key)
    assert row.get(SC.RAISED_ROUND_FIELD) >= 2
    assert row.get("disposition") == "out-of-scope"


def test_t6_disposition_precedence_blocks_overwrite(tmp_path):
    """T6 — live out-of-scope ruling blocks a later fixed disposition."""
    session_dir, key = _session_with_fix_batch(tmp_path)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0]["id"] = key
    _write_ruling_file(path, doc)
    assert RD.cmd_rule(session_dir, path, "owner")["ok"] is True
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    RD._record_disposition(state, key, "fixed", state["round"])
    _save_state(session_dir, state)
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    row = next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if r.get(SC.FINDING_KEY_FIELD) == key)
    assert row.get("disposition") == "out-of-scope"
    kinds = [d["kind"] for d in state.get("decisions") or []]
    assert "ruling-recorded" in kinds


def test_t7_receipt_projects_rulings_and_panel_diff_source(tmp_path):
    """T7 — build_receipt carries round rulings and panelDiffSource."""
    session_dir, key = _session_with_fix_batch(tmp_path)
    path = _minimal_ruling_file(tmp_path)
    doc = json.load(open(path, encoding="utf-8"))
    doc["rulings"][0]["id"] = key
    _write_ruling_file(path, doc)
    assert RD.cmd_rule(session_dir, path, "owner")["ok"] is True
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    state["rounds"]["2"]["panelDiffSource"] = "git-derived"
    receipt = RD.build_receipt(state, session_dir)
    round_entry = next(r for r in receipt["rounds"] if r["round"] == 2)
    assert round_entry.get("rulings")
    assert round_entry.get("panelDiffSource") == "git-derived"
    cert_rounds = RC._build_receipt_rounds(state, RC.RECEIPT_FORM_CERTIFIED)
    cert_entry = next(r for r in cert_rounds if r["round"] == 2)
    assert cert_entry.get("rulings")
    assert cert_entry.get("panelDiffSource") == "git-derived"
