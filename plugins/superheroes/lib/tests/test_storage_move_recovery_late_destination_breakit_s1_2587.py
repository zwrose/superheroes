"""Recovery preserves destination saves after an interrupted decisions carry."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr


@pytest.mark.parametrize("original_shape", ["absent", "symlink"])
def test_recovery_keeps_a_destination_saved_after_the_interruption(
    tmp_path, isolated_default_store_root, monkeypatch, original_shape
):
    # axis: recovery retains a later destination save for originally absent and linked slots.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    original_source = b'{"sourceDecision": "before"}\n'
    source = Path(_put(w.inrepo(_DEC), original_source.decode("utf-8")))
    destination = Path(w.d_gl(_DEC))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if original_shape == "symlink":
        referent = tmp_path / "previous-decisions.json"
        referent.write_bytes(b'{"previousDecision": true}\n')
        destination.symlink_to(referent)
    else:
        assert not os.path.lexists(destination)
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source) and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    publications = []
    real_copy = mm._copy_bytes

    def stop_after_carry(src, dst):
        real_copy(src, dst)
        if os.fspath(src) == str(source) and os.fspath(dst) == str(destination):
            publications.append(str(destination))
            raise OSError("simulated stop after carry publication")

    # Pinned interruption: stop immediately after publication, then save before recovery;
    # writes during byte transfer and other crash or multi-process schedules are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(mm, "_copy_bytes", stop_after_carry)
        with pytest.raises(OSError, match="simulated stop after carry publication"):
            mm.execute(migration, root=w.root)

    assert publications == [str(destination)]
    assert mm.active_journal(w.cwd, root=w.root) is not None
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    latest = b'{"ownerSavedAfterInterruption": "preserve"}\n'
    destination.write_bytes(latest)
    assert mm.recover(w.cwd, root=w.root)["status"] == "recovered"
    assert source.read_bytes() == original_source
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert any(
        path.is_file() and path.read_bytes() == latest
        for path in Path(w.store_dir()).rglob("*")
    ), "recovery discarded the later destination save without retaining any backup"
