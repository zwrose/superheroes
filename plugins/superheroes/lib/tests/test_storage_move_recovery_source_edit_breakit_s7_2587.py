"""Rollback preserves overwritten decisions despite a subsequent source save."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr


def test_recovery_preserves_previous_destination_after_source_changes(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: pre-commit rollback preserves an overwritten destination when the source changes after its successful carry.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    copied_bytes = b'{"sourceBeforeCarry": true}\n'
    previous_bytes = b'{"previousDestination": true}\n'
    latest_bytes = b'{"sourceSavedAfterCarry": true}\n'
    source = Path(_put(w.inrepo(_DEC), copied_bytes.decode("utf-8")))
    destination = Path(_put(w.d_gl(_DEC), previous_bytes.decode("utf-8")))
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )

    def save_source_then_interrupt(*args, **kwargs):
        assert destination.read_bytes() == copied_bytes
        source.write_bytes(latest_bytes)
        raise RuntimeError("stop before registry commit")

    # Pinned interleaving: save the source at the commit seam after copying, then interrupt before the registry write; other save timings and process schedules are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(mm, "_commit_registry", save_source_then_interrupt)
        with pytest.raises(RuntimeError, match="stop before registry commit"):
            mm.execute(migration, root=w.root)

    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert mm.active_journal(w.cwd, root=w.root) is not None
    assert source.read_bytes() == latest_bytes
    assert destination.read_bytes() == copied_bytes

    result = mm.recover(w.cwd, root=w.root)

    assert result["status"] == "recovered"
    assert source.read_bytes() == latest_bytes
    candidates = [destination] + [
        Path(entry["backup"])
        for entry in result.get("overwritten", [])
        if entry["path"] == str(destination)
    ]
    assert any(
        path.is_file() and path.read_bytes() == previous_bytes
        for path in candidates
    ), "rollback discarded the previous destination after a source-only save"
