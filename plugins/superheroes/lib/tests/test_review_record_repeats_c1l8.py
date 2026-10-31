"""The review record shows each repeat's mark, and a kept repeat reads its earlier outcome and adds no owner card.

A kept repeat is a ledger row carrying `repeatKept`; its outcome and reason become the record finding's, whatever its own
disposition says (J1). Its `repeatOf` names the earlier finding by the stored key (J2). A left-for-owner repeat whose
earlier finding is left for the owner in the same record is held there: no leftover line, no `leftForOwner` entry, no
sheet card (J3). A kept shown-wrong repeat passes the shown-wrong gate through the earlier finding's closure (J4), and
the repeat and the earlier finding are both written (J5).

Edges: E1 a `repeatOf` that is not an object, or names no key, holds nothing and admits nothing · E2 a `repeatKept` with
an outcome outside the vocabulary or an empty reason is ignored · E3 a left-for-owner repeat whose earlier finding is
not in the record keeps its card · E4 an earlier record that cannot be read admits nothing through the carry.
"""
import copy

import pytest

import review_findings_schema as rfs
import review_record as rr
import review_record_session as rs
from test_pr_sheet import BIG, bundle, build as sheet_build, leftover_cards, problems_of
from test_review_record import WRONG, Fake, account, build, closed, finding, put, wrong
from test_review_record_awaits_owner_2136 import Clean
from test_review_record_session import KEY, Fake as SessionFake, Session, extras, ledger_row, put_extras

LEFT = {"outcome": "left-for-owner", "reason": "needs owner"}
OTHER_KEY = "b.py::u@L9"
KEPT_REASON = "repeat of f-1; keeps its earlier outcome ({})"
REFUTED = dict(disposition="refuted", refutedReason="the cited line does not exist")


def stored(raw):
    return rr._key({"findingKey": raw})


def mark(key, **over):
    return {"findingKey": key, "id": None, "fixHolds": None, **over}


def kept(outcome):
    return {"outcome": outcome, "reason": KEPT_REASON.format(outcome)}


def lfo(fid, key, **over):
    """A left-for-owner finding of a record: its stored key is `key`."""
    return finding(fid, findingKey=key, title=fid, consequence="c", **LEFT, **over)


def decide(row, *others):
    by_key = {r["findingKey"]: r for r in (row, *others)}
    return rs._decide(row, by_key, {})[:2]


# --- J1: a kept repeat reads its earlier outcome -----------------------------------------------------------------------

@pytest.mark.parametrize("outcome", rfs.OUTCOMES)
def test_j1_a_kept_repeat_reads_the_outcome_and_reason_it_keeps(outcome):
    # axis: J1 the kept-outcome branch; the row reads repeatKept, whatever its own disposition says
    row = ledger_row(disposition="fixed", repeatKept=kept(outcome))
    assert decide(row) == (outcome, KEPT_REASON.format(outcome))


def test_j1_a_merged_member_reads_its_representatives_kept_outcome():
    member = ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto=KEY)
    rep = ledger_row(KEY, id="rep-1", disposition="fixed", repeatKept=kept("craft"))
    assert decide(member, rep) == ("craft", KEPT_REASON.format("craft"))


@pytest.mark.parametrize("bad", [
    pytest.param({"outcome": "wontfix", "reason": "r"}, id="outcome-outside-the-vocabulary"),
    pytest.param({"outcome": None, "reason": "r"}, id="no-outcome"),
    pytest.param({"outcome": "craft", "reason": ""}, id="empty-reason"),
    pytest.param({"outcome": "craft"}, id="no-reason"),
    pytest.param({"outcome": "craft", "reason": 3}, id="reason-not-text"),
    pytest.param("craft", id="not-an-object"),
    pytest.param(None, id="null"),
])
def test_j1_edge2_an_invalid_repeat_kept_is_ignored(bad):
    # E2: the row reads as it does without the mark
    row = ledger_row(disposition="fixed", repeatKept=bad)
    assert decide(row) == decide(ledger_row(disposition="fixed")) == ("fixed", "fixed and audited in round 2")


