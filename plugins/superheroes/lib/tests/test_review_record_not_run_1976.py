"""#1976: a composed grounding seat the auto-fix loop does not run is named as not run in the review record, not parked."""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pr_sheet  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

from test_pr_sheet import BIG, WORDS, bundle, build, problems_of  # noqa: E402
from test_review_record_session import CODEX, HEAD, Fake, Session, extras, send  # noqa: E402

SEAT = {"vendor": "codex", "model": CODEX}
UNFILLED_SEAT = {"vendor": None, "model": None, "effort": None, "tier": "deep", "family": None, "source": "unfilled"}
WHY = rr.NOT_RUN_REASONS["no-loop-phase"][1]
NOT_RUN = {"name": "grounding-seat", "reason": "no-loop-phase", "why": WHY}


def _session(tmp_path, seats, **state):
    """A finished loop session: code-reviewer journaled as ran on the final commit, the round-1 map composing `seats`."""
    s = Session(tmp_path, seatMapReceipts=[{"round": "1", "map": {"seats": seats, "makerFamilies": ["anthropic"]}}], **state)
    s.seat("code-reviewer", head=HEAD)
    return s


def _record(tmp_path, s):
    fake = Fake()
    out = send(tmp_path, s.save(), fake)
    assert out["ok"], out
    return rr.read(7, readers=fake.readers()), fake


def _hand_reviewers(*rows):
    code = {"name": "code-reviewer", "planned": True, "ran": True, "vendor": "codex", "model": CODEX,
            "commit": HEAD, "runDir": "/run/code-reviewer"}
    return [code, *rows]


def _grounding(**over):
    return {"name": "grounding-seat", "planned": True, "ran": False, "vendor": "codex", "model": CODEX,
            "commit": None, "runDir": None, "notRunReason": "no-loop-phase", **over}


def _hand(tmp_path, reviewers, runs=None):
    """Write a hand-written account through the writer; returns (the write result, the Fake)."""
    fake = Fake(runs=runs)
    acct = {"schema": "review-account/1", "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big", "finalCommit": HEAD,
            "ci": "green", "reviewers": reviewers, "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"],
            "makers": [{"family": "anthropic"}]}
    path = tmp_path / "account.json"
    path.write_text(json.dumps(acct))
    return rr.write(str(path), str(tmp_path), fake.readers()), fake


def test_a_composed_grounding_seat_is_named_as_not_run_and_does_not_park(tmp_path):
    # axis: the session's account lists the composed grounding seat; the record names it under seatsNotRun, adds no status line, does not park
    s = _session(tmp_path, {"code-reviewer": dict(SEAT), "grounding-seat": dict(SEAT)})
    rec, fake = _record(tmp_path, s)
    assert rec["seatsNotRun"] == [NOT_RUN]
    assert rec["missingReviews"] == []
    assert rec["parked"] is False and rec["status"] == "reviewed", rec["whatIsMissing"]
    assert "Not run: grounding-seat" in fake.marked()[0]["body"]


def test_a_hand_written_account_writes_the_same_entry_as_the_drivers(tmp_path):
    # axis: a hand-written account carrying the same reviewer row produces the identical seatsNotRun entry
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    driven, _ = _record(tmp_path / "a", _session(tmp_path / "a", {"code-reviewer": dict(SEAT), "grounding-seat": dict(SEAT)}))
    out, fake = _hand(tmp_path / "b", _hand_reviewers(_grounding()))
    assert out["ok"], out
    by_hand = rr.read(7, readers=fake.readers())
    assert by_hand["seatsNotRun"] == driven["seatsNotRun"] == [NOT_RUN]
    assert by_hand["parked"] is False and by_hand["missingReviews"] == []


@pytest.mark.parametrize("row,key", [
    ({"name": "code-reviewer"}, "reviewers[1].notRunReason"),
    ({"notRunReason": "no-such-reason"}, "reviewers[1].notRunReason"),
    ({"notRunReason": ["no-loop-phase"]}, "reviewers[1].notRunReason"),
    ({"ran": True}, "reviewers[1].notRunReason"),
    ({"planned": False}, "reviewers[1].notRunReason"),
    ({"runDir": "/failed/grounding-seat"}, "reviewers[1].notRunReason"),
    ({"commit": HEAD}, "reviewers[1].notRunReason"),
], ids=["other-seat", "unknown-token", "unhashable-token", "ran", "unplanned", "run-dir", "commit"])
def test_the_not_run_token_is_refused_anywhere_but_on_a_never_run_grounding_seat(tmp_path, row, key):
    # axis: the token labels only grounding-seat, planned, never run, no attempted run directory, no commit
    out, fake = _hand(tmp_path, _hand_reviewers(_grounding(**row)))
    assert out == {"ok": False, "reason": "review-account-invalid", "detail": key}
    assert fake.marked() == []


