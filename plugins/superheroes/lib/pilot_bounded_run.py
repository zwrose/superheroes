"""One bounded child-process runner for the pilot modules (#866).

`pilot_mint.run_gate_off_test` and `pilot_boundary._run_bounded_observer` grew the same shape
independently — spawn, read stdout on a reader thread with a byte cap, bound the read and the wait
by the same timeout, and reap the child on every exit path — and then **diverged** on process-group
handling. That divergence is the reason to extract rather than a reason not to: one copy signalled
the whole process group on timeout and the other only the direct child, so a runaway grandchild
outlived exactly one of them.

**This runner classifies, it never judges.** A run that finished is `completed`, whatever its exit
code, with stdout returned as raw bytes and undecoded. The two semantic differences the callers
actually have — `pilot_mint`'s neutral exit code (a nonzero gate-off run is a *reported result*,
distinct from a timeout or an oversize) versus `pilot_boundary`'s nonzero-is-failure — live in the
callers, where they belong. Anything this module decided for both would erase one of them.
"""
import os
import signal
import subprocess
import threading

# A run reaches exactly one of these. `completed` is the only one carrying an exit code.
OUTCOME_COMPLETED = "completed"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_OVERSIZE = "oversize"
OUTCOME_SPAWN_FAILED = "spawn-failed"


def run_bounded(
    command,
    *,
    run_cwd,
    env,
    timeout_seconds,
    max_output_bytes,
    new_process_group=False,
):
    """Run ``command`` bounded by wall-clock and stdout bytes; classify how it ended.

    Returns ``{"outcome": <OUTCOME_*>, "exitCode": int|None, "stdout": bytes}``. ``exitCode`` is
    non-None only for ``completed``; ``stdout`` is the raw bytes read, empty for every non-completed
    outcome. Never raises for a child's behaviour — a spawn failure, a read failure, and any other
    unexpected error all classify as ``spawn-failed``, because a caller that cannot see the child's
    output cannot distinguish them and must refuse either way.

    ``new_process_group=True`` starts the child in its own session and signals the whole group on
    every termination path, so a child that forks its own children does not leave them running.
    ``False`` signals the direct child only, which is what a caller wants when the command is a
    single short-lived observer.
    """
    # bite-axis: containment — stdout is read under a byte cap so oversized output cannot exhaust
    # memory, both the read and the wait are bounded by timeout_seconds, and the child (or its
    # whole group) is reaped on every exit path including the unexpected-exception path.
    try:
        proc = subprocess.Popen(
            command,
            cwd=run_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            env=env,
            start_new_session=bool(new_process_group),
        )
    except (OSError, ValueError):
        # ValueError, not just OSError: Popen raises it for an embedded NUL in an argv element
        # or in an environment name or value. Both callers validate their inputs as "non-empty
        # strings" and neither excludes a NUL, so those inputs reach here — and before this catch
        # the exception escaped the runner entirely, past `run_gate_off_test`'s refusal contract
        # and past `observe_datastore_identity`'s. A named refusal is the honest outcome, and it
        # is what makes this module's "never raises for a child's behaviour" claim true.
        return _result(OUTCOME_SPAWN_FAILED)

    pgid = None
    if new_process_group:
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, PermissionError):
            pgid = None

    reader = None
    try:
        stdout_holder = []
        read_error = []

        def _read_stdout():
            try:
                stdout_holder.append(proc.stdout.read(max_output_bytes + 1))
            except Exception as exc:  # noqa: BLE001 — the exception itself is never inspected
                read_error.append(exc)

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout_seconds)

        if reader.is_alive():
            _terminate(proc, pgid)
            reader.join(timeout=1)
            return _result(OUTCOME_TIMEOUT)

        if read_error:
            _terminate(proc, pgid)
            return _result(OUTCOME_SPAWN_FAILED)

        stdout_bytes = stdout_holder[0] if stdout_holder else b""
        if len(stdout_bytes) > max_output_bytes:
            _terminate(proc, pgid)
            return _result(OUTCOME_OVERSIZE)

        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate(proc, pgid)
            reader.join(timeout=1)
            return _result(OUTCOME_TIMEOUT)

        return {
            "outcome": OUTCOME_COMPLETED,
            "exitCode": proc.returncode,
            "stdout": stdout_bytes,
        }
    except Exception:  # noqa: BLE001 — every unexpected failure is an indeterminate run
        _terminate(proc, pgid)
        return _result(OUTCOME_SPAWN_FAILED)
    finally:
        if proc.poll() is None:
            _terminate(proc, pgid)
        if reader is not None and reader.is_alive():
            reader.join(timeout=1)
        # The two copies disagreed here and this is `pilot_mint`'s shape, adopted deliberately.
        # `pilot_boundary`'s copy closed the pipe unconditionally, which means closing a
        # BufferedReader another thread is blocked inside: `close()` waits on the buffer lock the
        # blocked `read()` holds, so the caller can hang in its own `finally`. Guarding on the
        # reader trades that hang for a bounded leak — if a descendant that inherited the pipe
        # outlives the direct child, this run leaves one daemon thread and one descriptor alive
        # until that descendant exits. That is reachable only with `new_process_group=False`
        # (with `True` the whole group is reaped), so today only the observer path can hit it,
        # where the command is a single short-lived process. Raised as an Important finding by
        # the #866 brief check; recorded here and handed on as a follow-up rather than fixed,
        # because the fix is a non-blocking/`select`-based reader — a redesign, not hygiene.
        if proc.stdout and (reader is None or not reader.is_alive()):
            proc.stdout.close()


def _result(outcome):
    return {"outcome": outcome, "exitCode": None, "stdout": b""}


def _terminate(proc, pgid):
    """Signal the child (or its whole group), then reap the direct child."""
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    elif proc.poll() is None:
        try:
            proc.terminate()
        except (ProcessLookupError, PermissionError):
            pass
    if proc.poll() is None:
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait()
            except Exception:  # noqa: BLE001 — the child is gone either way
                pass
