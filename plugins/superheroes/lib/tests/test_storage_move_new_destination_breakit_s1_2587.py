"""A storage flip must preserve a destination created after its preview."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr


def test_flip_refuses_a_decisions_destination_created_after_preview(
        tmp_path, isolated_default_store_root):
    # axis: a destination absent from the confirmed preview is never overwritten when another write creates it before execution.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source_bytes = b'{"sourceDecision": true}\n'
    source = Path(_put(w.inrepo(_DEC), source_bytes.decode("utf-8")))
    destination = Path(w.d_gl(_DEC))
    migration = w.plan(mr.GLOBAL)
    assert not migration.blocked
    assert not os.path.lexists(destination)
    shown = mm.preview(migration)
    assert str(destination) not in shown["overwrites"]

    # Pinned interleaving: write after preview and before execute; writes during copying are not sampled.
    new_bytes = b'{"newOwnerDecision": "preserve"}\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(new_bytes)
    result = mm.execute(migration, root=w.root)

    assert destination.read_bytes() == new_bytes, "flip overwrote a destination absent from its confirmed preview"
    assert result["status"] == "blocked"
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == source_bytes
