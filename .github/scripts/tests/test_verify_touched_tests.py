"""Tests for `.github/scripts/verify_touched_tests.py` (#1307, #1314).

Pins the reference-selection contract: every changed file is matched, refused, or named;
the fail direction is loud for unreferenced still-present Python sources and changed
conftest.py files; deletions and non-code diffs are named, not silent.
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

_LIB = "plugins/superheroes/lib"
_TESTS = _LIB + "/tests"


def _touch(root, rel, body="# x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def _select(root, paths):
    return V.select_targets(root, paths)


def _git(root, *args):
    subprocess.run(("git", "-C", root) + args, check=True, capture_output=True, text=True)


def _init_git(root):
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")


def _track(root, *rels):
    for rel in rels:
        _git(root, "add", rel)


@pytest.fixture()
def repo(tmp_path):
    root = str(tmp_path / "repo")
    os.makedirs(root)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    _touch(root, "seed.txt", "seed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    return root


# ------------------------------------------------------------------ classification


def test_classify_path_shapes():
    assert V._classify_path(_TESTS + "/test_foo.py") == "test"
    assert V._classify_path(_LIB + "/conftest.py") == "conftest"
    assert V._classify_path(_TESTS + "/helpers.py") == "helper"
    assert V._classify_path(_LIB + "/module.py") == "python"
    assert V._classify_path("README.md") == "non_python"


# -------------------------------------------------------- test file selects itself


def test_changed_test_file_selects_itself(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    rel = _TESTS + "/test_thing.py"
    _touch(root, rel)
    selected, *_ = _select(root, [rel])
    assert selected == [rel]


def test_deleted_test_file_named_on_stdout_not_in_pytest_argv(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    rel = _TESTS + "/test_gone.py"
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [rel])
    selected, _, _, deleted, *_ = _select(root, [rel])
    assert selected == []
    assert deleted == [rel]
    assert V.main(["--repo-root", root]) == 0
    out = capsys.readouterr().out
    assert rel in out
    assert "deleted" in out.lower() or "not run" in out.lower()
    argv = V.pytest_command("/usr/bin/python3", selected)
    assert rel not in argv


# -------------------------------------------------------------- conftest refusal


def test_changed_conftest_refuses_with_tree_naming_message(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    rel = _LIB + "/conftest.py"
    _touch(root, rel)
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [rel])
    assert V.main(["--repo-root", root]) == 1
    err = capsys.readouterr().err
    assert rel in err
    assert "run that tree's suite" in err
    assert "CI is the receipt" in err


def test_conftest_refusal_blocks_pytest_even_when_tests_would_run(
        tmp_path, monkeypatch):
    root = str(tmp_path)
    _init_git(root)
    _touch(root, _LIB + "/paired.py")
    _touch(root, _TESTS + "/test_paired.py", "from paired import x\n")
    _touch(root, _LIB + "/conftest.py")
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [
        _LIB + "/conftest.py", _LIB + "/paired.py"])
    real_run = V.subprocess.run
    seen = {"pytest": False}

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            return real_run(cmd, *args, **kwargs)
        if isinstance(cmd, (list, tuple)) and "-m" in cmd and "pytest" in cmd:
            seen["pytest"] = True
            class R:
                returncode = 0
            return R()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    assert V.main(["--repo-root", root]) == 1
    assert seen["pytest"] is False


def test_conftest_refusal_under_list_only_is_non_zero_and_runs_nothing(
        tmp_path, monkeypatch):
    root = str(tmp_path)
    _init_git(root)
    _touch(root, _LIB + "/conftest.py")
    monkeypatch.setattr(V, "changed_paths",
                        lambda *a, **k: [_LIB + "/conftest.py"])
    real_run = V.subprocess.run
    seen = {"pytest": False}

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            return real_run(cmd, *args, **kwargs)
        if isinstance(cmd, (list, tuple)) and "-m" in cmd and "pytest" in cmd:
            seen["pytest"] = True
            class R:
                returncode = 0
            return R()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    assert V.main(["--repo-root", root, "--list-only"]) == 1
    assert seen["pytest"] is False


def test_conftest_and_unreferenced_source_both_refuse_without_early_return(
        tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    _touch(root, _LIB + "/conftest.py")
    _touch(root, _LIB + "/orphan.py")
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [
        _LIB + "/conftest.py", _LIB + "/orphan.py"])
    assert V.main(["--repo-root", root]) == 1
    err = capsys.readouterr().err
    assert _LIB + "/conftest.py" in err
    assert _LIB + "/orphan.py" in err


# --------------------------------------------------------- tests-tree helper


def test_tests_tree_helper_selects_referencing_tests_not_in_pytest_argv(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    helper = _TESTS + "/round_driver.py"
    test_a = _TESTS + "/test_round.py"
    test_b = _TESTS + "/test_other.py"
    _touch(root, helper, "DRIVER = 1\n")
    _touch(root, test_a, 'from round_driver import DRIVER\n')
    _touch(root, test_b, "# unrelated\n")
    selected, *_ = _select(root, [helper])
    assert test_a in selected
    assert test_b not in selected
    argv = V.pytest_command("/usr/bin/python3", selected)
    assert helper not in argv


# ------------------------------------------------------- deleted python source


def test_deleted_python_without_surviving_tests_exits_zero_named_retired(
        tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    rel = _LIB + "/retired.py"
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [rel])
    selected, _, no_ref, _, retired, _, code = _select(root, [rel])
    assert (selected, no_ref, code) == ([], [], True)
    assert retired == [rel]
    assert V.main(["--repo-root", root]) == 0
    out = capsys.readouterr().out
    assert rel in out


def test_deleted_module_still_runs_its_surviving_tests(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    mod = "eval/lib/skills.py"
    test = "eval/lib/tests/test_skills.py"
    _touch(root, test, "from skills import x\n")
    selected, _, no_ref, _, retired, _, code = _select(root, [mod])
    assert selected == [test]
    assert (no_ref, retired, code) == ([], [], True)


def test_deleted_python_without_surviving_tests_is_named_on_stdout_not_failure(
        repo, monkeypatch, capsys):
    _touch(repo, _LIB + "/retired.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add module")
    os.remove(os.path.join(repo, _LIB + "/retired.py"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "retire module")
    monkeypatch.setattr(V, "changed_paths",
                        lambda *a, **k: [_LIB + "/retired.py"])
    assert V.main(["--repo-root", repo, "--base", "main~1"]) == 0
    out = capsys.readouterr().out
    assert _LIB + "/retired.py" in out
    assert "deleted" in out.lower() or "retired" in out.lower() or "nothing left" in out.lower()


# ---------------------------------------------------- loud fail: unreferenced


def test_unreferenced_python_source_exits_non_zero_naming_the_file(
        tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    rel = _LIB + "/orphan.py"
    _touch(root, rel)
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [rel])
    assert V.main(["--repo-root", root]) == 1
    assert rel in capsys.readouterr().err


# --------------------------------------------------------- no code changed


def test_docs_only_diff_exits_zero_with_a_message(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: ["README.md"])
    assert V.main(["--repo-root", root]) == 0
    assert "no code changed" in capsys.readouterr().out


# -------------------------------------------------------------- --list-only


def test_list_only_does_not_run_pytest(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    rel = _TESTS + "/test_thing.py"
    _touch(root, rel)
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [rel])
    real_run = V.subprocess.run
    seen = {"pytest": False}

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            return real_run(cmd, *args, **kwargs)
        if isinstance(cmd, (list, tuple)) and "-m" in cmd and "pytest" in cmd:
            seen["pytest"] = True
            class R:
                returncode = 0
            return R()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    assert V.main(["--repo-root", root, "--list-only"]) == 0
    assert seen["pytest"] is False
    assert "would run" in capsys.readouterr().out


# --------------------------------------------------------- base-ref resolution


def test_unresolvable_base_ref_exits_two(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise V.GitError("base ref 'nope' does not resolve")
    monkeypatch.setattr(V, "changed_paths", boom)
    assert V.main(["--repo-root", str(tmp_path), "--base", "nope"]) == 2
    assert "does not resolve" in capsys.readouterr().err


def test_base_ref_fallback_order_origin_main_then_main(repo):
    # Repo has only main; resolve_base with no explicit base picks main.
    assert V.resolve_base(repo) == "main"


# ------------------------------------------------------- reference clauses


def _setup_mod_and_test(root, mod_rel, test_body):
    if not os.path.isdir(os.path.join(root, ".git")):
        _init_git(root)
    test_rel = mod_rel.replace(".py", "").rsplit("/", 1)[0] + "/tests/test_mod.py"
    if "/tests/" not in test_rel:
        parts = mod_rel.rsplit("/", 1)
        test_rel = parts[0] + "/tests/test_" + parts[1].replace(".py", "") + ".py"
    _touch(root, mod_rel)
    _touch(root, test_rel, test_body)
    return mod_rel, test_rel


def test_reference_clause_from_import_selects(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/round_driver.py",
                                    "from round_driver import x\n")
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_import_as_selects(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/round_driver.py",
                                    "import round_driver as rd\n")
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_comment_only_does_not_select(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/round_driver.py",
                                    "# round_driver is mentioned here only\n")
    selected, *_ = _select(root, [mod])
    assert test not in selected


def test_reference_clause_quoted_module_name_selects(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/round_driver.py",
                                    '_load("round_driver")\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_quoted_module_name_negative(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/round_driver.py",
                                    '_load("round_driv")\n')
    selected, *_ = _select(root, [mod])
    assert test not in selected


def test_reference_clause_quoted_dotted_target_selects(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/store.py",
                                    '"store.get_repo_root"\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_state_json_over_selects_intentionally(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/state.py",
                                    '"state.json"\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_quoted_dotted_negative(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/store.py",
                                    '"stor.get_repo_root"\n')
    selected, *_ = _select(root, [mod])
    assert test not in selected


def test_reference_clause_basename_with_extension_selects(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/store.py",
                                    '"store.py"\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_basename_without_extension_does_not_select(tmp_path):
    root = str(tmp_path)
    mod, test = _setup_mod_and_test(root, _LIB + "/store.py",
                                    "from other_module import x\n")
    selected, *_ = _select(root, [mod])
    assert test not in selected


def test_reference_clause_path_suffix_forward_slash_selects(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    mod = _LIB + "/hooks/session_start.py"
    test = _TESTS + "/test_session.py"
    _touch(root, mod)
    _touch(root, test, '"hooks/session_start.py"\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_path_suffix_quote_joined_selects(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    mod = _LIB + "/hooks/session_start.py"
    test = _TESTS + "/test_session.py"
    _touch(root, mod)
    _touch(root, test,
           'os.path.join(_PLUGIN, "hooks", "session_start.py")\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


def test_reference_clause_path_suffix_negative(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    mod = _LIB + "/hooks/session_start.py"
    test = _TESTS + "/test_session.py"
    _touch(root, mod)
    _touch(root, test, '"hooks/other_start.py"\n')
    selected, *_ = _select(root, [mod])
    assert test not in selected


def test_reference_clause_rubric_quote_joined_selects(tmp_path):
    root = str(tmp_path)
    _init_git(root)
    mod = _LIB + "/rubric/covenant.md"
    test = _TESTS + "/test_covenant.py"
    _touch(root, mod, "covenant\n")
    _touch(root, test, 'rubric", "covenant.md"\n')
    selected, *_ = _select(root, [mod])
    assert test in selected


# ---------------------------------------------------- non-Python unreferenced


def test_unreferenced_non_python_path_named_on_stdout(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    rel = "docs/readme.txt"
    _touch(root, rel, "hello\n")
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [rel])
    _, _, _, _, _, unref, code = _select(root, [rel])
    assert unref == [rel]
    assert code is False
    assert V.main(["--repo-root", root]) == 0
    out = capsys.readouterr().out
    assert rel in out
    assert "referenced by nothing" in out


# ------------------------------------------------------ unreadable test file


def test_unreadable_test_file_treated_as_referencing_nothing(tmp_path, monkeypatch):
    root = str(tmp_path)
    _init_git(root)
    mod = _LIB + "/orphan.py"
    test = _TESTS + "/test_orphan.py"
    _touch(root, mod)
    _touch(root, test, "from orphan import x\n")
    original = V._read_test_text

    def patched(repo_root, path):
        if path == test:
            return None
        return original(repo_root, path)

    monkeypatch.setattr(V, "_read_test_text", patched)
    selected, _, no_ref, _, _, _, code = _select(root, [mod])
    assert test not in selected
    assert mod in no_ref
    assert code is True


# ------------------------------------------- untracked test in scanned universe


def test_untracked_new_test_file_is_part_of_scanned_universe(repo):
    mod = _LIB + "/fresh.py"
    test = _TESTS + "/test_fresh.py"
    _touch(repo, mod, "X = 1\n")
    _git(repo, "add", mod)
    _git(repo, "commit", "-qm", "add module only")
    _touch(repo, test, "from fresh import X\n")
    paths = V.changed_paths(repo, base="main~1")
    assert test in paths
    selected, _, no_ref, _, _, _, code = _select(repo, [mod])
    assert test in selected
    assert no_ref == []
    assert code is True


# -------------------------------------------------------- git integration pins


def test_non_ascii_path_survives_gits_default_quoting(repo):
    _git(repo, "config", "core.quotePath", "true")
    rel = _TESTS + "/test_café.py"
    _touch(repo, rel)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "non-ascii test file")
    paths = V.changed_paths(repo, base="main~1")
    assert rel in paths
    selected, _, no_ref, _, _, _, code = _select(repo, paths)
    assert selected == [rel]
    assert (no_ref, code) == ([], True)


def test_path_containing_a_newline_stays_one_path(repo):
    rel = _TESTS + "/test_odd\nname.py"
    _touch(repo, rel)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "newline in a path")
    assert rel in V.changed_paths(repo, base="main~1")


def test_rename_keeps_the_pre_image_as_changed_path(repo):
    mod = _LIB + "/foo.py"
    test = _TESTS + "/test_foo.py"
    _touch(repo, mod, "VALUE = 1\n" * 40)
    _touch(repo, test, "from foo import VALUE\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "module and its test")
    os.makedirs(os.path.join(repo, _LIB, "sub"), exist_ok=True)
    os.rename(os.path.join(repo, mod), os.path.join(repo, _LIB, "sub", "foo.py"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "move it out of the mapped root")
    paths = V.changed_paths(repo, base="main~1")
    assert mod in paths
    assert V._classify_path(mod) == "python"
    selected, _, no_ref, _, _, _, _ = _select(repo, paths)
    assert test in selected
    assert no_ref == []


def test_changed_paths_sees_committed_and_uncommitted_and_untracked(repo):
    _touch(repo, "committed.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work")
    _touch(repo, "seed.txt", "seed changed\n")
    _touch(repo, "untracked.py")
    paths = V.changed_paths(repo, base="main~1")
    assert set(paths) >= {"committed.py", "seed.txt", "untracked.py"}


def test_range_mode_compares_commits_only(repo):
    _touch(repo, "committed.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work")
    _touch(repo, "untracked.py")
    paths = V.changed_paths(repo, diff_range="main~1..main")
    assert paths == ["committed.py"]


def test_missing_base_ref_raises(repo):
    with pytest.raises(V.GitError):
        V.changed_paths(repo, base="no-such-ref")


# -------------------------------------------------------------- pytest command


def test_pytest_command_pins_the_cache_prefix_and_flags():
    cmd = V.pytest_command("/usr/bin/python3", ["a/test_x.py"])
    assert cmd == ["/usr/bin/python3", "-B", "-X", "pycache_prefix=/private/tmp/superheroes-pyc",
                   "-m", "pytest", "a/test_x.py", "-q", "-n", "auto", "-p", "no:cacheprovider"]


def test_main_runs_pytest_on_exactly_the_resolved_files(tmp_path, monkeypatch, capsys):
    root = str(tmp_path)
    _init_git(root)
    mod = _LIB + "/thing.py"
    test = _TESTS + "/test_thing.py"
    _touch(root, mod)
    _touch(root, test, "from thing import x\n")
    monkeypatch.setattr(V, "changed_paths", lambda *a, **k: [mod])
    seen = {}
    real_run = V.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            return real_run(cmd, *args, **kwargs)
        if isinstance(cmd, (list, tuple)) and "-m" in cmd and "pytest" in cmd:
            seen["cmd"] = cmd
            seen["cwd"] = kwargs.get("cwd")
            class R:
                returncode = 3
            return R()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    assert V.main(["--repo-root", root]) == 3
    assert seen["cwd"] == root
    assert seen["cmd"][seen["cmd"].index("pytest") + 1:] == [
        test, "-q", "-n", "auto", "-p", "no:cacheprovider"]
    assert test in capsys.readouterr().out


def test_script_runs_end_to_end_as_a_subprocess(repo):
    _touch(repo, _LIB + "/orphan.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "orphan module")
    proc = subprocess.run(
        [sys.executable, _SCRIPT, "--repo-root", repo, "--base", "main~1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert _LIB + "/orphan.py" in proc.stderr
