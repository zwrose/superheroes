import copy
import hashlib
import os
import shlex
import subprocess
import sys
import time

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402

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


def _block(path, content, run=None):
    run = run if run is not None else "%s %s" % (PY, shlex.quote(path))
    block, refusal = break_it.parse_block(
        "break-it-test v1\npath: %s\nrun: %s\n---\n%s" % (path, run, content))
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
    block = "break-it-test v1\npath: %s\nrun: %s %s\n---\nassert True\n" % (path, PY, path)
    out = {"title": "Break-it: %s" % path, "file": path, "taxonomy": break_it.TAXONOMY,
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
    assert set(record) == {"schema", "role", "path", "command", "head", "sha256", "outcome",
                           "reason", "exitCode", "output"}
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


# T9
def test_t9_run_one_kills_a_lingering_worker(repo, tmp_path):
    pidfile = tmp_path / "worker.pid"
    content = ("import os, subprocess\n"
               "p = subprocess.Popen(['sleep', '60'], start_new_session=False)\n"
               "open(os.environ['PIDFILE'], 'w').write(str(p.pid))\n")
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


# T10
def test_t10_run_one_caps_the_output_tail(repo):
    content = "for i in range(10000):\n    print('line-%05d' % i)\nassert False\n"
    record = break_it.run_one(str(repo), _head(repo), _block("tests/test_o.py", content))
    assert record["outcome"] == "failed"
    assert len(record["output"].encode("utf-8")) <= break_it.OUTPUT_TAIL_BYTES
    assert "line-09999" in record["output"]
    assert "line-00000" not in record["output"]


# T11
def test_t11_run_one_leaves_nothing_behind(repo, monkeypatch):
    made = []
    real = break_it.tempfile.mkdtemp

    def spy(*args, **kwargs):
        made.append(real(*args, **kwargs))
        return made[-1]

    monkeypatch.setattr(break_it.tempfile, "mkdtemp", spy)
    head = _head(repo)
    break_it.run_one(str(repo), head, _block("tests/test_a.py", "assert True\n"))
    break_it.run_one(str(repo), head, _block("tests/test_b.py", "assert False\n"))
    break_it.run_one(str(repo), head, _block("README.md", "x\n"))
    break_it.run_one(str(repo), "no-such-rev", _block("tests/test_c.py", "assert True\n"))
    assert len(made) == 4
    assert not any(os.path.exists(d) for d in made)
    listing = _git(repo, "worktree", "list", "--porcelain")
    assert [ln for ln in listing.splitlines() if ln.startswith("worktree ")] == [
        "worktree %s" % os.path.realpath(str(repo))]
    assert _git(repo, "status", "--porcelain") == ""
    assert _head(repo) == head


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


def test_t12_intercept_caps_the_runs_and_refuses_a_path_mismatch(repo):
    calls = []
    findings = [_finding("t/%d.py" % i) for i in range(4)]
    kept, runs, exempt = break_it.intercept(findings, str(repo), "H",
                                            runner=_fake("failed", calls))
    assert calls == ["t/0.py", "t/1.py", "t/2.py"]
    assert len(kept) == 4 and len(exempt) == 4
    capped = kept[3]["breakItRun"]
    assert (capped["outcome"], capped["reason"], capped["head"]) == ("not-run", "run-cap", "H")
    assert set(capped) == set(runs[0]) - {"title", "file"}
    assert capped["sha256"] is not None and capped["exitCode"] is None
    mismatch = _finding("t/real.py", file="t/other.py")
    calls.clear()
    kept, runs, exempt = break_it.intercept([mismatch], str(repo), "H", runner=_fake("passed", calls))
    assert calls == []
    assert kept[0]["breakItRun"]["reason"] == "path-mismatch" and id(kept[0]) in exempt
    bad = _finding("t/real.py", suggestion="not a block")
    kept, runs, exempt = break_it.intercept([bad], str(repo), "H", runner=_fake("passed", calls))
    assert kept[0]["breakItRun"]["reason"] == "block-header-missing"
    assert kept[0]["breakItRun"]["sha256"] is None and calls == []


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
