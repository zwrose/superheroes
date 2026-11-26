"""The wave watch reads a builder note or a terminal comment on a watched lane's own PR as that lane's (#2651).

A comment whose body opens with the builder-note header, or whose first line is a handback, stop or park
header, posted on a pull request GitHub links to exactly one watched lane's issue is treated as if it were
posted on that issue; its entry keeps `issue` as the lane's, gains `pr`, and keeps the PR comment's own url.
The link is one GitHub records, never the pull request's body text: the closing issue references (GraphQL) of a
pull request based on the default branch, or a cross-reference on the lane's issue timeline (REST) for a stack
layer based on another branch. Any other comment on a pull request stays no lane's. When the watch cannot read the
link it says so (builder-note-unavailable), never "no note".

Bites on: the re-key to the one linked lane (rows 1, 2, 6), the disclosure of an unreadable, unresolvable or
ambiguous attribution (rows 5, 7), the comment-kind filter (row 8), the started-at cutoff, the answered record,
the close bookkeeping that must not take an incomplete attribution for a complete read (row 11), and the link
itself: body text names no lane, a GraphQL refusal or failure, a truncated page, a failed pulls or timeline read
is unknown, never "no link".
Residual blind spots: the real GitHub payloads beyond the fields the watch reads; the read budget running out
between two requests of one pull request (the skip is per request in `_read_candidate_prs`, driven here only
between two numbers); and the loop's re-arm across a lane-terminal (covered with the other lane events).
"""
import json
import re
import subprocess
import time

import pytest

import cloud_builder as cb
import launch_ledger as ll
import stack_check as sc
import wave_watch as ww
from test_wave_watch_builder_note import (  # noqa: F401
    _cloud_lane, _comment, _NoteGh, _arm, _note_answered, _BATCH, _NOTE_BODY, _raw,
)
from test_wave_watch_cloud import _FRESH, _QUIET, _SLUG, clock, repo  # noqa: F401
from test_wave_watch_cloud_progress import _progress  # noqa: F401

_CONFIG_DIR = "/home/advisor/.claude-two"
_TIMELINE = re.compile(r"^repos/%s/issues/(\d+)/timeline\?per_page=100&page=(\d+)$" % re.escape(_SLUG))
_PULL = re.compile(r"^repos/%s/pulls/(\d+)$" % re.escape(_SLUG))
_ISSUE = re.compile(r"^repos/%s/issues/(\d+)$" % re.escape(_SLUG))


def _body(kind, text="Done with the work."):
    return cb.terminal_text(kind, text)["comment"]


def _pr(number, body, *, base="main"):
    """The issues-endpoint payload of a pull request: what GitHub serves at `issues/<n>`, its body text included."""
    return {
        "number": number, "body": body, "base_ref": base,
        "pull_request": {"url": "https://api.github.com/repos/%s/pulls/%d" % (_SLUG, number)},
    }


def _refusal_output():
    return " ".join(sc.GRAPHQL_REFUSED_MARKERS)


