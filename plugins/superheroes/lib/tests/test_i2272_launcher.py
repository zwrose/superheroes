"""The launcher's part of #2272: a usage limit stands in for a session listing, the deleted-branch
exemption is gone, the limit is read again right before anything spawns, and an adoption launches
in the cloud from a checkout at its adopted head.

`cloud_relay.account_limit` is another order's: these tests replace it with a fake (the attribute
may not exist, so `raising=False`) and replace the launcher's clock, so nothing here reads a relay
or waits. Everything else is the real launcher over throwaway repositories with a bare remote.
"""
import json
import os

import pytest

import cloud_relay

from test_adopt_original_session import (  # noqa: F401  (first_pr is a fixture)
    ADOPTED,
    LANE_ID,
    LANE_STARTED_TS,
    SESSION_ID,
    TOKEN_LIVE,
    TOKEN_UNREAD,
    L,
    _adopt,
    _adopted_repo,
    _adoption,
    _assert_refused_cloud_lane,
    _delete_remote_branch,
    _fixture,
    _proceeds,
    _refused_unread,
    _seed_lane as _seed_base_lane,
    _write_listing,
    first_pr,
)
from test_launcher import _all_checks, _make_spawn_fn, _valid_premise
from test_launcher_cloud import (  # noqa: F401  (_isolated is an autouse fixture)
    _cloud_repo,
    _fake_spawn,
    _git,
    _isolated,
    _lanes,
    _launch,
)
from test_launcher_cloud_checkout import OFF_BASE, _branch, _commit

LANE_B = "lane-b"
LANE_B_SESSION = "session_01FixtureLaneB000000000"
LANE_B_TITLE = "issue-656-fixturelane00000b"
# One account reading: recorded an hour after the lanes started, resetting two hours after that.
RECORDED_AT = LANE_STARTED_TS + 3600
RESETS_AT = LANE_STARTED_TS + 10800
NOW = LANE_STARTED_TS + 7200


def _seed_lane(repo, launch_id=LANE_ID, *, stamped=True, premise_extra=None, **kw):
    """The earlier cloud lane of test_adopt_original_session, its reserved premise carrying the launcher's
    `standDown: 1` stamp unless `stamped` is False (a lane launched before the stand-down check existed)."""
    extra = dict(premise_extra or {})
    if stamped:
        extra["standDown"] = 1
    _seed_base_lane(repo, launch_id, premise_extra=extra, **kw)


class _Account:
    """The fake `cloud_relay.account_limit`: what it answers, and every call made to it."""

    def __init__(self):
        self.calls = []
        self.answer = None

    def limited_until(self, resets_at=RESETS_AT, recorded_at=RECORDED_AT):
        """The account has a limit recorded at `recorded_at`; it holds while `now < resets_at`."""
        def answer(config_dir, now):
            return {
                "ok": True, "limited": now < resets_at, "configDir": config_dir,
                "relay": "relay-a", "limitType": "five_hour",
                "resetsAt": resets_at, "recordedAt": recorded_at,
            }
        self.answer = answer

    def no_reading(self):
        self.answer = lambda config_dir, now: {"ok": False, "reason": "config-dir-invalid"}

    def __call__(self, repo_root, config_dir, *, env=None, now=None):
        self.calls.append((config_dir, now))
        return self.answer(config_dir, now)


@pytest.fixture(autouse=True)
def account(monkeypatch):
    fake = _Account()
    fake.no_reading()
    monkeypatch.setattr(cloud_relay, "account_limit", fake, raising=False)
    monkeypatch.setattr(L, "_now_fn", lambda: NOW)
    return fake


def _check(repo, listing=None):
    return L._original_session_refusal(
        repo, 656, {"adoptsBranch": ADOPTED}, listing, dict(os.environ),
    )


def _two_bound_lanes(repo, **second):
    """A handed-back lane and a died one, both on account A (the seeded configDir), both bound to the adopted branch."""
    bound = {"adoptsBranch": ADOPTED}
    _seed_lane(repo, LANE_ID, premise_extra=bound)
    _seed_lane(
        repo, LANE_B, session_id=LANE_B_SESSION, title=LANE_B_TITLE, outcome="park",
        premise_extra=bound, **second,
    )


