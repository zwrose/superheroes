"""#2431 WO-2: every doctrine surface that could re-take a refused act cites the session-wide refusal
rule's one home by name and never copies the rule's text.
"""
import os

import pytest

import command_refusals as CR

_PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_DOCTRINE = {
    "workhorse-skill": "skills/workhorse/SKILL.md",
    "orders": "skills/workhorse/reference/orders.md",
    "dispatch-mechanics": "skills/workhorse/reference/dispatch-mechanics.md",
    "vetting": "skills/showrunner/reference/vetting.md",
    "vet-receipt": "skills/showrunner/reference/vet-receipt.md",
    "auto-fix-loop": "skills/review-code/reference/auto-fix-loop.md",
    "check-runner": "agents/check-runner.md",
}


def _body(relpath):
    with open(os.path.join(_PLUGIN_ROOT, *relpath.split("/")), encoding="utf-8") as fh:
        return " ".join(fh.read().split())


@pytest.mark.parametrize("relpath", list(_DOCTRINE.values()), ids=list(_DOCTRINE))
def test_doctrine_cites_the_session_rule(relpath):
    body = _body(relpath)
    # axis: the cite census — the surface names the rule's one home — see bite-proof record wo2_2431_doctrine_cites
    assert "lib/command_refusals.py" in body
    assert "SANCTIONED_RETRIES" in body or "SESSION_RULE" in body
    # axis: the no-copy guard — a cite, never a copy of the rule — see bite-proof record wo2_2431_doctrine_cites
    assert " ".join(CR.SESSION_RULE_HEAD.split()) not in body
    assert " ".join(CR.SESSION_RULE_TAIL.split()) not in body


@pytest.mark.parametrize(
    "relpath",
    ["skills/workhorse/SKILL.md", "skills/showrunner/reference/vetting.md"],
    ids=["workhorse-skill", "vetting"],
)
def test_workhorse_and_vet_doctrine_say_the_same(relpath):
    body = _body(relpath)
    # axis: same-say guard — workhorse duty 8 and the vet doctrine state the same list and entry rule
    # — see bite-proof record wo2_2431_doctrine_cites
    assert "SANCTIONED_RETRIES" in body
    assert "owner's word with its field sightings" in body
