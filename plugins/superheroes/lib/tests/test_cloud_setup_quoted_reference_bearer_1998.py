"""Environment references survive the script's shell quoting; Bearer headers take references."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import (  # noqa: E402
    SLUG, _compose, _inside, _outside, _store_commands)

import cloud_setup_text  # noqa: E402
import project_config  # noqa: E402

LITERAL = "v" * 20
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]
QUOTED = "echo \"OPENAI_API_KEY='$BUILD_OPENAI_KEY'\" > .env"
BEARER_REFERENCES = [
    "Bearer $TOKEN_FOR_REGISTRY_X",
    "Bearer ${TOKEN_FOR_REGISTRY_X}",
    'curl -H "Authorization: Bearer $REGISTRY_TOKEN_VALUE" https://packages.example.com',
    "curl -H 'Authorization: Bearer $REGISTRY_TOKEN_VALUE' https://packages.example.com",
    "curl -H Authorization:\\ Bearer\\ $REGISTRY_TOKEN_VALUE https://packages.example.com",
    "Bearer $REGISTRY_TOKEN_VALUE; npm ci",
]
BEARER_LITERALS = [
    "Bearer " + LITERAL,
    "Bearer $TOKEN." + LITERAL,
    "Bearer $REGISTRY_TOKEN_VALUE:abcdef",
    "Bearer ${REGISTRY_TOKEN_VALUE}abcdef",
    "Bearer $REGISTRY_TOKEN_VALUE-abcdef",
    'curl -H "Authorization: Bearer %s" https://packages.example.com' % LITERAL,
]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
def test_a_quoted_reference_in_a_command_is_set_and_composes(tmp_path, make):
    w = make(tmp_path)
    assert _set(w, QUOTED)["action"] != "refused"
    _store_commands(w, [QUOTED])
    result = _compose(w)
    assert result["action"] == "written", result


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
def test_a_hand_stored_literal_command_is_still_refused_by_compose(tmp_path, make):
    command = "echo \"OPENAI_API_KEY='%s'\" > .env" % LITERAL
    w = make(tmp_path)
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert result["reason"] in ("secret-shaped-content", "setup-commands-malformed"), result
    assert LITERAL not in json.dumps(result)


@pytest.mark.parametrize("command", BEARER_REFERENCES)
def test_scan_lets_a_bearer_environment_reference_pass(command):
    assert cloud_setup_text._scan(command) is None


@pytest.mark.parametrize("command", BEARER_LITERALS)
def test_scan_refuses_a_bearer_literal(command):
    assert cloud_setup_text._scan(command) is not None


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", BEARER_REFERENCES)
def test_a_bearer_reference_passes_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "written", result


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", BEARER_LITERALS)
def test_a_bearer_literal_is_refused_by_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
