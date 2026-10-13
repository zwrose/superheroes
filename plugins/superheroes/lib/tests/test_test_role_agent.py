"""Drift guard for the test role's agent file and the code reviewer's break-it reading duty.

Bites on: a second copy of the ``break-it-test v1`` block's lines in ``agents/test-role.md`` (the
grammar's one home is ``break_it.BLOCK_TEMPLATE``); the ``break-it-test`` taxonomy token in
``agents/code-reviewer.md``; and the absence of the retired ``agents/test-reviewer.md``.

Pins structure only, never a prose sentence.
"""
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
TEST_ROLE = PLUGIN / "agents" / "test-role.md"
CODE_REVIEWER = PLUGIN / "agents" / "code-reviewer.md"
RETIRED = PLUGIN / "agents" / "test-reviewer.md"


def _text(path):
    # Whitespace-collapsed, so a re-wrapped line does not move a pin.
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("*", ""))


def test_test_role_agent_pins_the_break_it_block_shape():
    raw = TEST_ROLE.read_text(encoding="utf-8")
    reviewer = _text(CODE_REVIEWER)
    # Bites on: a second copy of the block's lines in the agent file, which the dispatch renders from the code.
    assert not re.search(r"^break-it-test v1\npath:", raw, re.MULTILINE)
    # Bites on: the code reviewer's taxonomy token for the break-it tests a change keeps.
    assert "break-it-test" in reviewer


def test_test_reviewer_agent_file_is_gone():
    # Bites on: a revived test-reviewer agent, which would put two test seats on one panel.
    assert not RETIRED.exists()
