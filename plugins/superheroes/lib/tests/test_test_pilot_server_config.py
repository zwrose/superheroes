import json
import subprocess
import sys

import pytest

import test_pilot_server_config as cfg


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
