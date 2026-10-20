"""Credentials: compound commands must not hide literal credential assignments."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


@pytest.mark.parametrize("separator", ["&&", ";"])
def test_compound_assignment_is_refused_before_hook_creation(tmp_path, separator):
    # axis: shell separators cannot hide a literal credential from hook creation.
    world = _world(tmp_path, mode_registry.GLOBAL)
    credential = "fixture_private_key_123"
    command = "true" + separator + "AWS_SECRET_ACCESS_KEY=" + credential + " npm ci"
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    assert not world.settings.exists()
    assert credential not in json.dumps(result)
