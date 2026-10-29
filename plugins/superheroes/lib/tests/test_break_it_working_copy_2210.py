"""A break-it test runs in the session's own working copy, at the reviewed head, and leaves it as it was (#2210, FR-50).

The fixture repo is a scratch git repository; its commits pin their own config and pass an inline identity."""
import os
import shlex
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import test_break_it as TB  # noqa: E402  (the block helpers live there)

# The throwaway fixture repo's commits carry an inline identity; nothing is signed.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
PY = shlex.quote(sys.executable)


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
    TB._write(root, "mod.py", "def value():\n    return 2\n")
    TB._write(root, "helper.py", "HELPER = 1\n")
    _commit(root, "base")
    _git(root, "branch", "doomed")
    _git(root, "branch", "movable")
    return root


def _status(repo):
    return _git(repo, "status", "--porcelain", "--untracked-files=all")


def _refs(repo):
    return _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")


def _run(repo, path, content, **kwargs):
    block = TB._block(path, content)
    return break_it.run_one(str(repo), _git(repo, "rev-parse", "HEAD"), block, **kwargs)


def _no_tmp_folders(base):
    return not os.path.isdir(str(base)) or [n for n in os.listdir(str(base)) if n.startswith("break-it-tmp-")] == []


# ---- E1-E5: the precheck and the scratch check refuse before anything is written ---------------------------


def test_e1_a_working_copy_not_at_the_head_is_not_run_and_nothing_is_written(repo):
    older = _git(repo, "rev-parse", "HEAD")
    TB._write(repo, "mod.py", "def value():\n    return 3\n")
    _commit(repo, "newer")
    before = _refs(repo)
    record = break_it.run_one(str(repo), older, TB._block("tests/test_x.py", "assert True\n"))
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-not-at-head"), record
    assert record["restored"] == []
    assert not (repo / "tests").exists()
    assert _status(repo) == "" and _refs(repo) == before
    assert _no_tmp_folders(repo / ".git" / "superheroes")


def test_e2_a_modified_tracked_file_is_not_run_and_is_left_alone(repo):
    (repo / "README.md").write_text("edited by the session\n")
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-dirty"), record
    assert (repo / "README.md").read_text() == "edited by the session\n"
    assert not (repo / "tests").exists()


def test_e3_a_staged_change_is_not_run_and_stays_staged(repo):
    TB._write(repo, "staged.txt", "staged\n")
    _git(repo, "add", "staged.txt")
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-dirty"), record
    assert _git(repo, "diff", "--cached", "--name-only") == "staged.txt"
    assert not (repo / "tests").exists()


def test_e4_a_git_failure_in_the_precheck_is_unreadable(repo, tmp_path, monkeypatch):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    record = break_it.run_one(str(plain), "HEAD", TB._block("tests/test_x.py", "assert True\n"))
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-unreadable"), record
    real = break_it._git

    def failing(root, *args):
        if args[0] == "status":
            return subprocess.CompletedProcess(["git"] + list(args), 128, b"", b"status refused")
        return real(root, *args)

    monkeypatch.setattr(break_it, "_git", failing)
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-unreadable"), record
    assert "status refused" in record["output"]
    assert not (repo / "tests").exists()


@pytest.mark.parametrize("kind", ["missing", "a-file"])
def test_e5_a_scratch_that_is_not_a_directory_is_unresolved_before_anything_is_written(repo, tmp_path, kind):
    scratch = tmp_path / kind
    if kind == "a-file":
        scratch.write_text("x")
    record = _run(repo, "tests/test_x.py", "assert True\n", scratch=str(scratch))
    assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
    assert not (repo / "tests").exists()
    assert _status(repo) == ""


# ---- E6: everything a test can change in the working copy is put back -------------------------------------

E6_SCRIPT = '''\
import os, subprocess

ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def git(*args):
    subprocess.check_call(["git"] + ID + list(args))


git("config", "--local", "break.it", "x")
with open("README.md", "w") as fh:
    fh.write("committed by the test\\n")
git("add", "README.md")
git("commit", "-q", "-m", "by the test")
git("checkout", "-q", "--detach")
git("branch", "-f", "movable", "HEAD")
git("branch", "-D", "doomed")
git("tag", "added-by-test")
with open("mod.py", "w") as fh:
    fh.write("edited\\n")
os.remove("helper.py")
with open("staged.txt", "w") as fh:
    fh.write("staged\\n")
git("add", "staged.txt")
os.makedirs("newdir/deeper")
with open("newdir/deeper/inner.txt", "w") as fh:
    fh.write("x\\n")
with open("untracked.txt", "w") as fh:
    fh.write("x\\n")
'''


def _ref_map(repo):
    return dict(line.split(" ", 1) for line in _refs(repo).splitlines())


