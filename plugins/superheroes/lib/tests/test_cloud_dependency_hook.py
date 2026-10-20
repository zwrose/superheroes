"""Tests for cloud_dependency_hook (#2009): the cloud dependency hook module.

Every fixture project is a real git repository under tmp_path, and the generated script is run with
bash against it. The script's environment is built explicitly, so an inherited CLAUDE_CODE_REMOTE
(or git configuration) cannot leak in. No test touches the network or the real home directory.
"""
import copy
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_dependency_hook as hook  # noqa: E402

COMMANDS = ["echo one >> ran.txt", "echo two >> ran.txt", "echo three >> ran.txt"]
INPUTS = ["package-lock.json", "uv.lock"]


def _env(remote=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.devnull,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    if remote is not None:
        env["CLAUDE_CODE_REMOTE"] = remote
    return env


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), env=_env(), check=True)
    return root


def _installed(repo, commands=COMMANDS, inputs=INPUTS):
    result = hook.sync(str(repo), commands, inputs, True)
    assert result["action"] == "written", result
    return str(repo / hook.SCRIPT_REL.replace("/", os.sep))


def _run(script, *args, remote="true"):
    return subprocess.run(["bash", script, *args], env=_env(remote), capture_output=True,
                          text=True, timeout=60)


def _state(repo):
    path = repo / ".git" / hook.HASH_NAME
    return path.read_text() if path.exists() else None


def _ran(repo):
    path = repo / "ran.txt"
    return path.read_text().split() if path.exists() else []


def _record(repo, script, commands=COMMANDS, inputs=INPUTS):
    done = _run(script, "--record", hook.fingerprint(commands, inputs), remote=None)
    assert (done.returncode, done.stdout) == (0, "")
    assert _state(repo)


@pytest.mark.parametrize("remote", [None, "false", ""])
def test_outside_the_cloud_runs_nothing(repo, remote):
    script = _installed(repo)
    done = _run(script, remote=remote)
    assert (done.returncode, done.stdout) == (0, "")
    assert _ran(repo) == []
    assert _state(repo) is None
    assert not (repo / ".git" / hook.LOG_NAME).exists()


def test_cloud_unchanged_hash_runs_nothing(repo):
    (repo / "package-lock.json").write_text("{}\n")
    script = _installed(repo)
    _record(repo, script)
    before = _state(repo)
    done = _run(script)
    assert (done.returncode, done.stdout) == (0, "")
    assert _ran(repo) == []
    assert _state(repo) == before


def test_cloud_changed_hash_runs_commands_in_order_and_records(repo):
    (repo / "package-lock.json").write_text("{}\n")
    script = _installed(repo)
    _record(repo, script)
    recorded = _state(repo)
    (repo / "package-lock.json").write_text('{"changed": true}\n')
    done = _run(script)
    assert (done.returncode, done.stdout) == (0, "")
    assert _ran(repo) == ["one", "two", "three"]
    assert _state(repo) != recorded
    again = _run(script)
    assert (again.returncode, again.stdout) == (0, "")
    assert _ran(repo) == ["one", "two", "three"]


def test_cloud_never_recorded_runs_commands(repo):
    script = _installed(repo)
    done = _run(script)
    assert (done.returncode, done.stdout) == (0, "")
    assert _ran(repo) == ["one", "two", "three"]
    assert _state(repo)


def test_cloud_failed_command_prints_one_line_and_keeps_state(repo):
    commands = ["echo one >> ran.txt", "false", "echo three >> ran.txt"]
    (repo / "package-lock.json").write_text("{}\n")
    script = _installed(repo, commands)
    _record(repo, script, commands)
    recorded = _state(repo)
    (repo / "package-lock.json").write_text("changed\n")
    done = _run(script)
    assert done.returncode == 0
    assert done.stdout == (
        "superheroes: cloud setup command 2 failed, so dependencies may be out of date; "
        "the next session tries again (log: .git/%s)\n" % hook.LOG_NAME)
    assert done.stdout.count("\n") == 1
    assert "command 2 failed" in done.stdout
    assert _ran(repo) == ["one"]
    # the old success hash goes before the commands run, so a failed run leaves none
    assert recorded is not None
    assert _state(repo) is None


