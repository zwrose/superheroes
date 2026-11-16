"""The bounded pass in the review record, the session adapter and the sheet (issue 2554, layer 3).

A pass's rounds above the cap are left out of the count and its audited rounds are listed; the summary line names an
audit only for a round whose audits folded; a finding the pass left for the owner carries the pass's evidence into the
record, and the sheet's card for it renders that evidence from the record alone. Every reader of the `converged`
terminal reads the `bounded-pass` shape: a census of the readers, and one behaviour test for each.

Drives the real round driver through the helpers of `test_bounded_pass_b1_2552` and `test_bounded_pass_b2_2554`, the
session adapter through `X._account`, the record validator, and the sheet through `pr_sheet.build`.

Bite-proof record: i2554_bounded_pass_record
"""
import ast
import copy
import json
import os
import sys
from collections import Counter

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decision_kinds  # noqa: E402
import pr_body_stage  # noqa: E402
import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import test_bounded_pass_b1_2552 as B1  # noqa: E402
import test_bounded_pass_b2_2554 as B2  # noqa: E402
import test_c1l4b_extra_audit as X  # noqa: E402
import test_pr_sheet as TPS  # noqa: E402
import test_review_record as TRR  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD
CAP = X.CAP
NONE = object()  # an evidence key left off the finding

B2_CLEARS = {CAP + 1: ("not-discharged", None)}  # B1 leaves the fix open, B2's audit discharges it
B2_OPEN = {CAP + 1: ("not-discharged", None), CAP + 2: ("not-discharged", None)}  # both audits leave it open
B2_RAISED = {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", B1._issue("Important"))}
OPEN_REASON = "still open after the bounded pass's one fix step and audit round"
RAISED_REASON = "raised by the bounded pass's final audit and still open"


# --- sessions, driven once and read by many tests ------------------------------------------------------------

@pytest.fixture(scope="module")
def account_of(tmp_path_factory):
    """The account the session adapter writes for a state: `X._account` on a fresh directory."""
    return lambda state: X._account(tmp_path_factory.mktemp("rec"), copy.deepcopy(state))


def _driven(tmp_path_factory, answers):
    d, _terminal, _trace, state = B2._b2_run(tmp_path_factory.mktemp("run"), answers)
    return d, state


@pytest.fixture(scope="module")
def b1_only(tmp_path_factory):
    d, _terminal, _trace = B1._session(tmp_path_factory.mktemp("run"), B1._respond())
    return d, X._state(d)


@pytest.fixture(scope="module")
def b1_b2(tmp_path_factory):
    return _driven(tmp_path_factory, B2_CLEARS)


@pytest.fixture(scope="module")
def card_session(tmp_path_factory):
    """Converged `bounded-pass`, the cap round's finding left for the owner after B2's audit."""
    return _driven(tmp_path_factory, B2_OPEN)


@pytest.fixture(scope="module")
def raised_session(tmp_path_factory):
    return _driven(tmp_path_factory, B2_RAISED)


@pytest.fixture(scope="module")
def handed_back_before_b1_audit(tmp_path_factory):
    d = B1._at_cap_verify(tmp_path_factory.mktemp("run"))
    state = X._state(d)
    state["_headDiffUnknown"] = True  # the pass's round cannot derive the surface of the cap round's fixes
    RD.save_state(d, state)
    B1._run(d, None, B1._respond())
    return d, X._state(d)


@pytest.fixture(scope="module")
def handed_back_after_b2_fix(tmp_path_factory):
    respond = B2._by_round(B2_CLEARS)
    d, _n, _trace = B1._session(tmp_path_factory.mktemp("run"), respond,
                                stop=lambda n: (n["action"], n["round"]) == (RD.P_VERIFY, CAP + 1))
    state = X._state(d)
    state["_headDiffUnknown"] = True  # B2's audit round cannot derive the surface of B2's fix
    RD.save_state(d, state)
    B1._run(d, None, respond)
    return d, X._state(d)


@pytest.fixture(scope="module")
def stall(tmp_path_factory):
    d, _terminal, _trace, state = B2._stall_session(tmp_path_factory.mktemp("run"))
    return d, state


@pytest.fixture(scope="module")
def stall_handed_back_early(tmp_path_factory):
    """A stall pass that finds a fix record in round r: it hands back `bounded-pass-open` before its audit round began."""
    real = RD._begin_stall_bounded_pass

    def with_a_fix_record(state, config, breaker, session_dir=None):
        state["rounds"][str(state["round"])]["fix"] = {"fixes": [], "commits": []}
        return real(state, config, breaker, session_dir=session_dir)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(RD, "_begin_stall_bounded_pass", with_a_fix_record)
        d, _terminal, _trace, state = B2._stall_session(tmp_path_factory.mktemp("run"))
    return d, state


@pytest.fixture(scope="module")
def stall_open(tmp_path_factory):
    d, _terminal, _trace, state = B2._stall_session(tmp_path_factory.mktemp("run"), b2="not-discharged")
    return d, state


# --- the rounds projection ------------------------------------------------------------------------------------

def test_a_b1_only_pass_leaves_its_round_out_of_the_count_and_lists_it_audited(account_of, b1_only):
    # axis: a round-cap pass's round above the cap is not counted, and its folded audits are listed — see bite-proof
    # record i2554_bounded_pass_record (E-audited, E-count)
    account = account_of(b1_only[1])
    assert account["rounds"]["count"] == CAP and account["rounds"]["stoppedAtCap"] is True
    assert account["rounds"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1], "auditedRounds": [CAP + 1]}
    RR._validate(account)


