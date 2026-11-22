"""A storage flip preserves decisions appended while their carry is in flight."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import decisions
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_flip_preserves_a_decision_appended_after_its_copy(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: a decision appended to the currently resolved source after its carry copy remains readable after the flip.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(_DEC))
    decisions.append(str(source), {
        "id": "before-flip", "dimension": "Test",
        "category": "storage", "action": "skip",
    })
    destination = Path(w.d_gl(_DEC))
    migration = w.plan(mr.GLOBAL)
    assert not migration.blocked
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    late_record = {
        "id": "during-flip", "dimension": "Test",
        "category": "storage", "action": "guidance",
    }
    appended = []
    real_copy = mm._copy_bytes

    def append_after_carry(src, dst):
        real_copy(src, dst)
        if os.fspath(src) == str(source) and not appended:
            current = review_store.resolve(
                w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
            )
            assert current["exists"]
            assert current["path"] == str(source)
            decisions.append(current["path"], late_record)
            appended.append(late_record["id"])

    # Pinned interleaving: append immediately after the decisions copy, before registry commit; other writer timings and multi-process scheduling are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", append_after_carry)
    result = mm.execute(migration, root=w.root)
    assert appended == ["during-flip"]
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    after = review_store.resolve(
        w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
    )
    assert after["exists"]
    record_ids = {
        record["id"] for record in decisions.load_store(after["path"])["records"]
    }
    assert {"before-flip", "during-flip"} <= record_ids
