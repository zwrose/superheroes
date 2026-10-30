"""The account-limit reading (#2272): the relay check and the wave watch name a builders' account at its usage limit.

The relay's session record carries the limit as an `assistant` line per rejected turn. The reading is
`cloud_relay.account_limit`; `check` reports `account-limited` for a silent relay on a limited account;
the wave watch reports an `account-limited` event naming the account's live cloud lanes and does not
report them `lane-stale` while the limit holds. Anything that is not exactly the recorded shape is no reading.
"""
import json
import os
import time
from datetime import datetime, timezone

import pytest

import cloud_relay as cr
import launch_ledger as ll
import wave_watch as ww
from test_cloud_relay import (  # noqa: F401
    RELAY_ID, SESSION, _backdate, _check, _composed, _decide, _ensure_alive, _send_lines,
    _state_file, _write_record, world,
)
from test_wave_watch_builder_note import _NoteGh, _arm, _cloud_lane  # noqa: F401
from test_wave_watch_cloud import _BATCH, _add_cloud_lane, _quiet_gh, clock, repo  # noqa: F401

# Read from a real relay session record on 2026-10-30 (Claude Code 2.1.310); ids replaced.
LIMIT_LINE = '{"type": "assistant", "timestamp": "2026-10-30T09:40:59.896Z", "isApiErrorMessage": true, "error": "rate_limit", "apiError": "usage_limit_reached", "apiErrorStatus": 429, "apiErrorParams": {"rate_limit_info": {"status": "rejected", "rateLimitType": "seven_day", "resetsAt": 1793566800, "overageStatus": "rejected", "overageDisabledReason": "org_level_disabled", "isUsingOverage": false}}, "quotaLimits": {"status": "rejected", "rateLimitType": "seven_day", "resetsAt": 1793566800, "overageStatus": "rejected", "overageDisabledReason": "org_level_disabled", "isUsingOverage": false, "unifiedRateLimitFallbackAvailable": false, "upgradePaths": ["overage"]}, "message": {"type": "message", "role": "assistant", "model": "<synthetic>", "stop_reason": "stop_sequence", "stop_sequence": "", "content": [{"type": "text", "text": "You\'ve hit your weekly limit · resets Nov 1 at 4pm (America/New_York)"}], "usage": {"input_tokens": 0, "output_tokens": 0}}, "requestId": "req_fixture", "uuid": "00000000-0000-0000-0000-000000000001", "parentUuid": "00000000-0000-0000-0000-000000000000", "sessionId": "relay-session-fixture", "session_id": "relay-session-fixture", "sessionKind": "bg", "entrypoint": "cli", "version": "2.1.310", "cwd": "/repo", "gitBranch": "main", "isSidechain": false, "userType": "external", "perTurnEffort": "low"}'

RESETS_AT = 1793566800  # 2026-11-01T21:00:00Z
RECORDED_AT = 1793353259.896  # 2026-10-30T09:40:59.896Z
BEFORE_RESET = RESETS_AT - 3600
_GONE = object()


def _limit(mutate=None):
    """The fixture line as a dict, after `mutate(rec)`."""
    rec = json.loads(LIMIT_LINE)
    if mutate:
        mutate(rec)
    return rec


def _both(rec, key, value):
    """Set (or, with _GONE, drop) `key` in both info dicts, so neither stands in for the other."""
    for info in (rec["quotaLimits"], rec["apiErrorParams"]["rate_limit_info"]):
        if value is _GONE:
            info.pop(key, None)
        else:
            info[key] = value


