"""A cloud launch: `launch` starts a builder in a cloud session instead of a local child.

The platform command is never run here: every `launch_build` test injects the spawn function, and
the default spawn function is driven with stand-in scripts. A cloud launch makes no worktree,
leaves no local process, pushes nothing, and never ends a lane as refused when a cloud session may
exist.
"""
import argparse
import json
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import time
import types

import pytest

import engine_adapter as EA
import cloud_builder
import heartbeat as hb
import launch_doctrine
import launch_ledger as ll

from test_launcher import (  # noqa: E402
    L,
    _all_checks,
    _head_sha,
    _init_repo,
    _not_slot_calibrated,
    _reserve_live_lane,
    _slot_calibrated,
    _valid_premise,
    _write_json,
)


def _cloud_line():
    return launch_doctrine.load()["cloudLaunchLine"]


SESSION_ID = "session_01XkoXctZReLbM87S13947gp"
SESSION_URL = "https://claude.ai/code/%s" % SESSION_ID
ENV_ID = "env_01AbCdEf"
FAKE_PID = 424242


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    # The instance-pin gate applies only on a Claude-hosted seat; these tests are not one.
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    # The `started` append pauses between its tries; no test waits for it.
    monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
    # The launches below keep their base on a local bare remote; the commit is asked of that
    # remote by git rather than of GitHub. The GitHub question has its own tests.
    monkeypatch.setattr(L, "_base_on_remote_fn", _local_remote_has)
    # The fixture repositories must not depend on the developer's git config, such as signing.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _local_remote_has(repo_root, base, env):
    got = subprocess.run(
        ["git", "-C", repo_root, "remote", "get-url", "origin"],
        capture_output=True, text=True)
    origin = got.stdout.strip()
    if got.returncode != 0 or not origin:
        return None
    has = subprocess.run(
        ["git", "-C", origin, "cat-file", "-e", base + "^{commit}"], capture_output=True)
    return has.returncode == 0


def _pty_available():
    try:
        master, slave = os.openpty()
    except OSError:
        return False
    os.close(master)
    os.close(slave)
    return True


@pytest.fixture(params=["real-pty", "pipe-standin"])
def terminal(request, monkeypatch):
    """Whether the default spawn function runs under a real pseudo-terminal.

    The pipe stand-in replaces `pty.openpty` with a pipe, which exercises everything but the
    terminal itself (reading until end of output, the timeout kill, the log, the descriptors).
    The real-pty variants are skipped where no pseudo-terminal can be opened.
    """
    if request.param == "real-pty":
        if not _pty_available():
            pytest.skip("no pseudo-terminal can be opened here (os.openpty is not permitted)")
        return True
    monkeypatch.setattr(L.pty, "openpty", os.pipe)
    return False


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True,
    ).stdout


def _cloud_repo(tmp_path):
    """A repository whose HEAD is on a remote branch, with a bare remote to compare."""
    repo = _init_repo(tmp_path / "repo")
    remote = str(tmp_path / "remote.git")
    subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
    _git(repo, "remote", "add", "origin", remote)
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    # The checkout's own branch is on the remote too, as a cloud launch requires.
    branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/%s" % branch)
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _announced(name, session_id=SESSION_ID):
    """The measured output of the platform command, wrapped in terminal control sequences.

    `name` is the session name the launch requested: the receipt is only the launch's own when it
    announces that name, so every caller supplies it (a spawn reads it from the argv after `-n`).
    """
    return (
        "\x1b[?25l\x1b[2K\r"
        "Created cloud session: %s\r\n"
        "\x1b[1mView:\x1b[0m https://claude.ai/code/%s?from=cli&m=0\r\n"
        "Resume with: claude --teleport %s\r\n"
        "Branch build/1742-cloud-lane is not on GitHub, so the cloud session starts from its "
        "own commit, which origin/main has (fab8a63ea7f4).\r\n"
        "\x1b]0;claude\x07\x1b[?25h"
    ) % (name, session_id, session_id)


# What a real launch of the platform command printed, captured under a pseudo-terminal. The first
# line, the session name and the session id are stand-ins; every control byte is as captured.
REAL_CAPTURE = (
    "A warning line the command prints before anything else.\r\n"
    "\x1b7\x1b[r\x1b8\x1b[?25h\x1b[?25l\x1b[?2004h\x1b[?2031h\x1b[?1004h\x1b]11;?\x07\x1b[c\x1b[>0q"
    "\x1b[?u\x1b[c\x1b[>4m\x1b[<u\x1b[?1004l\x1b[?2031l\x1b[?2004l"
    "Created cloud session: %(name)s\r\n"
    "View: https://claude.ai/code/%(id)s?from=cli&m=0\r\n"
    "Resume with: claude --teleport %(id)s\r\n"
    "\x1b[?1006l\x1b[?1003l\x1b[?1002l\x1b[?1000l\x1b(B\x0f\x1b[?1016l\x1b[?1006l\x1b[?1003l"
    "\x1b[?1002l\x1b[?1000l\x1b[>4m\x1b[?1004l\x1b[?2031l\x1b[?2004l\x1b[<u\x1b[?25h\x1b7\x1b[r\x1b8"
)


def _spawned(output="", rc=0, timed_out=False, pid=FAKE_PID):
    return {"pid": pid, "rc": rc, "timedOut": timed_out, "output": output}


def _requested_name(argv):
    return argv[argv.index("-n") + 1]


def _fake_spawn(result=None, calls=None, raises=None):
    """A spawn whose `result` is a spawn result, or a function of the requested session name."""
    def spawn(argv, cwd, log_path, child_env, timeout):
        if calls is not None:
            calls.append({
                "argv": list(argv), "cwd": cwd, "logPath": log_path,
                "env": dict(child_env), "timeout": timeout,
            })
        if raises is not None:
            raise raises
        name = _requested_name(argv)
        if callable(result):
            return result(name)
        return result if result is not None else _spawned(_announced(name))
    return spawn


def _launch(repo, tmp_path, spawn, *, issue=656, premise=None, checks=None, **kwargs):
    kwargs.setdefault("place", "cloud")
    kwargs.setdefault("cloud_environment", ENV_ID)
    return L.launch_build(
        repo,
        issue,
        premise if premise is not None else _valid_premise(repo, issue=issue),
        checks if checks is not None else _all_checks(),
        str(tmp_path / "logs"),
        cloud_spawn_fn=spawn,
        **kwargs,
    )


def _lanes(repo):
    folded = ll.fold(ll.read(repo)["records"])
    assert folded["ok"], folded["reason"]
    return folded["launches"]


def _records(repo, launch_id, event):
    return [
        r for r in ll.read(repo)["records"]
        if r.get("launchId") == launch_id and r.get("event") == event
    ]


# --- the argv ----------------------------------------------------------------------------


def test_cloud_argv_shape_and_order():
    built = EA.claude_cloud_builder_argv("opus", "medium", "the prompt", ENV_ID, "issue-1-ab")
    assert built == {
        "argv": [
            "claude", "--cloud", "the prompt",
            "--settings", '{"remote":{"defaultEnvironmentId":"%s"}}' % ENV_ID,
            "--model", "opus", "--effort", "medium", "--permission-mode", "auto",
            "--disallowedTools", "AskUserQuestion", "-n", "issue-1-ab",
        ],
        "reason": None,
    }


@pytest.mark.parametrize("effort", [None, "", "medium"])
def test_cloud_argv_runs_the_session_in_auto_permission_mode(effort):
    # A cloud builder nobody watches stalls on a permission prompt; the argv is the only carrier.
    argv = EA.claude_cloud_builder_argv("opus", effort, "p", ENV_ID, "n")["argv"]
    assert argv.count("--permission-mode") == 1
    assert argv[argv.index("--permission-mode") + 1] == "auto"


def test_cloud_argv_starts_with_the_question_dialog_off_once_and_before_the_name():
    # The flag takes a variadic value, so the tool is its only value and `-n` follows at once.
    argv = EA.claude_cloud_builder_argv("opus", "medium", "p", ENV_ID, "n")["argv"]
    assert argv.count("--disallowedTools") == 1
    at = argv.index("--disallowedTools")
    assert argv[at + 1] == "AskUserQuestion"
    assert argv[at + 2] == "-n"
    assert argv[-2:] == ["-n", "n"]


@pytest.mark.parametrize("disallowed", [None, ()])
def test_cloud_argv_without_disallowed_tools_has_no_such_flag(disallowed):
    built = EA.claude_cloud_builder_argv("opus", "medium", "p", ENV_ID, "n", disallowed_tools=disallowed)
    assert built["reason"] is None
    assert "--disallowedTools" not in built["argv"]
    assert built["argv"][-2:] == ["-n", "n"]


def test_cloud_argv_without_permission_mode_still_turns_the_dialog_off():
    argv = EA.claude_cloud_builder_argv("opus", None, "p", ENV_ID, "n", permission_mode=None)["argv"]
    assert "--permission-mode" not in argv
    assert argv[-4:] == ["--disallowedTools", "AskUserQuestion", "-n", "n"]


@pytest.mark.parametrize("effort", [None, ""])
def test_cloud_argv_without_effort_has_no_effort_flag(effort):
    built = EA.claude_cloud_builder_argv("opus", effort, "p", ENV_ID, "n")
    assert built["reason"] is None
    assert "--effort" not in built["argv"]
    assert built["argv"][-2:] == ["-n", "n"]


def test_cloud_argv_refuses_unknown_tier():
    built = EA.claude_cloud_builder_argv("nope", None, "p", ENV_ID, "n")
    assert built["argv"] == []
    assert built["reason"] == "unknown-claude-tier"


def test_cloud_argv_carries_auto_mode_whatever_the_tier_alias():
    argv = EA.claude_cloud_builder_argv("haiku", None, "p", ENV_ID, "n")["argv"]
    assert argv[argv.index("--permission-mode") + 1] == "auto"


@pytest.mark.parametrize("prompt", ["", "   ", None, 7])
def test_cloud_argv_refuses_empty_prompt(prompt):
    built = EA.claude_cloud_builder_argv("opus", None, prompt, ENV_ID, "n")
    assert built["argv"] == []
    assert built["reason"] == "builder-prompt-missing"


@pytest.mark.parametrize("environment", [None, 7, "", "env_", "abc", "env_a-b", "env_ab\n", " env_ab"])
def test_cloud_argv_refuses_bad_environment(environment):
    built = EA.claude_cloud_builder_argv("opus", None, "p", environment, "n")
    assert built["argv"] == []
    assert built["reason"] == "cloud-environment-invalid"


@pytest.mark.parametrize("name", [None, 7, "", "a b", "a/b", "x" * 65, "n\n"])
def test_cloud_argv_refuses_bad_session_name(name):
    built = EA.claude_cloud_builder_argv("opus", None, "p", ENV_ID, name)
    assert built["argv"] == []
    assert built["reason"] == "cloud-session-name-invalid"


def test_cloud_argv_accepts_a_64_character_name():
    built = EA.claude_cloud_builder_argv("opus", None, "p", ENV_ID, "x" * 64)
    assert built["reason"] is None


# --- plugin_version ----------------------------------------------------------------------


