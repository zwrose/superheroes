"""A limit resetting during the final account read must prevent spawning."""
from test_i2272_launcher import (
    ADOPTED,
    L,
    RESETS_AT,
    TOKEN_UNREAD,
    _adopt,
    _adopted_repo,
    _lanes,
    _seed_lane,
    account,
    comments,
)
from test_launcher_cloud import _isolated  # noqa: F401 (_isolated is an autouse fixture)


def test_reset_during_final_account_read_prevents_cloud_spawn(
    tmp_path, monkeypatch, account, comments,
):
    # axis: stop authorization must still hold after the final account-record
    # read completes; crossing its reset during that read must refuse spawning.
    repo = _adopted_repo(tmp_path)
    _seed_lane(repo, premise_extra={"adoptsBranch": ADOPTED})
    account.limited_until()
    # Pin time before reset and advance it inside the final owned read only.
    # Actual disk latency, clock skew and concurrent scheduling are unobservable.
    clock = {"now": RESETS_AT - 60}
    monkeypatch.setattr(L, "_now_fn", lambda: clock["now"])
    final_check_active = [False]
    final_reads = []
    real_final_check = L._limit_expired_refusal
    account_answer = account.answer

    def final_check(*args, **kwargs):
        final_check_active[0] = True
        try:
            return real_final_check(*args, **kwargs)
        finally:
            final_check_active[0] = False

    def account_read_crossing_reset(config_dir, now):
        reading = account_answer(config_dir, now)
        if final_check_active[0]:
            final_reads.append(now)
            clock["now"] = RESETS_AT
        return reading

    monkeypatch.setattr(L, "_limit_expired_refusal", final_check)
    account.answer = account_read_crossing_reset
    result, calls = _adopt(repo, tmp_path, branch=ADOPTED)

    assert final_reads, "the final account-record reread was not exercised"
    assert comments.calls, "the supersession notice was not read"
    assert clock["now"] == RESETS_AT
    assert result["ok"] is False, result
    assert result["reason"] == TOKEN_UNREAD, result
    assert result["failedRead"] == "limit-expired"
    assert calls == []
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True
    assert lane["started"] is False
