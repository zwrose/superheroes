"""The session writer reads hand-submit sessions, carries the decisions a session holds, lists what the loop
refused, names the cap the loop stopped at, and follows a ruling through a merge."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import circuit_breaker  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402

from session_checkout import seed_session_meta  # noqa: E402
from test_panel_diff_at_head_1419 import _commit_file, _init_two_commit_repo  # noqa: E402
from test_round_driver import _cfg, _claim_reviewer, _drive_to_phase, _responder  # noqa: E402
from test_review_record_session import (  # noqa: E402
    CODEX, KEY, OOS, UNFILLED_SEAT, Fake, Session, _by_key, extras, ledger_row, put_extras, send,
)

CANON = {"kind": "canon", "ref": "canon-1"}
MEMBER = "m::t@L1"
RULED_BY = {"ruledBy": "the owner", "ruledAt": "2030-01-02"}


def _ruling(key=KEY, rnd=2, seq=1, decided_by=CANON, **over):
    row = {"seq": seq, "round": rnd, "findingKey": key, "ruling": "out-of-scope", "provenance": RULED_BY}
    if decided_by is not None:
        row["decidedBy"] = decided_by
    return dict(row, **over)


def _found(session, key=KEY):
    return {f["findingKey"]: f for f in rs.account_from_session(session, extras(), Fake().readers())["findings"]}[key]


def _hand_session(tmp_path, status, **state):
    """A session no seat result was journaled for: only the rounds' seat status says who ran."""
    rounds = {str(n): {"seatStatus": s} for n, s in status.items()}
    return Session(tmp_path, rounds=rounds, **state).save()


