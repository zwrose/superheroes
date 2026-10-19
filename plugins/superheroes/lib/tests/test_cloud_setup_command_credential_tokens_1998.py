"""The command-entry credential rule tokenizes keys into name components and values into whole
shell words, through set and compose in both storage modes."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import (  # noqa: E402
    SLUG, _compose, _inside, _outside, _store_commands)

import cloud_setup_text  # noqa: E402
import project_config  # noqa: E402

PASSWORD = "a1B2c3D4e5F6g7H8i9J0"
REFUSED = [
    # quoted nested Yarn key naming npmAuthIdent
    "yarn config set 'npmRegistries[\"//registry.example.com\"].npmAuthIdent' 'owner:%s'" % PASSWORD,
    "yarn config set npmAuthIdent 'owner:%s'" % PASSWORD,
    # a literal glued to a quoted reference
    'npm config set //registry.example.com/:_authToken="$NPM_TOKEN"' + PASSWORD,
    'yarn config set npmAuthIdent "${NPM_USER}":' + PASSWORD,
    'NPM_TOKEN="$NPM_TOKEN"' + PASSWORD + " npm ci",
    "NPM_TOKEN=$X-" + PASSWORD + " npm ci",
    "NPM_TOKEN=$X-literal npm ci",
    'NPM_TOKEN="${NPM_USER}":password npm ci',
    "npmAuthToken=" + PASSWORD,
    "export apiKey=" + PASSWORD,
    "export API_KEY=" + PASSWORD,
    # the URL-userinfo password and a query-string credential still refuse
    "pip install --extra-index-url https://auth:%s@auth.example.com:443/simple" % PASSWORD,
    "curl https://auth.example.com/x?token=" + PASSWORD,
]
PASSING = [
    "pip install tokenizers==0.20.3",
    'pip install "requests-oauthlib>=2"',
    "pip install requests-oauthlib==2.0.0",
    "pip install 'tokenizers<=0.21' 'authlib~=1.3' 'secretstorage!=3.0'",
    "GIT_AUTHOR_NAME=bot git commit -m x",
    "export AUTHORIZE=yes",
    'NPM_TOKEN="$NPM_TOKEN" npm ci',
    "NPM_TOKEN='${NPM_TOKEN}' npm ci",
    'NPM_TOKEN=\\"$NPM_TOKEN\\" npm ci',
    "yarn config set 'npmRegistries[\"//registry.example.com\"].npmAuthIdent' \"$NPM_IDENT\"",
    # a credential word in a URL host or path, or in an image reference, is no credential key
    "pip install --extra-index-url https://auth.example.com:443/simple -r requirements.txt",
    "docker pull ghcr.io/acme/auth-service:latest",
    "git clone https://auth.example.org:443/acme/project.git",
]
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", REFUSED)
def test_a_literal_credential_is_refused_by_set_and_compose(tmp_path, make, command):
    assert cloud_setup_text._command_credential(command)
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert PASSWORD not in json.dumps(result)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", PASSING)
def test_a_pinned_package_or_whole_reference_passes_set_and_compose(tmp_path, make, command):
    assert not cloud_setup_text._command_credential(command)
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    assert _compose(w)["action"] == "written"


@pytest.mark.parametrize("key,named", [
    ("npmAuthToken", True), ("npmAuthIdent", True), ("_auth", True), ("NPM_TOKEN", True),
    ("NODE_AUTH_TOKEN", True), ("//host/:_authToken", True), ("apiKey", True), ("API_KEY", True),
    ("'npmRegistries[\"//host\"].npmAuthIdent'", True),
    ("tokenizers", False), ("requests-oauthlib", False), ("GIT_AUTHOR_NAME", False),
    ("authorize", False), ("api", False)])
def test_a_key_is_credential_named_by_its_components(key, named):
    assert cloud_setup_text._credential_named(key) is named
