"""Existing hook commands in the settings are read by the shared whole-text scan: a reference
passes, a literal credential refuses `settings-secret-shaped`."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from test_cloud_dependency_hook_2009 import _world, mode_registry  # noqa: E402
import cloud_dependency_hook as hook  # noqa: E402
import cloud_setup_text  # noqa: E402

LITERAL = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
SCAN = cloud_setup_text._scan
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
    groups = json.loads(world.settings.read_text())["hooks"]["PreToolUse"]
    assert [h["command"] for g in groups for h in g["hooks"]].count(command) == 1
    assert hook.sync(str(world.repo), ["npm ci"], [], False)["action"] == "removed"
    assert world.settings.exists()


def test_existing_literal_hook_is_refused(tmp_path):
    world = _world(tmp_path, mode_registry.GLOBAL)
    _existing(world, "OPENAI_API_KEY=%s npm ci" % LITERAL)
    result = hook.sync(str(world.repo), ["npm ci"], [], True)
    assert result == {"action": "refused", "reason": "settings-secret-shaped", "changed": []}
    assert not world.script.exists()


@pytest.mark.parametrize("script", [
    "bash -c 'AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY npm ci'",
    'sh -c "AWS_SECRET_ACCESS_KEY=\\$AWS_SECRET_ACCESS_KEY npm ci"',
    "bash -c 'npm ci'",
    "bash script.sh",
])
def test_shell_c_script_references_are_accepted(script):
    assert not SCAN(script)
