"""Credentials: quoted references must not hide concatenated literal tokens."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import _compose, _inside, _outside, _store_commands


@pytest.mark.parametrize("make_world", [_inside, _outside], ids=["inside", "outside"])
def test_literal_after_quoted_reference_is_refused(tmp_path, make_world):
    # axis: only a whole bare environment reference may bypass literal credential refusal.
    credential = "a1B2" * 10
    command = 'npm config set //registry.example.com/:_authToken="$NPM_TOKEN"' + credential
    world = make_world(tmp_path)
    _store_commands(world, [command])
    result = _compose(world)
    assert result["action"] == "refused", result
    assert "text" not in result
    assert credential not in json.dumps(result)
