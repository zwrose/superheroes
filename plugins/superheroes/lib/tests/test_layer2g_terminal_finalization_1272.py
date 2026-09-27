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
_POST_FIX_DIFF = (
    "diff --git a/%s b/%s\nindex 1111111..2222222 100644\n"
    "--- a/%s\n+++ b/%s\n@@ -1,1 +1,1 @@\n-fix still present\n+fix still present\n"
) % (FIX_PATH, FIX_PATH, FIX_PATH, FIX_PATH)


def _fix_batch_entry():
    return {
        SC.FINDING_KEY_FIELD: FINDING_KEY,
        "id": "F-ledger-only",
        "file": FIX_PATH,
        "line": 1,
        "title": "guard issue",
        "severity": "Important",
    }


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
            "runKind": "review",
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


def _assert_no_evidence_postdates_terminal(state):
    current_round = state.get("round")
    for key, rec in (state.get("rounds") or {}).items():
        if not isinstance(rec, dict):
            continue
        if SC.VERIFIED_HEAD_FIELD in rec:
            assert int(key) <= current_round, (key, current_round, rec)


def _seed_for_faithful_terminal_chain(loaded):
    loaded.pop("terminal", None)
    loaded["certification"] = None
    loaded["decisions"] = []
    loaded["step"] = RD.P_PANEL
    loaded["round"] = 1
    loaded["rounds"] = {}
    loaded["findings"] = []
    loaded["auditRounds"] = []
    loaded["_auditOutcome"] = {"notDischarged": [], "discharged": []}
    loaded.pop("_newSurface", None)
    loaded["reviewedDiff"] = _POST_FIX_DIFF
    loaded["_fixBatch"] = [_fix_batch_entry()]
    loaded["_changedSubjects"] = []
    loaded["_changedSubjectsSincePanel"] = []
    loaded["surfacedSinceLastPanel"] = []
    cfg = loaded.get("config") or {}
    cfg.pop(SC.FIX_FOLD_HEAD_KEY, None)
    cfg["diff"] = _POST_FIX_DIFF
    loaded["config"] = cfg


def _drive_faithful_two_round_verify(state, config, session_dir, round_n=1):
    """Round records from real folds: fixFoldHead in round N, verifiedHead in round N+1."""
    state["round"] = round_n
    state.setdefault("rounds", {})
    RD._fold_fixer(state, config, {"fixes": [], "headDiff": _POST_FIX_DIFF},
                    session_dir=session_dir)
    fix_round = str(round_n)
    verify_round = str(round_n + 1)
    fix_rec = state["rounds"].get(fix_round)
    assert isinstance(fix_rec, dict), state["rounds"]
    assert fix_rec.get("fixFoldHead")
    assert SC.VERIFIED_HEAD_FIELD not in fix_rec
    state["round"] = round_n + 1
    RD._fold_verify(state, config, {"result": "pass"},
                    resolution=RD._verified_head_at_fold(session_dir, state))
    verify_rec = state["rounds"].get(verify_round)
    assert isinstance(verify_rec, dict), state["rounds"]
    assert verify_rec.get(SC.VERIFIED_HEAD_FIELD)
    assert verify_rec.get("verifyResult") == "pass"
    assert fix_round != verify_round
    return fix_rec["fixFoldHead"], verify_rec[SC.VERIFIED_HEAD_FIELD]


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
        "rounds": {},
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


def _certifiable_session(tmp_path, state=None, drive_faithful=True, **kwargs):
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
    if drive_faithful:
        with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
            loaded = json.load(fh)
        loaded["config"]["repoRoot"] = repo_root
        _seed_for_faithful_terminal_chain(loaded)
        _drive_faithful_two_round_verify(loaded, loaded["config"], session_dir)
        _assert_no_evidence_postdates_terminal(loaded)
        RD.save_state(session_dir, loaded)
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


def test_terminal_rebind_preserves_disposition_family(tmp_path):
    """BP-2g-i: terminal re-bind carries the row's whole family forward.

    A fixed ledger row that also carries `mergedInto` and another family member must keep
    every member after finalization; losing `mergedInto` turns a refusing unresolved-merge
    chain into a certifiable independent disposition — a fail-direction inversion.
    """
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    row = state["dispositionLedger"][0]
    row[SC.MERGED_INTO_FIELD] = "representative-key"
    row["followUp"] = {
        "item": "revisit",
        "trigger": "next release",
        "closure": "done",
    }
    RD._finalize_certification_inputs(session_dir, state, head_sha=certified_head)
    entry = state["dispositionLedger"][0]
    receipt = entry.get("dispositionReceipt")
    assert isinstance(receipt, dict)
    assert receipt.get("headSha") == certified_head
    assert receipt.get("verifyResult") == "pass"
    assert entry.get(SC.MERGED_INTO_FIELD) == "representative-key"
    assert entry.get("followUp") == {
        "item": "revisit",
        "trigger": "next release",
        "closure": "done",
    }


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

