"""Six-case birth suite and FR-D2 specimen pair for round_certification (#1271 C12 L2-K)."""
import os

import round_certification as RC
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
