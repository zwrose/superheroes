# plugins/superheroes/lib/tests/test_cloud_ready.py
"""Conformance: the readiness reader. Six conditions in a fixed order, the first false one names
the reason, and anything that cannot be read is not ready. Every store, account file and record is
built under tmp_path; no test touches the real home directory, clock or network."""
import datetime
import json
import os
import subprocess
import sys
import types

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_check  # noqa: E402
import cloud_plugin_pin  # noqa: E402
import cloud_ready as CR  # noqa: E402
import cloud_setup as CS  # noqa: E402
import cloud_setup_text  # noqa: E402
import core_md as CM  # noqa: E402
import project_config as PC  # noqa: E402

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

ACCOUNT = "acct-fixture-one"
OTHER_ACCOUNT = "acct-fixture-two"
ENVIRONMENT = "env-fixture-one"
STAMP = "sha256:" + "ab" * 32
OTHER_STAMP = "sha256:" + "cd" * 32
ADVISOR = "1.2.3"
TODAY = datetime.date(2026, 10, 11)
FUTURE = "2026-12-01"
PAST = "2026-10-10"

ALL_TRUE = {name: True for name in CR.CONDITION_ORDER}
ALL_FALSE = {name: False for name in CR.CONDITION_ORDER}
RESULT_KEYS = {"ready", "reason", "conditions", "setting", "account", "environment",
               "cloudVersion", "advisorVersion", "picksUpVersion", "checkedAt", "failedCheck",
               "pluginPin", "dependencyHookGap"}
NO_PIN = {"state": "absent", "reason": None, "version": None}


def _stamp_ok(cwd, root):
    return STAMP


def _setup_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def _record(repo, store, **over):
    values = {
        "account": ACCOUNT, "environment": ENVIRONMENT, "plugin_version": ADVISOR,
        "picks_up_version": False, "calibration_stamp": STAMP,
        "calibration_date": "2026-10-01", "pass_lapses": FUTURE, "checked_at": "2026-10-09",
    }
    values.update(over)
    got = CS.record_check(repo, root=store, **values)
    assert got["action"] in ("written", "noop"), got
    return got


def _ready(tmp_path, **over):
    repo, store = _setup_repo(tmp_path)
    _record(repo, store, **over)
    return repo, store


def _read(repo, store, **over):
    args = {"account": ACCOUNT, "advisor_version": ADVISOR, "today": TODAY, "root": store,
            "stamp_fn": _stamp_ok}
    args.update(over)
    return CR.readiness(repo, **args)


def _only_false(result, name):
    expected = dict(ALL_TRUE, **{name: False})
    assert result["conditions"] == expected
    assert result["ready"] is False
    assert result["reason"] == CR.REASON_FOR[name]


# ---------------------------------------------------------------- the interface


def test_the_interface_constants_are_exact():
    assert CR.CONDITION_ORDER == (
        "setup", "passPresent", "passLive", "version", "pluginPin", "dependencyHook", "calibration",
        "platform")
    assert CR.REASON_FOR == {
        "setup": "no-setup", "passPresent": "no-pass", "passLive": "pass-lapsed",
        "version": "version", "pluginPin": "plugin-pin", "dependencyHook": "dependency-hook",
        "calibration": "calibration", "platform": "unreachable"}
    assert CR.REPORTED_KEYS == ("pluginVersion", "noPass", "unreachable")


@pytest.mark.parametrize("reported", [
    None, {}, {"pluginVersion": "0.41.0"}, {"noPass": True}, {"unreachable": True},
    {"pluginVersion": "10.20.30", "noPass": True, "unreachable": True},
])
def test_valid_reported_accepts_the_known_shapes(reported):
    assert CR.valid_reported(reported) is True


@pytest.mark.parametrize("reported", [
    [], "x", 1, True, {"other": True}, {"noPass": False}, {"noPass": 1}, {"noPass": "true"},
    {"unreachable": None}, {"unreachable": 1.0}, {"pluginVersion": 41}, {"pluginVersion": ""},
    {"pluginVersion": "0.41"}, {"pluginVersion": "0.41.0\n"}, {"pluginVersion": "v0.41.0"},
    {"pluginVersion": "0.41.0-rc1"}, {"pluginVersion": None}, {"noPass": True, "extra": 1},
])
def test_valid_reported_refuses_every_other_shape(reported):
    assert CR.valid_reported(reported) is False


