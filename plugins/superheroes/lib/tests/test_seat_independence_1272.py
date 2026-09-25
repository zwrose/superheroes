"""Seat independence — loop record, driver seed, certification receipt (#1272 WO-2)."""
import model_registry
import receipt_disclosures
import round_certification as RC
import round_driver as RD
import round_records as RR

from round_certification_fixtures import (
    AUDIT_PHASE,
    DEFAULT_PANEL_PAYLOAD,
    DEFAULT_PANEL_PAYLOAD_SHA,
    HEAD_SHA,
    write_session,
)

FIXER_PHASE = "dispatch-fixer"
FIXER_SEAT = "dispatch-fixer"
AUDIT_SEAT = "audit-target-01"
HEAD = "diff --git a/a.py\n"


def _observation_fields(*, read="engaged", source="runner", tool_calls=1):
    return {
        "read": read,
        "source": source,
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
        "tokens": None,
        "toolCalls": tool_calls,
    }


def _execution_evidence(seat, phase, attempt, occurrence, *, source, payload=None):
    payload = payload if payload is not None else DEFAULT_PANEL_PAYLOAD
    result_digest = RR.payload_sha256(payload.get("findings", []))
    nonce = "nonce-%s-%s-a%d-o%d" % (seat, phase, attempt, occurrence)
    run_kind = "write" if phase == FIXER_PHASE else "review"
    return {
        "source": source,
        "runnerNonce": nonce,
        "recordDigest": "d" * 64,
        "resultDigest": result_digest,
        "resultKind": "findings",
        "runKind": run_kind,
        "observation": _observation_fields(source=source),
    }


def _journal_row(seat, phase, *, source, round_num=1, attempt=0, occurrence=0,
                 provenance=RC.PROVENANCE_DISPATCH_OBSERVED, payload_sha=None):
    payload_sha = payload_sha or DEFAULT_PANEL_PAYLOAD_SHA
    evidence = _execution_evidence(seat, phase, attempt, occurrence, source=source)
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": round_num,
        "attempt": attempt,
        "seat": seat,
        "occurrence": occurrence,
        "provenance": provenance,
        "payloadSha256": payload_sha,
        "headSha": HEAD_SHA,
        "citedHead": HEAD_SHA,
        "executionEvidence": evidence,
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": occurrence,
            "attempt": attempt,
        },
    }


def _envelope_spec(seat, phase, *, source, round_num=1, attempt=0, occurrence=0,
                   provenance=RC.PROVENANCE_DISPATCH_OBSERVED, payload=None):
    payload = payload if payload is not None else DEFAULT_PANEL_PAYLOAD
    payload_sha = RR.payload_sha256(payload)
    return {
        "seat": seat,
        "phase": phase,
        "round": round_num,
        "attempt": attempt,
        "occurrence": occurrence,
        "provenance": provenance,
        "payloadSha256": payload_sha,
        "payload": payload,
        "executionEvidence": _execution_evidence(
            seat, phase, attempt, occurrence, source=source, payload=payload
        ),
    }


def _independence_session(tmp_path, **kwargs):
    state_over = {
        "config": {
            "fixerVendor": "cursor",
            "baseGuard": RC.BASE_GUARD_CHECKED,
            "headSha": HEAD_SHA,
        },
    }
    state_over.update(kwargs.pop("state", {}))
    cfg = state_over.get("config") or {}
    cfg.setdefault("fixerVendor", "cursor")
    cfg.setdefault("baseGuard", RC.BASE_GUARD_CHECKED)
    cfg.setdefault("headSha", HEAD_SHA)
    state_over["config"] = cfg

    journal_lines = [
        _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
        _journal_row(FIXER_SEAT, FIXER_PHASE, source="cursor"),
        _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="claude"),
    ]
    journal_lines.extend(kwargs.pop("extra_journal", []))
    if "journal_lines" in kwargs:
        journal_lines = kwargs.pop("journal_lines")

    envelopes = [
        _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
        _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="cursor"),
        _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="claude"),
    ]
    envelopes.extend(kwargs.pop("extra_envelopes", []))
    if "envelopes" in kwargs:
        envelopes = kwargs.pop("envelopes")

    return write_session(
        tmp_path,
        state=state_over,
        journal_lines=journal_lines,
        envelopes=envelopes,
        **kwargs,
    )


