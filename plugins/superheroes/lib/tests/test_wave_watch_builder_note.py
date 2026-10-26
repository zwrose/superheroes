"""The wave watch surfaces a cloud builder's note to the advisor as a builder-note event."""
import json
import os
import re
import subprocess
import time

import pytest

import cloud_builder as cb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_cloud import (  # noqa: F401
    _BATCH, _FRESH, _QUIET, _SLUG, _graphql_body, _iso, _lane_activity, _reserved,
    clock, repo,
)

_ETAG = 'W/"0ca7aaaa"'
_NOTE_BODY = "%s\n\nShould the migration keep the old column?\n\n%s" % (
    cb.NOTE_HEADER, cb.NOTE_CLOSING,
)
_CONFIG_DIR = "/home/advisor/.claude-two"


def _evaluate_builder_notes(*args, **kwargs):
    """The notes half of `ww._evaluate_cloud_comments`, for the tests that read only notes."""
    return ww._evaluate_cloud_comments(*args, **kwargs)[0]


def _cloud_lane(
    repo_root, launch_id, issue, *, start_age=_QUIET, config_dir=_CONFIG_DIR, reserve_lead=1,
):
    """A started cloud lane whose recorded start is `start_age` seconds ago.

    The reserved record precedes the started one by `reserve_lead` seconds.
    """
    ll.append(repo_root, _reserved(
        launch_id, issue, "plugins/cloud-%d" % issue, repo_root,
        place=ll.PLACE_CLOUD, cloudEnvironment="env-1", pluginVersion="1.2.3",
        configDir=config_dir, ts=time.time() - start_age - reserve_lead,
    ))
    ll.append(repo_root, {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time() - start_age,
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": 999999999,
        "logPath": "/tmp/log",
        "errPath": "/tmp/err",
        "cloudSessionName": "cloud-%d" % issue,
        "cloudSessionUrl": "https://claude.ai/code/session_%d" % issue,
        "cloudSessionId": "session_%d" % issue,
    })


def _comment(comment_id, issue, body=_NOTE_BODY, *, age=_FRESH):
    return {
        "id": comment_id,
        "html_url": "https://github.com/%s/issues/%d#issuecomment-%d" % (_SLUG, issue, comment_id),
        "issue_url": "https://api.github.com/repos/%s/issues/%d" % (_SLUG, issue),
        "created_at": _iso(age),
        "body": body,
    }


def _ok(argv, comments, *, etag=_ETAG, link=None):
    headers = ["HTTP/2.0 200 OK", "Content-Type: application/json; charset=utf-8"]
    if etag is not None:
        headers.append("Etag: %s" % etag)
    if link is not None:
        headers.append('Link: <https://api.github.com/x?page=2>; rel="next"')
    stdout = "\r\n".join(headers) + "\r\n\r\n" + json.dumps(comments)
    return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


def _raw(argv, stdout, returncode=0):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")


class _NoteGh:
    """Injected gh_run: repo view, pr list, graphql, and the comments read.

    The comments read serves `comments` as a server would: a request carrying the current
    ETag as If-None-Match gets a 304 and exit 1 (measured), any other a 200. `script`
    entries answer the comment reads first: a CompletedProcess, an exception to raise, or a
    callable taking the request's argv.
    """

    def __init__(self, comments=(), *, script=()):
        self.comments = list(comments)
        self.script = list(script)
        self.calls = []
        self.kwargs = []

    def note_calls(self):
        return [argv for argv in self.calls if argv[:3] == ["gh", "api", "-i"]]

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)
        if argv[:3] == ["gh", "repo", "view"]:
            return _raw(argv, json.dumps({"nameWithOwner": _SLUG}))
        if argv[:3] == ["gh", "pr", "list"]:
            return _raw(argv, "[]")
        if argv[:3] == ["gh", "api", "graphql"]:
            query = next(arg for arg in argv if arg.startswith("query="))
            issues = [int(n) for n in re.findall(r"i(\d+): issue", query)]
            body = _graphql_body({n: _lane_activity() for n in issues})
            return _raw(argv, json.dumps(body))
        if argv[:3] == ["gh", "api", "-i"]:
            if self.script:
                step = self.script.pop(0)
                if isinstance(step, BaseException):
                    raise step
                return step(argv) if callable(step) else step
            if "If-None-Match: %s" % _ETAG in argv:
                return _raw(
                    argv, "HTTP/2.0 304 Not Modified\r\nEtag: %s\r\n\r\n" % _ETAG, 1,
                )
            return _ok(argv, self.comments)
        raise AssertionError("unexpected gh argv: %r" % argv)


