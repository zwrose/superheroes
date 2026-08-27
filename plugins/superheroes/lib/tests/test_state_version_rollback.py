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
    assert loaded["schemaVersion"] == version
    assert set(loaded) == set(payload)


def test_legacy_refusal_plain_session_names_next_submit(tmp_path):
    """A legacy session without durable pending records names ``next``/``submit`` recovery."""
    session_dir, gitdir, _head_path = _legacy_v3_session(tmp_path, name="legacy-plain")
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == RD.LEGACY_SESSION_REFUSAL
    assert "`next`/`submit`" in out.get("detail", "")
    assert "fresh session" not in out.get("detail", "")


def test_next_and_submit_still_finish_a_v3_session_unchanged(tmp_path):
    """`next`/`submit` finish an in-flight v3 session and leave schemaVersion at 3."""
    session_dir, _gitdir, _head_path = _bootstrap(tmp_path, name="v3-continuation")
    state = _state(session_dir)
    state["schemaVersion"] = 3
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    pend = RD.cmd_next(session_dir)
    assert pend["ok"] and pend["phase"] == RD.P_PANEL
    seats = {dim: {"findings": []} for dim in RD.DIMENSIONS}
    out = RD.cmd_submit(session_dir, pend["phase"], pend["attempt"], pend["expectedStateHash"],
                        {"seats": seats})
    assert out["ok"] is True
    assert _state(session_dir)["schemaVersion"] == 3


def test_legacy_refusal_durable_records_names_fresh_session(tmp_path):
    """A legacy session with durable pending records names a fresh session dir, not hand submit."""
    session_dir, gitdir, _head_path = _legacy_v3_session(
        tmp_path, name="legacy-durable", land_records=True)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == RD.LEGACY_SESSION_REFUSAL
    detail = out.get("detail", "")
    assert "fresh session" in detail
    assert "record-submit-interleaved" in detail
    assert "`next`/`submit`" not in detail
