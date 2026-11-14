"""Tests for issue 2452: an identifier that is present but empty never counts as a match.

Each site reads an identifier that can be present and empty (or not a string): the setup-record
environment in `cloud_parked._lapses`, the event `ref` in `cloud_recover._push_time`, the row `id` in
the launcher's `_listing_row_ok`, the row `environment_id` in `_page_created_by_environment`, and a
lane's `cloudEnvironment` and `cloudSessionId` in the original-session check. An empty one is unread:
it matches nothing, and the site refuses or skips exactly as it does for an identifier it cannot read.
A real identifier still matches, and an absent environment on `_lapses` (None, the no-lane caller)
keeps its behaviour. The fixtures are the ones the existing tests for each site use, imported not copied.
"""
import pytest

import cloud_parked as CP
import cloud_recover as CRV
import launch_ledger as ll

from test_adopt_original_session import (  # noqa: F401  (_no_account_reading is an autouse fixture)
    LANE_ID,
    SESSION_ID,
    SESSION_TITLE,
    TOKEN_LIVE,
    _adopt,
    _no_account_reading,
    _page_of,
    _proceeds,
    _refused_unread,
    _seed_lane,
    _unrelated_row,
    _write_listing,
)
from test_cloud_parked import ENVIRONMENT, PAST, w  # noqa: F401  (w is a fixture)
from test_cloud_recover import BRANCH, REPO, Gh, _at, _event, _stamp
from test_launcher import L
from test_launcher_cloud import (  # noqa: F401  (_isolated is an autouse fixture)
    _assert_refused_cloud_lane,
    _cloud_repo,
    _isolated,
)

NEWER = "2026-10-24T13:00:00.000000Z"  # after the seeded lane started (2026-10-24T12:00:00Z) by more than the skew allowance
SHA = "a" * 40


# --- O-4: cloud_parked._lapses ------------------------------------------------------------


def test_d1_an_empty_environment_reads_no_lapse_date_even_when_a_record_has_one(w):
    # axis: an environment that is present but empty is unread and matches no record — see bite-proof record i2452_empty_ids
    assert CP._lapses(w.repo, w.env, None, ENVIRONMENT) == PAST  # the record exists and has a date
    assert CP._lapses(w.repo, w.env, None, "") is None


@pytest.mark.parametrize("environment", [5, ["env"], {}, False], ids=["int", "list", "dict", "false"])
def test_d1_a_non_string_environment_reads_no_lapse_date(w, environment):
    # axis: an environment that is not a string is unread and matches no record — see bite-proof record i2452_empty_ids
    assert CP._lapses(w.repo, w.env, None, environment) is None


def test_d2_an_empty_environment_with_no_record_reads_no_lapse_date(w):
    assert CP._lapses(w.repo, w.env, None, "", account_id="acct-without-any-record") is None


def test_d3_a_named_environment_reads_its_record_and_no_environment_reads_any(w):
    assert CP._lapses(w.repo, w.env, None, ENVIRONMENT) == PAST  # healthy sibling: the record names it
    assert CP._lapses(w.repo, w.env, None, "env-another") is None  # another environment's record is not this one's
    assert CP._lapses(w.repo, w.env, None, None) == PAST  # the no-lane caller: unchanged


# --- O-5: cloud_recover._push_time --------------------------------------------------------


def _push_events(events):
    gh = Gh()
    gh.activity[BRANCH] = events
    return gh


def test_d4_a_push_event_with_no_ref_gives_no_push_time():
    # axis: an event supplies the push time only when its ref is the branch's own; a missing ref does not — see bite-proof record i2452_empty_ids
    event = _event(BRANCH, SHA, _stamp(9, 55))
    del event["ref"]
    assert CRV._push_time(REPO, BRANCH, SHA, {}, _push_events([event])) is None


@pytest.mark.parametrize("ref", ["", None, 7, "refs/heads/other"], ids=["empty", "null", "not-a-string", "other-branch"])
def test_d4_a_push_event_whose_ref_is_empty_or_not_the_branchs_gives_no_push_time(ref):
    # axis: an event supplies the push time only when its ref is the branch's own; an empty, null, non-string or other ref does not — see bite-proof record i2452_empty_ids
    event = dict(_event(BRANCH, SHA, _stamp(9, 55)), ref=ref)
    assert CRV._push_time(REPO, BRANCH, SHA, {}, _push_events([event])) is None


def test_d4_a_push_event_with_the_branchs_own_ref_gives_its_time():
    events = [_event(BRANCH, "f" * 40, _stamp(9, 59)), _event(BRANCH, SHA, _stamp(9, 55))]
    assert CRV._push_time(REPO, BRANCH, SHA, {}, _push_events(events)) == _at(9, 55)