# ---------------------------------------------------------------- ready, and the result's shape


def test_ready_when_all_six_hold_and_every_key_is_present(tmp_path):
    repo, store = _ready(tmp_path)
    got = _read(repo, store)
    assert set(got) == RESULT_KEYS
    assert got == {
        "ready": True, "reason": None, "conditions": ALL_TRUE, "setting": False,
        "account": ACCOUNT, "environment": ENVIRONMENT, "cloudVersion": ADVISOR,
        "advisorVersion": ADVISOR, "picksUpVersion": False, "checkedAt": "2026-10-09",
        "failedCheck": None, "pluginPin": NO_PIN}


def test_setting_comes_from_the_one_reader(tmp_path):
    repo, store = _ready(tmp_path)
    assert _read(repo, store)["setting"] is False
    assert PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)["action"] == "written"
    assert _read(repo, store)["setting"] is True


def test_real_stamp_formula_is_the_one_the_check_uses(tmp_path):
    repo, store = _setup_repo(tmp_path)
    real = cloud_check._placed_stamp(repo, store)
    assert real == CS.calibration_stamp(cloud_setup_text.stamped_files(repo, store))
    _record(repo, store, calibration_stamp=real)
    got = _read(repo, store, stamp_fn=None)
    assert got["ready"] is True and got["conditions"]["calibration"] is True
    _record(repo, store, calibration_stamp=OTHER_STAMP)
    _only_false(_read(repo, store, stamp_fn=None), "calibration")


