"""Detect the claude write sandbox's process-visibility limits so process-keyed tests adapt.

Two markers, each skipping inside the sandbox — and only there.

Inside the sandbox /proc is the procfs of an ancestor PID namespace: /proc/self names a pid that is not
os.getpid(), so a test that reads or signals other processes by pid through /proc observes the wrong
processes. A test marked `proc_containment` therefore skips there. The single predicate `skip_allowed()`
(the sandbox marker AND a foreign /proc) is the one home of that condition: the fixture and the outcome
hook both call it. A foreign /proc without the sandbox marker fails loudly, and a marked test that skips
on Linux when `skip_allowed()` is false is turned into a failure, so the skip can never hide a regression
on a normal host.

Inside the sandbox `ps -g <pgid> -o state=` also exits non-zero ("fatal library error, lookup self"), so a
test that lists a process group with ps cannot observe it. A test marked `process_listing` skips there. The
single predicate `process_listing_skip_allowed()` (the sandbox marker AND a failing ps probe) is the one
home of that condition: the fixture and the outcome hook both call it. A failing probe without the sandbox
marker fails loudly, and a marked test that skips on ANY platform when `process_listing_skip_allowed()` is
false is turned into a failure (the ps constraint also exists on macOS, so unlike `proc_containment` this
hook is not Linux-only).

This module is also a pytest plugin (`-p proc_namespace`); the tests conftest imports its fixtures and
outcome hook. The markers are registered in the repo-root pytest.ini.
"""
import os
import subprocess
import sys

import pytest

SANDBOX_MARKER_ENV = "SANDBOX_RUNTIME"
MARKER = "proc_containment"
PROCESS_LISTING_MARKER = "process_listing"


def _proc_self(readlink):
    """The pid string /proc/self links to, or None when there is no /proc or it is not a pid."""
    try:
        target = readlink("/proc/self")
    except OSError:
        return None
    return target if target.isdigit() else None


def proc_is_foreign(readlink=os.readlink, getpid=os.getpid):
    """True when /proc/self names a pid other than this process's own (another PID namespace's procfs).
    No /proc, or a /proc/self that is not a pid, is not this constraint: False."""
    target = _proc_self(readlink)
    return target is not None and target != str(getpid())


def in_write_sandbox(environ=None):
    return (os.environ if environ is None else environ).get(SANDBOX_MARKER_ENV) == "1"


def skip_allowed(readlink=os.readlink, getpid=os.getpid, environ=None):
    """True only when a proc_containment skip is legitimate: the sandbox marker is set AND /proc is foreign.
    The one home of the skip condition; the fixture and the outcome hook both call it."""
    return in_write_sandbox(environ) and proc_is_foreign(readlink, getpid)


def require_own_proc_namespace(readlink=os.readlink, getpid=os.getpid, environ=None):
    """Return when /proc is this process's own; skip in the claude write sandbox; fail otherwise."""
    if not proc_is_foreign(readlink, getpid):
        return
    seen = "/proc/self=%s, getpid()=%s" % (_proc_self(readlink), getpid())
    if skip_allowed(readlink, getpid, environ):
        pytest.skip("claude write sandbox: /proc belongs to another PID namespace (%s), so pid-keyed "
                    "containment cannot be observed here" % seen)
    pytest.fail("/proc belongs to another PID namespace (%s) outside the claude write sandbox (%s is "
                "not 1), so this containment test refuses to skip" % (seen, SANDBOX_MARKER_ENV),
                pytrace=False)


def process_group_listing_works(run=subprocess.run):
    """True when `ps -g <our pgid> -o state=` (the call engine_dispatch._process_group_alive makes) exits 0
    with output. Any exception, a non-zero exit, or empty output is not working: False."""
    try:
        done = run(["ps", "-g", str(os.getpgid(0)), "-o", "state="],
                   capture_output=True, text=True, timeout=5)
        return done.returncode == 0 and bool(done.stdout)
    except Exception:
        return False


def process_listing_skip_allowed(environ=None, probe=None):
    """True only when a process_listing skip is legitimate: the sandbox marker is set AND the ps probe fails.
    The one home of the skip condition; the fixture and the outcome hook both call it. The probe is looked
    up at call time so a monkeypatch of the module attribute reaches both."""
    if probe is None:
        probe = process_group_listing_works
    return in_write_sandbox(environ) and not probe()


def require_process_listing(environ=None, probe=None):
    """Return when the ps probe works; skip in the claude write sandbox; fail otherwise."""
    if probe is None:
        probe = process_group_listing_works
    if probe():
        return
    if process_listing_skip_allowed(environ, probe):
        pytest.skip("claude write sandbox: the `ps -g <pgid> -o state=` probe fails here, so a process "
                    "group cannot be listed and its liveness cannot be observed")
    pytest.fail("the `ps -g <pgid> -o state=` probe fails outside the claude write sandbox (%s is not 1), "
                "so this process-listing test refuses to skip" % SANDBOX_MARKER_ENV, pytrace=False)


@pytest.fixture(autouse=True)
def _proc_containment_guard(request):
    if request.node.get_closest_marker(MARKER) is not None:
        require_own_proc_namespace()


@pytest.fixture(autouse=True)
def _process_listing_guard(request):
    if request.node.get_closest_marker(PROCESS_LISTING_MARKER) is not None:
        require_process_listing()


def _fail_skip_outside_proc_containment(item, report):
    if item.get_closest_marker(MARKER) is None:
        return
    if not report.skipped or not sys.platform.startswith("linux") or skip_allowed():
        return
    original = report.longrepr[2] if isinstance(report.longrepr, tuple) else report.longrepr
    report.outcome = "failed"
    report.longrepr = ("a %s test was skipped outside the claude write sandbox, which is not allowed on "
                       "Linux: a skip needs both %s=1 and a foreign /proc; original skip reason: %s"
                       % (MARKER, SANDBOX_MARKER_ENV, original))


def _fail_skip_outside_process_listing(item, report):
    if item.get_closest_marker(PROCESS_LISTING_MARKER) is None:
        return
    if not report.skipped or process_listing_skip_allowed():
        return
    original = report.longrepr[2] if isinstance(report.longrepr, tuple) else report.longrepr
    report.outcome = "failed"
    report.longrepr = ("a %s test was skipped while the claude write sandbox condition does not hold, which "
                       "is not allowed: a skip needs both %s=1 and a failing ps probe; original skip "
                       "reason: %s" % (PROCESS_LISTING_MARKER, SANDBOX_MARKER_ENV, original))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    _fail_skip_outside_proc_containment(item, report)
    _fail_skip_outside_process_listing(item, report)
