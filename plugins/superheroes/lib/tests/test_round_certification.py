import json
import os
import sys

import model_registry
import pytest

import round_certification as RC
from round_certification_fixtures import write_session

HEAD = "a" * 40


def test_certify_clean_session_returns_receipt(tmp_path):
    session_dir = write_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt is not None
    assert receipt["terminalState"] == "certified"
    assert receipt["terminalCause"] is None
    assert receipt["verdict"] == "converged"
    assert receipt["seats"][0]["provenance"] == "dispatch-observed"


def test_absent_session_dir_refuses(tmp_path):
    missing = str(tmp_path / "missing")
    receipt, refusal = RC.certify(missing)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"


def test_unreadable_loop_state_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    path = os.path.join(session_dir, RC.STATE_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.STATE_FILE


def test_missing_loop_state_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    os.remove(os.path.join(session_dir, RC.STATE_FILE))
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["artifact"] == RC.STATE_FILE


def test_absent_journal_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    os.remove(os.path.join(session_dir, RC.JOURNAL_FILE))
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FILE


def test_unreadable_journal_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    os.remove(path)
    os.mkdir(path)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FILE


def test_journal_corrupt_line_refuses(tmp_path):
    session_dir = write_session(tmp_path)
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"cmd":"ok"}\n')
        fh.write("not-json\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == RC.JOURNAL_FILE
    assert "line 2" in refusal["detail"]


def test_journal_blank_lines_only_does_not_certify_claimed_seats(tmp_path):
    session_dir = write_session(tmp_path, envelopes=[])
    path = os.path.join(session_dir, RC.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n\n")
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal is not None


def test_unknown_verdict_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"terminal": "mystery-verdict"},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert "mystery-verdict" in refusal["detail"]


def test_unmapped_provenance_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "orchestrator-fulfilled",
                "payloadSha256": "abc123",
                "executionEvidence": {"read": "engaged", "source": "runner"},
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"


def test_seat_opened_never_closed_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "advance",
                "outcome": "opened",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "roster": [{"seat": "code-reviewer", "occurrence": 0}],
            }
        ],
        envelopes=[],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == "code-reviewer"


# --- check_unrun_review -------------------------------------------------------

def test_check_unrun_review_dispatch_observed_clean_passes(tmp_path):
    session_dir = write_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


def test_check_unrun_review_dispatch_observed_missing_telemetry_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == "code-reviewer"


def test_check_unrun_review_stale_head_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "abc123",
                "headSha": "b" * 40,
                "executionEvidence": {
                    "read": "engaged",
                    "source": "runner",
                    "telemetry": "tool-calls",
                    "stdoutBytes": 1,
                    "wallSeconds": 1.0,
                },
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unrun_review(ctx)
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-stale-head"


def test_check_unrun_review_hand_landed_clean_passes(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "hand-landed",
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": "abc123",
                "provenance": "hand-landed",
            }
        ],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unrun_review(ctx) is None


# --- check_same_family_seat ---------------------------------------------------

def test_check_same_family_seat_clean_passes(tmp_path):
    session_dir = write_session(tmp_path)
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_same_family_seat(ctx) is None


def test_check_same_family_seat_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "claude", "model": "sonnet-5"}},
                        "degradations": [
                            {
                                "constraint": "same-family",
                                "seat": "code-reviewer",
                            }
                        ],
                    },
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


def test_author_family_matches_registry_for_each_vendor(tmp_path):
    session_dir = write_session(tmp_path)
    for vendor in model_registry.VENDORS:
        ctx, _ = RC._load_context(session_dir)
        ctx["state"]["config"]["fixerVendor"] = vendor
        assert RC._author_family(ctx["state"]) == model_registry.family_for(
            "code-fixer", vendor
        )


@pytest.mark.parametrize("with_seats_entry", [False, True])
def test_same_family_declared_degradation_refuses(tmp_path, with_seats_entry):
    seat_map = {
        "degradations": [
            {
                "constraint": "same-family",
                "seat": "code-reviewer",
            }
        ],
    }
    if with_seats_entry:
        seat_map["seats"] = {"code-reviewer": {"vendor": "claude", "model": "sonnet-5"}}
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": seat_map,
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


