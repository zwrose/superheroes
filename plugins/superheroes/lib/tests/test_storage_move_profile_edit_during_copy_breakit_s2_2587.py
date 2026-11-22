"""Storage flips preserve profile edits saved after their archive copy."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr


def test_flip_preserves_profile_saved_after_archive_copy(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: a profile edit saved after its archive copy must survive the storage flip.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    profile = Path(_put(w.inrepo("review-profile.md"), "## Threat model\nold\n"))
    original = profile.read_bytes()
    latest = b"## Threat model\nthe owner saved this during the move\n"
    migration = w.plan(mr.GLOBAL)
    entries = [
        entry for entry in migration.files
        if entry["src"] == str(profile)
        and entry.get("role") == mm.ROLE_SET_ASIDE
    ]
    assert len(entries) == 1
    archived = Path(entries[0]["dst"])
    saves = []
    real_commit = mm._commit_registry

    def save_before_commit(*args, **kwargs):
        assert archived.read_bytes() == original
        profile.write_bytes(latest)
        saves.append(str(profile))
        return real_commit(*args, **kwargs)

    # Pinned interleaving: an editor that does not take config_lock saves immediately
    # before registry commit, after the archive copy; other save timings are not sampled.
    monkeypatch.setattr(mm, "_commit_registry", save_before_commit)
    result = mm.execute(migration, root=w.root)
    assert saves == [str(profile)]
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    assert any(
        path.is_file() and path.read_bytes() == latest
        for path in (profile, archived)
    ), "storage flip discarded the profile edit saved after its archive copy"
