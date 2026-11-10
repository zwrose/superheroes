"""#2436: an abandoned review session's record lists every planned seat that produced no result, with its reason.

Bite-proof record: i2436_abandoned_missing."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import dispatch_outcome  # noqa: E402
import record_paths  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_adapters  # noqa: E402
import round_phases  # noqa: E402
import round_records  # noqa: E402
import session_contract as sc  # noqa: E402

from test_review_record_session import (  # noqa: E402
    CODEX, HEAD, UNFILLED_SEAT, Fake, Session, extras, put_envelope, put_extras,
)

REASON = "owner stopped the loop"
PANEL, AUDITS, SYNTHESIS = round_phases.P_PANEL, round_phases.P_AUDITS, round_phases.P_SYNTHESIS
CODE, TEST = "code-reviewer", "test-role"
DIMS = [CODE, TEST]
ROUND = rs.REVIEWER_ROUND_FORMAT.format(rnd=1)
CODE_ROW, TEST_ROW = CODE + ROUND, TEST + ROUND
FORFEIT = {"vendor": "codex", "model": CODEX, "payload": {"reason": dispatch_outcome.REASON_FORFEITED}}
RESULT = {"vendor": "codex", "model": CODEX, "payload": {"findings": []}}
GO_AHEAD = {"kind": "owner-words", "words": "go on without it", "where": "the issue thread"}


def _pending(phase=PANEL, rnd=1, attempt=0):
    return {"action": "dispatch", "round": rnd, "phase": phase, "attempt": attempt, "payload": {}}


def _session(tmp_path, pending=None, seats=(CODE,), terminal=None, **state):
    """An abandoned (non-terminal) session pending the panel, the listed seats recorded with a result."""
    state.setdefault("config", {"maxRounds": 7, "dimensions": DIMS})
    s = Session(tmp_path, terminal=terminal, pending=pending if pending is not None else _pending(), **state)
    for seat in seats:
        s.seat(seat)
    return s


def _land(session, seat, body=None, raw=None, phase=PANEL, rnd=1, attempt=0, occ=0):
    path = record_paths.landing_path(session, rnd, phase, record_paths.storage_key(seat, occ), attempt)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(raw if raw is not None else json.dumps(body))


def _land_bare(session, seat, payload, phase=PANEL, rnd=1, attempt=0, occ=0):
    skey = record_paths.storage_key(seat, occ)
    for path, body in ((record_paths.bare_payload_path(session, rnd, phase, skey, attempt), payload),
                       (round_records.envelope_stub_path(session, rnd, phase, skey, attempt),
                        {"schema": round_records.SEAT_RESULT_SCHEMA, "vendor": "codex", "model": CODEX})):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(body, fh)


def _write(tmp_path, session, abandoned=REASON, **over):
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras(**over)), str(tmp_path), fake.readers(),
                                abandoned=abandoned)
    return out, fake


def _record(tmp_path, session, **over):
    out, fake = _write(tmp_path, session, **over)
    assert out["ok"], out
    return out, rr.read(7, readers=fake.readers())


def _account(session):
    return rs.account_from_session(session, extras(), Fake().readers(), abandoned=REASON)


def _missing(rec):
    return [(m["name"], m.get("reason")) for m in rec["missingReviews"]]


def test_a_pending_seat_whose_forfeit_landed_is_a_missing_review_with_the_forfeit_reason(tmp_path):
    """axis: G1/G2/G7 — a pending panel seat with no journal row and a landed forfeit is listed once, with its reason,
    parks the PR, and reads as a test lens that did not run."""
    s = _session(tmp_path)
    session = s.save()
    _land(session, TEST, dict(FORFEIT, schema=round_records.SEAT_RESULT_SCHEMA))
    out, rec = _record(tmp_path, session)
    assert len(rec["missingReviews"]) == 1
    entry = rec["missingReviews"][0]
    assert entry["name"] == TEST_ROW and entry["reason"] == dispatch_outcome.REASON_FORFEITED and entry["goAhead"] is None
    assert out["parked"] is True
    assert rec["testLens"]["listed"] is True and rec["testLens"]["ran"] is False
    assert rr.ABANDONED_MISSING_LINE.format(name=TEST_ROW, reason=dispatch_outcome.REASON_FORFEITED) in rec["whatIsMissing"]
    assert "Test lens: did not run." in rr.render(rec)


def test_a_pending_seat_with_nothing_landed_is_listed_as_no_result(tmp_path):
    """axis: G1 — the seat's orders went out and nothing came back: reason no-result."""
    session = _session(tmp_path).save()
    _, rec = _record(tmp_path, session)
    assert _missing(rec) == [(TEST_ROW, rr.NO_RESULT)]
    assert rr.NO_RESULT in rr.NO_RESULT_REASONS


