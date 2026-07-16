import json
import subprocess
import sys

import pytest

import test_pilot_server_config as cfg
import test_pilot_server_config_cli as cli


def test_profile_argv_resolves_to_managed_context():
    result = cfg.resolve(
        {"baseUrl": "http://localhost:5173", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-90",
    )

    assert result == {
        "schemaVersion": 1,
        "verdict": "managed",
        "workItem": "issue-90",
        "baseUrl": "http://localhost:5173",
        "readinessUrl": "http://localhost:5173/",
        "port": 5173,
        "portSource": "profile.baseUrl",
        "portDisclosure": "probing :5173 per profile.baseUrl",
        "command": ["npm", "run", "dev"],
        "shell": False,
        "source": "profile",
        "teardownRequired": True,
    }


@pytest.mark.parametrize(
    "command",
    [
        [],
        ["npm", 7, "dev"],
        ["npm", "run", "dev;rm -rf x"],
    ],
)
def test_unsafe_profile_argv_parks_before_launch(command):
    result = cfg.resolve({"devCommand": command, "mayManageServer": True}, {}, "issue-90")

    assert result["verdict"] == "park"
    assert "devCommand" in result["reason"]


def test_legacy_string_profile_command_parks_before_launch():
    result = cfg.resolve({"devCommand": "npm run dev", "mayManageServer": True}, {}, "issue-90")

    assert result["verdict"] == "park"
    assert "argv array" in result["reason"]


def test_package_detection_uses_safe_argv():
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "mayManageServer": True},
        {"source": "package.json", "script": "dev", "command": "npm run dev"},
        "issue-90",
    )

    assert result["verdict"] == "managed"
    assert result["command"] == ["npm", "run", "dev"]
    assert result["shell"] is False
    assert result["source"] == "package.json"


def test_package_detection_without_safe_metadata_parks():
    result = cfg.resolve(
        {"mayManageServer": True},
        {"source": "package.json", "command": "npm run dev && echo started"},
        "issue-90",
    )

    assert result["verdict"] == "park"
    assert "safe argv" in result["reason"]


def test_may_not_manage_requires_ready_external_server():
    ready = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "mayManageServer": False},
        {"ready": True},
        "issue-90",
    )
    parked = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "mayManageServer": False},
        {"ready": False},
        "issue-90",
    )

    assert ready["verdict"] == "ready_external"
    assert ready["teardownRequired"] is False
    assert "command" not in ready
    assert parked["verdict"] == "park"


def test_launch_uses_shell_false_for_argv_commands():
    calls = []

    def start(command, port, cwd=None, env=None, shell=None):
        calls.append((command, shell))
        return {"pid": 123, "port": port, "command": command}

    context = cfg.resolve({"devCommand": ["npm", "run", "dev"], "mayManageServer": True}, {}, "issue-90")
    launched = cfg.launch(context, start=start, poll_healthy=lambda *a, **k: True)

    assert launched["verdict"] == "managed"
    assert launched["handle"]["pid"] == 123
    assert calls == [(["npm", "run", "dev"], False)]


@pytest.mark.parametrize("poll_result", [False, Exception("boom")])
def test_launch_tears_down_managed_server_when_readiness_does_not_pass(poll_result):
    torn_down = []

    def start(command, port, cwd=None, env=None, shell=None):
        return {"pid": 123, "port": port, "command": command}

    def poll(*args, **kwargs):
        if isinstance(poll_result, Exception):
            raise poll_result
        return poll_result

    context = cfg.resolve({"devCommand": ["npm", "run", "dev"], "mayManageServer": True}, {}, "issue-90")
    result = cfg.launch(context, start=start, poll_healthy=poll, teardown=torn_down.append)

    assert result["verdict"] == "park"
    assert torn_down == [{"pid": 123, "port": 3000, "command": ["npm", "run", "dev"]}]


@pytest.mark.parametrize(
    "outcome",
    [
        {"action": "browser_failed"},
        {"action": "park_after_timeout"},
        {"action": "park_exception"},
        {"action": "park_retry_terminal"},
        {"action": "completed"},
    ],
)
def test_managed_server_tears_down_on_terminal_outcomes(outcome):
    torn_down = []
    context = {"verdict": "managed", "handle": {"pid": 123}}

    result = cfg.finish(context, outcome, teardown=torn_down.append)

    assert result == outcome
    assert torn_down == [{"pid": 123}]


