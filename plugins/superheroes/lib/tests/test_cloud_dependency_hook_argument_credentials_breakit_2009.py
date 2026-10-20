"""Credentials: a literal credential word in a command argument must not enter committed hooks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)

LITERAL = "echo 'AWS_SECRET_ACCESS_KEY=opaque-owner-credential-123456' > .env"
ACCEPTED = (
    "printf 'AWS_SECRET_ACCESS_KEY=%s\\n' \"$KEY\" > .env",
    "echo \"OPENAI_API_KEY='$BUILD_OPENAI_KEY'\" > .env",
)


def test_literal_echo_credential_is_refused_before_hook_creation(tmp_path):
    world = _world(tmp_path, mode_registry.GLOBAL)
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [LITERAL], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    assert "opaque-owner-credential" not in repr(result)


def test_stored_command_validator_refuses_literal_echo_and_keeps_references():
    assert PC._validate_command_list([LITERAL]) is not None
    for command in ACCEPTED:
        assert PC._validate_command_list([command]) is None, command
