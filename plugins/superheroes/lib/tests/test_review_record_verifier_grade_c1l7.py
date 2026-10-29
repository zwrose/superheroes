"""#2211 (C1-L7): the review record closes a finding as wrong only on the verifier's grade.

A finding reads `shown-wrong` only when the driver's verifier fold closed it in this session (its ledger row, or the
row of the representative it was merged into, is `refuted` and carries the grade `{"verdict": "wrong", ...}`) or the
latest earlier record on the PR already lists that finding shown-wrong (a carry). The session reader returns the open
outcome for a refuted row without the wrong grade, and the writer refuses a shown-wrong finding that is neither.

Edges: E1 a grade that is not a dict, or whose verdict is not exactly "wrong", closes nothing · E2 a merged-member chain
that does not resolve stays open · E3 no earlier record, no carry · E4 an earlier finding without a key, or a malformed
findings list, carries nothing · E5 a set key whose own grade is not wrong is refused unless the carry accepts it ·
E6 an absent set closes nothing new.
"""
import pytest

import review_record as rr
import review_record_session as rs
from test_review_record import WRONG, Fake, account, closed, finding, put, wrong
from test_review_record_session import KEY, Fake as SessionFake, Session, extras, ledger_row, put_extras

REFUSAL = "findings[0] is shown-wrong without the verifier's grade"
PLAUSIBLE = {"verdict": "plausible", "reason": "the verifier could not settle it"}
REFUTED = dict(disposition="refuted", refutedReason="the cited line does not exist")


def decide(row, *others):
    by_key = {r["findingKey"]: r for r in (row, *others)}
    return rs._decide(row, by_key, {})[:2]


# --- `_decide`: the session reader ---------------------------------------------------------------------------------

def test_a_refuted_row_with_the_wrong_grade_reads_shown_wrong():
    # axis: G1 the wrong-grade condition; a refuted row with the verifier's wrong grade is the one that closes a finding
    assert decide(ledger_row(**REFUTED, grade=WRONG)) == ("shown-wrong", "the cited line does not exist")


def test_a_refuted_row_with_no_grade_reads_open():
    # axis: G1 the wrong-grade condition; the refuted disposition alone closes nothing
    assert decide(ledger_row(**REFUTED)) == (None, rs.REFUTED_UNGRADED)
    assert rs.REFUTED_UNGRADED == "refuted without the verifier's wrong grade; still open"


@pytest.mark.parametrize("grade", [
    pytest.param(PLAUSIBLE, id="plausible"),
    pytest.param({"verdict": "confirmed", "reason": "reproduced"}, id="confirmed"),
    pytest.param({"verdict": "Wrong", "reason": "r"}, id="verdict-spelled-otherwise"),
    pytest.param({"reason": "r"}, id="no-verdict"),
    pytest.param("wrong", id="a-bare-string"),
    pytest.param(["wrong"], id="a-list"),
    pytest.param(None, id="null"),
])
def test_a_refuted_row_whose_grade_is_not_the_wrong_verdict_reads_open(grade):
    # axis: E1 a grade that is not a dict, or whose verdict is not exactly "wrong", closes nothing
    assert decide(ledger_row(**REFUTED, grade=grade)) == (None, rs.REFUTED_UNGRADED)


def test_an_author_justified_refuted_row_still_reads_left_for_owner():
    row = ledger_row(disposition="refuted", refutedReason="author-justified: kept on purpose")
    assert decide(row) == ("left-for-owner", "author-justified: kept on purpose")
    # the gate comes before the justification, as the order names: a wrong grade is the verifier's close
    assert decide(dict(row, grade=WRONG)) == ("shown-wrong", "author-justified: kept on purpose")


def test_a_merged_member_reads_its_representatives_grade_not_its_own():
    member = ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto=KEY, grade=WRONG)
    rep = ledger_row(KEY, id="rep-1", **REFUTED, grade=PLAUSIBLE)
    # bites on: a member's own wrong grade closing it while its representative was never shown wrong
    assert decide(member, rep) == (None, rs.REFUTED_UNGRADED)


def test_a_merged_member_whose_chain_does_not_resolve_stays_open():
    # E2: the representative the member names is not in the ledger
    member = ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto="gone::t@L9", grade=WRONG)
    assert decide(member) == (None, rs.STILL_OPEN)


# --- the session reader's account ----------------------------------------------------------------------------------

def merged_ledger(member_grade=PLAUSIBLE, rep_grade=WRONG):
    member = ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto=KEY, grade=member_grade)
    rep = ledger_row(KEY, id="rep-1", **REFUTED, grade=rep_grade)
    return [member, rep]


