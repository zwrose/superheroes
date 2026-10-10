"""A cloud launch: `launch` starts a builder in a cloud session instead of a local child.

The platform command is never run here: every `launch_build` test injects the spawn function, and
the default spawn function is driven with stand-in scripts. A cloud launch makes no worktree,
leaves no local process, pushes nothing, and never ends a lane as refused when a cloud session may
exist.
"""
import argparse
import json
import os
import signal
import subprocess
import sys

import pytest

import engine_adapter as EA
import heartbeat as hb
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

SESSION_ID = "session_01XkoXctZReLbM87S13947gp"
SESSION_URL = "https://claude.ai/code/%s" % SESSION_ID
ENV_ID = "env_01AbCdEf"
FAKE_PID = 424242


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    # The instance-pin gate applies only on a Claude-hosted seat; these tests are not one.
    monkeypatch.delenv("CLAUDE_PID", raising=False)


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
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _announced(name="issue-656-x", session_id=SESSION_ID):
    """The measured output of the platform command, wrapped in terminal control sequences."""
    return (
        "\x1b[?25l\x1b[2K\r"
        "Created cloud session: %s\r\n"
        "\x1b[1mView:\x1b[0m https://claude.ai/code/%s?from=cli&m=0\r\n"
        "Resume with: claude --teleport %s\r\n"
        "Branch build/1742-cloud-lane is not on GitHub, so the cloud session starts from its "
        "own commit, which origin/main has (fab8a63ea7f4).\r\n"
        "\x1b]0;claude\x07\x1b[?25h"
    ) % (name, session_id, session_id)


def _spawned(output="", rc=0, timed_out=False, pid=FAKE_PID):
    return {"pid": pid, "rc": rc, "timedOut": timed_out, "output": output}


def _fake_spawn(result=None, calls=None, raises=None):
    def spawn(argv, cwd, log_path, child_env, timeout):
        if calls is not None:
            calls.append({
                "argv": list(argv), "cwd": cwd, "logPath": log_path,
                "env": dict(child_env), "timeout": timeout,
            })
        if raises is not None:
            raise raises
        return result if result is not None else _spawned(_announced())
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
            "--model", "opus", "--effort", "medium", "-n", "issue-1-ab",
        ],
        "reason": None,
    }


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


def test_compose_cloud_prompt_differs_from_local_by_exactly_the_two_place_lines(tmp_path):
    # axis: the prompt differs from the local one by exactly those lines
    repo = _init_repo(tmp_path / "repo")
    local = L.compose_launch(repo, 656, _stamped(repo))
    cloud = _compose_cloud(repo)
    assert local["ok"] is True and cloud["ok"] is True
    version = L.plugin_version()
    lines = "Place: cloud session\nAdvisor plugin version: %s\n\n" % version
    assert lines in cloud["prompt"]
    assert cloud["prompt"].replace(lines, "", 1) == local["prompt"]
    rulings = local["doctrine"]["rulingsBlock"]
    assert rulings
    assert cloud["doctrine"]["rulingsBlock"] == rulings
    assert local["prompt"].endswith(rulings)
    assert cloud["prompt"].endswith(rulings)


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


# --- edge 3: HEAD must be on a remote branch ----------------------------------------------


def test_edge3_head_not_on_a_remote_branch_is_an_accounted_refusal(tmp_path):
    # axis: no cloud spawn from a commit the remote lacks
    repo = _init_repo(tmp_path / "repo")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-head-not-on-remote", "cloud-base")
    assert calls == []
    assert "warnings" in result