def test_a_b1_and_b2_pass_lists_both_rounds_audited_and_counts_neither(account_of, b1_b2):
    # axis: a B2 pass's two rounds above the cap are both listed audited and neither is counted — see bite-proof record
    # i2554_bounded_pass_record (E-audited, E-count)
    account = account_of(b1_b2[1])
    assert account["rounds"]["count"] == CAP
    assert account["rounds"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1, CAP + 2],
                                                "auditedRounds": [CAP + 1, CAP + 2]}
    RR._validate(account)


def test_a_pass_handed_back_before_b1s_audit_lists_no_audited_round(account_of, handed_back_before_b1_audit):
    # axis: a round whose audits never folded is listed but never audited — see bite-proof record
    # i2554_bounded_pass_record (E-audited)
    state = handed_back_before_b1_audit[1]
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert "3" not in state["rounds"], "the pass's round began and folded no audit"
    account = account_of(state)
    assert account["rounds"]["count"] == CAP
    assert account["rounds"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1], "auditedRounds": []}
    RR._validate(account)


def test_a_pass_handed_back_after_b2s_fix_before_its_audit_lists_only_b1s_round(account_of, handed_back_after_b2_fix):
    # axis: B2's round is listed but not audited when its audits never folded, so only B1's round is audited — see
    # bite-proof record i2554_bounded_pass_record (E-audited)
    state = handed_back_after_b2_fix[1]
    assert state["terminal"] == "handed-back" and state["boundedPass"]["rounds"] == [CAP + 1, CAP + 2]
    assert "audits" in state["rounds"][str(CAP + 1)] and str(CAP + 2) not in state["rounds"]
    account = account_of(state)
    assert account["rounds"]["count"] == CAP
    assert account["rounds"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1, CAP + 2],
                                                "auditedRounds": [CAP + 1]}
    RR._validate(account)


def test_a_round_is_audited_exactly_when_the_driver_folded_audits_into_its_record(account_of, b1_only):
    # axis: a round is audited exactly when its record holds folded audits, so a round with none is never listed audited
    # — see bite-proof record i2554_bounded_pass_record (E-audited)
    # the driver's marker of a folded audit round is `state["rounds"][n]["audits"]` (`_fold_audits`)
    state = copy.deepcopy(b1_only[1])
    state["rounds"][str(CAP + 1)].pop("audits")
    assert account_of(state)["rounds"]["boundedPass"]["auditedRounds"] == []


def test_a_fix_keeps_failing_pass_counts_every_one_of_its_rounds(account_of, stall):
    # axis: a stall pass's rounds are at or below the cap and are real rounds, so they count — see bite-proof record
    # i2554_bounded_pass_record (E-count)
    state = stall[1]
    pass_round = state["boundedPass"]["rounds"][0]
    assert state["boundedPass"]["trigger"] == "fix-keeps-failing" and pass_round <= RD._round_cap(state["config"])
    account = account_of(state)
    assert account["rounds"]["count"] == len(state["rounds"]) == pass_round
    assert account["rounds"]["stoppedAtCap"] is False
    assert account["rounds"]["boundedPass"] == {"trigger": "fix-keeps-failing", "rounds": [pass_round],
                                                "auditedRounds": [pass_round]}
    RR._validate(account)


