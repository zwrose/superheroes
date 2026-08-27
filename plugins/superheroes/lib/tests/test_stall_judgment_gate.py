"""#1107 WO-b1: stall self-recovery must consult the owner-judgment gate before P_FIXER."""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
FI = _load("finding_identity")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "claude"}
    base.update(over)
    return base


def _finding(file="f.py", line=1, title="bug", severity="Important", **extra):
    f = {"file": file, "line": line, "title": title, "severity": severity}
    f.update(extra)
    return f


_TRADEOFF = _finding(title="widen the API", tradeoff=True)


def _stall_state_with_open_target(target, stalled_identities):
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [dict(target)]
    state["_auditOutcome"] = {"notDischarged": [target["id"]], "discharged": []}
    state["selfRecovered"] = False
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": stalled_identities}
    return state, breaker


def test_stall_self_recovery_tradeoff_batch_routes_to_judgment():
    # axis: composed stall batch with tradeoff:true must route to P_JUDGMENT, not P_FIXER
    ident = FI.finding_identity(_TRADEOFF)
    target = {"id": "%s@L1" % ident, "identity": ident, **dict(_TRADEOFF)}
    state, breaker = _stall_state_with_open_target(target, [ident])
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_JUDGMENT
    assert state["step"] != RD.P_FIXER
    assert "_fixBatch" not in state
    judgment = state.get("_judgmentFindings") or []
    assert len(judgment) == 1
    assert judgment[0].get("tradeoff") is True
    assert judgment[0]["title"] == "widen the API"


def test_stall_self_recovery_mechanical_batch_routes_to_fixer():
    # axis: purely mechanical stall batch still routes to P_FIXER unchanged
    mech = _finding(title="null deref")
    ident = FI.finding_identity(mech)
    target = {"id": "%s@L1" % ident, "identity": ident, **dict(mech)}
    state, breaker = _stall_state_with_open_target(target, [ident])
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_FIXER
    assert state.get("_fixBatch")
    assert "_judgmentFindings" not in state


def test_stall_self_recovery_judgment_gate_keeps_self_recovered_flag():
    # axis: judgment-gate exit still spends the one-shot self-recovery guard
    ident = FI.finding_identity(_TRADEOFF)
    target = {"id": "%s@L1" % ident, "identity": ident, **dict(_TRADEOFF)}
    state, breaker = _stall_state_with_open_target(target, [ident])
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_JUDGMENT
    assert state.get("selfRecovered") is True


def test_stall_union_admitted_tradeoff_target_routes_to_judgment():
    # axis: a tradeoff target admitted by the #1165 union (not the stalled alias) still gates on judgment
    mech = _finding(title="null deref")
    mech_ident = FI.finding_identity(mech)
    stalled = {"id": "%s@L1" % mech_ident, "identity": mech_ident, **dict(mech)}
    to_ident = FI.finding_identity(_TRADEOFF)
    sibling = {"id": "%s@L1" % to_ident, "identity": to_ident, **dict(_TRADEOFF)}
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [dict(stalled), dict(sibling)]
    state["fixBatch"] = [dict(stalled), dict(sibling)]
    state["_auditOutcome"] = {"notDischarged": [stalled["id"], sibling["id"]], "discharged": []}
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": [mech_ident]}
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_JUDGMENT
    assert "_fixBatch" not in state
    assert [j["title"] for j in (state.get("_judgmentFindings") or [])] == ["widen the API"]
