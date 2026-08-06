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
# Round-2 audit (WO-6) found four real gaps in the first version of this section, fixed below:
# an untested `start_new_session` assumption (Task 1), an ordering check that ignored `poll` as a
# reaping event (Task 2), an AST route check with both false-positive and false-negative failure
# modes — replaced with a runtime spy (Task 3) — and a fake that leaked a blocked reader thread
# and cost ~2s per run for no reason (Task 4).


def _bounded_run_observer_layout(private_tmp):
    """A real observer file satisfying `_validate_observer`'s filesystem checks.

    Content is a real, trivially-succeeding one-line observer (`#!/bin/sh` echoing a distinctive
    token and exiting 0) — it actually runs in the runtime-spy route test below, and stays inert
    plumbing (never executed) in the faked-`Popen` timeout test, where content is irrelevant.
    `_validate_observer` stats the file for real either way (regular file, owned by us, not
    group/other writable, outside every reach root), so it has to actually exist on disk.
    """
    reach_root = os.path.join(private_tmp, "reach")
    run_cwd = os.path.join(private_tmp, "cwd")
    bin_dir = os.path.join(private_tmp, "bin")
    os.makedirs(reach_root)
    os.makedirs(run_cwd)
    os.makedirs(bin_dir)
    script = os.path.join(bin_dir, "observer.sh")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\necho distinctive-observer-identity-token\n")
    os.chmod(script, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return reach_root, run_cwd, script


def test_observe_datastore_identity_routes_through_the_shared_runner(private_tmp, monkeypatch):
    # axis: proves EXECUTED routing — a runtime spy wrapped around the real
    # `pilot_bounded_run.run_bounded` and confirmed to have FIRED — rather than proving the source
    # text merely contains a matching call. An `ast.walk` (the version this replaces, #866 WO-6
    # audit) accepts a call that sits in dead code (an unreachable `if False` branch, an uncalled
    # nested function) and rejects an equally-real route through an import alias, an assigned
    # callable, or a wrapper helper — both a false positive and a false negative a runtime spy
    # does not have, because it observes what actually ran. This test proves ROUTING only;
    # process-group CONTAINMENT itself is proved by the sibling seam test below and by
    # `pilot_mint`'s grandchild test, not here.
    #
    # BINDING (#866 WO-7 Task 1): "the spy fired" and "the caller returned the right identity"
    # are proved independently unless something ties the second to the first. Without this, a
    # caller could call `run_bounded` with the right command, discard its result, and obtain the
    # identity through a separate, UNCONTAINED subprocess — `spy_calls` would still be populated
    # and the same script token would still satisfy an identity check, so that regression would
    # stay green. The spy here substitutes a distinctive sentinel into the SPIED call's own
    # return value (not the real script's actual output) and the test asserts the caller's
    # returned identity IS that sentinel — the only way to pass is to have actually consumed the
    # spied call's result.
    #
    # LIMITATION, accepted and documented rather than fixed (#866 WO-7 Task 3, reviewer-confirmed
    # aliasing false-negative): this spy binds to `pilot_bounded_run.run_bounded` as a module
    # attribute. If `pilot_boundary` is ever refactored to call through a cached or aliased
    # reference obtained before this monkeypatch runs (e.g. `from pilot_bounded_run import
    # run_bounded as bounded`), the live route would still execute correctly but `spy_calls` would
    # stay empty and this test would go RED even though routing is fine. That is a deliberate
    # trade, not an oversight: the failure direction is a false RED — a spurious, immediately
    # visible failure a maintainer fixes by updating the spy's patch target — never a false GREEN
    # over an actually-broken route, which is the direction that would let a containment
    # regression ship silently. Chasing it away would mean reinstating the AST check this test
    # replaced (rejected above for its own false-positive/false-negative pair) or patching every
    # possible alias site, and neither buys more than it costs.
    reach_root, run_cwd, script = _bounded_run_observer_layout(private_tmp)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}

    sentinel = "wo7-spy-sentinel-b6b6d2f4"
    spy_calls = []
    real_run_bounded = pbr.run_bounded

    def _spy_run_bounded(*args, **kwargs):
        spy_calls.append((args, kwargs))
        real_result = real_run_bounded(*args, **kwargs)
        # Substitute the sentinel into THIS call's own result — the real script's actual stdout
        # ("distinctive-observer-identity-token") is deliberately discarded here so that only the
        # spied call's substituted value can satisfy the identity assertion below.
        return dict(real_result, stdout=(sentinel + "\n").encode("utf-8"))

    monkeypatch.setattr(pbr, "run_bounded", _spy_run_bounded)

    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        timeout_seconds=5,
    )

    assert spy_calls, (
        "observe_datastore_identity never called pilot_bounded_run.run_bounded — its "
        "process-group containment is inherited from the shared runner, so this caller must keep "
        "EXECUTING a call through it rather than spawning its own subprocess (#866 round-1 r1-3)"
    )
    called_args, _called_kwargs = spy_calls[0]
    assert called_args[0] == observer["command"], (
        "run_bounded was called, but not with the observer's own command: got %r, expected %r"
        % (called_args[0], observer["command"])
    )
    assert result["identity"] == sentinel, (
        "observe_datastore_identity's returned identity did not come from the SPIED call's own "
        "result — got %r, expected the sentinel %r substituted into that call's return value; "
        "this is exactly the escape where run_bounded is called but its result is discarded in "
        "favor of an identity obtained some other way (#866 WO-7 Task 1)"
        % (result["identity"], sentinel)
    )


