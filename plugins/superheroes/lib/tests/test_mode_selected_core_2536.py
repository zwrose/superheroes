"""#2536 WO-1 — the dispatch resolver reads the core.md the storage mode selects.

When both core.md candidates (in-repo and global) are regular files, ``calibration_resolve.resolve(...)["dispatch_core"]``
is the one the recorded storage mode selects, whichever resolve branch won. In every other case it is what it was before.
No reader is stubbed except where a test says so: the fixtures write real files under a temp ``HOME``.

Bite-proof record: wo1_2536_mode_selected_core
"""
import hashlib
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import calibration_read  # noqa: E402
import calibration_resolve  # noqa: E402
import core_md  # noqa: E402
import mode_registry  # noqa: E402

_GLOBAL_VERIFY = "global-verify"
_STALE_VERIFY = "stale-verify"
_LAYER_TEXT = "# Review crew\n\nPolicy version: 3\n\nThe layer rules for this project.\n"


def _facts(verify):
    return {"verifyCommand": verify, "stackTags": ["node"], "threatModel": "single-user",
            "patterns": "- x: a.ts:1", "enginePreferences": {"reviewer": "codex"}}


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _put_core(path, verify):
    _put(path, core_md.render_core(_facts(verify), "confirmed", "2026-06-26", "2026-06-26"))


def _global_core(repo):
    return os.path.join(mode_registry.project_store_dir(repo), "config", "core.md")


def _global_layer(repo):
    return os.path.join(mode_registry.project_store_dir(repo), "config", "review-crew.md")


def _inrepo_core(repo):
    return os.path.join(repo, core_md.in_repo_core_rel_path())


def _inrepo_layer(repo):
    return os.path.join(repo, ".claude", "superheroes", "review-crew.md")


def _legacy_profile(repo):
    return os.path.join(repo, mode_registry._HERO_LEGACY_INREPO["review-crew"])


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _dispatch_core(repo):
    return calibration_resolve.resolve(repo)["dispatch_core"]


def _core_stamp(repo, path):
    entries = calibration_read.stamp(repo, "Read the core calibration at %s before you start." % path)
    return [e for e in entries if e["label"] == calibration_read.LABEL_CORE]