def test_plugin_version_is_the_running_manifest_version():
    manifest = os.path.join(os.path.dirname(L._LIB_DIR), ".claude-plugin", "plugin.json")
    with open(manifest, encoding="utf-8") as fh:
        assert L.plugin_version() == json.load(fh)["version"]


@pytest.mark.parametrize("body", [None, "not json", "[]", '{"name": "x"}', '{"version": ""}',
                                  '{"version": 3}'])
def test_plugin_version_unreadable_is_none(tmp_path, monkeypatch, body):
    lib = tmp_path / "plugin" / "lib"
    lib.mkdir(parents=True)
    if body is not None:
        manifest_dir = tmp_path / "plugin" / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(body)
    monkeypatch.setattr(L, "_LIB_DIR", str(lib))
    assert L.plugin_version() is None


# --- compose -----------------------------------------------------------------------------


def _stamped(repo):
    return L.validate_premise(_valid_premise(repo), repo, issue=656)["premise"]


def _compose_cloud(repo, **kwargs):
    kwargs.setdefault("place", "cloud")
    kwargs.setdefault("cloud_environment", ENV_ID)
    kwargs.setdefault("session_name", "issue-656-preview")
    return L.compose_launch(repo, 656, _stamped(repo), **kwargs)


def test_compose_cloud_prompt_differs_from_local_by_the_four_place_lines_and_the_standing_permission(tmp_path):
    # axis: the prompt differs from the local one by exactly those lines and the standing permission
    repo = _init_repo(tmp_path / "repo")
    local = L.compose_launch(repo, 656, _stamped(repo))
    cloud = _compose_cloud(repo)
    assert local["ok"] is True and cloud["ok"] is True
    version = L.plugin_version()
    lines = (
        "Place: cloud session\nAdvisor plugin version: %s\nCloud environment: %s\n"
        "Base commit: %s\n\n" % (version, ENV_ID, _head_sha(repo))
    )
    permission = _cloud_line() + "\n\n"
    assert lines in cloud["prompt"]
    assert permission in cloud["prompt"]
    assert cloud["prompt"].replace(lines, "", 1).replace(permission, "", 1) == local["prompt"]
    rulings = local["doctrine"]["rulingsBlock"]
    assert rulings
    assert cloud["doctrine"]["rulingsBlock"] == rulings
    assert local["prompt"].endswith(rulings)
    assert cloud["prompt"].endswith(rulings)


def test_compose_cloud_prompt_carries_the_standing_permission_once_between_base_and_rulings(tmp_path):
    # axis: every cloud prompt carries the doctrine's standing push permission
    repo = _init_repo(tmp_path / "repo")
    cloud = _compose_cloud(repo)
    prompt = cloud["prompt"]
    text = _cloud_line()
    assert prompt.count(text) == 1
    assert text in prompt.split("\n")
    first_ruling = cloud["doctrine"]["rulingsBlock"].split("\n")[0]
    assert prompt.index("Base commit: ") < prompt.index(text) < prompt.index(first_ruling)
    assert "\n\n%s\n\n%s" % (text, first_ruling) in prompt


def test_compose_cloud_adopt_prompt_carries_the_standing_permission_after_the_adopt_line(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = dict(_stamped(repo), adoptsBranch="feature/adopted", adoptsHead=_head_sha(repo))
    cloud = L.compose_launch(repo, 656, premise, place="cloud", cloud_environment=ENV_ID,
                             session_name="issue-656-preview")
    assert cloud["ok"] is True
    prompt = cloud["prompt"]
    text = _cloud_line()
    assert prompt.count(text) == 1
    assert prompt.index("Base commit: ") < prompt.index("feature/adopted") < prompt.index(text)


def test_compose_local_prompts_do_not_carry_the_standing_permission(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    text = _cloud_line()
    adopting = dict(_stamped(repo), adoptsBranch="feature/adopted", adoptsHead=_head_sha(repo))
    for local in (L.compose_launch(repo, 656, _stamped(repo)),
                  L.compose_launch(repo, 656, _stamped(repo), place="local"),
                  L.compose_launch(repo, 656, adopting, place="local")):
        assert local["ok"] is True
        assert text not in local["prompt"]
        assert "Standing permission" not in local["prompt"]


def test_every_launch_path_carries_the_no_compound_delete_ruling(tmp_path):
    # axis: the no-compound-delete ruling (DELETE_RULE) reaches every composed builder prompt, local and cloud, fresh and adopt
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_d_2314_delete_ruling.md (wo_d_2314_delete_ruling)
    repo = _init_repo(tmp_path / "repo")
    adopting = dict(_stamped(repo), adoptsBranch="feature/adopted", adoptsHead=_head_sha(repo))
    composed = {
        "local fresh": L.compose_launch(repo, 656, _stamped(repo)),
        "local adopt": L.compose_launch(repo, 656, adopting, place="local"),
        "cloud fresh": _compose_cloud(repo),
        "cloud adopt": L.compose_launch(repo, 656, adopting, place="cloud", cloud_environment=ENV_ID,
                                        session_name="issue-656-preview"),
    }
    line = launch_doctrine.ruling_line(launch_doctrine.load(), "no-compound-delete")
    assert line
    for path, result in composed.items():
        assert result["ok"] is True, (path, result.get("reason"))
        assert result["prompt"].count(line) == 1, path


def test_compose_cloud_refuses_a_doctrine_with_no_cloud_launch_line(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    def loader():
        return {k: v for k, v in launch_doctrine.load().items() if k != "cloudLaunchLine"}

    refused = _compose_cloud(repo, doctrine_loader=loader)
    assert refused["ok"] is False
    assert refused["reason"] == "compose-cloud-launch-line-absent"
    assert "prompt" not in refused and "argv" not in refused
    # a local compose never reads the line, so the same loader still composes
    assert L.compose_launch(repo, 656, _stamped(repo), doctrine_loader=loader)["ok"] is True


def test_cloud_intake_reads_the_same_environment_and_base_from_the_composed_prompt(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    prompt = _compose_cloud(repo)["prompt"]
    text = _cloud_line()
    with_line = cloud_builder.parse_launch(prompt)
    without_line = cloud_builder.parse_launch(prompt.replace(text + "\n\n", "", 1))
    assert with_line == without_line
    assert with_line["environment"] == ENV_ID
    assert with_line["baseCommit"] == _head_sha(repo)


def test_compose_cloud_prompt_names_the_environment_on_its_own_line(tmp_path):
    # axis: the cloud prompt names the cloud environment on its own line
    repo = _init_repo(tmp_path / "repo")
    lines = _compose_cloud(repo)["prompt"].split("\n")
    assert lines.count("Cloud environment: %s" % ENV_ID) == 1
    at = lines.index("Advisor plugin version: %s" % L.plugin_version())
    assert lines[at + 1] == "Cloud environment: %s" % ENV_ID
    named = _compose_cloud(repo, cloud_environment="env_01Other")
    assert "\nCloud environment: env_01Other\n" in named["prompt"]


def test_compose_cloud_prompt_names_the_base_commit_on_its_own_line(tmp_path):
    # axis: the cloud prompt names the premise's base commit on its own line
    repo = _init_repo(tmp_path / "repo")
    base = _head_sha(repo)
    lines = _compose_cloud(repo)["prompt"].split("\n")
    assert lines.count("Base commit: %s" % base) == 1
    at = lines.index("Cloud environment: %s" % ENV_ID)
    assert lines[at + 1] == "Base commit: %s" % base


def test_compose_local_prompt_carries_neither_line(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    for local in (L.compose_launch(repo, 656, _stamped(repo)),
                  L.compose_launch(repo, 656, _stamped(repo), place="local")):
        assert local["ok"] is True
        assert "Cloud environment:" not in local["prompt"]
        assert "Base commit:" not in local["prompt"]


def test_compose_cloud_without_a_base_commit_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = dict(_stamped(repo))
    del premise["baseCommit"]
    result = L.compose_launch(repo, 656, premise, place="cloud", cloud_environment=ENV_ID,
                              session_name="issue-656-preview")
    assert result["ok"] is False
    assert result["reason"] == "premise-missing-field:baseCommit"


def test_compose_cloud_result_keys(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    local = L.compose_launch(repo, 656, _stamped(repo))
    cloud = _compose_cloud(repo)
    assert set(cloud) == set(local) | {"place", "pluginVersion", "cloudEnvironment",
                                       "cloudSessionName"}
    assert cloud["sessionId"] is None
    assert cloud["place"] == "cloud"
    assert cloud["pluginVersion"] == L.plugin_version()
    assert cloud["cloudEnvironment"] == ENV_ID
    assert cloud["cloudSessionName"] == "issue-656-preview"
    assert cloud["argv"][:2] == ["claude", "--cloud"]
    assert cloud["argv"][2] == cloud["prompt"]
    assert cloud["argv"][-2:] == ["-n", "issue-656-preview"]
    assert "-p" not in cloud["argv"]
    assert "--session-id" not in cloud["argv"]


def test_compose_local_place_is_the_unplaced_compose(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    plain = L.compose_launch(repo, 656, _stamped(repo))
    local = L.compose_launch(repo, 656, _stamped(repo), place="local")
    assert local["prompt"] == plain["prompt"]
    assert set(local) == set(plain)
    assert local["argv"][1:2] == ["--model"]


def test_compose_cloud_invalid_environment_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = _compose_cloud(repo, cloud_environment="not-an-environment")
    assert result["ok"] is False
    assert result["reason"] == "cloud-environment-invalid"


def test_compose_cloud_unreadable_plugin_version_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(L, "plugin_version", lambda: None)
    result = _compose_cloud(repo)
    assert result["ok"] is False
    assert result["reason"] == "compose-plugin-version-unreadable"


def test_compose_other_place_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _stamped(repo), place="elsewhere")
    assert result["ok"] is False
    assert result["reason"] == "launch-place-invalid"


# --- edge 1: the five refusals before any reservation ------------------------------------


def _assert_nothing_written(repo, spawn_calls):
    assert ll.read(repo)["state"] == "missing"
    assert spawn_calls == []


def test_edge1_place_invalid_writes_nothing(tmp_path):
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), place="elsewhere")
    assert result["ok"] is False
    assert result["reason"] == "launch-place-invalid"
    assert result["launchId"].startswith("launch-")
    _assert_nothing_written(repo, calls)


@pytest.mark.parametrize("kwargs", [
    {"slot": "slot-a"},
    {"generation": 1},
    {"slot": "slot-a", "generation": 1},
    {"boundary": {}},
], ids=["slot", "generation", "slot-generation", "boundary"])
def test_edge1_slot_generation_or_boundary_writes_nothing(tmp_path, kwargs):
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), **kwargs)
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-with-slot"
    assert "launchId" in result
    _assert_nothing_written(repo, calls)


def test_edge1_iphone_check_writes_nothing(tmp_path):
    repo = _cloud_repo(tmp_path)
    calls = []
    premise = _valid_premise(repo, iphoneCheck=True)
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-with-iphone-check"
    assert "launchId" in result
    _assert_nothing_written(repo, calls)


def test_edge1_unreadable_plugin_version_writes_nothing(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    monkeypatch.setattr(L, "plugin_version", lambda: None)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-plugin-version-unreadable"
    assert "launchId" in result
    _assert_nothing_written(repo, calls)


@pytest.mark.parametrize("environment", [None, "", "env_", "prod", "env_a b", 12])
def test_edge1_invalid_environment_writes_nothing(tmp_path, environment):
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), cloud_environment=environment)
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-environment-invalid"
    assert "launchId" in result
    _assert_nothing_written(repo, calls)


_BAD_ISSUES = [
    pytest.param("656", id="str"),
    pytest.param([656], id="list"),
    pytest.param({"n": 656}, id="dict"),
    pytest.param(True, id="bool"),
    pytest.param(None, id="none"),
    pytest.param(0, id="zero"),
    pytest.param(-3, id="negative"),
    pytest.param(656.0, id="float"),
]


@pytest.mark.parametrize("issue", _BAD_ISSUES)
def test_edge1_a_cloud_launch_with_a_bad_issue_writes_nothing(tmp_path, issue):
    # axis: refused before any write
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(
        repo, tmp_path, _fake_spawn(calls=calls), issue=issue, premise=_valid_premise(repo),
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-issue-invalid"
    assert "launchId" in result
    _assert_nothing_written(repo, calls)


@pytest.mark.parametrize("issue", _BAD_ISSUES)
@pytest.mark.parametrize("place", [None, "local"])
def test_a_local_launch_with_an_odd_issue_does_not_get_the_cloud_issue_refusal(issue, place):
    assert L._place_refusal("launch-x", place, None, None, None, {}, None, issue) is None


# --- edge 2: a cloud launch refused at a gate is a cloud lane ----------------------------


def _assert_refused_cloud_lane(repo, result, reason, stage):
    assert result["ok"] is False
    assert result["reason"] == reason
    lane = _lanes(repo)[result["launchId"]]
    assert lane["place"] == "cloud"
    assert lane["terminal"] is True
    assert lane["terminalKind"] == "refused"
    assert lane["started"] is False
    assert lane["cloudEnvironment"] == ENV_ID
    assert lane["pluginVersion"] == L.plugin_version()
    refused = _records(repo, result["launchId"], "refused")
    assert [r["stage"] for r in refused] == [stage]


def test_edge2_preflight_refusal_is_a_cloud_lane(tmp_path):
    # axis: a refused cloud launch is a cloud lane
    repo = _cloud_repo(tmp_path)
    calls = []
    checks = _all_checks(**{"engine-auth": {"state": "fail", "reason": "nope"}})
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), checks=checks)
    _assert_refused_cloud_lane(repo, result, "preflight-failed:engine-auth", "preflight")
    assert calls == []


