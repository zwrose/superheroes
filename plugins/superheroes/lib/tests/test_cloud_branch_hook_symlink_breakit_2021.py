"""Adoption must compare the contents consumed through a listed setup input."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cloud_branch_hook_2021 import CS, _commit, _hooked


def test_adoption_refuses_a_changed_target_of_an_unchanged_input_symlink(tmp_path):
    # axis: identical symlink blobs must not hide changed dependency-input contents.
    world, _, _ = _hooked(tmp_path)
    target = world.repo / "dependency-lock.json"
    target.write_text("v1\n")
    listed = world.repo / "package-lock.json"
    listed.unlink()
    listed.symlink_to(target.name)
    startup = _commit(world.cwd, "listed input is a symlink")

    target.write_text("v2\n")
    adopted = _commit(world.cwd, "adopted dependencies changed")

    assert CS.branch_hook_gap(
        world.cwd, world.root, startup, adopted
    ) == "adopted-input-not-a-file"
