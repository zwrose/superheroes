"""The wave watch reads an old resumed lane's own issue (#2333).

A dormant (resumed) cloud lane's comments created or updated at or after its basis are seen however old the
basis is, while no dormant lane pulls the shared repository-wide read further back than
`DORMANT_LOOKBACK_SECONDS` before the read. A dormant lane whose basis is older than that is read from its own
issue, one issue-scoped read per tick. A failed or incomplete read of it names that lane alone; a read skipped for
budget names it only when the tick made a comments request; a tick that made none names no lane; the disclosure
is recorded in every case.

Chronology: the lane started 3 days ago, its outcome (the basis) was recorded 2 days ago, and its handback is
36 hours old, so only a read from the basis reaches it. The fake gh filters by `since` as GitHub does.
"""
import os
import re
import time
from datetime import datetime, timezone

import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import (  # noqa: F401
    _BATCH, _SLUG, _cloud_lane, _comment, _note_answered, _ok, _raw,
)
from test_wave_watch_cloud import _iso, clock, repo  # noqa: F401
from test_wave_watch_cloud_progress import _ProgressGh, _progress
from test_wave_watch_fix_order import _ending, _handed_back
from test_wave_watch_resumed_2323 import _outcome_at

_DAY = 86400
_URL = re.compile(
    r"^repos/%s/issues/(?:(?P<issue>\d+)/)?comments\?since=(?P<since>[^&]+)&per_page=100" % re.escape(_SLUG),
)


def _epoch(stamp):
    return ww._parse_activity_time(stamp)


def _stamp(comment):
    return _epoch(comment.get("updated_at") or comment["created_at"])


class _ScopedGh(_ProgressGh):
    """`_ProgressGh` whose comment reads are filtered by `since` as GitHub filters them.

    The shared read (`/issues/comments?`) serves `shared` (else `comments`); an issue-scoped read
    (`/issues/<n>/comments?`) serves `scoped` (else `comments`) restricted to that issue. A comment is served
    when its `updated_at`, else its `created_at`, is at or after `since`. An issue in `failing_issues`
    answers its scoped read HTTP 500. Every requested URL is recorded in `urls`.
    """

    def __init__(self, comments=(), *, failing_issues=(), shared=None, scoped=None, **kwargs):
        kwargs.setdefault("activity_age", 60)
        super().__init__(comments, **kwargs)
        self.failing_issues = set(failing_issues)
        self.shared = shared
        self.scoped = scoped
        self.urls = []

    def shared_urls(self):
        return [url for url in self.urls if _URL.match(url).group("issue") is None]

    def scoped_urls(self, issue):
        return [url for url in self.urls if _URL.match(url).group("issue") == str(issue)]

    def __call__(self, argv, **kwargs):
        if argv[:3] != ["gh", "api", "-i"]:
            return super().__call__(argv, **kwargs)
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)
        url = argv[-1]
        self.urls.append(url)
        match = _URL.match(url)
        assert match, url
        issue = match.group("issue")
        if issue is None:
            pool = self.comments if self.shared is None else self.shared
        else:
            if int(issue) in self.failing_issues:
                return _raw(argv, "HTTP/2.0 500 Internal Server Error\r\n\r\n{}")
            pool = self.comments if self.scoped is None else self.scoped
            pool = [c for c in pool if c["issue_url"].endswith("/issues/%s" % issue)]
        since = _epoch(match.group("since"))
        return _ok(argv, [c for c in pool if _stamp(c) >= since])


def _since(url):
    return _epoch(_URL.match(url).group("since"))


def _dormant(repo_root, launch_id="cloud-a", issue=101):
    """A started cloud lane, started 3 days ago, whose outcome (the basis) was recorded 2 days ago."""
    _cloud_lane(repo_root, launch_id, issue, start_age=3 * _DAY)
    _outcome_at(repo_root, launch_id, 2 * _DAY)


def _live(repo_root):
    """A live started cloud lane with nothing to report: it makes the shared request happen."""
    _cloud_lane(repo_root, "cloud-live", 201, start_age=3600)


def _basis(repo_root, launch_id):
    [record] = [
        r for r in ll.read(repo_root, create=False)["records"]
        if r.get("event") == "outcome" and r.get("launchId") == launch_id
    ]
    return record["ts"]


