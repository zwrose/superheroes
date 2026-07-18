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


def test_review_plan_consumes_acceptance_before_verdict():
    """#433 (FR-14 interactive consume): the review-plan skill's compile step must run the
    acceptance-consume block BEFORE determining the verdict, and the detail file must carry
    the candidates load, the tested consumer, and the keep-on-uncertain direction."""
    skill = (ROOT / "skills/review-plan/SKILL.md").read_text(encoding="utf-8")
    detail = (ROOT / "skills/review-plan/reference/plan-detail.md").read_text(encoding="utf-8")
    section = skill[skill.index("### 4. Compile Findings"):skill.index("### 5. Revise Loop")]
    assert "Acceptance suppression" in section and "plan-detail.md" in section
    # the suppression step precedes the verdict determination
    assert section.index("Acceptance suppression") < section.index("Determine the verdict")
    assert "never re-asked" in section
    # the detail file wires the tested consumer, not duplicated logic
    assert "review_acceptance.py" in detail and " candidates " in detail
    assert "acceptance_rereview.py" in detail
    assert "hashMatches" in detail
    assert "Keep-on-uncertain" in detail or "keep-on-uncertain" in detail
    assert "effective finding set" in detail
    # scoped-review hardening: interactive mode flag, per-round stale-file cleanup, and the
    # stable ledger key (session paths never match across runs) are all documented
    assert "--acceptance-only" in detail
    assert 'rm -f "$SESSION_DIR/merged.json"' in detail
    assert "stable ledger key" in detail
    # consume is documented to run BEFORE the verdict; recording stays before gate_write.
    # Anchor on the section HEADINGS (a Contents entry would match first and prove nothing).
    assert detail.index("\n## Acceptance suppression") < detail.index("\n## Acceptance ledger (gate-approval)")


def test_review_tasks_consumes_acceptance_before_verdict():
    """#433 (FR-14 interactive consume), tasks leg — FR-13 symmetry with review-plan."""
    skill = (ROOT / "skills/review-tasks/SKILL.md").read_text(encoding="utf-8")
    detail = (ROOT / "skills/review-tasks/reference/tasks-detail.md").read_text(encoding="utf-8")
    section = skill[skill.index("### 4. Compile Findings"):skill.index("### 5. Revise Loop")]
    assert "Acceptance suppression" in section and "tasks-detail.md" in section
    assert section.index("Acceptance suppression") < section.index("Determine the verdict")
    assert "never re-asked" in section
    assert "review_acceptance.py" in detail and " candidates " in detail
    assert "acceptance_rereview.py" in detail
    assert "hashMatches" in detail
    assert "Keep-on-uncertain" in detail or "keep-on-uncertain" in detail
    assert "effective finding set" in detail
    # scoped-review hardening: interactive mode flag, per-round stale-file cleanup, and the
    # stable ledger key (session paths never match across runs) are all documented
    assert "--acceptance-only" in detail
    assert 'rm -f "$SESSION_DIR/merged.json"' in detail
    assert "stable ledger key" in detail
    # heading anchors, so a future Contents block cannot hollow this out
    assert detail.index("\n## Acceptance suppression") < detail.index("\n## Acceptance ledger (gate-approval)")
