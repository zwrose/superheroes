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
RENEW = CS._RENEW
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


def test_a_pass_already_lapsed_says_lapsed(w):
    _record(w, ACCOUNT, _lapsing_in(-4))
    assert _lines(w) == [{"account": ACCOUNT, "mark": "Renew now",
                          "line": "Cloud reviewer pass: lapsed 12 Oct. %s" % RENEW}]


def test_a_pass_lapsing_today_is_live_by_the_readiness_rule_and_says_it_lapses_today(w):
    import cloud_check
    _record(w, ACCOUNT, _lapsing_in(0))
    assert cloud_check._lapses_ok(_lapsing_in(0), TODAY)
    assert _lines(w) == [{"account": ACCOUNT, "mark": "Renew now",
                          "line": "Cloud reviewer pass: lapses today, 16 Oct. It won't last to the next "
                                  "gardening pass. %s" % RENEW}]


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
    assert got["line"].endswith("Cloud builds stay off until a check passes. Run the setup check again.")


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


def test_without_a_today_the_utc_date_is_used(w, monkeypatch):
    class _Clock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is datetime.timezone.utc
            return cls(2026, 10, 16, 23, 30, tzinfo=tz)

    monkeypatch.setattr(CS.datetime, "datetime", _Clock)
    _record(w, ACCOUNT, "2026-10-19")
    [got] = CS.gardening_lines(w[0], 7, root=w[1])
    assert got["line"].startswith("Cloud reviewer pass: 3 days left, lapses 19 Oct."), got


def test_every_renew_now_line_tells_the_owner_to_sign_the_reviewer_in_again(w):
    # axis: each Renew now line (lapsed, today, within the next pass, failed reviewer check) carries the sign-in sentence
    import cloud_check
    sentence = "Sign the reviewer in again if the date does not move."
    seen = []
    for days in (-4, 0, 3):
        _record(w, ACCOUNT, _lapsing_in(days))
        [got] = _lines(w)
        assert got["mark"] == "Renew now", got
        seen.append(got)
    _record(w, ACCOUNT, "2026-10-25")
    marker = cloud_check.failed_check_path(w[0], ACCOUNT, w[1])
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump({"schema": "cloud-check-failed/1", "account": ACCOUNT, "failedParts": ["reviewer"]}, fh)
    [got] = _lines(w)
    assert got["mark"] == "Renew now", got
    seen.append(got)
    assert len(seen) == 4
    for got in seen:
        assert sentence in got["line"], got


def test_a_non_reviewer_check_failure_keeps_the_expiry_warning_for_a_pass_lapsing_before_the_next_pass(w):
    import cloud_check
    _record(w, ACCOUNT, _lapsing_in(3))
    with open(cloud_check.failed_check_path(w[0], ACCOUNT, w[1]), "w", encoding="utf-8") as fh:
        json.dump({"schema": "cloud-check-failed/1", "account": ACCOUNT, "failedParts": ["version"]}, fh)
    [got] = _lines(w)
    assert got["mark"] == "Renew now"
    assert "failed on version" in got["line"] and "run the setup check again" in got["line"].lower()
    assert "3 days left" in got["line"] and RENEW in got["line"]


# ---- the gardening line reads only what it validates, and reports the real setting ---------------

PAUSED_ON = ("cloud builds are paused for this account until a check passes, and resume by "
             "themselves once one does. Run the setup check again.")
STAY_OFF = CS._CHECK_AGAIN
SETTING_UNREAD = CS._SETTING_UNREAD


def _marker(w, failed_parts, account=ACCOUNT):
    body = {"schema": CS.FAILED_CHECK_SCHEMA, "account": account, "failedParts": failed_parts}
    with open(CS.failed_check_path(w[0], account, w[1]), "w", encoding="utf-8") as fh:
        json.dump(body, fh)