def test_cloud_pipefail_failure_counts_as_a_failure(repo):
    script = _installed(repo, ["false | cat", "echo after >> ran.txt"], [])
    done = _run(script)
    assert done.returncode == 0
    assert "command 1 failed" in done.stdout
    assert _ran(repo) == []
    assert _state(repo) is None


def test_record_with_wrong_fingerprint_exits_2_and_records_nothing(repo):
    script = _installed(repo)
    done = _run(script, "--record", "not-the-fingerprint", remote=None)
    assert done.returncode == 2
    assert done.stdout.startswith("superheroes: dependency hook not recorded:")
    assert done.stdout.count("\n") == 1
    assert _state(repo) is None
    missing = _run(script, "--record", remote=None)
    assert missing.returncode == 2
    assert missing.stdout.startswith("superheroes: dependency hook not recorded:")
    assert _state(repo) is None


def test_record_that_cannot_write_its_state_exits_2(repo):
    script = _installed(repo)
    (repo / ".git" / hook.HASH_NAME).mkdir()
    done = _run(script, "--record", hook.fingerprint(COMMANDS, INPUTS), remote=None)
    assert done.returncode == 2
    assert done.stdout.startswith("superheroes: dependency hook not recorded:")
    assert done.stdout.count("\n") == 1


def test_record_outside_a_git_repository_exits_2_and_a_plain_run_exits_0(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    script = _installed(root)
    recorded = _run(script, "--record", hook.fingerprint(COMMANDS, INPUTS), remote=None)
    assert recorded.returncode == 2
    assert recorded.stdout.startswith("superheroes: dependency hook skipped:")
    assert _run(script).returncode == 0


def test_record_bypasses_the_cloud_guard_and_the_next_cloud_run_is_a_noop(repo):
    script = _installed(repo)
    _record(repo, script)
    assert _state(repo).strip().isalnum()
    assert _run(script).stdout == ""
    assert _ran(repo) == []


def test_missing_input_hashes_differently_from_an_empty_one(repo):
    script = _installed(repo, COMMANDS, ["package-lock.json"])
    _run(script, "--record", hook.fingerprint(COMMANDS, ["package-lock.json"]), remote=None)
    missing = _state(repo)
    (repo / "package-lock.json").write_text("")
    _run(script, "--record", hook.fingerprint(COMMANDS, ["package-lock.json"]), remote=None)
    empty = _state(repo)
    assert missing and empty and missing != empty


def test_empty_input_list_works(repo):
    script = _installed(repo, COMMANDS, [])
    _record(repo, script, COMMANDS, [])
    assert _run(script).stdout == ""
    assert _ran(repo) == []


def test_empty_input_list_runs_on_first_cloud_session(repo):
    script = _installed(repo, COMMANDS, [])
    done = _run(script)
    assert (done.returncode, done.stdout) == (0, "")
    assert _ran(repo) == ["one", "two", "three"]


def test_values_with_shell_metacharacters_are_quoted(repo):
    odd = "weird name's $(touch pwned).lock"
    (repo / odd).write_text("x")
    commands = ["echo \"it's $((1 + 1))\" >> ran.txt"]
    script = _installed(repo, commands, [odd])
    done = _run(script)
    assert (done.returncode, done.stdout) == (0, "")
    assert (repo / "ran.txt").read_text() == "it's 2\n"
    assert not (repo / "pwned").exists()


def test_outside_a_git_repository_prints_one_skipped_line(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    script = _installed(root)
    done = _run(script)
    assert done.returncode == 0
    assert done.stdout.startswith("superheroes: dependency hook skipped:")
    assert done.stdout.count("\n") == 1
    assert not (root / "ran.txt").exists()


def test_unreadable_input_prints_one_skipped_line_and_runs_nothing(repo):
    script = _installed(repo, COMMANDS, ["uv.lock"])
    (repo / "uv.lock").write_text("x")
    os.chmod(str(repo / "uv.lock"), 0)
    try:
        if os.access(str(repo / "uv.lock"), os.R_OK):
            pytest.skip("the file stays readable (running as root)")
        done = _run(script)
    finally:
        os.chmod(str(repo / "uv.lock"), 0o644)
    assert done.returncode == 0
    assert done.stdout.startswith("superheroes: dependency hook skipped:")
    assert done.stdout.count("\n") == 1
    assert _ran(repo) == []


def test_fingerprint_changes_with_commands_and_inputs():
    base = hook.fingerprint(COMMANDS, INPUTS)
    assert base == hook.fingerprint(tuple(COMMANDS), tuple(INPUTS))
    assert len(base) == 64
    assert hook.fingerprint(COMMANDS[:2], INPUTS) != base
    assert hook.fingerprint(list(reversed(COMMANDS)), INPUTS) != base
    assert hook.fingerprint(COMMANDS, INPUTS[:1]) != base
    assert hook.fingerprint(COMMANDS, list(reversed(INPUTS))) != base


def _hook_files(repo):
    script = repo / hook.SCRIPT_REL.replace("/", os.sep)
    settings = repo / hook.SETTINGS_REL.replace("/", os.sep)
    return script, settings


def _ours(obj):
    return [h for g in obj.get("hooks", {}).get("SessionStart", []) for h in g["hooks"]
            if hook.SCRIPT_REL in h.get("command", "")]


def test_sync_write_noop_regenerate_remove(repo):
    script, settings = _hook_files(repo)
    first = hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert first == {"action": "written", "reason": None,
                     "changed": sorted([hook.SCRIPT_REL, hook.SETTINGS_REL])}
    assert script.read_text() == hook.script_text(COMMANDS, INPUTS)
    assert os.stat(str(script)).st_mode & 0o777 == 0o755
    assert json.loads(settings.read_text()) == {"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": hook.HOOK_COMMAND, "timeout": hook.HOOK_TIMEOUT_SECONDS}]}]}}
    assert settings.read_text().endswith("}\n")

    assert hook.sync(str(repo), COMMANDS, INPUTS, True) == {
        "action": "noop", "reason": None, "changed": []}

    changed = hook.sync(str(repo), COMMANDS[:2], INPUTS, True)
    assert changed == {"action": "written", "reason": None, "changed": [hook.SCRIPT_REL]}
    assert script.read_text() == hook.script_text(COMMANDS[:2], INPUTS)
    assert len(_ours(json.loads(settings.read_text()))) == 1

    removed = hook.sync(str(repo), COMMANDS[:2], INPUTS, False)
    assert removed == {"action": "removed", "reason": None,
                       "changed": sorted([hook.SCRIPT_REL, hook.SETTINGS_REL])}
    assert not script.exists() and not settings.exists()
    assert hook.sync(str(repo), COMMANDS[:2], INPUTS, False)["action"] == "noop"


