"""Driver-side receipt boundary tests — writer tests stay driverless in test_round_certification."""
import json
import os
import sys

import engine_dispatch
import pytest
import resolved_inputs_vocab as riv
import round_adapters
import round_records
import session_contract

import round_certification as RC
import round_driver as RD
from round_certification_fixtures import (
    DEFAULT_PANEL_PAYLOAD_SHA,
    HEAD_SHA,
    write_certifiable_session,
)

import test_round_driver_integration as tdi

HEAD = HEAD_SHA


def test_journal_execution_evidence_fields_copies_optional_engine_model():
    evidence = {
        "source": "runner",
        "runnerNonce": "nonce-1",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
        "observation": {"read": "engaged"},
        "engineModel": "gpt-5.6-sol",
    }
    copied = RD._journal_execution_evidence_fields(evidence)
    assert copied["engineModel"] == "gpt-5.6-sol"
    without_optional = dict(evidence)
    del without_optional["engineModel"]
    copied_without = RD._journal_execution_evidence_fields(without_optional)
    assert "engineModel" not in copied_without


def _driver_panel_recorded_rows(tmp_path, native_seat, runner_seat):
    """Two panel seats recorded through the real driver path with distinct transports."""
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, name="driver-native-boundary")
    tdi._drive_to_phase(
        session_dir, gitdir, [tdi._blocking_finding("missing bounds guard", 2)],
        head_path, RC.PANEL_PHASE,
    )
    state = tdi._state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None
    slots = tdi._slots_of(roster)
    tdi._write_dispatch_manifest(session_dir, pend, slots, tdi._auditor_vendor_for(state))
    store_specs = []
    stored_by_seat = {}
    for seat, occurrence in slots:
        if seat not in (native_seat, runner_seat):
            continue
        payload = tdi._payload_for(session_dir, state, pend, seat, [], head_path)
        if seat == runner_seat:
            order_path = round_records.order_prompt_path(
                session_dir, pend["round"], pend["phase"],
                round_records.storage_key(seat, occurrence), pend["attempt"],
            )
            run_dir = tdi._execution_run_dir(tmp_path, order_path, [])
            tdi._dispatch_observed_land(session_dir, state, pend, seat, payload, occurrence)
            out = RD.cmd_record_result(
                session_dir, seat, occurrence=occurrence, evidence_run_dir=run_dir)
        else:
            tdi._land(session_dir, state, pend, seat, payload, occurrence=occurrence)
            out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
        assert out["ok"], out
        stored, err = round_records.read_json(out["storePath"])
        assert err is None
        if seat == native_seat:
            evidence = stored.get("executionEvidence")
            if isinstance(evidence, dict):
                observation = evidence.get("observation")
                if isinstance(observation, dict):
                    stored = dict(stored)
                    stored["executionEvidence"] = dict(evidence)
                    stored["executionEvidence"]["observation"] = dict(observation)
                    stored["executionEvidence"]["observation"]["read"] = "engaged"
                    stored["executionEvidence"]["observation"]["telemetry"] = "tool-calls"
                    stored["executionEvidence"]["observation"]["toolCalls"] = 1
                    stored["envelopeSha256"] = round_records.envelope_sha256(
                        stored.get("payload"), stored.get("executionEvidence"))
        stored_by_seat[seat] = stored
        store_specs.append({"seat": seat, "envelope": stored})
    journal = RD.read_journal(session_dir)
    recorded = {
        row["seat"]: row
        for row in journal
        if row.get("outcome") == "recorded" and isinstance(row.get("seat"), str)
    }
    native_row = dict(recorded[native_seat])
    native_row.update(RD._journal_stored_revision(stored_by_seat[native_seat]))
    runner_row = dict(recorded[runner_seat])
    runner_row.update(RD._journal_stored_revision(stored_by_seat[runner_seat]))
    return native_row, runner_row, store_specs


def test_unprobed_native_seat_disclosure_at_receipt_boundary(tmp_path):
    native_seat = "architecture-reviewer"
    runner_seat = "code-reviewer"
    native_row, runner_row, envelopes = _driver_panel_recorded_rows(
        tmp_path, native_seat, runner_seat,
    )
    assert native_row[session_contract.SEAT_TRANSPORT_KEY] in (
        session_contract.SEAT_TRANSPORTS_DISCLOSED)
    assert runner_row[session_contract.SEAT_TRANSPORT_KEY] == session_contract.SEAT_TRANSPORT_RUNNER
    runner_row = dict(runner_row)
    runner_row["headSha"] = HEAD
    session_dir = write_certifiable_session(
        tmp_path,
        name="cert-native-boundary",
        journal_lines=[runner_row, native_row],
        envelopes=envelopes,
    )
    state = json.load(open(os.path.join(session_dir, RC.STATE_FILE), encoding="utf-8"))
    disclosure_line = (
        "unprobed native seat(s) %s: seats with no runner execution record — run in-session on "
        "the host model, fallen open to it, or landed by hand — are declared live, never "
        "probed; their engagement rests on the seat's own record"
    )
    cert_receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    degraded = cert_receipt.get("degraded") or []
    assert any(disclosure_line % native_seat in line for line in degraded)
    assert not any(
        line.startswith("unprobed native seat(s) %s" % runner_seat) for line in degraded
    )
    driver_receipt = RD.build_receipt(state, session_dir)
    driver_degraded = driver_receipt.get("degraded") or []
    assert any(disclosure_line % native_seat in line for line in driver_degraded)
    assert not any(
        line.startswith("unprobed native seat(s) %s" % runner_seat) for line in driver_degraded
    )