def test_receipt_independence_reads_recorded_fixer_vendor_two_vendors(tmp_path):
    session_dir = _independence_session(tmp_path)
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    expected = {
        "status": "independent",
        "basis": "runner-recorded-audit-seats",
        "fixerVendor": "cursor",
        "fixerFamily": model_registry.family_for("code-fixer", "cursor"),
        "declaredVendors": ["claude"],
        "auditSeats": [
            {
                "seat": AUDIT_SEAT,
                "round": 1,
                "vendor": "claude",
                "family": model_registry.family_for("auditor", "claude"),
                "model": None,
            }
        ],
    }
    assert receipt["independence"] == expected
    assert "independence" in receipt["provenanceLabels"]["derived"]


def test_receipt_independence_no_declared_vendor_fails_closed(tmp_path):
    session_dir = write_session(
        tmp_path,
        state={"config": {"fixerVendor": None, "baseGuard": RC.BASE_GUARD_CHECKED, "headSha": HEAD_SHA}},
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"

    state = RD.new_state(RD._default_config({"vendors": ["claude"]}))
    assert state["independenceDegraded"] is True


def test_fixer_seat_contradicting_declaration_refuses(tmp_path):
    session_dir = _independence_session(
        tmp_path,
        journal_lines=[
            _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
            _journal_row(FIXER_SEAT, FIXER_PHASE, source="claude"),
            _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="codex"),
        ],
        envelopes=[
            _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
            _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="claude"),
            _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="codex"),
        ],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert refusal["bindingFailure"] == "fixer-vendor-contradicted"


def test_audit_seat_same_family_per_runner_record_reads_degraded(tmp_path):
    session_dir = _independence_session(
        tmp_path,
        state={"config": {"fixerVendor": "claude", "baseGuard": RC.BASE_GUARD_CHECKED, "headSha": HEAD_SHA}},
        journal_lines=[
            _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
            _journal_row(FIXER_SEAT, FIXER_PHASE, source="claude"),
            _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="claude"),
        ],
        envelopes=[
            _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
            _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="claude"),
            _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="claude"),
        ],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    assert receipt["independence"] == {
        "status": "degraded",
        "basis": "auditor-same-family",
        "fixerVendor": "claude",
        "fixerFamily": model_registry.family_for("code-fixer", "claude"),
        "declaredVendors": ["claude"],
        "auditSeats": [
            {
                "seat": AUDIT_SEAT,
                "round": 1,
                "vendor": "claude",
                "family": model_registry.family_for("auditor", "claude"),
                "model": None,
            }
        ],
        "sameFamilySeats": [AUDIT_SEAT],
    }


def test_audit_seat_source_runner_is_not_a_vendor_refuses(tmp_path):
    session_dir = _independence_session(
        tmp_path,
        journal_lines=[
            _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
            _journal_row(FIXER_SEAT, FIXER_PHASE, source="cursor"),
            _journal_row(AUDIT_SEAT, AUDIT_PHASE, source="runner"),
        ],
        envelopes=[
            _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
            _envelope_spec(FIXER_SEAT, FIXER_PHASE, source="cursor"),
            _envelope_spec(AUDIT_SEAT, AUDIT_PHASE, source="runner"),
        ],
    )
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal["class"] == "unfetched-findings"
    assert "runner" in refusal["detail"]


