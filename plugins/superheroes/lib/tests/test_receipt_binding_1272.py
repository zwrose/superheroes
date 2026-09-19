"""#1272 WO-A3: receipt binding, staged-id fail-closed, followUp submit validation."""
import base64
import hashlib
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
V = _load("verification")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}
    base.update(over)
    return base


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


def _write_head_blobs(tmp_path, head_sha, file_path, content):
    digest = hashlib.sha256(content).hexdigest()
    session_dir = str(tmp_path)
    data = {
        "schema": SC.HEAD_CONTENT_BLOBS_SCHEMA,
        "reads": [{
            "headSha": head_sha,
            "path": file_path,
            "contentDigest": digest,
            "bytes": len(content),
            "readError": None,
        }],
        "files": {file_path: base64.b64encode(content).decode("ascii")},
    }
    with open(os.path.join(session_dir, SC.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return digest


def _fixed_ledger_entry(key, head_sha, file_path, digest, verify_result="pass", disp_round=1):
    return {
        SC.FINDING_KEY_FIELD: key,
        "file": file_path,
        "line": 1,
        "title": "bug",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": disp_round,
        "dispositionReceipt": {
            "headSha": head_sha,
            "verifyResult": verify_result,
            "fixContentHeadSha": head_sha,
            "fixContentDigest": digest,
        },
    }


# --- J1 finalization -----------------------------------------------------------------

def test_finalize_rebinds_fixed_receipt_to_certified_head(tmp_path):
    head_r1 = "a" * 40
    head_r2 = "b" * 40
    path = "f.py"
    content = b"fixed content\n"
    digest = _write_head_blobs(tmp_path, head_r2, path, content)
    key = "f.py@L1#deadbeef"
    entry = _fixed_ledger_entry(key, head_r1, path, digest, disp_round=1)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head_r2
    state["rounds"] = {"1": {"verifyResult": "pass"}, "2": {"verifyResult": "pass"}}
    state["dispositionLedger"] = [entry]
    state["_foldSessionDir"] = str(tmp_path)
    fault = RD._finalize_fixed_disposition_receipts(state, str(tmp_path), state["config"])
    assert fault is None
    receipt = _ledger_by_key(state)[key]["dispositionReceipt"]
    assert receipt["headSha"] == head_r2
    assert receipt["verifyResult"] == "pass"


def test_finalize_refuses_when_fix_absent_at_certified_head(tmp_path):
    head = "c" * 40
    path = "missing.py"
    key = "missing.py@L1"
    entry = _fixed_ledger_entry(key, head, path, "d" * 64)
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head
    state["rounds"] = {"1": {"verifyResult": "pass"}}
    state["dispositionLedger"] = [entry]
    fault = RD._finalize_fixed_disposition_receipts(state, str(tmp_path), state["config"])
    assert fault == "fixed-disposition-fix-absent-at-certified-head"


def test_finalize_refuses_when_final_round_verify_not_pass(tmp_path):
    head = "d" * 40
    path = "g.py"
    content = b"ok\n"
    digest = _write_head_blobs(tmp_path, head, path, content)
    key = "g.py@L1"
    entry = _fixed_ledger_entry(key, head, path, digest)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head
    state["rounds"] = {"1": {"verifyResult": "pass"}, "2": {"verifyResult": "fail"}}
    state["dispositionLedger"] = [entry]
    fault = RD._finalize_fixed_disposition_receipts(state, str(tmp_path), state["config"])
    assert fault == "fixed-disposition-finalization-verify-not-pass"


def test_terminal_converged_parks_on_finalization_fault(tmp_path):
    head = "e" * 40
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head
    state["rounds"] = {"1": {"verifyResult": "fail"}}
    state["dispositionLedger"] = [_fixed_ledger_entry("k", head, "x.py", "f" * 64)]
    state["_foldSessionDir"] = str(tmp_path)
    RD._terminal_converged(state, state["config"], full_panel=False)
    assert state["terminal"] == "cannot-certify"
    assert "fixed-disposition-finalization-verify-not-pass" in state["certification"]["reason"]


# --- J2 staged id --------------------------------------------------------------------

def test_verifier_drop_unknown_staged_id_fault():
    finding = {"file": "r.py", "line": 3, "title": "leak", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    staged = V.stage_ids(compiled)
    fid = staged[0]["id"]
    fault = RD.verifier_drop_staged_id_fault(state, {
        "verdicts": [{"id": "v999", "verdict": "REFUTED", "reason": "gone"}]})
    assert fault == "staged-id-unresolvable: staged id 'v999' maps to no entry"
    fault = RD.verifier_drop_staged_id_fault(state, {
        "verdicts": [{"id": fid, "verdict": "REFUTED", "reason": "gone"}]})
    assert fault is None


def test_synthesis_merge_unknown_member_id_fault():
    f1 = {"file": "m.py", "line": 1, "title": "a", "severity": "Important", "verdict": "CONFIRMED"}
    f2 = {"file": "m.py", "line": 2, "title": "b", "severity": "Minor", "verdict": "CONFIRMED"}
    compiled, _ = RD.mechanical_compile([f1, f2], None)
    state = RD.new_state(_cfg())
    staged = V.stage_ids(compiled)
    state["_verified"] = staged
    id0, id1 = staged[0]["id"], staged[1]["id"]
    fault = RD.synthesis_staged_id_fault(state, {"grouping": [{
        "group_id": "g", "member_ids": [id0, "v-missing"]}]})
    assert fault == "staged-id-unresolvable: staged id 'v-missing' maps to no entry"


# --- J3 followUp at submit -----------------------------------------------------------

def test_judgment_malformed_follow_up_fault():
    fault = RD.judgment_follow_up_fault({"dispositions": [{
        "id": "k", "disposition": "skip", "reason": "choice",
        "followUp": {"revisitTrigger": "later"},
    }]})
    assert fault.startswith("follow-up-malformed:")


def test_judgment_absent_follow_up_not_malformed():
    assert RD.judgment_follow_up_fault({"dispositions": [{
        "id": "k", "disposition": "skip", "reason": "choice",
    }]}) is None


def test_stall_malformed_follow_up_fault():
    fault = RD.stall_follow_up_fault({
        "choice": RD.ACCEPT_RISK_CHOICE,
        "followUp": {"item": "risk accepted"},
    })
    assert fault.startswith("follow-up-malformed:")


# --- J4 identity invariance ----------------------------------------------------------

_TRANSIENT_ATTACH_FIELDS = (
    ("dispositionRound", 2),
    ("refutedReason", "not reproducible"),
    ("outOfScopeReason", "owner skip"),
    ("followUp", {"item": "x", "revisitTrigger": "m2", "classClosure": "none"}),
    ("mergedInto", "other-key"),
    ("raisedRound", 1),
)


@pytest.mark.parametrize("field,value", _TRANSIENT_ATTACH_FIELDS)
def test_disposition_fields_do_not_change_content_canonical(field, value):
    finding = {"file": "i.py", "line": 4, "title": "identity test", "severity": "Important"}
    before = SC.finding_content_canonical(finding)
    finding[field] = value
    after = SC.finding_content_canonical(finding)
    assert before == after


# --- J5 execution-only binding -------------------------------------------------------

def test_write_run_execution_binding_token():
    assert RD._execution_evidence_satisfies_payload_proof(SC.WRITE_RESULT_KIND) is False
    assert RD._execution_evidence_satisfies_payload_proof("findings") is True


def test_assemble_dispatch_evidence_write_run_names_execution_only(tmp_path, monkeypatch):
    import engine_dispatch
    record = {
        "source": "codex",
        "runnerNonce": "n" * 32,
        "recordDigest": "a" * 64,
        "resultDigest": "b" * 64,
        "resultKind": "evidence",
        "observation": {
            "read": "engaged",
            "source": "codex",
            "telemetry": "tool-calls",
            "stdoutBytes": 1,
            "wallSeconds": 1.0,
        },
        "orderPromptSha256": "c" * 64,
    }
    monkeypatch.setattr(engine_dispatch, "run_execution_record", lambda _d: (record, None))
    envelope = {"orderSha256": "c" * 64, "payload": {"fixes": []}}
    assembled, refusal, _extra = RD._assemble_dispatch_evidence(
        str(tmp_path), envelope, "/tmp/run")
    assert refusal is None
    assert assembled["executionBinding"] == "execution-only"


# --- bite-proof detectors (F1–F6) --------------------------------------------------

def test_bite_F1_fix_absent_detector():
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["config"][RD.FIX_FOLD_HEAD_KEY] = "f" * 40
    state["rounds"] = {"1": {"verifyResult": "pass"}}
    state["dispositionLedger"] = [_fixed_ledger_entry("k", "f" * 40, "nope.py", "a" * 64)]
    fault = RD._finalize_fixed_disposition_receipts(state, None, state["config"])
    assert fault == "fixed-disposition-fix-absent-at-certified-head"


def test_bite_F2_verify_not_pass_detector(tmp_path):
    head = "f" * 40
    path = "f.py"
    content = b"ok\n"
    _write_head_blobs(tmp_path, head, path, content)
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head
    state["rounds"] = {"1": {"verifyResult": "fail"}}
    digest = hashlib.sha256(content).hexdigest()
    state["dispositionLedger"] = [_fixed_ledger_entry("k", head, path, digest)]
    fault = RD._finalize_fixed_disposition_receipts(state, str(tmp_path), state["config"])
    assert fault == "fixed-disposition-finalization-verify-not-pass"


def test_bite_F3_staged_id_detector():
    fault = RD._staged_id_resolution_fault([], "v0")
    assert fault == "staged-id-unresolvable: staged id 'v0' maps to no entry"


def test_bite_F4_follow_up_malformed_detector():
    fault = RD._follow_up_shape_fault({"revisitTrigger": "later", "classClosure": "none"})
    assert fault.startswith("follow-up-malformed:")


def test_bite_F6_write_run_not_payload_bound():
    assert RD._execution_evidence_satisfies_payload_proof("evidence") is False
