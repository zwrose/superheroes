"""The wave watch reads a cloud builder's progress comment to decide lane-stale (#2018).

For a started cloud lane whose tick's comments read observed a progress comment, that comment
alone decides lane-stale; a lane with none keeps the activity rule; no extra request is made.
"""
import json
import os
import re
import subprocess
import time

import pytest

import cloud_builder as cb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import _NoteGh, _arm, _cloud_lane, _raw  # noqa: F401
from test_wave_watch_cloud import (  # noqa: F401
    _BATCH, _FRESH, _QUIET, _SLUG, _WINDOW, _graphql_body, _iso, _lane_activity,
    clock, repo,
)

_LONG_AGO = _QUIET * 5  # a lane start comfortably before every comment below
_EXPECTED_60 = 3600


def _body(expected="Expected: 60 minutes", phase="gate"):
    lines = [cb.PROGRESS_HEADER, "", "Phase: %s" % phase, "Now running: the full test suite",
             "Started: 2026-10-21T08:30:00Z"]
    if expected is not None:
        lines.append(expected)
    return "\n".join(lines)


def _progress(comment_id, issue, *, updated_age, created_age=None, body=None, **body_args):
    """A progress comment last edited `updated_age` seconds ago, created just before that."""
    created_age = updated_age + 10 if created_age is None else created_age
    return {
        "id": comment_id,
        "html_url": "https://github.com/%s/issues/%d#issuecomment-%d" % (_SLUG, issue, comment_id),
        "issue_url": "https://api.github.com/repos/%s/issues/%d" % (_SLUG, issue),
        "created_at": _iso(created_age),
        "updated_at": _iso(updated_age),
        "body": _body(**body_args) if body is None else body,
    }


class _ProgressGh(_NoteGh):
    """`_NoteGh` whose graphql answers `activity_age` seconds of activity, or fails."""

    def __init__(self, comments=(), *, activity_age=_QUIET, graphql_fails=False, script=()):
        super().__init__(comments, script=script)
        self.activity_age = activity_age
        self.graphql_fails = graphql_fails

    def __call__(self, argv, **kwargs):
        if argv[:3] == ["gh", "api", "graphql"]:
            self.calls.append(list(argv))
            self.kwargs.append(kwargs)
            if self.graphql_fails:
                return _raw(argv, "", 1)
            query = next(arg for arg in argv if arg.startswith("query="))
            issues = [int(n) for n in re.findall(r"i(\d+): issue", query)]
            body = _graphql_body({n: _lane_activity(issue_age=self.activity_age) for n in issues})
            return _raw(argv, json.dumps(body))
        return super().__call__(argv, **kwargs)


def _lane(repo_root, **kwargs):
    kwargs.setdefault("start_age", _LONG_AGO)
    _cloud_lane(repo_root, "cloud-a", 101, **kwargs)


def _only_launch(result):
    assert result["event"] == ww.EVENT_LANE_STALE
    [launch] = result["launches"]
    assert launch["launchId"] == "cloud-a"
    return launch


# --- the invariant: the progress comment alone decides ----------------------------


def test_t1_a_quiet_lane_inside_its_stated_step_is_not_stale(repo):
    # axis: a lane inside its stated step is not stale however quiet its activity; the activity rule would fire lane-stale on a long step
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=3000)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER


def test_t2_a_lane_past_its_stated_step_plus_the_window_is_stale(repo):
    # axis: a lane past its stated step plus the window is stale with the progress fields and no activity age; a missed lane would hang unseen
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 60)])
    launch = _only_launch(_arm(repo, gh))
    assert launch["place"] == "cloud"
    assert launch["state"] is None
    assert _EXPECTED_60 + _WINDOW + 60 <= launch["progressAgeSeconds"] < _EXPECTED_60 + _WINDOW + 180
    assert launch["progressExpectedSeconds"] == _EXPECTED_60
    assert launch["phase"] == "gate"
    assert launch["quietWindowSeconds"] == _WINDOW
    assert launch["cloudSessionName"] == "cloud-101"
    assert launch["cloudSessionId"] == "session_101"
    assert "activityAgeSeconds" not in launch


