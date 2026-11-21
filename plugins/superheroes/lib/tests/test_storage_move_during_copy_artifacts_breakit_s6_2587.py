"""Storage flips preserve pilot artifacts saved during the copy phase."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _PILOT, _put
import mode_migrate as mm
import mode_registry as mr
import store


@pytest.mark.parametrize("directory", ["blocks", "manifests"])
def test_flip_preserves_pilot_artifact_saved_during_copy(
    tmp_path, isolated_default_store_root, monkeypatch, directory
):
    # axis: retiring a legacy profile cannot strand an artifact saved after execution's plan recheck and before source deletion.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    core = _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("test-pilot.md"), _PILOT)
    profile = _put(w.inrepo("test-pilot", "profile.md"), _PILOT)
    before = store.resolve(w.cwd, w.tr)
    assert before["exists"] and before["refusal"] is None
    assert before["profile"] == profile
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == profile
        and entry.get("role") == mm.ROLE_SET_ASIDE
        for entry in migration.files
    )
    name = "saved.md" if directory == "blocks" else "saved.json"
    key = directory + "_dir"
    saved = Path(before[key]) / name
    payload = b'{"saved": true}\n'
    deliveries = []
    real_copy = mm._copy_bytes

    def save_during_copy(src, dst):
        real_copy(src, dst)
        if os.fspath(src) == core and not deliveries:
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(payload)
            deliveries.append(str(saved))

    # Pinned interleaving: save immediately after copying core.md, before profile deletion; other writer timings and multi-process scheduling are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", save_during_copy)
    result = mm.execute(migration, root=w.root)
    assert deliveries == [str(saved)]
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    after = store.resolve(w.cwd, w.tr)
    assert after["exists"] and after["refusal"] is None
    resolved = Path(after[key]) / name
    assert resolved.is_file(), "storage flip stranded an artifact saved during copying"
    assert resolved.read_bytes() == payload
