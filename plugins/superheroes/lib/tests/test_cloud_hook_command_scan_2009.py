"""Existing hook commands in the settings are read as shell commands (a reference passes, a
literal is refused); shell `-c` scripts and `NAME+=value` are scanned like any command."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from test_cloud_dependency_hook_2009 import _world, mode_registry  # noqa: E402
import cloud_dependency_hook as hook  # noqa: E402
import cloud_setup_text  # noqa: E402

LITERAL = "fixture_private_key_123"
SCAN = cloud_setup_text._CredentialAssignment().search
REFERENCE_HOOKS = [
    "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY npm ci",
    "printf 'AWS_SECRET_ACCESS_KEY=%s\\n' \"$AWS_SECRET_ACCESS_KEY\" > .env",
]


def _existing(world, command):
    world.settings.parent.mkdir(parents=True, exist_ok=True)
    world.settings.write_text(json.dumps(
        {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}))


@pytest.mark.parametrize("command", REFERENCE_HOOKS)
def test_existing_reference_hook_allows_enable_and_removal(tmp_path, command):
    world = _world(tmp_path, mode_registry.GLOBAL)
    _existing(world, command)
    assert hook.sync(str(world.repo), ["npm ci"], [], True)["action"] == "written"
    assert hook._hook_commands(json.loads(world.settings.read_text())).count(command) == 1
    assert hook.sync(str(world.repo), ["npm ci"], [], False)["action"] == "removed"
    assert world.settings.exists()


def test_existing_literal_hook_is_refused(tmp_path):
    world = _world(tmp_path, mode_registry.GLOBAL)
    _existing(world, "AWS_SECRET_ACCESS_KEY=%s npm ci" % LITERAL)
    result = hook.sync(str(world.repo), ["npm ci"], [], True)
    assert result == {"action": "refused", "reason": "settings-secret-shaped", "changed": []}
    assert not world.script.exists()


@pytest.mark.parametrize("script", [
    "bash -c 'AWS_SECRET_ACCESS_KEY=%s npm ci'" % LITERAL,
    'sh -c "AWS_SECRET_ACCESS_KEY=%s npm ci"' % LITERAL,
    "env /bin/bash -ec 'AWS_SECRET_ACCESS_KEY=%s npm ci'" % LITERAL,
    "zsh -lc \"true; export AWS_SECRET_ACCESS_KEY=%s\"" % LITERAL,
    "bash -c \"sh -c 'AWS_SECRET_ACCESS_KEY=%s npm ci'\"" % LITERAL,
    "AWS_SECRET_ACCESS_KEY+=%s npm ci" % LITERAL,
])
def test_shell_c_script_and_append_literals_are_refused(script):
    assert SCAN(script)


@pytest.mark.parametrize("script", [
    "bash -c 'AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY npm ci'",
    'sh -c "AWS_SECRET_ACCESS_KEY=\\$AWS_SECRET_ACCESS_KEY npm ci"',
    "bash -c 'npm ci'",
    "bash script.sh",
])
def test_shell_c_script_references_are_accepted(script):
    assert not SCAN(script)