def test_edge2_premise_refusal_is_a_cloud_lane(tmp_path):
    repo = _cloud_repo(tmp_path)
    calls = []
    premise = _valid_premise(repo, bashMaxTimeoutMs=0)
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), premise=premise)
    _assert_refused_cloud_lane(repo, result, "premise-bash-max-timeout", "premise")
    assert calls == []


def test_edge2_compose_refusal_is_a_cloud_lane(tmp_path):
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), model="not-a-model")
    _assert_refused_cloud_lane(repo, result, "model-not-registry-known", "model")
    assert calls == []


# --- edge 3: the named base commit must be on the remote -----------------------------------
# bite-proof record wo_c_place_call


def _later_commit(tmp_path, repo):
    """A commit on the working repo that no remote has; its sha."""
    count = len(os.listdir(tmp_path / "repo"))
    (tmp_path / "repo" / ("later-%d.txt" % count)).write_text("later\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-q", "-m", "later")
    return _head_sha(repo)


def test_edge3_a_checkout_with_no_origin_is_unchecked_and_refuses(tmp_path):
    # axis: a remote that could not be asked refuses
    repo = _init_repo(tmp_path / "repo")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-base-remote-unchecked", "cloud-base")
    assert calls == []
    assert "warnings" in result


def test_edge3_a_base_the_remote_lacks_refuses(tmp_path):
    # axis: a named base absent from the remote refuses
    repo = _cloud_repo(tmp_path)
    later = _later_commit(tmp_path, repo)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=later))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-base-not-on-remote", "cloud-base")
    assert calls == []


def test_edge3_a_head_past_the_named_base_refuses_even_when_the_remote_has_the_base(
    tmp_path,
):
    # axis: a checkout whose HEAD is not the named base refuses, though the remote has the base
    repo = _cloud_repo(tmp_path)
    base = _head_sha(repo)
    later = _later_commit(tmp_path, repo)
    assert later != base
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=base))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-checkout-off-base", "cloud-base")
    assert calls == []
    assert result["checkoutHead"] == later
    assert result["baseCommit"] == base


def test_edge3_a_stale_tracking_ref_does_not_decide_the_result(tmp_path):
    # axis: the remote is read, not local tracking refs
    repo = _cloud_repo(tmp_path)
    later = _later_commit(tmp_path, repo)
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert "origin/main" in _git(repo, "branch", "-r", "--contains", later)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=later))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-base-not-on-remote", "cloud-base")
    assert calls == []


def test_edge3_the_remote_losing_the_base_while_reserving_terminalizes_the_unstarted_lane(
    tmp_path, monkeypatch,
):
    # axis: the base is re-checked right before the command; reservation can wait on the lock
    repo = _cloud_repo(tmp_path)
    real_reserve = ll.reserve

    def reserve_then_lose_the_base(*args, **kwargs):
        result = real_reserve(*args, **kwargs)
        monkeypatch.setattr(L, "_base_on_remote_fn", lambda *a, **k: False)
        return result

    monkeypatch.setattr(ll, "reserve", reserve_then_lose_the_base)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-base-not-on-remote"
    assert calls == []
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True
    assert lane["started"] is False


@pytest.mark.parametrize("answer,reason", [
    (False, "launch-cloud-base-not-on-remote"),
    (None, "launch-cloud-base-remote-unchecked"),
    (True, None),
])
def test_cloud_base_refusal_maps_the_round_trip_to_its_token(monkeypatch, answer, reason):
    seen = []

    def asked(repo_root, base, env):
        seen.append((repo_root, base))
        return answer

    monkeypatch.setattr(L, "_base_on_remote_fn", asked)
    assert L._cloud_base_refusal("/repo", {"baseCommit": "abc123"}, None) == reason
    assert seen == [("/repo", "abc123")]


def _gh_runner(monkeypatch, answer):
    """Replace the gh call; record each (owner, repo, sha, timeout). ``answer`` is a
    CompletedProcess, None, or an exception to raise."""
    seen = []

    def run(owner, repo, sha, env, timeout):
        seen.append((owner, repo, sha, timeout))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(L, "_gh_commit_lookup", run)
    monkeypatch.setattr(L, "_base_on_remote_fn", L._base_on_remote)
    return seen


def _origin(tmp_path, url):
    repo = _init_repo(tmp_path / "repo")
    if url is not None:
        _git(repo, "remote", "add", "origin", url)
    return repo


SHA = "a" * 40


def _done(code, out="", err=""):
    return subprocess.CompletedProcess([], code, stdout=out, stderr=err)


def test_a_pushed_commit_is_on_the_remote(tmp_path, monkeypatch):
    # axis: the base is asked of GitHub afresh
    repo = _origin(tmp_path, "git@github.com:acme/widgets.git")
    seen = _gh_runner(monkeypatch, _done(0, SHA + "\n"))
    assert L._base_on_remote(repo, SHA, None) is True
    assert seen == [("acme", "widgets", SHA, L._WORKTREE_GIT_TIMEOUT)]


def test_a_success_that_names_another_commit_is_unchecked(tmp_path, monkeypatch):
    repo = _origin(tmp_path, "https://github.com/acme/widgets")
    _gh_runner(monkeypatch, _done(0, "b" * 40 + "\n"))
    assert L._base_on_remote(repo, SHA, None) is None


def test_only_the_422_no_commit_answer_is_absent(tmp_path, monkeypatch):
    # axis: only GitHub saying it has no such commit is "not on the remote"
    repo = _origin(tmp_path, "https://github.com/acme/widgets.git")
    _gh_runner(monkeypatch, _done(
        1, "", "gh: No commit found for SHA: %s (HTTP 422)" % SHA))
    assert L._base_on_remote(repo, SHA, None) is False
    assert L._cloud_base_refusal(repo, {"baseCommit": SHA}, None) == (
        "launch-cloud-base-not-on-remote")


@pytest.mark.parametrize("err", [
    "gh: Not Found (HTTP 404)",
    "gh: Bad credentials (HTTP 401)",
    "error connecting to api.github.com",
    "gh: Server Error (HTTP 500)",
])
def test_any_other_gh_failure_is_unchecked(tmp_path, monkeypatch, err):
    repo = _origin(tmp_path, "https://github.com/acme/widgets.git")
    _gh_runner(monkeypatch, _done(1, "", err))
    assert L._base_on_remote(repo, SHA, None) is None
    assert L._cloud_base_refusal(repo, {"baseCommit": SHA}, None) == (
        "launch-cloud-base-remote-unchecked")


def test_a_gh_that_cannot_run_or_times_out_is_unchecked(tmp_path, monkeypatch):
    repo = _origin(tmp_path, "https://github.com/acme/widgets.git")
    _gh_runner(monkeypatch, None)
    assert L._base_on_remote(repo, SHA, None) is None


@pytest.mark.parametrize("raised", [
    OSError("gh missing"), subprocess.TimeoutExpired(["gh"], 180),
])
def test_the_default_gh_call_maps_a_missing_gh_and_a_timeout_to_no_answer(
    monkeypatch, raised,
):
    def run(*args, **kwargs):
        raise raised

    monkeypatch.setattr(L.subprocess, "run", run)
    assert L._gh_commit_lookup("acme", "widgets", SHA, None, 5) is None


def test_the_default_gh_call_asks_the_commits_endpoint(monkeypatch):
    seen = []

    def run(argv, **kwargs):
        seen.append((argv, kwargs["timeout"]))
        return _done(0, SHA)

    monkeypatch.setattr(L.subprocess, "run", run)
    L._gh_commit_lookup("acme", "widgets", SHA, None, 7)
    assert seen == [(["gh", "api", "repos/acme/widgets/commits/" + SHA, "--jq", ".sha"], 7)]


@pytest.mark.parametrize("url", [
    "git@github.com:acme/widgets.git",
    "git@github.com:acme/widgets",
    "ssh://git@github.com/acme/widgets.git",
    "ssh://git@github.com/acme/widgets",
    "https://github.com/acme/widgets.git",
    "https://github.com/acme/widgets",
])
def test_every_github_address_form_names_its_owner_and_repository(tmp_path, monkeypatch, url):
    repo = _origin(tmp_path, url)
    seen = _gh_runner(monkeypatch, _done(0, SHA))
    assert L._base_on_remote(repo, SHA, None) is True
    assert seen[0][:2] == ("acme", "widgets")


@pytest.mark.parametrize("url", [
    "https://gitlab.com/acme/widgets.git",
    "https://github.com.evil.example/acme/widgets.git",
    "/srv/git/widgets.git",
    "file:///srv/git/widgets.git",
    "git@github.com:acme",
])
def test_an_origin_that_is_not_a_github_address_is_unchecked_without_asking(
    tmp_path, monkeypatch, url,
):
    repo = _origin(tmp_path, url)
    seen = _gh_runner(monkeypatch, _done(0, SHA))
    assert L._base_on_remote(repo, SHA, None) is None
    assert seen == []


