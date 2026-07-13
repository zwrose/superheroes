from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_review_skills_pass_reviewed_snapshot_identity_to_gate_write():
    for rel in [
        "skills/review-spec/SKILL.md",
        "skills/review-plan/SKILL.md",
        "skills/review-tasks/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "REVIEWED_HASH" in text
        assert "RUN_ID" in text
        assert "--expected-hash" in text
        assert "--run-id" in text


def test_showrunner_direct_gate_path_passes_fence_args():
    text = (ROOT / "lib" / "showrunner.js").read_text(encoding="utf-8")
    review_doc = text[text.index("async function reviewDocPhase"):text.index("module.exports.producePhase")]
    assert "--expected-hash" in review_doc
    assert "--run-id" in review_doc
    assert "--lease" in review_doc


def test_review_plan_records_acceptance_ledger_before_gate_write():
    """#397 FR-14: the certifying review-plan skill must record accepted findings before
    gate_write.py — not only write gates.review directly."""
    skill = (ROOT / "skills/review-plan/SKILL.md").read_text(encoding="utf-8")
    detail = (ROOT / "skills/review-plan/reference/plan-detail.md").read_text(encoding="utf-8")
    section = skill[skill.index("### 6. Record the review gate"):skill.index("## Plan-Content Requirements")]
    assert "plan-accept.json" in section or "acceptance ledger" in section.lower()
    assert "before" in section and "gate_write.py" in section
    assert section.index("acceptance") < section.index("gate_write.py")
    assert "review_acceptance.py" in detail and " record " in detail
    assert "plan-accept.json" in detail
    assert "collect-blocking" in detail
    assert "open-blockers.json" in detail
    assert "skip-set.json" not in detail
    assert "finding_identity" not in detail


def test_review_tasks_records_acceptance_ledger_before_gate_write():
    """#397 FR-14: the certifying review-tasks skill must record accepted findings before
    gate_write.py — not only write gates.review directly."""
    skill = (ROOT / "skills/review-tasks/SKILL.md").read_text(encoding="utf-8")
    detail = (ROOT / "skills/review-tasks/reference/tasks-detail.md").read_text(encoding="utf-8")
    section = skill[skill.index("### 6. Record the review gate"):skill.index("## Tasks-Content Requirements")]
    assert "tasks-accept.json" in section or "acceptance ledger" in section.lower()
    assert "before" in section and "gate_write.py" in section
    assert section.index("acceptance") < section.index("gate_write.py")
    assert "review_acceptance.py" in detail and " record " in detail
    assert "tasks-accept.json" in detail
    assert "collect-blocking" in detail
    assert "open-blockers.json" in detail
    assert "skip-set.json" not in detail
    assert "finding_identity" not in detail
