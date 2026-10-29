import copy
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import proc_namespace  # noqa: E402

PY = shlex.quote(sys.executable)
# The fixture repo's commits pass an inline identity (a CI runner has no configured one); the throwaway fixture repo also signs nothing.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _write(root, "README.md", "fixture\n")
    _write(root, "mod.py", "def value():\n    return 2\n")
    _commit(root, "base")
    return root


def _template():
    """The block grammar's lines, read from the one home of the grammar (`break_it.BLOCK_TEMPLATE`)."""
    lines = break_it.BLOCK_TEMPLATE.split("\n")
    assert len(lines) == 5 and lines[3] == "---"
    return lines


def _wire(path, run, content):
    """A block built from exactly the specification's template: header, path:, run:, ---, content."""
    head, path_line, run_line, sep, _ = _template()
    assert path_line.startswith("path: <") and run_line.startswith("run: <")
    return "\n".join([head, "path: " + path, "run: " + run, sep]) + "\n" + content


def _block(path, content, run=None):
    run = run if run is not None else "%s %s" % (PY, shlex.quote(path))
    block, refusal = break_it.parse_block(_wire(path, run, content))
    assert refusal is None
    return block


def _head(repo):
    return _git(repo, "rev-parse", "HEAD")


def _fake(outcome, calls=None):
    def runner(repo_root, head, block, **kwargs):
        if calls is not None:
            calls.append(block["path"])
        return break_it._record(head, block, outcome, exit_code=0 if outcome == "passed" else 1)
    return runner


def _finding(path, **extra):
    block = _wire(path, "%s %s" % (PY, path), "assert True\n")
    out = {"title": "Break-it: %s" % path, "file": path, "line": 1, "taxonomy": break_it.TAXONOMY,
           "suggestion": block}
    out.update(extra)
    return out


# T1
def test_t1_parse_block_round_trips_and_refuses():
    text = "break-it-test v1\npath: tests/test_x.py\nrun: python tests/test_x.py\n---\nA\r\n  b  \n\n"
    block, refusal = break_it.parse_block(text)
    assert refusal is None
    assert block == {"path": "tests/test_x.py", "run": "python tests/test_x.py",
                     "content": "A\r\n  b  \n\n",
                     "sha256": hashlib.sha256(b"A\r\n  b  \n\n").hexdigest()}
    good = "break-it-test v1\npath: t/x.py\nrun: python t/x.py\n---\nz\n"
    cases = [
        (None, "block-not-a-string"),
        ("break-it-test v2\npath: t/x.py\nrun: r\n---\n", "block-header-missing"),
        (" break-it-test v1\npath: t/x.py\nrun: r\n---\n", "block-header-missing"),
        ("break-it-test v1 \npath: t/x.py\nrun: r\n---\n", "block-header-missing"),
        ("break-it-test v1\r\npath: t/x.py\r\nrun: r\r\n---\r\n", "block-header-missing"),
        ("break-it-test v1\nrun: r\n---\n", "block-path-missing"),
        ("break-it-test v1\npath:\nrun: r\n---\n", "block-path-missing"),
        ("break-it-test v1\npath: t/x.py\npath: t/x.py\n---\n", "block-run-missing"),
        ("break-it-test v1\npath: t/x.py\nrun:   \n---\n", "block-run-missing"),
        ("break-it-test v1\npath: t/x.py\nrun: r\n--\nz", "block-separator-missing"),
        ("break-it-test v1\npath: t/x.py\nrun: r", "block-separator-missing"),
        ("break-it-test v1\npath: /abs/x.py\nrun: r\n---\n", "path-unsafe"),
        ("break-it-test v1\npath: t\\x.py\nrun: r\n---\n", "path-unsafe"),
        ("break-it-test v1\npath: t/../x.py\nrun: r\n---\n", "path-unsafe"),
        ("break-it-test v1\npath: ./x.py\nrun: r\n---\n", "path-unsafe"),
        ("break-it-test v1\npath: t//x.py\nrun: r\n---\n", "path-unsafe"),
    ]
    for given, expected in cases:
        assert break_it.parse_block(given) == (None, expected), given
    assert break_it.parse_block(good)[1] is None


