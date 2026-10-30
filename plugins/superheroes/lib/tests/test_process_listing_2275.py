import os
import subprocess
import sys

import pytest

import test_engine_dispatch_write
from proc_namespace import (PROCESS_LISTING_MARKER, SANDBOX_MARKER_ENV, process_group_listing_works,
                            process_listing_skip_allowed, require_process_listing)

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_TESTS_DIR))))
_FORCE_PROBE = "PROCESS_LISTING_FORCE_PROBE"

_ABANDON_LIVE_ID = ("plugins/superheroes/lib/tests/test_engine_dispatch.py::"
                    "test_terminal_transition_invariant_no_cleanup_before_durable_record[abandon_live_engine]")
_CENSUS_IDS = {
    _ABANDON_LIVE_ID,
    "plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_process_group_alive_zombie_only_is_dead",
    "plugins/superheroes/lib/tests/test_engine_dispatch_write.py::"
    "test_dispatch_abandon_alive_engine_releases_lease",
}


class _Done:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout


def _runner(returncode=0, stdout="S\n", raises=None):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if raises is not None:
            raise raises
        return _Done(returncode, stdout)
    run.calls = calls
    return run


# axis: sandbox-only skip predicate (truth table) - a skip is allowed only with SANDBOX_RUNTIME exactly "1" AND a failing probe; catches the marker alone, a failing probe alone, "0" or an absent marker being taken for the sandbox (E3), or an inverted probe.
@pytest.mark.parametrize("environ, works, expected", [
    ({SANDBOX_MARKER_ENV: "1"}, True, False),
    ({SANDBOX_MARKER_ENV: "1"}, False, True),
    ({}, True, False),
    ({}, False, False),
    ({SANDBOX_MARKER_ENV: "0"}, True, False),
    ({SANDBOX_MARKER_ENV: "0"}, False, False),
])
def test_process_listing_skip_allowed_truth_table(environ, works, expected):
    assert process_listing_skip_allowed(environ, lambda: works) is expected


# axis: skip-vs-fail refusal, working probe - a working probe neither skips nor fails, with or without the marker; catches the guard firing on a normal host.
@pytest.mark.parametrize("environ", [{}, {SANDBOX_MARKER_ENV: "1"}])
def test_require_process_listing_returns_none_when_the_probe_works(environ):
    assert require_process_listing(environ, lambda: True) is None


# axis: skip-vs-fail refusal, inside the sandbox - a failing probe with the marker skips with a message naming the sandbox and the ps probe; catches a hard failure or an unexplained skip.
def test_failing_probe_in_the_sandbox_skips_naming_the_sandbox():
    with pytest.raises(pytest.skip.Exception) as raised:
        require_process_listing({SANDBOX_MARKER_ENV: "1"}, lambda: False)
    message = str(raised.value)
    assert message.startswith("claude write sandbox:")
    assert "ps -g" in message


# axis: skip-vs-fail refusal, outside the sandbox (E5) - a failing probe with no marker fails and never skips; catches a skip that would hide a real ps problem.
def test_failing_probe_outside_the_sandbox_fails_never_skips():
    with pytest.raises(pytest.fail.Exception) as raised:
        require_process_listing({}, lambda: False)
    assert "refuses to skip" in str(raised.value)


# axis: skip-vs-fail refusal, wrong marker value (E3) - SANDBOX_RUNTIME other than "1" is not the sandbox, so a failing probe fails; catches "0" being taken for the sandbox.
def test_failing_probe_with_a_non_one_marker_fails_never_skips():
    with pytest.raises(pytest.fail.Exception) as raised:
        require_process_listing({SANDBOX_MARKER_ENV: "0"}, lambda: False)
    assert "refuses to skip" in str(raised.value)


# axis: probe argv - the probe runs exactly the ps call _process_group_alive makes, with capture and a timeout; catches a drifted argv that would probe something else.
def test_probe_runs_exactly_the_ps_group_listing():
    run = _runner()
    assert process_group_listing_works(run) is True
    argv, kwargs = run.calls[0]
    assert argv == ["ps", "-g", str(os.getpgid(0)), "-o", "state="]
    assert kwargs == {"capture_output": True, "text": True, "timeout": 5}


# axis: probe verdict (this test and the next three) - only exit 0 with non-empty output is working (E1, E2); catches a non-zero exit, empty output, or a raised exception being read as working.
def test_probe_exit_zero_with_output_is_working():
    assert process_group_listing_works(_runner(0, "S\n")) is True


def test_probe_non_zero_exit_is_not_working():
    assert process_group_listing_works(_runner(1, "")) is False
    assert process_group_listing_works(_runner(1, "S\n")) is False


def test_probe_exit_zero_with_empty_output_is_not_working():
    assert process_group_listing_works(_runner(0, "")) is False


def test_probe_raising_is_not_working():
    assert process_group_listing_works(_runner(raises=OSError("no ps"))) is False


# axis: census (I3), direct marks - the two engine_dispatch_write tests carry the process_listing mark; catches a mark removed from either.
def test_the_two_write_tests_carry_the_process_listing_mark():
    for func in (test_engine_dispatch_write.test_process_group_alive_zombie_only_is_dead,
                 test_engine_dispatch_write.test_dispatch_abandon_alive_engine_releases_lease):
        names = [mark.name for mark in getattr(func, "pytestmark", [])]
        assert PROCESS_LISTING_MARKER in names, "%s lacks @pytest.mark.%s" % (
            func.__name__, PROCESS_LISTING_MARKER)


