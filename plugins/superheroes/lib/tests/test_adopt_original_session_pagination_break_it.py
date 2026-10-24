"""A pagination suffix cannot prove an original cloud builder is gone."""
import json

from test_adopt_original_session import (
    SESSION_ID,
    _adopt,
    _fixture,
    _isolated,
    _seed_lane,
    _write_listing,
)
from test_launcher_cloud import _cloud_repo


def test_a_final_cursor_page_does_not_authorize_adoption(tmp_path):
    # axis: has_more false proves exhaustion after the cursor, not absence before it.
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo)
    with open(_fixture("list_page_complete_running.json"), encoding="utf-8") as fh:
        first_page = json.load(fh)
    first_page["has_more"] = True
    with open(_fixture("list_page_complete_without.json"), encoding="utf-8") as fh:
        last_page = json.load(fh)
    pages = {None: first_page, first_page["last_id"]: last_page}

    def list_sessions(*, cursor=None):
        return pages[cursor]

    first = list_sessions()
    assert first["data"][0]["id"] == SESSION_ID
    assert first["has_more"] is True
    captured = list_sessions(cursor=first["last_id"])
    assert captured["has_more"] is False
    result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, captured))
    assert result["ok"] is False, result
    assert result["reason"] == "adopt-original-session-unread"
    assert result["failedRead"] == "listing-incomplete"
    assert calls == []
