"""Round-2 review fixes for the working-copy break-it run (#2210, WO-E).

G1 the default scratch folder resolves the git directory through `store_core.get_worktree_gitdir`.
G3 a detached worker no sample saw is stopped by where it runs and when it started; a process older than the run survives.
G4 a ref another worktree changes during the run is left and listed in `refsLeft`; only HEAD's own branch is put back.
G7 a recorded `working-copy-restore-failed` run parks cannot-certify whatever the finding's disposition.
"""
import os
import shlex
import subprocess
import sys
import threading
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract  # noqa: E402
import store_core  # noqa: E402
import test_break_it as TB  # noqa: E402  (the block helpers live there)

# The throwaway fixture repo's commits carry an inline identity; nothing is signed.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
PY = shlex.quote(sys.executable)
HAS_PROC = os.path.isdir("/proc/self")
needs_sleep = pytest.mark.skipif(not os.path.exists("/bin/sleep"), reason="needs a system sleep")


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    """No git call here, the runner's own included, reads a user or system git config."""
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


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    TB._write(root, "README.md", "fixture\n")
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "base")
    return root


def _run(repo, path, content, **kwargs):
    block = TB._block(path, content)
    return break_it.run_one(str(repo), _git(repo, "rev-parse", "HEAD"), block, **kwargs)


def _refs(repo):
    return dict(line.split(" ", 1) for line in _git(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines())


def _gone(pid, wait=5.0):
    """True once ``pid`` is no process, or only a zombie nobody has reaped yet."""
    deadline = time.time() + wait
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:
            with open("/proc/%d/stat" % pid) as fh:
                if fh.read().rsplit(")", 1)[1].split()[0] == "Z":
                    return True
        except (OSError, IndexError):
            pass  # no /proc here: signal 0 alone decides
        if time.time() >= deadline:
            return False
        time.sleep(0.05)


def _kill_if_alive(pid):
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass


# axis: the death oracle answers False for a live worker even when /proc cannot be read, and True for a reaped child, so a host without /proc cannot pass a containment test by default
@needs_sleep
def test_gone_oracle_is_false_for_a_live_worker_without_proc_and_true_once_reaped(monkeypatch):
    real_open = open

    def no_proc(path, *args, **kwargs):
        if str(path).startswith("/proc/"):
            raise FileNotFoundError(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", no_proc)
    live = subprocess.Popen(["/bin/sleep", "60"])
    try:
        assert _gone(live.pid, wait=0) is False
    finally:
        live.kill()
        live.wait()
    assert _gone(live.pid, wait=0) is True


# ---- G1: the git directory comes from store_core ---------------------------------------------------------


def test_g1_the_default_scratch_folder_is_the_worktrees_own_git_directory_superheroes_folder(repo, tmp_path):
    base, reason = break_it._scratch_folder(str(repo), None)
    assert reason is None
    assert base == os.path.join(os.path.realpath(str(repo / ".git")), "superheroes")
    assert base == os.path.join(store_core.get_worktree_gitdir(str(repo)), "superheroes")
    other = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "-b", "linked", str(other))
    base, reason = break_it._scratch_folder(str(other), None)
    assert reason is None and os.path.isabs(base)
    assert base == os.path.join(os.path.realpath(str(repo / ".git" / "worktrees" / "linked")), "superheroes")


def test_g1_a_git_directory_that_cannot_be_resolved_reads_working_copy_unreadable(repo, monkeypatch):
    real = store_core.run_git_result

    def unavailable(cwd, *args, env=None):
        if args[:1] == ("rev-parse",) and "--absolute-git-dir" in args:
            return store_core.GitResult(None, store_core.GIT_UNAVAILABLE, "OSError: no git")
        return real(cwd, *args, env=env)

    monkeypatch.setattr(store_core, "run_git_result", unavailable)
    record = _run(repo, "tests/test_x.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-unreadable"), record
    assert "no git" in record["output"]
    assert not (repo / "tests").exists()


def test_g1_the_resolution_ignores_a_git_dir_routed_through_the_environment(repo, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _git(elsewhere, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))
    base, reason = break_it._scratch_folder(str(repo), None)
    assert reason is None
    assert base == os.path.join(os.path.realpath(str(repo / ".git")), "superheroes")


# ---- G3: the working-directory net ----------------------------------------------------------------------

DETACH = ("import subprocess, time\n"
          "w = subprocess.Popen(['/bin/sleep', '60'], start_new_session=True, env={}, stdin=subprocess.DEVNULL,\n"
          "    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
          "open(%r, 'w').write(str(w.pid))\n"
          "time.sleep(0.3)\n"
          "print('worker-alive=' + str(w.poll() is None) + ' exit=' + str(w.poll()))\n")
BARE_REAPER = ("import os, subprocess, sys\n"
               "os._exit(subprocess.Popen(sys.argv[2:], stdin=subprocess.DEVNULL).wait())\n")


def _dead(pid, wait=5.0):
    """True once signal 0 finds no process with ``pid``. Reads no ``/proc``: a sandbox's ``/proc`` may be another
    PID namespace's."""
    deadline = time.time() + wait
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.05)


