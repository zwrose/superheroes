"""Credentials: dollar-prefixed literal tokens must not leave compose."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands  # noqa: E402


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
@pytest.mark.parametrize("form", ["ansi-c", "environment-default"])
def test_dollar_prefixed_literal_credential_is_refused(tmp_path, make_world, form):
    # axis: dollar-prefixed shell syntax must not disguise an embedded literal registry token.
    world = make_world(tmp_path)
    credential = "a1B2" * 10
    if form == "ansi-c":
        value = "$'" + credential + "'"
    else:
        value = '"${NPM_TOKEN:-' + credential + '}"'
    command = "npm config set //registry.example.com/:_authToken=" + value
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused", result
    assert "text" not in result
    assert credential not in json.dumps(result)
