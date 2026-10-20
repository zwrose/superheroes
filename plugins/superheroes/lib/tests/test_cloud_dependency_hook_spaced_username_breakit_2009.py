"""Credentials in quoted URLs must not enter committed dependency hooks."""
import json
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_username_whitespace_cannot_hide_a_literal_url_password(tmp_path):
    # axis: whitespace in a quoted URL username must not hide its literal password.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture-private-password-1234567890"
    url = "https://build service:" + password + "@packages.example.invalid/simple"
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
    assert password not in json.dumps(result)
