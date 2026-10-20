"""Credentials: ANSI-C quoting an assignment word cannot hide its literal value."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_dependency_hook_2009 import (
    COMMANDS_SLUG, HOOK_SLUG, PC, _raw, _world, core_md, mode_registry,
)


@pytest.mark.parametrize("quoted_part", ["whole-word", "key"])
def test_ansi_c_assignment_word_is_refused_before_hook_creation(tmp_path, quoted_part):
    # axis: shell-equivalent credential assignment words never reach committed hook files.
    world = _world(tmp_path, mode_registry.GLOBAL)
    credential = "fixture_private_key_123"
    if quoted_part == "whole-word":
        word = "$'AWS_SECRET_ACCESS_KEY=" + credential + "'"
    else:
        word = "$'AWS_SECRET_ACCESS_KEY'=" + credential
    rendered = subprocess.run(
        ["bash", "-c", "printf %s " + word],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert rendered.stdout == "AWS_SECRET_ACCESS_KEY=" + credential
    stored = core_md.write_project_config_item(
        world.cwd, COMMANDS_SLUG, ["env " + word + " npm ci"], root=world.root,
    )
    assert stored["action"] in ("written", "noop"), stored

    result = PC.set_item(world.cwd, HOOK_SLUG, True, root=world.root)
    assert result == {"action": "refused", "reason": "setup-command-secret-shaped"}
    assert _raw(world, HOOK_SLUG) is None
    assert not world.script.exists()
    assert not world.settings.exists()
    assert credential not in json.dumps(result)
