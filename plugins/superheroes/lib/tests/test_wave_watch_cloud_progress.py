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
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=3000)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER


def test_t2_a_lane_past_its_stated_step_plus_the_window_is_stale(repo):
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
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 60)],
                     activity_age=_FRESH)
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressExpectedSeconds"] == _EXPECTED_60
    assert "activityAgeSeconds" not in launch


def test_the_boundary_is_the_stated_seconds_plus_the_window(repo):
    _lane(repo)
    inside = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW - 120)])
    assert _arm(repo, inside)["event"] == ww.EVENT_TIMER
    past = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 120)])
    assert _arm(repo, past)["event"] == ww.EVENT_LANE_STALE


# --- a lane with no progress comment keeps today's rule ---------------------------


def test_t4_no_progress_comment_and_quiet_activity_is_stale_by_activity(repo):
    _lane(repo)
    gh = _ProgressGh([])
    launch = _only_launch(_arm(repo, gh))
    assert _QUIET <= launch["activityAgeSeconds"] < _QUIET + 120
    assert "progressAgeSeconds" not in launch


def test_t5_no_progress_comment_and_fresh_activity_raises_no_event(repo):
    _lane(repo)
    gh = _ProgressGh([], activity_age=_FRESH)
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_a_comment_that_is_not_a_progress_comment_leaves_the_activity_rule(repo):
    _lane(repo)
    other = _progress(7, 101, updated_age=60, body="Looks good to me.")
    quoted = _progress(8, 101, updated_age=60, body="Quoting:\n" + _body())
    launch = _only_launch(_arm(repo, _ProgressGh([other, quoted])))
    assert "activityAgeSeconds" in launch


# --- edges -----------------------------------------------------------------------


def test_t6_a_future_dated_progress_comment_is_stale(repo):
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=-600, created_age=300)],
                     activity_age=_FRESH)
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressAgeSeconds"] < 0


def test_t7_a_progress_comment_created_before_the_lanes_start_is_not_the_lanes(repo):
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=100, created_age=_LONG_AGO + 600)])
    launch = _only_launch(_arm(repo, gh))
    assert "activityAgeSeconds" in launch
    assert "progressAgeSeconds" not in launch


@pytest.mark.parametrize("fresh_id,stale_id", [(5, 9), (9, 5)])
def test_t8_the_most_recently_updated_of_two_progress_comments_wins(repo, fresh_id, stale_id):
    _lane(repo)
    gh = _ProgressGh([
        _progress(stale_id, 101, updated_age=_EXPECTED_60 + _WINDOW + 600),
        _progress(fresh_id, 101, updated_age=100),
    ])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_t8_the_newer_comment_decides_even_when_it_is_the_stale_one(repo):
    _lane(repo)
    age = 60 + _WINDOW + 500
    gh = _ProgressGh([
        _progress(9, 101, updated_age=age, expected="Expected: 240 minutes"),
        _progress(5, 101, updated_age=age - 10, expected="Expected: 1 minutes"),
    ])
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressExpectedSeconds"] == 60


def test_t9_a_malformed_expected_adds_no_time(repo):
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_WINDOW + 300, expected="Expected: soon")],
                     activity_age=_FRESH)
    launch = _only_launch(_arm(repo, gh))
    assert launch["progressExpectedSeconds"] == 0


def test_a_missing_expected_adds_no_time(repo):
    _lane(repo)
    gh = _ProgressGh([_progress(7, 101, updated_age=_WINDOW + 300, expected=None)])
    assert _only_launch(_arm(repo, gh))["progressExpectedSeconds"] == 0


def test_e5_an_expected_over_the_cap_is_the_cap(repo):
    _lane(repo)
    cap = cb.PROGRESS_EXPECTED_MAX_MINUTES * 60
    gh = _ProgressGh([_progress(7, 101, updated_age=cap + _WINDOW + 60,
                                expected="Expected: 9999 minutes")])
    assert _only_launch(_arm(repo, gh))["progressExpectedSeconds"] == cap


def test_e6_a_progress_comment_without_a_readable_updated_at_is_skipped(repo):
    _lane(repo)
    missing = _progress(7, 101, updated_age=100)
    del missing["updated_at"]
    garbled = _progress(8, 101, updated_age=100)
    garbled["updated_at"] = "yesterday"
    launch = _only_launch(_arm(repo, _ProgressGh([missing, garbled])))
    assert "activityAgeSeconds" in launch


@pytest.mark.parametrize("fresh", [True, False])
def test_e8_a_failed_activity_read_leaves_the_comment_to_decide_and_keeps_the_token(repo, fresh):
    _lane(repo)
    updated = 100 if fresh else _EXPECTED_60 + _WINDOW + 60
    gh = _ProgressGh([_progress(7, 101, updated_age=updated)], graphql_fails=True)
    result = _arm(repo, gh)
    assert result["event"] == (ww.EVENT_TIMER if fresh else ww.EVENT_LANE_STALE)
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in result["degraded"]


def test_t13_e1_an_unreadable_comments_read_leaves_the_activity_rule(repo):
    _lane(repo)
    failing = _raw(["gh"], "HTTP/2.0 500 Internal Server Error\r\n\r\n", 1)
    gh = _ProgressGh([_progress(7, 101, updated_age=100)], script=[failing])
    result = _arm(repo, gh)
    launch = _only_launch(result)
    assert launch["activityAgeSeconds"] >= _QUIET
    assert "progressAgeSeconds" not in launch
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]


def test_a_progress_comment_decides_only_its_own_lane(repo):
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
    _lane(repo)
    without = _ProgressGh([], activity_age=_FRESH)
    with_progress = _ProgressGh([_progress(7, 101, updated_age=100)], activity_age=_FRESH)
    assert _arm(repo, without)["event"] == ww.EVENT_TIMER
    assert _arm(repo, with_progress)["event"] == ww.EVENT_TIMER
    assert len(without.calls) > 1
    assert [_shape(argv) for argv in with_progress.calls] == [_shape(a) for a in without.calls]
    assert len(with_progress.note_calls()) == len(without.note_calls())


def test_t10_the_progress_comment_costs_no_request_over_one_tick(repo):
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
    _lane(repo)
    result = ww.run(repo, _BATCH, gh_run=_ProgressGh([_progress(7, 101, updated_age=3000)]))
    assert result["event"] == ww.EVENT_TIMER
    assert _progress_keys(result["cloudLanes"][0])["progressExpectedSeconds"] == _EXPECTED_60


def test_t12_the_loops_result_carries_the_progress(repo):
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


def test_cloud_progress_breaks_an_updated_at_tie_by_comment_id():
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
    stamp = "2001-09-09T01:46:41Z"
    comments = [_comment_at(7, 101, stamp, stamp, _body())]
    (notes, terminals), out, _gh = _filled(comments)
    assert (notes, terminals) == ([], [])
    assert out[0]["cloud-a"]["commentId"] == 7


def test_evaluate_cloud_comments_leaves_the_progress_slot_untouched_on_every_early_return():
    stamp = "2001-09-09T01:46:41Z"
    comments = [_comment_at(7, 101, stamp, stamp, _body())]
    (_n, _t), out, gh = _filled(comments, watched_lanes={})
    assert out == [None] and gh.calls == []
    (_n, _t), out, gh = _filled(comments, deadline=100.0)
    assert out == [None] and gh.calls == []


def test_apply_cloud_progress_keeps_other_lanes_and_sorts_by_launch_id():
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