def test_parse_block_follows_block_template():
    good = _wire("tests/test_x.py", "python tests/test_x.py", "z\n")
    block, refusal = break_it.parse_block(good)
    assert refusal is None and block["path"] == "tests/test_x.py" and block["content"] == "z\n"
    header = _template()[0]
    assert break_it.parse_block(good.replace(header, header + "x", 1)) == (
        None, "block-header-missing")


# T2
def test_t2_parse_command_grammar_and_refusals():
    assert break_it.parse_command("FOO=1 BAR_2='a b' python -m x t.py") == (
        ["python", "-m", "x", "t.py"], {"FOO": "1", "BAR_2": "a b"}, None)
    assert break_it.parse_command("python t.py") == (["python", "t.py"], {}, None)
    for run in ("", "   ", None, "FOO=1"):
        assert break_it.parse_command(run) == (None, None, "run-empty"), run
    assert break_it.parse_command("python 'unclosed") == (None, None, "run-unparseable")
    for run in ("a | b", "a && b", "a; b", "a > f", "a >> f", "a 2> f", "a &> f", "a >f",
                "a <f", "a;", "a |", "a &", "a || b", "a `x`", "a $(x)", "a \"$(x)\""):
        assert break_it.parse_command(run) == (None, None, "run-shell-syntax"), run


# T3
def test_t3_run_one_failing_test_is_failed_with_output(repo):
    block = _block("tests/test_f.py", "assert 1 == 2, 'boom-marker'\n")
    record = break_it.run_one(str(repo), _head(repo), block)
    assert record["outcome"] == "failed"
    assert record["exitCode"] == 1
    assert record["reason"] is None
    assert "boom-marker" in record["output"]
    assert set(record) == {"schema", "role", "path", "command", "head", "sha256", "content", "outcome",
                           "reason", "exitCode", "output", "interpreter", "restored"}
    assert record["content"] == block["content"]
    assert record["schema"] == break_it.SCHEMA and record["role"] == break_it.ROLE


# T4
def test_t4_run_one_passing_test_is_passed(repo):
    block = _block("tests/test_p.py", "assert 1 == 1\n")
    record = break_it.run_one(str(repo), _head(repo), block)
    assert (record["outcome"], record["exitCode"], record["reason"]) == ("passed", 0, None)
    assert record["head"] == _head(repo) and record["sha256"] == block["sha256"]


# T5
def test_t5_run_one_command_not_found(repo):
    block = _block("tests/test_n.py", "pass\n", run="no-such-binary-xyz tests/test_n.py")
    record = break_it.run_one(str(repo), _head(repo), block)
    assert (record["outcome"], record["reason"]) == ("not-run", "command-not-found")
    assert record["exitCode"] is None


# T6
def test_t6_run_one_refuses_a_path_the_head_tracks(repo):
    _write(repo, "tests/test_t.py", "assert False, 'tracked'\n")
    head = _commit(repo, "tracked")
    block = _block("tests/test_t.py", "assert True\n")
    record = break_it.run_one(str(repo), head, block)
    assert (record["outcome"], record["reason"]) == ("not-run", "path-exists")
    assert (repo / "tests/test_t.py").read_text() == "assert False, 'tracked'\n"


# T6b
def test_t6b_run_one_runs_a_target_that_already_holds_the_blocks_bytes(repo):
    content = "assert False, 'kept and failing'\n"
    _write(repo, "tests/test_t.py", content)
    head = _commit(repo, "kept")
    record = break_it.run_one(str(repo), head, _block("tests/test_t.py", content))
    assert record["outcome"] == "failed" and record["reason"] is None
    assert "kept and failing" in record["output"]


def test_t6b_run_one_still_refuses_a_target_holding_other_bytes(repo):
    _write(repo, "tests/test_t.py", "assert True\n")
    head = _commit(repo, "tracked")
    record = break_it.run_one(str(repo), head, _block("tests/test_t.py", "assert True  # weakened\n"))
    assert (record["outcome"], record["reason"]) == ("not-run", "path-exists")


