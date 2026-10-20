"""Credentials: empty shell quotes must not hide a literal registry token."""
import json
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
@pytest.mark.parametrize("prefix", ["''", '""'], ids=["single-quotes", "double-quotes"])
def test_empty_quotes_do_not_hide_a_literal_registry_token(tmp_path, make_world, prefix):
    # axis: shell-concatenated literal registry credentials are refused before text is returned.
    credential = "a1B2" * 10
    key = "//registry.example.com/:_authToken"
    command = "npm config set " + key + "=" + prefix + credential
    assert shlex.split(command)[-1] == key + "=" + credential
    world = make_world(tmp_path)
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused", result
    assert result["reason"] in ("setup-commands-malformed", "secret-shaped-content")
    assert "text" not in result
    assert credential not in json.dumps(result)
