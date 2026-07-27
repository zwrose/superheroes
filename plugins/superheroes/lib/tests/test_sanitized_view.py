"""Tests for sanitized_view — disposable export with agent config stripped."""
import os
import subprocess
import sys
import time

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


def _leftover_view_dirs(tmp_base):
    try:
        return [
            name
            for name in os.listdir(tmp_base)
            if name.startswith(sv.SANITIZED_VIEW_DIR_PREFIX)
        ]
    except OSError:
        return []


# --- drift: config surface ----------------------------------------------------


def test_sanitized_config_tuples_pinned():
    assert sv.SANITIZED_CONFIG_FILES == (
        "AGENTS.md",
        "AGENTS.local.md",
        "AGENTS.override.md",
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


def test_every_config_name_stripped_root_and_nested(tmp_path):
    files = {"survives.txt": "ok\n"}
    stripped_expected = []
    for name in sv.SANITIZED_CONFIG_FILES:
        files[name] = "root\n"
        files["nested/%s" % name] = "nested\n"
        stripped_expected.append(name)
        stripped_expected.append("nested/%s" % name)
    for name in sv.SANITIZED_CONFIG_DIRS:
        files["%s/inside.txt" % name] = "d\n"
        files["pkg/%s/x.txt" % name] = "d\n"
        stripped_expected.append(name)
        stripped_expected.append("pkg/%s" % name)
    repo = _init_repo(tmp_path / "allnames", files=files)
    view = _build(repo)
    try:
        assert view["stripped"] == sorted(stripped_expected)
        root = view["path"]
        assert os.path.isfile(os.path.join(root, "survives.txt"))
        for rel in stripped_expected:
            assert not os.path.exists(os.path.join(root, *rel.split("/")))
    finally:
        sv.destroy_sanitized_view(view["path"])


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
    assert _leftover_view_dirs(fake_tmp) == []


def test_head_unresolved_no_commits(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "empty", commit=False)
    fake_tmp = str(tmp_path / "tmpdir")
    os.makedirs(fake_tmp)
    monkeypatch.setattr(sv.tempfile, "gettempdir", lambda: fake_tmp)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo)
    assert exc.value.detail == "sanitized-view-head-unresolved"
    assert _leftover_view_dirs(fake_tmp) == []


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
    real_popen = subprocess.Popen

    def fake_popen(argv, **kwargs):
        if len(argv) >= 5 and argv[0:4] == ["git", "-C", repo, "archive"]:

            class SlowStdout:
                def read(self, size):
                    return b""

            class Proc:
                def __init__(self):
                    self.returncode = 1
                    self.stdout = SlowStdout()
                    self.stderr = None

                def poll(self):
                    return self.returncode

                def wait(self, timeout=None):
                    return self.returncode

                def terminate(self):
                    pass

                def kill(self):
                    pass

            return Proc()
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(sv.subprocess, "Popen", fake_popen)
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


def test_export_incomplete_export_ignore(tmp_path):
    repo = _init_repo(
        tmp_path / "ignore",
        files={
            "normal.py": "print('ok')\n",
            "secret.py": "SECRET\n",
            ".gitattributes": "secret.py export-ignore\n.gitattributes export-ignore\n",
        },
    )
    with pytest.raises(sv.SanitizedViewError) as exc:
        _build(repo)
    assert exc.value.detail == "sanitized-view-export-incomplete"


def test_export_too_large(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "big", files={"tiny.txt": "x\n"})
    monkeypatch.setattr(sv, "SANITIZED_VIEW_EXPORT_MAX_BYTES", 4)
    with pytest.raises(sv.SanitizedViewError) as exc:
        _build(repo)
    assert exc.value.detail == "sanitized-view-export-too-large"


def test_export_timeout(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "slow", files={"tiny.txt": "x\n"})
    monkeypatch.setattr(sv, "SANITIZED_VIEW_EXPORT_TIMEOUT_SECONDS", 0.001)
    real_read = None

    class SlowReader:
        def __init__(self, inner):
            self._inner = inner

        def read(self, size):
            time.sleep(0.05)
            return self._inner.read(size)

    real_popen = subprocess.Popen

    def wrapping_popen(argv, **kwargs):
        proc = real_popen(argv, **kwargs)
        if len(argv) >= 5 and argv[0:4] == ["git", "-C", repo, "archive"]:
            proc.stdout = SlowReader(proc.stdout)
        return proc

    monkeypatch.setattr(sv.subprocess, "Popen", wrapping_popen)
    with pytest.raises(sv.SanitizedViewError) as exc:
        _build(repo)
    assert exc.value.detail == "sanitized-view-export-timeout"


def test_only_agents_md_tracked(tmp_path):
    repo = _init_repo(tmp_path / "onlyagents", files={"AGENTS.md": "only\n"})
    view = _build(repo)
    try:
        assert view["stripped"] == ["AGENTS.md"]
        assert view["strippedCount"] == 1
        assert _git(view["path"], "rev-parse", "HEAD").returncode == 0
    finally:
        sv.destroy_sanitized_view(view["path"])


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


