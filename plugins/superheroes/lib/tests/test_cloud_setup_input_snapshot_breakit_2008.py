"""A credential input rotation cannot publish a stamp for another snapshot."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_inputs_2008 import (
    _compose, _lock, _run_setup, _set_ok, _stamp, _world,
)
import cloud_setup
import mode_registry
import project_config


@pytest.mark.parametrize("mode", [mode_registry.GLOBAL, mode_registry.IN_REPO])
def test_rotating_a_credential_input_cannot_publish_an_unchecked_stamp(tmp_path, mode):
    # axis: input checks and the published stamp must describe the same file snapshot.
    world = _world(tmp_path, mode)
    before = '{"registryToken":"npm_' + 'a' * 36 + '"}\n'
    after = '{"registryToken":"npm_' + 'b' * 36 + '"}\n'
    _lock(world, text=before)
    stored = _set_ok(
        world, project_config.CLOUD_SETUP_COMMANDS_SLUG,
        ['echo ran >> "$PWD/ran.txt"'],
    )
    assert stored["inputsFilled"] == ["package-lock.json"]
    rotated = False

    def stamp_then_rotate(files):
        nonlocal rotated
        stamp = cloud_setup.calibration_stamp(files)
        if not rotated:
            # Deterministically model an editor or credential rotation after the stamp read.
            _lock(world, text=after)
            rotated = True
        return stamp

    composed = _compose(world, stamp_fn=stamp_then_rotate)
    assert rotated
    if composed["action"] == "refused":
        assert "text" not in composed
        return
    assert composed["action"] == "written", composed
    log, work, stamp_path = _run_setup(world, composed["text"], after)
    if not os.path.exists(stamp_path):
        assert "setup input package-lock.json differs" in log
        assert not (work / "ran.txt").exists()
        return
    assert (work / "ran.txt").exists()
    assert Path(stamp_path).read_text() == _stamp(world) + "\n", (
        "Setup accepted the rotated input but published the stamp for its previous contents"
    )
