"""The wave watch reads a cloud lane through its GitHub activity, never a pid, transcript or heartbeat."""
import json
import os
import subprocess
import time
from datetime import datetime, timezone

import pytest

import heartbeat as hb
import launch_ledger as ll
import stack_check as sc
import wave_watch as ww

_BATCH = "batch-cloud"
_WINDOW = ww.LIVENESS_QUIET_WINDOW_SECONDS
_QUIET = _WINDOW + 3600
_FRESH = 60
_SLUG = "owner/repo"
_SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class _Clock:
    """Virtual monotonic clock: time moves only when the watcher sleeps."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += max(duration, 0)


class _TimeModule:
    def __init__(self, clock):
        self.monotonic = clock.monotonic
        self.sleep = clock.sleep

    def __getattr__(self, name):
        return getattr(time, name)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    virtual = _Clock()
    module = _TimeModule(virtual)
    monkeypatch.setattr(ww, "time", module)
    monkeypatch.setattr(sc, "time", module)
    monkeypatch.setattr(
        sc.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None,
    )
    return virtual


def _init_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    git = [
        "git", "-C", str(tmp_path), "-c", "user.email=test@test.local",
        "-c", "user.name=test",
    ]
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "file.txt").write_text("x\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
    return str(tmp_path)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = _init_repo(tmp_path / "repo")
    store = str(tmp_path / "ledger-root")
    os.makedirs(store, mode=0o700, exist_ok=True)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, store)
    os.makedirs(os.path.join(store, ll.repo_identity(root)), mode=0o700, exist_ok=True)
    config_dir = tmp_path / "host-config"
    config_dir.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    ll.declare_batch(root, _BATCH, 4)
    return root


def _iso(age_seconds):
    stamp = datetime.fromtimestamp(time.time() - age_seconds, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _reserved(launch_id, issue, surface, repo_root, **extra):
    rec = {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": _BATCH,
        "repoId": ll.repo_identity(repo_root) or "test",
        "issue": issue,
        "surfaces": [surface],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc123",
        "model": "test-model",
    }
    rec.update(extra)
    return rec


def _add_cloud_lane(
    repo_root, launch_id, issue, *, started=True, pid=999999999, start_age=_QUIET * 5,
    unconfirmed=False,
):
    ll.append(repo_root, _reserved(
        launch_id, issue, "plugins/cloud-%d" % issue, repo_root,
        place=ll.PLACE_CLOUD, cloudEnvironment="env-1", pluginVersion="1.2.3",
    ))
    if not started:
        return
    rec = {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time() - start_age,
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": pid,
        "logPath": "/tmp/log",
        "errPath": "/tmp/err",
        "cloudSessionName": "cloud-%d" % issue,
        "cloudSessionUrl": "https://claude.ai/code/session_%d" % issue,
    }
    if unconfirmed:
        rec["cloudSessionUnconfirmed"] = True
    else:
        rec["cloudSessionId"] = "session_%d" % issue
    ll.append(repo_root, rec)


def _add_local_lane(repo_root, launch_id, issue, *, pid, start_age=_QUIET * 5):
    ll.append(repo_root, _reserved(
        launch_id, issue, "plugins/local-%d" % issue, repo_root, sessionId=_SESSION_ID,
    ))
    ll.append(repo_root, {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time() - start_age,
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": pid,
        "logPath": "/tmp/log",
        "errPath": "/tmp/err",
    })


def _lane_activity(issue_age=_FRESH, prs=(), branches=()):
    """One lane's measured GraphQL slice; ages are seconds before now."""
    return {
        "issue": {
            "updatedAt": _iso(issue_age),
            "closedByPullRequestsReferences": {"nodes": [
                {"number": number, "updatedAt": _iso(age), "headRefName": "x"}
                for number, age in prs
            ]},
        },
        "branches": {"nodes": [
            {"name": name, "target": {"committedDate": _iso(age)}}
            for name, age in branches
        ]},
    }


