"""A host clock ahead of the launcher cannot make a cursor suffix complete."""
import json

from test_adopt_original_session import (
    TOKEN_LIVE,
    TOKEN_UNREAD,
    _adopt,
    _fixture,
    _isolated,
    _seed_lane,
    _write_listing,
)
from test_launcher_cloud import _cloud_repo


def test_cursor_suffix_with_host_clock_ahead_cannot_authorize_adoption(tmp_path):
    # axis: cross-host clock skew must not let a cursor suffix hide a live builder.
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)  # Local startedTs is 2026-10-24T12:00:00Z.
    with open(_fixture("list_page_complete_running.json"), encoding="utf-8") as fh:
        first_page = json.load(fh)
    with open(_fixture("list_page_complete_without.json"), encoding="utf-8") as fh:
        last_page = json.load(fh)

    # The host is ahead of the local clock. Its pages remain newest-created first.
    first_page["data"][0].update(
        created_at="2026-10-24T12:00:02Z",
        updated_at="2026-10-24T12:10:00Z",
    )
    first_page["has_more"] = True
    last_page["data"][0].update(
        created_at="2026-10-24T12:00:01Z",
        updated_at="2026-10-24T12:10:00Z",
    )
    pages = {None: first_page, first_page["last_id"]: last_page}

    def list_sessions(*, cursor=None):
        return pages[cursor]

    first = list_sessions()
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, first, "first.json"))
    assert result["ok"] is False, result
    assert result["reason"] == TOKEN_LIVE
    assert calls == []

    captured = list_sessions(cursor=first["last_id"])
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, captured, "suffix.json"))
    assert result["ok"] is False, result
    assert result["reason"] == TOKEN_UNREAD
    assert result["failedRead"] == "listing-incomplete"
    assert calls == []
