"""Tests for the launcher's refusal of an adoption whose original cloud builder is still live (issue #2119).

A premise that carries `adoptsBranch` reaches no reservation, worktree, cloud command or spawn while an
earlier cloud lane for the same issue has a session the recorded host listing shows live, and none when
that cannot be decided. Everything else refuses `adopt-original-session-live` or
`adopt-original-session-unread` before anything is spent. Nothing here touches the network: the
repositories are throwaway, with a bare remote under tmp_path for the cloud path, and the host listings
are the recorded files under fixtures/cloud_sessions.
"""
import calendar
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import cloud_recover as CR
import cloud_relay
import launch_ledger as ll

from test_launcher import (
    L,
    _all_checks,
    _head_sha,
    _make_spawn_fn,
    _valid_premise,
)
from test_launcher_cloud import (  # noqa: F401  (_isolated is an autouse fixture)
    _assert_refused_cloud_lane,
    _cloud_repo,
    _fake_spawn,
    _git,
    _isolated,
    _launch,
)

TOKEN_LIVE = "adopt-original-session-live"
TOKEN_UNREAD = "adopt-original-session-unread"
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cloud_sessions")
LANE_ID = "lane-a"
SESSION_ID = "session_01FixtureLane0000000000"
SESSION_TITLE = "issue-656-fixturelane000001"
HEX40 = "c" * 40
# The seeded lane started at a fixed instant (2026-10-24T12:00:00Z) so the recorded fixture rows,
# created at 11:13:25Z, are older than it whatever the clock reads when the suite runs.
LANE_STARTED_TS = calendar.timegm((2026, 10, 24, 12, 0, 0))
# The environment the recorded newest-page row (list_page_recorded_newest.json) was created in.
RECORDED_ENVIRONMENT = "env_01UTDZ5skRKJT1PhMdo3k936"


def _fixture(name):
    return os.path.join(FIXTURES, name)


def _write_listing(tmp_path, value, name="listing.json"):
    path = tmp_path / name
    path.write_text(value if isinstance(value, str) else json.dumps(value))
    return str(path)


@pytest.fixture
def first_pr(monkeypatch):
    """Replace the read of the adopted branch's first pull request time; returns `set(value)`, whose
    `.calls` lists every call made."""
    calls = []
    answer = []

    def read(root, branch, env):
        calls.append(branch)
        return answer[0] if answer else None

    def set_value(value):
        answer[:] = [value]
        return calls

    monkeypatch.setattr(L, "_adopted_branch_first_pr_fn", read)
    return set_value


def _seed_lane(
    repo, launch_id=LANE_ID, *, session_id=SESSION_ID, title=SESSION_TITLE, outcome="handback",
    issue=656, environment="env-1", premise_extra=None,
):
    """An earlier cloud lane for the issue that started a session, ended with `outcome` (None: still running)."""
    assert ll.append(repo, {
        "event": "reserved", "launchId": launch_id, "ts": LANE_STARTED_TS - 60, "schema": ll.SCHEMA,
        "batchId": "wave-test", "repoId": ll.repo_identity(repo), "issue": issue,
        "surfaces": ["plugins/x-%s" % launch_id],
        "premise": dict({"issue": issue, "baseCommit": HEX40}, **(premise_extra or {})),
        "preflight": {}, "argv": [], "doctrineDigest": "abc123", "model": "test-model",
        "place": ll.PLACE_CLOUD, "cloudEnvironment": environment, "pluginVersion": "1.2.3",
        "configDir": "/cfg/acct",
    })
    started = {
        "event": "started", "launchId": launch_id, "ts": LANE_STARTED_TS, "schema": ll.SCHEMA,
        "attempt": 1, "pid": 999999999, "logPath": "/tmp/log", "errPath": "/tmp/err",
        "cloudSessionName": title, "cloudSessionUrl": "https://claude.ai/code/session_x",
    }
    if session_id is not None:
        started["cloudSessionId"] = session_id
    else:
        started["cloudSessionUnconfirmed"] = True
    assert ll.append(repo, started)
    if outcome is not None:
        assert ll.record_outcome(repo, launch_id, outcome, "ended")["ok"]


def _assess(repo, launch_id=LANE_ID, evidence="handover"):
    entry = {
        "verdict": "stopped", "evidence": evidence, "at": "2026-10-24T00:00:00Z",
        "stoppedAt": None, "handoverSha": HEX40,
    }
    assert CR._record(repo, "assessed", launch_id, entry)["ok"]


def _adoption(repo, branch=None):
    """An adoption premise that passes the head-on-base check: the checkout's head is its own base.

    The adopted branch is the checkout's own unless `branch` names another."""
    branch = branch or _git(repo, "symbolic-ref", "--short", "HEAD").strip()
    head = _head_sha(repo)
    return _valid_premise(repo, baseCommit=head, adoptsBranch=branch, adoptsHead=head)


def _adopt(repo, tmp_path, listing=None, branch=None):
    calls = []
    kwargs = {} if listing is None else {"cloud_sessions_file": listing}
    result = _launch(
        repo, tmp_path, _fake_spawn(calls=calls), premise=_adoption(repo, branch), **kwargs,
    )
    return result, calls


def _refused_unread(repo, result, calls, failed):
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
    assert result["failedRead"] == failed
    assert result["remedy"] == (
        L._ADOPT_ORIGINAL_REMEDY_STATE if failed in ("ledger", "recover-state")
        else L._ADOPT_ORIGINAL_REMEDY_UNREAD
    )
    assert calls == []


def _proceeds(result, calls):
    assert result["ok"] is True, result
    assert len(calls) == 1


# --- a live original builder refuses ------------------------------------------------------


