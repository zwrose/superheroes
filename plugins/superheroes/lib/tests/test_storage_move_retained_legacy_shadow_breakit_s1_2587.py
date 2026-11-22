"""A storage flip preserves the decisions read before activating a global layer."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_retained_legacy_decisions_do_not_shadow_the_carried_copy(
    tmp_path, isolated_default_store_root
):
    # axis: activating a global review layer during a flip preserves the decisions read beforehand even when a different legacy-store decisions copy exists.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.inrepo("review-profile.md"), "## Threat model\nlegacy\n")
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    expected = b'{"ownerDecision": "keep"}\n'
    source = Path(_put(w.inrepo(_DEC), expected.decode("utf-8")))
    _put(os.path.join(w.entry(w.rr), _DEC), '{"ownerDecision": "older"}\n')

    before = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert before["exists"]
    assert before["path"] == str(source)
    assert Path(before["path"]).read_bytes() == expected

    migration = w.plan(mr.GLOBAL)
    assert migration.blocked is False
    assert mm.execute(migration, root=w.root) == {"status": "done"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.GLOBAL
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert after["exists"]
    assert Path(after["path"]).read_bytes() == expected