def test_audit_seat_without_recorded_vendor_refuses(tmp_path):
    audit_payload = {"findings": [{"id": AUDIT_SEAT, "severity": "Minor", "title": "audit ok"}]}
    audit_payload_sha = RR.payload_sha256(audit_payload)
    evidence = _execution_evidence(
        AUDIT_SEAT, AUDIT_PHASE, 0, 0, source="claude", payload=audit_payload
    )
    del evidence["source"]
    obs = evidence.get("observation")
    if isinstance(obs, dict):
        obs = dict(obs)
        obs.pop("source", None)
        evidence["observation"] = obs
    session_dir = write_session(
        tmp_path,
        state={
            "config": {
                "fixerVendor": "cursor",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": HEAD_SHA,
            }
        },
        journal_lines=[
            _journal_row("code-reviewer", RC.PANEL_PHASE, source="codex"),
            {
                "cmd": "record-result",
                "outcome": "recorded",
                "phase": AUDIT_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": AUDIT_SEAT,
                "occurrence": 0,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "payloadSha256": audit_payload_sha,
                "headSha": HEAD_SHA,
                "citedHead": HEAD_SHA,
                "recordIdentity": {
                    "phase": AUDIT_PHASE,
                    "seat": AUDIT_SEAT,
                    "occurrence": 0,
                    "attempt": 0,
                },
            },
        ],
        envelopes=[
            _envelope_spec("code-reviewer", RC.PANEL_PHASE, source="codex"),
            {
                "seat": AUDIT_SEAT,
                "phase": AUDIT_PHASE,
                "round": 1,
                "attempt": 0,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "payloadSha256": audit_payload_sha,
                "payload": audit_payload,
                "executionEvidence": evidence,
            },
        ],
    )
    ctx, load_refusal = RC._load_context(session_dir)
    assert load_refusal is None
    refusal = RC.check_seat_independence(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "auditor-vendor-underivable"


def test_driver_seed_single_vendor_cross_family_fixer_is_independent():
    assert (
        RD.new_state(RD._default_config({"vendors": ["claude"], "fixerVendor": "cursor"}))[
            "independenceDegraded"
        ]
        is False
    )
    assert (
        RD.new_state(RD._default_config({"vendors": ["claude"], "fixerVendor": "claude"}))[
            "independenceDegraded"
        ]
        is True
    )
    assert RD.new_state(RD._default_config({"vendors": ["claude"]}))["independenceDegraded"] is True
    assert (
        RD.new_state(RD._default_config({"vendors": ["codex", "cursor"]}))["independenceDegraded"]
        is False
    )


def test_fixer_round_record_carries_declared_vendor():
    state = RD.new_state(RD._default_config({"fixerVendor": "cursor"}))
    RD._fold_panel(
        state,
        state["config"],
        {"seats": {dim: {"findings": []} for dim in RD.DIMENSIONS}},
    )
    RD._fold_fixer(state, state["config"], {"fixes": [], "headDiff": HEAD})
    # re-pinned (#1272 layer 2d): the fixer fold now advances the round; the vendor is recorded on the fold's own round
    assert state["rounds"]["1"]["fixerVendor"] == state["config"]["fixerVendor"]


def test_duplicate_vendor_entries_do_not_read_independent():
    assert (
        RD.new_state(RD._default_config({"vendors": ["claude", "claude"]}))["independenceDegraded"]
        is True
    )
    assert receipt_disclosures.live_vendors({"vendors": ["codex", "codex", "cursor"]}) == [
        "codex",
        "cursor",
    ]


def test_auditor_vendor_and_seed_share_one_rule():
    configs = [
        {"vendors": ["claude"], "fixerVendor": "cursor"},
        {"vendors": ["claude"], "fixerVendor": "claude"},
        {"vendors": ["codex", "cursor"], "fixerVendor": "cursor"},
    ]
    for cfg in configs:
        full_cfg = RD._default_config(cfg)
        fixer = full_cfg.get("fixerVendor")
        expected = (
            "independent"
            if receipt_disclosures.independent_auditor_available(full_cfg)[0]
            else "degraded"
        )
        assert RD._auditor_vendor(full_cfg, fixer)[1] == expected