def test_a_handed_back_builder_whose_session_the_host_shows_live_refuses(tmp_path):
    # axis: the field case — a handed-back builder still listed running refuses the adoption before spend
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"] == [{
        "launchId": LANE_ID, "cloudSessionName": SESSION_TITLE, "cloudSessionId": SESSION_ID,
        "sessionStatus": "SESSION_STATUS_RUNNING",
        "statusBucket": "SESSION_STATUS_BUCKET_REVIEW_READY",
    }]
    assert result["remedy"] == L._ADOPT_ORIGINAL_REMEDY_LIVE
    assert calls == []


def test_a_complete_listing_page_that_shows_the_session_running_refuses(tmp_path):
    # axis: a complete list page that holds the lane's running session refuses live
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_running.json"))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert result["originalSessions"][0]["statusBucket"] == "SESSION_STATUS_BUCKET_WORKING"
    assert calls == []


def test_a_session_failed_assessment_does_not_exempt_a_live_session(tmp_path):
    # axis: only a handover-stopped assessment exempts a lane; a session-failed one leaves the listing to decide
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _assess(repo, evidence="session-failed")
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_running.json"))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert calls == []


def test_a_matched_row_with_no_status_fields_is_live(tmp_path):
    # axis: a matched row whose status is unknown or absent is live, never gone
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    listing = _write_listing(tmp_path, {"data": [{"id": SESSION_ID}], "has_more": False})
    result, calls = _adopt(repo, tmp_path, listing)
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["sessionStatus"] is None
    assert result["originalSessions"][0]["statusBucket"] is None
    assert calls == []


def test_a_lane_whose_session_id_was_never_confirmed_matches_by_title(tmp_path):
    # axis: a lane with no confirmed session id is matched by its session name
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, session_id=None)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_running.json"))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["cloudSessionId"] is None
    assert calls == []


# --- a listing that cannot be read or that does not cover the lane refuses ----------------


def test_a_prior_cloud_lane_and_no_listing_refuses_not_given(tmp_path):
    # axis: an adoption over a lane that started a session with no listing given refuses unread
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_missing_listing_file_refuses_listing_file(tmp_path):
    # axis: a listing path that cannot be opened refuses unread
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, str(tmp_path / "no-such-listing.json"))
    _refused_unread(repo, result, calls, "listing-file")


def test_a_listing_that_is_not_json_refuses_listing_json(tmp_path):
    # axis: a listing that does not parse refuses unread
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, '{"data": ['))
    _refused_unread(repo, result, calls, "listing-json")


def test_a_listing_with_a_duplicate_key_refuses_listing_json(tmp_path):
    # axis: a duplicate key anywhere in the listing refuses unread, since the reader cannot say which won
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    text = (
        '{"data": [{"id": "%s", "session_status": "SESSION_STATUS_ARCHIVED", '
        '"session_status": "SESSION_STATUS_RUNNING"}], "has_more": false}' % SESSION_ID
    )
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, text))
    _refused_unread(repo, result, calls, "listing-json")


@pytest.mark.parametrize("shape", [
    [],
    {"data": "x"},
    {"id": 5},
    {"data": [{"id": SESSION_ID, "status_bucket": 7}], "has_more": False},
    {"data": [{"id": SESSION_ID, "archived": "yes"}], "has_more": False},
    {"data": [{"id": SESSION_ID}], "has_more": "no"},
    {"data": [{"title": "no id"}], "has_more": False},
    '"a string"',
], ids=[
    "empty-array", "data-not-a-list", "id-not-a-string", "status-bucket-not-a-string",
    "archived-not-a-bool", "has-more-not-a-bool", "row-without-id", "not-an-object",
])
def test_a_listing_that_is_not_a_host_shape_refuses_listing_shape(tmp_path, shape):
    # axis: a listing that is not a recorded host shape refuses unread
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, shape))
    _refused_unread(repo, result, calls, "listing-shape")


def test_a_page_with_more_to_read_that_lacks_the_lane_refuses_incomplete(tmp_path):
    # axis: absence from a page with has_more true proves nothing, so the lane is unproven
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_more.json"))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_a_get_session_result_for_another_session_refuses_incomplete(tmp_path):
    # axis: a get_session result covers only the session it returns, never one that is gone
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_unrelated.json"))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_two_complete_pages_that_lack_a_lane_refuse_incomplete(tmp_path):
    # axis: only exactly one complete page proves absence; an array of pages does not
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, "lane-a")
    _seed_lane(repo, "lane-b", session_id="session_01FixtureLaneB000000000", title="issue-656-fixturelane00000b")
    with open(_fixture("list_page_complete_archived.json")) as fh:
        lane_a_archived = json.load(fh)
    with open(_fixture("list_page_complete_without.json")) as fh:
        without = json.load(fh)
    listing = _write_listing(tmp_path, [lane_a_archived, without])
    result, calls = _adopt(repo, tmp_path, listing)
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == ["lane-b"]


def test_a_live_lane_wins_over_an_unproven_one(tmp_path):
    # axis: a live candidate refuses live even when another candidate is unproven in the same launch
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, "lane-a")
    _seed_lane(repo, "lane-b", session_id="session_01FixtureLaneB000000000", title="issue-656-fixturelane00000b")
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert [s["launchId"] for s in result["originalSessions"]] == ["lane-a"]
    assert calls == []


def _page_of(rows):
    return {"data": rows, "has_more": False}


def _unrelated_row(created_at, row_id="session_01Unrelated0000000000", environment_id=None):
    row = {"id": row_id, "title": "issue-1-other", "created_at": created_at}
    if environment_id is not None:
        row["environment_id"] = environment_id
    return row


