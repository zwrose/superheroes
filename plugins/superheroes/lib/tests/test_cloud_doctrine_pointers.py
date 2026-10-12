"""Cloud doctrine census: the charter points at the cloud reference, and the reference names real verbs."""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN = os.path.abspath(os.path.join(_LIB, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder  # noqa: E402

_CLOUD_REF = "skills/workhorse/reference/cloud.md"
_CLOUD_SECTIONS = ("1", "2", "3", "10", "11", "12")


def _read_plugin(rel):
    with open(os.path.join(_PLUGIN, rel), encoding="utf-8") as fh:
        return fh.read()


def _charter_section(number):
    chunks = re.split(r"(?m)^## ", _read_plugin("skills/workhorse/SKILL.md"))
    found = [chunk for chunk in chunks if chunk.startswith(number + ". ")]
    assert len(found) == 1, "charter section %s: expected one heading, found %d" % (number, len(found))
    return found[0]


@pytest.mark.parametrize("number", _CLOUD_SECTIONS)
def test_each_cloud_section_points_at_the_cloud_reference(number):
    assert _CLOUD_REF in _charter_section(number), (
        "charter section %s has no pointer to %s" % (number, _CLOUD_REF))


def test_every_cloud_builder_verb_the_reference_names_exists():
    named = set(re.findall(r"cloud_builder\.py\s+([a-z][a-z-]*)", _read_plugin(_CLOUD_REF)))
    parser = cloud_builder._build_parser()
    verbs = next(a for a in parser._actions if getattr(a, "choices", None)).choices
    assert named, "%s names no cloud_builder.py verb" % _CLOUD_REF
    assert sorted(named - set(verbs)) == [], "verbs the CLI lacks: %s" % sorted(named - set(verbs))
    required = {"intake", "note", "review-lapsed", "pr-json", "repo-json", "github-channel"}
    assert required <= named, "verbs the reference must name: %s" % sorted(required - named)


def test_size_names_the_builder_note():
    text = _read_plugin("rubric/review-discipline.md")
    match = re.search(r"(?ms)^### Size\n.*?(?=^#{2,3} |\Z)", text)
    assert match, "review-discipline.md has no ### Size section"
    assert "builder note" in match.group(0)
    assert _CLOUD_REF in match.group(0)
