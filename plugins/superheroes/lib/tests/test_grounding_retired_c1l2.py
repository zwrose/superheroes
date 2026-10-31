"""#2206 C1-L2: the grounding seat is retired. No roster composes it, a new review record carries no not-run seat
line, and an earlier record or persisted seat map that still names it keeps reading.

Bite-proof record: c1l2_wo2_not_run_retired (the records and the account), c1l2_wo2_move_up_roster_filter (the
persisted roster), c1l2_wo2_reviewer_pin_tier (the codex role-pin tier).
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import liveness_cache  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import seat_map as SM  # noqa: E402

from test_pr_sheet import BIG, SMALL, bundle, build, problems_of  # noqa: E402
from test_review_record import NO_READING, SEAT_MAP  # noqa: E402
from test_review_record_session import CODEX, HEAD, Fake, Session, extras, send  # noqa: E402
from test_seat_map import THREE_VENDORS, _PAYMENTS, _compose, _docs_commit, _project  # noqa: E402

SEAT = {"vendor": "codex", "model": CODEX}
UNFILLED_SEAT = {"vendor": None, "model": None, "effort": None, "tier": "deep", "family": None, "source": "unfilled"}
OLD_ROSTER = ["code-reviewer", "test-role", "grounding-seat"]


def _session(tmp_path, seats):
    """A finished loop session: code-reviewer journaled as ran on the final commit, the round-1 map an older plugin
    composed, its roster still naming the retired seat."""
    receipt = {"round": "1", "map": {"seats": seats, "roster": OLD_ROSTER, "makerFamilies": ["anthropic"]}}
    s = Session(tmp_path, seatMapReceipts=[receipt])
    s.seat("code-reviewer", head=HEAD)
    return s


def _hand(tmp_path, reviewers):
    """Write a hand-written account through the writer; returns (the write result, the Fake)."""
    fake = Fake()
    acct = {"schema": "review-account/1", "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big", "finalCommit": HEAD,
            "ci": "green", "reviewers": reviewers, "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"],
            "makers": [{"family": "anthropic"}]}
    path = tmp_path / "account.json"
    path.write_text(json.dumps(acct))
    return rr.write(str(path), str(tmp_path), fake.readers()), fake


def _row(name, **over):
    return {"name": name, "planned": True, "ran": False, "vendor": "codex", "model": CODEX,
            "commit": None, "runDir": None, **over}


def _code_row():
    return _row("code-reviewer", ran=True, commit=HEAD, runDir="/run/code-reviewer")


# --- (a) a new record carries no not-run seat line ---------------------------------------------------------------

@pytest.mark.parametrize("grounding", [dict(SEAT), dict(UNFILLED_SEAT)], ids=["seated", "unfilled"])
def test_a_driver_built_record_from_a_map_naming_the_retired_seat_has_no_not_run_line_and_does_not_park(tmp_path, grounding):
    # axis: a map whose roster and seats still name grounding-seat adds no seatsNotRun key, no reviewer row, no Not run line, and no park
    s = _session(tmp_path, {"code-reviewer": dict(SEAT), "grounding-seat": grounding})
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    assert [v["name"] for v in account["reviewers"]] == ["code-reviewer (round 1)"]
    assert not any("notRunReason" in v for v in account["reviewers"])
    fake = Fake()
    out = send(tmp_path, s.save(), fake)
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert "seatsNotRun" not in rec
    assert not any("grounding-seat" in v["name"] for v in rec["reviewers"])
    assert rec["missingReviews"] == []
    assert rec["parked"] is False and rec["status"] == "reviewed", rec["whatIsMissing"]
    assert "Not run:" not in rr.render(rec)
    assert "Not run:" not in fake.marked()[0]["body"]


# --- (b) the account refuses the retired field on any row ---------------------------------------------------------

@pytest.mark.parametrize("value", ["no-loop-phase", "no-such-reason", "", ["no-loop-phase"], 0, False],
                         ids=["old-token", "unknown-token", "empty", "list", "zero", "false"])
@pytest.mark.parametrize("which", [0, 1, 2])
def test_a_not_run_reason_on_any_reviewer_row_is_refused(tmp_path, which, value):
    # axis: notRunReason is no part of the account, on the old seat's row or any other, set to any value but null
    rows = [_code_row(), _row("security-reviewer"), _row("grounding-seat")]
    rows[which] = dict(rows[which], notRunReason=value)
    out, fake = _hand(tmp_path, rows)
    assert out == {"ok": False, "reason": "review-account-invalid", "detail": f"reviewers[{which}].notRunReason"}
    assert fake.marked() == []


def test_a_hand_written_account_with_a_never_run_seat_is_a_missing_review_not_a_not_run_line(tmp_path):
    # axis: a planned seat that did not run parks as a missing review, whatever its name; nothing labels it "not run"
    out, fake = _hand(tmp_path, [_code_row(), _row("grounding-seat")])
    rec = rr.read(7, readers=fake.readers())
    assert out["ok"] and rec["parked"] is True
    assert [m["name"] for m in rec["missingReviews"]] == ["grounding-seat"]
    assert "seatsNotRun" not in rec and "Not run:" not in rr.render(rec)


# --- (c) an earlier record still reads, and its sheet shows no not-run line -----------------------------------------

EARLIER_NOT_RUN = [{"name": "grounding-seat", "reason": "no-loop-phase",
                    "why": "no loop phase runs it, so no reviewer checked the PR body's claims"}]


def _earlier_record():
    """The small-lane fixture record (it misses no review), as an older writer left it: carrying the seatsNotRun list."""
    records, advisor = bundle(SMALL)
    assert "seatsNotRun" not in records[0] and records[0]["missingReviews"] == []
    records[0]["seatsNotRun"] = copy.deepcopy(EARLIER_NOT_RUN)
    return records, advisor


def test_an_earlier_record_with_seats_not_run_builds_and_its_sheet_names_no_such_line():
    # axis: a stored record carrying seatsNotRun still builds clean; the sheet says nothing of the seat or of a run that did not happen
    records, advisor = _earlier_record()
    shown = build(records, advisor)
    plain = build(*bundle(SMALL))
    text = json.dumps(shown).lower()
    assert "grounding" not in text and "did not run" not in text
    assert shown == plain


@pytest.mark.parametrize("bad", [[{"name": "", "why": "w"}], [{"name": "grounding-seat"}], ["grounding-seat"], "grounding-seat", {}])
def test_a_malformed_seats_not_run_is_a_problem(bad):
    # axis: a seatsNotRun that is not a list of {name, why} text entries is refused, never passed silently
    records, advisor = bundle(BIG)
    records[0]["seatsNotRun"] = copy.deepcopy(bad)
    assert any("its seats not run are malformed" in p for p in problems_of(records, advisor))


# --- (d) no roster on any path composes a grounding seat ----------------------------------------------------------

def _is_lens_only(roster_or_seats):
    return set(roster_or_seats) <= set(SM.LENS_SEATS)


def test_the_retired_seat_is_gone_from_the_seat_vocabulary():
    # axis: the known seats, the base roster and the panel roster hold lens seats only, and no constant names the retired seat
    assert SM.KNOWN_SEATS == SM.LENS_SEATS
    assert _is_lens_only(SM.BASE_ROSTER) and _is_lens_only(SM.PANEL_ROSTER)
    assert not hasattr(SM, "GROUNDING_SEAT")
    assert "grounding-seat" not in SM.DEFAULT_TIER_BY_SEAT and "grounding-seat" not in SM.MAKER_EXCLUDED_SEATS


@pytest.mark.parametrize("basis", [{"floor": None}, {"floor": "full"}, None, {}, "x"],
                         ids=["no-floor", "floor", "none", "empty", "string"])
def test_roster_for_composes_no_grounding_seat_on_any_lane_basis(basis):
    # axis: roster_for names a lens seat only, whichever shape of lane basis it is given
    roster = SM.roster_for(basis)
    assert roster and _is_lens_only(roster)


@pytest.mark.parametrize("live", [["claude", "codex"], THREE_VENDORS], ids=["two-vendors", "three-vendors"])
@pytest.mark.parametrize("author", ["xai", "anthropic", None])
@pytest.mark.parametrize("basis", [{"floor": None}, None], ids=["no-floor", "risky"])
def test_build_seats_lens_seats_only_and_records_no_grounding_degradation(live, author, basis):
    # axis: build over live vendors names no seat outside LENS_SEATS and no grounding-* constraint, whichever family is unknown
    m = SM.build(SM.roster_for(basis), live, author, SM.seed_from(2206, None))
    assert _is_lens_only(m["roster"]) and _is_lens_only(m["seats"])
    assert not [d for d in m["degradations"] if str(d.get("constraint", "")).startswith("grounding-")]
    default = SM.build(None, live, author, 0)
    assert _is_lens_only(default["roster"]) and _is_lens_only(default["seats"])


@pytest.mark.parametrize("live", ["claude,codex", "claude,codex,cursor"], ids=["two-vendors", "three-vendors"])
def test_compose_composes_no_grounding_seat_inside_or_outside_a_risk_area(tmp_path, monkeypatch, capsys, live):
    # axis: the compose command, on a full-floor and on a no-floor lane call, names no seat outside LENS_SEATS
    repo, base, head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    parent, docs_head = _docs_commit(repo)
    for got in (_compose(capsys, repo, base=base, head=head, live=live),
                _compose(capsys, repo, base=parent, head=docs_head, live=live)):
        assert got["roster"] and _is_lens_only(got["roster"]) and _is_lens_only(got["seats"])
        assert not [d for d in got["degradations"] if str(d.get("constraint", "")).startswith("grounding-")]


# --- (e) a persisted map that still names the retired seat --------------------------------------------------------

def _old_shape_map():
    """A seat map an older plugin wrote for a no-floor lane: its roster names grounding-seat, which was left unfilled."""
    seats = {n: dict(SEAT_MAP["seats"][n]) for n in ("code-reviewer", "test-role")}
    seats["grounding-seat"] = {"source": "unfilled", "family": None, "vendor": None}
    return dict(SEAT_MAP, roster=list(OLD_ROSTER), seats=seats, laneBasis={"floor": None})


def test_reading_next_ignores_a_retired_member_of_a_persisted_roster():
    # axis: an unfilled grounding-seat in a persisted roster does not park the lane; the panel seats decide
    out = rr.reading_next([NO_READING, NO_READING], _old_shape_map(), ["anthropic"])
    assert out["next"] == "move-up", out


def test_reading_next_still_parks_on_an_unfilled_member_that_is_known():
    # axis: the filter drops only retired names; an unfilled lens seat still parks
    sm = _old_shape_map()
    sm["seats"]["test-role"] = {"source": "unfilled", "family": None, "vendor": None}
    out = rr.reading_next([NO_READING, NO_READING], sm, ["anthropic"])
    assert out == {"next": "park", "reason": "a roster seat in the seat map is unfilled"}


def test_reading_next_with_only_retired_members_has_no_roster():
    # axis: a roster that names no known seat reads as no roster
    sm = dict(_old_shape_map(), roster=["grounding-seat"])
    out = rr.reading_next([NO_READING, NO_READING], sm, ["anthropic"])
    assert out == {"next": "park", "reason": "the seat map has no roster"}


def test_a_saved_pin_under_the_retired_seat_is_an_unknown_seat_pin_not_a_crash():
    # axis: an owner's saved pin keyed grounding-seat falls to the existing unknown-seat degradation
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins={"grounding-seat": {"vendor": "codex"}})
    assert {"constraint": "pin", "reason": "pin for unknown seat grounding-seat"} in m["degradations"]
    assert "grounding-seat" not in m["seats"]


def test_reviewer_stays_a_codex_role_pin_tier_after_the_retired_seat_took_its_default_with_it():
    # axis: a seat map's codexRolePins keyed reviewer still validates; the backfill downgrade tier keeps it a pin tier
    assert "reviewer" in SM.panel_pin_tiers() and "reviewer-deep" in SM.panel_pin_tiers()
    pins = {"reviewer": "gpt-5.6-sol", "reviewer-deep": "gpt-5.6-sol"}
    assert SM._read_codex_role_pins({"codexRolePins": pins}) == (pins, True)
    assert SM._read_codex_role_pins({"codexRolePins": {"reviewer": "gpt-5.6-sol", "no-such-role": "gpt-5.6-sol"}}) == (None, False)
    built = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "xai", 0)
    bare = {k: v for k, v in built.items() if k not in ("liveCells", "liveCellsSource")}
    cells, source = SM._live_cells_fields_for_receipt(dict(bare, codexRolePins=pins))
    assert source == liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED and cells
    assert SM.to_receipt(dict(bare, codexRolePins=pins), "xai")["codexRolePins"] == pins
    cells, source = SM._live_cells_fields_for_receipt(dict(bare, codexRolePins=dict(pins, **{"no-such-role": "x"})))
    assert source == liveness_cache.LIVE_CELLS_SOURCE_UNPROBED and cells == []


def test_the_backfill_tier_is_in_play_for_a_roster_with_no_reviewer_tier_seat():
    # axis: a no-floor roster seats only reviewer-deep, yet compose can backfill a seat at reviewer, so that tier's codex cell is probed and synthesized live
    roster = SM.roster_for({"floor": None})
    assert roster and {SM.DEFAULT_TIER_BY_SEAT[s] for s in roster} == {"reviewer-deep"}
    model, effort, _pin = SM._cell("reviewer", "codex", None)
    assert model is not None
    assert ("codex", model, effort) in SM._synthesize_live_cells(["codex"], roster, None)
    assert [model, effort] in SM.reachable_configs(["codex"], None, roster)["codex"]


def test_the_backfill_tier_follows_the_rosters_pins_in_reachable_configs():
    # axis: the backfill tier's cells follow the roster's pins - all seats honorably pinned narrow it to the pinned vendor, any rotating seat rotates it across every vendor
    roster = SM.roster_for({"floor": None})
    vendors = ["codex", "cursor"]
    codex_backfill = list(SM._cell("reviewer", "codex", None)[:2])
    # the codex reviewer cell differs from its reviewer-deep cell, so it discriminates; cursor's two cells are identical, so for cursor only presence/emptiness is asserted
    assert SM._cell("reviewer", "codex", None) != SM._cell("reviewer-deep", "codex", None)
    assert SM._cell("reviewer", "cursor", None) == SM._cell("reviewer-deep", "cursor", None)
    assert len(roster) > 1
    unpinned = SM.reachable_configs(vendors, None, roster)
    assert codex_backfill in unpinned["codex"] and unpinned["cursor"]
    all_codex = SM.reachable_configs(vendors, {s: {"vendor": "codex"} for s in roster}, roster)
    assert codex_backfill in all_codex["codex"] and all_codex["cursor"] == []
    mixed = SM.reachable_configs(vendors, {roster[0]: {"vendor": "codex"}}, roster)
    assert codex_backfill in mixed["codex"] and mixed["cursor"]
