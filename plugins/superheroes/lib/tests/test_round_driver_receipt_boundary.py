"""Driver-side receipt boundary tests."""
import importlib.util
import inspect
import json
import os
import sys

import engine_dispatch
import model_registry
import pytest
import resolved_inputs_vocab as riv
import round_adapters
import round_records
import session_contract

import round_driver as RD
from session_fixture_support import (
    HEAD_SHA,
    write_certifiable_session,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"),
)
tdi = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tdi)

_CODEX_REVIEWER_DEEP_MODEL, _CODEX_REVIEWER_DEEP_EFFORT = model_registry.matrix_config(
    "reviewer-deep", "codex"
)

HEAD = HEAD_SHA


def _stored_revision(envelope, cited_head=None):
    """What a `recorded` row carries for a stored envelope: the chokepoint's revision identity
    (``round_records.recorded_row_fields``) plus the journal transport stamp."""
    fields = round_records.recorded_row_fields(
        envelope, cited_head, round_records.stored_cited_head_source(envelope))
    fields.update(RD._journal_transport_fields(envelope))
    return fields


def _stored_with_engaged_observation(stored):
    """Certification refuses before model assertion unless observation.read is engaged."""
    evidence = stored.get("executionEvidence")
    if not isinstance(evidence, dict):
        return stored
    observation = evidence.get("observation")
    if not isinstance(observation, dict):
        return stored
    out = dict(stored)
    out["executionEvidence"] = dict(evidence)
    out["executionEvidence"]["observation"] = dict(observation)
    out["executionEvidence"]["observation"]["read"] = "engaged"
    out["executionEvidence"]["observation"]["telemetry"] = "tool-calls"
    out["executionEvidence"]["observation"]["toolCalls"] = 1
    out["envelopeSha256"] = round_records.envelope_sha256(
        out.get("payload"), out.get("executionEvidence"),
    )
    return out


def test_journal_execution_evidence_fields_copies_optional_engine_model():
    evidence = {
        "source": "runner",
        "runnerNonce": "nonce-1",
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
        "observation": {"read": "engaged"},
        "engineModel": _CODEX_REVIEWER_DEEP_MODEL,
    }
    copied = RD._journal_execution_evidence_fields(evidence)
    assert copied["engineModel"] == _CODEX_REVIEWER_DEEP_MODEL
    without_optional = dict(evidence)
    del without_optional["engineModel"]
    copied_without = RD._journal_execution_evidence_fields(without_optional)
    assert "engineModel" not in copied_without


