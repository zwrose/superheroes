"""#1272 layer 2f: disposition-ledger owner marker classification and family sync preconditions."""
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
RR = _load("round_records")


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _cfg_cert(**over):
    base = _cfg()
    base["baseGuard"] = RC.BASE_GUARD_CHECKED
    base.update(over)
    return base


def _run_loop_seams():
    return {
        "reviewer": lambda dim, tier, rnd, ctx: [],
        "verifier": lambda clusters, rnd: [],
        "synthesis": lambda findings, rnd: None,
        "auditor": lambda targets, rnd: [],
        "fix_step": lambda batch, rnd, payload: {
            "fixes": [], "headDiff": "diff", "changedSubjects": ["Code"],
        },
        "verify_runner": lambda command, rnd: "pass",
        "io": {},
    }


def _state_canonical(state):
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _ledger_by_key(state):
    return {SC.finding_identity_key(e): e
            for e in (state.get("dispositionLedger") or []) if isinstance(e, dict)}


def _seed_live_finding(state, compiled):
    state["findings"] = [dict(compiled[0])]


def _family_slice(row):
    if not isinstance(row, dict):
        return {}
    return {f: row[f] for f in SC.DISPOSITION_FAMILY_FIELDS if f in row}


def _unrecognized_marker_state():
    legacy = {
        "file": "old.py", "line": 1, "title": "legacy", "severity": "Minor",
        SC.FINDING_KEY_FIELD: "legacy-key",
        "disposition": "refuted", "dispositionRound": 1, "refutedReason": "only-in-records",
    }
    return {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger-v2",
        "dispositionLedger": [],
        "findings": [],
        "_records": [{"findings": [legacy]}],
    }


def _null_owner_marker_state():
    legacy = {
        "file": "old.py", "line": 1, "title": "legacy", "severity": "Minor",
        SC.FINDING_KEY_FIELD: "legacy-key",
        "disposition": "fixed", "dispositionRound": 1,
    }
    return {
        "schemaVersion": 5,
        "dispositionLedgerOwner": None,
        "dispositionLedger": [],
        "findings": [],
        "_records": [{"findings": [legacy]}],
    }


def _ctx(state, tmp_path):
    session_dir = str(tmp_path / "sess")
    os.makedirs(session_dir, exist_ok=True)
    RD.save_state(session_dir, state)
    with open(os.path.join(session_dir, RD.JOURNAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("")
    head = "a" * 40
    meta = {"sessionId": "s", "headSha": head, "baseGuard": RC.BASE_GUARD_CHECKED}
    with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    state.setdefault("config", {})["baseGuard"] = RC.BASE_GUARD_CHECKED
    state["config"]["headSha"] = head
    RD.save_state(session_dir, state)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    return ctx


def _panel_artifact():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {
        "findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}],
    }
    return {"seats": seats}


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


# --- marker: certification refuses unrecognized ---------------------------------------

def test_marker_certification_refuses_unrecognized_via_findings_by_key():
    state = _unrecognized_marker_state()
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == "disposition-ledger-owner-unrecognized"
    assert "legacy-key" not in by_key


def test_marker_certification_refuses_unrecognized_via_findings_wrapper():
    state = _unrecognized_marker_state()
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is not None
    assert refusal["bindingFailure"] == "disposition-ledger-owner-unrecognized"
    assert by_key == {}


def test_marker_certification_refuses_unrecognized_via_check_disposition(tmp_path):
    state = _unrecognized_marker_state()
    ctx = _ctx(state, tmp_path)
    refusal = RC.check_disposition_without_receipt(ctx)
    assert refusal is not None
    assert refusal["bindingFailure"] == "disposition-ledger-owner-unrecognized"


def test_marker_certification_refuses_unrecognized_via_build_receipt(tmp_path):
    state = _unrecognized_marker_state()
    state["terminal"] = "converged"
    ctx = _ctx(state, tmp_path)
    receipt, refusal = RC._build_receipt(ctx, "certified", None)
    assert receipt is None
    assert refusal is not None
    assert refusal["bindingFailure"] == "disposition-ledger-owner-unrecognized"


def test_marker_certification_refuses_null_owner_via_findings_by_key():
    state = _null_owner_marker_state()
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is not None
    assert refusal["bindingFailure"] == "disposition-ledger-owner-unrecognized"
    assert "legacy-key" not in by_key


def test_marker_driver_submit_refuses_null_owner(tmp_path):
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"], n
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state["dispositionLedgerOwner"] = None
    RD.save_state(session_dir, state)
    n = RD.cmd_next(session_dir)
    assert n["ok"], n
    before = _state_bytes(session_dir)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                        _panel_artifact())
    assert out["ok"] is False
    assert out["reason"] == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    assert _state_bytes(session_dir) == before


def test_marker_fold_chokepoint_raises_on_null_owner():
    state = RD.new_state(_cfg())
    state["dispositionLedgerOwner"] = None
    before = _state_canonical(state)
    with pytest.raises(RD.DispositionLedgerOwnerRefusal) as exc:
        RD._fold(state, state["config"], RD.P_PANEL, _panel_artifact())
    assert exc.value.reason == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    assert _state_canonical(state) == before


# --- marker: driver submit preflight ------------------------------------------------

def test_marker_driver_submit_refuses_unrecognized(tmp_path):
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"], n
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state["dispositionLedgerOwner"] = "ledger-v2"
    RD.save_state(session_dir, state)
    n = RD.cmd_next(session_dir)
    assert n["ok"], n
    before = _state_bytes(session_dir)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                        _panel_artifact())
    assert out["ok"] is False
    assert out["reason"] == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    assert _state_bytes(session_dir) == before
    ok, after = RD.load_state(session_dir)
    assert ok and after is not None
    assert after.get("pending") == state.get("pending")
    journal = RD.read_journal(session_dir)
    assert journal[-1].get("outcome") == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE


