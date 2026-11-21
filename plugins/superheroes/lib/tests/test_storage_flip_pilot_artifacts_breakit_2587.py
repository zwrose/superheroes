"""Storage flips preserve access to existing test-pilot artifacts."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _PILOT, _put
import mode_migrate as mm
import mode_registry as mr
import store


@pytest.mark.parametrize("target", [mr.GLOBAL, mr.IN_REPO])
@pytest.mark.parametrize("directory", ["blocks", "manifests"])
def test_flip_preserves_existing_pilot_artifact_access(
    tmp_path, isolated_default_store_root, target, directory
):
    # axis: retiring a legacy profile during either flip must not strand its existing blocks or manifests.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    current = mr.IN_REPO if target == mr.GLOBAL else mr.GLOBAL
    w.register(current)
    calibration = w.d_in if current == mr.IN_REPO else w.d_gl
    _put(calibration("core.md"), _CORE)
    _put(calibration("test-pilot.md"), _PILOT)
    if current == mr.IN_REPO:
        profile = w.inrepo("test-pilot", "profile.md")
    else:
        profile = os.path.join(w.entry(w.tr), "profile.md")
    _put(profile, _PILOT)
    name = "saved.md" if directory == "blocks" else "saved.json"
    artifact = Path(profile).parent / directory / name
    artifact.parent.mkdir(parents=True)
    payload = b'{"saved": true}\n'
    artifact.write_bytes(payload)
    key = directory + "_dir"
    before = store.resolve(w.cwd, w.tr)
    assert before["refusal"] is None
    assert (Path(before[key]) / name).read_bytes() == payload

    assert mm.execute(w.plan(target), root=w.root) == {"status": "done"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == target
    after = store.resolve(w.cwd, w.tr)
    assert after["refusal"] is None
    assert after["exists"]
    resolved = Path(after[key]) / name
    assert resolved.is_file(), "storage flip stranded an existing pilot artifact"
    assert resolved.read_bytes() == payload
