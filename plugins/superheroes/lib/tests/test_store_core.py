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
    and bare --git-common-dir both decline (simulating git < 2.31)."""
    repo = _init_repo(tmp_path / "r")
    calls = {"absolute": 0}
    real = sc.run_git_result

    def fake(cwd, *a):
        if a == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return sc.GitResult(None, sc.GIT_DECLINED, "unknown option --path-format")
        if a == ("rev-parse", "--git-common-dir"):
            return sc.GitResult(None, sc.GIT_DECLINED, "unknown option")
        if a == ("rev-parse", "--absolute-git-dir"):
            calls["absolute"] += 1
            return real(cwd, *a)
        return real(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    gd = sc.get_gitdir(repo)
    assert calls["absolute"] == 1
    assert os.path.isabs(gd)
    assert gd == os.path.realpath(gd)


# ---------------------------------------------------------------------------
# repo_root / get_gitdir fail-closed chokepoint (issue #742)
# ---------------------------------------------------------------------------

def test_repo_root_in_git_repo(tmp_path):
    repo = _init_repo(tmp_path / "r")
    sub = os.path.join(repo, "sub", "deep")
    os.makedirs(sub)
    assert sc.repo_root(repo) == os.path.realpath(repo)
    assert sc.repo_root(sub) == os.path.realpath(repo)


def test_repo_root_non_git_greenfield(tmp_path, monkeypatch):
    plain = str(tmp_path / "plain")
    os.makedirs(plain)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    assert sc.repo_root(plain) == os.path.realpath(plain)


def test_repo_root_raises_on_git_unavailable(tmp_path, monkeypatch):
    def fake(cwd, *a):
        return sc.GitResult(None, sc.GIT_UNAVAILABLE, "FileNotFoundError: no git")

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.repo_root(str(tmp_path))


def test_repo_root_ok_empty_output_returns_realpath_cwd(tmp_path, monkeypatch):
    def fake(cwd, *a):
        return sc.GitResult("", sc.GIT_OK, None)

    monkeypatch.setattr(sc, "run_git_result", fake)
    assert sc.repo_root(str(tmp_path)) == os.path.realpath(str(tmp_path))


def test_repo_root_raises_on_ok_nonexistent_toplevel(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "r1")
    nope = str(tmp_path / "NOPE")
    cwd = str(tmp_path / "plain")
    os.makedirs(cwd)
    monkeypatch.setenv("GIT_DIR", os.path.join(repo, ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", nope)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.repo_root(cwd)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    assert sc.repo_root(cwd) == os.path.realpath(cwd)


def test_repo_root_ok_nonexistent_without_env_vars_is_greenfield(tmp_path, monkeypatch):
    plain = str(tmp_path / "plain")
    os.makedirs(plain)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)

    def fake(cwd, *a):
        if a == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    assert sc.repo_root(plain) == os.path.realpath(plain)


def test_repo_root_raises_on_ok_file_not_directory(tmp_path, monkeypatch):
    f = tmp_path / "file.txt"
    f.write_text("x")

    def fake(cwd, *a):
        return sc.GitResult(str(f), sc.GIT_OK, None)

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.repo_root(str(tmp_path))


def test_repo_root_raises_on_corrupt_git_dir_pointer(tmp_path, monkeypatch):
    corrupt = tmp_path / "corrupt"
    corrupt.mkdir()
    (corrupt / "HEAD").write_text("garbage\n")
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_DIR", str(corrupt))
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.repo_root(str(plain))


def test_repo_root_raises_when_git_ancestor_present(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "r")
    sub = tmp_path / "r" / "sub"
    sub.mkdir()

    def fake(cwd, *a):
        if a == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable) as excinfo:
        sc.repo_root(str(sub))
    assert ".git present" in str(excinfo.value)


def test_repo_root_raises_on_dangling_git_symlink(tmp_path, monkeypatch):
    outer = tmp_path / "outer"
    outer.mkdir()
    os.symlink(str(tmp_path / "missing"), str(outer / ".git"))
    inner = outer / "inner"
    inner.mkdir()

    def fake(cwd, *a):
        if a == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.repo_root(str(inner))


def test_repo_root_raises_on_ancestor_walk_oserror(tmp_path, monkeypatch):
    def fake(cwd, *a):
        if a == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    monkeypatch.setattr(sc, "git_dot_entry_ancestor",
                        lambda cwd: (_ for _ in ()).throw(OSError("walk failed")))
    with pytest.raises(sc.RepoRootUnavailable) as excinfo:
        sc.repo_root(str(tmp_path))
    assert "walk failed" in str(excinfo.value)


def test_repo_root_raises_when_git_dir_env_set(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere"))
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)

    def fake(cwd, *a):
        if a == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable) as excinfo:
        sc.repo_root(str(plain))
    assert "GIT_DIR" in str(excinfo.value)


def test_repo_root_raises_when_git_work_tree_env_set(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "nowhere"))

    def fake(cwd, *a):
        if a == ("rev-parse", "--show-toplevel"):
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable) as excinfo:
        sc.repo_root(str(plain))
    assert "GIT_WORK_TREE" in str(excinfo.value)


def test_repo_root_raises_on_non_not_a_repository_decline(tmp_path, monkeypatch):
    def fake(cwd, *a):
        return sc.GitResult(
            None, sc.GIT_DECLINED, "fatal: detected dubious ownership")

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.repo_root(str(tmp_path))


def test_get_gitdir_raises_on_git_unavailable(tmp_path, monkeypatch):
    def fake(cwd, *a):
        return sc.GitResult(None, sc.GIT_UNAVAILABLE, "timeout")

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.get_gitdir(str(tmp_path))


def test_get_gitdir_raises_on_corrupt_git_dir_pointer(tmp_path, monkeypatch):
    corrupt = tmp_path / "corrupt"
    corrupt.mkdir()
    (corrupt / "HEAD").write_text("garbage\n")
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_DIR", str(corrupt))
    with pytest.raises(sc.RepoRootUnavailable):
        sc.get_gitdir(str(plain))


def test_get_gitdir_raises_when_git_ancestor_present(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "r")
    sub = tmp_path / "r" / "sub"
    sub.mkdir()
    real = sc.run_git_result

    def fake(cwd, *a):
        if a and a[0] == "rev-parse":
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return real(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    with pytest.raises(sc.RepoRootUnavailable):
        sc.get_gitdir(str(sub))


def test_get_gitdir_bare_common_dir_joins_relative_to_cwd(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "r")
    real = sc.run_git_result

    def fake(cwd, *a):
        if a == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return sc.GitResult(None, sc.GIT_DECLINED, "unknown option --path-format")
        if a == ("rev-parse", "--git-common-dir"):
            return sc.GitResult(".git", sc.GIT_OK, None)
        return real(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    gd = sc.get_gitdir(repo)
    assert gd == os.path.realpath(os.path.join(repo, ".git"))


def test_get_gitdir_step3_absolute_git_dir(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "r")
    real = sc.run_git_result
    expected = real(repo, "rev-parse", "--absolute-git-dir").out

    def fake(cwd, *a):
        if a == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return sc.GitResult(None, sc.GIT_DECLINED, "usage")
        if a == ("rev-parse", "--git-common-dir"):
            return sc.GitResult(None, sc.GIT_DECLINED, "usage")
        if a == ("rev-parse", "--absolute-git-dir"):
            return sc.GitResult(expected, sc.GIT_OK, None)
        return real(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    assert sc.get_gitdir(repo) == os.path.realpath(expected)


def test_get_gitdir_all_fail_greenfield(tmp_path, monkeypatch):
    plain = str(tmp_path / "plain")
    os.makedirs(plain)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)

    def fake(cwd, *a):
        if a[0] == "rev-parse":
            return sc.GitResult(
                None, sc.GIT_DECLINED, "fatal: not a git repository")
        return sc.run_git_result(cwd, *a)

    monkeypatch.setattr(sc, "run_git_result", fake)
    assert sc.get_gitdir(plain) == os.path.realpath(plain)


def test_core_md_repo_root_unavailable_is_store_core_alias():
    import core_md as cm
    assert cm.RepoRootUnavailable is sc.RepoRootUnavailable


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


# ---------------------------------------------------------------------------
# issue #699 rider 11 — run_git_result / run_git equivalence
# ---------------------------------------------------------------------------

def test_run_git_result_unavailable_on_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("no git")),
    )
    res = sc.run_git_result(str(tmp_path), "rev-parse", "--show-toplevel")
    assert res.out is None
    assert res.status == sc.GIT_UNAVAILABLE


def test_run_git_result_unavailable_on_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("git", 10)),
    )
    res = sc.run_git_result(str(tmp_path), "rev-parse", "--show-toplevel")
    assert res.out is None
    assert res.status == sc.GIT_UNAVAILABLE


def test_run_git_result_declined_on_nonzero_exit(tmp_path, monkeypatch):
    class _Declined:
        returncode = 128
        stdout = ""
        stderr = "not a git repository"

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _Declined())
    res = sc.run_git_result(str(tmp_path), "rev-parse", "--show-toplevel")
    assert res.out is None
    assert res.status == sc.GIT_DECLINED


def test_run_git_wrapper_matches_run_git_result_out(tmp_path, monkeypatch):
    class _Ok:
        returncode = 0
        stdout = "  /repo/root\n"
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _Ok())
    res = sc.run_git_result(str(tmp_path), "rev-parse", "--show-toplevel")
    assert sc.run_git(str(tmp_path), "rev-parse", "--show-toplevel") == res.out == "/repo/root"

    class _Declined:
        returncode = 1
        stdout = ""
        stderr = "err"

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _Declined())
    res = sc.run_git_result(str(tmp_path), "status")
    assert res.out is None and sc.run_git(str(tmp_path), "status") is None


def test_not_a_repository_true_on_declined_not_a_git_repo():
    res = sc.GitResult(None, sc.GIT_DECLINED, "fatal: not a git repository")
    assert sc.not_a_repository(res) is True


def test_not_a_repository_false_on_other_declined():
    res = sc.GitResult(None, sc.GIT_DECLINED, "fatal: detected dubious ownership")
    assert sc.not_a_repository(res) is False
    assert sc.not_a_repository(sc.GitResult(None, sc.GIT_UNAVAILABLE, "x")) is False
    assert sc.not_a_repository(sc.GitResult("/repo", sc.GIT_OK, None)) is False