def test_fix_not_at_head_leaves_the_receipt_unrebound_and_unverified(tmp_path):
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
    after_receipt = _ledger_receipt(loaded)
    assert after_receipt.get("headSha") == before_receipt.get("headSha")
    assert after_receipt.get("fixContentDigest") == bad_digest
    assert after_receipt.get("verifyResult") is None


# --- item 5: fault path -------------------------------------------------------------

def test_verify_not_pass_leaves_the_receipt_unrebound_and_unverified(tmp_path):
    _, certified_head = _init_git_repo(tmp_path)
    state = _ledger_only_fixed_state(
        certified_head,
        rounds={"1": {"verifyResult": "fail"}},
    )
    cfg = dict(state.get("config") or {})
    cfg["repoRoot"] = str(tmp_path / "repo")
    cfg["headSha"] = certified_head
    state["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name="verify-not-pass",
        state=state,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": str(tmp_path / "repo")},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    before_head = _ledger_receipt(loaded).get("headSha")
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    receipt = _ledger_receipt(loaded)
    assert receipt.get("headSha") == before_head == OLD_HEAD
    assert receipt.get("verifyResult") is None


def test_unchanged_head_with_failed_binding_leaves_the_receipt_unverified(tmp_path):
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    loaded["dispositionLedger"][0]["dispositionReceipt"] = _ledger_fixed_receipt(
        headSha=certified_head,
        fixContentDigest="0" * 64,
    )
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    receipt = _ledger_receipt(loaded)
    assert receipt.get("headSha") == certified_head
    assert receipt.get("verifyResult") is None


def test_fixed_row_without_receipt_remains_without_receipt_and_certification_refuses(tmp_path):
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    loaded["dispositionLedger"][0].pop("dispositionReceipt", None)
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    assert _ledger_receipt(loaded) is None
    RD.save_state(session_dir, loaded)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert "lacks verification receipt" in refusal.get("detail", "")


def test_run_loop_leg_does_not_synthesize_a_pass_receipt(tmp_path):
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        source_state = json.load(fh)
    source_state.pop("dispositionLedgerOwner", None)
    source_state.pop("dispositionLedger", None)
    source_state["findings"] = [{
        SC.FINDING_KEY_FIELD: FINDING_KEY,
        "id": "F-live-fixed",
        "file": FIX_PATH,
        "line": 1,
        "title": "guard issue",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": 1,
    }]
    materialized = RD._materialize_run_loop_session(
        source_state, 1, source_session_dir=session_dir
    )
    try:
        with open(os.path.join(materialized, RD.STATE_FILE), encoding="utf-8") as fh:
            loop_state = json.load(fh)
        live_row = loop_state["findings"][0]
        receipt = live_row.get("dispositionReceipt")
        assert not (
            isinstance(receipt, dict) and receipt.get("verifyResult") == "pass"
        ), "run-loop materialization must not synthesize a pass receipt"
        loop_receipt, loop_refusal = RC.certify(materialized)
        assert loop_receipt is None, loop_receipt
        assert loop_refusal is not None
        assert loop_refusal["class"] == "disposition-without-receipt"
    finally:
        shutil.rmtree(materialized, ignore_errors=True)


def test_legacy_ledger_tolerates_malformed_sibling_through_backfill_and_terminal(tmp_path):
    """axis: owner-absent legacy ledger skips malformed rows — verify backfill and re-bind proceed."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    state.pop("dispositionLedgerOwner", None)
    state["dispositionLedger"].append("not-a-dict")
    receipt = _ledger_receipt(state)
    if isinstance(receipt, dict):
        receipt["headSha"] = certified_head
    RD._backfill_fixed_disposition_verify_receipts(state, 1)
    receipt = _ledger_receipt(state)
    assert isinstance(receipt, dict)
    assert receipt.get("verifyResult") == "pass"
    RD._finalize_certification_inputs(session_dir, state, head_sha=certified_head)
    receipt = _ledger_receipt(state)
    assert receipt.get("headSha") == certified_head
    assert receipt.get("verifyResult") == "pass"


def test_unrecognized_owner_terminal_gate_leaves_state_byte_identical(tmp_path):
    """axis: unrecognized dispositionLedgerOwner refuses terminal finalization — no ledger rewrite."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    state["dispositionLedgerOwner"] = "ledger-v2"
    before = _state_bytes(state)
    RD._finalize_certification_inputs(session_dir, state, head_sha=certified_head)
    assert _state_bytes(state) == before


# --- verified-head invariant detectors (B1c) ----------------------------------------

def test_verified_post_fix_head_finalizes_and_certifies(tmp_path):
    """axis: a verified post-fix head finalizes and certifies on the faithful two-round sequence."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    fix_round = state["rounds"].get("1") or {}
    verify_round = state["rounds"].get("2") or {}
    assert fix_round.get("fixFoldHead")
    assert verify_round.get(SC.VERIFIED_HEAD_FIELD)
    assert "1" in state["rounds"] and "2" in state["rounds"]
    assert state["terminal"] == "converged"
    decisions = state.get("decisions") or []
    assert decisions
    last = decisions[-1]
    assert last.get("kind") == "converged"
    assert last.get("round") == state["round"]
    _assert_no_evidence_postdates_terminal(state)
    fault = RD._terminal_receipt_gate(session_dir, state)
    assert fault is None, fault
    cert_receipt, cert_refusal = RC.certify(session_dir)
    assert cert_refusal is None, cert_refusal
    head_sha, verify = _cert_receipt_fixed_binding(cert_receipt)
    assert head_sha == certified_head
    assert verify == "pass"


def test_head_verified_at_h_does_not_credit_h_prime(tmp_path):
    """axis: a head verified at H does not credit H' at finalization or certification."""
    repo_root, head1 = _init_git_repo(tmp_path)
    state = _ledger_only_fixed_state(head1)
    cfg = dict(state.get("config") or {})
    cfg["repoRoot"] = repo_root
    cfg["headSha"] = head1
    state["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name="two-head",
        state=state,
        journal_lines=[_dispatch_journal(head1)],
        meta={"headSha": head1, "repoRoot": repo_root},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
        faithful_session=False,
    )
    _write_head_content_blobs(session_dir, head=head1)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    loaded["config"]["repoRoot"] = repo_root
    verified_head, _ = _drive_faithful_two_round_verify(loaded, loaded["config"], session_dir)
    assert verified_head == head1
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "two"],
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
    head2 = proc.stdout.strip()
    _write_head_content_blobs(session_dir, head=head2)
    meta_path = os.path.join(session_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    meta.pop(SC.FIX_FOLD_HEAD_KEY, None)
    meta["headSha"] = head2
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
    loaded["config"].pop(SC.FIX_FOLD_HEAD_KEY, None)
    loaded["config"]["headSha"] = head2
    RD.save_state(session_dir, loaded)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    assert RD._session_certified_head(session_dir, state) == head2
    state["dispositionLedger"][0]["dispositionReceipt"]["headSha"] = head1
    RD._finalize_certification_inputs(session_dir, state, head_sha=head2)
    receipt = _ledger_receipt(state)
    assert receipt.get("headSha") == head1
    assert receipt.get("headSha") != head2
    assert receipt.get("verifyResult") is None
    RD.save_state(session_dir, state)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "verify-not-on-head"


def test_round_record_lacking_verified_head_refuses(tmp_path):
    """axis: verifyResult without verifiedHead is fail-closed — accessor and certification refuse."""
    _, certified_head = _init_git_repo(tmp_path)
    state = _ledger_only_fixed_state(certified_head)
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": certified_head}}
    state["dispositionLedger"][0]["dispositionReceipt"] = _ledger_fixed_receipt(
        headSha=certified_head,
    )
    assert SC.verify_result_for_head(state, certified_head) is None
    cfg = dict(state.get("config") or {})
    cfg["repoRoot"] = str(tmp_path / "repo")
    cfg["headSha"] = certified_head
    state["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name="no-verified-head",
        state=state,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": str(tmp_path / "repo")},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "verify-not-pass"


def test_stale_pass_stamp_at_certified_head_is_revoked(tmp_path):
    """axis: a stale verifyResult stamp is revoked when the accessor returns None."""
    _, certified_head = _init_git_repo(tmp_path)
    state = _ledger_only_fixed_state(certified_head)
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": certified_head}}
    row = state["dispositionLedger"][0]
    row[SC.MERGED_INTO_FIELD] = "representative-key"
    row["outOfScopeReason"] = "carried reason"
    row["dispositionReceipt"] = _ledger_fixed_receipt(
        headSha=certified_head,
        verifyResult="pass",
    )
    state["dispositionLedger"].append({
        SC.FINDING_KEY_FIELD: "representative-key",
        "id": "F-representative",
        "file": FIX_PATH,
        "line": 2,
        "title": "representative",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": 1,
        "dispositionReceipt": _ledger_fixed_receipt(headSha=certified_head),
    })
    cfg = dict(state.get("config") or {})
    cfg["repoRoot"] = str(tmp_path / "repo")
    cfg["headSha"] = certified_head
    state["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name="stale-pass",
        state=state,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": str(tmp_path / "repo")},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
        faithful_session=False,
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    entry = loaded["dispositionLedger"][0]
    receipt = entry.get("dispositionReceipt")
    assert isinstance(receipt, dict)
    assert "verifyResult" not in receipt
    assert receipt.get("headSha") == certified_head
    assert entry.get(SC.MERGED_INTO_FIELD) == "representative-key"
    assert entry.get("outOfScopeReason") == "carried reason"
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "verify-not-pass"


def test_fold_verify_without_session_dir_records_no_verified_head():
    """axis: _fold_verify with no session_dir refuses verifiedHead — accessor stays None."""
    state = RD.new_state({"fixerVendor": "claude"})
    head = "a" * 40
    state["round"] = 1
    state["config"]["headSha"] = head
    RD._fold_verify(state, state["config"], {"result": "pass"},
                    resolution=RD._verified_head_at_fold(None, state))
    rec = state["rounds"].get("1") or {}
    assert SC.VERIFIED_HEAD_FIELD not in rec
    assert rec.get("verifiedHeadRefused")
    assert SC.verify_result_for_head(state, head) is None


@pytest.mark.parametrize(
    "state,head,expected",
    [
        ({"rounds": {}}, None, None),
        ({"rounds": {}}, "", None),
        ({"rounds": {}}, 123, None),
        ({"rounds": {}}, "a" * 40, None),
        (None, "a" * 40, None),
        ({}, "a" * 40, None),
        ({"rounds": None}, "a" * 40, None),
        ({"rounds": {"1": "not-a-dict"}}, "a" * 40, None),
        (
            {
                "rounds": {
                    "1": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "fail"},
                    "2": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"},
                },
            },
            "h" * 40,
            "pass",
        ),
        (
            {"rounds": {"bad": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"}}},
            "h" * 40,
            None,
        ),
        (
            {
                "rounds": {
                    "1": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"},
                    "2": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "fail"},
                },
            },
            "h" * 40,
            "fail",
        ),
        (
            {
                "rounds": {
                    "1": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"},
                    "2": {SC.VERIFIED_HEAD_FIELD: "h" * 40},
                },
            },
            "h" * 40,
            None,
        ),
    ],
    ids=[
        "head-none",
        "head-empty",
        "head-non-str",
        "no-match",
        "state-none",
        "rounds-missing",
        "rounds-non-dict",
        "round-record-non-dict",
        "highest-round-wins",
        "non-integer-round-key-skipped",
        "older-pass-newer-fail",
        "newer-record-without-result",
    ],
)
def test_verify_result_for_head_accessor_axes(state, head, expected):
    """axis: verify_result_for_head is the one fail-closed reader of the verified-head fact."""
    assert SC.verify_result_for_head(state, head) == expected


_ORDERING_FINALIZATION_CASES = [
    pytest.param(
        {
            "1": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"},
            "2": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "fail"},
        },
        id="older-pass-newer-fail",
    ),
    pytest.param(
        {
            "1": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"},
            "2": {SC.VERIFIED_HEAD_FIELD: "h" * 40},
        },
        id="newer-record-without-result",
    ),
]


@pytest.mark.parametrize("rounds_template", _ORDERING_FINALIZATION_CASES)
def test_ordering_axes_carry_through_finalization(tmp_path, rounds_template):
    """axis: ordering axes revoke a stale pass stamp and refuse certification."""
    session_dir, certified_head = _certifiable_session(tmp_path, drive_faithful=False)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    rounds_map = {}
    for key, rec in rounds_template.items():
        entry = dict(rec)
        entry[SC.VERIFIED_HEAD_FIELD] = certified_head
        rounds_map[key] = entry
    loaded["rounds"] = rounds_map
    loaded["dispositionLedger"][0]["dispositionReceipt"] = _ledger_fixed_receipt(
        headSha=certified_head,
        verifyResult="pass",
    )
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    receipt = _ledger_receipt(loaded)
    assert isinstance(receipt, dict)
    assert receipt.get("verifyResult") != "pass"
    RD.save_state(session_dir, loaded)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "verify-not-pass"


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
    by_key, refusal = RC._certification_findings_by_key(loaded)
    assert by_key == {}
    assert refusal is not None
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_MALFORMED_TOKEN