def test_account_comes_from_the_launching_account_file(tmp_path):
    repo, store = _ready(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": ACCOUNT}}), encoding="utf-8")
    got = CR.readiness(repo, advisor_version=ADVISOR, today=TODAY, root=store,
                       stamp_fn=_stamp_ok, env={"HOME": str(home)})
    assert got["ready"] is True and got["account"] == ACCOUNT


def test_E1_unreadable_account_is_not_set_up(tmp_path):
    repo, store = _ready(tmp_path)
    home = tmp_path / "empty-home"
    home.mkdir()
    for env in ({"HOME": str(home)}, {"HOME": str(tmp_path / "no-such-home")}):
        got = CR.readiness(repo, advisor_version=ADVISOR, today=TODAY, root=store,
                           stamp_fn=_stamp_ok, env=env)
        assert got["ready"] is False and got["reason"] == "no-setup"
        assert got["conditions"] == ALL_FALSE and got["account"] is None
    bad = tmp_path / "bad-home"
    bad.mkdir()
    (bad / ".claude.json").write_text("{not json", encoding="utf-8")
    got = CR.readiness(repo, advisor_version=ADVISOR, today=TODAY, root=store,
                       stamp_fn=_stamp_ok, env={"HOME": str(bad)})
    assert got["reason"] == "no-setup" and got["conditions"] == ALL_FALSE


# ---------------------------------------------------------------- setup, and what it forces


def test_E2_missing_record_forces_every_later_condition_false(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = _read(repo, store, reported={})
    assert got["conditions"] == ALL_FALSE
    assert got["ready"] is False and got["reason"] == "no-setup"
    assert [got[k] for k in ("environment", "cloudVersion", "picksUpVersion", "checkedAt")] == [
        None, None, None, None]
    assert got["advisorVersion"] == ADVISOR and set(got) == RESULT_KEYS


def test_E3_unreadable_or_malformed_record_is_not_set_up(tmp_path):
    repo, store = _ready(tmp_path)
    path = CS.record_path(repo, ACCOUNT, store)
    for text in ("{not json", "[]", "null", json.dumps({"schema": CS.SCHEMA}), ""):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        got = _read(repo, store)
        assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup", text
        assert got["environment"] is None and got["checkedAt"] is None


def test_E4_record_for_another_account_is_not_set_up(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _record(repo, store, account=OTHER_ACCOUNT)
    got = _read(repo, store, account=ACCOUNT)
    assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
    assert _read(repo, store, account=OTHER_ACCOUNT)["ready"] is True


# ---------------------------------------------------------------- the pass


def test_E5_pass_lapsed_in_the_past_is_not_live(tmp_path):
    repo, store = _ready(tmp_path, pass_lapses=PAST)
    _only_false(_read(repo, store), "passLive")


def test_pass_that_lapses_today_is_still_live(tmp_path):
    repo, store = _ready(tmp_path, pass_lapses=TODAY.isoformat())
    assert _read(repo, store)["ready"] is True
    _only_false(_read(repo, store, today=TODAY + datetime.timedelta(days=1)), "passLive")


def test_today_defaults_to_the_utc_date(tmp_path, monkeypatch):
    # The clock is frozen just after UTC midnight; the stand-in refuses any zone but UTC.
    next_day = TODAY + datetime.timedelta(days=1)

    class FrozenDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is datetime.timezone.utc
            return cls(next_day.year, next_day.month, next_day.day, 0, 0, 30, tzinfo=tz)

    monkeypatch.setattr(CR, "datetime", types.SimpleNamespace(
        datetime=FrozenDatetime, date=datetime.date, timezone=datetime.timezone))
    repo, store = _ready(tmp_path, pass_lapses=TODAY.isoformat())
    _only_false(_read(repo, store, today=None), "passLive")
    (tmp_path / "second").mkdir()
    repo2, store2 = _ready(tmp_path / "second", pass_lapses=next_day.isoformat())
    assert _read(repo2, store2, today=None)["ready"] is True


@pytest.mark.parametrize("lapses", ["garbage", "2026-13-40", "", None, 20261201, "2026-12-01 "])
def test_E5_unparseable_lapse_date_is_not_live(tmp_path, monkeypatch, lapses):
    repo, store = _ready(tmp_path)
    real = CS.read(repo, ACCOUNT, root=store)
    record = dict(real["record"], passLapses=lapses)
    monkeypatch.setattr(CS, "read", lambda cwd, account, root=None: dict(real, record=record))
    _only_false(_read(repo, store), "passLive")


def test_reported_no_pass_is_no_pass(tmp_path):
    repo, store = _ready(tmp_path)
    _only_false(_read(repo, store, reported={"noPass": True}), "passPresent")


# ---------------------------------------------------------------- the version


def test_version_differs_and_the_cloud_does_not_pick_it_up(tmp_path):
    repo, store = _ready(tmp_path, plugin_version="1.2.2", picks_up_version=False)
    got = _read(repo, store)
    _only_false(got, "version")
    assert got["cloudVersion"] == "1.2.2" and got["advisorVersion"] == ADVISOR
    assert got["picksUpVersion"] is False


def test_version_differs_but_the_cloud_picks_it_up(tmp_path):
    repo, store = _ready(tmp_path, plugin_version="1.2.2", picks_up_version=True)
    got = _read(repo, store)
    assert got["ready"] is True and got["conditions"]["version"] is True
    assert got["cloudVersion"] == "1.2.2" and got["picksUpVersion"] is True


def test_reported_version_stands_in_for_the_records(tmp_path):
    repo, store = _ready(tmp_path, plugin_version=ADVISOR, picks_up_version=True)
    got = _read(repo, store, reported={"pluginVersion": "0.41.0"})
    _only_false(got, "version")
    assert got["cloudVersion"] == "0.41.0" and got["advisorVersion"] == ADVISOR


def test_reported_version_ignores_the_record_and_its_pickup(tmp_path):
    repo, store = _ready(tmp_path, plugin_version="1.2.2", picks_up_version=False)
    got = _read(repo, store, reported={"pluginVersion": ADVISOR})
    assert got["ready"] is True and got["cloudVersion"] == ADVISOR


def test_E6_unreadable_advisor_version_is_not_ready(tmp_path, monkeypatch):
    repo, store = _ready(tmp_path, picks_up_version=True)

    def refuse():
        raise cloud_setup_text._Refused("plugin-version-unreadable", "unreadable")

    monkeypatch.setattr(cloud_setup_text, "_plugin_version", refuse)
    for reported in (None, {"pluginVersion": ADVISOR}):
        got = CR.readiness(repo, account=ACCOUNT, today=TODAY, root=store, stamp_fn=_stamp_ok,
                           reported=reported)
        _only_false(got, "version")
        assert got["advisorVersion"] is None


def test_advisor_version_defaults_to_the_plugins_own(tmp_path):
    repo, store = _ready(tmp_path, plugin_version=cloud_setup_text._plugin_version())
    got = CR.readiness(repo, account=ACCOUNT, today=TODAY, root=store, stamp_fn=_stamp_ok)
    assert got["ready"] is True and got["advisorVersion"] == cloud_setup_text._plugin_version()


# ---------------------------------------------------------------- calibration and platform


def test_calibration_that_differs_is_not_ready(tmp_path):
    repo, store = _ready(tmp_path)
    _only_false(_read(repo, store, stamp_fn=lambda cwd, root: OTHER_STAMP), "calibration")


def test_E7_stamp_function_that_raises_is_not_ready(tmp_path):
    repo, store = _ready(tmp_path)

    def boom(cwd, root):
        raise OSError("stamp exploded")

    _only_false(_read(repo, store, stamp_fn=boom), "calibration")


def test_reported_unreachable_is_unreachable(tmp_path):
    repo, store = _ready(tmp_path)
    _only_false(_read(repo, store, reported={"unreachable": True}), "platform")


# ---------------------------------------------------------------- the edges


@pytest.mark.parametrize("reported", [
    [], "x", 1, {"other": True}, {"noPass": False}, {"noPass": "true"}, {"unreachable": 1},
    {"pluginVersion": 41}, {"pluginVersion": "0.41"}, {"noPass": True, "extra": 1},
])
def test_E8_invalid_reported_is_never_ready(tmp_path, reported):
    repo, store = _ready(tmp_path)
    PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)
    got = _read(repo, store, reported=reported)
    assert got["ready"] is False and got["reason"] == "no-setup"
    assert got["conditions"] == ALL_FALSE and set(got) == RESULT_KEYS
    assert got["setting"] is True


def test_an_unexpected_exception_reads_as_not_ready(tmp_path, monkeypatch):
    repo, store = _ready(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("reader exploded")

    monkeypatch.setattr(CS, "read", boom)
    got = _read(repo, store)
    assert got["ready"] is False and got["reason"] == "no-setup"
    assert got["conditions"] == ALL_FALSE and set(got) == RESULT_KEYS


# ---------------------------------------------------------------- which reason is given


def test_order_setup_before_pass_present(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = _read(repo, store, reported={"noPass": True, "pluginVersion": "0.41.0",
                                      "unreachable": True})
    assert got["reason"] == "no-setup"


def test_order_pass_present_before_pass_live(tmp_path):
    repo, store = _ready(tmp_path, pass_lapses=PAST)
    got = _read(repo, store, reported={"noPass": True})
    assert got["reason"] == "no-pass"
    assert got["conditions"]["passLive"] is False


def test_order_pass_live_before_version(tmp_path):
    repo, store = _ready(tmp_path, pass_lapses=PAST, plugin_version="1.2.2")
    got = _read(repo, store)
    assert got["reason"] == "pass-lapsed" and got["conditions"]["version"] is False


def test_order_version_before_calibration(tmp_path):
    repo, store = _ready(tmp_path, plugin_version="1.2.2")
    got = _read(repo, store, stamp_fn=lambda cwd, root: OTHER_STAMP)
    assert got["reason"] == "version" and got["conditions"]["calibration"] is False


def test_order_calibration_before_platform(tmp_path):
    repo, store = _ready(tmp_path)
    got = _read(repo, store, stamp_fn=lambda cwd, root: OTHER_STAMP,
                reported={"unreachable": True})
    assert got["reason"] == "calibration" and got["conditions"]["platform"] is False


def test_everything_false_but_setup_reports_the_pass(tmp_path):
    repo, store = _ready(tmp_path, pass_lapses=PAST, plugin_version="1.2.2")
    got = _read(repo, store, stamp_fn=lambda cwd, root: OTHER_STAMP,
                reported={"noPass": True, "unreachable": True})
    # the fixture has the dependency hook off, so that condition holds whatever the commit
    assert got["conditions"] == dict(ALL_FALSE, setup=True, dependencyHook=True, pluginPin=True)
    assert got["reason"] == "no-pass"


# ---------------------------------------------------------------- a failed check


def _mark(repo, store, parts, account=ACCOUNT, raw=None):
    """Leave the failed-check marker a failed check leaves beside the setup record."""
    path = cloud_check.failed_check_path(repo, account, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    marker = {"schema": cloud_check.FAILED_CHECK_SCHEMA, "account": account,
              "environment": ENVIRONMENT, "failedAt": "2026-10-10T00:00:00Z",
              "failedParts": parts}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(raw if raw is not None else json.dumps(marker))
    return path


def _count_marker_reads(monkeypatch):
    reads = []
    real = cloud_check.read_failed_check
    monkeypatch.setattr(
        cloud_check, "read_failed_check", lambda *a, **k: reads.append(a) or real(*a, **k))
    return reads


def test_failed_check_is_none_on_every_path_without_a_marker(tmp_path):
    repo, store = _ready(tmp_path)
    assert _read(repo, store)["failedCheck"] is None
    assert _read(repo, store, reported={"bogus": True})["failedCheck"] is None
    assert _read(repo, store, account=OTHER_ACCOUNT)["failedCheck"] is None


def test_any_marker_present_means_not_ready(tmp_path):
    # axis: any failed-check marker present means the latest check failed, so the setup is not ready
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["record"])
    got = _read(repo, store)
    assert got["ready"] is False and got["reason"] == "no-setup"
    assert got["conditions"] == ALL_FALSE
    assert got["failedCheck"] == ["record"] and set(got) == RESULT_KEYS


@pytest.mark.parametrize("part,condition", [
    ("reviewer", "passPresent"), ("version", "version"), ("calibration", "calibration")])
def test_a_named_part_forces_its_own_condition_false(tmp_path, part, condition):
    # axis: the reviewer, version and calibration parts each force their own condition false
    repo, store = _ready(tmp_path)
    _mark(repo, store, [part])
    got = _read(repo, store)
    _only_false(got, condition)
    assert got["failedCheck"] == [part]


def test_a_failed_version_check_leaves_no_cloud_version_unless_the_cloud_reported_one(tmp_path):
    # axis: a failed version check leaves the old record in place, so its version is not the cloud's current one — see bite-proof record wo_d_place_call
    repo, store = _ready(tmp_path, plugin_version="1.2.2")
    _mark(repo, store, ["version"])
    got = _read(repo, store)
    _only_false(got, "version")
    assert got["cloudVersion"] is None and got["failedCheck"] == ["version"]
    reported = _read(repo, store, reported={"pluginVersion": "0.41.0"})
    _only_false(reported, "version")
    assert reported["cloudVersion"] == "0.41.0"


def test_several_named_parts_apply_together_and_the_order_picks_the_reason(tmp_path):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["calibration", "version", "reviewer"])
    got = _read(repo, store)
    assert got["conditions"] == dict(ALL_TRUE, passPresent=False, version=False, calibration=False)
    assert got["reason"] == "no-pass"
    assert got["failedCheck"] == ["calibration", "version", "reviewer"]


@pytest.mark.parametrize("part", ["unread", "environment", "record", "setting", "other"])
def test_any_other_part_forces_the_setup_condition_false(tmp_path, part):
    # axis: any other failed part forces the setup condition false, and so every later one
    repo, store = _ready(tmp_path)
    _mark(repo, store, [part])
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
    assert got["failedCheck"] == [part]


def test_E3_a_marker_of_unknown_parts_only_is_no_setup(tmp_path):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["unread", "environment"])
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
    assert got["failedCheck"] == ["unread", "environment"]


def test_a_named_part_beside_an_unknown_one_is_no_setup(tmp_path):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["reviewer", "record"])
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", '{"schema": "other/9"}', ""])
def test_E1_a_damaged_marker_is_present_with_no_parts_and_no_setup(tmp_path, raw):
    # axis: a marker that cannot be read is present and damaged, so the setup is not ready
    repo, store = _ready(tmp_path)
    _mark(repo, store, [], raw=raw)
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
    assert got["failedCheck"] == []


def test_a_marker_with_no_parts_is_no_setup(tmp_path):
    repo, store = _ready(tmp_path)
    _mark(repo, store, [])
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["failedCheck"] == []


def test_E2_a_marker_read_that_raises_counts_as_damaged(tmp_path, monkeypatch):
    repo, store = _ready(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("marker reader exploded")

    monkeypatch.setattr(cloud_check, "read_failed_check", boom)
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
    assert got["failedCheck"] == []


def test_E4_a_marker_beside_an_unreadable_record_is_not_read(tmp_path, monkeypatch):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["reviewer"])
    os.unlink(CS.record_path(repo, ACCOUNT, store))
    reads = _count_marker_reads(monkeypatch)
    got = _read(repo, store)
    assert reads == []
    assert got["reason"] == "no-setup" and got["conditions"] == ALL_FALSE
    assert got["failedCheck"] is None


def test_a_marker_for_another_account_does_not_fail_this_one(tmp_path):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["reviewer"], account=OTHER_ACCOUNT)
    got = _read(repo, store)
    assert got["ready"] is True and got["failedCheck"] is None