def session_account(tmp_path, ledger):
    s = Session(tmp_path, dispositionLedger=ledger).seat("code-reviewer")
    return rs.account_from_session(s.save(), extras(), SessionFake().readers())


def test_j1_repeat_kept_is_never_a_finding_part_nor_written(tmp_path):
    row = ledger_row(disposition="fixed", repeatKept=kept("craft"), repeatOf=mark(KEY))
    (found,) = session_account(tmp_path, [row])["findings"]
    assert found["outcome"] == "craft" and "repeatKept" not in found


# --- J2: the repeat mark names the stored key ------------------------------------------------------------------------

@pytest.mark.parametrize("held", [
    pytest.param(OTHER_KEY, id="a-raw-session-key"),
    pytest.param(stored(OTHER_KEY), id="an-already-opaque-record-key"),
])
def test_j2_the_account_names_the_earlier_finding_by_its_stored_key(tmp_path, held):
    row = ledger_row(disposition="fixed", repeatOf={"findingKey": held, "id": "f-0", "fixHolds": True})
    (found,) = session_account(tmp_path, [row])["findings"]
    # axis: J2 the stored form; the record names the earlier finding by the key it stores, never the session's raw one
    assert found["repeatOf"] == {"findingKey": stored(OTHER_KEY), "id": "f-0", "fixHolds": True}


def test_j2_a_repeat_the_earlier_record_held_is_normalized_too():
    earlier = {"findingKey": stored(KEY), "repeatOf": mark(OTHER_KEY, id="f-0", fixHolds=False)}
    acct = {"findings": [{"findingKey": stored(KEY)}]}
    rs._fill(acct, [earlier])
    assert acct["findings"][0]["repeatOf"] == mark(stored(OTHER_KEY), id="f-0", fixHolds=False)


@pytest.mark.parametrize("bad", ["x", {"id": "f-0"}, {"findingKey": " "}, {"findingKey": 3}])
def test_j2_a_malformed_mark_is_left_for_the_writer_to_refuse(tmp_path, bad):
    (found,) = session_account(tmp_path, [ledger_row(repeatOf=bad)])["findings"]
    assert found["repeatOf"] == bad
    assert rr._repeat_fault(mark("k", id="f-0", fixHolds=True)) is None and rr._repeat_fault(bad) is not None


# --- J3: one predicate for "a repeat held elsewhere" -------------------------------------------------------------------

def held(f, *others):
    return rr.repeat_held_elsewhere(f, [f, *others])


@pytest.mark.parametrize("named", [
    pytest.param("session-key", id="a-raw-session-key"),
    pytest.param(stored("session-key"), id="an-opaque-record-key"),
])
def test_j3_a_left_for_owner_repeat_of_a_left_for_owner_finding_is_held(named):
    # axis: J3 the predicate; a raw session key and an opaque record key both name the earlier finding by its stored key
    earlier = lfo("e", stored("session-key"))
    assert held(lfo("r", "r-key", repeatOf=mark(named)), earlier) is True


def test_j3_the_earlier_finding_and_a_finding_without_a_mark_keep_their_cards():
    earlier = lfo("e", "e-key")
    assert held(earlier, lfo("r", "r-key", repeatOf=mark("e-key"))) is False
    assert held(lfo("r", "r-key", repeatOf=mark("r-key")), earlier) is False  # names its own key: the original finding


def test_j3_a_repeat_of_a_finding_with_another_outcome_keeps_its_card():
    # a repeat the table did not keep, now a new finding the session left for the owner
    for other in ("fixed", "shown-wrong", "craft", "ruling"):
        earlier = finding("e", findingKey="e-key", outcome=other, reason="r")
        assert held(lfo("r", "r-key", repeatOf=mark("e-key")), earlier) is False


