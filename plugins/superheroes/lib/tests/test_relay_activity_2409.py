"""Tests for #2409: `check` reads a pointer message delivered on a second basis when the relay's own record shows no
send, the pointer comment still matches the composed body byte for byte, and the message's own lane showed builder
activity on its issue after that comment.

Nothing runs a real `gh` or `claude`. `ActivityGh` is the suite's `FakeGh` that also answers the single comment read
with `created_at`/`updated_at`, and answers `repos/<r>/issues/<n>/comments?since=...&per_page=100&page=N` from a list
of comment dicts, keeping those updated at or after `since` the way GitHub does (a comment created long ago and
edited after the boundary is returned). The lanes are launch-ledger records written through the ledger's own
`reserve`, `append_under_lock` and `terminalize`.
"""
import datetime
import json
import os
import re
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402
import cloud_cleanup as CC  # noqa: E402
import cloud_recover  # noqa: E402
import cloud_relay as cr  # noqa: E402
import launch_ledger as ll  # noqa: E402
from test_cloud_relay import (  # noqa: E402,F401
    BEFORE, REPO_NAME, STAMP, FakeGh, _backdate, _check, _ensure_alive, _post, _send_lines, _state_file,
    _write_record, world,
)
from test_launch_ledger import _declare, _reserved, _started  # noqa: E402