def test_sync_repairs_a_script_that_lost_its_mode_or_was_edited(repo):
    script, _ = _hook_files(repo)
    hook.sync(str(repo), COMMANDS, INPUTS, True)
    os.chmod(str(script), 0o644)
    assert hook.sync(str(repo), COMMANDS, INPUTS, True)["changed"] == [hook.SCRIPT_REL]
    assert os.stat(str(script)).st_mode & 0o777 == 0o755
    script.write_text("# hand edited\n")
    assert hook.sync(str(repo), COMMANDS, INPUTS, True)["changed"] == [hook.SCRIPT_REL]
    assert script.read_text() == hook.script_text(COMMANDS, INPUTS)


def test_sync_empty_commands_or_not_true_removes(repo):
    script, settings = _hook_files(repo)
    hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert hook.sync(str(repo), [], INPUTS, True)["action"] == "removed"
    assert not script.exists() and not settings.exists()
    hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert hook.sync(str(repo), COMMANDS, INPUTS, 1)["action"] == "removed"
    assert not script.exists() and not settings.exists()


def _foreign_settings():
    return {
        "permissions": {"allow": ["Bash(ls:*)"], "deny": []},
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "check"}]}],
            "SessionStart": [{"matcher": "startup",
                              "hooks": [{"type": "command", "command": "echo hi"}]}],
        },
        "env": {"A": "é"},
    }


