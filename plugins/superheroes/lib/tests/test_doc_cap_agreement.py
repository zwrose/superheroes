import os, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _read(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def test_interactive_doc_legs_cap_at_three():
    for skill in ("plugins/superheroes/skills/review-plan/SKILL.md",
                  "plugins/superheroes/skills/review-tasks/SKILL.md"):
        text = _read(skill)
        assert "--max-rounds 3" in text, f"{skill} must cap the doc loop at 3"
        assert "--max-rounds 7" not in text, f"{skill} must not keep the old 7-round cap"
