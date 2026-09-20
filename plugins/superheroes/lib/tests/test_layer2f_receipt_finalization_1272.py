"""#1272 layer 2f WO-C — fixed disposition receipt finalization at the certified head."""
import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver",
    os.path.join(_HERE, "test_round_driver.py"),
)
_TDR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDR)

_FIX = importlib.util.spec_from_file_location(
    "round_certification_fixtures",
    os.path.join(_HERE, "round_certification_fixtures.py"),
)
_RCF = importlib.util.module_from_spec(_FIX)
_FIX.loader.exec_module(_RCF)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")
RC = _load("round_certification")
RR = _load("round_records")

_cfg = _TDR._cfg
_cfg_cert = _TDR._cfg_cert
_drive_cli = _TDR._drive_cli
_responder = _TDR._responder
HEAD_NEW_SURFACE = _TDR.HEAD_NEW_SURFACE

_FIX_BYTES = b"fix present\n"
_FIX_DIGEST = hashlib.sha256(_FIX_BYTES).hexdigest()


def _ledger_by_key(state):
    return {
        SC.finding_identity_key(e): e
        for e in (state.get("dispositionLedger") or [])
        if isinstance(e, dict)
    }


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _head_content_row(path, head):
    return {
        "headSha": head,
        "path": path,
        "contentDigest": _FIX_DIGEST,
        "bytes": len(_FIX_BYTES),
        "readAt": "2026-01-01T00:00:00Z",
        "source": "git-show",
        "readError": None,
    }


def _write_blobs(session_dir, head, path="f.py"):
    blobs = {
        "schema": SC.HEAD_CONTENT_BLOBS_SCHEMA,
        "headSha": head,
        "files": {path: base64.b64encode(_FIX_BYTES).decode("ascii")},
        "reads": [_head_content_row(path, head)],
    }
    out = os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(blobs, fh)


def _audit_discharge_fixed(state, head_sha):
    discharged_f = {"title": "fixed bug", "severity": "Important", "file": "f.py", "line": 1}
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head_sha
    state["fixBatch"] = [discharged_f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    discharged_id = RD._finding_key_of(discharged_f)
    RD._set_findings(state, [discharged_f])
    state["_newSurface"] = True
    auditor = state["_auditTargets"][0]["auditorVendor"]
    manifest = {discharged_id: auditor}
    RD._fold_audits(
        state,
        state["config"],
        {
            "results": [{"id": discharged_id, "ruling": "discharged", "reason": "gone"}],
            "collectionManifest": manifest,
        },
    )
    entry = _ledger_by_key(state)[discharged_id]
    return discharged_id, entry


def _init_repo(tmp_path, rel="f.py", content=_FIX_BYTES):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True)
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, capture_output=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return repo, head


def _session_dir(tmp_path, repo, head):
    session_dir = str(tmp_path / "sess")
    os.makedirs(session_dir, exist_ok=True)
    meta = {
        "sessionId": "l2f-finalize",
        "headSha": head,
        RD.FIX_FOLD_HEAD_KEY: head,
        "repoRoot": str(repo),
        "baseGuard": RC.BASE_GUARD_CHECKED,
    }
    with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
        fh.write("\n")
    return session_dir