class _BlockedFakeStdout:
    """A fake `Popen(...).stdout` whose `read` blocks on an Event, released only by a simulated
    SIGKILL to the group — modelling what really happens (killing the group closes the inherited
    pipe) rather than blocking forever and leaking a daemon thread for the rest of the process.

    This is what makes the run take the TIMEOUT branch without any real subprocess and without
    racing real wall-clock delay: the reader thread is still alive when the first, short
    `reader.join(timeout=timeout_seconds)` returns — the SIGKILL that unblocks it has not
    happened yet at that point, deterministically, every time.
    """

    def __init__(self, events):
        self._released = threading.Event()
        self._events = events

    def read(self, _max_bytes):
        self._released.wait()
        return b""

    def release(self):
        self._released.set()

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
    # ORDER of `Popen`/`killpg`/`wait`/`poll` calls, never on wall-clock, so it cannot be flaky the
    # way the deleted process-based test was.
    #
    # Two things this asserts that a naive fake would let slip through (#866 WO-6 audit, both
    # confirmed against the code):
    # 1. `start_new_session=True` on the `Popen` call. `killpg(proc.pid, ...)` only signals the
    #    observer's whole process group BECAUSE `proc.pid` is deterministically also the pgid —
    #    true only when the child started its own session/group. A fake that discarded this
    #    argument (as the first version of this test did) would stay green even if the runner
    #    stopped starting a new session, or made it caller-selectable and the boundary caller
    #    chose `False` — exactly the failure the deleted real-process test's surviving grandchild
    #    would have caught.
    # 2. Both `proc.wait(...)` AND `proc.poll()` count as reaping events for the ordering check,
    #    not `wait` alone — `Popen.poll()` can reap a terminated leader in real life, so a `poll`
    #    call sitting between the two `killpg` calls would release the pgid early while a
    #    wait-only check stayed green.
    #
    # `timeout_seconds=0.05` is sound here in a way it was NOT in the deleted test: that test
    # needed a REAL grandchild process to finish STARTING before the timeout fired, so a slow or
    # loaded machine (interpreter cold-start, measured up to ~1.9s in CI) could lose the race and
    # fail at setup rather than at the assertion (#866, CI run 31002921349). Here nothing has to
    # happen before the timeout: the fake reader is blocked by construction, so the timeout firing
    # IS the scenario, deterministically, on the first and every subsequent call. There is no race
    # left to lose. The fake's blocking `Event` is released by the fake `SIGKILL` (Task 4, #866
    # WO-6 audit) — modelling the real pipe closing when the group dies — so neither of
    # `run_bounded`'s two hardcoded 1-second `reader.join` calls actually waits its full second.
    reach_root, run_cwd, script = _bounded_run_observer_layout(private_tmp)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}

    events = []
    sleep_calls = []
    popen_calls = []
    created_procs = []
    fake_pid = 4242

    def _fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        proc = _FakeTimeoutProc(fake_pid, events)
        created_procs.append(proc)
        return proc

    def _fake_killpg(pgid, sig):
        events.append(("killpg", pgid, sig))
        if sig == signal.SIGKILL and created_procs:
            # Models reality: killing the whole group closes the pipe the reader is blocked on.
            created_procs[-1].stdout.release()

    def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    # Task 2 (#866 WO-8, flakiness introduced by WO-7's own fix): `pbr.os` IS the shared stdlib
    # `os` module, so patching `waitpid`/`wait`/`waitid`/`wait3`/`wait4` on it is PROCESS-GLOBAL,
    # not scoped to this test. Any unrelated thread that legitimately reaps some other child
    # while this test runs would append a foreign event — recorded with neither pid nor result,
    # so even an unrelated `waitpid(..., WNOHANG)` returning `(0, 0)` could land inside the
    # ordering window and fail the assertion spuriously. Scope the RECORDING (never the
    # delegation, which always runs) to the thread that is actually driving `run_bounded`/
    # `_terminate` — this test's own thread, since both execute synchronously on whichever thread
    # calls `observe_datastore_identity`. The runner's own reader thread never reaps, so nothing
    # we care about is filtered out by this.
    test_thread_ident = threading.get_ident()

    def _delegating_reap_recorder(event_name, original_fn):
        """Wrap `original_fn` to log a reap event (on the test's own thread only) and delegate."""

        def _recorder(*args, **kwargs):
            if threading.get_ident() == test_thread_ident:
                events.append((event_name,))
            return original_fn(*args, **kwargs)

        return _recorder

    monkeypatch.setattr(pbr.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(pbr.os, "killpg", _fake_killpg)
    monkeypatch.setattr(pbr.time, "sleep", _fake_sleep)
    # `waitpid`/`wait` exist on every platform pilot_bounded_run runs on; `waitid`/`wait3`/
    # `wait4` do not (macOS, for one, has no `os.waitid`) — guard with hasattr so this never
    # breaks on a platform missing one of them.
    monkeypatch.setattr(pbr.os, "waitpid", _delegating_reap_recorder("waitpid", pbr.os.waitpid))
    monkeypatch.setattr(pbr.os, "wait", _delegating_reap_recorder("os_wait", pbr.os.wait))
    for _reap_name in ("waitid", "wait3", "wait4"):
        if hasattr(pbr.os, _reap_name):
            monkeypatch.setattr(
                pbr.os,
                _reap_name,
                _delegating_reap_recorder(_reap_name, getattr(pbr.os, _reap_name)),
            )

    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            timeout_seconds=0.05,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED

    # Task 1: the scheme is only sound because the child started its own session, making its pid
    # deterministically also its pgid — assert that, not just that killpg targeted that pid.
    assert popen_calls, "Popen was never called"
    _popen_args, popen_kwargs = popen_calls[0]
    assert popen_kwargs.get("start_new_session") is True, (
        "run_bounded did not start the child in its own session (start_new_session=%r) — "
        "killpg(proc.pid, ...) only signals the observer's WHOLE group because the child is "
        "deterministically its own session/group leader; without that, killpg would not reach "
        "a runaway grandchild (#866 WO-6 audit, Task 1)"
        % (popen_kwargs.get("start_new_session"),)
    )

    killpg_events = [(e[1], e[2]) for e in events if e[0] == "killpg"]
    assert killpg_events == [(fake_pid, signal.SIGTERM), (fake_pid, signal.SIGKILL)], (
        "expected the WHOLE GROUP signalled (pgid == the child's pid, %d) with both signals, in "
        "that order; got %r" % (fake_pid, killpg_events)
    )

    # Task 2: one shared, ordered event list across Popen/killpg/wait/poll/waitpid/os_wait/waitid/
    # wait3/wait4 — not several separate lists to correlate afterwards — so the reap-after-signals
    # check is a single position comparison. `proc.wait`, `proc.poll`, AND every direct OS-level
    # reap call (`os.waitpid`/`os.wait`/`waitid`/`wait3`/`wait4`, whichever exist on this
    # platform) all count as reaping events: any of them can release the leader's pid in real
    # life, so any of them sitting between the two `killpg` calls is the same defect (#866 WO-7
    # Task 2, WO-8 Task 1 added bare `os.wait`).
    _REAP_EVENT_NAMES = ("wait", "poll", "waitpid", "os_wait", "waitid", "wait3", "wait4")
    reap_indices = [i for i, e in enumerate(events) if e[0] in _REAP_EVENT_NAMES]
    assert reap_indices, (
        "no reaping event (proc.wait, proc.poll, os.waitpid, os.wait, or another direct "
        "os.wait*/os.waitid call) was recorded at all — event log: %r" % (events,)
    )
    killpg_indices = [i for i, e in enumerate(events) if e[0] == "killpg"]
    assert max(killpg_indices) < min(reap_indices), (
        "a reaping event (%s) happened before both signals finished sending — event order was %r"
        % (events[min(reap_indices)][0], events)
    )

    assert sleep_calls, "the SIGTERM grace sleep never ran"


# --- retain_output=False contract (#830 WO-4) ---------------------------------


def _write_executable(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o700)


def _bounded_layout(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    bin_dir = os.path.join(private_tmp, "bin")
    os.makedirs(run_cwd)
    os.makedirs(bin_dir)
    return run_cwd, bin_dir


def test_retain_output_false_under_cap(private_tmp):
    run_cwd, bin_dir = _bounded_layout(private_tmp)
    script = os.path.join(bin_dir, "echo.sh")
    _write_executable(script, "#!/bin/sh\nprintf hello\n")
    result = pbr.run_bounded(
        [script],
        run_cwd=run_cwd,
        env={},
        timeout_seconds=5,
        max_output_bytes=100,
        retain_output=False,
    )
    assert result["outcome"] == pbr.OUTCOME_COMPLETED
    assert result["exitCode"] == 0
    assert result["stdout"] == b""
    assert result["stdoutBytes"] == 5
    assert result["stdoutTruncated"] is False


def test_retain_output_false_over_cap_is_completed_not_oversize(private_tmp):
    # axis: truncation is reportable, not refusable — the contract-difference test (#830 WO-4).
    run_cwd, bin_dir = _bounded_layout(private_tmp)
    script = os.path.join(bin_dir, "huge.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "i=0\n"
        "while [ $i -lt 500 ]; do printf x; i=$((i+1)); done\n",
    )
    result = pbr.run_bounded(
        [script],
        run_cwd=run_cwd,
        env={},
        timeout_seconds=10,
        max_output_bytes=100,
        retain_output=False,
    )
    assert result["outcome"] == pbr.OUTCOME_COMPLETED
    assert result["outcome"] != pbr.OUTCOME_OVERSIZE
    assert result["exitCode"] == 0
    assert result["stdout"] == b""
    assert result["stdoutBytes"] == 100
    assert result["stdoutTruncated"] is True


def test_retain_output_false_nonzero_exit_is_completed(private_tmp):
    run_cwd, bin_dir = _bounded_layout(private_tmp)
    script = os.path.join(bin_dir, "exit7.sh")
    _write_executable(script, "#!/bin/sh\nexit 7\n")
    result = pbr.run_bounded(
        [script],
        run_cwd=run_cwd,
        env={},
        timeout_seconds=5,
        max_output_bytes=4096,
        retain_output=False,
    )
    assert result["outcome"] == pbr.OUTCOME_COMPLETED
    assert result["exitCode"] == 7


def test_retain_output_true_over_cap_still_oversize(private_tmp):
    run_cwd, bin_dir = _bounded_layout(private_tmp)
    script = os.path.join(bin_dir, "huge.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "i=0\n"
        "while [ $i -lt 500 ]; do printf x; i=$((i+1)); done\n",
    )
    result = pbr.run_bounded(
        [script],
        run_cwd=run_cwd,
        env={},
        timeout_seconds=10,
        max_output_bytes=100,
        retain_output=True,
    )
    assert result["outcome"] == pbr.OUTCOME_OVERSIZE


def test_retain_output_true_completed_carries_byte_fields(private_tmp):
    run_cwd, bin_dir = _bounded_layout(private_tmp)
    script = os.path.join(bin_dir, "echo.sh")
    _write_executable(script, "#!/bin/sh\nprintf hi\n")
    result = pbr.run_bounded(
        [script],
        run_cwd=run_cwd,
        env={},
        timeout_seconds=5,
        max_output_bytes=100,
        retain_output=True,
    )
    assert result["outcome"] == pbr.OUTCOME_COMPLETED
    assert result["stdoutBytes"] == 2
    assert result["stdoutTruncated"] is False


def test_retain_output_false_timeout_kills_grandchild(private_tmp):
    # axis: process-group containment — a runaway grandchild must not survive timeout (#830 WO-4).
    run_cwd, bin_dir = _bounded_layout(private_tmp)
    pid_file = os.path.join(private_tmp, "grandchild.pid")
    script = os.path.join(bin_dir, "spawn.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "/bin/sleep 60 &\n"
        "echo $! > '%s'\n"
        "/bin/sleep 5\n" % pid_file,
    )
    result = pbr.run_bounded(
        [script],
        run_cwd=run_cwd,
        env={},
        timeout_seconds=1,
        max_output_bytes=4096,
        retain_output=False,
    )
    assert result["outcome"] == pbr.OUTCOME_TIMEOUT
    with open(pid_file, encoding="utf-8") as handle:
        pid = int(handle.read().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)

