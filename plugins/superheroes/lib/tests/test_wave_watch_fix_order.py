"""The wave watch watches a terminal cloud lane again once it is sent a fix order (#2148).

A `vet not-ready` amendment, or a recorded relay of a fix order to the lane's session, re-opens a lane
whose handback or park is recorded; the watch then reads it exactly like a live cloud lane over the
window [reopenedAt, close), the close being its first non-superseded ending comment. A comments read
that did not complete names the issues it could not read under `unreadIssues`.

Amendment timestamps are wall-clock `time.time()`, so a comment "after the fix order" is created in
the future (`age` negative) and one "before" it in the past.
"""
import json
import os
import time
from datetime import datetime, timezone

import cloud_builder as cb
import cloud_relay as cr
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import (  # noqa: F401
    _BATCH, _CONFIG_DIR, _NOTE_BODY, _NoteGh, _arm, _cloud_lane, _comment, _note_answered, _ok, _raw,
)
from test_wave_watch_cloud import _FRESH, _QUIET, _WINDOW, _add_local_lane, clock, repo  # noqa: F401
from test_wave_watch_cloud_progress import _EXPECTED_60, _LONG_AGO, _ProgressGh, _progress  # noqa: F401


def _ending(kind):
    return cb.terminal_text(kind, "Done with the work.")["comment"]


def _handed_back(repo_root, launch_id="cloud-a", issue=101, **lane):
    _cloud_lane(repo_root, launch_id, issue, **lane)
    assert ll.record_outcome(repo_root, launch_id, "handback", "built and gated")["ok"] is True


def _fix_order(repo_root, launch_id="cloud-a"):
    assert ll.amend(repo_root, launch_id, "vet", "not-ready", "needs the narrow fix")["ok"] is True


def _reopened(repo_root, launch_id="cloud-a", issue=101, **lane):
    _handed_back(repo_root, launch_id, issue, **lane)
    _fix_order(repo_root, launch_id)


def _amend_at(repo_root, launch_id, value, age, kind="vet"):
    """An amendment recorded `age` seconds ago, to lay a second cycle behind the first."""
    assert ll.append(repo_root, {
        "event": ll.AMENDMENT_EVENT, "launchId": launch_id, "ts": time.time() - age,
        "schema": ll.SCHEMA, "kind": kind, "value": value, "note": "n",
    })


def _later(comment_id, body=_NOTE_BODY, issue=101, secs=30):
    return _comment(comment_id, issue, body, age=-secs)


def _only_launch(result):
    assert result["event"] == ww.EVENT_LANE_TERMINAL, result
    [launch] = result["launches"]
    return launch


