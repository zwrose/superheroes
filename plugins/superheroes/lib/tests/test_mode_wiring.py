# Structural check that I2 wired the heroes into the registry record + coalesced nudge.
import os
import pytest

_SKILLS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills")

ASK_RECORD_SKILLS = ["review-init", "review-plan", "review-tasks",
                     "review-spec", "review-code", "audit-debt"]
NUDGE_SKILLS = ["review-init", "review-code", "audit-debt"]


def _skill(name):
    with open(os.path.join(_SKILLS, name, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


# NOTE: Both test functions below are STRUCTURAL string-presence checks only.
# They verify the required substrings exist somewhere in the skill file, but do NOT
# verify correct placement or gating of the snippet (e.g. that Snippet R is inside
# the `if [ "$LOCATION" = "none" ]` block, or that Snippet N is in the resolver block).
@pytest.mark.parametrize("name", ASK_RECORD_SKILLS)
def test_ask_branch_records_greenfield_pick(name):
    body = _skill(name)
    assert "mode_reconcile.py" in body and "reconcile --mode" in body, \
        f"{name} must record the greenfield pick via mode_reconcile reconcile --mode (FR-3)"


@pytest.mark.parametrize("name", NUDGE_SKILLS)
def test_run_surfaces_coalesced_nudge(name):
    body = _skill(name)
    assert "mode_reconcile.py" in body and "signals" in body, \
        f"{name} must surface the coalesced reconcile nudge via mode_reconcile signals (FR-7/8)"
