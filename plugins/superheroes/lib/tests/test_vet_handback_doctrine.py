"""The vet's handback doctrine keeps its structure: open findings, the cap-choice field, the claims check.

Each pin is a structural identifier, never a doctrine sentence: a heading or an anchor link, a receipt
field label, the cap-choice marker and its spellings, a removed flag. Each guarded element is one test
node. The text is read as the vet reads it, with runs of whitespace collapsed, so a re-wrapped line does
not move a pin.
"""
# Bites on: a structural identifier below (heading, anchor link, field label, cap-choice marker or spelling, removed flag) dropped or renamed out of its section; never doctrine sentences.
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN_ROOT = os.path.dirname(_LIB)
_SHOWRUNNER = os.path.join(_PLUGIN_ROOT, "skills", "showrunner")
_VET_RECEIPT = os.path.join(_SHOWRUNNER, "reference", "vet-receipt.md")
_VETTING = os.path.join(_SHOWRUNNER, "reference", "vetting.md")
_SKILL = os.path.join(_SHOWRUNNER, "SKILL.md")

_TRIGGERED = "## Triggered fields — the artifacts raise them, not your memory"
_OPEN_FINDINGS = "## A handback with open findings"
_CLAIMS = "## The claims check"

# (id, path, heading or None for the whole file, needles that must be present, needles that must be absent)
_ELEMENTS = (
    ("heading-open-findings", _VET_RECEIPT, _TRIGGERED,
     ("[A handback with open findings](#a-handback-with-open-findings)",), ()),
    ("heading-claims-check", _VET_RECEIPT, _TRIGGERED, ("[The claims check](#the-claims-check)",), ()),
    ("spelling-extra-audit-round", _VET_RECEIPT, _OPEN_FINDINGS, ("`extra-audit-round`",), ()),
    ("spelling-leftover", _VET_RECEIPT, _OPEN_FINDINGS, ("`leftover`",), ()),
    ("spelling-rethink", _VET_RECEIPT, _OPEN_FINDINGS, ("`rethink`",), ()),
    ("marker-template", _VET_RECEIPT, _OPEN_FINDINGS, ("<!-- superheroes:cap-choice choice=",), ()),
    ("key-is-finding-key", _VET_RECEIPT, _OPEN_FINDINGS, ("`findingKey`",), ()),
    ("field-cap-choices", _VET_RECEIPT, _OPEN_FINDINGS, ("`**Cap choices.**`",), ()),
    ("field-decided-for-veto", _VET_RECEIPT, _OPEN_FINDINGS, ("`**Decided for the owner's veto.**`",), ()),
    ("field-claims-checked", _VET_RECEIPT, _CLAIMS, ("`**Claims checked.**`",), ()),
    ("claims-line-shape", _VET_RECEIPT, _CLAIMS, ("— holds | does not hold —",), ()),
    ("vetting-no-review-only", _VETTING, None, (), ("--review-only",)),
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
    # axis: a structural identifier dropped or renamed out of its section
    text = _normalise(_section(path, heading))
    for needle in present:
        assert _normalise(needle) in text, f"{os.path.basename(path)} {heading or '(whole file)'}: missing {needle!r}"
    for needle in absent:
        assert _normalise(needle) not in text, f"{os.path.basename(path)}: still carries {needle!r}"
