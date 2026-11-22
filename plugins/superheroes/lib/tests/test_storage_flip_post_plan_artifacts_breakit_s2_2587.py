"""Storage flips preserve pilot artifacts created after planning."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _PILOT, _put
import mode_migrate as mm
import mode_registry as mr
import store


@pytest.mark.parametrize("directory", ["blocks", "manifests"])
def test_flip_preserves_artifacts_created_after_plan(
    tmp_path, isolated_default_store_root, directory
):
    # axis: a profile retirement planned before the first saved artifact must preserve that artifact's resolver access or refuse the flip.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("test-pilot.md"), _PILOT)
    profile = Path(_put(w.inrepo("test-pilot", "profile.md"), _PILOT))
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(profile)
        and entry.get("role") == mm.ROLE_SET_ASIDE
        for entry in migration.files
    )

    # Pinned interleaving: save after planning and before execution; saves during copying are not sampled.
    name = "saved.md" if directory == "blocks" else "saved.json"
    artifact = profile.parent / directory / name
    artifact.parent.mkdir(parents=True)
    payload = b'{"saved": true}\n'
    artifact.write_bytes(payload)
    key = directory + "_dir"
    before = store.resolve(w.cwd, w.tr)
    assert before["refusal"] is None and before["exists"]
    assert (Path(before[key]) / name).read_bytes() == payload

    result = mm.execute(migration, root=w.root)
    assert result["status"] in {"done", "blocked"}
    after = store.resolve(w.cwd, w.tr)
    assert after["refusal"] is None and after["exists"]
    resolved = Path(after[key]) / name
    assert resolved.is_file(), "storage flip stranded an artifact saved after planning"
    assert resolved.read_bytes() == payload
