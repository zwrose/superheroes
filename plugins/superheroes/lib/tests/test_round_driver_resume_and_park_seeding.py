#!/usr/bin/env python3
"""#1195-B — the producer park merges fresh candidates into the findings it carries."""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "fixerVendor": "claude"}
    base.update(over)
    return base


def _seed_record(round_no, **over):
    rec = {"schemaVersion": 2, "round": round_no, "kind": "baseline",
           "dimensions": {"test-role": {"status": "run", "confidence": "high",
                                            "tier": "reviewer-deep", "findings": []}},
           "findings": [], "coverageDecisions": []}
    rec.update(over)
    return rec


def _unwritable_records_path(tmp_path):
    """A records destination the driver cannot write: its parent "directory" is a regular file."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    return str(blocker / "round-records.json")


def _parking_state(tmp_path):
    """A state holding one ledger record whose records destination cannot be written."""
    cfg = _cfg(dimensions=["test-role"], recordsPath=_unwritable_records_path(tmp_path))
    state = RD.new_state(_cfg(dimensions=["test-role"]))
    state["config"] = cfg
    state["_records"] = [_seed_record(1)]
    return state, cfg


# --- F3: delta-fold park carries fresh candidates ---


def test_f3_delta_fold_park_carries_fresh_candidates(tmp_path):
    """F3 — producer park merges _toVerify into findings; same id different location is kept."""
    state, cfg = _parking_state(tmp_path)
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
    state, cfg = _parking_state(tmp_path)

    prior = {"id": "v0", "file": "same.py", "line": 10, "title": "dup-title", "severity": "Important"}
    dup_fresh = {"id": "v9", "file": "same.py", "line": 10, "title": "dup-title", "severity": "Important"}
    diff_line = {"id": "v1", "file": "same.py", "line": 20, "title": "dup-title", "severity": "Important"}
    not_dict = "not-a-dict"
    no_identity = {"severity": "Important"}
    state["findings"] = [prior]
    state["_toVerify"] = [dup_fresh, diff_line, not_dict, no_identity]
    RD._persist_round_records(state, cfg)
    titles_and_raw = [(f if isinstance(f, dict) else f) for f in (state.get("findings") or [])]
    assert titles_and_raw[0] == prior
    assert len([f for f in titles_and_raw if isinstance(f, dict) and f.get("line") == 10]) == 1
    assert any(isinstance(f, dict) and f.get("line") == 20 for f in titles_and_raw)
    assert "not-a-dict" in titles_and_raw
    assert no_identity in titles_and_raw

    state2, cfg2 = _parking_state(tmp_path)
    only_fresh = [{"id": "v0", "file": "z.py", "line": 1, "title": "only", "severity": "Important"}]
    state2["findings"] = []
    state2["_toVerify"] = list(only_fresh)
    RD._persist_round_records(state2, cfg2)
    assert state2.get("findings") == only_fresh


# --- F5: prior-vs-fresh severity on location collision ---


def test_f5_prior_vs_fresh_collision_keeps_higher_severity(tmp_path):
    """F5 — prior Important at a location is replaced by fresh Critical on park merge."""
    state, cfg = _parking_state(tmp_path)
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
