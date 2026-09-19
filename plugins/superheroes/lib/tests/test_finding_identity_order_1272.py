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
RC = _load("round_certification")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}
    base.update(over)
    return base


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


def test_audit_target_keys_opaque_id_row_by_content_and_stamps_marker():
    """T3: fix-batch row with opaque id and no findingKey keys by content, stamps marker."""
    row = {
        "id": "opaque@L1#1",
        "file": "f.py",
        "line": 1,
        "title": "legacy",
        "severity": "Important",
    }
    before = copy.deepcopy(row)
    state = RD.new_state(_cfg())
    state["fixBatch"] = [row]
    targets = RD._audit_targets(state, state["config"], {})
    assert len(targets) == 1
    assert targets[0]["id"] == SC.finding_identity_key(row)
    assert targets[0][SC.FINDING_KEY_FIELD] == targets[0]["id"]
    assert row == before


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


def test_finding_key_of_prefers_finding_key_over_id():
    """T5: _finding_key_of prefers findingKey over legacy id."""
    minted = SC.location_key({"file": "a.py", "line": 1, "title": "t"})
    row = {
        "id": "seat-controlled-id",
        SC.FINDING_KEY_FIELD: minted,
        "file": "a.py",
        "line": 1,
        "title": "t",
    }
    assert RD._finding_key_of(row) == minted
    assert RD._judgment_row_ids([row]) == [minted]
    state = RD.new_state(_cfg())
    state["fixBatch"] = [row]
    targets = RD._audit_targets(state, state["config"], {})
    assert len(targets) == 1
    assert targets[0]["id"] == minted


def test_carry_recombination_merges_same_anchor_rows_with_different_severity():
    """T6: carry concatenation merges loop-owned keys with different severity/dimension."""
    base = {"file": "a.py", "line": 1, "title": "t"}
    minor = dict(base, severity="Minor", dimension="Code")
    important = dict(base, severity="Important", dimension="Security")
    compiled_a, _ = RD.mechanical_compile([minor], None)
    compiled_b, _ = RD.mechanical_compile([important], None)
    expected_key = SC.location_key(base)

    state = RD.new_state(_cfg())
    RD._set_findings(state, compiled_a + compiled_b)
    assert len(state["findings"]) == 1
    survivor = state["findings"][0]
    assert survivor["severity"] == "Important"
    assert survivor["dimension"] == "Code + Security"
    assert survivor[SC.FINDING_KEY_FIELD] == expected_key

    state_rev = RD.new_state(_cfg())
    RD._set_findings(state_rev, compiled_b + compiled_a)
    assert len(state_rev["findings"]) == 1
    assert state_rev["findings"][0][SC.FINDING_KEY_FIELD] == expected_key