def test_the_marker_is_read_once(tmp_path, monkeypatch):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["version"])
    reads = _count_marker_reads(monkeypatch)
    _read(repo, store)
    assert len(reads) == 1 and reads[0][1] == ACCOUNT


def test_the_all_false_fallback_carries_failed_check_none(tmp_path, monkeypatch):
    repo, store = _ready(tmp_path)
    _mark(repo, store, ["reviewer"])

    def boom(*args, **kwargs):
        raise RuntimeError("reader exploded")

    monkeypatch.setattr(CR, "_readiness", boom)
    got = _read(repo, store)
    assert got["failedCheck"] is None and got["conditions"] == ALL_FALSE
    assert set(got) == RESULT_KEYS


# ---------------------------------------------------------------- the plugin pin hook

UNREAD_PIN = {"state": None, "reason": None, "version": None}


def _pin(version=ADVISOR):
    return {"source": "https://github.com/acme/superheroes.git", "commit": "a" * 40,
            "subdir": "plugins/superheroes", "version": version}


def _git(repo, *args):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.devnull,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=repo, env=env, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _commit_pin(repo, pin=None, broken=False):
    """Commit the plugin pin hook files for `pin` (or a broken pin file, or no hook files at all
    when `pin` is None and `broken` is False); returns the new commit."""
    if not os.path.isdir(os.path.join(repo, ".git")):
        _git(repo, "init", "-q")
        with open(os.path.join(repo, "README"), "w") as fh:
            fh.write("x\n")
    if pin is not None or broken:
        assert cloud_plugin_pin.sync(repo, pin or _pin())["action"] in ("written", "noop")
    if broken:
        with open(os.path.join(repo, ".claude", "superheroes-plugin-pin"), "w") as fh:
            fh.write("not a pin\n")
    _git(repo, "add", "README", *([".claude"] if os.path.isdir(os.path.join(repo, ".claude")) else []))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "x")
    return _git(repo, "rev-parse", "HEAD")