# T7
def test_t7_run_one_refuses_a_symlinked_ancestor(repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), str(repo / "linkdir"))
    head = _commit(repo, "symlink dir")
    block = _block("linkdir/test_e.py", "assert True\n")
    record = break_it.run_one(str(repo), head, block)
    assert (record["outcome"], record["reason"]) == ("not-run", "path-escapes")
    assert os.listdir(str(outside)) == []


# T8
def test_t8_run_one_times_out(repo):
    block = _block("tests/test_s.py", "import time\ntime.sleep(30)\n")
    started = time.monotonic()
    record = break_it.run_one(str(repo), _head(repo), block, timeout=2)
    assert time.monotonic() - started < 15
    assert (record["outcome"], record["reason"]) == ("not-run", "timeout")


def _gone(pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:
            with open("/proc/%d/stat" % pid) as fh:
                if fh.read().rsplit(")", 1)[1].split()[0] == "Z":
                    return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


_ENV_TAGS = {}


def _env_tags_readable():
    """Whether this host lets break_it's environment-tag net see a child's tag, found by trying it:
    a child started with a fresh tag must show up in ``_tagged_pids``. Inside the claude write
    sandbox ``ps`` cannot read process environments, so the net sees nothing there."""
    if "ok" not in _ENV_TAGS:
        token = "probe-%d" % os.getpid()
        env = dict(os.environ, **{break_it._TOKEN_ENV: token})
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], env=env)
        try:
            deadline = time.monotonic() + 5
            seen = False
            while not seen and time.monotonic() < deadline:
                seen = child.pid in break_it._tagged_pids(token)
                if not seen:
                    time.sleep(0.1)
            _ENV_TAGS["ok"] = seen
        finally:
            child.kill()
            child.wait()
    return _ENV_TAGS["ok"]


@pytest.fixture
def env_tags_readable():
    # Skips only inside the write sandbox: a blind net anywhere else (macOS included) is a regression and fails.
    if _env_tags_readable():
        return
    if proc_namespace.in_write_sandbox():
        pytest.skip("claude write sandbox: this host cannot read process environments (break_it._tagged_pids "
                    "did not see a tagged child), so the containment nets cannot be observed here")
    pytest.fail("break_it._tagged_pids did not see a tagged child outside the claude write sandbox (%s is not "
                "1), so the environment-tag net is broken here" % proc_namespace.SANDBOX_MARKER_ENV,
                pytrace=False)


# T9
# axis: containment covers a worker in the command's own group (False) and one that left it for a new session (True).
# A detached worker that also clears its environment is contained by the Linux reaper only.
@pytest.mark.proc_containment
@pytest.mark.parametrize("detached,clean_env", [
    (False, False), (True, False),
    pytest.param(True, True, marks=pytest.mark.skipif(
        not sys.platform.startswith("linux"), reason="needs the Linux child-subreaper reaper"))])
def test_t9_run_one_kills_a_lingering_worker(repo, tmp_path, detached, clean_env, env_tags_readable):
    pidfile = tmp_path / "worker.pid"
    content = ("import os, subprocess\n"
               "p = subprocess.Popen([%r, '60'], start_new_session=%s%s)\n"
               "open(os.environ['PIDFILE'], 'w').write(str(p.pid))\n"
               ) % (shutil.which("sleep"), detached, ", env={}, cwd='/'" if clean_env else "")
    block = _block("tests/test_w.py", content,
                   run="PIDFILE=%s %s tests/test_w.py" % (shlex.quote(str(pidfile)), PY))
    record = break_it.run_one(str(repo), _head(repo), block)
    assert record["outcome"] == "passed"
    pid = int(pidfile.read_text())
    try:
        assert _gone(pid), "the lingering worker outlived run_one"
    finally:
        if not _gone(pid):
            os.kill(pid, 9)