def _arm(repo_root, gh, **kwargs):
    return ww.watch_arm(
        repo_root, _BATCH, max_seconds=3, interval_seconds=1, gh_run=gh, **kwargs,
    )


def _answered_path(repo_root):
    return os.path.join(
        os.path.dirname(ll.ledger_path(repo_root)["path"]), ww.BUILDER_NOTES_ANSWERED_NAME,
    )


def _note_answered(repo_root, comment_id):
    return ww.note_answered(repo_root, comment_id)


# --- the invariant: which comments are notes ------------------------------------


def test_a_builder_note_on_a_watched_lanes_issue_ends_the_arm(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101)])
    result = _arm(repo, gh)
    assert result["ok"] is True
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["launchId"] == "cloud-a"
    [note] = result["notes"]
    assert note["url"] == "https://github.com/%s/issues/101#issuecomment-7" % _SLUG
    assert note["issue"] == 101
    assert note["launchId"] == "cloud-a"
    assert note["commentId"] == 7
    assert note["configDir"] == _CONFIG_DIR
    assert note["cloudSessionName"] == "cloud-101"
    assert note["cloudSessionId"] == "session_101"
    assert result["cloudLanes"][0]["launchId"] == "cloud-a"


def test_a_comment_that_is_not_a_note_raises_no_event(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, "Looks good to me.")])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER


def test_a_note_header_after_other_text_is_not_a_note(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, "Quoting: " + _NOTE_BODY)])
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER


def test_leading_whitespace_before_the_header_still_makes_a_note(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, "\n  " + _NOTE_BODY)])
    assert _arm(repo, gh)["event"] == ww.EVENT_BUILDER_NOTE


def test_a_note_on_an_issue_no_watched_lane_has_raises_no_event(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 999)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER


