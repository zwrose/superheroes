"""A target review layer must not activate stale legacy-store decisions."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_target_layer_activation_preserves_decisions_despite_legacy_store_copy(
    tmp_path, isolated_default_store_root
):
    # axis: activating the global review layer preserves the previously read decisions even when legacy-store decisions compete with the carried copy.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.inrepo("review-profile.md"), "## Threat model\nlegacy\n")
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    expected = b'{"ownerDecision": "keep"}\n'
    source = _put(w.inrepo(_DEC), expected.decode("utf-8"))
    _put(w.d_gl(_DEC), '{"previousGlobalDecision": true}\n')
    _put(os.path.join(w.entry(w.rr), _DEC), '{"obsoleteLegacyDecision": true}\n')

    before = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert before["exists"]
    assert before["path"] == source
    assert Path(before["path"]).read_bytes() == expected

    result = mm.execute(w.plan(mr.GLOBAL), root=w.root)
    assert result["status"] == "done" and set(result) <= {"status", "overwritten"}
    # axis: the global decisions copy the carry overwrote keeps its prior bytes in the backup folder
    assert [Path(o["backup"]).read_bytes() for o in result["overwritten"]] == [b'{"previousGlobalDecision": true}\n']
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.GLOBAL
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert after["exists"]
    assert Path(after["path"]).read_bytes() == expected