def test_t3_fresh_activity_does_not_save_a_lane_past_its_stated_step(repo):
    # axis: fresh activity does not rescue a lane past its stated step; letting it would hide a stuck builder
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 60)],
                     activity_age=_FRESH)
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressExpectedSeconds"] == _EXPECTED_60
    assert "activityAgeSeconds" not in launch


def test_the_boundary_is_the_stated_seconds_plus_the_window(repo):
    # axis: the stale limit is the stated seconds plus the window, either side by two minutes; a dropped term would move the limit
    _lane(repo)
    inside = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW - 120)])
    assert _arm(repo, inside)["event"] == ww.EVENT_TIMER
    past = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 120)])
    assert _arm(repo, past)["event"] == ww.EVENT_LANE_STALE


# --- a lane with no progress comment keeps today's rule ---------------------------


def test_t4_no_progress_comment_and_quiet_activity_is_stale_by_activity(repo):
    # axis: a lane with no progress comment and quiet activity stays stale by the activity rule; the progress rule must not replace it
    _lane(repo)
    gh = _ProgressGh([])
    launch = _only_launch(_arm(repo, gh))
    assert _QUIET <= launch["activityAgeSeconds"] < _QUIET + 120
    assert "progressAgeSeconds" not in launch


def test_t5_no_progress_comment_and_fresh_activity_raises_no_event(repo):
    # axis: a lane with no progress comment and fresh activity raises nothing; a false lane-stale would interrupt a live build
    _lane(repo)
    gh = _ProgressGh([], activity_age=_FRESH)
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_a_comment_that_is_not_a_progress_comment_leaves_the_activity_rule(repo):
    # axis: a non-progress or quoted comment leaves the activity rule; a loose match would let it decide the lane
    _lane(repo)
    other = _progress(7, 101, updated_age=60, body="Looks good to me.")
    quoted = _progress(8, 101, updated_age=60, body="Quoting:\n" + _body())
    launch = _only_launch(_arm(repo, _ProgressGh([other, quoted])))
    assert "activityAgeSeconds" in launch


# --- edges -----------------------------------------------------------------------


def test_t6_a_future_dated_progress_comment_is_stale(repo):
    # axis: a future-dated progress comment is stale with a negative age; trusting it would read as fresh forever
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=-600, created_age=300)],
                     activity_age=_FRESH)
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressAgeSeconds"] < 0


def test_t7_a_progress_comment_created_before_the_lanes_start_is_not_the_lanes(repo):
    # axis: a progress comment created before the lane started belongs to an earlier run and is ignored; using it would judge the lane on old time
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=100, created_age=_LONG_AGO + 600)])
    launch = _only_launch(_arm(repo, gh))
    assert "activityAgeSeconds" in launch
    assert "progressAgeSeconds" not in launch


@pytest.mark.parametrize("fresh_id,stale_id", [(5, 9), (9, 5)])
def test_t8_the_most_recently_updated_of_two_progress_comments_wins(repo, fresh_id, stale_id):
    # axis: the most recently updated of two progress comments decides, whatever the order or id; taking the first or the highest id would use stale text
    _lane(repo)
    gh = _ProgressGh([
        _progress(stale_id, 101, updated_age=_EXPECTED_60 + _WINDOW + 600),
        _progress(fresh_id, 101, updated_age=100),
    ])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_t8_the_newer_comment_decides_even_when_it_is_the_stale_one(repo):
    # axis: the newer comment decides even when it is the stale one; falling back to an older fresh comment would hide it
    _lane(repo)
    age = 60 + _WINDOW + 500
    gh = _ProgressGh([
        _progress(9, 101, updated_age=age, expected="Expected: 240 minutes"),
        _progress(5, 101, updated_age=age - 10, expected="Expected: 1 minutes"),
    ])
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressExpectedSeconds"] == 60