def test_a_note_created_before_the_lane_started_raises_no_event(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=600)
    gh = _NoteGh([_comment(7, 101, age=3000)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER


def test_a_note_recorded_answered_raises_no_event(repo):
    _cloud_lane(repo, "cloud-a", 101)
    assert _note_answered(repo, 7)["ok"] is True
    gh = _NoteGh([_comment(7, 101)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER


def test_notes_are_ordered_by_comment_id_and_name_the_first_notes_lane(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _cloud_lane(repo, "cloud-b", 202)
    gh = _NoteGh([_comment(9, 101), _comment(5, 202)])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [5, 9]
    assert result["launchId"] == "cloud-b"


def test_a_malformed_comment_element_is_skipped_and_the_rest_still_count(repo):
    _cloud_lane(repo, "cloud-a", 101)
    broken = [
        "not a dict",
        {**_comment(1, 101), "id": "1"},
        {**_comment(2, 101), "id": True},
        {k: v for k, v in _comment(3, 101).items() if k != "issue_url"},
        {**_comment(4, 101), "created_at": "yesterday"},
        {**_comment(5, 101), "body": None},
    ]
    gh = _NoteGh(broken + [_comment(8, 101)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [8]
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]


def test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count():
    gh = _NoteGh([_comment(3, 5), _comment(4, 6)])
    cloud = {"place": ll.PLACE_CLOUD, "started": True}
    lanes = {
        "cloud-x": {**cloud, "issue": 5, "startedTs": None},
        "cloud-y": {**cloud, "issue": 6, "startedTs": time.time() - 3600},
    }
    degraded = set()
    notes = _evaluate_builder_notes(
        "/", lanes, deadline=100.0, env={}, gh_run=gh, monotonic=lambda: 0.0,
        degraded=degraded, note_state=[None], known_slug=_SLUG,
    )
    assert [note["launchId"] for note in notes] == ["cloud-y"]
    assert degraded == set()


def test_a_lane_that_is_not_a_started_cloud_lane_causes_no_request(repo):
    ll.append(repo, _reserved("local-a", 55, "plugins/local-55", repo))
    gh = _NoteGh([_comment(7, 55)])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert gh.note_calls() == []
    assert result["event"] == ww.EVENT_TIMER


# --- the read: validator, 304, pages ---------------------------------------------


def test_the_request_is_the_issue_comments_list_since_the_earliest_start(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=_QUIET)
    _cloud_lane(repo, "cloud-b", 202, start_age=_QUIET // 2)
    gh = _NoteGh()
    ww.run(repo, _BATCH, gh_run=gh)
    [argv] = gh.note_calls()
    folded = ll.fold(ll.read(repo)["records"])["launches"]
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(folded["cloud-a"]["reservedTs"]))
    assert argv[:3] == ["gh", "api", "-i"]
    assert argv[3] == "repos/%s/issues/comments?since=%s&per_page=100" % (_SLUG, since)
    assert len(argv) == 4


def test_the_repeat_read_within_one_loop_sends_the_stored_validator(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh()
    result = ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=3, gh_run=gh,
    )
    assert result["event"] == ww.EVENT_TIMER
    calls = gh.note_calls()
    assert len(calls) >= 3
    assert "-H" not in calls[0]
    for argv in calls[1:]:
        assert "-H" in argv, "repeat read sent no validator: %r" % (argv,)
        assert argv[argv.index("-H") + 1] == "If-None-Match: %s" % _ETAG


def test_a_note_posted_between_reserved_and_started_is_surfaced(repo):
    # The launch command is still running when the session posts; started is stamped after.
    _cloud_lane(repo, "cloud-a", 101, start_age=60, reserve_lead=120)
    gh = _NoteGh([_comment(7, 101, age=90)])
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [n["commentId"] for n in result["notes"]] == [7]
    [argv] = gh.note_calls()[:1]
    folded = ll.fold(ll.read(repo)["records"])["launches"]
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(folded["cloud-a"]["reservedTs"]))
    assert "since=%s&" % since in argv[3]


def test_a_full_first_page_is_never_read_conditionally(repo):
    _cloud_lane(repo, "cloud-a", 101)
    full = [_comment(n, 202, "chatter") for n in range(1, 101)]
    gh = _NoteGh(full)
    ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=3, gh_run=gh,
    )
    calls = gh.note_calls()
    assert len(calls) >= 3
    for argv in calls:
        assert "-H" not in argv, "a full first page sent a validator: %r" % (argv,)


def test_a_304_after_a_new_lane_joins_re_evaluates_the_stored_list(repo, clock):
    _cloud_lane(repo, "cloud-a", 101, start_age=1000)
    gh = _NoteGh([_comment(7, 202, age=100)])

    def join_then_sleep(duration):
        if len(gh.note_calls()) == 1:
            _cloud_lane(repo, "cloud-b", 202, start_age=500)
        clock.sleep(duration)

    result = _arm(repo, gh, sleep=join_then_sleep)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["launchId"] == "cloud-b"
    assert [note["commentId"] for note in result["notes"]] == [7]
    first, second = gh.note_calls()
    assert "-H" not in first
    assert second[second.index("-H") + 1] == "If-None-Match: %s" % _ETAG


def test_the_validator_is_not_sent_for_another_since(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=1000)
    gh = _NoteGh()
    state = [None]
    ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, note_state=state)
    stored_url = state[0][0]
    state[0] = (stored_url.replace("since=", "since=1999-"), _ETAG, [])
    gh.calls.clear()
    ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, note_state=state)
    assert "-H" not in gh.note_calls()[0]


def test_later_pages_are_fetched_without_a_validator(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh(script=[
        lambda argv: _ok(argv, [_comment(1, 101, "chatter")], link=True),
        lambda argv: _ok(argv, [_comment(2, 101, "more chatter")], link=True),
        lambda argv: _ok(argv, [_comment(3, 101)]),
    ])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [3]
    calls = gh.note_calls()
    assert [argv[-1].rpartition("&page=")[2] for argv in calls[1:]] == ["2", "3"]
    assert all("-H" not in argv for argv in calls)


# --- fail-closed edges ----------------------------------------------------------


def _degraded_without_a_note(repo_root, gh):
    result = ww.run(repo_root, _BATCH, gh_run=gh)
    assert result["ok"] is True
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    return result


def test_e1_gh_that_cannot_run_degrades_without_raising(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _degraded_without_a_note(repo, _NoteGh(script=[FileNotFoundError("gh")]))


def test_e1_a_timeout_degrades_without_raising(repo):
    _cloud_lane(repo, "cloud-a", 101)
    timeout = subprocess.TimeoutExpired(["gh", "api"], 30)
    _degraded_without_a_note(repo, _NoteGh(script=[timeout]))


def test_e2_a_missing_status_line_degrades(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _degraded_without_a_note(repo, _NoteGh(script=[_raw([], "", 1)]))


def test_e2_a_status_other_than_200_or_304_degrades(repo):
    _cloud_lane(repo, "cloud-a", 101)
    forbidden = _raw([], "HTTP/2.0 403 Forbidden\r\n\r\n" + json.dumps([_comment(7, 101)]), 1)
    _degraded_without_a_note(repo, _NoteGh(script=[forbidden]))


def test_e2_a_body_that_is_not_a_json_array_degrades(repo):
    _cloud_lane(repo, "cloud-a", 101)
    for body in ('{"message": "nope"}', "not json"):
        stdout = "HTTP/2.0 200 OK\r\nEtag: %s\r\n\r\n%s" % (_ETAG, body)
        _degraded_without_a_note(repo, _NoteGh(script=[_raw([], stdout)]))


def test_e3_a_304_with_no_stored_list_degrades_and_is_never_no_notes(repo):
    _cloud_lane(repo, "cloud-a", 101)
    not_modified = _raw([], "HTTP/2.0 304 Not Modified\r\n\r\n", 1)
    _degraded_without_a_note(repo, _NoteGh(script=[not_modified]))


def test_e4_more_than_ten_pages_degrades(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh(script=[
        (lambda argv: _ok(argv, [_comment(3, 101, "chatter")], link=True)) for _ in range(12)
    ])
    _degraded_without_a_note(repo, gh)
    assert len(gh.note_calls()) == 10


def test_a_later_page_failure_keeps_a_note_read_on_an_earlier_page(repo):
    _cloud_lane(repo, "cloud-a", 101)
    bad = _raw([], "HTTP/2.0 502 Bad Gateway\r\n\r\n", 1)
    gh = _NoteGh(script=[
        (lambda argv: _ok(argv, [_comment(7, 101)], link=True)), bad,
    ])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]


def test_e7_an_unreadable_answered_file_leaves_the_note_surfacing(repo):
    _cloud_lane(repo, "cloud-a", 101)
    with open(_answered_path(repo), "w") as handle:
        handle.write("not json{")
    result = _arm(repo, _NoteGh([_comment(7, 101)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE


def test_e7_an_answered_file_of_the_wrong_shape_leaves_the_note_surfacing(repo):
    _cloud_lane(repo, "cloud-a", 101)
    with open(_answered_path(repo), "w") as handle:
        json.dump({"answered": [7, "8"]}, handle)
    result = _arm(repo, _NoteGh([_comment(7, 101)]))
    assert result["event"] == ww.EVENT_BUILDER_NOTE


def test_e7_note_answered_refuses_on_an_unreadable_file_and_never_overwrites_it(repo):
    path = _answered_path(repo)
    with open(path, "w") as handle:
        handle.write("not json{")
    result = _note_answered(repo, 7)
    assert result == {"ok": False, "reason": ww.REFUSAL_NOTE_ANSWERS_UNREADABLE}
    with open(path) as handle:
        assert handle.read() == "not json{"


@pytest.mark.parametrize("bad", [0, -3, "0", "-3", "abc", "1.5", "", 1.5, True, None])
def test_e8_note_answered_refuses_an_invalid_comment_id(repo, bad):
    result = _note_answered(repo, bad)
    assert result == {"ok": False, "reason": ww.REFUSAL_COMMENT_ID_INVALID}
    assert not os.path.exists(_answered_path(repo))


def test_e8_note_answered_refuses_when_the_ledger_path_is_unresolvable(tmp_path):
    bare = tmp_path / "no-git"
    bare.mkdir()
    result = _note_answered(str(bare), 7)
    assert result == {"ok": False, "reason": ww.REFUSAL_STORE_UNRESOLVABLE}


def test_e10_a_spent_time_budget_makes_no_request_and_discloses_it():
    gh = _NoteGh([_comment(7, 5)])
    lanes = {"cloud-x": {
        "place": ll.PLACE_CLOUD, "started": True, "issue": 5, "startedTs": time.time() - 60,
    }}
    degraded = set()
    notes = _evaluate_builder_notes(
        "/", lanes, deadline=10.0, env={}, gh_run=gh, monotonic=lambda: 10.0,
        degraded=degraded, note_state=[None], known_slug=_SLUG,
    )
    assert notes == []
    assert gh.calls == []
    assert degraded == {ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE}


# --- loop, run, and the verb ----------------------------------------------------


def test_the_loop_exits_on_the_event_instead_of_passing_it_over(repo):
    assert ww.EVENT_BUILDER_NOTE not in ww.BENIGN_EVENTS
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101)])
    result = ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=30, gh_run=gh,
    )
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["arms"] == 1
    assert result["passedOverCount"] == 0
    assert result["notes"][0]["commentId"] == 7


def test_run_makes_an_unconditional_read(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101)])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    [argv] = gh.note_calls()
    assert "-H" not in argv


def test_an_activity_request_that_spends_its_grant_does_not_starve_the_notes_read(repo):
    _cloud_lane(repo, "cloud-a", 101)
    now = [1000.0]
    inner = _NoteGh([_comment(7, 101)])

    def gh(argv, **kwargs):
        if argv[:3] == ["gh", "api", "graphql"]:
            inner.calls.append(list(argv))
            now[0] += kwargs["timeout"]
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return inner(argv, **kwargs)

    result = ww.run(repo, _BATCH, gh_run=gh, monotonic=lambda: now[0])
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert len(inner.note_calls()) == 1


def test_the_note_event_is_not_suppressible_and_ranks_below_builder_exited():
    assert ww.EVENT_BUILDER_NOTE not in ww._SUPPRESSIBLE_EVENTS
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in ww.DEGRADATIONS
    order = ww.EVENT_PRECEDENCE
    assert order.index(ww.EVENT_BUILDER_NOTE) == order.index(ww.EVENT_BUILDER_EXITED) + 1


def test_note_answered_round_trip_through_the_cli_stops_the_note(repo, capsys):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101), _comment(8, 101)])
    assert _arm(repo, gh)["notes"][0]["commentId"] == 7
    code = ww.main(["wave_watch.py", "note-answered", "--repo-root", repo, "--comment-id", "7"])
    printed = json.loads(capsys.readouterr().out)
    assert code == 0
    assert printed == {"ok": True, "commentId": 7, "path": _answered_path(repo)}
    again = _arm(repo, gh)
    assert [note["commentId"] for note in again["notes"]] == [8]
    ww.main(["wave_watch.py", "note-answered", "--repo-root", repo, "--comment-id", "8"])
    capsys.readouterr()
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
    with open(_answered_path(repo)) as handle:
        assert json.load(handle) == {"answered": [7, 8]}


