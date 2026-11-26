import json

import wave_watch as ww
from test_wave_watch_builder_note import _BATCH, _SLUG, _raw
from test_wave_watch_cloud import clock, repo  # noqa: F401
from test_wave_watch_lookback_2333 import _ScopedGh, _dormant, _live
from test_wave_watch_pr_comments_2651 import _body, _pr, _pr_comment


def test_old_resumed_lane_stays_issue_only_when_another_lane_opens_the_shared_read(repo):
    # axis: the old resumed lane's PR handback leaves the batch on its timer even when another lane opens the shared read.
    _dormant(repo)
    _live(repo)
    gh = _ScopedGh([_pr_comment(7, 501, _body("handback"), age=60)])

    def gh_run(argv, **kwargs):
        if argv == ["gh", "api", f"repos/{_SLUG}/issues/501"]:
            return _raw(argv, json.dumps(_pr(501, "Closes #101.")))
        return gh(argv, **kwargs)

    result = ww.run(repo, _BATCH, gh_run=gh_run)
    assert len(gh.shared_urls()) == 1
    assert len(gh.scoped_urls(101)) == 1
    assert result["event"] == ww.EVENT_TIMER, result