@pytest.mark.proc_containment
def test_t9_tag_net_kills_a_detached_worker_that_left_the_working_directory(repo, tmp_path, monkeypatch, env_tags_readable):
    # bites on: the _kill_tagged(token) call in run_one; the reaper cannot scan, the worker has its own session and has left the run's working directory but kept its environment, so only the environment-tag net can catch it; the worker is a Python child because macOS hides a system program's environment from `ps -E`.
    marker = 'PROC_ROOT = "/proc"'
    assert marker in break_it._REAPER
    monkeypatch.setattr(break_it, "_REAPER", break_it._REAPER.replace(marker, 'PROC_ROOT = "/nonexistent"'))
    pidfile = tmp_path / "worker.pid"
    content = ("import os, subprocess\n"
               "p = subprocess.Popen([%r, '-c', 'import time; time.sleep(60)'], start_new_session=True, cwd='/')\n"
               "open(os.environ['PIDFILE'], 'w').write(str(p.pid))\n") % sys.executable
    block = _block("tests/test_w.py", content,
                   run="PIDFILE=%s %s tests/test_w.py" % (shlex.quote(str(pidfile)), PY))
    assert break_it.run_one(str(repo), _head(repo), block)["outcome"] == "passed"
    pid = int(pidfile.read_text())
    try:
        assert _gone(pid), "the detached worker that left the working directory outlived run_one"
    finally:
        if not _gone(pid):
            os.kill(pid, 9)


@pytest.mark.proc_containment
def test_t9_drain_start_failure_still_reaps_the_launched_process(repo, monkeypatch, env_tags_readable):
    launched = []
    real = subprocess.Popen

    def spy(args, *a, **kw):
        proc = real(args, *a, **kw)
        if "-I" in args[:2]:
            launched.append(proc.pid)
        return proc

    def boom(self):
        time.sleep(1)  # let the launched test start, so a leak is a live process
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(break_it._TailDrain, "start", boom)
    monkeypatch.setattr(break_it.subprocess, "Popen", spy)
    block = _block("tests/test_d.py", "import time\ntime.sleep(60)\n")
    record = break_it.run_one(str(repo), _head(repo), block)
    assert (record["outcome"], record["reason"]) == ("not-run", "run-error")
    assert len(launched) == 1
    try:
        assert _gone(launched[0]), "the launched process outlived the failed run"
    finally:
        if not _gone(launched[0]):
            os.kill(launched[0], 9)


# T10
def test_t10_run_one_caps_the_output_tail(repo):
    content = "for i in range(10000):\n    print('line-%05d' % i)\nassert False\n"
    record = break_it.run_one(str(repo), _head(repo), _block("tests/test_o.py", content))
    assert record["outcome"] == "failed"
    assert len(record["output"].encode("utf-8")) <= break_it.OUTPUT_TAIL_BYTES
    assert "line-09999" in record["output"]
    assert "line-00000" not in record["output"]


# T11
def test_t11_run_one_leaves_nothing_behind(repo):
    head = _head(repo)
    before = _git(repo, "status", "--porcelain", "--untracked-files=all")
    records = [
        break_it.run_one(str(repo), head, _block("tests/test_a.py", "assert True\n")),
        break_it.run_one(str(repo), _head(repo), _block("tests/test_b.py", "assert False\n")),
        break_it.run_one(str(repo), head, _block("README.md", "x\n")),
        break_it.run_one(str(repo), "no-such-rev", _block("tests/test_c.py", "assert True\n"))]
    assert [(r["outcome"], r["reason"]) for r in records] == [
        ("passed", None), ("failed", None), ("not-run", "path-exists"), ("not-run", "working-copy-unreadable")]
    listing = _git(repo, "worktree", "list", "--porcelain")
    assert [ln for ln in listing.splitlines() if ln.startswith("worktree ")] == [
        "worktree %s" % os.path.realpath(str(repo))]
    assert not (repo / "tests").exists()
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == before == ""
    assert _head(repo) == head
    folders = repo / ".git" / "superheroes"
    assert not folders.exists() or [n for n in os.listdir(str(folders)) if n.startswith("break-it-tmp-")] == []