@pytest.mark.parametrize("bad", ["e-key", ["e-key"], None, {}, {"id": "e"}, {"findingKey": ""}, {"findingKey": " "}, {"findingKey": 3}])
def test_j3_edge1_a_repeat_of_that_is_no_object_or_names_no_key_holds_nothing(bad):
    assert held(lfo("r", "r-key", repeatOf=bad), lfo("e", "e-key")) is False


def test_j3_edge3_a_repeat_whose_earlier_finding_is_not_in_the_record_keeps_its_card():
    assert held(lfo("r", "r-key", repeatOf=mark("gone-key")), lfo("e", "e-key")) is False


def test_j3_a_ring_of_repeats_holds_nothing_so_no_card_is_lost():
    one, two = lfo("a", "a-key", repeatOf=mark("b-key")), lfo("b", "b-key", repeatOf=mark("a-key"))
    assert held(one, two) is False and held(two, one) is False


def test_j3_a_chain_of_repeats_leaves_the_one_card_at_its_end():
    chain = [lfo("a", "a-key"), lfo("b", "b-key", repeatOf=mark("a-key")), lfo("c", "c-key", repeatOf=mark("b-key"))]
    assert [rr.repeat_held_elsewhere(f, chain) for f in chain] == [False, True, True]


def record_with_repeat(tmp_path, repeat_over=None, earlier_over=None):
    """The record of an account holding an earlier left-for-owner finding and a repeat of it."""
    earlier = finding("e-1", **{"title": "one", **LEFT, **(earlier_over or {})})
    again = finding("r-1", **{"title": "two", **LEFT, "repeatOf": mark(rr._key(earlier)), **(repeat_over or {})})
    rec = build(account(repoRoot=str(tmp_path), findings=[earlier, again]), Clean())
    return rec, earlier, again


def test_j3_a_held_repeat_adds_no_leftover_line(tmp_path):
    rec, earlier, again = record_with_repeat(tmp_path)
    assert [f["outcome"] for f in rec["findings"]] == ["left-for-owner", "left-for-owner"]
    assert rec["whatIsMissing"] == [rr.leftover_line(earlier)]


def test_j3_a_held_repeat_adds_no_left_for_owner_entry_and_leaves_the_status_awaits_owner(tmp_path):
    rec, earlier, again = record_with_repeat(tmp_path)
    assert rec["leftForOwner"] == ["e-1"]
    assert rec["status"] == rr.AWAITS_OWNER
    assert rr._owner_only(dict(rec, status=rr.NOT_REVIEWED), rec["whatIsMissing"]) is True
    assert rr._owner_only(dict(rec, status=rr.NOT_REVIEWED), [rr.leftover_line(again)]) is False


def test_j3_a_repeat_of_a_finding_with_another_outcome_keeps_its_leftover_line_in_the_record(tmp_path):
    rec, earlier, again = record_with_repeat(tmp_path, earlier_over={"outcome": "craft"})
    assert rec["whatIsMissing"] == [rr.leftover_line(again)] and rec["leftForOwner"] == ["r-1"]


def test_j3_edge3_a_repeat_whose_earlier_finding_is_missing_keeps_its_line_in_the_record(tmp_path):
    again = finding("r-1", title="two", **LEFT, repeatOf=mark("gone-key"))
    rec = build(account(repoRoot=str(tmp_path), findings=[again]), Clean())
    assert rec["whatIsMissing"] == [rr.leftover_line(again)] and rec["leftForOwner"] == ["r-1"]


def sheet_with_repeat(over=None, advisor_over=None):
    records, advisor = bundle(BIG)
    records[0]["findings"].append({**records[0]["findings"][5], "id": "F9", "findingKey": "retry/no-notice-again",
                                   "title": "Customers still hear nothing", "repeatOf": mark("retry/no-notice"), **(over or {})})
    return records, dict(advisor, **(advisor_over or {}))