# --- O-6: launcher._listing_row_ok --------------------------------------------------------


def test_d5_a_listing_row_with_an_empty_id_is_not_ok():
    # axis: a row whose id is empty is not a recorded host shape — see bite-proof record i2452_empty_ids
    assert L._listing_row_ok({"id": ""}) is False
    assert L._listing_row_ok({"id": SESSION_ID}) is True


def test_d5_a_listing_holding_a_row_with_an_empty_id_refuses_listing_shape(tmp_path):
    # axis: a listing with a row whose id is empty is not a recorded host shape, so the check refuses unread — see bite-proof record i2452_empty_ids
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    listing = _write_listing(tmp_path, _page_of([{"id": ""}]))
    result, calls = _adopt(repo, tmp_path, listing)
    _refused_unread(repo, result, calls, "listing-shape")


def test_d5_a_listing_row_with_a_real_id_still_passes_the_shape_gate(tmp_path):
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    listing = _write_listing(tmp_path, _page_of([{"id": SESSION_ID}]))
    result, calls = _adopt(repo, tmp_path, listing)
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert calls == []


# --- O-7: launcher._page_created_by_environment ------------------------------------------


def test_d6_a_row_with_an_empty_environment_id_is_left_out_of_the_map():
    # axis: a row whose environment_id is empty is left out of the map, like a row with none — see bite-proof record i2452_empty_ids
    empty = _unrelated_row(NEWER, "session_01Empty00000000000000", environment_id="")
    real = _unrelated_row("2026-10-24T12:30:00.000000Z", "session_01Real000000000000000", environment_id="env-1")
    got = L._page_created_by_environment([_page_of([empty, real])])
    assert "" not in got
    assert got == {"env-1": L._listing_created_ts(real)}


# --- the lane side of the same absence proof ----------------------------------------------


def _fold_lane_with(monkeypatch, **fields):
    """The ledger fold with the seeded lane's fields replaced (the ledger itself accepts no empty id)."""
    real_fold = ll.fold

    def fold(records):
        folded = real_fold(records)
        if LANE_ID in folded["launches"]:
            folded["launches"][LANE_ID].update(fields)
        return folded

    monkeypatch.setattr(ll, "fold", fold)


def test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_by_rows_with_an_empty_environment_id(
    tmp_path, monkeypatch,
):
    # axis: a lane whose cloudEnvironment is empty proves nothing by absence, even against a row whose environment_id is empty too — see bite-proof record i2452_empty_ids
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _fold_lane_with(monkeypatch, cloudEnvironment="")
    rows = [_unrelated_row(NEWER, environment_id="")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_whatever_the_map_holds(
    tmp_path, monkeypatch,
):
    # axis: a lane whose cloudEnvironment is empty proves nothing by absence on its own, even when the by-environment map holds an empty key (the map's own skip is a second guard that shields the test above) — see bite-proof record i2452_empty_ids
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _fold_lane_with(monkeypatch, cloudEnvironment="")
    newer = L._listing_created_ts(_unrelated_row(NEWER))
    monkeypatch.setattr(L, "_page_created_by_environment", lambda pages: {"": newer})
    rows = [_unrelated_row(NEWER, environment_id="")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_d7_a_lane_with_a_real_cloud_environment_is_still_proven_gone(tmp_path):
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [_unrelated_row(NEWER, environment_id="env-1")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _proceeds(result, calls)


def test_d8_a_lane_with_an_empty_session_id_is_never_proven_gone(tmp_path, monkeypatch):
    # axis: a lane whose cloudSessionId is empty is unconfirmed, so absence never proves it gone — see bite-proof record i2452_empty_ids
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _fold_lane_with(monkeypatch, cloudSessionId="")
    rows = [_unrelated_row(NEWER, "session_01Newer00000000000000", "env-1")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_d8_a_lane_with_an_empty_session_id_is_matched_by_title(tmp_path, monkeypatch):
    # axis: a lane whose cloudSessionId is empty is matched by its session name, never by the empty id — see bite-proof record i2452_empty_ids
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _fold_lane_with(monkeypatch, cloudSessionId="")
    rows = [
        _unrelated_row(NEWER, "session_01Newer00000000000000", "env-1"),
        {
            "id": "session_01RetitledLive000000000", "title": SESSION_TITLE,
            "session_status": "SESSION_STATUS_RUNNING",
            "status_bucket": "SESSION_STATUS_BUCKET_WORKING",
            "created_at": "2026-10-24T11:59:30.000000Z", "environment_id": "env-1",
        },
    ]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert [s["launchId"] for s in result["originalSessions"]] == [LANE_ID]
    assert calls == []
