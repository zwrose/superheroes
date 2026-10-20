"""Credential refusal through the new setup-command composition path."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
def test_registry_authentication_command_cannot_return_a_literal_token(tmp_path, make_world):
    # axis: a literal registry credential must be refused before setup text is returned.
    world = make_world(tmp_path)
    credential = "npm_" + "a1B2c3D4" * 4 + "a1B2"
    command = "npm config set //registry.npmjs.org/:_authToken=" + credential
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused"
    assert "text" not in result
    assert credential not in json.dumps(result)