@pytest.mark.parametrize(
    "vendor",
    [pytest.param(None, id="missing"), pytest.param("", id="empty"), pytest.param(42, id="not-string")],
)
def test_same_family_declared_degradation_refuses_malformed_vendor(tmp_path, vendor):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": vendor, "model": "sonnet-5"}},
                        "degradations": [
                            {
                                "constraint": "same-family",
                                "seat": "code-reviewer",
                            }
                        ],
                    },
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


def test_same_family_unresolvable_maker_family_refuses(tmp_path):
    unknown_vendor = "not-a-registered-vendor"
    session_dir = write_session(
        tmp_path,
        state={
            "config": {"fixerVendor": unknown_vendor},
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "degradations": [
                            {
                                "constraint": "same-family",
                                "seat": "code-reviewer",
                            }
                        ],
                    },
                }
            ],
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["artifact"] == "seatMapReceipts/1"
    assert unknown_vendor in refusal["detail"]


def test_same_family_additive_undeclared_matching_family_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {
                            "code-reviewer": {"vendor": "claude", "model": "sonnet-5"},
                        },
                    },
                }
            ]
        },
        envelopes=[],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_same_family_seat(ctx)
    assert refusal["class"] == "same-family-seat"
    assert refusal["artifact"] == "code-reviewer"


# --- check_unfetched_findings -------------------------------------------------

def test_check_unfetched_findings_clean_passes(tmp_path):
    session_dir = write_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_unfetched_findings(ctx) is None


def test_check_unfetched_findings_missing_envelope_refuses(tmp_path):
    session_dir = write_session(tmp_path, envelopes=[])
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"


def test_check_unfetched_findings_journal_mismatch_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "wrong-hash",
                "executionEvidence": {"read": "engaged", "source": "runner"},
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_unfetched_findings(ctx)
    assert refusal["class"] == "unfetched-findings"
    assert refusal["bindingFailure"] == "journal-envelope-mismatch"


# --- check_disposition_without_receipt ------------------------------------------

def test_check_disposition_without_receipt_clean_passes(tmp_path):
    session_dir = write_session(tmp_path)
    ctx, _ = RC._load_context(session_dir)
    assert RC.check_disposition_without_receipt(ctx) is None


def test_check_disposition_without_receipt_base_guard_not_checked_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"config": {"fixerVendor": "claude", "baseGuard": "not-checked", "headSha": HEAD}},
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "base-guard-not-checked"


def test_check_disposition_without_receipt_fixed_missing_receipt_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "F1",
                    "severity": "Important",
                    "disposition": "fixed",
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "F1"


def test_check_disposition_without_receipt_critical_out_of_scope_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "C1",
                    "severity": "Critical",
                    "disposition": "out-of-scope",
                    "followUp": {
                        "revisitTrigger": "milestone M",
                        "classClosure": "none",
                    },
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == "C1"


def test_check_disposition_without_receipt_missing_revisit_trigger_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "I1",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {"classClosure": "tracked in issue-99"},
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["bindingFailure"] == "missing-revisit-trigger"


def test_check_disposition_without_receipt_missing_class_closure_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {
                    "id": "I1",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {"revisitTrigger": "2026-12-01"},
                }
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["bindingFailure"] == "missing-class-closure"


def test_check_disposition_without_receipt_refuted_missing_reason_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "findings": [
                {"id": "R1", "severity": "Minor", "disposition": "refuted"},
            ]
        },
    )
    ctx, _ = RC._load_context(session_dir)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal["class"] == "disposition-without-receipt"


# --- totality tables ----------------------------------------------------------

def test_verdict_totality_covers_certified_verdicts():
    for verdict in RC.CERTIFIED_VERDICTS:
        assert RC.map_verdict_to_terminal_state(verdict) is not None


def test_verdict_totality_unknown_refuses():
    assert RC.map_verdict_to_terminal_state("not-a-verdict") is None


def test_terminal_cause_known_converged_is_none():
    assert RC.map_terminal_cause("converged", "converged") is None


def test_terminal_cause_unknown_combination_refuses():
    assert RC.map_terminal_cause("converged", "verify-fail") is None
    assert RC.map_terminal_cause("halted", "converged") is None


def test_seat_provenance_totality_maps_receipt_values():
    assert RC.map_seat_provenance("dispatch-observed") == "dispatch-observed"
    assert RC.map_seat_provenance("hand-landed") == "hand-landed"


def test_seat_provenance_orchestrator_fulfilled_refuses():
    assert RC.map_seat_provenance("orchestrator-fulfilled") is None