def test_a_stall_pass_handed_back_before_its_audit_round_is_a_recordable_session_and_not_a_stop_at_the_cap(
        account_of, stall_handed_back_early):
    # axis: a stall pass that lists no round validates, and its `bounded-pass-open` is not a stop at the cap — see
    # bite-proof record i2554_bounded_pass_record (E-stall-record, E-stall-cap)
    state = stall_handed_back_early[1]
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert state["boundedPass"]["trigger"] == "fix-keeps-failing" and state["boundedPass"]["rounds"] == []
    account = account_of(state)
    RR._validate(account)
    assert account["rounds"]["boundedPass"] == {"trigger": "fix-keeps-failing", "rounds": [], "auditedRounds": []}
    assert account["rounds"]["stoppedAtCap"] is False
    assert RR._bounded_pass_line(account["rounds"]) == (
        "Bounded pass: it began after a fix kept failing, and handed back before its audit round began.")


@pytest.mark.parametrize("pass_state,expected", [
    ({"trigger": "round-cap", "rounds": [CAP + 1], "step": "done"}, True),
    ({"trigger": "fix-keeps-failing", "rounds": [], "step": "done"}, False),
    (None, False),
    ("unreadable", False),
], ids=["round-cap", "fix-keeps-failing", "no-bounded-pass", "unreadable-bounded-pass"])
def test_a_bounded_pass_open_hand_back_stops_at_the_cap_only_for_a_round_cap_pass(account_of, b1_b2, pass_state, expected):
    # axis: see E-stall-cap above
    state = copy.deepcopy(b1_b2[1])
    state["terminal"] = "handed-back"
    state["decisions"] = [*state["decisions"], {"kind": "bounded-pass-open", "detail": "x"}]
    state.pop("boundedPass", None)
    if pass_state is not None:
        state["boundedPass"] = pass_state
    assert account_of(state)["rounds"]["stoppedAtCap"] is expected


def test_the_cap_alone_decides_which_listed_rounds_are_left_out_of_the_count(account_of, b1_b2):
    # axis: only a listed round above the cap is left out of the count, so a listed round at the cap still counts — see
    # bite-proof record i2554_bounded_pass_record (E-count)
    state = copy.deepcopy(b1_b2[1])
    state["boundedPass"]["rounds"] = [CAP]  # a listed round at the cap is a real round
    assert account_of(state)["rounds"]["count"] == len(state["rounds"])
    state["boundedPass"]["rounds"] = [CAP, CAP + 1]
    assert account_of(state)["rounds"]["count"] == len(state["rounds"]) - 1


# --- the validator: rounds.boundedPass -------------------------------------------------------------------------

def _rounds(**bounded):
    return {"count": 2, "cap": 4, "stoppedAtCap": True, "boundedPass": bounded}


@pytest.mark.parametrize("bounded", [
    {"trigger": "round-cap", "rounds": [5], "auditedRounds": []},
    {"trigger": "round-cap", "rounds": [5], "auditedRounds": [5]},
    {"trigger": "round-cap", "rounds": [5, 6], "auditedRounds": [5, 6]},
    {"trigger": "round-cap", "rounds": [5, 6], "auditedRounds": [6]},
    {"trigger": "fix-keeps-failing", "rounds": [4], "auditedRounds": [4]},
    {"trigger": "fix-keeps-failing", "rounds": [], "auditedRounds": []},
], ids=["none-audited", "one", "both", "second-only", "stall", "stall-no-rounds"])
def test_the_validator_accepts_audited_rounds_that_are_listed_rounds_in_ascending_order(bounded):
    # axis: the validator accepts every `rounds.boundedPass` the driver writes, an empty `rounds` for a stall pass
    # included, so a valid record is never refused
    RR._validate(TRR.account(rounds=_rounds(**bounded)))


@pytest.mark.parametrize("bounded", [
    {"trigger": "round-cap", "rounds": [5]},
    {"trigger": "round-cap", "rounds": [5], "auditedRounds": [5], "why": "x"},
    {"trigger": "round-cap", "rounds": [5], "auditedRounds": 5},
    {"trigger": "round-cap", "rounds": [5], "auditedRounds": None},
    {"trigger": "round-cap", "rounds": [5, 6], "auditedRounds": [7]},
    {"trigger": "round-cap", "rounds": [5, 6], "auditedRounds": [6, 5]},
    {"trigger": "round-cap", "rounds": [5, 6], "auditedRounds": [5, 5]},
    {"trigger": "round-cap", "rounds": [1], "auditedRounds": [True]},
    {"trigger": "round-cap", "rounds": [5], "auditedRounds": ["5"]},
    {"trigger": "round-cap", "rounds": [], "auditedRounds": []},
], ids=["missing", "extra-key", "not-a-list", "null", "not-a-listed-round", "out-of-order", "duplicate", "bool",
        "string", "round-cap-no-rounds"])
