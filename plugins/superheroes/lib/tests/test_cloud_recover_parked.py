# plugins/superheroes/lib/tests/test_cloud_recover_parked.py
"""Conformance: `cloud_recover.assess` answers `parked` when the lane's issue holds a builder stop or park that
is the builder's last word, and never otherwise. Same fixtures as test_cloud_recover.py: a real bare remote, only
`gh` faked through `run=`; the comments, push events and answered-notes record are set by each test.

Bites on: the later-push check (a stop older than pushed work is not current), the push-time-source check (a
commit-time fallback is never trusted), the answered check, newest-only (a later handover or handback ends a
park), the reserved-first attempt cutoff, the comments-read guard, and `fresh` ahead of `parked`.
Residual blind spots: a comment edited after it was posted keeps its creation time here; two terminal comments
created in the same second are told apart only by kind (a handover or handback among them refuses the park);
the push check trusts GitHub's push events and does not see a force-push that left the head sha unchanged.
"""
import os
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder  # noqa: E402
import cloud_recover as CR  # noqa: E402
import launch_ledger as ll  # noqa: E402
import wave_watch  # noqa: E402
from test_cloud_recover import (  # noqa: E402,F401
    BRANCH, REPO, Gh, _assess, _comment, _died, _event, _git, _iso_ago, _lane, _push, _state, _successor, w,
)

STOP = cloud_builder.terminal_text("stop", "Stopped at intake: the brief names no surface.")["comment"]
PARK = cloud_builder.terminal_text("park", "Parked on a question: which of the two layouts?")["comment"]
HANDBACK = cloud_builder.terminal_text("handback", "The work is done.")["comment"]
FOOTERED_PARK = PARK + "\n\n" + cloud_builder.CLOUD_FOOTER


def _git_date(age):
    return _iso_ago(age).replace("Z", "+0000")


def _pushed_at(w, age, name="a", commit_age=None):
    """Push a branch for issue 17 whose push event was `age` seconds ago; returns its head sha."""
    sha = _push(w, BRANCH, name, when=_git_date(commit_age) if commit_age else None)
    w.gh.activity[BRANCH] = [_event(BRANCH, sha, _iso_ago(age))]
    return sha


def _comment_calls(w):
    return [c for c in w.gh.calls if c[0] == "gh" and "/comments?" in c[-1]]


def test_1_a_stop_newer_than_the_last_activity_reads_parked_and_names_the_comment(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600, cid=11)]
    out = _assess(w, state="idle")
    assert (out["verdict"], out["evidence"], out["parkRead"]) == ("parked", "builder-stop", "ok")
    assert out["parkComment"]["commentId"] == 11 and out["parkComment"]["kind"] == "stop"
    assert out["parkComment"]["url"].endswith("#issuecomment-11")
    assert out["parkComment"]["createdAt"] == w.gh.comments[0]["created_at"]


def test_1_a_footered_park_is_parked_even_when_the_session_is_gone(w):
    _lane(w, "l1")
    _pushed_at(w, 1500)  # work pushed before the park: the park is the builder's last word
    w.gh.comments = [_comment(FOOTERED_PARK, age=600, cid=12)]
    out = _assess(w, state="failed")
    assert (out["verdict"], out["evidence"], out["parkRead"]) == ("parked", "builder-park", "ok")
    assert out["parkComment"]["commentId"] == 12 and out["parkComment"]["kind"] == "park"
    assert not os.path.exists(CR._state_path(w.root, os.environ))


@pytest.mark.parametrize("state,verdict,evidence", [("idle", "ask-to-push", None), ("failed", "stopped", "session-failed")])
def test_2_a_stop_older_than_later_pushed_work_is_not_current(w, state, verdict, evidence):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=3000)]
    _pushed_at(w, 600)
    out = _assess(w, state=state)
    assert (out["verdict"], out["evidence"]) == (verdict, evidence)
    assert out["parkComment"] is None and out["parkRead"] == "ok"


@pytest.mark.parametrize("state,age,verdict,evidence", [
    ("idle", None, "ask-to-push", None), ("failed", None, "stopped", "session-failed"), ("working", 60, "working", None)])