def test_t1_an_old_resumed_lanes_handback_is_reported_from_its_own_issue(repo):
    # axis: an old dormant lane is read from its own issue, so its handback is seen however old its basis — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    handback = _comment(7, 101, _ending("handback"), age=36 * 3600)
    gh = _ScopedGh([handback])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_LANE_TERMINAL
    [launch] = result["launches"]
    assert (launch["launchId"], launch["state"], launch["commentId"]) == ("cloud-a", "handback", 7)
    [shared] = gh.shared_urls()
    # Only the scoped read can have served it: the shared read starts after the handback was created.
    assert _since(shared) > _epoch(handback["created_at"])
    assert len(gh.scoped_urls(101)) == 1


def test_t2_a_failed_per_lane_read_is_disclosed_for_that_lane_alone(repo):
    # axis: a per-lane read that failed is disclosed for that lane alone, never read as quiet — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo, "cloud-a", 101)
    _dormant(repo, "cloud-b", 102)
    gh = _ScopedGh([], failing_issues=[101])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]
    assert len(gh.scoped_urls(101)) == 1 and len(gh.scoped_urls(102)) == 1


def test_t3_no_dormant_lane_pulls_the_shared_read_past_the_lookback(repo):
    # axis: no dormant lane pulls the shared read further back than DORMANT_LOOKBACK_SECONDS — see bite-proof record i2333_old_resumed_lane.md
    assert ww.DORMANT_LOOKBACK_SECONDS == _DAY
    _dormant(repo)
    _live(repo)
    gh = _ScopedGh([])
    before = time.time()
    ww.run(repo, _BATCH, gh_run=gh)
    [shared] = gh.shared_urls()
    assert _since(shared) >= before - _DAY


