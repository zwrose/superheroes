"""The wave watch reports a cloud lane's handback, stop or park as lane-terminal (#1936).

Bites on: the terminal_kind-is-None skip, the lane-start cutoff, the answered record, the
newest-comment rule, the handover rule, and the extension of the tick's terminal launches.
Residual blind spots: the real GitHub comments payload beyond the fields the fixtures carry,
a gh failure that returns a well-formed but wrong comment list, and the loop's re-arm across
a lane-terminal (covered with the other lane events).
"""
import time
from datetime import datetime, timezone

import pytest

import cloud_builder as cb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import (  # noqa: F401
    _cloud_lane, _comment, _NoteGh, _arm, _note_answered, _BATCH, _NOTE_BODY, _raw,
)
from test_wave_watch_cloud import _FRESH, _QUIET, clock, repo  # noqa: F401
from test_wave_watch_cloud_progress import _progress  # noqa: F401

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


def test_direct_a_same_second_tie_is_broken_by_the_larger_comment_id():
    lanes = _lanes({"cloud-a": (101, 600)})
    park = _comment(7, 101, _body("park"), age=100)
    handback = {**_comment(8, 101, _body("handback"), age=100), "created_at": park["created_at"]}
    for order in ([park, handback], [handback, park]):
        [only] = ww._cloud_terminals(order, lanes, set())
        assert (only["state"], only["commentId"]) == ("handback", 8)


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


# --- a superseded park is not terminal (#2099) ---------------------------------------------


def _terminals(comments, answered=(), lane_age=600):
    return ww._cloud_terminals(comments, _lanes({"cloud-a": (101, lane_age)}), set(answered))


def test_p1_a_park_then_a_progress_edit_later_is_not_lane_terminal(repo):
    # axis: SUPERSEDED by progress — the recorded shape: a progress comment created before the park, edited after it
    _cloud_lane(repo, "cloud-a", 101)
    park = _comment(7, 101, _body("park"), age=1000)
    progress = _progress(8, 101, created_age=1200, updated_age=100)
    result = _arm(repo, _NoteGh([park, progress]))
    assert result["event"] == ww.EVENT_TIMER
    assert _terminals([park, progress], lane_age=3000) == []


def test_p2_a_progress_edit_then_a_later_park_is_lane_terminal_parked(repo):
    # axis: SUPERSEDED by progress — a park created after the last progress edit still fires
    _cloud_lane(repo, "cloud-a", 101)
    progress = _progress(8, 101, created_age=500, updated_age=300)
    park = _comment(7, 101, _body("park"), age=100)
    launch = _only_launch(_arm(repo, _NoteGh([progress, park])))
    assert (launch["state"], launch["commentId"]) == ("parked", 7)


def test_p3_a_park_and_a_progress_edit_in_the_same_second_keeps_the_park():
    # axis: STRICT — a tie keeps the park
    park = _comment(7, 101, _body("park"), age=1000)
    progress = {**_progress(8, 101, created_age=1200, updated_age=100), "updated_at": park["created_at"]}
    for order in ([park, progress], [progress, park]):
        [only] = _terminals(order, lane_age=3000)
        assert (only["state"], only["commentId"]) == ("parked", 7)
    later = {**progress, "updated_at": _progress(8, 101, created_age=1200, updated_age=50)["updated_at"]}
    assert _terminals([park, later], lane_age=3000) == []


def test_p3_a_park_and_a_builder_note_in_the_same_second_keeps_the_park():
    # axis: STRICT — a tie keeps the park, for a note as for a progress edit
    park = _comment(7, 101, _body("park"), age=100)
    note = {**_comment(8, 101, age=100), "created_at": park["created_at"]}
    for order in ([park, note], [note, park]):
        [only] = _terminals(order)
        assert (only["state"], only["commentId"]) == ("parked", 7)
    assert _terminals([park, _comment(8, 101, age=50)]) == []