def _reply(stamp):
    return {"type": "assistant", "timestamp": stamp,
            "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}


def _lines(world, *recs):
    """The relay is recorded and its session record holds `recs` (dicts, or raw strings)."""
    _ensure_alive(world)
    with open(world.record, "w", encoding="utf-8") as fh:
        for rec in recs:
            fh.write((rec if isinstance(rec, str) else json.dumps(rec)) + "\n")


def _read(world, *recs, now=BEFORE_RESET):
    _lines(world, *recs)
    return cr.account_limit(world.repo, world.config, env=world.env, now=now)


def _no_reading(out):
    return (out["ok"] is True and out["limited"] is False and out["limitType"] is None
            and out["resetsAt"] is None and out["recordedAt"] is None)


# ---- the reading ---------------------------------------------------------------------------


def test_the_fixture_line_alone_is_a_limit_before_its_reset(world):
    out = _read(world, LIMIT_LINE)
    assert out["ok"] is True and out["limited"] is True
    assert out["limitType"] == "seven_day"
    assert out["resetsAt"] == RESETS_AT
    assert out["recordedAt"] == pytest.approx(RECORDED_AT)
    assert out["configDir"] == world.config and out["relay"] == cr.relay_name(world.config)


def test_at_or_after_its_reset_the_limit_no_longer_holds_but_is_still_reported(world):
    for now in (RESETS_AT, RESETS_AT + 1):
        out = _read(world, LIMIT_LINE, now=now)
        assert out["ok"] is True and out["limited"] is False
        assert out["limitType"] == "seven_day" and out["resetsAt"] == RESETS_AT
        assert out["recordedAt"] == pytest.approx(RECORDED_AT)


def test_a_later_reply_from_the_account_clears_the_limit_but_it_is_still_reported(world):
    out = _read(world, LIMIT_LINE, _reply("2026-10-30T09:41:00.000Z"))
    assert out["ok"] is True and out["limited"] is False
    assert out["limitType"] == "seven_day" and out["resetsAt"] == RESETS_AT


def test_a_reply_that_is_not_strictly_later_or_is_not_a_reply_does_not_clear_it(world):
    not_replies = [
        _reply("2026-10-30T09:40:59.896Z"),  # the same instant
        _reply("2026-10-30T09:40:00.000Z"),  # earlier
        dict(_reply("2026-10-30T09:41:00.000Z"), isApiErrorMessage=True),  # another error line
        dict(_reply("2026-10-30T09:41:00.000Z"), type="user"),
        _reply("not a time"),
        _reply("2026-10-30T09:41:00.000"),  # no zone
    ]
    for rec in not_replies:
        assert _read(world, LIMIT_LINE, rec)["limited"] is True, rec


def test_the_newest_limit_record_decides_the_fields_whatever_the_file_order(world):
    older = _limit(lambda r: (_both(r, "rateLimitType", "five_hour"), _both(r, "resetsAt", RESETS_AT - 100),
                              r.update(timestamp="2026-10-30T08:00:00.000Z")))
    for order in ((older, LIMIT_LINE), (LIMIT_LINE, older)):
        out = _read(world, *order)
        assert out["limitType"] == "seven_day" and out["resetsAt"] == RESETS_AT


def test_a_limit_the_relay_records_for_the_other_account_is_not_read(world, tmp_path):
    other = tmp_path / ".claude-three"
    other.mkdir()
    _lines(world, LIMIT_LINE)
    out = cr.account_limit(world.repo, str(other), env=world.env, now=BEFORE_RESET)
    assert _no_reading(out)


# ---- anything that is not exactly the recorded shape is no reading ---------------------------


def test_a_line_the_host_does_not_mark_as_an_api_error_is_no_reading(world):
    for value in (False, _GONE, "true", 1, None):
        rec = _limit(lambda r: r.pop("isApiErrorMessage") if value is _GONE else r.update(isApiErrorMessage=value))
        assert _no_reading(_read(world, rec)), value
    assert _no_reading(_read(world, _limit(lambda r: r.update(type="user"))))


def test_a_line_that_is_neither_the_usage_limit_error_nor_a_rejected_rate_limit_is_no_reading(world):
    other_error = _limit(lambda r: r.update(apiError="overloaded", error="server_error"))
    assert _no_reading(_read(world, other_error))

    def not_rejected(rec):
        rec.pop("apiError")
        _both(rec, "status", "allowed")

    assert _no_reading(_read(world, _limit(not_rejected)))
    assert _no_reading(_read(world, _limit(lambda r: (r.pop("apiError"), r.pop("error")))))


def test_a_rate_limit_error_whose_info_says_rejected_is_a_limit_without_the_usage_limit_error(world):
    out = _read(world, _limit(lambda r: r.pop("apiError")))
    assert out["limited"] is True and out["limitType"] == "seven_day"


@pytest.mark.parametrize("value", [_GONE, "1793566800", True, False, -5, 0, float("nan"),
                                   float("inf"), None, [1793566800]])
def test_a_reset_time_that_is_not_a_finite_positive_number_is_no_reading(world, value):
    assert _no_reading(_read(world, _limit(lambda r: _both(r, "resetsAt", value))))


def test_a_reset_time_in_float_seconds_is_read(world):
    out = _read(world, _limit(lambda r: _both(r, "resetsAt", RESETS_AT + 0.5)))
    assert out["limited"] is True and out["resetsAt"] == RESETS_AT + 0.5


@pytest.mark.parametrize("value", [_GONE, "seven_day_opus", "seven_day_sonnet", "weekly", "", None, 7])
def test_a_limit_type_that_is_not_account_wide_is_no_reading(world, value):
    assert _no_reading(_read(world, _limit(lambda r: _both(r, "rateLimitType", value))))


def test_a_five_hour_limit_is_an_account_wide_limit(world):
    out = _read(world, _limit(lambda r: _both(r, "rateLimitType", "five_hour")))
    assert out["limited"] is True and out["limitType"] == "five_hour"


def test_without_quota_limits_the_rate_limit_info_is_read(world):
    out = _read(world, _limit(lambda r: r.pop("quotaLimits")))
    assert out["limited"] is True and out["limitType"] == "seven_day" and out["resetsAt"] == RESETS_AT


def test_quota_limits_without_a_usable_reset_falls_back_to_the_rate_limit_info(world):
    out = _read(world, _limit(lambda r: r["quotaLimits"].pop("resetsAt")))
    assert out["limited"] is True and out["resetsAt"] == RESETS_AT
    assert _no_reading(_read(world, _limit(lambda r: (r.pop("quotaLimits"), r.pop("apiErrorParams")))))


def test_a_limit_stamp_that_cannot_be_read_as_a_time_is_no_reading(world):
    for stamp in ("not a time", None, 12, "2026-10-30T09:40:59.896"):
        assert _no_reading(_read(world, _limit(lambda r: r.update(timestamp=stamp)))), stamp
    assert _no_reading(_read(world, _limit(lambda r: r.pop("timestamp"))))


def test_the_message_text_is_never_read(world):
    words = _limit(lambda r: r.update(isApiErrorMessage=False))
    assert _no_reading(_read(world, words))
    quiet = _limit(lambda r: r["message"]["content"][0].update(text="all fine"))
    assert _read(world, quiet)["limited"] is True


def test_noise_in_the_record_is_skipped(world):
    out = _read(world, "{not json", "[1, 2]", "", LIMIT_LINE)
    assert out["limited"] is True


def test_no_relay_recorded_is_no_reading(world):
    out = cr.account_limit(world.repo, world.config, env=world.env, now=BEFORE_RESET)
    assert _no_reading(out)


def test_a_relay_without_a_session_id_or_a_record_is_no_reading(world):
    _ensure_alive(world)
    assert _no_reading(cr.account_limit(world.repo, world.config, env=world.env, now=BEFORE_RESET))
    path = _state_file(world)
    state = json.load(open(path))
    state["relays"][cr.relay_name(world.config)]["sessionId"] = None
    json.dump(state, open(path, "w"))
    assert _no_reading(cr.account_limit(world.repo, world.config, env=world.env, now=BEFORE_RESET))


@pytest.mark.parametrize("config_dir", ["", None, 5, "/"])
def test_a_bad_config_dir_is_refused(world, config_dir):
    out = cr.account_limit(world.repo, config_dir, env=world.env, now=BEFORE_RESET)
    assert out == {"ok": False, "reason": "config-dir-invalid"}


def test_the_relay_states_refusals_pass_through(world):
    _lines(world, LIMIT_LINE)
    open(_state_file(world), "w").write("{not json")
    out = cr.account_limit(world.repo, world.config, env=world.env, now=BEFORE_RESET)
    assert out == {"ok": False, "reason": "relay-state-unreadable"}


def test_without_a_given_now_the_clock_decides(world):
    future = _limit(lambda r: _both(r, "resetsAt", int(time.time()) + 3600))
    _lines(world, future)
    assert cr.account_limit(world.repo, world.config, env=world.env)["limited"] is True
    _lines(world, LIMIT_LINE)  # the fixture's reset has passed by the time this runs
    assert cr.account_limit(world.repo, world.config, env=world.env)["limited"] is (time.time() < RESETS_AT)


def test_the_limit_verb_prints_the_reading_and_exits_1_only_on_a_refusal(world, capsys, monkeypatch):
    for key, value in world.env.items():
        monkeypatch.setenv(key, value)
    future = _limit(lambda r: _both(r, "resetsAt", int(time.time()) + 3600))
    _lines(world, future)
    code = cr.main(["limit", "--repo-root", world.repo, "--config-dir", world.config])
    printed = json.loads(capsys.readouterr().out)
    assert code == 0 and printed["ok"] is True and printed["limited"] is True
    assert printed["limitType"] == "seven_day"
    code = cr.main(["limit", "--repo-root", world.repo, "--config-dir", ""])
    assert code == 1 and json.loads(capsys.readouterr().out) == {"ok": False, "reason": "config-dir-invalid"}


# ---- the relay check -------------------------------------------------------------------------


def _check_at(world, msg_id, wall_now):
    return cr.check(world.repo, msg_id, wait=0, env=world.env, wall=lambda: wall_now)


def test_a_silent_relay_on_a_limited_account_reads_account_limited(world):
    msg = _composed(world)
    _write_record(world, [json.loads(LIMIT_LINE)])
    out = _check_at(world, msg["msgId"], BEFORE_RESET)
    assert out["ok"] is False and out["delivered"] is False
    assert out["reason"] == "account-limited"
    assert out["limitType"] == "seven_day" and out["resetsAt"] == RESETS_AT
    assert out["resetsAtIso"] == "2026-11-01T21:00:00Z"
    assert "seven_day" in out["say"] and "2026-11-01T21:00:00Z" in out["say"]
    assert msg["msgId"] in out["say"] and out["say"].endswith("; it was not delivered.")
    stored = json.load(open(_state_file(world)))["pending"][msg["msgId"]]["decision"]
    assert stored["reason"] == "account-limited" and stored["delivered"] is False


def test_a_silent_relay_past_the_reset_is_silent_as_before(world):
    msg = _composed(world)
    _write_record(world, [json.loads(LIMIT_LINE)])
    out = _check_at(world, msg["msgId"], RESETS_AT)
    assert out["reason"] == "relay-silent" and out["delivered"] is False
    assert "resetsAt" not in out and "limitType" not in out


def test_only_a_silent_relay_reads_account_limited(world):
    msg = _composed(world)
    wrong = _send_lines("toolu_1", SESSION, msg["forward"] + " altered", "2026-10-30T09:40:00.000Z")
    _write_record(world, wrong, [json.loads(LIMIT_LINE)])
    out = _check_at(world, msg["msgId"], BEFORE_RESET)
    assert out["reason"] == "relay-text-mismatch"
    exact = _send_lines("toolu_2", SESSION, msg["forward"], "2026-10-30T09:40:00.000Z")
    _write_record(world, exact, [json.loads(LIMIT_LINE)])
    out = _check_at(world, msg["msgId"], BEFORE_RESET)
    assert out["ok"] is True and out["delivered"] is True


def test_a_silent_relay_with_no_limit_on_record_is_silent(world):
    msg = _composed(world)
    _write_record(world, [])
    out = _check_at(world, msg["msgId"], BEFORE_RESET)
    assert out["reason"] == "relay-silent"


def test_an_account_limited_fix_order_is_not_listed_as_may_have_reached(world):
    msg = _composed(world)
    path = _state_file(world)
    state = json.load(open(path))
    state["pending"][msg["msgId"]]["fixOrder"] = True
    json.dump(state, open(path, "w"))
    _write_record(world, [json.loads(LIMIT_LINE)])
    assert _check_at(world, msg["msgId"], BEFORE_RESET)["reason"] == "account-limited"
    assert cr.fix_orders(world.repo, env=world.env) == {"ok": True, "records": []}
    listed = cr.fix_orders(world.repo, env=world.env, include_unchecked=True)
    assert [r["msgId"] for r in listed["records"]] == [msg["msgId"]]
    # the same message read relay-silent (the limit has reset) may have reached the builder
    assert _check_at(world, msg["msgId"], RESETS_AT)["reason"] == "relay-silent"
    again = cr.fix_orders(world.repo, env=world.env)
    assert [r["msgId"] for r in again["records"]] == [msg["msgId"]]


# ---- the wave watch --------------------------------------------------------------------------


def _live_limit(resets_in):
    """The fixture line moved to now: stamped a minute ago, resetting `resets_in` seconds from now."""
    now = time.time()
    rec = _limit(lambda r: _both(r, "resetsAt", int(now) + resets_in))
    rec["timestamp"] = datetime.fromtimestamp(now - 60, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return rec


def _account(repo_root, root, name, *recs):
    """An account directory whose relay is recorded with a session record of `recs`."""
    config = root / name
    session_id = "relay-" + name
    (config / "projects" / "p").mkdir(parents=True)
    with open(str(config / "projects" / "p" / (session_id + ".jsonl")), "w", encoding="utf-8") as fh:
        for rec in recs:
            fh.write(json.dumps(rec) + "\n")
    path, why = cr._state_path(repo_root, None)
    assert why is None
    state = json.load(open(path)) if os.path.exists(path) else {"relays": {}, "pending": {}}
    state["relays"][cr.relay_name(str(config))] = {
        "sessionId": session_id, "startedAt": 1, "configDir": str(config)}
    json.dump(state, open(path, "w"))
    return str(config)


def _wave(repo_root, tmp_path, *, a_resets_in=3600):
    """Two started cloud lanes on account A (at its limit), one on account B (its limit has reset)."""
    a = _account(repo_root, tmp_path, "acct-a", _live_limit(a_resets_in))
    b = _account(repo_root, tmp_path, "acct-b", _live_limit(-10))
    _cloud_lane(repo_root, "cloud-a1", 101, config_dir=a)
    _cloud_lane(repo_root, "cloud-a2", 102, config_dir=a)
    _cloud_lane(repo_root, "cloud-b1", 201, config_dir=b)
    return a, b


def _stale_ids(result):
    return sorted(entry["launchId"] for entry in result["launches"])


def test_the_event_names_every_live_cloud_lane_on_the_limited_account(repo, tmp_path):
    a, _b = _wave(repo, tmp_path)
    result = ww.run(repo, _BATCH, gh_run=_quiet_gh(101, 102, 201))
    assert result["ok"] is True and result["event"] == "account-limited"
    assert result["launchIds"] == ["cloud-a1", "cloud-a2"]
    assert result["launchId"] == "cloud-a1"
    [account] = result["accounts"]
    assert account["configDir"] == a
    assert account["limitType"] == "seven_day"
    assert account["resetsAt"] > time.time() and account["resetsAtIso"].endswith("Z")
    assert account["launchIds"] == ["cloud-a1", "cloud-a2"]
    assert result["alsoObserved"] == {"stale": ["cloud-b1"]}


def test_a_lane_on_a_limited_account_is_not_lane_stale_while_the_limit_holds(repo, tmp_path):
    _wave(repo, tmp_path)
    ignore = (("cloud-a1", "account-limited"), ("cloud-a2", "account-limited"))
    result = ww.run(repo, _BATCH, gh_run=_quiet_gh(101, 102, 201), ignore_events=ignore)
    assert result["event"] == "lane-stale"
    assert _stale_ids(result) == ["cloud-b1"]


def test_without_a_limit_the_same_quiet_lanes_are_lane_stale(repo, tmp_path):
    _wave(repo, tmp_path, a_resets_in=-10)
    result = ww.run(repo, _BATCH, gh_run=_quiet_gh(101, 102, 201))
    assert result["event"] == "lane-stale"
    assert _stale_ids(result) == ["cloud-a1", "cloud-a2", "cloud-b1"]


def test_ignoring_every_named_lane_suppresses_the_event_and_one_lane_leaves_the_rest(repo, tmp_path):
    _wave(repo, tmp_path)
    gh = _quiet_gh(101, 102, 201)
    one = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(("cloud-a1", "account-limited"),))
    assert one["event"] == "account-limited"
    assert one["launchIds"] == ["cloud-a2"] and one["launchId"] == "cloud-a2"
    assert one["accounts"][0]["launchIds"] == ["cloud-a2"]
    both = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(
        ("cloud-a1", "account-limited"), ("cloud-a2", "account-limited")))
    assert both["event"] != "account-limited"
    elsewhere = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(
        ("cloud-b1", "account-limited"), ("cloud-a1", "lane-stale")))
    assert elsewhere["event"] == "account-limited" and elsewhere["launchIds"] == ["cloud-a1", "cloud-a2"]


