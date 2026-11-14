"""A finding this session kept as a repeat follows its earlier finding's current outcome in the same record.

When the earlier finding reads fixed (in the session, or moved there at write time by a carried check that holds),
the repeat is decided by the one keep-or-new table on this session's own grade verdict of the repeat, which the
session writer stamps into the repeat's `repeatOf.kept` (T8, T9): `wrong` moves it to fixed with `fixHolds` true; any
other verdict keeps its own outcome and its owner card. In every other case nothing changes.

Edges: E1 earlier finding still left-for-owner · E2 earlier finding open · E3 earlier finding a ruling or craft · E4 the
earlier finding's carried check did not hold · E5 earlier finding not in the record · E6 the repeat's outcome is no
longer the kept one · E7 the repeat carries a decidedBy · E8 a carried check names the repeat · E9 no `kept` mark ·
E10 verdict confirmed, plausible or none · E11 the grade says wrong but the kept verdict is none · E12 a malformed
`kept` is refused · E13 the repeat already reads fixed.
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

from test_review_record_carried_recheck import PRIOR, X, X_KEY, account, entry, readers  # noqa: E402
from test_review_record_session import KEY, THIRD, ledger_row  # noqa: E402

OLD = "repeat of f-1; keeps its earlier outcome (left-for-owner)"
LFO = "left-for-owner"
X_FIXED = dict(X, outcome="fixed", reason="fixed in 1a2b3c4")


def mark(**over):
    return {"findingKey": X_KEY, "id": "f-1", "fixHolds": None, **over}


def kept(outcome=LFO, verdict="wrong"):
    return {"outcome": outcome, "verdict": verdict}


def repeat(outcome=LFO, verdict="wrong", fid="f-2", title="Same mistake again", line=12, of=X_KEY, **over):
    """A kept repeat of X (a different title and line, so a different stored key)."""
    return {**X, "id": fid, "title": title, "line": line, "outcome": outcome, "reason": OLD,
            "repeatOf": mark(findingKey=of, kept=kept(outcome, verdict)), **over}


def build(findings, checks=(), prior=PRIOR, **kw):
    return rr.build_record(account(list(checks), findings), readers(**kw), prior=prior)


def by_id(rec):
    return {f["id"]: f for f in rec["findings"]}


def touched(reason):
    """True when the follow wrote its text into ``reason``."""
    return any(text.format(name=name, verdict=v) in reason for text in (rr.REPEAT_FOLLOWS_FIXED, rr.REPEAT_KEEPS_OWN)
               for name in ("f-1", "f-2") for v in (*rr.GRADE_VERDICTS, "none"))


# --- the follow moves a wrong-graded kept repeat once its earlier finding reads fixed ---

def test_t1_a_carried_fixed_check_on_the_earlier_finding_moves_its_wrong_graded_kept_repeat():
    # axis: the field case, a repeat raised in the returning session follows the carried earlier finding a fixed check moved
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    assert rr._key(repeat()) != X_KEY
    rec = build([X, repeat()], [entry()])
    rows = by_id(rec)
    assert rows["f-1"]["outcome"] == "fixed"
    r = rows["f-2"]
    assert r["outcome"] == "fixed"
    assert r["reason"] == rr.REPEAT_FOLLOWS_FIXED.format(name="f-1") + "; earlier: " + OLD
    assert r["repeatOf"]["fixHolds"] is True
    assert r["repeatOf"][rr.REPEAT_KEPT_FIELD] == {"outcome": "fixed", "verdict": "wrong"}
    assert rec["leftForOwner"] == []
    assert rec["status"] != rr.AWAITS_OWNER
    assert rr.leftover_line(r) not in str(rec["whatIsMissing"])
    assert [row["result"] for row in rec["carriedRechecks"]] == ["fixed"]


def test_t1_control_without_the_fixed_check_the_repeat_stays_left_for_the_owner_and_held():
    # axis: the control of the field case, the earlier finding still left for the owner holds the repeat's card
    rec = build([X, repeat()], [])
    rows = by_id(rec)
    assert (rows["f-1"]["outcome"], rows["f-2"]["outcome"]) == (LFO, LFO)
    assert rows["f-2"]["reason"] == OLD
    assert rec["leftForOwner"] == ["f-1"]


def test_t2_an_earlier_finding_fixed_in_the_session_moves_its_wrong_graded_kept_repeat():
    # axis: the earlier finding needs no carried check, a fixed outcome of this account is enough
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    rec = build([X_FIXED, repeat()])
    r = by_id(rec)["f-2"]
    assert r["outcome"] == "fixed"
    assert r["reason"] == rr.REPEAT_FOLLOWS_FIXED.format(name="f-1") + "; earlier: " + OLD
    assert r["repeatOf"]["fixHolds"] is True and r["repeatOf"]["kept"] == kept("fixed", "wrong")
    assert rec["leftForOwner"] == []


def test_t2_the_input_findings_are_never_changed():
    # axis: the follow returns new findings and leaves the supplied dicts as they were
    findings = [X_FIXED, repeat()]
    before = copy.deepcopy(findings)
    rr._follow_repeats(findings, [])
    assert findings == before


# --- E10: another verdict keeps the repeat's own outcome and its owner card ---

@pytest.mark.parametrize("verdict", [
    pytest.param("confirmed", id="confirmed"),
    pytest.param("plausible", id="plausible"),
    pytest.param(None, id="none"),
])
def test_t3_e10_a_verdict_that_is_not_wrong_keeps_the_repeats_own_outcome_and_its_card(verdict):
    # axis: only a wrong verdict moves the repeat; any other verdict, or none, keeps the outcome and the owner card
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    rec = build([X_FIXED, repeat(verdict=verdict)])
    r = by_id(rec)["f-2"]
    assert r["outcome"] == LFO
    shown = verdict if verdict is not None else "none"
    assert r["reason"] == rr.REPEAT_KEEPS_OWN.format(name="f-1", verdict=shown) + "; earlier: " + OLD
    assert r["repeatOf"]["fixHolds"] is None and r["repeatOf"]["kept"] == kept(LFO, verdict)
    assert "f-2" in rec["leftForOwner"]


# --- E1 to E5: the earlier finding does not read fixed ---

@pytest.mark.parametrize("earlier, checks, kw, cards", [
    pytest.param(X, [], {}, ["f-1"], id="E1-earlier-still-left-for-owner"),
    pytest.param(dict(X, outcome=None, reason="still open"), [], {}, ["f-2"], id="E2-earlier-open"),
    pytest.param(dict(X, outcome="craft", reason="a craft call"), [], {}, ["f-2"], id="E3-earlier-craft"),
    pytest.param(dict(X, outcome="ruling", reason="the owner ruled it out of scope"), [], {}, ["f-2"],
                 id="E3-earlier-ruling"),
    pytest.param(X, [entry(settled="applies")], {}, ["f-1"], id="E4-check-applies"),
    pytest.param(X, [entry(settled="unsettled")], {}, ["f-1"], id="E4-check-unsettled"),
    pytest.param(X, [entry(checkedHead=THIRD)], {}, ["f-1"], id="E4-check-on-another-head"),
    pytest.param(X, [entry()], {"ancestor": False}, ["f-1"], id="E4-fix-not-in-history"),
    pytest.param(None, [], {}, ["f-2"], id="E5-earlier-not-in-the-record"),
])
def test_t4_e1_to_e5_a_repeat_whose_earlier_finding_does_not_read_fixed_is_unchanged(earlier, checks, kw, cards):
    # axis: the follow runs only when the earlier finding reads fixed in this record; every other case leaves the repeat and its card
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    given = repeat()
    rec = build([given] if earlier is None else [earlier, given], checks, **kw)
    r = by_id(rec)["f-2"]
    assert (r["outcome"], r["reason"], r["repeatOf"]) == (LFO, OLD, given["repeatOf"])
    assert rec["leftForOwner"] == cards


# --- E6 to E9, E11: the repeat is not eligible ---

APPLIES = entry(key="f-2", settled="applies", commit=None, checkedHead=None, evidence="still reads past the end")


@pytest.mark.parametrize("over, checks", [
    pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept(LFO, "wrong"))), [], id="E6-outcome-is-no-longer-the-kept-one"),
    pytest.param(dict(outcome="craft", repeatOf=mark(kept=kept("craft", "wrong")),
                      decidedBy={"kind": "canon", "ref": "c1"}), [], id="E7-carries-a-decidedBy"),
    pytest.param({}, [APPLIES], id="E8-a-carried-check-names-the-repeat"),
    pytest.param(dict(repeatOf=mark()), [], id="E9-no-kept-mark"),
])
def test_t5_e6_to_e9_an_ineligible_repeat_is_left_as_the_follow_found_it(over, checks):
    # axis: only a repeat still at its kept outcome, with no cited decision, no carried check naming it and a kept mark is read
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    given = repeat(**over)
    rec = build([X_FIXED, given], checks)
    r = by_id(rec)["f-2"]
    assert r["outcome"] == given["outcome"]
    assert r["reason"].startswith(OLD) and not touched(r["reason"])
    assert r["repeatOf"] == given["repeatOf"]


def test_t5_e11_the_verdict_is_read_from_the_kept_mark_never_from_the_grade():
    # axis: the repeat's own grade is not read at write time; a wrong grade beside a kept verdict of none keeps the outcome
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    given = repeat(verdict=None, grade={"verdict": "wrong", "reason": "the cited line does not exist"})
    rec = build([X_FIXED, given])
    r = by_id(rec)["f-2"]
    assert r["outcome"] == LFO
    assert r["reason"] == rr.REPEAT_KEEPS_OWN.format(name="f-1", verdict="none") + "; earlier: " + OLD
    assert "f-2" in rec["leftForOwner"]


def test_t5_e13_a_repeat_that_already_reads_fixed_keeps_its_reason():
    # axis: a repeat already at fixed has nothing to follow, so its reason is not rewritten
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    given = repeat("fixed", reason="repeat of f-1; keeps its earlier outcome (fixed); the verifier found the fix still holds")
    rec = build([X_FIXED, given])
    r = by_id(rec)["f-2"]
    assert r["outcome"] == "fixed" and r["reason"] == given["reason"] and r["repeatOf"] == given["repeatOf"]


# --- chains and rings ---

def test_t6_a_chain_of_kept_repeats_settles_to_a_fixed_point():
    # axis: a repeat of a repeat of a fixed finding follows once the repeat it repeats has moved, whatever their order
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    first = repeat(fid="f-2", title="Same mistake again", line=12)
    second = repeat(fid="f-3", title="Third sighting", line=15, of=rr._key(first))
    rec = build([X_FIXED, second, first])
    rows = by_id(rec)
    assert (rows["f-2"]["outcome"], rows["f-3"]["outcome"]) == ("fixed", "fixed")
    assert rows["f-2"]["reason"] == rr.REPEAT_FOLLOWS_FIXED.format(name="f-1") + "; earlier: " + OLD
    assert rows["f-3"]["reason"] == rr.REPEAT_FOLLOWS_FIXED.format(name="f-2") + "; earlier: " + OLD
    assert rec["leftForOwner"] == []


def test_t6_a_ring_of_kept_repeats_with_no_fixed_member_changes_nothing():
    # axis: a ring of repeats has no fixed earlier finding, so no member moves and none loses its card
    one = repeat(fid="f-2", title="One", line=12)
    two = repeat(fid="f-3", title="Two", line=15, of=rr._key(one))
    one = dict(one, repeatOf=dict(one["repeatOf"], findingKey=rr._key(two)))
    rec = build([one, two])
    rows = by_id(rec)
    assert [(rows[i]["outcome"], rows[i]["reason"], rows[i]["repeatOf"]) for i in ("f-2", "f-3")] == \
        [(LFO, OLD, one["repeatOf"]), (LFO, OLD, two["repeatOf"])]
    assert sorted(rec["leftForOwner"]) == ["f-2", "f-3"]


# --- E12: the validation of the kept mark ---

@pytest.mark.parametrize("bad", [
    pytest.param("fixed", id="not-an-object"),
    pytest.param(None, id="null"),
    pytest.param({"outcome": "wontfix", "verdict": None}, id="outcome-outside-the-vocabulary"),
    pytest.param({"verdict": "wrong"}, id="no-outcome"),
    pytest.param({"outcome": "fixed", "verdict": "maybe"}, id="verdict-outside-the-grade-vocabulary"),
    pytest.param({"outcome": "fixed", "verdict": 3}, id="verdict-not-text"),
])
def test_t7_e12_a_malformed_kept_mark_is_refused_naming_it(bad):
    # axis: the kept mark is validated as an outcome of the vocabulary and a grade verdict or none
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    given = repeat()
    given["repeatOf"][rr.REPEAT_KEPT_FIELD] = bad
    with pytest.raises(rr.Refusal) as caught:
        build([X, given])
    assert (caught.value.reason, caught.value.detail) == ("review-account-invalid", "findings[1].repeatOf.kept")


def test_t7_a_valid_kept_mark_with_a_none_verdict_and_an_absent_one_are_not_faults():
    # axis: none is a valid verdict, and a record written before the mark has no kept key at all
    assert rr._repeat_fault(mark(kept=kept("fixed", None))) is None
    assert rr._repeat_fault(mark()) is None
    assert all(rr._repeat_fault(mark(kept=kept(o, v))) is None for o in rr.rfs.OUTCOMES for v in (None, *rr.GRADE_VERDICTS))


# --- the session writer stamps the kept mark from its own decision only ---

OTHER_KEY = "b.py::u@L9"
GRADE = {"verdict": "wrong", "reason": "the cited line does not exist"}
KEPT_ROW = {"outcome": LFO, "reason": OLD}


def kept_row(key=OTHER_KEY, **over):
    return ledger_row(key, **{"id": "f-2", "title": "u", "file": "b.py", "line": 9, "consequence": "c", "disposition": LFO,
                              "settledReason": "needs owner", "repeatOf": {"findingKey": KEY, "id": "f-1", "fixHolds": None},
                              "repeatKept": KEPT_ROW, **over})


def written(*ledger):
    """The session writer's findings for a driver state holding ``ledger``, by raw finding key."""
    found, merged = rs._findings_and_merges({"findings": [], "dispositionLedger": list(ledger), "rounds": {}})
    return {f["findingKey"]: f for f in found}, merged