@pytest.mark.parametrize("shape", ["landed-envelope", "landed-bare-payload", "stored-envelope"])
def test_a_pending_seat_whose_result_landed_or_was_stored_is_never_listed(tmp_path, shape):
    """axis: G2 — a seat that produced a result (landing folder or store, not yet journaled) is not a missing review
    and adds no reviewer row."""
    session = _session(tmp_path).save()
    if shape == "landed-envelope":
        _land(session, TEST, dict(RESULT, schema=round_records.SEAT_RESULT_SCHEMA))
    elif shape == "landed-bare-payload":
        _land_bare(session, TEST, {"findings": []})
    else:
        put_envelope(session, TEST, RESULT)
    account = _account(session)
    assert [v["name"] for v in account["reviewers"]] == [CODE_ROW]
    _, rec = _record(tmp_path, session)
    assert rec["missingReviews"] == [] and [v["name"] for v in rec["reviewers"]] == [CODE_ROW]


@pytest.mark.parametrize("raw", ["{not json", "[]"], ids=["torn", "not-an-object"])
def test_a_landing_that_cannot_be_read_is_listed_landing_unreadable(tmp_path, raw):
    """axis: G3 — something landed that cannot be read as a result: it is neither a result nor nothing."""
    session = _session(tmp_path).save()
    _land(session, TEST, raw=raw)
    _, rec = _record(tmp_path, session)
    assert _missing(rec) == [(TEST_ROW, rr.LANDING_UNREADABLE)]


def test_a_recorded_forfeit_and_a_recorded_missing_seat_are_listed_once_each_with_their_reasons(tmp_path):
    """axis: G7 — a seat recorded as a forfeit reads its payload reason; one recorded missing reads its seat-missing reason."""
    forfeit_dir = tmp_path / "forfeit"
    forfeit_dir.mkdir()
    s = _session(forfeit_dir, seats=(CODE, TEST))
    session = s.save()
    put_envelope(session, TEST, FORFEIT)
    _, rec = _record(forfeit_dir, session)
    assert _missing(rec) == [(TEST_ROW, dispatch_outcome.REASON_FORFEITED)]
    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    s = _session(missing_dir, seats=(CODE,))
    s.seat(TEST, cmd="record-missing")
    session = s.save()
    put_envelope(session, TEST, {"schema": sc.SEAT_MISSING_SCHEMA, "reason": "timeout"})
    _, rec = _record(missing_dir, session)
    assert _missing(rec) == [(TEST_ROW, "timeout")]


UNFILLED_MAP = [{"round": "1", "map": {"seats": {TEST: UNFILLED_SEAT}, "makerFamilies": ["xai"]}}]


def test_a_seat_the_map_left_unfilled_is_listed_once_with_the_unfilled_reason(tmp_path):
    """axis: G11 — a journaled session's unfilled panel seat carries noResult unfilled, and the pending phase adds no second row for it."""
    session = _session(tmp_path, seatMapReceipts=UNFILLED_MAP).save()
    account = _account(session)
    assert [(v["name"], v["ran"], v["noResult"]) for v in account["reviewers"] if "noResult" in v] == [(TEST_ROW, False, "unfilled")]
    _, rec = _record(tmp_path, session)
    assert _missing(rec) == [(TEST_ROW, "unfilled")]


def test_a_pending_panel_round_with_an_unfilled_seat_lists_it_unfilled_in_a_hand_submit_session(tmp_path):
    """axis: G12 — a hand-submit session's pending panel seat whose lens the governing map leaves unfilled is listed unfilled, not no-result."""
    session = _session(tmp_path, pending=_pending(rnd=2), seats=(), _submitUsed=True, round=2, seatMapReceipts=UNFILLED_MAP,
                       rounds={"1": {"seatStatus": {CODE: "run"}}, "2": {}}).save()
    names = {"code-reviewer (round 2)", "test-role (round 2)"}
    account = _account(session)
    assert {v["name"]: v.get("noResult") for v in account["reviewers"] if v["name"] in names} == {
        "code-reviewer (round 2)": rr.NO_RESULT, "test-role (round 2)": "unfilled"}


