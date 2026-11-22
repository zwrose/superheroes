"""An aborted aliased decisions carry preserves both original destinations and late source writes."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import calibration_paths
import mode_migrate as mm
import mode_registry as mr
import store_core


def test_abort_restores_destination_after_live_source_update(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: a refused registry commit restores the prior destination bytes even when the carried source changed after copying and a legacy directory aliases the destination.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(_DEC))
    source_before = b'{"ownerDecision": "keep"}\n'
    source_after = b'{"ownerDecision": "updated"}\n'
    destination_before = b'{"previous": true}\n'
    source.write_bytes(source_before)
    destination = Path(w.d_gl(_DEC))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(destination_before)

    ident = store_core.derive_identifiers(w.cwd)
    entry = (Path(w.rr) / calibration_paths.LEGACY_STORE_ENTRIES_DIRNAME
             / ident["gitdir_hash"])
    entry.parent.mkdir(parents=True)
    entry.symlink_to(destination.parent, target_is_directory=True)
    store_core.write_pointer(w.rr, ident["gitdir_hash"], ident["gitdir_hash"])
    assert os.path.samefile(entry / _DEC, destination)

    migration = w.plan(mr.GLOBAL)
    assert not migration.blocked
    assert any(
        f["src"] == str(source) and f["dst"] == str(destination)
        and f.get("role") == mm.ROLE_CARRY
        for f in migration.files
    )
    attempts = []

    def refuse_commit(*args, **kwargs):
        assert destination.read_bytes() == source_before
        source.write_bytes(source_after)
        attempts.append(True)
        return False

    # Pinned interleaving: update the live source immediately before commit refusal; other writer timings and multi-process scheduling are not sampled.
    monkeypatch.setattr(mm, "_commit_registry", refuse_commit)
    assert mm.execute(migration, root=w.root) == {"status": "blocked"}
    assert attempts == [True]
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == source_after
    assert destination.read_bytes() == destination_before
