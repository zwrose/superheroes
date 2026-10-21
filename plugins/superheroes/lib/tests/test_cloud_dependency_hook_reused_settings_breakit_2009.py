"""Credentials: retrying an interrupted enable still checks commit-bound settings."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, CS, PC, hook, mode_registry,
    _raw, _set_ok, _world,
)


def test_retry_checks_credentials_when_the_hook_entry_already_matches(tmp_path):
    # axis: reusing an existing registration must not bypass the settings credential refusal.
    world = _world(tmp_path, mode_registry.GLOBAL)
    _set_ok(world, COMMANDS_SLUG, ["npm ci"])

    # Model interruption after the files were synced but before item 19 was stored.
    installed = hook.sync(world.cwd, ["npm ci"], [], True)
    assert installed["action"] == "written", installed
    assert _raw(world, HOOK_SLUG) is None

    secret = "sk-" + "a1B2c3D4" * 5
    assert CS._scan(secret) == "provider key"
    settings = json.loads(world.settings.read_text())
    settings["env"] = {"OPENAI_API_KEY": secret}
    world.settings.write_text(json.dumps(settings))
    before = world.settings.read_bytes()

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)

    assert result["action"] == "refused", result
    assert result["reason"] == "dependency-hook-unwritable"
    assert result["detail"] == "settings-secret-shaped"
    assert _raw(world, HOOK_SLUG) is None
    assert world.settings.read_bytes() == before
    assert secret not in json.dumps(result)