def test_edge3_a_remote_branch_without_head_still_refuses(tmp_path):
    repo = _cloud_repo(tmp_path)
    (tmp_path / "repo" / "later.txt").write_text("later\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-q", "-m", "later")
    calls = []
    result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                     premise=_valid_premise(repo, baseCommit=_head_sha(repo)))
    _assert_refused_cloud_lane(repo, result, "launch-cloud-head-not-on-remote", "cloud-base")
    assert calls == []


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
    result = L._default_cloud_spawn(
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


def test_default_spawn_kills_its_own_child_on_timeout(tmp_path, terminal):
    # axis: no child process outlives the launch
    script = _script(tmp_path, "import time\nprint('Created cloud session: x', flush=True)\n"
                              "time.sleep(30)\n")
    descriptors = _open_descriptors()
    result = None
    try:
        result = L._default_cloud_spawn(
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


def test_default_spawn_raises_oserror_for_a_missing_command_and_closes_descriptors(
    tmp_path, terminal,
):
    descriptors = _open_descriptors()
    with pytest.raises(OSError):
        L._default_cloud_spawn(
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


@pytest.mark.parametrize("spawned", [
    _spawned(_announced(), rc=1),
    _spawned(_announced(), rc=0),
    _spawned(_announced(), rc=None, timed_out=True),
    _spawned("Created cloud session: x\nsession_Abc123\n", rc=7),
], ids=["exit-1-with-id", "exit-0", "timed-out-with-id", "garbled"])
def test_outcome2_a_session_id_is_a_success_whatever_the_exit_code(tmp_path, spawned):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(spawned))
    assert result["ok"] is True, result
    assert result["cloudSessionId"].startswith("session_")
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is False and lane["started"] is True
    assert lane["cloudSessionId"] == result["cloudSessionId"]


def test_outcome2_without_a_url_the_url_is_none(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("Created cloud session: x\n"
                                                         "Resume with: claude --teleport %s\n"
                                                         % SESSION_ID)))
    assert result["ok"] is True
    assert result["cloudSessionUrl"] is None
    assert _lanes(repo)[result["launchId"]]["cloudSessionUrl"] is None


UNCONFIRMED = [
    pytest.param(_spawned("", rc=None, timed_out=True), id="timeout-no-output"),
    pytest.param(_spawned("", rc=0), id="exit-0-empty-output"),
    pytest.param(_spawned("Created cloud session: x\r\n", rc=1), id="exit-1-announced-no-id"),
    pytest.param(
        _spawned("Do you trust the files in this folder? (y/n)\r\n", rc=None, timed_out=True),
        id="trust-question-then-timeout",
    ),
]


@pytest.mark.parametrize("spawned", UNCONFIRMED)
def test_outcome3_an_uncertain_creation_keeps_the_lane_live(tmp_path, spawned):
    # axis: an uncertain creation keeps the lane live
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(spawned))
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
    assert _records(repo, result["launchId"], "refused") == []
    assert _records(repo, result["launchId"], "outcome") == []


def test_outcome4_a_confirmed_non_creation_is_terminalized(tmp_path):
    repo = _cloud_repo(tmp_path)
    result = _launch(repo, tmp_path, _fake_spawn(_spawned("some error\r\n", rc=2)))
    assert result["ok"] is False
    assert result["reason"] == "cloud-spawn-failed:2"
    assert result["logPath"].endswith("%s.stdout" % result["launchId"])
    lane = _lanes(repo)[result["launchId"]]
    assert lane["terminal"] is True and lane["terminalKind"] == "refused"
    assert lane["started"] is False
    assert [r["stage"] for r in _records(repo, result["launchId"], "refused")] == ["spawn"]


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


def test_edge6_started_append_failure_after_a_session_id_repairs_with_the_cloud_fields(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    _fail_started_appends(monkeypatch, spare_repairs=True)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is False
    assert result["cloudSessionId"] == SESSION_ID
    assert result["cloudSessionName"].startswith("issue-656-")
    lane = _lanes(repo)[result["launchId"]]
    assert lane["started"] is True
    assert lane["cloudSessionId"] == SESSION_ID
    assert lane["cloudSessionUrl"] == SESSION_URL
    assert lane["cloudSessionName"] == result["cloudSessionName"]
    assert lane["terminal"] is True and lane["terminalKind"] == "outcome"
    assert lane["outcome"] == "park"
    repaired = _records(repo, result["launchId"], "started")[0]
    assert repaired["repaired"] is True


def test_edge6_started_append_failure_without_a_repair_reports_the_terminalization_failure(
    tmp_path, monkeypatch,
):
    repo = _cloud_repo(tmp_path)
    _fail_started_appends(monkeypatch, spare_repairs=False)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is False
    assert result["reason"] == "terminalization-failed:ledger-append-failed"
    assert result["cloudSessionId"] == SESSION_ID
    assert _lanes(repo)[result["launchId"]]["terminal"] is False


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


def test_cli_launch_forwards_place_and_environment_only_when_a_place_is_given(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    checks_path, premise_path = tmp_path / "checks.json", tmp_path / "premise.json"
    _write_json(checks_path, _all_checks())
    _write_json(premise_path, _valid_premise(repo))
    forwarded = []

    def capture(*args, **kwargs):
        forwarded.append(kwargs)
        return {"ok": False, "reason": "injected-stop"}

    monkeypatch.setattr(L, "launch_build", capture)
    common = dict(repo_root=repo, premise=str(premise_path), checks=str(checks_path),
                  log_dir=str(tmp_path / "logs"))
    L._cli_launch(_args(**common))
    L._cli_launch(_args(place="cloud", cloud_environment=ENV_ID, **common))
    assert "place" not in forwarded[0] and "cloud_environment" not in forwarded[0]
    assert forwarded[1]["place"] == "cloud"
    assert forwarded[1]["cloud_environment"] == ENV_ID


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
