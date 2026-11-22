"""An aborted decisions carry preserves the destination's symbolic link."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _put
import mode_migrate as mm
import mode_registry as mr
import review_store
import store_core


@pytest.mark.parametrize("referent_exists", [True, False],
                         ids=["live-link", "dangling-link"])
def test_aborted_carry_preserves_destination_link(
        tmp_path, isolated_default_store_root, monkeypatch, referent_exists):
    # axis: a refused registry commit preserves the original destination link and target, whether its referent exists or is absent.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- local\n")
    name = review_store.FILENAMES["decisions"]
    source = Path(_put(w.inrepo(name), '{"source": true}\n'))
    source_before = source.read_bytes()
    destination = Path(w.d_gl(name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    referent = tmp_path / "linked-decisions.json"
    referent_before = b'{"previous": true}\n'
    if referent_exists:
        referent.write_bytes(referent_before)
    destination.symlink_to(referent)
    original_link = os.readlink(destination)
    migration = w.plan(mr.GLOBAL)
    registry_path = mr.registry_path(w.cwd, w.root)
    real_write = store_core.atomic_write

    def refuse_registry(path, text, *args, **kwargs):
        if os.fspath(path) == registry_path:
            raise OSError("simulated registry commit failure")
        return real_write(path, text, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(store_core, "atomic_write", refuse_registry)
        assert mm.execute(migration, root=w.root)["status"] == "blocked"

    assert mm.recover(w.cwd, root=w.root)["status"] in {"noop", "recovered"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert source.read_bytes() == source_before
    assert destination.is_symlink(), "rollback replaced the original destination link"
    assert os.readlink(destination) == original_link
    if referent_exists:
        assert referent.read_bytes() == referent_before
    else:
        assert not os.path.lexists(referent)