# T12
def test_t12_intercept_strips_a_forged_stamp_and_never_mutates(repo):
    forged = {"title": "plain", "file": "a.py", "breakItRun": {"outcome": "passed"}}
    plain = {"title": "other", "file": "b.py"}
    failing = _finding("tests/test_x.py", breakItRun={"outcome": "passed"})
    original = copy.deepcopy([forged, plain, failing, "not-a-dict"])
    given = copy.deepcopy(original)
    kept, runs, exempt = break_it.intercept(given, str(repo), "H", runner=_fake("failed"))
    assert given == original
    assert [k.get("title") for k in kept[:2]] == ["plain", "other"]
    assert "breakItRun" not in kept[0] and "breakItRun" not in kept[1]
    assert kept[0] is not given[0] and kept[3] == "not-a-dict"
    assert kept[2]["breakItRun"]["outcome"] == "failed"
    assert exempt == {id(kept[2])}
    assert len(runs) == 1 and runs[0]["title"] == "Break-it: tests/test_x.py"
    assert runs[0]["file"] == "tests/test_x.py"


def test_t12_intercept_drops_a_passed_run_and_keeps_failed_and_not_run(repo):
    findings = [_finding("t/a.py"), _finding("t/b.py"), _finding("t/c.py")]
    outcomes = {"t/a.py": "passed", "t/b.py": "failed", "t/c.py": "not-run"}

    def runner(repo_root, head, block, **kwargs):
        return _fake(outcomes[block["path"]])(repo_root, head, block)

    kept, runs, exempt = break_it.intercept(findings, str(repo), "H", runner=runner)
    assert [k["file"] for k in kept] == ["t/b.py", "t/c.py"]
    assert [r["outcome"] for r in runs] == ["passed", "failed", "not-run"]
    assert exempt == {id(k) for k in kept}
    assert all(k["breakItRun"]["role"] == break_it.ROLE for k in kept)


@pytest.mark.parametrize("run", [
    "sh -c 'printf probe | wc -c'", "bash -c 'x'", "/bin/dash -c x", "zsh -c x", "ksh -c x",
    "mksh -c x", "fish -c x", "busybox sh -c x", "FOO=1 sh -c x"])
def test_parse_command_refuses_shell_interpreters(run):
    assert break_it.parse_command(run) == (None, None, "run-shell-interpreter")


@pytest.mark.parametrize("run", [
    "env -u X sh -c 'x'", "env -S \"sh -c x\"", "env python t.py", "env FOO=1 python t.py",
    "/usr/bin/env zsh -c x", "FOO=1 env -i bash -c x"])
def test_parse_command_refuses_the_env_program(run):
    assert break_it.parse_command(run) == (None, None, "run-env-program")


def test_t12_intercept_runs_every_finding_and_refuses_a_path_mismatch(repo):
    calls = []
    findings = [_finding("t/%d.py" % i) for i in range(4)]
    kept, runs, exempt = break_it.intercept(findings, str(repo), "H",
                                            runner=_fake("failed", calls))
    assert calls == ["t/%d.py" % i for i in range(4)]
    assert len(kept) == 4 and len(exempt) == 4
    mismatch = _finding("t/real.py", file="t/other.py")
    calls.clear()
    kept, runs, exempt = break_it.intercept([mismatch], str(repo), "H", runner=_fake("passed", calls))
    assert calls == []
    assert kept[0]["breakItRun"]["reason"] == "path-mismatch" and id(kept[0]) not in exempt
    bad = _finding("t/real.py", suggestion="not a block")
    kept, runs, exempt = break_it.intercept([bad], str(repo), "H", runner=_fake("passed", calls))
    assert kept[0]["breakItRun"]["reason"] == "block-header-missing"
    assert kept[0]["breakItRun"]["sha256"] is None and calls == []
    assert id(kept[0]) not in exempt