def _reader_of(pids_and_starts, root):
    """A reader of the net's shape that reports each ``(pid, started)`` with its working directory in ``root``, as an
    orphan (parent 1), which is how a detached worker reads."""
    return lambda: ([(pid, os.path.realpath(str(root)), started(), 1, started())
                     for pid, started in pids_and_starts()], set(), None)


def _only_the_working_directory_net(monkeypatch, reader):
    """Every other net off: no sampling, no environment token, a reaper that adopts and sweeps nothing; the net's
    data source is ``reader``, the one thing that differs between Linux and the other hosts."""
    monkeypatch.setattr(break_it._DescendantWatch, "sample", lambda self: None)
    monkeypatch.setattr(break_it, "_kill_tagged", lambda token: None)
    monkeypatch.setattr(break_it, "_REAPER", BARE_REAPER)
    monkeypatch.setattr(break_it, "_cwd_table", reader)


@needs_sleep
def test_g3a_a_detached_worker_no_sample_saw_is_stopped_by_the_working_directory_net(repo, tmp_path, monkeypatch):
    pidfile = tmp_path / "worker.pid"
    _only_the_working_directory_net(monkeypatch, _reader_of(
        lambda: [(int(pidfile.read_text()), time.time)] if pidfile.exists() else [], repo))
    pid = None
    try:
        record = _run(repo, "tests/test_detach.py", DETACH % str(pidfile))
        assert record["outcome"] == "passed", record
        pid = int(pidfile.read_text())
        assert "worker-alive=True" in record["output"], record["output"]
        assert _dead(pid), "the detached worker outlived the run"
    finally:
        if pid is not None and not _dead(pid, wait=0):
            os.kill(pid, 9)


@needs_sleep
def test_g3b_a_process_started_before_the_run_with_its_directory_in_the_working_copy_survives(repo, monkeypatch):
    older = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo), start_new_session=True)
    _only_the_working_directory_net(monkeypatch, _reader_of(lambda: [(older.pid, lambda: time.time() - 3600)], repo))
    try:
        record = _run(repo, "tests/test_quiet.py", "assert True\n")
        assert record["outcome"] == "passed", record
        assert older.poll() is None, "a process older than the run was stopped"
    finally:
        older.kill()
        older.wait()


@needs_sleep
@pytest.mark.proc_containment
def test_g3a_the_proc_reader_finds_the_detached_worker_and_the_net_stops_it(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(break_it._DescendantWatch, "sample", lambda self: None)
    monkeypatch.setattr(break_it, "_kill_tagged", lambda token: None)
    monkeypatch.setattr(break_it, "_REAPER", BARE_REAPER)
    pidfile = tmp_path / "worker.pid"
    pid = None
    try:
        record = _run(repo, "tests/test_detach.py", DETACH % str(pidfile))
        assert record["outcome"] == "passed", record
        pid = int(pidfile.read_text())
        assert "worker-alive=True" in record["output"], record["output"]
        assert _gone(pid), "the detached worker outlived the run"
    finally:
        if pid is not None:
            _kill_if_alive(pid)


@needs_sleep
@pytest.mark.proc_containment
def test_g3b_the_proc_reader_spares_a_process_older_than_the_run(repo):
    older = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo), start_new_session=True)
    try:
        time.sleep(0.3)
        record = _run(repo, "tests/test_quiet.py", "assert True\n")
        assert record["outcome"] == "passed", record
        assert older.poll() is None, "a process older than the run was stopped"
    finally:
        older.kill()
        older.wait()