def _setting_on(w):
    import core_md
    import project_config
    facts = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
             "patterns": "- x: a.ts:1"}
    core_md.write(w[0], facts, "confirmed", root=w[1], now="2026-10-01")
    got = core_md.write_project_config_item(w[0], project_config.CLOUD_BUILDS_SLUG, True, root=w[1])
    assert got == {"action": "written"}, got


def _setting_reads(monkeypatch, got):
    import project_config

    def read(*args, **kwargs):
        if isinstance(got, BaseException):
            raise got
        return got

    monkeypatch.setattr(project_config, "read", read)


def _read_payload(items, **flags):
    """What `project_config.read` returns for a profile that was read, with the given items."""
    return {"profileAbsent": False, "profileUnparseable": False, "behind": False, "items": items, **flags}


def _cloud_item(**fields):
    return {"slug": "cloudBuilds", "raw": None, "source": "stamped", "malformed": False, **fields}


def test_cloud_setup_does_not_import_the_check_orchestrator():
    # axis: the gardening line imports no cloud_check, lazily or otherwise — see bite-proof record c8c_wo_a.md
    import ast
    with open(CS.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported += [alias.name for alias in node.names]
    assert "cloud_check" not in imported, imported


def test_cloud_check_keeps_the_lapse_rule_as_cloud_setups():
    import cloud_check
    assert cloud_check._lapses_ok is CS._lapses_ok
    assert CS._lapses_ok(_lapsing_in(0), TODAY) is True
    assert CS._lapses_ok(_lapsing_in(-1), TODAY) is False
    assert CS._lapses_ok("2026-13-01", TODAY) is False


@pytest.mark.parametrize("bad", ["", 5, None, ["a"], "has space", "-leading", "x" * 129])
def test_a_record_file_with_an_invalid_account_is_unreadable_and_reads_no_marker(w, monkeypatch, bad):
    # axis: an account read from a record file is validated before it builds a marker path — see bite-proof record c8c_wo_a.md
    _record(w, ACCOUNT, _lapsing_in(30))
    os.remove(CS.record_path(w[0], ACCOUNT, w[1]))
    directory = os.path.dirname(CS.record_path(w[0], ACCOUNT, w[1]))
    with open(os.path.join(directory, "odd.json"), "w", encoding="utf-8") as fh:
        json.dump({"account": bad}, fh)
    reads = []
    monkeypatch.setattr(CS, "read_failed_check", lambda *args, **kwargs: reads.append(args))
    assert _lines(w) == [{"account": None, "mark": None, "line": UNREADABLE}]
    assert reads == []


def test_a_record_file_with_no_account_key_is_unreadable(w):
    _record(w, ACCOUNT, _lapsing_in(30))
    os.remove(CS.record_path(w[0], ACCOUNT, w[1]))
    directory = os.path.dirname(CS.record_path(w[0], ACCOUNT, w[1]))
    with open(os.path.join(directory, "keyless.json"), "w", encoding="utf-8") as fh:
        json.dump({"schema": CS.SCHEMA}, fh)
    assert _lines(w) == [{"account": None, "mark": None, "line": UNREADABLE}]


def test_a_damaged_marker_is_the_renew_line_with_the_stay_off_sentence_while_the_setting_is_off(w):
    _record(w, ACCOUNT, "2026-10-25")
    with open(CS.failed_check_path(w[0], ACCOUNT, w[1]), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    [got] = _lines(w)
    assert got["mark"] == "Renew now" and got["account"] == ACCOUNT
    assert "last reviewer check failed" in got["line"]
    assert got["line"].endswith("Cloud builds stay off until a check passes. Run the setup check again.")


@pytest.mark.parametrize("parts", ["version", {"reviewer": True}, 5, ["version", 3], [3], None])
def test_a_marker_whose_failed_parts_is_not_a_list_of_strings_is_damaged(w, parts):
    # axis: a marker whose failedParts is not a list of strings is damaged, never iterated as valid — see bite-proof record c8c_wo_a.md
    _record(w, ACCOUNT, "2026-10-25")
    _marker(w, parts)
    [got] = _lines(w)
    assert got["mark"] == "Renew now" and got["account"] == ACCOUNT
    assert got["line"].startswith("Cloud reviewer pass: the last reviewer check failed")
    assert got["line"].endswith("Cloud builds stay off until a check passes. Run the setup check again.")


def test_a_list_of_strings_without_reviewer_is_a_repair_line_and_with_reviewer_is_the_renew_line(w):
    _record(w, ACCOUNT, "2026-10-25")
    _marker(w, ["version", "calibration"])
    [got] = _lines(w)
    assert got["mark"] is None
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version, calibration, "
                           "so " + STAY_OFF)
    _marker(w, ["version", "reviewer"])
    [got] = _lines(w)
    assert got["mark"] == "Renew now" and "last reviewer check failed" in got["line"]


def test_with_the_setting_on_a_repair_line_says_the_account_is_paused_and_resumes(w):
    # axis: the line says cloud builds stay off only while the owner's setting is off; with the setting on it says the account is paused and resumes by itself
    _record(w, ACCOUNT, "2026-10-25")
    _setting_on(w)
    _marker(w, ["version"])
    [got] = _lines(w)
    assert got["mark"] is None
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version, so "
                           + PAUSED_ON)
    assert "stay off" not in got["line"] and "switched" not in got["line"]


