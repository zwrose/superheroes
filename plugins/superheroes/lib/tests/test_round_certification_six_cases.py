"""Six-case birth suite and FR-D2 specimen pair for round_certification (#1271 C12 L2-K)."""
import json
import os

import pytest
import round_certification as RC
import session_contract
from round_certification_fixtures import (
    AUDIT_PHASE,
    HEAD_SHA,
    SIXTEEN_AUDIT_SEATS,
    base_guard_not_checked_session,
    case01_recovered_seat,
    case02_unrecovered_seat,
    case03_reverted_fix,
    case04_stale_cited_head,
    case05_critical_out_of_scope,
    case05_critical_skipped,
    case06_mixed_panel,
    case07_audited_chain,
    case07_audited_chain_missing_audit,
    case08_new_issue_audit,
    followup_class_closure_none,
    followup_documented_trigger,
    followup_missing_class_closure,
    followup_no_revisit_trigger,
    specimen_must_certify_sixteen_seat_audit,
    specimen_refuse_bare_fabricated_findings,
    specimen_refuse_caller_supplied_execution_evidence,
    specimen_refuse_fabricated_envelope_audited_chain,
)


def _certify(session_dir):
    return RC.certify(session_dir)


def _failed_attempt_visible_in_history(receipt):
    script_ran = receipt.get("scriptRan") or {}
    return script_ran.get("invocations", 0) >= 2


# --- six cases ----------------------------------------------------------------

