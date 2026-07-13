import importlib.util
import json
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DOC = """# Plan

## Architecture

The write path authenticates every request.

## Data flow

Records are append-only.
"""

BLOCKER = {
    "file": "plan.md",
    "line": 1,
    "title": "unauth write path",
    "severity": "Critical",
    "docSection": "Architecture",
}


def test_matching_hash_candidate_offered_to_judge(tmp_path):
    ar = _load("acceptance_rereview")
    cands = [{"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": True}]
    offered = ar.prefilter_for_judge([BLOCKER], cands)
    assert offered == ["plan.md::unauth write path"]


def test_changed_section_hash_not_offered():
    ar = _load("acceptance_rereview")
    cands = [{"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": False}]
    offered = ar.prefilter_for_judge([BLOCKER], cands)
    assert offered == []


def test_stubbed_judge_different_leaves_finding_blocking():
    ar = _load("acceptance_rereview")
    cands = [{"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": True}]
    verdicts = [{"id": "plan.md::unauth write path", "action": "different", "reason": "new concern"}]
    out = ar.consume_with_acceptance([BLOCKER], verdicts, cands)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["title"] == "unauth write path"
    assert out["drops"] == []


def test_stubbed_judge_same_drops_to_accepted():
    ar = _load("acceptance_rereview")
    cands = [{"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": True}]
    verdicts = [{"id": "plan.md::unauth write path", "action": "same",
                 "reason": "same concern the owner accepted"}]
    out = ar.consume_with_acceptance([BLOCKER], verdicts, cands)
    assert out["findings"] == []
    assert len(out["drops"]) == 1
    assert out["drops"][0]["accepted"] is True
    assert out["drops"][0]["was_blocking_tagged"] is True


def test_uncertain_same_without_reason_stays_blocking():
    ar = _load("acceptance_rereview")
    cands = [{"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": True}]
    verdicts = [{"id": "plan.md::unauth write path", "action": "same", "reason": ""}]
    out = ar.consume_with_acceptance([BLOCKER], verdicts, cands)
    assert len(out["findings"]) == 1
    assert out["drops"] == []
