#!/usr/bin/env python3
"""#977 — the record-submit interleave fence and advance manifest disclosure.

Real driver, real adapters, real session dir — same discipline as
`test_round_driver_integration.py`. Reuses that module's harness helpers.
"""
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
import round_records  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_bootstrap = _TDI._bootstrap
_land = _TDI._land
_write_dispatch_manifest = _TDI._write_dispatch_manifest
_slots_of = _TDI._slots_of
_payload_for = _TDI._payload_for
_blocking_finding = _TDI._blocking_finding
_state = _TDI._state
_fake_git = _TDI._fake_git
_drive_to_phase = _TDI._drive_to_phase
_auditor_vendor_for = _TDI._auditor_vendor_for


def _panel_hand_artifact(session_dir):
    dims = round_driver._panel_dimensions(_state(session_dir)["config"])
    return {"seats": {dim: {"findings": [], "confidence": "high", "tier": round_driver.DEEP}
                      for dim in dims}}


def _land_panel_and_sweep(session_dir, gitdir, head_path, panel_findings=None):
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == round_driver.P_PANEL
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    findings = panel_findings if panel_findings is not None else []
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, findings, head_path),
              occurrence=occurrence)
    out = round_driver.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is True, out
    return pend, slots, out


def test_hand_submit_refused_after_record_sweep_pending_unchanged(tmp_path):
    """record-result --sweep then hand submit → record-submit-interleaved; pending survives."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, _slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    before = _state(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(before), _panel_hand_artifact(session_dir))
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    assert "advance" in out.get("detail", "")
    after = _state(session_dir)
    assert after["pending"] == before["pending"]
    assert after.get("_incompletePanel") is not True
    assert after["step"] == round_driver.P_PANEL


def test_hand_submit_without_store_records_still_folds(tmp_path):
    """Clean hand-submit round with no durable records is unchanged."""
    session_dir, _gitdir, _head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    art = _panel_hand_artifact(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), art)
    assert out["ok"] is True, out
    assert _state(session_dir)["step"] == round_driver.P_VERIFIERS


def test_stale_attempt_store_does_not_fire_fence(tmp_path):
    """A store record at attempt K while pending is K+1 leaves hand submit permitted."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, _slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["pending"] = dict(state["pending"], attempt=pend["attempt"] + 1)
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    art = _panel_hand_artifact(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], state["pending"]["attempt"],
                                  round_driver.state_hash(state), art)
    assert out["ok"] is True, out


def test_corrupt_store_file_at_pending_attempt_fires_fence(tmp_path):
    """Existence probe: unreadable JSON at the pending attempt still refuses hand submit."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    seat, occurrence = slots[0]
    spath = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(seat, occurrence), pend["attempt"])
    with open(spath, "w", encoding="utf-8") as fh:
        fh.write("[not-a-dict]")
    state = _state(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), _panel_hand_artifact(session_dir))
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out


def test_advance_still_folds_with_records_present(tmp_path):
    """_via_advance=True exempts the record path from the fence."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    _land_panel_and_sweep(session_dir, gitdir, head_path,
                          [_blocking_finding("missing bounds guard", 2)])
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_PANEL


def test_repeated_seat_key_second_occurrence_probed_by_slot(tmp_path):
    """Two roster slots sharing one seat key: a record on occurrence 1 fires the fence."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)
    state = _state(session_dir)
    targets = list(state["_auditTargets"])
    shared_id = targets[0]["id"]
    dup = dict(targets[1])
    dup["id"] = shared_id
    state["_auditTargets"] = [targets[0], dup]
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    pend = state["pending"]
    slots = [(shared_id, 0), (shared_id, 1)]
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    _land(session_dir, state, pend, shared_id,
          {"id": shared_id, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"},
          occurrence=1)
    assert round_driver.cmd_record_result(session_dir, shared_id, occurrence=1)["ok"] is True
    state = _state(session_dir)
    out = round_driver.cmd_submit(
        session_dir, pend["phase"], pend["attempt"], round_driver.state_hash(state),
        {"results": [{"id": shared_id, "ruling": "discharged", "reason": "ok"},
                     {"id": shared_id, "ruling": "discharged", "reason": "ok"}]})
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    assert "%s#1" % shared_id in out.get("seats", []), out


def test_advance_reports_absent_dispatch_manifest_via_cmd_advance(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    expected = os.path.abspath(round_records.dispatch_manifest_path(
        session_dir, pend["round"], pend["phase"], pend["attempt"]))
    assert not os.path.exists(expected)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    disc = out.get("dispatchManifest")
    assert disc == {"path": expected, "status": "absent", "detail": None}, disc


def test_advance_reports_unreadable_dispatch_manifest(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    mpath = round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                                 pend["attempt"])
    os.makedirs(os.path.dirname(mpath), exist_ok=True)
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write("not json")
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    disc = out.get("dispatchManifest")
    assert disc["status"] == "unreadable", disc
    assert disc["path"] == os.path.abspath(mpath)
    assert disc["detail"] == "unparseable"
