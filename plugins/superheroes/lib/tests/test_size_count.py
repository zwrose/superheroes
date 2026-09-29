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


MATCHES = [
    ("test/integration/x.ts", "dir-test"),
    ("a/tests/b.py", "dir-tests"),
    ("src/lib/__tests__/foo.ts", "dir-__tests__"),
    ("spec/models/user_rb.rb", "dir-spec"),
    ("e2e/login.ts", "dir-e2e"),
    ("src/foo.test.ts", "glob-*.test.*"),
    ("src/foo.spec.tsx", "glob-*.spec.*"),
    ("lib/test_x.py", "glob-test_*.py"),
    ("pkg/x_test.py", "glob-*_test.py"),
    ("pkg/x_test.go", "glob-*_test.go"),
    ("go/pkg/testdata/golden.txt", "dir-testdata"),
    ("src/__mocks__/api.ts", "dir-__mocks__"),
    ("src/__fixtures__/user.json", "dir-__fixtures__"),
    ("plugins/x/conftest.py", "glob-conftest.py"),
    ("Tests/x.py", "dir-case-Tests"),
    ("src/__Mocks__/api.ts", "dir-case-__Mocks__"),
    ("E2E/login.ts", "dir-case-E2E"),
]

LOOK_ALIKES = [
    "docs/testing.md",
    "lib/contest.py",
    "contests/x.py",
    "plugins/superheroes/skills/test-pilot-plan/SKILL.md",
    "plugins/superheroes/evals/w2-size-tripwire/prompt.md",
    "plugins/superheroes/eval/lib/run.py",
    "docs/decisions/specs/x.md",
    "src/test-utils/render.tsx",
    "lib/latest.py",
    "lib/attestation.go",
    "src/testing.ts",
    "lib/x_test.rb",
    "",
    "lib/mocks.py",
    "docs/fixtures.md",
    "src/testdata.ts",
    "conftest.py.bak",
    "fixtures/seed.json",
    "mocks/client.ts",
    "src/Foo.Test.ts",
    "Conftest.py",
    "lib/myconftest.py",
]

BARE_NAMES = ["test", "tests", "__tests__", "spec", "e2e", "lib/tests", "testdata", "__mocks__", "__fixtures__"]

GLOB_DIRS = [
    "src/widget.test.ts/index.ts",
    "src/widget.spec.ts/index.ts",
    "test_dir.py/mod.rb",
    "src/conftest.py/index.rb",
]

COUNT_ROWS = [
    (5, 1, "src/__tests__/a.ts"),
    (7, 0, "src/foo.test.ts"),
    (3, 2, "src/app.ts"),
    (4, 0, "tests"),
    (2, 0, "src/widget.test.ts/index.ts"),
]


@pytest.mark.parametrize("path,case_id", MATCHES, ids=[m[1] for m in MATCHES])
def test_is_test_path_matches_each_convention(path, case_id):
    assert size_count.is_test_path(path)


def test_is_test_path_matches_backslash():
    assert size_count.is_test_path("a\\tests\\b.py")


@pytest.mark.parametrize("path", LOOK_ALIKES)
def test_is_test_path_rejects_look_alikes(path):
    assert not size_count.is_test_path(path)


@pytest.mark.parametrize("path", BARE_NAMES)
def test_is_test_path_directory_names_never_match_the_file_name(path):
    assert not size_count.is_test_path(path)


@pytest.mark.parametrize("path", GLOB_DIRS)
def test_is_test_path_globs_never_match_a_directory(path):
    assert not size_count.is_test_path(path)


def test_count_skips_test_paths_and_counts_look_alikes():
    out = size_count.count(COUNT_ROWS, set())
    assert out["tripwireCount"] == 11
    assert out["barCount"] == 9


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
    assert out["barCount"] == 3
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


def test_bar_exclude_counts_tripwire_not_bar():
    path = "docs/generated/readme.md"
    out = size_count.count(
        [(100, 0, path), (5, 0, "lib/a.py")],
        set(),
        bar_exclude=(path,),
    )
    assert out["tripwireCount"] == 105
    assert out["barCount"] == 5
    assert out["barExcluded"] == [path]


def test_revision_starting_with_dash_is_not_an_option(tmp_path):
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
    trap = tmp_path / "trap-output.json"
    trap_str = str(trap)
    out = size_count.collect(str(root), "--output=%s" % trap_str, "HEAD")
    assert out["ok"] is False
    assert out["reason"] == "git-failed"
    assert not trap.exists()
