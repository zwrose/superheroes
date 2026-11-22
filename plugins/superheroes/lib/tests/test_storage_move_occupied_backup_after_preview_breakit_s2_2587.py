"""#2587: a storage flip preserves a backup occupied after its preview."""
import json
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr


def test_flip_refuses_a_backup_occupied_after_preview(
        tmp_path, isolated_default_store_root):
    # axis: an occupied set-aside folder invalidates the preview; its existing archive and restore manifest are never overwritten.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(_put(w.inrepo("review-profile.md"), "## Threat model\ncurrent legacy settings\n"))
    source_bytes = source.read_bytes()
    migration = w.plan(mr.GLOBAL)
    assert not migration.blocked
    shown = mm.preview(migration)
    assert len(shown["setAside"]) == 1
    archive = Path(shown["setAside"][0]["to"])
    assert not archive.parent.exists()

    # Pinned interleaving: another operation occupies the folder after preview and before execute; writes during copying are not sampled.
    archive.parent.mkdir(parents=True)
    archived_bytes = b"previously retired settings\n"
    archive.write_bytes(archived_bytes)
    previous_source = tmp_path / "previous-checkout" / ".claude" / "review-profile.md"
    previous_manifest = {
        "schema": 1,
        "mode": mr.IN_REPO,
        "entries": [{
            "from": str(previous_source),
            "to": str(archive),
            "family": "review-crew",
        }],
    }
    manifest = archive.parent / "retired.json"
    manifest_bytes = json.dumps(previous_manifest).encode("utf-8")
    manifest.write_bytes(manifest_bytes)

    result = mm.execute(migration, root=w.root)

    assert manifest.read_bytes() == manifest_bytes, "flip replaced an existing backup's restore manifest"
    assert archive.read_bytes() == archived_bytes, "flip replaced an existing archived settings file"
    assert result["status"] == "blocked"
    assert result.get("reason", "").startswith("plan-changed")
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == source_bytes
