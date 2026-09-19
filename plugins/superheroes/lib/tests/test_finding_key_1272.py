"""#1272: durable findingKey identity — loop-owned, never positional vN id."""
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
RC = _load("round_certification")
V = _load("verification")


def _pad_to_index(finding, index=3):
    batch = [
        {"file": "pad.py", "line": i + 1, "title": "pad%d" % i, "severity": "Minor"}
        for i in range(index)
    ]
    batch.append(finding)
    return V.stage_ids(batch)[index]


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


# --- T1: DoD grader — unrelated v3 findings do not collide -----------------------------------

def test_unrelated_v3_findings_distinct_ledger_and_certification():
    finding1 = _pad_to_index({
        "file": "b.py",
        "line": 10,
        "title": "round1 bug",
        "severity": "Important",
        "disposition": "refuted",
    })
    assert finding1["id"] == "v3"

    finding2 = _pad_to_index({
        "file": "c.py",
        "line": 20,
        "title": "round2 bug",
        "severity": "Important",
    })
    assert finding2["id"] == "v3"

    state = RD.new_state(_cfg())
    RD._set_findings(state, [finding1])
    key1 = SC.finding_identity_key(state["findings"][0])
    assert key1 and key1 != "v3"

    RD._set_findings(state, [finding2])
    assert len(state["findings"]) == 1
    assert state["findings"][0]["file"] == "c.py"
    key2 = SC.finding_identity_key(state["findings"][0])
    assert key2 and key2 != "v3"
    assert key1 != key2

    ledger = state.get("dispositionLedger") or []
    assert len(ledger) == 1
    assert ledger[0]["file"] == "b.py"
    assert ledger[0]["disposition"] == "refuted"
    assert SC.finding_identity_key(ledger[0]) == key1

    certified = RC._certification_findings(state)
    cert_keys = {SC.finding_identity_key(f) for f in certified}
    assert key1 in cert_keys
    assert key2 in cert_keys
    assert len(cert_keys) == 2


# --- T2: mechanical_compile mints findingKey; verification pipeline preserves it ---------------

def test_mechanical_compile_mints_finding_key_equal_to_location_id():
    findings = [
        {"file": "f.py", "line": 5, "title": "leak", "severity": "Important"},
        {"file": "g.py", "line": 2, "title": "race", "severity": "Minor"},
    ]
    compiled, _ = RD.mechanical_compile(findings, None)
    for f in compiled:
        assert f.get(SC.FINDING_KEY_FIELD) == RD._location_id(f)


def test_mechanical_compile_discards_inbound_finding_key():
    findings = [
        {"file": "f.py", "line": 5, "title": "leak", "severity": "Important",
         SC.FINDING_KEY_FIELD: "caller-controlled"},
        {"file": "g.py", "line": 2, "title": "race", "severity": "Minor",
         SC.FINDING_KEY_FIELD: "caller-controlled"},
    ]
    compiled, _ = RD.mechanical_compile(findings, None)
    keys = [f[SC.FINDING_KEY_FIELD] for f in compiled]
    assert "caller-controlled" not in keys
    assert len(set(keys)) == 2


def test_mechanical_compile_mints_distinct_keys_when_location_collides():
    prefix = "x" * 165
    findings = [
        {"file": "f.py", "line": 5, "title": prefix + " alpha", "severity": "Important"},
        {"file": "f.py", "line": 5, "title": prefix + " beta", "severity": "Important"},
    ]
    compiled, _ = RD.mechanical_compile(findings, None)
    keys = [f[SC.FINDING_KEY_FIELD] for f in compiled]
    assert len(keys) == 2
    assert keys[0] != keys[1]
    assert keys[1] == keys[0] + "#1"


def test_seat_supplied_duplicate_finding_keys_do_not_collide_in_ledger():
    finding1 = {
        "file": "b.py", "line": 10, "title": "first defect", "severity": "Important",
        "disposition": "refuted", SC.FINDING_KEY_FIELD: "caller-controlled",
    }
    finding2 = {
        "file": "c.py", "line": 20, "title": "second defect", "severity": "Important",
        SC.FINDING_KEY_FIELD: "caller-controlled",
    }
    compiled1, _ = RD.mechanical_compile([finding1], None)
    compiled2, _ = RD.mechanical_compile([finding2], None)
    state = RD.new_state(_cfg())
    RD._set_findings(state, compiled1)
    key1 = SC.finding_identity_key(state["findings"][0])
    RD._set_findings(state, compiled2)
    key2 = SC.finding_identity_key(state["findings"][0])
    assert key1 != "caller-controlled"
    assert key2 != "caller-controlled"
    assert key1 != key2
    ledger = state.get("dispositionLedger") or []
    assert len(ledger) == 1
    assert SC.finding_identity_key(ledger[0]) == key1