def _graphql_body(per_issue):
    repository = {}
    for number, lane in per_issue.items():
        repository["i%d" % number] = lane["issue"]
        repository["b%d" % number] = lane["branches"]
    return {"data": {"repository": repository}}


class _Gh:
    """Injected gh_run: records every argv, answers repo view, pr list and graphql."""

    def __init__(self, body=None, *, graphql=None, slug_rc=0):
        self.body = body
        self.graphql = graphql
        self.slug_rc = slug_rc
        self.calls = []
        self.kwargs = []

    def api_calls(self):
        return [argv for argv in self.calls if argv[:3] == ["gh", "api", "graphql"]]

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)
        if argv[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(
                argv, self.slug_rc,
                stdout=json.dumps({"nameWithOwner": _SLUG}), stderr="",
            )
        if argv[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")
        if argv[:3] == ["gh", "api", "graphql"]:
            if self.graphql is not None:
                return self.graphql(argv, **kwargs)
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(self.body), stderr="",
            )
        raise AssertionError("unexpected gh argv: %r" % argv)


def _fresh_gh(*issues):
    return _Gh(_graphql_body({number: _lane_activity() for number in issues}))


def _quiet_gh(*issues):
    return _Gh(_graphql_body({
        number: _lane_activity(issue_age=_QUIET) for number in issues
    }))


def _run(repo_root, gh, **kwargs):
    return ww.run(repo_root, _BATCH, gh_run=gh, **kwargs)


# --- edge 1-3: the local readers never see a cloud lane -----------------------


def test_edge1_dead_recorded_pid_is_not_builder_exited(repo):
    _add_cloud_lane(repo, "cloud-a", 101, pid=999999999)
    result = _run(repo, _fresh_gh(101))
    assert result["event"] == "timer"
    assert ww.EVENT_BUILDER_EXITED != result["event"]
    assert ww.DEGRADATION_PID_PROBE_UNCERTAIN not in result["degraded"]


def test_edge2_live_recorded_pid_with_no_transcript_is_not_lane_stale(repo):
    _add_cloud_lane(repo, "cloud-a", 101, pid=os.getpid())
    result = _run(repo, _fresh_gh(101))
    assert result["event"] == "timer"
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED not in result["degraded"]
    assert ww.DEGRADATION_TRANSCRIPT_AMBIGUOUS not in result["degraded"]


def test_edge3_missing_heartbeat_at_deadline_is_not_never_stamped(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_fresh_gh(101),
    )
    assert result["event"] == "timer"
    assert ww.DEGRADATION_LANE_NEVER_STAMPED not in result["degraded"]


def test_edge3_stray_handback_heartbeat_is_not_lane_terminal(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    stamped = hb.stamp(repo, state="handback", phase="watch", launch_id="cloud-a")
    assert stamped.get("ok") is True, stamped
    result = _run(repo, _fresh_gh(101))
    assert result["event"] == "timer"
    assert ww.DEGRADATION_HEARTBEAT_UNREADABLE not in result["degraded"]


# --- edge 4: activity freshness -----------------------------------------------


def test_edge4_fresh_activity_produces_no_event(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    result = _run(repo, _fresh_gh(101))
    assert result["event"] == "timer"
    assert result["degraded"] == []


def test_edge4_quiet_activity_is_lane_stale_with_the_cloud_entry(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    result = _run(repo, _quiet_gh(101))
    assert result["event"] == "lane-stale"
    assert result["launchId"] == "cloud-a"
    [entry] = result["launches"]
    assert set(entry) == {
        "launchId", "state", "place", "activityAgeSeconds", "quietWindowSeconds",
        "cloudSessionName", "cloudSessionId",
    }
    assert entry["launchId"] == "cloud-a"
    assert entry["state"] is None
    assert entry["place"] == "cloud"
    assert entry["quietWindowSeconds"] == _WINDOW
    assert entry["cloudSessionName"] == "cloud-101"
    assert entry["cloudSessionId"] == "session_101"
    assert _QUIET <= entry["activityAgeSeconds"] < _QUIET + 120
    assert entry["activityAgeSeconds"] == round(entry["activityAgeSeconds"], 3)


def test_edge4_unconfirmed_session_has_no_id_in_the_stale_entry(repo):
    _add_cloud_lane(repo, "cloud-a", 101, unconfirmed=True)
    result = _run(repo, _quiet_gh(101))
    assert result["event"] == "lane-stale"
    assert result["launches"][0]["cloudSessionId"] is None
    assert result["cloudLanes"][0]["cloudSessionId"] is None


def test_edge4_future_dated_activity_is_stale(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    future = _lane_activity(issue_age=-7200)
    result = _run(repo, _Gh(_graphql_body({101: future})))
    assert result["event"] == "lane-stale"
    assert result["launches"][0]["activityAgeSeconds"] < 0


def test_edge4_recent_start_holds_a_quiet_lane_live(repo):
    _add_cloud_lane(repo, "cloud-a", 101, start_age=_FRESH)
    result = _run(repo, _quiet_gh(101))
    assert result["event"] == "timer"


def test_edge4_fresh_pr_activity_keeps_a_quiet_issue_live(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    lane = _lane_activity(issue_age=_QUIET, prs=[(900, _FRESH)])
    result = _run(repo, _Gh(_graphql_body({101: lane})))
    assert result["event"] == "timer"


# --- edge 5: branches ---------------------------------------------------------


def test_edge5_a_fresh_branch_push_alone_keeps_the_lane_live(repo):
    _add_cloud_lane(repo, "cloud-a", 17)
    lane = _lane_activity(
        issue_age=_QUIET, prs=[(900, _QUIET)],
        branches=[("feat/17-review-record", _FRESH)],
    )
    result = _run(repo, _Gh(_graphql_body({17: lane})))
    assert result["event"] == "timer"


def test_edge5_a_branch_with_a_longer_number_is_not_counted(repo):
    _add_cloud_lane(repo, "cloud-a", 17)
    lane = _lane_activity(
        issue_age=_QUIET, prs=[(900, _QUIET)],
        branches=[
            ("build/170-other", _FRESH), ("feat/2017-thing", _FRESH),
            ("build/117", _FRESH), ("build/1271-l2-a170", _FRESH),
        ],
    )
    result = _run(repo, _Gh(_graphql_body({17: lane})))
    assert result["event"] == "lane-stale"


# --- request shape ------------------------------------------------------------


def test_one_graphql_request_covers_every_cloud_lane(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    _add_cloud_lane(repo, "cloud-b", 102)
    gh = _fresh_gh(101, 102)
    result = _run(repo, gh)
    assert result["event"] == "timer"
    [argv] = gh.api_calls()
    assert argv[:9] == [
        "gh", "api", "graphql", "-F", "owner=owner", "-F", "name=repo", "-f", argv[8],
    ]
    query = argv[8]
    assert query.startswith("query=query($owner: String!, $name: String!) { repository(")
    for number in (101, 102):
        assert "i%d: issue(number: %d)" % (number, number) in query
        assert 'b%d: refs(refPrefix: "refs/heads/", query: "%d", first: 50)' % (
            number, number) in query
    assert "closedByPullRequestsReferences(first: 10, includeClosedPrs: true)" in query
    graphql_kwargs = gh.kwargs[gh.calls.index(argv)]
    assert graphql_kwargs["cwd"] == repo
    assert graphql_kwargs["timeout"] <= 30.0
    assert "GIT_DIR" not in graphql_kwargs["env"]


# --- edge 6: a read that could not be made ------------------------------------


def _raise_oserror(argv, **kwargs):
    raise OSError("gh vanished")


def _raise_timeout(argv, **kwargs):
    raise subprocess.TimeoutExpired(argv, 30)


def _exit_nonzero(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="boom")


def _not_json(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 0, stdout="<html>", stderr="")


def _with_errors(argv, **kwargs):
    body = _graphql_body({101: _lane_activity(issue_age=_QUIET)})
    body["errors"] = [{"message": "rate limited"}]
    return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(body), stderr="")


def _selection_missing(argv, **kwargs):
    body = _graphql_body({101: _lane_activity(issue_age=_QUIET)})
    del body["data"]["repository"]["i101"]
    return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(body), stderr="")


def _selection_null(argv, **kwargs):
    body = _graphql_body({101: _lane_activity(issue_age=_QUIET)})
    body["data"]["repository"]["i101"] = None
    return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(body), stderr="")


def _bad_timestamp(argv, **kwargs):
    lane = _lane_activity(issue_age=_QUIET)
    lane["issue"]["updatedAt"] = "yesterday"
    return subprocess.CompletedProcess(
        argv, 0, stdout=json.dumps(_graphql_body({101: lane})), stderr="",
    )


def _bad_branch_timestamp(argv, **kwargs):
    lane = _lane_activity(issue_age=_QUIET, branches=[("feat/101-x", 5)])
    lane["branches"]["nodes"][0]["target"]["committedDate"] = "2026-13-45T99:00:00Z"
    return subprocess.CompletedProcess(
        argv, 0, stdout=json.dumps(_graphql_body({101: lane})), stderr="",
    )


@pytest.mark.parametrize("graphql", [
    _raise_oserror, _raise_timeout, _exit_nonzero, _not_json, _with_errors,
    _selection_missing, _selection_null, _bad_timestamp, _bad_branch_timestamp,
])
def test_edge6_an_unreadable_read_degrades_and_the_lane_is_not_stale(repo, graphql):
    _add_cloud_lane(repo, "cloud-a", 101)
    result = _run(repo, _Gh(graphql=graphql))
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in result["degraded"]
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-a"]


def test_edge6_an_unresolvable_slug_degrades_and_the_lane_is_not_stale(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    gh = _Gh(_graphql_body({101: _lane_activity(issue_age=_QUIET)}), slug_rc=1)
    result = _run(repo, gh)
    assert result["event"] == "timer"
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in result["degraded"]
    assert gh.api_calls() == []


def test_edge6_one_bad_lane_does_not_hide_a_stale_sibling(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    _add_cloud_lane(repo, "cloud-b", 102)
    body = _graphql_body({
        101: _lane_activity(issue_age=_QUIET), 102: _lane_activity(issue_age=_QUIET),
    })
    body["data"]["repository"]["i101"] = None
    result = _run(repo, _Gh(body))
    assert result["event"] == "lane-stale"
    assert [entry["launchId"] for entry in result["launches"]] == ["cloud-b"]
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in result["degraded"]


# --- edge 7: reserved, not started --------------------------------------------


def test_edge7_a_reserved_unstarted_cloud_lane_makes_no_request(repo):
    _add_cloud_lane(repo, "cloud-a", 101, started=False)
    gh = _fresh_gh(101)
    result = _run(repo, gh)
    assert result["event"] == "timer"
    assert gh.api_calls() == []
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-a"]


def test_edge7_only_started_cloud_lanes_are_requested(repo):
    _add_cloud_lane(repo, "cloud-a", 101, started=False)
    _add_cloud_lane(repo, "cloud-b", 102)
    gh = _fresh_gh(102)
    result = _run(repo, gh)
    [argv] = gh.api_calls()
    assert "i102:" in argv[8] and "i101:" not in argv[8]
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-a", "cloud-b"]


# --- edge 8: a batch with no cloud lane ---------------------------------------


def test_edge8_a_local_only_batch_makes_no_graphql_request_and_has_no_key(repo):
    _add_local_lane(repo, "local-a", 201, pid=os.getpid())
    gh = _fresh_gh()
    result = _run(repo, gh)
    assert gh.api_calls() == []
    assert "cloudLanes" not in result


def test_edge8_an_empty_batch_has_no_key_on_run_or_deadline_timer(repo):
    gh = _fresh_gh()
    assert "cloudLanes" not in _run(repo, gh)
    deadline = ww.watch_arm(
        repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh,
    )
    assert deadline["event"] == "timer"
    assert "cloudLanes" not in deadline
    assert gh.api_calls() == []


# --- edge 9: mixed batch ------------------------------------------------------


def test_edge9_one_lane_stale_carries_a_stale_local_and_a_stale_cloud_lane(repo):
    _add_local_lane(repo, "local-a", 201, pid=os.getpid())
    _add_cloud_lane(repo, "cloud-b", 101)
    result = _run(repo, _quiet_gh(101))
    assert result["event"] == "lane-stale"
    assert [entry["launchId"] for entry in result["launches"]] == ["local-a", "cloud-b"]
    local_entry, cloud_entry = result["launches"]
    assert "transcriptAgeSeconds" in local_entry and "place" not in local_entry
    assert cloud_entry["place"] == "cloud"
    assert result["launchId"] == "local-a"
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-b"]


def test_edge9_a_higher_precedence_event_means_no_cloud_read(repo):
    _add_local_lane(repo, "local-a", 201, pid=999999999)
    _add_cloud_lane(repo, "cloud-b", 101)
    gh = _quiet_gh(101)
    result = _run(repo, gh)
    assert result["event"] == "builder-exited"
    assert gh.api_calls() == []
    assert "stale" not in result.get("alsoObserved", {})
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-b"]


# --- edge 10: one poll per interval -------------------------------------------


def test_edge10_a_second_tick_inside_sixty_seconds_makes_no_second_request(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    gh = _fresh_gh(101)
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=40, interval_seconds=10, gh_run=gh,
    )
    assert result["event"] == "timer"
    assert len(gh.api_calls()) == 1


def test_edge10_a_tick_after_sixty_seconds_reads_again(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    gh = _fresh_gh(101)
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=90, interval_seconds=30, gh_run=gh,
    )
    assert result["event"] == "timer"
    assert len(gh.api_calls()) == 2


def test_edge10_a_cached_failed_read_stays_disclosed_without_a_second_request(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    gh = _Gh(graphql=_exit_nonzero)
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=40, interval_seconds=10, gh_run=gh,
    )
    assert result["event"] == "timer"
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in result["degraded"]
    assert len(gh.api_calls()) == 1


def test_edge10_loop_threads_the_cache_across_arms(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    gh = _fresh_gh(101)
    result = ww.loop(
        repo, _BATCH, max_seconds=10, interval_seconds=5, max_total_seconds=40,
        gh_run=gh,
    )
    assert result["event"] == "timer"
    assert result["arms"] >= 3
    assert len(gh.api_calls()) == 1


# --- the public entry points carry the result key -----------------------------


def test_loop_exits_on_a_stale_cloud_lane_and_carries_cloud_lanes(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    result = ww.loop(
        repo, _BATCH, max_seconds=5, interval_seconds=5, gh_run=_quiet_gh(101),
    )
    assert result["event"] == "lane-stale"
    assert result["launches"][0]["place"] == "cloud"
    assert result["cloudLanes"] == [{
        "launchId": "cloud-a", "issue": 101,
        "cloudSessionName": "cloud-101", "cloudSessionId": "session_101",
    }]


def test_cloud_lanes_is_sorted_by_launch_id_and_names_the_session(repo):
    _add_cloud_lane(repo, "cloud-b", 102, unconfirmed=True)
    _add_cloud_lane(repo, "cloud-a", 101)
    result = _run(repo, _fresh_gh(101, 102))
    assert result["cloudLanes"] == [
        {"launchId": "cloud-a", "issue": 101,
         "cloudSessionName": "cloud-101", "cloudSessionId": "session_101"},
        {"launchId": "cloud-b", "issue": 102,
         "cloudSessionName": "cloud-102", "cloudSessionId": None},
    ]


def test_deadline_timer_carries_cloud_lanes(repo):
    _add_cloud_lane(repo, "cloud-a", 101)
    result = ww.watch_arm(
        repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_fresh_gh(101),
    )
    assert result["event"] == "timer"
    assert [lane["launchId"] for lane in result["cloudLanes"]] == ["cloud-a"]


def test_the_degradation_token_is_part_of_the_vocabulary():
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE == "cloud-activity-unavailable"
    assert ww.DEGRADATION_CLOUD_ACTIVITY_UNAVAILABLE in ww.DEGRADATIONS