def test_g3_a_proc_that_is_another_namespaces_is_not_read_and_says_so(monkeypatch):
    real = os.readlink
    monkeypatch.setattr(break_it.os, "readlink", lambda path: str(os.getpid() + 1) if path == "/proc/self" else real(path))
    processes, ancestors, note = break_it._proc_cwd_table()
    assert (processes, ancestors) == ([], set())
    assert "another PID namespace" in note


@needs_sleep
def test_g3_the_net_stops_what_the_run_started_inside_the_working_copy_and_spares_ancestors_and_outsiders(repo, tmp_path):
    inside = repo / "sub"
    inside.mkdir()
    since = time.time()
    victim = subprocess.Popen(["/bin/sleep", "60"], cwd=str(inside))
    ancestor = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    outsider = subprocess.Popen(["/bin/sleep", "60"], cwd=str(tmp_path))
    older = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    real = os.path.realpath
    me = os.getpid()
    table = [(victim.pid, real(str(inside)), since + 1, me, 1), (ancestor.pid, real(str(repo)), since + 1, me, 2),
             (outsider.pid, real(str(tmp_path)), since + 1, me, 3), (older.pid, real(str(repo)), since - 1, me, 4)]
    try:
        note = break_it._kill_in_working_copy(str(repo), since, reader=lambda: (table, {ancestor.pid}, None), run_pid=me)
        assert note is None
        assert victim.wait(timeout=5) == -9
        assert ancestor.poll() is None and outsider.poll() is None and older.poll() is None
    finally:
        for proc in (victim, ancestor, outsider, older):
            proc.kill()
            proc.wait()


@needs_sleep
def test_g3_a_process_launched_independently_in_the_checkout_during_the_run_survives(repo):
    # axis: a process that started after the run began, sits in the checkout, is not known and has a live parent that is not the run's is never signalled
    since = time.time()
    run_pid, shell_pid = os.getpid(), os.getpid() + 100000
    independent = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    child = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    orphan = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    root = os.path.realpath(str(repo))
    table = [(independent.pid, root, since + 1, shell_pid, 11), (child.pid, root, since + 1, run_pid, 12),
             (orphan.pid, root, since + 1, 1, 13), (shell_pid, root, since - 5, 1, 14)]
    try:
        assert break_it._kill_in_working_copy(str(repo), since, reader=lambda: (table, set(), None), run_pid=run_pid) is None
        assert child.wait(timeout=5) == -9 and orphan.wait(timeout=5) == -9
        assert independent.poll() is None, "a process the run did not start was stopped"
    finally:
        for proc in (independent, child, orphan):
            proc.kill()
            proc.wait()


@needs_sleep
def test_g3_a_process_already_running_when_the_run_launched_survives_a_same_second_rounded_start(repo):
    # axis: a pre-existing process whose rounded-up start reads as after the run began is spared by the launch-time snapshot, not by the clock
    since = time.time()
    older = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    fresh = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    root = os.path.realpath(str(repo))
    table = [(older.pid, root, since + 0.2, 1, 500), (fresh.pid, root, since + 0.3, 1, 501)]
    try:
        known = break_it._known_processes(reader=lambda: (table[:1], set(), None))
        assert known == {(older.pid, 500)}
        assert break_it._kill_in_working_copy(str(repo), since, reader=lambda: (table, set(), None), known=known) is None
        assert fresh.wait(timeout=5) == -9
        assert older.poll() is None, "a process that predates the run was stopped"
    finally:
        for proc in (older, fresh):
            proc.kill()
            proc.wait()


