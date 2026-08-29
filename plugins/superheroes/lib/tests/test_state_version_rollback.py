#!/usr/bin/env python3
"""#1185 — rollback refusal and hash-preserving load for STATE_SCHEMA_VERSION bump."""
import copy
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

_SPEC_TRD = importlib.util.spec_from_file_location(
    "test_round_driver",
    os.path.join(_HERE, "test_round_driver.py"))
_TRD = importlib.util.module_from_spec(_SPEC_TRD)
_SPEC_TRD.loader.exec_module(_TRD)

_bootstrap = _TDI._bootstrap
_land = _TDI._land
_write_dispatch_manifest = _TDI._write_dispatch_manifest
_slots_of = _TDI._slots_of
_payload_for = _TDI._payload_for
_auditor_vendor_for = _TDI._auditor_vendor_for
_state = _TDI._state
_fake_git = _TDI._fake_git

# A frozen pre-#681 v3 session: top-level ``seatMap``, no ``seatMapReceipts``. Hash pinned so a
# drift in the representative fixture fails loudly instead of silently relabelling a v4 bootstrap.
PRE_681_V3_DIFF = _TRD.DIFF
PRE_681_V3_SEAT_MAP = {
    "seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
              for dim in RD.DIMENSIONS}
}
PRE_681_V3_INITIAL = {
    "schemaVersion": 3,
    "config": {"leg": "code", "panel": False, "code": True, "vendors": ["claude", "codex"],
               "fixerVendor": "claude", "verifyCommand": "none", "maxRounds": 7,
               "maxRoundsAbsolute": 7, "dimensions": list(RD.DIMENSIONS),
               "recordsPath": None, "coveragePath": None, "priorComments": None,
               "seatMap": PRE_681_V3_SEAT_MAP, "diff": PRE_681_V3_DIFF},
    "round": 1, "step": RD.P_PANEL, "pending": None, "lastAccepted": None,
    "rounds": {}, "findings": [], "decisions": [], "auditRounds": [],
    "confirmations": 0, "selfRecovered": False, "independenceDegraded": False,
    "seatMap": dict(PRE_681_V3_SEAT_MAP), "reviewedDiff": PRE_681_V3_DIFF,
    "headDiff": None, "fixBatch": [], "fullPanelRan": False, "_incompletePanel": False,
    "_changedSubjectsSincePanel": [], "terminal": None, "certification": None,
    "_records": [], "_coverage": [], "_resumeCorrupt": None,
}
PRE_681_V3_INITIAL_HASH = (
    "caaadfcf13bfbe182510e3976e760f12d03f752dec1c465954ecc58933c5dac9")


def _seed_pre681_v3_session(tmp_path, name="pre681-v3"):
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    state = copy.deepcopy(PRE_681_V3_INITIAL)
    assert RD.state_hash(state) == PRE_681_V3_INITIAL_HASH
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    return session_dir


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


def test_legacy_refusal_plain_session_names_next_submit(tmp_path):
    """A legacy session without durable pending records names ``next``/``submit`` recovery."""
    session_dir, gitdir, _head_path = _legacy_v3_session(tmp_path, name="legacy-plain")
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == RD.LEGACY_SESSION_REFUSAL
    assert "`next`/`submit`" in out.get("detail", "")
    assert "fresh session" not in out.get("detail", "")


def test_next_and_submit_still_finish_a_v3_session_unchanged(tmp_path):
    """`next`/`submit` finish a genuine pre-#681 v3 session through a terminal receipt."""
    session_dir = _seed_pre681_v3_session(tmp_path)
    _TRD._drive_cli(session_dir, None, _TRD._responder(round1_findings=None))
    state = _state(session_dir)
    assert state["schemaVersion"] == 3
    # v3 hand-submit: journal backstop withholds certification when dispatch-* seats folded.
    assert state["terminal"] == "cannot-certify"
    with open(os.path.join(session_dir, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["schemaVersion"] == 3
    assert RD.receipt_kind(receipt) == RD.RECEIPT_CERTIFIED_SCHEMA % 3
    ok, why = RD.validate_receipt(receipt)
    assert ok, why


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


def test_legacy_refusal_advance_latched_names_fresh_session(tmp_path):
    """An advance-latched legacy session with no durable records names a fresh session dir."""
    session_dir, gitdir, _head_path = _legacy_v3_session(tmp_path, name="legacy-advance-latched")
    state = _state(session_dir)
    state["_advanceUsed"] = True
    RD.save_state(session_dir, state)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == RD.LEGACY_SESSION_REFUSAL
    detail = out.get("detail", "")
    assert "advance-submit-interleaved" in detail
    assert "fresh session" in detail
    assert "`next`/`submit`" not in detail


@pytest.mark.parametrize("land_records,next_submit,fresh_session,interleave_tag", [
    (False, True, False, None),
    (True, False, True, "record-submit-interleaved"),
])
def test_legacy_refusal_existing_branches_still_answer_as_before(
        tmp_path, land_records, next_submit, fresh_session, interleave_tag):
    """Plain and durable-record legacy refusal branches keep their recovery wording."""
    session_dir, gitdir, _head_path = _legacy_v3_session(
        tmp_path, name="legacy-branch-%s" % land_records, land_records=land_records)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == RD.LEGACY_SESSION_REFUSAL
    detail = out.get("detail", "")
    if next_submit:
        assert "`next`/`submit`" in detail
    else:
        assert "`next`/`submit`" not in detail
    if fresh_session:
        assert "fresh session" in detail
    if interleave_tag:
        assert interleave_tag in detail
