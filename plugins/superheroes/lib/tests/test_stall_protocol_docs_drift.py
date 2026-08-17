"""Stall-protocol drift guard: `round_phases` is authoritative, both hand-maintained doc copies
must follow (#1037 rider).

The stall menu is described in TWO places a reader can reach independently — the review-code
SKILL.md loop step and `reference/round-driver.md`'s phase table — and neither is generated from the
other. The #960 build changed the same word in both by hand and review caught the copy it missed;
that near-miss is what this census is for. It reads the vocabulary off the code constants and
requires it in BOTH files, so a vocabulary change in one fails until the other follows.

Scope, stated so a reader does not over-read the guard: this pins the stall VOCABULARY and the
eligibility/once-per-session gate words, not the surrounding prose. Two docs can still describe the
same vocabulary differently — no census over prose can rule that out — but neither can silently
carry a choice name the other does not.
"""
import os

import pytest

import round_phases as RP

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))

# The two hand-maintained copies. A third copy added without extending this tuple is exactly the
# drift this guard cannot see — keep it enumerated here, not discovered.
_STALL_DOCS = (
    "skills/review-code/SKILL.md",
    "skills/review-code/reference/round-driver.md",
)


def _read(rel):
    path = os.path.join(_PLUGIN, rel)
    assert os.path.exists(path), "stall-protocol doc moved or renamed: %s" % rel
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("rel", _STALL_DOCS)
def test_every_live_stall_choice_appears_in_both_docs(rel):
    """Each offerable choice name is spelled in each doc — the census that couples the two copies."""
    text = _read(rel)
    missing = [choice for choice in RP.STALL_CHOICES if choice not in text]
    assert not missing, (
        "%s does not carry stall choice(s) %r — `round_phases.STALL_CHOICES` is authoritative; "
        "update every doc in _STALL_DOCS together" % (rel, missing))


@pytest.mark.parametrize("rel", _STALL_DOCS)
def test_no_retired_stall_choice_is_still_advertised(rel):
    """A retired choice must not survive in a doc as a live menu item.

    `cmd_submit` refuses one with `stall-choice-retired:<name>`, so a doc that still names it sends
    an orchestrator to a guaranteed refusal."""
    text = _read(rel)
    lingering = [choice for choice in RP.RETIRED_STALL_CHOICES if choice in text]
    assert not lingering, (
        "%s still names retired stall choice(s) %r — `cmd_submit` refuses them "
        "(`stall-choice-retired:`)" % (rel, lingering))


@pytest.mark.parametrize("rel", _STALL_DOCS)
def test_both_docs_carry_the_eligibility_and_once_per_session_gates(rel):
    """The two gates that decide what the menu OFFERS, not just what it is called.

    `acceptRiskEligible` is the payload field an orchestrator reads to decide whether to present
    `accept-the-disclosed-risk`; `once per session` is the `one-more-round` latch. A doc carrying
    the choice names but neither gate would describe a menu with the wrong options."""
    text = _read(rel)
    for fragment in ("acceptRiskEligible", "once per session"):
        assert fragment in text, (
            "%s is missing the stall gate fragment %r" % (rel, fragment))


def test_the_census_is_not_vacuous():
    """A/B for the guard itself: the vocabulary it censuses is non-empty and really is in the docs.

    Without this, an emptied `STALL_CHOICES` (or a doc list that happened to match nothing) would
    make every parametrized case above pass by having nothing to check."""
    assert RP.STALL_CHOICES, "no live stall choices to census"
    assert RP.RETIRED_STALL_CHOICES, "no retired stall choices to census"
    for rel in _STALL_DOCS:
        text = _read(rel)
        assert any(choice in text for choice in RP.STALL_CHOICES), rel
