"""Credentials: wrapped URL passphrases must not enter commit-bound hook files."""
import json
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


@pytest.mark.parametrize("carrier", ["attached-option", "settings-hook"])
def test_wrapped_url_passphrase_is_refused_before_hook_writes(tmp_path, carrier):
    # axis: option prefixes and JSON serialization cannot hide literal URL passphrases.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture private index passphrase 123456"
    url = "https://builder:" + password + "@packages.example.invalid/simple"
    before = None
    if carrier == "attached-option":
        command = "pip install --index-url=" + shlex.quote(url) + " demo"
        assert shlex.split(command)[2] == "--index-url=" + url
        commands = [command]
        expected = {"action": "refused", "reason": "setup-command-secret-shaped"}
    else:
        command = "pip install --index-url " + shlex.quote(url) + " demo"
        assert shlex.split(command)[3] == url
        commands = ["true"]
        settings = {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": command}
        ]}]}}
        world.settings.parent.mkdir(parents=True, exist_ok=True)
        world.settings.write_text(json.dumps(settings, indent=2) + "\n")
        before = world.settings.read_text()
        expected = {"action": "refused", "reason": "dependency-hook-unwritable",
                    "detail": "settings-secret-shaped"}

    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, commands, root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored
    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert result == expected, result
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    if before is None:
        assert not world.settings.exists()
    else:
        assert world.settings.read_text() == before
    assert password not in json.dumps(result)
