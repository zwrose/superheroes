"""Storage flips preserve decisions created after their overwrite preview."""
import os
from pathlib import Path

from test_leftover_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_flip_refuses_a_decisions_destination_created_after_preview(
    tmp_path, isolated_default_store_root
):
    # axis: a destination created after a preview with no overwrites must survive, and the stale migration must refuse before moving sources.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    name = review_store.FILENAMES["decisions"]
    source_bytes = b'{"sourceDecision": true}\n'
    source = Path(_put(w.inrepo(name), source_bytes.decode("utf-8")))
    destination = Path(w.d_gl(name))
    migration = mm.plan(
        w.cwd, mr.GLOBAL, root=w.root, owner_authorized=True,
        review_root=w.rr, test_pilot_root=w.tr
    )
    assert migration.blocked is False
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    assert not os.path.lexists(destination)
    assert mm.preview(migration)["overwrites"] == []

    # Pinned interleaving: another settings write lands after planning and before execution; writes during copying are not sampled.
    destination.parent.mkdir(parents=True, exist_ok=True)
    late_bytes = b'{"newOwnerDecision": true}\n'
    destination.write_bytes(late_bytes)

    result = mm.execute(migration, root=w.root)
    assert destination.read_bytes() == late_bytes
    assert source.read_bytes() == source_bytes
    assert result["status"] == "blocked"
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