# --- 1. a lane on a limited account needs no listing while the limit holds --------------------


def test_two_lanes_on_a_limited_account_need_no_listing(tmp_path, account):
    # axis: lanes that started before a limit recorded on their account need no session read while the limit holds, and the account is read once per pass — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    assert _check(repo) is None
    assert account.calls == [("/cfg/acct", NOW)]
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _proceeds(result, calls)


# --- 2-3. the limit has to hold, and has to postdate the lane ---------------------------------


def test_a_limit_that_has_passed_leaves_both_lanes_needing_a_listing(tmp_path, account, monkeypatch):
    # axis: a limit whose reset time has passed (the reading says not limited) gives no relief, so both lanes need a listing — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    monkeypatch.setattr(L, "_now_fn", lambda: RESETS_AT)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID, LANE_B]


def test_a_limit_recorded_before_a_lane_started_leaves_that_lane_needing_a_listing(tmp_path, account):
    # axis: a limit recorded before a lane started says nothing about that lane, so it needs a listing while the older lane is relieved — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo, started_ts=RECORDED_AT + 60)
    account.limited_until()
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_B]


def test_a_limit_recorded_at_the_instant_a_lane_started_does_not_relieve_it(tmp_path, account):
    # axis: the limit must be recorded strictly after the lane started — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    account.limited_until(recorded_at=LANE_STARTED_TS)
    reason, detail = _check(repo)
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-not-given", [LANE_ID],
    )


def test_a_limited_lane_whose_premise_lacks_the_stand_down_stamp_still_needs_a_listing(tmp_path, account):
    # axis: a lane launched before the stand-down check existed cannot stand down on waking, so the limit gives it no relief; a stamped lane beside it is still relieved — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    bound = {"adoptsBranch": ADOPTED}
    _seed_lane(repo, LANE_ID, premise_extra=bound)
    _seed_lane(
        repo, LANE_B, session_id=LANE_B_SESSION, title=LANE_B_TITLE, outcome="park",
        premise_extra=bound, stamped=False,
    )
    account.limited_until()
    reason, detail = _check(repo)
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-not-given", [LANE_B],
    )


@pytest.mark.parametrize("stamp", [0, 2, True, "1", None])
def test_only_a_stand_down_stamp_of_one_relieves_a_limited_lane(tmp_path, account, stamp):
    # axis: the stamp is the integer 1 exactly — a bool, a string or another number is no stamp — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, stamped=False, premise_extra={"adoptsBranch": ADOPTED, "standDown": stamp})
    account.limited_until()
    reason, detail = _check(repo)
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-not-given", [LANE_ID],
    )


def test_recovery_strips_the_stand_down_stamp_from_a_successor_premise():
    import cloud_recover
    assert "standDown" in cloud_recover._LAUNCHER_STAMPED


def test_orchestration_says_an_older_lane_still_needs_the_session_read():
    path = os.path.join(os.path.dirname(L.__file__), "..", "skills", "showrunner", "reference", "orchestration.md")
    with open(path, encoding="utf-8") as fh:
        text = " ".join(fh.read().split())
    assert ("A lane launched before the stand-down check existed (its reserved premise lacks the launcher's "
            "`standDown` stamp) still needs the session read, limit or not.") in text


@pytest.mark.parametrize("reading", [
    {"ok": False, "reason": "config-dir-invalid"},
    {"ok": True, "limited": False, "recordedAt": RECORDED_AT, "resetsAt": RESETS_AT},
    {"ok": True, "limited": "yes", "recordedAt": RECORDED_AT, "resetsAt": RESETS_AT},
    {"ok": True, "limited": True, "recordedAt": None, "resetsAt": RESETS_AT},
    {"ok": True, "limited": True, "recordedAt": True, "resetsAt": RESETS_AT},
    {"ok": True, "limited": True, "recordedAt": "late", "resetsAt": RESETS_AT},
    {"ok": 1, "limited": True, "recordedAt": RECORDED_AT, "resetsAt": RESETS_AT},
    {"limited": True, "recordedAt": RECORDED_AT, "resetsAt": RESETS_AT},
    None,
], ids=[
    "refusal", "not-limited", "limited-not-a-bool", "no-recorded-at", "recorded-at-a-bool",
    "recorded-at-a-string", "ok-not-a-bool", "no-ok", "not-a-dict",
])
def test_anything_but_a_limited_reading_with_a_recorded_time_gives_no_relief(tmp_path, account, reading):
    # axis: only `ok` true, `limited` true and a numeric `recordedAt` count as a limit reading; every other answer is no reading — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    account.answer = lambda config_dir, now: reading
    reason, detail = _check(repo)
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-not-given", [LANE_ID],
    )


