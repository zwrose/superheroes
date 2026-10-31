"""#2157 — `rule` refuses a finding id that names more than one finding.

A staged id (`v0`..`vN`) is minted positionally by every verifier attempt, so the same id names a
different finding in each attempt. A ruling id resolves to a finding only when every store, and every
recorded verifier attempt, binds it to the same finding; otherwise `rule` refuses
`ruling-target-ambiguous`, lists the candidates, and writes nothing. A ruling that names the finding by
its `findingKey` binds.

Groups: DoD-1 the id names two findings (live stores, second-test carry, attempt history) · DoD-2 the
key binds · DoD-3 a unique id binds · R4 the non-dict placeholder is not a candidate · H the history
recorder and its reader tolerate every malformed shape.
"""
import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_second_test_c1l7 as C1L7  # noqa: E402

RD = C1L7.RD

_SPEC = importlib.util.spec_from_file_location(
    "test_rulings_channel_1445", os.path.join(_HERE, "test_rulings_channel_1445.py"))
_RC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RC)

_write_ruling_file = _RC._write_ruling_file
_rule = _RC._rule
_state = _RC._state
_state_bytes = _RC._state_bytes
_pending_apply_fixes_two_findings = _RC._pending_apply_fixes_two_findings
_provenance = _RC._provenance

Round = C1L7.Round
_HELD = C1L7._HELD
_PLAIN = C1L7._PLAIN
_MISSED = C1L7._MISSED
_PLAUSIBLE = C1L7._PLAUSIBLE


def _guidance(rid):
    return {"id": rid, "ruling": "guidance", "reason": "r", "guidance": "g"}


def _scrub_ids(state):
    """Drop every staged id the driven session left in the stores, so a test binds exactly the ids it sets."""
    for store in ("findings", "_fixBatch", "_fixQueue", "fixBatch", "_verified", "_refuted",
                  "_toVerify", "dispositionLedger"):
        for row in state.get(store) or []:
            if isinstance(row, dict):
                row.pop("id", None)
    state.pop(RD.STAGED_ID_BINDINGS_FIELD, None)


def _reused_id_session(tmp_path, a_lives_in):
    """A pending session where finding A holds `v0` in ``a_lives_in`` and the current attempt stages a
    different finding B as `v0`. Returns ``(session_dir, key_a, key_b)``."""
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    key_a, key_b = RD._finding_key_of(row_a), RD._finding_key_of(row_b)
    assert key_a != key_b
    state = _state(session_dir)
    _scrub_ids(state)
    if a_lives_in == "findings":
        for finding in state["findings"]:
            if RD._finding_key_of(finding) == key_a:
                finding["id"] = "v0"
    elif a_lives_in == "second-test-carry":
        state["_secondTestCarry"] = [dict(row_a, id="v0")]
    else:
        raise AssertionError(a_lives_in)
    state["_toVerify"] = [{k: v for k, v in row_b.items() if k != "id"}]
    RD.save_state(session_dir, state)
    return session_dir, key_a, key_b


def _rule_ids(tmp_path, session_dir, rid, name="ruling.json"):
    return _rule(session_dir, _write_ruling_file(tmp_path / name, [_guidance(rid)]))


def _assert_ambiguous(out, keys):
    assert out.get("ok") is False, out
    assert out.get("reason") == "ruling-target-ambiguous", out
    assert {c["findingKey"] for c in out["candidates"]} == set(keys), out
    assert "findingKey" in out["hint"], out


def _assert_binds_each_key(tmp_path, session_dir, keys):
    """Rule by each key in turn: each binds, and the new log row names that finding."""
    for index, key in enumerate(sorted(keys)):
        before = len(_state(session_dir).get("rulingsLog") or [])
        out = _rule_ids(tmp_path, session_dir, key, name="by-key-%d.json" % index)
        assert out.get("ok") is True, out
        log = _state(session_dir)["rulingsLog"]
        assert len(log) == before + 1
        assert log[-1]["findingKey"] == key