def test_E5_no_origin_is_unchecked(tmp_path, monkeypatch):
    repo = _origin(tmp_path, None)
    seen = _gh_runner(monkeypatch, _done(0, SHA))
    assert L._base_on_remote(repo, SHA, None) is None
    assert seen == []
    assert L._cloud_base_refusal(repo, {"baseCommit": SHA}, None) == (
        "launch-cloud-base-remote-unchecked")


def test_a_git_that_cannot_run_is_unchecked(tmp_path, monkeypatch):
    repo = _origin(tmp_path, "https://github.com/acme/widgets.git")
    seen = _gh_runner(monkeypatch, _done(0, SHA))
    monkeypatch.setattr(L, "_git_scrubbed", lambda *a, **k: None)
    assert L._base_on_remote(repo, SHA, None) is None
    assert seen == []


# --- the launch that works -----------------------------------------------------------------


def test_cloud_launch_records_one_lane_and_spawns_once(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    for name in (hb.LAUNCH_ID_ENV, hb.HEARTBEAT_ROOT_ENV, L.SLOT_REF_ENV, L.IPHONE_ID_ENV,
                 L.DEVICE_HUB_ENV):
        monkeypatch.setenv(name, "ambient")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["place"] == "cloud"
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionUrl"] == SESSION_URL
    assert result["cloudSessionName"] == "issue-656-%s" % result["launchId"][len("launch-"):]
    assert result["pid"] == FAKE_PID
    assert result["attempt"] == 1
    assert "worktree" not in result
    for key in ("launchId", "logPath", "errPath", "model", "modelResolution", "effort",
                "effortSource", "warnings"):
        assert key in result
    assert os.path.getsize(result["errPath"]) == 0

    assert len(calls) == 1
    call = calls[0]
    assert call["cwd"] == repo
    assert call["argv"][:2] == ["claude", "--cloud"]
    assert call["argv"][-2:] == ["-n", result["cloudSessionName"]]
    assert call["timeout"] == 120
    assert call["logPath"] == result["logPath"]
    for name in (hb.LAUNCH_ID_ENV, hb.HEARTBEAT_ROOT_ENV, L.SLOT_REF_ENV, L.IPHONE_ID_ENV,
                 L.DEVICE_HUB_ENV, ll.LEDGER_ROOT_ENV):
        assert name not in call["env"]

    lane = _lanes(repo)[result["launchId"]]
    assert lane["place"] == "cloud"
    assert lane["started"] is True
    assert lane["terminal"] is False
    assert lane["cloudSessionId"] == SESSION_ID
    assert lane["cloudSessionName"] == result["cloudSessionName"]
    assert lane["cloudSessionUrl"] == SESSION_URL
    assert lane["cloudSessionUnconfirmed"] is False
    assert lane["worktree"] is None
    assert lane["sessionId"] is None
    assert lane["cloudEnvironment"] == ENV_ID
    assert lane["pluginVersion"] == L.plugin_version()
    assert lane["configDir"] == call["env"][L.CONFIG_DIR_ENV]
    reserved = _records(repo, result["launchId"], "reserved")[0]
    assert "worktree" not in reserved and "sessionId" not in reserved
    started = _records(repo, result["launchId"], "started")[0]
    assert started["attempt"] == 1 and started["pid"] == FAKE_PID


def test_cloud_launch_with_the_default_spawn_leaves_no_worktree_process_or_push(
    tmp_path, monkeypatch, terminal,
):
    repo = _cloud_repo(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    seen = tmp_path / "seen.json"
    fake = bindir / "claude"
    fake.write_text(
        "#!%s\n"
        "import json, os, sys\n"
        "if os.environ.get('FAKE_CLAUDE_REQUIRE_TTY') == '1' and not (\n"
        "        os.isatty(0) and os.isatty(1) and os.isatty(2)):\n"
        "    sys.stderr.write('no terminal\\n')\n"
        "    sys.exit(3)\n"
        "with open(os.environ['FAKE_CLAUDE_SEEN'], 'w') as fh:\n"
        "    json.dump({'argv': sys.argv[1:], 'cwd': os.getcwd()}, fh)\n"
        "name = sys.argv[sys.argv.index('-n') + 1]\n"
        "print('Created cloud session: ' + name)\n"
        "print('View: %s?from=cli&m=0')\n"
        "print('Resume with: claude --teleport %s')\n"
        "print('Branch build/1742-cloud-lane is not on GitHub, so the cloud session starts from "
        "its own commit, which origin/main has (fab8a63ea7f4).')\n"
        % (sys.executable, SESSION_URL, SESSION_ID)
    )
    fake.chmod(0o755)
    worktrees = tmp_path / "worktrees-root"
    env = dict(os.environ)
    env["PATH"] = "%s%s%s" % (bindir, os.pathsep, env.get("PATH", ""))
    env["FAKE_CLAUDE_SEEN"] = str(seen)
    env["FAKE_CLAUDE_REQUIRE_TTY"] = "1" if terminal else "0"
    env[L.WORKTREES_ROOT_ENV] = str(worktrees)

    worktrees_before = _git(repo, "worktree", "list", "--porcelain")
    remote_before = _git(repo, "ls-remote", "origin")
    refs_before = _git(repo, "for-each-ref")

    result = L.launch_build(
        repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"),
        env=env, place="cloud", cloud_environment=ENV_ID,
    )
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionUrl"] == SESSION_URL

    assert _git(repo, "worktree", "list", "--porcelain") == worktrees_before
    assert _git(repo, "ls-remote", "origin") == remote_before
    assert _git(repo, "for-each-ref") == refs_before
    assert not worktrees.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(result["pid"], 0)

    seen_data = json.loads(seen.read_text())
    assert seen_data["argv"][0] == "--cloud"
    assert seen_data["argv"][seen_data["argv"].index("-n") + 1] == result["cloudSessionName"]
    assert os.path.realpath(seen_data["cwd"]) == os.path.realpath(repo)
    with open(result["logPath"], encoding="utf-8") as fh:
        assert "Created cloud session: %s" % result["cloudSessionName"] in fh.read()
    lane = _lanes(repo)[result["launchId"]]
    assert lane["place"] == "cloud" and lane["cloudSessionId"] == SESSION_ID


def test_cloud_command_environment_carries_the_resolved_effort(tmp_path, monkeypatch):
    # axis: which effort the command runs with
    repo = _cloud_repo(tmp_path)
    monkeypatch.setenv(L.EFFORT_ENV, "low")
    monkeypatch.setenv(L.EFFORT_REFLECTION_ENV, "low")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), effort="high")
    assert result["ok"] is True, result
    assert result["effort"] == "high"
    assert calls[0]["env"][L.EFFORT_ENV] == "high"
    assert L.EFFORT_REFLECTION_ENV not in calls[0]["env"]


def test_cloud_command_environment_is_untouched_when_no_effort_resolved(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    monkeypatch.setenv(L.EFFORT_ENV, "low")
    monkeypatch.setenv(L.EFFORT_REFLECTION_ENV, "xhigh")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), model="sonnet")
    assert result["ok"] is True, result
    assert result["effort"] is None
    assert calls[0]["env"][L.EFFORT_ENV] == "low"
    assert calls[0]["env"][L.EFFORT_REFLECTION_ENV] == "xhigh"


def test_a_batch_of_three_cloud_launches_counts_three_cloud_lanes(tmp_path):
    repo = _cloud_repo(tmp_path)
    assert ll.declare_batch(repo, "wave-test", 3)["ok"] is True
    launch_ids = []
    for issue, surface in ((701, "plugins/a"), (702, "plugins/b"), (703, "plugins/c")):
        premise = _valid_premise(repo, issue=issue, surfaces=[surface])
        result = _launch(repo, tmp_path, _fake_spawn(), issue=issue, premise=premise)
        assert result["ok"] is True, result
        launch_ids.append(result["launchId"])
    for launch_id in launch_ids:
        recorded = L.record_outcome(repo, launch_id, "handback", "handed back from the cloud")
        assert recorded["ok"] is True, recorded
    counted = L.count_batch(repo, "wave-test")
    assert counted["lanes"] == {"declared": 3, "resolved": 3, "cloud": 3}
    assert len(counted["laneDetail"]) == 3
    assert all(entry["place"] == "cloud" for entry in counted["laneDetail"])


# --- the default spawn function ----------------------------------------------------------


def _script(tmp_path, body):
    path = tmp_path / "standin.py"
    path.write_text(body)
    return str(path)


def _open_descriptors():
    return len(os.listdir("/dev/fd"))


def test_default_spawn_captures_the_measured_output_and_the_child_is_gone(
    tmp_path, terminal,
):
    script = _script(tmp_path, (
        "import os\n"
        "print('tty', os.isatty(0), os.isatty(1), os.isatty(2))\n"
        "print('Created cloud session: preflight-probe-1742')\n"
        "print('View: %s?from=cli&m=0')\n"
        "print('Resume with: claude --teleport %s')\n" % (SESSION_URL, SESSION_ID)
    ))
    log_path = str(tmp_path / "out.log")
    descriptors = _open_descriptors()
    result = L.default_cloud_spawn(
        [sys.executable, script], str(tmp_path), log_path, dict(os.environ), 30,
    )
    assert result["rc"] == 0
    assert result["timedOut"] is False
    if terminal:
        assert "tty True True True" in result["output"]
    assert "Created cloud session: preflight-probe-1742" in result["output"]
    assert "View: %s?from=cli&m=0" % SESSION_URL in result["output"]
    assert "Resume with: claude --teleport %s" % SESSION_ID in result["output"]
    with open(log_path, "rb") as fh:
        assert fh.read().decode("utf-8") == result["output"]
    with pytest.raises(ProcessLookupError):
        os.kill(result["pid"], 0)
    assert _open_descriptors() == descriptors


def _is_gone(pid, grace=5.0):
    """Whether `pid` is no longer a process, allowing a moment for init to reap an orphan."""
    end = time.monotonic() + grace
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.05)