def test_an_account_limited_ignore_is_accepted_on_the_cli_and_in_the_arguments(repo):
    assert ww._parse_ignore_event_cli("cloud-a1:account-limited") == ("cloud-a1", "account-limited")
    assert ww._parse_ignore_event_cli("a:b:account-limited") == ("a:b", "account-limited")
    assert ww._validate_ignore_events((("cloud-a1", "account-limited"),), _BATCH) is None


def test_a_reading_that_is_not_ok_is_no_reading_and_records_no_degradation(repo, tmp_path):
    _wave(repo, tmp_path)
    path, _why = cr._state_path(repo, None)
    open(path, "w").write("{not json")
    result = ww.run(repo, _BATCH, gh_run=_quiet_gh(101, 102, 201))
    assert result["event"] == "lane-stale"
    assert _stale_ids(result) == ["cloud-a1", "cloud-a2", "cloud-b1"]
    assert result["degraded"] == []


def test_a_lane_with_no_recorded_account_directory_is_not_read(repo, tmp_path, monkeypatch):
    _wave(repo, tmp_path)
    _add_cloud_lane(repo, "cloud-c1", 301)  # a record from before the account directory was recorded
    seen = []
    real = cr.account_limit
    monkeypatch.setattr(cr, "account_limit", lambda root, config_dir, **kw: (
        seen.append(config_dir), real(root, config_dir, **kw))[1])
    result = ww.run(repo, _BATCH, gh_run=_quiet_gh(101, 102, 201, 301))
    assert result["event"] == "account-limited"
    assert "cloud-c1" not in result["launchIds"]
    assert sorted(seen) == sorted(set(seen)) and "" not in seen and len(seen) == 2


