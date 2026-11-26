"""The wave watch reads a builder note or a terminal comment on a watched lane's own PR as that lane's (#2651).

A comment whose body opens with the builder-note header, or whose first line is a handback, stop or park
header, posted on a pull request whose body closes exactly one watched lane's issue is treated as if it were
posted on that issue; its entry keeps `issue` as the lane's, gains `pr`, and keeps the PR comment's own url.
Any other comment on a pull request stays no lane's. When the watch cannot tell which lane such a comment
belongs to it says so (builder-note-unavailable), never "no note".

Bites on: the re-key to the one closed lane (rows 1, 2, 6), the disclosure of an unreadable, unresolvable or
ambiguous attribution (rows 5, 7), the comment-kind filter (row 8), the started-at cutoff, the answered record,
and the close bookkeeping that must not take an incomplete attribution for a complete read (row 11).
Residual blind spots: the real GitHub issue payload beyond `number`, `body` and `pull_request`; a PR body
whose closing keyword names a cross-repository issue (the keyword grammar is stack_check's, tested there); the
read budget running out between two candidate PRs (the skip is in `_read_candidate_prs`, not driven here); and
the loop's re-arm across a lane-terminal (covered with the other lane events).
"""
import json
import time

import pytest

import cloud_builder as cb
import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import (  # noqa: F401
    _cloud_lane, _comment, _NoteGh, _arm, _note_answered, _BATCH, _NOTE_BODY, _raw,
)
from test_wave_watch_cloud import _FRESH, _QUIET, _SLUG, clock, repo  # noqa: F401
from test_wave_watch_cloud_progress import _progress  # noqa: F401

_CONFIG_DIR = "/home/advisor/.claude-two"
_PR_PATH = "repos/%s/issues/%d"


def _body(kind, text="Done with the work."):
    return cb.terminal_text(kind, text)["comment"]


def _pr(number, body, *, base="main"):
    """The issues-endpoint payload of a pull request."""
    return {
        "number": number, "body": body, "base_ref": base,
        "pull_request": {"url": "https://api.github.com/repos/%s/pulls/%d" % (_SLUG, number)},
    }


class _PrGh(_NoteGh):
    """`_NoteGh` that also answers `gh api repos/<slug>/issues/<n>` from `prs`: {number: a payload (served as
    JSON), a CompletedProcess (served as is), or an exception (raised)}. Every such read is recorded."""

    def __init__(self, comments=(), *, prs=None, script=()):
        super().__init__(comments, script=script)
        self.prs = dict(prs or {})
        self.pr_reads = []

    def __call__(self, argv, **kwargs):
        for number, answer in self.prs.items():
            if list(argv) == ["gh", "api", _PR_PATH % (_SLUG, number)]:
                self.calls.append(list(argv))
                self.kwargs.append(kwargs)
                self.pr_reads.append(number)
                if isinstance(answer, BaseException):
                    raise answer
                if hasattr(answer, "returncode"):
                    return answer
                return _raw(argv, json.dumps(answer))
        return super().__call__(argv, **kwargs)


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


def _failed(argv=()):
    return _raw(list(argv), "gh: Not Found (HTTP 404)", 1)


# --- row 1, 2: a handback or a builder note on the lane's own PR is the lane's ---------------


def test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _pr(501, "Closes #101.\n\nThe work.")})
    launch = _only_launch(_arm(repo, gh))
    assert launch["launchId"] == "cloud-a"
    assert launch["state"] == "handback"
    assert launch["issue"] == 101
    assert launch["pr"] == 501
    assert launch["commentId"] == 7
    assert launch["url"].endswith("/pull/501#issuecomment-7")
    assert gh.pr_reads == [501]


def test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501)], prs={501: _pr(501, "Closes #101.\n\nThe work.")})
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


def test_row3_a_handback_on_a_pr_that_closes_only_an_unwatched_issue_is_no_lanes(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _pr(501, "Closes #999.")})
    # One tick: a multi-tick arm reports builder-note-unavailable on its last tick for want of budget, with or without a PR.
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert "unreadIssues" not in result
    assert gh.pr_reads == [501]