ISSUE = 77
LANE = "issue-77-abcd1234"
SUCCESSOR = "issue-77-ffff0000"
BATCH = "b-activity"
T0 = datetime.datetime(2026, 11, 1, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp()  # the target lane's reserved time
POINTER_AT = T0 + 100  # when the pointer comment was created
SUCCESSOR_AT = T0 + 150  # when a later lane on the same issue was reserved


def iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ActivityGh(FakeGh):
    """FakeGh plus: `times` ({comment id: {"created_at", "updated_at"}}) merged into the single comment read, and
    `listing` (comment dicts) served by the issue comments list, filtered by `updated_at >= since`."""

    def __init__(self, comments=None):
        super().__init__(comments)
        self.times = {}
        self.listing = []
        self.list_fails = False

    def list_calls(self):
        return [c for c in self.calls if re.fullmatch(r"repos/[^/]+/[^/]+/issues/\d+/comments\?.*", c[2])]

    def single_calls(self):
        return [c for c in self.calls if re.fullmatch(r"repos/[^/]+/[^/]+/issues/comments/\d+", c[2])]

    def __call__(self, argv, **kwargs):
        listing = re.fullmatch(r"repos/[^/]+/[^/]+/issues/\d+/comments\?since=(\S+?)&per_page=100&page=(\d+)",
                               argv[2]) if argv[:2] == ["gh", "api"] else None
        if listing:
            self.calls.append(list(argv))
            if self.list_fails:
                return SimpleNamespace(returncode=1, stdout="", stderr="gh: Server Error (HTTP 500)")
            since, page = cloud_recover._epoch(listing.group(1)), int(listing.group(2))
            rows = [c for c in self.listing if cloud_recover._epoch(c["updated_at"]) >= since]
            return SimpleNamespace(returncode=0, stdout=json.dumps(rows[(page - 1) * 100:page * 100]), stderr="")
        out = super().__call__(argv, **kwargs)
        single = re.fullmatch(r"repos/[^/]+/[^/]+/issues/comments/(\d+)", argv[2]) if argv[:2] == ["gh", "api"] else None
        if single and out.returncode == 0:
            data = json.loads(out.stdout)
            data.update(self.times.get(int(single.group(1)), {}))
            return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        return out


@pytest.fixture
def scene(world):
    world.gh = ActivityGh(world.comments)
    assert _declare(world.repo, BATCH, 4, env=world.env)["ok"]
    return world


def _lane(w, launch_id, issue, session, ts, end=False):
    """A cloud lane written through the ledger's own writers; `end` closes it so a later lane may share its issue."""
    extra = {"place": "cloud", "cloudEnvironment": "env-fixture-one", "pluginVersion": "1.2.3", "issue": issue, "ts": ts}
    got = ll.reserve(w.repo, _reserved(launch_id, BATCH, [launch_id], w.repo, **extra), env=w.env)
    assert got["ok"], got
    started = _started(launch_id)
    started.update(cloudSessionName=session, cloudSessionId="session_01AbCdEf123")
    assert ll.append_under_lock(w.repo, started, env=w.env)["ok"]
    if end:
        assert ll.terminalize(w.repo, launch_id, child_ever_spawned=True, outcome="handback", evidence="x",
                              env=w.env)["ok"]


def _pointed(w, session=LANE, issue=ISSUE, created=POINTER_AT, with_times=True):
    """Compose on `session`, post the body as a comment on `issue` created at `created`, point; the relay record is
    empty (a silent relay). (point result, comment id)."""
    _ensure_alive(w)
    composed = cr.compose(w.repo, w.config, session, "Use the narrow fix.\n", env=w.env)
    assert composed["ok"] is True
    cid, url = _post(w, composed, issue)
    out = cr.point(w.repo, composed["msgId"], url, env=w.env, run=w.gh)
    assert out["ok"] is True, out
    _backdate(w, out["msgId"], BEFORE)
    if with_times:
        w.gh.times[cid] = {"created_at": iso(created), "updated_at": iso(created)}
        w.gh.listing.append({"id": cid, "body": w.comments[cid], "created_at": iso(created),
                             "updated_at": iso(created), "issue_url": "https://api.github.com/repos/%s/issues/%d"
                             % (REPO_NAME, issue)})
    _write_record(w, [])
    return out, cid


def _standard(w):
    """The target lane, reserved at T0 and left running, and a silent-relay message pointed at LANE."""
    _lane(w, "launch-aaaa", ISSUE, LANE, T0)
    return _pointed(w)


def _add(w, cid, body, created, updated=None, issue=ISSUE):
    w.gh.listing.append({"id": cid, "body": body, "created_at": iso(created), "updated_at": iso(updated or created),
                         "issue_url": "https://api.github.com/repos/%s/issues/%d" % (REPO_NAME, issue)})


def _note(w, cid, created, issue=ISSUE):
    _add(w, cid, cb.NOTE_HEADER + "\n\nMay I rename the helper?\n" + cb.CLOUD_FOOTER, created, issue=issue)


def _progress(w, cid, created, updated, phase="working: tests"):
    body = cb.progress_text(phase, "pytest", "2026-11-01T09:00:00Z", 10)["comment"]
    _add(w, cid, body, created, updated)


def _decision(w, msg_id):
    return json.load(open(_state_file(w)))["pending"][msg_id]["decision"]


def _silent(out, msg_id, *, activity_leg, missing):
    assert out["delivered"] is False and out["ok"] is False and out["reason"] == "relay-silent"
    assert out["pointerLeg"] == "relay-silent" and out["nothingReached"] is False
    assert out["activityLeg"] == activity_leg and out["missingLegs"] == missing
    assert "basis" not in out and "activity" not in out
    assert out["say"].startswith("The relay did not send message %s within 4 seconds; it was not delivered." % msg_id)


# ---- row 1: the second basis ---------------------------------------------------------------------

def test_a_builder_note_after_the_comment_from_the_target_lane_reads_delivered(scene):
    msg, cid = _standard(scene)
    _note(scene, 5001, POINTER_AT + 60)
    before = len(scene.gh.calls)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    made = scene.gh.calls[before:]
    assert out["delivered"] is True and out["ok"] is True and out["reason"] is None
    assert out["basis"] == "comment-and-activity" and out["failedParts"] == []
    assert out["activity"] == {"kind": "note", "commentId": 5001, "at": iso(POINTER_AT + 60)}
    assert out["pointerLeg"] == "relay-silent" and out["commentLeg"] == "matches" and out["nothingReached"] is False
    assert "activityLeg" not in out and "missingLegs" not in out
    assert out["say"].startswith("Message %s was delivered" % msg["msgId"])
    assert "relay's own report of the send is missing" in out["say"] and "builder note" in out["say"]
    assert "matches" in out["say"] and "not delivered" not in out["say"]
    decision = _decision(scene, msg["msgId"])
    assert decision["delivered"] is True and decision["basis"] == "comment-and-activity"
    # the comment is read once; the activity read is the issue's comment list
    assert [c[2] for c in made if "/issues/comments/" in c[2]] == ["repos/%s/issues/comments/%d" % (REPO_NAME, cid)]
    assert len([c for c in made if "/issues/%d/comments?" % ISSUE in c[2]]) == 1 and len(made) == 2


def test_the_lanes_progress_comment_edited_after_the_comment_with_a_working_phase_reads_delivered(scene):
    msg, _cid = _standard(scene)
    _progress(scene, 5002, POINTER_AT - 50, POINTER_AT + 200)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is True and out["basis"] == "comment-and-activity"
    assert out["activity"] == {"kind": "progress", "commentId": 5002, "at": iso(POINTER_AT + 200)}
    assert out["failedParts"] == [] and out["pointerLeg"] == "relay-silent"
    assert "progress comment" in out["say"]
    assert _decision(scene, msg["msgId"])["basis"] == "comment-and-activity"


# ---- row 2: no activity --------------------------------------------------------------------------

def test_a_matching_comment_with_no_later_activity_stays_relay_silent_and_names_the_legs(scene):
    msg, _cid = _standard(scene)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])
    assert out["commentLeg"] == "matches" and out["failedParts"] == ["pointer"]
    assert "Not established: the relay's own report of the send and builder activity on the lane's issue after the comment." \
        in out["say"]
    assert _decision(scene, msg["msgId"]) == dict(_decision(scene, msg["msgId"]), delivered=False, reason="relay-silent")
    assert "basis" not in _decision(scene, msg["msgId"])


