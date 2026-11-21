"""An aborted storage flip preserves both existing decisions copies."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr
import review_store
import store_core


@pytest.mark.parametrize("failure", ["registry-write", "after-carry"])
def test_failed_flip_preserves_original_decisions_bytes(
    tmp_path, isolated_default_store_root, monkeypatch, failure
):
    # axis: abort or recovery after a successful carry restores a pre-existing decisions destination byte for byte.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- local\n")
    _put(w.inrepo("review-profile.md"), "## Threat model\nlegacy\n")
    name = review_store.FILENAMES["decisions"]
    source = Path(_put(w.inrepo(name), '{"source": true}\n'))
    destination = Path(_put(w.d_gl(name), '{"previous": true}\n'))
    source_before = source.read_bytes()
    destination_before = destination.read_bytes()
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source) and entry["dst"] == str(destination)
        for entry in migration.files
    )
    if failure == "registry-write":
        failure_path = mr.registry_path(w.cwd, w.root)
    else:
        failure_path = next(
            entry["dst"] for entry in migration.files
            if entry.get("role") == mm.ROLE_SET_ASIDE
        )
    real_write = store_core.atomic_write

    def fail_selected_write(path, text, *args, **kwargs):
        if os.fspath(path) == failure_path:
            raise OSError("simulated migration write failure")
        return real_write(path, text, *args, **kwargs)

    real_copy = mm._copy_bytes

    def fail_selected_copy(src, dst):
        # the flip copies each file byte for byte, so the injected failure hits that copy too
        if os.fspath(dst) == failure_path:
            raise OSError("simulated migration write failure")
        return real_copy(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", fail_selected_write)
        patch.setattr(mm, "_copy_bytes", fail_selected_copy)
        if failure == "registry-write":
            assert mm.execute(migration, root=w.root) == {"status": "blocked"}
        else:
            with pytest.raises(OSError, match="simulated migration write failure"):
                mm.execute(migration, root=w.root)

    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    recovery = mm.recover(w.cwd, root=w.root)
    expected = "noop" if failure == "registry-write" else "recovered"
    assert recovery == {"status": expected}
    assert source.read_bytes() == source_before
    assert destination.is_file()
    assert destination.read_bytes() == destination_before
