"""An aborted carry preserves its destination after a concurrent source save."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr
import store_core


def test_abort_restores_destination_after_source_changes(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: a post-copy source save and failed registry commit preserve the latest source and the overwritten destination's original bytes.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source_before = b'{"sourceDecision": true}\n'
    destination_before = b'{"previousDestinationDecision": true}\n'
    latest_source = b'{"sourceSavedAfterCopy": true}\n'
    source = Path(_put(w.inrepo(_DEC), source_before.decode("utf-8")))
    destination = Path(_put(w.d_gl(_DEC), destination_before.decode("utf-8")))
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    registry_path = mr.registry_path(w.cwd, w.root)
    real_write = store_core.atomic_write
    attempts = []

    def save_source_and_refuse_commit(path, text, *args, **kwargs):
        if os.fspath(path) == registry_path:
            assert destination.read_bytes() == source_before
            source.write_bytes(latest_source)
            attempts.append(os.fspath(path))
            raise OSError("simulated registry commit failure")
        return real_write(path, text, *args, **kwargs)

    # Pinned interleaving: an editor that does not take config_lock saves the source after all copies and immediately before the registry write fails; other writer timings and process schedules are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", save_source_and_refuse_commit)
        result = mm.execute(migration, root=w.root)

    assert attempts == [registry_path]
    assert result == {"status": "blocked"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == latest_source
    assert destination.read_bytes() == destination_before
    assert mm.active_journal(w.cwd, root=w.root) is None
