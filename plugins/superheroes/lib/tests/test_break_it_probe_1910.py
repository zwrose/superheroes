"""The readiness probe runs inside the same containment as the test (#1910 WO-5)."""
import os
import shlex
import shutil
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import test_break_it as TB  # noqa: E402  (the git-repo fixtures and `_gone` live there)
import test_break_it_interpreter_1910 as TI  # noqa: E402  (the launcher fixture's helpers)
from test_break_it import repo  # noqa: E402,F401  (the fixture, reused by name)

WORKER_PIDFILE_ENV = "PROBE_WORKER_PIDFILE"
DETACHED_LAUNCHER = "scripts/detaching-python"
CHATTY_LAUNCHER = "scripts/chatty-python"


def _detaching_launcher_body(sleep_program):
    # The launcher's startup spawns a worker in its own session, with an empty environment, from `/`, and
    # records its pid in the file the environment names; only the reaper's own tree scan can catch it. It does so
    # for the readiness probe's `-c` only, so the recorded worker is the probe's and never the test run's. The
    # worker lets go of the pipe, so the launcher's exit ends the probe at once and the worker is what is left behind.
    return ("#!%s\n"
            "import os, subprocess, sys\n"
            "if sys.argv[1:2] == ['-c']:\n"
            "    d = subprocess.DEVNULL\n"
            "    p = subprocess.Popen([%r, '60'], start_new_session=True, env={}, cwd='/',\n"
            "                         stdin=d, stdout=d, stderr=d)\n"
            "    open(os.environ[%r], 'w').write(str(p.pid))\n"
            "    exec(sys.argv[2])\n") % (sys.executable, sleep_program,
                                                                WORKER_PIDFILE_ENV)


CHATTY_BODY = "#!/bin/sh\nwhile :; do echo launcher-keeps-talking-launcher-keeps-talking; done\n"


@pytest.fixture
def probe_repo(repo):
    # The same shape as `launcher_repo` in test_break_it_interpreter_1910: the project's launchers are committed.
    TI._add_launchers(repo)
    TB._write(repo, DETACHED_LAUNCHER, _detaching_launcher_body(shutil.which("sleep")))
    TB._write(repo, CHATTY_LAUNCHER, CHATTY_BODY)
    for rel in (DETACHED_LAUNCHER, CHATTY_LAUNCHER):
        os.chmod(str(repo / rel), 0o755)
    TB._commit(repo, "probe launchers")
    return repo


# ---- E1: a detached worker the probe's launcher spawns is gone after run_one ----------------

@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="needs the Linux child-subreaper reaper")
def test_e1_the_probes_detached_worker_is_gone_after_run_one(probe_repo, tmp_path):
    # bites on: the probe running through `_run_contained`; a worker with its own session, no environment and
    # cwd `/` escapes the group kill, the token sweep and the directory sweep, so only the reaper can catch it.
    pidfile = tmp_path / "worker.pid"
    block = TI._python_block(program="python3")
    block["run"] = "%s=%s python3 %s" % (WORKER_PIDFILE_ENV, shlex.quote(str(pidfile)), TI.TEST_PATH)
    record = break_it.run_one(str(probe_repo), TB._head(probe_repo), block, interpreter=DETACHED_LAUNCHER)
    assert pidfile.exists(), "the probe's launcher never ran"
    pid = int(pidfile.read_text())
    try:
        assert TB._gone(pid), "the probe's detached worker outlived run_one"
    finally:
        if not TB._gone(pid):
            os.kill(pid, 9)
    # the launcher itself exits 0, so the probe passes and the (failing) test then ran under it
    assert record["interpreter"] == DETACHED_LAUNCHER


# ---- E2: a launcher that prints without end keeps a bounded tail ----------------------------

def test_e2_a_launcher_that_prints_forever_records_a_bounded_tail(probe_repo, monkeypatch):
    # bites on: the trim in `_TailDrain.run`; the drain's buffer is watched, so an unbounded buffer is seen
    # directly and not only through the final truncation, which `_tail_text` applies whatever the drain kept.
    drains, peak = [], []

    class Watching(break_it._TailDrain):
        def __init__(self, stream):
            super().__init__(stream)
            drains.append(self)

        @property
        def buf(self):
            return self._buf

        @buf.setter
        def buf(self, value):
            self._buf = value
            peak.append(len(value))

    monkeypatch.setattr(break_it, "_TailDrain", Watching)
    record = break_it.run_one(str(probe_repo), TB._head(probe_repo), TI._python_block(),
                              interpreter=CHATTY_LAUNCHER, timeout=2)
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")
    assert "launcher-keeps-talking" in record["output"]
    assert len(record["output"].encode("utf-8")) <= break_it.OUTPUT_TAIL_BYTES
    assert len(drains) == 1, "the probe's output did not go through the tail drain"
    assert len(drains[0].buf) <= break_it.OUTPUT_TAIL_BYTES, "the drain kept more than the tail bound"
    # one read of at most 64 KiB is in flight before each trim, and the buffer holds no more than the bound
    assert max(peak) <= break_it.OUTPUT_TAIL_BYTES + 65536, "the drain's buffer outgrew the tail bound"


# ---- E3: the three ways a launcher cannot start still read not-run/interpreter-unavailable ----

@pytest.mark.parametrize("launcher, kwargs", [
    ("scripts/missing-python", {}),
    ("scripts/broken-python", {}),
    ("scripts/slow-python", {"timeout": 1}),
])
def test_e3_a_launcher_that_does_not_start_still_reads_not_run(probe_repo, launcher, kwargs):
    record = break_it.run_one(str(probe_repo), TB._head(probe_repo), TI._python_block(),
                              interpreter=launcher, **kwargs)
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")
    assert record["interpreter"] == launcher
    assert record["exitCode"] is None


def test_e3_the_probe_is_the_only_launch_outside_the_test_run():
    # `_probe_interpreter` is retired: the probe and the test share the one contained launch.
    assert not hasattr(break_it, "_probe_interpreter")
    assert callable(break_it._run_contained)
