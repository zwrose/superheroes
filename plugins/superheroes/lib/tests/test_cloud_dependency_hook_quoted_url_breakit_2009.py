"""Credentials: quoting a URL password must not permit committing it."""
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_quoted_url_password_is_refused_before_hook_creation(tmp_path):
    # axis: a shell-quoted literal URL password cannot migrate into a committed hook.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture-password-1234567890"
    command = (
        'pip install --index-url https://builder:"' + password
        + '"@packages.example.invalid/simple demo'
    )
    assert shlex.split(command)[3] == (
        "https://builder:" + password + "@packages.example.invalid/simple"
    )
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or password not in world.script.read_text(), (
        "Enabling the hook copied a quoted URL password into repository files"
    )
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert password not in json.dumps(result)
