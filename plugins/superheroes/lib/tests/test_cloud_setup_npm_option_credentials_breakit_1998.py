"""Credentials: npm options must not hide literal registry basic authentication."""
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
def test_npm_option_value_does_not_hide_literal_registry_auth(tmp_path, make_world):
    # axis: an npm option with a value must not bypass literal registry credential refusal.
    credential = base64.b64encode(("owner:" + "a1B2" * 10).encode()).decode("ascii")
    command = "npm config set --location=project //registry.example.com/:_auth " + credential
    world = make_world(tmp_path)
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused", result
    assert "text" not in result
    assert credential not in json.dumps(result)