def _hand_submit_two_panels(base):
    """Drive a fixture review with `submit` alone to a terminal: round 1 raises a finding, the round-2 scoped
    read raises a Critical one, so the loop seats a second full panel. Returns the session directory."""
    base.mkdir()
    repo, base_sha, diff = _init_two_commit_repo(base)
    session = str(base / "session")
    seed_session_meta(session, repo)
    cfg = _cfg(verifyCommand="pytest -q", diff=diff, repoRoot=repo, baseRef=base_sha)
    first = [{"title": "bug", "severity": "Important", "consequence": "a wrong answer", "file": "f.py", "line": 1}]
    worse = [{"title": "worse bug", "severity": "Critical", "consequence": "data loss", "file": "f.py", "line": 1}]
    answer = _responder(round1_findings=first, scoped=worse)

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER:
            _commit_file(repo, "f.py", "fixed head %d\n" % rnd, "fixer commit")
            return {"fixes": [{"file": "f.py"}], "changedSubjects": ["Code"]}
        return answer(phase, payload, rnd)

    n = _drive_to_phase(session, cfg, respond, RD.P_PANEL)
    for _ in range(120):
        if n["action"] == RD.P_TERMINAL:
            return session
        art = _claim_reviewer(session, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        out = RD.cmd_submit(session, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert out["ok"], out
        n = RD.cmd_next(session)
        assert n["ok"], n
    raise AssertionError("driver did not reach a terminal within 120 steps")


def _names(account):
    return {v["name"]: v for v in account["reviewers"]}


# --- item 1: a session driven by hand submit -------------------------------------------------------

def test_a_session_driven_by_hand_submit_is_written_from_the_rounds_seat_status(tmp_path):
    session = _hand_submit_two_panels(tmp_path / "hand")
    with open(os.path.join(session, "driver-journal.jsonl"), encoding="utf-8") as fh:
        journal = [json.loads(line) for line in fh if line.strip()]
    ok, state = RD.load_state(session)
    status = {int(n): r["seatStatus"] for n, r in state["rounds"].items() if "seatStatus" in r}
    # the fixture is the shape a hand submit really leaves: no journaled seat, a seat status for each panel round
    assert ok and not any(isinstance(r.get("seat"), str) for r in journal)
    assert len(status) >= 2 and all(v == "run" for s in status.values() for v in s.values())
    account = rs.account_from_session(session, extras(), Fake().readers())
    # bites on: a hand-submit session refused, or its panel rounds' seats not listed as reviewers that ran
    expected = {f"{seat} (round {n})" for n, s in status.items() for seat in s}
    assert set(_names(account)) == expected and len(account["reviewers"]) == len(expected)
    for v in account["reviewers"]:
        assert v["ran"] is True and v["planned"] is True and v["runDir"] is None and v["commit"] is None
        assert v["vendor"] and v["model"] and "notIndependent" not in v
    assert account["rawFindingsFiles"] == [] and rs.HAND_SUBMIT_NOTE in account["checked"]
    fake = Fake(head=account["finalCommit"])
    out = send(tmp_path, session, fake)
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert {v["name"] for v in rec["reviewers"]} == expected
    # the writer, not the adapter, decides whether a reviewer counts: no maker is named here, so none is credited
    assert {v["findingsCoverage"] for v in rec["reviewers"]} == {rr.SESSION} and {v["runDir"] for v in rec["reviewers"]} == {None}
    assert rs.HAND_SUBMIT_NOTE in json.dumps(rec)


def test_a_hand_submit_reviewer_is_posted_as_reported_by_the_session_and_a_missing_one_as_missing(tmp_path):
    seat = {"vendor": "codex", "model": CODEX}
    session = _hand_session(tmp_path, {1: {"code-reviewer": "run", "security-reviewer": "missing"}},
                            seatMapReceipts=[{"round": "1", "map": {"seats": {"code-reviewer": seat, "security-reviewer": seat},
                                                                   "makerFamilies": ["xai"]}}])
    fake = Fake()
    out = send(tmp_path, session, fake, ci="green")
    # bites on: a hand-submit reviewer that ran not reaching the record as reported by the session, or a missing one not parked
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert {v["name"]: v["ran"] for v in rec["reviewers"]} == {
        "code-reviewer (round 1)": "reported-by-session", "security-reviewer (round 1)": "not-run"}
    assert [m["name"] for m in rec["missingReviews"]] == ["security-reviewer (round 1)"]
    assert out["status"] == "not-reviewed"


def test_a_seat_session_keeps_its_own_path_and_adds_no_hand_submit_note(tmp_path):
    account = rs.account_from_session(Session(tmp_path).seat("code-reviewer").save(), extras(checked=["a"]))
    assert [v["name"] for v in account["reviewers"]] == ["code-reviewer (round 1)"]
    assert account["checked"] == ["a"]


# --- fail-closed edges of item 1 ---------------------------------------------------------------------

@pytest.mark.parametrize("rounds", [{"1": {}}, {"1": {"seatStatus": {}}}, {"1": {"seatStatus": "run"}}, {}])
def test_edge_1_a_hand_submit_session_with_no_seat_status_is_refused(tmp_path, rounds):
    session = Session(tmp_path, rounds=rounds).save()
    # bites on: a session that holds neither a journaled seat nor a seat status written as a record with no reviewers
    with pytest.raises(rs.Refusal) as err:
        rs.account_from_session(session, extras(), Fake().readers())
    assert err.value.args == (rs.UNSUPPORTED, "the session recorded no seat result or seat status")
    fake = Fake()
    out = send(tmp_path, session, fake)
    assert out["ok"] is False and out["reason"] == rs.UNSUPPORTED and fake.writes == []


def test_edge_2_a_seat_status_that_is_neither_run_nor_missing_is_never_credited_as_run(tmp_path):
    session = _hand_session(tmp_path, {1: {"code-reviewer": "run", "security-reviewer": "missing", "test-role": "weird"}})
    rows = _names(rs.account_from_session(session, extras(), Fake().readers()))
    assert {n: v["ran"] for n, v in rows.items()} == {
        "code-reviewer (round 1)": True, "security-reviewer (round 1)": False, "test-role (round 1)": False}


def test_edge_3_a_round_with_no_governing_seat_map_names_vendor_and_model_unknown(tmp_path):
    rows = rs.account_from_session(_hand_session(tmp_path, {1: {"code-reviewer": "run"}}), extras(), Fake().readers())
    (row,) = rows["reviewers"]
    assert (row["vendor"], row["model"]) == ("unknown", "unknown")
    fake = Fake()
    assert send(tmp_path, _hand_session(tmp_path / "w", {1: {"code-reviewer": "run"}}), fake)["ok"]


def test_the_governing_seat_map_names_the_vendor_and_model(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": "m-1"}}}
    session = _hand_session(tmp_path, {1: {"code-reviewer": "run"}}, seatMapReceipts=[{"round": "1", "map": seat_map}])
    (row,) = rs.account_from_session(session, extras(), Fake().readers())["reviewers"]
    assert (row["vendor"], row["model"]) == ("codex", "m-1")


def test_hand_submit_unfilled_seats_and_recovered_misses_follow_the_seat_session_rules(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": "m-1"}, "security-reviewer": dict(UNFILLED_SEAT)}}
    session = _hand_session(tmp_path, {1: {"code-reviewer": "missing", "security-reviewer": "missing"},
                                       2: {"code-reviewer": "run"}},
                            seatMapReceipts=[{"round": "1", "map": seat_map}])
    rows = _names(rs.account_from_session(session, extras(), Fake().readers()))
    # a later round ran code-reviewer, so the round-1 miss is recovered; the unfilled seat stays listed as planned, never run
    assert set(rows) == {"code-reviewer (round 2)", "security-reviewer (round 1)", "security-reviewer (round 2)"}
    assert rows["security-reviewer (round 1)"]["vendor"] == rs.UNFILLED and rows["security-reviewer (round 1)"]["ran"] is False


# --- item 2: decisions ride along --------------------------------------------------------------------

def test_a_ledger_decision_rides_along_and_a_finding_with_none_carries_null(tmp_path):
    held = ledger_row(disposition="left-for-owner", settledReason="the owner decides", decidedBy=CANON)
    none = ledger_row(disposition="left-for-owner", settledReason="the owner decides")
    assert _found(Session(tmp_path, dispositionLedger=[held]).seat("code-reviewer").save())["decidedBy"] == CANON
    (tmp_path / "n").mkdir()
    found = _found(Session(tmp_path / "n", dispositionLedger=[none]).seat("code-reviewer").save())
    assert found["decidedBy"] is None and found["outcome"] == "left-for-owner"


def test_a_ruling_logged_after_the_raise_supplies_the_decision(tmp_path):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**OOS)], rulingsLog=[_ruling()])
    found = _found(s.seat("code-reviewer").save())
    # bites on: the decision a ruling cites being lost between the session and the account
    assert (found["outcome"], found["decidedBy"]) == ("ruling", CANON)


def test_a_ruling_logged_against_a_finding_merged_into_it_supplies_the_decision(tmp_path):
    ledger = [ledger_row(MEMBER, id="m-1", disposition=None, mergedInto=KEY), ledger_row(KEY, id="rep-1", **OOS)]
    session = Session(tmp_path, dispositionLedger=ledger, rulingsLog=[_ruling(MEMBER)]).seat("code-reviewer").save()
    assert _found(session)["decidedBy"] == CANON and _found(session, MEMBER)["decidedBy"] == CANON


def test_edge_5_a_ruling_older_than_the_findings_latest_raise_is_not_recovered(tmp_path):
    row = ledger_row(raisedRound=3, **OOS)
    older = Session(tmp_path, dispositionLedger=[row], rulingsLog=[_ruling(rnd=2)]).seat("code-reviewer").save()
    # bites on: a ruling given before the finding was raised again being cited as the decision on the re-raise
    assert _found(older)["decidedBy"] is None
    (tmp_path / "same").mkdir()
    same = Session(tmp_path / "same", dispositionLedger=[row], rulingsLog=[_ruling(rnd=3)]).seat("code-reviewer").save()
    assert _found(same)["decidedBy"] == CANON
    (tmp_path / "merged").mkdir()
    ledger = [ledger_row(MEMBER, id="m-1", disposition=None, mergedInto=KEY, raisedRound=4), ledger_row(KEY, **OOS)]
    late = Session(tmp_path / "merged", dispositionLedger=ledger, rulingsLog=[_ruling(rnd=3)]).seat("code-reviewer").save()
    assert _found(late)["decidedBy"] is None  # the member's re-raise is the group's latest raise


@pytest.mark.parametrize("log", ["x", [5, None], [{"findingKey": ["x"], "decidedBy": CANON}],
                                 [_ruling(decided_by=None)], [_ruling(round=None)], [_ruling(round=True)],
                                 [_ruling(decided_by="canon-1")]])
def test_edge_4_a_malformed_rulings_log_recovers_no_decision_and_never_raises(tmp_path, log):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**OOS)], rulingsLog=log)
    assert _found(s.seat("code-reviewer").save())["decidedBy"] is None


