"""Tests for `.github/scripts/verify_touched_tests.py` (#1307).

The behaviour that matters is the fail direction: a changed mapped-root module with no
resolvable test file must exit non-zero naming the module, and a diff with no code in it must
exit 0 saying so. Those two, plus the resolution mapping, are what these tests pin.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

import verify_touched_tests as V

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_SCRIPT = os.path.join(_REPO_ROOT, ".github", "scripts", "verify_touched_tests.py")


def _touch(root, rel, body="# x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


# ---------------------------------------------------------------- mapping


def test_mapped_module_recognises_each_lib_root():
    assert V.mapped_module("plugins/superheroes/lib/core_md.py") == (
        "plugins/superheroes/lib", "core_md")
    assert V.mapped_module("eval/lib/skills.py") == ("eval/lib", "skills")


def test_mapped_module_ignores_tests_and_unmapped_paths():
    assert V.mapped_module("plugins/superheroes/lib/tests/test_core_md.py") is None
    assert V.mapped_module("plugins/superheroes/lib/sub/deeper.py") is None
    assert V.mapped_module(".github/scripts/validate_hosts.py") is None
    assert V.mapped_module("README.md") is None


def test_lib_roots_exist_in_this_repository():
    # A root that has been renamed would silently stop mapping anything.
    for root in V.LIB_ROOTS:
        assert os.path.isdir(os.path.join(_REPO_ROOT, root, "tests")), root


# ------------------------------------------------------------- resolution


def test_changed_test_file_resolves_itself(tmp_path):
    root = str(tmp_path)
    _touch(root, "plugins/superheroes/lib/tests/test_thing.py")
    files, unresolved, code = V.resolve_targets(
        root, ["plugins/superheroes/lib/tests/test_thing.py"])
    assert files == ["plugins/superheroes/lib/tests/test_thing.py"]
    assert unresolved == []
    assert code is True


def test_changed_module_resolves_its_prefix_matched_siblings(tmp_path):
    root = str(tmp_path)
    _touch(root, "plugins/superheroes/lib/round_certification.py")
    _touch(root, "plugins/superheroes/lib/tests/test_round_certification.py")
    _touch(root, "plugins/superheroes/lib/tests/test_round_certification_extra.py")
    _touch(root, "plugins/superheroes/lib/tests/test_unrelated.py")
    files, unresolved, code = V.resolve_targets(
        root, ["plugins/superheroes/lib/round_certification.py"])
    assert files == [
        "plugins/superheroes/lib/tests/test_round_certification.py",
        "plugins/superheroes/lib/tests/test_round_certification_extra.py",
    ]
    assert unresolved == []
    assert code is True


def test_deleted_test_file_is_not_handed_to_pytest(tmp_path):
    # The path is in the diff but no longer on disk; pytest would error on it.
    files, unresolved, code = V.resolve_targets(
        str(tmp_path), ["plugins/superheroes/lib/tests/test_gone.py"])
    assert files == []
    assert unresolved == []
    assert code is True


def test_deleted_module_with_its_tests_gone_too_is_not_a_mapping_miss(tmp_path):
    # A retirement commit deletes the module and its tests together; that is not a miss.
    files, unresolved, code = V.resolve_targets(
        str(tmp_path), ["plugins/superheroes/lib/retired.py"])
    assert (files, unresolved, code) == ([], [], True)


def test_deleted_module_still_runs_its_surviving_tests(tmp_path):
    # The surviving test is the one that should now fail (it imports a module that is gone);
    # exempting the deletion outright would let that failure pass unseen.
    root = str(tmp_path)
    _touch(root, "eval/lib/tests/test_skills.py")
    files, unresolved, code = V.resolve_targets(root, ["eval/lib/skills.py"])
    assert files == ["eval/lib/tests/test_skills.py"]
    assert unresolved == []
    assert code is True


def test_unmapped_module_with_no_test_is_not_unresolved(tmp_path):
    # Only the mapped library roots carry the module -> test obligation.
    files, unresolved, code = V.resolve_targets(str(tmp_path), [".github/scripts/whatever.py"])
    assert (files, unresolved, code) == ([], [], True)


def test_non_python_changes_are_not_code(tmp_path):
    files, unresolved, code = V.resolve_targets(str(tmp_path), ["README.md", "docs/x.md"])
    assert (files, unresolved, code) == ([], [], False)


# ------------------------------------------------------------ fail direction


def test_mapped_module_without_a_test_file_is_unresolved(tmp_path):
    root = str(tmp_path)
    _touch(root, "eval/lib/orphan.py")
    os.makedirs(os.path.join(root, "eval/lib/tests"), exist_ok=True)
    files, unresolved, code = V.resolve_targets(root, ["eval/lib/orphan.py"])
    assert files == []
    assert unresolved == ["eval/lib/orphan.py"]
    assert code is True


def test_unresolved_module_exits_non_zero_naming_the_module(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _touch(root, "plugins/superheroes/lib/orphan.py")
    monkeypatch.setattr(V, "changed_paths",
                        lambda *a, **k: ["plugins/superheroes/lib/orphan.py"])
    code = V.main(["--repo-root", root])
    assert code == 1
    err = capsys.readouterr().err
    assert "plugins/superheroes/lib/orphan.py" in err


def test_unresolved_module_blocks_even_when_another_module_resolved(tmp_path, monkeypatch):
    # Fail-closed per module: one resolvable sibling must not mask a mapping miss.
    root = str(tmp_path)
    _touch(root, "plugins/superheroes/lib/orphan.py")
    _touch(root, "plugins/superheroes/lib/paired.py")
    _touch(root, "plugins/superheroes/lib/tests/test_paired.py")
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [
        "plugins/superheroes/lib/orphan.py", "plugins/superheroes/lib/paired.py"])
    assert V.main(["--repo-root", root]) == 1


def test_docs_only_diff_exits_zero_with_a_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: ["README.md"])
    assert V.main(["--repo-root", str(tmp_path)]) == 0
    assert "no code changed" in capsys.readouterr().out


def test_code_change_outside_the_mapping_exits_zero_and_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [".github/scripts/thing.py"])
    assert V.main(["--repo-root", str(tmp_path)]) == 0
    assert "no touched test files resolved" in capsys.readouterr().out


def test_unresolvable_base_ref_exits_two(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise V.GitError("base ref 'nope' does not resolve")
    monkeypatch.setattr(V, "changed_paths", boom)
    assert V.main(["--repo-root", str(tmp_path)]) == 2
    assert "does not resolve" in capsys.readouterr().err


# ------------------------------------------------------------ pytest command


def test_pytest_command_pins_the_cache_prefix_and_flags():
    cmd = V.pytest_command("/usr/bin/python3", ["a/test_x.py"])
    assert cmd == ["/usr/bin/python3", "-B", "-X", "pycache_prefix=/private/tmp/superheroes-pyc",
                   "-m", "pytest", "a/test_x.py", "-q", "-n", "auto", "-p", "no:cacheprovider"]


def test_main_runs_pytest_on_exactly_the_resolved_files(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _touch(root, "plugins/superheroes/lib/thing.py")
    _touch(root, "plugins/superheroes/lib/tests/test_thing.py")
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: ["plugins/superheroes/lib/thing.py"])
    seen = {}

    def fake_run(cmd, cwd=None):
        seen["cmd"], seen["cwd"] = cmd, cwd
        class R:
            returncode = 3
        return R()

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    assert V.main(["--repo-root", root]) == 3
    assert seen["cwd"] == root
    assert seen["cmd"][seen["cmd"].index("pytest") + 1:] == [
        "plugins/superheroes/lib/tests/test_thing.py",
        "-q", "-n", "auto", "-p", "no:cacheprovider"]
    assert "plugins/superheroes/lib/tests/test_thing.py" in capsys.readouterr().out


def test_list_only_does_not_run_pytest(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _touch(root, "plugins/superheroes/lib/tests/test_thing.py")
    monkeypatch.setattr(V, "changed_paths",
                        lambda *a, **k: ["plugins/superheroes/lib/tests/test_thing.py"])

    def explode(*a, **k):  # pragma: no cover - the assertion is that it never runs
        raise AssertionError("pytest must not run under --list-only")

    monkeypatch.setattr(V.subprocess, "run", explode)
    assert V.main(["--repo-root", root, "--list-only"]) == 0
    assert "would run" in capsys.readouterr().out


# ------------------------------------------------------------ git integration


def _git(root, *args):
    subprocess.run(("git", "-C", root) + args, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path):
    root = str(tmp_path / "repo")
    os.makedirs(root)
    _git(root, "init", "-q", "-b", "main")
    # A throwaway fixture repo has no configured identity on a CI runner.
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    _touch(root, "seed.txt", "seed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    return root


def test_changed_paths_sees_committed_and_uncommitted_and_untracked(repo):
    _touch(repo, "committed.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work")
    _touch(repo, "seed.txt", "seed changed\n")   # uncommitted edit to a tracked file
    _touch(repo, "untracked.py")                  # never added
    paths = V.changed_paths(repo, base="main~1")
    assert set(paths) >= {"committed.py", "seed.txt", "untracked.py"}


def test_range_mode_compares_commits_only(repo):
    _touch(repo, "committed.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work")
    _touch(repo, "untracked.py")
    paths = V.changed_paths(repo, diff_range="main~1..main")
    assert paths == ["committed.py"]


def test_rename_keeps_the_pre_image_so_surviving_tests_still_run(repo):
    # git reports only the post-image for a detected rename. Moving a mapped module out of its
    # root would then hide the surviving test that imports it — red, and never run.
    _touch(repo, "plugins/superheroes/lib/foo.py", "VALUE = 1\n" * 40)
    _touch(repo, "plugins/superheroes/lib/tests/test_foo.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "module and its test")
    os.makedirs(os.path.join(repo, "plugins/superheroes/lib/sub"), exist_ok=True)
    os.rename(os.path.join(repo, "plugins/superheroes/lib/foo.py"),
              os.path.join(repo, "plugins/superheroes/lib/sub/foo.py"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "move it out of the mapped root")

    paths = V.changed_paths(repo, base="main~1")
    assert "plugins/superheroes/lib/foo.py" in paths      # the pre-image survives the listing
    files, unresolved, _ = V.resolve_targets(repo, paths)
    assert "plugins/superheroes/lib/tests/test_foo.py" in files
    assert unresolved == []


def test_non_ascii_path_survives_gits_default_quoting(repo):
    # With core.quotePath (git's default) a non-ASCII path comes back C-quoted and stops
    # ending in ".py"; the resolver would then read the diff as touching no code and exit 0.
    _git(repo, "config", "core.quotePath", "true")
    _touch(repo, "plugins/superheroes/lib/tests/test_café.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "non-ascii test file")
    paths = V.changed_paths(repo, base="main~1")
    assert "plugins/superheroes/lib/tests/test_café.py" in paths
    files, unresolved, code = V.resolve_targets(repo, paths)
    assert files == ["plugins/superheroes/lib/tests/test_café.py"]
    assert (unresolved, code) == ([], True)


def test_path_containing_a_newline_stays_one_path(repo):
    _touch(repo, "plugins/superheroes/lib/tests/test_odd\nname.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "newline in a path")
    assert "plugins/superheroes/lib/tests/test_odd\nname.py" in V.changed_paths(repo, base="main~1")


def test_missing_base_ref_raises(repo):
    with pytest.raises(V.GitError):
        V.changed_paths(repo, base="no-such-ref")


def test_script_runs_end_to_end_as_a_subprocess(repo):
    _touch(repo, "plugins/superheroes/lib/orphan.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "orphan module")
    proc = subprocess.run(
        [sys.executable, _SCRIPT, "--repo-root", repo, "--base", "main~1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "plugins/superheroes/lib/orphan.py" in proc.stderr