def _certifiable_shell(tmp_path, state, head, repo=None):
    meta = {"headSha": head, RD.FIX_FOLD_HEAD_KEY: head, "baseGuard": RC.BASE_GUARD_CHECKED}
    if repo is not None:
        meta["repoRoot"] = str(repo)
    evidence = {
        "source": "runner",
        "runnerNonce": "finalize-nonce",
        "recordDigest": "a" * 64,
        "resultDigest": _RCF.DEFAULT_FINDINGS_RESULT_SHA,
        "resultKind": "findings",
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    journal = [{
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": RC.PANEL_PHASE,
        "round": 1,
        "attempt": 0,
        "seat": "code-reviewer",
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": _RCF.DEFAULT_PANEL_PAYLOAD_SHA,
        "executionEvidence": {
            field: evidence[field] for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        },
        "recordIdentity": {
            "phase": RC.PANEL_PHASE,
            "seat": "code-reviewer",
            "occurrence": 0,
            "attempt": 0,
        },
    }]
    envelopes = [{
        "seat": "code-reviewer",
        "payloadSha256": _RCF.DEFAULT_PANEL_PAYLOAD_SHA,
        "executionEvidence": evidence,
        "payload": _RCF.DEFAULT_PANEL_PAYLOAD,
    }]
    session_dir = _RCF.write_session(
        tmp_path,
        name="sess",
        state=state,
        meta=meta,
        journal_lines=journal,
        envelopes=envelopes,
        faithful_session=True,
    )
    return session_dir


def _driver_binding_failure(session_dir, finding, receipt, certified_head, by_key=None):
    return RD._fix_still_present_at_head(
        session_dir, finding, receipt, certified_head, by_key=by_key,
    )


def _cert_binding_failure(ctx, finding, receipt, by_key=None):
    refusal = RC._fix_still_present_at_head(ctx, finding, receipt, by_key=by_key)
    if refusal is None:
        return None
    return refusal.get("bindingFailure")


_DRIFT_FIXTURES = [
    ("fix-content-missing", lambda sd, head: None),
    ("fix-content-unreadable", lambda sd, head: "{not json"),
    (
        "fix-content-schema-unsupported",
        lambda sd, head: {
            "headSha": head,
            "files": {"f.py": base64.b64encode(_FIX_BYTES).decode("ascii")},
            "fixCommits": [{"headSha": head, "path": "f.py", "present": True}],
        },
    ),
    (
        "fix-content-reverted",
        lambda sd, head: {
            "schema": SC.HEAD_CONTENT_BLOBS_SCHEMA,
            "headSha": head,
            "files": {"f.py": base64.b64encode(_FIX_BYTES).decode("ascii")},
            "reads": [_head_content_row("f.py", head)],
        },
    ),
]


def _drift_finding_and_receipt(head, binding):
    finding = {
        "id": "F-drift",
        "file": "f.py",
        "line": 1,
        "severity": "Important",
        "disposition": "fixed",
    }
    receipt = {"headSha": head, "verifyResult": "pass"}
    if binding == "fix-content-reverted":
        receipt["fixContentDigest"] = "0" * 64
    elif binding != "fix-content-missing":
        receipt["fixContentDigest"] = _FIX_DIGEST
    return finding, receipt


# --- end-to-end re-bind through disk -------------------------------------------------

def _blobs_for_bytes(head, path, raw):
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "schema": SC.HEAD_CONTENT_BLOBS_SCHEMA,
        "headSha": head,
        "files": {path: base64.b64encode(raw).decode("ascii")},
        "reads": [{
            "headSha": head,
            "path": path,
            "contentDigest": digest,
            "bytes": len(raw),
            "readAt": "2026-01-01T00:00:00Z",
            "source": "git-show",
            "readError": None,
        }],
    }, digest


