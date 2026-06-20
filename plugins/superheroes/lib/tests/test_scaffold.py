import json
import os
import re

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_manifest_is_valid_and_named_superheroes():
    with open(os.path.join(_PLUGIN, ".claude-plugin", "plugin.json")) as fh:
        m = json.load(fh)
    assert m["name"] == "superheroes"
    # Assert the version is well-formed SemVer, not a frozen literal — release-please
    # bumps this on every release, so pinning a specific value breaks releasability.
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"]), m["version"]
    assert m["description"] and isinstance(m["description"], str)
    assert m["author"]["name"] == "zwrose"