def _kill_quietly(*pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


# The stand-in command starts a long-lived child that shares its terminal and process group, then
# prints that child's pid; the `%s` is what the command does next.
_COMMAND_WITH_A_CHILD = (
    "import subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "print('child %%d' %% child.pid, flush=True)\n"
    "%s"
)


def _printed_child_pid(output):
    match = re.search(r"child (\d+)", output)
    assert match, output
    return int(match.group(1))


def test_default_spawn_kills_its_own_child_on_timeout(tmp_path, terminal):
    # axis: no child process outlives the launch
    script = _script(tmp_path, "import time\nprint('Created cloud session: x', flush=True)\n"
                              "time.sleep(30)\n")
    descriptors = _open_descriptors()
    result = None
    try:
        result = L.default_cloud_spawn(
            [sys.executable, script], str(tmp_path), str(tmp_path / "out.log"),
            dict(os.environ), 1,
        )
        assert result["timedOut"] is True
        assert "Created cloud session: x" in result["output"]
        with pytest.raises(ProcessLookupError):
            os.kill(result["pid"], 0)
    finally:
        if result is not None:
            try:
                os.kill(result["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
    assert _open_descriptors() == descriptors


def test_default_spawn_ends_a_child_left_behind_by_an_exited_command(tmp_path, terminal):
    # axis: no process the launch started outlives it
    script = _script(tmp_path, _COMMAND_WITH_A_CHILD % "")
    result = None
    child_pid = None
    try:
        started = time.monotonic()
        result = L.default_cloud_spawn(
            [sys.executable, script], str(tmp_path), str(tmp_path / "out.log"),
            dict(os.environ), 30,
        )
        elapsed = time.monotonic() - started
        child_pid = _printed_child_pid(result["output"])
        assert result["timedOut"] is False
        assert result["rc"] == 0
        assert elapsed < 15
        assert _is_gone(result["pid"], grace=0)
        assert _is_gone(child_pid)
    finally:
        _kill_quietly(*[p for p in (child_pid,) if p is not None])


def test_default_spawn_ends_the_whole_group_on_timeout(tmp_path, terminal):
    # axis: no process the launch started outlives it
    script = _script(tmp_path, _COMMAND_WITH_A_CHILD % "time.sleep(60)\n")
    result = None
    child_pid = None
    try:
        result = L.default_cloud_spawn(
            [sys.executable, script], str(tmp_path), str(tmp_path / "out.log"),
            dict(os.environ), 2,
        )
        child_pid = _printed_child_pid(result["output"])
        assert result["timedOut"] is True
        assert _is_gone(result["pid"], grace=0)
        assert _is_gone(child_pid)
    finally:
        _kill_quietly(*[p for p in (result and result["pid"], child_pid) if p])


def test_default_spawn_ends_the_group_when_the_read_raises(tmp_path, terminal, monkeypatch):
    # axis: no process the launch started outlives it
    pid_file = tmp_path / "pids.txt"
    script = _script(tmp_path, (
        "import os, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "with open(%r + '.tmp', 'w') as fh:\n"
        "    fh.write('%%d %%d' %% (os.getpid(), child.pid))\n"
        "os.rename(%r + '.tmp', %r)\n"
        "time.sleep(60)\n" % (str(pid_file), str(pid_file), str(pid_file))
    ))

    def read_fails(readers, writers, errors, timeout=None):
        end = time.monotonic() + 20
        while not pid_file.exists() and time.monotonic() < end:
            time.sleep(0.02)
        raise RuntimeError("the read failed")

    monkeypatch.setattr(L, "select", types.SimpleNamespace(select=read_fails))
    pids = []
    try:
        result = L.default_cloud_spawn(
            [sys.executable, script], str(tmp_path), str(tmp_path / "out.log"),
            dict(os.environ), 30,
        )
        assert result["readError"] == "RuntimeError"
        pids = [int(p) for p in pid_file.read_text().split()]
        assert len(pids) == 2
        assert _is_gone(pids[0], grace=0)
        assert _is_gone(pids[1])
    finally:
        _kill_quietly(*pids)


def test_default_spawn_reports_a_failed_group_signal_instead_of_raising(
    tmp_path, terminal, monkeypatch,
):
    # axis: the lane is not ended — a failure in the cleanup itself comes back, it does not raise
    script = _script(tmp_path, "print('printed before the cleanup failed')\n")

    def signal_fails(pid, sig):
        raise OSError(5, "the group signal failed")

    monkeypatch.setattr(os, "killpg", signal_fails)
    result = L.default_cloud_spawn(
        [sys.executable, script], str(tmp_path), str(tmp_path / "out.log"), dict(os.environ), 30,
    )
    assert result["readError"] == "OSError"
    assert "printed before the cleanup failed" in result["output"]
    assert result["rc"] == 0


def test_an_error_after_the_command_started_leaves_the_lane_live(
    tmp_path, terminal, monkeypatch,
):
    # axis: the lane is not ended — an error after the command started is not "it never started"
    repo = _cloud_repo(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "claude"
    fake.write_text("#!%s\nimport time\ntime.sleep(30)\n" % sys.executable)
    fake.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = "%s%s%s" % (bindir, os.pathsep, env.get("PATH", ""))

    def read_fails(readers, writers, errors, timeout=None):
        raise OSError(5, "the read failed")

    monkeypatch.setattr(L, "select", types.SimpleNamespace(select=read_fails))
    result = L.launch_build(
        repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"),
        env=env, place="cloud", cloud_environment=ENV_ID,
    )
    _assert_unconfirmed(repo, result)
    started = _records(repo, result["launchId"], "started")
    assert len(started) == 1 and started[0]["cloudSessionUnconfirmed"] is True
    assert _records(repo, result["launchId"], "refused") == []
    assert _records(repo, result["launchId"], "outcome") == []
    assert _lanes(repo)[result["launchId"]]["terminal"] is False


def test_default_spawn_raises_oserror_for_a_missing_command_and_closes_descriptors(
    tmp_path, terminal,
):
    descriptors = _open_descriptors()
    with pytest.raises(OSError):
        L.default_cloud_spawn(
            [str(tmp_path / "no-such-command")], str(tmp_path), str(tmp_path / "out.log"),
            dict(os.environ), 5,
        )
    assert _open_descriptors() == descriptors


# --- edge 4: the spawn outcomes ----------------------------------------------------------


def test_outcome1_oserror_means_the_command_never_ran(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(raises=FileNotFoundError("claude")))
    assert result["ok"] is False
    assert result["reason"] == "spawn-oserror"
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True and lane["terminalKind"] == "refused"
    assert lane["started"] is False
    assert [r["stage"] for r in _records(repo, result["launchId"], "refused")] == ["spawn"]


def _bare_receipt(name, session_id=SESSION_ID):
    """The receipt's lines without terminal control sequences."""
    return (
        "Created cloud session: %s\nView: https://claude.ai/code/%s?from=cli&m=0\n"
        "Resume with: claude --teleport %s\n" % (name, session_id, session_id)
    )


@pytest.mark.parametrize("spawned", [
    pytest.param(lambda name: _spawned(_announced(name), rc=1), id="exit-1-with-id"),
    pytest.param(lambda name: _spawned(_announced(name), rc=0), id="exit-0"),
    pytest.param(
        lambda name: _spawned(_announced(name), rc=None, timed_out=True), id="timed-out-with-id",
    ),
    pytest.param(lambda name: _spawned(_bare_receipt(name), rc=7), id="bare-lines-exit-7"),
])
def test_outcome2_a_coherent_receipt_is_a_success_whatever_the_exit_code(tmp_path, spawned):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(spawned))
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is False and lane["started"] is True
    assert lane["cloudSessionId"] == result["cloudSessionId"]


def test_outcome2_a_receipt_with_only_the_resume_line_yields_the_id_and_no_url(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Created cloud session: %s\nResume with: claude --teleport %s\n" % (name, SESSION_ID)
    )))
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionUrl"] is None
    lane = _lanes(repo)[result["launchId"]]
    assert lane["cloudSessionId"] == SESSION_ID
    assert lane["cloudSessionUrl"] is None


UNCONFIRMED = [
    pytest.param(_spawned("", rc=None, timed_out=True), id="timeout-no-output"),
    pytest.param(_spawned("", rc=0), id="exit-0-empty-output"),
    pytest.param(_spawned("", rc=1), id="exit-1-empty-output"),
    pytest.param(_spawned("some error\r\n", rc=2), id="exit-2-error-text"),
    pytest.param(_spawned("", rc=None), id="no-exit-code-empty-output"),
    pytest.param(_spawned("Created cloud session: x\r\n", rc=1), id="exit-1-announced-no-id"),
    pytest.param(_spawned("Created cloud session: x\r\n", rc=0), id="exit-0-announced-no-id"),
    pytest.param(
        _spawned("Do you trust the files in this folder? (y/n)\r\n", rc=None, timed_out=True),
        id="trust-question-then-timeout",
    ),
]


def _assert_unconfirmed(repo, result):
    assert result["ok"] is False
    assert result["reason"] == "cloud-session-unconfirmed"
    assert result["cloudSessionName"] == "issue-656-%s" % result["launchId"][len("launch-"):]
    assert result["logPath"].endswith("%s.stdout" % result["launchId"])
    assert "session listing" in result["remedy"] and "`died`" in result["remedy"]
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is False
    assert lane["started"] is True
    assert lane["cloudSessionUnconfirmed"] is True
    assert lane["cloudSessionId"] is None and lane["cloudSessionUrl"] is None
    assert lane["cloudSessionName"] == result["cloudSessionName"]
    assert "cloudSessionId" not in _records(repo, result["launchId"], "started")[0]
    assert _records(repo, result["launchId"], "refused") == []
    assert _records(repo, result["launchId"], "outcome") == []


@pytest.mark.parametrize("spawned", UNCONFIRMED)
def test_outcome3_an_uncertain_creation_keeps_the_lane_live(tmp_path, spawned):
    # axis: an uncertain creation keeps the lane live
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(spawned))
    _assert_unconfirmed(repo, result)


def test_outcome4_a_non_zero_exit_without_a_receipt_leaves_the_lane_live_and_unconfirmed(
    tmp_path,
):
    # axis: the lane is not ended — a non-zero exit with no receipt may still have made a session
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("some error\r\n", rc=2)))
    _assert_unconfirmed(repo, result)
    assert not result["reason"].startswith("cloud-spawn-failed")
    started = _records(repo, result["launchId"], "started")
    assert len(started) == 1 and started[0]["cloudSessionUnconfirmed"] is True


def test_outcome5_a_session_token_without_a_creation_line_is_not_a_session_id(tmp_path):
    # axis: where the id is read from — only a coherent creation receipt names a session
    repo = _cloud_repo(tmp_path)
    stray = "Unable to resume prior session_old123: authentication failed\r\n"
    result = _launch(repo, tmp_path, _fake_spawn(_spawned(stray, rc=2)))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result
    assert "cloudSessionUrl" not in result


def test_outcome5_a_stray_token_beside_a_receipt_for_another_name_is_not_an_id(tmp_path):
    repo = _cloud_repo(tmp_path)
    # The foreign receipt is complete, so the only thing wrong with it is the name it announces.
    result = _launch(repo, tmp_path, _fake_spawn(_spawned(
        "Reusing session_old123 for context\n"
        + _announced("issue-656-someone-elses", "session_01OtherLane")
    )))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


def test_outcome5_a_receipt_announcing_a_different_name_is_unconfirmed(tmp_path):
    # axis: whose session it is — the announced name must be the name this launch requested
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(
        _spawned(_announced("issue-656-someone-elses", "session_01OtherLane"))
    ))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


def test_outcome5_a_receipt_whose_two_ids_differ_is_unconfirmed(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Created cloud session: %s\n"
        "View: https://claude.ai/code/session_01AAA?from=cli&m=0\n"
        "Resume with: claude --teleport session_01BBB\n" % name
    )))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


def test_a_real_captured_receipt_is_read(tmp_path):
    # axis: the output the command really printed is read, escape sequences and all
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        REAL_CAPTURE % {"name": name, "id": SESSION_ID}
    )))
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionUrl"] == SESSION_URL
    lane = _lanes(repo)[result["launchId"]]
    assert lane["cloudSessionId"] == SESSION_ID and lane["cloudSessionUrl"] == SESSION_URL


