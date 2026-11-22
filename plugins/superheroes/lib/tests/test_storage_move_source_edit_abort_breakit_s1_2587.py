"""An aborted flip preserves an overwritten destination despite a later source edit."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr


@pytest.mark.parametrize("failure", ["registry-refusal", "copy-interruption"])
def test_source_edit_does_not_discard_the_destination_snapshot(
    tmp_path, isolated_default_store_root, monkeypatch, failure
):
    # axis: abort and recovery restore the old destination even when its source changed after copying.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source_before = b'{"sourceDecision": "before"}\n'
    destination_before = b'{"previousDestinationDecision": "keep"}\n'
    latest_source = b'{"sourceDecision": "saved-during-copy"}\n'
    source = Path(_put(w.inrepo(_DEC), source_before.decode("utf-8")))
    destination = Path(_put(w.d_gl(_DEC), destination_before.decode("utf-8")))
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source) and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    deliveries = []
    real_copy = mm._copy_bytes

    def edit_after_carry(src, dst):
        real_copy(src, dst)
        # only the first carry copy saves; the pre-commit re-copy that follows is not counted
        if os.fspath(src) == str(source) and os.fspath(dst) == str(destination) and not deliveries:
            assert destination.read_bytes() == source_before
            source.write_bytes(latest_source)
            deliveries.append(str(source))
            if failure == "copy-interruption":
                raise OSError("simulated stop after carry publication")

    # Pinned interleaving: save immediately after the real carry and stop at the selected boundary;
    # writes during byte transfer, other crash timings and multi-process schedules are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(mm, "_copy_bytes", edit_after_carry)
        if failure == "registry-refusal":
            patch.setattr(mm, "_commit_registry", lambda *args, **kwargs: False)
            assert mm.execute(migration, root=w.root) == {"status": "blocked"}
        else:
            with pytest.raises(OSError, match="simulated stop after carry publication"):
                mm.execute(migration, root=w.root)

    assert deliveries == [str(source)]
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    recovery = mm.recover(w.cwd, root=w.root)
    assert recovery["status"] == (
        "noop" if failure == "registry-refusal" else "recovered"
    )
    assert source.read_bytes() == latest_source
    assert destination.is_file()
    assert destination.read_bytes() == destination_before