def test_the_validator_refuses_audited_rounds_that_are_not_listed_rounds_in_ascending_order(bounded):
    # axis: the validator refuses audited rounds that are unlisted, unordered, duplicated or not integers, and a missing,
    # extra or non-list `auditedRounds`, so a malformed `rounds.boundedPass` is never recorded
    with pytest.raises(RR.Refusal) as refused:
        RR._validate(TRR.account(rounds=_rounds(**bounded)))
    assert refused.value.reason == "review-account-invalid" and refused.value.detail == "rounds.boundedPass"


# --- the summary line -------------------------------------------------------------------------------------------

def _line(trigger, rounds, audited, cap=4):
    return RR._bounded_pass_line({"cap": cap, "boundedPass": {"trigger": trigger, "rounds": rounds, "auditedRounds": audited}})


@pytest.mark.parametrize("trigger,rounds,audited,cap,expected", [
    ("round-cap", [5], [5], 4,
     "Bounded pass: the cap round's fixes were audited in round 5; round 5 is not counted in the 4 rounds."),
    ("round-cap", [5], [], 4,
     "Bounded pass: handed back before the cap round's fixes were audited; round 5 is not counted in the 4 rounds."),
    ("round-cap", [5, 6], [5, 6], 4,
     "Bounded pass: the cap round's fixes were audited in round 5, then one bounded fix was made and audited in "
     "round 6; rounds 5 and 6 are not counted in the 4 rounds."),
    ("round-cap", [5, 6], [5], 4,
     "Bounded pass: the cap round's fixes were audited in round 5, then one bounded fix was made and not audited; "
     "rounds 5 and 6 are not counted in the 4 rounds."),
    ("round-cap", [5], [5], None,
     "Bounded pass: the cap round's fixes were audited in round 5; round 5 is not counted in the rounds."),
    ("fix-keeps-failing", [4], [4], 7,
     "Bounded pass: a fix that kept failing got one more bounded fix, audited in round 4."),
    ("fix-keeps-failing", [4], [], 7,
     "Bounded pass: a fix that kept failing got one more bounded fix, which was not audited."),
    ("fix-keeps-failing", [], [], 7,
     "Bounded pass: it began after a fix kept failing, and handed back before its audit round began."),
], ids=["cap-b1", "cap-handed-back-before-b1-audit", "cap-b1-b2", "cap-b2-not-audited", "cap-unknown-cap", "stall-audited",
        "stall-not-audited", "stall-no-round"])
def test_the_line_names_an_audit_only_for_an_audited_round(trigger, rounds, audited, cap, expected):
    # axis: the line says "audited in round N" only for a round in `auditedRounds`, and "not counted" only for a
    # round-cap pass — see bite-proof record i2554_bounded_pass_record (E-audited)
    line = _line(trigger, rounds, audited, cap)
    assert line == expected
    assert all(f"audited in round {n}" not in line for n in rounds if n not in audited)
    assert ("not counted" in line) == (trigger == "round-cap")


def test_a_record_with_no_bounded_pass_has_no_line():
    # axis: a record with no bounded pass (or an unreadable one) gets no summary line, so an ordinary record is unchanged
    assert RR._bounded_pass_line({"cap": 4}) is None and RR._bounded_pass_line(None) is None


def test_the_session_line_of_each_ending_says_what_ran(account_of, b1_b2, handed_back_before_b1_audit,
                                                      handed_back_after_b2_fix):
    # axis: the summary line of each driven ending names what ran — audited, handed back before the audit, or a fix not
    # audited — never more — see bite-proof record i2554_bounded_pass_record (E-audited)
    assert RR._bounded_pass_line(account_of(b1_b2[1])["rounds"]) == (
        "Bounded pass: the cap round's fixes were audited in round 3, then one bounded fix was made and audited in "
        "round 4; rounds 3 and 4 are not counted in the 2 rounds.")
    assert "handed back before the cap round's fixes were audited" in RR._bounded_pass_line(
        account_of(handed_back_before_b1_audit[1])["rounds"])
    assert "one bounded fix was made and not audited" in RR._bounded_pass_line(
        account_of(handed_back_after_b2_fix[1])["rounds"])