def test_the_stripper_removes_every_sequence_in_the_real_capture():
    # axis: no escape byte survives stripping
    stripped = L.strip_terminal_sequences(
        REAL_CAPTURE % {"name": "issue-656-abc", "id": SESSION_ID}
    )
    assert "\x1b" not in stripped
    assert all(char == "\n" or ord(char) >= 0x20 for char in stripped)
    # Nothing else is left behind either: the two-byte sequences leave no digit in the text.
    assert stripped == (
        "A warning line the command prints before anything else.\n"
        "Created cloud session: issue-656-abc\n"
        "View: https://claude.ai/code/%s?from=cli&m=0\n"
        "Resume with: claude --teleport %s\n" % (SESSION_ID, SESSION_ID)
    )


def test_the_creation_text_is_found_anywhere_in_its_line(tmp_path):
    # axis: text before the creation text does not hide it
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Some printable text before it. Created cloud session: %s\n"
        "View: https://claude.ai/code/%s?from=cli&m=0\n"
        "Resume with: claude --teleport %s\n" % (name, SESSION_ID, SESSION_ID)
    )))
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID


def test_a_view_line_cut_off_by_the_time_limit_is_unconfirmed(tmp_path):
    # axis: a cut-off line is not an id
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Created cloud session: %s\r\nView: https://claude.ai/code/session_01X" % name,
        rc=None, timed_out=True,
    )))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


@pytest.mark.parametrize("tail", [
    pytest.param("View: https://claude.ai/code/session_01X\r", id="view-cut-between-cr-and-lf"),
    pytest.param("Resume with: claude --teleport session_01X", id="resume-cut-no-view-before"),
    pytest.param("", id="ends-right-after-the-creation-line"),
])
def test_a_receipt_cut_off_by_the_time_limit_is_unconfirmed(tmp_path, tail):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Created cloud session: %s\r\n%s" % (name, tail), rc=None, timed_out=True,
    )))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


def test_a_complete_view_line_then_a_cut_off_resume_line_is_a_success(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Created cloud session: %s\r\nView: https://claude.ai/code/%s?from=cli&m=0\r\n"
        "Resume with: claude --teleport session_01X" % (name, SESSION_ID),
        rc=None, timed_out=True,
    )))
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionUrl"] == SESSION_URL


def test_another_sessions_receipt_after_a_bare_creation_line_is_unconfirmed(tmp_path):
    # axis: whose receipt it is — identity lines belong to the nearest creation line before them
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        "Created cloud session: %s\n" % name + _bare_receipt("issue-656-someone-elses", "session_01Other")
    )))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


def test_another_sessions_whole_receipt_before_the_requested_one_is_not_taken(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        _bare_receipt("issue-656-someone-elses", "session_01Other") + _bare_receipt(name)
    )))
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    assert _lanes(repo)[result["launchId"]]["cloudSessionId"] == SESSION_ID


def test_a_receipt_id_the_ledger_would_refuse_is_unconfirmed(tmp_path):
    # axis: one grammar — the ledger's pattern alone decides what a session id is
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(lambda name: _spawned(
        _bare_receipt(name, "session_01-bad")
    )))
    _assert_unconfirmed(repo, result)
    assert "cloudSessionId" not in result


def test_a_spawn_result_that_is_not_a_dict_leaves_the_lane_live(tmp_path):
    repo = _cloud_repo(tmp_path)

    def spawn(argv, cwd, log_path, child_env, timeout):
        return None

    result = _launch(repo, tmp_path, spawn)
    assert result["ok"] is False
    assert result["reason"] == "cloud-spawn-result-invalid"
    assert _lanes(repo)[result["launchId"]]["terminal"] is False


def test_cloud_spawn_timeout_is_passed_to_the_spawn(tmp_path):
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls), cloud_spawn_timeout=7)
    assert result["ok"] is True
    assert calls[0]["timeout"] == 7


# --- edge 5: after an uncertain creation the lane is live ---------------------------------


def test_edge5_a_second_launch_for_the_issue_is_refused_and_died_records(tmp_path):
    repo = _cloud_repo(tmp_path)
    first = _launch(repo, tmp_path, _fake_spawn(_spawned("", rc=None, timed_out=True)))
    assert first["reason"] == "cloud-session-unconfirmed"
    calls = []
    second = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert second["ok"] is False
    assert second["reason"] == "surface-overlap:%s" % first["launchId"]
    assert calls == []
    died = L.record_outcome(repo, first["launchId"], "died", "no session of that name exists")
    assert died["ok"] is True, died
    lane = _lanes(repo)[first["launchId"]]
    assert lane["terminal"] is True and lane["terminalKind"] == "outcome"
    assert lane["outcome"] == "died"
    third = _launch(repo, tmp_path, _fake_spawn())
    assert third["ok"] is True


# --- edge 6: a `started` append that fails ------------------------------------------------


def _fail_started_appends(monkeypatch, *, spare_repairs):
    real_append = ll.append

    def failing_append(repo_root, record, env=None):
        if record.get("event") == "started" and not (spare_repairs and record.get("repaired")):
            return False
        return real_append(repo_root, record, env=env)

    monkeypatch.setattr(ll, "append", failing_append)


def test_edge6_started_append_failure_after_a_coherent_receipt_leaves_the_lane_live(
    tmp_path, monkeypatch,
):
    # axis: the lane is not ended — a session exists and is working, so nothing is terminalized
    repo = _cloud_repo(tmp_path)
    _fail_started_appends(monkeypatch, spare_repairs=True)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is False
    assert result["reason"] == "cloud-started-append-failed"
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionName"] == "issue-656-%s" % result["launchId"][len("launch-"):]
    assert result["cloudSessionUrl"] == SESSION_URL
    assert result["logPath"].endswith("%s.stdout" % result["launchId"])
    assert result["startedAppend"] == "ledger-append-failed"
    assert "cloud session exists" in result["remedy"] and "record-outcome" in result["remedy"]
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is False
    assert lane["started"] is False
    assert lane["cloudSessionId"] is None
    assert _records(repo, result["launchId"], "terminal") == []
    assert _records(repo, result["launchId"], "outcome") == []
    assert _records(repo, result["launchId"], "refused") == []
    assert _records(repo, result["launchId"], "started") == []


def test_pending_started_is_returned_when_the_receipt_path_append_fails(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    tries = _flaky_started_appends(monkeypatch, failures=99)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["reason"] == "cloud-started-append-failed"
    assert len(tries) == 3
    assert result["pendingStarted"] == tries[-1]
    assert result["pendingStarted"]["cloudSessionId"] == SESSION_ID
    assert "pendingStarted" in result["remedy"]


def test_pending_started_is_returned_when_the_unconfirmed_path_append_fails(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    tries = _flaky_started_appends(monkeypatch, failures=99)
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("", rc=None, timed_out=True)))
    assert result["reason"] == "cloud-session-unconfirmed"
    assert len(tries) == 3
    assert result["pendingStarted"] == tries[-1]
    assert result["pendingStarted"]["cloudSessionUnconfirmed"] is True
    assert "pendingStarted" in result["remedy"]


def _signal_after_hello_is_read(monkeypatch, signum):
    """Send this process `signum` from inside the launcher's own read, once `hello` has come back.

    The wrapper returns the bytes it read, so the launcher has captured them before it sees the
    cancellation; the signal never races the capture.
    """
    import os as _os

    real_read = _os.read
    seen = []
    sent = []

    def read_then_signal(fd, length):
        data = real_read(fd, length)
        seen.append(data)
        if not sent and b"hello" in b"".join(seen):
            sent.append(fd)
            _os.kill(_os.getpid(), signum)
        return data

    monkeypatch.setattr(L.os, "read", read_then_signal)
    return sent


def _assert_a_launcher_signal_ends_the_group(tmp_path, monkeypatch, signum):
    import os as _os
    import signal as _signal

    log = tmp_path / "signalled.stdout"
    before = _signal.getsignal(signum)
    sent = _signal_after_hello_is_read(monkeypatch, signum)
    result = L.default_cloud_spawn(
        ["sh", "-c", "echo hello; sleep 30"], str(tmp_path), str(log), dict(_os.environ), 20,
    )
    assert sent
    assert result["readError"] == "_LauncherTerminated"
    assert "hello" in result["output"]
    assert "hello" in log.read_text()
    assert result["rc"] is not None
    assert _signal.getsignal(signum) is before


def test_a_sigterm_to_the_launcher_ends_the_command_group_and_keeps_the_output(
    tmp_path, monkeypatch, terminal,
):
    import signal as _signal

    _assert_a_launcher_signal_ends_the_group(tmp_path, monkeypatch, _signal.SIGTERM)


def test_a_sigint_to_the_launcher_ends_the_command_group_and_keeps_the_output(
    tmp_path, monkeypatch, terminal,
):
    # axis: Ctrl-C is a cancellation like SIGTERM — the same outcome, never a KeyboardInterrupt
    import signal as _signal

    _assert_a_launcher_signal_ends_the_group(tmp_path, monkeypatch, _signal.SIGINT)


def test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal(
    tmp_path, monkeypatch, terminal,
):
    # axis: bytes still buffered in the pty master when the signal lands are drained before the
    # raise, not lost — see bite-proof record c8a_wo1.md
    import os as _os
    import select as _select
    import signal as _signal

    gate = tmp_path / "go"
    real_read = _os.read
    sent = []

    def read_then_signal_then_open_the_gate(fd, length):
        data = real_read(fd, length)
        if not sent and b"head" in data:
            sent.append(fd)
            _os.kill(_os.getpid(), _signal.SIGTERM)
            # The child writes `tail` only once this file exists, which is after the signal is
            # recorded, so the line can never have been read ahead of the cancellation.
            gate.write_text("go")
            # Hold the return until `tail` is buffered in the master, so the test never races the
            # child: the loop then sees the signal with unread bytes waiting, whatever the load.
            _select.select([fd], [], [], 10)
        return data

    monkeypatch.setattr(L.os, "read", read_then_signal_then_open_the_gate)
    script = f"echo head; while [ ! -e {shlex.quote(str(gate))} ]; do sleep 0.01; done; echo tail; sleep 30"
    result = L.default_cloud_spawn(
        ["sh", "-c", script], str(tmp_path), str(tmp_path / "t.stdout"), dict(_os.environ), 20,
    )
    assert sent
    assert result["readError"] == "_LauncherTerminated"
    assert "head" in result["output"]
    assert "tail" in result["output"]
    assert "tail" in (tmp_path / "t.stdout").read_text()
    assert result["rc"] is not None


# The one bound on waiting for a killed group's members to exit. SIGKILL cannot be caught or
# blocked, but the kernel delivers it asynchronously, so a member the launcher's group kill reached
# may still be finishing its exit when the call returns; this bounds that. A member still running
# at the bound was never killed and fails the test. A green run waits only for the kernel.
_GROUP_EXIT_BOUND_SECONDS = 10