def test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure(repo):
    _cloud_lane(repo, "cloud-a", 101)
    # A plain issue's comment has an `/issues/` html_url; reading 777 would fail here, so a read would be disclosed.
    gh = _PrGh([_comment(7, 777, _body("handback"))], prs={777: _failed()})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert "unreadIssues" not in result
    assert gh.pr_reads == []
    assert not [argv for argv in gh.calls if argv[-1:] == [_PR_PATH % (_SLUG, 777)]]


def test_a_pr_comment_whose_page_number_differs_from_its_issue_number_is_no_candidate(repo):
    _cloud_lane(repo, "cloud-a", 101)
    odd = dict(
        _pr_comment(7, 501, _body("handback")),
        html_url="https://github.com/%s/pull/502#issuecomment-7" % _SLUG,
    )
    gh = _PrGh([odd], prs={501: _pr(501, "Closes #101."), 502: _pr(502, "Closes #101.")})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
    assert gh.pr_reads == []
    assert ww._pr_candidate(odd, {101}, 0.0) is None


# --- row 4: the started-at cutoff applies to the PR's comment ---------------------------------


def test_row4_a_handback_on_the_lanes_pr_from_before_the_lane_started_is_not_reported(repo):
    _cloud_lane(repo, "cloud-a", 101, start_age=600, reserve_lead=100)
    gh = _PrGh(
        [_pr_comment(7, 501, _body("handback"), age=3000)], prs={501: _pr(501, "Closes #101.")},
    )
    result = _arm(repo, gh)
    assert result["event"] == ww.EVENT_TIMER
    assert gh.pr_reads == []


# --- row 5: an unreadable PR is disclosed, never "no note" -------------------------------------


def test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _failed()})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]
    assert gh.pr_reads == [501]


def test_a_pr_read_that_raises_is_disclosed_too(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: OSError("gh is gone")})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]


def test_a_pr_payload_that_is_not_json_is_disclosed(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _raw([], "<html>not json</html>")})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]


def test_a_pr_body_that_is_not_a_string_is_disclosed(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _pr(501, 12345)})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]


# --- row 6: a stack layer's PR targets the layer below and is still its own lane's ----------


def test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only(repo):
    _cloud_lane(repo, "cloud-lower", 101)
    _cloud_lane(repo, "cloud-upper", 102)
    gh = _PrGh(
        [_pr_comment(7, 502, _body("handback"))],
        prs={502: _pr(502, "Closes #102", base="layer-101-branch")},
    )
    result = _arm(repo, gh)
    launch = _only_launch(result)
    assert launch["launchId"] == "cloud-upper"
    assert launch["issue"] == 102
    assert launch["pr"] == 502


# --- row 7: a PR that closes two watched lanes' issues is no lane's, and is disclosed -------


def test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
    _cloud_lane(repo, "cloud-a", 101)
    _cloud_lane(repo, "cloud-b", 102)
    gh = _PrGh([_pr_comment(7, 503, _body("handback"))], prs={503: _pr(503, "Closes #101\nCloses #102")})
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] != ww.EVENT_LANE_TERMINAL
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [
        {"launchId": "cloud-a", "issue": 101}, {"launchId": "cloud-b", "issue": 102},
    ]


# --- row 8: only a note or an ending moves to the PR's lane ------------------------------------