def test_settings_census_round_trip_leaves_foreign_content_alone(repo):
    original = _foreign_settings()
    _, settings = _hook_files(repo)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps(original, indent=2, ensure_ascii=False) + "\n")
    hook.sync(str(repo), COMMANDS, INPUTS, True)
    mid = json.loads(settings.read_text())
    assert len(_ours(mid)) == 1
    stripped = copy.deepcopy(mid)
    stripped["hooks"]["SessionStart"] = stripped["hooks"]["SessionStart"][:-1]
    assert stripped == original
    hook.sync(str(repo), COMMANDS, INPUTS, False)
    after = json.loads(settings.read_text())
    assert after == original
    assert list(after) == list(original)
    assert list(after["hooks"]) == list(original["hooks"])


def test_rewrite_replaces_a_stale_hook_of_ours_and_keeps_its_neighbours(repo):
    original = _foreign_settings()
    stale = {"type": "command", "command": "bash old/" + hook.SCRIPT_REL, "timeout": 5}
    original["hooks"]["SessionStart"][0]["hooks"].append(stale)
    original["hooks"]["SessionStart"].append({"hooks": [dict(stale)]})
    _, settings = _hook_files(repo)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps(original))
    result = hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert result["action"] == "written"
    obj = json.loads(settings.read_text())
    assert _ours(obj) == [{"type": "command", "command": hook.HOOK_COMMAND,
                           "timeout": hook.HOOK_TIMEOUT_SECONDS}]
    assert obj["hooks"]["SessionStart"][0]["hooks"] == [{"type": "command", "command": "echo hi"}]
    assert len(obj["hooks"]["SessionStart"]) == 2
    hook.sync(str(repo), COMMANDS, INPUTS, False)
    clean = json.loads(settings.read_text())
    assert _ours(clean) == []
    assert clean["hooks"]["SessionStart"] == [{"matcher": "startup", "hooks": [
        {"type": "command", "command": "echo hi"}]}]


def test_removal_never_drops_what_was_already_empty(repo):
    _, settings = _hook_files(repo)
    settings.parent.mkdir(parents=True)
    ours = {"type": "command", "command": hook.HOOK_COMMAND, "timeout": 600}
    original = {"hooks": {"Stop": [], "SessionStart": [{"hooks": []}, {"hooks": [ours]}]},
                "other": {}}
    settings.write_text(json.dumps(original))
    assert hook.sync(str(repo), COMMANDS, INPUTS, False)["action"] == "removed"
    assert json.loads(settings.read_text()) == {
        "hooks": {"Stop": [], "SessionStart": [{"hooks": []}]}, "other": {}}

    settings.write_text(json.dumps({"hooks": {}, "other": {}}))
    assert hook.sync(str(repo), COMMANDS, INPUTS, False) == {
        "action": "noop", "reason": None, "changed": []}
    assert json.loads(settings.read_text()) == {"hooks": {}, "other": {}}

    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}))
    assert hook.sync(str(repo), COMMANDS, INPUTS, False)["action"] == "noop"
    assert json.loads(settings.read_text()) == {"hooks": {"SessionStart": []}}

    settings.write_text("{}")
    assert hook.sync(str(repo), COMMANDS, INPUTS, False)["action"] == "noop"
    assert settings.exists()


def test_removal_drops_only_the_containers_it_emptied(repo):
    _, settings = _hook_files(repo)
    settings.parent.mkdir(parents=True)
    ours = {"type": "command", "command": hook.HOOK_COMMAND, "timeout": 600}
    settings.write_text(json.dumps({"permissions": {}, "hooks": {"SessionStart": [{"hooks": [ours]}]}}))
    hook.sync(str(repo), COMMANDS, INPUTS, False)
    assert json.loads(settings.read_text()) == {"permissions": {}}