def test_3_no_terminal_comment_keeps_todays_answers(w, state, age, verdict, evidence):
    _lane(w, "l1")
    w.gh.comments = [_comment("an ordinary note", age=600)]
    out = _assess(w, state=state, age=age)
    assert (out["verdict"], out["evidence"]) == (verdict, evidence) and out["parkComment"] is None


def test_3b_a_fresh_working_lane_is_working_whatever_the_comments_say(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600)]
    out = _assess(w, state="working", age=60)
    assert out["verdict"] == "working" and out["parkComment"] is None and out["parkRead"] is None


def test_4_a_commit_time_fallback_is_not_trusted(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600)]
    _push(w, BRANCH, "a", when=_git_date(3000))  # older than the stop, but no push event can be read for it
    entry = CR.pushed(w.root, 17, repo=REPO, run=w.gh)["newest"]
    assert entry["pushTimeSource"] == "commit"
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["parkComment"] is None and out["parkRead"] == "failed"


def test_5_an_answered_park_is_not_current_and_an_older_stop_does_not_replace_it(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=2000, cid=1), _comment(PARK, age=600, cid=2)]
    wave_watch.note_answered(w.root, 2)
    out = _assess(w, state="failed")
    assert (out["verdict"], out["evidence"]) == ("stopped", "session-failed") and out["parkComment"] is None


@pytest.mark.parametrize("reverse", [False, True], ids=["ascending", "descending"])
def test_5_two_parks_in_one_second_are_told_apart_by_the_larger_comment_id(w, reverse):
    _lane(w, "l1")
    when = _iso_ago(600)
    parks = [dict(_comment(PARK, cid=cid), created_at=when, updated_at=when) for cid in (21, 22)]
    w.gh.comments = parks[::-1] if reverse else parks
    wave_watch.note_answered(w.root, 22)
    out = _assess(w, state="failed")
    assert (out["verdict"], out["evidence"]) == ("stopped", "session-failed") and out["parkComment"] is None


@pytest.mark.parametrize("footer,verdict,evidence", [("", "stopped", "handover"), ("\n\n" + cloud_builder.CLOUD_FOOTER, "stopped", "handover")],
                         ids=["bare-handover", "footered-handover"])
def test_6_a_later_handover_beats_a_park(w, footer, verdict, evidence):
    # since #1930, cloud_builder.handover_sha also reads a handover that carries the cloud's footer, so both shapes are a handover; either way the park must not be believed
    _lane(w, "l1")
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_comment(PARK, age=900, cid=1), _comment(cloud_builder.handover_text(sha) + footer, age=300, cid=2)]
    out = _assess(w, state="idle")
    assert (out["verdict"], out["evidence"]) == (verdict, evidence) and out["parkComment"] is None


def test_7_the_attempt_cutoff_is_the_reserved_time(w):
    _lane(w, "l1")  # reserved 7260 s ago, started 7200 s ago
    w.gh.comments = [_comment(STOP, age=7230, cid=1)]
    between = _assess(w, state="idle")
    assert between["verdict"] == "parked" and between["parkComment"]["commentId"] == 1
    w.gh.comments = [_comment(STOP, age=7500, cid=1)]
    before = _assess(w, state="idle")
    assert before["verdict"] == "ask-to-push" and before["parkComment"] is None


def test_8_a_later_handback_beats_a_park(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(PARK, age=900, cid=1), _comment(HANDBACK, age=300, cid=2)]
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["parkComment"] is None


def test_8_a_handback_in_the_same_second_as_a_park_refuses_the_park(w):
    _lane(w, "l1")
    when = _iso_ago(600)
    w.gh.comments = [dict(_comment(PARK, cid=1), created_at=when, updated_at=when),
                     dict(_comment(HANDBACK, cid=2), created_at=when, updated_at=when)]
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["parkComment"] is None


def test_9_comments_that_cannot_be_read_are_no_park(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600)]
    w.gh.comments_fail = True
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["parkComment"] is None and out["parkRead"] == "failed"
    assert out["handoverRead"] == "failed"


