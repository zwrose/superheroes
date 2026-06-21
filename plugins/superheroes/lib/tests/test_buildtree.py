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
# append to plugins/superheroes/lib/tests/test_buildtree.py
def test_recognize_union():
    assert buildtree.recognize(registered=True, on_record=False) is True   # crash-orphan
    assert buildtree.recognize(registered=False, on_record=True) is True    # branch-less
    assert buildtree.recognize(registered=True, on_record=True) is True
    assert buildtree.recognize(registered=False, on_record=False) is False  # owner dir
# append to plugins/superheroes/lib/tests/test_buildtree.py
def test_reap_decision_dirty_wins_over_every_tier():
    for pr in ("merged", "closed", "open", "unknown"):
        assert buildtree.reap_decision(pr, dirty=True, branch_deletable=True) == \
            buildtree.PRESERVE_NOTIFY


def test_reap_decision_merged_tier():
    assert buildtree.reap_decision("merged", dirty=False, branch_deletable=True) == \
        buildtree.REMOVE_AND_DELETE
    # committed-ahead / undeterminable -> preserve the branch (UFR-6)
    assert buildtree.reap_decision("merged", dirty=False, branch_deletable=False) == \
        buildtree.REMOVE_KEEP_BRANCH


def test_reap_decision_closed_and_open_and_unknown():
    assert buildtree.reap_decision("closed", dirty=False, branch_deletable=False) == \
        buildtree.REMOVE_KEEP_BRANCH                         # FR-7
    assert buildtree.reap_decision("open", dirty=False, branch_deletable=False) == \
        buildtree.SKIP_OPEN                                  # UFR-3
    assert buildtree.reap_decision("unknown", dirty=False, branch_deletable=False) == \
        buildtree.GATE_FAILCLOSED                            # UFR-2
# append to plugins/superheroes/lib/tests/test_buildtree.py
def test_branch_deletable_only_when_tip_equals_pr_head():
    assert buildtree.branch_deletable("abc", "abc", determinable=True) is True
    assert buildtree.branch_deletable("abc", "def", determinable=True) is False  # ahead/diverged


def test_branch_deletable_fail_closed():
    assert buildtree.branch_deletable("abc", "abc", determinable=False) is False
    assert buildtree.branch_deletable(None, "abc", determinable=True) is False
    assert buildtree.branch_deletable("abc", None, determinable=True) is False
# append to plugins/superheroes/lib/tests/test_buildtree.py
def test_plan_reconcile_bidirectional():
    disk = [{"path": "/wt/a", "branch": "superheroes/a-h1"},
            {"path": "/wt/c", "branch": "superheroes/c-h3"}]   # c is a crash-orphan
    record = [{"path": "/wt/a", "branch": "superheroes/a-h1"},
              {"path": "/wt/b", "branch": "superheroes/b-h2"}]  # b is branch-less on disk
    out = buildtree.plan_reconcile(disk, record)
    assert [e["path"] for e in out["to_record"]] == ["/wt/c"]           # disk\record
    assert sorted(e["path"] for e in out["candidates"]) == ["/wt/a", "/wt/b", "/wt/c"]
