"""#1272 layer 2d WO-B — order templates and round-driver reference round economy pins."""
import os

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_TESTS))

_FINDING_TEMPLATES = [
    "rubric/orders/dispatch-panel.md",
    "rubric/orders/dispatch-gap-sweep.md",
    "rubric/orders/dispatch-scoped-finder.md",
    "rubric/orders/dispatch-audits.md",
]


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("rel", _FINDING_TEMPLATES, ids=_FINDING_TEMPLATES)
def test_p1_line_compile_rule_prose(rel):
    # axis: four finding-producing templates document numeric-string coercion
    text = _read(rel)
    assert "is coerced to its integer" in text
    assert "line is not an integer" in text
    assert "a string line is refused at compile" not in text


def test_p2_fixer_template_verify_budget_placeholder():
    # axis: fixer template carries scoped verify budget, not full verify command
    text = _read("rubric/orders/dispatch-fixer.md")
    assert "{{VERIFY_BUDGET}}" in text
    assert "{{VERIFY_COMMAND}}" not in text
    assert "never the project's full verify command" in text


def test_p3_round_driver_round_economy_reference():
    # axis: round-driver reference documents round economy and concurrent gate
    text = _read("skills/review-code/reference/round-driver.md")
    assert "## Round economy" in text
    economy_start = text.index("## Round economy")
    economy_end = text.index("## Lens coverage beside counts", economy_start)
    economy = text[economy_start:economy_end]
    assert "round_phases.FIX_BATCH_CAP_DEFAULT" in economy
    audits_row_start = text.index("| `dispatch-audits` |")
    audits_row_end = text.index("\n", audits_row_start)
    assert "payload.verify" in text[audits_row_start:audits_row_end]
    verify_row_start = text.index("| `run-verify` |")
    verify_row_end = text.index("\n", verify_row_start)
    assert "one full verify run" in text[verify_row_start:verify_row_end].lower()


def test_p4_auto_fix_loop_fixer_verify_budget_copy():
    # axis: auto-fix-loop illustrative fixer copy matches scoped budget contract
    text = _read("skills/review-code/reference/auto-fix-loop.md")
    assert "Verify budget:" in text
    assert "never the project's full verify command" in text
