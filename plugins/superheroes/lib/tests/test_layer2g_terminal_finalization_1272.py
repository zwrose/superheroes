"""#1272 layer 2g: certified-head re-bind at the terminal chokepoint."""
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from round_certification_fixtures import (
    DEFAULT_PANEL_PAYLOAD_SHA,
    write_session,
)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = _load("session_contract")
RC = _load("round_certification")
RD = _load("round_driver")

OLD_HEAD = "b" * 40
FINDING_KEY = "fix@L1"
FIX_PATH = "src/guard.py"
_FIX_BYTES = b"fix still present\n"
_FIX_DIGEST = hashlib.sha256(_FIX_BYTES).hexdigest()


def _state_bytes(state):
    return json.dumps(state, sort_keys=True)


def _binding_fields(nonce="test-nonce"):
    return {
        "source": "runner",
        "runnerNonce": nonce,
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
    }


def _dispatch_journal(certified_head):
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": RC.PANEL_PHASE,
        "round": 1,
        "attempt": 0,
        "seat": "code-reviewer",
        "occurrence": 0,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
        "headSha": certified_head,
        "executionEvidence": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
            "toolCalls": 1,
            **_binding_fields(),
        },
        "recordIdentity": {
            "phase": RC.PANEL_PHASE,
            "seat": "code-reviewer",
            "occurrence": 0,
            "attempt": 0,
        },
    }


def _init_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    rel = FIX_PATH
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_FIX_BYTES)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return str(repo), proc.stdout.strip()


def _head_content_row(path=FIX_PATH, head=None):
    return {
        "headSha": head,
        "path": path,
        "contentDigest": _FIX_DIGEST,
        "bytes": len(_FIX_BYTES),
        "readAt": "2026-01-01T00:00:00Z",
        "source": "git-show",
        "readError": None,
    }


def _head_content_blobs(head):
    return {
        "schema": SC.HEAD_CONTENT_BLOBS_SCHEMA,
        "headSha": head,
        "files": {FIX_PATH: base64.b64encode(_FIX_BYTES).decode("ascii")},
        "reads": [_head_content_row(head=head)],
    }


def _write_head_content_blobs(session_dir, head):
    path = os.path.join(session_dir, SC.HEAD_CONTENT_BLOBS_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_head_content_blobs(head), fh, sort_keys=True)


def _ledger_fixed_receipt(**over):
    base = {
        "headSha": OLD_HEAD,
        "fixContentDigest": _FIX_DIGEST,
    }
    base.update(over)
    return base


def _ledger_only_fixed_state(certified_head, **over):
    base = {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger",
        "dispositionLedger": [
            {
                SC.FINDING_KEY_FIELD: FINDING_KEY,
                "id": "F-ledger-only",
                "file": FIX_PATH,
                "line": 1,
                "title": "guard issue",
                "severity": "Important",
                "disposition": "fixed",
                "dispositionRound": 1,
                "dispositionReceipt": _ledger_fixed_receipt(),
            },
        ],
        "findings": [],
        "_records": [],
        "round": 1,
        "rounds": {"1": {"verifyResult": "pass"}},
        "config": {
            "fixerVendor": "claude",
            "baseGuard": RC.BASE_GUARD_CHECKED,
            "headSha": certified_head,
        },
        "step": "terminal",
        "terminal": "converged",
        "certification": {
            "shape": "full-panel-confirmed",
            "fullPanel": True,
            "independence": "independent",
            "base": "fetched",
            "shapeDrivers": [],
        },
        "decisions": [{"round": 1, "kind": "converged", "detail": "certified"}],
    }
    base.update(over)
    return base


