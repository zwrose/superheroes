"""Tests for cloud_environment: the reader for the environment the owner picked with /remote-env.

Every test builds its Claude config directory under tmp_path and passes an explicit env mapping, so
nothing reads the real home directory or the process environment. No test touches the network.
"""
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_environment as CE  # noqa: E402
import engine_adapter  # noqa: E402

ENV_ID = "env_01ABCdef"
OTHER_ENV_ID = "env_09ZYXwvu"


def _env(tmp_path, name="acct"):
    directory = tmp_path / name
    directory.mkdir(exist_ok=True)
    return {"CLAUDE_CONFIG_DIR": str(directory), "HOME": str(tmp_path)}


def _settings(env):
    return os.path.join(env["CLAUDE_CONFIG_DIR"], "settings.json")


def _write(env, data):
    with open(_settings(env), "w", encoding="utf-8") as fh:
        fh.write(data if isinstance(data, str) else json.dumps(data))


def _with_value(value):
    return {engine_adapter.CLOUD_SETTINGS_SECTION: {engine_adapter.CLOUD_SETTINGS_ENVIRONMENT_KEY: value}}


def test_settings_path_has_one_home_and_the_external_spelling_is_pinned():
    # The one literal pin of Claude Code's own spelling; everything else reads the adapter's home.
    assert (engine_adapter.CLOUD_SETTINGS_SECTION, engine_adapter.CLOUD_SETTINGS_ENVIRONMENT_KEY) == (
        "remote", "defaultEnvironmentId")
    built = engine_adapter.claude_cloud_builder_argv("opus", None, "p", ENV_ID, "n")
    assert json.loads(built["argv"][built["argv"].index("--settings") + 1]) == {
        "remote": {"defaultEnvironmentId": ENV_ID}}


def test_first_pick_unchanged_asks_to_confirm_by_name(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, env=env)
    assert result["action"] == "not-picked"
    assert result["reason"] == "pick-unchanged"
    assert result["environment"] is None
    assert result["message"] == CE._ALREADY_PICKED


def test_first_pick_confirmed_by_name_returns_the_id(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "picked"
    assert result["reason"] == "kept-confirmed"
    assert result["environment"] == ENV_ID


def test_pick_unchanged_setting_asks_again_with_no_id(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, env=env)
    assert result["action"] == "not-picked"
    assert result["reason"] == "pick-unchanged"
    assert result["environment"] is None
    assert result["message"] == CE._ALREADY_PICKED


_MISSING = [
    pytest.param(None, id="no-file"),
    pytest.param({}, id="empty-object"),
    pytest.param({"remote": {}}, id="remote-empty"),
    pytest.param({"remote": "x"}, id="remote-not-object"),
    pytest.param(_with_value("env_ab-cd"), id="malformed-value"),
    pytest.param(_with_value("env_"), id="bare-prefix"),
    pytest.param(_with_value(" env_abc"), id="leading-space"),
    pytest.param(_with_value(123), id="number"),
    pytest.param(_with_value(None), id="null"),
]


@pytest.mark.parametrize("before", [None, ENV_ID])
@pytest.mark.parametrize("content", _MISSING)
def test_pick_missing_setting_asks_again_with_no_id(tmp_path, content, before):
    env = _env(tmp_path)
    if content is not None:
        _write(env, content)
    result = CE.pick(before=before, env=env)
    assert result["action"] == "not-picked"
    assert result["reason"] == "pick-missing"
    assert result["environment"] is None
    assert result["message"] == CE._ASK_AGAIN


@pytest.mark.parametrize("before", [ENV_ID, None])
def test_pick_changed_setting_returns_the_new_id(tmp_path, before):
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=before, env=env)
    assert result == {"action": "picked", "reason": None, "environment": OTHER_ENV_ID,
                      "message": CE._PICKED}


def test_snapshot_reads_the_current_value_and_none_when_never_picked(tmp_path):
    env = _env(tmp_path)
    assert CE.snapshot(env=env) == {"action": "read", "reason": "none-set", "environment": None}
    _write(env, {"remote": {}})
    assert CE.snapshot(env=env) == {"action": "read", "reason": "none-set", "environment": None}
    _write(env, _with_value("env_ab-cd"))
    assert CE.snapshot(env=env) == {"action": "read", "reason": "none-set", "environment": None}
    _write(env, _with_value(ENV_ID))
    assert CE.snapshot(env=env) == {"action": "read", "reason": None, "environment": ENV_ID}


