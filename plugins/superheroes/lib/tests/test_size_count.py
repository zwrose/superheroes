"""Tests for size_count (#1447)."""
import subprocess

import pytest

import size_count


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, capture_output=True)
    return root


def _commit(root, *paths):
    if paths:
        subprocess.run(["git", "-C", str(root), "add", *paths], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "-q",
            "-m",
            "c",
        ],
        check=True,
        capture_output=True,
    )


def test_is_test_path():
    assert size_count.is_test_path("a/tests/b.py")
    assert size_count.is_test_path("tests/x")
    assert not size_count.is_test_path("contests/x.py")
    assert not size_count.is_test_path("test_x.py")


def test_whole_deleted_file_is_listed_not_counted(tmp_path):
    root = _init_repo(tmp_path)
    lib = root / "lib"
    lib.mkdir()
    gone = lib / "gone.py"
    keep = lib / "keep.py"
    gone.write_text("\n".join("line%d" % i for i in range(10)) + "\n", encoding="utf-8")
    keep.write_text("keep\n", encoding="utf-8")
    _commit(root, "lib")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(root), "rm", "lib/gone.py"], check=True, capture_output=True)
    keep.write_text("keep\na\nb\nc\n", encoding="utf-8")
    _commit(root, "lib/keep.py")
    out = size_count.collect(str(root), base, "HEAD")
    assert out["ok"] is True
    assert out["tripwireCount"] == 3
    assert out["deletedFiles"] == [{"path": "lib/gone.py", "lines": 10}]


def test_partial_deletion_still_counts(tmp_path):
    root = _init_repo(tmp_path)
    lib = root / "lib"
    lib.mkdir()
    keep = lib / "keep.py"
    keep.write_text("\n".join("line%d" % i for i in range(10)) + "\n", encoding="utf-8")
    _commit(root, "lib/keep.py")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    keep.write_text("\n".join("line%d" % i for i in range(6)) + "\n", encoding="utf-8")
    _commit(root, "lib/keep.py")
    out = size_count.collect(str(root), base, "HEAD")
    assert out["ok"] is True
    assert out["tripwireCount"] == 4
    assert out["deletedFiles"] == []
    assert out["barCount"] == 0


def test_test_paths_are_excluded(tmp_path):
    root = _init_repo(tmp_path)
    pkg = root / "pkg" / "tests"
    pkg.mkdir(parents=True)
    tf = pkg / "t_test.py"
    tf.write_text("\n".join("line%d" % i for i in range(5)) + "\n", encoding="utf-8")
    _commit(root, "pkg")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(root), "rm", "pkg/tests/t_test.py"], check=True, capture_output=True)
    _commit(root)
    out = size_count.collect(str(root), base, "HEAD")
    assert out["ok"] is True
    assert out["tripwireCount"] == 0
    assert out["barCount"] == 0
    assert out["deletedFiles"] == []


def test_rename_is_not_a_deletion(tmp_path):
    root = _init_repo(tmp_path)
    f = root / "lib" / "module.py"
    f.parent.mkdir(parents=True)
    f.write_text("a\nb\nc\n", encoding="utf-8")
    _commit(root, "lib")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(root), "mv", "lib/module.py", "lib/renamed.py"],
        check=True,
        capture_output=True,
    )
    (root / "lib" / "renamed.py").write_text("a\nb\nc\nd\n", encoding="utf-8")
    _commit(root, "lib")
    out = size_count.collect(str(root), base, "HEAD")
    assert out["ok"] is True
    assert out["deletedFiles"] == []
    assert out["tripwireCount"] == 1
    assert out["barCount"] == 1


def test_git_failure_is_not_a_count(tmp_path):
    root = _init_repo(tmp_path)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
    )
    out = size_count.collect(str(root), "0" * 40, "HEAD")
    assert out["ok"] is False
    assert out["reason"] == "git-failed"
    assert isinstance(out.get("detail"), str)
    assert out["detail"]


def test_count_binary_rows():
    rows = [(None, None, "img.png"), (2, 1, "lib/a.py")]
    deleted = set()
    out = size_count.count(rows, deleted)
    assert out["binary"] == ["img.png"]
    assert out["tripwireCount"] == 3
    assert out["barCount"] == 2


def test_count_whole_deleted_non_test_listed():
    rows = [(0, 10, "lib/gone.py"), (3, 0, "lib/keep.py")]
    deleted = {"lib/gone.py"}
    out = size_count.count(rows, deleted)
    assert out["tripwireCount"] == 3
    assert out["deletedFiles"] == [{"path": "lib/gone.py", "lines": 10}]


def test_count_empty_diff():
    out = size_count.count([], set())
    assert out["tripwireCount"] == 0
    assert out["barCount"] == 0
    assert out["deletedFiles"] == []
    assert out["binary"] == []
