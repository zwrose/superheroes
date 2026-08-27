#!/usr/bin/env python3
"""#1177-A — every receipt round entry carries verifyPasses when the form permits the channel."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters  # noqa: E402
import round_driver  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_bootstrap = _TDI._bootstrap
_land = _TDI._land
_write_dispatch_manifest = _TDI._write_dispatch_manifest
_slots_of = _TDI._slots_of
_payload_for_base = _TDI._payload_for
_auditor_vendor_for = _TDI._auditor_vendor_for
_blocking_finding = _TDI._blocking_finding
_state = _TDI._state
_fake_git = _TDI._fake_git

# axis: every emitted round on v3-certified/attested/interim receipts must carry verifyPasses as a list.
# Bite-proof: WO 1177-A — always-emit rule and v2 form gate; durable build record.


def _payload_for(session_dir, state, pend, seat, panel_findings, head_diff_path):
    """Round-2 scoped-finder surfaces a blocking finding so the session reaches ≥3 rounds."""
    if pend["phase"] == round_driver.P_SCOPED and state["round"] == 2:
        return {"findings": [_blocking_finding("delta scoped issue", 2)]}
    return _payload_for_base(session_dir, state, pend, seat, panel_findings, head_diff_path)


def _drive_phase_with_sweep(session_dir, gitdir, head_path, panel_findings):
    state = _state(session_dir)
    pend = state["pending"]
    phase = pend["phase"]
    roster, reason = round_adapters.roster_for(phase, state, state.get("config") or {})
    assert reason is None, (phase, reason)
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        payload = _payload_for(session_dir, state, pend, seat, panel_findings, head_path)
        _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
    sweep = round_driver.cmd_record_result(session_dir, sweep=True)
    assert sweep["ok"] is True, (phase, sweep)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    return phase, out


def _drive_sweep_to_terminal(session_dir, gitdir, head_path, panel_findings, max_steps=48):
    for _ in range(max_steps):
        if _state(session_dir).get("terminal"):
            return
        phase, out = _drive_phase_with_sweep(session_dir, gitdir, head_path, panel_findings)
        assert out["ok"] is True, (phase, out)
    raise AssertionError("did not reach terminal within %d steps" % max_steps)


def _terminal_receipt(session_dir):
    with open(os.path.join(session_dir, round_driver.RECEIPT_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude"], "diff": _TDI.REVIEWED_DIFF,
            "fixerVendor": "claude", "verifyCommand": "none", "seatMap": _TDI.SEAT_MAP}
    base.update(over)
    return base


def _certified_v3_spine(rounds):
    return {
        "schemaVersion": 3,
        "schema": round_driver.RECEIPT_CERTIFIED_SCHEMA % 3,
        "verdict": "converged",
        "certificationShape": "audited-chain",
        "certification": {"shape": "audited-chain"},
        "scriptRan": {"byPhase": {}, "invocations": 1},
        "seatMap": {},
        "rounds": rounds,
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }


def _attested_spine(rounds):
    return {
        "schema": round_driver.RECEIPT_ATTESTED_SCHEMA,
        "verdict": round_driver.ATTESTED_VERDICT,
        "attestation": {"by": "owner"},
        "scriptRan": {"byPhase": {}, "invocations": 1},
        "seatMap": {},
        "artifacts": {"session/x": "abc"},
        "roster": {"test-reviewer": "recorded"},
        "rounds": rounds,
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }


def _interim_spine(rounds):
    return {
        "schema": round_driver.RECEIPT_INTERIM_SCHEMA,
        "stop": {"reason": "park", "writtenAt": "2026-08-26T00:00:00"},
        "scriptRan": {"byPhase": {}, "invocations": 1},
        "seatMap": {},
        "rounds": rounds,
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }


def test_terminal_receipt_verify_passes_invariant(tmp_path):
    """DoD: every round entry on the terminal receipt carries verifyPasses as a list."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, maxRounds=8)
    panel_findings = [_blocking_finding("missing bounds guard", 2)]
    _drive_sweep_to_terminal(session_dir, gitdir, head_path, panel_findings)

    state = _state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    receipt = _terminal_receipt(session_dir)
    rounds = receipt.get("rounds") or []
    assert len(rounds) >= 3, ("need ≥3 rounds to exercise empty and non-empty verifyPasses; got %d"
                              % len(rounds))

    with_key = [rd for rd in rounds if isinstance(rd, dict) and "verifyPasses" in rd]
    assert len(with_key) == len(rounds), (
        "verifyPasses must be present on every round entry (%d/%d)"
        % (len(with_key), len(rounds)))
    for rd in rounds:
        assert isinstance(rd, dict)
        assert "verifyPasses" in rd
        assert isinstance(rd["verifyPasses"], list)

    non_empty = [rd for rd in rounds if rd["verifyPasses"]]
    empty = [rd for rd in rounds if not rd["verifyPasses"]]
    assert non_empty, "expected at least one round with a non-empty verifyPasses list"
    assert empty, "expected at least one round with an empty verifyPasses list"