def test_p4_a_park_then_a_builder_note_created_later_is_not_lane_terminal(repo):
    # axis: SUPERSEDED by note — the note itself fires as builder-note
    _cloud_lane(repo, "cloud-a", 101)
    park = _comment(7, 101, _body("park"), age=300)
    note = _comment(8, 101, age=100)
    result = _arm(repo, _NoteGh([park, note]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [n["commentId"] for n in result["notes"]] == [8]
    assert _terminals([park, note]) == []


def test_p4_a_later_note_recorded_answered_still_supersedes_the_park():
    # axis: SUPERSEDED by note — a later note recorded answered still supersedes — an answered filter applied to superseders makes it fail
    park = _comment(7, 101, _body("park"), age=300)
    note = _comment(8, 101, age=100)
    assert _terminals([park, note], answered={8}) == []


def test_p4_a_note_created_before_the_park_does_not_supersede_it():
    # axis: SUPERSEDED by note — a note before the park does not supersede it — a supersession that ignores order makes it fail
    note = _comment(8, 101, age=300)
    park = _comment(7, 101, _body("park"), age=100)
    assert [t["commentId"] for t in _terminals([note, park])] == [7]


@pytest.mark.parametrize("kind, state", [("handback", "handback"), ("stop", "stopped")])
def test_p5_a_handback_or_stop_is_never_superseded(kind, state):
    # axis: PARK ONLY — the supersession applies to a park alone
    ending = _comment(7, 101, _body(kind), age=1000)
    progress = _progress(8, 101, created_age=1200, updated_age=100)
    note = _comment(9, 101, age=50)
    for later in ([progress], [note], [progress, note]):
        [only] = _terminals([ending] + later, lane_age=3000)
        assert (only["state"], only["commentId"]) == (state, 7)


def test_p6_a_newer_park_after_the_superseding_progress_fires(repo):
    # axis: SUPERSEDED by progress — a newer park after the superseding progress still fires — a supersession that silences the lane for good makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    first = _comment(5, 101, _body("park"), age=1000)
    progress = _progress(8, 101, created_age=1200, updated_age=300)
    second = _comment(6, 101, _body("park"), age=100)
    launch = _only_launch(_arm(repo, _NoteGh([first, progress, second])))
    assert (launch["state"], launch["commentId"]) == ("parked", 6)
    assert _terminals([first, progress], lane_age=3000) == []


def test_p6_a_superseded_park_does_not_fall_back_to_an_older_ending():
    # axis: NO FALLBACK — a superseded park does not fall back to an older ending — a fallback to the older stop makes it fail
    older = _comment(4, 101, _body("stop"), age=1200)
    park = _comment(7, 101, _body("park"), age=1000)
    progress = _progress(8, 101, created_age=1300, updated_age=100)
    assert _terminals([older, park, progress], lane_age=3000) == []


def test_p7_progress_on_another_lanes_issue_does_not_supersede():
    # axis: lane assignment — only the same lane's activity counts
    lanes = _lanes({"cloud-a": (101, 3000), "cloud-b": (202, 3000)})
    park = _comment(7, 101, _body("park"), age=1000)
    elsewhere = _progress(8, 202, created_age=1200, updated_age=100)
    unwatched = _progress(9, 999, created_age=1200, updated_age=100)
    other_note = _comment(10, 202, age=100)
    out = ww._cloud_terminals([park, elsewhere, unwatched, other_note], lanes, set())
    assert [(t["launchId"], t["commentId"]) for t in out] == [("cloud-a", 7)]


def test_p7_progress_created_before_the_lanes_cutoff_does_not_supersede():
    # axis: lane cutoff — progress created before the lane's cutoff does not supersede — a missing cutoff check makes it fail
    park = _comment(7, 101, _body("park"), age=1000)
    earlier_lane = _progress(8, 101, created_age=3000, updated_age=100)
    earlier_note = _comment(9, 101, age=3000)
    assert [t["commentId"] for t in _terminals([park, earlier_lane, earlier_note], lane_age=2000)] == [7]


@pytest.mark.parametrize("updated", [None, "soon", ""])
def test_p8_a_progress_comment_with_no_readable_updated_at_does_not_supersede(updated):
    # axis: unreadable updated_at — a progress comment whose updated_at is None, junk or empty does not supersede — treating it as a time makes it fail
    park = _comment(7, 101, _body("park"), age=1000)
    readable = _progress(8, 101, created_age=1200, updated_age=100)
    assert _terminals([park, readable], lane_age=3000) == []
    unreadable = {**readable, "updated_at": updated}
    assert [t["commentId"] for t in _terminals([park, unreadable], lane_age=3000)] == [7]


def test_p8_a_progress_comment_without_an_updated_at_key_does_not_supersede():
    # axis: missing updated_at key — a progress comment with no updated_at key does not supersede — a KeyError or a default time makes it fail
    park = _comment(7, 101, _body("park"), age=1000)
    full = _progress(8, 101, created_age=1200, updated_age=100)
    assert _terminals([park, full], lane_age=3000) == []
    keyless = {k: v for k, v in full.items() if k != "updated_at"}
    assert [t["commentId"] for t in _terminals([park, keyless], lane_age=3000)] == [7]


# --- a progress edit supersedes a park only when it shows the lane resumed (#2099, vet 622) ----


_WIDE = 30000


def _stamp(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _park_then_progress(
    gap, *, phase="gate", expected="Expected: 60 minutes", created_before=600, body=None, park_age=12000,
):
    """A park and the lane's progress comment, created `created_before` s before it and last edited `gap` s after it."""
    park = _comment(7, 101, _body("park"), age=park_age)
    park_at = ww._parse_activity_time(park["created_at"])
    progress = _progress(8, 101, created_age=0, updated_age=0, body=body, phase=phase, expected=expected)
    progress["created_at"] = _stamp(park_at - created_before)
    progress["updated_at"] = _stamp(park_at + gap)
    return park, progress


def _only_park(comments):
    [only] = _terminals(comments, lane_age=_WIDE)
    assert (only["state"], only["commentId"]) == ("parked", 7)


_RECORDED_PARKS = [
    pytest.param(5, "parked on a second owner gate", "Expected: 240 minutes", 600, id="second-owner-gate"),
    pytest.param(
        3, "stopped on the advisor's order (see the park comment below)", "Expected: 60 minutes", 1490,
        id="superheroes-2071",
    ),
    pytest.param(
        8, "parked at Step B (add_repo refused, [Permission Grant]); see the park comment",
        "Expected: 60 minutes", 80, id="superheroes-1948",
    ),
]


@pytest.mark.parametrize("gap, phase, expected, created_before", _RECORDED_PARKS)
def test_p9_the_recorded_park_then_a_seconds_later_parked_progress_edit_stays_terminal(
    gap, phase, expected, created_before,
):
    # axis: grace window + phase — the recorded live shapes: a park then a progress edit seconds later with a parked or stopped phase is still a park
    park, progress = _park_then_progress(gap, phase=phase, expected=expected, created_before=created_before)
    _only_park([park, progress])
    _only_park([progress, park])


def test_p9_a_recorded_park_shape_is_lane_terminal_through_the_arm(repo):
    # axis: grace window + phase — the recorded shape drives the arm to lane-terminal with the park
    _cloud_lane(repo, "cloud-a", 101)
    park, progress = _park_then_progress(
        5, phase="parked on a second owner gate", expected="Expected: 240 minutes", park_age=1000,
    )
    launch = _only_launch(_arm(repo, _NoteGh([park, progress])))
    assert (launch["state"], launch["commentId"]) == ("parked", 7)


def test_p10_a_progress_edit_301_seconds_after_the_park_with_a_building_phase_supersedes_it():
    # axis: SUPERSEDED by progress — a resumed phase past the window supersedes the park
    park, progress = _park_then_progress(301, phase="building WO-2 after the advisor's answer")
    assert _terminals([park, progress], lane_age=_WIDE) == []


def test_p10_the_real_resume_two_hours_forty_three_minutes_later_supersedes_the_park():
    # axis: resum exception — the field resume shape: a phase that names the park but says it resumed supersedes it
    park, progress = _park_then_progress(9780, phase="resumed after the park; building")
    assert _terminals([park, progress], lane_age=_WIDE) == []


@pytest.mark.parametrize("gap, superseded", [(5, False), (299, False), (300, False), (301, True)])
def test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after(gap, superseded):
    # axis: STRICT window — exactly PARK_SUPERSESSION_GRACE_SECONDS keeps the park, one second more supersedes it
    assert ww.PARK_SUPERSESSION_GRACE_SECONDS == 300
    park, progress = _park_then_progress(gap, phase="building WO-2")
    if superseded:
        assert _terminals([park, progress], lane_age=_WIDE) == []
    else:
        _only_park([park, progress])


@pytest.mark.parametrize("phase", [
    pytest.param("parked on a second owner gate", id="parked-on-a-gate"),
    pytest.param("still parked awaiting review", id="still-parked"),
    pytest.param("Still stopped for owner", id="still-stopped-capitalised"),
    pytest.param("stopped", id="stopped"),
    pytest.param("PARKED", id="PARKED"),
    pytest.param("parking-lot review", id="parking-lot"),
])
def test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park(phase):
    # axis: phase veto — an edit long after the park whose phase reads parked or stopped (any case, any word) is not a resume
    park, progress = _park_then_progress(3600, phase=phase)
    _only_park([park, progress])


def test_p12_a_progress_edit_past_the_window_with_no_phase_or_an_empty_phase_keeps_the_park():
    # axis: phase veto — a missing or empty Phase line never supersedes
    no_phase_body = "\n".join([cb.PROGRESS_HEADER, "", "Now running: the suite", "Expected: 60 minutes"])
    park, missing = _park_then_progress(3600, body=no_phase_body)
    assert ww._cloud_progress([missing], _lanes({"cloud-a": (101, _WIDE)}))["cloud-a"]["phase"] is None
    _only_park([park, missing])
    park, empty = _park_then_progress(3600, phase="")
    assert ww._cloud_progress([empty], _lanes({"cloud-a": (101, _WIDE)}))["cloud-a"]["phase"] is None
    _only_park([park, empty])


@pytest.mark.parametrize("phase, reads_resumed", [
    ("building WO-2", True), ("gate", True), ("Resumed: building", True), ("parked, then resumed", True),
    ("parked", False), ("PARKED", False), ("Stopped for owner", False), ("parking-lot review", False),
    ("", False), (None, False), (5, False), (["resumed"], False),
])
def test_p12_the_phase_helper_reads_resumed_only_for_a_nonempty_string(phase, reads_resumed):
    # axis: phase helper — None, empty and non-string never read resumed; park/stop words veto unless a resum word is present
    assert ww._phase_reads_resumed(phase) is reads_resumed


def test_p13_a_builder_note_five_seconds_after_the_park_still_supersedes_it():
    # axis: SUPERSEDED by note — the note rule is unchanged: created strictly after the park, no window, no phase
    park, progress = _park_then_progress(3, phase="parked on a second owner gate", park_age=1000)
    note = _comment(8, 101, age=995)
    assert _terminals([park, note], lane_age=_WIDE) == []
    assert _terminals([park, progress, note], lane_age=_WIDE) == []