def test_e6_everything_the_test_changes_is_restored_and_named(repo):
    pinned = _git(repo, "rev-parse", "HEAD")
    refs_before = _ref_map(repo)
    config_before = (repo / ".git" / "config").read_bytes()
    record = _run(repo, "tests/test_e6.py", E6_SCRIPT)
    assert record["outcome"] == "passed", record
    assert record["reason"] is None
    assert record["restored"] == ["test-file", "refs", "head", "config", "index", "tracked", "untracked"], record
    assert _git(repo, "rev-parse", "HEAD") == pinned
    assert _git(repo, "symbolic-ref", "HEAD") == "refs/heads/main"
    # the branch HEAD pointed at is put back; every other ref the test moved, deleted or added is left and listed
    refs_after = _ref_map(repo)
    left = ["refs/heads/doomed", "refs/heads/movable", "refs/tags/added-by-test"]
    assert record["refsLeft"] == left, record
    assert refs_after["refs/heads/main"] == refs_before["refs/heads/main"] == pinned
    assert "refs/heads/doomed" not in refs_after
    assert refs_after["refs/heads/movable"] != refs_before["refs/heads/movable"]
    assert "refs/tags/added-by-test" not in refs_before and "refs/tags/added-by-test" in refs_after
    assert {r: o for r, o in refs_after.items() if r not in left} == {r: o for r, o in refs_before.items() if r not in left}
    assert (repo / ".git" / "config").read_bytes() == config_before
    assert (repo / "README.md").read_text() == "fixture\n"
    assert (repo / "mod.py").read_text() == "def value():\n    return 2\n"
    assert (repo / "helper.py").read_text() == "HELPER = 1\n"
    assert not (repo / "staged.txt").exists() and not (repo / "untracked.txt").exists()
    assert not (repo / "newdir").exists() and not (repo / "tests").exists()
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    assert _status(repo) == ""


def test_e6_a_detached_head_is_put_back_detached_at_the_pinned_commit(repo):
    _git(repo, "checkout", "-q", "--detach")
    pinned = _git(repo, "rev-parse", "HEAD")
    content = "import subprocess\nsubprocess.check_call(['git', 'checkout', '-q', 'main'])\n"
    record = _run(repo, "tests/test_d.py", content)
    assert record["outcome"] == "passed", record
    assert record["restored"] == ["test-file", "head"], record
    assert subprocess.run(["git", "-C", str(repo), "symbolic-ref", "-q", "HEAD"], capture_output=True).returncode == 1
    assert _git(repo, "rev-parse", "HEAD") == pinned


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_e6_an_index_flag_the_test_sets_to_hide_an_edit_is_cleared_and_the_edit_undone(repo, flag):
    # axis: a test that flags a tracked file then edits it leaves neither the edit nor the flag behind
    content = ("import subprocess\n"
               "subprocess.check_call(['git', 'update-index', %r, 'README.md'])\n"
               "open('README.md', 'w').write('hidden edit\\n')\n" % flag)
    record = _run(repo, "tests/test_h.py", content)
    assert record["outcome"] == "passed", record
    assert "index" in record["restored"] and "tracked" in record["restored"], record
    assert (repo / "README.md").read_text() == "fixture\n"
    assert not [l for l in _git(repo, "ls-files", "-v").splitlines() if l[0] in "hsS"]
    assert _status(repo) == ""


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_e2_a_pre_existing_hiding_index_flag_is_not_run(repo, flag):
    # axis: a flag already hiding edits is refused at the precheck, since status cannot show what the restore must undo
    _git(repo, "update-index", flag, "README.md")
    (repo / "README.md").write_text("hidden edit\n")
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-dirty"), record
    assert (repo / "README.md").read_text() == "hidden edit\n"
    assert not (repo / "tests").exists()


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_e2_a_pre_existing_index_flag_on_a_clean_file_is_run_and_kept(repo, flag):
    # axis: a flag on a file that matches the head is not a hidden change, so the run goes ahead and the owner's flag is still set after it
    _git(repo, "update-index", flag, "README.md")
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert record["outcome"] == "passed", record
    assert [l[2:] for l in _git(repo, "ls-files", "-v").splitlines() if l[0] in "hsS"] == ["README.md"]


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_e2_a_run_that_edits_a_pre_existing_flagged_file_has_the_edit_undone_and_the_flag_kept(repo, flag):
    # axis: an edit to a file the owner had flagged is put back although status cannot see it, and the owner's flag survives
    _git(repo, "update-index", flag, "README.md")
    record = _run(repo, "tests/test_x.py", "open('README.md', 'w').write('hidden edit\\n')\n")
    assert record["outcome"] == "passed", record
    assert (repo / "README.md").read_text() == "fixture\n"
    assert [l[2:] for l in _git(repo, "ls-files", "-v").splitlines() if l[0] in "hsS"] == ["README.md"]