def test_stage_ids_preserves_finding_key_while_rewriting_id():
    raw = {"file": "h.py", "line": 7, "title": "x", "severity": "Minor"}
    compiled, _ = RD.mechanical_compile([raw], None)
    minted_key = compiled[0][SC.FINDING_KEY_FIELD]
    staged = V.stage_ids(compiled)
    assert staged[0]["id"] == "v0"
    assert staged[0][SC.FINDING_KEY_FIELD] == minted_key


def test_apply_verdicts_merge_and_rank_author_filter_preserve_finding_key():
    raw = {"file": "i.py", "line": 3, "title": "y", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([raw], None)
    minted_key = compiled[0][SC.FINDING_KEY_FIELD]
    staged = V.stage_ids(compiled)
    fid = staged[0]["id"]
    result = V.apply_verdicts(staged, [{"id": fid, "verdict": "CONFIRMED", "evidence": "seen"}])
    survivors = result["findings"]
    merged = V.merge_and_rank(survivors)["findings"]
    kept, _ = RD.author_justification_filter(merged, [])
    assert kept[0][SC.FINDING_KEY_FIELD] == minted_key


# --- T3: finding_identity_key never returns positional id ------------------------------------

def test_finding_identity_key_never_returns_positional_id():
    f = {"id": "v3", "file": "z.py", "line": 1, "title": "only id"}
    key = SC.finding_identity_key(f)
    assert key != "v3"
    assert key == RD._location_id(f)


# --- T4: fail-closed edges E1–E3, E6 ---------------------------------------------------------

def test_edge_e1_no_file_no_title_returns_location_form_no_exception():
    key = SC.finding_identity_key({})
    assert key is not None
    assert "@L" in key


def test_edge_e2_non_str_label_no_exception():
    for bad in (42, ["x"], None):
        f = {"file": "a.py", "line": 1, "title": bad}
        key = SC.finding_identity_key(f)
        assert isinstance(key, str) and key


def test_edge_e3_empty_or_non_str_finding_key_uses_location():
    loc = SC.location_key({"file": "a.py", "line": 2, "title": "t"})
    assert SC.finding_identity_key({"file": "a.py", "line": 2, "title": "t", SC.FINDING_KEY_FIELD: ""}) == loc
    assert SC.finding_identity_key({"file": "a.py", "line": 2, "title": "t", SC.FINDING_KEY_FIELD: 99}) == loc


def test_edge_e6_existing_finding_key_not_re_minted():
    preserved = "custom-stable-key"
    f = {"file": "a.py", "line": 1, "title": "t", SC.FINDING_KEY_FIELD: preserved}
    RD._mint_finding_keys([f])
    assert f[SC.FINDING_KEY_FIELD] == preserved


def test_edge_e4_non_dict_skipped_by_mint_and_identity_key_returns_none():
    mixed = ["not-a-dict", {"file": "a.py", "line": 1, "title": "ok"}]
    RD._mint_finding_keys(mixed)
    assert SC.finding_identity_key("not-a-dict") is None


# --- T5: legacy id-only ledger and live entries key by location ------------------------------

def test_legacy_id_only_entries_key_by_location_not_v3():
    state = RD.new_state(_cfg())
    legacy_ledger = {"id": "v3", "file": "old.py", "line": 5, "title": "legacy", "disposition": "fixed"}
    live = {"id": "v3", "file": "new.py", "line": 9, "title": "live"}
    state["dispositionLedger"] = [legacy_ledger]
    RD._set_findings(state, [live])

    ledger_key = SC.finding_identity_key(state["dispositionLedger"][0])
    live_key = SC.finding_identity_key(state["findings"][0])
    assert ledger_key != "v3"
    assert live_key != "v3"
    assert ledger_key != live_key
