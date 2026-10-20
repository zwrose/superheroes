"""Enabling the hook refuses a settings file that already carries a credential."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry  # noqa: E402
import cloud_dependency_hook as hook  # noqa: E402


def test_a_credential_in_existing_settings_is_never_directed_to_commit(tmp_path):
    # axis: the rewritten settings file is scanned before either hook file is written.
    world = _world(tmp_path, mode_registry.GLOBAL)
    secret = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2"
    world.settings.parent.mkdir(parents=True, exist_ok=True)
    world.settings.write_text(json.dumps({"env": {"OPENAI_API_KEY": secret}}))
    before = world.settings.read_text()
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, ["npm ci"], root=world.root)
    assert stored["action"] in ("written", "noop"), stored

    result = hook.sync(str(world.repo), ["npm ci"], [], True)
    assert result == {"action": "refused", "reason": "settings-secret-shaped", "changed": []}
    assert not world.script.exists()
    assert world.settings.read_text() == before

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert result["action"] == "refused", result
    assert not world.script.exists()
    assert _raw(world, HOOK_SLUG) is None
    assert secret not in json.dumps(result)


def test_a_credential_in_settings_is_never_directed_to_commit_on_removal(tmp_path):
    # axis: removal rewrites the settings file too, so it is scanned like the enable write.
    world = _world(tmp_path, mode_registry.GLOBAL)
    assert hook.sync(str(world.repo), ["npm ci"], [], True)["action"] == "written"
    secret = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2"
    settings = json.loads(world.settings.read_text())
    settings["env"] = {"OPENAI_API_KEY": secret}
    world.settings.write_text(json.dumps(settings))
    before = world.settings.read_text()

    result = hook.sync(str(world.repo), ["npm ci"], [], False)
    assert result == {"action": "refused", "reason": "settings-secret-shaped", "changed": []}
    assert world.settings.read_text() == before
    assert world.script.exists()
    assert secret not in json.dumps(result)
