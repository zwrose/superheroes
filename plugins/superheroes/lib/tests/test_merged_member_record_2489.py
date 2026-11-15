"""A finding merged into another reads fixed only on its own fix-audit ruling (the record side).

The review record's writer resolves a merged member through `mergedInto` and inherits its representative's outcome.
The one exception is `fixed`: the representative's row carries `memberResults` (the fix audit's answer for each member,
`[{"findingKey": <member>, "fixed": true|false}]`), and a member reads fixed only when `member_ruled_fixed` finds its
own true answer there. Where the representative reads fixed and the member has none, the member has no outcome
(`MERGED_MEMBER_UNAUDITED`), so the repeat pool and the carry treat it as open. Every other inherited outcome is
unchanged, and a kept repeat that moves to fixed no longer takes its merged members with it.

Edges: 1 member ruled fixed · 2 member ruled not fixed · 3 no `memberResults` · 4 another key only · 5 malformed ·
6 the member answered both ways · 7 a kept repeat reading fixed · 8 a full-panel-not-reraised representative ·
9 every non-fixed representative · 10 the representative itself · 11 an unresolvable chain · 12 the disposition family.
Each of 1-9 is read through `review_record_session._decide` and through the account.
"""
import itertools
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import repeat_marks  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import session_contract as sc  # noqa: E402

from test_review_record_carried_recheck import X  # noqa: E402
from test_review_record_repeat_follows_2438 import X_FIXED, build as build_2438, repeat  # noqa: E402
from test_review_record_repeat_follows_2438 import mark as mark_2438  # noqa: E402
from test_review_record_repeat_follows_ruling_2479 import (  # noqa: E402
    LFO, MEMBER_RAW as MEMBER_RAW_2479, WAS, build as build_ruling, by_id, member, member_repeat)
from test_review_record_session import KEY, WRONG, Session, extras, ledger_row  # noqa: E402

MK = "m::t@L1"  # the merged member's key
REP_REASON = "fixed and audited in round 2"
NOTE = "; the fix audit ruled this finding's own part fixed"
RESULTS = sc.MEMBER_RESULTS_FIELD


def ledger(rep_over=None, member_over=None):
    """A member row merged into a representative row (`rep-1`, KEY); the representative reads fixed unless overridden."""
    return [ledger_row(MK, id="m-1", disposition=None, mergedInto=KEY, **(member_over or {})),
            ledger_row(KEY, id="rep-1", **(rep_over or {}))]


def decide(rows):
    """`_decide` over a ledger: the member's (outcome, reason)."""
    by_key = {r["findingKey"]: r for r in rows}
    return rs._decide(by_key[MK], by_key, {})[:2]


def decide_rep(rows):
    by_key = {r["findingKey"]: r for r in rows}
    return rs._decide(by_key[KEY], by_key, {})[:2]


_SESSIONS = itertools.count()


def account_rows(tmp_path, rows):
    """The account's findings by key, from a session whose disposition ledger is ``rows`` (its own directory each call)."""
    root = tmp_path / f"s{next(_SESSIONS)}"
    root.mkdir()
    s = Session(root, dispositionLedger=rows)
    s.seat("code-reviewer")
    return {f["findingKey"]: f for f in rs.account_from_session(s.save(), extras())["findings"]}


def both(tmp_path, rows):
    """The member's (outcome, reason) read through `_decide` and through the account."""
    found = account_rows(tmp_path, rows)[MK]
    return decide(rows), (found["outcome"], found["reason"])


def said(fixed, key=MK):
    return {"findingKey": key, "fixed": fixed}


# --- edges 1-9: through `_decide` and through the account ---

def test_edge1_a_member_the_audit_ruled_fixed_reads_fixed_with_the_ruling_noted(tmp_path):
    # axis: the one row naming the member with fixed true is the member's own ruling, so it reads fixed
    rows = ledger({RESULTS: [said(True)]})
    via_decide, via_account = both(tmp_path, rows)
    assert via_decide == ("fixed", REP_REASON + NOTE)
    assert via_account == ("fixed", REP_REASON + NOTE + " (merged into rep-1)")


def test_edge2_a_member_the_audit_ruled_not_fixed_has_no_outcome(tmp_path):
    # axis: fixed false is the audit saying the member's own part was not fixed
    via_decide, via_account = both(tmp_path, ledger({RESULTS: [said(False)]}))
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")