def test_9_an_answered_record_that_cannot_be_read_is_no_park(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600)]
    path = wave_watch._answered_notes_path(w.root, os.environ, create=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json")
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["parkComment"] is None and out["parkRead"] == "failed"


def test_9_a_remote_that_cannot_be_listed_is_no_park(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600)]
    _git(w.root, "remote", "set-url", "origin", str(w.tmp / "nowhere.git"))
    out = _assess(w, state="idle")
    assert out["verdict"] == "ask-to-push" and out["parkComment"] is None and out["parkRead"] == "failed"


def test_10_one_comments_request_serves_the_handover_and_the_park(w):
    _lane(w, "l1")
    w.gh.comments = [_comment(STOP, age=600)]
    out = _assess(w, state="idle")
    assert out["verdict"] == "parked" and out["handoverRead"] == "ok"
    assert len(_comment_calls(w)) == 1


def test_11_a_park_withdraws_an_earlier_stop_authorization(w):
    _lane(w, "l1")
    assert _assess(w, state="failed")["verdict"] == "stopped"
    assert "l1" in _state(w)["assessed"]
    w.gh.comments = [_comment(STOP, age=600)]
    assert _assess(w, state="failed")["verdict"] == "parked"
    assert "l1" not in _state(w)["assessed"]
    _died(w, "l1")
    assert _successor(w, "l1") == {"ok": False, "reason": "lane-not-assessed-stopped"}


# ---------------------------------------------------------------- #2319: an archived or self-archived lane reads stopped

SA = "launch-s1"  # a real-shaped launch id: the fixtures' default "l1" does not match cloud_builder._LAUNCH_ID_RE


def _self_archive(sha, launch_id=SA, age=300, cid=40, footer=""):
    return _comment(cloud_builder.self_archive_text(launch_id, sha) + footer, age=age, cid=cid)


def test_t1_an_archived_lane_with_a_newer_park_reads_stopped_and_gets_a_successor_premise(w):
    _lane(w, "l1")
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_comment(PARK, age=600, cid=11)]
    out = _assess(w, state="archived")
    assert (out["verdict"], out["evidence"]) == ("stopped", "session-archived")
    _died(w, "l1")
    got = _successor(w)
    assert got["ok"] is True and got["premise"]["adoptsBranch"] == BRANCH and got["premise"]["adoptsHead"] == sha


def test_t2_a_self_archive_record_newer_than_a_park_reads_stopped_and_names_its_head(w):
    _lane(w, SA)
    pushed = _pushed_at(w, 1500)
    w.gh.comments = [_comment(PARK, age=600, cid=11), _self_archive(pushed, age=300)]
    out = _assess(w, launch_id=SA, state="idle")
    assert (out["verdict"], out["evidence"]) == ("stopped", "self-archived")
    assert out["stoppedAt"] == CR._epoch(w.gh.comments[1]["created_at"])
    assert _state(w)["assessed"][SA]["handoverSha"] == pushed
    _died(w, SA)
    got = _successor(w, launch_id=SA)
    assert got["ok"] is True and got["premise"]["adoptsBranch"] == BRANCH and got["premise"]["adoptsHead"] == pushed


def test_t2_the_self_archive_record_keeps_its_own_head_and_a_branch_moved_past_it_is_refused(w):
    _lane(w, SA)
    named = _pushed_at(w, 1500)
    w.gh.comments = [_self_archive(named)]
    _push(w, BRANCH, "b")  # work pushed after the record's head: the record's head is kept, not the newest pushed
    out = _assess(w, launch_id=SA, state="idle")
    assert (out["verdict"], out["evidence"]) == ("stopped", "self-archived")
    assert _state(w)["assessed"][SA]["handoverSha"] == named
    _died(w, SA)
    assert _successor(w, launch_id=SA) == {"ok": False, "reason": "handover-head-not-pushed"}


def test_t3_e1_a_record_naming_another_launch_or_a_longer_id_is_not_this_lanes_record(w):
    _lane(w, SA)
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_self_archive(sha, launch_id="launch-s2", cid=41), _self_archive(sha, launch_id="launch-s10", cid=42)]
    out = _assess(w, launch_id=SA, state="idle")
    assert out["verdict"] == "ask-to-push" and out["evidence"] is None


