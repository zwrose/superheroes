"""A flip preserves active linked decisions instead of selecting an unread copy."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_flip_preserves_the_decisions_read_through_a_legacy_symlink(
    tmp_path, isolated_default_store_root
):
    # axis: rejecting an active decisions symlink as a migration source must not promote a different unread decisions copy.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.GLOBAL)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    _put(w.d_gl(_DEC), '{"staleDecision": true}\n')
    original = b'{"ownerDecision": "keep"}\n'
    referent = tmp_path / "active-decisions.json"
    referent.write_bytes(original)
    legacy = Path(w.entry(w.rr)) / _DEC
    legacy.symlink_to(referent)
    before = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert before["exists"]
    assert before["path"] == str(legacy)
    assert Path(before["path"]).read_bytes() == original

    assert mm.execute(w.plan(mr.IN_REPO), root=w.root) == {"status": "done"}
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert after["exists"]
    assert Path(after["path"]).read_bytes() == original
    assert referent.read_bytes() == original
