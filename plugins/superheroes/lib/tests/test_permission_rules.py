import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import permission_rules as pr


def test_real_worktree_interpreter_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    wt = root / "abc123"
    wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'print(1)'", str(wt)) is True


def test_root_itself_is_not_a_strict_descendant(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    root.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'x'", str(root)) is False


def test_parent_hop_earns_nothing(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    (root / "wt").mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    # cwd escapes the root via `..` — realpath resolves it OUT of the root
    escaped = os.path.join(str(root), "wt", "..", "..")
    assert pr.worktree_confined("python3 -c 'x'", escaped) is False


def test_symlink_into_root_is_resolved_and_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    (root / "real").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(root / "real")
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    # a symlink whose realpath IS under root -> confined
    assert pr.worktree_confined("python3 -c 'x'", str(link)) is True


def test_symlink_lookalike_outside_root_earns_nothing(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    root.mkdir(parents=True)
    outside = tmp_path / "evil"
    outside.mkdir()
    link = root.parent / ".superheroes-worktrees-evil"   # name-prefix lookalike, not a descendant
    link.symlink_to(outside)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'x'", str(link)) is False


def test_non_interpreter_command_not_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    wt = root / "abc"; wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("gh pr merge 1", str(wt)) is False


def test_missing_or_bad_cwd_not_confined(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(tmp_path / ".superheroes-worktrees"))
    assert pr.worktree_confined("python3 -c 'x'", None) is False
    assert pr.worktree_confined("python3 -c 'x'", "") is False


# --- Task 2: Rules store paths + provenance-checked read (FR-6 substrate, UFR-9) ---

import json


def _write_rules(root, cwd, entries, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    d = os.path.join(root, "projects", "KEY", "permission")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "rules.json"), "w") as f:
        json.dump({"rules": entries}, f)
    return d


def test_store_dir_is_config_keyed(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    got = pr._store_dir("/some/cwd", root=str(tmp_path))
    assert got == os.path.join(str(tmp_path), "projects", "KEY", "permission")


def test_rules_reads_provenance_valid_only(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
        {"family": "sneaky", "pattern": "gh pr merge", "provenance": None},   # untraceable -> ignored
        {"family": "sneaky2", "pattern": "rm -rf"},                            # no provenance key -> ignored
    ], monkeypatch)
    got = pr.rules("/cwd", root=str(tmp_path))
    fams = [r["family"] for r in got]
    assert fams == ["test-run"]


def test_rules_missing_store_is_empty(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "NONE")
    assert pr.rules("/cwd", root=str(tmp_path)) == []


def test_rules_corrupt_store_is_empty_not_raise(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission"); os.makedirs(d)
    with open(os.path.join(d, "rules.json"), "w") as f:
        f.write("{ this is not json")
    assert pr.rules("/cwd", root=str(tmp_path)) == []   # UFR-2 fail-safe: corrupt -> empty -> prompt