def _flags(repo):
    return {l[2:]: l[0] for l in _git(repo, "ls-files", "-v").splitlines() if l[0] in "hsS"}


@pytest.mark.parametrize("owner_flag, run_flag, action", [
    ("--assume-unchanged", "--skip-worktree", "os.remove('README.md')"),
    ("--assume-unchanged", "--skip-worktree", "open('README.md', 'w').write('hidden edit\\n')"),
    ("--skip-worktree", "--assume-unchanged", "os.remove('README.md')"),
    ("--skip-worktree", "--assume-unchanged", "os.chmod('README.md', 0o755)"),
    ("--assume-unchanged", "--no-assume-unchanged", "open('README.md', 'w').write('hidden edit\\n')"),
])
def test_e2_a_run_that_changes_the_flags_on_an_owner_flagged_file_leaves_its_content_and_its_flags_as_before(
        repo, owner_flag, run_flag, action):
    # axis: the flags are compared and put back by value, not by path, so a flag the run adds to (or clears from) an owner-flagged file, and the deletion, edit or mode change it then hides, are all undone
    _git(repo, "update-index", owner_flag, "README.md")
    before = _flags(repo)
    content = ("import os, subprocess\n"
               "subprocess.check_call(['git', 'update-index', %r, 'README.md'])\n"
               "%s\n" % (run_flag, action))
    record = _run(repo, "tests/test_f.py", content)
    assert record["outcome"] == "passed", record
    assert (repo / "README.md").read_text() == "fixture\n"
    assert not os.stat(str(repo / "README.md")).st_mode & 0o100
    assert _flags(repo) == before
    for option in ("--no-assume-unchanged", "--no-skip-worktree"):
        _git(repo, "update-index", option, "README.md")
    assert _status(repo) == ""


def test_e2_a_sparse_absent_skip_worktree_path_stays_absent_and_flagged(repo):
    # axis: a skip-worktree path a sparse checkout left absent is run over and is absent and flagged again after a run that wrote it
    _git(repo, "update-index", "--skip-worktree", "helper.py")
    os.remove(str(repo / "helper.py"))
    record = _run(repo, "tests/test_s.py", "open('helper.py', 'w').write('run wrote this\\n')\n")
    assert record["outcome"] == "passed", record
    assert not (repo / "helper.py").exists()
    assert _flags(repo) == {"helper.py": "S"}
    assert _status(repo) == ""


def test_e2_a_pre_existing_flagged_file_whose_mode_differs_is_not_run(repo):
    # axis: a mode change hidden by a flag is an owner edit too, so the precheck refuses rather than let the restore revert it
    _git(repo, "update-index", "--assume-unchanged", "README.md")
    os.chmod(str(repo / "README.md"), 0o755)
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-dirty"), record
    assert os.stat(str(repo / "README.md")).st_mode & 0o100


def test_e6_a_config_file_that_did_not_exist_is_deleted_again(repo):
    config = repo / ".git" / "config.worktree"
    assert not config.exists()
    content = "open('.git/config.worktree', 'w').write('[break]\\n\\tit = x\\n')\n"
    record = _run(repo, "tests/test_c.py", content)
    assert record["outcome"] == "passed", record
    assert record["restored"] == ["test-file", "config"], record
    assert not config.exists()


def test_the_kept_test_is_run_as_it_stands_and_stays(repo):
    content = "assert True\n"
    TB._write(repo, "tests/test_k.py", content)
    _commit(repo, "kept")
    record = _run(repo, "tests/test_k.py", content)
    assert record["outcome"] == "passed", record
    assert "test-file" not in record["restored"]
    assert (repo / "tests" / "test_k.py").read_text() == content
    assert _status(repo) == ""


# ---- E7: a restore step that fails is a failed run -------------------------------------------------------


def test_e7_a_failing_restore_call_is_working_copy_restore_failed(repo, monkeypatch):
    real = break_it._git

    def failing(root, *args):
        if args[0] == "reset":
            return subprocess.CompletedProcess(["git"] + list(args), 1, b"", b"reset refused")
        return real(root, *args)

    content = ("import subprocess\nopen('README.md', 'w').write('edited')\n"
               "subprocess.check_call(['git', 'add', 'README.md'])\n")
    monkeypatch.setattr(break_it, "_git", failing)
    record = _run(repo, "tests/test_r.py", content)
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-restore-failed"), record
    assert "index" in record["output"] and "reset refused" in record["output"]
    assert "index" in record["restored"]
    # the steps after the failing one still ran
    assert (repo / "README.md").read_text() == "fixture\n"


