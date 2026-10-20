"""Credentials: ANSI-C quoted URL passwords must not enter committed hooks."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_ansi_c_quoted_password_is_refused_before_hook_creation(tmp_path):
    # axis: a Bash literal must not be mistaken for an environment reference.
    world = _world(tmp_path, mode_registry.GLOBAL)
    password = "fixture_private_password_123"
    url_word = "https://builder:$'" + password + "'@packages.example.invalid/simple"
    rendered = subprocess.run(
        ["bash", "-c", "printf %s " + url_word],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert rendered.stdout == (
        "https://builder:" + password + "@packages.example.invalid/simple"
    )
    command = "pip install --index-url " + url_word + " demo"
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or password not in world.script.read_text(), (
        "A literal URL password was copied into the commit-bound hook"
    )
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    assert password not in json.dumps(result)