def _pin_ready(tmp_path, pin=None, broken=False, **over):
    """A ready project whose repository commits the hook for `pin` (a broken one when `broken`)."""
    _commit_pin(str(tmp_path), pin, broken)
    return _ready(tmp_path, **over)


def test_an_absent_hook_changes_nothing_but_the_two_additions(tmp_path):
    for name, hooked in (("git-no-hook", False), ("no-git", None)):
        (tmp_path / name).mkdir()
        if hooked is False:
            _commit_pin(str(tmp_path / name))
        repo, store = _ready(tmp_path / name)
        got = _read(repo, store)
        assert got["conditions"] == ALL_TRUE and got["ready"] is True and got["reason"] is None
        assert got["pluginPin"] == NO_PIN and set(got) == RESULT_KEYS
        assert got["cloudVersion"] == ADVISOR
        stale = _read(repo, store, reported={"pluginVersion": "1.2.2"})
        _only_false(stale, "version")
        assert stale["pluginPin"] == NO_PIN


def test_the_early_returns_carry_the_unread_pin_and_every_condition_false(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = _read(repo, store)
    assert got["conditions"] == ALL_FALSE and got["pluginPin"] == UNREAD_PIN
    assert got["conditions"]["pluginPin"] is False


def test_rule_a_a_reported_version_decides_and_the_pin_never_overrides_it(tmp_path):
    repo, store = _pin_ready(tmp_path, _pin(ADVISOR))
    stale = _read(repo, store, reported={"pluginVersion": "1.2.2"})
    # axis: a reported version stands alone; the pin never overrides it
    _only_false(stale, "version")
    assert stale["cloudVersion"] == "1.2.2"
    assert stale["pluginPin"] == {"state": "valid", "reason": None, "version": ADVISOR}
    # and it does not make a pin that names another version fail either
    (tmp_path / "other").mkdir()
    repo2, store2 = _pin_ready(tmp_path / "other", _pin("1.0.0"))
    current = _read(repo2, store2, reported={"pluginVersion": ADVISOR})
    assert current["conditions"] == ALL_TRUE and current["cloudVersion"] == ADVISOR


def test_rule_b_a_valid_pin_naming_the_advisor_makes_the_cloud_current(tmp_path):
    repo, store = _pin_ready(tmp_path, _pin(ADVISOR), plugin_version="1.2.2")
    got = _read(repo, store)
    assert got["ready"] is True and got["conditions"] == ALL_TRUE
    # the record says 1.2.2 and no pick-up is on file; the pin is what the cloud will run
    assert got["cloudVersion"] == ADVISOR
    assert got["pluginPin"] == {"state": "valid", "reason": None, "version": ADVISOR}


def test_rule_c_a_valid_pin_naming_another_version_is_not_current(tmp_path):
    repo, store = _pin_ready(tmp_path, _pin("1.2.2"))
    got = _read(repo, store)
    # axis: the pin is current only when its version is the advisor's
    _only_false(got, "pluginPin")
    assert got["reason"] == "plugin-pin" and got["cloudVersion"] == "1.2.2"
    assert got["pluginPin"] == {"state": "valid", "reason": None, "version": "1.2.2"}


def test_rule_d_a_broken_pin_is_not_current_and_is_not_read_as_absent(tmp_path):
    repo, store = _pin_ready(tmp_path, broken=True)
    got = _read(repo, store)
    # axis: a broken pin hook is never read as absent
    _only_false(got, "pluginPin")
    assert got["pluginPin"]["state"] == "broken" and got["pluginPin"]["reason"]
    assert got["pluginPin"]["version"] is None
    reported = _read(repo, store, reported={"pluginVersion": ADVISOR})
    _only_false(reported, "pluginPin")


def test_E2_the_pin_is_read_at_the_start_commit_not_the_working_tree(tmp_path):
    repo = str(tmp_path)
    bare = _commit_pin(repo)
    valid = _commit_pin(repo, _pin(ADVISOR))
    broken = _commit_pin(repo, broken=True)
    _, store = _ready(tmp_path)
    assert _read(repo, store, commit=valid)["conditions"] == ALL_TRUE
    assert _read(repo, store, commit=bare)["pluginPin"] == NO_PIN
    _only_false(_read(repo, store, commit=broken), "pluginPin")
    # a commit that does not exist, with the hook files in the working tree, is not read as absent
    _only_false(_read(repo, store, commit="d" * 40), "pluginPin")


def test_E2_a_pin_reader_that_raises_reads_as_not_current(tmp_path, monkeypatch):
    repo, store = _pin_ready(tmp_path, _pin(ADVISOR))

    def boom(*args, **kwargs):
        raise RuntimeError("pin reader exploded")

    monkeypatch.setattr(cloud_plugin_pin, "at_commit", boom)
    got = _read(repo, store)
    _only_false(got, "pluginPin")
    assert got["pluginPin"] == {"state": "broken", "reason": "commit-unreadable", "version": None}


def test_E6_a_failed_check_pin_part_forces_the_condition_false(tmp_path):
    repo, store = _pin_ready(tmp_path, _pin(ADVISOR))
    assert _read(repo, store)["ready"] is True
    _mark(repo, store, ["pin"])
    got = _read(repo, store)
    # axis: the pin part forces the plugin-pin condition false
    _only_false(got, "pluginPin")
    assert got["failedCheck"] == ["pin"] and got["reason"] == "plugin-pin"
    assert got["pluginPin"] == {"state": "valid", "reason": None, "version": ADVISOR}


def test_the_version_reason_comes_before_the_plugin_pin_reason(tmp_path):
    repo, store = _pin_ready(tmp_path, broken=True, plugin_version="1.2.2")
    got = _read(repo, store)
    assert got["conditions"]["version"] is False and got["conditions"]["pluginPin"] is False
    assert got["reason"] == "version"