def test_e7_a_restore_that_leaves_the_tree_dirty_fails_the_verify(repo, monkeypatch):
    monkeypatch.setattr(break_it, "_restore_tracked", lambda root, snap: False)
    record = _run(repo, "tests/test_r.py", "open('README.md', 'w').write('edited')\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-restore-failed"), record
    assert "verify" in record["output"]


# ---- E8: an exception inside the run still restores ------------------------------------------------------


def test_e8_an_exception_inside_the_run_still_restores(repo, monkeypatch):
    def boom(argv, env, cwd, repo_root, token, timeout, **kwargs):
        with open(os.path.join(cwd, "README.md"), "w") as fh:
            fh.write("leaked\n")
        with open(os.path.join(cwd, "leak.txt"), "w") as fh:
            fh.write("x")
        raise RuntimeError("boom")

    monkeypatch.setattr(break_it, "_run_contained", boom)
    record = _run(repo, "tests/test_b.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "run-error"), record
    assert record["restored"] == ["test-file", "tracked", "untracked"], record
    assert _status(repo) == ""
    assert not (repo / "tests").exists() and not (repo / "leak.txt").exists()


# ---- E9: the default scratch is the git directory's superheroes folder -----------------------------------

PRINT_TMP = "import tempfile\nprint('TMPDIR=' + tempfile.gettempdir())\n"


def test_e9_without_a_scratch_the_temp_folder_lies_under_the_git_directory_and_is_gone_afterwards(repo):
    record = _run(repo, "tests/test_t.py", PRINT_TMP)
    assert record["outcome"] == "passed", record
    printed = record["output"].split("TMPDIR=", 1)[1].splitlines()[0]
    base = os.path.realpath(str(repo / ".git" / "superheroes"))
    assert os.path.realpath(printed).startswith(base + os.sep), (printed, base)
    assert os.path.basename(printed).startswith("break-it-tmp-")
    assert _no_tmp_folders(repo / ".git" / "superheroes")
    assert not os.path.exists(printed)


# ---- the run and the probe both run in the repository root -----------------------------------------------


def test_the_probe_and_the_test_run_with_the_repository_root_as_their_working_directory(repo, monkeypatch):
    seen = []
    real = break_it._run_contained

    def spy(argv, env, cwd, repo_root, token, timeout, **kwargs):
        seen.append(cwd)
        return real(argv, env, cwd, repo_root, token, timeout, **kwargs)

    monkeypatch.setattr(break_it, "_run_contained", spy)
    block = TB._block("tests/test_w.py", "assert True\n", run="python3 tests/test_w.py")
    record = break_it.run_one(str(repo), _git(repo, "rev-parse", "HEAD"), block, interpreter=sys.executable)
    assert record["outcome"] == "passed", record
    assert seen == [str(repo), str(repo)]


# ---- FR-50 ------------------------------------------------------------------------------------------------


def test_t_search_the_source_holds_no_copy_machinery():
    with open(break_it.__file__, encoding="utf-8") as fh:
        source = fh.read()
    for word in ("mkdtemp", "clone", "worktree add", "git worktree", "os.symlink", "DEPENDENCY_DIRS", "_link_dependencies"):
        assert word not in source, word


WRITES_CONTENT = ("import os, tempfile\n"
                  "f = tempfile.NamedTemporaryFile(delete=False)\n"
                  "f.write(b'x')\n"
                  "f.close()\n"
                  "print('TMPDIR=' + tempfile.gettempdir())\n"
                  "print('FILE=' + f.name)\n"
                  "for name in ('TMPDIR', 'TMP', 'TEMP', 'XDG_CACHE_HOME'):\n"
                  "    path = os.path.join(os.environ[name], 'made-through-' + name)\n"
                  "    with open(path, 'w') as fh:\n"
                  "        fh.write('x')\n"
                  "    print('MADE_' + name + '=' + path)\n")


def test_t_writes_the_runs_temp_files_land_in_the_session_folder_and_nowhere_else(repo, tmp_path, monkeypatch):
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    scratch = tmp_path / "session"
    scratch.mkdir()
    for name in ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME"):
        monkeypatch.setenv(name, str(sentinel))
    before = _status(repo)
    record = _run(repo, "tests/test_w.py", WRITES_CONTENT, scratch=str(scratch))
    assert record["outcome"] == "passed", record
    lines = dict(line.split("=", 1) for line in record["output"].splitlines() if "=" in line)
    under = os.path.realpath(str(scratch)) + os.sep
    assert os.path.realpath(lines["TMPDIR"]).startswith(under), lines
    assert os.path.realpath(lines["FILE"]).startswith(under), lines
    for name in ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME"):
        assert os.path.realpath(lines["MADE_" + name]).startswith(under), (name, lines)
    assert os.listdir(str(sentinel)) == []
    assert os.listdir(str(scratch)) == []
    assert _status(repo) == before == ""
