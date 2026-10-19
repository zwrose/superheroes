import os
import subprocess
import sys

import pytest

import test_break_it
import test_break_it_probe_1910
from proc_namespace import (MARKER, SANDBOX_MARKER_ENV, in_write_sandbox, proc_is_foreign,
                            require_own_proc_namespace)

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# The complete census of tests whose assertion reads or signals processes by pid through /proc.
_CENSUS = (
    test_break_it.test_t9_run_one_kills_a_lingering_worker,
    test_break_it.test_t9_cwd_net_kills_a_detached_worker_without_the_reaper,
    test_break_it.test_t9_tag_net_kills_a_detached_worker_that_left_the_copy,
    test_break_it.test_exception_after_launch_still_lets_the_reaper_collect_a_detached_worker,
    test_break_it_probe_1910.test_e1_the_probes_detached_worker_is_gone_after_run_one,
)


def _readlink_returning(target):
    def readlink(path):
        assert path == "/proc/self"
        return target
    return readlink


def _readlink_raising(path):
    assert path == "/proc/self"
    raise OSError("no /proc")


# axis: sandbox-marker identity - the env name and the pytest mark name are the contract with the sandbox runtime and the census; catches a renamed marker that silently disarms the guard.
def test_marker_env_name_is_the_sandbox_runtime_variable():
    assert SANDBOX_MARKER_ENV == "SANDBOX_RUNTIME"
    assert MARKER == "proc_containment"


# axis: PID comparison (this test and the next) - equal numbers are own, different are foreign, and the path read must be /proc/self; catches an inverted comparison or a wrong proc path.
def test_equal_numbers_are_not_foreign():
    assert proc_is_foreign(_readlink_returning("3"), lambda: 3) is False


def test_different_numbers_are_foreign():
    assert proc_is_foreign(_readlink_returning("8"), lambda: 3) is True


# axis: missing/non-numeric proc (this test and the next) - no /proc or a non-pid /proc/self is not this constraint; catches either being reported as foreign.
def test_a_missing_proc_is_not_foreign():
    assert proc_is_foreign(_readlink_raising, lambda: 3) is False


def test_a_non_numeric_proc_self_is_not_foreign():
    assert proc_is_foreign(_readlink_returning("thread-self"), lambda: 3) is False


# axis: sandbox-marker value - only SANDBOX_RUNTIME=1 means the write sandbox; catches any other value or absence being taken for it.
def test_in_write_sandbox_reads_only_the_exact_marker_value():
    assert in_write_sandbox({SANDBOX_MARKER_ENV: "1"}) is True
    assert in_write_sandbox({SANDBOX_MARKER_ENV: "0"}) is False
    assert in_write_sandbox({}) is False


# axis: skip-vs-fail refusal, inside the sandbox - a foreign /proc skips with a message naming the sandbox and both pids; catches a hard failure or an unexplained skip.
def test_foreign_proc_in_the_sandbox_skips_naming_the_sandbox():
    with pytest.raises(pytest.skip.Exception) as raised:
        require_own_proc_namespace(_readlink_returning("8"), lambda: 3, {SANDBOX_MARKER_ENV: "1"})
    message = str(raised.value)
    assert message.startswith("claude write sandbox:")
    assert "/proc/self=8, getpid()=3" in message
    assert "cannot be observed here" in message


# axis: skip-vs-fail refusal, outside the sandbox - a foreign /proc fails and never skips; catches a skip that would hide a real namespace problem.
def test_foreign_proc_outside_the_sandbox_fails_never_skips():
    with pytest.raises(pytest.fail.Exception) as raised:
        require_own_proc_namespace(_readlink_returning("8"), lambda: 3, {})
    assert "another PID namespace" in str(raised.value)
    assert "refuses to skip" in str(raised.value)


# axis: skip-vs-fail refusal, own namespace - an own /proc neither skips nor fails; catches the guard firing on a normal host.
def test_own_proc_namespace_returns_none():
    assert require_own_proc_namespace(_readlink_returning("3"), lambda: 3, {}) is None


# axis: host truth - the real /proc on a normal host is not foreign (skipped in the sandbox); catches the detector misreading the live host.
def test_a_normal_host_does_not_look_foreign():
    if in_write_sandbox():
        pytest.skip("inside the claude write sandbox /proc is foreign by design")
    assert not proc_is_foreign()


# axis: census membership - each of the five /proc-reading tests carries the proc_containment mark; catches a census test left unguarded.
def test_every_census_test_carries_the_proc_containment_mark():
    assert len(_CENSUS) == 5
    for func in _CENSUS:
        names = [mark.name for mark in func.pytestmark]
        assert MARKER in names, "%s lacks @pytest.mark.%s" % (func.__name__, MARKER)


_FORCED_SKIP = """\
import pytest


@pytest.fixture(autouse=True)
def _proc_containment_guard():
    # Shadow the plugin's guard so only the outcome hook is under test, even in a foreign /proc.
    pass


@pytest.mark.proc_containment
def test_forced():
    pytest.skip("forced")
"""


def _run_forced_skip(tmp_path, environ):
    test_file = tmp_path / "test_forced_skip.py"
    test_file.write_text(_FORCED_SKIP)
    env = {k: v for k, v in os.environ.items() if k != SANDBOX_MARKER_ENV}
    env.update(environ)
    env["PYTHONPATH"] = _TESTS_DIR
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "proc_namespace", "-p", "no:cacheprovider", "-q",
         "-rA", "-c", os.devnull, "--rootdir", str(tmp_path), str(test_file)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, check=False)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the guard is Linux-only")
# axis: pytest outcome hook (this test and the next) - a skip of a marked test fails outside the sandbox and stays skipped inside it; catches a skip hiding an unobserved assertion, or a failure inside the sandbox.
def test_outcome_guard_turns_a_skip_outside_the_sandbox_into_a_failure(tmp_path):
    done = _run_forced_skip(tmp_path, {})
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert "skipped outside the claude write sandbox" in output, output
    assert "forced" in output, output


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the guard is Linux-only")
def test_outcome_guard_leaves_a_skip_inside_the_sandbox_skipped(tmp_path):
    done = _run_forced_skip(tmp_path, {SANDBOX_MARKER_ENV: "1"})
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "1 skipped" in output, output
