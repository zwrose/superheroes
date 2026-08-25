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
    assert r["artifacts_dir"].startswith(root)


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
    assert r["artifacts_dir"].startswith(root)
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
    assert r["artifacts_dir"].startswith(root)
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
    assert r["artifacts_dir"].startswith(root)


def test_create_global_then_resolve(tmp_path):
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    c = store.create(repo, "global", root)
    assert c["artifacts_dir"].startswith(root)
    assert not os.path.exists(c["artifacts_dir"])
    assert os.path.isdir(c["plans_dir"])
    assert os.path.isdir(c["state_dir"])
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
    assert store.decide_location("in-repo", cwd=repo, root=root) == {
        "mode": "in-repo", "source": "env", "provisional": False}
    assert store.decide_location("global", cwd=repo, root=root) == {
        "mode": "global", "source": "env", "provisional": False}
    d = store.decide_location(None, cwd=repo, root=root)
    assert d["mode"] == "global" and d["source"] == "provisional" and d["provisional"] is True
    d = store.decide_location("bogus", cwd=repo, root=root)
    assert d["mode"] == "global" and d["provisional"] is True  # invalid env falls through


def test_decide_location_honors_recorded_mode(tmp_path):
    import mode_registry as mr
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    mr.write_registry(repo, mr.IN_REPO, None, root=root)
    d = store.decide_location(None, cwd=repo, root=root)
    assert d == {"mode": "in-repo", "source": "registry", "provisional": False}


