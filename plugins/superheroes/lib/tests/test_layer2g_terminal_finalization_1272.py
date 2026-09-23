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

import round_adapters  # noqa: E402

_TDI_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration", os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_TDI_SPEC)
_TDI_SPEC.loader.exec_module(_TDI)

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


_REVIEWED_DIFF = ("diff --git a/%s b/%s\n" % (FIX_PATH, FIX_PATH)
                  + "index 1111111..2222222 100644\n"
                  + "--- a/%s\n" % FIX_PATH
                  + "+++ b/%s\n" % FIX_PATH
                  + "@@ -0,0 +1 @@\n"
                  + "+broken guard\n")
_HEAD_DIFF = _REVIEWED_DIFF.replace("+broken guard", "+fix still present")
_FIX_LEG = [RD.P_FIXER, RD.P_AUDITS, RD.P_VERIFY]


def _seed_fix_leg(session_dir):
    """The fixture's ONE seeded position: round 1 with its fix leg pending over the fixed ledger
    row's finding. Nothing terminal is seeded — the loop reaches its own terminal from here."""
    ok, state = RD.load_state(session_dir)
    assert ok, state
    for key in ("terminal", "certification", "pending"):
        state.pop(key, None)
    for key, value in RD.new_state(dict(state["config"])).items():
        state.setdefault(key, value)
    state.update(round=1, step=RD.P_FIXER, decisions=[], reviewedDiff=_REVIEWED_DIFF)
    state["_fixBatch"] = [{"file": FIX_PATH, "line": 1, "id": "F-ledger-only",
                           SC.FINDING_KEY_FIELD: FINDING_KEY, "title": "guard issue",
                           "severity": "Important"}]
    RD.save_state(session_dir, state)


def _fix_leg_payload(state, phase, seat):
    if phase == RD.P_FIXER:
        return {"fixes": [{"file": FIX_PATH, "summary": "guard restored"}], "escalated": False,
                "headDiff": _HEAD_DIFF}
    if phase == RD.P_AUDITS:
        return {"id": seat, "ruling": "discharged",
                "auditorVendor": _TDI._auditor_vendor_for(state)(seat),
                "reason": "re-read the fixed hunk; the cited defect is gone"}
    if phase == RD.P_VERIFY:
        return {"result": "pass"}
    raise AssertionError("the fix leg does not reach phase %r" % phase)


def _drive_fix_leg_to_terminal(session_dir, gitdir, max_steps=8):
    """Land, record and `advance` each pending step until the loop reaches its own terminal.
    `advance` folds through `cmd_submit`, so every fold runs the real submit chokepoint."""
    folded = []
    for _ in range(max_steps):
        ok, state = RD.load_state(session_dir)
        assert ok, state
        if state.get("terminal"):
            return folded
        nxt = RD.cmd_next(session_dir)
        assert nxt["ok"], nxt
        ok, state = RD.load_state(session_dir)
        pend = state["pending"]
        roster, reason = round_adapters.roster_for(pend["phase"], state, state["config"])
        assert reason is None, (pend["phase"], reason)
        slots = _TDI._slots_of(roster)
        _TDI._write_dispatch_manifest(session_dir, pend, slots, _TDI._auditor_vendor_for(state))
        for seat, occurrence in slots:
            _TDI._land(session_dir, state, pend, seat,
                       _fix_leg_payload(state, pend["phase"], seat),
                       occurrence=occurrence, evidence_read="engaged")
            out = _TDI._record(session_dir, seat, occurrence=occurrence)
            assert out["ok"], (pend["phase"], seat, out)
        out = RD.cmd_advance(session_dir, git=_TDI._fake_git(gitdir))
        assert out["ok"], (pend["phase"], out)
        assert out["folded"]["phase"] == pend["phase"], out
        folded.append(pend["phase"])
    raise AssertionError("the fix leg did not reach a terminal in %d steps: %s"
                         % (max_steps, folded))


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


