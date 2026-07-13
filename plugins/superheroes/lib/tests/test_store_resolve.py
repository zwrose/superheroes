import json
import os
import subprocess

import pytest

import store


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], check=True,
                   capture_output=True, text=True)


def _init_repo(path, remote=None):
    path = str(path)
    subprocess.run(["git", "init", "-q", path], check=True,
                   capture_output=True, text=True)
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return path


_LAYER = (
    "<!-- test-pilot: schemaVersion=2 status=confirmed created=2026-07-01 "
    "updated=2026-07-01 nudge-ack={} -->\n\n"
    "## Machine-readable config\n\n"
    "```json test-pilot-config\n"
    '{"schemaVersion": 1, "baseUrl": "http://localhost:3000"}\n'
    "```\n"
)


def _write_in_repo_layer(repo, text=_LAYER):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "test-pilot.md")
    open(p, "w").write(text)
    return p


def _write_global_layer(repo, text=_LAYER):
    """Write the unified layer into the out-of-repo project store (global mode). Uses the
    same mode-aware store dir the resolver probes; WORKHORSE_STORE_ROOT is pinned by conftest
    so this never touches the real ~/.claude store."""
    import mode_registry
    d = os.path.join(mode_registry.project_store_dir(repo), "config")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "test-pilot.md")
    open(p, "w").write(text)
    return p