def test_t9_a_malformed_expected_adds_no_time(repo):
    # axis: a malformed Expected adds no time to the limit; a default wait would delay a stale report
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_WINDOW + 300, expected="Expected: soon")],
                     activity_age=_FRESH)
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressExpectedSeconds"] == 0


def test_a_missing_expected_adds_no_time(repo):
    # axis: a missing Expected adds no time to the limit; a default wait would delay a stale report
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_WINDOW + 300, expected=None)])
    assert _only_launch(_arm(repo, gh))["progressExpectedSeconds"] == 0


def test_e5_an_expected_over_the_cap_is_the_cap(repo):
    # axis: an Expected over the cap is the cap in the lane result; an uncapped value would stretch the limit
    _lane(repo)
    cap = cb.PROGRESS_EXPECTED_MAX_MINUTES * 60
    gh = _ProgressGh([_progress(7, 101, updated_age=cap + _WINDOW + 60,
                                expected="Expected: 9999 minutes")])
    assert _only_launch(_arm(repo, gh))["progressExpectedSeconds"] == cap


def test_e6_a_progress_comment_without_a_readable_updated_at_is_skipped(repo):
    # axis: a progress comment with a missing or unreadable updated_at is skipped to the activity rule; guessing an age would decide the lane on nothing
    _lane(repo)
    missing = _progress(7, 101, updated_age=100)
    del missing["updated_at"]
    garbled = _progress(8, 101, updated_age=100)
    garbled["updated_at"] = "yesterday"
    launch = _only_launch(_arm(repo, _ProgressGh([missing, garbled])))
    assert "activityAgeSeconds" in launch


@pytest.mark.parametrize("fresh", [True, False])
def test_e8_a_failed_activity_read_leaves_the_comment_to_decide_and_keeps_the_token(repo, fresh):
    # axis: a failed activity read still lets the comment decide and records the degradation; the lane would otherwise go unjudged
    _lane(repo)
    updated = 100 if fresh else _EXPECTED_60 + _WINDOW + 60
    gh = _ProgressGh([_progress(7, 101, updated_age=updated)], graphql_fails=True)
    result = _arm(repo, gh)
    assert result["event"] == (ww.EVENT_TIMER if fresh else ww.EVENT_LANE_STALE)
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in result["degraded"]


def test_t13_e1_an_unreadable_comments_read_leaves_the_activity_rule(repo):
    # axis: an unreadable comments read leaves the activity rule and records the degradation; a progress decision from no data would be invented
    _lane(repo)
    failing = _raw(["gh"], "HTTP/2.0 500 Internal Server Error\r\n\r\n", 1)
    gh = _ProgressGh([_progress(7, 101, updated_age=100)], script=[failing])
    result = _arm(repo, gh)
    launch = _only_launch(result)
    assert launch["activityAgeSeconds"] >= _QUIET
    assert "progressAgeSeconds" not in launch
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]


def test_a_progress_comment_decides_only_its_own_lane(repo):
    # axis: a progress comment decides only its own lane's issue; another lane would be judged on a comment that is not its own
    _lane(repo)
    _cloud_lane(repo, "cloud-b", 202, start_age=_LONG_AGO)
    gh = _ProgressGh([_progress(7, 101, updated_age=100)])
    launch = _only_launch_of(_arm(repo, gh), "cloud-b")
    assert "activityAgeSeconds" in launch


def _only_launch_of(result, launch_id):
    assert result["event"] == ww.EVENT_LANE_STALE
    [launch] = result["launches"]
    assert launch["launchId"] == launch_id
    return launch


# --- no request the tick did not make before ---------------------------------------


def _shape(argv):
    return re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", "<time>", " ".join(argv))


