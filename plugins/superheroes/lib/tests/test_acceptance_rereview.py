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
    # `different` and no-verdict both stay blocking AT THEIR SEVERITY (presence alone is not
    # enough — a silent demotion would be a functional accept); only the clear `same` drops
    assert {f["title"]: f["severity"] for f in out["findings"]} == {
        "records dropped on concurrent edit": "Important",
        "retry constant unbounded": "Important"}
    assert out["downgrades"] == []
    accepted = [d for d in out["drops"] if d.get("accepted")]
    assert len(accepted) == 1 and accepted[0]["id"] == "plan.md::unauth write path"
    assert accepted[0]["was_blocking_tagged"] is True


def test_cli_empty_candidates_suppresses_nothing(tmp_path, capsys):
    """#433: empty candidates — the fail-closed direction after the skill's absent-ledger
    `[]` fallback (the absent-FILE case is the shell's `|| echo '[]'`, not reachable here)."""
    ar = _load("acceptance_rereview")
    m, l, c = tmp_path / "merged.json", tmp_path / "leaf.json", tmp_path / "cands.json"
    m.write_text(json.dumps([{"file": "plan.md", "line": 1, "title": "x", "severity": "Important"}]))
    l.write_text("[]"); c.write_text("[]")
    rc = ar.main(["acceptance_rereview", "--merged", str(m), "--leaf", str(l), "--candidates", str(c)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_cli_same_verdict_on_changed_content_never_suppresses(tmp_path, capsys):
    """FR-14 second rule through the CLI: a `same`+reason verdict targeting a candidate whose
    section hash CHANGED must not suppress — the finding is judged afresh. Kills the mutant
    that drops on any same+reason verdict regardless of hashMatches."""
    ar = _load("acceptance_rereview")
    m, l, c = tmp_path / "merged.json", tmp_path / "leaf.json", tmp_path / "cands.json"
    m.write_text(json.dumps([
        {"file": "plan.md", "line": 1, "title": "unauth write path", "severity": "Critical"}]))
    c.write_text(json.dumps([
        {"identity": "plan.md::unauth write path", "docSection": "Architecture",
         "hashMatches": False}]))
    l.write_text(json.dumps([
        {"id": "plan.md::unauth write path", "action": "same",
         "reason": "looks like the accepted one"}]))
    rc = ar.main(["acceptance_rereview", "--merged", str(m), "--leaf", str(l), "--candidates", str(c)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["title"] == "unauth write path"
    assert out["findings"][0]["severity"] == "Critical"
    assert out["drops"] == []


def test_cli_acceptance_only_neutralizes_drifted_and_smuggled_verdicts(tmp_path, capsys):
    """Scoped-review fix: on the interactive path there is NO legitimate normal-synthesis leaf,
    so --acceptance-only filters the verdict file to clear sameness verdicts and strips
    severity. A drifted `drop` action (offered or not) and a smuggled severity must have no
    effect — the findings survive at their own severity."""
    ar = _load("acceptance_rereview")
    m, l, c = tmp_path / "merged.json", tmp_path / "leaf.json", tmp_path / "cands.json"
    m.write_text(json.dumps([
        {"file": "plan.md", "line": 1, "title": "unauth write path", "severity": "Critical"},
        {"file": "plan.md", "line": 5, "title": "records dropped", "severity": "Important"},
    ]))
    c.write_text(json.dumps([
        {"identity": "plan.md::unauth write path", "docSection": "A", "hashMatches": True},
        {"identity": "plan.md::records dropped", "docSection": "B", "hashMatches": False},
    ]))
    l.write_text(json.dumps([
        # drifted action on an offered id — must not suppress
        {"id": "plan.md::unauth write path", "action": "drop", "reason": "drifted schema"},
        # drop + smuggled severity on an UNOFFERED id — must neither drop nor re-tier
        {"id": "plan.md::records dropped", "action": "drop", "reason": "x", "severity": "Nit"},
    ]))
    rc = ar.main(["acceptance_rereview", "--acceptance-only",
                  "--merged", str(m), "--leaf", str(l), "--candidates", str(c)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert {f["title"]: f["severity"] for f in out["findings"]} == {
        "unauth write path": "Critical", "records dropped": "Important"}
    assert out["drops"] == [] and out["downgrades"] == []


def test_conflicting_duplicate_sameness_verdicts_resolve_to_keep():
    """Scoped-review fix: duplicate verdicts for one id that disagree resolve to `different`
    (kept, judged afresh) — a contradicted `same` never suppresses via last-wins."""
    ar = _load("acceptance_rereview")
    cands = [{"identity": "plan.md::unauth write path", "docSection": "Architecture", "hashMatches": True}]
    verdicts = [
        {"id": "plan.md::unauth write path", "action": "different", "reason": "not the same"},
        {"id": "plan.md::unauth write path", "action": "same", "reason": "contradicts the above"},
    ]
    out = ar.consume_with_acceptance([BLOCKER], verdicts, cands)
    assert len(out["findings"]) == 1 and out["findings"][0]["title"] == "unauth write path"
    assert out["drops"] == []
