"""#1272 layer 2e — staged ids never resolve silently."""
import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_SPEC = importlib.util.spec_from_file_location(
    "round_driver", os.path.join(_LIB, "round_driver.py"))
RD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RD)

_V_SPEC = importlib.util.spec_from_file_location(
    "verification", os.path.join(_LIB, "verification.py"))
V = importlib.util.module_from_spec(_V_SPEC)
_V_SPEC.loader.exec_module(V)

_SC_SPEC = importlib.util.spec_from_file_location(
    "session_contract", os.path.join(_LIB, "session_contract.py"))
SC = importlib.util.module_from_spec(_SC_SPEC)
_SC_SPEC.loader.exec_module(SC)

from test_round_driver import (  # noqa: E402
    _A_FINDING,
    _at,
    _cfg,
    _drive_to_phase,
    _responder,
    _state_bytes,
)

_AJ_BODY = "intentional pattern for performance " + ("x" * 40)


def _verified_id(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok
    verified = state.get("_verified") or []
    assert verified and isinstance(verified[0], dict)
    return verified[0]["id"]


def test_e1_verifier_drop_missing_staged_id_refused_at_fold(monkeypatch):
    # axis: e1 — verdict drop id absent (None/missing key)
    finding = {"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}
    compiled, _ = RD.mechanical_compile([finding], None)
    state = RD.new_state(_cfg())
    RD._stage_findings(state, compiled)
    real_apply = RD.verification.apply_verdicts

    def fake_apply(staged, verdicts):
        out = real_apply(staged, verdicts)
        patched = dict(out)
        patched["drops"] = list(out["drops"]) + [{"id": None, "reason": "synthetic drop"}]
        return patched

    monkeypatch.setattr(RD.verification, "apply_verdicts", fake_apply)
    RD._fold_verifiers(state, state["config"], {"verdicts": []})
    assert state["step"] == RD.P_TERMINAL
    assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in state["certification"]["reason"]
    assert "missing staged id" in state["certification"]["reason"]


def test_e2_verifier_drop_unknown_id_refused_at_submit(tmp_path):
    # axis: e2 — drop id matches no staged finding
    d, n = _at(tmp_path, RD.P_VERIFIERS)
    before = _state_bytes(d)
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"verdicts": [{"id": "v99", "verdict": "REFUTED", "reason": "not in staged set"}]})
    assert out["ok"] is False
    assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in out["reason"]
    assert "maps to no entry" in out["reason"]
    assert _state_bytes(d) == before
    journal = RD.read_journal(d)
    assert journal[-1].get("outcome") == "staged-id-unresolvable"


def test_e3_duplicate_staged_id_refused(monkeypatch):
    # axis: e3 — two staged findings share one id
    dup = {"id": "dup", "file": "a.py", "line": 1, "title": "one", "severity": "Important"}
    staged = [dict(dup), dict(dup)]
    by_id, fault = RD._staged_by_id_map(staged)
    assert by_id is None
    assert fault == "%s: duplicate staged id %r" % (RD.STAGED_ID_UNRESOLVABLE_CAUSE, "dup")


def test_e4_staged_finding_no_derivable_key_refused(monkeypatch, tmp_path):
    # axis: e4 — staged finding with no derivable key
    orig_key = RD._finding_identity_key

    def key_fn(finding):
        if isinstance(finding, dict) and finding.get("file") == "bad.py":
            return None
        return orig_key(finding)

    monkeypatch.setattr(RD, "_finding_identity_key", key_fn)

    def staged_with_bad(findings):
        return [{"id": "v0", "file": "bad.py", "line": 1, "title": "x", "severity": "Important"}]

    monkeypatch.setattr(RD.verification, "stage_ids", staged_with_bad)
    d, n = _at(tmp_path, RD.P_VERIFIERS)
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"verdicts": [{"id": "v0", "verdict": "REFUTED", "reason": "bad key"}]})
    assert out["ok"] is False
    assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in out["reason"]
    assert "no derivable finding key" in out["reason"]


