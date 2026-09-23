"""#1272 WO-D: ruling evidence adoption, model field, and receipt naming."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_dispatch  # noqa: E402
import round_certification as RC  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402

from test_seat_provenance_1272 import (  # noqa: E402
    _audit_execution_run_dir,
    _audit_payload,
    _audit_roster,
    _anchor_head_sha,
    _drive_to_audits,
    _land_audits,
    _state,
)

_fake_git = TRI._fake_git


def _pending(session_dir):
    return _state(session_dir)["pending"]


def _store_path(session_dir, seat, pend=None):
    pend = pend or _pending(session_dir)
    return RR.store_path(session_dir, pend["round"], pend["phase"],
                         RR.storage_key(seat), pend["attempt"])


def _patch_run_opened_engine_model(run_dir, engine_model):
    journal_path = engine_dispatch._journal_path(os.path.realpath(run_dir))
    records, _ = engine_dispatch._journal_read(run_dir)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                resolved = dict(rec.get("resolvedInputs") or {})
                if engine_model is None:
                    resolved.pop("engineModel", None)
                else:
                    resolved["engineModel"] = engine_model
                rec["resolvedInputs"] = resolved
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")


def _stub_dispatch_observed_land(session_dir, state, pend, seat, payload=None, occurrence=0):
    manifest_sha, order_sha = TRI._anchor_hashes(session_dir, state, pend, seat, occurrence)
    envelope = {
        "schema": RR.SEAT_RESULT_SCHEMA_V2,
        "session": TRI._session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-01-01T00:00:00",
        "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
        "envelopeSha256": RR.envelope_sha256(payload, None),
    }
    if payload is not None:
        envelope["payload"] = payload
        envelope["payloadSha256"] = RR.payload_sha256(payload)
    if occurrence:
        envelope["occurrence"] = occurrence
    path = RR.landing_path(session_dir, pend["round"], pend["phase"],
                           RR.storage_key(seat, occurrence), pend["attempt"])
    RR.atomic_write_json(path, envelope)
    return path


def _scrubbed_ruling_payload(seat):
    return {
        "id": seat,
        "ruling": "discharged",
        "reason": "re-read the fixed hunk; the defect is gone",
        "auditorVendor": "codex",
    }


def test_edge1_stub_ruling_landing_adopts_runner_payload(tmp_path):
    """Edge 1 — stub landing adopts runner graded record and records model."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge1-adopt")
    seat = _audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
    run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
    _patch_run_opened_engine_model(run_dir, "gpt-5.6-sol-medium")
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert isinstance(record.get("resultContent"), dict)
    state = _state(session_dir)
    _stub_dispatch_observed_land(session_dir, state, pend, seat, payload=None)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, read_err = RR.read_json(out["storePath"])
    assert read_err is None
    assert stored["provenance"] == RR.PROVENANCE_DISPATCH_OBSERVED
    assert stored["payload"] == record["resultContent"]
    assert stored["executionEvidence"]["model"] == "gpt-5.6-sol-medium"


def test_edge2_matching_scrubbed_payload_binds_with_model(tmp_path):
    """Edge 2 — landing payload equals runner scrubbed record; model in evidence."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge2-match")
    seat = _audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
    run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
    _patch_run_opened_engine_model(run_dir, "claude-opus-5-5-medium")
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    ruling_payload = record["resultContent"]
    state = _state(session_dir)
    TRI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, read_err = RR.read_json(out["storePath"])
    assert read_err is None
    assert stored["executionEvidence"]["model"] == "claude-opus-5-5-medium"
    assert RR.payload_sha256(stored["payload"]) == record["resultDigest"]


def test_edge3_raw_seat_stdout_with_investigated_refuses_expected_digest(tmp_path):
    """Edge 3 — raw seat stdout with investigated refuses with expectedPayloadSha256."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge3-raw")
    seat = _audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
    run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    raw_payload = dict(_scrubbed_ruling_payload(seat), investigated=["reviewed.py"])
    state = _state(session_dir)
    TRI._dispatch_observed_land(session_dir, state, pend, seat, raw_payload)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is False
    assert out["reason"] == "evidence-result-mismatch"
    assert out["expectedPayloadSha256"] == RR.payload_sha256(record["resultContent"])
    assert not os.path.exists(_store_path(session_dir, seat))


def test_edge4_stub_non_ruling_kind_refuses_without_adoption(tmp_path):
    """Edge 4 — stub landing on findings run refuses without adoption."""
    order_path = str(tmp_path / "panel-order.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Review the panel findings.\n")
    panel_findings = [{"dimension": "Architecture", "taxonomy": "t", "title": "x"}]
    run_dir = TRI._execution_run_dir(tmp_path, order_path, panel_findings)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert record["resultKind"] == "findings"
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    envelope = {
        "phase": RD.P_PANEL,
        "orderSha256": record["orderPromptSha256"],
        "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
    }
    assembled, refusal, extra, _source = RD._assemble_dispatch_evidence(
        session_dir, envelope, run_dir, "abc123fake", RD.P_PANEL)
    assert assembled is None
    assert refusal == "evidence-result-mismatch"
    assert extra.get("resultKind") == "findings"