def test_v2_certified_receipt_omits_verify_passes(tmp_path):
    """v2 certified receipts must not emit verifyPasses even when the round recorded a list."""
    import verification
    state = round_driver.new_state(_cfg())
    state["schemaVersion"] = 2
    f = _blocking_finding("issue", 1)
    staged = verification.stage_ids([f])
    state["_toVerify"] = staged
    round_driver._fold_verifiers(
        state, state["config"],
        {"verdicts": [{"id": staged[0]["id"], "verdict": "CONFIRMED", "evidence": "ran"}]})
    assert state["rounds"]["1"]["verifyPasses"]
    receipt = round_driver.build_receipt(state, str(tmp_path))
    assert receipt["schemaVersion"] == 2
    assert "verifyPasses" not in receipt["rounds"][0]


def test_terminal_receipt_validates(tmp_path):
    """validate_receipt accepts the multi-round terminal receipt."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, maxRounds=8)
    _drive_sweep_to_terminal(session_dir, gitdir, head_path,
                            [_blocking_finding("missing bounds guard", 2)])
    receipt = _terminal_receipt(session_dir)
    ok, reason = round_driver.validate_receipt(receipt)
    assert ok is True, reason


@pytest.mark.parametrize("bad_entry", [None, "not-an-object", 42])
@pytest.mark.parametrize("form,spine_fn", [
    ("certified-v3", _certified_v3_spine),
    ("attested", _attested_spine),
    ("interim", _interim_spine),
])
def test_validator_refuses_non_object_round_entries(form, spine_fn, bad_entry):
    """Applicable forms refuse non-object round entries without conflating missing/malformed."""
    receipt = spine_fn([bad_entry])
    ok, reason = round_driver.validate_receipt(receipt)
    assert ok is False, (form, bad_entry, reason)
    assert "not an object" in reason
    assert "missing" not in reason
    assert "must be a list" not in reason


@pytest.mark.parametrize("form,spine_fn", [
    ("certified-v3", _certified_v3_spine),
    ("attested", _attested_spine),
    ("interim", _interim_spine),
])
def test_validator_refuses_missing_or_malformed_verify_passes(form, spine_fn):
    """Applicable forms refuse round entries missing verifyPasses or carrying a non-list."""
    base_round = {"round": 1, "kind": "baseline", "verifyPasses": [{"CONFIRMED": 1}]}
    missing = spine_fn([{"round": 1, "kind": "baseline"}])
    ok, reason = round_driver.validate_receipt(missing)
    assert ok is False, (form, reason)
    assert "verifyPasses" in reason
    assert "missing" in reason
    assert "must be a list" not in reason

    for malformed in ({"CONFIRMED": 1}, "not-a-list"):
        bad = spine_fn([dict(base_round, verifyPasses=malformed)])
        ok, reason = round_driver.validate_receipt(bad)
        assert ok is False, (form, malformed, reason)
        assert "verifyPasses" in reason
        assert "must be a list" in reason
        assert "missing" not in reason


def test_validator_accepts_certified_v2_without_verify_passes():
    """Certified v2 receipts without verifyPasses on rounds remain valid."""
    receipt = {
        "schemaVersion": 2,
        "verdict": "converged",
        "certificationShape": "audited-chain",
        "certification": {"shape": "audited-chain"},
        "scriptRan": {"byPhase": {}, "invocations": 1},
        "seatMap": {},
        "rounds": [{"round": 1, "kind": "baseline"}],
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }
    ok, reason = round_driver.validate_receipt(receipt)
    assert ok is True, reason