@needs_sleep
def test_g3_a_pre_existing_process_whose_derived_start_time_moves_between_readings_survives(repo):
    # axis: identity is the raw start mark, not the derived float time, so a start time that reads differently at cleanup does not make a pre-existing process eligible
    since = time.time()
    older = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    root = os.path.realpath(str(repo))
    first = [(older.pid, root, since + 0.2, 1, 777)]
    later = [(older.pid, root, since + 0.2000001, 1, 777)]
    try:
        known = break_it._known_processes(reader=lambda: (first, set(), None))
        assert break_it._kill_in_working_copy(str(repo), since, reader=lambda: (later, set(), None), known=known) is None
        assert older.poll() is None, "a pre-existing process was stopped because its derived start time moved"
    finally:
        older.kill()
        older.wait()


def test_g3_a_watcher_is_joined_before_its_dictionary_is_swept(monkeypatch):
    # axis: stop_and_kill waits out a sample in progress, so an insertion cannot race the sweep and the thread is gone on return
    watch = break_it._DescendantWatch(os.getpid())
    entered = threading.Event()

    def slow_sample():
        entered.set()
        time.sleep(0.3)
        for i in range(2000):
            watch.seen[10 ** 9 + i] = "never a real start"

    monkeypatch.setattr(watch, "sample", slow_sample)
    watch.start()
    assert entered.wait(5)
    watch.stop_and_kill()
    assert not watch.is_alive()


def test_g3_a_reader_that_names_a_note_skips_the_net_and_says_why(repo):
    assert break_it._kill_in_working_copy(str(repo), 0, reader=lambda: ([], set(), "skipped: why")) == "skipped: why"


@needs_sleep
@pytest.mark.skipif(not HAS_PROC or not os.path.exists("/usr/bin/lsof"), reason="needs /proc and lsof")
def test_g3_the_lsof_reader_drives_the_same_net(repo):
    if not break_it._ps_table():
        pytest.skip("ps cannot be read from this process")
    since = time.time() - 2
    victim = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    try:
        processes, ancestors, note = break_it._lsof_cwd_table()
        assert note is None
        assert os.getpid() in ancestors
        mine = [p for p in processes if p[0] == victim.pid]
        assert mine and mine[0][1] == os.path.realpath(str(repo)) and mine[0][2] >= since
        assert break_it._kill_in_working_copy(str(repo), since, reader=break_it._lsof_cwd_table, run_pid=os.getpid()) is None
        assert victim.wait(timeout=5) == -9
    finally:
        victim.kill()
        victim.wait()


@needs_sleep
def test_g3_the_lsof_reader_assembles_its_table_from_lsof_and_ps_text(repo, monkeypatch):
    victim = subprocess.Popen(["/bin/sleep", "60"], cwd=str(repo))
    real = subprocess.run
    root = os.path.realpath(str(repo))
    lsof_text = "p%d\nn%s\np%d\nn/elsewhere\n" % (victim.pid, root, os.getpid())
    lstart = time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(time.time() + 5))

    def fake(cmd, *args, **kwargs):
        if cmd[0] == "lsof":
            return subprocess.CompletedProcess(cmd, 0, lsof_text.encode(), b"")
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(break_it.subprocess, "run", fake)
    monkeypatch.setattr(break_it, "_ps_table", lambda: {victim.pid: (os.getpid(), lstart),
                                                         os.getpid(): (os.getppid(), lstart),
                                                         os.getppid(): (1, lstart)})
    try:
        processes, ancestors, note = break_it._lsof_cwd_table()
        assert note is None
        assert sorted(p[:2] for p in processes) == sorted([(victim.pid, root), (os.getpid(), "/elsewhere")])
        assert {os.getpid(), os.getppid()} <= ancestors and victim.pid not in ancestors
        assert break_it._kill_in_working_copy(str(repo), time.time(), reader=break_it._lsof_cwd_table, run_pid=os.getpid()) is None
        assert victim.wait(timeout=5) == -9
    finally:
        victim.kill()
        victim.wait()