def test_a_fixed_finding_takes_no_decision_from_a_ruling(tmp_path):
    s = Session(tmp_path, dispositionLedger=[ledger_row()], rulingsLog=[_ruling()])
    assert _found(s.seat("code-reviewer").save())["decidedBy"] is None


def test_the_decision_reaches_the_account_the_writer_reads(tmp_path):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**OOS)], rulingsLog=[_ruling()]).seat("code-reviewer")
    fake = Fake()
    out = send(tmp_path, s.save(), fake)
    assert out["ok"], out
    (posted,) = _by_key(fake)
    assert posted["outcome"] == "ruling" and "ruled by the owner" in posted["reason"]


# --- item 3: a ruling followed through a merge -----------------------------------------------------

def test_an_attributed_ruling_logged_against_a_merged_member_settles_the_representative(tmp_path):
    ledger = [ledger_row(MEMBER, id="m-1", disposition=None, mergedInto=KEY), ledger_row(KEY, id="rep-1", **OOS)]
    s = Session(tmp_path, dispositionLedger=ledger, rulingsLog=[_ruling(MEMBER)]).seat("code-reviewer")
    found = {f["findingKey"]: f for f in rs.account_from_session(s.save(), extras())["findings"]}
    # bites on: a ruling logged against a merged member ignored, leaving the merged finding with the owner
    assert found[KEY]["outcome"] == "ruling"
    assert found[MEMBER]["outcome"] == "ruling"
    assert found[MEMBER]["reason"] == "belongs to the follow-up (ruled by the owner, 2030-01-02) (merged into rep-1)"