def test_note_answered_cli_exits_1_on_a_refusal(repo, capsys):
    code = ww.main(["wave_watch.py", "note-answered", "--repo-root", repo, "--comment-id", "-4"])
    assert code == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": ww.REFUSAL_COMMENT_ID_INVALID}


# --- the slug is resolved once per tick; the cached validator on a paged and a changed read ---


def _repo_views(gh):
    return [argv for argv in gh.calls if argv[:3] == ["gh", "repo", "view"]]


def test_the_repository_slug_is_resolved_once_per_tick(repo):
    # axis: one `gh repo view` per tick, however many readers need the slug — see bite-proof record c8a_wo3.md
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101)])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert len(gh.note_calls()) == 1
    assert len(_repo_views(gh)) == 1


def test_a_slug_that_could_not_be_resolved_is_not_tried_again_within_the_tick(repo):
    # axis: a failed slug resolution is cached for the tick, so no reader retries it — see bite-proof record c8a_wo3.md
    _cloud_lane(repo, "cloud-a", 101)

    class _NoSlugGh(_NoteGh):
        def __call__(self, argv, **kwargs):
            if argv[:3] == ["gh", "repo", "view"]:
                self.calls.append(list(argv))
                return _raw(argv, "", 1)
            return super().__call__(argv, **kwargs)

    gh = _NoSlugGh([_comment(7, 101)])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert gh.note_calls() == []
    assert len(_repo_views(gh)) == 1


