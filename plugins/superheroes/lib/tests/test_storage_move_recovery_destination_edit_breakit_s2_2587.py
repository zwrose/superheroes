"""Storage-flip recovery preserves destination saves after a failed carry."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr


def test_recovery_preserves_destination_saved_after_failed_carry(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: recovery must preserve an owner edit saved at a decisions destination after the carry failed, either in place or in a backup.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source_bytes = b'{"sourceDecision": true}\n'
    previous_bytes = b'{"previousDestinationDecision": true}\n'
    source = Path(_put(w.inrepo(_DEC), source_bytes.decode("utf-8")))
    destination = Path(_put(w.d_gl(_DEC), previous_bytes.decode("utf-8")))
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    real_copy = mm._copy_bytes
    interruptions = []

    def fail_before_carry(src, dst):
        if os.fspath(dst) == str(destination):
            interruptions.append(str(destination))
            raise OSError("simulated stop before decisions carry")
        return real_copy(src, dst)

    # Pinned interruption: fail before the carry publishes, after snapshot journaling; failures during byte transfer and other crash timings are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(mm, "_copy_bytes", fail_before_carry)
        with pytest.raises(OSError, match="simulated stop before decisions carry"):
            mm.execute(migration, root=w.root)

    assert interruptions == [str(destination)]
    assert mm.active_journal(w.cwd, root=w.root) is not None
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert destination.read_bytes() == previous_bytes
    latest_bytes = b'{"ownerSavedAfterFailure": "preserve this edit"}\n'
    destination.write_bytes(latest_bytes)

    mm.recover(w.cwd, root=w.root)

    assert source.read_bytes() == source_bytes
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert any(
        path.is_file() and path.read_bytes() == latest_bytes
        for path in Path(w.store_dir()).rglob("*")
    ), "recovery discarded the destination edit without preserving a backup"
