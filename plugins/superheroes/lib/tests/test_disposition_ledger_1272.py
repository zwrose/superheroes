"""#1272 WO-2: disposition ledger is the one owner — staging, recording, writer merge."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")
RC = _load("round_certification")
V = _load("verification")
RR = _load("round_records")


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


def _ctx(state, tmp_path):
    session_dir = str(tmp_path / "sess")
    os.makedirs(session_dir, exist_ok=True)
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    meta = {"sessionId": "s", "headSha": "a" * 40,
            "baseGuard": RC.BASE_GUARD_CHECKED}
    meta_path = os.path.join(session_dir, RR.META_FILE)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    state.setdefault("config", {})["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["config"]["headSha"] = "a" * 40
    RD.save_state(session_dir, state)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    return ctx


# --- L1 ------------------------------------------------------------------------------

def test_L1_stage_findings_seeds_ledger_and_owner_marker():
    state = RD.new_state(_cfg())
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    RD._stage_findings(state, compiled)
    assert state["dispositionLedgerOwner"] == "ledger"
    key = SC.finding_identity_key(compiled[0])
    ledger = _ledger_by_key(state)
    assert key in ledger
    assert ledger[key]["raisedRound"] == 1
    RD._stage_findings(state, compiled)
    assert len(state["dispositionLedger"]) == 1


# --- L2 ------------------------------------------------------------------------------

def test_L2_verifier_refuted_never_live_ledger_refuted():
    finding = {"file": "r.py", "line": 3, "title": "leak", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    staged = V.stage_ids(compiled)
    fid = staged[0]["id"]
    RD._fold_verifiers(state, state["config"], {
        "verdicts": [{"id": fid, "verdict": "REFUTED", "reason": "not reproducible"}]})
    assert key not in {SC.finding_identity_key(f) for f in (state.get("findings") or [])}
    entry = _ledger_by_key(state)[key]
    assert entry["disposition"] == "refuted"
    assert entry["refutedReason"] == "not reproducible"


def test_L2_author_justified_plausible_drop_refuted():
    finding = {"file": "aj.py", "line": 2, "title": "style", "severity": "Important",
               "verdict": "PLAUSIBLE"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    staged = V.stage_ids(compiled)
    state["_verified"] = staged
    key = SC.finding_identity_key(staged[0])
    state["config"]["priorComments"] = [
        {"file": "aj.py", "line": 2, "body": "intentional pattern for performance " + ("x" * 40)}]
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g0",
                                                               "member_ids": [staged[0]["id"]]}]})
    entry = _ledger_by_key(state)[key]
    assert entry["disposition"] == "refuted"
    assert entry["refutedReason"].startswith("author-justified: ")


def test_L2_merged_away_member_resolves_through_representative(tmp_path):
    f1 = {"file": "m.py", "line": 1, "title": "root a", "severity": "Important",
          "verdict": "CONFIRMED"}
    f2 = {"file": "m.py", "line": 2, "title": "root b", "severity": "Minor",
          "verdict": "CONFIRMED"}
    compiled, _ = RD.mechanical_compile([f1, f2], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    staged = V.stage_ids(compiled)
    state["_verified"] = staged
    id0, id1 = staged[0]["id"], staged[1]["id"]
    key0 = SC.finding_identity_key(staged[0])
    key1 = SC.finding_identity_key(staged[1])
    RD._fold_synthesis(state, state["config"], {"grouping": [{"group_id": "g",
                                                              "member_ids": [id0, id1]}]})
    ledger = _ledger_by_key(state)
    assert ledger[key1]["mergedInto"] == key0
    live = [f for f in (state.get("findings") or []) if isinstance(f, dict)]
    assert len(live) == 1
    rep = live[0]
    assert SC.finding_identity_key(rep) == key0
    rep["disposition"] = "refuted"
    rep["refutedReason"] = "merged into representative"
    state["dispositionLedgerOwner"] = "ledger"
    ctx = _ctx(state, tmp_path)
    assert RC.check_disposition_without_receipt(ctx) is None
    rep.pop("disposition", None)
    rep.pop("refutedReason", None)
    rep.pop("dispositionRound", None)
    state["findings"] = []
    state["dispositionLedger"] = [ledger[key1]]
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["detail"] in (
        "finding has no disposition recorded",
        "merged-into chain does not resolve",
    )


# --- L3 ------------------------------------------------------------------------------

def test_L3_fold_audits_stamps_fixed_on_discharged_only():
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["config"][RD.FIX_FOLD_HEAD_KEY] = "b" * 40
    state["rounds"] = {"2": {"verifyResult": "pass"}}
    discharged_f = {"title": "fixed bug", "severity": "Important", "file": "f.py", "line": 1}
    open_f = {"title": "open bug", "severity": "Important", "file": "g.py", "line": 2}
    state["fixBatch"] = [discharged_f, open_f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    discharged_id = RD._finding_key_of(discharged_f)
    open_id = RD._finding_key_of(open_f)
    RD._set_findings(state, [discharged_f, open_f])
    state["_newSurface"] = True
    auditor = state["_auditTargets"][0]["auditorVendor"]
    manifest = {discharged_id: auditor, open_id: auditor}
    RD._fold_audits(state, state["config"], {
        "results": [
            {"id": discharged_id, "ruling": "discharged", "reason": "gone"},
            {"id": open_id, "ruling": "not-discharged", "reason": "still there"},
        ],
        "collectionManifest": manifest,
    })
    ledger = _ledger_by_key(state)
    assert ledger[discharged_id]["disposition"] == "fixed"
    assert ledger[discharged_id]["dispositionRound"] == 2
    receipt = ledger[discharged_id]["dispositionReceipt"]
    assert receipt["headSha"] == "b" * 40
    assert receipt["verifyResult"] == "pass"
    live_discharged = next(f for f in state["findings"]
                           if SC.finding_identity_key(f) == discharged_id)
    assert live_discharged.get("disposition") == "fixed"
    open_live = next((f for f in state["findings"] if SC.finding_identity_key(f) == open_id), None)
    if open_live is not None:
        assert open_live.get("disposition") is None
    elif open_id in ledger:
        assert ledger[open_id].get("disposition") is None


# --- L4 ------------------------------------------------------------------------------

def test_L4_judgment_skip_records_out_of_scope_with_follow_up():
    finding = {"title": "tradeoff", "severity": "Important", "file": "j.py", "line": 5,
               "tradeoff": True}
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(finding)])
    fid = RD._judgment_row_ids(state["_judgmentFindings"])[0]
    follow_up = {"item": "defer auth redesign", "revisitTrigger": "when #1300 lands",
                 "classClosure": "tracked separately"}
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": fid, "disposition": "skip", "reason": "product choice",
         "followUp": follow_up}]})
    entry = _ledger_by_key(state)[fid]
    assert entry["disposition"] == "out-of-scope"
    assert entry["followUp"] == follow_up


def test_L4_judgment_skip_without_follow_up_refuses_writer(tmp_path):
    finding = {"title": "tradeoff", "severity": "Important", "file": "j.py", "line": 6,
               "tradeoff": True}
    state = RD.new_state(_cfg())
    RD._route_judgment_blockers(state, [dict(finding)])
    fid = RD._judgment_row_ids(state["_judgmentFindings"])[0]
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": fid, "disposition": "skip", "reason": "product choice"}]})
    entry = _ledger_by_key(state)[fid]
    assert entry["disposition"] == "out-of-scope"
    assert "followUp" not in entry
    state["dispositionLedgerOwner"] = "ledger"
    entry["severity"] = "Important"
    state["findings"] = [entry]
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["detail"] == "out-of-scope disposition lacks named follow-up item"


# --- L5 ------------------------------------------------------------------------------

def test_L5_stall_accept_risk_records_out_of_scope_on_targets():
    state, ident, tgt = _stall_target_state()
    key = RD._finding_key_of(tgt)
    RD._fold_stall(state, state["config"], {"choice": RD.ACCEPT_RISK_CHOICE})
    entry = _ledger_by_key(state)[key]
    assert entry["disposition"] == "out-of-scope"
    assert entry["outOfScopeReason"] == "owner accepted the disclosed risk (stall gate)"


def _stall_target_state(verdict="CONFIRMED", evidence="ran", identity=None):
    state = RD.new_state(_cfg())
    state["findings"] = []
    f = {"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
         "verdict": verdict, "evidence": evidence}
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    ident = identity or tgt["identity"]
    state["_auditOutcome"] = {"notDischarged": [tgt["id"]]}
    state["selfRecovered"] = True
    RD._handle_stall(state, state["config"], {"reason": "audit-stall",
                                              "detail": "x", "stalledIdentities": [ident]})
    return state, ident, tgt


# --- L6 ------------------------------------------------------------------------------

def test_L6_without_owner_marker_three_source_merge_unchanged():
    legacy = {"file": "old.py", "line": 1, "title": "legacy", "severity": "Minor",
              SC.FINDING_KEY_FIELD: "legacy-key"}
    state = {"schemaVersion": 5, "findings": [], "_records": [{"findings": [legacy]}]}
    certified = RC._certification_findings(state)
    keys = {SC.finding_identity_key(f) for f in certified}
    assert "legacy-key" in keys


def test_L6_with_owner_marker_empty_ledger_excludes_records_findings():
    legacy = {"file": "old.py", "line": 1, "title": "legacy", "severity": "Minor",
              SC.FINDING_KEY_FIELD: "legacy-key"}
    state = {"schemaVersion": 5, "dispositionLedgerOwner": "ledger", "dispositionLedger": [],
             "findings": [], "_records": [{"findings": [legacy]}]}
    certified = RC._certification_findings(state)
    assert certified == []


# --- L7 bite-proof: departure chokepoint ---------------------------------------------

def test_L7_departure_outside_chokepoint_still_on_ledger(tmp_path):
    finding = {"file": "d.py", "line": 1, "title": "live", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    RD._set_findings(state, compiled)
    state["findings"] = []
    ledger = _ledger_by_key(state)
    assert key in ledger
    assert ledger[key].get("disposition") is None
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["detail"] == "finding has no disposition recorded"


# --- L8 uses L2 open-representative case (bite-proof run separately) -----------------