def test_e5_synthesis_merge_kept_id_unresolvable_refused_at_submit(tmp_path, monkeypatch):
    # axis: e5 — merge kept_id unresolvable → whole merge refused, never dropped
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    real_merge = RD.verification.merge_and_rank

    def merge_with_bad_kept(survivors, grouping=None):
        out = real_merge(survivors, grouping)
        patched = dict(out)
        patched["merges"] = list(out["merges"]) + [{
            "group_id": "ghost",
            "member_ids": ["v0"],
            "kept_id": "missing-kept",
        }]
        return patched

    monkeypatch.setattr(RD.verification, "merge_and_rank", merge_with_bad_kept)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                        {"grouping": None})
    assert out["ok"] is False
    assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in out["reason"]
    assert "missing-kept" in out["reason"]


def test_e6_synthesis_one_bad_member_refused_at_submit(tmp_path):
    # axis: e6 — one member_ids entry unresolvable while others resolve → refused
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    good_id = _verified_id(d)
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"grouping": [{"group_id": "g", "member_ids": [good_id, "v99"]}]})
    assert out["ok"] is False
    assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in out["reason"]
    assert "v99" in out["reason"]


def test_e7_kept_id_member_self_no_fault(tmp_path):
    # axis: e7 — member_id == kept_id stays a no-op (not a fault)
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    good_id = _verified_id(d)
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"grouping": [{"group_id": "g", "member_ids": [good_id, good_id]}]})
    assert out["ok"] is True


@pytest.mark.parametrize("artifact", [
    {"grouping": None},
    {"grouping": []},
], ids=["none", "empty-list"])
def test_e8_empty_grouping_no_fault(tmp_path, artifact):
    # axis: e8 — grouping null or empty list → no fault (unchanged)
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
    assert out["ok"] is True


def test_e8b_missing_grouping_key_refused_at_submit(tmp_path):
    # axis: e8b — artifact without grouping key refused at payload contract
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    before = _state_bytes(d)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], {})
    assert out["ok"] is False
    assert "grouping" in out["reason"]
    assert _state_bytes(d) == before


def test_e9_synthesis_non_object_artifact_refused_at_submit(tmp_path):
    # axis: e9 — non-object synthesis artifact refused before staged-id lookup
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    before = _state_bytes(d)
    out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], [])
    assert out["ok"] is False
    assert "synthesis artifact is list" in out["reason"]
    assert _state_bytes(d) == before
    journal = RD.read_journal(d)
    assert journal[-1].get("outcome") == "synthesis-results-shape"


def test_e10_synthesis_non_string_member_refused_at_submit(tmp_path):
    # axis: e10 — non-string member_ids entry refused before staged-id lookup
    d, n = _at(tmp_path, RD.P_SYNTHESIS)
    before = _state_bytes(d)
    out = RD.cmd_submit(
        d, n["phase"], n["attempt"], n["expectedStateHash"],
        {"grouping": [{"member_ids": [{}]}]})
    assert out["ok"] is False
    assert "member_ids[0]" in out["reason"]
    assert _state_bytes(d) == before
    journal = RD.read_journal(d)
    assert journal[-1].get("outcome") == "synthesis-results-shape"


def test_author_justified_drop_unresolvable_id_parks_at_fold():
    """Fold-only guard when submit gate was bypassed (author-justified drops)."""
    finding = {
        "file": "aj.py", "line": 2, "title": "style", "severity": "Important",
        "verdict": "PLAUSIBLE", "id": None,
    }
    state = RD.new_state(_cfg())
    state["_verified"] = [finding]
    state["config"]["priorComments"] = [
        {"file": "aj.py", "line": 2, "body": _AJ_BODY}]
    RD._fold_synthesis(state, state["config"], {"grouping": None})
    assert state["step"] == RD.P_TERMINAL
    assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in state["certification"]["reason"]