def test_t10_the_progress_comment_costs_no_request_over_one_arm(repo):
    # axis: reading progress adds no gh request over one arm; an added call would spend rate limit on every arm
    _lane(repo)
    without = _ProgressGh([], activity_age=_FRESH)
    with_progress = _ProgressGh([_progress(7, 101, updated_age=100)], activity_age=_FRESH)
    assert _arm(repo, without)["event"] == ww.EVENT_TIMER
    assert _arm(repo, with_progress)["event"] == ww.EVENT_TIMER
    assert len(without.calls) > 1
    assert [_shape(argv) for argv in with_progress.calls] == [_shape(a) for a in without.calls]
    assert len(with_progress.note_calls()) == len(without.note_calls())


def test_t10_the_progress_comment_costs_no_request_over_one_tick(repo):
    # axis: reading progress adds no gh request over one tick; an added call would spend rate limit on every tick
    _lane(repo)
    without = _ProgressGh([])
    with_progress = _ProgressGh([_progress(7, 101, updated_age=100)])
    ww.run(repo, _BATCH, gh_run=without)
    ww.run(repo, _BATCH, gh_run=with_progress)
    assert [_shape(argv) for argv in with_progress.calls] == [_shape(a) for a in without.calls]


# --- the result carries the progress ----------------------------------------------


def _progress_keys(entry):
    return {key: entry.get(key) for key in ("phase", "progressAgeSeconds", "progressExpectedSeconds")}


def test_t11_the_timer_results_cloud_lane_carries_the_progress(repo):
    # axis: the timer result's cloud lane carries phase, progress age and expected seconds; dropped keys would blind the advisor
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=3000)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER
    [lane] = result["cloudLanes"]
    keys = _progress_keys(lane)
    assert keys["phase"] == "gate"
    assert 3000 <= keys["progressAgeSeconds"] < 3100
    assert keys["progressExpectedSeconds"] == _EXPECTED_60
    assert lane["launchId"] == "cloud-a"
    assert lane["issue"] == 101
    assert lane["cloudSessionId"] == "session_101"
    assert lane["activityAgeSeconds"] >= _QUIET


def test_a_single_tick_result_carries_the_progress(repo):
    # axis: a single tick's result carries the progress keys; only the arm path reporting them would blind the advisor
    _lane(repo)
    result = ww.run(repo, _BATCH, gh_run=_ProgressGh([_progress(7, 101, updated_age=3000)]))
    assert result["event"] == ww.EVENT_TIMER
    assert _progress_keys(result["cloudLanes"][0])["progressExpectedSeconds"] == _EXPECTED_60


def test_t12_the_loops_result_carries_the_progress(repo):
    # axis: the loop's result carries the progress keys over several arms; dropping them between arms would blind the advisor
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=3000)])
    result = ww.loop(
        repo, _BATCH, max_seconds=5, interval_seconds=5, max_total_seconds=15, gh_run=gh,
    )
    assert result["event"] == "timer"
    assert result["arms"] >= 2
    [lane] = result["cloudLanes"]
    keys = _progress_keys(lane)
    assert keys["phase"] == "gate"
    assert 3000 <= keys["progressAgeSeconds"] < 3100
    assert keys["progressExpectedSeconds"] == _EXPECTED_60


def test_a_lane_without_a_progress_comment_carries_none_of_the_three_keys(repo):
    # axis: a lane with no progress comment carries none of the three progress keys; stale keys would claim a progress it lacks
    _lane(repo)
    result = _arm(repo, _ProgressGh([], activity_age=_FRESH))
    [lane] = result["cloudLanes"]
    assert not {"phase", "progressAgeSeconds", "progressExpectedSeconds"} & set(lane)


# --- the pieces --------------------------------------------------------------------


def _watched(issue=101, start=1_000.0):
    return {"cloud-a": {"issue": issue, "reservedTs": start - 1, "startedTs": start}}


