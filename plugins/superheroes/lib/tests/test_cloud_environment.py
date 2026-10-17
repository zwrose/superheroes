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
    # axis: the one pinned spelling of Claude Code's settings section and key, and the argv built from it — see bite-proof record c8a_wo3.md
    # The one literal pin of Claude Code's own spelling; everything else reads the adapter's home.
    assert (engine_adapter.CLOUD_SETTINGS_SECTION, engine_adapter.CLOUD_SETTINGS_ENVIRONMENT_KEY) == (
        "remote", "defaultEnvironmentId")
    built = engine_adapter.claude_cloud_builder_argv("opus", None, "p", ENV_ID, "n")
    assert json.loads(built["argv"][built["argv"].index("--settings") + 1]) == {
        "remote": {"defaultEnvironmentId": ENV_ID}}


def test_first_pick_unchanged_asks_to_confirm_by_name(tmp_path):
    # axis: refusal — an unchanged first pick asks to confirm by name (section R6) — see bite-proof record wo_a_1771_environment_reader.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, env=env)
    assert result["action"] == "not-picked"
    assert result["reason"] == "pick-unchanged"
    assert result["environment"] is None
    assert result["message"] == CE._ALREADY_PICKED


def test_first_pick_confirmed_by_name_returns_the_id(tmp_path):
    # axis: retry-keeps-or-asks — an unchanged value equal to the confirmed id is kept — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "picked"
    assert result["reason"] == "kept-confirmed"
    assert result["environment"] == ENV_ID


def test_pick_unchanged_setting_asks_again_with_no_id(tmp_path):
    # axis: refusal — an unchanged value is no pick and gives no id (section R1) — see bite-proof record wo_a_1771_environment_reader.md
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
    # axis: refusal and grammar — a missing or malformed value is no pick and gives no id (sections R2, R3) — see bite-proof record wo_a_1771_environment_reader.md
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
    # axis: the picked id — a changed, well-formed value is returned as the new id — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=before, env=env)
    assert result == {"action": "picked", "reason": None, "environment": OTHER_ENV_ID,
                      "message": CE._PICKED}


def test_snapshot_reads_the_current_value_and_none_when_never_picked(tmp_path):
    # axis: snapshot-reads — the current well-formed value, or none-set when never picked — see bite-proof record c8a_wo3.md
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
    # axis: never-raises/unreadable — a file that cannot be understood never gives an id — see bite-proof record c8a_wo3.md
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
    # axis: never-raises/unreadable — an unresolvable config directory is unreadable, not a raise — see bite-proof record c8a_wo3.md
    env = {"CLAUDE_CONFIG_DIR": "relative/dir"}
    assert CE.settings_path(env=env) is None
    assert CE.snapshot(env=env)["reason"] == "settings-unreadable"
    result = CE.pick(env=env)
    assert result["action"] == "not-picked" and result["reason"] == "settings-unreadable"
    assert result["environment"] is None


def test_unexpected_exception_is_reported_as_unreadable(tmp_path, monkeypatch):
    # axis: never-raises/unreadable — an unexpected exception in the read is reported as unreadable — see bite-proof record c8a_wo3.md
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
    # axis: refuses-malformed — a before value that is not an environment id is refused — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=before, env=env)
    assert result["action"] == "refused" and result["reason"] == "before-invalid"
    assert result["environment"] is None
    assert result["message"] == "The value read before the pick is not an environment id."


def test_pick_refuses_a_malformed_before_before_reading_the_file(tmp_path):
    # axis: refuses-malformed — a malformed before is refused before the settings file is read — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _make_directory(env)
    assert CE.pick(before="abc", env=env)["reason"] == "before-invalid"


def test_reader_follows_the_account_config_dir(tmp_path):
    # axis: snapshot-reads — the read follows the account's config directory — see bite-proof record c8a_wo3.md
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
    # axis: message wording — no reader message asks the owner to type, paste or copy an id — see bite-proof record c8a_wo3.md
    messages = [value for name, value in vars(CE).items()
                if name.startswith("_") and name.isupper() and isinstance(value, str)]
    assert len(messages) == 10
    for message in messages:
        assert not re.search(r"\b(type|paste|copy)\b", message, re.IGNORECASE), message


