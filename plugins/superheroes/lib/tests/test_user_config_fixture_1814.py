"""The mod tests' userConfig fixture equals the manifest's userConfig (#1814)."""

import json
import os

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_the_mod_tests_user_config_fixture_equals_the_manifest_user_config():
    with open(os.path.join(_PLUGIN_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        manifest = json.load(f)["userConfig"]
    with open(os.path.join(_PLUGIN_ROOT, "hooks", "mod", "user-config.fixture.ts"), encoding="utf-8") as f:
        fixture = f.read().split("export const USER_CONFIG = ", 1)[1]

    assert json.loads(fixture) == manifest