def _comment_at(comment_id, issue, created, updated, body):
    return {
        "id": comment_id, "issue_url": "https://api.github.com/repos/%s/issues/%d" % (_SLUG, issue),
        "created_at": created, "updated_at": updated, "body": body,
    }


def test_cloud_progress_skips_malformed_elements_and_never_raises():
    # axis: malformed elements beside a good comment are skipped and never raise; the good comment still decides (each rejection alone is tested separately)
    stamp = "2001-09-09T01:46:41Z"  # after the lane start of 1_000.0
    good = _comment_at(7, 101, stamp, stamp, _body())
    bad = [
        None, "x", 3, [], {},
        dict(good, id=True), dict(good, id=0), dict(good, id="7"), dict(good, body=None),
        dict(good, body=b"x"), dict(good, body="no header"), dict(good, updated_at=None),
        dict(good, updated_at="soon"), dict(good, created_at=None), dict(good, issue_url=None),
        dict(good, issue_url="https://api.github.com/repos/o/r/issues/999"),
    ]
    got = ww._cloud_progress(bad + [good], _watched())
    assert list(got) == ["cloud-a"]
    assert got["cloud-a"] == {
        "commentId": 7, "updatedAt": stamp, "updatedEpoch": ww._parse_activity_time(stamp),
        "phase": "gate", "expectedSeconds": _EXPECTED_60,
    }
    assert ww._cloud_progress([], _watched()) == {}


_STAMP = "2001-09-09T01:46:41Z"  # after the lane start of 1_000.0
_GOOD = _comment_at(7, 101, _STAMP, _STAMP, _body())


@pytest.mark.parametrize("bad", [
    None, "x", 3, [], {},
    dict(_GOOD, id=True), dict(_GOOD, id=0), dict(_GOOD, id="7"), dict(_GOOD, body=None),
    dict(_GOOD, body=b"x"), dict(_GOOD, body="no header"), dict(_GOOD, updated_at=None),
    dict(_GOOD, updated_at="soon"), dict(_GOOD, created_at=None), dict(_GOOD, issue_url=None),
    dict(_GOOD, issue_url="https://api.github.com/repos/o/r/issues/999"),
], ids=[
    "none", "str", "int", "list", "empty-dict", "id-true", "id-zero", "id-str", "body-none",
    "body-bytes", "body-not-progress", "updated-at-none", "updated-at-unreadable", "created-at-none",
    "issue-url-none", "issue-url-other-issue",
])
def test_cloud_progress_rejects_each_malformed_element_on_its_own(bad):
    # axis: each malformed element alone yields {}, so a good comment beside it cannot mask a rejection that stopped working
    assert ww._cloud_progress([bad], _watched()) == {}
    assert list(ww._cloud_progress([_GOOD], _watched())) == ["cloud-a"]  # the same watched mapping accepts the good one


def test_cloud_progress_breaks_an_updated_at_tie_by_comment_id():
    # axis: an updated_at tie goes to the higher comment id whatever the input order; an order-dependent pick would flap
    stamp = "2001-09-09T01:46:41Z"
    low = _comment_at(5, 101, stamp, stamp, _body(phase="low"))
    high = _comment_at(9, 101, stamp, stamp, _body(phase="high"))
    assert ww._cloud_progress([high, low], _watched())["cloud-a"]["phase"] == "high"
    assert ww._cloud_progress([low, high], _watched())["cloud-a"]["phase"] == "high"


def _filled(comments, *, deadline=130.0, watched_lanes=None):
    lanes = watched_lanes if watched_lanes is not None else {
        "cloud-a": {"place": ll.PLACE_CLOUD, "started": True, "issue": 101,
                    "reservedTs": 999.0, "startedTs": 1_000.0},
    }
    out = [None]
    gh = _ProgressGh(comments)
    result = ww._evaluate_cloud_comments(
        "/nowhere", lanes, deadline=deadline, env={}, gh_run=gh, monotonic=lambda: 100.0,
        degraded=set(), note_state=[None], known_slug=_SLUG, progress_out=out,
    )
    return result, out, gh


