"""Tests for pilot_bounded_run.py — structural detector for #866 audit r2-2 (pgid-reuse window),
and (round-1 r1-3) the boundary caller's process-group containment proof, rebuilt deterministic."""
import ast
import inspect
import os
import signal
import stat
import sys
import threading

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_bounded_run as pbr  # noqa: E402
import pilot_boundary as pb  # noqa: E402


def _terminate_function_ast():
    """Parse `_terminate`'s own source (not the whole module) into its `ast.FunctionDef`."""
    source = inspect.getsource(pbr._terminate)
    tree = ast.parse(source)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef) and func.name == "_terminate", (
        "inspect.getsource(pbr._terminate) did not parse to a single FunctionDef named "
        "_terminate — got %r" % (ast.dump(tree),)
    )
    return func


def _is_os_killpg_with_signal(node, signal_name):
    """True for an `os.killpg(<pgid>, signal.<signal_name>)` call node, structurally."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "killpg":
        return False
    if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "os"):
        return False
    if len(node.args) < 2:
        return False
    sig_arg = node.args[1]
    return (
        isinstance(sig_arg, ast.Attribute)
        and isinstance(sig_arg.value, ast.Name)
        and sig_arg.value.id == "signal"
        and sig_arg.attr == signal_name
    )


def _is_proc_reap_call(node):
    """True for a `proc.wait(...)` or `proc.poll()` call node — either reaps the group leader."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in ("wait", "poll"):
        return False
    return isinstance(node.func.value, ast.Name) and node.func.value.id == "proc"


def test_terminate_signals_the_whole_group_before_any_reap():
    # axis: statement ORDER inside `_terminate` — both `os.killpg(..., SIGTERM)` and
    # `os.killpg(..., SIGKILL)` must precede the first `proc.wait(...)`/`proc.poll()` call,
    # wherever in the function body it sits (the calls live inside nested `try` blocks, so this
    # walks the whole subtree via `ast.walk` and orders by `node.lineno` rather than assuming a
    # flat body). #866 audit r2-2: reaping the process-group leader releases its pid, and pgid IS
    # that pid, so a reap between the two signals lets the kernel hand the pid to an unrelated
    # same-UID process group that the second `killpg` would then hit. That consequence is a race
    # — the kernel would have to reuse the exact pid inside a narrow window — which no behavioural
    # test can force to reproduce; a re-run of this batch's own WO-2 bite-proof confirmed exactly
    # that (both containment tests stayed green with the pre-fix order restored). The ORDER of
    # operations is what makes the fix correct, and unlike its consequence, the order is
    # mechanically checkable by inspecting the source — so that is what this test checks.
    func = _terminate_function_ast()
    calls = [node for node in ast.walk(func) if isinstance(node, ast.Call)]

    sigterm_calls = [c for c in calls if _is_os_killpg_with_signal(c, "SIGTERM")]
    sigkill_calls = [c for c in calls if _is_os_killpg_with_signal(c, "SIGKILL")]
    reap_calls = [c for c in calls if _is_proc_reap_call(c)]

    # Non-vacuity: both killpg calls must actually be present, or the ordering check below would
    # trivially pass over a `_terminate` that stopped sending one of the signals altogether.
    assert sigterm_calls, "_terminate no longer calls os.killpg(..., signal.SIGTERM) at all"
    assert sigkill_calls, "_terminate no longer calls os.killpg(..., signal.SIGKILL) at all"
    # Non-vacuity: a reap call must exist too, or "both killpg calls precede the first reap" would
    # be vacuously true for a `_terminate` that never reaps the leader at all — its own defect.
    assert reap_calls, (
        "_terminate has no proc.wait(...)/proc.poll() reaping call at all — the ordering "
        "assertion below would be vacuously satisfied by a function that never reaps"
    )

    first_reap_lineno = min(c.lineno for c in reap_calls)
    last_sigterm_lineno = max(c.lineno for c in sigterm_calls)
    last_sigkill_lineno = max(c.lineno for c in sigkill_calls)

    assert last_sigterm_lineno < first_reap_lineno, (
        "os.killpg(..., signal.SIGTERM) at relative line %d does not precede the first reap "
        "at relative line %d — a reap between the signals can release the leader's pid before "
        "the group is fully signalled (#866 audit r2-2)"
        % (last_sigterm_lineno, first_reap_lineno)
    )
    assert last_sigkill_lineno < first_reap_lineno, (
        "os.killpg(..., signal.SIGKILL) at relative line %d does not precede the first reap "
        "at relative line %d — a reap between the signals can release the leader's pid before "
        "the group is fully signalled (#866 audit r2-2)"
        % (last_sigkill_lineno, first_reap_lineno)
    )


