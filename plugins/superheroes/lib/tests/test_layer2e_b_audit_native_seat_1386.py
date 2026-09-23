"""#1386 WO-C: refuse host-channel auditor seats on dispatch-audits when advance-latched."""
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
import round_records as RR  # noqa: E402

RD = importlib.import_module("round_driver")

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

from test_round_driver import (  # noqa: E402
    HEAD_NEW_SURFACE,
    _cfg as _hand_cfg,
    _drive_to_phase as _hand_drive_to_phase,
    _responder,
)

_bootstrap = _TDI._bootstrap
_blocking_finding = _TDI._blocking_finding
_drive_one_phase = _TDI._drive_one_phase
_drive_to_phase = _TDI._drive_to_phase
_fake_git = _TDI._fake_git
_state = _TDI._state
_write_dispatch_manifest = _TDI._write_dispatch_manifest
_auditor_vendor_for = _TDI._auditor_vendor_for
_slots_of = _TDI._slots_of
_land = _TDI._land
_record = _TDI._record

_REFUSAL = RD.DISCHARGE_PHASE_NATIVE_SEAT_REFUSAL
_ADVANCE_REFUSAL = RD.ADVANCE_AUDIT_SEAT_NATIVE_REFUSAL
_RECOVERY = "drive this session by hand next/submit, or configure a runner-backed auditor vendor"
_HAND_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _orders_manifest_path(session_dir):
    state = _state(session_dir)
    pend = state["pending"]
    return RD._orders_manifest_path(session_dir, pend["round"], pend["phase"], pend["attempt"])


def _claude_auditor_cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "fixerVendor": "codex",
            "verifyCommand": "none"}
    base.update(over)
    return base


def _codex_auditor_cfg(**over):
    base = {"leg": "code", "vendors": ["codex", "claude"], "fixerVendor": "claude",
            "verifyCommand": "none"}
    base.update(over)
    return base


def _drive_to_audits_pending_codex(tmp_path, name="codex-audits"):
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name=name, **_codex_auditor_cfg())
    findings = [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_AUDITS)
    state = _state(session_dir)
    assert state.get("_advanceUsed"), "expected advance latch"
    assert state["pending"]["phase"] == RD.P_AUDITS
    return session_dir, gitdir, head_path


def _force_claude_auditor_targets(session_dir):
    state = _state(session_dir)
    targets = []
    for target in state.get("_auditTargets") or []:
        if isinstance(target, dict):
            t = dict(target)
            t["auditorVendor"] = "claude"
            targets.append(t)
    state["_auditTargets"] = targets
    payload = dict(state["pending"].get("payload") or {})
    payload_targets = []
    for target in payload.get("targets") or []:
        if isinstance(target, dict):
            t = dict(target)
            t["auditorVendor"] = "claude"
            payload_targets.append(t)
    payload["targets"] = payload_targets
    state["pending"] = dict(state["pending"])
    state["pending"]["payload"] = payload
    RD.save_state(session_dir, state)


def _prepared_latched_claude_audits_emit(tmp_path, name):
    session_dir, _gitdir, _head_path = _drive_to_audits_pending_codex(tmp_path, name=name)
    _force_claude_auditor_targets(session_dir)
    state = _state(session_dir)
    targets = state.get("_auditTargets") or []
    assert targets
    seat = targets[0]["id"]
    cfg = state.get("config") or {}
    payload = state["pending"]["payload"]
    pend = state["pending"]
    roster = [seat]
    return session_dir, state, seat, cfg, payload, pend, roster


def test_edge1_first_advance_claude_auditor_refused_before_fold(tmp_path):
    """BP-1386-1: first `advance` refuses before `_advanceUsed` is set or state folds.

    Neutralize `_advance_audit_seat_native_refusal` → red:
    AssertionError: assert out['reason'] == 'advance-audit-seat-native'
    (advance folds fixer and later refuses `order-render-refused` instead).
    """
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="edge1-advance", **_claude_auditor_cfg())
    findings = [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_FIXER)
    before = _state_bytes(session_dir)
    assert not os.path.exists(
        RD._orders_manifest_path(session_dir, _state(session_dir)["round"], RD.P_AUDITS, 0))
    phase, out = _drive_one_phase(session_dir, gitdir, findings, head_path)
    assert phase == RD.P_FIXER
    assert out["ok"] is False
    assert out["reason"] == _ADVANCE_REFUSAL
    assert _RECOVERY in (out.get("detail") or "")
    assert _state(session_dir).get("_advanceUsed") is None
    assert _state_bytes(session_dir) == before
    assert not os.path.exists(
        RD._orders_manifest_path(session_dir, _state(session_dir)["round"], RD.P_AUDITS, 0))


def test_edge1b_plain_next_after_advance_refusal_still_works(tmp_path):
    """BP-1386-2: hand `next` after advance refusal is not latched out.

    Neutralize the early refusal → red:
    AssertionError: assert out['ok'] is True (cmd_next returns order-render-refused).
    """
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="edge1b", **_claude_auditor_cfg())
    findings = [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_FIXER)
    phase, out = _drive_one_phase(session_dir, gitdir, findings, head_path)
    assert phase == RD.P_FIXER
    assert out["ok"] is False
    assert out["reason"] == _ADVANCE_REFUSAL
    assert _state(session_dir).get("_advanceUsed") is None
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True, out
    assert _state(session_dir).get("_advanceUsed") is None
    assert os.path.isfile(_orders_manifest_path(session_dir))


