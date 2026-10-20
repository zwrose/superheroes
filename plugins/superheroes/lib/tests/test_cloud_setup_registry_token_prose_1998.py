"""Ordinary registry-token prose and get/delete commands are not secrets (#1998 round 3)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cloud_setup_text as T
from test_cloud_setup_text import (CS, SLUG, _both_modes, _compose, _outside, _put,
                                   _store_commands, project_config)

PASSING = [
    "The npmAuthToken comes from the cloud environment.",
    "npm config delete //registry.example.com/:_authToken && npm ci",
    "npm config get //registry.example.com/:_authToken",
]
REFUSED = [
    "npm config set //registry.example.com/:_authToken " + "a1B2" * 10,
    'npm config set "//registry.example.com/:_authToken" "%s"' % ("a1B2" * 10),
    "npm config set --global //registry.example.com/:_authToken " + "a1B2" * 10,
    "npm set //registry.example.com/:_authToken " + "a1B2" * 10,
    "yarn config set npmAuthToken " + "a1B2" * 10,
]


@pytest.mark.parametrize("text", PASSING)
def test_scan_passes_prose_get_and_delete(text):
    assert CS._scan(text) is None


@pytest.mark.parametrize("text", REFUSED)
def test_scan_still_refuses_a_config_set_literal(text):
    assert CS._scan(text) == "registry token"


@pytest.mark.parametrize("command", PASSING[1:])
def test_set_and_compose_accept_the_command_in_both_modes(tmp_path, command):
    for name, w in _both_modes(tmp_path):
        _store_commands(w, [])
        done = project_config.set_item(w.cwd, SLUG, [command], root=w.root)
        assert done["action"] == "written", (name, done)
        result = _compose(w)
        assert result["action"] == "written", (name, result)


def test_placed_calibration_prose_naming_npmauthtoken_composes(tmp_path):
    w = _outside(tmp_path)
    _put(w, "config/core.md", b"# Core\nThe npmAuthToken comes from the cloud environment.\n")
    result = _compose(w)
    assert result["action"] == "written", result
    assert result["calibration"]["placed"] is True

