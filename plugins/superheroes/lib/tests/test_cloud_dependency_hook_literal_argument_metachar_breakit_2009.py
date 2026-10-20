"""Credentials: punctuation in literal passwords must not permit committed hooks."""
import json
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


@pytest.mark.parametrize("password", [
    "fixture%private-password-123",
    "fixture$private-password-123",
])
def test_literal_echo_password_is_refused_before_hook_creation(tmp_path, password):
    # axis: literal dollar and percent characters do not make an echo argument credential-free.
    world = _world(tmp_path, mode_registry.GLOBAL)
    assignment = "DATABASE_PASSWORD=" + password
    command = "echo '" + assignment + "' > .env"
    assert shlex.split(command)[1] == assignment
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    assert not world.settings.exists()
    assert password not in json.dumps(result)
