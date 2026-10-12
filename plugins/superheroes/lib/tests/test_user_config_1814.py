"""The manifest's userConfig has the shape the mod's settingsFrom reads and the owner's ruled defaults (#1814)."""

import json
import os

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _user_config():
    with open(os.path.join(_PLUGIN_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        return json.load(f)["userConfig"]


def test_the_manifest_user_config_has_the_shape_the_mod_reads():
    config = _user_config()

    for key in ("autoCheckpointTokens", "autoCheckpointAllowance"):
        spec = config[key]
        assert all(isinstance(spec[field], (int, float)) for field in ("default", "min", "max"))
        assert spec["min"] <= spec["default"] <= spec["max"]
    mode = config["autoCheckpointMode"]
    assert mode["default"] in mode["options"]


def test_the_manifest_user_config_carries_the_owners_ruled_defaults():
    config = _user_config()
    tokens, allowance, mode = (
        config["autoCheckpointTokens"],
        config["autoCheckpointAllowance"],
        config["autoCheckpointMode"],
    )

    assert tokens["default"] == 500000
    assert mode["default"] == "auto"
    assert mode["options"] == ["auto", "click-only", "off"]
    assert allowance["default"] < tokens["default"]