# --- round-1 r1-3: the boundary caller's process-group containment, proved deterministically ---
# (#866, replacing the deleted `test_observe_datastore_identity_timeout_reaps_process_group`,
# which raced its own timeout against real interpreter cold-start latency in CI and was parked.)


def _observe_datastore_identity_function_ast():
    """Parse `pilot_boundary.observe_datastore_identity`'s own source into its `ast.FunctionDef`."""
    source = inspect.getsource(pb.observe_datastore_identity)
    tree = ast.parse(source)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef) and func.name == "observe_datastore_identity", (
        "inspect.getsource(pb.observe_datastore_identity) did not parse to a single FunctionDef "
        "named observe_datastore_identity — got %r" % (ast.dump(tree),)
    )
    return func


def test_observe_datastore_identity_routes_through_the_shared_runner():
    # axis: the boundary caller's process-group containment is INHERITED from
    # `pilot_bounded_run.run_bounded`, not reimplemented locally — so what must never silently
    # change is that `observe_datastore_identity` still ROUTES through the shared runner rather
    # than spawning its own subprocess. Checked by AST inspection of the function's own source
    # (`inspect.getsource` + `ast.parse`, not substring matching), so a rewrite that keeps the
    # string "run_bounded" in a comment but stops calling it would still redden here.
    func = _observe_datastore_identity_function_ast()
    calls = [node for node in ast.walk(func) if isinstance(node, ast.Call)]
    # Non-vacuity: a parse that found zero `ast.Call` nodes at all would make the routing check
    # below vacuously fail to find anything to disprove, for the wrong reason.
    assert calls, "observe_datastore_identity parsed to zero ast.Call nodes at all"

    routes_through_runner = any(
        isinstance(c.func, ast.Attribute)
        and c.func.attr == "run_bounded"
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id == "pilot_bounded_run"
        for c in calls
    )
    assert routes_through_runner, (
        "observe_datastore_identity no longer calls pilot_bounded_run.run_bounded — its "
        "process-group containment is inherited from the shared runner, so this caller must keep "
        "routing through it rather than spawning its own subprocess (#866 round-1 r1-3)"
    )


