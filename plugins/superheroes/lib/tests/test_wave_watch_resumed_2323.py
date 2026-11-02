"""The wave watch keeps a lane resumed after its terminal outcome (#2323).

A started, outcome-terminal cloud lane that was not relaunched is a dormant lane: the watch reports its
newest unanswered ending and its unanswered builder notes created at or after its basis (the later of its
recorded outcome and its newest ledger amendment), and counts it for staleness, account limits and
`cloudLanes` only while it is active.

Ledger outcome and amendment timestamps are wall-clock `time.time()`, so a comment "after the basis" is
created in the future (`age` negative) and one "before" it in the past.
"""
import math
import time
from datetime import datetime, timezone

import pytest

import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import _BATCH, _NoteGh, _cloud_lane, _note_answered  # noqa: F401
from test_wave_watch_cloud import _QUIET, _add_local_lane, _iso, _reserved, repo  # noqa: F401
from test_wave_watch_cloud_progress import _LONG_AGO, _ProgressGh, _progress  # noqa: F401
from test_wave_watch_fix_order import _amend_at, _ending, _handed_back, _later, _only_launch  # noqa: F401


def _outcome_at(repo_root, launch_id, age, outcome="handback"):
    """A recorded outcome `age` seconds ago, to lay the basis behind the comments below.

    The public writers stamp the outcome with the clock, so a basis in the past is written raw."""
    assert ll._append_raw(repo_root, {
        "event": "outcome", "launchId": launch_id, "ts": time.time() - age,
        "schema": ll.SCHEMA, "outcome": outcome, "evidence": "built and gated",
    })


def _dormant_at(repo_root, age, launch_id="cloud-a", issue=101, outcome="handback"):
    """A started cloud lane whose outcome was recorded `age` seconds ago."""
    _cloud_lane(repo_root, launch_id, issue, start_age=_LONG_AGO)
    _outcome_at(repo_root, launch_id, age, outcome)


def _run(repo_root, comments):
    return ww.run(repo_root, _BATCH, gh_run=_ProgressGh(comments))


def _folded(repo_root):
    return ll.fold(ll.read(repo_root, create=False)["records"])["launches"]


# --- rows 1-5: a resumed lane's next ending and notes are reported ---------------------------------


def test_row1_a_lane_resumed_by_a_progress_edit_and_handing_back_again_is_lane_terminal(repo):
    _handed_back(repo, start_age=_LONG_AGO)
    comments = [
        _later(3, _ending("handback"), secs=-600),  # the first handback, before the basis
        _progress(9, 101, updated_age=-400, created_age=_LONG_AGO, phase="resumed: fixing the gate"),
        _later(7, _ending("handback"), secs=450),
    ]
    launch = _only_launch(_run(repo, comments))
    assert (launch["launchId"], launch["state"], launch["commentId"]) == ("cloud-a", "handback", 7)


def test_row2_a_handback_after_the_basis_is_reported_with_no_progress_edit_at_all(repo):
    _handed_back(repo, start_age=_LONG_AGO)
    # The lane's progress comment still reads handback from its first ending, edited before the basis.
    comments = [
        _progress(9, 101, updated_age=600, created_age=_LONG_AGO, phase="handback"),
        _later(7, _ending("handback")),
    ]
    launch = _only_launch(_run(repo, comments))
    assert (launch["launchId"], launch["state"], launch["commentId"]) == ("cloud-a", "handback", 7)


def test_row3_a_builder_note_after_the_basis_is_a_builder_note(repo):
    _handed_back(repo, start_age=_LONG_AGO)
    result = _run(repo, [_later(7)])
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [7]
    assert result["launchId"] == "cloud-a"


def test_row4_a_park_answered_by_message_then_resumed_and_handed_back_reports_the_handback(repo):
    _dormant_at(repo, 1000, outcome="park")
    comments = [
        _later(3, _ending("park"), secs=-900),  # the recorded park, before the basis
        _later(7, _ending("handback")),
    ]
    launch = _only_launch(_run(repo, comments))
    assert (launch["state"], launch["commentId"]) == ("handback", 7)


