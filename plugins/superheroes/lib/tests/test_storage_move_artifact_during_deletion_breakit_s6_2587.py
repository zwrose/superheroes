"""Storage moves preserve artifacts saved after source deletion begins."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _PILOT, _put
import mode_migrate as mm
import mode_registry as mr
import store


@pytest.mark.parametrize("directory", ["blocks", "manifests"])
def test_artifact_saved_during_deletion_remains_reachable(
    tmp_path, isolated_default_store_root, monkeypatch, directory
):
    # axis: retiring a legacy profile cannot strand an artifact saved after the source-deletion phase begins.
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
    key = directory + "_dir"
    name = "saved.py" if directory == "blocks" else "saved.json"
    payload = (
        b"def check(context):\n    return True\n"
        if directory == "blocks" else b'{"saved": true}\n'
    )
    saved = Path(before[key]) / name
    deliveries = []
    real_remove = mm._remove

    def save_after_first_source_delete(path):
        real_remove(path)
        if os.fspath(path) == core and not deliveries:
            assert not os.path.lexists(core)
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(payload)
            deliveries.append(str(saved))

    # Pinned interleaving: save after core.md deletion, after the initial artifact check and before legacy-profile deletion; other writer timings and multi-process scheduling are not sampled.
    monkeypatch.setattr(mm, "_remove", save_after_first_source_delete)
    result = mm.execute(migration, root=w.root)
    assert deliveries == [str(saved)]
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    after = store.resolve(w.cwd, w.tr)
    assert after["exists"] and after["refusal"] is None
    resolved = Path(after[key]) / name
    assert resolved.is_file(), "storage move stranded an artifact saved during deletion"
    assert resolved.read_bytes() == payload