# --- the finding evidence in the record ----------------------------------------------------------------------------

def test_the_adapter_carries_the_evidence_of_a_finding_the_pass_left_for_the_owner(account_of, card_session):
    # axis: a left-for-owner finding the pass settled carries its representative row's evidence into the record,
    # end to end from a converged B2 session — see bite-proof record i2554_bounded_pass_record (E-evidence)
    _d, state = card_session
    ledger = B2._fixed_row(state)
    account = account_of(state)
    row = next(f for f in account["findings"] if f["title"] == "open-important")
    assert row["outcome"] == "left-for-owner" and row["openAtLoopEnd"] is True
    assert row["boundedPassEvidence"] == ledger["boundedPassEvidence"]
    assert row["boundedPassEvidence"]["audit"] == {"ruling": "not-discharged", "reasonKind": "wrong", "reason": "still broken"}
    assert row["boundedPassEvidence"]["fixCommit"] == state["rounds"][str(CAP + 1)]["fixFoldHead"]
    RR._validate(account)


def test_the_adapter_carries_the_evidence_of_a_finding_the_final_audit_raised(account_of, raised_session):
    # axis: a finding the final audit raised carries the raised-by-final-audit evidence (no fix commit) into the record —
    # see bite-proof record i2554_bounded_pass_record (E-evidence)
    account = account_of(raised_session[1])
    raised = next(f for f in account["findings"] if f["title"] == "raised-by-the-audit")
    assert raised["outcome"] == "left-for-owner"
    assert raised["boundedPassEvidence"] == {"fixCommit": None, "raisedByFinalAudit": True}
    RR._validate(account)


def test_a_stall_passs_stuck_finding_carries_its_evidence_too(account_of, stall_open):
    # axis: a stall pass's stuck finding left for the owner carries its audit evidence into the record, as a round-cap
    # pass's does — see bite-proof record i2554_bounded_pass_record (E-evidence)
    account = account_of(stall_open[1])
    late = next(f for f in account["findings"] if f["title"] == "late")
    assert late["outcome"] == "left-for-owner" and late["boundedPassEvidence"]["audit"]["reason"] == "still broken"
    RR._validate(account)


def test_a_finding_the_pass_cleared_or_a_session_with_no_pass_carries_no_evidence(account_of, b1_b2, b1_only):
    # axis: a finding the pass cleared, and a session whose pass never fixed anything, carry no evidence, so the
    # evidence marks only what was left for the owner
    for state in (b1_b2[1], b1_only[1]):
        assert not [f for f in account_of(state)["findings"] if "boundedPassEvidence" in f]


def _held(evidence=NONE, **over):
    """A left-for-owner record finding, with the evidence given."""
    finding = TRR.finding("code-001", outcome="left-for-owner", reason="left for you", **over)
    if evidence is not NONE:
        finding["boundedPassEvidence"] = evidence
    return finding


AUDIT = {"ruling": "not-discharged", "reasonKind": "wrong", "reason": "still broken"}


@pytest.mark.parametrize("evidence", [
    {"fixCommit": "abc1234def", "audit": AUDIT},
    {"fixCommit": None, "audit": AUDIT},
    {"fixCommit": "abc1234def", "audit": {"ruling": None, "reasonKind": None, "reason": None}},
    {"fixCommit": None, "raisedByFinalAudit": True},
], ids=["commit-and-audit", "no-commit", "audit-of-nulls", "raised"])
def test_the_validator_accepts_the_two_shapes_the_driver_writes(evidence):
    # axis: the validator accepts both evidence shapes the driver writes, so a valid pass record is never refused
    RR._validate(TRR.account(findings=[_held(evidence)]))