@pytest.mark.parametrize("grade, verdict", [
    pytest.param(GRADE, "wrong", id="wrong"),
    pytest.param({"verdict": "plausible", "reason": "could not show it"}, "plausible", id="plausible"),
    pytest.param(None, None, id="no-grade"),
])
def test_t8_a_row_with_its_own_valid_repeat_kept_is_stamped_with_the_outcome_and_its_own_verdict(grade, verdict):
    # axis: the kept mark is stamped from the row's own decision, with the row's own grade verdict or none
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    ledger = kept_row(**({"grade": grade} if grade else {}))
    found, _ = written(ledger)
    assert found[OTHER_KEY]["outcome"] == LFO
    assert found[OTHER_KEY]["repeatOf"] == {**rs._stored_repeat(ledger["repeatOf"]),
                                            rr.REPEAT_KEPT_FIELD: {"outcome": LFO, "verdict": verdict}}
    assert rr.REPEAT_KEPT_FIELD not in ledger["repeatOf"]  # the ledger row's own mark is never changed


@pytest.mark.parametrize("over", [
    pytest.param({"repeatKept": None}, id="no-repeat-kept"),
    pytest.param({"repeatKept": {"outcome": LFO, "reason": ""}}, id="invalid-repeat-kept"),
])
def test_t8_a_stale_kept_in_the_ledger_marks_is_dropped_when_the_row_has_no_valid_repeat_kept(over):
    # axis: a kept mark the ledger row already carries is not trusted; only this session's own decision writes it
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    stale = {"findingKey": KEY, "id": "f-1", "fixHolds": None, "kept": {"outcome": "fixed", "verdict": "wrong"}}
    found, _ = written(kept_row(repeatOf=stale, **over))
    assert found[OTHER_KEY]["repeatOf"] == {"findingKey": rr._key({"findingKey": KEY}), "id": "f-1", "fixHolds": None}
    assert stale[rr.REPEAT_KEPT_FIELD] == {"outcome": "fixed", "verdict": "wrong"}  # the supplied mark is never changed


