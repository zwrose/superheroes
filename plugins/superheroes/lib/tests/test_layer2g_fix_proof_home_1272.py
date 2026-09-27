"""#1272 layer 2g: fix-proof decision home in session_contract."""
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

HEAD = "a" * 40


def _fix_receipt(**over):
    base = {"headSha": HEAD, "verifyResult": "pass", "fixContentDigest": "d" * 64}
    base.update(over)
    return base


def _finding(**over):
    base = {
        "id": "F-1",
        "file": "src/guard.py",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionReceipt": _fix_receipt(),
    }
    base.update(over)
    return base


def _binding_from_session(session_dir, finding, receipt=None):
    ctx, _ = RC._load_context(session_dir)
    receipt = receipt or finding.get("dispositionReceipt")
    head = receipt.get("headSha") or RC._certified_head_sha(ctx)
    read_outcome = RC._read_head_content_blobs(session_dir)
    return SC.fix_still_present_at_head(finding, receipt, head, read_outcome)


# --- read-outcome distinction (BP-2g-d axis) ----------------------------------------

def test_absent_head_content_blobs_refuses_fix_content_missing(tmp_path):
    session_dir = str(tmp_path)
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, RC.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"findings": [_finding()]}, fh)
    binding = _binding_from_session(session_dir, _finding())
    assert binding is not None
    token, _detail = binding
    assert token == "fix-content-missing"


def test_unreadable_head_content_blobs_refuses_fix_content_unreadable(tmp_path):
    session_dir = str(tmp_path)
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, RC.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"findings": [_finding()]}, fh)
    with open(os.path.join(session_dir, SC.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    binding = _binding_from_session(session_dir, _finding())
    assert binding is not None
    token, _detail = binding
    assert token == "fix-content-unreadable"


# --- merged-chain proof path (BP-2g-e axis) -------------------------------------------

def _ledger_owned_fixed_merged_state():
    rep_key = "rep@L1"
    mem_key = "mem@L1"
    return {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger",
        "dispositionLedger": [
            {
                SC.FINDING_KEY_FIELD: rep_key,
                "file": "rep.py",
                "line": 1,
                "title": "root",
                "severity": "Critical",
                "disposition": "fixed",
                "dispositionRound": 1,
                "dispositionReceipt": _fix_receipt(),
            },
            {
                SC.FINDING_KEY_FIELD: mem_key,
                "file": "mem.py",
                "line": 1,
                "title": "root",
                "severity": "Important",
                "disposition": "fixed",
                "dispositionRound": 1,
                SC.MERGED_INTO_FIELD: rep_key,
                "dispositionReceipt": _fix_receipt(),
            },
        ],
        "findings": [],
        "_records": [],
    }


def test_merged_away_member_fixed_row_contributes_representative_path():
    state = _ledger_owned_fixed_merged_state()
    paths = RD._fixed_ledger_content_paths(state)
    assert "rep.py" in paths
    assert "mem.py" not in paths


def test_fix_proof_path_resolves_merged_chain():
    state = _ledger_owned_fixed_merged_state()
    rows, by_key, fault = RD._fixed_ledger_rows(state)
    assert fault is None
    mem_entry = by_key["mem@L1"]
    assert SC.fix_proof_path(mem_entry, by_key) == "rep.py"
