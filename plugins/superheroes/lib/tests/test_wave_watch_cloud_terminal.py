"""The wave watch reports a cloud lane's handback, stop or park as lane-terminal (#1936).

Bites on: the terminal_kind-is-None skip, the lane-start cutoff, the answered record, the
newest-comment rule, the handover rule, and the extension of the tick's terminal launches.
Residual blind spots: the real GitHub comments payload beyond the fields the fixtures carry,
a gh failure that returns a well-formed but wrong comment list, and the loop's re-arm across
a lane-terminal (covered with the other lane events).
"""
import time

import pytest

import cloud_builder as cb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import (  # noqa: F401
    _cloud_lane, _comment, _NoteGh, _arm, _note_answered, _BATCH, _NOTE_BODY, _raw,
)
from test_wave_watch_cloud import _FRESH, _QUIET, clock, repo  # noqa: F401

_CONFIG_DIR = "/home/advisor/.claude-two"


def _body(kind, text="Done with the work."):
    return cb.terminal_text(kind, text)["comment"]


def _footered(kind):
    return _body(kind) + "\n\n" + cb.CLOUD_FOOTER


def _only_launch(result):
    assert result["event"] == ww.EVENT_LANE_TERMINAL, result
    [launch] = result["launches"]
    return launch


def test_a_footered_handback_on_a_watched_lanes_issue_is_lane_terminal(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, _footered("handback"))])
    result = _arm(repo, gh)
    assert result["launchId"] == "cloud-a"
    launch = _only_launch(result)
    assert launch["launchId"] == "cloud-a"
    assert launch["state"] == "handback"
    assert launch["kind"] == "handback"
    assert launch["commentId"] == 7
    assert launch["issue"] == 101
    assert launch["source"] == "comment"
    assert launch["cloudSessionName"] == "cloud-101"
    assert launch["cloudSessionId"] == "session_101"
    assert launch["configDir"] == _CONFIG_DIR
    assert launch["url"].endswith("/issues/101#issuecomment-7")


def test_a_stop_is_lane_terminal_with_state_stopped(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, _body("stop"))])
    launch = _only_launch(_arm(repo, gh))
    assert launch["state"] == "stopped"
    assert launch["kind"] == "stop"
    assert launch["commentId"] == 7


def test_a_park_is_lane_terminal_with_state_parked(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, _body("park"))])
    launch = _only_launch(_arm(repo, gh))
    assert launch["state"] == "parked"
    assert launch["kind"] == "park"
    assert launch["commentId"] == 7


def test_two_lanes_ending_in_one_interval_ride_one_event_sorted_by_launch_id(repo):
    _cloud_lane(repo, "cloud-b", 202)
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(9, 202, _body("stop")), _comment(5, 101, _body("handback"))])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_LANE_TERMINAL
    assert [(x["launchId"], x["state"]) for x in result["launches"]] == [
        ("cloud-a", "handback"), ("cloud-b", "stopped"),
    ]
    assert result["launchId"] == "cloud-a"


@pytest.mark.parametrize("body, event", [
    ("Builder stop at intake. The Anchor did not resolve.", ww.EVENT_TIMER),
    ("Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.", ww.EVENT_TIMER),
    ("Update\n" + cb.STOP_HEADER + "\n\nStopped.", ww.EVENT_TIMER),
    (_NOTE_BODY, ww.EVENT_BUILDER_NOTE),
    (cb.REFUSAL_HEADER + "\n\nNo.", ww.EVENT_TIMER),
])
def test_free_form_comments_do_not_trigger_lane_terminal(repo, body, event):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, body)])
    assert _arm(repo, gh)["event"] == event


def test_a_terminal_comment_created_before_the_lane_began_is_not_reported(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=600, reserve_lead=100)
    gh = _NoteGh([_comment(7, 101, _body("stop"), age=3000)])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_a_terminal_comment_between_reserved_and_started_is_reported(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=600, reserve_lead=100)
    gh = _NoteGh([_comment(7, 101, _body("stop"), age=650)])
    assert _only_launch(_arm(repo, gh))["commentId"] == 7


