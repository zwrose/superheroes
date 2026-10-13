# plugins/superheroes/lib/tests/test_cloud_setup_gardening.py
"""Conformance: the gardening pass's reviewer-pass line, read from every setup record in the project
store. Every record is written through `record_check` under a temporary store; the clock is a parameter."""
import datetime
import json
import os
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_setup as CS  # noqa: E402

ACCOUNT = "acct-fixture-one"
OTHER_ACCOUNT = "acct-fixture-two"
STAMP = "sha256:" + "ab" * 32
TODAY = datetime.date(2026, 10, 16)
RENEW = "Run the pass command and paste the new pass into the environment."
UNREADABLE = "Cloud reviewer pass: the setup record could not be read."


def _record(w, account, lapses):
    got = CS.record_check(
        w[0], root=w[1], account=account, environment="env-fixture-one", plugin_version="1.2.3",
        picks_up_version=False, calibration_stamp=STAMP, calibration_date="2026-10-01",
        pass_lapses=lapses, checked_at="2026-10-01")
    assert got["action"] == "written", got


def _lapsing_in(days):
    return (TODAY + datetime.timedelta(days=days)).isoformat()


@pytest.fixture
def w(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    return str(repo), str(tmp_path / "store")


def _lines(w, next_pass_days=7):
    return CS.gardening_lines(w[0], next_pass_days, today=TODAY, root=w[1])


def test_a_pass_that_will_not_last_to_the_next_gardening_pass_is_marked_renew_now(w):
    _record(w, ACCOUNT, _lapsing_in(3))
    [got] = _lines(w, next_pass_days=7)
    assert got["mark"] == "Renew now" and got["account"] == ACCOUNT
    assert "Run the pass command" in got["line"] and "paste the new pass into the environment" in got["line"]
    assert got["line"] == ("Cloud reviewer pass: 3 days left, lapses 19 Oct. It won't last to the next "
                           "gardening pass. " + RENEW)


def test_a_pass_with_time_to_spare_says_there_is_nothing_to_do(w):
    _record(w, ACCOUNT, "2026-10-25")
    assert _lines(w) == [{"account": ACCOUNT, "mark": None,
                          "line": "Cloud reviewer pass: 9 days left, lapses 25 Oct. Nothing to do."}]


def test_the_threshold_is_the_next_pass_days_inclusive(w):
    _record(w, ACCOUNT, _lapsing_in(7))
    assert _lines(w)[0]["mark"] == "Renew now"
    _record(w, ACCOUNT, _lapsing_in(8))
    [got] = _lines(w)
    assert got["mark"] is None and got["line"].endswith("Nothing to do.")


def test_one_day_left_is_singular(w):
    _record(w, ACCOUNT, _lapsing_in(1))
    [got] = _lines(w)
    assert got["mark"] == "Renew now" and "1 day left, lapses 17 Oct." in got["line"] and "1 days" not in got["line"]


def test_a_pass_lapsing_today_or_already_lapsed_says_lapsed(w):
    for days, lapsed in ((0, "16 Oct"), (-4, "12 Oct")):
        _record(w, ACCOUNT, _lapsing_in(days))
        assert _lines(w) == [{"account": ACCOUNT, "mark": "Renew now",
                              "line": "Cloud reviewer pass: lapsed %s. %s" % (lapsed, RENEW)}]


def test_every_accounts_record_in_the_store_gets_a_line(w):
    _record(w, ACCOUNT, _lapsing_in(30))
    _record(w, OTHER_ACCOUNT, _lapsing_in(2))
    assert {g["account"]: g["mark"] for g in _lines(w)} == {ACCOUNT: None, OTHER_ACCOUNT: "Renew now"}


def test_a_project_with_no_cloud_setup_sees_nothing(w):
    assert _lines(w) == []
    os.makedirs(os.path.dirname(CS.record_path(w[0], "x", w[1])))
    assert _lines(w) == []


def test_a_corrupt_record_gives_the_unreadable_line(w):
    _record(w, ACCOUNT, _lapsing_in(30))
    directory = os.path.dirname(CS.record_path(w[0], ACCOUNT, w[1]))
    for name, text in (("bad.json", "{not json"), ("list.json", "[1]")):
        with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    with open(CS.record_path(w[0], OTHER_ACCOUNT, w[1]), "w", encoding="utf-8") as fh:
        json.dump({"account": OTHER_ACCOUNT, "schema": "nope"}, fh)
    got = _lines(w)
    assert len(got) == 4
    assert [g["line"] for g in got].count(UNREADABLE) == 3
    assert {"account": OTHER_ACCOUNT, "mark": None, "line": UNREADABLE} in got
    assert [g for g in got if g["account"] == ACCOUNT][0]["line"].endswith("Nothing to do.")


def test_the_cli_prints_the_lines_and_a_bad_today_exits_1(w, capsys):
    _record(w, ACCOUNT, "2026-10-25")
    base = ["gardening", "--cwd", w[0], "--root", w[1]]
    assert CS.main(base + ["--today", "2026-10-16", "--next-pass-days", "7"]) == 0
    assert json.loads(capsys.readouterr().out) == {"lines": [
        {"account": ACCOUNT, "mark": None, "line": "Cloud reviewer pass: 9 days left, lapses 25 Oct. Nothing to do."}]}
    assert CS.main(base + ["--today", "2026-10-16", "--next-pass-days", "10"]) == 0
    assert json.loads(capsys.readouterr().out)["lines"][0]["mark"] == "Renew now"
    for bad in ("2026-13-01", "tomorrow", ""):
        assert CS.main(base + ["--today", bad, "--next-pass-days", "7"]) == 1
        assert json.loads(capsys.readouterr().out) == {"reason": "today-invalid"}


def test_the_cli_refuses_a_missing_or_non_positive_next_pass_days(w, capsys):
    _record(w, ACCOUNT, "2026-10-25")
    base = ["gardening", "--cwd", w[0], "--root", w[1], "--today", "2026-10-16"]
    for extra in ([], ["--next-pass-days", "0"], ["--next-pass-days", "-3"]):
        assert CS.main(base + extra) == 1
        assert json.loads(capsys.readouterr().out) == {"reason": "next-pass-days-invalid"}


def test_a_failed_check_marker_makes_the_saved_date_stale_and_is_not_a_record(w):
    _record(w, ACCOUNT, "2026-10-25")
    import cloud_check
    marker = cloud_check.failed_check_path(w[0], ACCOUNT, w[1])
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump({"schema": "cloud-check-failed/1", "account": ACCOUNT, "failedParts": ["reviewer"]}, fh)
    [got] = _lines(w)
    assert got["account"] == ACCOUNT and got["mark"] == "Renew now"
    assert "last reviewer check failed" in got["line"] and "Nothing to do" not in got["line"]
    assert RENEW in got["line"]


def test_a_failed_check_marker_without_a_reviewer_failure_names_its_parts_and_does_not_ask_for_renewal(w):
    import cloud_check
    _record(w, ACCOUNT, "2026-10-25")
    with open(cloud_check.failed_check_path(w[0], ACCOUNT, w[1]), "w", encoding="utf-8") as fh:
        json.dump({"schema": "cloud-check-failed/1", "account": ACCOUNT, "failedParts": ["version"]}, fh)
    [got] = _lines(w)
    assert got["mark"] is None
    assert "failed on version" in got["line"] and "run the setup check again" in got["line"].lower()
    assert "renew" not in got["line"].lower() and "reviewer check failed" not in got["line"]


def test_an_unreadable_setup_directory_is_one_unreadable_line(w, monkeypatch):
    _record(w, ACCOUNT, "2026-10-25")

    def _denied(path):
        raise PermissionError("denied")

    monkeypatch.setattr(os, "listdir", _denied)
    assert _lines(w) == [{"account": None, "mark": None, "line": UNREADABLE}]