def test_with_the_setting_on_a_renew_line_says_the_account_is_paused_and_resumes(w):
    # axis: the line says cloud builds stay off only while the owner's setting is off; with the setting on it says the account is paused and resumes by itself
    _record(w, ACCOUNT, "2026-10-25")
    _setting_on(w)
    _marker(w, ["reviewer"])
    [got] = _lines(w)
    assert got["mark"] == "Renew now"
    assert got["line"].endswith(RENEW + " " + PAUSED_ON[0].upper() + PAUSED_ON[1:])
    assert "stay off" not in got["line"]


def test_a_setting_on_beside_a_marker_is_paused_never_called_off(w):
    # axis: the line says cloud builds stay off only while the owner's setting is off; with the setting on it says the account is paused and resumes by itself
    _record(w, ACCOUNT, _lapsing_in(3))
    _setting_on(w)
    _marker(w, ["version"])
    [got] = _lines(w)
    assert got["mark"] == "Renew now"
    assert "failed on version" in got["line"] and PAUSED_ON in got["line"]
    assert "stay off" not in got["line"] and "3 days left" in got["line"]


@pytest.mark.parametrize("answer", [
    RuntimeError("config store gone"),
    _read_payload([]),
    _read_payload([_cloud_item(effective="yes")]),
    _read_payload([_cloud_item(effective=None)]),
    ["not", "a", "mapping"],
])
def test_an_unreadable_setting_is_claimed_neither_on_nor_off(w, monkeypatch, answer):
    # axis: an unreadable setting is not read as off — see bite-proof record c8c_wo_a.md
    _record(w, ACCOUNT, "2026-10-25")
    _marker(w, ["version"])
    _setting_reads(monkeypatch, answer)
    [got] = _lines(w)
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version. "
                           + SETTING_UNREAD)
    assert "stay off" not in got["line"] and "still on" not in got["line"]
    _marker(w, ["reviewer"])
    [got] = _lines(w)
    assert got["mark"] == "Renew now" and got["line"].endswith(RENEW + " " + SETTING_UNREAD)


def test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off(w):
    # axis: a corrupt profile is an unreadable setting, a missing one is off — see bite-proof record c8c_wo_d.md
    _record(w, ACCOUNT, "2026-10-25")
    _setting_on(w)
    _write_corrupt_profile(w)
    _marker(w, ["version"])
    [got] = _lines(w)
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version. "
                           + CS._SETTING_UNREAD)
    assert "stay off" not in got["line"] and "still on" not in got["line"]
    _marker(w, ["reviewer"])
    [got] = _lines(w)
    assert got["mark"] == "Renew now" and got["line"].endswith(RENEW + " " + CS._SETTING_UNREAD)
    assert "stay off" not in got["line"] and "still on" not in got["line"]