@pytest.mark.parametrize("evidence", [
    "audited", None, [], {},
    {"fixCommit": "", "audit": AUDIT},
    {"fixCommit": 5, "audit": AUDIT},
    {"fixCommit": "abc1234def"},
    {"audit": AUDIT},
    {"fixCommit": "abc1234def", "audit": "still broken"},
    {"fixCommit": "abc1234def", "audit": {}},
    {"fixCommit": "abc1234def", "audit": {"ruling": "not-discharged", "reasonKind": "wrong"}},
    {"fixCommit": "abc1234def", "audit": {**AUDIT, "extra": "x"}},
    {"fixCommit": "abc1234def", "audit": {**AUDIT, "reason": 7}},
    {"fixCommit": "abc1234def", "audit": AUDIT, "raisedByFinalAudit": False},
    {"fixCommit": "abc1234def", "audit": AUDIT, "note": "x"},
    {"fixCommit": "abc1234def", "raisedByFinalAudit": True},
    {"fixCommit": None, "raisedByFinalAudit": False},
    {"fixCommit": None, "raisedByFinalAudit": "yes"},
    {"raisedByFinalAudit": True},
    {"fixCommit": None, "audit": AUDIT, "raisedByFinalAudit": True},
], ids=["string", "null", "list", "empty", "empty-commit", "int-commit", "no-audit", "no-commit-key", "audit-a-string",
        "audit-empty", "audit-missing-reason", "audit-extra-key", "audit-int-reason", "audit-and-flag-false", "extra-key",
        "raised-with-a-commit", "raised-false", "raised-a-string", "raised-no-commit-key", "raised-with-an-audit"])
def test_the_validator_refuses_evidence_that_is_not_one_of_the_two_shapes(evidence):
    # axis: the evidence is exactly one of the two shapes the driver writes, never another value — see bite-proof
    # record i2554_bounded_pass_record (E-evidence-shape)
    with pytest.raises(RR.Refusal) as refused:
        RR._validate(TRR.account(findings=[_held(evidence)]))
    assert refused.value.reason == "review-account-invalid" and refused.value.detail == "findings[0].boundedPassEvidence"


@pytest.mark.parametrize("outcome", ["fixed", None], ids=["fixed", "undecided"])
def test_the_validator_refuses_evidence_on_a_finding_that_is_not_left_for_the_owner(outcome):
    # axis: evidence on a finding whose outcome is not left-for-owner is refused, so a stale or misplaced card is never
    # recorded
    finding = TRR.finding("code-001", outcome=outcome, boundedPassEvidence={"fixCommit": None, "raisedByFinalAudit": True})
    with pytest.raises(RR.Refusal) as refused:
        RR._validate(TRR.account(findings=[finding]))
    assert refused.value.detail == "findings[0].boundedPassEvidence"


def test_a_finding_the_owner_later_decides_is_written_without_the_evidence():
    # axis: a finding the owner moved off left-for-owner is written without its evidence, and a finding still left for
    # the owner keeps it
    held = _held({"fixCommit": None, "raisedByFinalAudit": True})
    moved = dict(held, outcome="fixed")
    other = TRR.finding("code-002")
    out = RR._drop_stale_open_marker([held, moved, other])
    assert out[0] == held and "boundedPassEvidence" not in out[1] and out[2] == other
    assert {k: v for k, v in moved.items() if k != "boundedPassEvidence"} == out[1]
    RR._validate(TRR.account(findings=[out[1]]))


# --- the card on the sheet ----------------------------------------------------------------------------------------

def _card(evidence):
    """The leftover card of the sheet fixture's first left-for-owner finding, built with `evidence` on the record."""
    records, advisor = TPS.bundle(TPS.BIG)
    finding = records[0]["findings"][5]
    assert finding["outcome"] == "left-for-owner"
    if evidence is not NONE:
        finding["boundedPassEvidence"] = evidence
    sheet = TPS.build(records, advisor)
    return next(c for c in TPS.leftover_cards(sheet) if c["question"] == finding["title"]), sheet


def _tried(card):
    sections = [s for s in card["context"] if s["title"] == "What the loop tried"]
    assert len(sections) <= 1
    return [s["blocks"] for s in sections]


def test_a_card_with_no_evidence_is_unchanged():
    # axis: a leftover card whose record finding has no evidence gets no "What the loop tried" section, so an ordinary
    # card is unchanged — see bite-proof record i2554_bounded_pass_record (E-card)
    card, _sheet = _card(NONE)
    assert [s["title"] for s in card["context"]] == [TPS.WORDS["whyYours"], TPS.WORDS["whatHappened"], TPS.WORDS["ifLeft"]]
    assert _tried(card) == []


