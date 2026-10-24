"""The wave watch's open-PR list and cloud-activity read fall back to REST on the proxy's GraphQL refusal."""
import calendar
import json
import pathlib
import subprocess
import time

import pytest

import launch_ledger as ll
import stack_check as sc
import wave_watch as ww

_FIXTURES = pathlib.Path(__file__).parent / "fixtures"
_CLOUD = _FIXTURES / "cloud_rest"
_STACK = _FIXTURES / "stack_rest"
_SLUG = "zwrose/superheroes"
_BASE = "repos/%s" % _SLUG
_PAGE = "per_page=100&page=%d"
_PR_LIST_REST = sc._OPEN_PRS_REST_PATH + "&" + _PAGE % 1
_QUIET = ww.LIVENESS_QUIET_WINDOW_SECONDS + 3600
_BRANCH_SHA = "34dc2c5c6aa8d0836363fdd7e51c397b7d0d40db"
_ISSUE_AT = "2026-10-24T03:16:29Z"
_PR_AT = "2026-10-24T03:15:57Z"
_COMMIT_AT = "2026-10-24T02:53:34Z"
_FRESH_AT = "2026-10-25T00:00:00Z"
_OTHER_TIME = "2026-10-20T00:00:00Z"
_DEADLINE = 100.0


def _epoch(stamp):
    return float(calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")))


def _text(path):
    return path.read_text()


def _json(name):
    return json.loads(_text(_CLOUD / name))


class _Clock:
    """Virtual monotonic clock plus a fixed wall time; time moves only when a test moves it."""

    def __init__(self):
        self.now = 0.0
        self.wall = _epoch(_ISSUE_AT) + _QUIET

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += max(duration, 0)


class _TimeModule:
    def __init__(self, clock):
        self.monotonic = clock.monotonic
        self.sleep = clock.sleep
        self.time = lambda: clock.wall

    def __getattr__(self, name):
        return getattr(time, name)


@pytest.fixture
def clock(monkeypatch):
    virtual = _Clock()
    module = _TimeModule(virtual)
    monkeypatch.setattr(ww, "time", module)
    monkeypatch.setattr(sc, "time", module)
    return virtual


def _proc(argv, rc, out, err=""):
    return subprocess.CompletedProcess(argv, rc, stdout=out, stderr=err)


class _Gh:
    """Injected gh_run keyed on argv: `gh api <endpoint>` by endpoint, `gh api graphql`, `gh pr list`.

    A route is (returncode, stdout, stderr) or a callable taking argv and returning that tuple.
    A route that is missing answers a failure and is recorded, so a read never passes by luck."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []
        self.kwargs = []
        self.unrouted = []

    @staticmethod
    def _key(argv):
        if argv[:3] == ["gh", "api", "graphql"]:
            return "graphql"
        if argv[:3] == ["gh", "pr", "list"]:
            return "pr-list"
        if argv[:2] == ["gh", "api"]:
            return argv[2]
        return tuple(argv)

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)
        key = self._key(argv)
        route = self.routes.get(key)
        if route is None:
            self.unrouted.append(key)
            return _proc(argv, 1, "", "no route for %s" % (key,))
        if callable(route):
            route = route(argv)
        return _proc(argv, *route)

    def rest_calls(self):
        return [
            call for call in self.calls
            if call[:2] == ["gh", "api"] and call[2] != "graphql"
        ]


_PR_LIST_REFUSED = (1, "", _text(_CLOUD / "gh_pr_list_refused.stderr"))
_GRAPHQL_REFUSED = (
    1, _text(_STACK / "graphql_refused.stdout"), _text(_STACK / "graphql_refused.stderr"),
)
_BOOM = (1, "", "boom")


def _pages(path, rows):
    """The page routes of a REST list read by number: full pages, then the short or empty one."""
    routes = {}
    chunks = [rows[i:i + 100] for i in range(0, len(rows), 100)]
    if not chunks or len(chunks[-1]) == 100:
        chunks.append([])
    for number, chunk in enumerate(chunks, 1):
        routes["%s?%s" % (path, _PAGE % number)] = (0, json.dumps(chunk), "")
    return routes


def _branch_rows():
    return _json("branches_page1.json") + _json("branches_page2.json")


def _xref(pr, body="Closes #2110.", repo=_SLUG):
    return {
        "event": "cross-referenced",
        "source": {"type": "issue", "issue": {
            "number": pr, "pull_request": {}, "body": body,
            "repository": {"full_name": repo},
        }},
    }


_NO_STACK = object()


def _pull(pr, base="main", updated=_PR_AT, head="claude/issue-2110-nxhfk5", stack=_NO_STACK):
    """A `pulls/<n>` object; it carries a `stack` key only when `stack` is given."""
    payload = {
        "number": pr, "base": {"ref": base}, "head": {"ref": head, "sha": _BRANCH_SHA},
        "updated_at": updated,
    }
    if stack is not _NO_STACK:
        payload["stack"] = stack
    return payload


def _issue(number, updated=_ISSUE_AT):
    payload = _json("issues_2110.json")
    payload["number"] = number
    payload["updated_at"] = updated
    return payload


def _routes(*, timeline=None, pulls=None, branches=None, extra_issues=()):
    """The REST routes of a readable activity read for issue 2110 (and any `extra_issues`)."""
    routes = {
        _BASE: (0, _text(_STACK / "repos_superheroes.json"), ""),
        "%s/issues/2110" % _BASE: (0, _text(_CLOUD / "issues_2110.json"), ""),
        "%s/git/commits/%s" % (_BASE, _BRANCH_SHA): (
            0, _text(_CLOUD / "git_commits_34dc2c5c.json"), ""),
    }
    rows = _branch_rows() if branches is None else branches
    routes.update(_pages("%s/branches" % _BASE, rows))
    timeline = _json("issues_2110_timeline_page1.json") if timeline is None else timeline
    routes.update(_pages("%s/issues/2110/timeline" % _BASE, timeline))
    pulls = {2113: _json("pulls_2113.json")} if pulls is None else pulls
    for number, payload in pulls.items():
        routes["%s/pulls/%d" % (_BASE, number)] = (0, json.dumps(payload), "")
    for number in extra_issues:
        routes["%s/issues/%d" % (_BASE, number)] = (0, json.dumps(_issue(number, _OTHER_TIME)), "")
        routes.update(_pages("%s/issues/%d/timeline" % (_BASE, number), []))
    return routes


def _activity_gh(graphql, **rest):
    routes = _routes(**rest)
    routes["graphql"] = graphql
    return _Gh(routes)


def _graphql_body():
    """The GraphQL response for issue 2110, built from the same recorded data the REST routes serve."""
    commit = _json("git_commits_34dc2c5c.json")
    refs = []
    for row in _branch_rows():
        if "2110" in row["name"]:
            assert row["commit"]["sha"] == commit["sha"]
            refs.append({
                "name": row["name"], "target": {"committedDate": commit["committer"]["date"]},
            })
    pull = _json("pulls_2113.json")
    return {"data": {"repository": {
        "i2110": {
            "updatedAt": _json("issues_2110.json")["updated_at"],
            "closedByPullRequestsReferences": {
                "pageInfo": {"hasNextPage": False},
                "nodes": [{
                    "number": pull["number"], "updatedAt": pull["updated_at"],
                    "headRefName": pull["head"]["ref"],
                }],
            },
        },
        "b2110": {"pageInfo": {"hasNextPage": False}, "nodes": refs},
    }}}


def _graphql_ok():
    return (0, json.dumps(_graphql_body()), "")


def _fetch(gh, root, issues=(2110,), deadline=_DEADLINE, clock=None):
    return ww._fetch_cloud_activity(
        str(root), list(issues), deadline, clock.monotonic, gh, None, _SLUG,
    )


def _poll(gh, root, clock):
    degraded = set()
    sampled = [False]
    result = ww._poll_open_pr_numbers(
        str(root), _DEADLINE, clock.monotonic, gh, None, degraded, sampled,
    )
    return result, degraded, sampled[0]


_PR_NUMBERS = [row["number"] for row in _json("pulls_open_page1.json")]


# --- open-PR list --------------------------------------------------------------


def test_the_pr_list_argv_stays_the_one_the_watch_always_ran():
    assert ww._GH_PR_LIST_ARGV == [
        "gh", "pr", "list", "--state", "open", "--json", "number", "--limit", "1000",
    ]


def test_w1_graphql_pr_list_answers_with_zero_rest_calls(tmp_path, clock):
    gh = _Gh({"pr-list": (0, json.dumps([{"number": n} for n in _PR_NUMBERS]), "")})
    result, degraded, sampled = _poll(gh, tmp_path, clock)
    assert result == (sorted(_PR_NUMBERS), True)
    assert degraded == set()
    assert sampled is True
    assert gh.rest_calls() == []


def test_w2_refused_pr_list_reads_the_numbers_through_rest(tmp_path, clock):
    gh = _Gh({
        "pr-list": _PR_LIST_REFUSED,
        _PR_LIST_REST: (0, _text(_CLOUD / "pulls_open_page1.json"), ""),
    })
    result, degraded, sampled = _poll(gh, tmp_path, clock)
    assert result == (sorted(_PR_NUMBERS), True)
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE not in degraded
    assert sampled is True
    assert gh.unrouted == []


def test_w3_rest_page_failing_after_the_refusal_is_pr_signal_unavailable(tmp_path, clock):
    gh = _Gh({"pr-list": _PR_LIST_REFUSED, _PR_LIST_REST: _BOOM})
    result, degraded, sampled = _poll(gh, tmp_path, clock)
    assert result == (None, False)
    assert degraded == {ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE}
    assert sampled is False


def test_pr_list_failing_without_the_refusal_never_falls_back(tmp_path, clock):
    gh = _Gh({"pr-list": _BOOM})
    result, degraded, _sampled = _poll(gh, tmp_path, clock)
    assert result == (None, False)
    assert degraded == {ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE}
    assert gh.rest_calls() == []


@pytest.mark.parametrize("number", [True, "7", None])
def test_a_row_whose_number_is_not_an_int_is_pr_signal_unavailable(tmp_path, clock, number):
    gh = _Gh({"pr-list": (0, json.dumps([{"number": number}]), "")})
    result, degraded, sampled = _poll(gh, tmp_path, clock)
    assert result == (None, False)
    assert degraded == {ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE}
    assert sampled is False


def test_the_pr_list_runs_in_the_repo_with_the_scrubbed_env(tmp_path, clock):
    gh = _Gh({"pr-list": (0, "[]", "")})
    _poll(gh, tmp_path, clock)
    assert gh.calls == [ww._GH_PR_LIST_ARGV]
    assert gh.kwargs[0]["cwd"] == str(tmp_path)
    assert gh.kwargs[0]["env"] == ww._gh_scrub_env(None)


@pytest.mark.parametrize("transport", ["graphql", "rest"])
def test_a_pr_list_equivalence_same_numbers_on_both_transports(tmp_path, clock, transport):
    if transport == "graphql":
        gh = _Gh({"pr-list": (0, json.dumps([{"number": n} for n in _PR_NUMBERS]), "")})
    else:
        gh = _Gh({
            "pr-list": _PR_LIST_REFUSED,
            _PR_LIST_REST: (0, _text(_CLOUD / "pulls_open_page1.json"), ""),
        })
    result, degraded, _sampled = _poll(gh, tmp_path, clock)
    assert result == (sorted(_PR_NUMBERS), True)
    assert degraded == set()


# --- cloud activity: equivalence -------------------------------------------------


@pytest.mark.parametrize("transport", ["graphql", "rest"])
def test_b_activity_equivalence_same_epoch_on_both_transports(tmp_path, clock, transport):
    graphql = _graphql_ok() if transport == "graphql" else _GRAPHQL_REFUSED
    gh = _activity_gh(graphql)
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}
    assert gh.unrouted == []
    if transport == "graphql":
        assert gh.rest_calls() == []


def test_rest_branch_committer_date_is_the_newest_activity(tmp_path, clock):
    # axis: the branch head commit's committer date, not its author date or the issue's time
    gh = _activity_gh(_GRAPHQL_REFUSED)
    commit = _json("git_commits_34dc2c5c.json")
    commit["author"]["date"] = _OTHER_TIME
    commit["committer"]["date"] = _FRESH_AT
    endpoint = "%s/git/commits/%s" % (_BASE, _BRANCH_SHA)
    gh.routes[endpoint] = (0, json.dumps(commit), "")
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_FRESH_AT)}
    assert gh.unrouted == []


def test_graphql_branch_committed_date_is_the_newest_activity(tmp_path, clock):
    # the same data on the GraphQL transport answers the same epoch as the REST test above
    body = _graphql_body()
    nodes = body["data"]["repository"]["b2110"]["nodes"]
    assert nodes
    for node in nodes:
        node["target"]["committedDate"] = _FRESH_AT
    gh = _activity_gh((0, json.dumps(body), ""))
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_FRESH_AT)}
    assert gh.rest_calls() == []


def _lane(started_ts):
    return {
        "2110": {
            "place": ll.PLACE_CLOUD, "started": True, "issue": 2110, "startedTs": started_ts,
            "cloudSessionName": "cloud-2110", "cloudSessionId": "session_2110",
        },
    }


@pytest.mark.parametrize("wall_after", [_QUIET, 60])
def test_b_activity_evaluation_reports_the_same_on_both_transports(tmp_path, clock, wall_after):
    clock.wall = _epoch(_ISSUE_AT) + wall_after
    outcomes = []
    for graphql in (_graphql_ok(), _GRAPHQL_REFUSED):
        gh = _activity_gh(graphql)
        degraded = set()
        stale = ww._evaluate_cloud_activity(
            str(tmp_path), _lane(_epoch(_ISSUE_AT) - 86400), deadline=_DEADLINE, env=None,
            gh_run=gh, monotonic=clock.monotonic, degraded=degraded, cloud_state=None,
            known_slug=_SLUG,
        )
        assert gh.unrouted == []
        outcomes.append((stale, degraded))
    assert outcomes[0] == outcomes[1]
    stale, degraded = outcomes[1]
    assert degraded == set()
    assert bool(stale) is (wall_after == _QUIET)


# --- cloud activity: fail-closed edges -------------------------------------------


def test_w4_graphql_failing_without_the_refusal_is_unreadable_with_zero_rest_calls(tmp_path, clock):
    gh = _activity_gh(_BOOM)
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}
    assert gh.rest_calls() == []


def test_the_rest_reads_run_in_the_repo_on_the_explicit_slug_with_the_scrubbed_env(tmp_path, clock):
    gh = _activity_gh(_GRAPHQL_REFUSED)
    _fetch(gh, tmp_path, clock=clock)
    assert all(call[2].startswith(_BASE) for call in gh.rest_calls())
    assert all(kwargs["cwd"] == str(tmp_path) for kwargs in gh.kwargs)
    assert all(kwargs["env"] == ww._gh_scrub_env(None) for kwargs in gh.kwargs)


_TWO = {
    "baseline": None,
    "default-branch": _BASE,
    "issue": "%s/issues/2110" % _BASE,
    "timeline": "%s/issues/2110/timeline?%s" % (_BASE, _PAGE % 1),
    "branches-page-2": "%s/branches?%s" % (_BASE, _PAGE % 2),
    "git-commit": "%s/git/commits/%s" % (_BASE, _BRANCH_SHA),
    "pull-request": "%s/pulls/2113" % _BASE,
    "second-issue-timeline": "%s/issues/2111/timeline?%s" % (_BASE, _PAGE % 1),
}


def test_two_issues_read_when_every_get_answers(tmp_path, clock):
    assert not any("2111" in row["name"] for row in _branch_rows())
    gh = _activity_gh(_GRAPHQL_REFUSED, extra_issues=(2111,))
    assert _fetch(gh, tmp_path, issues=(2110, 2111), clock=clock) == {
        2110: _epoch(_ISSUE_AT), 2111: _epoch(_OTHER_TIME),
    }
    assert gh.unrouted == []


@pytest.mark.parametrize("failing", [name for name in _TWO if name != "baseline"])
def test_w5_any_one_rest_get_failing_makes_every_issue_unreadable(tmp_path, clock, failing):
    gh = _activity_gh(_GRAPHQL_REFUSED, extra_issues=(2111,))
    gh.routes[_TWO[failing]] = _BOOM
    assert _fetch(gh, tmp_path, issues=(2110, 2111), clock=clock) == {2110: None, 2111: None}


@pytest.mark.parametrize("mutate", [
    lambda issue: issue.update(pull_request={"url": "x"}),
    lambda issue: issue.update(number=2111),
], ids=["pull-request-shaped", "number-mismatch"])
def test_w6_a_pr_shaped_issue_response_is_unreadable(tmp_path, clock, mutate):
    issue = _issue(2110)
    mutate(issue)
    gh = _activity_gh(_GRAPHQL_REFUSED)
    gh.routes["%s/issues/2110" % _BASE] = (0, json.dumps(issue), "")
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}


@pytest.mark.parametrize("event", ["connected", "disconnected"])
def test_w7_a_manual_link_event_is_unreadable(tmp_path, clock, event):
    timeline = _json("issues_2110_timeline_page1.json") + [{"event": event}]
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline)
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}


def test_w8_a_keyword_pr_to_another_branch_is_not_a_closing_node(tmp_path, clock):
    # a plain PR (no stack) to another branch: GitHub lists it in no closing reference
    other = _pull(2113, base="dev", updated=_FRESH_AT)
    assert "stack" not in other
    gh = _activity_gh(_GRAPHQL_REFUSED, pulls={2113: other})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}


def _graphql_2103():
    """The GraphQL response for issue 2103, built from the recorded REST data."""
    pull = _json("pulls_2105.json")
    return {"data": {"repository": {
        "i2103": {
            "updatedAt": _json("issues_2103.json")["updated_at"],
            "closedByPullRequestsReferences": {
                "pageInfo": {"hasNextPage": False},
                "nodes": [{
                    "number": pull["number"], "updatedAt": pull["updated_at"],
                    "headRefName": pull["head"]["ref"],
                }],
            },
        },
        "b2103": {"pageInfo": {"hasNextPage": False}, "nodes": []},
    }}}


def _gh_2103(graphql, pull=None):
    routes = {
        _BASE: (0, _text(_STACK / "repos_superheroes.json"), ""),
        "%s/issues/2103" % _BASE: (0, _text(_CLOUD / "issues_2103.json"), ""),
        "%s/pulls/2105" % _BASE: (0, json.dumps(_json("pulls_2105.json") if pull is None else pull), ""),
        "graphql": graphql,
    }
    routes.update(_pages("%s/branches" % _BASE, _branch_rows()))
    routes.update(_pages("%s/issues/2103/timeline" % _BASE, _json("issues_2103_timeline_page1.json")))
    return _Gh(routes)


@pytest.mark.parametrize("transport", ["graphql", "rest"])
def test_a_stack_layer_closing_pr_counts_the_same_on_both_transports(tmp_path, clock, transport):
    assert not any("2103" in row["name"] for row in _branch_rows())
    pull = _json("pulls_2105.json")
    assert pull["base"]["ref"] != "main" and pull["stack"]["number"] == 2106
    graphql = (0, json.dumps(_graphql_2103()), "") if transport == "graphql" else _GRAPHQL_REFUSED
    gh = _gh_2103(graphql)
    assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: _epoch(pull["updated_at"])}
    assert gh.unrouted == []
    if transport == "graphql":
        assert gh.rest_calls() == []


@pytest.mark.parametrize("stack", [{"number": "x"}, "not-an-object", 7, []],
                         ids=["bad-number", "string", "integer", "list"])
def test_a_stack_layer_whose_stack_is_malformed_makes_the_whole_read_unavailable(
    tmp_path, clock, stack,
):
    pull = _json("pulls_2105.json")
    pull["stack"] = stack
    gh = _gh_2103(_GRAPHQL_REFUSED, pull=pull)
    assert _fetch(gh, tmp_path, issues=(2103,), clock=clock) == {2103: None}


def test_a_default_branch_pr_with_a_stack_key_still_counts(tmp_path, clock):
    pull = _pull(2113, base="main", updated=_FRESH_AT, stack={"number": "x"})
    gh = _activity_gh(_GRAPHQL_REFUSED, pulls={2113: pull})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_FRESH_AT)}


def test_w8_control_the_same_pr_to_the_default_branch_counts(tmp_path, clock):
    fresh = _pull(2113, base="main", updated=_FRESH_AT)
    gh = _activity_gh(_GRAPHQL_REFUSED, pulls={2113: fresh})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_FRESH_AT)}


@pytest.mark.parametrize("body,counts", [
    ("Closes https://github.com/%s/issues/2110" % _SLUG, True),
    ("Fixes: https://github.com/%s/issues/2110." % _SLUG, True),
    ("Intro line\n\nResolves #2110", True),
    ("Closes:\n\n#2110", False),
    ("Closes\n#2110", False),
    ("Closes https://github.com/%s/issues/21100" % _SLUG, False),
])
def test_the_closing_reference_follows_githubs_same_line_syntax(tmp_path, clock, body, counts):
    timeline = [_xref(2113, body=body)]
    fresh = _pull(2113, base="main", updated=_FRESH_AT)
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline, pulls={2113: fresh})
    expected = _epoch(_FRESH_AT) if counts else _epoch(_ISSUE_AT)
    assert _fetch(gh, tmp_path, clock=clock) == {2110: expected}


def test_a_closing_url_for_another_repository_is_unreadable(tmp_path, clock):
    timeline = [_xref(3001, body="Closes https://github.com/%s/issues/2110" % _SLUG,
                      repo="other/repo")]
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline, pulls={})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}


def _many_prs(count):
    timeline = [_xref(3000 + k) for k in range(count)]
    pulls = {3000 + k: _pull(3000 + k, updated=_OTHER_TIME) for k in range(count)}
    return timeline, pulls


@pytest.mark.parametrize("count,readable", [(11, False), (10, True)])
def test_w9_more_than_ten_keyword_prs_on_the_default_branch_is_unreadable(
    tmp_path, clock, count, readable,
):
    timeline, pulls = _many_prs(count)
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline, pulls=pulls)
    result = _fetch(gh, tmp_path, clock=clock)
    assert result == {2110: _epoch(_ISSUE_AT) if readable else None}
    assert gh.unrouted == []


def _extra_branches(count):
    return [
        {"name": "q-21100-%d" % k, "commit": {"sha": "%040x" % (k + 1)}} for k in range(count)
    ]


@pytest.mark.parametrize("extra,readable", [(50, False), (49, True)])
def test_w10_more_than_fifty_substring_branches_is_unreadable(tmp_path, clock, extra, readable):
    rows = _branch_rows() + _extra_branches(extra)
    gh = _activity_gh(_GRAPHQL_REFUSED, branches=rows)
    result = _fetch(gh, tmp_path, clock=clock)
    assert result == {2110: _epoch(_ISSUE_AT) if readable else None}
    assert gh.unrouted == []


def test_w11_a_cross_repository_closing_link_is_unreadable(tmp_path, clock):
    timeline = [_xref(3001, body="Closes %s#2110" % _SLUG, repo="other/repo")]
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline, pulls={})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}


def test_w11_control_a_bare_number_in_another_repositorys_pr_names_that_repositorys_issue(
    tmp_path, clock,
):
    timeline = [_xref(3001, body="Closes #2110", repo="other/repo")]
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline, pulls={})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}
    assert gh.unrouted == []


def test_a_qualified_keyword_for_another_issue_is_not_a_closing_node(tmp_path, clock):
    timeline = [
        _xref(3001, body="Closes #2111"),
        _xref(3002, body="Closes other/repo#2110"),
        _xref(3003, body=None),
    ]
    gh = _activity_gh(_GRAPHQL_REFUSED, timeline=timeline, pulls={})
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}
    assert gh.unrouted == []


def test_w12_a_branch_carrying_a_longer_number_contributes_nothing(tmp_path, clock):
    rows = _branch_rows() + [{
        "name": "claude/issue-21100-x", "commit": {"sha": "f" * 40},
    }]
    gh = _activity_gh(_GRAPHQL_REFUSED, branches=rows)
    assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_ISSUE_AT)}
    assert gh.unrouted == []


def test_w13_the_budget_spent_mid_rest_is_unreadable_and_never_raises(tmp_path, clock):
    gh = _activity_gh(_GRAPHQL_REFUSED)
    served = gh.routes[_BASE]

    def spend(_argv):
        clock.now = _DEADLINE + 1
        return served

    gh.routes[_BASE] = spend
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}
    assert len(gh.rest_calls()) == 1


@pytest.mark.parametrize("mutate", [
    lambda routes: routes.update({_BASE: (0, json.dumps({"default_branch": ""}), "")}),
    lambda routes: routes.update({_BASE: (0, json.dumps({}), "")}),
    lambda routes: routes.update({
        "%s/branches?%s" % (_BASE, _PAGE % 1): (0, json.dumps([{"name": "x"}]), ""),
    }),
    lambda routes: routes.update({
        "%s/git/commits/%s" % (_BASE, _BRANCH_SHA): (0, json.dumps({"committer": {}}), ""),
    }),
    lambda routes: routes.update({
        "%s/pulls/2113" % _BASE: (0, json.dumps(_pull(2113, updated=None)), ""),
    }),
], ids=["empty-default-branch", "no-default-branch", "branch-without-commit",
        "commit-without-date", "pull-without-updated-at"])
def test_a_missing_or_mistyped_field_is_unreadable(tmp_path, clock, mutate):
    gh = _activity_gh(_GRAPHQL_REFUSED)
    mutate(gh.routes)
    assert _fetch(gh, tmp_path, clock=clock) == {2110: None}
