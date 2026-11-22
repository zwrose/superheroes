"""Vet 1005's R1: a file that appears at a destination after a separate preview run keeps its bytes."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import mode_migrate as mm
import mode_registry as mr


def test_a_destination_written_after_a_separate_preview_keeps_its_bytes_in_the_backup_folder(
        tmp_path, isolated_default_store_root):
    # axis: an overwritten destination's prior bytes go to the dated backup folder and are named, never dropped on success
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source_bytes = b'{"sourceDecision": true}\n'
    _put(w.inrepo(_DEC), source_bytes.decode("utf-8"))
    destination = Path(w.d_gl(_DEC))
    shown = mm.preview(w.plan(mr.GLOBAL))      # the preview command's own run
    assert str(destination) not in shown["overwrites"]
    late_bytes = b'{"writtenAfterThePreview": "keep me"}\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(late_bytes)
    result = mm.execute(w.plan(mr.GLOBAL), root=w.root)   # the execute command re-plans afresh
    assert result["status"] == "done"
    assert destination.read_bytes() == source_bytes
    named = {o["path"]: o["backup"] for o in result.get("overwritten", [])}
    assert str(destination) in named, "the overwritten destination is not named in the result"
    backup = Path(named[str(destination)])
    assert backup.read_bytes() == late_bytes
    assert "leftover-backups" in backup.parts
