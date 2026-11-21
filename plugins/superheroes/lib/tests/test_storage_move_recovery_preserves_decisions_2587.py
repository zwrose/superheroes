"""#2587: interrupted migration preserves a decisions destination it never wrote."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr
import review_store
import store_core


def test_recovery_preserves_an_untouched_decisions_destination(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: recovery after a failed carry preserves the existing destination's exact bytes.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- local\n")
    name = review_store.FILENAMES["decisions"]
    source = Path(_put(w.inrepo(name), '{"source": true}\n'))
    destination = Path(_put(w.d_gl(name), '{"previous": true}\n'))
    source_before = source.read_bytes()
    destination_before = destination.read_bytes()
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == "carry"
        for entry in migration.files
    )
    real_atomic_write = store_core.atomic_write

    def interrupt_copy(path, text, *args, **kwargs):
        if os.fspath(path) == str(destination):
            raise OSError("simulated copy interruption")
        return real_atomic_write(path, text, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", interrupt_copy)
        with pytest.raises(OSError, match="simulated copy interruption"):
            mm.execute(migration, root=w.root)

    assert destination.read_bytes() == destination_before
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert mm.recover(w.cwd, root=w.root) == {"status": "recovered"}
    assert source.read_bytes() == source_before
    assert destination.is_file(), "rollback deleted an untouched decisions copy"
    assert destination.read_bytes() == destination_before