def _relay_stamp(age=0):
    stamp = datetime.fromtimestamp(time.time() - age, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _relay_path(repo_root):
    path, why = cr._state_path(repo_root, os.environ)
    assert why is None
    return path


def _relay(repo_root, *entries):
    pending = {
        e["msgId"]: {"session": "cloud-101", "forward": "f", "configDir": _CONFIG_DIR,
                     "relay": "r", "sentAfter": _relay_stamp(), **e}
        for e in entries
    }
    with open(_relay_path(repo_root), "w") as fh:
        json.dump({"relays": {}, "pending": pending}, fh)


def _delivered(msg_id="m1", **extra):
    return {"msgId": msg_id, "fixOrder": True,
            "decision": {"delivered": True, "reason": None, "at": _relay_stamp()}, **extra}


# --- row 1: a fix order re-opens a handed-back lane ----------------------------------


def test_row1_a_note_after_a_fix_order_surfaces_as_a_builder_note(repo):
    _reopened(repo)
    result = _arm(repo, _NoteGh([_later(7)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [7]
    assert result["launchId"] == "cloud-a"


def test_row1_a_park_after_a_fix_order_is_lane_terminal_parked(repo):
    _reopened(repo)
    launch = _only_launch(_arm(repo, _NoteGh([_later(7, _ending("park"))])))
    assert (launch["launchId"], launch["state"], launch["commentId"]) == ("cloud-a", "parked", 7)


def test_row1_a_handback_after_a_fix_order_is_lane_terminal_handback(repo):
    _reopened(repo)
    launch = _only_launch(_arm(repo, _NoteGh([_later(7, _ending("handback"))])))
    assert (launch["launchId"], launch["state"], launch["commentId"]) == ("cloud-a", "handback", 7)
    assert launch["cloudSessionName"] == "cloud-101"


# --- rows 2-3: the close, the closers, and a lane never sent a fix order ----------------


def test_row2_after_the_closing_handback_a_later_note_is_not_surfaced_and_the_lane_is_not_stale(repo):
    _reopened(repo, start_age=_LONG_AGO)
    # The progress comment is future-dated, so a watched lane would read stale on it at once.
    gh = _ProgressGh([
        _later(5, _ending("handback"), secs=10), _later(6, secs=20),
        _progress(9, 101, updated_age=-3000, created_age=3000),
    ])
    # One tick, so the comments read is complete: a tick that cannot read knows no close.
    assert _only_launch(ww.run(repo, _BATCH, gh_run=gh))["commentId"] == 5
    assert _note_answered(repo, 5)["ok"] is True
    assert ww.run(repo, _BATCH, gh_run=gh)["event"] == ww.EVENT_TIMER


def test_row2_comments_sharing_the_closing_second_are_ordered_by_comment_id(repo):
    _reopened(repo, start_age=_LONG_AGO)
    comments = [_later(5, _ending("handback"), secs=10), _comment(6, 101, cb.handover_text("a" * 40), age=-10),
                _later(7, secs=10)]
    for comment in comments:
        comment["created_at"] = comments[0]["created_at"]
    # The handback (5) closes the lane: the handover (6) and the note (7) of its second are after it.
    assert _only_launch(ww.run(repo, _BATCH, gh_run=_ProgressGh(comments)))["commentId"] == 5


def _closed_by_a_handback(repo_root):
    """A reopened lane whose closing handback (comment 5) is answered, and the comments that read it:
    the handback, and a future-dated progress comment that would read the lane stale at once if watched."""
    _reopened(repo_root, start_age=_LONG_AGO)
    assert _note_answered(repo_root, 5)["ok"] is True
    return [_later(5, _ending("handback"), secs=10), _progress(9, 101, updated_age=-3000, created_age=3000)]


def test_row2_a_closed_lane_stays_closed_on_a_tick_that_makes_no_comments_read(repo):
    # The arm reads on its ticks at 0, 1 and 2 seconds; the tick at its 3-second deadline has no budget.
    result = _arm(repo, _ProgressGh(_closed_by_a_handback(repo)))
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]  # the deadline tick made no read


def test_row2_a_stored_close_does_not_outlive_a_newer_fix_order(repo, clock):
    _handed_back(repo, start_age=_LONG_AGO)
    _amend_at(repo, "cloud-a", "not-ready", 1000)
    assert _note_answered(repo, 5)["ok"] is True
    gh = _ProgressGh([_comment(5, 101, _ending("handback"), age=500),
                      _progress(9, 101, updated_age=-3000, created_age=3000)])

    def sleep(duration):
        clock.sleep(duration)
        if clock.now >= 3:  # a second fix order lands before the deadline tick, which makes no read
            _fix_order(repo)

    result = _arm(repo, gh, sleep=sleep)
    assert result["event"] == ww.EVENT_LANE_STALE
    assert [launch["launchId"] for launch in result["launches"]] == ["cloud-a"]


def test_row2_a_partial_read_keeps_the_close_a_complete_read_showed(repo):
    comments = _closed_by_a_handback(repo)
    # axis: a partial read filters notes and endings by the close a complete read showed — see bite-proof record wo_2148_fix_order.md
    gh = _ProgressGh(comments, script=[
        lambda argv: _ok(argv, comments),
        lambda argv: _ok(argv, comments + [_later(6, secs=20)], link=True),  # a note after the close
        lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n"),
    ])
    # Ticks at 0 (complete), 1 (partial) and 2 seconds (the deadline: no read).
    result = ww.watch_arm(repo, _BATCH, max_seconds=2, interval_seconds=1, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


def test_row2_a_partial_read_does_not_surface_an_ending_after_the_close_a_complete_read_showed(repo):
    # axis: a partial read filters notes and endings by the close a complete read showed — see bite-proof record wo_2148_fix_order.md
    comments = _closed_by_a_handback(repo)
    later_stop = _later(6, _ending("park"), secs=20)
    gh = _ProgressGh(comments, script=[
        lambda argv: _ok(argv, comments),
        lambda argv: _ok(argv, comments + [later_stop], link=True),
        lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n"),
    ])
    result = ww.watch_arm(repo, _BATCH, max_seconds=2, interval_seconds=1, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER


def test_row2_a_partial_read_drops_a_cached_park_close_that_a_note_it_shows_supersedes(repo):
    _reopened(repo)
    assert _note_answered(repo, 5)["ok"] is True
    park, note = _later(5, _ending("park"), secs=10), _later(6, secs=20)
    # axis: a cached park close that the comments a partial read observed show superseded is dropped, so its note surfaces — see bite-proof record wo_2148_fix_order.md
    gh = _NoteGh([park], script=[
        lambda argv: _ok(argv, [park]),
        lambda argv: _ok(argv, [park, note], link=True),  # page one: the park and a note after it
        lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n"),  # page two fails
    ])
    result = ww.watch_arm(repo, _BATCH, max_seconds=2, interval_seconds=1, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [n["commentId"] for n in result["notes"]] == [6]


def test_row2_a_later_reoutcome_closes_the_fix_order_and_the_lane_is_not_watched(repo):
    _reopened(repo)
    assert ll.amend(repo, "cloud-a", "reoutcome", "handback", "re-handed back")["ok"] is True
    gh = _NoteGh([_later(7)])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
    assert gh.note_calls() == []


def test_row2_a_vet_ready_or_parked_blocker_after_the_fix_order_closes_it(repo):
    for n, ruling in enumerate(("ready", "parked-blocker")):
        lane, issue = "cloud-%d" % n, 300 + n
        _reopened(repo, lane, issue)
        assert ll.amend(repo, lane, "vet", ruling, "settled")["ok"] is True
        gh = _NoteGh([_later(7, issue=issue)])
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
        assert gh.note_calls() == []


def test_row3_a_handed_back_lane_with_no_fix_order_stays_unwatched(repo):
    _handed_back(repo)
    gh = _NoteGh([_later(7)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER
    assert gh.note_calls() == [] and "cloudLanes" not in result


# --- row 4: nothing from before the fix order re-fires -----------------------------------


def test_row4_the_old_handback_comment_does_not_re_fire_after_not_ready(repo):
    _reopened(repo)
    gh = _NoteGh([_comment(7, 101, _ending("handback"), age=600)])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
    assert gh.note_calls()  # the lane was read, and the old ending was not its ending


def test_row4_an_old_note_does_not_re_fire_after_not_ready(repo):
    _reopened(repo)
    gh = _NoteGh([_comment(7, 101, age=600)])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
    assert gh.note_calls()


# --- row 5: a park closes, and a note after it supersedes it ---------------------------


def test_row5_a_closing_park_then_a_note_that_supersedes_it_then_a_closing_handback(repo):
    _reopened(repo)
    park, note = _later(5, _ending("park"), secs=10), _later(6, secs=20)
    assert _only_launch(_arm(repo, _NoteGh([park])))["state"] == "parked"
    superseded = _arm(repo, _NoteGh([park, note]))
    assert superseded["event"] == ww.EVENT_BUILDER_NOTE
    assert [n["commentId"] for n in superseded["notes"]] == [6]
    closed = _arm(repo, _NoteGh([park, note, _later(7, _ending("handback"), secs=30)]))
    assert _only_launch(closed)["state"] == "handback"


# --- row 6: the stale floors --------------------------------------------------------------


def test_row6_a_progress_comment_last_edited_before_the_fix_order_is_not_stale(repo):
    _reopened(repo, start_age=_LONG_AGO)
    gh = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 3600)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER
    [lane] = result["cloudLanes"]
    assert lane["phase"] == "gate"


def test_row6_activity_quiet_before_the_fix_order_is_not_stale(repo):
    _reopened(repo, start_age=_LONG_AGO)
    result = _arm(repo, _ProgressGh([]))
    assert result["event"] == ww.EVENT_TIMER
    assert 0 <= result["cloudLanes"][0]["activityAgeSeconds"] < _FRESH


# --- row 7: a fix-order relay record re-opens the lane -----------------------------------


def test_row7_a_delivered_fix_order_relay_re_opens_the_lane(repo):
    _handed_back(repo)
    _relay(repo, _delivered())
    result = _arm(repo, _NoteGh([_later(7)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["cloudLanes"][0]["reopenedBy"] == "fix-order-relay"


def test_row7_the_window_opens_at_the_send_not_at_a_later_check(repo):
    # axis: the relay opens the window at the message's sentAfter, never the decision's check time — see bite-proof record wo_2148_fix_order.md
    _handed_back(repo, start_age=_LONG_AGO)
    # Sent 100 seconds ago, the builder answered 50 seconds ago, and the check only now read it delivered.
    _relay(repo, _delivered(sentAfter=_relay_stamp(age=100)))
    result = _arm(repo, _NoteGh([_comment(7, 101, _NOTE_BODY, age=50)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [7]
    assert result["cloudLanes"][0]["reopenedBy"] == "fix-order-relay"


def test_row7_a_relay_that_may_hold_the_text_re_opens_the_lane(repo):
    _handed_back(repo)
    _relay(repo, {"msgId": "m1", "fixOrder": True,
                  "decision": {"delivered": False, "reason": "relay-silent", "at": _relay_stamp()}})
    assert _arm(repo, _NoteGh([_later(7)]))["event"] == ww.EVENT_BUILDER_NOTE


def test_row7_an_undecided_draft_does_not_re_open_the_lane(repo):
    _handed_back(repo)
    _relay(repo, {"msgId": "m1", "fixOrder": True, "decision": None})
    assert _arm(repo, _NoteGh([_later(7)]))["event"] == ww.EVENT_TIMER


def test_row7_a_send_failed_relay_does_not_re_open_the_lane(repo):
    _handed_back(repo)
    _relay(repo, {"msgId": "m1", "fixOrder": True,
                  "decision": {"delivered": False, "reason": "relay-send-failed", "at": _relay_stamp()}})
    assert _arm(repo, _NoteGh([_later(7)]))["event"] == ww.EVENT_TIMER


def test_row7_a_delivered_relay_without_the_fix_order_flag_does_not_re_open_the_lane(repo):
    _handed_back(repo)
    plain = _delivered()
    del plain["fixOrder"]
    _relay(repo, plain)
    assert _arm(repo, _NoteGh([_later(7)]))["event"] == ww.EVENT_TIMER


def test_row7_a_relay_to_another_session_does_not_re_open_the_lane(repo):
    _handed_back(repo)
    _relay(repo, _delivered(session="cloud-999"))
    assert _arm(repo, _NoteGh([_later(7)]))["event"] == ww.EVENT_TIMER


def test_row7_a_relay_stamp_that_cannot_be_read_is_skipped(repo):
    _handed_back(repo)
    _relay(repo, _delivered(sentAfter="yesterday"))
    result = _arm(repo, _NoteGh([_later(7)]))
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_FIX_ORDER_UNAVAILABLE not in result["degraded"]


# --- row 8: a second cycle ------------------------------------------------------------------


def test_row8_a_second_fix_order_re_opens_a_lane_the_first_cycle_closed(repo):
    _handed_back(repo)
    _amend_at(repo, "cloud-a", "not-ready", 1000)
    closing = _comment(5, 101, _ending("handback"), age=500)
    assert _only_launch(_arm(repo, _NoteGh([closing])))["commentId"] == 5
    _amend_at(repo, "cloud-a", "not-ready", 100)
    result = _arm(repo, _NoteGh([closing, _comment(7, 101, age=50)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [7]


# --- row 9: a read that did not complete names the issues it could not read -----------------


def _two_pages_then_failure():
    return [lambda argv: _ok(argv, [], link=True), lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n")]


_UNREAD = [{"launchId": "cloud-a", "issue": 101}, {"launchId": "cloud-b", "issue": 202}]


def test_row9_a_partial_read_names_every_watched_issue(repo):
    _reopened(repo)
    _cloud_lane(repo, "cloud-b", 202)
    result = _arm(repo, _NoteGh(script=_two_pages_then_failure()))
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == _UNREAD


def test_row9_a_single_tick_names_the_unread_issues_too(repo):
    _reopened(repo)
    _cloud_lane(repo, "cloud-b", 202)
    result = ww.run(repo, _BATCH, gh_run=_NoteGh(script=_two_pages_then_failure()))
    assert result["unreadIssues"] == _UNREAD


def test_row9_an_event_found_on_a_partial_read_carries_the_unread_issues(repo):
    _reopened(repo)
    page_one = lambda argv: _ok(argv, [_later(7)], link=True)  # noqa: E731
    result = ww.run(repo, _BATCH, gh_run=_NoteGh(script=[page_one, _two_pages_then_failure()[1]]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


def test_row9_a_complete_read_carries_no_unread_issues(repo):
    _reopened(repo)
    # (An arm's closing tick at its deadline has no budget left to read, so its timer is not a complete read.)
    result = _arm(repo, _NoteGh([_later(7)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE and "unreadIssues" not in result
    assert "unreadIssues" not in ww.run(repo, _BATCH, gh_run=_NoteGh([]))


def test_row9_a_tick_that_made_no_request_discloses_it_and_names_no_unread_issue(repo):
    _reopened(repo)
    result = _arm(repo, _NoteGh([]))  # the deadline tick has no budget to read
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert "unreadIssues" not in result


def test_row9_a_lane_named_unread_in_an_arm_stays_named_in_the_loop_ceiling_timer(repo):
    _reopened(repo)
    result = ww.loop(
        repo, _BATCH, max_seconds=2, interval_seconds=1, max_total_seconds=3,
        gh_run=_NoteGh(script=_two_pages_then_failure()),
    )
    assert result["event"] == ww.EVENT_TIMER
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


def test_row9_a_lane_named_unread_in_an_earlier_arm_stays_named_when_a_later_arm_exits_on_attention(repo):
    # axis: an attention exit keeps the lanes an earlier arm named unread — see bite-proof record wo_2148_fix_order.md
    _reopened(repo)
    arms = [
        {"ok": True, "event": ww.EVENT_TIMER, "unreadIssues": [{"launchId": "cloud-a", "issue": 101}]},
        {"ok": True, "event": ww.EVENT_BUILDER_NOTE, "notes": []},
    ]
    result = ww.loop(
        repo, _BATCH, max_seconds=2, interval_seconds=1,
        run_fn=lambda *args, **kwargs: dict(arms.pop(0)),
    )
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["arms"] == 2
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


# --- row 10: an unreadable relay state, and the cloud-only rule -----------------------------


def test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works(repo):
    _reopened(repo)
    with open(_relay_path(repo), "w") as fh:
        fh.write("{not json")
    result = _arm(repo, _NoteGh([_later(7)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert ww.DEGRADATION_FIX_ORDER_UNAVAILABLE in result["degraded"]
    assert ww.DEGRADATION_FIX_ORDER_UNAVAILABLE in ww.DEGRADATIONS


def test_row10_the_relay_is_not_read_while_no_lane_is_terminal(repo):
    _cloud_lane(repo, "cloud-a", 101)
    with open(_relay_path(repo), "w") as fh:
        fh.write("{not json")
    assert ww.DEGRADATION_FIX_ORDER_UNAVAILABLE not in ww.run(repo, _BATCH, gh_run=_NoteGh())["degraded"]


def test_row10_a_local_lane_with_a_handback_is_never_re_opened_by_not_ready(repo):
    _add_local_lane(repo, "local-a", 55, pid=999999999)
    assert ll.record_outcome(repo, "local-a", "handback", "built")["ok"] is True
    assert ll.amend(repo, "local-a", "vet", "not-ready", "needs a fix")["ok"] is True
    result = ww.run(repo, _BATCH, gh_run=_NoteGh())
    assert result["event"] == ww.EVENT_TIMER


# --- the helper's fail-closed edges ----------------------------------------------------------


def _info(amendments, **overrides):
    info = {"place": ll.PLACE_CLOUD, "started": True, "terminal": True, "terminalKind": "outcome",
            "amendments": amendments}
    info.update(overrides)
    return info


def _am(kind, value, ts):
    return {"kind": kind, "value": value, "note": "n", "ts": ts}


def test_a_malformed_amendment_or_relay_time_is_skipped_and_never_raises():
    junk = [None, "x", 3, {}, _am("vet", "not-ready", float("nan")), _am("vet", "not-ready", float("inf")),
            _am("vet", "not-ready", True), _am("vet", "not-ready", "5"), _am("reoutcome", "park", None)]
    assert ww._reopen_candidate(_info(junk), [float("nan"), "x", None, True]) is None
    assert ww._reopen_candidate(_info(junk + [_am("vet", "not-ready", 50.0)]), []) == (50.0, "vet-not-ready")
    assert ww._reopen_candidate(_info(junk), [float("nan"), 70.0]) == (70.0, "fix-order-relay")
    assert ww._reopen_candidate(_info(None), []) is None


def test_the_newest_opener_must_be_strictly_later_than_the_newest_closer():
    opener = _am("vet", "not-ready", 100.0)
    for closer in (_am("reoutcome", "park", 100.0), _am("reoutcome", "handback", 150.0),
                   _am("vet", "ready", 150.0), _am("vet", "parked-blocker", 100.0)):
        assert ww._reopen_candidate(_info([opener, closer]), []) is None
        assert ww._reopen_candidate(_info([closer]), [120.0]) == (
            (120.0, "fix-order-relay") if closer["ts"] < 120.0 else None)
    assert ww._reopen_candidate(_info([_am("vet", "ready", 90.0), opener]), []) == (100.0, "vet-not-ready")
    assert ww._reopen_candidate(_info([_am("evidence", "x", 1.0), opener]), [100.0]) == (100.0, "vet-not-ready")


def test_a_refused_unstarted_local_or_unfinished_lane_is_never_re_opened():
    opener = [_am("vet", "not-ready", 100.0)]
    assert ww._reopen_candidate(_info(opener), []) == (100.0, "vet-not-ready")
    for change in ({"terminalKind": "refused"}, {"terminalKind": None}, {"started": False},
                   {"started": None}, {"place": ll.PLACE_LOCAL}, {"terminal": False}):
        assert ww._reopen_candidate(_info(opener, **change), [120.0]) is None


def test_a_reopened_lane_in_ignore_launch_is_not_re_added(repo):
    _reopened(repo)
    gh = _NoteGh([_later(7)])
    assert _arm(repo, gh, ignore_launch_ids=["cloud-a"])["event"] == ww.EVENT_TIMER
    assert gh.note_calls() == []


# --- what the result and the read show for a reopened lane ----------------------------------


def test_the_cloud_lanes_entry_and_the_read_since_show_the_fix_order(repo):
    _reopened(repo, start_age=_LONG_AGO)
    gh = _NoteGh()
    result = ww.run(repo, _BATCH, gh_run=gh)
    at = ll.fold(ll.read(repo)["records"])["launches"]["cloud-a"]["amendments"][-1]["ts"]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at))
    [lane] = result["cloudLanes"]
    assert (lane["reopenedAt"], lane["reopenedBy"]) == (stamp, "vet-not-ready")
    [argv] = gh.note_calls()
    assert "since=%s&" % stamp in argv[-1]


def test_a_live_lane_beside_a_reopened_one_reads_since_the_earlier_of_the_two(repo):
    _reopened(repo, start_age=_LONG_AGO)
    _cloud_lane(repo, "cloud-b", 202, start_age=_QUIET)
    gh = _NoteGh()
    ww.run(repo, _BATCH, gh_run=gh)
    started = ll.fold(ll.read(repo)["records"])["launches"]["cloud-b"]["reservedTs"]
    [argv] = gh.note_calls()
    assert "since=%s&" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)) in argv[-1]


def test_a_reopened_lane_does_not_mutate_the_folded_lane(repo):
    _reopened(repo)
    _all, live, _ok_ = ww._derive_batch_lanes(repo, _BATCH, os.environ, set(), ())
    assert live["cloud-a"]["reopenedBy"] == "vet-not-ready"
    assert "reopenedAt" not in _all["cloud-a"]