def test_head_sha_and_measurements(tmp_path):
    repo = _init_repo(
        tmp_path / "measure",
        files={"only.txt": "abcdef\n"},
    )
    source_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    view = _build(repo)
    try:
        assert view["headSha"] == source_head
        assert view["fileCount"] == 1
        assert view["bytes"] == len("abcdef\n")
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
    assert sv.destroy_sanitized_view(missing) is True
    repo = _init_repo(tmp_path / "repo")
    view = sv.build_sanitized_view(repo)
    path = view["path"]
    assert sv.destroy_sanitized_view(path) is True
    assert not os.path.exists(path)
    assert sv.destroy_sanitized_view(path) is True


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
        for obj in ("HEAD:CLAUDE.md", "HEAD:sub/AGENTS.md", "HEAD:.cursor/rules.md"):
            show = _git(root, "show", obj, check=False)
            assert show.returncode != 0
        count = _git(root, "rev-list", "--count", "--all", check=False)
        assert count.stdout.strip() == "1"
        parent = _git(root, "rev-parse", "HEAD~1", check=False)
        assert parent.returncode != 0
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_similar_names_not_stripped(tmp_path):
    """Order-authorized inversion: claude.md is stripped (case variant); unlike basenames survive."""
    repo = _init_repo(
        tmp_path / "similar",
        files={
            "CLAUDE.md.bak": "bak\n",
            "docs/AGENTS.md.txt": "txt\n",
            "claude.md": "lower\n",
            "agents.md": "agents lower\n",
            ".Cursor/rules.md": "cursor case\n",
            "Claude.MD": "mixed case\n",
        },
    )
    view = _build(repo)
    try:
        root = view["path"]
        stripped_set = set(view["stripped"])
        assert stripped_set >= {".Cursor", "agents.md"}
        assert "claude.md" in stripped_set or "Claude.MD" in stripped_set
        assert len(stripped_set) == len(
            {p.casefold() for p in stripped_set}
        )
        assert os.path.isfile(os.path.join(root, "CLAUDE.md.bak"))
        assert os.path.isfile(os.path.join(root, "docs", "AGENTS.md.txt"))
        assert not os.path.exists(os.path.join(root, "claude.md"))
        assert not os.path.exists(os.path.join(root, "agents.md"))
        assert not os.path.exists(os.path.join(root, ".Cursor"))
        assert not os.path.exists(os.path.join(root, "Claude.MD"))
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_untracked_excluded_and_dirty_uses_committed_bytes(tmp_path):
    repo = _init_repo(
        tmp_path / "wt",
        files={"tracked.txt": "COMMITTED_BYTES\n"},
    )
    secret = os.path.join(repo, "never_added_secret.txt")
    with open(secret, "w", encoding="utf-8") as fh:
        fh.write("UNTRACKED_LEAK\n")
    dirty_path = os.path.join(repo, "tracked.txt")
    with open(dirty_path, "w", encoding="utf-8") as fh:
        fh.write("DIRTY_WORKTREE\n")
    view = _build(repo)
    try:
        root = view["path"]
        assert not os.path.exists(os.path.join(root, "never_added_secret.txt"))
        with open(os.path.join(root, "tracked.txt"), encoding="utf-8") as fh:
            assert fh.read() == "COMMITTED_BYTES\n"
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_sanitized_view_notice_no_repo_paths(tmp_path):
    repo = _init_repo(
        tmp_path / "notice",
        files={
            "do_not_echo_this_dir_name/AGENTS.md": "x\n",
            "CLAUDE.md": "y\n",
        },
    )
    view = _build(repo)
    try:
        notice = sv.sanitized_view_notice(view)
        assert "do_not_echo_this_dir_name" not in notice
        assert "evil/inject" not in notice
        assert "AGENTS.md" in notice
        assert "CLAUDE.md" in notice
        assert "2 path(s) removed" in notice
        assert view["stripped"]
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


def test_source_dirty_unknown_when_status_fails(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "statusfail", files={"a.txt": "a\n"})
    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        if len(argv) >= 4 and argv[0:3] == ["git", "-C", repo] and argv[3] == "status":
            class R:
                returncode = 1
                stdout = ""
                stderr = "fail"
            return R()
        return real_run(argv, **kwargs)

    monkeypatch.setattr(sv.subprocess, "run", fake_run)
    view = _build(repo)
    try:
        assert view["sourceDirty"] is None
    finally:
        sv.destroy_sanitized_view(view["path"])


def test_strip_oserror_cleans_temp_dir(tmp_path, monkeypatch):
    import tempfile

    repo = _init_repo(tmp_path / "stripfail", files={"CLAUDE.md": "x\n", "keep.txt": "y\n"})
    tmp_base = tmp_path / "tmpdir"
    tmp_base.mkdir()
    monkeypatch.setattr(sv.tempfile, "gettempdir", lambda: str(tmp_base))
    real_remove = os.remove

    def boom_remove(path):
        if path.endswith("CLAUDE.md"):
            raise OSError("simulated strip failure")
        return real_remove(path)

    monkeypatch.setattr(sv.os, "remove", boom_remove)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo)
    assert exc.value.detail == "sanitized-view-export-failed"
    assert _leftover_view_dirs(str(tmp_base)) == []


def test_source_dirty_false_when_only_untracked(tmp_path):
    repo = _init_repo(tmp_path / "ut", files={"keep.txt": "k\n"})
    with open(os.path.join(repo, "brand_new.txt"), "w", encoding="utf-8") as fh:
        fh.write("never added\n")
    view = _build(repo)
    try:
        assert view["sourceDirty"] is False
    finally:
        sv.destroy_sanitized_view(view["path"])
