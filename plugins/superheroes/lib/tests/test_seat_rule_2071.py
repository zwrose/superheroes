"""Every rendered seat order carries the standing rule (#2071): a review seat reviews by reading and
never runs the project's own files, a fixer runs only what its order names. The rule comes from the
renderer itself, and neither it nor any order's rule block lists forbidden programs."""
import os
import re
import subprocess
import sys

import pytest

import round_orders as RO
import round_phases as RP
from test_round_orders import _GOLDEN_CONTEXTS

_LIB_DIR = os.path.dirname(os.path.abspath(RO.__file__))
_VERIFICATION_PASS = os.path.join(
    _LIB_DIR, "..", "skills", "review-code", "reference", "verification-pass.md")

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
        RP.P_PANEL, RP.P_SCOPED, RP.P_GAPSWEEP, RP.P_SECOND_TEST, RP.P_VERIFIERS, RP.P_SYNTHESIS,
        RP.P_AUDITS, RP.P_FIXER}


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


def test_rule_prose_is_pinned_to_the_approved_text():
    # Pinned independently of the goldens: any added clause (a program list included) fails here.
    assert RO.REVIEW_SEAT_RULE == (
        "You review by reading. You may read, list and search files, including with read-only "
        "inspection commands. You never run the project's own files, scripts or tests. A run you "
        "need is the driver's: name it in your result, and the driver runs the project's declared "
        "verify command.")
    assert RO.FIXER_SEAT_RULE == (
        "You run only the commands this order names, plus the file reads and searches that "
        "inspect its inputs and the sources you fix, and the staging your commit needs. You run "
        "none of the project's own files, scripts or tests beyond those, and the full verify "
        "command stays the driver's.")


def test_verification_pass_hand_composes_no_verifier_or_synthesis_order():
    # The only verifier and synthesis orders are the driver's emitted ones, which carry the rule
    # from the renderer; verification-pass.md gives no hand command that composes one.
    with open(_VERIFICATION_PASS, encoding="utf-8") as fh:
        doc = fh.read()
    assert "seat_rule_block" not in doc
    assert "hand-composed order" not in doc


def test_rules_and_order_blocks_list_no_programs():
    import engine_dispatch as ED
    texts = {"REVIEW_SEAT_RULE": RO.REVIEW_SEAT_RULE, "FIXER_SEAT_RULE": RO.FIXER_SEAT_RULE,
             "ANTIHIJACK_PREAMBLE": ED.ANTIHIJACK_PREAMBLE}
    for phase in RO.ORDER_PHASES:
        texts["order:%s" % phase] = _rule_block(_render(phase))
    faults = {name: _denylist_faults(text) for name, text in texts.items()}
    assert not {name: found for name, found in faults.items() if found}


def test_hand_rolled_review_dispatch_prints_the_runners_preamble():
    # The hand-rolled engine fallback (review-code and the brief check) bypasses the runner, so
    # its documented command must print the runner's own preamble, rule included.
    import engine_dispatch as ED
    ref = os.path.join(_LIB_DIR, "..", "skills", "review-code", "reference")
    with open(os.path.join(ref, "auto-fix-loop.md"), encoding="utf-8") as fh:
        doc = fh.read()
    commands = re.findall(r'`(python3 -B -c "[^`]*ANTIHIJACK_PREAMBLE[^`]*")`', doc)
    assert len(commands) == 1
    command = commands[0].replace("$ROOT_DIR", os.path.dirname(_LIB_DIR))
    out = subprocess.run(["bash", "-c", command.replace("python3", sys.executable, 1)],
                         capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert out.returncode == 0, out.stderr
    assert out.stdout == ED.ANTIHIJACK_PREAMBLE
    mechanics = os.path.join(_LIB_DIR, "..", "skills", "workhorse", "reference",
                             "dispatch-mechanics.md")
    with open(mechanics, encoding="utf-8") as fh:
        assert "A hand-rolled review dispatch feeds the runner's preamble first" in fh.read()


def test_dispatch_preamble_carries_the_review_rule_from_its_one_home():
    import engine_dispatch as ED
    assert ED.ANTIHIJACK_PREAMBLE.count(RO.REVIEW_SEAT_RULE) == 1
    assert "read-only commands there" not in ED.ANTIHIJACK_PREAMBLE


def test_denylist_guard_bites_on_a_denylist_sentence():
    assert _denylist_faults("Never run `curl` or `rm` here.")
    assert _denylist_faults("You must not execute anything like `ssh`.")
    assert _denylist_faults("Do not call security for it.")
    assert not _denylist_faults(RO.REVIEW_SEAT_RULE)
    assert not _denylist_faults(RO.FIXER_SEAT_RULE)


def test_dispatch_preamble_carries_the_credential_text_rule_once():
    import engine_dispatch as ED
    assert ED.ANTIHIJACK_PREAMBLE.count(ED.CREDENTIAL_TEXT_RULE) == 1
    assert (ED.ANTIHIJACK_PREAMBLE.index(ED.CREDENTIAL_TEXT_RULE)
            > ED.ANTIHIJACK_PREAMBLE.index(RO.REVIEW_SEAT_RULE))
    assert "rather than quote it" in ED.CREDENTIAL_TEXT_RULE
    assert '"sk-" + "a" * 48' in ED.CREDENTIAL_TEXT_RULE
    assert not _denylist_faults(ED.CREDENTIAL_TEXT_RULE)