# ---- DoD-1 ----------------------------------------------------------------------------------------------------

def test_dod1_live_stores_an_id_staged_now_and_stamped_on_a_finding_is_ambiguous(tmp_path):
    session_dir, key_a, key_b = _reused_id_session(tmp_path, "findings")
    before = _state_bytes(session_dir)
    out = _rule_ids(tmp_path, session_dir, "v0")
    _assert_ambiguous(out, {key_a, key_b})
    assert _state_bytes(session_dir) == before


def test_dod1_second_test_carry_an_id_held_in_the_carry_and_staged_now_is_ambiguous(tmp_path):
    session_dir, key_a, key_b = _reused_id_session(tmp_path, "second-test-carry")
    before = _state_bytes(session_dir)
    out = _rule_ids(tmp_path, session_dir, "v0")
    _assert_ambiguous(out, {key_a, key_b})
    assert _state_bytes(session_dir) == before


def _attempt_history_session(tmp_path):
    r = Round(tmp_path, plain=[_PLAIN],
              first={_HELD["title"]: _MISSED, _PLAIN["title"]: _PLAUSIBLE},
              second={_HELD["title"]: _MISSED})
    r.drive(stop=RD.P_SYNTHESIS)
    return r


def _reused_ids(state):
    """Ids the attempt history binds to two or more findings while the live stores bind at most one."""
    live, history = {}, {}
    for key, row in RD._ruling_candidate_rows(state):
        if isinstance(row.get("id"), str):
            live.setdefault(row["id"], set()).add(key)
    for entry in state[RD.STAGED_ID_BINDINGS_FIELD]:
        for sid, key in entry["bindings"].items():
            history.setdefault(sid, set()).add(key)
    return live, history, sorted(sid for sid, keys in history.items()
                                 if len(keys) >= 2 and len(live.get(sid, set())) <= 1)


def test_dod1_attempt_history_an_id_the_second_pass_renumbered_is_ambiguous(tmp_path):
    r = _attempt_history_session(tmp_path)
    state = r.state()
    sources = [entry["source"] for entry in state[RD.STAGED_ID_BINDINGS_FIELD]]
    assert "verifiers" in sources and "second-pass-restage" in sources, sources
    _, history, reused = _reused_ids(state)
    assert reused, "no id the history binds to two findings and the live stores to one: %r" % history
    rid = reused[0]
    keys = {C1L7._key(_HELD), C1L7._key(_PLAIN)}
    assert history[rid] == keys
    before = _state_bytes(r.dir)
    out = _rule_ids(tmp_path, r.dir, rid)
    _assert_ambiguous(out, keys)
    assert _state_bytes(r.dir) == before


# ---- DoD-2 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("a_lives_in", ["findings", "second-test-carry"])
def test_dod2_a_ruling_naming_the_finding_by_its_key_binds(tmp_path, a_lives_in):
    session_dir, key_a, key_b = _reused_id_session(tmp_path, a_lives_in)
    _assert_binds_each_key(tmp_path, session_dir, {key_a, key_b})


def test_dod2_attempt_history_each_candidate_key_binds(tmp_path):
    r = _attempt_history_session(tmp_path)
    _assert_binds_each_key(tmp_path, r.dir, {C1L7._key(_HELD), C1L7._key(_PLAIN)})


_ROW_A = {"id": "v0", "file": "a.py", "line": 1, "title": "old", "severity": "Important"}
_ROW_B = {"file": "b.py", "line": 2, "title": "new", "severity": "Important"}


def test_dod2_a_key_that_lives_only_in_the_staged_view_binds():
    key_b = RD._finding_key_of(_ROW_B)
    state = {"findings": [], "_toVerify": [dict(_ROW_B)]}
    key, row, fault = RD._resolve_ruling_target(state, key_b)
    assert (key, fault) == (key_b, None)
    assert row["title"] == "new"


