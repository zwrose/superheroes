"""Command-entry credential rule: option tokens, enclosing quotes and URL userinfo passwords."""
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
    "npm config set --location=project //registry.example.com/:_auth %s" % LITERAL,
    "npm config set --location=project -g %s %s" % (KEY, LITERAL),
    "npm config set -g %s=%s" % (KEY, LITERAL),
    'echo "%s=%s" >> .npmrc' % (KEY, LITERAL),
    "echo '%s=%s' >> .npmrc" % (KEY, LITERAL),
    "pip install --index-url https://owner:%s@packages.example/simple -r requirements.txt" % LITERAL,
    'pip install --index-url "https://owner:%s@packages.example/simple"' % LITERAL,
    "pip install --index-url https://$USER:%s@packages.example/simple" % LITERAL,
]
PASSING = [
    "npm config set --location=project //registry.example.com/:_auth $REGISTRY_AUTH",
    'npm config set --location=project %s "$NPM_TOKEN"' % KEY,
    'echo "%s=$NPM_TOKEN" >> .npmrc' % KEY,
    'echo "%s=${NPM_TOKEN}" >> .npmrc' % KEY,
    "pip install --index-url https://owner@packages.example/simple",
    "pip install --index-url https://$USER:$PASS@packages.example/simple",
    "pip install --index-url https://${USER}:${PASS}@packages.example/simple",
    "git clone ssh://git@github.com/org/repo.git",
]
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", LITERALS)
def test_literal_forms_are_refused_by_set_and_compose(tmp_path, make, command):
    assert cloud_setup_text._command_credential(command)
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert LITERAL not in json.dumps(result)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", PASSING)
def test_reference_forms_pass_set_and_compose(tmp_path, make, command):
    assert not cloud_setup_text._command_credential(command)
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "written", result