@pytest.mark.parametrize("evidence,sentence", [
    ({"fixCommit": "abc1234def5678", "audit": AUDIT},
     "The loop tried one bounded fix at abc1234; its audit said: still broken"),
    ({"fixCommit": None, "audit": AUDIT}, "The loop tried one bounded fix; its audit said: still broken"),
    ({"fixCommit": None, "raisedByFinalAudit": True}, "Raised by the final audit; no fix was tried."),
    ({"fixCommit": "abc1234def5678", "audit": {**AUDIT, "reason": None}}, "The loop tried one bounded fix at abc1234."),
    ({"fixCommit": "abc1234def5678", "audit": {**AUDIT, "reason": "  "}}, "The loop tried one bounded fix at abc1234."),
    ({"fixCommit": None, "audit": {**AUDIT, "reason": None}}, "The loop tried one bounded fix."),
    ({"fixCommit": None, "audit": {**AUDIT, "reason": ""}}, "The loop tried one bounded fix."),
], ids=["commit-and-reason", "no-commit", "raised", "reason-null", "reason-blank", "no-commit-no-reason",
        "no-commit-empty-reason"])
def test_the_card_renders_the_evidence_from_the_record(evidence, sentence):
    # axis: a leftover card whose record finding carries evidence gets a "What the loop tried" section after "What
    # happened", rendered from the record alone; a null or blank reason drops only the audit clause — see bite-proof
    # record i2554_bounded_pass_record (E-card)
    card, sheet = _card(evidence)
    assert _tried(card) == [[{"paragraph": sentence}]]
    assert [s["title"] for s in card["context"]] == [TPS.WORDS["whyYours"], TPS.WORDS["whatHappened"],
                                                     "What the loop tried", TPS.WORDS["ifLeft"]]
    assert "None" not in json.dumps(card["context"])
    assert list(TPS.Draft202012Validator(TPS.SCHEMA).iter_errors(sheet)) == [] and TPS.check_sheet_problems(sheet) == []


# --- the converged readers: a census, and each reader on a converged bounded pass -----------------------------------

def _converged_readers_in(source, module):
    """Every comparison in `source` that tests a value against the string `converged`: an `==`, `!=`, `in` or
    `not in` with one side that constant, or a tuple, list or set holding it. Keyed by (module, enclosing function)."""
    def holds(node):
        if isinstance(node, ast.Constant):
            return node.value == "converged"
        return isinstance(node, (ast.Tuple, ast.List, ast.Set)) and any(
            isinstance(e, ast.Constant) and e.value == "converged" for e in node.elts)

    found, stack = [], []

    def visit(node):
        is_function = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if is_function:
            stack.append(node.name)
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for i, op in enumerate(node.ops):
                if isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) and (holds(operands[i]) or holds(operands[i + 1])):
                    found.append((module, stack[-1] if stack else "<module>"))
        for child in ast.iter_child_nodes(node):
            visit(child)
        if is_function:
            stack.pop()

    visit(ast.parse(source))
    return found


def _converged_readers():
    """The readers in every non-test module under `plugins/superheroes/lib`, as a Counter of (module, function)."""
    found = []
    for root, dirs, files in os.walk(_LIB):
        dirs[:] = sorted(d for d in dirs if d not in ("tests", "__pycache__"))
        for name in sorted(files):
            if name.endswith(".py"):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as handle:
                    found += _converged_readers_in(handle.read(), os.path.relpath(path, _LIB).replace(os.sep, "/"))
    return Counter(found)


# the readers of the `converged` terminal or verdict, each with its behaviour test below. One entry per comparison: the
# eight lines of the orchestrator's table are nine comparisons, `map_terminal_cause` line 173 testing both the verdict and
# the decision kind, and `account_from_session` holds two of the lines
READERS = Counter([
    ("decision_kinds.py", "map_terminal_cause"),
    ("decision_kinds.py", "map_terminal_cause"),
    ("pr_body_stage.py", "_converged"),
    ("review_record.py", "_validate"),
    ("review_record_session.py", "_empty_returning_round"),
    ("review_record_session.py", "account_from_session"),
    ("review_record_session.py", "account_from_session"),
    ("round_driver.py", "_settle_open_findings"),
    ("round_driver.py", "_validate_rounds_lens_coverage"),
])


def test_the_census_finds_exactly_the_listed_readers_of_the_converged_terminal():
    # axis: a new reader of `converged`, in any of the four comparison forms, fails this census until it is added with a
    # behaviour test below — see bite-proof record i2554_bounded_pass_record (E-census)
    assert _converged_readers() == READERS


