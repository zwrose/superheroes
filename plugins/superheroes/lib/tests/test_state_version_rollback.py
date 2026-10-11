#!/usr/bin/env python3
"""#1185 — rollback refusal and hash-preserving load for STATE_SCHEMA_VERSION bump."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402

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
_auditor_vendor_for = _TDI._auditor_vendor_for
_state = _TDI._state
_fake_git = _TDI._fake_git


def _legacy_v3_session(tmp_path, name="legacy-v3", *, land_records=False):
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name=name)
    if land_records:
        _land_panel_records(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["schemaVersion"] = 3
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    return session_dir, gitdir, head_path


def _land_panel_records(session_dir, gitdir, head_path):
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == RD.P_PANEL
    roster, reason = __import__("round_adapters").roster_for(
        pend["phase"], state, state.get("config") or {})
    assert reason is None, reason
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        payload = _payload_for(session_dir, state, pend, seat, [], head_path)
        _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
    sweep = RD.cmd_record_result(session_dir, sweep=True)
    assert sweep["ok"] is True, sweep


def test_rollback_reader_refuses_schema_version_4(tmp_path, monkeypatch):
    """A v3-vintage reader (SUPPORTED_STATE_VERSIONS=(2, 3)) truthfully refuses schemaVersion 4."""
    monkeypatch.setattr(RD, "SUPPORTED_STATE_VERSIONS", (2, 3))
    d = str(tmp_path / "v4")
    os.makedirs(d)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 4, "rounds": {}}, fh)
    ok, reason = RD.load_state(d)
    assert ok is False
    assert isinstance(reason, str)
    assert "4" in reason
    assert "2" in reason and "3" in reason
    assert "not one of" in reason


@pytest.mark.parametrize("version", [2, 3, 4])
def test_load_state_accepts_supported_versions_unchanged(tmp_path, version):
    """The current reader accepts 2, 3, and 4 and returns schemaVersion exactly as persisted."""
    d = str(tmp_path / ("v%d" % version))
    os.makedirs(d)
    payload = {"schemaVersion": version, "rounds": {}, "round": 1}
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    ok, loaded = RD.load_state(d)
    assert ok is True
    # Full-value equality (#1194 FU6): a reader that rewrites any persisted VALUE — not just one
    # that adds or drops a key — must go red here.
    assert loaded == payload


def _finish(session_dir):
    """Mark the saved state as finished: it carries a terminal answer."""
    state = _state(session_dir)
    state["terminal"] = "converged"
    RD.save_state(session_dir, state)


def _assert_legacy_refusal(out):
    assert out["ok"] is False
    assert out["reason"] == RD.LEGACY_SESSION_REFUSAL
    assert out.get("detail") == RD.LEGACY_SESSION_REFUSAL_DETAIL
    assert "earlier plugin version" in out["detail"]
    assert "finished" in out["detail"]
    assert "fresh session" in out["detail"]


def test_unfinished_legacy_session_is_refused_by_the_upgrade_gate(tmp_path):
    """An unfinished earlier-schema session never reaches the hand command: the upgrade gate
    refuses it first."""
    session_dir, gitdir, _head_path = _legacy_v3_session(tmp_path, name="legacy-unfinished")
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == RD.SESSION_FROM_EARLIER_VERSION


def test_finished_legacy_session_refusal_names_a_fresh_session(tmp_path):
    """A finished earlier-schema session answers the hand command with one fixed detail."""
    session_dir, gitdir, _head_path = _legacy_v3_session(tmp_path, name="legacy-plain")
    _finish(session_dir)
    _assert_legacy_refusal(RD.cmd_advance(session_dir, git=_fake_git(gitdir)))


@pytest.mark.parametrize("land_records", [False, True], ids=["plain", "durable-records"])
@pytest.mark.parametrize("advance_latched", [False, True], ids=["unlatched", "advance-latched"])
def test_finished_legacy_refusal_detail_does_not_depend_on_the_session(
        tmp_path, land_records, advance_latched):
    """Durable records at the pending slot and an advance latch change nothing: one detail."""
    session_dir, gitdir, _head_path = _legacy_v3_session(
        tmp_path, name="legacy-%s-%s" % (land_records, advance_latched), land_records=land_records)
    state = _state(session_dir)
    state["terminal"] = "converged"
    if advance_latched:
        state["_advanceUsed"] = True
    RD.save_state(session_dir, state)
    _assert_legacy_refusal(RD.cmd_advance(session_dir, git=_fake_git(gitdir)))