def test_certification_shape_matrix():
    state = {"certification": {"shape": "custom-shape"}}
    seats_dispatch = [{"provenance": "dispatch-observed"}]
    assert RC._certification_shape(state, seats_dispatch) == "custom-shape"

    state_full = {"certification": {"shape": "full-panel-confirmed"}}
    seats_hand = [{"provenance": "hand-landed"}]
    assert RC._certification_shape(state_full, seats_hand) == "audited-chain"

    state_none = {"certification": {"shape": None}}
    assert RC._certification_shape(state_none, seats_hand) == "audited-chain"

    state_other = {"certification": {"shape": "custom-shape"}}
    assert RC._certification_shape(state_other, seats_hand) == "custom-shape"


def test_hand_landed_forces_audited_chain_shape(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
            }
        },
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "hand-landed",
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": "abc123",
                "provenance": "hand-landed",
            }
        ],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None
    assert receipt["certificationShape"] == "audited-chain"


# --- bite-proof targets (neutralization lives in test, detector unedited) -----

def test_bite_unrun_review_dispatch_telemetry_removed_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_bite_same_family_seat_degradation_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "claude"}},
                        "degradations": [{"constraint": "same-family", "seat": "code-reviewer"}],
                    },
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "same-family-seat"


def test_bite_unfetched_findings_open_seat_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "next",
                "outcome": "opened",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "security-reviewer",
            }
        ],
        envelopes=[],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"


def test_bite_disposition_without_receipt_base_guard_refuses(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"config": {"fixerVendor": "claude", "baseGuard": "not-checked", "headSha": HEAD}},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "disposition-without-receipt"


# --- producer meta cannot bypass escape-class checks (#1271 WO-L2-I) ------------

def _meta_bypass_session(tmp_path, *, state=None, journal_lines=None, envelopes=None, meta=None):
    return write_session(
        tmp_path,
        name="meta-bypass",
        state=state,
        journal_lines=journal_lines,
        envelopes=envelopes,
        meta=dict(meta or {}, producer="run-loop"),
    )


def test_meta_producer_cannot_bypass_unrun_review(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_meta_producer_cannot_bypass_same_family_seat(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        state={
            "seatMapReceipts": [
                {
                    "round": "1",
                    "map": {
                        "seats": {"code-reviewer": {"vendor": "claude"}},
                        "degradations": [{"constraint": "same-family", "seat": "code-reviewer"}],
                    },
                }
            ]
        },
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "same-family-seat"


def test_meta_producer_cannot_bypass_unfetched_findings(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        journal_lines=[
            {
                "cmd": "next",
                "outcome": "opened",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "security-reviewer",
            }
        ],
        envelopes=[],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"


def test_meta_producer_cannot_bypass_disposition_without_receipt(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        state={"config": {"fixerVendor": "claude", "baseGuard": "not-checked", "headSha": HEAD}},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "disposition-without-receipt"


def test_meta_producer_arbitrary_key_cannot_bypass_unrun_review(tmp_path):
    session_dir = _meta_bypass_session(
        tmp_path,
        meta={"producer": "run-loop", "mode": "pr", "bypassToken": "anything"},
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": "dispatch-panel",
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": "dispatch-observed",
                "payloadSha256": "abc123",
                "recordIdentity": {
                    "phase": "dispatch-panel",
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unrun-review"


def test_materialized_session_preserves_checked_base_guard(tmp_path):
    session_dir = write_session(
        tmp_path,
        name="checked-guard",
        state={"config": {"fixerVendor": "claude", "baseGuard": RC.BASE_GUARD_CHECKED, "headSha": HEAD}},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    with open(os.path.join(session_dir, RC.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    import round_driver as RD

    materialized = RD._materialize_run_loop_session(state, 1, source_session_dir=session_dir)
    try:
        with open(os.path.join(materialized, RC.STATE_FILE), encoding="utf-8") as fh:
            materialized_state = json.load(fh)
        assert materialized_state["config"]["baseGuard"] == RC.BASE_GUARD_CHECKED
        receipt, refusal = RC.certify(materialized)
        assert refusal is None, refusal
        assert receipt["baseGuard"] == RC.BASE_GUARD_CHECKED
    finally:
        import shutil

        shutil.rmtree(materialized, ignore_errors=True)