def _run(capsys, argv):
    code = CE.main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    # axis: CLI exit-code mapping for snapshot and pick — see bite-proof record c8a_wo3.md
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
    # axis: retry-keeps-or-asks — the same environment on a retry keeps the confirmed id — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result == {"action": "picked", "reason": "kept-confirmed", "environment": ENV_ID,
                      "message": CE._KEPT}


def test_retry_with_a_different_environment_returns_the_new_id(tmp_path):
    # axis: retry-keeps-or-asks — a different environment on a retry returns the new id — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result == {"action": "picked", "reason": None, "environment": OTHER_ENV_ID,
                      "message": CE._PICKED}


def test_retry_unchanged_value_that_is_not_the_confirmed_id_asks_again(tmp_path):
    # axis: retry-keeps-or-asks — an unchanged value that is not the confirmed id asks again — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.pick(before=OTHER_ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "pick-unchanged"
    assert result["environment"] is None
    assert result["message"] == CE._ASK_AGAIN
    assert result["message"] != CE._ALREADY_PICKED


@pytest.mark.parametrize("content", _MISSING)
def test_retry_with_a_missing_value_asks_again(tmp_path, content):
    # axis: retry-keeps-or-asks — a missing value on a retry asks again — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    if content is not None:
        _write(env, content)
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "pick-missing"
    assert result["environment"] is None and result["message"] == CE._ASK_AGAIN


def test_retry_with_an_unreadable_file_asks_again(tmp_path):
    # axis: retry-keeps-or-asks — an unreadable file on a retry asks again, with no id — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _make_invalid_json(env)
    result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
    assert result["action"] == "not-picked" and result["reason"] == "settings-unreadable"
    assert result["environment"] is None


@pytest.mark.parametrize("confirmed", ["abc", "", "env_", 123])
def test_pick_refuses_a_malformed_confirmed(tmp_path, confirmed):
    # axis: refuses-malformed — a confirmed value that is not an environment id is refused — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.pick(before=ENV_ID, confirmed=confirmed, env=env)
    assert result["action"] == "refused" and result["reason"] == "confirmed-invalid"
    assert result["environment"] is None


def test_cli_confirmed_retry(tmp_path, monkeypatch, capsys):
    # axis: retry-keeps-or-asks — the command line passes --confirmed through and keeps the id — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", env["CLAUDE_CONFIG_DIR"])
    monkeypatch.setenv("HOME", env["HOME"])
    _write(env, _with_value(ENV_ID))
    code, out = _run(capsys, ["pick", "--before", ENV_ID, "--confirmed", ENV_ID])
    assert code == 0 and out["reason"] == "kept-confirmed" and out["environment"] == ENV_ID
    code, out = _run(capsys, ["pick", "--before", ENV_ID, "--confirmed", "abc"])
    assert code == 1 and out["reason"] == "confirmed-invalid"


def test_cli_relative_config_dir_with_relative_cwd_reads(tmp_path, monkeypatch, capsys):
    # axis: snapshot-reads — a relative config directory with a relative cwd is read — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", env["HOME"])
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "acct")
    code, out = _run(capsys, ["snapshot", "--cwd", "."])
    assert code == 0 and out == {"action": "read", "reason": None, "environment": ENV_ID}


def test_compare_matched_when_the_id_is_the_picked_environment(tmp_path):
    # axis: compare-verdict — the id about to be used is the picked one: matched — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
    assert result["action"] == "matched" and result["environment"] == ENV_ID


def test_compare_mismatched_returns_the_current_picked_environment(tmp_path):
    # axis: compare-verdict — a different picked environment: mismatched, with the picked id — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
    assert result["action"] == "mismatched"
    assert result["environment"] == OTHER_ENV_ID
    assert result["message"] == CE._MISMATCHED
    assert "use the picked one" in result["message"]


