"""Credential-named assignments: a bare environment reference passes, a literal is refused."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import (  # noqa: E402
    SLUG, _compose, _inside, _outside, _store_commands)

import project_config  # noqa: E402

LITERAL = "v" * 12
REFERENCES = [
    "OPENAI_API_KEY=$BUILD_OPENAI_KEY npm run build",
    "OPENAI_API_KEY=${BUILD_OPENAI_KEY} npm run build",
    'OPENAI_API_KEY="$BUILD_OPENAI_KEY" npm run build',
    "access_token=${TOKEN}",
    "access_token=$TOKEN",
    'access_token="${TOKEN}"',
    "refresh_token=$TOKEN; npm run build",
]
LITERALS = [
    "OPENAI_API_KEY=%s npm run build" % LITERAL,
    'access_token="%s"' % LITERAL,
    "access_token='%s'" % LITERAL,
    "access_token=$'%s'" % LITERAL,
    "access_token=${TOKEN:-%s}" % LITERAL,
    "access_token=$TOKEN-%s" % LITERAL,
    'access_token="$TOKEN"%s' % LITERAL,
]
WORLDS = [_inside, _outside]
IDS = ["inside", "outside"]


def _set(w, command):
    _store_commands(w, [])
    return project_config.set_item(w.cwd, SLUG, [command], root=w.root)


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", REFERENCES)
def test_a_bare_reference_assignment_passes_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command)["action"] != "refused"
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "written", result


@pytest.mark.parametrize("make", WORLDS, ids=IDS)
@pytest.mark.parametrize("command", LITERALS)
def test_a_literal_assignment_is_refused_by_set_and_compose(tmp_path, make, command):
    w = make(tmp_path)
    assert _set(w, command) == {"action": "refused",
                                "reason": project_config.REASON_SETUP_COMMAND_SECRET_SHAPED}
    _store_commands(w, [command])
    result = _compose(w)
    assert result["action"] == "refused" and "text" not in result, result
    assert LITERAL not in json.dumps(result)