def test_the_latest_ruling_among_the_group_stands(tmp_path):
    ledger = [ledger_row(MEMBER, id="m-1", disposition=None, mergedInto=KEY), ledger_row(KEY, id="rep-1", **OOS)]
    newer = _ruling(MEMBER, seq=5, decided_by={"kind": "canon", "ref": "canon-2"})
    older = _ruling(KEY, seq=2)
    s = Session(tmp_path, dispositionLedger=ledger, rulingsLog=[newer, older]).seat("code-reviewer")
    assert _found(s.save())["decidedBy"] == {"kind": "canon", "ref": "canon-2"}


def test_edge_6_a_merge_chain_that_does_not_resolve_stays_undecided(tmp_path):
    ledger = [ledger_row(MEMBER, id="m-1", disposition=None, mergedInto="gone::x@L9")]
    found = _found(Session(tmp_path, dispositionLedger=ledger, rulingsLog=[_ruling(MEMBER)]).seat("code-reviewer").save(), MEMBER)
    assert (found["outcome"], found["reason"], found["decidedBy"]) == (None, rs.STILL_OPEN, None)


# --- item 4: refused findings ------------------------------------------------------------------------

def test_edge_7_every_round_drop_is_listed_with_its_round_and_malformed_ones_are_skipped(tmp_path):
    drop1 = {"file": "a.py", "line": 3, "title": "Unchecked index", "reason": "outside the reviewed diff"}
    drop2 = {"file": "b.py", "line": None, "title": "Stale name", "reason": "no consequence stated"}
    rounds = {"2": {"compileDrops": [drop2, "junk", {"title": "x"}, {"reason": "y"}, {"title": "", "reason": "y"}, None]},
              "1": {"compileDrops": [drop1]}, "3": {"compileDrops": "x"}, "4": "x", "5": {}}
    account = rs.account_from_session(Session(tmp_path, rounds=rounds).seat("code-reviewer").save(), extras())
    # bites on: a refused finding missing from the account, listed under the wrong round, or a malformed entry raising
    assert account["refused"] == [dict(drop1, round=1), dict(drop2, round=2)]


def test_a_session_without_drops_lists_none(tmp_path):
    assert rs.account_from_session(Session(tmp_path).seat("code-reviewer").save(), extras())["refused"] == []


# --- item 5: the cap the loop stopped at -------------------------------------------------------------

def _stopped(tmp_path, cfg, terminal="halted", kind="round-ceiling"):
    s = Session(tmp_path, terminal=terminal, rounds={"1": {}, "2": {}}, config=cfg,
                decisions=[{"kind": kind, "round": 2}]).seat("code-reviewer")
    return s.save()


