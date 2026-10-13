"""The manifest's userConfig has the shape the mod's settingsFrom reads (#1814)."""

import json
import os

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_the_manifest_user_config_has_the_shape_the_mod_reads():
    with open(os.path.join(_PLUGIN_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        config = json.load(f)["userConfig"]

    for key in ("autoCheckpointTokens", "autoCheckpointAllowance"):
        spec = config[key]
        assert all(isinstance(spec[field], (int, float)) for field in ("default", "min", "max"))
        assert spec["min"] <= spec["default"] <= spec["max"]
    mode = config["autoCheckpointMode"]
    assert mode["default"] in mode["options"]