class _PrGh(_NoteGh):
    """`_NoteGh` that also answers the reads that link a pull request to a lane.

    `prs` is {number: {"base": "main" | "<other branch>", "closes": [issue, ...], and optionally "body": the PR's
    text, "foreign": [issue, ...] closing references in another repository}}. It answers `repos/<slug>` with the
    default branch `main`, `repos/<slug>/pulls/<n>` with the base ref, a `gh api graphql` closing-references query with
    the PR's `closes` (and `foreign`), a timeline list read of an issue with a cross-reference row for each PR
    whose `closes` holds the issue (the lower layer's PR too, as GitHub records it), and `repos/<slug>/issues/<n>` with the PR's body
    text (a read the watch must never make). Every other argv defers to `_NoteGh`.

    Failure switches: `fail_pulls` (numbers whose pulls read exits 1), `pulls_answers` ({number: a CompletedProcess
    served as is, or an exception raised}), `graphql` (None, "exit", "refused", "next_page", "not_json", "errors",
    "raises" for every closing-references read), `graphql_answer` (a CompletedProcess served for every such read),
    `fail_timeline` (True, or the issues whose timeline read exits 1), `timeline_rows` ({issue: extra rows}),
    `repo_default` (the default branch the repository read serves), `graphql_repo` and `timeline_repo` (the
    repository name the answers carry). Every read is recorded by kind in `reads`.
    """

    def __init__(
        self, comments=(), *, prs=None, script=(), fail_pulls=(), pulls_answers=None, graphql=None,
        graphql_answer=None, fail_timeline=(), timeline_rows=None, repo_default="main", graphql_repo=_SLUG,
        timeline_repo=_SLUG,
    ):
        super().__init__(comments, script=script)
        self.prs = dict(prs or {})
        self.fail_pulls = set(fail_pulls)
        self.pulls_answers = dict(pulls_answers or {})
        self.graphql = graphql
        self.graphql_answer = graphql_answer
        self.fail_timeline = fail_timeline
        self.timeline_rows = dict(timeline_rows or {})
        self.repo_default = repo_default
        self.graphql_repo = graphql_repo
        self.timeline_repo = timeline_repo
        self.reads = {"repo": [], "pulls": [], "graphql": [], "timeline": [], "issues": []}

    @property
    def pr_reads(self):
        """The pull requests whose pulls read was made."""
        return self.reads["pulls"]

    def _record(self, argv, kwargs):
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)

    def _graphql(self, argv):
        number = int(next(arg for arg in argv if arg.startswith("number=")).split("=", 1)[1])
        if self.graphql == "raises":
            raise OSError("gh is gone")
        if self.graphql_answer is not None:
            return self.graphql_answer
        if self.graphql == "exit":
            return _raw(argv, "", 1)
        if self.graphql == "refused":
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr=_refusal_output())
        if self.graphql == "not_json":
            return _raw(argv, "<html>not json</html>")
        if self.graphql == "errors":
            return _raw(argv, json.dumps({"errors": [{"message": "boom"}], "data": None}))
        pr = self.prs.get(number, {})
        nodes = [{"number": i, "repository": {"nameWithOwner": self.graphql_repo}} for i in pr.get("closes", [])]
        nodes += [{"number": i, "repository": {"nameWithOwner": "other/repo"}} for i in pr.get("foreign", [])]
        refs = {"pageInfo": {"hasNextPage": self.graphql == "next_page"}, "nodes": nodes}
        return _raw(argv, json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": refs}}}}))

    def _timeline(self, issue):
        rows = [{"event": "labeled", "label": {"name": "x"}}]
        for number, pr in self.prs.items():
            if issue in pr.get("closes", []):
                rows.append({
                    "event": "cross-referenced",
                    "source": {"type": "issue", "issue": {
                        "number": number, "pull_request": {"url": "u"},
                        "repository": {"full_name": self.timeline_repo},
                    }},
                })
        return rows + list(self.timeline_rows.get(issue, []))

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        if argv[:3] == ["gh", "api", "graphql"] and any("closingIssuesReferences" in arg for arg in argv):
            self._record(argv, kwargs)
            self.reads["graphql"].append(int(next(a for a in argv if a.startswith("number=")).split("=", 1)[1]))
            return self._graphql(argv)
        if len(argv) == 3 and argv[:2] == ["gh", "api"]:
            path = argv[2]
            if path == "repos/%s" % _SLUG:
                self._record(argv, kwargs)
                self.reads["repo"].append(path)
                return _raw(argv, json.dumps({"default_branch": self.repo_default}))
            match = _PULL.match(path)
            if match:
                number = int(match.group(1))
                self._record(argv, kwargs)
                self.reads["pulls"].append(number)
                answer = self.pulls_answers.get(number)
                if isinstance(answer, BaseException):
                    raise answer
                if answer is not None:
                    return answer
                if number in self.fail_pulls or number not in self.prs:
                    return _raw(argv, "gh: Not Found (HTTP 404)", 1)
                return _raw(argv, json.dumps({"number": number, "base": {"ref": self.prs[number].get("base", "main")}}))
            match = _TIMELINE.match(path)
            if match:
                issue, page = int(match.group(1)), int(match.group(2))
                self._record(argv, kwargs)
                if page == 1:
                    self.reads["timeline"].append(issue)
                if self.fail_timeline is True or issue in self.fail_timeline:
                    return _raw(argv, "gh: Not Found (HTTP 404)", 1)
                return _raw(argv, json.dumps(self._timeline(issue) if page == 1 else []))
            match = _ISSUE.match(path)
            if match and int(match.group(1)) in self.prs:
                number = int(match.group(1))
                self._record(argv, kwargs)
                self.reads["issues"].append(number)
                return _raw(argv, json.dumps(_pr(number, self.prs[number].get("body", ""))))
        return super().__call__(argv, **kwargs)


def _on_main(*closes, **extra):
    """A pull request based on the default branch that GitHub links to `closes`."""
    return {"base": "main", "closes": list(closes), **extra}


def _stacked(*closes, **extra):
    """A stack layer: based on another branch, cross-referenced from each of `closes`' timelines."""
    return {"base": "layer-branch", "closes": list(closes), **extra}


def _as_pr(comment):
    """The comment as GitHub serves one on a pull request: its html_url is the PR's `/pull/<n>` page, while its
    issue_url still ends `/issues/<n>`."""
    number = int(comment["issue_url"].rsplit("/", 1)[1])
    return dict(comment, html_url="https://github.com/%s/pull/%d#issuecomment-%d" % (_SLUG, number, comment["id"]))


def _pr_comment(comment_id, pr, body=_NOTE_BODY, *, age=_FRESH):
    return _as_pr(_comment(comment_id, pr, body, age=age))


def _only_launch(result):
    assert result["event"] == ww.EVENT_LANE_TERMINAL, result
    [launch] = result["launches"]
    return launch


def _lanes(specs, **extra):
    """Watched started cloud lanes by launch id; each spec is (issue, seconds since start)."""
    now = time.time()
    return {
        lid: {
            "place": ll.PLACE_CLOUD, "started": True, "issue": issue,
            "reservedTs": now - age - 1, "startedTs": now - age,
            "cloudSessionName": "cloud-%d" % issue, "cloudSessionId": "session_%d" % issue,
            "configDir": _CONFIG_DIR, **extra,
        }
        for lid, (issue, age) in specs.items()
    }


def _evaluate(lanes, gh, **kwargs):
    degraded = kwargs.setdefault("degraded", set())
    result = ww._evaluate_cloud_comments(
        "/", lanes, deadline=100.0, env={}, gh_run=gh, monotonic=lambda: 0.0,
        note_state=[None], known_slug=_SLUG, **kwargs,
    )
    return result, degraded


# --- row 1, 2: a handback or a builder note on the lane's own PR is the lane's ---------------


@pytest.mark.parametrize("kind, state", [("handback", "handback"), ("stop", "stopped"), ("park", "parked")])
def test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane(repo, kind, state):
    # axis: every terminal kind (handback, stop, park) on the lane's own PR is the lane's ending
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body(kind))], prs={501: _on_main(101)})
    launch = _only_launch(_arm(repo, gh))
    assert launch["launchId"] == "cloud-a"
    assert launch["kind"] == kind
    assert launch["state"] == state
    assert launch["issue"] == 101
    assert launch["pr"] == 501
    assert launch["commentId"] == 7
    assert launch["url"].endswith("/pull/501#issuecomment-7")
    assert gh.pr_reads == [501]
    assert gh.reads["graphql"] == [501]
    assert gh.reads["issues"] == []


def test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501)], prs={501: _on_main(101)})
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert result["launchId"] == "cloud-a"
    [note] = result["notes"]
    assert note["issue"] == 101
    assert note["pr"] == 501
    assert note["commentId"] == 7
    assert note["url"].endswith("/pull/501#issuecomment-7")