def test_a_missing_profile_reads_as_cloud_builds_off(w):
    # axis: a corrupt profile is an unreadable setting, a missing one is off — see bite-proof record c8c_wo_d.md
    _record(w, ACCOUNT, "2026-10-25")
    _marker(w, ["version"])
    assert CS._cloud_builds_setting(w[0], w[1]) is False
    [got] = _lines(w)
    assert got["line"].endswith(CS._CHECK_AGAIN)
    assert CS._SETTING_UNREAD not in got["line"]


def _write_corrupt_profile(w):
    import core_md
    path = core_md.core_path(w[0], w[1])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("this is not a profile\n")


@pytest.mark.parametrize("answer, expected", [
    (_read_payload([_cloud_item(effective=True)]), True),
    (_read_payload([_cloud_item(effective=False)]), False),
    (_read_payload([_cloud_item(effective=True)], profileUnparseable=None), None),
    (_read_payload([_cloud_item(effective=False)], profileUnparseable="yes"), None),
    (_read_payload([_cloud_item(effective=False, malformed=True)]), None),
    (_read_payload([{"slug": "stackingTool", "effective": True, "malformed": False}]), None),
    (_read_payload([_cloud_item(effective=1)]), None),
])
def test_the_setting_is_a_bool_only_for_a_read_profile_with_a_well_formed_item(w, monkeypatch, answer, expected):
    _setting_reads(monkeypatch, answer)
    assert CS._cloud_builds_setting(w[0], w[1]) is expected


@pytest.mark.parametrize("flags", [
    {"profileUnparseable": True},
    {"profileAbsent": True, "profileUnparseable": True},
])
def test_an_unparseable_report_is_off_without_a_core_file_and_unreadable_with_one(w, monkeypatch, flags):
    _setting_reads(monkeypatch, _read_payload([_cloud_item(effective=False)], **flags))
    assert CS._cloud_builds_setting(w[0], w[1]) is False
    _write_corrupt_profile(w)
    assert CS._cloud_builds_setting(w[0], w[1]) is None


def test_a_presence_check_that_raises_is_an_unreadable_setting(w, monkeypatch):
    import core_md
    _setting_reads(monkeypatch, _read_payload([_cloud_item(effective=False)], profileUnparseable=True))

    def core_path(*args, **kwargs):
        raise OSError("store gone")

    monkeypatch.setattr(core_md, "core_path", core_path)
    assert CS._cloud_builds_setting(w[0], w[1]) is None


def test_the_presence_check_writes_nothing(w, monkeypatch):
    import core_md
    seen = []
    real = core_md.core_path

    def core_path(*args, **kwargs):
        seen.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(core_md, "core_path", core_path)
    _setting_reads(monkeypatch, _read_payload([_cloud_item(effective=False)], profileUnparseable=True))
    assert CS._cloud_builds_setting(w[0], w[1]) is False
    assert seen == [{"persist_backfill": False}]


def test_cloud_checks_paused_wording_is_read_from_cloud_setup():
    import cloud_check
    assert CS.PAUSED_RESUME in cloud_check._PAUSED_STANDING
    # the gardening line carries the same rule in its own clause
    assert "resume by themselves once one does" in CS._PAUSED_ON
    assert CS._check_again(True)[0] == CS._PAUSED_ON
    assert "setting" not in [name for name, _s, _fix in cloud_check._PARTS]
    for gone in ("_UNREAD_STILL_ON", "_SWITCHED_OFF", "_switch_off"):
        assert not hasattr(cloud_check, gone), gone
