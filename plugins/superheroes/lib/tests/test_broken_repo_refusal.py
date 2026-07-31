"""Broken-repo regression: refuse store-key derivation from nested cwd (issue #742 item 4).

From a nested subdirectory, broken/indeterminate git states must raise RepoRootUnavailable
(never key a store path off the subdirectory). Genuine greenfield non-git dirs still fall
back to realpath(cwd) — pinned elsewhere and left unchanged.

Structural fixtures only: never classify by matching git stderr prose.
"""
import os
import shutil
import subprocess
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import calibration_resolve as cr
import guardian_sweep as gsw
import hero_setup as HS
import mode_migrate as mm
import mode_registry as mr
import review_store as rs
import store
import store_core as sc


def _init_repo(path):
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)


def _nested_layout(tmp_path):
    repo = tmp_path / "repo"
    nested = repo / "pkg" / "deep"
    nested.mkdir(parents=True)
    return str(repo), str(nested)


_BROKEN_REPO_SHAPES = (
    "unreadable_git",
    "dead_gitdir_pointer",
    "git_unavailable",
    "external_git_dir_corrupt",
    "git_dir_nonexistent_work_tree",
)


def _assert_raises_repo_root_unavailable(fn, nested):
    with pytest.raises(sc.RepoRootUnavailable) as excinfo:
        fn()
    # The old fall-open bug keyed off the nested cwd, not the real repo root.
    msg = str(excinfo.value)
    refusal_markers = (
        ".git present",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "git could not be run",
        "git declined",
        "non-directory path",
        "nonexistent path",
        "cannot determine repository root",
    )
    assert any(marker in msg for marker in refusal_markers), msg


def _apply_unreadable_git(repo):
    _init_repo(repo)
    git_dir = os.path.join(repo, ".git")
    os.chmod(git_dir, 0)
    if os.access(git_dir, os.R_OK):
        pytest.skip("chmod 000 on .git does not deny access for this user")
    return git_dir


def _apply_dead_gitdir_pointer(repo):
    _init_repo(repo)
    shutil.rmtree(os.path.join(repo, ".git"))
    with open(os.path.join(repo, ".git"), "w", encoding="utf-8") as fh:
        fh.write("gitdir: /nonexistent/gitdir\n")


def _apply_git_unavailable(monkeypatch):
    real = sc.run_git_result

    def fake(cwd, *args):
        if args and args[0] == "rev-parse":
            return sc.GitResult(None, sc.GIT_UNAVAILABLE, "FileNotFoundError: no git")
        return real(cwd, *args)

    monkeypatch.setattr(sc, "run_git_result", fake)


def _apply_external_git_dir_corrupt(tmp_path, repo, monkeypatch):
    _init_repo(repo)
    corrupt = tmp_path / "corrupt-gitdir"
    corrupt.mkdir()
    (corrupt / "HEAD").write_text("garbage\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DIR", str(corrupt))
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)


def _apply_git_dir_nonexistent_work_tree(tmp_path, repo, monkeypatch):
    _init_repo(repo)
    nope = str(tmp_path / "NOPE")
    monkeypatch.setenv("GIT_DIR", os.path.join(repo, ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", nope)


@pytest.fixture
def registry_root(tmp_path):
    return str(tmp_path / "registry")


@pytest.fixture(autouse=True)
def _restore_unreadable_git_permissions(request):
    yield
    git_dir = getattr(request.node, "_restore_git_dir", None)
    if git_dir and os.path.isdir(git_dir):
        try:
            os.chmod(git_dir, 0o755)
        except OSError:
            pass


def _consumers(nested, registry_root):
    return {
        "calibration_resolve": lambda: cr.resolve(nested, root=registry_root),
        # hero_evidence anchors in-repo probes at repo root (_repo_root), not get_gitdir alone.
        "mode_registry": lambda: mr.hero_evidence(nested, registry_root),
        "mode_migrate": lambda: mm._in_repo_cal_dir(nested),
        "guardian_sweep": lambda: gsw.read_config(nested, registry_root),
        "review_store": lambda: rs.resolve(nested, "profile"),
        "store.get_repo_root": lambda: store.get_repo_root(nested),
    }


@pytest.mark.parametrize("shape", _BROKEN_REPO_SHAPES)
def test_broken_repo_refusal_from_nested_subdirectory(
        tmp_path, monkeypatch, registry_root, shape, request):
    repo, nested = _nested_layout(tmp_path)
    if shape == "unreadable_git":
        request.node._restore_git_dir = _apply_unreadable_git(repo)
    elif shape == "dead_gitdir_pointer":
        _apply_dead_gitdir_pointer(repo)
    elif shape == "git_unavailable":
        _apply_git_unavailable(monkeypatch)
    elif shape == "external_git_dir_corrupt":
        _apply_external_git_dir_corrupt(tmp_path, repo, monkeypatch)
    elif shape == "git_dir_nonexistent_work_tree":
        _apply_git_dir_nonexistent_work_tree(tmp_path, repo, monkeypatch)
    else:
        raise AssertionError("unknown shape: %s" % shape)

    for name, fn in _consumers(nested, registry_root).items():
        _assert_raises_repo_root_unavailable(fn, nested)


def test_greenfield_plain_directory_still_returns_realpath_cwd(tmp_path, monkeypatch):
    """Positive control: unconditional refusal would fail this — genuine greenfield must pass."""
    plain = str(tmp_path / "plain")
    os.makedirs(plain)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    assert sc.repo_root(plain) == os.path.realpath(plain)
    assert sc.get_gitdir(plain) == os.path.realpath(plain)


@pytest.mark.parametrize("shape", _BROKEN_REPO_SHAPES)
def test_hero_setup_never_raises_from_nested_subdirectory(
        tmp_path, monkeypatch, registry_root, shape, request):
    repo, nested = _nested_layout(tmp_path)
    if shape == "unreadable_git":
        request.node._restore_git_dir = _apply_unreadable_git(repo)
    elif shape == "dead_gitdir_pointer":
        _apply_dead_gitdir_pointer(repo)
    elif shape == "git_unavailable":
        _apply_git_unavailable(monkeypatch)
    elif shape == "external_git_dir_corrupt":
        _apply_external_git_dir_corrupt(tmp_path, repo, monkeypatch)
    elif shape == "git_dir_nonexistent_work_tree":
        _apply_git_dir_nonexistent_work_tree(tmp_path, repo, monkeypatch)
    else:
        raise AssertionError("unknown shape: %r" % (shape,))

    # Documented never-raise surface: read_declined / mark_declined (not offerable — it
    # probes layer paths and may propagate RepoRootUnavailable through core_md).
    assert HS.read_declined(nested, registry_root) == set()
    declined = HS.mark_declined(nested, "test-pilot", registry_root)
    assert declined.get("deferred") is True or declined["declined"] == []