def test_an_issue_comment_entry_carries_no_pr_key(repo):
    _cloud_lane(repo, "cloud-a", 101)
    launch = _only_launch(_arm(repo, _PrGh([_comment(7, 101, _body("handback"))])))
    assert "pr" not in launch


# --- row 3, 9: a PR no watched lane opened, and a plain issue, are no lane's -----------------


def test_row3_a_handback_on_a_pr_linked_only_to_an_unwatched_issue_is_no_lanes(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(999)})
    # One tick: a multi-tick arm reports builder-note-unavailable on its last tick for want of budget, with or without a PR.
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert "unreadIssues" not in result
    assert gh.pr_reads == [501]


def test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure(repo):
    _cloud_lane(repo, "cloud-a", 101)
    # A plain issue's comment has an `/issues/` html_url; reading 777 would fail here, so a read would be disclosed.
    gh = _PrGh([_comment(7, 777, _body("handback"))], prs={777: _on_main(101)}, fail_pulls={777})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert "unreadIssues" not in result
    assert gh.pr_reads == []
    assert not [argv for argv in gh.calls if argv[-1:] == ["repos/%s/pulls/777" % _SLUG]]


def test_a_pr_comment_whose_page_number_differs_from_its_issue_number_is_no_candidate(repo):
    _cloud_lane(repo, "cloud-a", 101)
    odd = dict(
        _pr_comment(7, 501, _body("handback")),
        html_url="https://github.com/%s/pull/502#issuecomment-7" % _SLUG,
    )
    gh = _PrGh([odd], prs={501: _on_main(101), 502: _on_main(101)})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert gh.pr_reads == []
    assert ww._pr_candidate(odd, {101}, 0.0) is None


@pytest.mark.parametrize("html_url", [
    "https://example.com/%s/pull/501#issuecomment-7" % _SLUG,
    "https://github.com/%s/pull/501#issuecomment-0" % _SLUG,
    "https://github.com/%s/pull/501#issuecomment-7/x" % _SLUG,
])
def test_a_pr_comment_whose_permalink_is_not_a_github_pr_comment_is_no_candidate(html_url):
    # axis: the watch reads the html_url with the builder's own permalink parser, whole string, never a suffix
    odd = dict(_pr_comment(7, 501, _body("handback")), html_url=html_url)
    assert ww._pr_candidate(odd, {101}, 0.0) is None


# --- row 4: the started-at cutoff applies to the PR's comment ---------------------------------


def test_row4_a_handback_on_the_lanes_pr_from_before_the_lane_started_is_not_reported(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=600, reserve_lead=100)
    gh = _PrGh(
        [_pr_comment(7, 501, _body("handback"), age=3000)], prs={501: _on_main(101)},
    )
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER
    assert gh.pr_reads == []


# --- row 5: an unreadable PR is disclosed, never "no note" -------------------------------------


def _assert_disclosed_unread(result, gh=None):
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


def test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, fail_pulls={501})
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))
    assert gh.pr_reads == [501]
    assert gh.reads["graphql"] == []


def test_a_pr_read_that_raises_is_disclosed_too(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh(
        [_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, pulls_answers={501: OSError("gh is gone")},
    )
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))


def test_a_pr_payload_that_is_not_json_is_disclosed(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh(
        [_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)},
        pulls_answers={501: _raw([], "<html>not json</html>")},
    )
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))


@pytest.mark.parametrize("payload", [{"number": 501}, {"number": 501, "base": {"ref": ""}}, {"number": 501, "base": {"ref": 5}}])
def test_a_pr_payload_with_no_base_branch_is_disclosed(repo, payload):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh(
        [_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)},
        pulls_answers={501: _raw([], json.dumps(payload))},
    )
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))


# --- the link is GitHub's, never the body text, and an unreadable link is disclosed ------------------


def test_a_pr_whose_body_says_closes_but_whose_github_links_are_empty_names_no_lane(repo):
    # axis: a default-branch PR belongs to a lane only through the closing issue references GitHub records, never through its body text
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(body="Closes #101.\n\nThe work.")})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert "unreadIssues" not in result
    assert gh.reads["graphql"] == [501]
    assert gh.reads["issues"] == []


def test_a_stack_layer_whose_body_says_closes_but_has_no_cross_reference_names_no_lane(repo):
    # axis: a stack layer belongs to a lane only through a cross-reference on the lane's issue timeline, never through its body text
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _stacked(body="Closes #101.")})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert gh.reads["timeline"] == [101]
    assert gh.reads["issues"] == []


def test_a_pr_whose_body_says_nothing_but_whose_closing_references_hold_101_is_lane_101s(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101, body="The work.")})
    launch = _only_launch(ww.run(repo, _BATCH, gh_run=gh))
    assert launch["launchId"] == "cloud-a"
    assert launch["pr"] == 501


def test_a_closing_reference_in_another_repository_names_no_lane(repo):
    # axis: only a same-repository closing reference names a lane
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(foreign=[101])})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]


def test_the_repository_name_in_a_closing_reference_matches_without_regard_to_case(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, graphql_repo="OWNER/Repo")
    assert _only_launch(ww.run(repo, _BATCH, gh_run=gh))["pr"] == 501


@pytest.mark.parametrize("failure", ["refused", "exit", "next_page", "not_json", "errors", "raises"])
def test_an_unreadable_closing_reference_read_is_disclosed_never_no_link(repo, failure):
    # axis: a closing-references read that fails, is refused by the proxy, or is truncated or malformed is unknown, never "no link"
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, graphql=failure)
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))
    assert gh.reads["graphql"] == [501]
    assert gh.reads["timeline"] == []


def test_a_graphql_proxy_refusal_falls_back_to_nothing_else(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, graphql="refused")
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))
    assert gh.reads["timeline"] == []
    assert gh.reads["issues"] == []
    assert not [argv for argv in gh.calls if argv[:3] == ["gh", "pr", "view"]]


def test_a_failed_timeline_read_is_disclosed_never_no_link(repo):
    # axis: a timeline read that fails is unknown, never "no link"
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh(
        [_pr_comment(7, 501, _body("handback"))], prs={501: _stacked(101)}, fail_timeline=True,
    )
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))
    assert gh.reads["timeline"] == [101]


