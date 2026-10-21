"""Credential input inspection failures must not become missing-file receipts."""
import errno
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_inputs_2008 import _compose, _set_ok, _world
import mode_registry
import project_config


@pytest.mark.parametrize("mode", [mode_registry.GLOBAL, mode_registry.IN_REPO])
def test_inaccessible_credential_input_is_refused(tmp_path, monkeypatch, mode):
    # axis: failure to inspect a configured credential input refuses composition, never stamps it missing.
    world = _world(tmp_path, mode)
    credential_path = world.repo / ".npmrc"
    token = "npm_" + "a" * 36
    credential_path.write_text("//registry.npmjs.org/:_authToken=" + token + "\n")
    _set_ok(world, project_config.CLOUD_SETUP_COMMANDS_SLUG, ["npm ci"])
    _set_ok(world, project_config.CLOUD_SETUP_INPUTS_SLUG, [".npmrc"])
    baseline = _compose(world)
    assert baseline["action"] == "written", baseline
    assert token not in json.dumps(baseline)
    real_lstat = os.lstat

    def denied_lstat(path, *args, **kwargs):
        if os.fspath(path) == str(credential_path):
            raise PermissionError(errno.EACCES, "Permission denied", str(credential_path))
        return real_lstat(path, *args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(os, "lstat", denied_lstat)
        result = _compose(world)
    assert result.get("action") == "refused", result
    assert result.get("reason") == "setup-inputs-unreadable", result
    assert "text" not in result
    assert token not in json.dumps(result)