def _resolved_inputs_for_runner_seat(tmp_path, seat, order_path):
    """Mirror dispatch_review's _build_resolved_inputs call site (~6433)."""
    run_dir = str(tmp_path / "dispatch-evidence-run")
    repo_root = str(tmp_path / "dispatch-evidence-repo")
    staged_prompt = os.path.join(run_dir, engine_dispatch.PROMPT_NAME)
    progress_path = os.path.join(run_dir, "progress.jsonl")
    return engine_dispatch._build_resolved_inputs(
        seat=seat,
        role_kind=engine_dispatch.RUN_KIND_REVIEW,
        repo_root=repo_root,
        run_dir_real=run_dir,
        run_dir_source=riv.RESOLVED,
        staged_prompt_path=staged_prompt,
        timeout=30,
        timeout_source=riv.DEFAULT,
        retry_timeout=30,
        retry_timeout_source=riv.DEFAULT,
        max_wait=None,
        max_wait_source=riv.DEFAULT,
        preflight_timeout=None,
        preflight_timeout_source=riv.DECLARED_NONE,
        mode="review",
        mode_source=riv.DEFAULT,
        expected_result_kind="findings",
        expected_result_kind_source=riv.CALLER,
        base_sha=None,
        base_sha_source=riv.DECLARED_NONE,
        diff_base=None,
        diff_base_source=riv.DECLARED_NONE,
        progress_path=progress_path,
        progress_path_source=riv.RESOLVED,
        engine_model_opts={"cwd": repo_root},
    )


def _record_runner_seat_with_resolved_inputs(tmp_path, runner_seat):
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, name="runner-model-boundary")
    tdi._drive_to_phase(
        session_dir, gitdir, [tdi._blocking_finding("missing bounds guard", 2)],
        head_path, RC.PANEL_PHASE,
    )
    state = tdi._state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None
    slots = tdi._slots_of(roster)
    tdi._write_dispatch_manifest(session_dir, pend, slots, tdi._auditor_vendor_for(state))
    seat_spec = {
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "role": "reviewer-deep",
    }
    occurrence = 0
    for seat, occ in slots:
        if seat != runner_seat:
            continue
        occurrence = occ
        payload = tdi._payload_for(session_dir, state, pend, seat, [], head_path)
        order_path = round_records.order_prompt_path(
            session_dir, pend["round"], pend["phase"],
            round_records.storage_key(seat, occurrence), pend["attempt"],
        )
        snapshot = _resolved_inputs_for_runner_seat(tmp_path, seat_spec, order_path)
        assert snapshot["engineModel"] == "gpt-5.6-sol"
        run_dir = tdi._execution_run_dir(
            tmp_path, order_path, [], resolved_inputs=snapshot,
        )
        tdi._dispatch_observed_land(session_dir, state, pend, seat, payload, occurrence)
        out = RD.cmd_record_result(
            session_dir, seat, occurrence=occurrence, evidence_run_dir=run_dir,
        )
        assert out["ok"], out
        stored, err = round_records.read_json(out["storePath"])
        assert err is None
        journal = RD.read_journal(session_dir)
        recorded_row = next(
            row for row in journal
            if row.get("outcome") == "recorded" and row.get("seat") == seat
        )
        return session_dir, recorded_row, stored
    pytest.fail("runner seat %r not in roster slots" % runner_seat)


# axis: receipt seat model comes from the runner's execution record, not the seat map pin.
def test_receipt_seat_model_is_the_runner_records_engine_model(tmp_path):
    runner_seat = "code-reviewer"
    _session_dir, recorded_row, stored = _record_runner_seat_with_resolved_inputs(
        tmp_path, runner_seat,
    )
    assert recorded_row[session_contract.SEAT_TRANSPORT_KEY] == session_contract.SEAT_TRANSPORT_RUNNER
    assert recorded_row["executionEvidence"]["engineModel"] == "gpt-5.6-sol"
    runner_row = dict(recorded_row)
    runner_row.update(RD._journal_stored_revision(stored))
    runner_row["headSha"] = HEAD
    seat_cfg = {
        "vendor": "codex",
        "model": "gpt-6-astra",
        "tier": "reviewer-deep",
    }
    session_dir = write_certifiable_session(
        tmp_path,
        name="runner-model-receipt",
        state={
            "seatMapReceipts": [{"round": "1", "map": {"seats": {runner_seat: dict(seat_cfg)}}}],
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "seatMap": {"seats": {runner_seat: dict(seat_cfg)}},
            },
        },
        journal_lines=[runner_row],
        envelopes=[{"seat": runner_seat, "envelope": stored}],
    )
    receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    row = next(item for item in receipt["seats"] if item["seat"] == runner_seat)
    assert row["model"] == "gpt-5.6-sol"
    assert all(item.get("model") != "gpt-6-astra" for item in receipt["seats"])