# ---- row 3: the comment is not what was composed -------------------------------------------------

def test_an_altered_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read(scene):
    msg, cid = _standard(scene)
    _note(scene, 5001, POINTER_AT + 60)
    scene.comments[cid] = scene.comments[cid] + " edited"
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="not-read", missing=["relay-report", "comment-match", "later-activity"])
    assert out["commentLeg"] == "altered" and out["failedParts"] == ["pointer", "comment"]
    assert scene.gh.list_calls() == []
    assert "a pointer comment that matches the composed text" in out["say"]


def test_a_missing_comment_with_a_later_note_is_never_delivered_and_no_activity_is_read(scene):
    msg, cid = _standard(scene)
    _note(scene, 5001, POINTER_AT + 60)
    del scene.comments[cid]
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="not-read", missing=["relay-report", "comment-match", "later-activity"])
    assert out["commentLeg"] == "missing" and scene.gh.list_calls() == []
    assert out["say"].endswith("is missing; it was not delivered.")


# ---- row 4: the lane binding ---------------------------------------------------------------------

def test_a_note_from_a_successor_lane_on_the_same_issue_is_not_the_target_lanes_activity(scene):
    _lane(scene, "launch-aaaa", ISSUE, LANE, T0, end=True)
    _lane(scene, "launch-bbbb", ISSUE, SUCCESSOR, SUCCESSOR_AT)
    msg, _cid = _pointed(scene)
    _note(scene, 5003, SUCCESSOR_AT + 50)
    _progress(scene, 5004, SUCCESSOR_AT + 10, SUCCESSOR_AT + 200)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


def test_the_target_lanes_own_note_still_counts_when_a_successor_exists(scene):
    _lane(scene, "launch-aaaa", ISSUE, LANE, T0, end=True)
    _lane(scene, "launch-bbbb", ISSUE, SUCCESSOR, SUCCESSOR_AT)
    msg, _cid = _pointed(scene)
    _note(scene, 5003, SUCCESSOR_AT + 50)
    _note(scene, 5005, POINTER_AT + 20)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is True and out["activity"]["commentId"] == 5005


def test_a_progress_comment_created_before_the_lanes_cutoff_and_edited_after_the_comment_is_not_its_activity(scene):
    msg, _cid = _standard(scene)
    _progress(scene, 5006, T0 - 500, POINTER_AT + 200)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


# ---- row 5: the progress rules -------------------------------------------------------------------

def test_a_progress_comment_created_after_the_pointer_comment_is_not_activity(scene):
    msg, _cid = _standard(scene)
    _progress(scene, 5007, POINTER_AT + 30, POINTER_AT + 200)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


@pytest.mark.parametrize("phase", ["parked: waiting on the advisor", "handed back", "stopped: owner asked"])
def test_a_progress_edit_whose_phase_reads_parked_stopped_or_handed_back_is_not_activity(scene, phase):
    msg, _cid = _standard(scene)
    _progress(scene, 5008, POINTER_AT - 50, POINTER_AT + 200, phase=phase)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


def test_a_progress_comment_not_edited_after_the_pointer_comment_is_not_activity(scene):
    msg, _cid = _standard(scene)
    _progress(scene, 5009, POINTER_AT - 50, POINTER_AT)
    _progress(scene, 5010, POINTER_AT - 40, POINTER_AT - 10)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


# ---- row 6: the note is strictly after the comment -----------------------------------------------

@pytest.mark.parametrize("offset", [-30, 0], ids=["before", "same-second"])
def test_a_note_created_before_or_in_the_second_of_the_pointer_comment_is_not_activity(scene, offset):
    msg, _cid = _standard(scene)
    _note(scene, 5011, POINTER_AT + offset)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


def test_other_comments_by_the_lane_are_not_activity(scene):
    msg, _cid = _standard(scene)
    for n, text in enumerate(("Builder parked (cloud build).\n\nwaiting", "Builder handback (cloud build).\n\ndone",
                              "I pushed my work and stopped working on this issue.", "just a human remark")):
        _add(scene, 5020 + n, text, POINTER_AT + 20 + n)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="none", missing=["relay-report", "later-activity"])


# ---- row 7: fail closed --------------------------------------------------------------------------

