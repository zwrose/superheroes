"""C1-L11e (WO-B): the doctrine says a stacked layer catches up at handback.

Read-only prose guards over the edited docs: a review session reads a stacked layer against the
lower-layer commit it pinned, a lower-layer move never stops or restarts it, and the layer catches up
before handback (a `--no-ff` merge, verify on the merged head, a returning review of the catch-up),
with the handback check refusing `stack-not-caught-up` until it has.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)

_NATIVE_STACKS = os.path.join(_PLUGIN, "rubric", "native-stacks.md")
_REVIEW_SKILL = os.path.join(_PLUGIN, "skills", "review-code", "SKILL.md")
_ROUND_DRIVER = os.path.join(_PLUGIN, "skills", "review-code", "reference", "round-driver.md")
_WORKHORSE = os.path.join(_PLUGIN, "skills", "workhorse", "SKILL.md")
_HANDBACK = os.path.join(_PLUGIN, "skills", "workhorse", "reference", "handback.md")
_TRANSITION = os.path.join(_PLUGIN, "TRANSITION.md")


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _flat(text):
    return " ".join(text.split())


def _slice(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _stays_current():
    return _flat(_slice(_text(_NATIVE_STACKS), "## How a stack stays current", "## Anti-patterns"))


def _workhorse_section(number):
    # § 12 is the last numbered section; "## Memory" follows it
    end = "## Memory" if number == 12 else "## %d. " % (number + 1)
    return _flat(_slice(_text(_WORKHORSE), "## %d. " % number, end))


# --- rubric/native-stacks.md -----------------------------------------------------------------------

def test_native_stacks_names_the_pinned_commit_and_the_catch_up_at_handback():
    # axis: the section says the session reads the pinned lower-layer commit and the layer catches up at handback
    section = _stays_current()
    assert "the lower-layer commit it pinned when it started, for its whole run" in section
    assert "a lower-layer move never stops or restarts it" in section
    assert "before the layer hands back" in section
    assert "local `--no-ff` merge" in section
    assert "runs the calibrated verify on the merged head" in section


def test_native_stacks_reviews_the_catch_up_as_a_returning_review():
    # axis: the catch-up is a returning review of the layer's own changed lines, empty when none changed
    section = _stays_current()
    assert "returning review session" in section
    assert "only what the catch-up changed in the layer's own lines" in section
    assert "empty returning round that carries the earlier review" in section
    assert "re-checked against the caught-up head" in section


def test_native_stacks_names_the_handback_check_refusal():
    # axis: the handback check refuses stack-not-caught-up until the pushed head holds the lower layer's head
    section = _stays_current()
    assert "lib/vet_slot.py handback --pr <n> --repo <owner/name>" in section
    assert "`stack-not-caught-up`" in section


def test_native_stacks_keeps_never_bring_current_mid_review():
    # axis: the section keeps the rule that a layer is not brought current while its review loop is open
    section = _stays_current()
    assert "while its review loop is open" in section
    assert "`view-head-anchor-mismatch`" in section


def test_native_stacks_holds_no_stop_and_restart_wording():
    # axis: the section has no retired token and no stop, abandon or new-session wording for a lower-layer move
    section = _stays_current()
    for banned in ("stack-lower-moved", "stack-lower-ahead", "starts a new session", "abandoned"):
        assert banned not in section, banned


# --- review-code ----------------------------------------------------------------------------------

def test_review_code_docs_hold_no_retired_stack_tokens():
    # axis: neither the review-code skill nor the round-driver reference keeps a retired token or identifier
    for path in (_REVIEW_SKILL, _ROUND_DRIVER):
        text = _text(path)
        for banned in ("stack-lower-moved", "stack-lower-ahead", "stackLower", "STACK_LOWER"):
            assert banned not in text, (os.path.basename(path), banned)


def test_review_code_skill_says_the_session_reads_the_pinned_base_and_catches_up_at_handback():
    # axis: the replacement paragraph names the pinned base, that a move never stops the session, and the returning review
    text = _flat(_text(_REVIEW_SKILL))
    assert "reads the layer against the base commit pinned at Setup for its whole run" in text
    assert "a move of the lower layer never stops it" in text
    assert "The layer catches up at handback" in text
    assert "reviewed as a returning PR" in text


# --- workhorse --------------------------------------------------------------------------------------

def test_workhorse_section_10_names_the_catch_up_before_handback():
    # axis: § 10 says the layer catches up before handback and the handback check refuses stack-not-caught-up
    section = _workhorse_section(10)
    assert "A stacked layer catches up before handback." in section
    assert "catch-up reviewed as a returning review" in section
    assert "`stack-not-caught-up`" in section
    assert "start a new session" not in section


def test_workhorse_section_12_names_the_catch_up_between_sessions():
    # axis: § 12 says the catch-up happens between review sessions, never inside one, and re-runs the handback check
    section = _workhorse_section(12)
    assert "catches up between review sessions, never inside one" in section
    assert "`--no-ff` merge" in section
    assert "returning review" in section
    assert "`stack-not-caught-up`" in section
    assert "start a new session" not in section


# --- handback.md and TRANSITION.md ------------------------------------------------------------------

def test_handback_reference_names_the_pr_mode_handback_check():
    # axis: handback.md has the builder run the PR-mode handback check, naming its stacked-layer refusal
    text = _flat(_text(_HANDBACK))
    assert "vet_slot.py\" handback --pr <n> --repo <owner/name>" in text
    assert "`stack-not-caught-up`" in text


def test_transition_has_the_catch_up_note_and_no_retired_token():
    # axis: TRANSITION.md carries the catch-up subsection (wherever release day moved it) and never the retired lower-layer-moved token
    text = _text(_TRANSITION)
    heading = "### Review: a stacked layer catches up at handback"
    start = text.index(heading)
    following = re.search(r"^#{2,3} ", text[start + len(heading):], re.M)
    end = start + len(heading) + following.start() if following else len(text)
    note = text[start:end]
    assert "`stack-not-caught-up`" in note
    assert "stack-lower-moved" not in note