def test_the_loop_exits_on_the_event_instead_of_passing_it_over(repo, tmp_path):
    _wave(repo, tmp_path)
    assert ww.EVENT_ACCOUNT_LIMITED not in ww.BENIGN_EVENTS
    result = ww.loop(repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=30,
                     gh_run=_quiet_gh(101, 102, 201))
    assert result["event"] == "account-limited"
    assert result["arms"] == 1 and result["passedOverCount"] == 0


def test_the_loop_exits_on_account_limited():
    assert ww._loop_exits_on({"ok": True, "event": "account-limited", "launchIds": ["a"]}) is True
    assert ww._loop_exits_on({"ok": True, "event": "timer"}) is False


def test_the_event_is_in_every_set_that_has_to_know_it():
    event = ww.EVENT_ACCOUNT_LIMITED
    assert event == "account-limited"
    assert event in ww.EVENTS and event in ww.ATTENTION_EVENTS
    assert event not in ww.BENIGN_EVENTS and event not in ww.LANE_ENDING_EVENTS
    assert event in ww._SUPPRESSIBLE_EVENTS
    assert event in ww._EVENT_PAYLOAD_BUILDERS
    order = ww.EVENT_PRECEDENCE
    assert order.index(event) == order.index(ww.EVENT_BUILDER_NOTE) + 1