def test_a_comment_list_that_cannot_be_read_is_unreadable_and_stays_silent(scene):
    msg, _cid = _standard(scene)
    _note(scene, 5001, POINTER_AT + 60)
    scene.gh.list_fails = True
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    _silent(out, msg["msgId"], activity_leg="unreadable", missing=["relay-report", "later-activity"])


def test_a_session_with_no_launch_is_unattributable_and_stays_silent(scene):
    msg, _cid = _pointed(scene)
    _note(scene, 5001, POINTER_AT + 60)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent" and out["pointerLeg"] == "relay-silent"
    assert out["activityLeg"] == "unattributable" and out["missingLegs"] == ["relay-report", "later-activity"]
    assert scene.gh.list_calls() == []
    # no lane to judge: the sentence is today's, the keys carry the legs
    assert out["say"] == "The relay did not send message %s within 4 seconds; it was not delivered." % msg["msgId"]


def test_a_pointer_comment_without_a_created_at_leaves_the_activity_unjudged(scene):
    _lane(scene, "launch-aaaa", ISSUE, LANE, T0)
    msg, _cid = _pointed(scene, with_times=False)
    _note(scene, 5001, POINTER_AT + 60)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["reason"] == "relay-silent" and out["commentLeg"] == "matches"
    assert out["activityLeg"] == "unattributable" and out["missingLegs"] == ["relay-report", "later-activity"]
    assert scene.gh.list_calls() == []


def test_two_cloud_launches_with_the_session_name_are_unattributable(scene):
    _lane(scene, "launch-aaaa", ISSUE, LANE, T0)
    _lane(scene, "launch-cccc", 78, LANE, T0 + 10)
    msg, _cid = _pointed(scene)
    _note(scene, 5001, POINTER_AT + 60)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["activityLeg"] == "unattributable" and scene.gh.list_calls() == []


def test_a_pointer_comment_on_another_issue_than_the_lanes_is_unattributable(scene):
    _lane(scene, "launch-aaaa", 78, LANE, T0)
    msg, _cid = _pointed(scene)
    _note(scene, 5001, POINTER_AT + 60, issue=78)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["activityLeg"] == "unattributable" and scene.gh.list_calls() == []


def test_an_unreadable_launch_ledger_is_unattributable(scene):
    _lane(scene, "launch-aaaa", ISSUE, LANE, T0)
    msg, _cid = _pointed(scene)
    _note(scene, 5001, POINTER_AT + 60)
    path = ll.ledger_path(scene.repo, env=scene.env)["path"]
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(b"{not json\n" + raw)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is False and out["activityLeg"] == "unattributable" and scene.gh.list_calls() == []


# ---- row 8: today's path -------------------------------------------------------------------------

def test_the_exact_pointer_sent_with_success_reads_delivered_on_the_relay_report(scene):
    msg, _cid = _standard(scene)
    _write_record(scene, _send_lines("toolu_1", LANE, msg["forward"], STAMP))
    out, clock = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is True and out["basis"] == "relay-report" and out["reason"] is None
    assert out["pointerLeg"] == "delivered" and out["failedParts"] == [] and "activity" not in out
    assert out["say"] == "Message %s was delivered to the cloud session." % msg["msgId"]
    assert _decision(scene, msg["msgId"])["basis"] == "relay-report"
    assert scene.gh.list_calls() == [] and clock.t == 0


# ---- row 9: an archive request settles delivered -------------------------------------------------

def test_an_archive_request_recorded_uncertain_settles_delivered_when_check_reads_delivered(scene):
    msg, _cid = _standard(scene)
    _note(scene, 5001, POINTER_AT + 60)
    out, _ = _check(scene, msg["msgId"], wait=4, interval=2)
    assert out["delivered"] is True and out["basis"] == "comment-and-activity"
    pr = 412
    path, receipts = CC._load(scene.repo, scene.env)
    assert receipts == []
    CC._save(path, [{"repo": REPO_NAME, "pr": pr, "session": LANE, "msgId": out["msgId"], "outcome": "uncertain",
                     "at": "2026-11-01T10:00:00Z", "closedAt": "2026-11-01T09:00:00Z", "closure": "merged"}])
    # the merge-train rule records the outcome `check` reads: delivered: true -> "delivered"
    outcome = "delivered" if out["delivered"] else "uncertain"
    got = CC.record(scene.repo, REPO_NAME, pr, out["msgId"], outcome, env=scene.env, run=scene.gh)
    assert got["ok"] is True and "already" not in got
    assert got["request"]["outcome"] == "delivered" and got["request"]["msgId"] == out["msgId"]
    assert got["ownerMessage"] == CC.OWNER_MESSAGE_MERGED % pr and got["ownerMessage"] is not None
    saved = json.load(open(path))
    assert [(r["msgId"], r["outcome"]) for r in saved] == [(out["msgId"], "delivered")]
