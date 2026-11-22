"""Storage-flip resynchronization preserves acknowledged decision appends."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import decisions
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_flip_preserves_destination_append_during_resynchronization(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: every acknowledged decision remains readable when source and destination writers overlap a carry retry.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(_DEC))
    destination = Path(w.d_gl(_DEC))
    decisions.append(str(source), {
        "id": "before-flip", "dimension": "Test",
        "category": "storage", "action": "skip",
    })
    acknowledged = {"before-flip"}
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    copies = []
    real_copy = mm._copy_bytes

    def append_after_copy(src, dst):
        real_copy(src, dst)
        if os.fspath(src) != str(source):
            return
        copies.append(os.fspath(dst))
        if len(copies) == 1:
            record_id, expected_path = "source-late", source
        elif len(copies) == 2:
            # the second save lands after the pre-commit re-copy, while the source is still the one read
            record_id, expected_path = "source-after-recopy", source
        else:
            return
        current = review_store.resolve(
            w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
        )
        assert current["exists"]
        assert current["path"] == str(expected_path)
        entry = decisions.append(current["path"], {
            "id": record_id, "dimension": "Test",
            "category": "storage", "action": "guidance",
        })
        acknowledged.add(entry["id"])

    # Pinned interleaving: append to the active source after its first copy, then
    # again after the pre-commit re-copy publishes and before its digest is sampled. Writes during byte transfer and other process schedules are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", append_after_copy)
    result = mm.execute(migration, root=w.root)
    assert "source-late" in acknowledged
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert after["exists"]
    visible = {
        record["id"] for record in decisions.load_store(after["path"])["records"]
    }
    assert acknowledged <= visible, "flip discarded an acknowledged decision"
