"""A refused storage flip preserves an existing decisions symlink."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr
import review_store
import store_core


@pytest.mark.parametrize("link_shape", ["live", "dangling"])
def test_refused_flip_restores_the_decisions_symlink(
    tmp_path, isolated_default_store_root, monkeypatch, link_shape
):
    # axis: registry-write refusal preserves the original decisions symlink, including a dangling one, rather than replacing it with a regular file.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- local\n")
    name = review_store.FILENAMES["decisions"]
    source = Path(_put(w.inrepo(name), '{"source": true}\n'))
    source_before = source.read_bytes()
    target = tmp_path / "linked-decisions.json"
    target_before = b'{"linked": true}\n'
    if link_shape == "live":
        target.write_bytes(target_before)
    destination = Path(w.d_gl(name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(target)
    original_link = os.readlink(destination)
    assert destination.is_symlink()

    migration = w.plan(mr.GLOBAL)
    assert any(
        entry["src"] == str(source)
        and entry["dst"] == str(destination)
        and entry.get("role") == "carry"
        for entry in migration.files
    )
    registry_path = mr.registry_path(w.cwd, w.root)
    real_write = store_core.atomic_write
    attempts = []

    def refuse_registry_write(path, text, *args, **kwargs):
        if os.fspath(path) == registry_path:
            attempts.append(os.fspath(path))
            raise OSError("simulated registry write refusal")
        return real_write(path, text, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", refuse_registry_write)
        assert mm.execute(migration, root=w.root) == {"status": "blocked"}

    assert attempts == [registry_path]
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == source_before
    assert destination.is_symlink(), "refused flip replaced the owner's decisions symlink"
    assert os.readlink(destination) == original_link
    if link_shape == "live":
        assert target.read_bytes() == target_before
    else:
        assert not target.exists()
    assert mm.recover(w.cwd, root=w.root) == {"status": "noop"}
