"""Stored credentials must not migrate from global calibration into a committed hook."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _compose, _raw, _world, core_md, mode_registry,
)


def test_enabling_hook_refuses_a_credential_in_existing_global_commands(tmp_path):
    # axis: enabling item 19 must not copy a stored literal credential into repository files.
    world = _world(tmp_path, mode_registry.GLOBAL)
    credential = "npm_" + "a1B2c3D4" * 5
    command = "npm config set //registry.npmjs.org/:_authToken=" + credential
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    # Model an owner-edited existing calibration; the setup-text path already refuses it.
    before = _compose(world)
    assert before["action"] == "refused", before
    assert before["reason"] == "setup-commands-malformed", before
    assert "text" not in before
    assert credential not in json.dumps(before)

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or credential not in world.script.read_text(), (
        "Enabling the hook copied a literal credential into a commit-bound script"
    )
    assert result["action"] == "refused", result
    assert _raw(world, HOOK_SLUG) is None
    assert credential not in json.dumps(result)