def test_a_lane_with_no_started_time_gets_no_relief_from_a_limit(tmp_path, account, monkeypatch):
    # axis: a lane whose started time is not a number cannot be placed before the limit, so it needs a listing — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    account.limited_until()
    real_fold = L.ll.fold

    def fold_without_started_ts(records):
        folded = real_fold(records)
        for info in folded["launches"].values():
            info["startedTs"] = None
        return folded

    monkeypatch.setattr(L.ll, "fold", fold_without_started_ts)
    reason, detail = _check(repo)
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-not-given", [LANE_ID],
    )


def test_a_lane_with_no_config_dir_gets_no_relief_and_asks_no_account(tmp_path, account, monkeypatch):
    # axis: a lane with no recorded configDir has no account to read, so it needs a listing and account_limit is not asked — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    account.limited_until()
    real_fold = L.ll.fold

    def fold_without_config_dir(records):
        folded = real_fold(records)
        for info in folded["launches"].values():
            info["configDir"] = None
        return folded

    monkeypatch.setattr(L.ll, "fold", fold_without_config_dir)
    reason, detail = _check(repo)
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-not-given", [LANE_ID],
    )
    assert account.calls == []


# --- 4. a limited lane is still refused when a listing shows it live --------------------------


def test_a_limited_lane_whose_session_the_listing_shows_live_refuses_live(tmp_path, account):
    # axis: a limit relieves a lane of needing a listing but a supplied listing that shows its session live still refuses — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    account.limited_until()
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"), branch=ADOPTED)
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert [s["launchId"] for s in result["originalSessions"]] == [LANE_ID]
    assert calls == []


def test_a_handed_back_lane_with_no_limit_reading_and_a_live_listing_still_refuses_live(
    tmp_path, account, first_pr,
):
    # axis: #2131's case unchanged — with no limit reading, a handed-back lane the listing shows live refuses live
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, LANE_ID)
    first_pr(LANE_STARTED_TS - 3600)
    result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"))
    _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")
    assert [s["launchId"] for s in result["originalSessions"]] == [LANE_ID]
    assert calls == []


def test_a_limited_lane_absent_from_a_supplied_listing_is_skipped(tmp_path, account):
    # axis: a limited lane a supplied listing does not show is skipped, never unproven, so the listing's incompleteness does not refuse it — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    account.limited_until()
    assert _check(repo, _fixture("get_session_unrelated.json")) is None
    account.no_reading()
    reason, detail = _check(repo, _fixture("get_session_unrelated.json"))
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-incomplete", [LANE_ID],
    )


def test_a_limited_lane_does_not_hide_an_unproven_one_beside_it(tmp_path, account, monkeypatch):
    # axis: a limited lane leaves the listing check to the others, so a lane on another account that reads no limit and that no listing covers still refuses unread
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    limited_answer = account.answer
    account.answer = lambda config_dir, now: (
        limited_answer(config_dir, now) if config_dir == "/cfg/acct"
        else {"ok": False, "reason": "config-dir-invalid"}
    )
    real_fold = L.ll.fold

    def lane_b_on_account_b(records):
        folded = real_fold(records)
        folded["launches"][LANE_B]["configDir"] = "/cfg/other"
        return folded

    monkeypatch.setattr(L.ll, "fold", lane_b_on_account_b)
    reason, detail = _check(repo, _fixture("get_session_unrelated.json"))
    assert (reason, detail["failedRead"], detail["launchIds"]) == (
        TOKEN_UNREAD, "listing-incomplete", [LANE_B],
    )
    assert sorted(config for config, _ in account.calls) == ["/cfg/acct", "/cfg/other"]


