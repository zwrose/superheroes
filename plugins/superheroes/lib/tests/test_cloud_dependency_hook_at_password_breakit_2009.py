"""Credentials: an @ inside a literal URL password must not bypass hook refusal."""
import json
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_literal_password_containing_at_is_refused_before_hook_creation(tmp_path):
    # axis: the complete URL password, including an embedded @, must be checked before committing it.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "$fixture_private_password_123@tail"
    url = "https://builder:" + password + "@packages.example.invalid/simple"
    command = "pip install --index-url " + shlex.quote(url) + " demo"
    assert urlsplit(shlex.split(command)[3]).password == password
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or password not in world.script.read_text(), (
        "Enabling the hook copied a literal URL password into repository files"
    )
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    assert password not in json.dumps(result)