def test_a_settings_file_we_created_is_deleted_on_removal(repo):
    _, settings = _hook_files(repo)
    hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert settings.exists()
    hook.sync(str(repo), COMMANDS, INPUTS, False)
    assert not settings.exists()
    assert (repo / ".claude").is_dir()


@pytest.mark.parametrize("text", [
    "[1]", '{"hooks": []}', "{not json", "", b"\xff\xfe\x00", '{"hooks": {"SessionStart": {}}}',
    '{"hooks": {"SessionStart": [3]}}', '{"hooks": {"SessionStart": [{"hooks": {}}]}}',
    '{"hooks": {"SessionStart": [{}]}}', '"text"', "null"])
@pytest.mark.parametrize("enabled", [True, False])
def test_malformed_settings_are_refused_and_nothing_is_written(repo, text, enabled):
    script, settings = _hook_files(repo)
    settings.parent.mkdir(parents=True)
    raw = text if isinstance(text, bytes) else text.encode("utf-8")
    settings.write_bytes(raw)
    result = hook.sync(str(repo), COMMANDS, INPUTS, enabled)
    assert result == {"action": "refused", "reason": "settings-unreadable", "changed": []}
    assert settings.read_bytes() == raw
    assert not script.exists()
    assert not (repo / ".claude" / "hooks").exists()


def test_a_settings_path_that_is_a_directory_is_refused(repo):
    script, settings = _hook_files(repo)
    settings.mkdir(parents=True)
    result = hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert result == {"action": "refused", "reason": "settings-unreadable", "changed": []}
    assert not script.exists()


def test_unwritable_targets_are_refused(repo, tmp_path):
    script, _ = _hook_files(repo)
    script.parent.mkdir(parents=True)
    script.mkdir()
    result = hook.sync(str(repo), COMMANDS, INPUTS, True)
    assert result["action"] == "refused" and result["reason"] == "hook-files-unwritable"
    gone = hook.sync(str(tmp_path / "no-such-root"), COMMANDS, INPUTS, True)
    assert gone == {"action": "refused", "reason": "hook-files-unwritable", "changed": []}
    assert not (tmp_path / "no-such-root").exists()
    assert hook.sync(str(tmp_path / "no-such-root"), COMMANDS, INPUTS, False)["action"] == "noop"


def test_non_text_arguments_are_refused_not_raised(repo):
    assert hook.sync(str(repo), [1], INPUTS, True)["reason"] == "invalid-arguments"
    assert hook.sync(str(repo), COMMANDS, None, True)["reason"] == "invalid-arguments"
    assert not (repo / ".claude").exists()


def test_the_script_text_carries_the_published_names(repo):
    text = hook.script_text(COMMANDS, INPUTS)
    assert text.startswith("#!/bin/bash\n")
    assert hook.fingerprint(COMMANDS, INPUTS) in text
    assert hook.HASH_NAME in text and hook.LOG_NAME in text
    assert hook.HOOK_COMMAND == 'bash "$CLAUDE_PROJECT_DIR/%s"' % hook.SCRIPT_REL
    assert "set -e" not in text


def test_a_failed_run_does_not_let_a_return_to_the_earlier_inputs_skip_the_setup(repo):
    commands = ["cp deps.lock installed-deps", "grep -qx A deps.lock"]
    script = _installed(repo, commands, ["deps.lock"])
    (repo / "deps.lock").write_text("A\n")
    assert _run(script).returncode == 0
    assert (repo / "installed-deps").read_text() == "A\n"
    (repo / "deps.lock").write_text("B\n")
    assert "command 2 failed" in _run(script).stdout
    assert (repo / "installed-deps").read_text() == "B\n"
    (repo / "deps.lock").write_text("A\n")
    assert _run(script).returncode == 0
    assert (repo / "installed-deps").read_text() == "A\n"
    assert _state(repo) is not None
