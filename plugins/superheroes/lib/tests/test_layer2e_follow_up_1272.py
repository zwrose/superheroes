"""#1272 layer 2e: followUp shape — one home, owner submit gates, certification reads it."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import session_contract as SC
from round_certification_fixtures import write_session
from test_round_driver import _cfg, _cfg_cert

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_fake_git = _TDI._fake_git

def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RC = _load("round_certification")

_TRADEOFF = {"title": "widen the API", "severity": "Important",
             "file": "f.py", "line": 1, "tradeoff": True}
_TRADEOFF_ID = "f.py::widen the api@L1"
_WELL_FORMED = {
    "item": "defer auth redesign",
    "revisitTrigger": "when #1300 lands",
    "classClosure": "tracked separately",
}


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _load_state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state


def _parked_judgment_session(tmp_path, name="judgment"):
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    state = RD.new_state(_cfg_cert())
    state["step"] = RD.P_JUDGMENT
    state["pending"] = {
        "action": RD.P_JUDGMENT,
        "round": 1,
        "phase": RD.P_JUDGMENT,
        "attempt": 0,
        "payload": {},
    }
    state["_judgmentFindings"] = [dict(_TRADEOFF)]
    state["_judgmentMechanical"] = []
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    return session_dir


def _parked_stall_session(tmp_path, name="stall", accept_risk=True):
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    state = RD.new_state(_cfg_cert())
    state["findings"] = []
    finding = {"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
               "verdict": "CONFIRMED", "evidence": "ran"}
    state["fixBatch"] = [finding]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    ident = tgt["identity"]
    state["_auditOutcome"] = {"notDischarged": [tgt["id"]]}
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], {
        "reason": "audit-stall", "detail": "x", "stalledIdentities": [ident],
    })
    if not accept_risk:
        state["_stallChoices"] = [c for c in state["_stallChoices"]
                                  if c != RD.ACCEPT_RISK_CHOICE]
        state["_acceptRiskEligible"] = False
    state["step"] = RD.P_STALL
    state["pending"] = {
        "action": RD.P_STALL,
        "round": state["round"],
        "phase": RD.P_STALL,
        "attempt": 0,
        "payload": {},
    }
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    return session_dir


def _pending_submit(session_dir, artifact):
    state = _load_state(session_dir)
    pend = state["pending"]
    return RD.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                         RD.state_hash(state), artifact)


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


def _cert_ctx(state, tmp_path):
    head = (state.get("config") or {}).get("headSha") or ("a" * 40)
    session_dir = write_session(
        tmp_path,
        state=state,
        journal_lines=[],
        meta={"baseGuard": RC.BASE_GUARD_CHECKED, "headSha": head},
        faithful_session=False,
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    return ctx


def _write_owner_artifact(tmp_path, artifact, name="owner-artifact.json"):
    path = str(tmp_path / name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh)
    return path


# --- helper unit tests (rules 1–6) -----------------------------------------------

def test_rule_1_not_dict():
    # axis: rule 1 — non-dict followUp
    fault = SC.follow_up_shape_fault(None)
    assert fault == (None, "out-of-scope disposition lacks named follow-up item")


def test_rule_2_item_absent_passes():
    # axis: rule 2 — item optional when absent
    fault = SC.follow_up_shape_fault({"revisitTrigger": "later", "classClosure": "none"})
    assert fault is None


def test_rule_2b_present_empty_item_refused():
    # axis: rule 2b — present-but-empty item refused
    fault = SC.follow_up_shape_fault({
        "item": "",
        "revisitTrigger": "later",
        "classClosure": "none",
    })
    assert fault == ("missing-follow-up-item", "out-of-scope follow-up lacks named item")


def test_rule_3_missing_revisit_trigger():
    # axis: rule 3 — revisitTrigger required
    fault = SC.follow_up_shape_fault({"item": "defer", "classClosure": "none"})
    assert fault == ("missing-revisit-trigger", "out-of-scope follow-up lacks revisit trigger")


def test_rule_4_documented_trigger():
    # axis: rule 4 — documented token forbidden
    fault = SC.follow_up_shape_fault({
        "item": "defer",
        "revisitTrigger": "documented in the PR",
        "classClosure": "none",
    })
    assert fault == (None, "revisit trigger must not be the word documented")


def test_rule_5_missing_class_closure():
    # axis: rule 5 — classClosure required
    fault = SC.follow_up_shape_fault({"item": "defer", "revisitTrigger": "2026-12-01"})
    assert fault == ("missing-class-closure", "out-of-scope follow-up lacks class-closure line")


def test_rule_6_well_formed_returns_none():
    # axis: rule 6 — fully shaped followUp accepted
    assert SC.follow_up_shape_fault(dict(_WELL_FORMED)) is None


# --- driver / certification edges (e1–e10) -----------------------------------------

def test_e1_judgment_skip_well_formed_follow_up_folds(tmp_path):
    # axis: e1 — well-formed skip followUp folds into ledger
    session_dir = _parked_judgment_session(tmp_path)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": dict(_WELL_FORMED)}]}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is True, out
    entry = _ledger_by_key(_load_state(session_dir))[_TRADEOFF_ID]
    assert entry["disposition"] == "out-of-scope"
    assert entry["followUp"] == _WELL_FORMED


def test_e2_judgment_skip_item_less_follow_up_folds_at_submit(tmp_path):
    # axis: e2 — item-less followUp with trigger and closure folds
    session_dir = _parked_judgment_session(tmp_path)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": {"revisitTrigger": "later", "classClosure": "none"}}]}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is True, out
    entry = _ledger_by_key(_load_state(session_dir))[_TRADEOFF_ID]
    assert entry["followUp"] == {"revisitTrigger": "later", "classClosure": "none"}


def test_e2b_judgment_skip_present_empty_item_refused_at_submit(tmp_path):
    # axis: e2b — present-but-empty item refused before fold
    session_dir = _parked_judgment_session(tmp_path)
    before = _state_bytes(session_dir)
    bad = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": {"item": "", "revisitTrigger": "later", "classClosure": "none"}}]}
    out = _pending_submit(session_dir, bad)
    assert out["ok"] is False, out
    assert "follow-up-malformed" in out["reason"]
    assert _state_bytes(session_dir) == before


def test_e3_judgment_skip_documented_trigger_refused(tmp_path):
    # axis: e3 — documented revisit trigger refused at submit
    session_dir = _parked_judgment_session(tmp_path)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": {"item": "defer", "revisitTrigger": "documented in the PR",
                     "classClosure": "none"}}]}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is False, out


def test_e4_judgment_skip_null_follow_up_refused(tmp_path):
    # axis: e4 — present-but-null followUp refused
    session_dir = _parked_judgment_session(tmp_path)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": None}]}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is False, out


def test_e5_judgment_skip_without_follow_up_folds(tmp_path):
    # axis: e5 — absent followUp key still folds at submit
    session_dir = _parked_judgment_session(tmp_path)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice"}]}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is True, out
    entry = _ledger_by_key(_load_state(session_dir))[_TRADEOFF_ID]
    assert entry["disposition"] == "out-of-scope"
    assert "followUp" not in entry


def test_e6_judgment_fix_stray_follow_up_not_checked(tmp_path):
    # axis: e6 — non-skip disposition ignores stray followUp
    session_dir = _parked_judgment_session(tmp_path)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-as-suggested",
         "followUp": {"item": "ignored"}}]}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is True, out
    state = _load_state(session_dir)
    assert state["step"] == RD.P_FIXER
    assert "dispositionLedger" not in state or not state.get("dispositionLedger")


def test_e7_stall_accept_risk_malformed_follow_up_refused(tmp_path):
    # axis: e7 — accept-risk with malformed followUp refused
    session_dir = _parked_stall_session(tmp_path)
    artifact = {"choice": RD.ACCEPT_RISK_CHOICE,
                "followUp": {"item": "defer", "revisitTrigger": "documented",
                             "classClosure": "none"}}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is False, out


def test_e8_stall_hold_with_follow_up_not_checked(tmp_path):
    # axis: e8 — hold choice ignores followUp
    session_dir = _parked_stall_session(tmp_path, accept_risk=False)
    artifact = {"choice": RD.HOLD_CHOICE,
                "followUp": {"item": "ignored", "revisitTrigger": "x", "classClosure": "y"}}
    out = _pending_submit(session_dir, artifact)
    assert out["ok"] is True, out
    assert _load_state(session_dir)["terminal"] == "held"


def test_e9_item_less_persisted_follow_up_certifies(tmp_path):
    # axis: e9 — resumed ledger without item certifies when trigger and closure present
    finding = {"file": "o.py", "line": 1, "title": "old", "severity": "Important",
               "disposition": "out-of-scope", "outOfScopeReason": "deferred",
               "followUp": {"revisitTrigger": "later", "classClosure": "none"}}
    state = RD.new_state(_cfg(baseGuard=RC.BASE_GUARD_CHECKED))
    state["findings"] = [finding]
    state["dispositionLedgerOwner"] = "ledger"
    state["dispositionLedger"] = [dict(finding, dispositionRound=1)]
    ctx = _cert_ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is None


def test_e9b_present_empty_item_refused_at_certification(tmp_path):
    # axis: e9b — present-but-empty item refused at certification
    finding = {"file": "o.py", "line": 1, "title": "old", "severity": "Important",
               "disposition": "out-of-scope", "outOfScopeReason": "deferred",
               "followUp": {"item": "", "revisitTrigger": "later", "classClosure": "none"}}
    state = RD.new_state(_cfg(baseGuard=RC.BASE_GUARD_CHECKED))
    state["findings"] = [finding]
    state["dispositionLedgerOwner"] = "ledger"
    state["dispositionLedger"] = [dict(finding, dispositionRound=1)]
    ctx = _cert_ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "missing-follow-up-item"


def test_e10_advance_owner_artifact_malformed_follow_up_refused(tmp_path):
    # axis: e10 — advance owner-artifact shares submit prepare gate
    session_dir = _parked_judgment_session(tmp_path, name="advance-follow-up")
    state = _load_state(session_dir)
    state["_advanceUsed"] = True
    RD.save_state(session_dir, state)
    artifact = {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": {"item": "defer", "revisitTrigger": "documented in the PR",
                      "classClosure": "none"}}]}
    gitdir = str(tmp_path / "gitdir")
    os.makedirs(gitdir, exist_ok=True)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir),
                         owner_artifact_path=_write_owner_artifact(tmp_path, artifact))
    assert out["ok"] is False, out
    assert out.get("reason") == "fold-refused"
    assert "follow-up-malformed" in (out.get("detail") or "")