def test_edge3_a_fixed_representative_with_no_member_results_leaves_its_member_without_an_outcome(tmp_path):
    # axis: the member gate; the representative reads fixed, the member must not inherit it without its own ruling
    rows = ledger()
    via_decide, via_account = both(tmp_path, rows)
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")
    assert decide_rep(rows) == ("fixed", REP_REASON)  # the representative itself still reads fixed
    assert account_rows(tmp_path, rows)[KEY]["outcome"] == "fixed"


def test_edge4_member_results_naming_another_key_only_rule_nothing_for_this_member(tmp_path):
    # axis: a row is the member's only when its findingKey is the member's own
    via_decide, via_account = both(tmp_path, ledger({RESULTS: [said(True, key="x::other@L9")]}))
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")


@pytest.mark.parametrize("results", [
    pytest.param({MK: True}, id="a-dict-not-a-list"),
    pytest.param("true", id="a-string"),
    pytest.param(True, id="a-bool"),
    pytest.param([MK, 3, None, ["findingKey", MK]], id="rows-not-dicts"),
    pytest.param([said("true")], id="fixed-a-string"),
    pytest.param([said(1)], id="fixed-a-number"),
    pytest.param([{"findingKey": MK}], id="fixed-absent"),
    pytest.param([{"fixed": True}], id="key-absent"),
])
def test_edge5_malformed_member_results_rule_nothing(tmp_path, results):
    # axis: only a list of dict rows with fixed exactly true rules a member fixed; every other shape reads as no ruling
    via_decide, via_account = both(tmp_path, ledger({RESULTS: results}))
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")


@pytest.mark.parametrize("answers", [[True, False], [False, True], [True, True, False]])
def test_edge6_a_member_answered_both_ways_is_not_ruled_fixed(tmp_path, answers):
    # axis: every answer for the member must be true; one false answer withdraws the ruling whatever its position
    via_decide, via_account = both(tmp_path, ledger({RESULTS: [said(a) for a in answers]}))
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")
    assert sc.member_ruled_fixed({RESULTS: [said(a) for a in answers]}, MK) is False


def test_edge7_a_member_of_a_kept_repeat_reading_fixed_has_no_outcome_while_the_repeat_reads_fixed(tmp_path):
    # axis: the kept-repeat return site is behind the same gate, so a member does not inherit a fixed kept repeat
    kept = {"outcome": "fixed", "reason": "repeat of f-1; keeps its earlier outcome (fixed)"}
    rows = ledger({"repeatKept": kept})
    via_decide, via_account = both(tmp_path, rows)
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")
    assert decide_rep(rows) == ("fixed", kept["reason"])
    assert account_rows(tmp_path, rows)[KEY]["outcome"] == "fixed"


def test_edge8_a_member_of_a_full_panel_not_reraised_representative_has_no_outcome(tmp_path):
    # axis: the full-panel return site is behind the same gate, so a member does not inherit that fixed reading
    receipt = {"kind": sc.FULL_PANEL_NOT_RERAISED, "panelRound": 3}
    rows = ledger({"dispositionReceipt": receipt})
    reason = "fixed; the full panel in round 3 did not raise it again"
    via_decide, via_account = both(tmp_path, rows)
    assert via_decide == (None, rs.MERGED_MEMBER_UNAUDITED)
    assert via_account == (None, rs.MERGED_MEMBER_UNAUDITED + " (merged into rep-1)")
    assert decide_rep(rows) == ("fixed", reason)
    # and ruled fixed by the audit, the member reads fixed with the representative's reason
    ruled = ledger({"dispositionReceipt": receipt, RESULTS: [said(True)]})
    assert decide(ruled) == ("fixed", reason + NOTE)


@pytest.mark.parametrize("rep_over, outcome, reason", [
    pytest.param({"disposition": "craft", "settledReason": "code quality only"}, "craft", "code quality only", id="craft"),
    pytest.param({"disposition": "left-for-owner", "settledReason": "only the owner can settle this"}, "left-for-owner",
                 "only the owner can settle this", id="left-for-owner"),
    pytest.param({"disposition": "ruling", "settledReason": "decided"}, "ruling", "decided", id="ruling"),
    pytest.param({"disposition": "refuted", "grade": WRONG, "refutedReason": "the cited line does not exist"},
                 "shown-wrong", "the cited line does not exist", id="shown-wrong"),
])
def test_edge9_a_member_inherits_every_representative_outcome_but_fixed_exactly_as_before(tmp_path, rep_over, outcome, reason):
    # axis: the gate touches only a fixed reading; every other inherited outcome and reason is the representative's own
    for results in (None, [said(False)], [said(True)]):  # the audit's answers change nothing here
        over = dict(rep_over, **({RESULTS: results} if results is not None else {}))
        via_decide, via_account = both(tmp_path, ledger(over))
        assert via_decide == (outcome, reason)
        assert via_account == (outcome, reason + " (merged into rep-1)")


