"""Refuse literal registry credentials supplied as separate command arguments."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
@pytest.mark.parametrize("quoted", [False, True], ids=["unquoted", "quoted"])
def test_space_separated_registry_credential_is_not_returned(tmp_path, make_world, quoted):
    # axis: literal _authToken values are refused even without '=' or a provider prefix.
    world = make_world(tmp_path)
    credential = "a1B2" * 10
    key = "//registry.example.com/:_authToken"
    if quoted:
        command = 'npm config set "{}" "{}"'.format(key, credential)
    else:
        command = "npm config set {} {}".format(key, credential)
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused"
    assert "text" not in result
    assert credential not in json.dumps(result)