def test_evaluate_cloud_comments_fills_the_progress_slot_and_keeps_its_return_value():
    # axis: the comments evaluation fills the progress slot and still returns (notes, terminals) unchanged; breaking either would regress notes
    stamp = "2001-09-09T01:46:41Z"
    comments = [_comment_at(7, 101, stamp, stamp, _body())]
    (notes, terminals), out, _gh = _filled(comments)
    assert (notes, terminals) == ([], [])
    assert out[0]["cloud-a"]["commentId"] == 7


def test_evaluate_cloud_comments_leaves_the_progress_slot_untouched_on_every_early_return():
    # axis: an early return (no lanes, spent deadline) leaves the slot None and makes no call; filling it would clobber the stored snapshot
    stamp = "2001-09-09T01:46:41Z"
    comments = [_comment_at(7, 101, stamp, stamp, _body())]
    (_n, _t), out, gh = _filled(comments, watched_lanes={})
    assert out == [None] and gh.calls == []
    (_n, _t), out, gh = _filled(comments, deadline=100.0)
    assert out == [None] and gh.calls == []


def test_apply_cloud_progress_keeps_other_lanes_and_sorts_by_launch_id():
    # axis: other lanes keep their entries, results sort by launch id and a progress entry for a non-lane decides nothing; dropping others would lose stale lanes
    lanes = {
        "cloud-a": {"place": ll.PLACE_CLOUD, "started": True, "issue": 101},
        "cloud-b": {"place": ll.PLACE_CLOUD, "started": True, "issue": 202},
        "cloud-c": {"place": ll.PLACE_CLOUD, "started": True, "issue": 303},
    }
    activity = [{"launchId": "cloud-a", "activityAgeSeconds": 9.0},
                {"launchId": "cloud-c", "activityAgeSeconds": 9.0}]
    progress = {
        "cloud-a": {"commentId": 1, "updatedAt": "x", "updatedEpoch": 900.0,
                    "phase": "gate", "expectedSeconds": 0},
        "cloud-b": {"commentId": 2, "updatedAt": "x", "updatedEpoch": 0.0,
                    "phase": None, "expectedSeconds": 0},
    }
    now = 900.0 + _WINDOW - 1
    stale = ww._apply_cloud_progress(activity, lanes, progress, now)
    assert [entry["launchId"] for entry in stale] == ["cloud-b", "cloud-c"]
    assert stale[1] == {"launchId": "cloud-c", "activityAgeSeconds": 9.0}
    assert stale[0]["progressAgeSeconds"] == now
    assert stale[0]["phase"] is None
    # a progress entry for a lane that is not a started cloud lane in the batch decides nothing
    ghost = {"cloud-z": dict(progress["cloud-b"])}
    assert ww._apply_cloud_progress(activity, lanes, ghost, now) == activity


def test_apply_cloud_progress_stale_boundary_is_strict():
    # axis: a lane exactly at its stated seconds plus the window is not stale and one tick past it is, so a >= or a shifted limit is caught
    lanes = {"cloud-a": {"place": ll.PLACE_CLOUD, "started": True, "issue": 101}}
    progress = {"cloud-a": {"commentId": 7, "updatedAt": "x", "updatedEpoch": 1000.0,
                            "phase": "gate", "expectedSeconds": 3600}}
    limit = 1000.0 + 3600 + ww.LIVENESS_QUIET_WINDOW_SECONDS
    assert ww._apply_cloud_progress([], lanes, progress, limit) == []
    past = ww._apply_cloud_progress([], lanes, progress, limit + 0.001)
    assert [entry["launchId"] for entry in past] == ["cloud-a"]


# --- a tick that makes no comments request reuses the stored snapshot ---------------


