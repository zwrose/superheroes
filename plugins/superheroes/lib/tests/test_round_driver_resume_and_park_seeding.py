#!/usr/bin/env python3
"""#1195-B — resume read path parks on structural corruption; producer park merges fresh candidates."""
import importlib.util
import json
import os
import stat

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "fixerVendor": "claude",
            "persistRecords": True}
    base.update(over)
    return base


def _seams():
    def default_reviewer(dim, tier, rnd, ctx):
        return []

    return {"reviewer": default_reviewer}


def _seed_record(round_no, **over):
    rec = {"schemaVersion": 2, "round": round_no, "kind": "baseline",
           "dimensions": {"test-reviewer": {"status": "run", "confidence": "high",
                                            "tier": "reviewer-deep", "findings": []}},
           "findings": [], "coverageDecisions": []}
    rec.update(over)
    return rec


def _fresh_state():
    return {"leg": "code", "vendors": ["claude"], "rounds": {}, "_records": [],
            "_coverage": [], "_resumeCorrupt": None, "config": {}}


# --- F1: corrupt-records resume parks instead of raising ---


def test_f1_corrupt_records_resume_parks_instead_of_raising(tmp_path):
    """F1 — valid JSON list with a non-object element parks via _resumeCorrupt, never seeds _records."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1), "oops"]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = _fresh_state()
    RD._seed_resume(state, cfg)
    assert state.get("_resumeCorrupt")
    assert isinstance(state["_resumeCorrupt"], str)
    assert state["_resumeCorrupt"]
    assert state.get("_records") == []
    receipt = RD.run_loop(_seams(), cfg)
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None


def test_f1_nested_record_field_corruption_parks_instead_of_raising(tmp_path):
    """F1 extension — schema-v2 record with non-list coverageDecisions parks, never crashes."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([{"schemaVersion": 2, "round": 1, "coverageDecisions": 7}]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = _fresh_state()
    RD._seed_resume(state, cfg)
    assert state.get("_resumeCorrupt")
    assert isinstance(state["_resumeCorrupt"], str)
    assert state.get("_records") == []
    receipt = RD.run_loop(_seams(), cfg)
    assert receipt["verdict"] == "cannot-certify"
    assert receipt["certificationShape"] is None


# --- F2: structured refusals unchanged ---


def test_f2_structured_refusals_pin_exact_resume_corrupt_messages(tmp_path):
    """F2 — unreadable, invalid JSON, and non-list top-level still use not-ok branch with exact text."""
    dims = ["test-reviewer"]

    rm = _load("review_memory")

    unreadable = tmp_path / "unreadable.json"
    unreadable.write_text("[]")
    os.chmod(unreadable, 0o000)
    try:
        if os.geteuid() == 0:
            pytest.skip("unreadable-file probe skipped when running as root")
        loaded = rm.load_records_state(str(unreadable), dims)
        state = _fresh_state()
        RD._seed_resume(state, _cfg(dimensions=dims, recordsPath=str(unreadable)))
        assert state["_resumeCorrupt"] == (
            "resume state %s (%s) — cannot certify; a fresh full reviewer-deep round is owed"
            % (loaded.get("state") or "unreadable", loaded.get("reason") or "unreadable"))
    finally:
        os.chmod(unreadable, stat.S_IRUSR | stat.S_IWUSR)

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json")
    state = _fresh_state()
    RD._seed_resume(state, _cfg(dimensions=dims, recordsPath=str(bad_json)))
    loaded = rm.load_records_state(str(bad_json), dims)
    assert state["_resumeCorrupt"] == (
        "resume state corrupt (%s) — cannot certify; a fresh full reviewer-deep round is owed"
        % (loaded.get("reason") or "unreadable"))

    not_list = tmp_path / "not-list.json"
    not_list.write_text('{"round": 1}')
    state = _fresh_state()
    RD._seed_resume(state, _cfg(dimensions=dims, recordsPath=str(not_list)))
    loaded = rm.load_records_state(str(not_list), dims)
    assert state["_resumeCorrupt"] == (
        "resume state corrupt (not a list) — cannot certify; "
        "a fresh full reviewer-deep round is owed")

    missing = tmp_path / "missing.json"
    state = _fresh_state()
    RD._seed_resume(state, _cfg(dimensions=dims, recordsPath=str(missing)))
    assert state.get("_resumeCorrupt") is None


def test_f2_except_branch_corrupt_vocabulary(tmp_path, monkeypatch):
    """F2 — defence-in-depth except branch uses corrupt vocabulary, not unreadable."""

    def _raise_type_error(path, dims):
        raise TypeError("'int' object is not iterable")

    monkeypatch.setattr(RD.review_memory, "load_records_state", _raise_type_error)
    state = _fresh_state()
    RD._seed_resume(state, _cfg(dimensions=["test-reviewer"], recordsPath=str(tmp_path / "x.json")))
    assert state["_resumeCorrupt"] == (
        "resume state corrupt ('int' object is not iterable) — cannot certify; "
        "a fresh full reviewer-deep round is owed")


# --- F3: delta-fold park carries fresh candidates ---


