"""Committed storage-flip recovery preserves archived profile bytes."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _put
import leftover_settings as ls
import mode_migrate as mm
import mode_registry as mr


@pytest.mark.parametrize("ending", [b"\r\n", b"\r"], ids=["crlf", "lone-cr"])
def test_recovery_recreates_a_missing_profile_archive_without_changing_bytes(
    tmp_path, isolated_default_store_root, monkeypatch, ending
):
    # axis: committed recovery and restore preserve every profile byte when the archive is missing but the source remains.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    profile = Path(w.inrepo("review-profile.md"))
    original = ending.join([b"## Threat model", b"single owner", b""])
    profile.write_bytes(original)
    migration = w.plan(mr.GLOBAL)
    archives = [
        entry for entry in migration.files
        if entry["src"] == str(profile)
        and entry.get("role") == mm.ROLE_SET_ASIDE
    ]
    assert len(archives) == 1
    archived = Path(archives[0]["dst"])
    first_source = migration.files[0]["src"]
    real_remove = mm._remove

    def interrupt_before_source_deletion(path):
        if os.fspath(path) == first_source:
            raise RuntimeError("simulated stop after registry commit")
        return real_remove(path)

    # Pinned interruption: stop at the first source deletion; other production crash timings within the deleting phase are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(mm, "_remove", interrupt_before_source_deletion)
        with pytest.raises(RuntimeError, match="simulated stop after registry commit"):
            mm.execute(migration, root=w.root)

    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.GLOBAL
    assert mm.active_journal(w.cwd, root=w.root) is not None
    assert profile.read_bytes() == original
    assert archived.read_bytes() == original
    # Exercise the supported missing-destination recovery branch using only this test's temporary backup.
    archived.unlink()
    assert mm.recover(w.cwd, root=w.root) == {"status": "recovered"}
    assert not profile.exists()
    assert archived.read_bytes() == original

    restored = ls.restore(w.cwd, str(archived.parent), root=w.root)
    assert restored["status"] == "restored"
    assert restored["skipped"] == []
    assert profile.read_bytes() == original