def _certifiable_session(tmp_path, name="session", **kwargs):
    """A session that reached its terminal THROUGH THE REAL LOOP: seeded at round 1's fix leg,
    then fixer → audits → verify folded by `advance` → `cmd_submit` to the converged terminal,
    whose terminal gate finalized and certified. No terminal field is ever restored by hand."""
    repo_root, certified_head = _init_git_repo(tmp_path)
    state_obj = _ledger_only_fixed_state(certified_head)
    cfg = dict(state_obj.get("config") or {})
    cfg["repoRoot"] = repo_root
    cfg["headSha"] = certified_head
    cfg["diff"] = _REVIEWED_DIFF
    state_obj["config"] = cfg
    session_dir = write_session(
        tmp_path,
        name=name,
        state=state_obj,
        journal_lines=[_dispatch_journal(certified_head)],
        meta={"headSha": certified_head, "repoRoot": repo_root},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
        **kwargs,
    )
    _write_head_content_blobs(session_dir, head=certified_head)
    _seed_fix_leg(session_dir)
    folded = _drive_fix_leg_to_terminal(session_dir, str(tmp_path / (name + "-gitdir")))
    assert folded == _FIX_LEG, folded
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

def test_fix_not_at_head_leaves_receipt_unbound(tmp_path):
    """R28 re-pin: the retired residuals field is no longer the observable — the untouched receipt
    is, and it is what certification reads."""
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
    assert after_receipt == before_receipt
    assert after_receipt.get("headSha") == OLD_HEAD
    assert "verifyResult" not in after_receipt


# --- item 5: fault path -------------------------------------------------------------

def test_verify_not_pass_leaves_receipt_unbound(tmp_path):
    """R28 re-pin: observed through the untouched receipt, not the retired residuals field."""
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
    before_receipt = dict(_ledger_receipt(loaded))
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    assert _ledger_receipt(loaded) == before_receipt
    assert before_receipt.get("headSha") == OLD_HEAD
    assert "verifyResult" not in before_receipt


