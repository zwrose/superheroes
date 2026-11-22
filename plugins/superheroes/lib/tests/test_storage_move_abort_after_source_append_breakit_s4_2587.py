"""An aborted carry preserves its previous target despite a source append."""
import os
from pathlib import Path

from test_leftover_settings_2587 import W, _CORE, _put
import decisions
import mode_migrate as mm
import mode_registry as mr
import review_store
import store_core


def test_abort_after_source_append_restores_previous_destination(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: registry refusal after a source append preserves both the appended source record and the overwritten destination's original bytes.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    name = review_store.FILENAMES["decisions"]
    source = Path(w.inrepo(name))
    destination = Path(w.d_gl(name))
    decisions.append(str(source), {
        "id": "before-copy", "dimension": "Test",
        "category": "storage", "action": "skip",
    })
    decisions.append(str(destination), {
        "id": "previous-target", "dimension": "Test",
        "category": "storage", "action": "guidance",
    })
    copied_bytes = source.read_bytes()
    previous_bytes = destination.read_bytes()
    migration = mm.plan(
        w.cwd, mr.GLOBAL, root=w.root, owner_authorized=True,
        review_root=w.rr, test_pilot_root=w.tr,
    )
    assert not migration.blocked
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
            decisions.append(str(source), {
                "id": "after-copy", "dimension": "Test",
                "category": "storage", "action": "guidance",
            })
            attempts.append(os.fspath(path))
            raise OSError("simulated registry refusal")
        return real_write(path, text, *args, **kwargs)

    # Pinned interleaving: append after the carry publishes, immediately before registry refusal; writes during copying and other process schedules are not sampled.
    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", append_then_refuse_registry)
        result = mm.execute(migration, root=w.root)

    assert attempts == [registry_path]
    assert result == {"status": "blocked"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert {
        record["id"] for record in decisions.load_store(str(source))["records"]
    } == {"before-copy", "after-copy"}
    assert mm.recover(w.cwd, root=w.root) == {"status": "noop"}
    assert destination.read_bytes() == previous_bytes
