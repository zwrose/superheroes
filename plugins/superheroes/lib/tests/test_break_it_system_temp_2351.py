"""A break-it run's default per-run folder is the system temp folder, and only a provably outside-every-repository one (#2351).

T-DoD: a kept check in a linked worktree whose repository refuses an in-repository base temp certifies (the real defect).
T-sibling: an explicit `scratch` is still honoured: the per-run folder is its child, and is gone afterwards.
T-inrepo: a system temp folder inside a work tree reads not-run `scratch-unresolved`, and nothing is written.
T-unresolvable: a system temp folder that cannot be resolved reads not-run `scratch-unresolved`.
T-mode: the default per-run folder is private (0700); a caller-given session folder's per-run folder is today's mkdir.
The remaining tests pin the other fail-closed edges: git's other answers, git that cannot start, and a bad `scratch`.

Every test that runs the runner points `tempfile.tempdir` at a test-private folder, so nothing scans the shared system
temp folder, and asserts the per-run path it captured is gone, never that no `break-it-tmp-*` exists anywhere."""
import hashlib
import os
import shlex
import subprocess
import sys
import tempfile

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import test_break_it as TB  # noqa: E402  (the block helpers live there)

# The throwaway fixture repo's commits carry an inline identity; nothing is signed.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
PY = shlex.quote(sys.executable)