def _members_of_group(pgid):
    """Every pid in process group `pgid`, zombies included."""
    if os.path.isdir("/proc/self"):
        pids = []
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % name) as fh:
                    stat = fh.read()
            except OSError:
                continue  # the process went away between the listing and the read
            fields = stat[stat.rfind(")") + 2:].split()  # state, ppid, pgrp, ...
            if len(fields) > 2 and int(fields[2]) == pgid:
                pids.append(int(name))
        return pids
    out = subprocess.run(
        ["ps", "-A", "-o", "pid=,pgid="], capture_output=True, text=True, check=True,
    ).stdout
    rows = (line.split() for line in out.splitlines() if line.strip())
    return [int(pid) for pid, group in rows if int(group) == pgid]


def _in_group(pid, pgid):
    try:
        return os.getpgid(pid) == pgid
    except ProcessLookupError:
        return False


def _exits_by(pid, pgid, deadline):
    """True once `pid` has exited (a zombie has), False when it is still running at `deadline`.

    It waits on the kernel's own exit event for the pid, never on a sleep. The membership check
    runs after the handle is held, so a pid reaped and reused by an unrelated process reads as an
    exited member.
    """
    if hasattr(os, "pidfd_open"):
        try:
            handle = os.pidfd_open(pid)
        except ProcessLookupError:
            return True
        try:
            if not _in_group(pid, pgid):
                return True
            ready, _, _ = select.select([handle], [], [], max(0, deadline - time.monotonic()))
            return bool(ready)
        finally:
            os.close(handle)
    queue = select.kqueue()
    try:
        exit_event = select.kevent(
            pid, filter=select.KQ_FILTER_PROC, flags=select.KQ_EV_ADD,
            fflags=select.KQ_NOTE_EXIT,
        )
        try:
            queue.control([exit_event], 0, 0)
        except ProcessLookupError:
            return True  # gone, or already a zombie, which kqueue does not attach to
        if not _in_group(pid, pgid):
            return True
        return bool(queue.control(None, 1, max(0, deadline - time.monotonic())))
    finally:
        queue.close()


def _group_members_still_running(pgid):
    """The members of group `pgid` still running once each has had the bound to exit.

    A killed member is not required to be reaped: an orphaned grandchild is its init's to reap,
    which happens whenever init gets to it, and never in a container whose pid 1 does not reap. A
    zombie is a process that has ended, so it counts as ended here.
    """
    if not hasattr(os, "pidfd_open") and not hasattr(select, "kqueue"):
        pytest.skip("no process-exit event (os.pidfd_open or select.kqueue) on this host")
    deadline = time.monotonic() + _GROUP_EXIT_BOUND_SECONDS
    return [pid for pid in _members_of_group(pgid) if not _exits_by(pid, pgid, deadline)]


def test_a_sigterm_landing_as_the_child_starts_still_ends_its_group(
    tmp_path, monkeypatch, terminal,
):
    # axis: a launcher cancelled between child creation and the read loop still ends the group
    import os as _os
    import signal as _signal

    real_popen = L.subprocess.Popen
    started = []

    def popen_then_sigterm(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        started.append(proc)
        _os.kill(_os.getpid(), _signal.SIGTERM)
        return proc

    monkeypatch.setattr(L.subprocess, "Popen", popen_then_sigterm)
    before = _signal.getsignal(_signal.SIGTERM)
    result = L.default_cloud_spawn(
        ["sh", "-c", "sleep 30"], str(tmp_path), str(tmp_path / "t.stdout"), dict(_os.environ), 20,
    )
    monkeypatch.undo()  # the membership read may run `ps`, which must not send a SIGTERM
    assert result["readError"] == "_LauncherTerminated"
    assert result["rc"] is not None
    assert _group_members_still_running(started[0].pid) == []
    assert _signal.getsignal(_signal.SIGTERM) is before


def test_a_sigterm_landing_during_the_cleanup_does_not_cut_the_group_kill_short(
    tmp_path, monkeypatch, terminal,
):
    # axis: a launcher cancelled while the cleanup is under way still ends the group it started
    import os as _os
    import signal as _signal

    real_killpg = _os.killpg
    signalled = []

    def sigterm_then_killpg(pid, sig):
        if sig == _signal.SIGKILL and not signalled:
            signalled.append(pid)
            _os.kill(_os.getpid(), _signal.SIGTERM)
        return real_killpg(pid, sig)

    monkeypatch.setattr(L.os, "killpg", sigterm_then_killpg)
    before = _signal.getsignal(_signal.SIGTERM)
    result = L.default_cloud_spawn(
        ["sh", "-c", "sleep 30"], str(tmp_path), str(tmp_path / "t.stdout"), dict(_os.environ), 1,
    )
    monkeypatch.undo()
    assert len(signalled) == 1
    assert result["timedOut"] is True
    assert result["rc"] is not None
    assert _group_members_still_running(signalled[0]) == []
    assert result["readError"] == "_LauncherTerminated"
    assert _signal.getsignal(_signal.SIGTERM) is before


def _flaky_started_appends(monkeypatch, failures):
    """The first `failures` tries of a `started` append fail; the count of tries made."""
    real_append = ll.append
    tries = []

    def flaky_append(repo_root, record, env=None):
        if record.get("event") == "started":
            tries.append(record)
            if len(tries) <= failures:
                return False
        return real_append(repo_root, record, env=env)

    monkeypatch.setattr(ll, "append", flaky_append)
    return tries


def test_a_started_append_that_fails_twice_then_succeeds_is_a_success(tmp_path, monkeypatch):
    # axis: one failure does not strand the lane
    repo = _cloud_repo(tmp_path)
    tries = _flaky_started_appends(monkeypatch, failures=2)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is True, result
    assert result["cloudSessionId"] == SESSION_ID
    assert len(tries) == 3
    assert len(_records(repo, result["launchId"], "started")) == 1
    lane = _lanes(repo)[result["launchId"]]
    assert lane["started"] is True and lane["cloudSessionId"] == SESSION_ID


def test_a_started_append_that_fails_three_times_is_tried_exactly_three_times(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    tries = _flaky_started_appends(monkeypatch, failures=99)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is False
    assert result["reason"] == "cloud-started-append-failed"
    assert result["startedAppend"] == "ledger-append-failed"
    assert result["remedy"] == L._CLOUD_STARTED_APPEND_REMEDY
    assert len(tries) == 3
    assert _records(repo, result["launchId"], "started") == []


def test_the_unconfirmed_path_with_a_failed_append_does_not_say_to_record_died(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    tries = _flaky_started_appends(monkeypatch, failures=99)
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("", rc=None, timed_out=True)))
    assert result["reason"] == "cloud-session-unconfirmed"
    assert result["startedAppend"] == "ledger-append-failed"
    assert len(tries) == 3
    remedy = result["remedy"]
    assert remedy == L._CLOUD_UNCONFIRMED_APPEND_REMEDY
    assert "died" not in remedy
    assert "`reserved` record alone" in remedy
    assert "`cloudSessionName`" in remedy
    assert "launcher.py repair-lane --pending-file" in remedy
    assert result["remedy"] != L._CLOUD_UNCONFIRMED_REMEDY


def test_the_started_append_pauses_between_its_tries(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    _flaky_started_appends(monkeypatch, failures=99)
    pauses = []
    monkeypatch.setattr(L, "_pause_between_appends", lambda: pauses.append(True))
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["reason"] == "cloud-started-append-failed"
    assert len(pauses) == 2
    assert 0 < L._CLOUD_APPEND_PAUSE_SECONDS < 1


def test_edge6_a_second_launch_is_refused_while_an_append_failed_lane_is_live(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    with monkeypatch.context() as patched:
        _fail_started_appends(patched, spare_repairs=True)
        first = _launch(repo, tmp_path, _fake_spawn())
    assert first["reason"] == "cloud-started-append-failed"
    calls = []
    second = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert second["ok"] is False
    assert second["reason"] == "surface-overlap:%s" % first["launchId"]
    assert calls == []


def test_outcome3_a_second_launch_is_refused_while_a_non_zero_exit_lane_is_live(tmp_path):
    repo = _cloud_repo(tmp_path)
    first = _launch(repo, tmp_path, _fake_spawn(_spawned("some error\r\n", rc=2)))
    assert first["reason"] == "cloud-session-unconfirmed"
    calls = []
    second = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    assert second["ok"] is False
    assert second["reason"] == "surface-overlap:%s" % first["launchId"]
    assert calls == []


# --- every path past the spawn leaves the lane to the ledger's owner ---------------------


def _drive_cloud_spawn(tmp_path, monkeypatch, *, spawned=None, raises=None, append_ok=True,
                       err_dir_exists=True):
    """`_run_cloud_spawn` driven directly, with `_terminalize` replaced by a recorder."""
    terminalized = []

    def recorder(*args, **kwargs):
        terminalized.append((args, kwargs))
        return {"ok": True, "reason": None}

    monkeypatch.setattr(L, "_terminalize", recorder)
    monkeypatch.setattr(
        L, "_append_under_lock",
        lambda repo_root, record, env=None: (
            {"ok": True} if append_ok else {"ok": False, "reason": "ledger-append-failed"}
        ),
    )

    def spawn(argv, cwd, log_path, child_env, timeout):
        if raises is not None:
            raise raises
        return spawned(_requested_name(argv)) if callable(spawned) else spawned

    name = "issue-656-census"
    err_path = str(tmp_path / ("err" if err_dir_exists else "no-such-dir") / "launch.stderr")
    (tmp_path / "err").mkdir(exist_ok=True)
    result = L._run_cloud_spawn(
        str(tmp_path), "launch-census", ["claude", "--cloud", "p", "-n", name], name,
        str(tmp_path / "launch.stdout"), err_path, {}, 5, spawn, None, {},
        lambda reason, **extra: dict(extra, ok=False, reason=reason),
        {"ok": True, "reason": None},
    )
    return result, terminalized


@pytest.mark.parametrize("drive", [
    pytest.param(dict(err_dir_exists=False), id="edge1-err-path-unopenable"),
    pytest.param(dict(raises=FileNotFoundError("claude")), id="edge2-spawn-oserror"),
])
def test_census_a_command_that_never_started_is_terminalized(tmp_path, monkeypatch, drive):
    result, terminalized = _drive_cloud_spawn(
        tmp_path, monkeypatch, spawned=_spawned(""), **drive,
    )
    assert result["ok"] is False
    assert len(terminalized) == 1
    assert terminalized[0][0][3] in ("log-open-failed", "spawn-oserror")


@pytest.mark.parametrize("drive,reason", [
    pytest.param(dict(spawned=None), "cloud-spawn-result-invalid", id="edge3-not-a-dict"),
    pytest.param(
        dict(spawned=lambda name: _spawned(_announced(name))), None, id="edge4-receipt-appended",
    ),
    pytest.param(
        dict(spawned=lambda name: _spawned(_announced(name)), append_ok=False),
        "cloud-started-append-failed", id="edge5-receipt-append-failed",
    ),
    pytest.param(dict(spawned=_spawned("", rc=0)), "cloud-session-unconfirmed", id="edge6-rc0"),
    pytest.param(
        dict(spawned=_spawned("some error", rc=2)), "cloud-session-unconfirmed", id="edge6-rc2",
    ),
    pytest.param(
        dict(spawned=_spawned("", rc=None, timed_out=True)), "cloud-session-unconfirmed",
        id="edge6-timed-out",
    ),
    pytest.param(
        dict(spawned=_spawned("some error", rc=2), append_ok=False), "cloud-session-unconfirmed",
        id="edge7-unconfirmed-append-failed",
    ),
])
def test_census_once_the_command_has_run_nothing_is_terminalized(
    tmp_path, monkeypatch, drive, reason,
):
    # axis: the lane is not ended — after the spawn returned, `_run_cloud_spawn` never terminalizes
    result, terminalized = _drive_cloud_spawn(tmp_path, monkeypatch, **drive)
    assert terminalized == []
    assert result["reason"] == reason
    assert result["ok"] is (reason is None)


def test_edge6_started_append_failure_when_unconfirmed_terminalizes_nothing(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    _fail_started_appends(monkeypatch, spare_repairs=True)
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("", rc=None, timed_out=True)))
    assert result["ok"] is False
    assert result["reason"] == "cloud-session-unconfirmed"
    assert result["startedAppend"] == "ledger-append-failed"
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is False
    assert lane["started"] is False
    assert _records(repo, result["launchId"], "outcome") == []
    assert _records(repo, result["launchId"], "refused") == []


# --- edge 7: a cloud lane needs no slot ---------------------------------------------------


def test_edge7_a_cloud_launch_in_a_slot_calibrated_parallel_batch_needs_no_slot(
    tmp_path, monkeypatch,
):
    # axis: a cloud lane needs no slot
    repo = _cloud_repo(tmp_path)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 3)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is True, result
    assert _lanes(repo)[result["launchId"]]["place"] == "cloud"


def test_edge7_a_live_cloud_lane_does_not_block_a_slotted_local_launch(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 3)
    first = _launch(repo, tmp_path, _fake_spawn())
    assert first["ok"] is True, first
    slotted = L.walk_preflight(
        _all_checks(), repo, batch_id="wave-test", slot="slot-a", generation=1,
    )
    assert slotted["ok"] is True, slotted
    unslotted = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert unslotted["ok"] is False
    assert unslotted["reason"] == "preflight-slot-reservation-required"
    assert unslotted["missing"] == ["this-launch"]
    cloud = L.walk_preflight(_all_checks(), repo, batch_id="wave-test", place="cloud")
    assert cloud["ok"] is True, cloud


def test_edge7_a_live_unslotted_local_lane_still_blocks_a_cloud_launch(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 3)
    _reserve_live_lane(repo, "wave-test", "live-local")
    result = _launch(repo, tmp_path, _fake_spawn(),
                     premise=_valid_premise(repo, issue=700, surfaces=["plugins/elsewhere"]),
                     issue=700)
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert result["missing"] == ["live-local"]


def test_edge7_a_cloud_lane_is_visible_in_the_live_state(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    _not_slot_calibrated(monkeypatch)
    result = _launch(repo, tmp_path, _fake_spawn(), issue=701,
                     premise=_valid_premise(repo, issue=701))
    state = L._ledger_live_state(repo)
    assert state["detail"][result["launchId"]]["place"] == "cloud"
    assert state["allDetail"][result["launchId"]]["place"] == "cloud"
    _reserve_live_lane(repo, "other-batch", "live-local", surfaces=["plugins/else"])
    assert L._ledger_live_state(repo)["detail"]["live-local"]["place"] == "local"


# --- outcomes and the canary on a cloud lane ---------------------------------------------


@pytest.mark.parametrize("outcome", ["handback", "park", "died"])
def test_record_outcome_on_a_started_cloud_lane(tmp_path, outcome):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn())
    recorded = L.record_outcome(repo, result["launchId"], outcome, "evidence for %s" % outcome)
    assert recorded["ok"] is True, recorded
    assert recorded["recorded"] == "outcome"
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True and lane["outcome"] == outcome


def test_canary_refuses_cloud_lane(tmp_path):
    # axis: a cloud lane is not read as a lane with a missing transcript
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn())
    canary = L.canary(repo, result["launchId"])
    assert canary["ok"] is False
    assert canary["reason"] == "canary-cloud-lane"


