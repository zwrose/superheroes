"""Census of the surfaces that tell a panel reviewer what to do with issues in untouched lines.

`rubric/review-base.md` is the one home of the rule and of its number (the cap on outside findings per
reviewer). Every other surface states the same number beside the words "outside finding" and points at that
home. No surface may still say such issues are only skipped.
"""
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]

HOME = PLUGIN / "rubric" / "review-base.md"
PANEL_SURFACES = [
    "agents/architecture-reviewer.md",
    "agents/code-reviewer.md",
    "agents/security-reviewer.md",
    "agents/premortem-reviewer.md",
    "agents/test-role.md",
    "rubric/orders/dispatch-panel.md",
]
VET_RECEIPT = PLUGIN / "skills" / "showrunner" / "reference" / "vet-receipt.md"
GLOSSARY = PLUGIN / "rubric" / "glossary.md"

# The phrases that told a reviewer untouched-line issues are only skipped.
OLD_SKIP_PHRASES = [
    "Pre-existing patterns outside the diff are out of scope",
    "Pre-existing layering smells outside the diff are out of scope",
    "Pre-existing weaknesses outside the diff are out of scope",
    "Pre-existing test smells outside the diff are out of scope",
    "pre-existing — SKIP",
    "pre-existing — skip",
    "pre-existing → SKIP",
    "SKIPPED, not reported",
    "Do NOT flag pre-existing",
    "Pre-existing test smells in context lines → SKIP",
]

_NUMBER = re.compile(r"\bat most (\d+)\b", re.IGNORECASE)
_WINDOW = 120


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def cap_numbers(text):
    """The numbers of every `at most N` that sits within a short window of `outside finding`."""
    found = []
    for match in _NUMBER.finditer(text):
        window = text[max(0, match.start() - _WINDOW):match.end() + _WINDOW]
        if re.search(r"outside\s+findings?", window, re.IGNORECASE):
            found.append(match.group(1))
    return found


def _home_cap():
    numbers = cap_numbers(_read(HOME))
    assert numbers, "review-base.md states no cap beside the words 'outside finding'"
    assert len(set(numbers)) == 1, f"review-base.md states more than one cap: {numbers}"
    return numbers[0]


def test_d1_home_states_the_cap():
    assert _home_cap().isdigit()
    assert len(cap_numbers(_read(HOME))) == 1, "the home states the cap in exactly one sentence"


@pytest.mark.parametrize("surface", PANEL_SURFACES)
def test_d2_surface_states_the_homes_cap(surface):
    home = _home_cap()
    numbers = cap_numbers(_read(PLUGIN / surface))
    assert numbers, f"{surface} states no cap beside the words 'outside finding'"
    assert set(numbers) == {home}, f"{surface} states {numbers}, the home states {home}"


@pytest.mark.parametrize("surface", ["rubric/review-base.md"] + PANEL_SURFACES)
def test_d3_no_surface_still_only_skips_untouched_lines(surface):
    text = _read(PLUGIN / surface)
    left = [phrase for phrase in OLD_SKIP_PHRASES if phrase in text]
    assert not left, f"{surface} still says: {left}"


def test_d4_vet_receipt_sorts_the_outside_list():
    text = _read(VET_RECEIPT)
    triggered = [line for line in text.splitlines() if line.startswith("|") and "outsideThisPR" in line]
    assert triggered, "no triggered-fields row names outsideThisPR"
    assert "## The outside list" in text
    assert "(#the-outside-list)" in text, "the Contents or the row does not link the section"


def _outside_section(text):
    """The text of vet-receipt.md's `## The outside list` section, up to the next `## ` heading."""
    assert "## The outside list" in text
    return text.split("## The outside list", 1)[1].split("\n## ", 1)[0]


def _numbered_instructions(section):
    """The numbered instruction list of the section (`1. ...`, `2. ...`), each item with its continuation lines. The
    list ends at the first line that is neither an item, an indented continuation nor blank, so the field template and
    the sample block after it are never part of it."""
    items, started = [], False
    for line in section.splitlines():
        if re.match(r"\d+\.\s", line):
            items.append(line)
            started = True
        elif started and line.startswith((" ", "\t")):
            items[-1] += "\n" + line
        elif started and line.strip():
            break
    return items


def test_d4_the_numbered_instructions_carry_the_two_choices_and_the_owners_word():
    # read from the numbered list alone: the template and the sample block both say `dismissed`, so they cannot stand in
    items = _numbered_instructions(_outside_section(_read(VET_RECEIPT)))
    assert len(items) == 2, f"expected two numbered choices, found {len(items)}"
    follow_up, dismissal = items
    assert "follow-up" in follow_up and re.search(r"proposed follow-up|follow-up filing", follow_up), "no follow-up choice"
    assert re.search(r"[Nn]othing\s+is\s+filed\s+until\s+the\s+owner's\s+word", follow_up), \
        "the follow-up does not wait on the owner's word"
    assert re.search(r"dismissal|dismissed", dismissal) and "reason" in dismissal, "no dismissal-with-reason choice"
    # the choice words the field carries are the template's, kept apart from the instructions above
    assert "follow-up | dismissed" in _fenced_blocks(_outside_section(_read(VET_RECEIPT)))[0]


def _fenced_blocks(section):
    """The body of each fenced code block in `section`, in order."""
    return re.findall(r"^```[^\n]*\n(.*?)^```", section, re.MULTILINE | re.DOTALL)


def test_d4_each_block_the_vet_receipt_emits_opens_with_the_outside_field():
    section = _outside_section(_read(VET_RECEIPT))
    # the prose sentence that names the field, checked on its own
    assert re.search(r"fixed field, `\*\*Outside this PR\.\*\*`", section), "the prose does not name the field"
    blocks = _fenced_blocks(section)
    assert len(blocks) == 2, f"expected the template block and the sample block, found {len(blocks)}"
    template, sample = blocks
    for name, block in (("template", template), ("sample", sample)):
        assert block.splitlines()[0] == "**Outside this PR.**", f"the {name} block's first line is not the field"
    assert "<hit id>" in template and "<hit id>" not in sample, "the template and sample blocks are not in that order"


def test_d5_glossary_defines_outside_finding_and_home_links_it():
    assert "### Outside finding" in _read(GLOSSARY)
    assert "glossary.md#outside-finding" in _read(HOME)