def test_j3_a_held_repeat_adds_no_sheet_card_and_needs_no_leftovers_entry():
    records, advisor = sheet_with_repeat()
    base = sheet_build(*bundle(BIG))
    sheet = sheet_build(records, advisor)
    # axis: J3 pr_sheet card creation; the repeat of a left-for-owner finding the sheet already asks about adds no second card
    assert [c["id"] for c in leftover_cards(sheet)] == [c["id"] for c in leftover_cards(base)] and len(leftover_cards(sheet)) == 2
    assert [c["id"] for c in sheet["cards"]] == [c["id"] for c in base["cards"]]


def test_j3_a_leftovers_entry_for_a_held_repeat_names_no_card():
    records, advisor = sheet_with_repeat()
    advisor["leftovers"] = dict(advisor["leftovers"], **{"retry/no-notice-again": advisor["leftovers"]["F6"]})
    assert problems_of(records, advisor) == ["leftovers key 'retry/no-notice-again' names no left-for-owner finding"]


@pytest.mark.parametrize("over", [
    pytest.param({"repeatOf": mark("retry/gone")}, id="earlier-finding-absent"),
    pytest.param({"repeatOf": mark("retry/charge-twice")}, id="earlier-finding-fixed"),
    pytest.param({"repeatOf": mark("retry/no-notice-again")}, id="names-its-own-key"),
    pytest.param({"repeatOf": "retry/no-notice"}, id="mark-not-an-object"),
])
def test_j3_a_repeat_that_is_not_held_keeps_its_sheet_card_and_needs_its_own_entry(over):
    records, advisor = sheet_with_repeat(over)
    assert problems_of(records, advisor) == [
        "left-for-owner finding 'Customers still hear nothing' on PR #" + str(records[0]["pr"])
        + " has no leftovers entry (key 'retry/no-notice-again'); give it why, context and options, or a craft determination"]
    advisor["leftovers"] = dict(advisor["leftovers"], **{"retry/no-notice-again": advisor["leftovers"]["F6"]})
    assert len(leftover_cards(sheet_build(records, advisor))) == 3


# --- J4: the shown-wrong gate admits a kept repeat through the earlier finding's closure -------------------------------

def repeat_wrong(earlier, fid="a-2", title="two"):
    """A kept shown-wrong repeat of `earlier`: no wrong grade of its own."""
    return finding(fid, title=title, outcome="shown-wrong", reason="repeat of a-1; keeps its earlier outcome (shown-wrong)",
                   repeatOf=mark(rr._key(earlier), id="a-1"))


def write(tmp_path, fake, findings, **kw):
    return rr.write(put(tmp_path, account(findings=findings)), str(tmp_path), fake.readers(), **kw)


def test_j4_a_kept_shown_wrong_repeat_passes_through_the_carried_earlier_finding(tmp_path):
    fake = Fake()
    first = wrong("a-1", title="one", reason="not a bug")
    assert write(tmp_path, fake, [first], verifier_closed=closed(first))["ok"]
    again = repeat_wrong(first)
    out = write(tmp_path, fake, [first, again])  # axis: J4 the carried-key admission
    assert out["ok"], out
    # J5: both rows are in the written record, each with its outcome
    rows = {f["id"]: f for f in rr.read(7, readers=fake.readers())["findings"]}
    assert (rows["a-1"]["outcome"], rows["a-2"]["outcome"]) == ("shown-wrong", "shown-wrong")
    assert rows["a-2"]["repeatOf"]["findingKey"] == rr._key(first)


def test_j4_a_kept_shown_wrong_repeat_passes_through_a_verifier_closed_finding_of_this_account(tmp_path):
    fake = Fake()
    first = wrong("a-1", title="one", reason="not a bug")
    out = write(tmp_path, fake, [first, repeat_wrong(first)], verifier_closed=closed(first))
    assert out["ok"], out


