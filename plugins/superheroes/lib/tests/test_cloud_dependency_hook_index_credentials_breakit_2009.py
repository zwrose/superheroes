"""Private package-index passwords must not migrate into committed hooks."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_index_password_never_reaches_committed_hook(tmp_path):
    # axis: enabling the hook refuses literal URL passwords before writing repository files.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture-index-password-1234567890"
    command = (
        "python -m pip install --index-url https://builder:"
        + password + "@packages.example.invalid/simple demo"
    )
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or password not in world.script.read_text(), (
        "Enabling the hook copied a private index password into a committed script"
    )
    assert result["action"] == "refused", result
    assert _raw(world, HOOK_SLUG) is None
    assert password not in json.dumps(result)