def test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress():
    lanes = _lanes({"cloud-a": (101, 600)})
    gh = _PrGh([_as_pr(_progress(9, 501, updated_age=100))], prs={501: _pr(501, "Closes #101.")})
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
    gh = _PrGh(comments, prs={501: _pr(501, "Closes #101.")})
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
    gh = _PrGh([_pr_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
    assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
    assert gh.pr_reads == []


# --- row 10: no candidate, no request ----------------------------------------------------------


def test_row10_a_tick_with_no_pr_comment_makes_no_pr_read(repo):
    _cloud_lane(repo, "cloud-a", 101)
    gh = _PrGh(
        [_comment(7, 101, _body("handback")), _comment(8, 101, _NOTE_BODY)],
        prs={501: _pr(501, "Closes #101.")},
    )
    _only_launch(ww.run(repo, _BATCH, gh_run=gh))
    assert gh.pr_reads == []
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


def test_row11_an_unresolved_pr_comment_leaves_the_closed_slot_unset():
    lanes, comments = _reopened_lane_and_comments()
    gh = _PrGh(comments, prs={501: _failed()})
    closed_out, unread_out = [None], {}
    _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert closed_out[0] is None
    assert unread_out == {"cloud-a": 101}


def test_row11_control_a_resolved_pr_comment_sets_the_closed_slot():
    lanes, comments = _reopened_lane_and_comments()
    gh = _PrGh(comments, prs={501: _pr(501, "Closes #101.")})
    closed_out, unread_out = [None], {}
    _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
    assert closed_out[0] is not None and set(closed_out[0]) == {"cloud-a"}
    assert unread_out == {}


def test_row11_an_unresolved_pr_comment_keeps_the_known_closes():
    lanes, comments = _reopened_lane_and_comments()
    known = {"cloud-a": ((time.time() - 300, 7), "handback")}
    gh = _PrGh(comments, prs={501: _failed()})
    (notes, terminals), degraded = _evaluate(lanes, gh, known_closes=known)
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert terminals == []  # the cached close, not this read's first ending, bounds the window


# --- row 12: the answered record stops a PR comment surfacing ---------------------------------


def test_row12_an_answered_pr_handback_no_longer_surfaces(repo):
    _cloud_lane(repo, "cloud-a", 101)
    comments = [_pr_comment(7, 501, _body("handback"))]
    prs = {501: _pr(501, "Closes #101.")}
    assert _only_launch(_arm(repo, _PrGh(comments, prs=prs)))["commentId"] == 7
    assert _note_answered(repo, 7)["ok"] is True
    assert _arm(repo, _PrGh(comments, prs=prs))["event"] == ww.EVENT_TIMER


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
    gh = _PrGh(broken + [_pr_comment(8, 501, good)], prs={501: _pr(501, "Closes #101.")})
    assert _only_launch(_arm(repo, gh))["commentId"] == 8


def test_pr_candidate_never_raises_on_a_malformed_comment():
    for comment in (None, 5, [], {}, {"id": 1}, {"id": 1, "body": 3, "issue_url": "x", "created_at": 1}):
        assert ww._pr_candidate(comment, {101}, 0.0) is None


def test_pr_closing_issues_reads_this_repositorys_closing_keywords_only():
    body = "Closes #101, fixes owner/repo#102, resolves other/repo#103, see #104."
    assert ww._pr_closing_issues(_pr(1, body), "Owner/Repo") == (101, 102)
    assert ww._pr_closing_issues(_pr(1, None), "owner/repo") == ()
    assert ww._pr_closing_issues({"number": 1, "body": "Closes #101"}, "owner/repo") == ()
    assert ww._pr_closing_issues(_pr(1, 7), "owner/repo") is None
    assert ww._pr_closing_issues([], "owner/repo") is None


def test_attribution_never_mutates_the_comments_it_is_given():
    lanes = _lanes({"cloud-a": (101, 600)})
    comment = _pr_comment(7, 501, _body("handback"))
    before = dict(comment)
    comments = [comment]
    out, complete = ww._attribute_pr_comments(comments, lanes, {501: (101,)}, 0.0)
    assert complete is True
    assert comment == before and comments == [comment]
    assert out[0] is not comment
    assert out[0]["issue_url"].endswith("/issues/101") and out[0]["prNumber"] == 501
    assert out[0]["html_url"] == comment["html_url"]


def test_a_pr_read_skipped_for_budget_is_unresolved_for_it_and_every_later_number():
    gh = _PrGh(prs={
        501: _pr(501, "Closes #101."), 502: _pr(502, "Closes #102."), 503: _pr(503, "Closes #103."),
    })
    clock_values = iter([0.0, 10.0])  # budget left for the first read, spent from the second on
    resolved = ww._read_candidate_prs(
        [503, 501, 502], _SLUG, "/", 10.0, lambda: next(clock_values, 10.0), gh, {},
    )
    assert resolved == {501: (101,), 502: None, 503: None}
    assert gh.pr_reads == [501]
