"""A move never starts over an interrupted one, and a shared file is never re-copied after the commit."""
import os
from pathlib import Path

import pytest

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import decisions
import mode_migrate as mm
import mode_registry as mr


def _world(tmp_path, root):
    w = W(tmp_path, os.path.realpath(root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    return w


def _ids(path):
    return {record["id"] for record in decisions.load_store(str(path))["records"]}


def _save(path, record_id):
    decisions.append(str(path), {"id": record_id, "dimension": "Test",
                                 "category": "storage", "action": "guidance"})


def test_execute_refuses_while_an_interrupted_move_is_outstanding(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: vet 1008 P5: a crash after copying over an existing destination; a fresh plan's execute
    # refuses with recover-first and changes nothing; after recover the destination holds its prior bytes.
    w = _world(tmp_path, isolated_default_store_root)
    destination_before = b'{"previousDestinationDecision": "keep"}\n'
    source = Path(_put(w.inrepo(_DEC), '{"sourceDecision": "moving"}\n'))
    destination = Path(_put(w.d_gl(_DEC), destination_before.decode("utf-8")))
    real_copy = mm._copy_bytes

    def crash_after_carry(src, dst):
        real_copy(src, dst)
        if os.fspath(src) == str(source):
            raise OSError("simulated crash after the carry copy")

    with monkeypatch.context() as patch:
        patch.setattr(mm, "_copy_bytes", crash_after_carry)
        with pytest.raises(OSError, match="simulated crash"):
            mm.execute(w.plan(mr.GLOBAL), root=w.root)
    assert destination.read_bytes() == source.read_bytes()
    assert mm.active_journal(w.cwd, root=w.root) is not None

    interrupted = destination.read_bytes()
    assert mm.execute(w.plan(mr.GLOBAL), root=w.root) == {"status": "blocked", "reason": "recover-first"}
    assert destination.read_bytes() == interrupted
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.IN_REPO
    assert mm.active_journal(w.cwd, root=w.root) is not None

    assert mm.recover(w.cwd, root=w.root)["status"] == "recovered"
    assert destination.read_bytes() == destination_before


def test_execute_runs_when_no_journal_is_outstanding(tmp_path, isolated_default_store_root):
    # axis: the healthy case: with no journal at the store, the move runs to its commit
    w = _world(tmp_path, isolated_default_store_root)
    _put(w.inrepo(_DEC), '{"sourceDecision": "moving"}\n')
    assert mm.active_journal(w.cwd, root=w.root) is None
    result = mm.execute(w.plan(mr.GLOBAL), root=w.root)
    assert result["status"] in {"done", "done-with-leftovers"}
    assert mr.read_registry(w.cwd, w.root)["storageMode"] == mr.GLOBAL


def test_saves_at_both_places_after_the_commit_survive(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: vet 1008 P6: after the commit, one save at the old place and one at the new place; both survive
    w = _world(tmp_path, isolated_default_store_root)
    source = Path(w.inrepo(_DEC))
    destination = Path(w.d_gl(_DEC))
    _save(source, "before-flip")
    migration = w.plan(mr.GLOBAL)
    real_commit, real_copy = mm._commit_registry, mm._copy_bytes
    state = {"committed": False, "new_saved": False}

    def commit_then_save_old(*args, **kwargs):
        ok = real_commit(*args, **kwargs)
        if ok:
            state["committed"] = True
            _save(source, "old-place")
        return ok

    def save_new_before_late_copy(src, dst):
        # a save at the new place lands just before any copy the move makes after its commit
        if state["committed"] and os.fspath(src) == str(source) and not state["new_saved"]:
            _save(destination, "new-place")
            state["new_saved"] = True
        real_copy(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(mm, "_commit_registry", commit_then_save_old)
        patch.setattr(mm, "_copy_bytes", save_new_before_late_copy)
        result = mm.execute(migration, root=w.root)
    if not state["new_saved"]:
        _save(destination, "new-place")
    assert result["status"] in {"done", "done-with-leftovers"}
    assert state["committed"]
    assert "old-place" in _ids(source)
    assert "new-place" in _ids(destination)