# axis: census (I3), collected set - selecting the process_listing mark over both engine_dispatch files yields exactly the three named node ids; catches a missing mark (including the abandon_live_engine param) or a mark on any other test.
def test_the_mark_selects_exactly_the_three_census_tests():
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", PROCESS_LISTING_MARKER,
         "-p", "no:cacheprovider",
         os.path.join(_TESTS_DIR, "test_engine_dispatch.py"),
         os.path.join(_TESTS_DIR, "test_engine_dispatch_write.py")],
        cwd=_REPO_ROOT, capture_output=True, text=True, check=False)
    output = done.stdout + done.stderr
    selected = {line for line in done.stdout.splitlines() if "::" in line}
    assert selected == _CENSUS_IDS, output


_CHILD = """\
import os

import pytest

import proc_namespace

_forced = os.environ.get("PROCESS_LISTING_FORCE_PROBE")
if _forced in ("1", "0"):
    # At import, so it is in place before the plugin's guard fixture runs; the child process is
    # discarded afterwards.
    proc_namespace.process_group_listing_works = lambda *a, **k: _forced == "1"
%(shadow)s

@pytest.mark.process_listing
def test_marked():
%(body)s
"""

_SHADOW = """

@pytest.fixture(autouse=True)
def _process_listing_guard():
    # Shadow the plugin's guard so only the outcome hook is under test.
    pass

"""


def _run_child(tmp_path, body, environ, shadow=True):
    test_file = tmp_path / "test_child_process_listing.py"
    test_file.write_text(_CHILD % {"shadow": _SHADOW if shadow else "", "body": body})
    env = {k: v for k, v in os.environ.items() if k != SANDBOX_MARKER_ENV}
    env.update(environ)
    env["PYTHONPATH"] = _TESTS_DIR
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "proc_namespace", "-p", "no:cacheprovider", "-q",
         "-rA", "-c", os.devnull, "--rootdir", str(tmp_path), str(test_file)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, check=False)


_SKIP = '    pytest.skip("forced")'
_NODE = "test_child_process_listing.py::test_marked"


# axis: pytest outcome hook (E4; the cases through test_a_marked_test_that_passes_outside_the_sandbox_passes) - a marked test's skip survives only with the sandbox marker AND a failing probe, on every platform; catches a skip hiding an unobserved assertion outside the sandbox.
def test_a_skip_with_no_marker_and_a_working_probe_is_a_failure(tmp_path):
    done = _run_child(tmp_path, _SKIP, {_FORCE_PROBE: "1"})
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert "FAILED " + _NODE in output, output
    assert "skipped while the claude write sandbox condition does not hold" in output, output
    assert "forced" in output, output


def test_a_skip_with_the_marker_and_a_failing_probe_stays_skipped(tmp_path):
    done = _run_child(tmp_path, _SKIP, {SANDBOX_MARKER_ENV: "1", _FORCE_PROBE: "0"})
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "SKIPPED" in output, output
    assert "1 skipped" in output, output


def test_a_skip_with_the_marker_and_a_working_probe_is_a_failure(tmp_path):
    done = _run_child(tmp_path, _SKIP, {SANDBOX_MARKER_ENV: "1", _FORCE_PROBE: "1"})
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert "FAILED " + _NODE in output, output


# axis: break-it (DoD) - the mark never hides a real failure outside the sandbox; catches the mark turning an assertion failure into a skip or a pass.
def test_a_marked_test_that_really_fails_outside_the_sandbox_fails(tmp_path):
    done = _run_child(tmp_path, "    assert False", {_FORCE_PROBE: "1"})
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert "FAILED " + _NODE in output, output
    assert "1 failed" in output, output


# axis: the mark does not stop the test running outside the sandbox - a marked test with a working probe runs and passes; catches the guard skipping or failing a healthy host.
def test_a_marked_test_that_passes_outside_the_sandbox_passes(tmp_path):
    done = _run_child(tmp_path, "    assert True", {_FORCE_PROBE: "1"})
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "PASSED " + _NODE in output, output


# axis: fixture fail-not-skip leg (E5, real guard fixture) - a failing probe with no marker fails with "refuses to skip"; catches the guard skipping outside the sandbox.
def test_the_real_guard_fails_a_failing_probe_outside_the_sandbox(tmp_path):
    done = _run_child(tmp_path, "    assert True", {_FORCE_PROBE: "0"}, shadow=False)
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    # pytest.fail in a fixture is reported as an ERROR at setup, never as a skip.
    assert "ERROR " + _NODE in output, output
    assert "SKIPPED" not in output, output
    assert "refuses to skip" in output, output


# axis: hermetic seat env (I1) - the autouse store-isolation fixture scrubs the ambient CLAUDE_PID; catches an inherited CLAUDE_PID reaching the launcher's instance-pin gate.
def test_ambient_claude_pid_is_scrubbed():
    assert "CLAUDE_PID" not in os.environ
