"""Credential-named assignments inside a JSON-serialized command keep their word boundaries, and
a quoted literal (ANSI-C or single-quoted) is never read as an environment reference."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cloud_setup_text  # noqa: E402

LITERAL = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd"
SCAN = cloud_setup_text._CredentialAssignment().search


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
    "AWS_SECRET_ACCESS_KEY=%s npm ci" % LITERAL,
    "AWS_SECRET_ACCESS_KEY=$'%s' npm ci" % LITERAL,
    "AWS_SECRET_ACCESS_KEY='%s' npm ci" % LITERAL,
    "AWS_SECRET_ACCESS_KEY='$AWS_SECRET_ACCESS_KEY' npm ci",
    "AWS_SECRET_ACCESS_KEY=$'$AWS_SECRET_ACCESS_KEY' npm ci",
])
def test_literal_is_refused_bare_and_in_json_command(command):
    assert SCAN(command)
    assert SCAN(_as_json(command))
