"""Storage flips retain review decisions appended during the carry."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _put
import decisions
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_flip_retains_a_decision_appended_after_the_carry_copy(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: an acknowledged decisions.append after the carry copy remains visible through the active review reader after the flip.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(review_store.FILENAMES["decisions"]))
    decisions.append(str(source), {
        "id": "before-copy", "dimension": "Code",
        "category": "concurrency", "action": "skip",
    })
    before = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root,
    )
    assert before["exists"] and before["path"] == str(source)
    migration = w.plan(mr.GLOBAL)
    delivered = []
    real_copy = mm._copy_bytes

    def append_after_carry(src, dst):
        real_copy(src, dst)
        if os.fspath(src) == str(source) and not delivered:
            entry = decisions.append(str(source), {
                "id": "after-copy", "dimension": "Code",
                "category": "concurrency", "action": "guidance",
            })
            delivered.append(entry["id"])

    # Pinned interleaving: append immediately after the real carry copy returns; writes before copying, during byte transfer, and other process schedules are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", append_after_carry)
    result = mm.execute(migration, root=w.root)
    assert delivered == ["after-copy"]
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root,
    )
    assert after["exists"]
    ids = {record["id"] for record in decisions.load_store(after["path"])["records"]}
    assert {"before-copy", "after-copy"} <= ids, "flip discarded an acknowledged decision append"
