# plugins/superheroes/lib/tests/test_duplication_skip_item_2500.py
"""Calibration item 20 (duplicationSkip): the set path, and the never-raising, read-only reader."""
import importlib.util
import os
import subprocess
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


PC = _load("project_config")
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
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    CM.write(repo, dict(_CORE_FACTS), "confirmed", root=store, now="2026-06-26")
    return repo, store


def _bare_repo(tmp_path):
    """A git repo with no core.md anywhere: no calibration."""
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    return repo, store


def _snapshot(directory):
    seen = {}
    for base, _dirs, files in os.walk(directory):
        for name in files:
            full = os.path.join(base, name)
            seen[full] = os.stat(full).st_mtime_ns
    return seen


def test_registry_carries_item_20_duplication_skip():
    item = next(entry for entry in PC.ITEMS if entry["slug"] == "duplicationSkip")
    assert item["number"] == 20 and item["name"] == "Duplication skip trees"
    assert item["shape"] == "globList" and item["plugin_default"] is None
    assert item["home"] == PC.HOME_PROJECT_CONFIGURATION
    assert PC.DUPLICATION_SKIP_SLUG == "duplicationSkip"


def test_set_then_get_round_trip(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.set_item(repo, "duplicationSkip", ["snapshots/**"], root=store)
    assert got["action"] == "written"
    read_back = PC.get_item(repo, "duplicationSkip", root=store)
    assert read_back["effective"] == ["snapshots/**"]
    assert read_back["source"] == "stamped"


@pytest.mark.parametrize(
    "bad",
    ["snapshots/**", [" "], [3], ["/abs/**"]],
    ids=["not-a-list", "blank-entry", "non-string-entry", "absolute-entry"],
)
def test_set_refuses_a_malformed_value(tmp_path, bad):
    # axis: a malformed glob list is refused at set, and nothing is stored
    repo, store = _setup_repo(tmp_path)
    got = PC.set_item(repo, "duplicationSkip", bad, root=store)
    assert got["action"] == "refused"
    assert got["reason"] == "malformed-value"
    assert PC.get_item(repo, "duplicationSkip", root=store)["source"] == "unset"


def test_reader_with_no_core_md_skips_nothing(tmp_path):
    repo, store = _bare_repo(tmp_path)
    got = PC.read_duplication_skip(repo, root=store)
    assert got == {"globs": [], "reason": None, "detail": None}


def test_reader_with_item_unset_skips_nothing(tmp_path):
    repo, store = _setup_repo(tmp_path)
    got = PC.read_duplication_skip(repo, root=store)
    assert got == {"globs": [], "reason": None, "detail": None}


def test_reader_returns_the_stored_globs_as_a_copy(tmp_path):
    repo, store = _setup_repo(tmp_path)
    stored = ["snapshots/**", "styles/generated/*.css"]
    assert PC.set_item(repo, "duplicationSkip", stored, root=store)["action"] == "written"
    got = PC.read_duplication_skip(repo, root=store)
    assert got == {"globs": stored, "reason": None, "detail": None}
    got["globs"].append("mutated/**")
    assert PC.read_duplication_skip(repo, root=store)["globs"] == stored


def test_reader_names_a_malformed_stored_value(tmp_path):
    # axis: a malformed stored value skips nothing and names duplication-skip-malformed
    repo, store = _setup_repo(tmp_path)
    CM.write_project_config(repo, {"duplicationSkip": "not-a-list"}, root=store)
    got = PC.read_duplication_skip(repo, root=store)
    assert got["globs"] == []
    assert got["reason"] == "duplication-skip-malformed"
    assert isinstance(got["detail"], str) and got["detail"]


def test_reader_names_an_unreadable_core_md(tmp_path):
    # axis: an unparseable core.md skips nothing and names duplication-skip-unreadable
    repo, store = _setup_repo(tmp_path)
    PC.set_item(repo, "duplicationSkip", ["snapshots/**"], root=store)
    with open(CM.core_path(repo, store), "w") as fh:
        fh.write("not core\n")
    got = PC.read_duplication_skip(repo, root=store)
    assert got["globs"] == []
    assert got["reason"] == "duplication-skip-unreadable"
    assert isinstance(got["detail"], str) and got["detail"]


def test_reader_never_raises_when_the_read_raises(tmp_path, monkeypatch):
    # axis: the reader never raises, whatever core_md.read does
    repo, store = _setup_repo(tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("read failed")

    monkeypatch.setattr(PC.core_md, "read", _boom)
    got = PC.read_duplication_skip(repo, root=store)
    assert got["globs"] == []
    assert got["reason"] == "duplication-skip-unreadable"
    assert "read failed" in got["detail"]


def test_reader_names_an_unavailable_repo_root(tmp_path, monkeypatch):
    repo, store = _setup_repo(tmp_path)

    def _no_root(*a, **k):
        raise PC.core_md.RepoRootUnavailable("no repo root")

    monkeypatch.setattr(PC.core_md, "_size_exclude_core_path", _no_root)
    got = PC.read_duplication_skip(repo, root=store)
    assert got["globs"] == []
    assert got["reason"] == "duplication-skip-unreadable"


def test_reader_writes_nothing(tmp_path):
    repo, store = _bare_repo(tmp_path)
    before = _snapshot(store)
    PC.read_duplication_skip(repo, root=store)
    after = _snapshot(store)
    assert before == after
    assert not os.path.exists(os.path.join(repo, ".claude", "superheroes", "core.md"))
