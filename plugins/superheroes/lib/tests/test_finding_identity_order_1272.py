"""#1272 layer 2: finding keys are a pure function of content, not list position."""
import copy
import importlib.util
import os
import sys

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


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _clamped_collision_pair():
    prefix = "x" * 165
    alpha = {"file": "f.py", "line": 5, "title": prefix + " alpha", "severity": "Important"}
    beta = {"file": "f.py", "line": 5, "title": prefix + " beta", "severity": "Important"}
    return alpha, beta


def test_compile_and_set_findings_order_independent_keys():
    """T1: clamped-title collision — same key set regardless of compile/set order."""
    alpha, beta = _clamped_collision_pair()
    compiled_ab, _ = RD.mechanical_compile([alpha, beta], None)
    compiled_ba, _ = RD.mechanical_compile([beta, alpha], None)
    keys_ab = {f[SC.FINDING_KEY_FIELD] for f in compiled_ab}
    keys_ba = {f[SC.FINDING_KEY_FIELD] for f in compiled_ba}
    assert keys_ab == keys_ba
    assert len(keys_ab) == 2

    state_alpha_first = RD.new_state(_cfg())
    RD._set_findings(state_alpha_first, compiled_ab)
    map_alpha_first = {
        SC.finding_identity_key(f): f.get("title") for f in state_alpha_first["findings"]
    }

    state_beta_first = RD.new_state(_cfg())
    RD._set_findings(state_beta_first, compiled_ba)
    map_beta_first = {
        SC.finding_identity_key(f): f.get("title") for f in state_beta_first["findings"]
    }
    assert map_alpha_first == map_beta_first

    state_audit_ab = RD.new_state(_cfg())
    state_audit_ab["fixBatch"] = list(compiled_ab)
    targets_ab = RD._audit_targets(state_audit_ab, state_audit_ab["config"], {})
    id_title_ab = {t["id"]: t["title"] for t in targets_ab}

    state_audit_ba = RD.new_state(_cfg())
    state_audit_ba["fixBatch"] = list(compiled_ba)
    targets_ba = RD._audit_targets(state_audit_ba, state_audit_ba["config"], {})
    id_title_ba = {t["id"]: t["title"] for t in targets_ba}
    assert id_title_ab == id_title_ba


def test_set_findings_merges_identical_content_same_key():
    """T2: duplicate content collapses to one row; higher severity and unioned dimension win."""
    base = {"file": "a.py", "line": 1, "title": "bug", "severity": "Minor", "dimension": "Code"}
    state = RD.new_state(_cfg())
    RD._set_findings(state, [dict(base), dict(base)])
    assert len(state["findings"]) == 1

    copy_a = dict(base)
    copy_b = dict(base)
    copy_b["severity"] = "Important"
    copy_b["dimension"] = "Security"
    state2 = RD.new_state(_cfg())
    RD._set_findings(state2, [copy_a, copy_b])
    assert len(state2["findings"]) == 1
    survivor = state2["findings"][0]
    assert survivor["severity"] == "Important"
    assert survivor["dimension"] == "Code + Security"


def test_audit_target_preserves_opaque_requeued_id():
    """T3: fix-batch row with id and no findingKey keeps that id as audit target id."""
    row = {
        "id": "opaque@L1#1",
        "file": "f.py",
        "line": 1,
        "title": "legacy",
        "severity": "Important",
    }
    state = RD.new_state(_cfg())
    state["fixBatch"] = [row]
    targets = RD._audit_targets(state, state["config"], {})
    assert len(targets) == 1
    assert targets[0]["id"] == "opaque@L1#1"


def test_readers_do_not_mutate_rows_missing_finding_key():
    """T4: _judgment_row_ids and _audit_targets never write findingKey onto caller rows."""
    row = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}
    mint_state = RD.new_state(_cfg())
    RD._set_findings(mint_state, [dict(row)])
    expected_key = mint_state["findings"][0][SC.FINDING_KEY_FIELD]

    judgment_row = copy.deepcopy(row)
    before_judgment = copy.deepcopy(judgment_row)
    ids = RD._judgment_row_ids([judgment_row])
    assert judgment_row == before_judgment
    assert ids == [expected_key]

    audit_row = copy.deepcopy(row)
    audit_state = RD.new_state(_cfg())
    audit_state["fixBatch"] = [audit_row]
    before_fix_batch = copy.deepcopy(audit_state["fixBatch"])
    targets = RD._audit_targets(audit_state, audit_state["config"], {})
    assert audit_state["fixBatch"] == before_fix_batch
    assert len(targets) == 1
    assert targets[0]["id"] == expected_key