def _bounded_run_observer_layout(private_tmp):
    """A real observer file satisfying `_validate_observer`'s filesystem checks.

    Its content never runs — `subprocess.Popen` is faked in the tests below — but
    `pilot_boundary._validate_observer` still stats it for real (regular file, owned by us,
    not group/other writable, outside every reach root), so it has to actually exist on disk.
    """
    reach_root = os.path.join(private_tmp, "reach")
    run_cwd = os.path.join(private_tmp, "cwd")
    bin_dir = os.path.join(private_tmp, "bin")
    os.makedirs(reach_root)
    os.makedirs(run_cwd)
    os.makedirs(bin_dir)
    script = os.path.join(bin_dir, "observer.sh")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\necho unused\n")
    os.chmod(script, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return reach_root, run_cwd, script


class _BlockedFakeStdout:
    """A fake `Popen(...).stdout` whose `read` blocks forever on an Event that is never set.

    This is what makes the run take the TIMEOUT branch without any real subprocess or real
    wall-clock delay: the reader thread is still alive when `reader.join(timeout=...)` returns,
    every time, deterministically — there is no cold-start, no scheduler jitter, nothing to race.
    """

    def __init__(self, events):
        self._never = threading.Event()
        self._events = events

    def read(self, _max_bytes):
        self._never.wait()
        return b""  # unreachable — the event above is never set

    def close(self):
        self._events.append(("stdout_close",))


class _FakeTimeoutProc:
    """A fake `Popen` return value with `poll`/`wait` recorded into one shared, ordered list."""

    def __init__(self, pid, events):
        self.pid = pid
        self.returncode = None
        self._events = events
        self.stdout = _BlockedFakeStdout(events)

    def poll(self):
        self._events.append(("poll",))
        return self.returncode

    def wait(self, timeout=None):
        self._events.append(("wait",))
        # Simulate the leader having been reaped: from here on `poll()` reports "not running",
        # so `run_bounded`'s own `finally` sweep does not re-enter `_terminate` a second time.
        self.returncode = -9
        return self.returncode


def test_observe_datastore_identity_timeout_signals_whole_group_before_reaping(
    private_tmp, monkeypatch
):
    # axis: end-to-end call-SEQUENCE proof of round-1 r1-3 for the boundary caller, driving the
    # REAL `pilot_boundary.observe_datastore_identity` with the process layer faked underneath —
    # the #876 seam-injection pattern (see test_pilot_appctl.py's
    # test_stop_reaped_leader_still_signals_surviving_group_members and siblings). Asserted on the
    # ORDER of `killpg`/`wait` calls, never on wall-clock, so it cannot be flaky the way the
    # deleted process-based test was.
    #
    # `timeout_seconds=0.05` is sound here in a way it was NOT in the deleted test: that test
    # needed a REAL grandchild process to finish STARTING before the timeout fired, so a slow or
    # loaded machine (interpreter cold-start, measured up to ~1.9s in CI) could lose the race and
    # fail at setup rather than at the assertion (#866, CI run 31002921349). Here nothing has to
    # happen before the timeout: the fake reader is blocked by construction, so the timeout firing
    # IS the scenario, deterministically, on the first and every subsequent call. There is no race
    # left to lose.
    reach_root, run_cwd, script = _bounded_run_observer_layout(private_tmp)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}

    events = []
    sleep_calls = []
    fake_pid = 4242

    def _fake_popen(*_args, **_kwargs):
        return _FakeTimeoutProc(fake_pid, events)

    def _fake_killpg(pgid, sig):
        events.append(("killpg", pgid, sig))

    def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(pbr.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(pbr.os, "killpg", _fake_killpg)
    monkeypatch.setattr(pbr.time, "sleep", _fake_sleep)

    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            timeout_seconds=0.05,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED

    killpg_events = [(e[1], e[2]) for e in events if e[0] == "killpg"]
    assert killpg_events == [(fake_pid, signal.SIGTERM), (fake_pid, signal.SIGKILL)], (
        "expected the WHOLE GROUP signalled (pgid == the child's pid, %d) with both signals, in "
        "that order; got %r" % (fake_pid, killpg_events)
    )

    # One shared, ordered event list across killpg/wait/poll — not three separate lists to
    # correlate afterwards — so the reap-after-signals check is a single position comparison.
    wait_indices = [i for i, e in enumerate(events) if e[0] == "wait"]
    assert wait_indices, "no reap (proc.wait) was recorded at all — event log: %r" % (events,)
    killpg_indices = [i for i, e in enumerate(events) if e[0] == "killpg"]
    assert max(killpg_indices) < min(wait_indices), (
        "a reap happened before both signals finished sending — event order was %r" % (events,)
    )

    assert sleep_calls, "the SIGTERM grace sleep never ran"
