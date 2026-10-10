# plugins/superheroes/lib/tests/test_cloud_setup.py
"""Conformance: the cloud-builds setting, the setup record reader and its one write path."""
import importlib.util
import io
import json
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CS = _load("cloud_setup")
PC = _load("project_config")
CM = _load("core_md")

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


def _setup_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def _fixture(**over):
    values = {
        "account": ACCOUNT,
        "environment": ENVIRONMENT,
        "plugin_version": "1.2.3",
        "picks_up_version": True,
        "calibration_stamp": STAMP,
        "calibration_date": "2026-07-01",
        "pass_lapses": "2026-08-01",
        "checked_at": "2026-07-02",
    }
    values.update(over)
    return values


def _record_dict(**over):
    values = _fixture(**over)
    return {
        "schema": CS.SCHEMA,
        "account": values["account"],
        "environment": values["environment"],
        "pluginVersion": values["plugin_version"],
        "picksUpVersion": values["picks_up_version"],
        "calibrationStamp": values["calibration_stamp"],
        "calibrationDate": values["calibration_date"],
        "passLapses": values["pass_lapses"],
        "checkedAt": values["checked_at"],
    }


def _check(repo, store, **over):
    return CS.record_check(repo, root=store, **_fixture(**over))


def _record_files(repo, store):
    directory = os.path.join(CS.mode_registry.project_store_dir(repo, store), "state", "cloud-setup")
    if not os.path.isdir(directory):
        return []
    return sorted(os.listdir(directory))


