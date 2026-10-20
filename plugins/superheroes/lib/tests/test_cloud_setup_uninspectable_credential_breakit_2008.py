"""Uninspectable credential inputs must not be receipted as missing."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_setup_inputs_2008 import _compose, _run_setup, _set_ok, _world
import mode_registry
import project_config


def test_uninspectable_credential_parent_withholds_setup_stamp(tmp_path):
    # axis: an ELOOP inspecting a credential input is unreadable, not the expected absence.
    world = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(world, project_config.CLOUD_SETUP_COMMANDS_SLUG,
            ['echo ran >> "$PWD/ran.txt"'])
    _set_ok(world, project_config.CLOUD_SETUP_INPUTS_SLUG, ["private/.npmrc"])
    composed = _compose(world)
    assert composed["action"] == "written", composed

    work = world.tmp / "work"
    work.mkdir()
    (work / "private").symlink_to("private", target_is_directory=True)
    log, work, stamp, proc = _run_setup(world, composed["text"], None)

    assert proc.returncode != 0, (log, proc.stdout, proc.stderr)
    assert not (work / "ran.txt").exists(), log
    assert not os.path.exists(stamp), log
