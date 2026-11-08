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
    # axis: section pointers; a cloud section of the charter with no pointer to the cloud reference
    assert _CLOUD_REF in _charter_section(number), (
        "charter section %s has no pointer to %s" % (number, _CLOUD_REF))


def _named_verbs(text):
    return set(re.findall(r"cloud_builder\.py\s+([^\s`]+)", text))


def _parser_verbs():
    parser = cloud_builder._build_parser()
    return next(a for a in parser._actions if getattr(a, "choices", None)).choices


def test_every_cloud_builder_verb_the_reference_names_exists():
    # axis: verbs; a verb the reference names that the CLI lacks, or a required verb the reference omits
    named = _named_verbs(_read_plugin(_CLOUD_REF))
    verbs = _parser_verbs()
    assert named, "%s names no cloud_builder.py verb" % _CLOUD_REF
    assert sorted(named - set(verbs)) == [], "verbs the CLI lacks: %s" % sorted(named - set(verbs))
    required = {"intake", "note", "review-lapsed", "pr-json", "repo-json", "github-channel"}
    assert required <= named, "verbs the reference must name: %s" % sorted(required - named)


def test_size_names_the_builder_note():
    # axis: the Size section; the review-discipline Size section not naming the builder note and the cloud reference
    text = _read_plugin("rubric/review-discipline.md")
    match = re.search(r"(?ms)^### Size\n.*?(?=^#{2,3} |\Z)", text)
    assert match, "review-discipline.md has no ### Size section"
    assert "builder note" in match.group(0)
    assert _CLOUD_REF in match.group(0)


_DETECTIVE_CLOUD_REF = "skills/detective/reference/cloud.md"
_TRANSIT = "Text changed in transit"


def _section_of(rel, heading):
    chunks = re.split(r"(?m)^## ", _read_plugin(rel))
    found = [chunk for chunk in chunks if chunk.split("\n", 1)[0] == heading]
    assert len(found) == 1, "%s: expected one '## %s' heading, found %d" % (rel, heading, len(found))
    return found[0]


@pytest.mark.parametrize(
    "rel, heading",
    [
        pytest.param(_CLOUD_REF, "Preflight", id="preflight"),
        pytest.param(_CLOUD_REF, "Review", id="review"),
        pytest.param(_CLOUD_REF, "Terminal comments: handback, stop, park", id="terminal-comments"),
        pytest.param(_CLOUD_REF, "Handback", id="handback"),
        pytest.param(_DETECTIVE_CLOUD_REF, "Terminal notes", id="detective-terminal-notes"),
    ],
)
def test_each_write_section_names_the_transit_read_back(rel, heading):
    # axis: transit pointers; a section where a builder writes to GitHub that no longer names the read-back section — see bite-proof record i2383_transit_compare
    assert _TRANSIT in _section_of(rel, heading), (
        "%s '## %s' does not name '%s'" % (rel, heading, _TRANSIT))
    _section_of(_CLOUD_REF, _TRANSIT)  # the section the pointers name must itself exist, exactly once


def test_verb_census_reads_whole_tokens():
    # axis: whole tokens; a misspelled verb that merely starts with a real one read as the real one
    named = _named_verbs("cloud_builder.py intake2 --repo-root /repo --launch-file /launch")
    assert named == {"intake2"}
    assert named - set(_parser_verbs()) == {"intake2"}
