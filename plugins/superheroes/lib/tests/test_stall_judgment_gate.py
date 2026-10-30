"""#1107 WO-b1 (reworked by C1-L4): stall self-recovery holds an owner-choice finding out of the fix
batch — it never reaches the fixer and never reaches the owner mid-review."""
import importlib.util
import os

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
_TRADEOFF_KEY = "f.py::widen the api@L1"


def _stall_state_with_open_target(target, stalled_identities):
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [dict(target)]
    state["_auditOutcome"] = {"notDischarged": [target["id"]], "discharged": []}
    state["selfRecovered"] = False
    state["_changedSubjects"] = ["Code"]  # a known, non-cross-cutting surface: no confirmation re-arm
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": stalled_identities}
    return state, breaker


def test_stall_self_recovery_tradeoff_batch_is_held_not_fixed_and_handed_back():
    # axis: composed stall batch with tradeoff:true is held out of the fixer batch, then handed back open
    ident = FI.finding_identity(_TRADEOFF)
    target = {"id": "%s@L1" % ident, "identity": ident, **dict(_TRADEOFF)}
    state, breaker = _stall_state_with_open_target(target, [ident])
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] != RD.P_APPLY_FIXES
    assert "_fixBatch" not in state
    assert state["ownerChoiceHeld"] == [_TRADEOFF_KEY]
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"


def test_stall_self_recovery_mechanical_batch_routes_to_fixer():
    # axis: purely mechanical stall batch still routes to P_APPLY_FIXES unchanged
    mech = _finding(title="null deref")
    ident = FI.finding_identity(mech)
    target = {"id": "%s@L1" % ident, "identity": ident, **dict(mech)}
    state, breaker = _stall_state_with_open_target(target, [ident])
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_APPLY_FIXES
    assert state.get("_fixBatch")
    assert "ownerChoiceHeld" not in state


def test_stall_self_recovery_owner_choice_exit_still_spends_the_one_shot_guard():
    # axis: a held-batch exit still spends the one-shot self-recovery guard
    ident = FI.finding_identity(_TRADEOFF)
    target = {"id": "%s@L1" % ident, "identity": ident, **dict(_TRADEOFF)}
    state, breaker = _stall_state_with_open_target(target, [ident])
    RD._handle_stall(state, state["config"], breaker)
    assert state.get("selfRecovered") is True
    assert [d["kind"] for d in state["decisions"]].count("self-recovery") == 1


def test_stall_union_admitted_tradeoff_target_is_held_and_the_mechanical_one_is_fixed():
    # axis: a tradeoff target admitted by the #1165 union (not the stalled alias) is held, the stalled one fixed
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
    assert state["step"] == RD.P_APPLY_FIXES
    assert [r["title"] for r in state["_fixBatch"]] == ["null deref"]
    assert state["ownerChoiceHeld"] == [_TRADEOFF_KEY]