def test_g3_a_host_without_lsof_skips_the_net_with_a_note(repo, monkeypatch):
    real = subprocess.run

    def no_lsof(cmd, *args, **kwargs):
        if cmd[0] == "lsof":
            raise FileNotFoundError("lsof")
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(break_it.subprocess, "run", no_lsof)
    processes, ancestors, note = break_it._lsof_cwd_table()
    assert (processes, ancestors) == ([], set())
    assert "lsof is absent" in note
    assert break_it._kill_in_working_copy(str(repo), 0, reader=break_it._lsof_cwd_table) == note


def test_g3_the_lsof_and_ps_text_readers():
    assert break_it._lsof_cwds("p12\nn/a/b\np34\nn/c d\n") == {12: "/a/b", 34: "/c d"}
    started = break_it._ps_start("Thu Oct 29 12:00:05 2026")
    assert started == time.mktime(time.strptime("Thu Oct 29 12:00:05 2026", "%a %b %d %H:%M:%S %Y")) + 1
    assert break_it._ps_start("not a date") is None
    assert break_it._ancestors({5: 4, 4: 1, 1: 0}, 5) == {5, 4, 1}


# ---- G5: untracked files that existed before the run are put back --------------------------------------


def test_g5_an_existing_untracked_file_the_run_deletes_or_overwrites_is_restored(repo):
    # axis: the owner's uncommitted untracked files come back byte for byte, mode included, after a run that removed or clobbered them
    (repo / "owner-notes.txt").write_text("irreplaceable\n")
    (repo / "other.txt").write_text("keep me\n")
    os.chmod(str(repo / "other.txt"), 0o755)
    record = _run(repo, "tests/test_clobber.py",
                  "import os\nos.remove('owner-notes.txt')\nopen('other.txt', 'w').write('clobbered')\n")
    assert record["outcome"] == "passed", record
    assert (repo / "owner-notes.txt").read_text() == "irreplaceable\n"
    assert (repo / "other.txt").read_text() == "keep me\n"
    assert os.stat(str(repo / "other.txt")).st_mode & 0o777 == 0o755
    assert "untracked" in record["restored"], record


def test_g5_an_existing_untracked_nested_repository_refuses_the_run(repo):
    # axis: an untracked nested repository cannot be backed up, so the run is refused and its files are left alone
    nested = repo / "nested"
    nested.mkdir()
    _git(nested, "init", "-q")
    (nested / "owner-notes.txt").write_text("irreplaceable\n")
    record = _run(repo, "tests/test_quiet.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-unreadable"), record
    assert (nested / "owner-notes.txt").read_text() == "irreplaceable\n"


def test_g5_untracked_files_too_large_to_protect_refuse_the_run(repo, monkeypatch):
    # axis: a run that cannot protect the existing untracked files is not run at all, rather than reporting a restoration it cannot make
    (repo / "big.bin").write_bytes(b"x" * 100)
    monkeypatch.setattr(break_it, "_UNTRACKED_BACKUP_LIMIT", 10)
    record = _run(repo, "tests/test_quiet.py", "assert True\n")
    assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-unreadable"), record
    assert (repo / "big.bin").read_bytes() == b"x" * 100


# ---- G4: only HEAD's own branch is put back; every other changed ref is left and listed ----------------


def test_g4_a_branch_another_worktree_creates_during_the_run_survives_and_is_listed(repo, tmp_path):
    other = tmp_path / "other-wt"
    _git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    content = ("import subprocess\n"
               "subprocess.run(['git', '-C', %r, 'branch', 'saved-work', 'HEAD'], check=True)\n"
               "subprocess.run(['git', '-C', %r] + %r + ['commit', '-q', '--allow-empty', '-m', 'b work'], check=True)\n"
               % (str(other), str(other), _ID))
    pinned = _git(repo, "rev-parse", "HEAD")
    record = _run(repo, "tests/test_concurrent.py", content)
    assert record["outcome"] == "passed", record
    refs = _refs(repo)
    assert refs["refs/heads/saved-work"] == pinned
    assert _git(repo, "log", "-1", "--format=%s", "other") == "b work"
    assert record["refsLeft"] == ["refs/heads/other", "refs/heads/saved-work"], record
    assert record["restored"] == ["test-file"], record
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == ""