@pytest.mark.parametrize("cfg,cap", [
    pytest.param({"maxRounds": 3, "maxRoundsAbsolute": 5}, 5, id="named-ceiling"),
    pytest.param({"maxRounds": 3}, circuit_breaker.DEFAULT_MAX_ROUNDS_ABSOLUTE, id="default-ceiling"),
    pytest.param({"maxRounds": 3, "maxRoundsAbsolute": None}, circuit_breaker.DEFAULT_MAX_ROUNDS_ABSOLUTE,
                 id="unnamed-ceiling"),
])
def test_a_round_ceiling_stop_names_the_ceiling_not_the_configured_cap(tmp_path, cfg, cap):
    session = _stopped(tmp_path, cfg)
    rounds = rs.account_from_session(session, extras())["rounds"]
    # bites on: a ceiling stop reporting the configured cap, which the loop did not stop at
    assert rounds == {"count": 2, "cap": cap, "capKind": "ceiling", "stoppedAtCap": True}
    fake = Fake()
    assert send(tmp_path, session, fake)["ok"]
    assert rr.read(7, readers=fake.readers())["rounds"]["cap"] == cap


@pytest.mark.parametrize("named", ["x", 2.5, True, []])
def test_edge_8_a_ceiling_that_does_not_resolve_leaves_the_cap_null(tmp_path, named):
    rounds = rs.account_from_session(_stopped(tmp_path, {"maxRounds": 3, "maxRoundsAbsolute": named}), extras())["rounds"]
    assert rounds["cap"] is None and rounds["capKind"] == "ceiling"


def test_a_stop_at_the_configured_cap_still_names_that_cap(tmp_path):
    session = _stopped(tmp_path, {"maxRounds": 3, "maxRoundsAbsolute": 9}, "capped-with-open-blocker", "capped-with-open-blocker")
    assert rs.account_from_session(session, extras())["rounds"] == {
        "count": 2, "cap": 3, "capKind": "rounds", "stoppedAtCap": True}


# --- item 6: a fix a later full panel did not raise again ---------------------------------------------

@pytest.mark.parametrize("receipt,reason", [
    pytest.param({"kind": "full-panel-not-reraised", "panelRound": 3}, "fixed; the full panel in round 3 did not raise it again",
                 id="later-full-panel"),
    pytest.param({"kind": "audit", "panelRound": 3}, "fixed and audited in round 2", id="another-receipt"),
    pytest.param("full-panel-not-reraised", "fixed and audited in round 2", id="receipt-not-an-object"),
    pytest.param(None, "fixed and audited in round 2", id="no-receipt"),
])
def test_a_fix_reads_as_the_receipt_says(tmp_path, receipt, reason):
    found = _found(Session(tmp_path, dispositionLedger=[ledger_row(dispositionReceipt=receipt)]).seat("code-reviewer").save())
    # bites on: a fix a later full panel did not raise again reading as audited, or any other receipt reading as that panel
    assert (found["outcome"], found["reason"]) == ("fixed", reason)


# --- item 7: extras pass-through -----------------------------------------------------------------------

def test_the_sheet_answers_and_base_ref_pass_to_the_account_unchanged(tmp_path):
    answers = {"card-1": {"answer": "yes"}}
    session = Session(tmp_path).seat("code-reviewer").save()
    account = rs.account_from_session(session, extras(sheetAnswers=answers, baseRef="origin/main"))
    # bites on: the extras' sheet answers or base ref dropped on the way to the account
    assert account["sheetAnswers"] == answers and account["baseRef"] == "origin/main"
    bare = rs.account_from_session(session, extras())
    assert bare["sheetAnswers"] is None and bare["baseRef"] is None
    nulls = rs.account_from_session(session, extras(sheetAnswers=None, baseRef=None))
    assert nulls["sheetAnswers"] is None and nulls["baseRef"] is None


@pytest.mark.parametrize("over,key", [({"sheetAnswers": "x"}, "sheetAnswers"), ({"sheetAnswers": []}, "sheetAnswers"),
                                      ({"baseRef": ""}, "baseRef"), ({"baseRef": 5}, "baseRef"),
                                      ({"baseRef": ["main"]}, "baseRef")])
def test_a_malformed_sheet_answers_or_base_ref_is_refused_naming_the_key(tmp_path, over, key):
    session = Session(tmp_path).seat("code-reviewer").save()
    with pytest.raises(rs.Refusal) as err:
        rs.account_from_session(session, extras(**over))
    assert err.value.args == (rs.BAD_EXTRAS, key)
    out = rs.write_from_session(session, put_extras(tmp_path, extras(**over)), str(tmp_path), Fake().readers())
    assert out["ok"] is False and out["reason"] == rs.BAD_EXTRAS
