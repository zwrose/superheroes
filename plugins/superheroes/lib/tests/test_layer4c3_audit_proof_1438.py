"""#1438 layer 4c-3: discharged-but-new-issue fix-receipt reconciliation."""
import hashlib
import json
import os

import audits
import pytest
import record_paths
import round_certification as RC
import round_records as RR
import session_contract as SC
from round_certification_fixtures import (
    AUDIT_PHASE,
    JOURNAL_FILE,
    SCOPED_PHASE,
    SCOPED_SEAT,
    _FIX_PRESENT_BYTES,
    _audit_dispatch_envelope,
    _default_case08_new_issues,
    _head_content_blobs_for_findings,
    _recorded_row_from_envelope,
    _write_head_content_blobs,
    _orders_manifest_for_seat,
    _write_orders_manifest,
    case07_audited_chain,
    case08_new_issue_audit,
    two_fix_rounds_rebound_session,
)


def _certify(session_dir):
    return RC.certify(session_dir)


def _state_path(session_dir):
    return os.path.join(session_dir, RC.STATE_FILE)


def _load_state(session_dir):
    return json.load(open(_state_path(session_dir), encoding="utf-8"))


def _save_state(session_dir, state):
    with open(_state_path(session_dir), "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _fold_id(state):
    for row in state.get(SC.DISPOSITION_LEDGER_KEY) or []:
        if row.get("disposition") == "fixed":
            return row.get(SC.FINDING_KEY_FIELD)
    return None


def _new_issue_template():
    return dict(_default_case08_new_issues()[0])


def _new_issue_key(candidate=None):
    cand = candidate or _new_issue_template()
    return SC.minted_identity_key(cand)


def _assert_reconciliation_gap(refusal, suffix):
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:%s" % suffix in refusal["detail"]


def _assert_new_issue_gap(refusal):
    _assert_reconciliation_gap(refusal, "new-issue-undispositioned")


def _assert_fix_receipt_gap(refusal):
    assert refusal is not None
    assert "audited-chain-gap:fix-receipt" in refusal["detail"]


def _assert_fix_receipt_stale_head(refusal):
    _assert_fix_receipt_gap(refusal)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"


def _resync_audit_journal_from_store(session_dir, target_id, *, rnd=2):
    path = record_paths.store_path(
        session_dir, rnd, AUDIT_PHASE, record_paths.storage_key(target_id, 0), 0)
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    head = meta[SC.FIX_FOLD_HEAD_KEY]
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if (
                row.get("outcome") == "recorded"
                and row.get("phase") == AUDIT_PHASE
                and row.get("seat") == target_id
                and row.get("attempt") == 0
                and row.get("round") == rnd
            ):
                row = _recorded_row_from_envelope(
                    envelope, target_id, AUDIT_PHASE, rnd, head_sha=head, attempt=0)
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _mutate_audit_payload(session_dir, fold_id, *, new_issues, ruling="discharged-but-new-issue", rnd=2):
    path = record_paths.store_path(
        session_dir, rnd, AUDIT_PHASE, record_paths.storage_key(fold_id, 0), 0)
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    payload = dict(envelope["payload"])
    payload["ruling"] = ruling
    if ruling == "discharged-but-new-issue":
        payload["newIssues"] = new_issues
    elif ruling == "discharged":
        payload.pop("newIssues", None)
    envelope["payload"] = payload
    envelope["payloadSha256"] = SC.payload_sha256(payload)
    envelope["envelopeSha256"] = RR.envelope_sha256(payload, envelope["executionEvidence"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, sort_keys=True)
    _resync_audit_journal_from_store(session_dir, fold_id, rnd=rnd)


def _case07_fold_id(session_dir):
    state = _load_state(session_dir)
    for finding in state.get("findings") or []:
        if finding.get("disposition") == "fixed":
            return finding.get(SC.FINDING_KEY_FIELD)
    return None


def _ledger_row_for_candidate(candidate, *, disposition="refuted", raised_round=2, raised_seq=1, disp_seq=2, **extra):
    key = SC.minted_identity_key(candidate)
    row = {
        SC.FINDING_KEY_FIELD: key,
        "file": candidate["file"],
        "line": candidate["line"] if isinstance(candidate["line"], int) else int(str(candidate["line"]).strip()),
        "title": candidate["title"],
        "severity": candidate["severity"],
        SC.RAISED_ROUND_FIELD: raised_round,
        SC.RAISED_SEQ_FIELD: raised_seq,
        "disposition": disposition,
        SC.DISPOSITION_SEQ_FIELD: disp_seq,
    }
    row.update(extra)
    return row


def _append_disposition(session_dir, candidate, **row_kw):
    state = _load_state(session_dir)
    state[SC.DISPOSITION_LEDGER_KEY].append(_ledger_row_for_candidate(candidate, **row_kw))
    _save_state(session_dir, state)


def _append_raised_undispositioned(session_dir, candidate, *, raised_seq=1):
    state = _load_state(session_dir)
    cand = candidate
    state[SC.DISPOSITION_LEDGER_KEY].append({
        SC.FINDING_KEY_FIELD: _new_issue_key(cand),
        "file": cand["file"],
        "line": cand["line"] if isinstance(cand["line"], int) else int(str(cand["line"]).strip()),
        "title": cand["title"],
        "severity": cand["severity"],
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: raised_seq,
    })
    _save_state(session_dir, state)


def test_refuted_new_issue_certifies_once_dispositioned(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    _append_disposition(session_dir, cand, disposition="refuted", refutedReason="benign")
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None


def test_out_of_scope_new_issue_certifies_once_dispositioned(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    _append_disposition(
        session_dir,
        cand,
        disposition="out-of-scope",
        outOfScopeReason="accepted adjacent risk",
        followUp={
            "item": "track in backlog",
            "revisitTrigger": "next release",
            "classClosure": "tracked in issue-42",
        },
    )
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal


def test_fixed_new_issue_certifies_with_later_discharged_audit(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    certified_head = meta[SC.FIX_FOLD_HEAD_KEY]
    fold_id = _fold_id(state)
    cand = _new_issue_template()
    new_key = _new_issue_key(cand)
    fix_digest = hashlib.sha256(_FIX_PRESENT_BYTES).hexdigest()
    state[SC.DISPOSITION_LEDGER_KEY].append({
        SC.FINDING_KEY_FIELD: new_key,
        "file": cand["file"],
        "line": cand["line"],
        "title": cand["title"],
        "severity": cand["severity"],
        "disposition": "fixed",
        "dispositionRound": 3,
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: 1,
        SC.DISPOSITION_SEQ_FIELD: 2,
        "dispositionReceipt": {
            "headSha": certified_head,
            "verifyResult": "pass",
            "fixContentHeadSha": certified_head,
            "fixContentDigest": fix_digest,
            "fixContentBytes": len(_FIX_PRESENT_BYTES),
        },
    })
    state["round"] = 3
    state["rounds"]["2"]["fixFoldHead"] = certified_head
    state["rounds"]["3"] = {
        "roundKind": "fix",
        "scopedFinder": "skipped-empty-surface",
        "verifyResult": "pass",
        "verifiedHead": certified_head,
    }
    audit_env = _audit_dispatch_envelope(new_key, 3, ruling="discharged")
    state.setdefault("findings", [])
    _save_state(session_dir, state)
    audit_manifest = _orders_manifest_for_seat(new_key, rnd=3, attempt=0, phase=AUDIT_PHASE)
    audit_manifest_sha = _write_orders_manifest(session_dir, audit_manifest)
    orders_row = {
        "cmd": "advance",
        "outcome": "orders-emitted",
        "phase": AUDIT_PHASE,
        "round": 3,
        "attempt": 0,
        "manifestSha256": audit_manifest_sha,
    }
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(orders_row, sort_keys=True) + "\n")
        fh.write(json.dumps(
            _recorded_row_from_envelope(
                audit_env, new_key, AUDIT_PHASE, 3, head_sha=certified_head),
            sort_keys=True,
        ) + "\n")
    audit_store = record_paths.store_path(
        session_dir, 3, AUDIT_PHASE, record_paths.storage_key(new_key, 0), 0)
    os.makedirs(os.path.dirname(audit_store), exist_ok=True)
    with open(audit_store, "w", encoding="utf-8") as fh:
        json.dump(audit_env, fh, sort_keys=True)
    _resync_audit_journal_from_store(session_dir, new_key, rnd=3)
    new_row = state[SC.DISPOSITION_LEDGER_KEY][-1]
    finding_blob = {
        "file": cand["file"],
        "line": cand["line"],
        "disposition": "fixed",
        "dispositionReceipt": new_row["dispositionReceipt"],
    }
    blobs = _head_content_blobs_for_findings([finding_blob], certified_head)
    assert blobs is not None
    existing_path = os.path.join(session_dir, RC.HEAD_CONTENT_BLOBS_FILE)
    if os.path.isfile(existing_path):
        prior = json.load(open(existing_path, encoding="utf-8"))
        prior["files"].update(blobs["files"])
        prior["reads"].extend(blobs["reads"])
        blobs = prior
    _write_head_content_blobs(session_dir, blobs)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal


def test_string_line_coerces_and_certifies_once_dispositioned(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    cand = {"severity": "Minor", "file": "src/leak.py", "line": "12", "title": "string line"}
    _mutate_audit_payload(session_dir, fold_id, new_issues=[cand])
    _append_disposition(session_dir, cand, disposition="refuted", refutedReason="noise")
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal


def test_e1_empty_linked_set_refuses(tmp_path, monkeypatch):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    real_apply = audits.apply_audit_results

    def _empty_linked_outcome(targets, results, **kwargs):
        outcome = real_apply(targets, results, **kwargs)
        patched = dict(outcome)
        audits_out = []
        for entry in outcome.get("audits") or []:
            row = dict(entry)
            if row.get("id") == fold_id:
                row["ruling"] = "discharged-but-new-issue"
            audits_out.append(row)
        patched["audits"] = audits_out
        patched["newIssues"] = []
        return patched

    monkeypatch.setattr(audits, "apply_audit_results", _empty_linked_outcome)
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-evidence-malformed")


def test_e2_foreign_candidates_only_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    candidate = _new_issue_template()
    _append_disposition(session_dir, candidate, disposition="refuted", refutedReason="closed")
    state = _load_state(session_dir)
    linked = [dict(candidate, originAuditId=fold_id)]
    foreign = [dict(candidate, originAuditId="other-audit")]
    assert RC._new_issues_reconciliation_gap(state, fold_id, 2, foreign) == "new-issue-evidence-malformed"
    assert RC._new_issues_reconciliation_gap(state, fold_id, 2, linked) is None


def test_e3_non_coercible_line_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    bad = dict(_new_issue_template(), line="not-a-number")
    _mutate_audit_payload(session_dir, _fold_id(state), new_issues=[bad])
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-evidence-malformed")


def test_e4_candidate_key_equals_fold_id_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    same = {
        "severity": "Important",
        "file": "src/guard.py",
        "line": 12,
        "title": "missing bounds guard",
    }
    _mutate_audit_payload(session_dir, fold_id, new_issues=[same])
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-evidence-malformed")


def test_e5_unrecognized_ledger_owner_refuses(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    fold_id = _case07_fold_id(session_dir)
    _mutate_audit_payload(session_dir, fold_id, new_issues=_default_case08_new_issues())
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-ledger-owner-unrecognized")


def test_e6_zero_ledger_rows_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    _, refusal = _certify(session_dir)
    _assert_new_issue_gap(refusal)


def test_e7_duplicate_ledger_rows_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    row = _ledger_row_for_candidate(cand, disposition="refuted", refutedReason="x")
    state = _load_state(session_dir)
    state[SC.DISPOSITION_LEDGER_KEY].extend([row, dict(row)])
    _save_state(session_dir, state)
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-duplicate-identity")


def test_e8_stale_raised_round_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    _append_disposition(session_dir, cand, raised_round=1, disposition="refuted", refutedReason="x")
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-ledger-malformed")


def test_e9_missing_raised_seq_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    row = _ledger_row_for_candidate(cand, disposition="refuted", refutedReason="x")
    row.pop(SC.RAISED_SEQ_FIELD)
    state = _load_state(session_dir)
    state[SC.DISPOSITION_LEDGER_KEY].append(row)
    _save_state(session_dir, state)
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-ledger-malformed")


def test_e10_unresolvable_merge_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    row = _ledger_row_for_candidate(
        cand, disposition="refuted", refutedReason="x", mergedInto="missing-rep")
    state = _load_state(session_dir)
    state[SC.DISPOSITION_LEDGER_KEY].append(row)
    _save_state(session_dir, state)
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-merge-unresolvable")


def test_e11b_representative_is_fold_target_with_later_seq_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    for row in state[SC.DISPOSITION_LEDGER_KEY]:
        if row.get(SC.FINDING_KEY_FIELD) == fold_id:
            row[SC.DISPOSITION_SEQ_FIELD] = 5
    cand = _new_issue_template()
    member = {
        SC.FINDING_KEY_FIELD: _new_issue_key(cand),
        "file": cand["file"],
        "line": cand["line"],
        "title": cand["title"],
        "severity": cand["severity"],
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: 1,
        "mergedInto": fold_id,
    }
    state[SC.DISPOSITION_LEDGER_KEY].append(member)
    _save_state(session_dir, state)
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-merge-unresolvable")


def test_e11_representative_key_equals_fold_id_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    cand = _new_issue_template()
    member = _ledger_row_for_candidate(
        cand, disposition="refuted", refutedReason="x", mergedInto=fold_id)
    state[SC.DISPOSITION_LEDGER_KEY].append(member)
    _save_state(session_dir, state)
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-merge-unresolvable")


def test_e12b_minor_seq_without_disposition_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = dict(_new_issue_template(), severity="Minor")
    row = {
        SC.FINDING_KEY_FIELD: _new_issue_key(cand),
        "file": cand["file"],
        "line": cand["line"],
        "title": cand["title"],
        "severity": cand["severity"],
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: 1,
        SC.DISPOSITION_SEQ_FIELD: 2,
    }
    state = _load_state(session_dir)
    state[SC.DISPOSITION_LEDGER_KEY].append(row)
    _save_state(session_dir, state)
    fold_id = _fold_id(state)
    _mutate_audit_payload(session_dir, fold_id, new_issues=[cand])
    _, refusal = _certify(session_dir)
    _assert_new_issue_gap(refusal)


def test_e12_invalid_disposition_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    _append_disposition(session_dir, cand, disposition="open")
    _, refusal = _certify(session_dir)
    _assert_new_issue_gap(refusal)


def test_e13_disposition_seq_not_after_raise_refuses(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path)
    cand = _new_issue_template()
    _append_disposition(session_dir, cand, disposition="refuted", refutedReason="x", disp_seq=1)
    _, refusal = _certify(session_dir)
    _assert_new_issue_gap(refusal)


@pytest.mark.parametrize("order", ["disposed-first", "undisposed-first"])
def test_e15_duplicate_merge_representative_both_orders_refuse(tmp_path, order):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    cand = _new_issue_template()
    member_key = _new_issue_key(cand)
    rep = {
        "severity": "Important",
        "file": "src/rep.py",
        "line": 99,
        "title": "representative dup",
    }
    rep_key = SC.minted_identity_key(rep)
    row_disposed = {
        SC.FINDING_KEY_FIELD: rep_key,
        "file": rep["file"],
        "line": rep["line"],
        "title": rep["title"],
        "severity": rep["severity"],
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: 2,
        "disposition": "refuted",
        SC.DISPOSITION_SEQ_FIELD: 3,
        "refutedReason": "closed",
    }
    row_undisposed = {
        SC.FINDING_KEY_FIELD: rep_key,
        "file": rep["file"],
        "line": rep["line"],
        "title": rep["title"],
        "severity": rep["severity"],
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: 2,
    }
    member_row = {
        SC.FINDING_KEY_FIELD: member_key,
        "file": cand["file"],
        "line": cand["line"],
        "title": cand["title"],
        "severity": cand["severity"],
        SC.RAISED_ROUND_FIELD: 2,
        SC.RAISED_SEQ_FIELD: 1,
        "mergedInto": rep_key,
    }
    dup_rows = (
        [row_disposed, row_undisposed]
        if order == "disposed-first"
        else [row_undisposed, row_disposed]
    )
    state[SC.DISPOSITION_LEDGER_KEY].extend([member_row, *dup_rows])
    _save_state(session_dir, state)
    _mutate_audit_payload(session_dir, fold_id, new_issues=[cand])
    _, refusal = _certify(session_dir)
    _assert_reconciliation_gap(refusal, "new-issue-duplicate-identity")


@pytest.mark.parametrize("order", ["pass-first", "fail-first"])
def test_e14_mixed_candidates_both_orders_refuse(tmp_path, order):
    session_dir = case08_new_issue_audit(tmp_path)
    state = _load_state(session_dir)
    fold_id = _fold_id(state)
    good = _new_issue_template()
    bad = {
        "severity": "Minor",
        "file": "src/bad.py",
        "line": 7,
        "title": "second regression",
    }
    if order == "pass-first":
        issues = [good, bad]
    else:
        issues = [bad, good]
    _mutate_audit_payload(session_dir, fold_id, new_issues=issues)
    _append_disposition(session_dir, good, disposition="refuted", refutedReason="ok")
    _append_raised_undispositioned(session_dir, bad, raised_seq=2)
    _, refusal = _certify(session_dir)
    _assert_new_issue_gap(refusal)


def test_not_discharged_still_refuses_fix_receipt(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path, ruling="not-discharged")
    _, refusal = _certify(session_dir)
    _assert_fix_receipt_gap(refusal)


def test_two_fix_rounds_with_rebound_receipts_certify(tmp_path):
    session_dir = two_fix_rounds_rebound_session(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


def test_two_fix_rounds_f1_wrong_fix_content_head_refuses(tmp_path):
    def _mutate(finding1, **_kw):
        finding1["dispositionReceipt"]["fixContentHeadSha"] = _kw["certified_head"]

    session_dir = two_fix_rounds_rebound_session(tmp_path, receipt_mutator=_mutate)
    _, refusal = _certify(session_dir)
    _assert_fix_receipt_stale_head(refusal)


def test_two_fix_rounds_f2_missing_fix_content_head_refuses(tmp_path):
    def _mutate(finding1, **_kw):
        finding1["dispositionReceipt"].pop("fixContentHeadSha", None)

    session_dir = two_fix_rounds_rebound_session(tmp_path, receipt_mutator=_mutate)
    _, refusal = _certify(session_dir)
    _assert_fix_receipt_stale_head(refusal)


def test_two_fix_rounds_f3_non_descendant_head_sha_refuses(tmp_path):
    def _mutate(finding1, **_kw):
        finding1["dispositionReceipt"]["headSha"] = _kw["panel_head"]

    session_dir = two_fix_rounds_rebound_session(tmp_path, receipt_mutator=_mutate)
    _, refusal = _certify(session_dir)
    _assert_fix_receipt_stale_head(refusal)
