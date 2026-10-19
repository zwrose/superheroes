"""The command-entry credential rule: a credential-named key never takes a literal value."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import (  # noqa: E402
    SLUG, _compose, _inside, _outside, _store_commands)

import cloud_setup_text  # noqa: E402
import project_config  # noqa: E402

LITERAL = "glpat-" + "t" * 20
KEY = "//registry.example.com/:_authToken"
LITERALS = [
    "export NPM_TOKEN=%s; npm config set %s=\"$NPM_TOKEN\"" % (LITERAL, KEY),
    "NODE_AUTH_TOKEN=%s npm ci" % LITERAL,
    "export YARN_NPM_AUTH_TOKEN=%s" % LITERAL,
    "NPM_TOKEN='%s' npm ci" % LITERAL,
    'NPM_TOKEN="%s" npm ci' % LITERAL,
    "NPM_TOKEN=\"\"%s npm ci" % LITERAL,
    "npm config set //registry.example.com/:_auth=%s" % LITERAL,
    "npm config set //registry.example.com/:_auth '%s'" % LITERAL,
    "npm config set --json //registry.example.com/:_auth '\"%s\"'" % LITERAL,
    "yarn config set npmAuthIdent %s" % LITERAL,
    "yarn config set npmAuthToken %s" % LITERAL,
    "npm set _password %s" % LITERAL,
    "npm config set _password=%s" % LITERAL,
    "echo 'npmAuthIdent: %s' >> .yarnrc.yml" % LITERAL,
    "export NPM_TOKEN=$OTHER; NODE_AUTH_TOKEN=%s npm ci" % LITERAL,
]
REFERENCES = [
    "export NPM_TOKEN=$NPM_TOKEN",
    "NODE_AUTH_TOKEN=${NODE_AUTH_TOKEN} npm ci",
    'NODE_AUTH_TOKEN="$NODE_AUTH_TOKEN" npm ci',
    "NODE_AUTH_TOKEN='${NODE_AUTH_TOKEN}' npm ci",
    "npm config set //registry.example.com/:_auth=$REGISTRY_AUTH",
    "npm config set //registry.example.com/:_auth \"$REGISTRY_AUTH\"",
    "yarn config set npmAuthIdent '$YARN_IDENT'",
    "yarn config set npmAuthToken ${YARN_TOKEN}",
    "npm ci",
    "make build",
    "pip install -r requirements.txt",
]
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", LITERALS)
def test_a_literal_credential_value_is_refused_by_set_and_compose(tmp_path, make, command):
    assert cloud_setup_text._command_credential(command)
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert result["reason"] in ("secret-shaped-content", "setup-commands-malformed")
    assert LITERAL not in json.dumps(result)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", REFERENCES)
def test_a_bare_reference_or_plain_command_passes_set_and_compose(tmp_path, make, command):
    assert not cloud_setup_text._command_credential(command)
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "written", result
