"""#1272 WO-2: disposition ledger is the one owner — staging, recording, writer merge."""
import importlib.util
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
V = _load("verification")

# The three checks every audit result owes (`audits.audit_checks_fault`), each answered `yes`.
_AUDIT_CHECKS = {name: {"answer": "yes", "why": "checked"}
                 for name in ("right", "brokeNothing", "testWouldFail")}


def _cfg():
    # A native `claude` seat takes the seat map's hostFamily; without one the host is unknown and
    # the seat is ineligible to verify a `codex` fixer's findings (#1851).
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex",
            "seatMap": {"hostFamily": "anthropic"}}


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


# --- L1 ------------------------------------------------------------------------------

def test_L1_stage_findings_seeds_ledger_and_owner_marker():
    state = RD.new_state(_cfg())
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
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
    finding = {"file": "r.py", "line": 3, "title": "leak", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
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
               "verdict": "PLAUSIBLE", "consequence": "a reviewer-found defect stays in the change"}
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


def test_L2_restaged_finding_strips_prior_round_disposition():
    finding = {"file": "r.py", "line": 1, "title": "bug", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    state["round"] = 2
    RD._stage_findings(state, compiled)
    RD._record_disposition(state, key, "fixed", 2,
                           dispositionReceipt={"headSha": "b" * 40})
    state["round"] = 3
    RD._stage_findings(state, compiled)
    entry = _ledger_by_key(state)[key]
    assert entry["raisedRound"] == 3
    assert "disposition" not in entry
    assert "dispositionReceipt" not in entry


def test_L2_same_round_restage_keeps_disposition():
    finding = {"file": "s.py", "line": 1, "title": "bug", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    key = SC.finding_identity_key(compiled[0])
    RD._stage_findings(state, compiled)
    RD._record_disposition(state, key, "fixed", 2,
                           dispositionReceipt={"headSha": "b" * 40})
    RD._stage_findings(state, compiled)
    entry = _ledger_by_key(state)[key]
    assert entry["disposition"] == "fixed"
    assert entry["dispositionReceipt"]["headSha"] == "b" * 40


def test_L2_stage_findings_strips_seat_supplied_disposition_family():
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important",
               "disposition": "fixed", "dispositionReceipt": {"headSha": "z" * 40},
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    entry = _ledger_by_key(state)[key]
    assert "disposition" not in entry
    assert "dispositionReceipt" not in entry
    staged = state.get("_toVerify") or []
    assert len(staged) == 1
    assert "disposition" not in staged[0]
    assert "dispositionReceipt" not in staged[0]


def test_L2_append_review_record_then_stage_strips_seat_supplied_disposition():
    finding = {"file": "x", "line": 1, "title": "t", "severity": "Minor",
               "disposition": "refuted", "dispositionRound": 1, "refutedReason": "seat",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._append_review_record(state, 1, "baseline", {}, compiled)
    RD._stage_findings(state, compiled)
    staged = state.get("_toVerify") or []
    assert len(staged) == 1
    assert staged[0].get("disposition") is None
    assert staged[0].get("dispositionRound") is None
    assert staged[0].get("refutedReason") is None
    key = SC.finding_identity_key(compiled[0])
    entry = _ledger_by_key(state)[key]
    assert entry.get("disposition") is None


def test_L2_backfill_last_record_wins_over_earlier_disposition(tmp_path):
    key = "o::old@L1"
    old = {"file": "o", "line": 1, "title": "old", "severity": "Important",
           SC.FINDING_KEY_FIELD: key, "disposition": "refuted",
           "dispositionRound": 1, "refutedReason": "stale"}
    later = {"file": "o", "line": 1, "title": "old", "severity": "Important",
             SC.FINDING_KEY_FIELD: key}
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["_records"] = [{"findings": [old]}, {"findings": [later]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    assert ledger[key].get("disposition") is None


def test_L2_synthesis_merge_records_member_into_representative(tmp_path):
    f1 = {"file": "m.py", "line": 1, "title": "root a", "severity": "Important",
          "verdict": "CONFIRMED", "consequence": "a reviewer-found defect stays in the change"}
    f2 = {"file": "m.py", "line": 2, "title": "root b", "severity": "Minor",
          "verdict": "CONFIRMED", "consequence": "a reviewer-found defect stays in the change"}
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


def test_L3_fold_audits_stamps_fixed_on_discharged_only():
    state = RD.new_state(_cfg())
    state["round"] = 2
    head = "b" * 40
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head
    state["rounds"] = {"2": {"verifyResult": "pass"}}
    discharged_f = {"title": "fixed bug", "severity": "Important", "file": "f.py", "line": 1}
    open_f = {"title": "open bug", "severity": "Important", "file": "g.py", "line": 2}
    state["fixBatch"] = [discharged_f, open_f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    discharged_id = RD._finding_key_of(discharged_f)
    open_id = RD._finding_key_of(open_f)
    RD._set_findings(state, [discharged_f, open_f])
    state["_newSurface"] = True
    state["_fixDeltaDiff"] = "diff --git a/f.py b/f.py\n"
    auditor = state["_auditTargets"][0]["auditorVendor"]
    manifest = {discharged_id: auditor, open_id: auditor}
    RD._fold_audits(state, state["config"], {
        "results": [
            {"id": discharged_id, "ruling": "discharged", "reason": "gone", "checks": _AUDIT_CHECKS},
            {"id": open_id, "ruling": "not-discharged", "reason": "still there",
             "checks": _AUDIT_CHECKS},
        ],
        "collectionManifest": manifest,
    })
    ledger = _ledger_by_key(state)
    assert ledger[discharged_id]["disposition"] == "fixed"
    assert ledger[discharged_id]["dispositionRound"] == 2
    receipt = ledger[discharged_id]["dispositionReceipt"]
    assert receipt["headSha"] == head
    assert set(receipt) <= {"headSha"}
    live_discharged = next(f for f in state["findings"]
                           if SC.finding_identity_key(f) == discharged_id)
    assert live_discharged.get("disposition") == "fixed"
    open_live = next((f for f in state["findings"] if SC.finding_identity_key(f) == open_id), None)
    if open_live is not None:
        assert open_live.get("disposition") is None
    elif open_id in ledger:
        assert ledger[open_id].get("disposition") is None


# --- L6 ------------------------------------------------------------------------------

def test_L6_first_stage_backfills_records_into_ledger_undisposed(tmp_path):
    old = {"file": "o", "line": 1, "title": "old", "severity": "Important",
           SC.FINDING_KEY_FIELD: "o::old@L1"}
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["_records"] = [{"findings": [old]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    assert "o::old@L1" in ledger
    assert ledger["o::old@L1"].get("disposition") is None


# --- C13: fix-fold head and record backfill ------------------------------------------

def test_C13_fix_fold_records_fix_fold_head(tmp_path, monkeypatch):
    state = RD.new_state(_cfg())
    state["round"] = 2
    head = "f" * 40
    monkeypatch.setattr(RD, "_resolve_fix_fold_head_sha", lambda _sd, _st: (head, None))
    state["_fixBatch"] = []
    RD._fold_apply_fixes(state, state["config"], {"fixes": []}, session_dir=str(tmp_path))
    assert state["rounds"]["2"]["fixFoldHead"] == head


def test_C13_backfill_preserves_preexisting_ledger_disposition():
    key = "o::old@L1"
    refuted_reason = "persisted refutation"
    preexisting_entry = {
        "file": "o", "line": 1, "title": "old", "severity": "Important",
        SC.FINDING_KEY_FIELD: key,
        "disposition": "refuted",
        "dispositionRound": 1,
        "refutedReason": refuted_reason,
    }
    record_finding = {
        "file": "o", "line": 1, "title": "old", "severity": "Important",
        SC.FINDING_KEY_FIELD: key, "disposition": "fixed",
        "dispositionRound": 1, "dispositionReceipt": {"headSha": "z" * 40},
    }
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["dispositionLedger"] = [preexisting_entry]
    state["_records"] = [{"findings": [record_finding]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    assert ledger[key]["disposition"] == "refuted"
    assert ledger[key]["refutedReason"] == refuted_reason


def test_C13_backfill_merges_record_severity_preserves_disposition_family(tmp_path):
    key = "o::old@L1"
    follow_up = {"item": "defer auth redesign", "revisitTrigger": "when #1300 lands",
                 "classClosure": "tracked separately"}
    preexisting_family = {
        "disposition": "out-of-scope",
        "dispositionRound": 1,
        "outOfScopeReason": "product choice",
        "followUp": follow_up,
    }
    preexisting_entry = {
        "file": "o", "line": 1, "title": "old", "severity": "Minor",
        SC.FINDING_KEY_FIELD: key,
        **preexisting_family,
    }
    record_finding = {
        "file": "o", "line": 1, "title": "old", "severity": "Critical",
        SC.FINDING_KEY_FIELD: key,
    }
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["dispositionLedger"] = [dict(preexisting_entry)]
    state["_records"] = [{"findings": [record_finding]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    entry = ledger[key]
    assert entry["severity"] == "Critical"
    for field in SC.DISPOSITION_FAMILY_FIELDS:
        if field in preexisting_family:
            assert entry[field] == preexisting_family[field]
        else:
            assert field not in entry


# --- L7 bite-proof: departure chokepoint ---------------------------------------------

def test_L7_archive_departure_without_prior_staging():
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    state["findings"] = compiled
    assert key not in _ledger_by_key(state)
    RD._set_findings(state, [])
    assert key in _ledger_by_key(state)


def test_L7_departure_outside_chokepoint_still_on_ledger(tmp_path):
    finding = {"file": "d.py", "line": 1, "title": "live", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    RD._set_findings(state, compiled)
    state["findings"] = []
    ledger = _ledger_by_key(state)
    assert key in ledger
    assert ledger[key].get("disposition") is None


def test_L7_departure_preserves_raised_round_through_archive_and_record(tmp_path):
    finding = {"file": "d.py", "line": 1, "title": "live", "severity": "Important",
               "consequence": "a reviewer-found defect stays in the change"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    key = SC.finding_identity_key(compiled[0])
    assert _ledger_by_key(state)[key]["raisedRound"] == 1
    RD._set_findings(state, compiled)
    RD._set_findings(state, [])
    archived = _ledger_by_key(state)[key]
    assert archived.get("raisedRound") == 1
    RD._record_disposition(state, key, "refuted", 1, refutedReason="gone")
    assert _ledger_by_key(state)[key].get("raisedRound") == 1

