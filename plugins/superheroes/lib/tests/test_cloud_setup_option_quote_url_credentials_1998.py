"""Reference forms and URL userinfo that the shared scan must not over-refuse, through set and compose."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import (  # noqa: E402
    SLUG, _compose, _inside, _outside, _store_commands)

import cloud_setup_text  # noqa: E402
import project_config  # noqa: E402

KEY = "//registry.example.com/:_authToken"
PASSING = [
    "npm config set --location=project //registry.example.com/:_auth $REGISTRY_AUTH",
    'npm config set --location=project %s "$NPM_TOKEN"' % KEY,
    'echo "%s=$NPM_TOKEN" >> .npmrc' % KEY,
    'echo "%s=${NPM_TOKEN}" >> .npmrc' % KEY,
    "pip install --index-url https://owner@packages.example/simple",
    "pip install --index-url https://$USER:$PASS@packages.example/simple",
    "pip install --index-url https://${USER}:${PASS}@packages.example/simple",
    "git clone ssh://git@github.com/org/repo.git",
    "export OPENAI_API_KEY=$BUILD_OPENAI_KEY&& npm run build",
    "OPENAI_API_KEY=$BUILD_OPENAI_KEY|| npm run build",
]
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", PASSING)
def test_reference_forms_pass_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "written", result


def test_a_literal_before_a_shell_operator_is_still_a_credential_assignment():
    # axis: a reference may end at & or |, but a literal value there is still flagged
    assert cloud_setup_text._scan("export OPENAI_API_KEY=abc123&& npm run build") \
        == "credential assignment"