def test_a_complete_page_whose_rows_are_all_older_than_the_lane_start_refuses_incomplete(tmp_path):
    # axis: a has_more-false page older than the lane start is a cursor-read last page, which proves nothing
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    listing = _write_listing(tmp_path, _page_of([_unrelated_row("2026-10-24T11:59:59.000000Z")]))
    result, calls = _adopt(repo, tmp_path, listing)
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_a_complete_page_whose_rows_are_out_of_created_order_refuses_incomplete(tmp_path):
    # axis: rows not newest-created first prove nothing about the page's span; the first row is newer than the lane start, so only the order check can refuse it
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [
        _unrelated_row("2026-10-24T13:00:00.000000Z", "session_01First000000000000000", environment_id="env-1"),
        _unrelated_row("2026-10-24T10:00:00.000000Z", "session_01Second00000000000000", environment_id="env-1"),
        _unrelated_row("2026-10-24T14:00:00.000000Z", "session_01Third000000000000000", environment_id="env-1"),
    ]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


@pytest.mark.parametrize("created_at", [
    "not-a-time", "2026-10-24T12:00:00", "2026-10-24T12:00:00+02:00", 12345, None,
], ids=["garbage", "no-zone", "non-utc-zone", "not-a-string", "null"])
def test_a_complete_page_with_an_unparseable_created_at_refuses_incomplete(tmp_path, created_at):
    # axis: a created_at that is not an ISO-8601 UTC time proves nothing
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [_unrelated_row("2026-10-24T13:00:00.000000Z"), _unrelated_row("x", "session_01Bad")]
    rows[1]["created_at"] = created_at
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")


def test_a_complete_page_with_no_created_at_refuses_incomplete(tmp_path):
    # axis: a row with no created_at proves nothing about the page's span
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    listing = _write_listing(tmp_path, _page_of([{"id": "session_01Unrelated0000000000"}]))
    result, calls = _adopt(repo, tmp_path, listing)
    _refused_unread(repo, result, calls, "listing-incomplete")


def test_an_empty_complete_page_refuses_incomplete(tmp_path):
    # axis: an empty page spans no instant, so absence from it proves nothing
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of([])))
    _refused_unread(repo, result, calls, "listing-incomplete")


def test_a_lane_with_no_started_time_is_never_proven_gone(tmp_path, monkeypatch):
    # axis: a candidate lane with no started timestamp proves nothing by absence
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    real_fold = ll.fold

    def fold_without_started_ts(records):
        folded = real_fold(records)
        for info in folded["launches"].values():
            info.pop("startedTs", None)
        return folded

    monkeypatch.setattr(ll, "fold", fold_without_started_ts)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_newer.json"))
    _refused_unread(repo, result, calls, "listing-incomplete")


def test_a_complete_page_with_a_row_newer_than_the_lane_start_proves_absence(tmp_path):
    # axis: an ordered page whose newest row is at or after the lane start spans its creation, so absence is proven
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [
        _unrelated_row("2026-10-24T13:00:00.000000Z", "session_01Newer00000000000000", "env-1"),
        _unrelated_row("2026-10-24T12:00:00.000000Z", "session_01AtStart0000000000000"),
        _unrelated_row("2026-10-24T09:00:00Z", "session_01Older00000000000000"),
    ]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _proceeds(result, calls)


def test_a_newer_row_from_another_environment_refuses_incomplete(tmp_path):
    # axis: absence is proven only by a row of the lane's own cloud environment, so another account's page proves nothing — see bite-proof record i2119_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [_unrelated_row("2026-10-24T13:00:00.000000Z", environment_id="env-other")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_a_newer_row_with_no_or_non_string_environment_refuses_incomplete(tmp_path):
    # axis: a row with no environment_id never counts as the absence proof, and a non-string one is not a listing shape — see bite-proof record i2119_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [_unrelated_row("2026-10-24T13:00:00.000000Z")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    rows[0]["environment_id"] = 7
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows), "bad.json"))
    _refused_unread(repo, result, calls, "listing-shape")


def test_a_row_only_300_seconds_after_the_lane_start_refuses_incomplete(tmp_path):
    # axis: a row inside the clock-skew allowance after the lane start cannot prove absence — see bite-proof record i2119_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    rows = [_unrelated_row("2026-10-24T12:05:00Z", environment_id="env-1")]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_an_unconfirmed_lane_with_a_retitled_live_session_is_never_proven_gone(tmp_path):
    # axis: a lane whose session id was never confirmed is matched by title only, so a live session under another title is not proven gone by a newer row of the same environment — see bite-proof record i2119_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, session_id=None)
    rows = [
        _unrelated_row("2026-10-24T13:00:00.000000Z", "session_01Newer00000000000000", "env-1"),
        {
            "id": "session_01RetitledLive000000000", "title": "Fix the launcher gate",
            "session_status": "SESSION_STATUS_RUNNING",
            "status_bucket": "SESSION_STATUS_BUCKET_WORKING",
            "created_at": "2026-10-24T11:59:30.000000Z", "environment_id": "env-1",
        },
    ]
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_a_lane_with_no_cloud_environment_is_never_proven_gone(tmp_path, monkeypatch):
    # axis: a candidate lane with no cloudEnvironment proves nothing by absence — see bite-proof record i2119_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    real_fold = ll.fold

    def fold_without_environment(records):
        folded = real_fold(records)
        if LANE_ID in folded["launches"]:
            folded["launches"][LANE_ID]["cloudEnvironment"] = None
        return folded

    monkeypatch.setattr(ll, "fold", fold_without_environment)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_newer.json"))
    _refused_unread(repo, result, calls, "listing-incomplete")


# --- healthy launches proceed -------------------------------------------------------------


def test_an_adoption_with_no_prior_cloud_lane_proceeds_without_a_listing(tmp_path):
    # axis: no earlier lane started a session, so no listing is needed and the launch goes ahead
    repo = _cloud_repo(tmp_path)
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_an_adoption_proceeds_when_a_complete_page_does_not_hold_the_session(tmp_path):
    # axis: a session absent from one complete page that reaches past the lane start is gone, and the launch goes ahead
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_newer.json"))
    _proceeds(result, calls)