def test_t8_a_merged_member_of_a_kept_repeat_gets_no_kept_mark():
    # axis: the mark is stamped only on a finding that is its own representative, never on a member merged into one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    member = ledger_row("m::t@L1", id="m-1", title="m", file="m.py", line=1, consequence="c", disposition=None,
                        mergedInto=OTHER_KEY, repeatOf={"findingKey": KEY, "id": "f-1", "fixHolds": None})
    found, merged = written(kept_row(), member)
    assert merged == {"m::t@L1": OTHER_KEY}
    assert found[OTHER_KEY]["repeatOf"][rr.REPEAT_KEPT_FIELD] == {"outcome": LFO, "verdict": None}
    assert found["m::t@L1"]["outcome"] == LFO
    assert rr.REPEAT_KEPT_FIELD not in found["m::t@L1"]["repeatOf"]


# --- the kept mark never crosses records ---

def kept_finding():
    return {"findingKey": rr._key({"findingKey": KEY}), "id": "f-2", "reason": "waits",
            "repeatOf": mark(findingKey=OTHER_KEY, kept=kept("fixed", "wrong"))}


def test_t9_fill_copies_the_earlier_records_repeat_without_its_kept_mark():
    # axis: the earlier record's kept mark is not carried into the current finding; it is the current session's own decision's alone
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    earlier = kept_finding()
    before = copy.deepcopy(earlier)
    acct = {"findings": [{"findingKey": earlier["findingKey"]}]}
    rs._fill(acct, [earlier])
    assert acct["findings"][0]["repeatOf"] == mark(findingKey=rr._key({"findingKey": OTHER_KEY}))
    assert earlier == before


def test_t9_carried_copies_an_earlier_finding_without_its_kept_mark_and_leaves_the_earlier_one_alone():
    # axis: a finding carried from the earlier record does not bring its kept mark into this record
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2438_repeat_follows.md
    earlier = kept_finding()
    before = copy.deepcopy(earlier)
    (copied,) = rs._carried({"findings": []}, [earlier])
    assert copied["repeatOf"] == mark(findingKey=OTHER_KEY)
    assert copied["reason"] == "waits" + rs.CARRIED
    assert earlier == before