def test_a_grounding_seat_with_an_attempted_run_and_no_token_still_parks(tmp_path):
    # axis: an attempted run (a run directory) with no token stays a missing review and parks
    failed = {"/failed/grounding-seat": (None, "the run failed")}
    out, fake = _hand(tmp_path, _hand_reviewers(_grounding(runDir="/failed/grounding-seat", notRunReason=None)), failed)
    rec = rr.read(7, readers=fake.readers())
    assert out["ok"] and rec["parked"] is True
    assert [m["name"] for m in rec["missingReviews"]] == ["grounding-seat"]
    assert "seatsNotRun" not in rec


def test_a_grounding_seat_without_the_token_is_today_a_missing_review(tmp_path):
    # axis: no notRunReason (absent) keeps today's behaviour: a planned seat that did not run is missing and parks
    row = _grounding()
    del row["notRunReason"]
    out, fake = _hand(tmp_path, _hand_reviewers(row))
    rec = rr.read(7, readers=fake.readers())
    assert out["ok"] and rec["parked"] is True
    assert [m["name"] for m in rec["missingReviews"]] == ["grounding-seat"]
    assert "seatsNotRun" not in rec and rec["status"] == "not-reviewed"


def test_a_session_that_composes_no_grounding_seat_has_no_row_and_no_key(tmp_path):
    # axis: no grounding seat in any panel round's map means no grounding row and no seatsNotRun key
    s = _session(tmp_path, {"code-reviewer": dict(SEAT)})
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    assert [v["name"] for v in account["reviewers"]] == ["code-reviewer (round 1)"]
    rec, _ = _record(tmp_path, s)
    assert "seatsNotRun" not in rec


def test_a_grounding_seat_already_among_the_journaled_rows_gets_no_second_row(tmp_path):
    # axis: a composed grounding seat the journal already names is not listed twice
    s = _session(tmp_path, {"code-reviewer": dict(SEAT), "grounding-seat": dict(SEAT)})
    s.seat("grounding-seat", head=HEAD)
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    assert [v["name"] for v in account["reviewers"] if v["name"].startswith("grounding-seat")] == ["grounding-seat (round 1)"]


def test_an_unfilled_grounding_seat_is_named_with_unfilled_vendor_and_model(tmp_path):
    # axis: an unfilled grounding seat still gets the row and the token, with the unfilled vendor and model
    s = _session(tmp_path, {"code-reviewer": dict(SEAT), "grounding-seat": dict(UNFILLED_SEAT)})
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    row = next(v for v in account["reviewers"] if v["name"] == "grounding-seat")
    assert (row["vendor"], row["model"], row["notRunReason"]) == ("unfilled", "unfilled", "no-loop-phase")


def test_a_session_with_no_rounds_reads_round_ones_map(tmp_path):
    # axis: with no rounds recorded, round 1's governing map decides whether the grounding seat is composed
    s = _session(tmp_path, {"code-reviewer": dict(SEAT), "grounding-seat": dict(SEAT)}, rounds={})
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    assert [v["name"] for v in account["reviewers"] if v["name"] == "grounding-seat"] == ["grounding-seat"]


def test_the_sheet_history_shows_the_seat_not_run_and_makes_no_card(tmp_path):
    # axis: the sheet's history carries one line per seatsNotRun entry; no card, and a record without the key builds as before
    records, advisor = bundle(BIG)
    plain = build(records, advisor)
    assert "seatsNotRun" not in records[0]
    records[0]["seatsNotRun"] = [NOT_RUN]
    shown = build(records, advisor)
    line = pr_sheet._fill(WORDS["historyNotRun"], name="grounding-seat", why=WHY)
    assert line in shown["prSheet"]["history"] and line not in plain["prSheet"]["history"]
    assert [l for l in shown["prSheet"]["history"] if l != line] == plain["prSheet"]["history"]
    assert {k: v for k, v in shown["prSheet"].items() if k != "history"} == {k: v for k, v in plain["prSheet"].items() if k != "history"}
    assert {k: v for k, v in shown.items() if k != "prSheet"} == {k: v for k, v in plain.items() if k != "prSheet"}


@pytest.mark.parametrize("bad", [[{"name": "", "why": WHY}], [{"name": "grounding-seat"}], ["grounding-seat"], "grounding-seat", {}])
def test_a_malformed_seats_not_run_is_a_problem(bad):
    # axis: a seatsNotRun that is not a list of {name, why} text entries is refused, never passed silently
    records, advisor = bundle(BIG)
    records[0]["seatsNotRun"] = copy.deepcopy(bad)
    assert any("its seats not run are malformed" in p for p in problems_of(records, advisor))
