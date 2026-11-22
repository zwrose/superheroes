"""Storage flips preserve destination edits saved after their snapshot."""
import os
from pathlib import Path

from test_leftover_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr
import review_store


def test_destination_saved_after_snapshot_keeps_its_latest_bytes(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: a destination saved after its snapshot survives the carry, either in place or in a named backup.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    name = review_store.FILENAMES["decisions"]
    source = Path(_put(w.inrepo(name), '{"sourceDecision": true}\n'))
    original = b'{"previousDecision": true}\n'
    destination = Path(_put(w.d_gl(name), original.decode("utf-8")))
    latest = b'{"ownerSavedDuringMove": true}\n'
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
    saves = []
    real_copy = mm._copy_bytes

    def save_after_snapshot(src, dst):
        real_copy(src, dst)
        if (
            os.fspath(src) == str(destination)
            and Path(dst).parent.name == mm._SNAPSHOT_DIRNAME
            and not saves
        ):
            assert Path(dst).read_bytes() == original
            destination.write_bytes(latest)
            saves.append(str(destination))

    # Pinned interleaving: an editor saves immediately after the destination snapshot, before its carry; other save timings and process schedules are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", save_after_snapshot)
    result = mm.execute(migration, root=w.root)
    assert saves == [str(destination)]
    candidates = [destination] + [
        Path(entry["backup"])
        for entry in result.get("overwritten", [])
        if entry["path"] == str(destination)
    ]
    assert any(
        path.is_file() and path.read_bytes() == latest
        for path in candidates
    ), "storage flip discarded the destination edit saved after its snapshot"
