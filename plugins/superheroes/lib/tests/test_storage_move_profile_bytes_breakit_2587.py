"""Storage-move archives restore legacy profiles without changing their bytes."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _put
import leftover_settings as ls
import mode_migrate as mm
import mode_registry as mr


@pytest.mark.parametrize("ending", [b"\r\n", b"\r"], ids=["crlf", "lone-cr"])
def test_storage_move_restores_original_profile_bytes(
    tmp_path, isolated_default_store_root, ending
):
    # axis: setting a legacy profile aside and restoring it preserves every byte, including non-LF line endings.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    profile = Path(w.inrepo("review-profile.md"))
    original = ending.join([b"## Threat model", b"single owner", b""])
    profile.write_bytes(original)

    migration = w.plan(mr.GLOBAL)
    entries = [
        entry for entry in migration.files
        if entry["src"] == str(profile)
        and entry.get("role") == mm.ROLE_SET_ASIDE
    ]
    assert len(entries) == 1
    archived = Path(entries[0]["dst"])
    assert mm.execute(migration, root=w.root) == {"status": "done"}
    assert not profile.exists()
    assert archived.read_bytes() == original

    restored = ls.restore(w.cwd, str(archived.parent), root=w.root)
    assert restored["status"] == "restored"
    assert restored["skipped"] == []
    assert profile.read_bytes() == original
