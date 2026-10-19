"""Detect the claude write sandbox's foreign /proc so pid-keyed containment tests adapt.

Inside the sandbox /proc is the procfs of an ancestor PID namespace: /proc/self names a pid that is not
os.getpid(), so a test that reads or signals other processes by pid through /proc observes the wrong
processes. A test marked `proc_containment` therefore skips there — and only there. The single predicate
`skip_allowed()` (the sandbox marker AND a foreign /proc) is the one home of that condition: the fixture
and the outcome hook both call it. A foreign /proc without the sandbox marker fails loudly, and a marked
test that skips on Linux when `skip_allowed()` is false is turned into a failure, so the skip can never
hide a regression on a normal host.

This module is also a pytest plugin (`-p proc_namespace`); the tests conftest imports its fixture and
outcome hook. The marker is registered in the repo-root pytest.ini.
"""
import os
import sys

import pytest

SANDBOX_MARKER_ENV = "SANDBOX_RUNTIME"
MARKER = "proc_containment"


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


@pytest.fixture(autouse=True)
def _proc_containment_guard(request):
    if request.node.get_closest_marker(MARKER) is not None:
        require_own_proc_namespace()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if item.get_closest_marker(MARKER) is None:
        return
    report = outcome.get_result()
    if not report.skipped or not sys.platform.startswith("linux") or skip_allowed():
        return
    original = report.longrepr[2] if isinstance(report.longrepr, tuple) else report.longrepr
    report.outcome = "failed"
    report.longrepr = ("a %s test was skipped outside the claude write sandbox, which is not allowed on "
                       "Linux: a skip needs both %s=1 and a foreign /proc; original skip reason: %s"
                       % (MARKER, SANDBOX_MARKER_ENV, original))