def test_fixed_receipt_rebound_certifies_from_disk(tmp_path):
    """Fix in round 1, terminal at a later head — reload from disk and certify."""
    repo, head1 = _init_repo(tmp_path)
    head2_bytes = b"fixed at head2\n"
    path = repo / "f.py"
    path.write_bytes(head2_bytes)
    subprocess.run(["git", "add", "f.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "fix2"], cwd=repo, check=True, capture_output=True)
    head2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    head2_blobs, head2_digest = _blobs_for_bytes(head2, "f.py", head2_bytes)

    state = RD.new_state(_cfg())
    state["config"]["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["config"]["repoRoot"] = str(repo)
    state["config"]["headSha"] = head2
    state["round"] = 1
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": head1}}
    key, entry = _audit_discharge_fixed(state, head1)
    assert entry["dispositionReceipt"]["headSha"] == head1

    state["round"] = 2
    state["rounds"]["2"] = {"verifyResult": "pass", "fixFoldHead": head2}
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [entry]
    state["decisions"] = [{"round": 2, "kind": "converged", "detail": "certified"}]

    session_dir = _certifiable_shell(tmp_path, state, head2, repo=repo)
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault

    ok, reloaded = RD.load_state(session_dir)
    assert ok and reloaded is not None
    rebound = _ledger_by_key(reloaded)[key]["dispositionReceipt"]
    assert rebound["headSha"] == head2
    assert rebound["verifyResult"] == "pass"
    assert rebound.get("fixContentDigest") == head2_digest

    with open(os.path.join(session_dir, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        round_receipt = json.load(fh)
    ok, reason = RD.validate_receipt(round_receipt)
    assert ok, reason

    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is None, refusal
    cert_receipt, cert_refusal = RC.certify(session_dir)
    if cert_refusal is not None:
        assert cert_refusal.get("bindingFailure") not in (
            "verify-not-on-head",
            "verify-not-pass",
        ), cert_refusal
    else:
        assert cert_receipt is not None


# --- confirmation path without final-round verify ------------------------------------

def test_confirmation_path_still_certifies(tmp_path):
    """Fix round, delta round, clean confirmation panel — no verify in the final round."""
    repo, head = _init_repo(tmp_path)
    state = RD.new_state(_cfg())
    state["config"]["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["config"]["repoRoot"] = str(repo)
    state["config"]["headSha"] = head
    state["dispositionLedgerOwner"] = "ledger"
    state["fullPanelRan"] = True

    state["round"] = 1
    state["rounds"] = {
        "1": {"verifyResult": "pass", "fixFoldHead": head, "roundKind": "fix"},
    }
    key, entry = _audit_discharge_fixed(state, head)

    state["round"] = 2
    state["rounds"]["2"] = {"verifyResult": "pass", "fixFoldHead": head, "roundKind": "delta"}

    state["round"] = 3
    state["rounds"]["3"] = {"roundKind": "confirmation"}
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "full-panel-confirmed",
        "fullPanel": True,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["findings"] = [_ledger_by_key(state)[key]]
    state["decisions"] = [{"round": 3, "kind": "converged", "detail": "certified"}]

    session_dir = _certifiable_shell(tmp_path, state, head, repo=repo)
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    assert live["rounds"]["3"].get("verifyResult") is None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault
    certified_head = RD._session_certified_head(session_dir, live)
    rebound = _ledger_by_key(RD.load_state(session_dir)[1])[key]["dispositionReceipt"]
    assert rebound["headSha"] == certified_head
    assert rebound["verifyResult"] == "pass"
    ctx, err = RC._load_context(session_dir)
    assert err is None
    disposition_refusal = RC.check_disposition_without_receipt(ctx)
    assert disposition_refusal is None, disposition_refusal
    ok, parked = RD.load_state(session_dir)
    assert ok
    assert RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE not in str(
        parked.get("_receiptFault") or ""
    )


# --- unprovable re-bind leaves receipt untouched -------------------------------------

def test_unprovable_rebind_leaves_receipt_untouched_and_does_not_park(tmp_path):
    """Re-validation cause: terminal completes, receipt unchanged, residual records why."""
    head = "e" * 40
    state = RD.new_state(_cfg())
    state["config"]["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["round"] = 1
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": head}}
    key, entry = _audit_discharge_fixed(state, head)
    stale_head = "d" * 40
    stale_receipt = {"headSha": stale_head}
    RD._record_disposition(
        state, key, "fixed", entry["dispositionRound"], dispositionReceipt=stale_receipt,
    )
    receipt_before = dict(_ledger_by_key(state)[key]["dispositionReceipt"])
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [_ledger_by_key(state)[key]]
    state["config"]["headSha"] = head
    state["decisions"] = [{"round": 1, "kind": "converged", "detail": "certified"}]
    session_dir = _certifiable_shell(tmp_path, state, head)
    blobs_path = os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE)
    with open(blobs_path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault
    ok, reloaded = RD.load_state(session_dir)
    assert ok
    receipt_after = _ledger_by_key(reloaded)[key]["dispositionReceipt"]
    assert receipt_after == receipt_before
    residuals = reloaded.get("_fixedDispositionFinalizationResiduals") or {}
    assert residuals.get(key) == "fix-content-unreadable"
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal.get("bindingFailure") == "verify-not-on-head"


# --- verify-not-pass leaves receipt untouched ----------------------------------------

def test_verify_not_pass_leaves_receipt_untouched_and_does_not_park(tmp_path):
    """Non-pass verify lookup: terminal completes, receipt unchanged, residual records why."""
    repo, head1 = _init_repo(tmp_path)
    path = repo / "f.py"
    path.write_bytes(b"second head\n")
    subprocess.run(["git", "add", "f.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "two"], cwd=repo, check=True, capture_output=True)
    head2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()

    state = RD.new_state(_cfg())
    state["config"]["repoRoot"] = str(repo)
    state["config"]["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["round"] = 2
    state["rounds"] = {
        "1": {"verifyResult": "pass", "fixFoldHead": head1},
        "2": {},
    }
    key, entry = _audit_discharge_fixed(state, head2)
    receipt_before = dict(_ledger_by_key(state)[key]["dispositionReceipt"])
    receipt_before["fixContentDigest"] = _FIX_DIGEST
    RD._record_disposition(
        state, key, "fixed", entry["dispositionRound"],
        dispositionReceipt=receipt_before,
    )
    receipt_before = dict(_ledger_by_key(state)[key]["dispositionReceipt"])
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [entry]
    state["config"]["headSha"] = head2
    state["decisions"] = [{"round": 2, "kind": "converged", "detail": "certified"}]
    session_dir = _certifiable_shell(tmp_path, state, head2, repo=repo)
    _write_blobs(session_dir, head2)
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault
    ok, reloaded = RD.load_state(session_dir)
    assert ok
    receipt_after = _ledger_by_key(reloaded)[key]["dispositionReceipt"]
    assert receipt_after == receipt_before
    residuals = reloaded.get("_fixedDispositionFinalizationResiduals") or {}
    assert residuals.get(key) == RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal.get("bindingFailure") == "verify-not-pass"


# --- four driver-side cause classes --------------------------------------------------

@pytest.mark.parametrize(
    "binding",
    ["fix-content-missing", "fix-content-unreadable", "fix-content-schema-unsupported",
     "fix-content-reverted"],
)
def test_driver_fix_content_binding_classes(tmp_path, binding):
    head = "c" * 40
    finding, receipt = _drift_finding_and_receipt(head, binding)
    session_dir = str(tmp_path / binding)
    os.makedirs(session_dir, exist_ok=True)
    blob_writer = next(writer for name, writer in _DRIFT_FIXTURES if name == binding)
    payload = blob_writer(session_dir, head)
    if payload is not None:
        if isinstance(payload, str):
            with open(os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
                fh.write(payload)
        else:
            with open(os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
    assert _driver_binding_failure(session_dir, finding, receipt, head) == binding


# --- drift detector ------------------------------------------------------------------

@pytest.mark.parametrize("binding,_writer", _DRIFT_FIXTURES)
def test_fix_content_classifier_drift_detector(tmp_path, binding, _writer):
    head = "d" * 40
    finding, receipt = _drift_finding_and_receipt(head, binding)
    session_dir = str(tmp_path / ("drift-" + binding))
    os.makedirs(session_dir, exist_ok=True)
    payload = _writer(session_dir, head)
    if payload is not None:
        if isinstance(payload, str):
            with open(os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
                fh.write(payload)
        else:
            with open(os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
    state = {"findings": [finding], "config": {"headSha": head, "baseGuard": RC.BASE_GUARD_CHECKED}}
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
        json.dump({"sessionId": "s", "headSha": head, "baseGuard": RC.BASE_GUARD_CHECKED}, fh)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    assert _driver_binding_failure(session_dir, finding, receipt, head) == binding
    assert _cert_binding_failure(ctx, finding, receipt) == binding


# --- partial backfill retired --------------------------------------------------------

def test_backfill_helper_absent_same_round_audits_before_verify_still_stamps(tmp_path):
    assert not hasattr(RD, "_backfill_fixed_disposition_verify_receipts")
    repo, head = _init_repo(tmp_path)
    state = RD.new_state(_cfg())
    state["config"]["repoRoot"] = str(repo)
    state["round"] = 2
    state["rounds"] = {"2": {}}
    key, entry = _audit_discharge_fixed(state, head)
    assert entry["dispositionReceipt"].get("verifyResult") is None
    RD._fold_verify(state, state["config"], {"result": "pass"})
    state["rounds"]["2"]["fixFoldHead"] = head
    assert state["rounds"]["2"]["verifyResult"] == "pass"
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [_ledger_by_key(state)[key]]
    state["config"]["headSha"] = head
    state["decisions"] = [{"round": 3, "kind": "converged", "detail": "certified"}]
    session_dir = _certifiable_shell(tmp_path, state, head, repo=repo)
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault
    ok, reloaded = RD.load_state(session_dir)
    assert ok
    receipt = _ledger_by_key(reloaded)[key]["dispositionReceipt"]
    assert receipt.get("verifyResult") == "pass"
    assert receipt.get("headSha") == head


# --- head unchanged stamps verify from covering gate ---------------------------------

def test_head_unchanged_stamps_verify_result_when_blobs_unreadable(tmp_path):
    """Head already bound to certified head — stamp verifyResult without re-bind."""
    head = "f" * 40
    state = RD.new_state(_cfg())
    state["config"]["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["round"] = 2
    state["rounds"] = {
        "1": {"verifyResult": "pass", "fixFoldHead": head},
        "2": {"verifyResult": "pass", "fixFoldHead": head, "roundKind": "delta"},
    }
    key, entry = _audit_discharge_fixed(state, head)
    bare_receipt = {"headSha": head}
    RD._record_disposition(
        state, key, "fixed", entry["dispositionRound"], dispositionReceipt=bare_receipt,
    )
    receipt_before = dict(_ledger_by_key(state)[key]["dispositionReceipt"])
    assert receipt_before.get("headSha") == head
    assert receipt_before.get("verifyResult") is None
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [_ledger_by_key(state)[key]]
    state["config"]["headSha"] = head
    state["decisions"] = [{"round": 2, "kind": "converged", "detail": "certified"}]
    session_dir = _certifiable_shell(tmp_path, state, head)
    blobs_path = os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE)
    if os.path.isfile(blobs_path):
        os.remove(blobs_path)
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault
    ok, reloaded = RD.load_state(session_dir)
    assert ok
    receipt_after = _ledger_by_key(reloaded)[key]["dispositionReceipt"]
    assert receipt_after.get("headSha") == head
    assert receipt_after.get("verifyResult") == "pass"
    assert reloaded.get("_fixedDispositionFinalizationResiduals") is None


# --- persistence order ---------------------------------------------------------------

def test_persistence_order_rebound_on_disk(tmp_path):
    repo, head1 = _init_repo(tmp_path)
    path = repo / "f.py"
    path.write_bytes(b"later head\n")
    subprocess.run(["git", "add", "f.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "later"], cwd=repo, check=True, capture_output=True)
    head2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()

    state = RD.new_state(_cfg())
    state["config"]["repoRoot"] = str(repo)
    state["round"] = 2
    state["rounds"] = {
        "1": {"verifyResult": "pass", "fixFoldHead": head1},
        "2": {"verifyResult": "pass", "fixFoldHead": head2},
    }
    key, entry = _audit_discharge_fixed(state, head1)
    state["terminal"] = "converged"
    state["step"] = RD.P_TERMINAL
    state["certification"] = {
        "shape": "audited-chain",
        "fullPanel": False,
        "independence": "independent",
        "base": "fetched",
        "shapeDrivers": [],
    }
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [entry]
    state["config"]["headSha"] = head2
    state["decisions"] = [{"round": 2, "kind": "converged", "detail": "certified"}]
    session_dir = _certifiable_shell(tmp_path, state, head2, repo=repo)
    ok, live = RD.load_state(session_dir)
    assert ok and live is not None
    fault = RD._terminal_receipt_gate(session_dir, live)
    assert fault is None, fault

    ok, loop_state = RD.load_state(session_dir)
    assert ok
    loop_receipt = _ledger_by_key(loop_state)[key]["dispositionReceipt"]
    assert loop_receipt["headSha"] == head2

    live_row = next(
        f for f in (loop_state.get("findings") or [])
        if isinstance(f, dict) and SC.finding_identity_key(f) == key
    )
    assert live_row["dispositionReceipt"]["headSha"] == head2

    with open(os.path.join(session_dir, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        round_receipt = json.load(fh)
    ok, reason = RD.validate_receipt(round_receipt)
    assert ok, reason
    assert round_receipt["verdict"] == "converged"
