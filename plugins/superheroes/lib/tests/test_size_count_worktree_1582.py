"""Tests for size_count.collect working-tree mode (#1582): read-only, scrubbed, deadline-bounded."""
import json
import os
import subprocess
import time

import size_count

IDENT = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    ).stdout.decode()


def _commit(root, message="c"):
    _git(root, "add", "-A")
    _git(root, *IDENT, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD").strip()


def _lines(n, tag="x"):
    return "".join(f"{tag}{i}\n" for i in range(n))


def _repo(tmp_path, name="repo"):
    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text("*.log\n")
    (root / "keep.txt").write_text(_lines(5, "k"))
    (root / "gone.txt").write_text(_lines(4, "g"))
    return root, _commit(root, "base")


def test_committed_uncommitted_and_untracked_all_counted(tmp_path):
    root, base = _repo(tmp_path)
    (root / "added.txt").write_text(_lines(10, "a"))
    _commit(root, "add")
    (root / "keep.txt").write_text("k0\nk1\nn0\nn1\nn2\nk3\nk4\n")  # +3 -1
    (root / "new_mod.py").write_text(_lines(7, "m"))
    (root / "debug.log").write_text(_lines(50, "l"))
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text(_lines(20, "t"))

    result = size_count.collect(str(root), base, head=None)

    assert result["ok"] is True
    assert result["tripwireCount"] == 21
    assert result["worktree"] is True
    assert result["head"] is None
    assert result["base"] == base


def test_untracked_only_241_lines(tmp_path):
    root, base = _repo(tmp_path)
    (root / "big.py").write_text(_lines(241, "b"))

    result = size_count.collect(str(root), base, head=None)

    assert result["ok"] is True
    assert result["tripwireCount"] == 241


def test_assume_unchanged_refuses(tmp_path):
    root, base = _repo(tmp_path)
    _git(root, "update-index", "--assume-unchanged", "keep.txt")
    with open(root / "keep.txt", "a") as fh:
        fh.write(_lines(241, "z"))

    assert size_count.collect(str(root), base, head=None) == {
        "ok": False,
        "reason": "index-flags-hide-changes",
    }


def test_skip_worktree_refuses(tmp_path):
    root, base = _repo(tmp_path)
    _git(root, "update-index", "--skip-worktree", "keep.txt")
    with open(root / "keep.txt", "a") as fh:
        fh.write(_lines(241, "z"))

    assert size_count.collect(str(root), base, head=None) == {
        "ok": False,
        "reason": "index-flags-hide-changes",
    }


def test_both_flags_refuse(tmp_path):
    root, base = _repo(tmp_path)
    _git(root, "update-index", "--assume-unchanged", "--skip-worktree", "keep.txt")

    assert size_count.collect(str(root), base, head=None) == {
        "ok": False,
        "reason": "index-flags-hide-changes",
    }


def _objects(root):
    found = []
    for dirpath, _dirs, files in os.walk(root / ".git" / "objects"):
        found.extend(os.path.join(dirpath, f) for f in files)
    return sorted(found)


def test_working_tree_count_writes_no_git_state(tmp_path):
    root, base = _repo(tmp_path)
    (root / "keep.txt").write_text("changed\n")
    (root / "unique.py").write_text(f"{os.urandom(16).hex()}\n{os.urandom(16).hex()}\n")
    index = root / ".git" / "index"
    before = (
        index.read_bytes(),
        index.stat().st_mtime_ns,
        _objects(root),
        _git(root, "--no-optional-locks", "status", "--porcelain"),
    )

    result = size_count.collect(str(root), base, head=None)

    after = (
        index.read_bytes(),
        index.stat().st_mtime_ns,
        _objects(root),
        _git(root, "--no-optional-locks", "status", "--porcelain"),
    )
    assert result["ok"] is True
    assert result["tripwireCount"] == 8  # keep.txt +1 -5, unique.py +2
    assert after == before


def test_inherited_routing_env_is_ignored(tmp_path, monkeypatch):
    root_a, base_a = _repo(tmp_path, "a")
    root_b, _base_b = _repo(tmp_path, "b")
    (root_a / "only_a.py").write_text(_lines(9, "a"))
    (root_b / "only_b.py").write_text(_lines(300, "b"))
    monkeypatch.setenv("GIT_DIR", str(root_b / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(root_b))

    result = size_count.collect(str(root_a), base_a, head=None)

    assert result["ok"] is True
    assert result["tripwireCount"] == 9


def test_deadline_already_passed_runs_no_git(tmp_path, monkeypatch):
    root, base = _repo(tmp_path)
    calls = []

    def recorder(*args, **kwargs):
        calls.append(args)
        raise AssertionError("git must not run past the deadline")

    monkeypatch.setattr(subprocess, "run", recorder)

    result = size_count.collect(str(root), base, head=None, deadline=time.monotonic() - 1)

    assert result == {"ok": False, "reason": "git-timeout"}
    assert calls == []


def test_no_index_exit_two_is_git_failed(tmp_path, monkeypatch):
    root, base = _repo(tmp_path)
    (root / "new.py").write_text(_lines(3, "n"))
    real_run = subprocess.run

    def fake_run(argv, *args, **kwargs):
        if "--no-index" in argv:
            return subprocess.CompletedProcess(argv, 2, b"", b"fatal: boom\n")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = size_count.collect(str(root), base, head=None)

    assert result == {"ok": False, "reason": "git-failed", "detail": "fatal: boom"}


def test_timeout_is_git_timeout(tmp_path, monkeypatch):
    root, base = _repo(tmp_path)

    def fake_run(argv, *args, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert size_count.collect(str(root), base, head=None) == {
        "ok": False,
        "reason": "git-timeout",
    }


def test_missing_git_is_git_unavailable(tmp_path, monkeypatch):
    root, base = _repo(tmp_path)

    def fake_run(argv, *args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert size_count.collect(str(root), base, head=None) == {
        "ok": False,
        "reason": "git-unavailable",
    }


def test_unresolvable_base_is_git_failed(tmp_path):
    root, _base = _repo(tmp_path)

    result = size_count.collect(str(root), "no-such-ref", head=None)

    assert result["ok"] is False
    assert result["reason"] == "git-failed"


def test_untracked_binary_listed_not_counted(tmp_path):
    root, base = _repo(tmp_path)
    (root / "b.dat").write_bytes(b"\x00\x01\x02" * 100)

    result = size_count.collect(str(root), base, head=None)

    assert result["ok"] is True
    assert result["binary"] == ["b.dat"]
    assert result["tripwireCount"] == 0


def test_unstaged_deleted_tracked_file_is_listed_not_counted(tmp_path):
    root, base = _repo(tmp_path)
    os.remove(root / "gone.txt")

    result = size_count.collect(str(root), base, head=None)

    assert result["ok"] is True
    assert result["deletedFiles"] == [{"path": "gone.txt", "lines": 4}]
    assert result["tripwireCount"] == 0


def test_untracked_name_with_spaces_and_unicode_is_counted(tmp_path):
    root, base = _repo(tmp_path)
    (root / "my file é.py").write_text(_lines(6, "u"))

    result = size_count.collect(str(root), base, head=None)

    assert result["ok"] is True
    assert result["tripwireCount"] == 6


def test_no_changes_counts_zero(tmp_path):
    root, base = _repo(tmp_path)

    result = size_count.collect(str(root), base, head=None)

    assert result["ok"] is True
    assert result["tripwireCount"] == 0


def test_cli_worktree_flag(tmp_path, capsys):
    root, base = _repo(tmp_path)
    (root / "new.py").write_text(_lines(4, "n"))

    code = size_count.main(
        ["size_count.py", "count", "--base", base, "--repo-root", str(root), "--worktree"]
    )

    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["worktree"] is True
    assert out["tripwireCount"] == 4
