# eval/lib/tests/test_skill_frontmatter_yaml.py
"""Per-skill application of validate_skills.check_frontmatter_yaml plus non-vacuity guard.

The frontmatter-YAML rule is owned by validate_skills.check_frontmatter_yaml; this module
does not re-derive it — it applies that function to every shipped SKILL.md and asserts
an empty violation list per skill.
"""
import os
import sys

import pytest

import skills

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_PATHS = skills.iter_skill_paths(os.path.join(ROOT, "plugins"))

_SCRIPTS = os.path.join(ROOT, ".github", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

try:
    from validate_skills import check_frontmatter_yaml
except ImportError as exc:
    raise ImportError(
        f"validate_skills is not importable from {_SCRIPTS!r} — "
        "frontmatter-YAML gate cannot run"
    ) from exc


def test_there_are_skills_to_check():
    assert _PATHS, "no SKILL.md files found — yaml round-trip gate would be vacuous"


@pytest.mark.parametrize("path", _PATHS, ids=[skills.skill_key(p) for p in _PATHS])
def test_frontmatter_round_trips_through_yaml(path):
    key = skills.skill_key(path)
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    # Stricter than check_frontmatter_yaml alone: every shipped SKILL.md must have frontmatter.
    assert skills._FRONTMATTER.match(raw), f"{key}: no leading frontmatter block"
    regex_description, _ = skills.parse_skill(raw)
    violations = check_frontmatter_yaml(key, raw, regex_description)
    assert violations == [], f"{key}: {violations}"
