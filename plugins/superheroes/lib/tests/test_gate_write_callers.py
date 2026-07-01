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