@pytest.mark.parametrize("naming", [
    pytest.param(lambda first, elsewhere, bare: mark("rr1:" + "0" * 32), id="a-key-no-finding-holds"),
    pytest.param(lambda first, elsewhere, bare: mark(rr._key(elsewhere)), id="a-finding-that-is-not-shown-wrong"),
    pytest.param(lambda first, elsewhere, bare: mark(rr._key(bare)), id="its-own-key"),
    pytest.param(lambda first, elsewhere, bare: None, id="no-mark"),
])
def test_j4_a_shown_wrong_repeat_naming_anything_else_is_still_refused(tmp_path, naming):
    first = wrong("a-1", title="one", reason="not a bug")
    elsewhere = finding("a-3", title="three", outcome="fixed", reason="fixed in 1a2b3c4")
    bare = finding("a-2", title="two", outcome="shown-wrong", reason="r")
    named = naming(first, elsewhere, bare)
    # axis: J4 the narrowness; a mark naming a key that is neither carried nor closed in this account admits nothing
    out = write(tmp_path, Fake(), [first, dict(bare, repeatOf=named) if named else bare, elsewhere], verifier_closed=closed(first))
    assert (out["ok"], out["detail"]) == (False, "findings[1] is shown-wrong without the verifier's grade")


def test_j4_a_kept_repeat_of_an_earlier_finding_that_is_not_closed_is_refused(tmp_path):
    # the earlier finding is itself bare, so there is no closure to pass through
    bare = finding("a-1", title="one", outcome="shown-wrong", reason="r")
    # both are refused: the repeat gains no closure through an original that has none
    assert rr._wrong_ungraded([bare, repeat_wrong(bare)], None, closed(bare)) == [0, 1]
    out = write(tmp_path, Fake(), [bare, repeat_wrong(bare)], verifier_closed=closed(bare))
    assert out["ok"] is False and out["detail"].startswith("findings[")


@pytest.mark.parametrize("prior", [
    pytest.param(None, id="no-earlier-record"),
    pytest.param({"findings": "x"}, id="findings-not-a-list"),
    pytest.param({"findings": [None, "x"]}, id="findings-not-objects"),
    pytest.param({"findings": [{"outcome": "shown-wrong", "reason": "r"}]}, id="finding-without-a-key"),
])
def test_j4_edge4_an_earlier_record_that_cannot_be_read_admits_nothing_through_the_carry(prior):
    first = wrong("a-1", title="one")
    carried_only = finding("a-2", title="two", outcome="shown-wrong", reason="r", repeatOf=mark("rr1:" + "1" * 32))
    here = repeat_wrong(first, "a-3", "three")
    # the in-account closure still admits a repeat of a finding closed here; the carry admits nothing
    assert rr._wrong_ungraded([first, carried_only, here], prior, closed(first)) == [1]


def test_j4_edge1_a_mark_that_is_no_object_or_names_no_key_admits_nothing():
    first = wrong("a-1", title="one")
    bare = finding("a-2", title="two", outcome="shown-wrong", reason="r")
    for bad in ("rr1:x", {}, {"id": "a-1"}, {"findingKey": ""}, {"findingKey": " "}, {"findingKey": 3}, None):
        assert rr._wrong_ungraded([first, dict(bare, repeatOf=bad)], None, closed(first)) == [1], bad


# --- J5 and FR-22 through the session writer ------------------------------------------------------------------------------

def earlier_row(**over):
    return ledger_row(KEY, id="f-1", consequence="c", **over)


def repeat_row(outcome, **over):
    return ledger_row(OTHER_KEY, **{"id": "f-2", "title": "u", "file": "b.py", "line": 9, "consequence": "c",
                                    "dispositionSeq": 6, "repeatOf": mark(KEY, id="f-1"), "repeatKept": kept(outcome), **over})


