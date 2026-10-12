"""Drift guard for the test role's agent file and the code reviewer's break-it reading duty.

Bites on: the load-bearing statements of ``agents/test-role.md`` and ``agents/code-reviewer.md``,
each pinned by a short literal; and the absence of the retired ``agents/test-reviewer.md``.

Residual blind spot: a literal proves the sentence is present, not that a reviewer obeys it.
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


def test_test_role_agent_pins_its_load_bearing_statements():
    raw = TEST_ROLE.read_text(encoding="utf-8")
    role = _text(TEST_ROLE)
    reviewer = _text(CODE_REVIEWER)
    # Bites on: the role's first duty, the mutation-survival question for each changed test.
    assert "would this test fail if the code under test were wrong" in role
    # Bites on: the cannot-fail finding, one per file, naming each such test.
    assert "one finding per file" in role
    assert "names each such test" in role
    # Bites on: the break-it block's header line, which the review loop parses.
    assert "```\nbreak-it-test v1\npath:" in raw
    # Bites on: the block's path and run lines, which the review loop parses.
    assert "path: <the same repo-relative path as `file`>\nrun: <one command, run from the repository root, that runs only this test file>\n" in raw
    # Bites on: the block's separator line between the header lines and the file content.
    assert "that runs only this test file>\n---\n<the complete file content>" in raw
    # Bites on: the first dropped duty, no coverage request outside every risk area.
    assert "More test coverage in code outside every risk area" in role
    # Bites on: the second dropped duty, no change of test style alone.
    assert "A change of test style alone" in role
    # Bites on: the rule that the share of test code is never a finding.
    assert "How much of a change is test code is never a finding on its own" in role
    # Bites on: the code reviewer reads the break-it tests a change keeps.
    assert "break-it-test" in reviewer
    assert "for bloat and for tests that pass without checking anything" in reviewer


def test_test_reviewer_agent_file_is_gone():
    # Bites on: a revived test-reviewer agent, which would put two test seats on one panel.
    assert not RETIRED.exists()