# T13
def _kept_fixture(repo, content, run_tail="tests/test_k.py"):
    """Commit a base, then a head that adds the test file; return (base, head, record)."""
    base = _head(repo)
    _write(repo, "tests/test_k.py", content)
    head = _commit(repo, "add test")
    record = {"path": "tests/test_k.py", "command": "%s %s" % (PY, run_tail),
              "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
    return base, head, record


def test_t13_check_kept_kept(repo):
    base, head, record = _kept_fixture(repo, "assert True\n")
    result = break_it.check_kept(str(repo), base, head, record)
    assert result["outcome"] == "kept" and result["run"]["outcome"] == "passed"
    assert result["path"] == "tests/test_k.py"


def test_t13_check_kept_missing(repo):
    base = _head(repo)
    record = {"path": "tests/test_k.py", "command": "%s tests/test_k.py" % PY,
              "sha256": hashlib.sha256(b"assert True\n").hexdigest()}
    result = break_it.check_kept(str(repo), base, base, record)
    assert (result["outcome"], result["run"]) == ("missing", None)
    # Present in head but already in base: the final diff does not carry it.
    _write(repo, "tests/test_k.py", "assert True\n")
    with_file = _commit(repo, "file in base")
    _write(repo, "unrelated.txt", "x\n")
    head = _commit(repo, "unrelated")
    result = break_it.check_kept(str(repo), with_file, head, record)
    assert (result["outcome"], result["reason"]) == ("missing", "not-in-diff")


def test_t13_check_kept_changed(repo):
    base, head, record = _kept_fixture(repo, "assert True\n")
    record["sha256"] = hashlib.sha256(b"assert 1 == 1\n").hexdigest()
    assert break_it.check_kept(str(repo), base, head, record)["outcome"] == "changed"


def test_t13_check_kept_not_regular(repo):
    base = _head(repo)
    os.makedirs(str(repo / "tests"))
    os.symlink("../README.md", str(repo / "tests/test_k.py"))
    head = _commit(repo, "symlink test")
    record = {"path": "tests/test_k.py", "command": "%s tests/test_k.py" % PY, "sha256": "0" * 64}
    assert break_it.check_kept(str(repo), base, head, record)["outcome"] == "not-regular"


def test_t13_check_kept_failing(repo):
    content = "import sys\nsys.path.insert(0, '.')\nimport mod\nassert mod.value() == 1, 'bad'\n"
    base, head, record = _kept_fixture(repo, content)
    result = break_it.check_kept(str(repo), base, head, record)
    assert result["outcome"] == "failing" and result["run"]["outcome"] == "failed"
    assert "bad" in result["run"]["output"]


def test_t13_check_kept_unresolved(repo):
    base, head, record = _kept_fixture(repo, "assert True\n")
    assert break_it.check_kept(str(repo), None, head, record)["outcome"] == "unresolved"
    assert break_it.check_kept(str(repo), base, head, {})["outcome"] == "unresolved"
    assert break_it.check_kept(str(repo), "no-such-rev", head, record)["outcome"] == "unresolved"


# T13
def test_t13_git_routing_is_scrubbed_and_refused(repo, tmp_path, monkeypatch):
    head = _head(repo)
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    content = ("import os, subprocess\n"
               "assert 'GIT_DIR' not in os.environ and 'GIT_WORK_TREE' not in os.environ\n"
               "top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()\n"
               "assert os.path.realpath(top) == os.path.realpath(os.getcwd()), top\n")
    record = break_it.run_one(str(repo), head, _block("tests/test_r.py", content))
    assert record["outcome"] == "passed", record
    refused = _block("tests/test_r.py", "pass\n", run="GIT_DIR=/x %s tests/test_r.py" % PY)
    record = break_it.run_one(str(repo), head, refused)
    assert (record["outcome"], record["reason"]) == ("not-run", "run-env-refused")


# T14
def test_t14_git_metadata_the_test_writes_is_restored(repo):
    content = ("import subprocess\n"
               "subprocess.check_call(['git', 'config', '--local', 'break.it', 'x'])\n"
               "subprocess.check_call(['git', 'tag', 'break-it-tag'])\n")
    record = break_it.run_one(str(repo), _head(repo), _block("tests/test_m.py", content))
    assert record["outcome"] == "passed", record
    assert record["restored"] == ["test-file", "refs", "config"]
    assert _git(repo, "tag", "--list") == ""
    done = subprocess.run(["git", "-C", str(repo), "config", "--local", "break.it"], capture_output=True)
    assert done.returncode != 0


# T15
def test_t15_run_one_bounds_stored_output(repo, monkeypatch):
    monkeypatch.setattr(break_it, "OUTPUT_TAIL_BYTES", 256)
    content = "import sys\nfor i in range(20000):\n    sys.stdout.write('x' * 100 + '\\n')\nassert False\n"
    record = break_it.run_one(str(repo), _head(repo), _block("tests/test_b.py", content))
    assert record["outcome"] == "failed"
    assert len(record["output"].encode("utf-8")) <= 256


def test_tail_drain_never_retains_more_than_the_cap(monkeypatch):
    monkeypatch.setattr(break_it, "OUTPUT_TAIL_BYTES", 256)
    rfd, wfd = os.pipe()

    def writer():
        with os.fdopen(wfd, "wb") as out:
            for i in range(5000):
                out.write(b"x" * 100 + b" line%d\n" % i)
            out.write(b"LAST-MARKER\n")

    with os.fdopen(rfd, "rb") as stream:
        drain = break_it._TailDrain(stream)
        drain.start()
        feeder = threading.Thread(target=writer)
        feeder.start()
        feeder.join(30)
        drain.join(30)
        assert not drain.is_alive()
    assert len(drain.buf) <= 256
    assert drain.buf.endswith(b"LAST-MARKER\n")


def test_clean_env_keeps_scalar_settings_and_drops_absolute_root_aliases(tmp_path, monkeypatch):
    root = tmp_path / "caller"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("TEST_MODE", "offline")
    monkeypatch.setenv("SERVICE_TOKEN", "x")
    monkeypatch.setenv("ROOT_ALIAS_VAR", str(alias))
    env = break_it._clean_env(root=str(root))
    assert env["TEST_MODE"] == "offline"
    assert env["SERVICE_TOKEN"] == "x"
    assert "ROOT_ALIAS_VAR" not in env


def test_reaper_without_proc_still_propagates_the_child_exit_status(repo, monkeypatch):
    # A host with no /proc (macOS): the reaper's descendant sweep is a no-op and the exit status survives.
    assert 'PROC_ROOT = "/proc"' in break_it._REAPER
    monkeypatch.setattr(break_it, "_REAPER",
                        break_it._REAPER.replace('PROC_ROOT = "/proc"', 'PROC_ROOT = "/nonexistent-proc-root"'))
    passing = break_it.run_one(str(repo), _head(repo), _block("tests/test_np.py", "assert 1 == 1\n"))
    assert (passing["outcome"], passing["exitCode"]) == ("passed", 0)
    failing = break_it.run_one(str(repo), _head(repo), _block("tests/test_nf.py", "assert 1 == 2\n"))
    assert (failing["outcome"], failing["exitCode"]) == ("failed", 1)


# The run's working directory is the caller's own tree, so an inherited import path into it is still scrubbed: the
# script's own folder, not the root, is all the test finds on its path until it adds the working directory itself.
_NOT_ON_PATH = ("import importlib.util, os, sys\nassert 'PYTHONPATH' not in os.environ\n"
                "assert importlib.util.find_spec('callermod') is None\n"
                "sys.path.append(os.getcwd())\nimport callermod\nassert callermod.VALUE == 'head', callermod.VALUE\n")


def test_inherited_import_path_into_the_caller_tree_is_dropped(repo, monkeypatch):
    _write(repo, "callermod.py", "VALUE = 'head'\n")
    head = _commit(repo, "add callermod")
    monkeypatch.setenv("PYTHONPATH", str(repo))
    record = break_it.run_one(str(repo), head, _block("tests/test_ip.py", _NOT_ON_PATH))
    assert record["outcome"] == "passed", record


def test_import_path_with_dot_segment_spelling_is_dropped(repo, monkeypatch):
    _write(repo, "callermod.py", "VALUE = 'head'\n")
    head = _commit(repo, "add callermod")
    monkeypatch.setenv("PYTHONPATH", os.path.join(str(repo.parent), ".", repo.name))
    record = break_it.run_one(str(repo), head, _block("tests/test_ipd.py", _NOT_ON_PATH))
    assert record["outcome"] == "passed", record


def test_clean_env_scrubs_aliased_root_entries_and_keeps_unrelated(repo, tmp_path, monkeypatch):
    aliased = os.path.join(str(repo.parent), ".", repo.name, "sub")
    monkeypatch.setenv("BI_ALIASED", "/nowhere" + os.pathsep + aliased)
    monkeypatch.setenv("BI_UNRELATED", str(tmp_path / "elsewhere"))
    env = break_it._clean_env({"BI_EXTRA": "1"}, str(repo))
    assert "BI_ALIASED" not in env
    assert env["BI_UNRELATED"] == str(tmp_path / "elsewhere")
    assert env["BI_EXTRA"] == "1"


@pytest.mark.proc_containment
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="needs the Linux child-subreaper reaper")
def test_exception_after_launch_still_lets_the_reaper_collect_a_detached_worker(repo, tmp_path, monkeypatch):
    pidfile = tmp_path / "worker.pid"

    def boom(self):  # the run fails after launch, once the test has started its detached worker
        deadline = time.monotonic() + 20
        while not (pidfile.exists() and pidfile.read_text()) and time.monotonic() < deadline:
            time.sleep(0.05)
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(break_it._TailDrain, "start", boom)
    content = ("import os, subprocess, time\n"
               "p = subprocess.Popen([%r, '60'], start_new_session=True, env={}, cwd='/')\n"
               "open(os.environ['PIDFILE'], 'w').write(str(p.pid))\n"
               "time.sleep(60)\n") % shutil.which("sleep")
    block = _block("tests/test_x.py", content,
                   run="PIDFILE=%s %s tests/test_x.py" % (shlex.quote(str(pidfile)), PY))
    record = break_it.run_one(str(repo), _head(repo), block)
    assert (record["outcome"], record["reason"]) == ("not-run", "run-error")
    pid = int(pidfile.read_text())
    try:
        assert _gone(pid), "the detached worker outlived the failed run"
    finally:
        if not _gone(pid):
            os.kill(pid, 9)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="scans /proc for the helper")