def test_row5_two_activity_only_cycles_then_a_vet_amendment_moves_the_basis_for_the_third(repo):
    _dormant_at(repo, 3000)
    cycles = [_later(5, _ending("handback"), secs=-2000), _later(6, _ending("handback"), secs=-1000)]
    # Two handbacks after the recorded outcome, neither answered: the newest one fires, not the first.
    assert _only_launch(_run(repo, cycles))["commentId"] == 6
    # The advisor vets the resumed handback: the amendment moves the basis past both.
    _amend_at(repo, "cloud-a", "ready", 500)
    assert _run(repo, cycles)["event"] == ww.EVENT_TIMER
    third = _later(7, _ending("handback"))
    assert _only_launch(_run(repo, cycles + [third]))["commentId"] == 7


# --- rows 6-10: what a dormant lane does not report ------------------------------------------------


def test_row6_a_dormant_lane_with_no_activity_after_its_basis_is_quiet_and_not_listed(repo):
    _dormant_at(repo, 1000)
    # A progress comment that would read a live lane stale (last edited long before its stated step).
    result = _run(repo, [_progress(9, 101, updated_age=_QUIET * 3, created_age=_LONG_AGO)])
    assert result["event"] == ww.EVENT_TIMER
    assert "cloudLanes" not in result


def test_row7_a_handback_created_before_the_basis_is_not_reported(repo):
    _dormant_at(repo, 100)
    result = _run(repo, [_later(3, _ending("handback"), secs=-500), _later(4, secs=-400)])
    assert result["event"] == ww.EVENT_TIMER
    assert "cloudLanes" not in result


@pytest.mark.parametrize("updated_age, phase", [
    (-200, "resumed: fixing the gate"),  # inside the grace window
    (-400, "handed back"),
    (-400, "handback"),
    (-400, "parked: waiting on the owner"),
    (-400, "stopped"),
])
def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
    _handed_back(repo, start_age=_LONG_AGO)
    # A future-dated progress comment would read a watched lane stale at once (negative age).
    result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
    assert result["event"] == ww.EVENT_TIMER
    assert "cloudLanes" not in result


def test_row8_a_phase_reading_handed_back_but_resumed_is_activity(repo):
    _handed_back(repo, start_age=_LONG_AGO)
    result = _run(repo, [_progress(9, 101, updated_age=-400, created_age=_LONG_AGO, phase="resumed after handback")])
    assert result["event"] == ww.EVENT_LANE_STALE  # active, and its future-dated progress reads stale
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-a"]


def test_row9_a_newer_launch_on_the_same_issue_in_another_batch_makes_the_older_lane_not_dormant(repo):
    _handed_back(repo, start_age=_LONG_AGO)
    newer = [_later(7, _ending("handback")), _later(8, secs=40)]
    # Control: without the newer launch the older lane is resumed and reports the handback.
    assert _only_launch(_run(repo, newer))["commentId"] == 7
    ll.append(repo, _reserved(
        "cloud-b", 101, "plugins/cloud-101", repo, batchId="other-batch",
        place=ll.PLACE_CLOUD, cloudEnvironment="env-1", pluginVersion="1.2.3", ts=time.time(),
    ))
    result = _run(repo, newer)
    assert result["event"] == ww.EVENT_TIMER
    assert "cloudLanes" not in result


def test_row10_a_local_terminal_lane_is_not_dormant(repo):
    _add_local_lane(repo, "local-a", 102, pid=999999999)
    assert ll.record_outcome(repo, "local-a", "handback", "built and gated")["ok"] is True
    result = _run(repo, [_later(7, _ending("handback"), issue=102), _later(8, issue=102)])
    assert result["event"] == ww.EVENT_TIMER
    assert "cloudLanes" not in result


def test_row10_a_refused_cloud_lane_is_not_dormant(repo):
    ll.append(repo, _reserved(
        "cloud-r", 103, "plugins/cloud-103", repo, place=ll.PLACE_CLOUD, cloudEnvironment="env-1",
        pluginVersion="1.2.3", ts=time.time() - _LONG_AGO,
    ))
    assert ll._append_raw(repo, {
        "event": "refused", "launchId": "cloud-r", "ts": time.time() - 1000, "schema": ll.SCHEMA,
        "stage": "preflight", "reason": "no environment",
    })
    result = _run(repo, [_later(7, _ending("handback"), issue=103), _later(8, issue=103)])
    assert result["event"] == ww.EVENT_TIMER
    assert "cloudLanes" not in result