def _make_invalid_json(env):
    _write(env, "{not json")


def _make_list(env):
    _write(env, ["remote"])


def _make_bad_utf8(env):
    with open(_settings(env), "wb") as fh:
        fh.write(b'{"remote": {"defaultEnvironmentId": "env_\xff\xfe"}}')


def _make_directory(env):
    os.mkdir(_settings(env))


@pytest.mark.parametrize("make", [_make_invalid_json, _make_list, _make_bad_utf8, _make_directory],
                         ids=["invalid-json", "top-level-list", "invalid-utf8", "directory"])
def test_unreadable_settings_never_give_an_id(tmp_path, make):
    env = _env(tmp_path)
    make(env)
    snap = CE.snapshot(env=env)
    assert snap["action"] == "refused" and snap["reason"] == "settings-unreadable"
    assert snap["environment"] is None and snap["message"] == CE._UNREADABLE
    for before in (None, ENV_ID):
        result = CE.pick(before=before, env=env)
        assert result["action"] == "not-picked" and result["reason"] == "settings-unreadable"
        assert result["environment"] is None and result["message"] == CE._UNREADABLE


def test_unresolvable_config_dir_is_unreadable_not_a_raise():
    env = {"CLAUDE_CONFIG_DIR": "relative/dir"}
    assert CE.settings_path(env=env) is None
    assert CE.snapshot(env=env)["reason"] == "settings-unreadable"
    result = CE.pick(env=env)
    assert result["action"] == "not-picked" and result["reason"] == "settings-unreadable"
    assert result["environment"] is None


def test_unexpected_exception_is_reported_as_unreadable(tmp_path, monkeypatch):
    env = _env(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(CE, "_read", boom)
    snap = CE.snapshot(env=env)
    assert snap["action"] == "refused" and snap["reason"] == "settings-unreadable"
    result = CE.pick(before=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "settings-unreadable"
    assert result["environment"] is None


@pytest.mark.parametrize("before", ["abc", "", "env_", 123])
def test_pick_refuses_a_malformed_before(tmp_path, before):
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=before, env=env)
    assert result["action"] == "refused" and result["reason"] == "before-invalid"
    assert result["environment"] is None
    assert result["message"] == "The value read before the pick is not an environment id."


def test_pick_refuses_a_malformed_before_before_reading_the_file(tmp_path):
    env = _env(tmp_path)
    _make_directory(env)
    assert CE.pick(before="abc", env=env)["reason"] == "before-invalid"


def test_reader_follows_the_account_config_dir(tmp_path):
    one = _env(tmp_path, "one")
    two = _env(tmp_path, "two")
    _write(one, _with_value(ENV_ID))
    _write(two, _with_value(OTHER_ENV_ID))
    assert CE.settings_path(env=one) == os.path.join(one["CLAUDE_CONFIG_DIR"], "settings.json")
    assert CE.snapshot(env=one)["environment"] == ENV_ID
    assert CE.snapshot(env=two)["environment"] == OTHER_ENV_ID
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps(_with_value("env_0HOMEdefault")))
    default_env = {"HOME": str(home)}
    assert CE.settings_path(env=default_env) == str(home / ".claude" / "settings.json")
    assert CE.snapshot(env=default_env)["environment"] == "env_0HOMEdefault"


def test_no_message_asks_to_type_or_paste_an_id():
    messages = [value for name, value in vars(CE).items()
                if name.startswith("_") and name.isupper() and isinstance(value, str)]
    assert len(messages) == 9
    for message in messages:
        assert not re.search(r"\b(type|paste|copy)\b", message, re.IGNORECASE), message


def _run(capsys, argv):
    code = CE.main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", env["CLAUDE_CONFIG_DIR"])
    monkeypatch.setenv("HOME", env["HOME"])
    _write(env, _with_value(ENV_ID))
    code, out = _run(capsys, ["snapshot"])
    assert code == 0 and out == {"action": "read", "reason": None, "environment": ENV_ID}
    _write(env, _with_value(OTHER_ENV_ID))
    code, out = _run(capsys, ["pick", "--before", ENV_ID])
    assert code == 0 and out["action"] == "picked" and out["environment"] == OTHER_ENV_ID
    code, out = _run(capsys, ["pick", "--before", OTHER_ENV_ID])
    assert code == 1 and out["reason"] == "pick-unchanged" and out["environment"] is None
    code, out = _run(capsys, ["pick", "--before", "abc"])
    assert code == 1 and out["reason"] == "before-invalid"