def test_a_failed_timeline_read_of_one_of_two_lanes_is_disclosed_for_both(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _cloud_lane(repo, "cloud-b", 102)
    gh = _PrGh(
        [_pr_comment(7, 502, _body("handback"))], prs={502: _stacked(102)}, fail_timeline={101},
    )
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [
        {"launchId": "cloud-a", "issue": 101}, {"launchId": "cloud-b", "issue": 102},
    ]


# --- row 6: a stack layer's PR targets the layer below and is still its own lane's ----------


def test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only(repo):
    _cloud_lane(repo, "cloud-lower", 101)
    _cloud_lane(repo, "cloud-upper", 102)
    # The lower layer's own pull request (501) is cross-referenced on 101's timeline; the upper layer's (502) only on 102's.
    gh = _PrGh(
        [_pr_comment(7, 502, _body("handback"))],
        prs={501: _on_main(101), 502: _stacked(102, body="Closes #101")},
    )
    result = _arm(repo, gh)
    launch = _only_launch(result)
    assert launch["launchId"] == "cloud-upper"
    assert launch["issue"] == 102
    assert launch["pr"] == 502
    assert gh.reads["graphql"] == []
    assert gh.reads["timeline"] == [101, 102]


@pytest.mark.parametrize("row", [
    {"event": "cross-referenced", "source": {"issue": {
        "number": 502, "pull_request": {"url": "u"}, "repository": {"full_name": "other/repo"}}}},
    {"event": "cross-referenced", "source": {"issue": {
        "number": 504, "pull_request": {"url": "u"}, "repository": {"full_name": _SLUG}}}},
    {"event": "cross-referenced", "source": {"issue": {
        "number": 502, "repository": {"full_name": _SLUG}}}},
    {"event": "referenced", "source": {"issue": {
        "number": 502, "pull_request": {"url": "u"}, "repository": {"full_name": _SLUG}}}},
])
def test_a_cross_reference_from_another_pull_request_repository_or_event_is_no_link(repo, row):
    # axis: only a cross-reference whose source is this pull request, of this repository, links a stack layer to a lane
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 502, _body("handback"))], prs={502: _stacked()}, timeline_rows={101: [row]})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]


def test_the_repository_name_in_a_cross_reference_matches_without_regard_to_case(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 502, _body("handback"))], prs={502: _stacked(101)}, timeline_repo="Owner/REPO")
    assert _only_launch(ww.run(repo, _BATCH, gh_run=gh))["pr"] == 502


@pytest.mark.parametrize("row", [
    "not a dict",
    {"event": "cross-referenced", "source": {"issue": "x"}},
    {"event": "cross-referenced", "source": {"issue": {"pull_request": {}, "number": "502", "repository": {"full_name": _SLUG}}}},
    {"event": "cross-referenced", "source": {"issue": {"pull_request": {}, "number": 502}}},
])
def test_a_malformed_timeline_row_is_disclosed_never_no_link(repo, row):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 502, _body("handback"))], prs={502: _stacked()}, timeline_rows={101: [row]})
    _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))


# --- row 7: a PR linked to two watched lanes' issues is no lane's, and is disclosed -------


def test_row7_a_pr_linked_to_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _cloud_lane(repo, "cloud-b", 102)
    gh = _PrGh([_pr_comment(7, 503, _body("handback"))], prs={503: _on_main(101, 102)})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [
        {"launchId": "cloud-a", "issue": 101}, {"launchId": "cloud-b", "issue": 102},
    ]


# --- row 8: only a note or an ending moves to the PR's lane ------------------------------------


def test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress():
    lanes = _lanes({"cloud-a": (101, 600)})
    gh = _PrGh([_as_pr(_progress(9, 501, updated_age=100))], prs={501: _on_main(101)})
    progress_out = [None]
    _evaluate(lanes, gh, progress_out=progress_out)
    assert progress_out[0] == {}
    assert gh.pr_reads == []


def test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [
        _comment(5, 101, _body("stop"), age=200),
        _pr_comment(6, 501, cb.handover_text("a" * 40), age=100),
    ]
    gh = _PrGh(comments, prs={501: _on_main(101)})
    launch = _only_launch(_arm(repo, gh))
    assert launch["state"] == "stopped"
    assert launch["commentId"] == 5
    assert "pr" not in launch


@pytest.mark.parametrize("body", [
    "Builder stop at intake. The Anchor did not resolve.",
    "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
    cb.REFUSAL_HEADER + "\n\nNo.",
])
def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, body)], prs={501: _on_main(101)})
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
    assert gh.pr_reads == []


# --- row 10: no candidate, no request ----------------------------------------------------------