def test_an_answered_terminal_comment_no_longer_surfaces_and_no_older_one_takes_its_place(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [_comment(6, 101, _body("stop"), age=200), _comment(7, 101, _body("park"), age=100)]
    assert _only_launch(_arm(repo, _NoteGh(comments)))["commentId"] == 7
    assert _note_answered(repo, 7)["ok"] is True
    assert _arm(repo, _NoteGh(comments))["event"] == ww.EVENT_TIMER


def test_the_newest_terminal_comment_decides_by_time_not_by_id(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [_comment(9, 101, _body("park"), age=200), _comment(4, 101, _body("handback"), age=100)]
    launch = _only_launch(_arm(repo, _NoteGh(comments)))
    assert launch["state"] == "handback"
    assert launch["commentId"] == 4


def test_a_park_then_a_later_handback_is_a_handback(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [_comment(5, 101, _body("park"), age=200), _comment(6, 101, _body("handback"), age=100)]
    assert _only_launch(_arm(repo, _NoteGh(comments)))["state"] == "handback"


def test_a_stop_then_a_later_handover_surfaces_nothing(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [
        _comment(5, 101, _body("stop"), age=200),
        _comment(6, 101, cb.handover_text("a" * 40), age=100),
    ]
    assert _arm(repo, _NoteGh(comments))["event"] == ww.EVENT_TIMER


def test_a_comment_on_an_issue_no_watched_lane_has_surfaces_nothing(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 999, _body("stop"))])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_a_malformed_element_is_skipped_and_the_rest_still_count(repo):
    _cloud_lane(repo, "cloud-a", 101)
    good = _body("stop")
    broken = [
        "not a dict",
        {**_comment(1, 101, good), "id": "1"},
        {**_comment(2, 101, good), "id": True},
        {k: v for k, v in _comment(3, 101, good).items() if k != "issue_url"},
        {**_comment(4, 101, good), "created_at": "yesterday"},
        {**_comment(5, 101, good), "body": None},
    ]
    gh = _NoteGh(broken + [_comment(8, 101, good)])
    assert _only_launch(_arm(repo, gh))["commentId"] == 8


def test_the_tick_that_reports_a_cloud_lane_terminal_made_one_comments_request(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, _body("handback"))])
    _only_launch(ww.run(repo, _BATCH, gh_run=gh))
    assert len(gh.note_calls()) == 1


def test_a_builder_note_and_a_stop_on_two_lanes_in_one_tick_report_lane_terminal(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _cloud_lane(repo, "cloud-b", 202)
    gh = _NoteGh([_comment(7, 101), _comment(8, 202, _body("stop"))])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_LANE_TERMINAL
    assert [x["launchId"] for x in result["launches"]] == ["cloud-b"]
    assert len(gh.note_calls()) == 1


def test_a_failed_comments_read_yields_no_cloud_terminal_and_is_disclosed(repo):
    _cloud_lane(repo, "cloud-a", 101)
    failed = _raw([], "HTTP/2.0 500 Internal Server Error\r\n\r\n", 1)
    result = ww.run(repo, _BATCH, gh_run=_NoteGh(script=[failed]))
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]


# --- the same reading without a ledger: lanes handed straight to the evaluator ----------


def _lanes(specs):
    """Watched started cloud lanes by launch id; each spec is (issue, seconds since start)."""
    now = time.time()
    return {
        lid: {
            "place": ll.PLACE_CLOUD, "started": True, "issue": issue,
            "reservedTs": now - age - 1, "startedTs": now - age,
            "cloudSessionName": "cloud-%d" % issue, "cloudSessionId": "session_%d" % issue,
            "configDir": _CONFIG_DIR,
        }
        for lid, (issue, age) in specs.items()
    }


def _evaluate(lanes, comments):
    return ww._evaluate_cloud_comments(
        "/", lanes, deadline=100.0, env={}, gh_run=_NoteGh(comments),
        monotonic=lambda: 0.0, degraded=set(), note_state=[None], known_slug="owner/repo",
    )