def test_the_slug_lookup_skipped_for_a_spent_budget_is_resolved_by_a_later_reader(repo):
    # axis: a budget-skipped slug lookup leaves the tick's cell unresolved, so a later reader with budget resolves — see bite-proof record c8c_wo_a.md
    gh = _NoteGh()
    cell = [ww._SLUG_UNRESOLVED]
    skipped = ww._slug_for_read(repo, 10.0, lambda: 10.0, gh, {}, None, cell)
    assert skipped is None
    assert cell[0] is ww._SLUG_UNRESOLVED
    assert gh.calls == []
    later = ww._slug_for_read(repo, 100.0, lambda: 10.0, gh, {}, None, cell)
    assert later == _SLUG
    assert cell[0] == _SLUG
    assert len(_repo_views(gh)) == 1


def test_a_slug_lookup_that_failed_is_cached_and_a_later_reader_makes_no_second_call(repo):
    # axis: a real lookup failure is cached for the tick, so no later reader retries it — see bite-proof record c8c_wo_a.md
    gh = _NoteGh()
    failing_calls = []

    def failing_gh(argv, **kwargs):
        failing_calls.append(list(argv))
        return _raw(argv, "", 1)

    cell = [ww._SLUG_UNRESOLVED]
    assert ww._slug_for_read(repo, 100.0, lambda: 10.0, failing_gh, {}, None, cell) is None
    assert cell[0] is None
    assert len(failing_calls) == 1
    assert ww._slug_for_read(repo, 100.0, lambda: 10.0, gh, {}, None, cell) is None
    assert gh.calls == []
    assert len(failing_calls) == 1