def test_g4_the_working_copys_own_branch_the_test_moves_is_put_back(repo):
    pinned = _git(repo, "rev-parse", "HEAD")
    content = ("import subprocess\n"
               "subprocess.run(['git'] + %r + ['commit', '-q', '--allow-empty', '-m', 'by the test'], check=True)\n"
               % (_ID,))
    record = _run(repo, "tests/test_own.py", content)
    assert record["outcome"] == "passed", record
    assert record["restored"] == ["test-file", "refs"], record
    assert record["refsLeft"] == []
    assert _refs(repo) == {"refs/heads/main": pinned}
    assert _git(repo, "rev-parse", "HEAD") == pinned


def test_g4_a_deleted_own_branch_is_created_again_and_a_ref_the_test_adds_is_not_deleted(repo):
    pinned = _git(repo, "rev-parse", "HEAD")
    content = ("import subprocess\n"
               "subprocess.run(['git', 'update-ref', '--no-deref', 'HEAD', %r], check=True)\n"
               "subprocess.run(['git', 'branch', '-D', 'main'], check=True)\n"
               "subprocess.run(['git', 'tag', 'added'], check=True)\n" % pinned)
    record = _run(repo, "tests/test_del.py", content)
    assert record["outcome"] == "passed", record
    assert _refs(repo) == {"refs/heads/main": pinned, "refs/tags/added": pinned}
    assert record["refsLeft"] == ["refs/tags/added"], record
    assert _git(repo, "symbolic-ref", "HEAD") == "refs/heads/main"


def test_g4_a_quiet_run_and_a_not_run_both_carry_an_empty_refs_left(repo):
    assert _run(repo, "tests/test_q.py", "assert True\n")["refsLeft"] == []
    refused = break_it.run_one(str(repo), "HEAD", TB._block("tests/test_q.py", "assert True\n", run="a | b"))
    assert (refused["outcome"], refused["refsLeft"]) == ("not-run", [])


def test_g4_the_helper_that_listed_other_checkouts_is_gone():
    assert not hasattr(break_it, "_other_checkouts")


# ---- G7: a restore-failed run parks cannot-certify -----------------------------------------------------

KEY = "finding-key-1"


def _kept_state(runs_by_round):
    rounds = {str(n): {"breakItRuns": runs} for n, runs in runs_by_round.items()}
    return {"round": max(runs_by_round), "rounds": rounds, "decisions": [], "step": RD.P_VERIFIERS,
            "config": {}, "findings": [],
            "dispositionLedgerOwner": session_contract.DISPOSITION_LEDGER_OWNER_VALUE,
            session_contract.DISPOSITION_LEDGER_KEY: [
                {session_contract.FINDING_KEY_FIELD: KEY, "file": "a.py", "title": "t",
                 "disposition": "refuted", "dispositionRound": 1, "refutedReason": "no defect"}]}


def _run_record(outcome, reason=None, output=""):
    return {"path": "tests/test_a.py", "findingKey": KEY, "outcome": outcome, "reason": reason, "output": output,
            "command": "c", "sha256": "s"}


def test_g7_a_restore_failed_run_for_a_refuted_finding_parks_cannot_certify():
    state = _kept_state({1: [_run_record("not-run", "working-copy-restore-failed", "index: reset refused")]})
    assert RD._break_it_kept_step(state, state["config"]) is True
    assert state["terminal"] == "cannot-certify" and state["step"] == RD.P_TERMINAL
    assert "working copy not restored" in state["certification"]["reason"]
    assert "reset refused" in state["certification"]["reason"]


def test_g7_a_later_passing_run_for_the_same_finding_does_not_lift_the_park():
    state = _kept_state({1: [_run_record("not-run", "working-copy-restore-failed", "index: reset refused")],
                         2: [_run_record("passed")]})
    assert RD._break_it_kept_step(state, state["config"]) is True
    assert state["terminal"] == "cannot-certify"
    assert "working copy not restored" in state["certification"]["reason"]


def test_g7_the_same_refuted_finding_with_only_a_passing_run_does_not_park():
    state = _kept_state({1: [_run_record("passed")]})
    assert RD._break_it_kept_step(state, state["config"]) is False
    assert state.get("terminal") is None
