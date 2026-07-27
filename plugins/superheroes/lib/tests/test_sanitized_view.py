"""Tests for sanitized_view — disposable export with agent config stripped."""
import os
import subprocess
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import sanitized_view as sv


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path, *, commit=True, files=None):
    """Minimal git repo under path (str or Path)."""
    path = str(path)
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    for rel, content in (files or {"README.md": "hello\n"}).items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    if commit:
        _git(path, "add", "-A")
        _git(
            path,
            "-c",
            "user.email=test@test.local",
            "-c",
            "user.name=test",
            "commit",
            "-q",
            "-m",
            "init",
        )
    return path


def _build(repo):
    return sv.build_sanitized_view(repo)


# --- drift: config surface ----------------------------------------------------


def test_sanitized_config_tuples_pinned():
    assert sv.SANITIZED_CONFIG_FILES == (
        "AGENTS.md",
        "AGENTS.local.md",
        "CLAUDE.md",
        "CLAUDE.local.md",
        "GEMINI.md",
        "copilot-instructions.md",
        ".cursorrules",
        ".windsurfrules",
        ".clinerules",
        ".aiderrules",
        ".goosehints",
    )
    assert sv.SANITIZED_CONFIG_DIRS == (
        ".claude",
        ".codex",
        ".cursor",
        ".aider",
        ".windsurf",
        ".gemini",
    )
    for name in sv.SANITIZED_CONFIG_FILES:
        assert "/" not in name and "\\" not in name
    for name in sv.SANITIZED_CONFIG_DIRS:
        assert "/" not in name and "\\" not in name


# --- fail-closed edges --------------------------------------------------------


def test_linked_worktree_builds(tmp_path):
    main = _init_repo(tmp_path / "main")
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", str(linked), "-q")
    assert os.path.isfile(os.path.join(linked, ".git"))
    view = _build(str(linked))
    try:
        assert view["strategy"] == sv.SANITIZED_VIEW_STRATEGY
        assert os.path.isdir(os.path.join(view["path"], ".git"))
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_tempbase_inside_repo_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    fake_tmp = os.path.join(repo, "tmpdir")
    os.makedirs(fake_tmp)
    monkeypatch.setattr(sv.tempfile, "gettempdir", lambda: fake_tmp)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo)
    assert exc.value.detail == "sanitized-view-tempbase-inside-repo"
    assert not os.path.isdir(os.path.join(fake_tmp, "superheroes-sanitized-view-"))


def test_head_unresolved_no_commits(tmp_path):
    repo = _init_repo(tmp_path / "empty", commit=False)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo)
    assert exc.value.detail == "sanitized-view-head-unresolved"


def test_export_failed_cleans_up(tmp_path, monkeypatch):
    import tempfile

    repo = _init_repo(tmp_path / "repo")
    created = []
    orig_mkdtemp = tempfile.mkdtemp

    def track_mkdtemp(*args, **kwargs):
        path = orig_mkdtemp(*args, **kwargs)
        created.append(path)
        return path

    monkeypatch.setattr(sv.tempfile, "mkdtemp", track_mkdtemp)
    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        if len(argv) >= 5 and argv[0:4] == ["git", "-C", repo, "archive"]:
            class R:
                returncode = 1
                stdout = b""
                stderr = b"archive failed"

            return R()
        return real_run(argv, **kwargs)

    monkeypatch.setattr(sv.subprocess, "run", fake_run)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo)
    assert exc.value.detail == "sanitized-view-export-failed"
    assert created
    assert all(not os.path.exists(p) for p in created)


def test_init_failed_cleans_up(tmp_path, monkeypatch):
    import tempfile

    repo = _init_repo(tmp_path / "repo")
    created = []
    orig_mkdtemp = tempfile.mkdtemp

    def track_mkdtemp(*args, **kwargs):
        path = orig_mkdtemp(*args, **kwargs)
        created.append(path)
        return path

    monkeypatch.setattr(sv.tempfile, "mkdtemp", track_mkdtemp)
    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        if argv[0] == "git" and "commit" in argv:
            class R:
                returncode = 1
                stdout = b""
                stderr = b"commit failed"
            return R()
        return real_run(argv, **kwargs)

    monkeypatch.setattr(sv.subprocess, "run", fake_run)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo)
    assert exc.value.detail == "sanitized-view-init-failed"
    assert created
    assert all(not os.path.exists(p) for p in created)