# --- 5. the deleted-branch exemption is gone --------------------------------------------------


def test_a_bound_lane_whose_branch_is_gone_with_no_listing_refuses_unread_naming_the_helper_read(
    tmp_path, first_pr,
):
    # axis: a lane bound to the adopted branch needs a session read whether or not its branch is still on origin — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    _delete_remote_branch(repo)
    first_pr(None)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID]
    assert "cloud helper" in result["remedy"] and "get_session" in result["remedy"]
    assert "cloud_relay.py limit" in result["remedy"]


@pytest.mark.parametrize("row", [
    {"id": SESSION_ID, "session_status": "SESSION_STATUS_ARCHIVED",
     "status_bucket": "SESSION_STATUS_BUCKET_COMPLETED", "archived": True},
    {"id": SESSION_ID, "session_status": "SESSION_STATUS_IDLE",
     "status_bucket": "SESSION_STATUS_BUCKET_FAILED", "archived": False},
], ids=["archived", "failed"])
def test_a_bound_lane_whose_branch_is_gone_proceeds_on_a_get_session_row_showing_it_ended(
    tmp_path, first_pr, row,
):
    # axis: a bound lane whose branch is gone is cleared by the session read a cloud helper posts, a bare get_session object carrying only id, session_status, status_bucket and archived — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
    _delete_remote_branch(repo)
    first_pr(None)
    listing = _write_listing(tmp_path, row)
    assert set(json.load(open(listing))) == {"id", "session_status", "status_bucket", "archived"}
    result, calls = _adopt(repo, tmp_path, listing, branch=ADOPTED)
    _proceeds(result, calls)


# --- 5b. the limit is read again right before anything spawns ---------------------------------


