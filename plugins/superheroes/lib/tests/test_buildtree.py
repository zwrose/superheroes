# plugins/superheroes/lib/tests/test_buildtree.py
import os
import buildtree


def test_managed_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt"))
    assert buildtree.managed_root() == os.path.realpath(str(tmp_path / "wt"))


def test_managed_root_default(monkeypatch):
    monkeypatch.delenv("SUPERHEROES_WORKTREES_ROOT", raising=False)
    assert buildtree.managed_root().endswith("/.superheroes-worktrees")


def test_branch_name():
    assert buildtree.branch_name("wi-abc123", "deadbeefdeadbeef") == \
        "superheroes/wi-abc123-deadbeefdeadbeef"


def test_worktree_path_deterministic_and_namespaced(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "wt"))
    monkeypatch.setattr(buildtree.control_plane, "checkout_key", lambda cwd: "KEY")
    p = buildtree.worktree_path("/repo", "wi-abc123", "deadbeefdeadbeef")
    assert p == os.path.join(os.path.realpath(str(tmp_path / "wt")),
                             "KEY", "wi-abc123-deadbeefdeadbeef")
    # distinct checkout-key -> distinct path (FR-1 no-collision)
    monkeypatch.setattr(buildtree.control_plane, "checkout_key", lambda cwd: "KEY2")
    assert buildtree.worktree_path("/repo", "wi-abc123", "deadbeefdeadbeef") != p
# append to plugins/superheroes/lib/tests/test_buildtree.py
import pytest


def _entry(path="/wt/a", wi="wi-a", ch="h1"):
    return {"workItem": wi, "contentHash": ch,
            "branch": buildtree.branch_name(wi, ch), "path": path}


def test_record_missing_reads_empty(tmp_path):
    assert buildtree.record_read(str(tmp_path / "nope.json")) == []


def test_record_garbled_reads_empty(tmp_path):
    f = tmp_path / "worktrees.json"
    f.write_text("{ not json")
    assert buildtree.record_read(str(f)) == []


def test_record_add_is_idempotent_by_path(tmp_path):
    f = str(tmp_path / "worktrees.json")
    buildtree.record_add(f, _entry(path="/wt/a"))
    buildtree.record_add(f, _entry(path="/wt/a"))      # same path -> replace, not dup
    buildtree.record_add(f, _entry(path="/wt/b"))
    paths = sorted(e["path"] for e in buildtree.record_read(f))
    assert paths == ["/wt/a", "/wt/b"]


def test_record_remove_by_path(tmp_path):
    f = str(tmp_path / "worktrees.json")
    buildtree.record_add(f, _entry(path="/wt/a"))
    buildtree.record_add(f, _entry(path="/wt/b"))
    buildtree.record_remove(f, "/wt/a")
    assert [e["path"] for e in buildtree.record_read(f)] == ["/wt/b"]


def test_record_unknown_schema_raises(tmp_path):
    f = tmp_path / "worktrees.json"
    f.write_text('{"schemaVersion": 999, "worktrees": []}')
    with pytest.raises(buildtree.RecordSchemaError):
        buildtree.record_read(str(f))
