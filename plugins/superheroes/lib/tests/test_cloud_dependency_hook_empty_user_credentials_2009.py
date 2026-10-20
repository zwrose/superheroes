"""Password-only URL credentials must stay out of committed dependency hooks."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_enabling_hook_refuses_a_password_only_url(tmp_path):
    # axis: an empty URL username must not bypass credential refusal during hook creation.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture-redis-password-1234567890"
    command = "redis-cli -u redis://:" + password + "@cache.example.invalid PING"
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or password not in world.script.read_text(), (
        "Enabling the hook copied a URL password into a commit-bound script"
    )
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert password not in json.dumps(result)