def _driver_panel_recorded_rows(tmp_path, native_seat, runner_seat):
    """Two panel seats recorded through the real driver path with distinct transports."""
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, name="driver-native-boundary")
    tdi._drive_to_phase(
        session_dir, gitdir, [tdi._blocking_finding("missing bounds guard", 2)],
        head_path, session_contract.PANEL_PHASE,
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
            run_dir = tdi._execution_run_dir(
                tmp_path, order_path, [],
                view_head_sha=RD._anchor_cited_head(state, session_dir, pend["round"], pend["phase"], pend["attempt"]))
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
            stored = _stored_with_engaged_observation(stored)
        stored_by_seat[seat] = stored
        store_specs.append({"seat": seat, "envelope": stored})
    journal = RD.read_journal(session_dir)
    recorded = {
        row["seat"]: row
        for row in journal
        if row.get("outcome") == "recorded" and isinstance(row.get("seat"), str)
    }
    native_row = dict(recorded[native_seat])
    native_row.update(_stored_revision(stored_by_seat[native_seat], native_row.get("citedHead")))
    runner_row = dict(recorded[runner_seat])
    runner_row.update(_stored_revision(stored_by_seat[runner_seat], runner_row.get("citedHead")))
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
    state = json.load(open(os.path.join(session_dir, session_contract.STATE_FILE), encoding="utf-8"))
    disclosure_line = (
        "unprobed native seat(s) %s: seats with no runner execution record — run in-session on "
        "the host model, fallen open to it, or landed by hand — are declared live, never "
        "probed; their engagement rests on the seat's own record"
    )
    driver_receipt = RD.build_receipt(state, session_dir)
    driver_degraded = driver_receipt.get("degraded") or []
    assert any(disclosure_line % native_seat in line for line in driver_degraded)
    assert not any(
        line.startswith("unprobed native seat(s) %s" % runner_seat) for line in driver_degraded
    )


def _resolved_inputs_for_runner_seat(tmp_path, seat):
    """Mirror engine_dispatch._build_resolved_inputs call site for runner evidence."""
    run_dir = str(tmp_path / "dispatch-evidence-run")
    repo_root = str(tmp_path / "dispatch-evidence-repo")
    staged_prompt = os.path.join(run_dir, engine_dispatch.PROMPT_NAME)
    progress_path = os.path.join(run_dir, "progress.jsonl")
    kwargs = {
        "seat": seat,
        "role_kind": engine_dispatch.RUN_KIND_REVIEW,
        "repo_root": repo_root,
        "run_dir_real": run_dir,
        "run_dir_source": riv.RESOLVED,
        "staged_prompt_path": staged_prompt,
        "timeout": 30,
        "timeout_source": riv.DEFAULT,
        "retry_timeout": 30,
        "retry_timeout_source": riv.DEFAULT,
        "max_wait": None,
        "max_wait_source": riv.DEFAULT,
        "preflight_timeout": None,
        "preflight_timeout_source": riv.DECLARED_NONE,
        "mode": "review",
        "mode_source": riv.DEFAULT,
        "expected_result_kind": "findings",
        "expected_result_kind_source": riv.CALLER,
        "base_sha": None,
        "base_sha_source": riv.DECLARED_NONE,
        "diff_base": None,
        "diff_base_source": riv.DECLARED_NONE,
        "progress_path": progress_path,
        "progress_path_source": riv.RESOLVED,
        "engine_model_opts": {"cwd": repo_root},
    }
    sig = inspect.signature(engine_dispatch._build_resolved_inputs)
    passed = set(kwargs)
    required = {
        name for name, param in sig.parameters.items()
        if param.default is inspect.Parameter.empty
    }
    optional_deliberately_passed = set()
    assert passed == required | optional_deliberately_passed, (
        "kwargs %r do not match _build_resolved_inputs signature %r"
        % (sorted(passed), sorted(sig.parameters))
    )
    return engine_dispatch._build_resolved_inputs(**kwargs)


def _record_runner_seat_with_resolved_inputs(tmp_path, runner_seat):
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, name="runner-model-boundary")
    tdi._drive_to_phase(
        session_dir, gitdir, [tdi._blocking_finding("missing bounds guard", 2)],
        head_path, session_contract.PANEL_PHASE,
    )
    state = tdi._state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None
    slots = tdi._slots_of(roster)
    tdi._write_dispatch_manifest(session_dir, pend, slots, tdi._auditor_vendor_for(state))
    seat_spec = {
        "vendor": "codex",
        "model": _CODEX_REVIEWER_DEEP_MODEL,
        "effort": _CODEX_REVIEWER_DEEP_EFFORT,
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
        snapshot = _resolved_inputs_for_runner_seat(tmp_path, seat_spec)
        assert snapshot["engineModel"] == _CODEX_REVIEWER_DEEP_MODEL
        run_dir = tdi._execution_run_dir(
            tmp_path, order_path, [], resolved_inputs=snapshot,
            view_head_sha=RD._anchor_cited_head(state, session_dir, pend["round"], pend["phase"], pend["attempt"]),
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


# axis: the driver stamps the runner transport and the runner's engine model on the recorded row.
def test_runner_seat_record_carries_runner_transport_and_engine_model(tmp_path):
    runner_seat = "code-reviewer"
    _session_dir, recorded_row, _stored = _record_runner_seat_with_resolved_inputs(
        tmp_path, runner_seat,
    )
    assert recorded_row[session_contract.SEAT_TRANSPORT_KEY] == session_contract.SEAT_TRANSPORT_RUNNER
    assert recorded_row["executionEvidence"]["engineModel"] == _CODEX_REVIEWER_DEEP_MODEL


# axis: a hand-landed record is stamped hand-landed even when its evidence carries engineModel.
def test_hand_landed_record_carrying_a_model_is_stamped_hand_landed(tmp_path):
    seat = "code-reviewer"
    session_dir, gitdir, head_path = tdi._bootstrap(tmp_path, name="hand-landed-model-boundary")
    tdi._drive_to_phase(
        session_dir, gitdir, [tdi._blocking_finding("missing bounds guard", 2)],
        head_path, session_contract.PANEL_PHASE,
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