def session_record(tmp_path, ledger, fake=None):
    fake = fake or SessionFake()
    s = Session(tmp_path, dispositionLedger=ledger).seat("code-reviewer")
    out = rs.write_from_session(s.save(), put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    return rr.read(7, readers=fake.readers()), fake


def by_id(rec):
    return {f["id"]: f for f in rec["findings"]}


def test_fr22_a_kept_repeat_of_a_craft_finding_reads_craft_and_changes_nothing_for_the_owner(tmp_path):
    rec, _ = session_record(tmp_path, [earlier_row(disposition="craft", settledReason="a craft call"),
                                       repeat_row("craft", disposition="craft")])
    rows = by_id(rec)
    assert (rows["f-1"]["outcome"], rows["f-2"]["outcome"]) == ("craft", "craft")
    assert rows["f-2"]["reason"] == KEPT_REASON.format("craft") and "repeatKept" not in rows["f-2"]
    assert rows["f-2"]["repeatOf"] == mark(stored(KEY), id="f-1")
    assert rec["leftForOwner"] == [] and rec["status"] != rr.AWAITS_OWNER


def test_fr22_a_kept_repeat_of_a_left_for_owner_finding_adds_no_line_no_entry_and_no_status_change(tmp_path):
    held_rec, _ = session_record(tmp_path, [earlier_row(disposition="left-for-owner", settledReason="needs owner"),
                                            repeat_row("left-for-owner", disposition="left-for-owner")])
    root = tmp_path / "alone"
    root.mkdir()
    alone, _ = session_record(root, [earlier_row(disposition="left-for-owner", settledReason="needs owner")])
    rows = by_id(held_rec)
    assert (rows["f-1"]["outcome"], rows["f-2"]["outcome"]) == ("left-for-owner", "left-for-owner")
    assert rows["f-2"]["reason"] == KEPT_REASON.format("left-for-owner")
    assert held_rec["leftForOwner"] == alone["leftForOwner"] == ["f-1"]
    assert held_rec["whatIsMissing"] == alone["whatIsMissing"]
    assert held_rec["status"] == alone["status"]


def test_j5_a_session_record_over_a_carried_earlier_finding_and_its_kept_shown_wrong_repeat_holds_both(tmp_path):
    first, fake = session_record(tmp_path, [earlier_row(**REFUTED, grade=WRONG)])
    (earlier_stored,) = first["findings"]
    assert earlier_stored["outcome"] == "shown-wrong"
    second_root = tmp_path / "second"
    second_root.mkdir()
    again = repeat_row("shown-wrong", disposition="refuted", refutedReason=KEPT_REASON.format("shown-wrong"),
                       repeatOf=mark(earlier_stored["findingKey"], id="f-1"))
    rec, _ = session_record(second_root, [again], fake)
    rows = by_id(rec)
    # the earlier finding is carried from the earlier record and the repeat passes the gate through it
    assert (rows["f-1"]["outcome"], rows["f-2"]["outcome"]) == ("shown-wrong", "shown-wrong")
    assert rows["f-2"]["reason"] == KEPT_REASON.format("shown-wrong") and "grade" not in rows["f-2"]
    assert rows["f-2"]["repeatOf"]["findingKey"] == earlier_stored["findingKey"]


def test_j5_a_kept_shown_wrong_repeat_in_the_same_session_passes_through_the_closed_earlier_finding(tmp_path):
    rec, _ = session_record(tmp_path, [earlier_row(**REFUTED, grade=WRONG),
                                       repeat_row("shown-wrong", disposition="refuted",
                                                  refutedReason=KEPT_REASON.format("shown-wrong"))])
    rows = by_id(rec)
    assert (rows["f-1"]["outcome"], rows["f-2"]["outcome"]) == ("shown-wrong", "shown-wrong")


def test_j5_nothing_is_dropped_the_unaccounted_and_carried_readers_behave_as_before():
    earlier = lfo("e", "e-key")
    assert rr._unaccounted({"findings": [earlier]}, [lfo("r", "r-key", repeatOf=mark("e-key"))]) == ["e"]
    acct = {"findings": [dict(lfo("r", "r-key", repeatOf=mark("e-key")))]}
    assert rs._carried(copy.deepcopy(acct), [earlier]) == [dict(earlier, reason=earlier["reason"] + rs.CARRIED)]