def account_findings(tmp_path, ledger):
    s = Session(tmp_path, dispositionLedger=ledger).seat("code-reviewer")
    return {f["findingKey"]: f for f in rs.account_from_session(s.save(), extras(), SessionFake().readers())["findings"]}


def test_a_merged_member_emits_the_closing_representatives_wrong_grade(tmp_path):
    found = account_findings(tmp_path, merged_ledger())
    member, rep = found["m::t@L1"], found[KEY]
    # axis: G4 the merged member's emitted closing grade is the representative's, whatever grade the member holds
    assert (member["outcome"], member["grade"]) == ("shown-wrong", WRONG)
    assert (rep["outcome"], rep["grade"]) == ("shown-wrong", WRONG)


def test_a_merged_member_with_no_grade_of_its_own_emits_the_representatives(tmp_path):
    member = ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto=KEY)
    found = account_findings(tmp_path, [member, ledger_row(KEY, id="rep-1", **REFUTED, grade=WRONG)])
    assert found["m::t@L1"]["grade"] == WRONG


def test_a_finding_that_stays_open_keeps_the_grade_it_holds(tmp_path):
    found = account_findings(tmp_path, [ledger_row(**REFUTED, grade=PLAUSIBLE)])
    assert (found[KEY]["outcome"], found[KEY]["grade"]) == (None, PLAUSIBLE)


# --- `review_record.write`: the writer gate ------------------------------------------------------------------------

def write(tmp_path, fake, findings, **kw):
    return rr.write(put(tmp_path, account(findings=findings)), str(tmp_path), fake.readers(), **kw)


def test_a_direct_account_with_a_shown_wrong_finding_and_no_grade_is_refused(tmp_path):
    fake = Fake()
    out = write(tmp_path, fake, [finding("a-1", outcome="shown-wrong", reason="not a bug")])
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", REFUSAL)
    assert fake.comments == []


def test_a_direct_account_with_a_forged_wrong_grade_is_refused(tmp_path):
    fake = Fake()
    forged = wrong("a-1", reason="not a bug")
    out = write(tmp_path, fake, [forged])
    # axis: G2 the writer gate; a well-formed wrong grade the driver never set is not the verifier's close
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", REFUSAL)
    assert fake.comments == []
    out = write(tmp_path, fake, [forged], verifier_closed=set())
    assert (out["ok"], out["detail"]) == (False, REFUSAL) and fake.comments == []


def test_the_refusal_names_the_finding_by_its_place_in_the_account(tmp_path):
    out = write(tmp_path, Fake(), [finding("a-1"), wrong("a-2")])
    assert out["detail"] == "findings[1] is shown-wrong without the verifier's grade"


def test_a_finding_in_the_set_is_accepted_with_the_wrong_grade(tmp_path):
    fake = Fake()
    shown = wrong("a-1", reason="not a bug")
    out = write(tmp_path, fake, [shown], verifier_closed=closed(shown))
    assert out["ok"], out
    stored = rr.read(7, readers=fake.readers())["findings"][0]
    assert (stored["outcome"], stored["grade"]) == ("shown-wrong", WRONG)


@pytest.mark.parametrize("grade", [PLAUSIBLE, {"verdict": "confirmed", "reason": "r"}, "wrong", None])
def test_a_finding_in_the_set_whose_own_grade_is_not_wrong_is_refused(tmp_path, grade):
    # E5
    fake = Fake()
    shown = finding("a-1", outcome="shown-wrong", reason="r", **({} if grade is None else {"grade": grade}))
    out = rr.write(put(tmp_path, account(findings=[shown])), str(tmp_path), fake.readers(), verifier_closed=closed(shown))
    # a malformed grade is refused by the account's own validation, a well-formed one by the gate
    assert (out["ok"], out["reason"]) == (False, "review-account-invalid")
    assert fake.comments == []


def test_a_wrong_grade_on_another_finding_does_not_close_this_one(tmp_path):
    fake = Fake()
    graded, bare = wrong("a-1", title="one"), finding("a-2", title="two", outcome="shown-wrong", reason="r")
    out = write(tmp_path, fake, [graded, bare], verifier_closed=closed(graded))
    assert (out["ok"], out["detail"]) == (False, "findings[1] is shown-wrong without the verifier's grade")


@pytest.mark.parametrize("grade", [WRONG, None, PLAUSIBLE])
def test_a_finding_the_latest_earlier_record_lists_shown_wrong_is_carried(tmp_path, grade):
    # axis: G3 the carry exception; an outcome the earlier record already stored stands whatever this account's grade says
    fake = Fake()
    first = wrong("a-1", reason="not a bug")
    assert write(tmp_path, fake, [first], verifier_closed=closed(first))["ok"]
    again = finding("a-1", outcome="shown-wrong", reason="not a bug", **({} if grade is None else {"grade": grade}))
    out = write(tmp_path, fake, [again])
    assert out["ok"], out
    assert len(fake.marked()) == 2


