"""#2587 layer 1, vet 1002's layouts: a storage move never loses the review decisions read now (A1-A3),
and keeps a legacy profile whose core.md is missing or empty (B1)."""
import os

import pytest

from test_storage_move_settings_2587 import W, _CORE, _DEC, _put, _text
import mode_migrate as mm
import mode_registry as mr
import review_store


@pytest.fixture
def w(tmp_path, isolated_default_store_root):
    return W(tmp_path, os.path.realpath(isolated_default_store_root))


def _read_now(w):
    path = review_store.resolve(w.cwd, "decisions", legacy_root=w.rr, registry_root=w.root)["path"]
    return path, (_text(path) if path and os.path.isfile(path) else None)


def _layout(w, case):
    profile = "## Threat model\nlegacy\n"
    if case == "A1":
        # registry global, only core.md in the repo, an in-repo legacy profile, a global review layer;
        # the read copy is the in-repo decisions file, a stale copy sits in config
        w.register(mr.GLOBAL)
        _put(w.d_in("core.md"), _CORE)
        _put(w.inrepo("review-profile.md"), profile)
        _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
        _put(w.inrepo(_DEC), '{"read": true}\n')
        _put(w.d_gl(_DEC), '{"stale": true}\n')
        return mr.IN_REPO
    # A2/A3: the mirror, registry in-repo, only core.md globally, the global review layer read, an in-repo
    # legacy profile; the read copy is config's (A2) or the legacy store entry's (A3), a stale copy in the repo
    w.register(mr.IN_REPO)
    entry = w.entry(w.rr)
    _put(w.d_gl("core.md"), _CORE)
    _put(w.inrepo("review-profile.md"), profile)
    _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
    _put(w.inrepo(_DEC), '{"in-repo": true}\n')
    if case == "A2":
        _put(w.d_gl(_DEC), '{"config": true}\n')
    else:
        _put(os.path.join(entry, _DEC), '{"entry": true}\n')
    return mr.GLOBAL


@pytest.mark.parametrize("case", ["A1", "A2", "A3"])
def test_a_move_never_loses_the_decisions_read_now(w, case):
    # axis: the decisions read before the flip are still what reviews read after it, byte for byte (every copy differs)
    target = _layout(w, case)
    _, before = _read_now(w)
    assert before is not None
    assert mm.execute(w.plan(target), root=w.root) == {"status": "done"}
    _, after = _read_now(w)
    assert after == before


@pytest.mark.parametrize("core", ["absent", "empty"])
def test_a_legacy_profile_without_a_populated_core_stays(w, core):
    # axis: a legacy review profile whose core.md is missing or has empty facts stays in place in a flip, as find's gate
    w.register(mr.IN_REPO)
    if core == "empty":
        _put(w.d_in("core.md"), "")
    _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
    legacy = _put(w.inrepo("review-profile.md"), "## Threat model\nlegacy\n")
    pv = mm.preview(w.enumerate(mr.GLOBAL))
    assert legacy not in [a["from"] for a in pv["setAside"]]
    assert (legacy, "only-copy") in [(e["path"], e["why"]) for e in pv["leftInPlace"]]