def test_dod2_a_key_that_lives_only_in_the_second_test_carry_binds():
    key_b = RD._finding_key_of(_ROW_B)
    state = {"findings": [], "_secondTestCarry": [dict(_ROW_B)]}
    assert RD._resolve_ruling_target(state, key_b)[::2] == (key_b, None)


def test_dod2_a_key_that_is_also_another_rows_id_binds_the_key_holder():
    key_a = RD._finding_key_of(_ROW_A)
    state = {"findings": [dict(_ROW_A), dict(_ROW_B, id=key_a)]}
    assert RD._resolve_ruling_target(state, key_a)[::2] == (key_a, None)


# ---- DoD-3 ----------------------------------------------------------------------------------------------------

def test_dod3_an_id_every_store_binds_to_one_finding_binds(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    key_a = RD._finding_key_of(row_a)
    state = _state(session_dir)
    _scrub_ids(state)
    for finding in state["findings"]:
        if RD._finding_key_of(finding) == key_a:
            finding["id"] = "v0"
    state["_toVerify"] = [{k: v for k, v in row_a.items() if k != "id"}]
    RD.save_state(session_dir, state)
    out = _rule_ids(tmp_path, session_dir, "v0")
    assert out.get("ok") is True, out
    assert _state(session_dir)["rulingsLog"][-1]["findingKey"] == key_a


def test_dod3_the_session_that_bound_the_id_on_the_base_still_binds(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    out = _rule_ids(tmp_path, session_dir, row_a["id"])
    assert out.get("ok") is True, out
    assert _state(session_dir)["rulingsLog"][-1]["findingKey"] == RD._finding_key_of(row_a)


# ---- R4 -------------------------------------------------------------------------------------------------------

def test_r4_a_non_dict_staged_original_is_a_placeholder_not_a_candidate():
    state = {"findings": [dict(_ROW_A)], "_toVerify": [None, dict(_ROW_B)]}
    key_a = RD._finding_key_of(_ROW_A)
    assert RD._resolve_ruling_target(state, "v0")[::2] == (key_a, None)
    assert [c["findingKey"] for c in RD._ruling_target_candidates(state, "v0")] == [key_a]


# ---- the rulings log and the malformed shapes -----------------------------------------------------------------

def test_a_ruling_logged_under_the_id_for_another_finding_makes_the_id_ambiguous():
    key_a, key_b = RD._finding_key_of(_ROW_A), RD._finding_key_of(_ROW_B)
    state = {"findings": [dict(_ROW_A)],
             "rulingsLog": [{"id": "v0", "findingKey": key_b}]}
    assert RD._resolve_ruling_target(state, "v0") == (None, None, RD.RULING_TARGET_AMBIGUOUS)
    cands = RD._ruling_target_candidates(state, "v0")
    assert [c["findingKey"] for c in cands] == sorted([key_a, key_b])
    by_key = {c["findingKey"]: c for c in cands}
    assert by_key[key_a]["title"] == "old" and by_key[key_b]["title"] is None


def test_a_malformed_rulings_log_is_skipped_by_the_scan():
    state = {"findings": [dict(_ROW_A)], "rulingsLog": "not-a-list"}
    assert RD._resolve_ruling_target(state, "v0")[::2] == (RD._finding_key_of(_ROW_A), None)


def test_the_candidate_rows_skip_every_malformed_store():
    state = {"findings": "x", "_fixBatch": 3, "_verified": {"a": 1}, "_refuted": [None, 5, {}],
             "_secondTestCarry": None, "_secondTestRefutedCarry": "x",
             "_secondTestHeld": [None, {"finding": 4}, {"note": "n"}, {"finding": dict(_ROW_B)}],
             "_toVerify": "not-a-list"}
    rows = RD._ruling_candidate_rows(state)
    assert [row.get("title") for _, row in rows if row.get("title")] == ["new"]
    state["_toVerify"] = 7
    assert RD._resolve_ruling_target(state, "nothing") == (None, None, None)


def test_a_ledger_read_fault_still_binds_a_finding_key_the_findings_name():
    key_a = RD._finding_key_of(_ROW_A)
    state = {"findings": [dict(_ROW_A)], "dispositionLedger": {"not": "a-list"},
             RD.session_contract.DISPOSITION_LEDGER_OWNER_FIELD:
                 RD.session_contract.DISPOSITION_LEDGER_OWNER_VALUE}
    assert RD._resolve_ruling_target(state, key_a)[::2] == (key_a, None)
    assert RD._resolve_ruling_target(state, "other") == (None, None, RD.RULING_FILE_UNREADABLE)


# ---- H the history recorder ---------------------------------------------------------------------------------

def test_h_the_recorder_binds_each_staged_id_to_its_original_findings_key():
    originals = [dict(_ROW_A), dict(_ROW_B)]
    state = {"round": 3}
    RD._record_staged_id_bindings(state, originals, RD.verification.stage_ids(originals), "verifiers")
    assert state[RD.STAGED_ID_BINDINGS_FIELD] == [{
        "round": 3, "source": "verifiers",
        "bindings": {"v0": RD._finding_key_of(_ROW_A), "v1": RD._finding_key_of(_ROW_B)}}]


def test_h_the_recorder_leaves_out_a_non_dict_original_and_a_keyless_one(monkeypatch):
    real = RD._finding_identity_key
    monkeypatch.setattr(RD, "_finding_identity_key",
                        lambda f: "" if isinstance(f, dict) and f.get("nokey") else real(f))
    originals = [None, {"nokey": True, "title": "x"}, dict(_ROW_B)]
    state = {"round": 1}
    RD._record_staged_id_bindings(state, originals, RD.verification.stage_ids(originals), "verifiers")
    assert state[RD.STAGED_ID_BINDINGS_FIELD][0]["bindings"] == {"v2": RD._finding_key_of(_ROW_B)}


def test_h_an_all_skipped_call_appends_nothing(monkeypatch):
    originals = [None, 5]
    state = {"round": 1}
    RD._record_staged_id_bindings(state, originals, RD.verification.stage_ids(originals), "verifiers")
    assert RD.STAGED_ID_BINDINGS_FIELD not in state
    state[RD.STAGED_ID_BINDINGS_FIELD] = []
    RD._record_staged_id_bindings(state, [], [], "verifiers")
    assert state[RD.STAGED_ID_BINDINGS_FIELD] == []


def test_h_a_present_non_list_history_is_replaced_by_a_list_holding_the_entry():
    originals = [dict(_ROW_B)]
    state = {"round": 2, RD.STAGED_ID_BINDINGS_FIELD: "garbage"}
    RD._record_staged_id_bindings(state, originals, RD.verification.stage_ids(originals), "second-pass-restage")
    (entry,) = state[RD.STAGED_ID_BINDINGS_FIELD]
    assert entry["source"] == "second-pass-restage" and entry["bindings"] == {
        "v0": RD._finding_key_of(_ROW_B)}


def test_h_a_malformed_history_entry_is_skipped_by_the_resolver():
    state = {"findings": [dict(_ROW_A)],
             RD.STAGED_ID_BINDINGS_FIELD: [None, "x", {"bindings": []}, {"bindings": {"v0": 5}},
                                           {"bindings": {"v0": ""}}, {"round": 1}]}
    assert RD._resolve_ruling_target(state, "v0")[::2] == (RD._finding_key_of(_ROW_A), None)
    state[RD.STAGED_ID_BINDINGS_FIELD] = "not-a-list"
    assert RD._resolve_ruling_target(state, "v0")[::2] == (RD._finding_key_of(_ROW_A), None)


def test_h_a_well_formed_history_entry_for_another_finding_makes_the_id_ambiguous():
    key_b = RD._finding_key_of(_ROW_B)
    state = {"findings": [dict(_ROW_A)],
             RD.STAGED_ID_BINDINGS_FIELD: [{"round": 1, "source": "verifiers", "bindings": {"v0": key_b}}]}
    assert RD._resolve_ruling_target(state, "v0") == (None, None, RD.RULING_TARGET_AMBIGUOUS)