def test_t3_e2_a_record_created_before_the_lanes_start_is_not_read(w):
    _lane(w, SA, start_age=300)  # reserved 60s before it started
    sha = _pushed_at(w, 100)
    # dated from the ledger's own recorded times (not a second clock reading, which slow git could skew):
    # the midpoint is after the reservation and before the start
    lane = ll.fold(ll.read(w.root)["records"])["launches"][SA]
    midpoint = (lane["reservedTs"] + lane["startedTs"]) / 2
    assert lane["reservedTs"] < midpoint < lane["startedTs"]
    record = _self_archive(sha)
    record["created_at"] = record["updated_at"] = CR._iso(midpoint)
    w.gh.comments = [record]
    out = _assess(w, launch_id=SA, state="idle")
    assert out["handoverRead"] == "ok" and out["verdict"] == "ask-to-push" and out["evidence"] is None


@pytest.mark.parametrize("make", [
    lambda t: t + "\n\n" + cloud_builder.CLOUD_FOOTER + "\n\n" + cloud_builder.CLOUD_FOOTER,
    lambda t: t + " And one more thing.",
    lambda t: t.replace("launch-s1", "launch-s1x-"),
    lambda t: t.replace("launch-s1", "launch_s1"),
    lambda t: t[:t.index("My pushed head is ") + len("My pushed head is ")] + "abc123. I am archiving this session now.",
    lambda t: t.replace(t[t.index("head is ") + 8:t.index("head is ") + 48], t[t.index("head is ") + 8:t.index("head is ") + 48].upper()),
], ids=["two-footers", "extra-text", "bad-launch-id", "malformed-launch-id", "bad-sha", "uppercase-sha"])
def test_t3_e3_a_malformed_record_is_not_a_record(w, make):
    _lane(w, SA)
    sha = _pushed_at(w, 1500)
    body = make(cloud_builder.self_archive_text(SA, sha))
    assert cloud_builder.self_archive_record(body) is None
    w.gh.comments = [_comment(body, age=300)]
    out = _assess(w, launch_id=SA, state="idle")
    assert out["verdict"] == "ask-to-push" and out["evidence"] is None


def test_t3_e3_one_cloud_footer_is_still_a_record(w):
    _lane(w, SA)
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_self_archive(sha, footer="\n\n" + cloud_builder.CLOUD_FOOTER)]
    out = _assess(w, launch_id=SA, state="idle")
    assert (out["verdict"], out["evidence"]) == ("stopped", "self-archived")


def test_t3_e4_a_comments_read_that_failed_yields_no_self_archive_record(w):
    _lane(w, SA)
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_self_archive(sha)]
    w.gh.comments_fail = True
    out = _assess(w, launch_id=SA, state="idle")
    assert out["handoverRead"] == "failed" and out["verdict"] == "ask-to-push" and out["evidence"] is None


def test_t3_e5_a_fresh_working_lane_with_a_self_archive_record_still_reads_working(w):
    _lane(w, SA)
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_self_archive(sha)]
    out = _assess(w, launch_id=SA, state="working", age=60)
    assert out["verdict"] == "working" and out["evidence"] is None
    assert not os.path.exists(CR._state_path(w.root, os.environ))  # nothing was recorded as stopped


def test_t4_a_parked_lane_that_is_not_archived_and_has_no_record_still_reads_parked(w):
    _lane(w, "l1")
    _pushed_at(w, 1500)
    w.gh.comments = [_comment(PARK, age=600, cid=11)]
    out = _assess(w, state="idle")
    assert (out["verdict"], out["evidence"]) == ("parked", "builder-park")
    _died(w, "l1")
    assert _successor(w) == {"ok": False, "reason": "lane-not-assessed-stopped"}


def test_t5_handover_stopped_ids_returns_a_self_archived_lane_and_not_a_session_archived_one(w):
    _lane(w, SA)
    _lane(w, "l2")
    sha = _pushed_at(w, 1500)
    w.gh.comments = [_self_archive(sha)]
    assert _assess(w, launch_id=SA, state="idle")["evidence"] == "self-archived"
    w.gh.comments = []
    assert _assess(w, launch_id="l2", state="archived")["evidence"] == "session-archived"
    ids, readable = CR.handover_stopped_ids(w.root)
    assert readable is True and ids == {SA}