# --- the command line --------------------------------------------------------------------


def _args(**overrides):
    base = dict(
        repo_root=None, issue=656, premise=None, checks=None, log_dir=None, model=None,
        effort=None, slot=None, generation=None, boundary=None, allow_foreign_instance=False,
        place=None, cloud_environment=None, batch=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_cli_compose_cloud_names_the_preview_session(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise_path = tmp_path / "premise.json"
    _write_json(premise_path, _valid_premise(repo))
    result = L._cli_compose(_args(
        repo_root=repo, premise=str(premise_path), place="cloud", cloud_environment=ENV_ID,
    ))
    assert result["ok"] is True, result
    assert result["place"] == "cloud"
    assert result["cloudSessionName"] == "issue-656-preview"
    assert result["argv"][-2:] == ["-n", "issue-656-preview"]


def test_cli_compose_without_a_place_is_the_local_compose(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise_path = tmp_path / "premise.json"
    _write_json(premise_path, _valid_premise(repo))
    result = L._cli_compose(_args(repo_root=repo, premise=str(premise_path)))
    assert result["ok"] is True
    assert "place" not in result
    assert result["sessionId"]


def test_cli_launch_refuses_an_environment_and_compose_forwards_one(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    checks_path, premise_path = tmp_path / "checks.json", tmp_path / "premise.json"
    _write_json(checks_path, _all_checks())
    _write_json(premise_path, _valid_premise(repo))
    forwarded = []

    def capture(*args, **kwargs):
        forwarded.append(kwargs)
        return {"ok": False, "reason": "injected-stop"}

    monkeypatch.setattr(L, "launch_build", capture)
    composed = []

    def compose(*args, **kwargs):
        composed.append(kwargs)
        return {"ok": False, "reason": "injected-stop"}

    monkeypatch.setattr(L, "compose_launch", compose)
    common = dict(repo_root=repo, premise=str(premise_path), checks=str(checks_path),
                  log_dir=str(tmp_path / "logs"))
    refused = L._cli_launch(_args(place="cloud", cloud_environment=ENV_ID, **common))
    assert refused["ok"] is False and refused["reason"] == "launch-cloud-environment-routed"
    assert forwarded == []
    L._cli_compose(_args(place="cloud", cloud_environment=ENV_ID, **common))
    assert composed[0]["place"] == "cloud"
    assert composed[0]["cloud_environment"] == ENV_ID


def test_cli_preflight_forwards_the_place(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    checks_path = tmp_path / "checks.json"
    _write_json(checks_path, _all_checks())
    seen = {}

    def capture(checks, repo_root, **kwargs):
        seen.update(kwargs)
        return {"ok": True, "reason": None}

    monkeypatch.setattr(L, "walk_preflight", capture)
    L._cli_preflight(_args(repo_root=repo, checks=str(checks_path), place="cloud"))
    assert seen["place"] == "cloud"


@pytest.mark.parametrize("verb", ["launch", "compose", "preflight"])
def test_cli_place_flag_accepts_only_local_and_cloud(verb, capsys):
    common = {
        "launch": ["--issue", "1", "--premise", "p", "--checks", "c", "--log-dir", "l"],
        "compose": ["--issue", "1", "--premise", "p"],
        "preflight": ["--checks", "c"],
    }[verb]
    with pytest.raises(SystemExit) as exc:
        L.main([verb, "--repo-root", "r", *common, "--place", "elsewhere"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


_VERB_ARGS = {
    "launch": ["--issue", "1", "--premise", "p", "--checks", "c", "--log-dir", "l"],
    "compose": ["--issue", "1", "--premise", "p"],
    "preflight": ["--checks", "c"],
}


@pytest.mark.parametrize("verb", ["compose", "preflight"])
@pytest.mark.parametrize("word", ["local", "cloud"])
def test_cli_place_flag_reaches_compose_and_preflight_as_a_mechanical_place(
    verb, word, monkeypatch,
):
    seen = []
    monkeypatch.setattr(L, "_cli_" + verb, lambda args: seen.append(args.place) or {"ok": True})
    assert L.main([verb, "--repo-root", "r", *_VERB_ARGS[verb], "--place", word]) == 0
    assert seen == [word]


def test_cli_launch_place_flag_is_the_launch_word_and_takes_only_local_and_cloud(
    monkeypatch, capsys,
):
    seen = []
    monkeypatch.setattr(L, "_cli_launch", lambda args: seen.append(args.place) or {"ok": True})
    for word in ("local", "cloud"):
        assert L.main(["launch", "--repo-root", "r", *_VERB_ARGS["launch"], "--place", word]) == 0
    assert L.main(["launch", "--repo-root", "r", *_VERB_ARGS["launch"]]) == 0
    assert seen == ["local", "cloud", None]
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        L.main(["launch", "--repo-root", "r", *_VERB_ARGS["launch"], "--place", "elsewhere"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("verb", ["compose", "preflight"])
def test_cli_compose_and_preflight_take_no_boundary_file(verb, capsys):
    # A boundary is a fallback resource of a launch; the previews have nowhere to take one.
    with pytest.raises(SystemExit) as exc:
        L.main([
            verb, "--repo-root", "r", *_VERB_ARGS[verb], "--place", "cloud", "--boundary", "b",
        ])
    assert exc.value.code == 2
    assert "unrecognized arguments: --boundary" in capsys.readouterr().err


def test_a_cloud_place_with_slot_generation_and_boundary_answers_cloud_with_slot(tmp_path):
    # The mechanical cloud launch names the cloud's own refusal, never a slot or boundary token.
    repo = _cloud_repo(tmp_path)
    calls = []
    result = _launch(
        repo, tmp_path, _fake_spawn(calls=calls),
        slot="slot-a", generation=1, boundary={"slotRef": "slot-a@1"},
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-cloud-with-slot"
    _assert_nothing_written(repo, calls)


_ROUTED_CLOUD = {
    "place": "cloud", "pointedAtCloud": True, "by": "word", "reason": None, "need": None,
    "cloudVersion": None, "advisorVersion": None, "environment": ENV_ID, "reported": None,
}


def test_cli_launch_holds_slot_generation_and_boundary_back_from_a_cloud_call(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    checks_path, premise_path = tmp_path / "checks.json", tmp_path / "premise.json"
    boundary_path = tmp_path / "boundary.json"
    _write_json(checks_path, _all_checks())
    _write_json(premise_path, _valid_premise(repo))
    _write_json(boundary_path, {"slotRef": "slot-a@1"})
    forwarded = []

    def capture(*args, **kwargs):
        forwarded.append(kwargs)
        return {"ok": True, "reason": None}

    monkeypatch.setattr(
        L.launch_place, "route", lambda cwd, premise, word=None, **kw: _ROUTED_CLOUD,
    )
    monkeypatch.setattr(L, "launch_build", capture)
    result = L._cli_launch(_args(
        repo_root=repo, premise=str(premise_path), checks=str(checks_path),
        log_dir=str(tmp_path / "logs"), place="cloud", slot="slot-a", generation=1,
        boundary=str(boundary_path),
    ))
    assert len(forwarded) == 1
    assert forwarded[0]["place"] == "cloud"
    assert forwarded[0]["cloud_environment"] == ENV_ID
    for held_back in ("slot", "generation", "boundary"):
        assert held_back not in forwarded[0]
    assert result["fallbackResourcesUnused"] == {"slot": "slot-a", "generation": 1}