def test_edge5_stub_ruling_missing_result_content_refuses(tmp_path):
    """Edge 5 — stub ruling landing without resultContent refuses as today."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge5-missing")
    seat = _audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
    run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
    real_record = engine_dispatch.run_execution_record

    def _patched(_run_dir):
        record, err = real_record(_run_dir)
        if record is not None:
            record = dict(record)
            record.pop("resultContent", None)
        return record, err

    engine_dispatch.run_execution_record = _patched
    try:
        state = _state(session_dir)
        _stub_dispatch_observed_land(session_dir, state, pend, seat, payload=None)
        out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    finally:
        engine_dispatch.run_execution_record = real_record
    assert out["ok"] is False
    assert out["reason"] == "evidence-result-mismatch"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_edge6_adopted_ruling_wrong_id_preflight_refuses(tmp_path):
    """Edge 6 — adopted ruling id not matching seat target refuses at preflight."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge6-wrong-id")
    seat = _audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
    wrong_seat = "other-target::wrong@L1"
    run_dir = _audit_execution_run_dir(tmp_path, order_path, wrong_seat, view_head_sha=anchor_head)
    state = _state(session_dir)
    _stub_dispatch_observed_land(session_dir, state, pend, seat, payload=None)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is False
    assert out["reason"] == "payload-fault"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_edge7_no_engine_model_evidence_model_none(tmp_path):
    """Edge 7 — runner snapshot without engineModel yields model None in evidence."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path, name="edge7-no-model")
    seat = _audit_roster(session_dir)[0]
    pend = _pending(session_dir)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat), pend["attempt"])
    anchor_head = _anchor_head_sha(session_dir) or "abc123fake"
    run_dir = _audit_execution_run_dir(tmp_path, order_path, seat, view_head_sha=anchor_head)
    _patch_run_opened_engine_model(run_dir, None)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert "model" not in record
    ruling_payload = record["resultContent"]
    state = _state(session_dir)
    TRI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, read_err = RR.read_json(out["storePath"])
    assert read_err is None
    assert stored["executionEvidence"].get("model") is None


def test_edge8_old_evidence_without_model_still_valid():
    """Edge 8 — execution evidence without model field is not malformed."""
    evidence = {
        "source": "codex",
        "runnerNonce": "nonce-edge8",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "ruling",
        "observation": {
            "tokens": None,
            "toolCalls": 1,
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
            "source": "codex",
            "read": "engaged",
            "telemetry": "tool-calls",
        },
    }
    assert RR._validate_execution_evidence(evidence) is None


@pytest.mark.parametrize("bad_model", ["", 42, ["list"]])
def test_edge9_bad_model_value_refuses_malformed(bad_model):
    """Edge 9 — model present but empty, numeric, or list refuses malformed."""
    evidence = {
        "source": "codex",
        "runnerNonce": "nonce-edge9",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "ruling",
        "model": bad_model,
        "observation": {
            "tokens": None,
            "toolCalls": 1,
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
            "source": "codex",
            "read": "engaged",
            "telemetry": "tool-calls",
        },
    }
    reason, extra = RR._validate_execution_evidence(evidence)
    assert reason == "execution-evidence-malformed"
    assert extra == {}


def test_edge10_unknown_evidence_field_refuses():
    """Edge 10 — unknown evidence key other than model refuses unknown-field."""
    evidence = {
        "source": "codex",
        "runnerNonce": "nonce-edge10",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "ruling",
        "investigated": ["reviewed.py"],
        "observation": {
            "tokens": None,
            "toolCalls": 1,
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
            "source": "codex",
            "read": "engaged",
            "telemetry": "tool-calls",
        },
    }
    reason, extra = RR._validate_execution_evidence(evidence)
    assert reason == "execution-evidence-unknown-field"
    assert extra["field"] == "investigated"


def test_edge11_write_run_omits_result_content(tmp_path):
    """Edge 11 — write run has no resultContent; execution-only binding unchanged."""
    from test_engine_dispatch_write import (
        _build_ok_stdout,
        _execution_record_completed_write_attempt,
    )

    run_dir = str(tmp_path / "write-edge11")
    os.makedirs(run_dir, exist_ok=True)
    _execution_record_completed_write_attempt(tmp_path, run_dir, stdout=_build_ok_stdout())
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert "resultContent" not in record
    assert record.get("resultKind") == session_contract.WRITE_RESULT_KIND


def test_receipt_audit_seat_model_equals_runner_engine_model(tmp_path):
    """Receipt test — independence.auditSeats[0].model equals runner engineModel."""
    from round_certification_fixtures import (
        AUDIT_PHASE,
        DEFAULT_PANEL_PAYLOAD,
        DEFAULT_PANEL_PAYLOAD_SHA,
        HEAD_SHA,
        write_session,
    )

    engine_model = "gemini-3.8-flash-high"
    audit_seat = "audit-target-01"
    audit_payload = {
        "id": audit_seat,
        "ruling": "discharged",
        "reason": "ok",
        "auditorVendor": "claude",
    }
    audit_payload_sha = RR.payload_sha256(audit_payload)
    audit_evidence = {
        "source": "claude",
        "runnerNonce": "nonce-receipt-model",
        "recordDigest": "d" * 64,
        "resultDigest": audit_payload_sha,
        "resultKind": "ruling",
        "model": engine_model,
        "observation": {
            "read": "engaged",
            "source": "claude",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
            "tokens": None,
            "toolCalls": 1,
        },
    }
    obs_fields = audit_evidence["observation"]
    panel_evidence = {
        "source": "codex",
        "runnerNonce": "nonce-panel",
        "recordDigest": "d" * 64,
        "resultDigest": RR.payload_sha256(DEFAULT_PANEL_PAYLOAD["findings"]),
        "resultKind": "findings",
        "observation": dict(obs_fields, source="codex"),
    }
    fixer_evidence = {
        "source": "cursor",
        "runnerNonce": "nonce-fixer",
        "recordDigest": "d" * 64,
        "resultDigest": RR.payload_sha256(DEFAULT_PANEL_PAYLOAD["findings"]),
        "resultKind": "findings",
        "observation": dict(obs_fields, source="cursor"),
    }
    journal_lines = [
        {
            "cmd": "record-result",
            "outcome": "recorded",
            "phase": RC.PANEL_PHASE,
            "round": 1,
            "attempt": 0,
            "seat": "code-reviewer",
            "occurrence": 0,
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
            "headSha": HEAD_SHA,
            "citedHead": HEAD_SHA,
            "executionEvidence": panel_evidence,
            "recordIdentity": {
                "phase": RC.PANEL_PHASE,
                "seat": "code-reviewer",
                "occurrence": 0,
                "attempt": 0,
            },
        },
        {
            "cmd": "record-result",
            "outcome": "recorded",
            "phase": "dispatch-fixer",
            "round": 1,
            "attempt": 0,
            "seat": "dispatch-fixer",
            "occurrence": 0,
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
            "headSha": HEAD_SHA,
            "citedHead": HEAD_SHA,
            "executionEvidence": fixer_evidence,
            "recordIdentity": {
                "phase": "dispatch-fixer",
                "seat": "dispatch-fixer",
                "occurrence": 0,
                "attempt": 0,
            },
        },
        {
            "cmd": "record-result",
            "outcome": "recorded",
            "phase": AUDIT_PHASE,
            "round": 1,
            "attempt": 0,
            "seat": audit_seat,
            "occurrence": 0,
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": audit_payload_sha,
            "headSha": HEAD_SHA,
            "citedHead": HEAD_SHA,
            "executionEvidence": audit_evidence,
            "recordIdentity": {
                "phase": AUDIT_PHASE,
                "seat": audit_seat,
                "occurrence": 0,
                "attempt": 0,
            },
        },
    ]
    envelopes = [
        {
            "seat": "code-reviewer",
            "phase": RC.PANEL_PHASE,
            "round": 1,
            "attempt": 0,
            "occurrence": 0,
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
            "payload": DEFAULT_PANEL_PAYLOAD,
            "executionEvidence": panel_evidence,
        },
        {
            "seat": "dispatch-fixer",
            "phase": "dispatch-fixer",
            "round": 1,
            "attempt": 0,
            "occurrence": 0,
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
            "payload": DEFAULT_PANEL_PAYLOAD,
            "executionEvidence": fixer_evidence,
        },
        {
            "seat": audit_seat,
            "phase": AUDIT_PHASE,
            "round": 1,
            "attempt": 0,
            "occurrence": 0,
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": audit_payload_sha,
            "payload": audit_payload,
            "executionEvidence": audit_evidence,
        },
    ]
    session_dir = write_session(
        tmp_path,
        state={
            "config": {
                "fixerVendor": "cursor",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": HEAD_SHA,
            },
            "terminal": "converged",
            "step": "terminal",
        },
        journal_lines=journal_lines,
        envelopes=envelopes,
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    audit_seats = receipt["independence"]["auditSeats"]
    assert audit_seats[0]["model"] == engine_model
