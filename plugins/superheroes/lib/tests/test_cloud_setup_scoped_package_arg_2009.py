"""A credential-free command with a URL then a scoped package is not secret-shaped (#2009)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_text import CS, _compose, _outside, _put

COMMAND = "npm install --registry https://registry.example.invalid:8443 @acme/widget"


def test_plain_command_is_not_secret_shaped():
    assert CS._scan(COMMAND) is None


def test_json_serialized_command_is_not_secret_shaped():
    settings = json.dumps({"projectConfiguration": {"verifyCommand": COMMAND}})
    assert CS._scan(settings) is None
    assert CS._scan(json.dumps(settings)) is None


def test_real_credential_beside_it_is_still_secret_shaped():
    assert CS._scan(COMMAND + " https://u:p4ss@host.example.invalid/x") is not None


def test_credential_free_verify_command_still_produces_setup_text(tmp_path):
    w = _outside(tmp_path)
    core = json.dumps({"projectConfiguration": {"verifyCommand": COMMAND}})
    _put(w, "config/core.md", ("# Core\n```json\n" + core + "\n```\n").encode())
    result = _compose(w)
    assert result["action"] == "written", result
    assert "text" in result