def test_cli_decide_location_emits_json(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    env = dict(os.environ, TEST_PILOT_STORE_ROOT=str(tmp_path / "store"))
    lib = os.path.dirname(os.path.abspath(store.__file__))
    out = subprocess.run(
        ["/usr/bin/python3", os.path.join(lib, "store.py"), "decide-location"],
        capture_output=True, text=True, cwd=repo, env=env)
    assert out.returncode == 0
    payload = json.loads(out.stdout)
    assert set(payload) >= {"mode", "source", "provisional"}
    assert payload["mode"] in ("in-repo", "global")


def test_cli_decide_location_rejects_stale_interactive_flag(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    env = dict(os.environ, TEST_PILOT_STORE_ROOT=str(tmp_path / "store"))
    lib = os.path.dirname(os.path.abspath(store.__file__))
    for extra in (["--interactive", "true"], ["--interactive=true"]):
        out = subprocess.run(
            ["/usr/bin/python3", os.path.join(lib, "store.py"), "decide-location"] + extra,
            capture_output=True, text=True, cwd=repo, env=env)
        assert out.returncode != 0
        assert "1136" in out.stderr


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


# ---------------------------------------------------------------------------
# #428 direction 2 — create() is layer-native on migrated projects. Pointing
# callers (test-pilot-init writes the profile at create()'s returned path) back
# at the legacy .claude/test-pilot/profile.md re-minted the legacy file, which had been the
# trigger for core_md.migrate_on_read inside build worktrees — the destructive layer-deletion
# commit (weekly-eats 9dad0f6). That migration path was removed in #724.
# ---------------------------------------------------------------------------

def test_create_in_repo_migrated_project_targets_layer_not_legacy(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer = _write_in_repo_layer(repo)
    c = store.create(repo, "in-repo", root)
    assert c["profileSource"] == "layer"
    assert c["profile"] == layer
    assert c["exists"] is True
    # the legacy path is neither returned nor created
    assert not os.path.exists(os.path.join(repo, ".claude", "test-pilot", "profile.md"))
    # blocks/manifests keep their in-repo home (the migration does not move them)
    base = os.path.join(repo, ".claude", "test-pilot")
    assert c["blocks_dir"] == os.path.join(base, "blocks")
    assert c["manifests_dir"] == os.path.join(base, "manifests")


def test_create_global_migrated_project_targets_layer_not_legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    layer = _write_global_layer(repo)
    c = store.create(repo, "global", root)
    assert c["profileSource"] == "layer"
    assert c["profile"] == layer
    assert c["exists"] is True


def test_create_fresh_project_still_targets_legacy_scaffold_path(tmp_path):
    # A genuinely un-migrated project keeps the pre-#428 scaffold target, byte-identical:
    # the legacy path is returned (profileSource profile-md) but never written by create().
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    c = store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"
    assert c["profile"] == os.path.join(repo, ".claude", "test-pilot", "profile.md")
    assert c["exists"] is False
    assert not os.path.exists(c["profile"])


def test_create_legacy_present_keeps_legacy_precedence_over_layer(tmp_path):
    # resolve() is legacy-first when both exist; create() must mirror that precedence or
    # init would write the layer while the engine keeps reading the still-present legacy.
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    base = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(base)
    legacy = os.path.join(base, "profile.md")
    open(legacy, "w").write("# p\n")
    _write_in_repo_layer(repo)
    c = store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"
    assert c["profile"] == legacy


def test_create_prose_only_layer_falls_back_to_legacy_path(tmp_path):
    # A layer without the test-pilot-config block is not engine calibration (epic #327):
    # create() must not hand it back as the profile target.
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    _write_in_repo_layer(repo, text="<!-- test-pilot -->\n\n## App launch\n- npm run dev\n")
    c = store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"
    assert c["profile"] == os.path.join(repo, ".claude", "test-pilot", "profile.md")


def test_create_legacy_global_without_pointer_keeps_precedence_over_layer(tmp_path):
    # #428/#724: surviving entry dir with legacy profile.md but no key pointer must keep
    # legacy-first precedence so create() and resolve() agree.
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    ident = store.derive_identifiers(repo)
    entry_dir = os.path.join(root, "entries", ident["gitdir_hash"])
    os.makedirs(entry_dir)
    open(os.path.join(entry_dir, "profile.md"), "w").write("# legacy\n")
    _write_in_repo_layer(repo)
    c = store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"
    r = store.resolve(repo, root)
    assert r["profileSource"] == "profile-md"


def test_create_cross_mode_legacy_keeps_precedence_over_layer(tmp_path):
    # #428 round-2 review: resolve()'s precedence puts ANY legacy (in-repo OR global-entry
    # profile.md) ahead of the layers. create() must honor the cross-location legacy too, or a
    # direct caller would write over a live layer while the engine keeps reading the legacy.
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    g = store.create(repo, "global", root)          # mint the global entry
    open(g["profile"], "w").write("# p\n")           # global-entry legacy profile.md
    _write_in_repo_layer(repo)                       # in-repo layer with config block
    c = store.create(repo, "in-repo", root)
    assert c["profileSource"] == "profile-md"        # global legacy keeps precedence
    assert c["profile"] == os.path.join(repo, ".claude", "test-pilot", "profile.md")


def test_candidate_profile_paths_agrees_with_resolve_per_position(tmp_path, monkeypatch):
    """Drift guard: resolve() must select the same path candidate_profile_paths() names."""
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    cases = [
        ("legacy_in_repo", lambda repo, root: (
            store.create(repo, "global", root),
            os.makedirs(os.path.join(repo, ".claude", "test-pilot"), exist_ok=True),
            open(os.path.join(repo, ".claude", "test-pilot", "profile.md"), "w").write("# p\n"),
        )),
        ("legacy_global", lambda repo, root: (
            open(store.create(repo, "global", root)["profile"], "w").write("# p\n"),
        )),
        ("in_repo_layer", lambda repo, root: (
            store.create(repo, "global", root),
            _write_in_repo_layer(repo),
        )),
        ("global_layer", lambda repo, root: (
            store.create(repo, "global", root),
            _write_global_layer(repo),
        )),
    ]
    for idx, (name, setup) in enumerate(cases):
        repo = _init_repo(tmp_path / f"repo-{name}", remote="git@github.com:org/repo.git")
        root = str(tmp_path / f"store-{name}")
        setup(repo, root)
        candidates = store.candidate_profile_paths(repo, root)
        assert len(candidates) == 4, name
        r = store.resolve(repo, root)
        assert r["profile"] == candidates[idx], name


# ---------------------------------------------------------------------------
# #782 — fail-closed layer classification
# ---------------------------------------------------------------------------

def _tree_snapshot(root):
    snapshot = {}
    if not os.path.isdir(root):
        return snapshot
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as fh:
                snapshot[p] = fh.read()
    return snapshot


def test_resolve_in_repo_layer_directory_refusal(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer_dir = os.path.join(repo, ".claude", "superheroes", "test-pilot.md")
    os.makedirs(layer_dir, exist_ok=True)
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["exists"] is False
    assert r["refusal"] is not None
    assert r["refusal"]["reason"] == store.STORE_REASON_LAYER_UNREADABLE


def test_resolve_in_repo_layer_dangling_symlink_refusal(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    os.symlink("/no/such/layer", os.path.join(d, "test-pilot.md"))
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["refusal"] is not None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_classify_layer_unsearchable_parent_directory_reports_unreadable_not_absent(
    tmp_path,
):
    """Unsearchable parent directory → unreadable, not absent (os.stat outer handler)."""
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer = _write_in_repo_layer(repo)
    claude_dir = os.path.join(repo, ".claude")
    os.chmod(claude_dir, 0o000)
    try:
        result = store.classify_layer_config_block(layer)
        assert result.status == store.LAYER_UNREADABLE
        assert result.status != store.LAYER_ABSENT
        r = store.resolve(repo, root)
        assert r["location"] == "none"
        assert r["refusal"] is not None
        assert r["refusal"]["reason"] == store.STORE_REASON_LAYER_UNREADABLE
    finally:
        try:
            os.chmod(claude_dir, 0o700)
        except OSError as exc:
            pytest.fail("could not restore parent directory mode: %s" % exc)


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode 0o000 files")
def test_resolve_in_repo_layer_mode_zero_refusal(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer = _write_in_repo_layer(repo)
    os.chmod(layer, 0o000)
    try:
        r = store.resolve(repo, root)
        assert r["location"] == "none"
        assert r["refusal"] is not None
    finally:
        os.chmod(layer, 0o644)


def test_resolve_in_repo_layer_invalid_utf8_refusal(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    layer = os.path.join(d, "test-pilot.md")
    with open(layer, "wb") as fh:
        fh.write(b"\xff\xfe")
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["refusal"] is not None


def test_resolve_unreadable_in_repo_does_not_fall_through_to_global(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    os.symlink("/no/such/in-repo-layer", os.path.join(d, "test-pilot.md"))
    _write_global_layer(repo)
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["refusal"] is not None
    assert r["profileSource"] == "none"


def test_resolve_legacy_profile_unstatable_refusal(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    base = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(base, exist_ok=True)
    legacy = os.path.join(base, "profile.md")
    os.symlink("/no/such/legacy", legacy)
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["refusal"] is not None


def test_resolve_layer_without_config_block_refusal_none(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    _write_in_repo_layer(repo, text="<!-- test-pilot -->\n\n## App launch\n- npm run dev\n")
    r = store.resolve(repo, root)
    assert r["location"] == "none"
    assert r["refusal"] is None


def test_resolve_pointer_unreadable_refusal(tmp_path):
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    store.create(repo, "global", root)
    ident = store.derive_identifiers(repo)
    pointer = os.path.join(root, "keys", ident["gitdir_hash"])
    os.chmod(pointer, 0o000)
    try:
        r = store.resolve(repo, root)
        assert r["location"] == "none"
        assert r["refusal"] is not None
        assert r["refusal"]["reason"] == store.STORE_REASON_POINTER_UNREADABLE
    finally:
        os.chmod(pointer, 0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode 0o000 files")
def test_create_unreadable_layer_raises_without_writing(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer = _write_in_repo_layer(repo)
    os.chmod(layer, 0o000)
    before = _tree_snapshot(root)
    try:
        with pytest.raises(store.LayerUnreadable):
            store.create(repo, "in-repo", root)
    finally:
        os.chmod(layer, 0o644)
    after = _tree_snapshot(root)
    assert before == after


def test_cli_resolve_unreadable_layer_exit_one(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    os.symlink("/no/such/layer", os.path.join(d, "test-pilot.md"))
    env = dict(os.environ, TEST_PILOT_STORE_ROOT=root)
    lib = os.path.dirname(os.path.abspath(store.__file__))
    out = subprocess.run(
        ["/usr/bin/python3", os.path.join(lib, "store.py"), "resolve"],
        capture_output=True, text=True, cwd=repo, env=env)
    assert out.returncode == 1
    payload = json.loads(out.stdout)
    assert payload["refusal"] is not None


# ---------------------------------------------------------------------------
# #782 — structured refusal path/source fields
# ---------------------------------------------------------------------------

def test_resolve_refusal_unreadable_in_repo_layer_carries_path(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    layer = os.path.join(d, "test-pilot.md")
    os.symlink("/no/such/layer", layer)
    r = store.resolve(repo, root)
    assert r["refusal"] is not None
    assert r["refusal"]["path"] == layer
    assert r["refusal"]["source"] == "layer"


def test_resolve_refusal_unreadable_legacy_profile_carries_path_and_source(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    base = os.path.join(repo, ".claude", "test-pilot")
    os.makedirs(base, exist_ok=True)
    legacy = os.path.join(base, "profile.md")
    os.symlink("/no/such/legacy", legacy)
    r = store.resolve(repo, root)
    assert r["refusal"] is not None
    assert r["refusal"]["path"] == legacy
    assert r["refusal"]["source"] == "profile-md"


def test_resolve_refusal_unreadable_global_layer_carries_path(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    store.create(repo, "global", root)
    import mode_registry
    d = os.path.join(mode_registry.project_store_dir(repo), "config")
    os.makedirs(d, exist_ok=True)
    layer = os.path.join(d, "test-pilot.md")
    os.symlink("/no/such/global-layer", layer)
    r = store.resolve(repo, root)
    assert r["refusal"] is not None
    assert r["refusal"]["path"] == layer
    assert r["refusal"]["source"] == "layer"


def test_resolve_refusal_pointer_unreadable_carries_path(tmp_path):
    repo = _init_repo(tmp_path / "repo", remote="git@github.com:org/repo.git")
    root = str(tmp_path / "store")
    store.create(repo, "global", root)
    ident = store.derive_identifiers(repo)
    pointer = os.path.join(root, "keys", ident["gitdir_hash"])
    os.chmod(pointer, 0o000)
    try:
        r = store.resolve(repo, root)
        assert r["refusal"] is not None
        assert r["refusal"]["reason"] == store.STORE_REASON_POINTER_UNREADABLE
        assert r["refusal"]["path"] == pointer
    finally:
        os.chmod(pointer, 0o644)


def test_resolve_every_refusal_carries_path_key(tmp_path, monkeypatch):
    """Every refusal dict includes an explicit path key (possibly None)."""
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "core-store"))
    cases = []

    repo1 = _init_repo(tmp_path / "repo-layer")
    d1 = os.path.join(repo1, ".claude", "superheroes")
    os.makedirs(d1, exist_ok=True)
    layer1 = os.path.join(d1, "test-pilot.md")
    os.symlink("/no/such/layer", layer1)
    cases.append(store.resolve(repo1, str(tmp_path / "store1")))

    repo2 = _init_repo(tmp_path / "repo-legacy")
    base = os.path.join(repo2, ".claude", "test-pilot")
    os.makedirs(base, exist_ok=True)
    os.symlink("/no/such/legacy", os.path.join(base, "profile.md"))
    cases.append(store.resolve(repo2, str(tmp_path / "store2")))

    repo3 = _init_repo(tmp_path / "repo-global", remote="git@github.com:org/repo.git")
    root3 = str(tmp_path / "store3")
    store.create(repo3, "global", root3)
    import mode_registry
    d3 = os.path.join(mode_registry.project_store_dir(repo3), "config")
    os.makedirs(d3, exist_ok=True)
    os.symlink("/no/such/global", os.path.join(d3, "test-pilot.md"))
    cases.append(store.resolve(repo3, root3))

    repo4 = _init_repo(tmp_path / "repo-pointer", remote="git@github.com:org/repo-pointer.git")
    root4 = str(tmp_path / "store4")
    store.create(repo4, "global", root4)
    ident = store.derive_identifiers(repo4)
    pointer = os.path.join(root4, "keys", ident["gitdir_hash"])
    os.chmod(pointer, 0o000)
    try:
        cases.append(store.resolve(repo4, root4))
    finally:
        os.chmod(pointer, 0o644)

    for r in cases:
        refusal = r["refusal"]
        assert refusal is not None
        assert "path" in refusal
