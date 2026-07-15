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


def test_cli_interactive_flow_keep_on_uncertain(tmp_path, capsys):
    """#433: the interactive skills' documented consume flow — stage merged/leaf/candidates
    files exactly as plan-detail.md/tasks-detail.md instruct and invoke the CLI. Three
    hash-matched candidates: a clear `same`+reason suppresses (accepted drop), a `different`
    stays blocking, and a finding with NO verdict (the uncertain case) stays blocking —
    keep-on-uncertain never silently accepts on the interactive path either."""
    ar = _load("acceptance_rereview")
    merged = [
        {"file": "plan.md", "line": 1, "title": "unauth write path", "severity": "Critical"},
        {"file": "plan.md", "line": 9, "title": "records dropped on concurrent edit", "severity": "Important"},
        {"file": "plan.md", "line": 20, "title": "retry constant unbounded", "severity": "Important"},
    ]
    cands = [
        {"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": True},
        {"identity": "plan.md::records dropped on concurrent edit", "docSection": "Data flow", "hashMatches": True},
        {"identity": "plan.md::retry constant unbounded", "docSection": "Rollout", "hashMatches": True},
    ]
    verdicts = [
        {"id": "plan.md::unauth write path", "action": "same",
         "reason": "same accepted concern; section unchanged"},
        {"id": "plan.md::records dropped on concurrent edit", "action": "different",
         "reason": "new failure mode this round"},
        # third finding: NO verdict — the orchestrator was uncertain
    ]
    m, l, c = tmp_path / "merged.json", tmp_path / "leaf.json", tmp_path / "cands.json"
    m.write_text(json.dumps(merged)); l.write_text(json.dumps(verdicts)); c.write_text(json.dumps(cands))
    rc = ar.main(["acceptance_rereview", "--merged", str(m), "--leaf", str(l), "--candidates", str(c)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    titles = {f["title"] for f in out["findings"]}
    # `different` and no-verdict both stay blocking; only the clear `same` is suppressed
    assert titles == {"records dropped on concurrent edit", "retry constant unbounded"}
    accepted = [d for d in out["drops"] if d.get("accepted")]
    assert len(accepted) == 1 and accepted[0]["id"] == "plan.md::unauth write path"
    assert accepted[0]["was_blocking_tagged"] is True


def test_cli_empty_candidates_suppresses_nothing(tmp_path, capsys):
    """#433: absent/empty ledger — the skills' fail-closed skip path. Every finding survives."""
    ar = _load("acceptance_rereview")
    m, l, c = tmp_path / "merged.json", tmp_path / "leaf.json", tmp_path / "cands.json"
    m.write_text(json.dumps([{"file": "plan.md", "line": 1, "title": "x", "severity": "Important"}]))
    l.write_text("[]"); c.write_text("[]")
    rc = ar.main(["acceptance_rereview", "--merged", str(m), "--leaf", str(l), "--candidates", str(c)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["findings"]) == 1 and out["drops"] == []