@pytest.mark.parametrize("content", [None, "not json", {}, _with_value("bad id")])
def test_compare_unchecked_without_a_valid_current_pick(tmp_path, content):
    # axis: compare-verdict — no readable, valid current pick: unchecked — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    if content is not None:
        _write(env, content)
    result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
    assert result["action"] == "unchecked" and result["environment"] is None
    assert result["message"] == CE._UNCHECKED


@pytest.mark.parametrize("environment", [None, "", "bad id", 5])
def test_compare_unchecked_for_a_malformed_environment(tmp_path, environment):
    # axis: compare-verdict — a malformed id to compare: unchecked — see bite-proof record c8a_wo3.md
    env = _env(tmp_path)
    _write(env, _with_value(ENV_ID))
    result = CE.compare(environment, env=env, cwd=str(tmp_path))
    assert result["action"] == "unchecked" and result["environment"] is None


def test_compare_never_raises(tmp_path, monkeypatch):
    # axis: never-raises/unreadable — compare reports unchecked when the read raises — see bite-proof record c8a_wo3.md
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(CE, "_read", boom)
    result = CE.compare(ENV_ID, env=_env(tmp_path), cwd=str(tmp_path))
    assert result["action"] == "unchecked"


def test_compare_cli_exit_codes(tmp_path, monkeypatch, capsys):
    # axis: compare-verdict — matched exits 0, mismatched and unchecked exit 1 — see bite-proof record c8a_wo3.md
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


THIRD_ENV_ID = "env_05MNOpqr"
ACCOUNT = "acct-fixture-one"
OTHER_ACCOUNT = "acct-fixture-two"


def _signed_in(env, account=ACCOUNT):
    with open(os.path.join(env["CLAUDE_CONFIG_DIR"], ".claude.json"), "w", encoding="utf-8") as fh:
        json.dump({"oauthAccount": {"accountUuid": account}}, fh)


