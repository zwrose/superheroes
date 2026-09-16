# plugins/superheroes/lib/tests/test_core_md_profile_absent.py
"""Conformance: gate_config_profile_is_absent absent-versus-unreadable distinction."""
import importlib.util
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}


def _setup_repo(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


# --- fail-closed edges ---


def test_edge1_profile_absent(tmp_path):
    # axis: absent-versus-unreadable — wo_g_1276_profile-absent
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    assert CM.gate_config_profile_is_absent(repo, root=store) is True


def test_edge2_profile_unreadable(tmp_path):
    # axis: absent-versus-unreadable — wo_g_1276_profile-absent
    repo, store = _setup_repo(tmp_path)
    open(CM.core_path(repo, store), "w").write("not core\n")
    assert CM.gate_config_profile_is_absent(repo, root=store) is False


def test_edge3_repo_root_unavailable(tmp_path, monkeypatch):
    # axis: absent-versus-unreadable — wo_g_1276_profile-absent
    def _raise(_cwd, _root=None):
        raise CM.RepoRootUnavailable("synthetic")

    monkeypatch.setattr(CM, "core_path", _raise)
    assert CM.gate_config_profile_is_absent(str(tmp_path), root=str(tmp_path / "store")) is False