def test_edge1c_re_emit_refused_on_latched_native_audits(tmp_path):
    """BP-1386-3: render-time backstop still refuses latched native audit seats.

    Neutralize the `_build_order_render_context` guard → red:
    ValueError not raised from `_emit_orders_manifest` on a latched claude-audits seat.
    """
    session_dir, state, _seat, _cfg, payload, pend, roster = _prepared_latched_claude_audits_emit(
        tmp_path, "edge1c")
    state["_advanceUsed"] = True
    RD.save_state(session_dir, state)
    with pytest.raises(ValueError) as exc:
        RD._emit_orders_manifest(session_dir, state, pend["round"], RD.P_AUDITS, pend["attempt"],
                                 roster, journal_cmd="re-emit", pending_payload=payload,
                                 seat_map=RD._effective_seat_map(state))
    assert "order-render-refused" in str(exc.value)
    assert _REFUSAL in str(exc.value)
    assert _RECOVERY in str(exc.value)
    control = _state(session_dir)
    control.pop("_advanceUsed", None)
    RD._emit_orders_manifest(session_dir, control, pend["round"], RD.P_AUDITS, pend["attempt"],
                             roster, journal_cmd="re-emit", pending_payload=payload,
                             seat_map=RD._effective_seat_map(control))


def test_edge2_codex_auditor_emits_on_advance_path(tmp_path):
    """BP-1386-4: runner-backed auditor sessions still fold on first `advance`.

    Neutralize the early refusal for engine-channel auditors → red:
    AssertionError: assert out['ok'] is True (first advance refused advance-audit-seat-native).
    """
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="edge2", **_codex_auditor_cfg())
    findings = [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_FIXER)
    phase, out = _drive_one_phase(session_dir, gitdir, findings, head_path)
    assert out["ok"] is True, out
    state = _state(session_dir)
    assert state["pending"]["phase"] == RD.P_AUDITS
    manifest = RD._orders_manifest_path(session_dir, state["round"], RD.P_AUDITS, state["pending"]["attempt"])
    assert os.path.isfile(manifest)


def test_edge3_hand_path_claude_auditor_emits(tmp_path):
    session_dir = str(tmp_path)
    cfg = _hand_cfg(**_claude_auditor_cfg())
    _hand_drive_to_phase(session_dir, cfg,
                         _responder(round1_findings=_HAND_FINDING, head=HEAD_NEW_SURFACE),
                         RD.P_AUDITS)
    state = _state(session_dir)
    assert state.get("_advanceUsed") is None
    assert state["pending"]["phase"] == RD.P_AUDITS
    targets = state["pending"]["payload"].get("targets") or state.get("_auditTargets") or []
    assert any(isinstance(t, dict) and t.get("auditorVendor") == "claude" for t in targets)
    assert os.path.isfile(_orders_manifest_path(session_dir))


def test_edge4_latched_non_discharge_host_seat_emits(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="edge4", **_codex_auditor_cfg())
    findings = [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_SYNTHESIS)
    state = _state(session_dir)
    assert state.get("_advanceUsed")
    assert state["pending"]["phase"] == RD.P_SYNTHESIS
    out = RD.cmd_next(session_dir)
    assert out["ok"] is True, out
    assert os.path.isfile(_orders_manifest_path(session_dir))


def test_edge5_absent_auditor_vendor_stdout_not_refused(tmp_path):
    session_dir, _gitdir, _head_path = _drive_to_audits_pending_codex(tmp_path, name="edge5")
    state = _state(session_dir)
    targets = state.get("_auditTargets") or []
    assert targets
    seat = targets[0]["id"]
    for coll in (state["_auditTargets"], state["pending"]["payload"]["targets"]):
        coll[0] = dict(coll[0])
        coll[0].pop("auditorVendor", None)
    RD.save_state(session_dir, state)
    cfg = state.get("config") or {}
    payload = state["pending"]["payload"]
    row = RD._seat_transport_row(state, RD.P_AUDITS, seat, 0, cfg, payload,
                                 cfg.get("repoRoot") or session_dir)
    assert RD._seat_channel(RD.P_AUDITS, row) == RD.CHANNEL_STDOUT
    pend = state["pending"]
    roster = [seat]
    RD._emit_orders_manifest(session_dir, state, pend["round"], RD.P_AUDITS, pend["attempt"],
                             roster, journal_cmd="next", pending_payload=payload,
                             seat_map=RD._effective_seat_map(state))


def test_edge6_truthy_non_boolean_advance_latch_refused(tmp_path):
    session_dir, state, _seat, _cfg, payload, pend, roster = _prepared_latched_claude_audits_emit(
        tmp_path, "edge6")
    state["_advanceUsed"] = 1
    RD.save_state(session_dir, state)
    with pytest.raises(ValueError) as exc:
        RD._emit_orders_manifest(session_dir, state, pend["round"], RD.P_AUDITS, pend["attempt"],
                                 roster, journal_cmd="next", pending_payload=payload,
                                 seat_map=RD._effective_seat_map(state))
    assert "order-render-refused" in str(exc.value)
    assert _REFUSAL in str(exc.value)
    control = _state(session_dir)
    control.pop("_advanceUsed", None)
    RD._emit_orders_manifest(session_dir, control, pend["round"], RD.P_AUDITS, pend["attempt"],
                             roster, journal_cmd="next", pending_payload=payload,
                             seat_map=RD._effective_seat_map(control))
