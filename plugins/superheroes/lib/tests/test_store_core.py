"""Characterization tests for store_core.py — the shared two-key pointer +
self-heal resolution algorithm extracted from store.py and review_store.py.

Step 1 (TDD): write first, run → RED, then extract store_core.py → GREEN.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

import store_core as sc


# ---------------------------------------------------------------------------
# normalize_remote
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    # scp-style
    ("git@github.com:org/repo.git", "github.com/org/repo"),
    ("git@github.com:org/repo",     "github.com/org/repo"),
    # https with scheme
    ("https://github.com/org/repo.git", "github.com/org/repo"),
    ("https://user@github.com/org/repo.git", "github.com/org/repo"),
    ("https://GitHub.com/Org/Repo.git", "github.com/Org/Repo"),
    ("https://github.com/org/repo/", "github.com/org/repo"),
    # ssh with port
    ("ssh://git@github.com:22/org/repo.git", "github.com/org/repo"),
    # empty / unparseable
    ("", None),
    (None, None),
    ("   ", None),
    ("not-a-url", None),
])
def test_normalize_remote(url, expected):
    assert sc.normalize_remote(url) == expected


def test_normalize_remote_lowercases_host():
    assert sc.normalize_remote("git@GitHub.COM:Org/Repo.git").startswith("github.com/")


def test_normalize_remote_strips_trailing_slashes():
    result = sc.normalize_remote("https://github.com/org/repo///")
    assert result is not None and not result.endswith("/")


# ---------------------------------------------------------------------------
# short_hash
# ---------------------------------------------------------------------------

def test_short_hash_is_16_hex():
    h = sc.short_hash("anything")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_short_hash_is_sha256():
    s = "github.com/org/repo"
    expected = hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
    assert sc.short_hash(s) == expected


def test_short_hash_is_stable():
    assert sc.short_hash("x") == sc.short_hash("x")


def test_short_hash_differs_for_different_inputs():
    assert sc.short_hash("a") != sc.short_hash("b")


# ---------------------------------------------------------------------------
# get_remote / get_gitdir  (require a real temp git dir)
# ---------------------------------------------------------------------------

def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], check=True,
                   capture_output=True, text=True)


def _init_repo(path, remote=None):
    path = str(path)
    subprocess.run(["git", "init", "-q", path], check=True,
                   capture_output=True, text=True)
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return path


def test_get_remote_with_origin(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:org/repo.git")
    assert sc.get_remote(repo) == "github.com/org/repo"


def test_get_remote_no_origin(tmp_path):
    repo = _init_repo(tmp_path / "r")
    assert sc.get_remote(repo) is None


def test_get_gitdir_is_absolute_realpath(tmp_path):
    repo = _init_repo(tmp_path / "r")
    gd = sc.get_gitdir(repo)
    assert os.path.isabs(gd)
    assert gd == os.path.realpath(gd)


def test_get_gitdir_non_git_fallback(tmp_path):
    plain = str(tmp_path / "plain")
    os.makedirs(plain)
    result = sc.get_gitdir(plain)
    assert result == os.path.realpath(plain)


def test_get_gitdir_worktrees_share_common_dir(tmp_path):
    repo = _init_repo(tmp_path / "main")
    (tmp_path / "main" / "f").write_text("x")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", "init")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-q", wt)
    assert sc.get_gitdir(repo) == sc.get_gitdir(wt)


# ---------------------------------------------------------------------------
# resolve_global — the two-key remote-wins + self-heal algorithm
# ---------------------------------------------------------------------------

def test_resolve_global_none_when_nothing_registered(tmp_path):
    repo = _init_repo(tmp_path / "r")
    root = str(tmp_path / "store")
    assert sc.resolve_global(repo, root) is None


def test_resolve_global_happy_path(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:o/p.git")
    root = str(tmp_path / "store")
    ident = sc.derive_identifiers(repo)
    eid = ident["gitdir_hash"]
    entry_dir = os.path.join(root, "entries", eid)
    os.makedirs(entry_dir)
    sc.write_pointer(root, ident["gitdir_hash"], eid)
    sc.write_pointer(root, ident["remote_hash"], eid)
    sc._write_keys_json(entry_dir, ident)
    g = sc.resolve_global(repo, root)
    assert g is not None
    assert g["entry_id"] == eid
    assert g["dir"] == entry_dir
    assert g["healed"] is False


def test_resolve_global_self_heals_missing_gitdir_pointer(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:o/p.git")
    root = str(tmp_path / "store")
    ident = sc.derive_identifiers(repo)
    eid = ident["gitdir_hash"]
    os.makedirs(os.path.join(root, "entries", eid))
    sc._write_keys_json(os.path.join(root, "entries", eid), ident)
    sc.write_pointer(root, ident["remote_hash"], eid)   # only remote pointer
    g = sc.resolve_global(repo, root)
    assert g["entry_id"] == eid
    assert g["healed"] is True
    assert sc.read_pointer(root, ident["gitdir_hash"]) == eid


def test_resolve_global_self_heals_missing_remote_pointer(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:o/p.git")
    root = str(tmp_path / "store")
    ident = sc.derive_identifiers(repo)
    eid = ident["gitdir_hash"]
    os.makedirs(os.path.join(root, "entries", eid))
    sc._write_keys_json(os.path.join(root, "entries", eid), ident)
    sc.write_pointer(root, ident["gitdir_hash"], eid)   # only gitdir pointer
    g = sc.resolve_global(repo, root)
    assert g["healed"] is True
    assert sc.read_pointer(root, ident["remote_hash"]) == eid


def test_resolve_global_prefers_remote_on_genuine_disagreement(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:o/p.git")
    root = str(tmp_path / "store")
    ident = sc.derive_identifiers(repo)
    sc.write_pointer(root, ident["remote_hash"], "entry-REMOTE")
    sc.write_pointer(root, ident["gitdir_hash"], "entry-GITDIR")
    os.makedirs(os.path.join(root, "entries", "entry-REMOTE"))
    os.makedirs(os.path.join(root, "entries", "entry-GITDIR"))
    g = sc.resolve_global(repo, root)
    assert g["entry_id"] == "entry-REMOTE"
    assert g["healed"] is True
    assert sc.read_pointer(root, ident["gitdir_hash"]) == "entry-REMOTE"


def test_resolve_global_falls_back_to_live_when_preferred_dangles(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:o/p.git")
    root = str(tmp_path / "store")
    ident = sc.derive_identifiers(repo)
    sc.write_pointer(root, ident["remote_hash"], "entry-DANGLING")
    sc.write_pointer(root, ident["gitdir_hash"], "entry-LIVE")
    os.makedirs(os.path.join(root, "entries", "entry-LIVE"))
    g = sc.resolve_global(repo, root)
    assert g["entry_id"] == "entry-LIVE"
    assert g["healed"] is True
    assert sc.read_pointer(root, ident["remote_hash"]) == "entry-LIVE"


def test_resolve_global_none_when_all_dangle(tmp_path):
    repo = _init_repo(tmp_path / "r")
    root = str(tmp_path / "store")
    ident = sc.derive_identifiers(repo)
    sc.write_pointer(root, ident["gitdir_hash"], "entry-GONE")
    assert sc.resolve_global(repo, root) is None


# ---------------------------------------------------------------------------
# pointer read/write
# ---------------------------------------------------------------------------

def test_pointer_round_trip(tmp_path):
    root = str(tmp_path / "store")
    assert sc.read_pointer(root, "abc123") is None
    sc.write_pointer(root, "abc123", "entry-xyz")
    assert sc.read_pointer(root, "abc123") == "entry-xyz"
    sc.write_pointer(root, "abc123", "entry-2")
    assert sc.read_pointer(root, "abc123") == "entry-2"


def test_disjoint_keys_dont_clobber(tmp_path):
    root = str(tmp_path / "store")
    sc.write_pointer(root, "hashA", "entryA")
    sc.write_pointer(root, "hashB", "entryB")
    assert sc.read_pointer(root, "hashA") == "entryA"
    assert sc.read_pointer(root, "hashB") == "entryB"


# ---------------------------------------------------------------------------
# derive_identifiers
# ---------------------------------------------------------------------------

def test_derive_identifiers_with_remote(tmp_path):
    repo = _init_repo(tmp_path / "r", remote="git@github.com:org/repo.git")
    ident = sc.derive_identifiers(repo)
    assert ident["remote"] == "github.com/org/repo"
    assert ident["remote_hash"] == sc.short_hash("github.com/org/repo")
    assert os.path.isabs(ident["gitdir"])
    assert ident["gitdir_hash"] == sc.short_hash(ident["gitdir"])


def test_derive_identifiers_no_remote(tmp_path):
    repo = _init_repo(tmp_path / "r")
    ident = sc.derive_identifiers(repo)
    assert ident["remote"] is None
    assert ident["remote_hash"] is None
    assert ident["gitdir_hash"]


# ---------------------------------------------------------------------------
# Same hashes for same inputs across the two consumers
# (verify the core produces identical results to the old store.py / review_store.py)
# ---------------------------------------------------------------------------

def test_short_hash_matches_store_and_review_store():
    """Core hash must match what both consumers computed (SHA-256 first 16 hex)."""
    import store
    import review_store
    for s in ["github.com/org/repo", "some/path", "x"]:
        assert sc.short_hash(s) == store.short_hash(s)
        assert sc.short_hash(s) == review_store.short_hash(s)


def test_normalize_remote_matches_store_and_review_store():
    """Core normalize_remote must match both consumers for the same URLs."""
    import store
    import review_store
    urls = [
        "git@github.com:org/repo.git",
        "https://github.com/org/repo.git",
        "https://user@github.com/org/repo/",
        "ssh://git@github.com:22/org/repo.git",
        "",
        None,
    ]
    for url in urls:
        assert sc.normalize_remote(url) == store.normalize_remote(url), f"Mismatch for {url!r}"
        assert sc.normalize_remote(url) == review_store.normalize_remote(url), f"Mismatch for {url!r}"