def test_case_1_recovered_seat_certifies_with_failed_attempt_history(tmp_path):
    session_dir = case01_recovered_seat(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["terminalState"] == "certified"
    assert _failed_attempt_visible_in_history(receipt)
    assert receipt["seats"] == [
        {
            "seat": "code-reviewer",
            "phase": RC.PANEL_PHASE,
            "round": 1,
            "attempt": 1,
            "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
            "model": None,
        }
    ]


def test_case_2_unrecovered_seat_refuses(tmp_path):
    session_dir = case02_unrecovered_seat(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] in ("unrun-review", "unfetched-findings")
    assert refusal["artifact"]


def test_case_3_reverted_fix_refuses_disposition_without_receipt(tmp_path):
    session_dir = case03_reverted_fix(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "F-fix"


def test_case_4_stale_cited_head_refuses(tmp_path):
    session_dir = case04_stale_cited_head(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == "code-reviewer"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"


def test_case_5_critical_out_of_scope_refuses(tmp_path):
    session_dir = case05_critical_out_of_scope(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "C-oos"


def test_case_5_critical_skipped_refuses(tmp_path):
    session_dir = case05_critical_skipped(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "C-skip"


def _mutate_panel_omitted_expected_dimension(session_dir):
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    cfg = state.setdefault("config", {})
    cfg["dimensions"] = ["code-reviewer", "security-reviewer"]
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _mutate_panel_two_heads(session_dir):
    from round_certification_fixtures import (
        _dispatch_envelope_for,
        _orders_manifest_for_seat,
        _recorded_row_from_envelope,
        _write_orders_manifest,
    )

    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    panel_head = meta["headSha"]
    alt_head = "b" * 40
    manifest = _orders_manifest_for_seat("code-reviewer")
    manifest["seats"]["security-reviewer"] = dict(manifest["seats"]["code-reviewer"])
    manifest["seats"]["security-reviewer"]["storeKey"] = "security-reviewer"
    manifest["seats"]["security-reviewer"]["seat"] = "security-reviewer"
    manifest_sha = _write_orders_manifest(session_dir, manifest)
    sec_env = _dispatch_envelope_for("security-reviewer", RC.PANEL_PHASE, 1)
    sec_row = _recorded_row_from_envelope(
        sec_env, "security-reviewer", RC.PANEL_PHASE, 1, head_sha=alt_head)
    journal_path = os.path.join(session_dir, RC.JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("outcome") == "orders-emitted" and row.get("phase") == RC.PANEL_PHASE:
                row["manifestSha256"] = manifest_sha
            lines.append(row)
    lines.append(sec_row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    import record_paths

    path = record_paths.store_path(
        session_dir, 1, RC.PANEL_PHASE, record_paths.storage_key("security-reviewer", 0), 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sec_env, fh, sort_keys=True)


def _drop_scoped_finder_record(session_dir):
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    kept = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("phase") == "dispatch-scoped-finder" and row.get("outcome") == "recorded":
                continue
            kept.append(row)
    with open(path, "w", encoding="utf-8") as fh:
        for row in kept:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _mutate_fix_receipt_fail(session_dir):
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    for finding in state.get("findings") or []:
        if finding.get("disposition") == "fixed":
            finding["dispositionReceipt"]["verifyResult"] = "fail"
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _mutate_verify_fail(session_dir):
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    state["rounds"]["2"]["verifyResult"] = "fail"
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def _mutate_descent_sibling(session_dir):
    from session_checkout import _git

    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    repo = meta["repoRoot"]
    panel_head = meta["headSha"]
    _git(repo, "checkout", "-q", panel_head)
    _git(repo, "checkout", "-qb", "sibling")
    with open(os.path.join(repo, "sibling.txt"), "w", encoding="utf-8") as fh:
        fh.write("sibling\n")
    _git(repo, "add", "sibling.txt")
    _git(repo, "commit", "-q", "-m", "sibling tip")
    sibling_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", "main")
    meta["headSha"] = sibling_head
    with open(os.path.join(session_dir, RC.META_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, sort_keys=True)
    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    state["config"]["headSha"] = sibling_head
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)
    journal_path = os.path.join(session_dir, RC.JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("seat") == "code-reviewer" and row.get("outcome") == "recorded":
                row["headSha"] = sibling_head
                row["citedHead"] = sibling_head
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def test_case_7_audited_chain_certifies(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"
    meta = json.load(open(os.path.join(session_dir, RC.META_FILE), encoding="utf-8"))
    panel_head = meta["headSha"]
    assert receipt["auditedChain"]["panelHead"] == panel_head
    seat_names = {row["seat"] for row in receipt["seats"]}
    assert "code-reviewer" in seat_names


_CASE8_MINOR_NEW_ISSUE = {
    "severity": "Minor",
    "file": "src/leak.py",
    "line": 4,
    "title": "regression adjacent to fix",
}


def test_case_8_new_issue_audit_refuses_then_certifies_once_dispositioned(tmp_path):
    session_dir = case08_new_issue_audit(
        tmp_path,
        seed_raised_new_issue=True,
        new_issues=[dict(_CASE8_MINOR_NEW_ISSUE)],
    )
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:new-issue-undispositioned" in refusal["detail"]

    state_path = os.path.join(session_dir, RC.STATE_FILE)
    state = json.load(open(state_path, encoding="utf-8"))
    new_issue = _CASE8_MINOR_NEW_ISSUE
    new_key = session_contract.minted_identity_key(new_issue)
    raised_seq = None
    for row in state[session_contract.DISPOSITION_LEDGER_KEY]:
        if row.get(session_contract.FINDING_KEY_FIELD) == new_key:
            raised_seq = row[session_contract.RAISED_SEQ_FIELD]
            row["disposition"] = "refuted"
            row["refutedReason"] = "not reproduced on re-read"
            row[session_contract.DISPOSITION_SEQ_FIELD] = raised_seq + 1
            break
    assert raised_seq is not None
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


def test_case_8_important_new_issue_refuses_with_chain_token(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path, seed_raised_new_issue=True)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] != "disposition-without-receipt"
    assert "audited-chain-gap:new-issue-undispositioned" in refusal["detail"]


def test_case_8_plain_discharged_still_certifies(tmp_path):
    session_dir = case08_new_issue_audit(tmp_path, ruling="discharged")
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"


def test_case_7_missing_audit_dispatch_refuses_fix_receipt_leg(tmp_path):
    session_dir = case07_audited_chain_missing_audit(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:fix-receipt" in refusal["detail"]


def test_case_7_omitted_panel_dimension_refuses_roster_gap(tmp_path):
    session_dir = case07_audited_chain(tmp_path)
    _mutate_panel_omitted_expected_dimension(session_dir)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:panel" in refusal["detail"]


@pytest.mark.parametrize(
    "leg,mutator",
    [
        (
            "panel",
            _mutate_panel_two_heads,
        ),
        (
            "descent",
            _mutate_descent_sibling,
        ),
        (
            "fix-receipt",
            lambda sd: _mutate_fix_receipt_fail(sd),
        ),
        (
            "scoped-finder",
            lambda sd: _drop_scoped_finder_record(sd),
        ),
        (
            "verify",
            lambda sd: _mutate_verify_fail(sd),
        ),
    ],
)
def test_case_7_missing_leg_refuses(tmp_path, leg, mutator):
    session_dir = case07_audited_chain(tmp_path)
    mutator(session_dir)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"
    assert "audited-chain-gap:%s" % leg in refusal["detail"]


def test_case_6_mixed_panel_certifies_audited_chain(tmp_path):
    session_dir = case06_mixed_panel(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"
    assert receipt["certificationShape"] != "full-panel-confirmed"
    provenance_by_seat = {row["seat"]: row["provenance"] for row in receipt["seats"]}
    assert provenance_by_seat == {
        "code-reviewer": RC.PROVENANCE_DISPATCH_OBSERVED,
        "security-reviewer": RC.PROVENANCE_HAND_LANDED,
    }


# --- FR-D2 specimen pair -------------------------------------------------------

def test_specimen_must_certify_sixteen_seat_out_of_manifest_audit(tmp_path):
    session_dir = specimen_must_certify_sixteen_seat_audit(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"
    assert len(receipt["seats"]) == 16
    assert {row["seat"] for row in receipt["seats"]} == set(SIXTEEN_AUDIT_SEATS)
    assert all(
        row["provenance"] == RC.PROVENANCE_HAND_LANDED for row in receipt["seats"]
    )
    assert all(row["phase"] == AUDIT_PHASE for row in receipt["seats"])


def test_specimen_refuse_bare_fabricated_findings(tmp_path):
    session_dir = specimen_refuse_bare_fabricated_findings(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] in ("unrun-review", "unfetched-findings")
    assert refusal["artifact"]
    assert os.path.basename(refusal["artifact"]).endswith(".json") or refusal["artifact"]


def test_specimen_refuse_fabricated_envelope_refuses_full_panel_confirmed(tmp_path):
    session_dir = specimen_refuse_fabricated_envelope_audited_chain(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["certificationShape"] == "audited-chain"
    assert receipt["certificationShape"] != "full-panel-confirmed"


def test_specimen_refuse_caller_supplied_execution_evidence(tmp_path):
    session_dir = specimen_refuse_caller_supplied_execution_evidence(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] in ("unrun-review", "unfetched-findings")
    assert refusal["artifact"]


def test_base_guard_not_checked_does_not_certify(tmp_path):
    session_dir = base_guard_not_checked_session(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "base-guard-not-checked"


# --- follow-up rows (register R6) ---------------------------------------------

def test_followup_missing_class_closure_refuses(tmp_path):
    session_dir = followup_missing_class_closure(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "missing-class-closure"
    assert refusal["artifact"] == "I-missing-closure"


def test_followup_class_closure_none_certifies(tmp_path):
    session_dir = followup_class_closure_none(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert refusal is None, refusal
    assert receipt is not None
    assert receipt["terminalState"] == "certified"


def test_followup_no_revisit_trigger_refuses(tmp_path):
    """DoD dry run — register R6: follow-up with no revisit trigger refuses."""
    session_dir = followup_no_revisit_trigger(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "missing-revisit-trigger"
    assert refusal["artifact"] == "I-no-trigger"


def test_followup_documented_trigger_refuses(tmp_path):
    session_dir = followup_documented_trigger(tmp_path)
    receipt, refusal = _certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "I-documented"
