"""One bounded child-process runner for the pilot modules (#866).

`pilot_mint.run_gate_off_test` and `pilot_boundary._run_bounded_observer` grew the same shape
independently — spawn, read stdout on a reader thread with a byte cap, bound the read and the wait
by the same timeout, and reap the child on every exit path — and then **diverged** on process-group
handling. That divergence is the reason to extract rather than a reason not to: one copy signalled
the whole process group on timeout and the other only the direct child, so a runaway grandchild
outlived exactly one of them.

**Process-group containment on every termination path is unconditional.** Every run starts its own
session (`start_new_session=True`), so every child is the leader of its own process group, and
timeout, oversize output, a read failure, an unexpected error, and the `finally` sweep of a child
still running all signal that whole group — never just the direct child, and with no per-caller
opt-out. What this does NOT cover: a command that **exits on its own** is reaped as the leader
only, because `_terminate` is never called on that path. A descendant it left running with stdout
detached is not signalled — that gap is known and out of scope here, tracked as a follow-up.

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
import time

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
    retain_output=True,
):
    """Run ``command`` bounded by wall-clock and stdout bytes; classify how it ended.

    Returns ``{"outcome": <OUTCOME_*>, "exitCode": int|None, "stdout": bytes,
    "stdoutBytes": int, "stdoutTruncated": bool}``. ``exitCode`` is non-None only for
    ``completed``; ``stdout`` is the raw bytes read when ``retain_output`` is true (empty
    otherwise). Never raises for a child's behaviour — a spawn failure, a read failure, and any
    other unexpected error all classify as ``spawn-failed``, because a caller that cannot see the
    child's output cannot distinguish them and must refuse either way.

    With ``retain_output=True`` (the default), stdout is retained up to ``max_output_bytes`` and
    output beyond the cap classifies as ``oversize``. With ``retain_output=False``, stdout is
    counted but never accumulated; truncation is reported on a ``completed`` outcome instead of
    refusing as ``oversize``.

    Every run starts its own session (``start_new_session=True``), and every *termination* path
    (timeout, oversize, read failure, unexpected error, or the ``finally`` sweep of a still-running
    child) signals the whole process group, unconditionally. A command that exits on its own is a
    different path: it is reaped as the leader only, so a descendant it left behind with stdout
    detached is not signalled — a known, deliberate gap, not covered by this change.
    """
    # bite-axis: containment — stdout is read under a byte cap so oversized output cannot exhaust
    # memory, both the read and the wait are bounded by timeout_seconds, and the child's whole
    # process group is reaped on every exit path including the unexpected-exception path.
    try:
        proc = subprocess.Popen(
            command,
            cwd=run_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            env=env,
            start_new_session=True,
        )
    except (OSError, ValueError):
        # ValueError, not just OSError: Popen raises it for an embedded NUL in an argv element
        # or in an environment name or value. Both callers validate their inputs as "non-empty
        # strings" and neither excludes a NUL, so those inputs reach here — and before this catch
        # the exception escaped the runner entirely, past `run_gate_off_test`'s refusal contract
        # and past `observe_datastore_identity`'s. A named refusal is the honest outcome, and it
        # is what makes this module's "never raises for a child's behaviour" claim true.
        return _result(OUTCOME_SPAWN_FAILED, max_output_bytes=max_output_bytes)

    # With start_new_session=True the child IS the process-group leader, so its pgid is
    # deterministically its own pid — no need to query it back with os.getpgid(proc.pid), which
    # would race a child that has already exited (os.getpgid raises ProcessLookupError, pgid would
    # fall to None, and the surviving group would then never be signalled).
    pgid = proc.pid

    reader = None
    try:
        stdout_holder = []
        count_meta = []
        read_error = []

        if retain_output:

            def _read_stdout():
                try:
                    stdout_holder.append(proc.stdout.read(max_output_bytes + 1))
                except Exception as exc:  # noqa: BLE001 — the exception itself is never inspected
                    read_error.append(exc)

        else:

            def _read_stdout():
                total = 0
                truncated = False
                try:
                    while True:
                        chunk = proc.stdout.read(65536)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_output_bytes:
                            truncated = True
                except Exception as exc:  # noqa: BLE001 — match pilot_cleanup's count reset
                    read_error.append(exc)
                    total = 0
                    truncated = False
                count_meta.append((total, truncated))

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout_seconds)

        if reader.is_alive():
            _terminate(proc, pgid)
            reader.join(timeout=1)
            return _result(
                OUTCOME_TIMEOUT,
                max_output_bytes=max_output_bytes,
                counted=count_meta[0] if count_meta else None,
                retain_output=retain_output,
            )

        if read_error:
            _terminate(proc, pgid)
            return _result(OUTCOME_SPAWN_FAILED, max_output_bytes=max_output_bytes)

        if not retain_output:
            total, truncated = count_meta[0] if count_meta else (0, False)
            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate(proc, pgid)
                reader.join(timeout=1)
                return _result(
                    OUTCOME_TIMEOUT,
                    max_output_bytes=max_output_bytes,
                    counted=(total, truncated),
                    retain_output=False,
                )

            return {
                "outcome": OUTCOME_COMPLETED,
                "exitCode": proc.returncode,
                "stdout": b"",
                "stdoutBytes": min(total, max_output_bytes),
                "stdoutTruncated": truncated,
            }

        stdout_bytes = stdout_holder[0] if stdout_holder else b""
        if len(stdout_bytes) > max_output_bytes:
            _terminate(proc, pgid)
            return _result(OUTCOME_OVERSIZE, max_output_bytes=max_output_bytes)

        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate(proc, pgid)
            reader.join(timeout=1)
            return _result(OUTCOME_TIMEOUT, max_output_bytes=max_output_bytes)

        return {
            "outcome": OUTCOME_COMPLETED,
            "exitCode": proc.returncode,
            "stdout": stdout_bytes,
            "stdoutBytes": len(stdout_bytes),
            "stdoutTruncated": False,
        }
    except Exception:  # noqa: BLE001 — every unexpected failure is an indeterminate run
        _terminate(proc, pgid)
        return _result(OUTCOME_SPAWN_FAILED, max_output_bytes=max_output_bytes)
    finally:
        if proc.poll() is None:
            _terminate(proc, pgid)
        if reader is not None and reader.is_alive():
            reader.join(timeout=1)
        # The two copies disagreed here and this is `pilot_mint`'s shape, adopted deliberately.
        # Now that every termination path signals the whole process group unconditionally
        # (Task 1, #866), a descendant that inherited the pipe is signalled along with everything
        # else in its group: SIGKILL cannot be ignored, so the blocked `read()` unblocks on EOF
        # and the reader thread exits. This is no longer the leak/hang tradeoff it used to be —
        # closing the pipe here is not what reaps a lingering descendant, the group kill above
        # already did that. The guard below is belt-and-braces, not the primary defense: closing
        # a BufferedReader while another thread is still blocked inside it makes `close()` wait on
        # the buffer lock that blocked `read()` holds, which can hang the caller in its own
        # `finally`, so this still only closes once the reader is confirmed not alive rather than
        # assuming that timing.
        if proc.stdout and (reader is None or not reader.is_alive()):
            proc.stdout.close()


def _result(outcome, *, max_output_bytes, counted=None, retain_output=True):
    stdout_bytes = 0
    stdout_truncated = False
    if not retain_output and counted is not None:
        total, truncated = counted
        stdout_bytes = min(total, max_output_bytes)
        stdout_truncated = truncated
    return {
        "outcome": outcome,
        "exitCode": None,
        "stdout": b"",
        "stdoutBytes": stdout_bytes,
        "stdoutTruncated": stdout_truncated,
    }


def _terminate(proc, pgid):
    """Signal the child's whole process group, then reap the direct child."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    # Deliberately a bare sleep, not `proc.wait(timeout=1)`: reaping the group leader here would
    # release its pid — and pgid IS that pid, since this runner's pgid is always the leader's own
    # pid (start_new_session=True) — for the kernel to hand to an unrelated same-UID process group
    # before the SIGKILL below runs. An unreaped zombie leader keeps holding that pid/pgid identity,
    # which is exactly what stops the second killpg from ever hitting a process we don't mean to
    # (#866 audit r2-2). Reaping happens only after both signals, below.
    time.sleep(1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
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