def test_row10_a_tick_with_no_pr_comment_makes_no_pr_read(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh(
        [_comment(7, 101, _body("handback")), _comment(8, 101, _NOTE_BODY)],
        prs={501: _on_main(101)},
    )
    _only_launch(ww.run(repo, _BATCH, gh_run=gh))
    assert gh.reads == {"repo": [], "pulls": [], "graphql": [], "timeline": [], "issues": []}
    assert [argv for argv in gh.calls if argv[:2] == ["gh", "api"] and "/issues/" in argv[-1]
            and "comments" not in argv[-1]] == []


# --- row 11: an incomplete attribution is not a complete read for the closes ------------------


def _reopened_lane_and_comments(*, reopened_ago=500):
    lanes = _lanes({"cloud-a": (101, 700)}, reopenedAt=time.time() - reopened_ago)
    comments = [
        _comment(7, 101, _body("handback"), age=100),
        _pr_comment(8, 501, _body("handback"), age=50),
    ]
    return lanes, comments


def test_row11_an_unresolved_pr_comment_stores_nothing_new_for_its_lane():
    # axis: a lane an unattributed PR comment may belong to is a partial read: the issue handback it shows is not stored as its close
    lanes, comments = _reopened_lane_and_comments()
    gh = _PrGh(comments, prs={501: _on_main(101)}, fail_pulls={501})
    closed_out, unread_out = [None], {}
    _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert closed_out[0] == {}
    assert unread_out == {"cloud-a": 101}


def test_row11_a_refused_graphql_read_stores_nothing_new_for_its_lane():
    lanes, comments = _reopened_lane_and_comments()
    gh = _PrGh(comments, prs={501: _on_main(101)}, graphql="refused")
    closed_out, unread_out = [None], {}
    _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert closed_out[0] == {}
    assert unread_out == {"cloud-a": 101}


def test_row11_control_a_resolved_pr_comment_sets_the_closed_slot():
    lanes, comments = _reopened_lane_and_comments()
    gh = _PrGh(comments, prs={501: _on_main(101)})
    closed_out, unread_out = [None], {}
    _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert closed_out[0] is not None and set(closed_out[0]) == {"cloud-a"}
    assert unread_out == {}


def test_row11_an_unresolved_pr_comment_keeps_the_known_closes():
    lanes, comments = _reopened_lane_and_comments()
    known = {"cloud-a": ((time.time() - 300, 7), "handback")}
    gh = _PrGh(comments, prs={501: _on_main(101)}, fail_pulls={501})
    closed_out = [None]
    (notes, terminals), degraded = _evaluate(lanes, gh, known_closes=dict(known), closed_out=closed_out)
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert terminals == []  # the cached close, not this read's first ending, bounds the window
    assert closed_out[0] == known  # the unsure lane keeps its cached close in the slot the complete read sets


def test_row11_with_no_stored_close_an_unsure_lane_has_no_bound_and_says_so():
    # The ruled cost of the narrow degraded case: with no stored close, a note after an issue handback can surface on
    # a tick whose PR attribution is partial; the tick is disclosed and the lane named, never silent.
    lanes, comments = _reopened_lane_and_comments()
    comments = comments + [_comment(9, 101, _NOTE_BODY, age=60)]
    gh = _PrGh(comments, prs={501: _on_main(101)}, fail_pulls={501})
    closed_out, unread_out = [None], {}
    (notes, terminals), degraded = _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert unread_out == {"cloud-a": 101}
    assert [note["commentId"] for note in notes] == [9]
    assert closed_out[0] == {}


def test_row11_an_observed_park_is_not_a_close_while_a_pr_note_after_it_is_unread():
    # axis: an unsure lane with no stored close has no bound on a partial attribution, so the park the unread PR note may supersede does not hide the later issue stop
    lanes = _lanes({"cloud-a": (101, 700)}, reopenedAt=time.time() - 500)
    comments = [
        _comment(7, 101, _body("park"), age=300),
        _pr_comment(8, 501, _NOTE_BODY, age=250),
        _comment(9, 101, _body("stop"), age=200),
    ]
    gh = _PrGh(comments, prs={501: _on_main(101)}, fail_pulls={501})
    closed_out = [None]
    (notes, terminals), degraded = _evaluate(lanes, gh, closed_out=closed_out)
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert [(t["commentId"], t["kind"]) for t in terminals] == [(9, "stop")]
    assert closed_out[0] == {}  # nothing new stored for the unsure lane


def test_row11_a_stored_close_wins_over_a_park_a_partial_read_observes():
    # axis: an unsure lane's stored close (a complete read's) is its bound, never an earlier park this partial read cannot judge
    lanes = _lanes({"cloud-a": (101, 700)}, reopenedAt=time.time() - 500)
    comments = [
        _comment(7, 101, _body("park"), age=300),
        _pr_comment(8, 501, _NOTE_BODY, age=250),
        _comment(9, 101, _body("stop"), age=200),
    ]
    stop_key = (ww._parse_activity_time(comments[2]["created_at"]), 9)
    known = {"cloud-a": (stop_key, "stop")}
    gh = _PrGh(comments, prs={501: _on_main(101)}, fail_pulls={501})
    closed_out = [None]
    (notes, terminals), degraded = _evaluate(lanes, gh, closed_out=closed_out, known_closes=dict(known))
    assert [(t["commentId"], t["kind"]) for t in terminals] == [(9, "stop")]
    assert closed_out[0] == known


def test_a_failed_comments_read_with_a_stored_park_and_no_pr_candidate_is_a_normal_degraded_result(repo):
    # axis: a comments read that fails with a stored park and no pull-request candidate returns the degraded result, never internal-error
    import test_wave_watch_fix_order as fo

    fo._reopened(repo)
    assert _note_answered(repo, 5)["ok"] is True
    park = fo._later(5, fo._ending("park"), secs=10)
    gh = _NoteGh([park], script=[
        lambda argv: fo._ok(argv, [park]),  # tick 0: complete, the park is stored as the close
        lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n"),  # tick 1: page one fails
        lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n"),
    ])
    result = ww.watch_arm(repo, _BATCH, max_seconds=2, interval_seconds=1, gh_run=gh)
    assert result["ok"] is True, result
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


def _reopened(issue, reopened_ago):
    now = time.time()
    return {
        "place": ll.PLACE_CLOUD, "started": True, "issue": issue, "reservedTs": now - 701, "startedTs": now - 700,
        "reopenedAt": now - reopened_ago, "cloudSessionName": "cloud-%d" % issue,
        "cloudSessionId": "session_%d" % issue, "configDir": _CONFIG_DIR,
    }


def test_row11_an_unresolved_pr_comment_keeps_the_observed_close_of_a_lane_it_cannot_be():
    # axis: a partial pull-request attribution is partial for the lanes it could be only, so another lane's close the complete issue read observed stands
    lanes = {"cloud-a": _reopened(101, 30), "cloud-b": _reopened(102, 500)}
    comments = [_comment(7, 101, _body("handback"), age=10), _pr_comment(8, 502, _body("handback"), age=50)]
    gh = _PrGh(comments, prs={502: _on_main(102)}, fail_pulls={502})
    closed_out, unread_out = [None], {}
    (notes, terminals), degraded = _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert unread_out == {"cloud-b": 102}  # the PR comment (50s old) is from before cloud-a's fix order (30s ago)
    assert set(closed_out[0]) == {"cloud-a"}
    assert closed_out[0]["cloud-a"][0][1] == 7
    assert [t["launchId"] for t in terminals] == ["cloud-a"]


# --- a reopened lane's window bounds its pull-request comments --------------------------------


def test_a_pr_comment_from_before_every_lanes_fix_order_causes_no_read_and_no_disclosure():
    # axis: the candidate cutoff is the lane's window (its fix order), never the original attempt's start
    lanes = {"cloud-a": _reopened(101, 300)}
    gh = _PrGh([_pr_comment(8, 501, _body("handback"), age=500)], prs={501: _on_main(101)}, fail_pulls={501})
    unread_out = {}
    (notes, terminals), degraded = _evaluate(lanes, gh, unread_out=unread_out)
    assert gh.pr_reads == []
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in degraded
    assert unread_out == {}
    assert terminals == []


def test_a_lane_read_only_from_its_own_issue_does_not_open_the_pr_cutoff(repo):
    # axis: the candidate cutoff is taken over the lanes that can take a PR comment, never an old resumed lane read only from its own issue
    from test_wave_watch_lookback_2333 import _ScopedGh, _dormant

    _dormant(repo, "cloud-old", 301)
    _cloud_lane(repo, "cloud-a", 101, start_age=200, reserve_lead=1)
    # Created after the old lane's basis (2 days ago) but before cloud-a began (200 s ago), and edited since, so the
    # shared read (which filters by update time) returns it; reading PR 501 fails here, so a read would be disclosed.
    edited = dict(_pr_comment(7, 501, _body("handback"), age=600), updated_at=_pr_comment(9, 501, age=10)["created_at"])
    scoped = _ScopedGh([edited])
    links = _PrGh(prs={501: _on_main(101)}, fail_pulls={501})

    def gh_run(argv, **kwargs):
        argv = list(argv)
        if argv[:3] == ["gh", "api", "graphql"] or (len(argv) == 3 and argv[:2] == ["gh", "api"] and (
                argv[2] == "repos/%s" % _SLUG or _PULL.match(argv[2]))):
            return links(argv, **kwargs)
        return scoped(argv, **kwargs)

    result = ww.run(repo, _BATCH, gh_run=gh_run)
    assert links.pr_reads == []
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert "unreadIssues" not in result


def test_a_pr_comment_from_before_its_lanes_fix_order_is_not_the_lanes():
    # axis: attribution re-keys a PR comment only to a lane whose window it is in
    lanes = {"cloud-a": _reopened(101, 100), "cloud-b": dict(_lanes({"cloud-b": (102, 700)})["cloud-b"])}
    comment = _pr_comment(8, 501, _body("handback"), age=300)
    out, uncertain = ww._attribute_pr_comments([comment], lanes, {501: (101,)}, 0.0)
    assert uncertain == set()
    assert out == [comment]


def test_an_ambiguous_pr_comment_is_unsure_only_for_linked_lanes_whose_window_it_is_in():
    # axis: the ambiguity disclosure keeps each linked lane's window: a lane whose fix order came after the comment is not named
    base = _lanes({"cloud-b": (102, 700), "cloud-c": (103, 700)})
    lanes = {"cloud-a": _reopened(101, 100), **base}
    comment = _pr_comment(8, 501, _body("handback"), age=300)
    out, uncertain = ww._attribute_pr_comments([comment], lanes, {501: (101, 102)}, 0.0)
    assert uncertain == {"cloud-b"}
    assert out == [comment]
    lanes["cloud-b"] = _reopened(102, 100)
    assert ww._attribute_pr_comments([comment], lanes, {501: (101, 102)}, 0.0)[1] == set()


def test_an_unread_pr_comment_is_unsure_only_for_lanes_whose_window_it_is_in():
    lanes = {"cloud-a": _reopened(101, 100), "cloud-b": dict(_lanes({"cloud-b": (102, 700)})["cloud-b"])}
    comment = _pr_comment(8, 501, _body("handback"), age=300)
    out, uncertain = ww._attribute_pr_comments([comment], lanes, {501: None}, 0.0)
    assert uncertain == {"cloud-b"}
    assert out == [comment]


# --- row 12: the answered record stops a PR comment surfacing ---------------------------------


def test_row12_an_answered_pr_handback_no_longer_surfaces(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [_pr_comment(7, 501, _body("handback"))]
    prs = {501: _on_main(101)}
    assert _only_launch(_arm(repo, _PrGh(comments, prs=prs)))["commentId"] == 7
    assert _note_answered(repo, 7)["ok"] is True
    assert _arm(repo, _PrGh(comments, prs=prs))["event"] == ww.EVENT_TIMER


# --- two copies of an ending ---------------------------------------------------------------------


def test_an_ending_on_both_the_issue_and_the_pr_is_two_endings_and_each_is_answered(repo):
    # axis: nothing pairs: both copies are the lane's endings, the newer fires, and answering it leaves no older one in its place
    _cloud_lane(repo, "cloud-a", 101)
    pr_copy = _pr_comment(7, 501, _body("handback"), age=200)
    issue_body = cb.terminal_text("handback", "Done with the work.", also_on=pr_copy["html_url"])["comment"]
    comments = [pr_copy, _comment(8, 101, issue_body, age=100)]
    prs = {501: _on_main(101)}
    assert _only_launch(ww.run(repo, _BATCH, gh_run=_PrGh(comments, prs=prs)))["commentId"] == 8
    assert _note_answered(repo, 8)["ok"] is True
    assert ww.run(repo, _BATCH, gh_run=_PrGh(comments, prs=prs))["event"] == ww.EVENT_TIMER


def test_a_pointer_line_in_any_issue_comment_hides_nothing_on_the_pr(repo):
    # axis: no comment pairs or hides another: a PR note stays the lane's note whatever an issue comment names
    _cloud_lane(repo, "cloud-a", 101)
    pr_note = _pr_comment(7, 501, _NOTE_BODY, age=200)
    pasted = "Looking at this:\n\n%s%s" % (cb.ALSO_ON_LINE, pr_note["html_url"])
    gh = _PrGh([pr_note, _comment(8, 101, pasted, age=100)], prs={501: _on_main(101)})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert [note["commentId"] for note in result["notes"]] == [7]


def test_a_pr_linked_to_a_live_issue_and_an_old_resumed_issue_stays_ambiguous():
    # axis: ambiguity is counted over every watched issue before an issue-only lane is excluded
    lanes = _lanes({"cloud-a": (101, 700), "cloud-b": (102, 700)})
    out, uncertain = ww._attribute_pr_comments(
        [_pr_comment(7, 501, _body("handback"))], lanes, {501: (101, 102)}, 0.0, issue_only=frozenset({101}))
    assert uncertain == {"cloud-b"}  # no lane is named; the disclosure names the live lane only
    assert "prNumber" not in out[0]


def test_a_pr_linked_to_an_issue_only_lane_is_not_rekeyed_but_one_linked_to_a_live_lane_is():
    # axis: a resumed lane read only from its own issue never takes a pull-request comment
    lanes = _lanes({"cloud-a": (101, 700), "cloud-b": (102, 700)})
    comments = [_pr_comment(7, 501, _body("handback")), _pr_comment(8, 502, _body("handback"))]
    out, uncertain = ww._attribute_pr_comments(
        comments, lanes, {501: (101,), 502: (102,)}, 0.0, issue_only=frozenset({101}))
    assert uncertain == set()
    assert "prNumber" not in out[0] and out[0]["issue_url"] == comments[0]["issue_url"]
    assert out[1]["prNumber"] == 502 and out[1]["issue_url"].endswith("/issues/102")


def test_the_attributed_kinds_follow_the_builders_header_map(monkeypatch):
    # axis: a kind added to cloud_builder.TERMINAL_HEADERS is attributed through a PR with no second list to edit
    header = "Builder pause (cloud build)."
    monkeypatch.setitem(cb.TERMINAL_HEADERS, "pause", header)
    paused = _pr_comment(7, 501, header + "\n\nPaused.")
    assert ww._pr_candidate(paused, {101}, 0.0) == 501


@pytest.mark.parametrize("html_url", [
    "https://github.com/%s/pull/501#issuecomment-8" % _SLUG,
    "https://github.com/other/repo/pull/501#issuecomment-7",
])
def test_a_permalink_naming_another_comment_or_repository_is_no_candidate(html_url):
    # axis: the permalink must name this comment: its own id and the repository its issue_url names
    odd = dict(_pr_comment(7, 501, _body("handback")), html_url=html_url)
    assert ww._pr_candidate(odd, {101}, 0.0) is None


def test_an_oversized_permalink_number_is_no_permalink():
    # axis: a number past the digit limit reads as no permalink, never an exception
    huge = "9" * 5000
    assert cb.comment_permalink("https://github.com/acme/widgets/pull/%s#issuecomment-1" % huge) is None
    bad = dict(_pr_comment(7, 501, _body("handback")), html_url="https://github.com/%s/pull/501#issuecomment-%s"
               % (_SLUG, huge))
    assert ww._pr_candidate(bad, {101}, 0.0) is None


# --- units ---------------------------------------------------------------------------------------


def test_a_malformed_element_is_skipped_and_the_rest_still_count(repo):
    _cloud_lane(repo, "cloud-a", 101)
    good = _body("handback")
    broken = [
        "not a dict",
        {**_pr_comment(1, 501, good), "id": "1"},
        {**_pr_comment(2, 501, good), "id": True},
        {k: v for k, v in _pr_comment(3, 501, good).items() if k != "issue_url"},
        {**_pr_comment(4, 501, good), "created_at": "yesterday"},
        {**_pr_comment(5, 501, good), "body": None},
        {**_pr_comment(6, 501, good), "issue_url": "https://api.github.com/repos/owner/repo/pulls/501"},
        {k: v for k, v in _pr_comment(9, 501, good).items() if k != "html_url"},
        {**_pr_comment(10, 501, good), "html_url": 501},
    ]
    gh = _PrGh(broken + [_pr_comment(8, 501, good)], prs={501: _on_main(101)})
    assert _only_launch(_arm(repo, gh))["commentId"] == 8


def test_pr_candidate_never_raises_on_a_malformed_comment():
    for comment in (None, 5, [], {}, {"id": 1}, {"id": 1, "body": 3, "issue_url": "x", "created_at": 1}):
        assert ww._pr_candidate(comment, {101}, 0.0) is None


def test_attribution_never_mutates_the_comments_it_is_given():
    lanes = _lanes({"cloud-a": (101, 600)})
    comment = _pr_comment(7, 501, _body("handback"))
    before = dict(comment)
    comments = [comment]
    out, uncertain = ww._attribute_pr_comments(comments, lanes, {501: (101,)}, 0.0)
    assert uncertain == set()
    assert comment == before and comments == [comment]
    assert out[0] is not comment
    assert out[0]["issue_url"].endswith("/issues/101") and out[0]["prNumber"] == 501
    assert out[0]["html_url"] == comment["html_url"]


def test_a_pr_read_skipped_for_budget_is_unresolved_for_it_and_every_later_number():
    gh = _PrGh(prs={501: _on_main(101), 502: _on_main(102), 503: _on_main(103)})
    # Budget left until the first pull request's closing references are asked for, spent from then on.
    resolved = ww._read_candidate_prs(
        [503, 501, 502], _SLUG, {101, 102, 103}, "/", 10.0, lambda: 10.0 if gh.reads["graphql"] else 0.0, gh, {},
    )
    assert resolved == {501: (101,), 502: None, 503: None}
    assert gh.pr_reads == [501]
    assert gh.reads["repo"] == ["repos/%s" % _SLUG]


def test_a_spent_budget_reads_nothing():
    gh = _PrGh(prs={501: _on_main(101)})
    assert ww._read_candidate_prs([501], _SLUG, {101}, "/", 10.0, lambda: 10.0, gh, {}) == {501: None}
    assert gh.calls == []


def test_the_default_branch_is_read_once_and_each_pull_request_is_read_in_sorted_order():
    gh = _PrGh(prs={501: _on_main(101), 502: _stacked(102), 503: _on_main(102)})
    resolved = ww._read_candidate_prs([503, 501, 502], _SLUG, {101, 102}, "/", 100.0, lambda: 0.0, gh, {})
    assert resolved == {501: (101,), 502: (102,), 503: (102,)}
    assert gh.reads["repo"] == ["repos/%s" % _SLUG]
    assert gh.reads["pulls"] == [501, 502, 503]
    assert gh.reads["graphql"] == [501, 503]
    assert gh.reads["timeline"] == [101, 102]


@pytest.mark.parametrize("repo_default", ["", None, 5])
def test_an_unreadable_default_branch_makes_every_number_unknown(repo_default):
    gh = _PrGh(prs={501: _on_main(101), 502: _on_main(101)}, repo_default=repo_default)
    resolved = ww._read_candidate_prs([501, 502], _SLUG, {101}, "/", 100.0, lambda: 0.0, gh, {})
    assert resolved == {501: None, 502: None}
    assert gh.reads["repo"] == ["repos/%s" % _SLUG]
    assert gh.reads["pulls"] == []


@pytest.mark.parametrize("stdout", [
    "[]",
    json.dumps({"data": None}),
    json.dumps({"data": {"repository": None}}),
    json.dumps({"data": {"repository": {"pullRequest": None}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": None}}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": {"nodes": []}}}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
        "pageInfo": {"hasNextPage": None}, "nodes": []}}}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
        "pageInfo": {"hasNextPage": False}, "nodes": [{"number": "101", "repository": {"nameWithOwner": _SLUG}}]}}}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
        "pageInfo": {"hasNextPage": False}, "nodes": [{"number": 101, "repository": {"nameWithOwner": 5}}]}}}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
        "pageInfo": {"hasNextPage": False}, "nodes": [{"number": 101}]}}}}}),
    json.dumps({"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
        "pageInfo": {"hasNextPage": False}, "nodes": ["x"]}}}}}),
])
def test_a_malformed_closing_references_answer_is_unknown(stdout):
    gh = _PrGh(prs={501: _on_main(101)}, graphql_answer=_raw([], stdout))
    assert ww._read_candidate_prs([501], _SLUG, {101}, "/", 100.0, lambda: 0.0, gh, {}) == {501: None}