# The shape of the real guard (tests/conftest.py `_tmp_base_outside_any_repository`): only git's own
# "not a git repository" answer lets the run proceed.
GUARD_CONFTEST = '''import os
import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def _tmp_base_outside_any_repository(tmp_path_factory):
    base = str(tmp_path_factory.getbasetemp())
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["LC_ALL"] = "C"
    proc = subprocess.run(["git", "-C", base, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                          check=False, env=env)
    if not (proc.returncode != 0 and "not a git repository" in proc.stderr):
        pytest.fail("base temp %s is not provably outside every git repository (rc=%s, err=%r)"
                    % (base, proc.returncode, proc.stderr.strip()))
'''
PASSING_TEST = "def test_k():\n    assert True\n"
TEST_PATH = "tests/test_k.py"
PRINT_TMP = ("import os, stat, tempfile\n"
             "folder = tempfile.gettempdir()\n"
             "print('TMPDIR=' + folder)\n"
             "print('MODE=%o' % stat.S_IMODE(os.stat(folder).st_mode))\n")


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    """The fixture's own git calls read no user or system git config. The runner drops GIT_CONFIG_GLOBAL from the
    environment it gives git, so its own git calls are kept off the developer's configuration by an empty per-test
    HOME and XDG_CONFIG_HOME."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def systmp(monkeypatch, tmp_path):
    """A test-private system temp folder."""
    folder = tmp_path / "systmp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    TB._write(root, "README.md", "fixture\n")
    _commit(root, "base")
    return root


def _run(repo, path, content, **kwargs):
    block = TB._block(path, content)
    return break_it.run_one(str(repo), _git(repo, "rev-parse", "HEAD"), block, **kwargs)


def _printed(record, key):
    return record["output"].split(key + "=", 1)[1].splitlines()[0]


def _fail_git_on_the_temp_probe(monkeypatch, exc):
    """Make the one git call `_scratch_folder` makes raise `exc`; every other git call is the real one."""
    real = break_it._git_env

    def failing(root, args, env):
        if tuple(args[:2]) == ("rev-parse", "--show-toplevel"):
            raise exc
        return real(root, args, env)

    monkeypatch.setattr(break_it, "_git_env", failing)


# ---- T-DoD: the converge-time kept check certifies in a linked worktree ----------------------------------


def test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept(tmp_path, systmp):
    main = tmp_path / "fx"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "symbolic-ref", "HEAD", "refs/heads/main")
    TB._write(main, "conftest.py", GUARD_CONFTEST)
    TB._write(main, "pytest.ini", "[pytest]\n")
    TB._write(main, "README.md", "fixture\n")
    base = _commit(main, "base")
    linked = tmp_path / "fx-linked"
    _git(main, "worktree", "add", "-q", "-b", "feature", str(linked))
    TB._write(linked, TEST_PATH, PASSING_TEST)
    head = _commit(linked, "head")
    record = {"path": TEST_PATH, "command": "%s -m pytest -q -p no:cacheprovider %s" % (PY, TEST_PATH),
              "sha256": hashlib.sha256(PASSING_TEST.encode("utf-8")).hexdigest()}
    result = break_it.check_kept(str(linked), base, head, record)
    run = result["run"] or {}
    assert result["outcome"] == "kept", (result["outcome"], run.get("outcome"), run.get("reason"), run.get("output"))
    assert run["outcome"] == "passed", run
    assert _git(linked, "status", "--porcelain") == ""


# ---- T-sibling: a caller-given scratch is honoured --------------------------------------------------------


def test_sibling_an_explicit_scratch_holds_the_per_run_folder_and_it_is_gone_afterwards(repo, tmp_path, systmp):
    session = tmp_path / "session"
    session.mkdir()
    record = _run(repo, "tests/test_t.py", PRINT_TMP, scratch=str(session))
    assert record["outcome"] == "passed", record
    printed = _printed(record, "TMPDIR")
    assert os.path.realpath(os.path.dirname(printed)) == os.path.realpath(str(session)), printed
    assert os.path.basename(printed).startswith("break-it-tmp-")
    assert not os.path.exists(printed)
    assert os.listdir(str(systmp)) == []


def test_a_scratch_that_is_not_an_existing_directory_is_not_run_scratch_unresolved(repo, tmp_path, systmp):
    record = _run(repo, "tests/test_t.py", PRINT_TMP, scratch=str(tmp_path / "missing"))
    assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
    assert not (repo / "tests").exists()


# ---- T-inrepo: a system temp folder inside a work tree is refused -----------------------------------------


def test_inrepo_a_system_temp_folder_inside_the_work_tree_is_not_run_scratch_unresolved(repo, monkeypatch):
    (repo / ".git" / "info" / "exclude").write_text("inner-tmp/\n")
    inner = repo / "inner-tmp"
    inner.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(inner))
    record = _run(repo, "tests/test_t.py", PRINT_TMP)
    assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
    assert not (repo / "tests").exists()
    assert os.listdir(str(inner)) == []


def test_a_system_temp_folder_inside_a_git_directory_is_not_run_scratch_unresolved(repo, monkeypatch):
    # git answers "must be run in a work tree" there: not the one answer that proves the folder is outside every repository
    inner = repo / ".git" / "inner-tmp"
    inner.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(inner))
    record = _run(repo, "tests/test_t.py", PRINT_TMP)
    assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
    assert not (repo / "tests").exists()
    assert os.listdir(str(inner)) == []


# ---- T-unresolvable: a system temp folder that cannot be resolved -----------------------------------------


def test_unresolvable_a_system_temp_folder_that_cannot_be_resolved_is_not_run_scratch_unresolved(repo, monkeypatch):
    def gone():
        raise FileNotFoundError("no usable temporary directory")

    monkeypatch.setattr(tempfile, "gettempdir", gone)
    record = _run(repo, "tests/test_t.py", PRINT_TMP)
    assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
    assert not (repo / "tests").exists()


@pytest.mark.parametrize("exc", [OSError("no git"), subprocess.TimeoutExpired(["git"], 1)])
def test_git_that_cannot_start_or_times_out_in_the_system_temp_folder_is_not_run_scratch_unresolved(repo, systmp, monkeypatch, exc):
    _fail_git_on_the_temp_probe(monkeypatch, exc)
    record = _run(repo, "tests/test_t.py", PRINT_TMP)
    assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
    assert not (repo / "tests").exists()
    assert os.listdir(str(systmp)) == []


# ---- T-mode: the default per-run folder is private --------------------------------------------------------


def test_mode_the_default_per_run_folder_is_private_and_a_given_scratch_folder_keeps_the_plain_mkdir(repo, tmp_path, systmp):
    session = tmp_path / "session"
    session.mkdir()
    old_umask = os.umask(0o022)  # fixed, so a plain mkdir (0755) differs from the private one (0700)
    try:
        default = _run(repo, "tests/test_t.py", PRINT_TMP)
        given = _run(repo, "tests/test_t.py", PRINT_TMP, scratch=str(session))
    finally:
        os.umask(old_umask)
    assert default["outcome"] == "passed" and given["outcome"] == "passed", (default, given)
    assert os.path.realpath(os.path.dirname(_printed(default, "TMPDIR"))) == os.path.realpath(str(systmp))
    assert _printed(default, "MODE") == "700"
    assert int(_printed(given, "MODE"), 8) == 0o777 & ~0o022
    assert not os.path.exists(_printed(default, "TMPDIR")) and not os.path.exists(_printed(given, "TMPDIR"))


# ---- T-locale: git's answer is read under the C locale ---------------------------------------------------

FAKE_LOCALIZED_GIT = """#!/bin/sh
# Answers like a translated git: English only under the C locale.
if [ "$LC_ALL" = "C" ]; then
  echo "fatal: not a git repository (or any of the parent directories): .git" >&2
else
  echo "fatal: kein Git-Repository (oder irgendeines der Elternverzeichnisse): .git" >&2
fi
exit 128
"""


def test_locale_a_translated_git_still_proves_the_system_temp_folder_outside_every_repository(repo, tmp_path, systmp,
                                                                                               monkeypatch):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(FAKE_LOCALIZED_GIT)
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    monkeypatch.setenv("LANGUAGE", "de")
    base, reason = break_it._scratch_folder(str(repo), None)
    assert (base, reason) == (os.path.abspath(str(systmp)), None)