def test_f3_delta_fold_park_carries_fresh_candidates(tmp_path):
    """F3 — producer park merges _toVerify into findings; same id different location is kept."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1), "oops"]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"]))
    state["config"] = cfg
    prior_a = {"id": "v0", "file": "a.py", "line": 1, "title": "prior-a", "severity": "Important"}
    prior_b = {"id": "v1", "file": "b.py", "line": 2, "title": "prior-b", "severity": "Important"}
    state["findings"] = [prior_a, prior_b]
    fresh_a = {"id": "v2", "file": "c.py", "line": 3, "title": "fresh-a", "severity": "Important"}
    fresh_trap = {"id": "v0", "file": "d.py", "line": 4, "title": "fresh-trap", "severity": "Important"}
    state["_toVerify"] = [fresh_a, fresh_trap]
    RD._persist_round_records(state, cfg)
    merged = state.get("findings") or []
    assert [f.get("title") for f in merged] == [
        "prior-a", "prior-b", "fresh-a", "fresh-trap"]
    assert len(merged) == 4
    assert state.get("terminal") == "cannot-certify"


# --- F4: dedupe and round-1 behaviour ---


def test_f4_park_findings_merge_dedupe_and_round1(tmp_path):
    """F4 — location dedupe, distinct lines kept, unidentifiable kept, round-1 copies _toVerify."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1), "oops"]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))

    prior = {"id": "v0", "file": "same.py", "line": 10, "title": "dup-title", "severity": "Important"}
    dup_fresh = {"id": "v9", "file": "same.py", "line": 10, "title": "dup-title", "severity": "Important"}
    diff_line = {"id": "v1", "file": "same.py", "line": 20, "title": "dup-title", "severity": "Important"}
    not_dict = "not-a-dict"
    no_identity = {"severity": "Important"}
    state = RD.new_state(_cfg(dimensions=["test-reviewer"]))
    state["config"] = cfg
    state["findings"] = [prior]
    state["_toVerify"] = [dup_fresh, diff_line, not_dict, no_identity]
    RD._persist_round_records(state, cfg)
    titles_and_raw = [(f if isinstance(f, dict) else f) for f in (state.get("findings") or [])]
    assert titles_and_raw[0] == prior
    assert len([f for f in titles_and_raw if isinstance(f, dict) and f.get("line") == 10]) == 1
    assert any(isinstance(f, dict) and f.get("line") == 20 for f in titles_and_raw)
    assert "not-a-dict" in titles_and_raw
    assert no_identity in titles_and_raw

    state2 = RD.new_state(_cfg(dimensions=["test-reviewer"]))
    state2["config"] = cfg
    only_fresh = [{"id": "v0", "file": "z.py", "line": 1, "title": "only", "severity": "Important"}]
    state2["findings"] = []
    state2["_toVerify"] = list(only_fresh)
    RD._persist_round_records(state2, cfg)
    assert state2.get("findings") == only_fresh


# --- F5: prior-vs-fresh severity on location collision ---


def test_f5_prior_vs_fresh_collision_keeps_higher_severity(tmp_path):
    """F5 — prior Important at a location is replaced by fresh Critical on park merge."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1), "oops"]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = RD.new_state(_cfg(dimensions=["test-reviewer"]))
    state["config"] = cfg
    prior = {"id": "v0", "file": "f.py", "line": 4, "title": "same",
             "severity": "Important", "dimension": "Code"}
    fresh = {"id": "v1", "file": "f.py", "line": 4, "title": "same",
             "severity": "Critical", "dimension": "Architecture"}
    state["findings"] = [prior]
    state["_toVerify"] = [fresh]
    RD._persist_round_records(state, cfg)
    merged = state.get("findings") or []
    assert len(merged) == 1
    assert merged[0]["severity"] == "Critical"
    assert merged[0]["dimension"] == "Code + Architecture"
    assert state.get("terminal") == "cannot-certify"


# --- #1195c-A: junk-round park on resume path ---


def test_junk_infinity_round_parks_resume_corrupt(tmp_path):
    """Junk round parks _seed_resume — no OverflowError, non-empty corrupt reason."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(float("inf"))]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = _fresh_state()
    RD._seed_resume(state, cfg)
    assert isinstance(state.get("_resumeCorrupt"), str)
    assert state["_resumeCorrupt"]
    assert "cannot certify" in state["_resumeCorrupt"]


def test_legacy_none_round_does_not_park_and_resumes(tmp_path):
    """None round is legacy/absent — must not park; resume round stays 2 after round 1."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([{"schemaVersion": 2, "round": None, "kind": "baseline",
                                    "dimensions": {"test-reviewer": {"status": "run",
                                                                       "confidence": "high",
                                                                       "tier": "reviewer-deep",
                                                                       "findings": []}},
                                    "findings": [], "coverageDecisions": []},
                                   _seed_record(1)]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = _fresh_state()
    RD._seed_resume(state, cfg)
    assert state.get("_resumeCorrupt") is None
    assert state.get("round") == 2


def test_well_formed_round_resume_unchanged(tmp_path):
    """Well-formed round 1 still resumes at round 2."""
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([_seed_record(1)]))
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    state = _fresh_state()
    RD._seed_resume(state, cfg)
    assert state.get("_resumeCorrupt") is None
    assert state.get("round") == 2
