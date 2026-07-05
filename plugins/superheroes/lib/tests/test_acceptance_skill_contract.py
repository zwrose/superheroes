# plugins/superheroes/lib/tests/test_acceptance_skill_contract.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_run as run

SKILL = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "acceptance", "SKILL.md")


def test_skill_file_exists_and_declares_frontmatter():
    assert os.path.isfile(SKILL)
    head = open(SKILL, encoding="utf-8").read(400)
    assert head.startswith("---")
    assert "name:" in head and "description:" in head


def test_nesting_refusal_true_inside_a_run():
    r = run.nesting_refusal({"SUPERHEROES_ACCEPTANCE_CONTEXT": "1"})
    assert r["refuse"] is True
    assert "nest" in r["reason"].lower()


def test_nesting_refusal_false_at_top_level():
    r = run.nesting_refusal({})
    assert r["refuse"] is False