def test_an_adoption_proceeds_when_the_session_is_archived(tmp_path):
    # axis: a session listed archived is not live, and the launch goes ahead
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_archived.json"))
    _proceeds(result, calls)


def test_an_adoption_proceeds_when_the_recorded_archived_session_is_listed(tmp_path):
    # axis: the archived spelling recorded from the live host (SESSION_STATUS_ARCHIVED, bucket COMPLETED) reads not live, and the launch goes ahead
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, session_id="session_01JrM7yEUSzgrgDkpqoPrA7e", title="issue-2118-2ae8a497deff24a2")
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_archived_recorded.json"))
    _proceeds(result, calls)


def test_a_recorded_newest_page_with_more_to_read_refuses_incomplete(tmp_path):
    # axis: the recorded row is in the lane's environment and created well past the lane start, so only has_more true can refuse it
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, environment=RECORDED_ENVIRONMENT)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_recorded_newest.json"))
    _refused_unread(repo, result, calls, "listing-incomplete")
    assert result["launchIds"] == [LANE_ID]


def test_the_recorded_newest_page_with_has_more_false_proves_absence(tmp_path):
    # axis: the same recorded row and lane with has_more false is a complete page that reaches past the lane start, so the session is gone and the launch goes ahead
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, environment=RECORDED_ENVIRONMENT)
    with open(_fixture("list_page_recorded_newest.json")) as handle:
        recorded = json.load(handle)
    listing = _write_listing(tmp_path, {"data": recorded["data"], "has_more": False})
    result, calls = _adopt(repo, tmp_path, listing)
    _proceeds(result, calls)


def test_a_live_cloud_lane_of_another_issue_does_not_hold_this_adoption(tmp_path):
    # axis: only lanes of this issue are candidates, so another issue's live lane (no outcome, its own surfaces, so only the issue scoping is under test) needs no listing — see bite-proof record i2119_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, "lane-other", issue=999, outcome=None)
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_an_adoption_proceeds_when_the_session_bucket_reads_failed(tmp_path):
    # axis: a session whose status bucket reads failed is not live, and the launch goes ahead
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_failed.json"))
    _proceeds(result, calls)


def test_an_adoption_proceeds_over_a_handover_stopped_lane_with_no_listing(tmp_path):
    # axis: a lane assess recorded stopped on a handover is exempt and needs no listing
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _assess(repo)
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_an_adoption_proceeds_over_a_lane_that_refused_at_intake_with_no_listing(tmp_path):
    # axis: a lane whose latest outcome is refusal built nothing, so its still-listed session is not an original builder
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, outcome="refusal")
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_a_launch_that_adopts_nothing_is_none_of_the_gates_business(tmp_path):
    # axis: without adoptsBranch the gate does not apply, whatever earlier cloud lanes exist
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _proceeds(result, calls)


# --- unreadable state refuses -------------------------------------------------------------


def test_an_unreadable_recover_state_with_a_handed_back_lane_refuses_recover_state(tmp_path):
    # axis: a recover state that cannot be read refuses unread while a lane still needs it
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    path = CR._state_path(repo, os.environ)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json at all")
    result, calls = _adopt(repo, tmp_path, _fixture("list_page_complete_without.json"))
    _refused_unread(repo, result, calls, "recover-state")


def test_an_unreadable_recover_state_does_not_matter_when_every_lane_refused_at_intake(tmp_path):
    # axis: the recover state is read only while a lane still needs it
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, outcome="refusal")
    path = CR._state_path(repo, os.environ)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json at all")
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_a_ledger_that_cannot_be_read_refuses_ledger(tmp_path, monkeypatch):
    # axis: a ledger that cannot be read refuses unread, since the earlier lanes are unknown
    repo = _cloud_repo(tmp_path)
    monkeypatch.setattr(L.ll, "read", lambda *args, **kwargs: {"state": "corrupt", "records": []})
    got = L._original_session_refusal(
        repo, 656, {"adoptsBranch": "feature/x"}, None, dict(os.environ),
    )
    assert got is not None
    reason, detail = got
    assert reason == TOKEN_UNREAD
    assert detail == {"failedRead": "ledger", "remedy": L._ADOPT_ORIGINAL_REMEDY_STATE}


def test_a_stamped_premise_without_adopts_branch_passes_without_reading_the_ledger(monkeypatch):
    # axis: a premise that adopts nothing is none of this check's business
    def boom(*args, **kwargs):
        raise AssertionError("the ledger must not be read")

    monkeypatch.setattr(L.ll, "read", boom)
    assert L._original_session_refusal(".", 656, {"baseCommit": HEX40}, None, {}) is None


# --- the local path and the command line --------------------------------------------------


def test_local_launch_over_a_prior_cloud_lane_with_no_listing_refuses_and_spawns_nothing(tmp_path):
    # axis: the refusal holds for a local launch too — no child is spawned
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    spawned = []
    delegate = _make_spawn_fn("sleep")

    def recording_spawn(*args, **kwargs):
        spawned.append(args)
        return delegate(*args, **kwargs)

    result = L.launch_build(
        repo, 656, _adoption(repo), _all_checks(), str(tmp_path / "logs"),
        spawn_fn=recording_spawn, settle_seconds=0.2,
    )
    assert result["ok"] is False
    assert result["reason"] == TOKEN_UNREAD
    assert result["failedRead"] == "listing-not-given"
    assert spawned == []


