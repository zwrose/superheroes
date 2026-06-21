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


def test_get_gitdir_pre_231_fallback(tmp_path, monkeypatch):
    """get_gitdir falls back to --absolute-git-dir when --path-format=absolute
    --git-common-dir returns None (simulating git < 2.31)."""
    repo = _init_repo(tmp_path / "r")
    calls = {"n": 0}
    real = sc.run_git

    def fake(cwd, *a):
        if a == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return None  # simulate git < 2.31 not supporting the flag
        if a == ("rev-parse", "--absolute-git-dir"):
            calls["n"] += 1
            return real(cwd, *a)
        return real(cwd, *a)

    monkeypatch.setattr(sc, "run_git", fake)
    gd = sc.get_gitdir(repo)
    assert calls["n"] == 1            # fell back to --absolute-git-dir exactly once
    assert os.path.isabs(gd)
    assert gd == os.path.realpath(gd)


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
    sc.write_keys_json(entry_dir, ident)
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
    sc.write_keys_json(os.path.join(root, "entries", eid), ident)
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
    sc.write_keys_json(os.path.join(root, "entries", eid), ident)
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
# Golden-value behavioral tests for short_hash and normalize_remote
# (pin concrete expected outputs so tests FAIL if the implementation changes)
# ---------------------------------------------------------------------------

def test_short_hash_golden_values():
    """short_hash must produce the exact SHA-256-first-16-hex values for known inputs.

    These golden values were computed from the implementation and will catch any
    accidental mutation of the hash algorithm or truncation length.
    """
    assert sc.short_hash("github.com/org/repo") == "4c06e3f1e1c41311"
    assert sc.short_hash("some/path") == "d1563248892cd59a"
    assert sc.short_hash("x") == "2d711642b726b044"


def test_normalize_remote_golden_values():
    """normalize_remote must produce the exact canonical forms for known URL shapes.

    These golden values pin the stripping of scheme, user-info, .git suffix, trailing
    slashes, and port — any logic change will break these assertions.
    """
    assert sc.normalize_remote("git@github.com:org/repo.git") == "github.com/org/repo"
    assert sc.normalize_remote("https://github.com/org/repo.git") == "github.com/org/repo"
    assert sc.normalize_remote("https://user@github.com/org/repo/") == "github.com/org/repo"
    assert sc.normalize_remote("ssh://git@github.com:22/org/repo.git") == "github.com/org/repo"
    assert sc.normalize_remote("") is None
    assert sc.normalize_remote(None) is None


# ---------------------------------------------------------------------------
# resolve_global — heal=False read-only mode
# ---------------------------------------------------------------------------

def test_resolve_global_heal_false_is_read_only(tmp_path):
    root = str(tmp_path / "store")
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    ident = sc.derive_identifiers(str(repo))
    entry = os.path.join(root, "entries", "e1"); os.makedirs(entry)
    # only the gitdir pointer is healthy; the remote pointer is absent (a heal opportunity)
    sc.write_pointer(root, ident["gitdir_hash"], "e1")
    before = sorted(os.listdir(os.path.join(root, "keys")))
    g = sc.resolve_global(str(repo), root, heal=False)
    assert g is not None and g["entry_id"] == "e1" and g["healed"] is False
    assert sorted(os.listdir(os.path.join(root, "keys"))) == before  # no new pointer written
    assert not os.path.exists(os.path.join(entry, "keys.json"))      # no keys.json written
