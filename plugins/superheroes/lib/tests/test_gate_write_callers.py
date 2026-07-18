from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_review_skills_pass_reviewed_snapshot_identity_to_gate_write():
    # review-spec is the surviving gate_write caller (mode reset). The plan/tasks certifying
    # legs (review-plan/review-tasks) + their acceptance-ledger flow retired in S1 train 2 (#469).
    for rel in [
        "skills/review-spec/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "REVIEWED_HASH" in text
        assert "RUN_ID" in text
        assert "--expected-hash" in text
        assert "--run-id" in text