def test_resolve_none_when_nothing_exists(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["profile"] is None
    assert r["profileSource"] == "none"
    # state/plans are computed even with no profile (machine-local, always global)
    assert r["state_dir"].startswith(root)
    assert r["plans_dir"].startswith(root)


def test_resolve_layer_only_in_repo(tmp_path):
    """#412: a migrated in-repo project (layer, no profile.md) resolves via the layer."""
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer = _write_in_repo_layer(repo)
    r = store.resolve(repo, root)
    assert r["location"] == "in-repo"
    assert r["profileSource"] == "layer"
    assert r["profile"] == layer
    # blocks/manifests follow in-repo mode (the migration did not move them)
    base = os.path.join(repo, ".claude", "test-pilot")
    assert r["blocks_dir"] == os.path.join(base, "blocks")
    assert r["manifests_dir"] == os.path.join(base, "manifests")
    # engine can load the config block straight from the layer path resolve() returned
    import engine
    assert engine.load_profile_config(r["profile"])["baseUrl"] == "http://localhost:3000"


def test_resolve_layer_only_global(tmp_path, monkeypatch):
    """#412: a migrated out-of-repo project resolves via the project-store layer."""
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    layer = _write_global_layer(repo)
    r = store.resolve(repo, root)
    assert r["location"] == "global"
    assert r["profileSource"] == "layer"
    assert r["profile"] == layer
    assert r["blocks_dir"].startswith(root)  # machine-local entry, not in-repo
    import engine
    assert engine.load_profile_config(r["profile"])["baseUrl"] == "http://localhost:3000"


def test_resolve_profile_md_precedence_over_layer(tmp_path):
    """#412: legacy profile.md still wins when BOTH it and the layer are present."""
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    base = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(base)
    open(os.path.join(base, "profile.md"), "w").write("# p\n")
    _write_in_repo_layer(repo)
    r = store.resolve(repo, root)
    assert r["location"] == "in-repo"
    assert r["profileSource"] == "profile-md"
    assert r["profile"] == os.path.join(base, "profile.md")


def test_resolve_layer_without_config_block_is_none(tmp_path):
    """#412 / epic #327: a layer carrying only prose (no test-pilot-config block) is NOT
    engine calibration — resolution must honestly report `none`, not a phantom profile."""
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    _write_in_repo_layer(repo, text="<!-- test-pilot -->\n\n## App launch\n- npm run dev\n")
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["profile"] is None
    assert r["profileSource"] == "none"


def test_resolve_global_layer_without_config_block_is_none(tmp_path, monkeypatch):
    """#412 / epic #327, global mode: the out-of-repo layer branch carries its own
    config-block gate — a prose-only project-store layer must not become a phantom profile."""
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    _write_global_layer(repo, text="<!-- test-pilot -->\n\n## App launch\n- npm run dev\n")
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["profile"] is None
    assert r["profileSource"] == "none"


def test_resolve_global_profile_md_precedence_over_global_layer(tmp_path, monkeypatch):
    """#412, global mode: a legacy global-entry profile.md still wins over the
    project-store layer when both are present."""
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    c = store.create(repo, "global", root)
    open(c["profile"], "w").write("# p\n")
    _write_global_layer(repo)
    r = store.resolve(repo, root)
    assert r["location"] == "global"
    assert r["profileSource"] == "profile-md"
    assert r["profile"] == c["profile"]


def test_in_repo_profile_wins_but_state_stays_global(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    base = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(base)
    open(os.path.join(base, "profile.md"), "w").write("# p\n")
    r = store.resolve(repo, root)
    assert r["location"] == "in-repo"
    assert r["profileSource"] == "profile-md"
    assert r["profile"] == os.path.join(base, "profile.md")
    assert r["blocks_dir"] == os.path.join(base, "blocks")
    assert r["manifests_dir"] == os.path.join(base, "manifests")
    # The deliberate divergence from review-crew's store design:
    assert r["state_dir"].startswith(root)
    assert r["plans_dir"].startswith(root)


def test_create_global_then_resolve(tmp_path):
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    c = store.create(repo, "global", root)
    open(c["profile"], "w").write("# p\n")
    r = store.resolve(repo, root)
    assert r["location"] == "global"
    assert r["profileSource"] == "profile-md"
    assert r["profile"] == c["profile"]
    assert os.path.isdir(r["blocks_dir"])


def test_worktrees_share_an_entry(tmp_path):
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    open(os.path.join(repo, "f"), "w").write("x")
    _git(repo, "add", "f")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-q", wt)
    root = str(tmp_path / "store")
    store.create(repo, "global", root)
    a = store.resolve(repo, root)
    b = store.resolve(wt, root)
    assert a["entry_id"] == b["entry_id"]
    assert a["state_dir"] == b["state_dir"]


def test_decide_location_greenfield_delegates_to_decide_mode(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    assert store.decide_location("in-repo", True, cwd=repo, root=root) == "in-repo"
    assert store.decide_location("global", False, cwd=repo, root=root) == "global"
    assert store.decide_location(None, True, cwd=repo, root=root) == "ask"
    assert store.decide_location(None, False, cwd=repo, root=root) == "global"
    assert store.decide_location("bogus", True, cwd=repo, root=root) == "ask"  # invalid env falls through


def test_decide_location_honors_recorded_mode(tmp_path):
    import mode_registry as mr
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    mr.write_registry(repo, mr.IN_REPO, None, root=root)
    assert store.decide_location(None, True, cwd=repo, root=root) == "in-repo"  # FR-4, no "ask"


def test_resolve_global_self_heals_dangling_remote_pointer(tmp_path):
    """test-004: write a dangling remote pointer; resolve_global heals it."""
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    # Create a real global entry
    c = store.create(repo, "global", root)
    live_entry = c["entry_id"]
    # Overwrite the remote-hash pointer to a nonexistent entry
    ident = store.derive_identifiers(repo)
    dead_entry = "deadbeefdeadbeef"
    store.write_pointer(root, ident["remote_hash"], dead_entry)
    # resolve_global should fall back to the live gitdir-keyed entry and heal
    result = store.resolve_global(repo, root)
    assert result is not None
    assert result["entry_id"] == live_entry
    assert result["healed"] is True
    # The remote pointer must now point at the live entry
    assert store.read_pointer(root, ident["remote_hash"]) == live_entry


# r2-test-test-002: create() reuses an existing live entry for a second clone
# with the same remote URL (distinct gitdir).
def test_create_reuses_entry_for_second_clone(tmp_path):
    remote = "git@github.com:org/shared-repo.git"
    clone_a = _init_repo(tmp_path / "clone_a", remote=remote)
    clone_b = _init_repo(tmp_path / "clone_b", remote=remote)
    root = str(tmp_path / "store")
    c1 = store.create(clone_a, "global", root)
    c2 = store.create(clone_b, "global", root)
    # Both clones must resolve to the same entry (reuse via remote pointer).
    assert c2["entry_id"] == c1["entry_id"]
    # Both gitdir pointers must now point at that entry.
    ident_a = store.derive_identifiers(clone_a)
    ident_b = store.derive_identifiers(clone_b)
    assert store.read_pointer(root, ident_a["gitdir_hash"]) == c1["entry_id"]
    assert store.read_pointer(root, ident_b["gitdir_hash"]) == c1["entry_id"]


# r2-test-test-005: get_repo_root — git repo returns toplevel; non-git dir returns itself.
def test_get_repo_root_in_git_repo(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    sub = os.path.join(repo, "sub", "dir")
    os.makedirs(sub)
    assert store.get_repo_root(sub) == os.path.realpath(repo)


def test_get_repo_root_non_git_fallback(tmp_path):
    plain = str(tmp_path / "plain")
    os.makedirs(plain)
    result = store.get_repo_root(plain)
    assert result == os.path.realpath(plain)


def test_cli_key_and_resolve(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    env = dict(os.environ, TEST_PILOT_STORE_ROOT=str(tmp_path / "store"))
    lib = os.path.dirname(os.path.abspath(store.__file__))
    out = subprocess.run(
        ["python3", os.path.join(lib, "store.py"), "key",
         "--branch", "feat/x", "--slot", "admin"],
        capture_output=True, text=True, cwd=repo, env=env)
    assert out.returncode == 0
    assert out.stdout.strip() == "feat%2Fx~admin"
    out = subprocess.run(
        ["python3", os.path.join(lib, "store.py"), "resolve"],
        capture_output=True, text=True, cwd=repo, env=env)
    assert out.returncode == 0
    assert json.loads(out.stdout)["location"] == "none"