# axis: hand-landed transport suppresses receipt model even when journal evidence carries engineModel.
def test_receipt_seat_model_none_for_hand_landed_record_carrying_a_model(tmp_path):
    seat = "code-reviewer"
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, name="hand-landed-model-boundary")
    tdi._drive_to_phase(
        session_dir, gitdir, [tdi._blocking_finding("missing bounds guard", 2)],
        head_path, RC.PANEL_PHASE,
    )
    state = tdi._state(session_dir)
    pend = state["pending"]
    payload = tdi._payload_for(session_dir, state, pend, seat, [], head_path)
    tdi._land(session_dir, state, pend, seat, payload)
    landing_path = round_records.landing_path(
        session_dir, pend["round"], pend["phase"],
        round_records.storage_key(seat, 0), pend["attempt"],
    )
    stored, err = round_records.read_json(landing_path)
    assert err is None
    evidence = dict(stored.get("executionEvidence") or {})
    evidence["engineModel"] = "gpt-6-astra"
    stored = dict(stored)
    stored["executionEvidence"] = evidence
    stored["envelopeSha256"] = round_records.envelope_sha256(
        stored.get("payload"), evidence,
    )
    round_records.atomic_write_json(landing_path, stored)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"], out
    journal = RD.read_journal(session_dir)
    recorded_row = next(
        row for row in journal
        if row.get("outcome") == "recorded" and row.get("seat") == seat
    )
    assert recorded_row[session_contract.SEAT_TRANSPORT_KEY] == session_contract.SEAT_TRANSPORT_HAND_LANDED
    assert recorded_row["executionEvidence"]["engineModel"] == "gpt-6-astra"
    durable, err = round_records.read_json(out["storePath"])
    assert err is None
    evidence = durable.get("executionEvidence")
    if isinstance(evidence, dict):
        observation = evidence.get("observation")
        if isinstance(observation, dict):
            durable = dict(durable)
            durable["executionEvidence"] = dict(evidence)
            durable["executionEvidence"]["observation"] = dict(observation)
            durable["executionEvidence"]["observation"]["read"] = "engaged"
            durable["executionEvidence"]["observation"]["telemetry"] = "tool-calls"
            durable["executionEvidence"]["observation"]["toolCalls"] = 1
            durable["envelopeSha256"] = round_records.envelope_sha256(
                durable.get("payload"), durable.get("executionEvidence"),
            )
    journal_row = dict(recorded_row)
    journal_row.update(RD._journal_stored_revision(durable))
    journal_row["headSha"] = HEAD
    cert_dir = write_certifiable_session(
        tmp_path,
        name="hand-landed-model-receipt",
        journal_lines=[journal_row],
        envelopes=[{"seat": seat, "envelope": durable}],
    )
    receipt, refusal = RC.certify(cert_dir)
    assert refusal is None, refusal
    row = next(item for item in receipt["seats"] if item["seat"] == seat)
    assert row["model"] is None


def test_materialized_session_preserves_checked_base_guard(tmp_path):
    session_dir = write_certifiable_session(
        tmp_path,
        name="checked-guard",
        state={"config": {"fixerVendor": "claude", "baseGuard": RC.BASE_GUARD_CHECKED, "headSha": HEAD}},
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    with open(os.path.join(session_dir, RC.STATE_FILE), encoding="utf-8") as fh:
        state = json.load(fh)
    materialized = RD._materialize_run_loop_session(state, 1, source_session_dir=session_dir)
    try:
        with open(os.path.join(materialized, RC.STATE_FILE), encoding="utf-8") as fh:
            materialized_state = json.load(fh)
        assert materialized_state["config"]["baseGuard"] == RC.BASE_GUARD_CHECKED
        from round_certification_fixtures import _head_content_blobs_for_findings, _write_head_content_blobs

        blobs = _head_content_blobs_for_findings(materialized_state.get("findings") or [])
        if blobs is None:
            blobs = _head_content_blobs_for_findings(
                [{"id": "F1", "file": "a.py", "disposition": "fixed"}]
            )
        _write_head_content_blobs(materialized, blobs)
        receipt, refusal = RC.certify(materialized)
        assert refusal is None, refusal
        assert receipt["baseGuard"] == RC.BASE_GUARD_CHECKED
    finally:
        import shutil

        shutil.rmtree(materialized, ignore_errors=True)
