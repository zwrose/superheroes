"""#1272 WO-2: disposition ledger is the one owner — staging, recording, writer merge."""
import base64
import hashlib
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


_FIX_PRESENT_BYTES = b"fix present\n"
_FIX_PRESENT_DIGEST = hashlib.sha256(_FIX_PRESENT_BYTES).hexdigest()


def _head_content_blobs(findings, head):
    reads = []
    files = {}
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("disposition") != "fixed":
            continue
        path = finding.get("file")
        if not isinstance(path, str) or not path:
            continue
        reads.append({
            "headSha": head,
            "path": path,
            "contentDigest": _FIX_PRESENT_DIGEST,
            "bytes": len(_FIX_PRESENT_BYTES),
            "readAt": "2026-01-01T00:00:00Z",
            "source": "git-show",
            "readError": None,
        })
        files[path] = base64.b64encode(_FIX_PRESENT_BYTES).decode("ascii")
    if not reads:
        return None
    return {
        "schema": SC.HEAD_CONTENT_BLOBS_SCHEMA,
        "headSha": head,
        "files": files,
        "reads": reads,
    }


def _ctx(state, tmp_path, certified_head=None):
    session_dir = str(tmp_path / "sess")
    os.makedirs(session_dir, exist_ok=True)
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    head = certified_head or ("a" * 40)
    meta = {"sessionId": "s", "headSha": head, "baseGuard": RC.BASE_GUARD_CHECKED}
    meta_path = os.path.join(session_dir, RR.META_FILE)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    state.setdefault("config", {})["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["config"]["headSha"] = head
    blobs = _head_content_blobs(state.get("findings") or [], head)
    if blobs is not None:
        with open(os.path.join(session_dir, RC.HEAD_CONTENT_BLOBS_FILE), "w", encoding="utf-8") as fh:
            json.dump(blobs, fh)
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


def test_L2_stage_findings_strips_seat_supplied_disposition_family():
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important",
               "disposition": "fixed", "dispositionReceipt": {"headSha": "z" * 40}}
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


# --- C13: head-bound verify receipts -------------------------------------------------

def _audit_discharge_fixed(state, head_sha):
    """Fold audits discharging the sole fix-batch target; return ledger key and receipt."""
    discharged_f = {"title": "fixed bug", "severity": "Important", "file": "f.py", "line": 1}
    state["config"][RD.FIX_FOLD_HEAD_KEY] = head_sha
    state["fixBatch"] = [discharged_f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    discharged_id = RD._finding_key_of(discharged_f)
    RD._set_findings(state, [discharged_f])
    state["_newSurface"] = True
    auditor = state["_auditTargets"][0]["auditorVendor"]
    manifest = {discharged_id: auditor}
    RD._fold_audits(state, state["config"], {
        "results": [{"id": discharged_id, "ruling": "discharged", "reason": "gone"}],
        "collectionManifest": manifest,
    })
    entry = _ledger_by_key(state)[discharged_id]
    return discharged_id, entry.get("dispositionReceipt") or {}


def test_C13_two_round_moving_head_no_stale_verify_then_backfill(tmp_path):
    head1, head2 = "a" * 40, "b" * 40
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": head1}}
    key, receipt1 = _audit_discharge_fixed(state, head1)
    assert receipt1.get("verifyResult") == "pass"
    assert receipt1.get("headSha") == head1

    state["round"] = 2
    state["rounds"]["2"] = {}
    key, receipt2 = _audit_discharge_fixed(state, head2)
    assert receipt2.get("headSha") == head2
    assert receipt2.get("verifyResult") is None

    RD._fold_verify(state, state["config"], {"result": "pass"})
    entry = _ledger_by_key(state)[key]
    receipt_after = entry.get("dispositionReceipt") or {}
    assert receipt_after.get("verifyResult") == "pass"
    assert receipt_after.get("headSha") == head2

    state["dispositionLedgerOwner"] = "ledger"
    entry = dict(entry)
    receipt_after = dict(entry.get("dispositionReceipt") or {})
    receipt_after["fixContentDigest"] = _FIX_PRESENT_DIGEST
    entry["dispositionReceipt"] = receipt_after
    state["findings"] = [entry]
    ctx = _ctx(state, tmp_path, certified_head=head2)
    assert RC.check_disposition_without_receipt(ctx) is None


def test_C13_two_round_moving_head_verify_never_passes_refuses(tmp_path):
    head1, head2 = "a" * 40, "b" * 40
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"] = {"1": {"verifyResult": "pass", "fixFoldHead": head1}}
    _audit_discharge_fixed(state, head1)

    state["round"] = 2
    state["rounds"]["2"] = {}
    key, receipt2 = _audit_discharge_fixed(state, head2)
    assert receipt2.get("verifyResult") is None

    entry = _ledger_by_key(state)[key]
    state["dispositionLedgerOwner"] = "ledger"
    state["findings"] = [entry]
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "verify-not-pass"


def test_C13_fix_fold_records_fix_fold_head(tmp_path, monkeypatch):
    state = RD.new_state(_cfg())
    state["round"] = 2
    head = "f" * 40
    monkeypatch.setattr(RD, "_resolve_fix_fold_head_sha", lambda _sd, _st: (head, None))
    state["_fixBatch"] = []
    RD._fold_fixer(state, state["config"], {"fixes": []}, session_dir=str(tmp_path))
    assert state["rounds"]["2"]["fixFoldHead"] == head


def test_C13_delta_same_head_carries_prior_pass():
    head = "c" * 40
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["rounds"] = {"2": {"verifyResult": "pass", "fixFoldHead": head}}
    _audit_discharge_fixed(state, head)

    state["round"] = 3
    state["rounds"]["3"] = {}
    _, receipt3 = _audit_discharge_fixed(state, head)
    assert receipt3.get("verifyResult") == "pass"
    assert receipt3.get("headSha") == head


def test_C13_prior_verify_without_fix_fold_head_not_carried():
    head1, head2 = "d" * 40, "e" * 40
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"] = {"1": {"verifyResult": "pass"}}
    _audit_discharge_fixed(state, head1)

    state["round"] = 2
    state["rounds"]["2"] = {}
    _, receipt2 = _audit_discharge_fixed(state, head2)
    assert receipt2.get("verifyResult") is None


# --- L7 bite-proof: departure chokepoint ---------------------------------------------

def test_L7_archive_departure_without_prior_staging():
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    state["findings"] = compiled
    assert key not in _ledger_by_key(state)
    RD._set_findings(state, [])
    assert key in _ledger_by_key(state)


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


def test_L7_departure_preserves_raised_round_through_archive_and_record(tmp_path):
    finding = {"file": "d.py", "line": 1, "title": "live", "severity": "Important"}
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


# --- L8 uses L2 open-representative case (bite-proof run separately) -----------------
