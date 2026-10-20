"""Credentials: quoted URL passphrases must not enter committed hooks."""
import json
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_url_passphrase_is_refused_before_hook_creation(tmp_path):
    # axis: whitespace in a literal URL password cannot bypass hook credential refusal.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture private index passphrase 123456"
    url = "https://builder:" + password + "@packages.example.invalid/simple"
    command = "pip install --index-url " + shlex.quote(url) + " demo"
    assert urlsplit(shlex.split(command)[3]).password == password
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or password not in world.script.read_text(), (
        "Enabling the hook copied a literal URL passphrase into repository files"
    )
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert password not in json.dumps(result)
