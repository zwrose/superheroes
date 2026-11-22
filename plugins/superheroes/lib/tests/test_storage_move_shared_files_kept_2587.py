"""Owner ruling 690 b: a storage move copies the files other sessions write and never deletes them."""
import os
from pathlib import Path

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put
import decisions
import mode_migrate as mm
import mode_registry as mr


def test_a_decision_appended_after_the_final_compare_survives_at_the_original(
        tmp_path, isolated_default_store_root, monkeypatch):
    # axis: a write landing after the move's last compare (session 8's s3 window) survives at the original, which stays as a named leftover
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("review-crew.md"), "## Focus hints\n- current\n")
    source = Path(w.inrepo(_DEC))
    decisions.append(str(source), {"id": "before", "dimension": "Test", "category": "storage", "action": "skip"})
    real_settled = mm._settled

    def append_after_compare(f):
        ok = real_settled(f)
        if f["src"] == str(source):
            decisions.append(str(source), {"id": "late", "dimension": "Test", "category": "storage",
                                           "action": "guidance"})
        return ok

    # Pinned interleaving: append right after the source's final compare, before any delete decision.
    monkeypatch.setattr(mm, "_settled", append_after_compare)
    result = mm.execute(w.plan(mr.GLOBAL), root=w.root)
    assert result["status"] == "done-with-leftovers"
    assert str(source) in result["undeleted"], "the shared original is not named as a leftover"
    assert {r["id"] for r in decisions.load_store(str(source))["records"]} == {"before", "late"}
    assert {r["id"] for r in decisions.load_store(w.d_gl(_DEC))["records"]} >= {"before"}