def _write_raw(repo, store, text, account=ACCOUNT):
    path = CS.record_path(repo, account, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _stored(repo, store):
    return PC.get_item(repo, "cloudBuilds", root=store)


def test_fresh_project_reads_setting_off(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = _stored(repo, store)
    assert got["effective"] is False
    assert got["source"] == "plugin-default"
    read = CS.read(repo, ACCOUNT, root=store)
    assert read == {"setting": False, "state": "none", "ready": False, "record": None}


def test_switch_on_with_record_stores_on_and_returns_confirmation(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert _check(repo, store)["action"] == "written"
    name = os.path.basename(os.path.abspath(repo))
    got = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)
    assert got["action"] == "written"
    assert _stored(repo, store)["raw"] is True
    assert "this one local" in got["message"]
    assert got["message"] == CS.switch_message("on", name)
    assert CS.read(repo, ACCOUNT, root=store)["setting"] is True


def test_switch_off_keeps_record_and_switch_on_again_needs_no_new_setup(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    path = CS.record_path(repo, ACCOUNT, store)
    before = open(path, "rb").read()
    on = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT, project_name="fixture")
    assert on["action"] == "written"
    off = PC.set_item(repo, "cloudBuilds", False, root=store, project_name="fixture")
    assert off["action"] == "written"
    assert off["message"] == CS.switch_message("off", "fixture")
    assert _stored(repo, store)["raw"] is False
    assert open(path, "rb").read() == before
    again = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT, project_name="fixture")
    assert again["action"] == "written"
    assert again["message"] == CS.switch_message("on", "fixture")
    assert _stored(repo, store)["raw"] is True
    assert open(path, "rb").read() == before


def test_switch_on_refused_without_record_stores_nothing(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT, project_name="fixture")
    assert got["action"] == "refused"
    assert got["reason"] == PC.REASON_CLOUD_SETUP_MISSING
    assert got["message"] == CS.switch_message("refused", "fixture")
    stored = _stored(repo, store)
    assert stored["raw"] is None
    assert stored["effective"] is False


def test_switch_on_refused_with_record_for_another_account_only(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert _check(repo, store, account=OTHER_ACCOUNT)["action"] == "written"
    got = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)
    assert got["action"] == "refused"
    assert got["reason"] == PC.REASON_CLOUD_SETUP_MISSING
    assert _stored(repo, store)["raw"] is None


def test_switch_on_refused_without_account(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    got = PC.set_item(repo, "cloudBuilds", True, root=store)
    assert got["action"] == "refused"
    assert got["reason"] == PC.REASON_CLOUD_SETUP_MISSING
    assert _stored(repo, store)["raw"] is None


def test_switch_with_non_boolean_is_malformed_before_the_reader_is_asked(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise AssertionError("the reader must not be asked")

    monkeypatch.setattr(CS, "read", _boom)
    monkeypatch.setitem(sys.modules, "cloud_setup", CS)
    got = PC.set_item(repo, "cloudBuilds", "yes", root=store, account=ACCOUNT)
    assert got == {"action": "refused", "reason": PC.REASON_MALFORMED_VALUE}
    assert _stored(repo, store)["raw"] is None


def test_reader_returns_every_record_field(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    got = CS.read(repo, ACCOUNT, root=store)
    assert got["state"] == "ready"
    assert got["ready"] is True
    assert set(got["record"]) == set(CS.RECORD_FIELDS)
    assert got["record"] == _record_dict()


_SECRET_VALUES = [
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.signature",
    "Bearer abc123def456",
    "sk-abc123def456",
    '{"token": "abc"}',
    "a" * 200,
    "-----BEGIN PRIVATE KEY-----",
]


@pytest.mark.parametrize("field", ["environment", "account"])
@pytest.mark.parametrize("value", _SECRET_VALUES)
def test_secret_shaped_value_refused_at_write(tmp_path, field, value):
    repo, store = _setup_repo(tmp_path)
    got = _check(repo, store, **{field: value})
    assert got["action"] == "refused"
    assert got["reason"] == "secret-shaped-value"
    assert got["field"] == field
    assert _record_files(repo, store) == []


def test_unknown_field_refused_at_write(tmp_path):
    repo, store = _setup_repo(tmp_path)
    bad = dict(_record_dict(), extra="x")
    assert CS._validate(bad) == {"reason": "unknown-field", "field": "extra"}
    got = CS._write(repo, ACCOUNT, store, lambda current: (bad, None))
    assert got == {"action": "refused", "reason": "unknown-field", "field": "extra"}
    assert _record_files(repo, store) == []


def _without(key):
    record = _record_dict()
    del record[key]
    return json.dumps(record)


_UNREADABLE = {
    "not-json": "this is not json",
    "empty-file": "",
    "json-list": "[1, 2]",
    "wrong-schema": json.dumps(dict(_record_dict(), schema="cloud-setup/2")),
    "missing-key": _without("passLapses"),
    "extra-key": json.dumps(dict(_record_dict(), extra="x")),
    "bool-as-string": json.dumps(dict(_record_dict(), picksUpVersion="true")),
    "bad-version": json.dumps(dict(_record_dict(), pluginVersion="1.2")),
    "bad-stamp": json.dumps(dict(_record_dict(), calibrationStamp="sha256:xyz")),
    "bad-date": json.dumps(dict(_record_dict(), passLapses="2026-13-45")),
    "non-string-date": json.dumps(dict(_record_dict(), checkedAt=20260702)),
    "secret-in-record": json.dumps(dict(_record_dict(), environment="sk-abc123def456")),
}


@pytest.mark.parametrize("name", sorted(_UNREADABLE))
def test_unreadable_record_reads_as_no_setup(tmp_path, name):
    repo, store = _setup_repo(tmp_path)
    _write_raw(repo, store, _UNREADABLE[name])
    got = CS.read(repo, ACCOUNT, root=store)
    assert got["ready"] is False
    assert got["state"] == "unreadable"
    assert got["record"] is None


def test_record_path_that_cannot_be_opened_reads_unreadable(tmp_path):
    repo, store = _setup_repo(tmp_path)
    path = CS.record_path(repo, ACCOUNT, store)
    os.makedirs(path)
    got = CS.read(repo, ACCOUNT, root=store)
    assert got["ready"] is False
    assert got["state"] == "unreadable"


def test_record_for_other_account_reads_not_ready(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _write_raw(repo, store, json.dumps(_record_dict(account=OTHER_ACCOUNT)))
    got = CS.read(repo, ACCOUNT, root=store)
    assert got["ready"] is False
    assert got["state"] == "unreadable"
    assert got["record"] is None


@pytest.mark.parametrize("account", [None, "", 7, "bad account!", "a" * 200])
def test_missing_account_reads_not_ready(tmp_path, account):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    got = CS.read(repo, account, root=store)
    assert got["ready"] is False
    assert got["state"] == "unreadable"
    assert got["record"] is None


def test_reader_uses_the_given_store_root(tmp_path):
    repo, store = _setup_repo(tmp_path)
    other_store = str(tmp_path / "other-store")
    _check(repo, store)
    assert CS.read(repo, ACCOUNT, root=store)["ready"] is True
    elsewhere = CS.read(repo, ACCOUNT, root=other_store)
    assert elsewhere["ready"] is False
    assert elsewhere["state"] == "none"
    assert CS.record_path(repo, ACCOUNT, store) != CS.record_path(repo, ACCOUNT, other_store)


def test_confirm_pass_moves_only_the_lapse_date(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    got = CS.confirm_pass(repo, ACCOUNT, "2026-12-01", environment=ENVIRONMENT, root=store)
    assert got["action"] == "written"
    record = CS.read(repo, ACCOUNT, root=store)["record"]
    assert record == _record_dict(pass_lapses="2026-12-01")
    again = CS.confirm_pass(repo, ACCOUNT, "2026-12-01", root=store)
    assert again["action"] == "noop"


def test_confirm_pass_bad_date_refused(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    path = CS.record_path(repo, ACCOUNT, store)
    before = open(path, "rb").read()
    got = CS.confirm_pass(repo, ACCOUNT, "next week", root=store)
    assert got == {"action": "refused", "reason": "malformed-value", "field": "passLapses"}
    assert open(path, "rb").read() == before


def test_confirm_pass_refused_without_record(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = CS.confirm_pass(repo, ACCOUNT, "2026-12-01", root=store)
    assert got == {"action": "refused", "reason": "cloud-setup-missing"}
    assert _record_files(repo, store) == []
    _check(repo, store, account=OTHER_ACCOUNT)
    other_only = CS.confirm_pass(repo, ACCOUNT, "2026-12-01", root=store)
    assert other_only == {"action": "refused", "reason": "cloud-setup-missing"}


def test_confirm_pass_refused_on_environment_mismatch(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    path = CS.record_path(repo, ACCOUNT, store)
    before = open(path, "rb").read()
    got = CS.confirm_pass(repo, ACCOUNT, "2026-12-01", environment="env-fixture-two", root=store)
    assert got == {"action": "refused", "reason": "environment-mismatch"}
    assert open(path, "rb").read() == before


def test_record_check_and_confirm_pass_refused_when_store_locked(tmp_path):
    repo, store = _setup_repo(tmp_path)
    _check(repo, store)
    path = CS.record_path(repo, ACCOUNT, store)
    before = open(path, "rb").read()
    with CS.mode_registry.config_lock(repo, store) as held:
        assert held is True
        rewritten = _check(repo, store, environment="env-fixture-two")
        confirmed = CS.confirm_pass(repo, ACCOUNT, "2026-12-01", root=store)
    assert rewritten == {"action": "refused", "reason": "store-locked"}
    assert confirmed == {"action": "refused", "reason": "store-locked"}
    assert open(path, "rb").read() == before


def test_record_check_is_a_noop_when_the_record_is_unchanged(tmp_path):
    repo, store = _setup_repo(tmp_path)
    assert _check(repo, store)["action"] == "written"
    assert _check(repo, store)["action"] == "noop"
    assert _check(repo, store, checked_at="2026-07-03")["action"] == "written"


def test_record_check_malformed_field_is_named(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = _check(repo, store, picks_up_version="true")
    assert got == {"action": "refused", "reason": "malformed-value", "field": "picksUpVersion"}
    assert _record_files(repo, store) == []


def test_calibration_stamp_is_pure_and_order_independent():
    one = {"a.md": b"alpha", "b/c.md": b"beta"}
    two = {"b/c.md": b"beta", "a.md": b"alpha"}
    stamp = CS.calibration_stamp(one)
    assert stamp == CS.calibration_stamp(two)
    assert stamp.startswith("sha256:") and len(stamp) == len("sha256:") + 64
    assert CS.calibration_stamp({"a.md": b"alpha", "b/c.md": b"betA"}) != stamp
    assert CS.calibration_stamp({}) == "none"
    assert CS.calibration_stamp({"a": b"bc"}) != CS.calibration_stamp({"ab": b"c"})
    assert CS.calibration_stamp({"a": b"b", "c": b"d"}) != CS.calibration_stamp({"a": b"bcd"})
    with pytest.raises(TypeError):
        CS.calibration_stamp({1: b"x"})
    with pytest.raises(TypeError):
        CS.calibration_stamp({"a": "text"})


def _account_file(directory, payload):
    os.makedirs(str(directory), exist_ok=True)
    with open(os.path.join(str(directory), ".claude.json"), "w", encoding="utf-8") as fh:
        fh.write(payload if isinstance(payload, str) else json.dumps(payload))


def _oauth(account_id):
    return {"oauthAccount": {"accountUuid": account_id, "billingType": "fixture"}}


def test_launching_account_reads_the_config_dir_account_file(tmp_path):
    config = tmp_path / "cfg"
    _account_file(config, _oauth(ACCOUNT))
    env = {"CLAUDE_CONFIG_DIR": str(config), "HOME": str(tmp_path / "unused-home")}
    assert CS.launching_account(env=env) == ACCOUNT

    home = tmp_path / "home"
    _account_file(home, _oauth(OTHER_ACCOUNT))
    assert CS.launching_account(env={"HOME": str(home)}) == OTHER_ACCOUNT
    assert CS.launching_account(env={"HOME": str(home), "CLAUDE_CONFIG_DIR": "  "}) == OTHER_ACCOUNT

    work = tmp_path / "work"
    _account_file(work / "rel-cfg", _oauth("acct-fixture-three"))
    relative = {"CLAUDE_CONFIG_DIR": "rel-cfg", "HOME": str(home)}
    assert CS.launching_account(env=relative, cwd=str(work)) == "acct-fixture-three"
    assert CS.launching_account(env=relative) is None


@pytest.mark.parametrize("payload", [
    None,
    "not json",
    [],
    {},
    {"oauthAccount": "text"},
    {"oauthAccount": {}},
    {"oauthAccount": {"accountUuid": 7}},
    {"oauthAccount": {"accountUuid": ""}},
    {"oauthAccount": {"accountUuid": "bad account!"}},
    {"oauthAccount": {"accountUuid": "sk-abc" + "x" * 200}},
])
def test_launching_account_unreadable_is_none(tmp_path, payload):
    config = tmp_path / "cfg"
    os.makedirs(str(config))
    if payload is not None:
        _account_file(config, payload)
    assert CS.launching_account(env={"CLAUDE_CONFIG_DIR": str(config)}) is None


def test_switch_messages_are_the_approved_words():
    assert CS.switch_message("on", "demo") == (
        "Cloud builds are on for demo. From the next launch, every build that can run in the "
        "cloud will.\n\n"
        'Say "this one local" at any launch to keep a build on your machine.'
    )
    assert CS.switch_message("off", "demo") == (
        "Cloud builds are off for demo. Builds run on your machine, as before.\n\n"
        "The cloud setup is kept, so switching back on needs no new setup."
    )
    assert CS.switch_message("refused", "demo") == (
        "Cloud builds can't be switched on yet. This project has no cloud setup on this "
        'Claude account. Say "set up cloud builds" and I\'ll walk you through it.'
    )
    with pytest.raises(ValueError):
        CS.switch_message("maybe", "demo")


def _run(main, argv, capsys, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    assert main(argv) == 0
    return json.loads(capsys.readouterr().out)


def test_cli_read_and_record_check_round_trip(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    config = tmp_path / "cfg"
    _account_file(config, _oauth(ACCOUNT))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    common = ["--cwd", repo, "--root", store]

    assert _run(CS.main, ["account", "--cwd", repo], capsys) == {"account": ACCOUNT}
    before = _run(CS.main, ["read", *common], capsys)
    assert before["state"] == "none"

    wrote = _run(CS.main, [
        "record-check", *common,
        "--environment", ENVIRONMENT,
        "--plugin-version", "1.2.3",
        "--picks-up-version", "true",
        "--calibration-stamp", STAMP,
        "--calibration-date", "2026-07-01",
        "--pass-lapses", "2026-08-01",
        "--checked-at", "2026-07-02",
    ], capsys)
    assert wrote["action"] == "written"
    after = _run(CS.main, ["read", *common], capsys)
    assert after["ready"] is True
    assert after["record"] == _record_dict()
    explicit = _run(CS.main, ["read", *common, "--account", OTHER_ACCOUNT], capsys)
    assert explicit["ready"] is False

    confirmed = _run(CS.main, [
        "confirm-pass", *common, "--lapses", "2026-12-01", "--environment", ENVIRONMENT], capsys)
    assert confirmed["action"] == "written"
    assert _run(CS.main, ["read", *common], capsys)["record"]["passLapses"] == "2026-12-01"


def test_cli_set_cloud_builds_resolves_the_launching_account(tmp_path, capsys, monkeypatch):
    repo, store = _setup_repo(tmp_path)
    config = tmp_path / "cfg"
    _account_file(config, _oauth(ACCOUNT))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    common = ["set", "--item", "cloudBuilds", "--cwd", repo, "--root", store,
              "--project-name", "fixture"]

    refused = _run(PC.main, common, capsys, stdin="true", monkeypatch=monkeypatch)
    assert refused["reason"] == "cloud-setup-missing"
    _check(repo, store)
    on = _run(PC.main, common, capsys, stdin="true", monkeypatch=monkeypatch)
    assert on["action"] == "written"
    assert on["message"] == CS.switch_message("on", "fixture")
    off = _run(PC.main, common, capsys, stdin="false", monkeypatch=monkeypatch)
    assert off["message"] == CS.switch_message("off", "fixture")