def test_the_launch_command_accepts_and_forwards_cloud_sessions_file(tmp_path, monkeypatch):
    # axis: the launch subparser takes --cloud-sessions-file and hands it to launch_build
    repo = _cloud_repo(tmp_path)
    checks_path = _write_listing(tmp_path, _all_checks(), "checks.json")
    premise_path = _write_listing(tmp_path, _valid_premise(repo), "premise.json")
    listing = _fixture("list_page_complete_without.json")
    forwarded = []

    def capture_launch_build(*args, **kwargs):
        forwarded.append(kwargs)
        return {"ok": False, "reason": "injected-stop", "launchId": "l-test"}

    monkeypatch.setattr(L, "launch_build", capture_launch_build)
    code = L.main([
        "launch", "--repo-root", repo, "--issue", "656", "--checks", checks_path,
        "--premise", premise_path, "--log-dir", str(tmp_path / "logs"),
        "--cloud-sessions-file", listing,
    ])
    assert code == 1
    assert forwarded and all(kw["cloud_sessions_file"] == listing for kw in forwarded)
    forwarded.clear()
    L.main([
        "launch", "--repo-root", repo, "--issue", "656", "--checks", checks_path,
        "--premise", premise_path, "--log-dir", str(tmp_path / "logs"),
    ])
    assert forwarded and all(kw["cloud_sessions_file"] is None for kw in forwarded)


def test_the_launch_command_refuses_an_adoption_over_a_live_original_and_spawns_nothing(
    tmp_path, monkeypatch, capsys,
):
    # axis: the shipped launch command, through the real launch guard, refuses live, accounts the refusal and spawns zero builders
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    spawns = []
    monkeypatch.setattr(L, "default_cloud_spawn", _fake_spawn(calls=spawns))
    # routing is not under test: pin it to a cloud placement so only the spawn boundary is replaced
    monkeypatch.setattr(
        L.launch_place, "route",
        lambda *a, **k: L.launch_place._placement(
            "cloud", True, "word", None, None, None, None, "env_01AbCdEf", None,
        ),
    )
    checks_path = _write_listing(tmp_path, _all_checks(), "checks.json")
    premise_path = _write_listing(tmp_path, _adoption(repo), "premise.json")
    code = L.main([
        "launch", "--repo-root", repo, "--issue", "656", "--checks", checks_path,
        "--premise", premise_path, "--log-dir", str(tmp_path / "logs"), "--place", "cloud",
        "--cloud-sessions-file", _fixture("list_page_complete_running.json"),
    ])
    assert code == 1
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert spawns == []


# --- the check counts only lanes that could still write the adopted branch ---------------


ADOPTED = "adopted/x"


def _branch(repo):
    return _git(repo, "symbolic-ref", "--short", "HEAD").strip()


def _adopted_repo(tmp_path):
    """A cloud repository whose remote also holds the adopted branch; the checkout's own branch stays
    on the remote, as a cloud launch requires, so only the adopted branch is ever deleted."""
    repo = _cloud_repo(tmp_path)
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/%s" % ADOPTED)
    return repo


def _delete_remote_branch(repo):
    _git(repo, "push", "-q", "origin", "--delete", ADOPTED)


def _utc_stamp(offset):
    return datetime.fromtimestamp(time.time() + offset, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _relay_records(monkeypatch, records):
    monkeypatch.setattr(
        cloud_relay, "fix_orders",
        lambda repo_root, *, env=None, include_unchecked=False: {"ok": True, "records": records},
    )


def test_a_lane_that_handed_back_before_the_branchs_first_pr_proceeds_with_no_listing(tmp_path, first_pr):
    # axis: a handed-back lane with no fix order since and a first pull request on the branch after the handback writes only another branch — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_a_first_pr_on_the_branch_before_the_handback_keeps_the_lane(tmp_path, first_pr):
    # axis: a pull request on the branch opened before the handback means the lane's own pull request may be on it, so the lane stays — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    first_pr(time.time() - 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID]


def test_a_first_pr_inside_the_clock_skew_allowance_keeps_the_lane(tmp_path, first_pr):
    # axis: a first pull request only seconds after the handback is inside the clock-skew allowance, so it proves nothing
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    first_pr(time.time() + 60)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_vet_not_ready_after_the_handback_keeps_the_lane(tmp_path, first_pr):
    # axis: a vet not-ready after the handback is a fix order sent since, so the lane may write the branch again — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    time.sleep(0.01)
    assert ll.amend(repo, LANE_ID, "vet", "not-ready", "x")["ok"]
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_vet_not_ready_recorded_during_the_first_pr_lookup_keeps_the_live_lane(tmp_path, monkeypatch):
    # axis: the ledger is read again after the slow first-pull-request lookup, so a vet not-ready recorded during it keeps the lane and the listing then shows it live — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    lookups = []

    def read_first_pr(root, branch, env):
        lookups.append(branch)
        time.sleep(0.01)
        assert ll.amend(root, LANE_ID, "vet", "not-ready", "x", env=env)["ok"]
        return time.time() + 3600

    monkeypatch.setattr(L, "_adopted_branch_first_pr_fn", read_first_pr)
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"))
    assert len(lookups) == 1
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert calls == []


def test_a_handover_recorded_during_the_first_pr_lookup_is_honoured(tmp_path, monkeypatch):
    # axis: the handover-stopped set is read again after the slow first-pull-request lookup, so a lane assess recorded stopped on a handover during it is exempt — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    lookups = []

    def read_first_pr(root, branch, env):
        lookups.append(branch)
        got = ll.read(root, env=env)
        terminal = ll.fold(got["records"])["launches"][LANE_ID]["terminalIndex"]
        handback = got["records"][terminal]["ts"]
        _assess(root)
        return handback + 60

    monkeypatch.setattr(L, "_adopted_branch_first_pr_fn", read_first_pr)
    result, calls = _adopt(repo, tmp_path)
    assert len(lookups) == 1
    _proceeds(result, calls)


def test_a_fix_order_relay_to_the_lane_after_the_handback_keeps_the_lane(tmp_path, first_pr):
    # axis: a fix order composed for the lane's session after the handback, never checked, reopens the lane — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    time.sleep(0.01)
    assert cloud_relay.compose(repo, "/cfg/acct", SESSION_TITLE, "fix it", fix_order=True)["ok"]
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_fix_order_relay_stamped_after_the_handback_keeps_the_lane(tmp_path, first_pr, monkeypatch):
    # axis: a relay record for the lane's session stamped after the handback reopens it — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _relay_records(monkeypatch, [{"session": SESSION_TITLE, "at": _utc_stamp(60)}])
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_relay_read_that_fails_keeps_the_lane(tmp_path, first_pr, monkeypatch):
    # axis: a fix-order relay read that fails keeps every handed-back lane — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    monkeypatch.setattr(
        cloud_relay, "fix_orders",
        lambda repo_root, *, env=None, include_unchecked=False: {"ok": False, "reason": "relay-state-unreadable"},
    )
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_relay_record_whose_time_does_not_parse_keeps_the_lane(tmp_path, first_pr, monkeypatch):
    # axis: a relay record for the lane's session whose send time does not parse counts as an opener after the handback
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _relay_records(monkeypatch, [{"session": SESSION_TITLE, "at": "yesterday"}])
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_relay_record_for_another_session_does_not_keep_the_lane(
    tmp_path, first_pr, monkeypatch,
):
    # axis: only a fix order to this lane's own session opens it, at any compose time; one to another session does not
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _relay_records(monkeypatch, [
        {"session": "issue-656-someone-else", "at": _utc_stamp(-3600)},
        {"session": "issue-656-someone-else", "at": _utc_stamp(60)},
        {"session": "issue-656-unparseable", "at": "yesterday"},
    ])
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)