# --- marker: absent and recognized regression floor -----------------------------------

def test_marker_absent_backfills_on_first_stage():
    old = {"file": "o", "line": 1, "title": "old", "severity": "Important",
           SC.FINDING_KEY_FIELD: "o::old@L1"}
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["_records"] = [{"findings": [old]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    assert "o::old@L1" in ledger
    assert state["dispositionLedgerOwner"] == "ledger"


def test_marker_recognized_skips_backfill():
    old = {"file": "o", "line": 1, "title": "old", "severity": "Important",
           SC.FINDING_KEY_FIELD: "o::old@L1"}
    new_raw = {"file": "n", "line": 2, "title": "new", "severity": "Minor"}
    compiled, _ = RD.mechanical_compile([new_raw], None)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["dispositionLedgerOwner"] = "ledger"
    state["dispositionLedger"] = []
    state["_records"] = [{"findings": [old]}]
    RD._stage_findings(state, compiled)
    ledger = _ledger_by_key(state)
    assert "o::old@L1" not in ledger


# --- family sync ----------------------------------------------------------------------

def test_family_sync_restaged_key_clears_prior_family():
    finding = {"file": "r.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    RD._stage_findings(state, compiled)
    _seed_live_finding(state, compiled)
    RD._record_disposition(state, key, "refuted", 1, refutedReason="first")
    RD._record_disposition(state, key, "fixed", 2,
                           dispositionReceipt={"headSha": "b" * 40, "verifyResult": "pass"})
    entry = _ledger_by_key(state)[key]
    live = next(f for f in (state.get("findings") or [])
                if SC.finding_identity_key(f) == key)
    assert _family_slice(entry) == _family_slice(live)
    assert "refutedReason" not in entry
    assert "refutedReason" not in live


def test_family_sync_merge_over_disposition_keeps_only_merged_into():
    finding = {"file": "m.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    RD._stage_findings(state, compiled)
    _seed_live_finding(state, compiled)
    RD._record_disposition(state, key, "fixed", 1,
                           dispositionReceipt={"headSha": "a" * 40, "verifyResult": "pass"})
    into_key = "other-key"
    RD._record_merged_into(state, key, into_key)
    entry = _ledger_by_key(state)[key]
    live = next(f for f in (state.get("findings") or [])
                if SC.finding_identity_key(f) == key)
    assert set(_family_slice(entry)) == {SC.MERGED_INTO_FIELD}
    assert entry[SC.MERGED_INTO_FIELD] == into_key
    assert _family_slice(entry) == _family_slice(live)


def test_family_sync_no_live_row_ledger_only():
    key = "orphan-key"
    state = RD.new_state(_cfg())
    state["findings"] = []
    RD._record_disposition(state, key, "refuted", 1, refutedReason="gone")
    entry = _ledger_by_key(state)[key]
    assert entry["disposition"] == "refuted"
    RD._record_merged_into(state, key, "keeper")
    entry = _ledger_by_key(state)[key]
    assert set(_family_slice(entry)) == {SC.MERGED_INTO_FIELD}


# --- marker: _fold chokepoint refuses unrecognized ------------------------------------

def test_marker_run_loop_parks_on_unrecognized_disposition_ledger_owner():
    parked_reasons = []
    orig_park = RD._park_cannot_certify
    orig_new_state = RD.new_state

    def _capture_park(state, detail):
        parked_reasons.append(detail)
        return orig_park(state, detail)

    def _state_with_unrecognized_marker(config=None):
        state = orig_new_state(config)
        state["dispositionLedgerOwner"] = "ledger-v2"
        return state

    RD._park_cannot_certify = _capture_park
    RD.new_state = _state_with_unrecognized_marker
    try:
        result = RD.run_loop(_run_loop_seams(), _cfg_cert())
    finally:
        RD._park_cannot_certify = orig_park
        RD.new_state = orig_new_state
    assert result["loopTerminal"] == "cannot-certify"
    assert result["loopCertificationShape"] is None
    assert "verdict" not in result
    assert parked_reasons == [RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE]


def test_marker_fold_chokepoint_raises_before_mutation():
    state = RD.new_state(_cfg())
    state["dispositionLedgerOwner"] = "ledger-v2"
    before = _state_canonical(state)
    with pytest.raises(RD.DispositionLedgerOwnerRefusal) as exc:
        RD._fold(state, state["config"], RD.P_PANEL, _panel_artifact())
    assert exc.value.reason == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    assert _state_canonical(state) == before


def test_marker_fold_absent_marker_still_folds():
    state = RD.new_state(_cfg())
    RD._fold(state, state["config"], RD.P_PANEL, _panel_artifact())
    assert state.get("rounds")


def test_marker_fold_recognized_marker_still_folds():
    state = RD.new_state(_cfg())
    state["dispositionLedgerOwner"] = "ledger"
    state["dispositionLedger"] = []
    RD._fold(state, state["config"], RD.P_PANEL, _panel_artifact())
    assert state.get("rounds")


# --- bite-proof detectors (axis lines live at the guarded production sites) -------------

def test_bite_bp2f_a_certification_marker_refusal():
    """axis: unrecognized dispositionLedgerOwner refuses certification reads — never legacy merge."""
    state = _unrecognized_marker_state()
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is not None
    assert "legacy-key" not in by_key


def test_bite_bp2f_b_driver_submit_preflight_refusal(tmp_path):
    """axis: unrecognized dispositionLedgerOwner refuses submit before fold — state byte-unchanged."""
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    ok, state = RD.load_state(session_dir)
    state["dispositionLedgerOwner"] = "ledger-v2"
    RD.save_state(session_dir, state)
    n = RD.cmd_next(session_dir)
    assert n["ok"], n
    before = _state_bytes(session_dir)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                        _panel_artifact())
    assert out["ok"] is False
    assert _state_bytes(session_dir) == before


def test_bite_bp2f_c_record_disposition_family_sync():
    """axis: re-staged disposition family is byte-equal on ledger and live with no stale fields."""
    finding = {"file": "b.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    RD._stage_findings(state, compiled)
    _seed_live_finding(state, compiled)
    RD._record_disposition(state, key, "refuted", 1, refutedReason="stale")
    RD._record_disposition(state, key, "fixed", 2,
                           dispositionReceipt={"headSha": "c" * 40, "verifyResult": "pass"})
    entry = _ledger_by_key(state)[key]
    live = next(f for f in (state.get("findings") or [])
                if SC.finding_identity_key(f) == key)
    assert _family_slice(entry) == _family_slice(live)
    assert "refutedReason" not in entry


def test_bite_bp2f_d_record_merged_into_family_sync():
    """axis: merge records only mergedInto on ledger and live — prior disposition family cleared."""
    finding = {"file": "b.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    key = SC.finding_identity_key(compiled[0])
    RD._stage_findings(state, compiled)
    _seed_live_finding(state, compiled)
    RD._record_disposition(state, key, "fixed", 1,
                           dispositionReceipt={"headSha": "d" * 40, "verifyResult": "pass"})
    RD._record_merged_into(state, key, "keeper")
    entry = _ledger_by_key(state)[key]
    live = next(f for f in (state.get("findings") or [])
                if SC.finding_identity_key(f) == key)
    assert set(_family_slice(entry)) == {SC.MERGED_INTO_FIELD}
    assert _family_slice(entry) == _family_slice(live)


def test_bite_bp2f_i_fold_chokepoint_refusal():
    """axis: unrecognized dispositionLedgerOwner refuses at _fold — never reaches a fold arm."""
    state = RD.new_state(_cfg())
    state["dispositionLedgerOwner"] = "ledger-v2"
    with pytest.raises(RD.DispositionLedgerOwnerRefusal):
        RD._fold(state, state["config"], RD.P_PANEL, _panel_artifact())