@pytest.mark.parametrize("source,expected", [
    ("def f(x):\n    return x == 'converged'\n", 1),
    ("def f(x):\n    return 'converged' == x\n", 1),
    ("def f(x):\n    return x != 'converged'\n", 1),
    ("def f(x):\n    return x in ('halted', 'converged')\n", 1),
    ("def f(x):\n    return x not in ['converged']\n", 1),
    ("def f(x):\n    return x in {'converged', 'x'}\n", 1),
    ("def f(x):\n    return 'converged' in x\n", 1),
    ("def f(x):\n    return x == 'convergedx' or x in ('halted',) or x is None\n", 0),
], ids=["eq", "eq-reversed", "ne", "in-tuple", "not-in-list", "in-set", "in-reversed", "other-strings"])
def test_the_census_sees_every_comparison_form(source, expected):
    # axis: the census scan finds a `converged` comparison in each of its four forms and none in other strings, so a new
    # reader cannot hide in a form the scan misses — see bite-proof record i2554_bounded_pass_record (E-census)
    assert len(_converged_readers_in(source, "m.py")) == expected
    assert all(key == ("m.py", "f") for key in _converged_readers_in(source, "m.py"))


def test_decision_kinds_reads_a_converged_bounded_pass_as_no_cause(card_session):
    # axis: the decision-kind reader maps a converged bounded pass to no terminal cause, so it never reads as a stop
    _d, state = card_session
    assert state["terminal"] == "converged" and state["certification"]["shape"] == "bounded-pass"
    assert decision_kinds.map_terminal_cause(state["terminal"], state["decisions"][-1]["kind"]) is None


def test_the_pr_body_stage_reads_the_receipt_as_converged(card_session):
    # axis: the PR-body stage reads a bounded-pass receipt as converged, so it is never staged as an unconverged review
    assert pr_body_stage._converged(card_session[0]) is True


def test_the_record_validator_reads_the_absence_of_an_uncertified_stamp(account_of, card_session):
    # axis: the record validator accepts a converged bounded-pass account with no uncertified stamp and refuses one that
    # carries it
    account = account_of(card_session[1])
    assert "uncertified" not in account and account["findings"]
    RR._validate(account)
    stamped = dict(account, uncertified={"terminal": "converged", "reason": "x"})
    with pytest.raises(RR.Refusal) as refused:
        RR._validate(stamped)
    assert refused.value.detail == "uncertified"


def test_a_converged_bounded_pass_is_not_the_empty_returning_round(card_session):
    # axis: a converged bounded pass is not read as an empty returning round, so its record is written in full
    assert RS._empty_returning_round(card_session[1]) is None


def test_the_adapter_reads_stopped_at_the_cap_from_the_pass_trigger(account_of, card_session, stall_open):
    # axis: `stoppedAtCap` follows the pass trigger — true for a round-cap pass, false for a stall pass — see bite-proof
    # record i2554_bounded_pass_record (E-stall-cap)
    assert account_of(card_session[1])["rounds"]["stoppedAtCap"] is True  # a round-cap pass kept the cap
    assert account_of(stall_open[1])["rounds"]["stoppedAtCap"] is False  # a fix-keeps-failing pass never reached it


def test_the_adapter_writes_no_uncertified_stamp_for_a_converged_bounded_pass(account_of, card_session, stall_open):
    # axis: the adapter stamps no `uncertified` on a converged bounded pass of either trigger, so it is never recorded
    # as uncertified
    for _d, state in (card_session, stall_open):
        assert state["terminal"] == "converged"
        assert "uncertified" not in account_of(state)


def test_the_cards_settled_reason_is_the_bounded_passs_own(card_session, raised_session):
    # axis: the pass's own settled reason survives the terminal settle, so a card never reads as left unfixed at converge
    # the terminal settle's `left unfixed when the review loop converged` never overwrites the pass's own reason
    assert B2._fixed_row(card_session[1])["settledReason"] == OPEN_REASON
    raised = X._rows(raised_session[1], "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["settledReason"] == RAISED_REASON
    for state in (card_session[1], raised_session[1]):
        assert "left unfixed when the review loop converged" not in json.dumps(state[RD.session_contract.DISPOSITION_LEDGER_KEY])


def test_the_drivers_receipt_validator_reads_the_converged_bounded_pass_receipt(card_session):
    # axis: the driver's receipt validators accept a converged bounded-pass receipt, so it is never refused as an
    # unrecognised shape
    d, _state = card_session
    with open(os.path.join(d, "round-receipt.json"), encoding="utf-8") as handle:
        receipt = json.load(handle)
    assert receipt["verdict"] == "converged" and receipt["certification"]["shape"] == "bounded-pass"
    assert RD._validate_rounds_lens_coverage(receipt) == (True, None)
    assert RD._verify_terminal_receipt(d) is None