def test_a_fix_order_delivered_before_the_handback_keeps_the_lane(tmp_path, first_pr, monkeypatch):
    # axis: any fix order to the lane's session keeps the lane, even one the relay confirmed delivered before the handback — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _relay_records(monkeypatch, [{
        "session": SESSION_TITLE, "at": _utc_stamp(-3600),
        "decision": {"delivered": True, "reason": "relay-delivered", "at": _utc_stamp(-60)},
    }])
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID]


def test_a_fix_order_delivered_after_the_handback_keeps_the_lane(tmp_path, first_pr, monkeypatch):
    # axis: a fix order whose delivery was confirmed after the handback may have reopened the lane, so it stays — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _relay_records(monkeypatch, [{
        "session": SESSION_TITLE, "at": _utc_stamp(-3600),
        "decision": {"delivered": True, "reason": "relay-delivered", "at": _utc_stamp(60)},
    }])
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_an_undecided_fix_order_composed_before_the_handback_keeps_the_lane(tmp_path, first_pr, monkeypatch):
    # axis: a fix order with no decision may still be delivered after the handback, so it keeps the lane whatever its compose time — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    _relay_records(monkeypatch, [{"session": SESSION_TITLE, "at": _utc_stamp(-3600), "decision": None}])
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_first_pr_that_could_not_be_read_keeps_the_lane(tmp_path, first_pr):
    # axis: a first-pull-request time that could not be read keeps the lane
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    first_pr(None)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


def test_a_lane_that_parked_is_kept_whatever_the_first_pr_time(tmp_path, first_pr):
    # axis: only a handback excuses a lane by timing; a parked lane may still be working
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, outcome="park")
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")


@pytest.mark.parametrize("first_offset, proceeds", [(3600, False), (7200 + 3600, True)], ids=["before", "after"])
def test_a_reoutcome_handback_is_timed_from_the_reoutcome(tmp_path, first_pr, monkeypatch, first_offset, proceeds):
    # axis: a lane re-outcomed to handback is timed from the amendment, never from its first terminal record
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, outcome="park")
    t0 = next(
        record["ts"] for record in ll.read(repo)["records"]
        if record.get("event") == "outcome" and record.get("launchId") == LANE_ID
    )
    # The amendment is stamped by `time.time()` inside launch_ledger; pin it two hours after the park.
    with monkeypatch.context() as patched:
        patched.setattr(ll, "time", SimpleNamespace(**{**vars(time), "time": lambda: t0 + 7200}))
        assert ll.amend(repo, LANE_ID, "reoutcome", "handback", "re-read")["ok"]
    first_pr(t0 + first_offset)
    result, calls = _adopt(repo, tmp_path)
    if proceeds:
        _proceeds(result, calls)
    else:
        _refused_unread(repo, result, calls, "listing-not-given")
        assert result["launchIds"] == [LANE_ID]


def test_the_first_pr_is_read_once_for_every_lane_that_reaches_the_timing_test(tmp_path, first_pr):
    # axis: the first-pull-request read happens at most once per check, whatever the number of lanes
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, "lane-a")
    _seed_lane(repo, "lane-b", session_id="session_01FixtureLaneB000000000", title="issue-656-fixturelane00000b")
    reads = first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _proceeds(result, calls)
    assert len(reads) == 1


def test_a_lane_bound_to_the_branch_whose_branch_is_gone_from_the_remote_proceeds(tmp_path, first_pr):
    # axis: a lane bound to the adopted branch by its premise is dropped when origin shows that branch gone, with no listing — see bite-proof record i2254_original_session
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": ADOPTED})
    _delete_remote_branch(repo)
    first_pr(None)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _proceeds(result, calls)


def test_a_gone_branch_lane_whose_session_the_listing_shows_live_refuses_live(tmp_path, first_pr):
    # axis: a gone-branch lane needs no listing, but a supplied listing that shows its session live still refuses, since the deleted ref does not stop its builder — see bite-proof record i2254_original_session
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": ADOPTED})
    _delete_remote_branch(repo)
    first_pr(None)
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"), branch=ADOPTED)
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert calls == []