def test_a_pull_request_is_routed_by_the_repositorys_own_default_branch():
    # axis: the base branch is compared with the default branch the repository read serves, never a hard-coded name
    gh = _PrGh(
        prs={501: {"base": "trunk", "closes": [101]}, 502: {"base": "main", "closes": [102]}}, repo_default="trunk",
    )
    resolved = ww._read_candidate_prs([501, 502], _SLUG, {101, 102}, "/", 100.0, lambda: 0.0, gh, {})
    assert resolved == {501: (101,), 502: (102,)}
    assert gh.reads["graphql"] == [501]  # based on the default branch `trunk`: closing references
    assert gh.reads["timeline"] == [101, 102]  # based on `main`, not the default here: a stack layer


def test_the_closing_references_read_is_one_direct_graphql_call_with_the_pull_request_number():
    gh = _PrGh(prs={501: _on_main(101)})
    ww._read_candidate_prs([501], _SLUG, {101}, "/", 100.0, lambda: 0.0, gh, {})
    [argv] = [call for call in gh.calls if call[:3] == ["gh", "api", "graphql"]]
    assert argv[3:9] == ["-f", "owner=owner", "-f", "name=repo", "-F", "number=501"]
    assert argv[9] == "-f" and argv[10].startswith("query=")
    # The query sent asks for every field the answer is read by, independently of the module's own constant, in any order.
    query = " ".join(argv[10][len("query="):].split())
    assert "pullRequest(number: $number)" in query
    # No alias renames a selection on the path the reader walks (data.repository.pullRequest...).
    assert not re.search(
        r"\w+\s*:\s*(repository|pullRequest|closingIssuesReferences|pageInfo|hasNextPage|nodes|number|nameWithOwner)\b",
        query)
    assert "closingIssuesReferences(first: 25)" in query
    assert re.search(r"pageInfo \{[^{}]*\bhasNextPage\b[^{}]*\}", query)
    # The `nodes` selection directly under the unaliased closingIssuesReferences, braces balanced, so a field selected
    # elsewhere does not count; no alias renames a key the reader reads.
    refs = re.search(r"(?<![\w:] )(?<!: )\bclosingIssuesReferences\(first: 25\) \{", query)
    assert refs and not re.search(r"\w+\s*:\s*closingIssuesReferences", query)

    def block(at):
        depth, end = 1, at
        while depth:
            depth += {"{": 1, "}": -1}.get(query[end], 0)
            end += 1
        return at, end - 1

    refs_start, refs_end = block(refs.end())
    inner = query[refs_start:refs_end]
    at = inner.index("nodes {")
    assert inner[:at].count("{") == inner[:at].count("}")  # a direct child of the connection
    assert not re.search(r"\w+\s*:\s*nodes\b", inner)
    nodes_start, nodes_end = block(refs_start + at + len("nodes {"))
    nodes = query[nodes_start:nodes_end]
    assert not re.search(r"\w+\s*:\s*(number|repository|nameWithOwner)\b", nodes)
    assert re.search(r"repository \{[^{}]*\bnameWithOwner\b[^{}]*\}", nodes)
    assert re.search(r"\bnumber\b", re.sub(r"repository \{[^{}]*\}", "", nodes))
    assert ww._read_candidate_prs([501], _SLUG, {101}, "/", 100.0, lambda: 0.0, _PrGh(prs={501: _on_main(101)}), {}) \
        == {501: (101,)}