class _Expiring:
    """A clock that reads before the reset time on its first call and at the reset time on every later one."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return RESETS_AT - 60 if self.calls == 1 else RESETS_AT


def _terminalized_at_original_session(repo, result):
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True
    assert lane["terminalKind"] == "refused"
    assert lane["started"] is False


def test_a_limit_that_expires_before_the_cloud_spawn_refuses_and_spawns_nothing(
    tmp_path, account, monkeypatch,
):
    # axis: the limit read by the first original-session check is read again right before the cloud command, so a limit that expired in between refuses unread and terminalizes the lane — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    clock = _Expiring()
    monkeypatch.setattr(L, "_now_fn", clock)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    _refused_unread(repo, result, calls, "listing-not-given")
    assert result["launchIds"] == [LANE_ID, LANE_B]
    assert clock.calls == 2
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
    _terminalized_at_original_session(repo, result)
    assert calls == []


def _local_adoption(repo, tmp_path, spawn_fn):
    return L.launch_build(
        repo, 656, _adoption(repo, ADOPTED), _all_checks(), str(tmp_path / "logs"),
        spawn_fn=spawn_fn, settle_seconds=0.2, backoff_seconds=(0,),
    )


def test_a_limit_that_expires_before_the_local_spawn_refuses_and_spawns_nothing(
    tmp_path, account, monkeypatch,
):
    # axis: the limit read by the first original-session check is read again right before the local spawn, so a limit that expired in between refuses unread and terminalizes the lane — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    clock = _Expiring()
    monkeypatch.setattr(L, "_now_fn", clock)
    spawned = []
    delegate = _make_spawn_fn("sleep")

    def recording_spawn(*args, **kwargs):
        spawned.append(args)
        return delegate(*args, **kwargs)

    result = _local_adoption(repo, tmp_path, recording_spawn)
    assert result["ok"] is False
    assert result["reason"] == TOKEN_UNREAD
    assert result["failedRead"] == "listing-not-given"
    assert result["launchIds"] == [LANE_ID, LANE_B]
    assert clock.calls == 2
    _terminalized_at_original_session(repo, result)
    assert spawned == []


def test_a_limit_that_expires_before_a_local_retry_refuses_the_retry(tmp_path, account, monkeypatch):
    # axis: the limit is read again before every local spawn attempt, a retry after a spawn OSError included — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    reads = []

    def clock():
        reads.append(1)
        return RESETS_AT - 60 if len(reads) <= 3 else RESETS_AT

    monkeypatch.setattr(L, "_now_fn", clock)
    spawned = []

    def failing_spawn(*args, **kwargs):
        spawned.append(args)
        raise OSError("spawn failed")

    result = _local_adoption(repo, tmp_path, failing_spawn)
    assert result["ok"] is False
    assert result["reason"] == TOKEN_UNREAD
    assert len(reads) == 4
    assert len(spawned) == 1
    _terminalized_at_original_session(repo, result)


class _Crossing:
    """A clock that reads before the reset time until `cross()` is called, and at the reset time after."""

    def __init__(self):
        self.now = RESETS_AT - 60

    def __call__(self):
        return self.now

    def cross(self):
        self.now = RESETS_AT


def test_a_limit_that_expires_during_the_final_cloud_checkout_lookup_refuses_and_spawns_nothing(
    tmp_path, account, monkeypatch,
):
    # axis: the limit the re-check relied on is compared with the clock right before the cloud command with no remote read, so a reset during the final remote lookup refuses limit-expired and spawns nothing — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    clock = _Crossing()
    monkeypatch.setattr(L, "_now_fn", clock)
    real = L._cloud_start_refusal
    real_check = L._original_session_refusal
    rechecked = []
    lookups = []

    def check_marks(*args, **kwargs):
        result = real_check(*args, **kwargs)
        rechecked.append(1)
        return result

    def lookup_then_cross(*args, **kwargs):
        result = real(*args, **kwargs)
        if len(rechecked) >= 2:  # the final lookup, after the pre-spawn re-check
            lookups.append(1)
            clock.cross()
        return result

    monkeypatch.setattr(L, "_original_session_refusal", check_marks)
    monkeypatch.setattr(L, "_cloud_start_refusal", lookup_then_cross)
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
    assert lookups
    _refused_unread(repo, result, calls, "limit-expired")
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
    _terminalized_at_original_session(repo, result)
    assert calls == []


def test_a_limit_that_expires_during_the_final_local_session_lookup_refuses_and_spawns_nothing(
    tmp_path, account, monkeypatch,
):
    # axis: the limit the re-check relied on is compared with the clock right before the local spawn with no remote read, so a reset during the check's own lookup refuses limit-expired and spawns nothing — see bite-proof record i2272_launcher
    repo = _adopted_repo(tmp_path)
    _two_bound_lanes(repo)
    account.limited_until()
    clock = _Crossing()
    monkeypatch.setattr(L, "_now_fn", clock)
    real = L._original_session_refusal
    seen = []

    def check_then_cross(*args, **kwargs):
        result = real(*args, **kwargs)
        seen.append(result)
        if len(seen) == 2:  # the pre-spawn re-check; the first is the premise check
            clock.cross()
        return result

    monkeypatch.setattr(L, "_original_session_refusal", check_then_cross)
    spawned = []
    delegate = _make_spawn_fn("sleep")

    def recording_spawn(*args, **kwargs):
        spawned.append(args)
        return delegate(*args, **kwargs)

    result = _local_adoption(repo, tmp_path, recording_spawn)
    assert seen == [None, None]
    assert result["ok"] is False
    assert result["reason"] == TOKEN_UNREAD
    assert result["failedRead"] == "limit-expired"
    _terminalized_at_original_session(repo, result)
    assert spawned == []


def test_the_pre_spawn_recheck_changes_nothing_for_a_launch_that_adopts_nothing(tmp_path, account):
    # axis: a launch whose premise has no adoptsBranch is none of the original-session check's business, before or after the reservation
    repo = _cloud_repo(tmp_path)
    _seed_lane(repo, LANE_ID)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _proceeds(result, calls)
    assert account.calls == []


# --- 6. an adoption launches from a checkout at its adopted head ------------------------------


def _adoption_checkout(tmp_path):
    """A checkout one commit past its base, on a branch the remote holds at that commit; the base is on the remote too."""
    repo = _cloud_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    head = _commit(repo, "adopted.txt")
    branch = _branch(repo)
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/%s" % branch)
    return repo, base, head, branch


def _stamped(base, **more):
    return dict({"baseCommit": base}, **more)


def test_an_adoption_checkout_at_its_adopted_head_passes_the_checkout_check(tmp_path):
    # axis: an adoption is checked against its adopted head, not its base, so a checkout at that head whose remote tip is the head passes — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    stamped = _stamped(base, adoptsBranch=branch, adoptsHead=head)
    assert L._cloud_start_refusal(repo, stamped, dict(os.environ)) is None


def test_the_same_checkout_for_a_launch_that_adopts_nothing_is_off_base(tmp_path):
    # axis: a launch that is not an adoption keeps the rule that the checkout sits on its base commit, and the refusal says so — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    reason, detail = L._cloud_start_refusal(repo, _stamped(base), dict(os.environ))
    assert reason == OFF_BASE
    assert detail["checkedAgainst"] == "baseCommit"
    assert detail["baseCommit"] == base
    assert detail["checkoutHead"] == head


def test_an_adopted_head_without_an_adopted_branch_is_still_checked_against_the_base(tmp_path):
    # axis: only a premise that carries adoptsBranch is checked against adoptsHead; a stray adoptsHead alone keeps the base rule — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    reason, detail = L._cloud_start_refusal(
        repo, _stamped(base, adoptsHead=head), dict(os.environ),
    )
    assert reason == OFF_BASE
    assert detail["checkedAgainst"] == "baseCommit"


@pytest.mark.parametrize("adopted_head", ["not-a-sha", "ab" * 10, None, 7])
def test_an_adoption_whose_head_is_not_a_full_sha_is_checked_against_the_base(tmp_path, adopted_head):
    # axis: the adopted head replaces the base as the checkout target only when it is a 40-hex sha — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    reason, detail = L._cloud_start_refusal(
        repo, _stamped(base, adoptsBranch=branch, adoptsHead=adopted_head), dict(os.environ),
    )
    assert reason == OFF_BASE
    assert detail["checkedAgainst"] == "baseCommit"


def test_an_adoption_checkout_off_its_adopted_head_refuses_and_says_which_it_checked(tmp_path):
    # axis: an adoption whose checkout is not at its adopted head refuses off-base against adoptsHead, with the base commit kept in the detail — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    _git(repo, "checkout", "-q", "-B", branch, base)
    reason, detail = L._cloud_start_refusal(
        repo, _stamped(base, adoptsBranch=branch, adoptsHead=head), dict(os.environ),
    )
    assert reason == OFF_BASE
    assert detail["checkedAgainst"] == "adoptsHead and baseCommit"
    assert detail["baseCommit"] == base
    assert detail["checkoutHead"] == base


def test_an_adoption_checkout_at_its_base_passes_the_checkout_check(tmp_path):
    # axis: an adoption passes from a checkout at its adopted head or at its base, each checked whole — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    _git(repo, "checkout", "-q", "-B", branch, base)
    _git(repo, "push", "-q", "-f", "origin", "HEAD:refs/heads/%s" % branch)
    stamped = _stamped(base, adoptsBranch=branch, adoptsHead=head)
    assert L._cloud_start_refusal(repo, stamped, dict(os.environ)) is None


def test_an_adoption_checkout_at_neither_commit_refuses_with_the_adopted_head_reason(tmp_path):
    # axis: an adoption refuses only when both the adopted head and the base refuse, and names both in checkedAgainst — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    other = _commit(repo, "elsewhere.txt")
    reason, detail = L._cloud_start_refusal(
        repo, _stamped(base, adoptsBranch=branch, adoptsHead=head), dict(os.environ),
    )
    assert reason == OFF_BASE
    assert "adoptsHead" in detail["checkedAgainst"] and "baseCommit" in detail["checkedAgainst"]
    assert detail["checkoutHead"] == other


def test_an_adoption_launch_from_a_checkout_at_its_adopted_head_launches_in_the_cloud(tmp_path):
    # axis: the whole cloud launch of an adoption whose base is an ancestor of its adopted head goes ahead from a checkout at that head — see bite-proof record i2272_launcher
    repo, base, head, branch = _adoption_checkout(tmp_path)
    calls = []
    result = _launch(
        repo, tmp_path, _fake_spawn(calls=calls),
        premise=_valid_premise(repo, baseCommit=base, adoptsBranch=branch, adoptsHead=head),
    )
    _proceeds(result, calls)