def test_the_note_read_on_an_absent_ledger_root_creates_no_directory(repo, tmp_path, monkeypatch):
    # axis: the builder-note read's answered-notes lookup makes no ledger directory — see bite-proof record c8c_wo_a.md
    absent = tmp_path / "absent-ledger-root"
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(absent))
    gh = _NoteGh([_comment(7, 5)])
    lanes = {"cloud-x": {
        "place": ll.PLACE_CLOUD, "started": True, "issue": 5, "startedTs": time.time() - 3600,
    }}
    degraded = set()
    notes = _evaluate_builder_notes(
        repo, lanes, deadline=100.0, env=None, gh_run=gh, monotonic=lambda: 0.0,
        degraded=degraded, note_state=[None], known_slug=_SLUG,
    )
    assert [note["commentId"] for note in notes] == [7]
    assert not absent.exists()


def _primed(repo):
    """The note state a first empty read leaves: the URL for this lane's `since`, the ETag, no comments."""
    state = [None]
    ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_NoteGh(), note_state=state)
    stored_url = state[0][0]
    state[0] = (stored_url, _ETAG, [])
    return state


def test_a_primed_validator_rides_page_one_only_and_a_multi_page_read_clears_it(repo):
    # axis: the cached validator goes on page one only, and a multi-page read stores none — see bite-proof record c8a_wo3.md
    _cloud_lane(repo, "cloud-a", 101, start_age=1000)
    state = _primed(repo)
    gh = _NoteGh(script=[
        lambda argv: _ok(argv, [_comment(1, 101, "chatter")], link=True),
        lambda argv: _ok(argv, [_comment(2, 101, "more chatter")], link=True),
        lambda argv: _ok(argv, [_comment(3, 101)]),
    ])
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, note_state=state,
    )
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    pages = gh.note_calls()
    assert [argv[-1].rpartition("&page=")[2] for argv in pages[1:]] == ["2", "3"]
    assert pages[0][pages[0].index("-H") + 1] == "If-None-Match: %s" % _ETAG
    assert all("-H" not in argv for argv in pages[1:])
    assert state[0][1] is None
    assert [comment["id"] for comment in state[0][2]] == [1, 2, 3]


def test_a_note_arriving_after_an_empty_cached_read_is_surfaced(repo):
    # axis: a 200 after an empty cached read returns the response's comments, not the cached list — see bite-proof record c8a_wo3.md
    _cloud_lane(repo, "cloud-a", 101, start_age=1000)
    state = _primed(repo)
    new_etag = 'W/"1bbbbbbb"'
    gh = _NoteGh(script=[lambda argv: _ok(argv, [_comment(7, 101)], etag=new_etag)])
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, note_state=state,
    )
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [7]
    [request] = gh.note_calls()
    assert request[request.index("-H") + 1] == "If-None-Match: %s" % _ETAG
    assert state[0][1] == new_etag


# --- one answered note ignored by id (#2099) ---------------------------------------------------


def _ids(result):
    return [note["commentId"] for note in result["notes"]]


def _ignore(launch_id, comment_id):
    return (launch_id, ww.EVENT_BUILDER_NOTE, comment_id)


class _QuietGh(_NoteGh):
    """`_NoteGh` whose graphql answers quiet activity, so a started lane is stale by activity."""

    def __call__(self, argv, **kwargs):
        if argv[:3] == ["gh", "api", "graphql"]:
            self.calls.append(list(argv))
            query = next(arg for arg in argv if arg.startswith("query="))
            issues = [int(n) for n in re.findall(r"i(\d+): issue", query)]
            body = _graphql_body({n: _lane_activity(issue_age=_QUIET) for n in issues})
            return _raw(argv, json.dumps(body))
        return super().__call__(argv, **kwargs)


def test_n1_two_notes_on_one_lane_with_one_ignored_fires_with_only_the_other(repo):
    # axis: NOTE IGNORE — the filter drops the named note and keeps every other
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, age=120), _comment(8, 101, age=60)])
    for result in (
        ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-a", 7),)),
        _arm(repo, gh, ignore_events=(_ignore("cloud-a", 7),)),
    ):
        assert result["event"] == ww.EVENT_BUILDER_NOTE
        assert _ids(result) == [8]
        assert result["launchId"] == "cloud-a"
        assert result["ignoredNotes"] == [7]


def test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it(repo):
    # axis: IGNORED NOTES — a suppressed note is never invisible: the timer result carries its id
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101)])
    ignore = (_ignore("cloud-a", 7),)
    ran = ww.run(repo, _BATCH, gh_run=gh, ignore_events=ignore)
    armed = ww.watch_arm(
        repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, ignore_events=ignore,
    )
    for result in (ran, armed):
        assert result["ok"] is True
        assert result["event"] == ww.EVENT_TIMER
        assert result["ignoredNotes"] == [7]


