"""Every rendered seat order carries the standing rule (#2071): a review seat reviews by reading and
never runs the project's own files, a fixer runs only what its order names. The rule comes from the
renderer itself, and neither it nor any order's rule block lists forbidden programs."""
import re

import pytest

import round_orders as RO
import round_phases as RP
from test_round_orders import _GOLDEN_CONTEXTS

# The guard's probe data: a sample of program names, kept here and nowhere in shipped code.
_PROGRAM_SAMPLE = ("security", "curl", "bash", "sh", "zsh", "python", "node", "rm", "mongosh",
                   "osascript", "ssh", "npm", "make", "git")
_DENYLIST_VERB_RE = re.compile(
    r"(?i)\b(never|do not|don't|must not|cannot)\s+(run|execute|call|invoke)\b.{0,80}?`[^`]+`",
    re.S)


def _render(phase):
    text, reason = RO.render_order(phase, "golden-seat", _GOLDEN_CONTEXTS[phase]())
    assert reason is None, reason
    return text


def _rule_block(text):
    """The text under the rule heading, up to the next blank line."""
    assert text.count(RO.SEAT_RULE_HEADING) == 1
    return text.split(RO.SEAT_RULE_HEADING + "\n\n", 1)[1].split("\n\n", 1)[0]


def _denylist_faults(text):
    faults = []
    if _DENYLIST_VERB_RE.search(text):
        faults.append("a never-run clause followed by a backticked word")
    for name in _PROGRAM_SAMPLE:
        if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text):
            faults.append("program name %r" % name)
    return faults


def test_every_seat_phase_is_rendered_and_covered():
    assert set(_GOLDEN_CONTEXTS) == set(RO.ORDER_PHASES)
    assert set(RO.ORDER_PHASES) == {
        RP.P_PANEL, RP.P_SCOPED, RP.P_GAPSWEEP, RP.P_VERIFIERS, RP.P_SYNTHESIS, RP.P_AUDITS,
        RP.P_FIXER}


@pytest.mark.parametrize("phase", list(RO.ORDER_PHASES))
def test_every_order_carries_its_rule_exactly_once(phase):
    text = _render(phase)
    expected = RO.FIXER_SEAT_RULE if phase == RP.P_FIXER else RO.REVIEW_SEAT_RULE
    other = RO.REVIEW_SEAT_RULE if phase == RP.P_FIXER else RO.FIXER_SEAT_RULE
    assert _rule_block(text) == expected
    assert text.count(expected) == 1
    assert other not in text


def test_review_rule_says_read_and_never_run_the_projects_files():
    assert "review by reading" in RO.REVIEW_SEAT_RULE
    assert "never run the project's own files, scripts or tests" in RO.REVIEW_SEAT_RULE
    assert "driver's" in RO.REVIEW_SEAT_RULE
    assert "run only the commands this order names" in RO.FIXER_SEAT_RULE
    assert "none of the project's own files, scripts or tests beyond those" in RO.FIXER_SEAT_RULE


def test_rules_and_order_blocks_list_no_programs():
    texts = {"REVIEW_SEAT_RULE": RO.REVIEW_SEAT_RULE, "FIXER_SEAT_RULE": RO.FIXER_SEAT_RULE}
    for phase in RO.ORDER_PHASES:
        texts["order:%s" % phase] = _rule_block(_render(phase))
    faults = {name: _denylist_faults(text) for name, text in texts.items()}
    assert not {name: found for name, found in faults.items() if found}


def test_denylist_guard_bites_on_a_denylist_sentence():
    assert _denylist_faults("Never run `curl` or `rm` here.")
    assert _denylist_faults("You must not execute anything like `ssh`.")
    assert _denylist_faults("Do not call security for it.")
    assert not _denylist_faults(RO.REVIEW_SEAT_RULE)
    assert not _denylist_faults(RO.FIXER_SEAT_RULE)