def test_a_lane_bound_to_the_branch_by_its_adopts_number_is_dropped_when_the_branch_is_gone(tmp_path, first_pr):
    # axis: a lane whose premise adopts the same pull request number is bound to the branch too (asked directly: a launch premise carrying `adopts` needs a stack)
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adopts": 77})
    _delete_remote_branch(repo)
    first_pr(None)
    stamped = {"adoptsBranch": ADOPTED, "adopts": 77}
    assert L._original_session_refusal(repo, 656, stamped, None, dict(os.environ)) is None
    stamped = {"adoptsBranch": ADOPTED, "adopts": 78}
    reason, detail = L._original_session_refusal(repo, 656, stamped, None, dict(os.environ))
    assert (reason, detail["failedRead"]) == (TOKEN_UNREAD, "listing-not-given")


def test_a_lane_bound_to_the_branch_whose_branch_is_on_the_remote_refuses_live(tmp_path, first_pr):
    # axis: a bound lane is dropped only when the branch is gone, so a branch still on the remote leaves the listing to say the lane is live — see bite-proof record i2254_original_session
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": ADOPTED})
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"), branch=ADOPTED)
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert result["originalSessions"][0]["launchId"] == LANE_ID
    assert calls == []


def test_a_bound_lane_with_its_branch_on_the_remote_and_no_listing_refuses_unread(tmp_path, first_pr):
    # axis: a bound lane whose branch is still on the remote stays, and with no listing refuses unread — see bite-proof record i2254_original_session
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": ADOPTED})
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID]


def test_a_bound_lane_stays_when_origin_cannot_be_asked(tmp_path, first_pr):
    # axis: a branch read that fails (no origin) keeps a bound lane — see bite-proof record i2254_original_session
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": ADOPTED})
    _git(repo, "remote", "remove", "origin")
    first_pr(time.time() + 3600)
    reason, detail = L._original_session_refusal(
        repo, 656, {"adoptsBranch": ADOPTED}, None, dict(os.environ),
    )
    assert reason == TOKEN_UNREAD
    assert detail["failedRead"] == "listing-not-given"
    assert detail["launchIds"] == [LANE_ID]


def test_a_live_fresh_lane_refuses_beside_a_bound_lane_whose_branch_is_gone(tmp_path, first_pr):
    # axis: dropping the bound lane never excuses a different lane the listing shows live (asked directly: a running lane stops the refusal from being reserved)
    repo = _adopted_repo(tmp_path)
    _seed_lane(
        repo, "lane-bound", session_id="session_01FixtureLaneB000000000",
        title="issue-656-fixturelane00000b", premise_extra={"adoptsBranch": ADOPTED},
    )
    _seed_lane(repo, LANE_ID, outcome=None)
    _delete_remote_branch(repo)
    first_pr(time.time() + 3600)
    reason, detail = L._original_session_refusal(
        repo, 656, {"adoptsBranch": ADOPTED}, _fixture("get_session_running.json"), dict(os.environ),
    )
    assert reason == TOKEN_LIVE
    assert [s["launchId"] for s in detail["originalSessions"]] == [LANE_ID]


def test_a_lane_recorded_on_another_branch_is_not_excused_by_that_alone(tmp_path, first_pr):
    # axis: a premise naming another branch never excuses a lane; only the timing evidence does
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": "someone/else"})
    _delete_remote_branch(repo)
    first_pr(time.time() - 3600)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID]


# --- every refusal's remedy is a step the advisor runs itself -----------------------------

REMEDIES = (
    L._ADOPT_ORIGINAL_REMEDY_LIVE, L._ADOPT_ORIGINAL_REMEDY_UNREAD, L._ADOPT_ORIGINAL_REMEDY_STATE,
)


def test_no_remedy_asks_the_owner():
    # axis: none of the three remedies names the owner as the one who acts
    assert all("owner" not in remedy.lower() for remedy in REMEDIES)
    assert len(set(REMEDIES)) == 3


@pytest.mark.parametrize("path", [
    "live", "ledger", "recover-state", "listing-not-given", "listing-file", "listing-json",
    "listing-shape", "listing-incomplete",
])
def test_every_refusal_path_carries_a_remedy_that_never_names_the_owner(tmp_path, monkeypatch, path):
    # axis: every refusal the check can return carries one of the three remedies, none of which asks the owner
    repo = _cloud_repo(tmp_path)
    listing = None
    if path == "ledger":
        monkeypatch.setattr(L.ll, "read", lambda *args, **kwargs: {"state": "corrupt", "records": []})
    else:
        _seed_lane(repo)
    if path == "recover-state":
        state = CR._state_path(repo, os.environ)
        os.makedirs(os.path.dirname(state), exist_ok=True)
        with open(state, "w", encoding="utf-8") as fh:
            fh.write("not json at all")
    listing = {
        "live": _fixture("get_session_running.json"),
        "listing-file": str(tmp_path / "no-such-listing.json"),
        "listing-json": _write_listing(tmp_path, '{"data": [', "json.json"),
        "listing-shape": _write_listing(tmp_path, [], "shape.json"),
        "listing-incomplete": _fixture("list_page_more.json"),
    }.get(path)
    if path == "recover-state":
        listing = _fixture("list_page_complete_without.json")
    reason, detail = L._original_session_refusal(
        repo, 656, {"adoptsBranch": _branch(repo)}, listing, dict(os.environ),
    )
    assert reason == (TOKEN_LIVE if path == "live" else TOKEN_UNREAD)
    if path != "live":
        assert detail["failedRead"] == path
    assert detail["remedy"] in REMEDIES
    assert "owner" not in detail["remedy"].lower()
    assert detail["remedy"] == (
        L._ADOPT_ORIGINAL_REMEDY_LIVE if path == "live"
        else L._ADOPT_ORIGINAL_REMEDY_STATE if path in ("ledger", "recover-state")
        else L._ADOPT_ORIGINAL_REMEDY_UNREAD
    )
    if path.startswith("listing-"):
        assert detail["launchIds"] == [LANE_ID]