def test_t3_a_lone_old_dormant_lane_makes_no_shared_request_and_one_scoped_read_from_its_basis(repo):
    # axis: a lone old dormant lane makes no unneeded shared request and is read from its basis, not from the clamped bound — see bite-proof record i2333_old_resumed_lane.md
    _cloud_lane(repo, "cloud-a", 101, start_age=3 * _DAY)
    _outcome_at(repo, "cloud-a", 30 * 3600)
    gh = _ScopedGh([])
    ww.run(repo, _BATCH, gh_run=gh)
    assert gh.shared_urls() == []
    [scoped] = gh.scoped_urls(101)
    expected = datetime.fromtimestamp(_basis(repo, "cloud-a"), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert _URL.match(scoped).group("since") == expected


def test_t4_a_failed_per_lane_read_does_not_unclose_a_reopened_lane_or_name_it(repo):
    # axis: a failed old-lane read neither discards another lane's complete close nor names that lane — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo, "cloud-old", 101)
    _handed_back(repo, "cloud-r", 103, start_age=3 * _DAY)
    assert ll.amend(repo, "cloud-r", "vet", "not-ready", "needs the narrow fix")["ok"] is True
    # The reopened lane's closing handback (5) is answered; a note (6) follows the close.
    assert _note_answered(repo, 5)["ok"] is True
    comments = [
        _comment(5, 103, _ending("handback"), age=-10),
        _comment(6, 103, age=-20),
    ]
    gh = _ScopedGh(comments, failing_issues=[101])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert "notes" not in result
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
    assert result["unreadIssues"] == [{"launchId": "cloud-old", "issue": 101}]
    assert len(gh.shared_urls()) == 1


def test_t5_a_comment_in_both_reads_keeps_its_newest_revision(repo):
    # axis: a repeated comment id keeps the newest revision, so the per-lane read's edit is not shadowed by an older copy — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    created = 2.5 * _DAY
    parked = _progress(9, 101, updated_age=3000, created_age=created, phase="parked: waiting")
    resumed = _progress(9, 101, updated_age=1800, created_age=created, phase="resumed: fixing")
    gh = _ScopedGh([], shared=[parked], scoped=[resumed])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert len(gh.shared_urls()) == 1 and len(gh.scoped_urls(101)) == 1
    assert "cloud-a" in [lane["launchId"] for lane in result.get("cloudLanes", [])]


def test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park(repo):
    # axis: a lane's newest note, not its oldest, supersedes a park — see bite-proof record i2333_old_resumed_lane.md
    _cloud_lane(repo, "cloud-a", 101, start_age=5 * _DAY)
    note_a = _comment(11, 101, age=3000)
    park = _comment(12, 101, _ending("park"), age=2000)
    note_b = _comment(13, 101, age=1000)
    assert _note_answered(repo, 11)["ok"] is True
    assert _note_answered(repo, 13)["ok"] is True
    # GitHub serves both comment endpoints oldest first, so a "keep the first note seen" regression keeps the oldest note.
    gh = _ScopedGh([note_a, park, note_b])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER


class _SpendingGh(_ScopedGh):
    """`_ScopedGh` whose shared read spends the budget: it moves the fake clock to `spend_to` before answering."""

    def __init__(self, comments=(), *, now, spend_to, **kwargs):
        super().__init__(comments, **kwargs)
        self.now = now
        self.spend_to = spend_to

    def __call__(self, argv, **kwargs):
        if argv[:3] == ["gh", "api", "-i"] and _URL.match(argv[-1]).group("issue") is None:
            self.now[0] = self.spend_to
        return super().__call__(argv, **kwargs)


def _lanes(repo_root):
    return ww._derive_batch_lanes(repo_root, _BATCH, os.environ, set(), [])[1]


def _evaluate(repo_root, gh, *, deadline, monotonic, degraded, unread):
    return ww._evaluate_cloud_comments(
        repo_root, _lanes(repo_root), deadline=deadline, env=os.environ, gh_run=gh,
        monotonic=monotonic, degraded=degraded, note_state=[None], known_slug=_SLUG, unread_out=unread,
    )


def test_t7_a_tick_whose_reads_all_succeeded_names_no_lane_at_its_deadline(repo):
    # axis: a tick whose reads all succeeded names no old resumed lane, even though its last tick runs at its deadline with no budget — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    gh = _ScopedGh([])
    result = ww.watch_arm(repo, _BATCH, max_seconds=3, interval_seconds=1, gh_run=gh)
    assert result["event"] == ww.EVENT_TIMER
    assert len(gh.scoped_urls(101)) >= 1
    assert "unreadIssues" not in result


def test_t8_a_tick_that_made_no_request_names_no_lane_and_keeps_the_disclosure(repo):
    # axis: a tick that made no comments request names no lane, old resumed ones included, and records builder-note-unavailable — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    gh = _ScopedGh([])
    degraded, unread = set(), {}
    _evaluate(repo, gh, deadline=0.0, monotonic=lambda: 1.0, degraded=degraded, unread=unread)
    assert unread == {}
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert gh.urls == []


def test_t9_a_per_lane_read_skipped_after_a_request_names_its_lane(repo):
    # axis: a per-lane read skipped for budget after this tick made a request names its lane and records builder-note-unavailable — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    now = [0.0]
    gh = _SpendingGh([], now=now, spend_to=200.0)
    degraded, unread = set(), {}
    _evaluate(repo, gh, deadline=100.0, monotonic=lambda: now[0], degraded=degraded, unread=unread)
    assert len(gh.shared_urls()) == 1
    assert gh.scoped_urls(101) == []
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
    assert unread == {"cloud-a": 101}


def test_t10_a_comment_in_both_reads_keeps_the_newer_shared_copy(repo):
    # axis: a repeated comment id keeps the newest revision, even when the shared copy is the newer, so the per-lane copy does not always win — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    created = 2.5 * _DAY
    parked = _progress(9, 101, updated_age=3000, created_age=created, phase="parked: waiting")
    resumed = _progress(9, 101, updated_age=1800, created_age=created, phase="resumed: fixing")
    gh = _ScopedGh([], shared=[resumed], scoped=[parked])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert len(gh.shared_urls()) == 1 and len(gh.scoped_urls(101)) == 1
    assert "cloud-a" in [lane["launchId"] for lane in result.get("cloudLanes", [])]


def test_t11_a_note_served_by_both_reads_is_reported_once(repo):
    # axis: a comment id in both reads is merged to one copy, so a note is reported once, not twice — see bite-proof record i2333_old_resumed_lane.md
    _dormant(repo)
    _live(repo)
    note = _comment(21, 101, age=36 * 3600)
    note["updated_at"] = _iso(1800)
    gh = _ScopedGh([note])
    result = ww.run(repo, _BATCH, gh_run=gh)
    assert result["event"] == ww.EVENT_BUILDER_NOTE
    assert len(gh.shared_urls()) == 1 and len(gh.scoped_urls(101)) == 1
    assert [n["commentId"] for n in result["notes"]] == [21]


def test_t12_a_dormant_lane_with_a_recent_basis_is_read_by_the_shared_read_alone(repo):
    # axis: only a dormant lane whose basis is older than DORMANT_LOOKBACK_SECONDS gets a per-lane read; a recent basis costs no extra request — see bite-proof record i2333_old_resumed_lane.md
    _cloud_lane(repo, "cloud-a", 101, start_age=3 * _DAY)
    _outcome_at(repo, "cloud-a", 3600)
    gh = _ScopedGh([])
    ww.run(repo, _BATCH, gh_run=gh)
    assert gh.scoped_urls(101) == []
    assert len(gh.shared_urls()) == 1
