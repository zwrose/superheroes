# plugins/superheroes/lib/tests/test_acceptance_skill_contract.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_run as run

# The acceptance skill front door lives repo-local (issue #237) — a developing-superheroes
# tool, not a distributed plugin skill. The harness lib + fixtures stay in the plugin.
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SKILL = os.path.join(_REPO, ".claude", "skills", "acceptance", "SKILL.md")


def test_skill_file_exists_and_declares_frontmatter():
    assert os.path.isfile(SKILL)
    head = open(SKILL, encoding="utf-8").read(400)
    assert head.startswith("---")
    assert "name:" in head and "description:" in head


def test_skill_is_repo_local_not_plugin_rooted():
    # repo-local skills cannot resolve via the plugin-root seam; they resolve the lib from the
    # checkout instead. (The seam may be *named* in explanatory prose, but never USED to resolve.)
    body = open(SKILL, encoding="utf-8").read()
    assert "${CLAUDE_PLUGIN_ROOT:-" not in body  # the resolution seam is absent
    assert "git rev-parse --show-toplevel" in body


def test_nesting_refusal_true_inside_a_run():
    r = run.nesting_refusal({"SUPERHEROES_ACCEPTANCE_CONTEXT": "1"})
    assert r["refuse"] is True
    assert "nest" in r["reason"].lower()


def test_nesting_refusal_false_at_top_level():
    r = run.nesting_refusal({})
    assert r["refuse"] is False
