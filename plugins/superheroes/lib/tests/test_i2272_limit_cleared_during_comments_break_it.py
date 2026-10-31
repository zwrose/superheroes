"""A relay reply during the final comments lookup withdraws limit relief."""
import json
from datetime import datetime, timezone
from pathlib import Path

import cloud_builder
import cloud_relay
import launch_ledger as ll
from test_adopt_original_session import (
    ADOPTED, LANE_STARTED_TS, L, TOKEN_UNREAD, _adopt, _adopted_repo,
)
from test_launcher_cloud import (  # noqa: F401 (_isolated is an autouse fixture)
    _head_sha, _isolated, _lanes,
)


def _stamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def test_limit_cleared_during_final_comments_read_prevents_cloud_spawn(tmp_path, monkeypatch):
    # axis: a later relay reply invalidates account-limit stop evidence before
    # spawning, even when the originally advertised reset remains in the future.
    repo = _adopted_repo(tmp_path)
    launch_id = "launch-aaaa1111"
    config = tmp_path / "builders-account"
    now = LANE_STARTED_TS + 7200
    reset = LANE_STARTED_TS + 10800
    # Pin the clock before reset to isolate record clearance. Real clock skew,
    # reset schedules and wall-clock progress during network calls are unobservable.
    monkeypatch.setattr(L, "_now_fn", lambda: now)
    assert ll.append(repo, {
        "event": "reserved", "launchId": launch_id,
        "ts": LANE_STARTED_TS - 60, "schema": ll.SCHEMA,
        "batchId": "wave-test", "repoId": ll.repo_identity(repo), "issue": 656,
        "surfaces": ["plugins/earlier-builder"],
        "premise": {"issue": 656, "baseCommit": _head_sha(repo),
                    "adoptsBranch": ADOPTED, "standDown": 1},
        "preflight": {}, "argv": [], "doctrineDigest": "fixture",
        "model": "test-model", "place": ll.PLACE_CLOUD,
        "cloudEnvironment": "env-1", "pluginVersion": "1.2.3",
        "configDir": str(config),
    })
    assert ll.append(repo, {
        "event": "started", "launchId": launch_id,
        "ts": LANE_STARTED_TS, "schema": ll.SCHEMA,
        "attempt": 1, "pid": 999999999,
        "logPath": "/tmp/log", "errPath": "/tmp/err",
        "cloudSessionName": ll.cloud_session_name(656, launch_id),
        "cloudSessionId": "session_" + "a" * 24,
        "cloudSessionUrl": "https://claude.ai/code/session_fixture",
    })
    # A lane with no outcome is live for the same issue and would refuse the new launch as a duplicate.
    assert ll.record_outcome(repo, launch_id, "handback", "ended")["ok"]
    record = config / "projects" / "fixture" / "relay-fixture.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({
        "type": "assistant", "timestamp": _stamp(LANE_STARTED_TS + 3600),
        "isApiErrorMessage": True, "apiError": "usage_limit_reached",
        "quotaLimits": {"rateLimitType": "five_hour", "resetsAt": reset},
    }) + "\n", encoding="utf-8")
    state_path, why = cloud_relay._state_path(repo, None)
    assert why is None
    Path(state_path).write_text(json.dumps({
        "relays": {cloud_relay.relay_name(str(config)): {
            "sessionId": "relay-fixture", "configDir": str(config),
            "startedAt": LANE_STARTED_TS,
        }},
        "pending": {},
    }), encoding="utf-8")
    assert cloud_relay.account_limit(repo, str(config), now=now)["limited"] is True
    comment_reads = []

    def comments_with_reply(root, issue, env):
        comment_reads.append(issue)
        if len(comment_reads) == 2:
            # Inject the reply at the final owned remote-read seam. Real network
            # latency and concurrent process scheduling are not exercised.
            with record.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({
                    "type": "assistant", "timestamp": _stamp(LANE_STARTED_TS + 5400),
                    "message": {"role": "assistant", "content": [
                        {"type": "text", "text": "Account can run again."},
                    ]},
                }) + "\n")
        return [{
            "id": 1, "created_at": _stamp(LANE_STARTED_TS + 3700),
            "body": cloud_builder.superseded_notice_text(launch_id),
        }]

    monkeypatch.setattr(L, "_issue_comments_fn", comments_with_reply)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    assert len(comment_reads) >= 2
    assert cloud_relay.account_limit(repo, str(config), now=now)["limited"] is False
    assert result["ok"] is False, result
    assert result["reason"] == TOKEN_UNREAD, result
    # The owner's ruling: the final local re-read refuses with limit-expired.
    assert result["failedRead"] == "limit-expired"
    assert calls == []
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True and lane["started"] is False