# --- row 11: an active dormant lane is listed and can go stale -------------------------------------


def test_row11_an_active_dormant_lane_is_listed_with_its_basis_and_goes_stale_on_its_progress(repo):
    basis = time.time() - _QUIET * 3
    _cloud_lane(repo, "cloud-a", 101, start_age=_LONG_AGO)
    _outcome_at(repo, "cloud-a", _QUIET * 3)
    # Resumed (edited well past the grace after the basis) and then quiet past its stated hour.
    result = _run(repo, [_progress(9, 101, updated_age=_QUIET * 2, created_age=_LONG_AGO, phase="resumed: fixing")])
    assert result["event"] == ww.EVENT_LANE_STALE
    [launch] = result["launches"]
    assert launch["launchId"] == "cloud-a" and launch["progressAgeSeconds"] > _QUIET
    [lane] = result["cloudLanes"]
    assert lane["launchId"] == "cloud-a"
    assert lane["reopenedBy"] == "builder-activity"
    assert lane["reopenedAt"] == datetime.fromtimestamp(basis, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_row11_an_active_dormant_lane_inside_its_stated_step_is_listed_and_not_stale(repo):
    _dormant_at(repo, _QUIET * 3)
    result = _run(repo, [_progress(9, 101, updated_age=_QUIET, created_age=_LONG_AGO, phase="resumed: fixing",
                                   expected="Expected: 600 minutes")])
    assert result["event"] == ww.EVENT_TIMER
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-a"]


# --- row 12: the fold, and the fail-closed edges at the basis --------------------------------------


def test_row12_fold_exposes_the_outcome_time_as_terminal_ts(repo):
    _cloud_lane(repo, "cloud-a", 101)
    assert _folded(repo)["cloud-a"]["terminalTs"] is None
    _outcome_at(repo, "cloud-a", 77)
    record = [r for r in ll.read(repo, create=False)["records"] if r.get("event") == "outcome"][0]
    assert _folded(repo)["cloud-a"]["terminalTs"] == record["ts"]


def _dormant_info(**extra):
    info = {
        "place": ll.PLACE_CLOUD, "started": True, "terminal": True, "terminalKind": "outcome",
        "issue": 101, "reservedTs": 100.0, "terminalTs": 500.0, "amendments": [],
    }
    info.update(extra)
    return info


def test_e1_a_time_that_is_not_a_finite_number_never_yields_a_basis():
    assert ww._dormant_basis("a", _dormant_info(), {}) == 500.0
    for bad in (None, float("nan"), math.inf, "500", True):
        assert ww._dormant_basis("a", _dormant_info(terminalTs=bad), {}) is None
        assert ww._dormant_basis("a", _dormant_info(reservedTs=bad), {}) is None
        amendments = [{"kind": "vet", "ts": bad}, {"kind": "vet", "ts": 600.0}, "junk"]
        assert ww._dormant_basis("a", _dormant_info(amendments=amendments), {}) == 600.0


def test_e5_only_a_started_outcome_terminal_cloud_lane_has_a_basis():
    assert ww._dormant_basis("a", _dormant_info(place=ll.PLACE_LOCAL), {}) is None
    assert ww._dormant_basis("a", _dormant_info(terminalKind="refused"), {}) is None
    assert ww._dormant_basis("a", _dormant_info(started=False), {}) is None
    assert ww._dormant_basis("a", _dormant_info(terminal=False), {}) is None


def test_e2_a_launch_reserved_later_on_the_issue_in_any_batch_means_no_basis():
    later = {"b": {"issue": 101, "reservedTs": 101.0, "batchId": "other"}}
    assert ww._dormant_basis("a", _dormant_info(), later) is None
    assert ww._dormant_basis("a", _dormant_info(), {"b": {"issue": 102, "reservedTs": 101.0}}) == 500.0
    assert ww._dormant_basis("a", _dormant_info(), {"b": {"issue": 101, "reservedTs": 99.0}}) == 500.0
    assert ww._dormant_basis("a", _dormant_info(), {"b": {"issue": 101, "reservedTs": float("nan")}}) == 500.0
