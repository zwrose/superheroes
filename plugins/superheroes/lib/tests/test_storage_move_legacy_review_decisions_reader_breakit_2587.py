"""A storage flip preserves decisions when a target review layer becomes active."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_flip_preserves_decisions_when_the_target_review_layer_becomes_active(
    tmp_path, isolated_default_store_root
):
    # axis: moving core.md to an existing global review layer must preserve the decisions selected by the review reader.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.inrepo("review-profile.md"), "## Threat model\nlegacy\n")
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    original = b'{"ownerDecision": "keep"}\n'
    source = Path(_put(w.inrepo(_DEC), original.decode("utf-8")))
    before = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert before["exists"]
    assert before["path"] == str(source)
    assert Path(before["path"]).read_bytes() == original

    assert mm.execute(w.plan(mr.GLOBAL), root=w.root) == {"status": "done"}
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert after["exists"], "the flip made the previously read decisions unreachable"
    assert Path(after["path"]).read_bytes() == original
