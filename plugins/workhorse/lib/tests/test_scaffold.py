import json
import os

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_manifest_is_valid_and_named_workhorse():
    with open(os.path.join(_PLUGIN, ".claude-plugin", "plugin.json")) as fh:
        m = json.load(fh)
    assert m["name"] == "workhorse"
    assert m["version"] == "0.2.0"
    assert m["description"] and isinstance(m["description"], str)
    assert m["author"]["name"] == "zwrose"
