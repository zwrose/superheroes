"""Round-1 review fixes for the working-copy break-it run (#2210): bytecode isolation, concurrent worktrees,
detached-child cleanup off Linux, and binding a run to the full finding anchor."""
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
import round_driver  # noqa: E402
import test_break_it as TB  # noqa: E402

_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
PY = shlex.quote(sys.executable)


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    TB._git(root, "init", "-q")
    TB._git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    TB._write(root, "README.md", "fixture\n")
    TB._commit(root, "base")
    return root


def _run(repo, path, content):
    return break_it.run_one(str(repo), TB._git(repo, "rev-parse", "HEAD"), TB._block(path, content))


def test_bytecode_is_routed_to_the_per_run_folder(repo):
    content = ("import os, sys\n"
               "prefix = sys.pycache_prefix\n"
               "assert prefix, 'no pycache prefix'\n"
               "assert 'break-it-tmp-' in prefix, prefix\n")
    record = _run(repo, "tests/test_pyc.py", content)
    assert record["outcome"] == "passed", record


def test_a_branch_another_worktree_has_checked_out_is_not_rewound(repo, tmp_path):
    other = tmp_path / "other-wt"
    TB._git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    content = ("import subprocess\n"
               "subprocess.run(['git', '-C', %r] + %r + ['commit', '-q', '--allow-empty', '-m', 'b work'], check=True)\n"
               % (str(other), _ID))
    record = _run(repo, "tests/test_concurrent.py", content)
    assert record["outcome"] == "passed", record
    # the other build's commit survives the restore
    assert TB._git(other, "log", "-1", "--format=%s") == "b work"
    assert TB._git(repo, "log", "-1", "--format=%s", "other") == "b work"
    assert TB._git(repo, "status", "--porcelain") == ""


@pytest.mark.skipif(not os.path.exists("/bin/sleep"), reason="needs a system sleep")
def test_descendant_watch_stops_a_detached_system_worker(tmp_path):
    parent = subprocess.Popen([sys.executable, "-c",
                               "import subprocess, sys, time\n"
                               "w = subprocess.Popen(['/bin/sleep', '60'], start_new_session=True)\n"
                               "print(w.pid, flush=True)\n"
                               "time.sleep(60)\n"],
                              stdout=subprocess.PIPE, text=True)
    try:
        worker = int(parent.stdout.readline())
        watch = break_it._DescendantWatch(parent.pid)
        watch.sample()
        assert worker in watch.seen
        parent.kill()
        parent.wait()
        watch.stop_and_kill()
        deadline = time.time() + 5
        state = "R"
        while time.time() < deadline and state != "":
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(worker)], capture_output=True,
                                   text=True).stdout.strip()
            if state.startswith("Z"):
                state = ""
            time.sleep(0.05)
        assert state == "", "the detached worker outlived the watch"
    finally:
        parent.kill()


def test_runs_bind_to_the_full_anchor_when_file_and_title_repeat():
    def finding(line, key, sha):
        return {"file": "a.py", "title": "Same title", "line": line, "findingKey": key,
                break_it.RUN_FIELD: {"sha256": sha, "command": "c", "reason": None},
                "suggestion": "x", "taxonomy": break_it.TAXONOMY}

    compiled = [finding(10, "k10", "s10"), finding(20, "k20", "s20")]
    runs = [{"file": "a.py", "title": "Same title", "line": 10, "sha256": "s10", "command": "c", "reason": None},
            {"file": "a.py", "title": "Same title", "line": 20, "sha256": "s20", "command": "c", "reason": None}]
    out = round_driver._break_it_run_keys(runs, compiled)
    assert [r["findingKey"] for r in out] == ["k10", "k20"]
    assert not any(r.get("supersededAtCompile") or r.get("droppedAtCompile") for r in out)