# --- the two reads that decide a drop -----------------------------------------------------


def _github_origin(tmp_path):
    repo = _cloud_repo(tmp_path)
    _git(repo, "remote", "set-url", "origin", "https://github.com/o/r.git")
    return repo


def _pull(created_at="2026-10-20T10:00:00Z", ref="feature/x", full_name="o/r"):
    return {"head": {"ref": ref, "repo": {"full_name": full_name}}, "created_at": created_at}


def _gh_answer(monkeypatch, rows=None, returncode=0, stdout=None):
    text = json.dumps(rows) if stdout is None else stdout
    monkeypatch.setattr(
        L, "_gh_branch_pulls",
        lambda owner, repo, branch, env, timeout: subprocess.CompletedProcess([], returncode, text, ""),
    )


def _first_pr(repo):
    return L._adopted_branch_first_pr(repo, "feature/x", dict(os.environ))


def test_gh_branch_pulls_asks_for_pull_requests_in_every_state(monkeypatch):
    # axis: the pulls query asks for every state, since a merged or closed pull request on the branch is still its first
    argvs = []

    def record(args, **kwargs):
        argvs.append(args)
        return subprocess.CompletedProcess(args, 0, "[]", "")

    monkeypatch.setattr(L.subprocess, "run", record)
    L._gh_branch_pulls("o", "r", "feat/x", dict(os.environ), 5)
    assert argvs == [["gh", "api", "repos/o/r/pulls?state=all&head=o:feat%2Fx&per_page=100"]]


def test_the_first_pr_is_the_earliest_created_of_the_branchs_pull_requests(tmp_path, monkeypatch):
    # axis: the branch's first pull request is the minimum created_at over every pull request headed at it, merged ones included
    repo = _github_origin(tmp_path)
    _gh_answer(monkeypatch, [_pull("2026-10-22T10:00:00Z"), _pull("2026-10-20T10:00:00Z", full_name="O/R")])
    assert _first_pr(repo) == calendar.timegm((2026, 10, 20, 10, 0, 0))


@pytest.mark.parametrize("answer", [
    {"rows": [_pull() for _ in range(100)]},
    {"rows": [_pull(), _pull(full_name="fork/r")]},
    {"rows": [_pull(), _pull(ref="feature/y")]},
    {"rows": [_pull(), _pull(created_at="not-a-time")]},
    {"rows": [_pull(), _pull(created_at="2026-10-20T10:00:00")]},
    {"rows": [_pull(), "not a pull"]},
    {"rows": [_pull(), {"head": None, "created_at": "2026-10-01T00:00:00Z"}]},
    {"rows": [_pull(), {"head": "x", "created_at": "2026-10-01T00:00:00Z"}]},
    {"rows": [_pull()], "returncode": 1},
    {"rows": []},
    {"rows": {"message": "Not Found"}},
    {"stdout": "not json"},
], ids=[
    "full-page", "fork-head", "other-branch", "bad-created-at", "no-zone-created-at",
    "row-not-an-object", "head-null", "head-not-an-object", "gh-failed", "no-pull-requests",
    "not-a-list", "not-json",
])
def test_a_first_pr_read_that_cannot_be_trusted_is_none(tmp_path, monkeypatch, answer):
    # axis: any page that could be incomplete or hold another repository's or branch's pull request, or a failed call, reads as unknown
    repo = _github_origin(tmp_path)
    _gh_answer(monkeypatch, **answer)
    assert _first_pr(repo) is None


def test_a_first_pr_read_with_gh_unable_to_run_or_no_github_origin_is_none(tmp_path, monkeypatch):
    # axis: gh that could not run, and an origin that is not on github.com, read as unknown
    repo = _github_origin(tmp_path)
    monkeypatch.setattr(L, "_gh_branch_pulls", lambda owner, repo, branch, env, timeout: None)
    assert _first_pr(repo) is None
    _gh_answer(monkeypatch, [_pull()])
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "remote.git"))
    assert _first_pr(repo) is None
    _git(repo, "remote", "remove", "origin")
    assert _first_pr(repo) is None


def test_the_branch_read_tells_gone_from_present_from_unknown(tmp_path):
    # axis: ls-remote with no line is gone, a line for exactly the branch is present, and a failed ask is unknown
    repo = _cloud_repo(tmp_path)
    branch = _branch(repo)
    env = dict(os.environ)
    assert L._adopted_branch_absent(repo, branch, env) is False
    assert L._adopted_branch_absent(repo, branch + "-nope", env) is True
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    assert L._adopted_branch_absent(repo, branch, env) is None


@pytest.mark.parametrize("entry", [None, {"fixOrder": None}])
def test_a_relay_state_with_a_malformed_pending_entry_keeps_the_lane(tmp_path, first_pr, entry):
    # axis: a pending relay entry that is not a dict may be a damaged fix order, so the real relay read refuses and the lane stays — see bite-proof record i2254_original_session
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    state, _ = cloud_relay._state_path(repo, cloud_relay._env(None))
    os.makedirs(os.path.dirname(state), exist_ok=True)
    with open(state, "w", encoding="utf-8") as fh:
        json.dump({"relays": {}, "pending": {"m": entry}}, fh)
    first_pr(time.time() + 3600)
    result, calls = _adopt(repo, tmp_path)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID]