def test_no_config_paths_still_builds(tmp_path):
    repo = _init_repo(
        tmp_path / "plain",
        files={"src/app.py": "MARKER_STRING\n"},
    )
    view = _build(repo)
    try:
        assert view["stripped"] == []
        assert view["strippedCount"] == 0
        assert _git(view["path"], "rev-parse", "HEAD").returncode == 0
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_nested_config_dir_stripped_once(tmp_path):
    repo = _init_repo(
        tmp_path / "nested",
        files={
            "a/b/.cursor/rules.md": "secret\n",
            "a/b/keep.txt": "ok\n",
        },
    )
    view = _build(repo)
    try:
        assert view["stripped"] == ["a/b/.cursor"]
        assert not os.path.exists(os.path.join(view["path"], "a", "b", ".cursor"))
        assert os.path.isfile(os.path.join(view["path"], "a", "b", "keep.txt"))
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_destroy_never_raises(tmp_path):
    missing = str(tmp_path / "nope")
    sv.destroy_sanitized_view(missing)
    repo = _init_repo(tmp_path / "repo")
    view = sv.build_sanitized_view(repo)
    path = view["path"]
    sv.destroy_sanitized_view(path)
    sv.destroy_sanitized_view(path)


# --- isolation and matching semantics -----------------------------------------


def test_isolation_worktree_and_object_db(tmp_path):
    repo = _init_repo(
        tmp_path / "iso",
        files={
            "CLAUDE.md": "top secret\n",
            "sub/AGENTS.md": "nested secret\n",
            ".cursor/rules.md": "cursor secret\n",
            "src/visible.py": "VISIBLE_GREP_TOKEN\n",
        },
    )
    view = sv.build_sanitized_view(repo)
    try:
        root = view["path"]
        assert not os.path.exists(os.path.join(root, "CLAUDE.md"))
        assert not os.path.exists(os.path.join(root, "sub", "AGENTS.md"))
        assert not os.path.exists(os.path.join(root, ".cursor"))
        show = _git(root, "show", "HEAD:CLAUDE.md", check=False)
        assert show.returncode != 0
        assert "does not exist" in (show.stderr or "").lower() or show.returncode != 0
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_similar_names_not_stripped(tmp_path):
    repo = _init_repo(
        tmp_path / "similar",
        files={
            "CLAUDE.md.bak": "bak\n",
            "docs/AGENTS.md.txt": "txt\n",
            "claude.md": "lower\n",
        },
    )
    view = _build(repo)
    try:
        root = view["path"]
        assert view["stripped"] == []
        assert os.path.isfile(os.path.join(root, "CLAUDE.md.bak"))
        assert os.path.isfile(os.path.join(root, "docs", "AGENTS.md.txt"))
        assert os.path.isfile(os.path.join(root, "claude.md"))
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_view_git_clean_and_grep_works(tmp_path):
    repo = _init_repo(
        tmp_path / "grep",
        files={"lib/module.py": "UNIQUE_SANITIZED_VIEW_GREP\n"},
    )
    view = sv.build_sanitized_view(repo)
    try:
        root = view["path"]
        status = _git(root, "status", "--porcelain", check=False)
        assert status.stdout.strip() == ""
        grep = _git(root, "grep", "UNIQUE_SANITIZED_VIEW_GREP", check=False)
        assert grep.returncode == 0
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_source_dirty_tracked_only(tmp_path):
    repo = _init_repo(tmp_path / "dirty", files={"tracked.txt": "a\n"})
    clean = sv.build_sanitized_view(repo)
    sv.destroy_sanitized_view(clean["path"])
    assert clean["sourceDirty"] is False

    with open(os.path.join(repo, "tracked.txt"), "a", encoding="utf-8") as fh:
        fh.write("modified\n")
    dirty = sv.build_sanitized_view(repo)
    sv.destroy_sanitized_view(dirty["path"])
    assert dirty["sourceDirty"] is True

    os.makedirs(os.path.join(repo, "untracked_only"), exist_ok=True)
    with open(os.path.join(repo, "untracked_only", "new.txt"), "w", encoding="utf-8") as fh:
        fh.write("x\n")
    untracked = sv.build_sanitized_view(repo)
    sv.destroy_sanitized_view(untracked["path"])
    assert untracked["sourceDirty"] is True  # still dirty from tracked mod

    _git(repo, "checkout", "--", "tracked.txt")
    only_untracked = sv.build_sanitized_view(repo)
    sv.destroy_sanitized_view(only_untracked["path"])
    assert only_untracked["sourceDirty"] is False


def test_source_dirty_false_when_only_untracked(tmp_path):
    repo = _init_repo(tmp_path / "ut", files={"keep.txt": "k\n"})
    with open(os.path.join(repo, "brand_new.txt"), "w", encoding="utf-8") as fh:
        fh.write("never added\n")
    view = _build(repo)
    try:
        assert view["sourceDirty"] is False
    finally:
        sv.destroy_sanitized_view(view["path"])
