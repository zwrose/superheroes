"""A late artifact veto keeps legacy test-pilot siblings together."""
import os
from pathlib import Path

from test_leftover_settings_2587 import W, _CORE, _PILOT, _put
import mode_migrate as mm
import mode_registry as mr
import store


def test_late_sibling_artifact_does_not_change_the_selected_profile(
    tmp_path, isolated_default_store_root, monkeypatch
):
    # axis: an artifact gained by either legacy sibling during copying must not cause the selected sibling to be deleted while the other remains.
    w = W(tmp_path, os.path.realpath(isolated_default_store_root))
    w.register(mr.IN_REPO)
    core = _put(w.d_in("core.md"), _CORE)
    _put(w.d_in("test-pilot.md"), _PILOT)
    active_text = _PILOT + "\n# Selected in-repo profile\n"
    active = _put(w.inrepo("test-pilot", "profile.md"), active_text)
    sibling = _put(
        os.path.join(w.entry(w.tr), "profile.md"),
        _PILOT + "\n# Other legacy profile\n",
    )
    before = store.resolve(w.cwd, w.tr)
    assert before["exists"] and before["refusal"] is None
    assert before["profile"] == active
    migration = mm.plan(
        w.cwd, mr.GLOBAL, root=w.root, owner_authorized=True,
        review_root=w.rr, test_pilot_root=w.tr,
    )
    planned = {
        entry["src"] for entry in migration.files
        if entry.get("role") == mm.ROLE_SET_ASIDE
        and entry.get("family") == "test-pilot"
    }
    assert planned == {active, sibling}
    saved = Path(sibling).parent / "blocks" / "saved-during-copy.md"
    deliveries = []
    real_copy = mm._copy_bytes

    def save_during_copy(src, dst):
        real_copy(src, dst)
        if os.fspath(src) == core and not deliveries:
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text("saved block\n", encoding="utf-8")
            deliveries.append(str(saved))

    # Pinned interleaving: the sibling gains a block after core.md is copied, after the locked plan recheck and before source deletion; other copy timings and multi-process scheduling are not sampled.
    monkeypatch.setattr(mm, "_copy_bytes", save_during_copy)
    result = mm.execute(migration, root=w.root)
    assert deliveries == [str(saved)]
    assert result["status"] in {"done", "done-with-leftovers", "blocked"}
    after = store.resolve(w.cwd, w.tr)
    assert after["exists"] and after["refusal"] is None
    assert after["profile"] == before["profile"], "partial sibling retirement changed the selected profile"
    assert after["blocks_dir"] == before["blocks_dir"]
    assert Path(active).read_bytes() == active_text.encode("utf-8")
    assert saved.read_text(encoding="utf-8") == "saved block\n"