def test_unchanged_head_with_failed_binding_stamps_no_verify(tmp_path):
    """R28 re-pin: observed through the receipt, not the retired residuals field."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    loaded["dispositionLedger"][0]["dispositionReceipt"] = _ledger_fixed_receipt(
        headSha=certified_head,
        fixContentDigest="0" * 64,
    )
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    receipt = _ledger_receipt(loaded)
    assert receipt == _ledger_fixed_receipt(headSha=certified_head, fixContentDigest="0" * 64)
    assert receipt.get("verifyResult") is None


def test_fixed_row_without_receipt_stays_receiptless(tmp_path):
    """R28 re-pin: finalization synthesizes no receipt; certification refuses the row."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    loaded["dispositionLedger"][0].pop("dispositionReceipt", None)
    RD._finalize_certification_inputs(session_dir, loaded, head_sha=certified_head)
    assert _ledger_receipt(loaded) is None
    assert "_fixedDispositionFinalizationResiduals" not in loaded


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
    """axis: the positive certification fixture reaches its terminal THROUGH THE REAL LOOP.

    The fix leg's fixer, audits and verify steps fold through `advance` → `cmd_submit`; the loop
    enters its own converged terminal and its terminal gate writes the certification receipt. The
    terminal round is the round holding the latest evidence — nothing restored a snapshot over it."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    assert state["terminal"] == "converged", state.get("certification")
    assert state["step"] == RD.P_TERMINAL
    assert state["round"] == 2
    assert sorted(state["rounds"], key=int)[-1] == "2"
    assert state["rounds"]["1"].get("fixFoldHead") == certified_head
    verify_round = state["rounds"]["2"]
    assert verify_round.get("verifyResult") == "pass"
    assert verify_round.get(SC.VERIFIED_HEAD_FIELD) == certified_head
    accepted = [row for row in RD.read_journal(session_dir)
                if row.get("cmd") == "submit" and row.get("outcome") == "accepted"]
    assert [row.get("phase") for row in accepted] == _FIX_LEG
    cert_path = os.path.join(session_dir, RD.CERTIFICATION_RECEIPT_FILE)
    assert os.path.isfile(cert_path), "the loop's terminal gate must write the receipt"
    with open(cert_path, encoding="utf-8") as fh:
        loop_receipt = json.load(fh)
    assert _cert_receipt_fixed_binding(loop_receipt) == (certified_head, "pass")
    cert_receipt, cert_refusal = RC.certify(session_dir)
    assert cert_refusal is None, cert_refusal
    assert _cert_receipt_fixed_binding(cert_receipt) == (certified_head, "pass")


def test_head_verified_at_h_does_not_credit_h_prime(tmp_path):
    """axis: a head verified at H does not credit H' at finalization or certification.

    R28 re-pin: the head moves AND the persisted `fixFoldHeadSha` pin is cleared from meta and
    config, so certification binds to H' itself — and refuses `verify-not-on-head`. With the pin
    left standing the certified head silently stayed H and the old `verify-not-pass` expectation
    never exercised a moved certified head at all."""
    session_dir, head1 = _certifiable_session(tmp_path, name="two-head")
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded["rounds"]["2"][SC.VERIFIED_HEAD_FIELD] == head1
    assert _ledger_receipt(loaded).get("headSha") == head1
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
    meta["headSha"] = head2
    assert meta.pop(RD.FIX_FOLD_HEAD_KEY) == head1
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
    loaded["config"]["headSha"] = head2
    assert loaded["config"].pop(RD.FIX_FOLD_HEAD_KEY) == head1
    RD.save_state(session_dir, loaded)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    RD._finalize_certification_inputs(session_dir, state, head_sha=head2)
    receipt = _ledger_receipt(state)
    assert receipt.get("headSha") == head1
    assert "verifyResult" not in receipt
    ctx, err = RC._load_context(session_dir)
    assert err is None
    assert RC._certified_head_sha(ctx) == head2
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


def test_fold_verify_without_a_resolved_head_records_no_verified_head():
    """axis: the in-process leg hands `_fold_verify` no head — none is recorded, the accessor stays
    None, and no refusal record is written (R28 re-pin: `verifiedHeadRefused` is retired, because a
    refusal record followed by an advance is exactly what the submit-side refusal forbids)."""
    state = RD.new_state({"fixerVendor": "claude"})
    head = "a" * 40
    state["round"] = 1
    state["config"]["headSha"] = head
    RD._fold_verify(state, state["config"], {"result": "pass"})
    rec = state["rounds"].get("1") or {}
    assert rec.get("verifyResult") == "pass"
    assert SC.VERIFIED_HEAD_FIELD not in rec
    assert "verifiedHeadRefused" not in rec
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
        (
            {"rounds": {"bad": {SC.VERIFIED_HEAD_FIELD: "h" * 40, "verifyResult": "pass"}}},
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
        "older-pass-newer-fail",
        "newer-record-without-a-result",
        "non-integer-round-key-skipped",
    ],
)
def test_verify_result_for_head_accessor_axes(state, head, expected):
    """axis: verify_result_for_head is the one fail-closed reader of the verified-head fact."""
    assert SC.verify_result_for_head(state, head) == expected


@pytest.mark.parametrize(
    "newer_record",
    [{"verifyResult": "fail"}, {}],
    ids=["older-pass-newer-fail", "newer-record-without-a-result"],
)
def test_ordering_axis_carried_through_finalization(tmp_path, newer_record):
    """axis: the NEWEST verify record for the certified head decides — an older pass never
    outlives a newer fail or a newer record that carries no result. Carried through terminal
    finalization (the stamped pass is revoked) and certification (`verify-not-pass`)."""
    session_dir, certified_head = _certifiable_session(tmp_path)
    with open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    assert state["rounds"]["2"][SC.VERIFIED_HEAD_FIELD] == certified_head
    assert state["rounds"]["2"]["verifyResult"] == "pass"
    assert _ledger_receipt(state).get("verifyResult") == "pass"
    newer = {SC.VERIFIED_HEAD_FIELD: certified_head}
    newer.update(newer_record)
    state["rounds"]["3"] = newer
    RD.save_state(session_dir, state)
    RD._finalize_certification_inputs(session_dir, state, head_sha=certified_head)
    receipt = _ledger_receipt(state)
    assert receipt.get("headSha") == certified_head
    assert "verifyResult" not in receipt
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
