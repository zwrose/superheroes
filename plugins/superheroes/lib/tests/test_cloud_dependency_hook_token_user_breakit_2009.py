"""Credentials: token usernames remain secret when the URL password is empty."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


def test_token_username_with_empty_password_never_enters_hook(tmp_path):
    # axis: enabling the hook refuses a literal HTTP token username despite an empty password.
    world = _world(tmp_path, mode_registry.GLOBAL)
    credential = "fixture-private-token-1234567890"
    command = (
        "git clone https://" + credential
        + ":@git.example.invalid/team/private.git"
    )
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, [command], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert not world.script.exists() or credential not in world.script.read_text(), (
        "Enabling the hook copied an HTTP token username into repository files"
    )
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert credential not in json.dumps(result)