def test_a_session_that_ended_writes_what_it_wrote_before(tmp_path):
    """axis: the ended session's missing entry is exactly name and goAhead, its account rows carry no noResult, and its
    pending step lists nothing."""
    s = _session(tmp_path, seats=(CODE, TEST), terminal="converged",
                 config={"maxRounds": 7, "dimensions": DIMS + ["security-reviewer"]})
    session = s.save()
    put_envelope(session, TEST, FORFEIT)
    account = rs.account_from_session(session, extras(), Fake().readers())
    assert not any("noResult" in v for v in account["reviewers"])
    assert [v["name"] for v in account["reviewers"]] == [CODE_ROW, TEST_ROW]
    out, fake = _write(tmp_path, session, abandoned=None)
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert [set(m) for m in rec["missingReviews"]] == [{"name", "goAhead"}]
    assert "did not run (" not in " ".join(rec["whatIsMissing"])
    assert f"{TEST_ROW} did not run" in rec["whatIsMissing"]


def _hand_account(tmp_path, rows, abandoned):
    acct = {"schema": rr.ACCOUNT_SCHEMA, "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big", "finalCommit": HEAD,
            "ci": "green", "reviewers": rows, "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"],
            "makers": [{"family": "anthropic"}], **({"abandoned": {"reason": REASON}} if abandoned else {})}
    path = tmp_path / "account.json"
    path.write_text(json.dumps(acct))
    fake = Fake()
    return rr.write(str(path), str(tmp_path), fake.readers()), fake


def _row(name, **over):
    return {"name": name, "planned": True, "ran": False, "vendor": "codex", "model": CODEX,
            "commit": None, "runDir": None, **over}


CODE_RAN = _row(CODE, ran=True, commit=HEAD, runDir="/run/code-reviewer")


@pytest.mark.parametrize("abandoned, over", [
    (False, {"noResult": rr.NO_RESULT}),
    (True, {"ran": True, "noResult": rr.NO_RESULT}),
    (True, {"planned": False, "noResult": rr.NO_RESULT}),
    (True, {"noResult": "no-such-reason"}),
    (True, {"noResult": None}),
    (True, {"noResult": ["no-result"]}),
], ids=["ended-account", "ran-row", "unplanned-row", "token-outside-vocabulary", "null", "list"])
def test_the_account_refuses_a_no_result_reason_anywhere_but_a_not_run_row_of_an_abandoned_account(tmp_path, abandoned, over):
    """axis: G8 — noResult rides only a planned, not-run row of an abandoned account, from the fixed vocabulary."""
    out, fake = _hand_account(tmp_path, [_row("security-reviewer", **over), CODE_RAN], abandoned)
    assert out == {"ok": False, "reason": "review-account-invalid", "detail": "reviewers[0].noResult"}
    assert fake.marked() == []


def test_the_account_still_accepts_a_vocabulary_reason_and_still_refuses_the_retired_not_run_reason(tmp_path):
    """axis: G8 — every vocabulary token is accepted on an abandoned account's not-run row; notRunReason stays retired."""
    for token in sorted(rr.NO_RESULT_REASONS):
        sub = tmp_path / token
        sub.mkdir()
        out, fake = _hand_account(sub, [_row("security-reviewer", noResult=token), CODE_RAN], True)
        assert out["ok"], (token, out)
        entry = rr.read(7, readers=fake.readers())["missingReviews"][0]
        assert entry["reason"] == token
    retired = tmp_path / "retired"
    retired.mkdir()
    out, _ = _hand_account(retired, [_row("security-reviewer", notRunReason="no-loop-phase"), CODE_RAN], True)
    assert out == {"ok": False, "reason": "review-account-invalid", "detail": "reviewers[0].notRunReason"}


def test_an_owners_go_ahead_attaches_to_the_listed_seat_and_lifts_the_parking(tmp_path):
    """axis: G9 — the go-ahead matches the entry by name; the entry keeps its reason beside it."""
    session = _session(tmp_path).save()
    out, rec = _record(tmp_path, session, goAheads=[dict(GO_AHEAD, reviewer=TEST_ROW)])
    entry = rec["missingReviews"][0]
    assert entry["name"] == TEST_ROW and entry["reason"] == rr.NO_RESULT
    assert entry["goAhead"]["kind"] == "owner-words"
    assert out["parked"] is False and out["status"] == "not-reviewed"
    assert any(line.startswith(rr.ABANDONED_MISSING_LINE.format(name=TEST_ROW, reason=rr.NO_RESULT) + "; go-ahead: ")
               for line in rec["whatIsMissing"])