# --- edges 10-12 ---

def test_edge10_the_representative_itself_reads_fixed_without_member_results(tmp_path):
    # axis: the gate applies to a row merged into another only, never to the representative reading its own disposition
    rows = ledger()
    assert decide_rep(rows) == ("fixed", REP_REASON)
    assert rs._decide(rows[1], {r["findingKey"]: r for r in rows}, {})[2] is rows[1]
    found = account_rows(tmp_path, rows)
    assert (found[KEY]["outcome"], found[KEY]["reason"]) == ("fixed", REP_REASON)


def test_edge10_a_row_standing_alone_with_a_fixed_disposition_still_reads_fixed():
    row = ledger_row()
    assert rs._decide(row, {KEY: row}, {})[:2] == ("fixed", REP_REASON)


def test_edge11_an_unresolvable_merge_chain_is_open_with_no_representative(tmp_path):
    # axis: no representative means no outcome, as before the gate existed
    rows = [ledger_row(MK, id="m-1", disposition=None, mergedInto="no::such@L1")]
    by_key = {r["findingKey"]: r for r in rows}
    assert rs._decide(by_key[MK], by_key, {}) == (None, rs.STILL_OPEN, None)
    found = account_rows(tmp_path, rows)[MK]
    assert (found["outcome"], found["reason"]) == (None, rs.STILL_OPEN)


def test_edge12_a_newer_disposition_a_strip_or_a_snapshot_carries_member_results_with_the_family():
    # axis: memberResults is a disposition-family field, so a newer disposition clears a stale one with the rest
    assert sc.MEMBER_RESULTS_FIELD == "memberResults"
    fields = sc.DISPOSITION_FAMILY_FIELDS
    assert fields[fields.index("placeResults") + 1] == RESULTS
    row = {"disposition": "left-for-owner", RESULTS: [said(True)], "id": "keep"}
    assert sc.disposition_family_snapshot(row)[RESULTS] == [said(True)]
    sc.apply_disposition_family(row, {"disposition": "fixed"})
    assert RESULTS not in row and row["disposition"] == "fixed" and row["id"] == "keep"
    assert RESULTS not in sc.strip_disposition_family({"disposition": "fixed", RESULTS: [said(True)]})
    assert "member_ruled_fixed" in sc.__all__ and "MEMBER_RESULTS_FIELD" in sc.__all__


@pytest.mark.parametrize("rep", [None, "rep", [], {}, {RESULTS: None}])
def test_member_ruled_fixed_is_false_for_every_input_that_is_not_a_fixed_answer(rep):
    assert sc.member_ruled_fixed(rep, MK) is False


def test_the_repeat_pool_treats_an_unaudited_member_as_open_and_an_audited_one_as_fixed():
    # axis: the pool reads the record writer's outcome, so a member with none is not pooled
    unaudited = ledger()
    audited = ledger({RESULTS: [said(True)]})
    for rows, pooled in ((unaudited, False), (audited, True)):
        state = {"dispositionLedger": [dict(r, raisedSeq=1, dispositionSeq=r.get("dispositionSeq", 4)) for r in rows]}
        keys = {e["key"] for e in repeat_marks.build_pool(state, 3, [])}  # the representative was decided in round 2
        assert KEY in keys  # the representative itself is pooled either way
        assert (MK in keys) is pooled


# --- the repeat-follows pass (review_record) ---

def test_repeat_follows_fixed_leaves_a_merged_member_at_its_own_outcome_and_the_ruling_branch_still_moves_it():
    # axis: a member of a kept repeat that moves to fixed keeps its own outcome; the ruling branch still moves members
    given = repeat(repeatOf=mark_2438(kept={"outcome": LFO, "verdict": "wrong", "members": [MEMBER_RAW_2479]}))
    rec = build_2438([X_FIXED, given, member()])
    rows = by_id(rec)
    assert rows["f-2"]["outcome"] == "fixed" and rows["f-2"]["repeatOf"]["fixHolds"] is True  # the repeat itself follows
    assert rows["f-3"]["outcome"] == LFO and rows["f-3"]["reason"] == WAS  # the member is untouched
    ruled = by_id(build_ruling([X, member_repeat(), member()]))
    assert (ruled["f-2"]["outcome"], ruled["f-3"]["outcome"]) == ("ruling", "ruling")  # the ruling branch is unchanged
    assert rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") in ruled["f-3"]["reason"]
