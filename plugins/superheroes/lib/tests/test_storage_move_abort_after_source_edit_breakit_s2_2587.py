"""An aborted carry preserves destination decisions despite a source append."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import decisions
import mode_migrate as mm
import mode_registry as mr


def test_abort_restores_destination_after_source_append(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: an abort restores an unchanged destination's original bytes while preserving a decisions append at the source.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(_DEC))
    decisions.append(str(source), {
        "id": "before-copy", "dimension": "Test",
        "category": "storage", "action": "skip",
    })
    destination = Path(_put(w.d_gl(_DEC), '{"previousDecision": true}\n'))
    previous = destination.read_bytes()
    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == mm.ROLE_CARRY
        for entry in migration.files
    )
    appended = []
    real_copy = mm._copy_bytes

    def append_after_carry(src, dst):
        real_copy(src, dst)
        if (
            os.fspath(src) == str(source)
            and os.fspath(dst) == str(destination)
            and not appended
        ):
            decisions.append(str(source), {
                "id": "after-copy", "dimension": "Test",
                "category": "storage", "action": "guidance",
            })
            appended.append(source.read_bytes())

    # Pinned interleaving: append after the real carry copy and before a refused registry commit; other writer timings and process schedules are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", append_after_carry)
    monkeypatch.setattr(mm, "_commit_registry", lambda *args, **kwargs: False)
    assert mm.execute(migration, root=w.root) == {"status": "blocked"}
    assert len(appended) == 1
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == appended[0]
    assert {
        record["id"] for record in decisions.load_store(str(source))["records"]
    } == {"before-copy", "after-copy"}
    assert destination.read_bytes() == previous, "abort discarded the original destination decisions"
