import wave_watch as ww
from test_wave_watch_builder_note import _BATCH, _SLUG
from test_wave_watch_cloud import clock, repo  # noqa: F401
from test_wave_watch_lookback_2333 import _ScopedGh, _dormant, _live
from test_wave_watch_pr_comments_2651 import _PULL, _PrGh, _body, _on_main, _pr_comment


def test_old_resumed_lane_stays_issue_only_when_another_lane_opens_the_shared_read(repo):
    # axis: the old resumed lane's PR handback leaves the batch on its timer even when another lane opens the shared read.
    _dormant(repo)
    _live(repo)
    gh = _ScopedGh([_pr_comment(7, 501, _body("handback"), age=60)])
    # GitHub links PR 501 to the old lane's issue 101, read the way the watch reads it, so the issue-only exclusion,
    # not an unknown link, is what keeps the handback off the lane.
    links = _PrGh(prs={501: _on_main(101)})

    def gh_run(argv, **kwargs):
        argv = list(argv)
        if argv[:3] == ["gh", "api", "graphql"] or (len(argv) == 3 and argv[:2] == ["gh", "api"] and (
                argv[2] == "repos/%s" % _SLUG or _PULL.match(argv[2]))):
            return links(argv, **kwargs)
        return gh(argv, **kwargs)

    result = ww.run(repo, _BATCH, gh_run=gh_run)
    assert len(gh.shared_urls()) == 1
    assert len(gh.scoped_urls(101)) == 1
    assert links.reads["graphql"] == [501]
    assert result["event"] == ww.EVENT_TIMER, result
    assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
