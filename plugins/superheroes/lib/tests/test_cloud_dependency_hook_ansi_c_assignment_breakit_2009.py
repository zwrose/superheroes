"""Credentials: ANSI-C quoted assignment values are literals, not references."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_ansi_c_assignment_is_refused_before_hook_creation(tmp_path):
    # axis: Bash literal quoting cannot turn an embedded credential into an allowed reference.
    world = _world(tmp_path, mode_registry.GLOBAL)
    credential = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd"
    word = "$'" + credential + "'"
    rendered = subprocess.run(
        ["bash", "-c", "printf %s " + word],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert rendered.stdout == credential
    command = "AWS_SECRET_ACCESS_KEY=" + word + " npm ci"
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
