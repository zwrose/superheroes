"""Credential-named assignments inside a JSON-serialized command keep their word boundaries: a
bare environment reference is never read as a literal credential."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cloud_setup_text  # noqa: E402

SCAN = cloud_setup_text._scan


def _as_json(command):
    return json.dumps({"hooks": [{"command": command}]})


@pytest.mark.parametrize("command", [
    "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY npm ci",
    "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} npm ci",
    'AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" npm ci',
])
def test_reference_in_json_command_is_accepted(command):
    assert not SCAN(command)
    assert not SCAN(_as_json(command))


@pytest.mark.parametrize("command", [
    "X_TOKEN=$TOKEN; npm ci",
    "X_TOKEN=$TOKEN;",
    "true&&X_TOKEN=$TOKEN npm ci",
    "KEY_TOKEN=$KEY&& npm ci",
])
def test_reference_beside_separator_is_accepted(command):
    assert not SCAN(command)


PRINTF_COMMANDS = [
    "printf 'AWS_SECRET_ACCESS_KEY=%s\\n' \"$AWS_SECRET_ACCESS_KEY\" > .env",
    "echo \"OPENAI_API_KEY='$BUILD_OPENAI_KEY'\" > .env",
]


@pytest.mark.parametrize("command", PRINTF_COMMANDS)
def test_credential_word_as_a_command_argument_is_accepted(command):
    # axis: only assignment position is checked; a printf format or echo argument is data
    assert not SCAN(command)
    assert not SCAN(_as_json(command))


@pytest.mark.parametrize("command", PRINTF_COMMANDS)
def test_credential_free_printf_command_is_stored_and_composed(tmp_path, command):
    import project_config
    from test_cloud_setup_text import SLUG, _compose, _inside, _store_commands
    w = _inside(tmp_path)
    _store_commands(w, [])
    assert project_config.set_item(w.cwd, SLUG, [command], root=w.root)["action"] != "refused"
    _store_commands(w, [command])
    assert _compose(w)["action"] == "written"