def test_git_setup_timeout_kills_the_helper_descendants(repo, tmp_path, monkeypatch):
    marker = "61.37"
    _write(repo, ".gitattributes", "*.dat filter=slow\n")
    _write(repo, "a.dat", "x\n")
    head = _commit(repo, "add filtered file")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[filter \"slow\"]\n\tsmudge = sleep %s\n" % marker)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.setattr(break_it, "_GIT_TIMEOUT", 3)

    def helpers():
        found = []
        for name in os.listdir("/proc"):
            try:
                with open("/proc/%s/cmdline" % name, "rb") as fh:
                    if marker.encode() in fh.read():
                        found.append(int(name))
            except OSError:
                pass
        return found

    try:
        started = time.monotonic()
        # the test rewrites a tracked file, so the restore's checkout of it runs the slow smudge helper
        content = "open('a.dat', 'w').write('changed\\n')\n"
        record = break_it.run_one(str(repo), head, _block("tests/test_g.py", content))
        assert time.monotonic() - started < 30, "the restore waited for the helper instead of killing it"
        assert (record["outcome"], record["reason"]) == ("not-run", "working-copy-restore-failed")
        deadline = time.monotonic() + 5
        while helpers() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert helpers() == [], "a git helper outlived the timed-out restore"
    finally:
        for pid in helpers():
            os.kill(pid, 9)