@pytest.fixture
def unrecorded(tmp_path, monkeypatch):
    """A git repo under a temp HOME with no calibration file and no mode registry anywhere."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for var in ("SUPERHEROES_STORE_ROOT", "WORKHORSE_STORE_ROOT", "CLAUDE_CODE_REMOTE"):
        monkeypatch.delenv(var, raising=False)
    path = str(tmp_path / "repo")
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True)
    return path


@pytest.fixture
def bare(unrecorded):
    """The unrecorded repo with the mode recorded as global."""
    assert mode_registry.write_registry(unrecorded, mode_registry.GLOBAL, "rk") is not None
    return unrecorded


@pytest.fixture
def repo(bare):
    """The bare repo plus a global core (global-verify), a stale in-repo core (stale-verify) and the in-repo layer
    beside it, so the in-repo layer wins the resolve branch and its core is the one the old code returned."""
    _put_core(_global_core(bare), _GLOBAL_VERIFY)
    _put_core(_inrepo_core(bare), _STALE_VERIFY)
    _put(_inrepo_layer(bare), _LAYER_TEXT)
    return bare


def _record_mode(repo, mode):
    assert mode_registry.write_registry(repo, mode, "rk", allow_migration=True) is not None


def test_both_cores_global_mode_dispatches_the_global_core(repo):
    # axis: with both cores regular files and the mode global, dispatch_core is the global core, not the in-repo one
    registry = mode_registry.registry_path(repo)
    before = _bytes(registry)
    info = calibration_resolve.resolve(repo)
    assert info["layout"] == "unified" and info["location"] == mode_registry.IN_REPO  # the in-repo layer won the branch
    assert info["core_path"] == _inrepo_core(repo)  # and the branch's own core_path is left alone
    assert info["dispatch_core"] == _global_core(repo)
    assert _bytes(registry) == before  # nothing was written
    # setup's $CORE and its verify read agree
    read_verify = core_md.read(repo, persist_backfill=False)["verifyCommand"]
    with open(info["dispatch_core"], encoding="utf-8") as fh:
        assert core_md.parse_core(fh.read())["verifyCommand"] == read_verify == _GLOBAL_VERIFY
    # the driver's stamp and path resolution name the same core
    assert calibration_read.resolved_paths(repo)[0] == _global_core(repo)
    got = _core_stamp(repo, _global_core(repo))
    assert len(got) == 1 and got[0]["path"] == _global_core(repo) and got[0]["sha256"] == _sha(_global_core(repo))


def test_both_cores_in_repo_mode_dispatches_the_in_repo_core(repo):
    # axis: with both cores regular files and the mode in-repo, dispatch_core is the in-repo core, not the global one
    _record_mode(repo, mode_registry.IN_REPO)
    assert _dispatch_core(repo) == _inrepo_core(repo)
    assert calibration_read.resolved_paths(repo)[0] == _inrepo_core(repo)


def test_mode_is_read_without_writing_a_registry(unrecorded):
    # axis: the mode is read with persist_backfill=False, so evidence alone never writes a registry
    _put_core(_global_core(unrecorded), _GLOBAL_VERIFY)
    _put_core(_inrepo_core(unrecorded), _STALE_VERIFY)
    _put(_inrepo_layer(unrecorded), _LAYER_TEXT)
    assert not os.path.exists(mode_registry.registry_path(unrecorded))
    assert _dispatch_core(unrecorded) == _inrepo_core(unrecorded)  # the in-repo layer is the evidence: mode in-repo
    assert not os.path.exists(mode_registry.registry_path(unrecorded))


def test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core(bare):
    # axis: the mode-selected core wins whichever resolve branch won, the legacy-profile branch included
    _put_core(_global_core(bare), _GLOBAL_VERIFY)
    _put_core(_inrepo_core(bare), _STALE_VERIFY)
    _put(_legacy_profile(bare), "# legacy review profile\n")
    info = calibration_resolve.resolve(bare)
    assert info["layout"] == "legacy" and info["legacy_path"] == _legacy_profile(bare)  # the legacy branch won
    assert info["core_path"] is None  # so today's dispatch_core would be the legacy profile
    assert info["dispatch_core"] == _global_core(bare)
    assert calibration_read.resolved_paths(bare)[0] == _global_core(bare)
    got = _core_stamp(bare, _global_core(bare))
    assert len(got) == 1 and got[0]["path"] == _global_core(bare) and got[0]["sha256"] == _sha(_global_core(bare))


def test_a_dangling_in_repo_core_is_not_a_core_and_dispatch_keeps_todays_value(bare):
    # axis: only a regular file counts as a candidate, so a dangling symlink leaves dispatch_core as it was
    _put_core(_global_core(bare), _GLOBAL_VERIFY)
    _put(_global_layer(bare), _LAYER_TEXT)
    os.makedirs(os.path.dirname(_inrepo_core(bare)), exist_ok=True)
    os.symlink(os.path.join(bare, "no-such-core.md"), _inrepo_core(bare))
    assert os.path.lexists(_inrepo_core(bare)) and not os.path.isfile(_inrepo_core(bare))
    _record_mode(bare, mode_registry.IN_REPO)  # the mode that would select the dangling side
    assert _dispatch_core(bare) == _global_core(bare)


def test_a_dangling_global_core_is_not_a_core_and_dispatch_keeps_todays_value(bare):
    # axis: only a regular file counts as a candidate, so a dangling symlink leaves dispatch_core as it was
    _put_core(_inrepo_core(bare), _STALE_VERIFY)
    _put(_inrepo_layer(bare), _LAYER_TEXT)
    os.makedirs(os.path.dirname(_global_core(bare)), exist_ok=True)
    os.symlink(os.path.join(bare, "no-such-core.md"), _global_core(bare))
    assert os.path.lexists(_global_core(bare)) and not os.path.isfile(_global_core(bare))
    assert _dispatch_core(bare) == _inrepo_core(bare)  # mode global would select the dangling side


def test_only_an_in_repo_core_dispatches_it_as_before(bare):
    _put_core(_inrepo_core(bare), _STALE_VERIFY)
    _put(_inrepo_layer(bare), _LAYER_TEXT)
    assert not os.path.lexists(_global_core(bare))
    assert _dispatch_core(bare) == _inrepo_core(bare)
    got = _core_stamp(bare, _inrepo_core(bare))
    assert len(got) == 1 and got[0]["path"] == _inrepo_core(bare) and got[0]["sha256"] == _sha(_inrepo_core(bare))


def test_only_a_global_core_dispatches_it_as_before(bare):
    _put_core(_global_core(bare), _GLOBAL_VERIFY)
    _put(_global_layer(bare), _LAYER_TEXT)
    assert not os.path.lexists(_inrepo_core(bare))
    assert _dispatch_core(bare) == _global_core(bare)
    got = _core_stamp(bare, _global_core(bare))
    assert len(got) == 1 and got[0]["path"] == _global_core(bare) and got[0]["sha256"] == _sha(_global_core(bare))


def test_no_core_dispatches_what_it_did_before(bare):
    assert _dispatch_core(bare) is None
    _put(_inrepo_layer(bare), _LAYER_TEXT)  # a layer alone: today's dispatch_core falls back to the layer
    assert _dispatch_core(bare) == _inrepo_layer(bare)


def test_a_candidate_computation_that_raises_leaves_todays_value(repo, monkeypatch):
    # axis: a failure computing the candidates never reaches the caller and never changes dispatch_core
    def boom(cwd, root=None):
        raise core_md.RepoRootUnavailable("git could not be run", git_status=None)
    monkeypatch.setattr(core_md, "_core_candidates", boom)
    info = calibration_resolve.resolve(repo)
    assert info["dispatch_core"] == _inrepo_core(repo)  # today's value: the core beside the winning in-repo layer


def test_a_mode_read_that_raises_leaves_todays_value(repo, monkeypatch):
    # axis: a failure reading the mode never reaches the caller and never changes dispatch_core
    def boom(cwd, root=None, *, persist_backfill=True):
        raise mode_registry.UnknownSchemaVersion("registry newer than this plugin")
    monkeypatch.setattr(mode_registry, "resolve", boom)
    assert _dispatch_core(repo) == _inrepo_core(repo)