def test_direct_each_kind_maps_to_its_state():
    lanes = _lanes({"cloud-a": (101, 600), "cloud-b": (202, 600), "cloud-c": (303, 600)})
    comments = [
        _comment(1, 303, _body("park")), _comment(2, 101, _footered("handback")),
        _comment(3, 202, _body("stop")),
    ]
    notes, terminals = _evaluate(lanes, comments)
    assert notes == []
    assert [(t["launchId"], t["state"], t["kind"], t["commentId"]) for t in terminals] == [
        ("cloud-a", "handback", "handback", 2), ("cloud-b", "stopped", "stop", 3),
        ("cloud-c", "parked", "park", 1),
    ]
    assert terminals[0]["source"] == "comment"
    assert terminals[0]["issue"] == 101
    assert terminals[0]["cloudSessionId"] == "session_101"
    assert terminals[0]["configDir"] == _CONFIG_DIR


@pytest.mark.parametrize("body", [
    "Builder stop at intake. The Anchor did not resolve.",
    "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
    "Update\n" + cb.STOP_HEADER + "\n\nStopped.",
    _NOTE_BODY,
    cb.REFUSAL_HEADER + "\n\nNo.",
])
def test_direct_free_form_comments_are_no_terminal(body):
    lanes = _lanes({"cloud-a": (101, 600)})
    assert _evaluate(lanes, [_comment(7, 101, body)])[1] == []


def test_direct_a_comment_before_the_cutoff_is_not_the_lanes_and_one_after_the_reserve_is():
    lanes = _lanes({"cloud-a": (101, 600)})
    assert _evaluate(lanes, [_comment(7, 101, _body("stop"), age=3000)])[1] == []
    lanes["cloud-a"]["reservedTs"] = time.time() - 700
    between = _comment(8, 101, _body("stop"), age=650)
    assert [t["commentId"] for t in _evaluate(lanes, [between])[1]] == [8]


def test_direct_an_answered_newest_comment_surfaces_nothing_and_no_older_one_replaces_it():
    lanes = _lanes({"cloud-a": (101, 600)})
    older = _comment(6, 101, _body("stop"), age=200)
    newest = _comment(7, 101, _body("park"), age=100)
    assert [t["commentId"] for t in ww._cloud_terminals([older, newest], lanes, set())] == [7]
    assert ww._cloud_terminals([older, newest], lanes, {7}) == []


def test_direct_the_newest_comment_decides_by_time_then_id():
    lanes = _lanes({"cloud-a": (101, 600)})
    park = _comment(9, 101, _body("park"), age=200)
    handback = _comment(4, 101, _body("handback"), age=100)
    for order in ([park, handback], [handback, park]):
        [only] = ww._cloud_terminals(order, lanes, set())
        assert (only["state"], only["commentId"]) == ("handback", 4)


def test_direct_a_newer_handover_surfaces_nothing():
    lanes = _lanes({"cloud-a": (101, 600)})
    stop = _comment(5, 101, _body("stop"), age=200)
    handover = _comment(6, 101, cb.handover_text("a" * 40), age=100)
    assert ww._cloud_terminals([stop, handover], lanes, set()) == []


def test_direct_an_unwatched_issue_and_a_malformed_element_surface_nothing():
    lanes = _lanes({"cloud-a": (101, 600)})
    good = _body("stop")
    broken = [
        "not a dict", {**_comment(1, 101, good), "id": True},
        {**_comment(2, 101, good), "created_at": "yesterday"},
        {**_comment(3, 101, good), "body": None}, _comment(4, 999, good),
    ]
    assert ww._cloud_terminals(broken, lanes, set()) == []


def test_direct_an_unreadable_read_returns_empty_lists_and_is_disclosed():
    failed = _raw([], "HTTP/2.0 500 Internal Server Error\r\n\r\n", 1)
    degraded = set()
    out = ww._evaluate_cloud_comments(
        "/", _lanes({"cloud-a": (101, 600)}), deadline=100.0, env={},
        gh_run=_NoteGh(script=[failed]), monotonic=lambda: 0.0, degraded=degraded,
        note_state=[None], known_slug="owner/repo",
    )
    assert out == ([], [])
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