def test_ready_external_never_starts_or_tears_down():
    context = cfg.resolve({"mayManageServer": False}, {"ready": True}, "issue-90")

    launched = cfg.launch(
        context,
        start=lambda *a, **k: pytest.fail("external server must not start"),
        poll_healthy=lambda *a, **k: pytest.fail("external server must not poll here"),
    )
    result = cfg.finish(launched, {"action": "completed"}, teardown=lambda h: pytest.fail("external server must not teardown"))

    assert launched["verdict"] == "ready_external"
    assert result == {"action": "completed"}


def test_cli_resolve_prints_server_context_json(tmp_path):
    profile = tmp_path / "profile.json"
    detection = tmp_path / "detection.json"
    profile.write_text(json.dumps({"baseUrl": "http://localhost:3000", "mayManageServer": True}))
    detection.write_text(json.dumps({"source": "package.json", "script": "dev"}))

    proc = subprocess.run(
        [
            sys.executable,
            "plugins/superheroes/lib/test_pilot_server_config_cli.py",
            "resolve",
            "--profile-json",
            str(profile),
            "--detection-json",
            str(detection),
            "--work-item",
            "issue-90",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = json.loads(proc.stdout)
    assert result["verdict"] == "managed"
    assert result["command"] == ["npm", "run", "dev"]


def test_cli_launch_and_finish_expose_lifecycle_helper_json(tmp_path, monkeypatch, capsys):
    context = tmp_path / "context.json"
    outcome = tmp_path / "outcome.json"
    context.write_text(json.dumps({
        "verdict": "managed",
        "workItem": "issue-90",
        "baseUrl": "http://localhost:3000",
        "readinessUrl": "http://localhost:3000/",
        "port": 3000,
        "command": ["npm", "run", "dev"],
        "shell": False,
    }))
    outcome.write_text(json.dumps({"source": "browser", "steps": [{"id": "s1", "status": "passed"}]}))

    monkeypatch.setattr(cfg.devserver, "start", lambda *a, **k: {
        "pid": 123,
        "port": 3000,
        "command": ["npm", "run", "dev"],
        "_proc": object(),
    })
    monkeypatch.setattr(cfg.devserver, "poll_healthy", lambda *a, **k: True)
    torn_down = []
    monkeypatch.setattr(cfg.devserver, "teardown", torn_down.append)

    assert cli.main([
        "test_pilot_server_config_cli.py",
        "launch",
        "--context-json",
        str(context),
    ]) == 0
    launched = json.loads(capsys.readouterr().out)
    launched_path = tmp_path / "launched.json"
    launched_path.write_text(json.dumps(launched))

    assert cli.main([
        "test_pilot_server_config_cli.py",
        "finish",
        "--context-json",
        str(launched_path),
        "--outcome-json",
        str(outcome),
    ]) == 0
    finished = json.loads(capsys.readouterr().out)

    assert launched["handle"]["pid"] == 123
    assert "_proc" not in launched["handle"]
    assert finished["source"] == "browser"
    assert torn_down == [{"pid": 123, "port": 3000, "command": ["npm", "run", "dev"]}]


# --- #451: per-worktree PORT seam --------------------------------------------
# The launch cwd's .env.local PORT is what the dev server ACTUALLY binds (e.g.
# weekly-eats' scripts/dev-server.js reads .env.local and ignores env PORT).
# It must win over the band default so the readiness probe follows the real
# bind instead of timing out on :3000 — and the resolved port is disclosed.


def _write_env_local(dir_path, body):
    (dir_path / ".env.local").write_text(body, encoding="utf-8")


def test_env_local_port_overrides_band_default(tmp_path):
    _write_env_local(tmp_path, "MONGODB_URI=mongodb://x\nPORT=3003\n")
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["verdict"] == "managed"
    assert result["port"] == 3003
    assert result["baseUrl"] == "http://localhost:3003"
    assert result["readinessUrl"] == "http://localhost:3003/"
    assert result["portSource"] == "%s/.env.local" % tmp_path
    assert result["portDisclosure"] == "probing :3003 per %s/.env.local" % tmp_path
    # The launch cwd is embedded so the launcher runs the server in the worktree.
    assert result["cwd"] == str(tmp_path)


def test_env_local_absent_keeps_band_default(tmp_path):
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["port"] == 3000
    assert result["baseUrl"] == "http://localhost:3000"
    assert result["portSource"] == "profile.baseUrl"
    assert "3000" in result["portDisclosure"]


def test_env_local_no_cwd_is_backwards_compatible():
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
    )

    assert result["port"] == 3000
    assert "cwd" not in result


@pytest.mark.parametrize("body", ["PORT=not-a-port\n", "PORT=\n", "PORT=99999\n", "PORT=0\n", "# PORT=3003\n"])
def test_env_local_invalid_port_falls_back_to_band(tmp_path, body):
    _write_env_local(tmp_path, body)
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["port"] == 3000
    assert result["portSource"] == "profile.baseUrl"


def test_env_local_port_tolerates_inline_comment(tmp_path):
    _write_env_local(tmp_path, "PORT=3003 # per-worktree port, minted by postinstall\n")
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["port"] == 3003


def test_env_local_non_utf8_falls_back_without_raising(tmp_path):
    # Honor _env_local_port's never-raises contract: a non-UTF-8 .env.local must not
    # crash the run (UnicodeDecodeError is a ValueError, not an OSError).
    (tmp_path / ".env.local").write_bytes(b"PORT=3003\n\xff\xfe not utf-8\n")
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["port"] == 3000
    assert result["portSource"] == "profile.baseUrl"


def test_env_local_last_assignment_wins_and_honors_export(tmp_path):
    _write_env_local(tmp_path, "export PORT=3005\nPORT=3007\n")
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["port"] == 3007


def test_env_local_port_rewrites_explicit_readiness_url(tmp_path):
    _write_env_local(tmp_path, "PORT=3003\n")
    result = cfg.resolve(
        {
            "baseUrl": "http://localhost:3000",
            "readinessUrl": "http://localhost:3000/api/health",
            "devCommand": ["npm", "run", "dev"],
            "mayManageServer": True,
        },
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["readinessUrl"] == "http://localhost:3003/api/health"
    assert result["baseUrl"] == "http://localhost:3003"


def test_env_local_port_discloses_on_ready_external(tmp_path):
    _write_env_local(tmp_path, "PORT=3003\n")
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "mayManageServer": False},
        {"ready": True},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["verdict"] == "ready_external"
    assert result["port"] == 3003
    assert result["baseUrl"] == "http://localhost:3003"
    assert result["portDisclosure"] == "probing :3003 per %s/.env.local" % tmp_path


def test_env_local_matching_band_port_still_discloses_source(tmp_path):
    _write_env_local(tmp_path, "PORT=3000\n")
    result = cfg.resolve(
        {"baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True},
        {},
        "issue-451",
        cwd=str(tmp_path),
    )

    assert result["port"] == 3000
    assert result["portSource"] == "%s/.env.local" % tmp_path


def test_cli_resolve_honors_worktree_env_local(tmp_path):
    profile = tmp_path / "profile.json"
    detection = tmp_path / "detection.json"
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_env_local(worktree, "PORT=3003\n")
    profile.write_text(json.dumps({
        "baseUrl": "http://localhost:3000", "devCommand": ["npm", "run", "dev"], "mayManageServer": True,
    }))
    detection.write_text(json.dumps({}))

    proc = subprocess.run(
        [
            sys.executable,
            "plugins/superheroes/lib/test_pilot_server_config_cli.py",
            "resolve",
            "--profile-json", str(profile),
            "--detection-json", str(detection),
            "--work-item", "issue-451",
            "--worktree", str(worktree),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = json.loads(proc.stdout)
    assert result["verdict"] == "managed"
    assert result["port"] == 3003
    assert result["baseUrl"] == "http://localhost:3003"
    assert result["cwd"] == str(worktree)


def test_cli_launch_runs_server_in_context_cwd(tmp_path, monkeypatch, capsys):
    context = tmp_path / "context.json"
    context.write_text(json.dumps({
        "verdict": "managed",
        "workItem": "issue-451",
        "baseUrl": "http://localhost:3003",
        "readinessUrl": "http://localhost:3003/",
        "port": 3003,
        "cwd": str(tmp_path),
        "command": ["npm", "run", "dev"],
        "shell": False,
    }))

    seen = {}

    def fake_start(command, port, cwd=None, env=None, shell=None):
        seen["cwd"] = cwd
        seen["port"] = port
        return {"pid": 123, "port": port, "command": command, "_proc": object()}

    monkeypatch.setattr(cfg.devserver, "start", fake_start)
    monkeypatch.setattr(cfg.devserver, "poll_healthy", lambda *a, **k: True)
    monkeypatch.setattr(cfg.devserver, "teardown", lambda *a, **k: None)

    assert cli.main([
        "test_pilot_server_config_cli.py",
        "launch",
        "--context-json",
        str(context),
    ]) == 0
    launched = json.loads(capsys.readouterr().out)

    assert launched["handle"]["pid"] == 123
    assert seen == {"cwd": str(tmp_path), "port": 3003}