def test_n2_without_a_note_ignore_the_key_is_absent(repo):
    # axis: valid inputs return a non-refusal result — and that result carries no ignoredNotes without a note ignore
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, "chatter")])
    pair = (("cloud-a", ww.EVENT_LANE_STALE),)
    for ignore in ((), pair):
        ran = ww.run(repo, _BATCH, gh_run=gh, ignore_events=ignore)
        armed = ww.watch_arm(
            repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, ignore_events=ignore,
        )
        for result in (ran, armed):
            assert result["ok"] is True
            assert result["event"] == ww.EVENT_TIMER
            assert "ignoredNotes" not in result


def test_n2_ignored_notes_is_the_sorted_deduplicated_list_of_int_ids(repo):
    # axis: IGNORED NOTES shape — an int-sorted, deduplicated id list — an unsorted, repeated or non-int list makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    ignore = (_ignore("cloud-a", 9), _ignore("cloud-a", 7), _ignore("cloud-b", 9))
    result = ww.run(repo, _BATCH, gh_run=_NoteGh(), ignore_events=ignore)
    assert result["ignoredNotes"] == [7, 9]
    assert all(type(item) is int for item in result["ignoredNotes"])


def test_n3_the_triple_matches_the_launch_id_and_the_comment_id_together(repo):
    # axis: NOTE IGNORE keyed on both — the same comment id on another lane is not suppressed
    _cloud_lane(repo, "cloud-a", 101)
    _cloud_lane(repo, "cloud-b", 202)
    gh = _NoteGh([_comment(7, 101), _comment(9, 202)])
    only_a = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-a", 7),))
    assert only_a["event"] == ww.EVENT_BUILDER_NOTE
    assert _ids(only_a) == [9]
    assert only_a["launchId"] == "cloud-b"
    wrong_lane = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-b", 7),))
    assert _ids(wrong_lane) == [7, 9]
    assert wrong_lane["ignoredNotes"] == [7]


_BAD_CLI = [
    "cloud-a:builder-note", "cloud-a:builder-note:0", "cloud-a:builder-note:-3",
    "cloud-a:builder-note:abc", "cloud-a:builder-note:+5", "cloud-a:builder-note:1.5",
    "cloud-a:builder-note:", ":builder-note:5", ":builder-note", "", "builder-note:5",
    "cloud-a:lane-terminal:5", "cloud-a:builder-note:5:6",
]


@pytest.mark.parametrize("raw", _BAD_CLI)
def test_n4_a_malformed_note_ignore_is_refused_from_the_cli(repo, capsys, raw):
    # axis: NOTE ID validation — the CLI form needs a launch id, builder-note and a positive decimal id
    code = ww.main(["wave_watch.py", "run", "--repo-root", repo, "--batch", _BATCH, "--ignore-event", raw])
    printed = json.loads(capsys.readouterr().out)
    assert code == 1
    assert printed["ok"] is False
    assert printed["reason"] == ww.REFUSAL_IGNORE_EVENT_INVALID


def test_n4_the_cli_parses_the_note_form_splitting_from_the_right():
    # axis: CLI note form — splits from the right, so a launch id with a colon survives — a left split makes it fail
    assert ww._parse_ignore_event_cli("cloud-a:builder-note:7") == ("cloud-a", "builder-note", 7)
    assert ww._parse_ignore_event_cli("a:b:builder-note:12") == ("a:b", "builder-note", 12)
    assert ww._parse_ignore_event_cli("cloud-a:lane-terminal") == ("cloud-a", "lane-terminal")
    for raw in _BAD_CLI:
        assert ww._parse_ignore_event_cli(raw) is None, raw


def test_n4_the_cli_hands_the_note_triple_to_run(repo, monkeypatch):
    # axis: CLI to run — the parsed note triple reaches run as ignore_events — a CLI that drops or reshapes it makes it fail
    seen = {}

    def fake_run(repo_root, batch_id, **kwargs):
        seen.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(ww, "run", fake_run)
    code = ww.main([
        "wave_watch.py", "run", "--repo-root", repo, "--batch", _BATCH,
        "--ignore-event", "cloud-a:builder-note:7", "--ignore-event", "cloud-a:lane-stale",
    ])
    assert code == 0
    assert seen["ignore_events"] == (("cloud-a", "builder-note", 7), ("cloud-a", "lane-stale"))


_BAD_API = [
    ("cloud-a", "builder-note"),
    ("cloud-a", "builder-note", 0), ("cloud-a", "builder-note", -3),
    ("cloud-a", "builder-note", "7"), ("cloud-a", "builder-note", 1.5),
    ("cloud-a", "builder-note", True), ("cloud-a", "builder-note", False),
    ("cloud-a", "builder-note", None),
    ("cloud-a", "lane-terminal", 7), ("cloud-a", "timer", 7), ("cloud-a", "", 7),
    ("", "builder-note", 7), (None, "builder-note", 7), (7, "builder-note", 7),
    ("cloud-a", "builder-note", 7, 8), ["cloud-a"],
]