def test_legacy_unsuffixed_key_bridges_to_recompiled_long_title_copy():
    """T8: legacy unsuffixed loop key merges with freshly compiled long-title copy."""
    prefix = "x" * 165
    finding = {"file": "f.py", "line": 5, "title": prefix + " alpha", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    minted_key = compiled[0][SC.FINDING_KEY_FIELD]
    bare_key = SC.location_key(finding)
    assert minted_key != bare_key
    assert "#" in minted_key
    legacy = dict(finding, **{SC.FINDING_KEY_FIELD: bare_key})

    state = RD.new_state(_cfg())
    RD._set_findings(state, [legacy] + compiled)
    assert len(state["findings"]) == 1
    assert state["findings"][0][SC.FINDING_KEY_FIELD] == bare_key

    state2 = RD.new_state(_cfg())
    RD._set_findings(state2, compiled + [legacy])
    assert len(state2["findings"]) == 1
    assert state2["findings"][0][SC.FINDING_KEY_FIELD] == bare_key


def test_ambiguous_legacy_key_never_collapses_distinct_findings():
    """T10: two distinct long-title findings sharing one bare legacy key keep minted keys."""
    prefix = "x" * 165
    alpha = {"file": "f.py", "line": 5, "title": prefix + " alpha", "severity": "Important"}
    bravo = {"file": "f.py", "line": 5, "title": prefix + " bravo", "severity": "Important"}
    bare_key = SC.location_key(alpha)
    legacy_a = dict(alpha, **{SC.FINDING_KEY_FIELD: bare_key})
    legacy_b = dict(bravo, **{SC.FINDING_KEY_FIELD: bare_key})

    state = RD.new_state(_cfg())
    RD._set_findings(state, [legacy_a, legacy_b])
    keys = [f[SC.FINDING_KEY_FIELD] for f in state["findings"]]
    assert len(state["findings"]) == 2
    assert keys[0] != keys[1]
    assert "#" in keys[0] and "#" in keys[1]

    state_rev = RD.new_state(_cfg())
    RD._set_findings(state_rev, [legacy_b, legacy_a])
    keys_rev = [f[SC.FINDING_KEY_FIELD] for f in state_rev["findings"]]
    assert len(state_rev["findings"]) == 2
    assert keys_rev[0] != keys_rev[1]
    assert "#" in keys_rev[0] and "#" in keys_rev[1]


def test_staged_id_is_never_a_finding_identity():
    """T11: staged v<N> ids are positional — keyed by minted content, not the staged id."""
    row = {"id": "v0", "file": "a.py", "line": 1, "title": "t", "severity": "Important"}
    assert RD._finding_key_of(row) == SC.location_key(row)
    assert RD._judgment_row_ids([row]) == [SC.location_key(row)]

    rowA = row
    rowB = {"id": "v0", "file": "b.py", "line": 9, "title": "u", "severity": "Important"}
    state = RD.new_state(_cfg())
    state["fixBatch"] = [rowA, rowB]
    before_fix_batch = copy.deepcopy(state["fixBatch"])
    targets = RD._audit_targets(state, state["config"], {})
    assert state["fixBatch"] == before_fix_batch
    assert len(targets) == 2
    assert targets[0]["id"] != targets[1]["id"]
    assert targets[0]["id"] != "v0"
    assert targets[1]["id"] != "v0"
    assert len(RD._union_open_blockers(targets)) == 2


def test_merge_same_finding_rederives_classification_from_merged_tradeoff():
    """T12: merged classification always follows merged tradeoff."""
    base = {"file": "a.py", "line": 1, "title": "t"}
    existing = dict(base, severity="Important", tradeoff=False, classification="mechanical")
    incoming = dict(base, severity="Minor", tradeoff=True, classification="mechanical")
    state = RD.new_state(_cfg())
    RD._set_findings(state, [existing, incoming])
    survivor = state["findings"][0]
    assert survivor["tradeoff"] is True
    assert survivor["classification"] == "judgment"

    both_false_existing = dict(base, severity="Important", tradeoff=False, classification="mechanical")
    both_false_incoming = dict(base, severity="Minor", tradeoff=False, classification="judgment")
    state2 = RD.new_state(_cfg())
    RD._set_findings(state2, [both_false_existing, both_false_incoming])
    assert state2["findings"][0]["tradeoff"] is False
    assert state2["findings"][0]["classification"] == "mechanical"


def test_foreign_preset_key_collision_still_rekeys():
    """T7: foreign preset keys on different locations stay content-hash re-keyed."""
    finding1 = {
        "file": "b.py",
        "line": 10,
        "title": "first",
        "severity": "Important",
        SC.FINDING_KEY_FIELD: "caller-controlled",
    }
    finding2 = {
        "file": "c.py",
        "line": 20,
        "title": "second",
        "severity": "Important",
        SC.FINDING_KEY_FIELD: "caller-controlled",
    }
    state = RD.new_state(_cfg())
    RD._set_findings(state, [finding1, finding2])
    keys = [f[SC.FINDING_KEY_FIELD] for f in state["findings"]]
    assert len(keys) == 2
    assert keys[0].startswith("caller-controlled#") and len(keys[0]) == len("caller-controlled#") + 12
    assert keys[1].startswith("caller-controlled#") and len(keys[1]) == len("caller-controlled#") + 12


def test_legacy_bare_key_with_clamp_exact_new_finding_keeps_two_rows():
    """T13: legacy bare K plus clamp-exact new row at same location keeps two rows."""
    from finding_identity import clamp_title, finding_label

    prefix = "x" * 165
    long = {"file": "f.py", "line": 5, "title": prefix + " alpha", "severity": "Critical"}
    bare = SC.location_key(long)
    legacy = dict(long, **{SC.FINDING_KEY_FIELD: bare})
    short_title = clamp_title(finding_label(long))
    short = dict(long, title=short_title, severity="Important")
    assert SC.location_key(short) == bare
    assert SC.minted_identity_key(short) == bare

    state = RD.new_state(_cfg())
    RD._set_findings(state, [legacy, short])
    assert len(state["findings"]) == 2
    keys = {f[SC.FINDING_KEY_FIELD] for f in state["findings"]}
    assert keys == {bare, SC.minted_identity_key(long)}

    state_rev = RD.new_state(_cfg())
    RD._set_findings(state_rev, [short, legacy])
    assert len(state_rev["findings"]) == 2
    keys_rev = {f[SC.FINDING_KEY_FIELD] for f in state_rev["findings"]}
    assert keys_rev == {bare, SC.minted_identity_key(long)}

    foreign = {
        "file": "g.py", "line": 1, "title": "other", "severity": "Important",
        SC.FINDING_KEY_FIELD: bare,
    }
    state_foreign = RD.new_state(_cfg())
    RD._set_findings(state_foreign, [legacy, foreign])
    assert len(state_foreign["findings"]) == 2
    by_file = {f["file"]: f[SC.FINDING_KEY_FIELD] for f in state_foreign["findings"]}
    assert by_file["g.py"] == bare
    assert by_file["f.py"] == SC.minted_identity_key(long)


def test_foreign_collision_keys_are_staging_order_independent():
    """T14: foreign preset collision keys are independent of staging order and transient fields."""
    V = _load("verification")
    finding1 = {
        "file": "b.py", "line": 10, "title": "first", "severity": "Important",
        SC.FINDING_KEY_FIELD: "caller-controlled",
    }
    finding2 = {
        "file": "c.py", "line": 20, "title": "second", "severity": "Important",
        SC.FINDING_KEY_FIELD: "caller-controlled",
    }
    staged_a = V.stage_ids([finding1, finding2])
    staged_b = V.stage_ids([finding2, finding1])
    state_a = RD.new_state(_cfg())
    RD._set_findings(state_a, staged_a)
    state_b = RD.new_state(_cfg())
    RD._set_findings(state_b, staged_b)
    keys_a = {f[SC.FINDING_KEY_FIELD] for f in state_a["findings"]}
    keys_b = {f[SC.FINDING_KEY_FIELD] for f in state_b["findings"]}
    assert keys_a == keys_b

    stamped_a = [dict(f, verdict="CONFIRMED", evidence="a") for f in staged_a]
    stamped_b = [dict(f, verdict="REFUTED", evidence="b") for f in staged_b]
    state_sa = RD.new_state(_cfg())
    RD._set_findings(state_sa, stamped_a)
    state_sb = RD.new_state(_cfg())
    RD._set_findings(state_sb, stamped_b)
    assert {f[SC.FINDING_KEY_FIELD] for f in state_sa["findings"]} == keys_a
    assert {f[SC.FINDING_KEY_FIELD] for f in state_sb["findings"]} == keys_b


def test_finding_identity_has_one_home_driver_and_certification_agree():
    """T15: two unkeyed long-title siblings stay distinct; driver and certification agree."""
    alpha, beta = _clamped_collision_pair()
    state = RD.new_state(_cfg())
    RD._set_findings(state, [alpha, beta])
    assert len(state["findings"]) == 2
    certified = RC._certification_findings(state)
    assert len(certified) == 2
    a, b = state["findings"][0], state["findings"][1]
    assert SC.finding_identity_key(a) != SC.finding_identity_key(b)
    assert RD._finding_key_of(a) == SC.finding_identity_key(a)
    assert RD._finding_key_of(b) == SC.finding_identity_key(b)


def test_persisted_targets_without_marker_dedupe_by_content():
    """T16: persisted audit targets without findingKey dedupe by content identity."""
    ident = SC.finding_identity_key({"file": "f.py", "line": 4, "title": "same"})
    target_k = {
        "id": ident, "identity": ident.split("@L")[0], "file": "f.py", "line": 4,
        "title": "same", "severity": "Important",
    }
    target_suffix = {
        "id": ident + "#1", "identity": ident.split("@L")[0], "file": "f.py", "line": 4,
        "title": "same", "severity": "Important",
    }
    batch = RD._union_open_blockers([target_k], [target_suffix])
    assert len(batch) == 1

    marker_a = ident + "@L1"
    marker_b = ident + "@L1#abcdef012345"
    target_marked_a = dict(target_k, id=marker_a, **{SC.FINDING_KEY_FIELD: marker_a})
    target_marked_b = dict(target_k, id=marker_b, **{SC.FINDING_KEY_FIELD: marker_b})
    batch_marked = RD._union_open_blockers([target_marked_a], [target_marked_b])
    assert len(batch_marked) == 2

    state = RD.new_state(_cfg(maxRounds=20))
    state["_auditTargets"] = [target_k, target_suffix]
    state["_auditOutcome"] = {"notDischarged": [target_k["id"], target_suffix["id"]], "discharged": []}
    state["auditRounds"] = [{"round": 2, "outcomes": []}]
    state["findings"] = []
    RD._settle_delta(state, state["config"])
    assert state.get("step") == RD.P_FIXER
    fix_batch = state.get("_fixBatch") or []
    assert len(fix_batch) == 1


def test_identity_derivation_has_one_home_census():
    """Census: identity derivation lives only in session_contract except _mint_finding_keys."""
    import ast

    forbidden_calls = {
        "location_key", "clamp_title", "_loop_minted_key", "_title_clamp_hash_suffix",
        "_location_id", "_finding_content_canonical", "_content_hash_suffix",
    }
    forbidden_defs = {
        "_loop_minted_key", "_title_clamp_hash_suffix", "_location_id",
        "_finding_content_canonical", "_content_hash_suffix",
    }
    modules = ("round_driver", "round_certification", "round_records", "verification")
    for mod_name in modules:
        path = os.path.join(_LIB, mod_name + ".py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        mint_fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_mint_finding_keys":
                mint_fn = node
                break
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in forbidden_defs:
                raise AssertionError("%s defines forbidden %s" % (mod_name, node.name))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if mint_fn is not None and hasattr(node, "lineno"):
                if mint_fn.lineno <= node.lineno <= getattr(mint_fn, "end_lineno", mint_fn.lineno):
                    continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in forbidden_calls:
                raise AssertionError("%s calls forbidden %s at line %s" % (mod_name, name, node.lineno))
    rd_path = os.path.join(_LIB, "round_driver.py")
    with open(rd_path, encoding="utf-8") as fh:
        rd_src = fh.read()
    assert "session_contract.finding_identity_key" in rd_src
    rc_path = os.path.join(_LIB, "round_certification.py")
    with open(rc_path, encoding="utf-8") as fh:
        rc_src = fh.read()
    assert "finding_identity_key" in rc_src
