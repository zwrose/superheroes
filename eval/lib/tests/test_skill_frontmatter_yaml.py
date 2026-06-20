# eval/lib/tests/test_skill_frontmatter_yaml.py
"""Every shipped SKILL.md frontmatter must round-trip through strict yaml.safe_load.

The published-skill loader and the structural validate_skills.py regex tolerate a bare
``colon: space`` in a description, but strict ``yaml.safe_load`` rejects it. Guard against
that drift: parse each frontmatter block — with the SAME regex skills.parse_skill uses — via
a real YAML loader and assert the description it yields matches the one the stdlib structural
parser (skills.parse_skill) extracts.
"""
import os

import pytest
import yaml

import skills

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_PATHS = skills.iter_skill_paths(os.path.join(ROOT, "plugins"))


def test_there_are_skills_to_check():
    assert _PATHS, "no SKILL.md files found — yaml round-trip gate would be vacuous"


@pytest.mark.parametrize("path", _PATHS, ids=[skills.skill_key(p) for p in _PATHS])
def test_frontmatter_round_trips_through_yaml(path):
    key = skills.skill_key(path)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = skills._FRONTMATTER.match(text)
    assert m, f"{key}: no leading frontmatter block"
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:  # pragma: no cover - the assertion message is the point
        pytest.fail(
            f"{key}: frontmatter is not strict-YAML (quote the description if it "
            f"has a bare 'colon: space'): {exc}")
    assert isinstance(data, dict) and "description" in data, \
        f"{key}: frontmatter has no description"
    regex_desc, _ = skills.parse_skill(text)
    assert data["description"] == regex_desc, (
        f"{key}: yaml.safe_load and skills.parse_skill disagree on the description")