def _record(tmp_path, environment, account=ACCOUNT, **over):
    repo, store = str(tmp_path), str(tmp_path / "store")
    record = {
        "schema": CE.cloud_setup.SCHEMA, "account": account, "environment": environment,
        "pluginVersion": "1.2.3", "picksUpVersion": True, "calibrationStamp": "none",
        "calibrationDate": "2026-10-01", "passLapses": "2099-01-01", "checkedAt": "2026-10-02",
    }
    record.update(over)
    path = CE.cloud_setup.record_path(repo, account, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    return repo, store


def test_compare_matches_the_recorded_id_when_the_shared_pick_names_another(tmp_path):
    # axis: recorded-match — after first setup the record's id matches whatever the shared pick holds — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _signed_in(env)
    _write(env, _with_value(OTHER_ENV_ID))
    repo, store = _record(tmp_path, ENV_ID)
    result = CE.compare(ENV_ID, env=env, cwd=repo, root=store)
    assert result == {"action": "matched", "reason": "recorded", "environment": ENV_ID}


def test_compare_matches_the_recorded_id_with_no_readable_pick(tmp_path):
    # axis: recorded-match — the record's id matches without reading the picker at all — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _signed_in(env)
    _write(env, "not json")
    repo, store = _record(tmp_path, ENV_ID)
    result = CE.compare(ENV_ID, env=env, cwd=repo, root=store)
    assert result["action"] == "matched" and result["reason"] == "recorded"


@pytest.mark.parametrize("environment", [THIRD_ENV_ID, OTHER_ENV_ID])
def test_compare_refuses_an_id_other_than_the_record_toward_the_record(tmp_path, environment):
    # axis: recorded-refuses — a recorded account refuses any other id, even one the shared pick names, and points back to the record — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _signed_in(env)
    _write(env, _with_value(OTHER_ENV_ID))
    repo, store = _record(tmp_path, ENV_ID)
    result = CE.compare(environment, env=env, cwd=repo, root=store)
    assert result["action"] == "mismatched" and result["reason"] == "recorded-differs"
    assert result["environment"] == ENV_ID
    assert result["message"] == CE._RECORDED_DIFFERS


def test_compare_a_move_goes_to_the_picker(tmp_path):
    # axis: recorded-refuses — on a move the record is set aside and the shared pick decides — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _signed_in(env)
    _write(env, _with_value(OTHER_ENV_ID))
    repo, store = _record(tmp_path, ENV_ID)
    result = CE.compare(OTHER_ENV_ID, env=env, cwd=repo, root=store, moving=True)
    assert result == {"action": "matched", "reason": None, "environment": OTHER_ENV_ID}
    result = CE.compare(ENV_ID, env=env, cwd=repo, root=store, moving=True)
    assert result["action"] == "mismatched" and result["reason"] == "picked-differs"
    assert result["environment"] == OTHER_ENV_ID
    result = CE.compare(THIRD_ENV_ID, env=env, cwd=repo, root=store, moving=True)
    assert result["action"] == "mismatched" and result["environment"] == OTHER_ENV_ID
    _write(env, "not json")
    result = CE.compare(THIRD_ENV_ID, env=env, cwd=repo, root=store, moving=True)
    assert result["action"] == "unchecked" and result["environment"] is None


def test_compare_first_setup_with_no_record_still_needs_the_pick(tmp_path):
    # axis: recorded-match — with no record the shared pick decides, as before — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _signed_in(env)
    repo, store = str(tmp_path), str(tmp_path / "store")
    _write(env, _with_value(OTHER_ENV_ID))
    result = CE.compare(ENV_ID, env=env, cwd=repo, root=store)
    assert result["action"] == "mismatched" and result["environment"] == OTHER_ENV_ID
    _write(env, _with_value(ENV_ID))
    result = CE.compare(ENV_ID, env=env, cwd=repo, root=store)
    assert result == {"action": "matched", "reason": None, "environment": ENV_ID}


@pytest.mark.parametrize("case", ["other-account", "signed-out", "invalid-record"])
def test_compare_a_record_that_is_not_this_accounts_valid_one_never_matches(tmp_path, case):
    # axis: recorded-match — only a valid record for the signed-in account matches without the picker — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _write(env, _with_value(OTHER_ENV_ID))
    if case == "other-account":
        _signed_in(env, OTHER_ACCOUNT)
        repo, store = _record(tmp_path, ENV_ID)
    elif case == "signed-out":
        repo, store = _record(tmp_path, ENV_ID)
    else:
        _signed_in(env)
        repo, store = _record(tmp_path, ENV_ID, pluginVersion="not a version")
    result = CE.compare(ENV_ID, env=env, cwd=repo, root=store)
    assert result["action"] == "mismatched" and result["environment"] == OTHER_ENV_ID


def test_compare_cli_matches_the_recorded_id(tmp_path, monkeypatch, capsys):
    # axis: recorded-match — the command line reads the record from the project's store — see bite-proof record c1918_recorded_environment.md
    env = _env(tmp_path)
    _signed_in(env)
    _write(env, _with_value(OTHER_ENV_ID))
    repo, store = _record(tmp_path, ENV_ID)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", env["CLAUDE_CONFIG_DIR"])
    monkeypatch.setenv("HOME", env["HOME"])
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    code, out = _run(capsys, ["compare", "--environment", ENV_ID, "--cwd", repo])
    assert code == 0 and out == {"action": "matched", "reason": "recorded", "environment": ENV_ID}
    code, out = _run(capsys, ["compare", "--environment", OTHER_ENV_ID, "--cwd", repo])
    assert code == 1 and out["action"] == "mismatched" and out["environment"] == ENV_ID
    code, out = _run(capsys, ["compare", "--environment", OTHER_ENV_ID, "--cwd", repo, "--moving"])
    assert code == 0 and out == {"action": "matched", "reason": None, "environment": OTHER_ENV_ID}
