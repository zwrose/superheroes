"""The vet's handback doctrine stays in its sections: open findings, the cap-choice field, the claims check.

Each guarded element is one test node. The text is read as the vet reads it, with runs of whitespace
collapsed, so a re-wrapped line does not move a pin.
"""
# Bites on: a vet-doctrine rule below dropped or reworded out of its section.
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN_ROOT = os.path.dirname(_LIB)
_SHOWRUNNER = os.path.join(_PLUGIN_ROOT, "skills", "showrunner")
_VET_RECEIPT = os.path.join(_SHOWRUNNER, "reference", "vet-receipt.md")
_VETTING = os.path.join(_SHOWRUNNER, "reference", "vetting.md")
_OWNER_DECISIONS = os.path.join(_SHOWRUNNER, "reference", "owner-decisions.md")
_SKILL = os.path.join(_SHOWRUNNER, "SKILL.md")

_TRIGGERED = "## Triggered fields — the artifacts raise them, not your memory"
_OPEN_FINDINGS = "## A handback with open findings"
_CLAIMS = "## The claims check"
_ESCALATION = "## Vet-time escalation"
_SPINE = "## The per-item spine"

# (id, path, heading or None for the whole file, needles that must be present, needles that must be absent)
_ELEMENTS = (
    ("heading-open-findings", _VET_RECEIPT, _TRIGGERED,
     ("[A handback with open findings](#a-handback-with-open-findings)",), ()),
    ("heading-claims-check", _VET_RECEIPT, _TRIGGERED, ("[The claims check](#the-claims-check)",), ()),
    ("spelling-extra-audit-round", _VET_RECEIPT, _OPEN_FINDINGS, ("`extra-audit-round`",), ()),
    ("spelling-leftover", _VET_RECEIPT, _OPEN_FINDINGS, ("`leftover`",), ()),
    ("spelling-rethink", _VET_RECEIPT, _OPEN_FINDINGS, ("`rethink`",), ()),
    ("marker-template", _VET_RECEIPT, _OPEN_FINDINGS, ("<!-- superheroes:cap-choice choice=",), ()),
    ("key-is-finding-key", _VET_RECEIPT, _OPEN_FINDINGS, ("`key` is", "`findingKey`", "never the finding's `id`"), ()),
    ("posted-line-never-rewritten", _VET_RECEIPT, _OPEN_FINDINGS, ("A posted line is never removed or rewritten",),
     ()),
    ("once-per-pr", _VET_RECEIPT, _OPEN_FINDINGS, ("at most once",), ()),
    ("audit-only-scope", _VET_RECEIPT, _OPEN_FINDINGS, ("no panel", "no new search"), ()),
    ("no-leftover-for-critical", _VET_RECEIPT, _OPEN_FINDINGS, ("An open Critical is never a leftover",), ()),
    ("craft-not-a-question", _VET_RECEIPT, _OPEN_FINDINGS, ("It never reaches the owner as a question",), ()),
    ("claims-tests-ran", _VET_RECEIPT, _CLAIMS, ("each claim that tests ran or passed",), ()),
    ("claims-dod-rows", _VET_RECEIPT, _CLAIMS, ("each row of its definition-of-done table",), ()),
    ("claims-verify-passed", _VET_RECEIPT, _CLAIMS, ("each claim that the verify command passed",), ()),
    ("claims-holds-shape", _VET_RECEIPT, _CLAIMS, ("holds | does not hold",), ()),
    ("claims-one-line-not-enough", _VET_RECEIPT, _CLAIMS,
     ("One line saying the claims were checked does not meet",), ()),
    ("vetting-no-review-only", _VETTING, None, (), ("--review-only",)),
    ("vetting-one-reviewer", _VETTING, _ESCALATION, ("one independent reviewer given the",), ()),
    ("leftover-owner-terms", _OWNER_DECISIONS, _SPINE, ("never a pick between code fixes",), ()),
    ("skill-cites-open-findings", _SKILL, None, ("vet-receipt.md` § A handback with open findings",), ()),
    ("skill-cites-claims-check", _SKILL, None, ("vet-receipt.md` § The claims check",), ()),
)


def _normalise(text):
    return re.sub(r"\s+", " ", text).strip()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section(path, heading):
    """The text from the `## ` heading line up to the next line starting with `## `, or the whole file."""
    text = _read(path)
    if heading is None:
        return text
    lines = text.split("\n")
    assert heading in lines, f"{os.path.basename(path)} has no heading {heading!r}"
    start = lines.index(heading)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


@pytest.mark.parametrize("path,heading,present,absent", [e[1:] for e in _ELEMENTS], ids=[e[0] for e in _ELEMENTS])
def test_vet_doctrine_rule_stays_in_its_section(path, heading, present, absent):
    # axis: a vet-doctrine rule dropped or reworded out of its section
    text = _normalise(_section(path, heading))
    for needle in present:
        assert _normalise(needle) in text, f"{os.path.basename(path)} {heading or '(whole file)'}: missing {needle!r}"
    for needle in absent:
        assert _normalise(needle) not in text, f"{os.path.basename(path)}: still carries {needle!r}"