@pytest.mark.parametrize("bad", _BAD_API)
def test_n4_a_malformed_note_ignore_is_refused_from_the_api(repo, bad):
    # axis: NOTE ID validation — a 3-tuple needs builder-note and a positive int comment id
    for result in (
        ww.run(repo, _BATCH, gh_run=_NoteGh(), ignore_events=(bad,)),
        ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_NoteGh(), ignore_events=(bad,)),
        ww.loop(repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=2, gh_run=_NoteGh(), ignore_events=(bad,)),
    ):
        assert result["ok"] is False
        assert result["reason"] == ww.REFUSAL_IGNORE_EVENT_INVALID
        assert "ignoredNotes" not in result


def test_n4_a_list_triple_is_accepted_like_a_tuple(repo):
    # axis: NOTE IGNORE form — a list triple is accepted like a tuple — a validator that refuses a list makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    result = ww.run(repo, _BATCH, gh_run=_NoteGh([_comment(7, 101)]), ignore_events=(["cloud-a", "builder-note", 7],))
    assert result["event"] == ww.EVENT_TIMER
    assert result["ignoredNotes"] == [7]


def test_n5_a_note_ignore_never_suppresses_lane_terminal(repo):
    # axis: NOTE IGNORE scope — only the named note is dropped; the lane's ending still fires
    _cloud_lane(repo, "cloud-a", 101)
    stop = cb.terminal_text("stop", "Stopped.")["comment"]
    gh = _NoteGh([_comment(7, 101, age=120), _comment(8, 101, stop, age=60)])
    result = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-a", 7),))
    assert result["event"] == ww.EVENT_LANE_TERMINAL
    assert [(x["launchId"], x["state"]) for x in result["launches"]] == [("cloud-a", "stopped")]
    assert result["ignoredNotes"] == [7]


def test_n5_a_note_ignore_never_suppresses_lane_stale(repo):
    # axis: NOTE IGNORE scope — a note ignore never suppresses lane-stale — an ignore that also drops the stale lane makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    gh = _QuietGh([_comment(7, 101)])
    result = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-a", 7),))
    assert result["event"] == ww.EVENT_LANE_STALE
    assert [x["launchId"] for x in result["launches"]] == ["cloud-a"]
    assert result["ignoredNotes"] == [7]


def test_n5_a_note_ignore_leaves_a_class_pair_for_another_event_working(repo):
    # axis: NOTE IGNORE beside a class pair — a lane-stale class pair still suppresses beside a note ignore — a note ignore that displaces the pair makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    gh = _QuietGh([_comment(7, 101)])
    ignore = (_ignore("cloud-a", 7), ("cloud-a", ww.EVENT_LANE_STALE))
    result = ww.run(repo, _BATCH, gh_run=gh, ignore_events=ignore)
    assert result["event"] == ww.EVENT_TIMER
    assert result["ignoredNotes"] == [7]


def test_n6_the_loop_keeps_arming_past_the_ignored_note_and_its_result_carries_it(repo):
    # axis: the loop does not exit on an ignored note, and its final result still names it
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101)])
    result = ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=3, gh_run=gh,
        ignore_events=(_ignore("cloud-a", 7),),
    )
    assert result["ok"] is True
    assert result["event"] == ww.EVENT_TIMER
    assert result["arms"] >= 2
    assert result["ignoredNotes"] == [7]


def test_n6_the_loop_exits_on_a_note_that_is_not_ignored_and_still_names_the_ignored_one(repo):
    # axis: the loop exits on a non-ignored note — a loop that keeps arming past every note makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    gh = _NoteGh([_comment(7, 101, age=120), _comment(8, 101, age=60)])
    result = ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=30, gh_run=gh,
        ignore_events=(_ignore("cloud-a", 7),),
    )
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["arms"] == 1
    assert _ids(result) == [8]
    assert result["ignoredNotes"] == [7]


def test_n6_without_a_note_ignore_the_loop_result_has_no_ignored_notes(repo):
    # axis: loop result shape — no ignoredNotes key without a note ignore — a loop that always adds the key makes it fail
    _cloud_lane(repo, "cloud-a", 101)
    result = ww.loop(
        repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=2,
        gh_run=_NoteGh(),
    )
    assert result["event"] == ww.EVENT_TIMER
    assert "ignoredNotes" not in result