def test_the_carry_covers_only_the_finding_the_earlier_record_lists(tmp_path):
    fake = Fake()
    first = wrong("a-1", title="one")
    assert write(tmp_path, fake, [first], verifier_closed=closed(first))["ok"]
    other = finding("a-2", title="two", outcome="shown-wrong", reason="r")
    out = write(tmp_path, fake, [first, other])
    assert (out["ok"], out["detail"]) == (False, "findings[1] is shown-wrong without the verifier's grade")


def test_a_finding_the_earlier_record_listed_with_another_outcome_is_not_carried(tmp_path):
    fake = Fake()
    assert write(tmp_path, fake, [finding("a-1", outcome="left-for-owner", reason="owner call")])["ok"]
    out = write(tmp_path, fake, [finding("a-1", outcome="shown-wrong", reason="r", grade=WRONG)])
    assert (out["ok"], out["detail"]) == (False, REFUSAL)


def test_with_no_earlier_record_nothing_is_carried(tmp_path):
    # E3
    out = write(tmp_path, Fake(), [finding("a-1", outcome="shown-wrong", reason="r")])
    assert (out["ok"], out["detail"]) == (False, REFUSAL)


@pytest.mark.parametrize("earlier", [
    pytest.param([{"outcome": "shown-wrong", "reason": "r"}], id="no-key"),
    pytest.param([None, "x"], id="not-objects"),
    pytest.param("x", id="not-a-list"),
])
def test_an_earlier_record_without_usable_findings_carries_nothing(earlier):
    # E4: the helper reads the prior directly; the writer's own refusal for a malformed list stands apart
    shown = wrong("a-1")
    assert rr._wrong_ungraded([shown], {"findings": earlier}, closed()) == [0]
    assert rr._wrong_ungraded([shown], None, closed()) == [0]


def test_an_absent_set_closes_nothing_new():
    # E6
    shown = wrong("a-1")
    assert rr._wrong_ungraded([shown], None, frozenset()) == [0]
    assert rr._wrong_ungraded([shown], None, closed(shown)) == []
    assert rr.write.__defaults__[-1] == frozenset()


# --- the session writer ----------------------------------------------------------------------------------------------

def test_a_session_written_record_stores_a_verifier_closed_finding_shown_wrong_with_its_grade(tmp_path):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**REFUTED, grade=WRONG)]).seat("code-reviewer")
    fake = SessionFake()
    out = rs.write_from_session(s.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    (stored,) = rr.read(7, readers=fake.readers())["findings"]
    assert (stored["outcome"], stored["reason"], stored["grade"]) == ("shown-wrong", "the cited line does not exist", WRONG)


def test_a_session_written_record_stores_a_merged_group_closed_by_its_representative(tmp_path):
    # axis: G4 the merged member's emitted closing grade; the member's own plausible grade would be refused as no wrong grade
    s = Session(tmp_path, dispositionLedger=merged_ledger()).seat("code-reviewer")
    fake = SessionFake()
    out = rs.write_from_session(s.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    stored = {f["findingKey"]: f for f in rr.read(7, readers=fake.readers())["findings"]}
    assert {k: (f["outcome"], f["grade"]) for k, f in stored.items()} == {
        rr._key({"findingKey": k}): ("shown-wrong", WRONG) for k in ("m::t@L1", KEY)}


def test_a_session_whose_refuted_row_has_no_wrong_grade_leaves_the_finding_open(tmp_path):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**REFUTED)]).seat("code-reviewer")
    fake = SessionFake()
    out = rs.write_from_session(s.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    (stored,) = rr.read(7, readers=fake.readers())["findings"]
    assert (stored["outcome"], stored["reason"]) == (None, rs.REFUTED_UNGRADED)


def test_a_later_session_carries_the_shown_wrong_outcome_the_earlier_record_stored(tmp_path):
    # the carry in the session writer: the earlier record's row, not raised again, keeps its outcome and grade
    fake = SessionFake()
    first = Session(tmp_path, dispositionLedger=[ledger_row(**REFUTED, grade=WRONG)]).seat("code-reviewer")
    assert rs.write_from_session(first.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())["ok"]
    second_root = tmp_path / "second"
    second_root.mkdir()
    second = Session(second_root, dispositionLedger=[ledger_row("b.py::u@L9", id="f-2", file="b.py", title="u", line=9)])
    second.seat("code-reviewer")
    out = rs.write_from_session(second.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    stored = {f["findingKey"]: f for f in rr.read(7, readers=fake.readers())["findings"]}
    carried = [f for f in stored.values() if f["outcome"] == "shown-wrong"]
    assert len(carried) == 1 and carried[0]["grade"] == WRONG
