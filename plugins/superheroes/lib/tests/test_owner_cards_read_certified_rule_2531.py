"""Tests for #2531: the gardening pass's owner-card count and repeat suppression read the certified-review rule (#2493).

A card is a finding that reaches the owner as one (`review_record.waits_for_owner`): a Minor or Nit listed for the
merge verdict is no card, and a no-outcome Minor or Nit card (in a risk area, or of unknown risk) is one. A no-outcome
Minor card that repeats another card is held like a left-for-owner repeat.
"""
import datetime
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import review_measures as RM  # noqa: E402
import review_record as rr  # noqa: E402

D = datetime.date.fromisoformat
FROM, UNTIL = D("2026-10-28"), D("2026-11-11")
RELEASES = [{"version": "0.50.0", "since": "2026-10-20"}]
SEC = "security-reviewer (round 1)"


def _f(key, outcome="left-for-owner", severity="Minor", risk=True, **over):
    f = {"id": key, "findingKey": key, "outcome": outcome, "severity": severity, "inRiskArea": risk,
         "raisedBy": "security-reviewer"}
    if outcome is not None:
        f["reason"] = "why"
    f.update(over)
    return f


def _repeat(f, of):
    return dict(f, repeatOf={"findingKey": of, "id": of, "fixHolds": None})


def _rec(findings, status="awaits-owner", at="2026-11-01T10:00:00Z", session="s1"):
    return {"pr": 1, "sessionId": session, "writtenAt": at, "status": status, "rounds": {"count": 1},
            "reviewers": [{"name": SEC, "ran": "engine-record", "commit": "c1"}], "findings": list(findings)}


def _cards(findings):
    row = RM.compute({"records": [_rec(findings)], "releases": RELEASES, "mergedPrs": [1]}, FROM, UNTIL)
    assert RM.problems(row) == []
    return row["measures"]["ownerCardsPerMergedPr"]["byRelease"]["0.50.0"]["total"]


# --- the owner-card count --------------------------------------------------------------------------------------------

def test_a_listed_minor_left_for_the_owner_is_no_owner_card():
    # break-it: counting by `outcome == left-for-owner` alone counts this listed Minor, and the total reads 2
    assert _cards([_f("k1", risk=False), _f("k2", severity="Important")]) == 1


def test_a_listed_minor_with_no_outcome_is_no_owner_card():
    assert _cards([_f("k1", outcome=None, risk=False)]) == 0


@pytest.mark.parametrize("risk", [True, None], ids=["in-a-risk-area", "risk-unknown"])
def test_a_no_outcome_minor_card_is_an_owner_card(risk):
    # break-it: counting by `outcome == left-for-owner` alone misses this no-outcome card, and the total reads 0
    assert _cards([_f("k1", outcome=None, risk=risk)]) == 1


def test_a_no_outcome_important_is_a_missing_outcome_not_an_owner_card():
    assert _cards([_f("k1", outcome=None, severity="Important")]) == 0


def test_a_no_outcome_minor_card_repeating_another_card_is_not_counted_twice():
    # break-it: a repeat rule that holds only left-for-owner repeats counts the no-outcome repeat too, and the total reads 2
    assert _cards([_f("k1"), _repeat(_f("k2", outcome=None), "k1")]) == 1


# --- repeat suppression ----------------------------------------------------------------------------------------------

def test_a_no_outcome_minor_card_repeating_a_left_for_owner_card_is_held():
    holder, again = _f("k1"), _repeat(_f("k2", outcome=None), "k1")
    # break-it: requiring `outcome == left-for-owner` of the repeat leaves this card waiting, so the owner sees it twice
    assert rr.repeat_held_elsewhere(again, [holder, again]) is True
    assert [rr.waits_for_owner(f, [holder, again]) for f in (holder, again)] == [True, False]


def test_a_repeat_of_a_no_outcome_minor_card_is_held_by_it():
    holder, again = _f("k1", outcome=None), _repeat(_f("k2"), "k1")
    # break-it: a holder set of left-for-owner findings only misses this no-outcome holder, so both cards wait
    assert rr.repeat_held_elsewhere(again, [holder, again]) is True
    assert [rr.waits_for_owner(f, [holder, again]) for f in (holder, again)] == [True, False]


def test_a_no_outcome_important_holds_no_card_so_its_repeat_keeps_its_own():
    holder, again = _f("k1", outcome=None, severity="Important"), _repeat(_f("k2"), "k1")
    assert rr.repeat_held_elsewhere(again, [holder, again]) is False
    assert rr.waits_for_owner(again, [holder, again]) is True


def test_a_listed_repeat_holds_nothing_and_waits_for_nothing():
    holder, again = _f("k1"), _repeat(_f("k2", outcome=None, risk=False), "k1")
    assert rr.repeat_held_elsewhere(again, [holder, again]) is False
    assert rr.waits_for_owner(again, [holder, again]) is False


# --- the clean-loop and cap-choice readers ---------------------------------------------------------------------------

def test_a_listed_minor_leaves_a_reviewed_record_clean():
    # break-it: reading `outcome in (None, left-for-owner)` alone calls this certified record not clean
    assert RM._clean(_rec([_f("k1", risk=False), _f("k2", outcome=None, risk=False)], status="reviewed")) is True
    assert RM._clean(_rec([_f("k1")], status="reviewed")) is False
    assert RM._clean(_rec([_f("k1", outcome=None)], status="reviewed")) is False


def test_raised_by_constant_is_gone():
    assert not hasattr(RM, "RAISED_BY")