def _certifiable_session(tmp_path, state=None, **kwargs):
    repo_root, certified_head = _init_git_repo(tmp_path)
    state_obj = state or _ledger_only_fixed_state(certified_head)
    cfg = dict(state_obj.get("config") or {})
    cfg["repoRoot"] = repo_root
    cfg["headSha"] = certified_head
    state_obj["config"] = cfg
    session_dir = write_session(
        tmp_path,
        state=state_obj,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": repo_root},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
        **kwargs,
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    return session_dir, certified_head


def _ledger_receipt(state, key=FINDING_KEY):
    for row in state.get("dispositionLedger") or []:
        if isinstance(row, dict) and row.get(SC.FINDING_KEY_FIELD) == key:
            return row.get("dispositionReceipt")
    return None


def _cert_receipt_fixed_binding(receipt, key=FINDING_KEY):
    for finding in receipt.get("findings") or []:
        if finding.get(SC.FINDING_KEY_FIELD) == key:
            proof = finding.get("dispositionReceipt")
            assert isinstance(proof, dict), finding
            return proof.get("headSha"), proof.get("verifyResult")
    raise AssertionError("fixed finding %r missing from certify receipt" % key)


# --- item 1: ledger-only re-bind ----------------------------------------------------

def test_ledger_only_fixed_row_rebinds_to_certified_head(tmp_path):
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    RD._finalize_certification_inputs(session_dir, state, head_sha=certified_head)
    receipt = _ledger_receipt(state)
    assert isinstance(receipt, dict)
    assert receipt.get("headSha") == certified_head
    assert receipt.get("verifyResult") == "pass"


# --- item 2: persistence-order detector (BP-2g-f) -----------------------------------

def test_terminal_gate_rebind_visible_to_certify_receipt(tmp_path):
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    fault = RD._terminal_receipt_gate(session_dir, state)
    assert fault is None, fault
    cert_path = os.path.join(session_dir, RD.CERTIFICATION_RECEIPT_FILE)
    assert os.path.isfile(cert_path), "certify during gate must write certification-receipt.json"
    with open(cert_path, encoding="utf-8") as fh:
        cert_receipt = json.load(fh)
    head_sha, verify = _cert_receipt_fixed_binding(cert_receipt)
    assert head_sha == certified_head
    assert verify == "pass"


# --- item 3: both terminal legs -----------------------------------------------------

def test_cli_and_run_loop_legs_share_certified_head_binding(tmp_path):
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    fault = RD._terminal_receipt_gate(session_dir, state)
    assert fault is None, fault
    cli_receipt, cli_refusal = RC.certify(session_dir)
    assert cli_refusal is None, cli_refusal
    cli_head, cli_verify = _cert_receipt_fixed_binding(cli_receipt)

    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        source_state = json.load(fh)
    materialized = RD._materialize_run_loop_session(
        source_state, 1, source_session_dir=session_dir
    )
    try:
        loop_receipt, loop_refusal = RC.certify(materialized)
        assert loop_refusal is None, loop_refusal
        loop_head, loop_verify = _cert_receipt_fixed_binding(loop_receipt)
        assert loop_head == cli_head == certified_head
        assert loop_verify == cli_verify == "pass"
    finally:
        shutil.rmtree(materialized, ignore_errors=True)


# --- item 4: residual path (BP-2g-h) ------------------------------------------------

def test_fix_not_at_head_records_residual_without_rebind(tmp_path):
    bad_digest = "0" * 64
    _, certified_head = _init_git_repo(tmp_path)
    state = _ledger_only_fixed_state(certified_head)
    state["dispositionLedger"][0]["dispositionReceipt"] = _ledger_fixed_receipt(
        fixContentDigest=bad_digest,
    )
    cfg = dict(state.get("config") or {})
    cfg["repoRoot"] = str(tmp_path / "repo")
    cfg["headSha"] = certified_head
    state["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name="residual",
        state=state,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": str(tmp_path / "repo")},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    before_receipt = dict(_ledger_receipt(loaded))
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    residuals = loaded.get("_fixedDispositionFinalizationResiduals") or {}
    assert FINDING_KEY in residuals
    assert residuals[FINDING_KEY] == "fix-content-reverted"
    after_receipt = _ledger_receipt(loaded)
    assert after_receipt.get("headSha") == before_receipt.get("headSha")


# --- item 5: fault path -------------------------------------------------------------

def test_malformed_ledger_fault_leaves_state_unchanged(tmp_path):
    _, certified_head = _init_git_repo(tmp_path)
    state = _ledger_only_fixed_state(certified_head, dispositionLedger=None)
    cfg = dict(state.get("config") or {})
    cfg["repoRoot"] = str(tmp_path / "repo")
    cfg["headSha"] = certified_head
    state["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name="fault",
        state=state,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": str(tmp_path / "repo")},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    before = _state_bytes(loaded)
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    assert _state_bytes(loaded) == before
    assert "_fixedDispositionFinalizationResiduals" not in loaded
    by_key, refusal = RC._certification_findings_by_key(loaded)
    assert by_key == {}
    assert refusal is not None
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_MALFORMED_TOKEN