def test_retry_with_the_same_environment_keeps_the_confirmed_id(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result == {"action": "picked", "reason": "kept-confirmed", "environment": ENV_ID,
                      "message": CE._KEPT}


def test_retry_with_a_different_environment_returns_the_new_id(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result == {"action": "picked", "reason": None, "environment": OTHER_ENV_ID,
                      "message": CE._PICKED}


def test_retry_unchanged_value_that_is_not_the_confirmed_id_asks_again(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=OTHER_ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "pick-unchanged"
    assert result["environment"] is None
    assert result["message"] == CE._ASK_AGAIN
    assert result["message"] != CE._ALREADY_PICKED


@pytest.mark.parametrize("content", _MISSING)
def test_retry_with_a_missing_value_asks_again(tmp_path, content):
    env = _env(tmp_path)
    if content is not None:
        _write(env, content)
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "pick-missing"
    assert result["environment"] is None and result["message"] == CE._ASK_AGAIN


def test_retry_with_an_unreadable_file_asks_again(tmp_path):
    env = _env(tmp_path)
    _make_invalid_json(env)
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "settings-unreadable"
    assert result["environment"] is None


@pytest.mark.parametrize("confirmed", ["abc", "", "env_", 123])
def test_pick_refuses_a_malformed_confirmed(tmp_path, confirmed):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=confirmed, env=env)
    assert result["action"] == "refused" and result["reason"] == "confirmed-invalid"
    assert result["environment"] is None


def test_cli_confirmed_retry(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", env["CLAUDE_CONFIG_DIR"])
    monkeypatch.setenv("HOME", env["HOME"])
    _write(env, _with_value(ENV_ID))
    code, out = _run(capsys, ["pick", "--before", ENV_ID, "--confirmed", ENV_ID])
    assert code == 0 and out["reason"] == "kept-confirmed" and out["environment"] == ENV_ID
    code, out = _run(capsys, ["pick", "--before", ENV_ID, "--confirmed", "abc"])
    assert code == 1 and out["reason"] == "confirmed-invalid"


def test_cli_relative_config_dir_with_relative_cwd_reads(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", env["HOME"])
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "acct")
    code, out = _run(capsys, ["snapshot", "--cwd", "."])
    assert code == 0 and out == {"action": "read", "reason": None, "environment": ENV_ID}


def test_compare_matched_when_the_id_is_the_picked_environment(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
    assert result["action"] == "matched" and result["environment"] == ENV_ID


def test_compare_mismatched_returns_the_current_picked_environment(tmp_path):
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
    assert result["action"] == "mismatched"
    assert result["environment"] == OTHER_ENV_ID
    assert result["message"] == CE._MISMATCHED
    assert "use the picked one" in result["message"]


@pytest.mark.parametrize("content", [None, "not json", {}, _with_value("bad id")])
def test_compare_unchecked_without_a_valid_current_pick(tmp_path, content):
    env = _env(tmp_path)
    if content is not None:
        _write(env, content)
    result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
    assert result["action"] == "unchecked" and result["environment"] is None
    assert result["message"] == CE._UNCHECKED


@pytest.mark.parametrize("environment", [None, "", "bad id", 5])
def test_compare_unchecked_for_a_malformed_environment(tmp_path, environment):
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.compare(environment, env=env, cwd=str(tmp_path))
    assert result["action"] == "unchecked" and result["environment"] is None


def test_compare_never_raises(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(CE, "_read", boom)
    result = CE.compare(ENV_ID, env=_env(tmp_path), cwd=str(tmp_path))
    assert result["action"] == "unchecked"


def test_compare_cli_exit_codes(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", env["CLAUDE_CONFIG_DIR"])
    monkeypatch.setenv("HOME", env["HOME"])
    _write(env, _with_value(ENV_ID))
    code, out = _run(capsys, ["compare", "--environment", ENV_ID])
    assert code == 0 and out["action"] == "matched"
    code, out = _run(capsys, ["compare", "--environment", OTHER_ENV_ID])
    assert code == 1 and out["action"] == "mismatched" and out["environment"] == ENV_ID
    code, out = _run(capsys, ["compare", "--environment", "bad id"])
    assert code == 1 and out["action"] == "unchecked"
    code, out = _run(capsys, ["compare"])
    assert code == 1 and out["action"] == "unchecked"
