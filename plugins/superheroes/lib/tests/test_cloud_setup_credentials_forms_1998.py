"""Registry-credential forms, pipefail and a malformed container, through set and compose."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import (  # noqa: E402
    CS, SLUG, _compose, _edit_core_block, _inside, _outside, _refusal, _store_commands)

import project_config  # noqa: E402

LITERAL = "glpat-" + "t" * 20
KEY = "//registry.example.com/:_authToken"
REFERENCES = [
    "npm config set %s=$NPM_TOKEN" % KEY,
    "npm config set %s=${NPM_TOKEN}" % KEY,
    'npm config set %s="$NPM_TOKEN"' % KEY,
    "npm config set %s='$NPM_TOKEN'" % KEY,
    'npm config set %s="${NPM_TOKEN}"' % KEY,
    "npm config set %s $NPM_TOKEN" % KEY,
    'npm config set %s "$NPM_TOKEN"' % KEY,
    "npm config set %s:$NPM_TOKEN" % KEY,
]
LITERALS = [
    "npm config set %s=%s" % (KEY, LITERAL),
    'npm config set %s="%s"' % (KEY, LITERAL),
    "npm config set %s='%s'" % (KEY, LITERAL),
    "npm config set %s %s" % (KEY, LITERAL),
    'npm config set %s "%s"' % (KEY, LITERAL),
    "npm config set %s '%s'" % (KEY, LITERAL),
    "npm config set %s:%s" % (KEY, LITERAL),
]
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", REFERENCES)
def test_an_environment_reference_passes_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "written", result


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", LITERALS)
def test_a_literal_value_is_refused_by_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert result["reason"] in ("secret-shaped-content", "setup-commands-malformed")
    assert LITERAL not in json.dumps(result)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
def test_commands_run_under_pipefail(tmp_path, make):
    w = make(tmp_path)
    _store_commands(w, ["curl -fsSL https://example.invalid/i | bash"])
    text = _compose(w)["text"]
    assert 'bash -o pipefail -c "$cmd"' in text
    assert 'bash -c "$cmd"' not in text


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
def test_a_non_object_configuration_container_is_refused(tmp_path, make):
    w = make(tmp_path)
    _store_commands(w, ["npm ci"])
    _edit_core_block(w, lambda obj: obj.__setitem__("projectConfiguration",
                                                    [{"cloudSetupCommands": ["npm ci"]}]))
    _refusal(_compose(w), "setup-commands-unreadable")


@pytest.mark.parametrize("command", REFERENCES)
def test_the_scan_passes_a_reference_in_its_stored_json_form(command):
    assert CS._scan(json.dumps({SLUG: [command]}, indent=2)) is None


@pytest.mark.parametrize("command", LITERALS)
def test_the_scan_flags_a_literal_in_its_stored_json_form(command):
    assert CS._scan(json.dumps({SLUG: [command]}, indent=2)) is not None


YARN_REFERENCES = [
    "yarn config set npmAuthToken $NPM_TOKEN",
    'yarn config set npmAuthToken "${NPM_TOKEN}"',
    "yarn config set -H npmScopes.acme.npmAuthToken $NPM_TOKEN",
    'yarn config set \'npmRegistries["//registry.example.com"].npmAuthToken\' "$NPM_TOKEN"',
]
YARN_LITERALS = [
    "yarn config set npmAuthToken " + LITERAL,
    'yarn config set npmAuthToken "%s"' % LITERAL,
    "yarn config set -H npmScopes.acme.npmAuthToken " + LITERAL,
    'yarn config set \'npmRegistries["//registry.example.com"].npmAuthToken\' "%s"' % LITERAL,
]


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", YARN_REFERENCES)
def test_a_yarn_environment_reference_passes_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    assert _compose(w)["action"] == "written"


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", YARN_LITERALS)
def test_a_yarn_literal_is_refused_by_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert LITERAL not in json.dumps(result)


def test_a_failed_stamp_write_ends_the_commands_block_non_zero():
    block = "\n".join(CS._commands_block(["true"], None, "sha256:probe", 0))
    assert 'setup stamp write FAILED"; ok=0' in block
    assert "setup did not finish" in block and "ok=0 ; fi" in block