def _tick(repo_root, gh, progress_state, *, spent, cloud_state, note_state):
    """One `_evaluate_tick`, its arm deadline `spent` or a minute ahead; (result, payload, degraded)."""
    now = ww.time.monotonic()
    payload, degraded = {}, set()
    result = ww._evaluate_tick(
        repo_root, _BATCH, deadline=now - 1 if spent else now + 60, env=os.environ, gh_run=gh,
        membership_reader=lambda *a, **k: None, monotonic=ww.time.monotonic, degraded=degraded,
        ignore_launch_ids=(), pr_state=[None], stack_state=[None], pr_sampled=[False],
        first_tick=[False], ignore_set=set(), cloud_state=cloud_state,
        cloud_payload_out=payload, note_state=note_state, progress_state=progress_state,
    )
    return result, payload, degraded


def test_t14_a_tick_with_no_comments_request_reuses_the_stored_snapshot(repo):
    # axis: a tick that makes no comments request decides from the stored snapshot; losing it would fall back to the activity rule mid-step
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=3000)])
    progress_state, cloud_state, note_state = [None], [None], [None]
    result, _payload, _degraded = _tick(
        repo, gh, progress_state, spent=False, cloud_state=cloud_state, note_state=note_state,
    )
    assert result is None
    assert progress_state[0]["cloud-a"]["commentId"] == 7
    assert len(gh.note_calls()) == 1
    stored = progress_state[0]

    result, payload, _degraded = _tick(
        repo, gh, progress_state, spent=True, cloud_state=cloud_state, note_state=note_state,
    )
    assert len(gh.note_calls()) == 1  # the spent tick asked for no comments
    assert result is None  # the quiet activity did not fire lane-stale: the stored snapshot decided
    assert progress_state[0] is stored
    [lane] = payload["cloudLanes"]
    assert lane["phase"] == "gate"
    assert lane["progressExpectedSeconds"] == _EXPECTED_60


def test_t15_a_request_that_finds_no_progress_comment_replaces_the_stored_snapshot(repo):
    # axis: a request that finds no progress comment replaces the stored snapshot with {}; keeping the old one would judge on a vanished comment
    _lane(repo)
    stale_snapshot = {"cloud-a": {
        "commentId": 7, "updatedAt": "x", "updatedEpoch": time.time() - 100,
        "phase": "gate", "expectedSeconds": _EXPECTED_60,
    }}
    progress_state = [stale_snapshot]
    gh = _ProgressGh([])
    result, payload, _degraded = _tick(
        repo, gh, progress_state, spent=False, cloud_state=[None], note_state=[None],
    )
    assert len(gh.note_calls()) == 1
    assert progress_state[0] == {}
    launch = _only_launch(result)
    assert "activityAgeSeconds" in launch  # the activity rule, quiet and so stale
    assert "progressAgeSeconds" not in launch
    [lane] = payload["cloudLanes"]
    assert "phase" not in lane


def test_t16_a_reused_snapshot_past_its_expected_time_is_stale(repo):
    # axis: a reused snapshot past its expected time is stale with no comments call; the lane would never go stale between reads
    _lane(repo)
    old = time.time() - (_EXPECTED_60 + _WINDOW + 60)
    progress_state = [{"cloud-a": {
        "commentId": 7, "updatedAt": "x", "updatedEpoch": old,
        "phase": "gate", "expectedSeconds": _EXPECTED_60,
    }}]
    gh = _ProgressGh([], activity_age=_FRESH)
    result, _payload, _degraded = _tick(
        repo, gh, progress_state, spent=True, cloud_state=[None], note_state=[None],
    )
    assert gh.note_calls() == []
    launch = _only_launch(result)
    assert launch["progressExpectedSeconds"] == _EXPECTED_60
    assert launch["progressAgeSeconds"] >= _EXPECTED_60 + _WINDOW + 60
    assert "activityAgeSeconds" not in launch
