"""The wave watch reads a cloud detective lane's incident-issue comments like a builder lane's.

Bites on: the detective intake note being no ending and no builder note, the progress comment
deciding staleness for a detective lane, and each terminal kind being lane-terminal there.
Residual blind spots: the real GitHub comments payload beyond the fields the fixtures carry.
"""
import time

import pytest

import cloud_builder as cb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import _CONFIG_DIR, _NoteGh, _arm, _comment  # noqa: F401
from test_wave_watch_cloud import _FRESH, _QUIET, _WINDOW, _reserved, clock, repo  # noqa: F401
from test_wave_watch_cloud_progress import _ProgressGh, _progress  # noqa: F401
from test_wave_watch_cloud_terminal import _evaluate, _lanes

_LONG_AGO = _QUIET * 5
_EXPECTED_60 = 3600
_SHA = "a" * 40


def _detective_lane(repo_root, launch_id, issue, *, start_age=_LONG_AGO):
    """A started cloud lane whose `reserved` record names `charter: detective`."""
    ll.append(repo_root, _reserved(
        launch_id, issue, "plugins/cloud-%d" % issue, repo_root,
        place=ll.PLACE_CLOUD, cloudEnvironment="env-1", pluginVersion="1.2.3",
        configDir=_CONFIG_DIR, charter="detective", ts=time.time() - start_age - 1,
    ))
    ll.append(repo_root, {
        "event": "started", "launchId": launch_id, "ts": time.time() - start_age,
        "schema": ll.SCHEMA, "attempt": 1, "pid": 999999999,
        "logPath": "/tmp/log", "errPath": "/tmp/err",
        "cloudSessionName": "cloud-%d" % issue,
        "cloudSessionUrl": "https://claude.ai/code/session_%d" % issue,
        "cloudSessionId": "session_%d" % issue,
    })


def _intake_note():
    return cb.DETECTIVE_INTAKE_TEXT.format(v="1.2.3", sha=_SHA)


def _adopt_note():
    return cb.DETECTIVE_INTAKE_ADOPT_TEXT.format(v="1.2.3", sha=_SHA, branch="feature/adopted-1")


def _progress_body(phase="reproduction A/B"):
    result = cb.progress_text(phase, "the A/B against the base", "2026-10-21T08:30:00Z", 60)
    assert result["ok"] is True, result
    return result["comment"]


def _terminal_body(kind):
    result = cb.terminal_text(kind, "Receipt: https://github.com/owner/repo/issues/101#issuecomment-5")
    assert result["ok"] is True, result
    return result["comment"]


# --- (1) the detective intake note is no ending and no note ---------------------------------


@pytest.mark.parametrize("make", [_intake_note, _adopt_note], ids=["started", "adopted"])
@pytest.mark.parametrize("footered", [False, True], ids=["bare", "footered"])
def test_a_detective_intake_note_is_neither_lane_terminal_nor_a_builder_note(repo, make, footered):
    # axis: the intake note opens with no header the watch reads, so it is never an ending or a note
    body = make() + ("\n\n" + cb.CLOUD_FOOTER if footered else "")
    _detective_lane(repo, "cloud-a", 101)
    assert _arm(repo, _ProgressGh([_comment(7, 101, body)], activity_age=_FRESH))["event"] == ww.EVENT_TIMER
    assert _evaluate(_lanes({"cloud-a": (101, 600)}), [_comment(7, 101, body)]) == ([], [])


# --- (2) the progress comment decides staleness as for a builder lane ----------------------


def test_a_fresh_progress_comment_on_a_detective_lane_is_not_stale(repo):
    # axis: a detective lane inside its stated step is not stale however quiet its activity
    _detective_lane(repo, "cloud-a", 101)
    gh = _ProgressGh([_progress(7, 101, updated_age=3000, body=_progress_body())])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_a_progress_comment_past_its_step_plus_the_window_on_a_detective_lane_is_stale(repo):
    # axis: a detective lane past its stated step plus the window is stale with the progress fields
    _detective_lane(repo, "cloud-a", 101)
    age = _EXPECTED_60 + _WINDOW + 60
    result = _arm(repo, _ProgressGh([_progress(7, 101, updated_age=age, body=_progress_body())]))
    assert result["event"] == ww.EVENT_LANE_STALE
    [launch] = result["launches"]
    assert launch["launchId"] == "cloud-a"
    assert launch["progressExpectedSeconds"] == _EXPECTED_60
    assert launch["phase"] == "reproduction A/B"
    assert "activityAgeSeconds" not in launch


# --- (3) each terminal kind posted on the detective lane's issue is lane-terminal ----------


@pytest.mark.parametrize("kind, state", [("handback", "handback"), ("park", "parked"), ("stop", "stopped")])
def test_each_terminal_kind_on_a_detective_lane_is_lane_terminal_through_the_ledger(repo, kind, state):
    # axis: the watch reads a detective lane's terminal comment; the ledger path carries the detective record
    _detective_lane(repo, "cloud-a", 101)
    body = _terminal_body(kind) + "\n\n" + cb.CLOUD_FOOTER
    result = _arm(repo, _NoteGh([_comment(7, 101, body)]))
    assert result["event"] == ww.EVENT_LANE_TERMINAL, result
    [launch] = result["launches"]
    assert (launch["launchId"], launch["state"], launch["kind"], launch["commentId"]) == (
        "cloud-a", state, kind, 7)
    assert launch["issue"] == 101


def test_each_terminal_kind_is_lane_terminal_when_the_lanes_go_straight_to_the_evaluator():
    lanes = _lanes({"cloud-a": (101, 600), "cloud-b": (202, 600), "cloud-c": (303, 600)})
    comments = [_comment(1, 303, _terminal_body("park")), _comment(2, 101, _terminal_body("handback")),
                _comment(3, 202, _terminal_body("stop"))]
    notes, terminals = _evaluate(lanes, comments)
    assert notes == []
    assert [(t["launchId"], t["state"]) for t in terminals] == [
        ("cloud-a", "handback"), ("cloud-b", "stopped"), ("cloud-c", "parked")]