@pytest.mark.parametrize("recorded", [0, 1])
def test_a_repeated_audit_key_is_two_slots_and_only_the_unrecorded_one_is_listed(tmp_path, recorded):
    """axis: G6 — two audit targets sharing one id are two slots; the recorded occurrence never hides its sibling."""
    s = Session(tmp_path, terminal=None, pending=_pending(AUDITS), _auditTargets=[{"id": "T1"}, {"id": "T1"}])
    s.seat("T1", phase=AUDITS, occurrence=recorded)
    session = s.save()
    _, rec = _record(tmp_path, session)
    assert _missing(rec) == [(f"audits T1{ROUND}", rr.NO_RESULT)]
    assert sorted(v["ran"] != "not-run" for v in rec["reviewers"]) == [False, True]
    assert {v["name"] for v in rec["reviewers"]} == {f"audits T1{ROUND}"}


@pytest.mark.parametrize("phase, extra", [(SYNTHESIS, {}), (round_phases.P_APPLY_FIXES, {})], ids=["synthesis", "apply-fixes"])
def test_a_pending_synthesis_or_apply_fixes_phase_lists_nothing(tmp_path, phase, extra):
    """axis: G4 — synthesis is no reviewer and apply-fixes is no review phase: neither is ever listed."""
    session = _session(tmp_path, pending=_pending(phase), seats=(CODE, TEST), **extra).save()
    roster, why = round_adapters.roster_for(phase, {"round": 1}, {})
    assert why is None and roster
    _, rec = _record(tmp_path, session)
    assert rec["missingReviews"] == [] and [v["name"] for v in rec["reviewers"]] == [CODE_ROW, TEST_ROW]


def test_a_hand_submit_session_lists_only_its_pending_panels_unreported_seats(tmp_path):
    """axis: G5 — a hand-submit session's pending panel seat that no seat status named is listed; any other pending phase adds nothing."""
    status = {"1": {"seatStatus": {CODE: "run"}}}
    session = _session(tmp_path, seats=(), _submitUsed=True, rounds=status).save()
    account = _account(session)
    assert [(v["name"], v["ran"], v.get("noResult")) for v in account["reviewers"]] == [
        (CODE_ROW, True, None), (TEST_ROW, False, rr.NO_RESULT)]
    _, rec = _record(tmp_path, session)
    assert _missing(rec) == [(TEST_ROW, rr.NO_RESULT)]
    other = tmp_path / "other"
    other.mkdir()
    session = _session(other, pending=_pending(round_phases.P_SEAMS), seats=(), _submitUsed=True, rounds=status).save()
    assert [v["name"] for v in _account(session)["reviewers"]] == [CODE_ROW]


def test_a_returning_session_with_no_recorded_seat_lists_its_pending_scoped_finder(tmp_path):
    """axis: G1 — a session that is not hand-submitted and recorded no seat still lists its pending phase's seat."""
    phase = round_phases.P_SCOPED
    session = _session(tmp_path, pending=_pending(phase), seats=()).save()
    roster, why = round_adapters.roster_for(phase, {"round": 1}, {})
    assert why is None and len(roster) == 1
    account = _account(session)
    assert [(v["name"], v["ran"], v["noResult"]) for v in account["reviewers"]] == [
        (f"{phase.removeprefix('dispatch-')} {roster[0]}{ROUND}", False, rr.NO_RESULT)]
    _, rec = _record(tmp_path, session)
    assert [m["reason"] for m in rec["missingReviews"]] == [rr.NO_RESULT]


def test_a_pending_roster_that_cannot_be_derived_refuses_and_posts_nothing(tmp_path):
    """axis: fail closed — an underivable roster is a refusal, never an empty one."""
    session = _session(tmp_path, pending=_pending(AUDITS), _auditTargets="not-a-list").save()
    out, fake = _write(tmp_path, session)
    assert out["ok"] is False and out["reason"] == rs.UNREADABLE, out
    assert fake.comments == [] and fake.writes == []
