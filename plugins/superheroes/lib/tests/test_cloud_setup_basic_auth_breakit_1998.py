"""Credentials: literal registry basic authentication must not enter setup text."""
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
@pytest.mark.parametrize("tool", ["npm", "yarn"])
def test_literal_registry_basic_auth_is_refused(tmp_path, make_world, tool):
    # axis: literal registry basic authentication is refused before setup text is returned.
    identity = "owner:" + "a1B2" * 10
    if tool == "npm":
        credential = base64.b64encode(identity.encode("utf-8")).decode("ascii")
        command = "npm config set //registry.example.com/:_auth=" + credential
    else:
        credential = identity
        command = "yarn config set npmAuthIdent " + credential
    world = make_world(tmp_path)
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused", result
    assert "text" not in result
    assert credential not in json.dumps(result)
