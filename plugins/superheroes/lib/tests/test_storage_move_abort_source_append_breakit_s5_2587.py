"""A refused flip preserves its old destination despite a concurrent source append."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import decisions
import mode_migrate as mm
import mode_registry as mr
import review_store
import store_core


def test_abort_restores_destination_after_source_append(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: registry refusal after a source append preserves both acknowledged source records and the destination's original bytes.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(_DEC))
    decisions.append(str(source), {
        "id": "before-copy", "dimension": "Test",
        "category": "storage", "action": "skip",
    })
    copied_bytes = source.read_bytes()
    previous = b'{"previousDestination": "keep"}\n'
    destination = Path(_put(w.d_gl(_DEC), previous.decode("utf-8")))
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    registry_path = mr.registry_path(w.cwd, w.root)
    attempts = []
    real_write = store_core.atomic_write

    def append_then_refuse_registry(path, text, *args, **kwargs):
        if os.fspath(path) == registry_path:
            assert destination.read_bytes() == copied_bytes
            current = review_store.resolve(
                w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root
            )
            assert current["path"] == str(source)
            entry = decisions.append(current["path"], {
                "id": "during-commit", "dimension": "Test",
                "category": "storage", "action": "guidance",
            })
            attempts.append(entry["id"])
            raise OSError("simulated registry write failure")
        return real_write(path, text, *args, **kwargs)

    # Pinned interleaving: append after the carry publishes and immediately before registry refusal; writes during byte transfer and other process schedules are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", append_then_refuse_registry)
        result = mm.execute(migration, root=w.root)

    assert attempts == ["during-commit"]
    assert result == {"status": "blocked"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert {
        record["id"] for record in decisions.load_store(str(source))["records"]
    } == {"before-copy", "during-commit"}
    assert destination.read_bytes() == previous, "abort discarded the original destination after a source append"
    assert mm.recover(w.cwd, root=w.root) == {"status": "noop"}
