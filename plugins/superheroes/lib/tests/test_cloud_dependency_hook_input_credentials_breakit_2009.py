"""Credentials in private setup inputs must not enter committed hook files."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, INPUTS_SLUG, PC, _compose, _raw,
    _set_ok, _world, mode_registry,
)


def test_input_name_cannot_copy_a_credential_into_the_hook(tmp_path):
    # axis: enabling the hook must not commit a credential accepted as a plain input path.
    world = _world(tmp_path, mode_registry.GLOBAL)
    credential = "npm_" + "a1B2c3D4" * 5
    _set_ok(world, COMMANDS_SLUG, ["npm ci"])
    _set_ok(world, INPUTS_SLUG, ["locks/" + credential + ".lock"])

    before = _compose(world)
    assert before["action"] == "refused", before
    assert "text" not in before
    assert credential not in json.dumps(before)

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or credential not in world.script.read_text(), (
        "Enabling the hook copied a private credential into a commit-bound script"
    )
    assert result["action"] == "refused", result
    assert _raw(world, HOOK_SLUG) is None
    assert credential not in json.dumps(result)
