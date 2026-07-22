#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_collect.py
"""Shared collector helpers for Guardian lenses — one tool-running behavior, not three.

Stdlib-only apart from the sibling `guardian_tools` import (itself stdlib-only, so this
module stays stdlib-only transitively — just no longer self-contained). Lens `collect()`
implementations use these so "tool missing", "tool timed out", and "tool failed" degrade
the same way in every lens (CONVENTIONS §11 — one home for the behavior). run_tool never
raises: it normalizes every failure into a dict a lens can turn into a `not-collected` /
`partial` status.
"""
import os
import shutil
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# Import at module level (load time, before cwd is the swept repo), matching every other
# guardian module — a lazy import inside run_tool's production branch would be the FIRST
# import of guardian_tools during a sweep and resolve against sweep-time sys.path, opening
# an import-path RCE window if the swept repo ships its own guardian_tools.py. No cycle:
# guardian_tools imports nothing from guardian_collect.
import guardian_tools as gt

DEFAULT_TIMEOUT = 60


def tool_available(name):
    """True when `name` resolves on PATH. Probe only — never spawns a subprocess."""
    return shutil.which(name) is not None


def _result(ok, exit_code, stdout, stderr, reason):
    return {
        "ok": ok,
        "exit": exit_code,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "reason": reason,
    }


def _translate_invoke_result(res, argv, ok_exits):
    """Map guardian_tools.invoke's result-dict onto run_tool's {ok, exit, ...} shape.

    invoke already applied the hardening (repo-local rejection, sanitized env,
    neutral cwd, bounded output, process-group kill) — this only reads its verdict.
    Fails closed on any outcome it does not recognize.
    """
    argv0 = argv[0] if argv else "<empty argv>"
    outcome = res.get("outcome")
    returncode = res.get("returncode")
    stdout = res.get("stdout", "")
    stderr = res.get("stderr", "")

    if outcome == "ok":
        # invoke emits "ok" only for returncode 0, but gate on ok_exits anyway so this
        # composes with the injected seam (which returns ok only when exit ∈ ok_exits).
        # A rc-0 run under an ok_exits that excludes 0 must read ok=False.
        if returncode in ok_exits:
            return _result(True, returncode, stdout, stderr, None)
        return _result(False, returncode, stdout, stderr,
                       "%s exited %s" % (argv0, returncode))

    if outcome in ("nonzero-exit", "empty-output"):
        if returncode in ok_exits:
            return _result(True, returncode, stdout, stderr, None)
        reason = res.get("reason") or "%s exited %s" % (argv0, returncode)
        return _result(False, returncode, stdout, stderr, reason)

    # truncated-output / capture-incomplete are FAILURES even when returncode is an
    # ok exit — an ok_exits match must never override a bounded-output tripwire.
    if outcome in ("tool-absent", "timeout", "spawn-failed",
                   "truncated-output", "capture-incomplete"):
        reason = res.get("reason") or "%s failed (%s)" % (argv0, outcome)
        return _result(False, returncode, stdout, stderr, reason)

    # Unknown / unexpected outcome — fail closed with a clear reason.
    return _result(False, returncode, stdout, stderr,
                   "%s failed: unexpected invoke outcome %r" % (argv0, outcome))


def run_tool(argv, ctx=None, timeout=DEFAULT_TIMEOUT, cwd=None, ok_exits=(0,)):
    """Run `argv` and normalize the outcome. Never raises.

    Returns {"ok": bool, "exit": int|None, "stdout": str, "stderr": str, "reason": str|None}.

    Two paths, split on whether a `run` was injected via `ctx["run"]`:

    - **Injected** (`ctx["run"]` present) — the TEST / CONFORMANCE seam. Runs the
      injected callable directly and normalizes, so tests drive every scenario
      (incl. missing-tool) without spawning anything. Behavior here is unchanged.
    - **Production** (`ctx["run"]` is None/absent) — routes the real spawn through
      `guardian_tools.invoke`, inheriting its hardening (repo-local-executable
      rejection, sanitized env, neutral child cwd, bounded output, process-group
      kill). `cwd` (defaulting to the process cwd) is the repo root used for
      resolution / rejection / env-sanitization; the collector still runs from
      invoke's neutral cwd.

    `ok_exits` is the set of exit codes that mean the tool succeeded (default `(0,)`).
    Many OSS analyzers exit non-zero when they *find* something — vulture exits 3,
    knip exits 1, npm audit exits 1, pip-audit exits 1 — and those are successful
    collections, not failures. Pass the tool's real success codes here so `ok` is
    trustworthy; do not override `ok` locally after the fact (a future author who
    trusts the flag would otherwise silently misclassify a findings run as a failure,
    which reads as clean).
    """
    argv0 = argv[0] if argv else "<empty argv>"
    run = (ctx or {}).get("run")

    if run is not None:
        # TEST / CONFORMANCE SEAM — unchanged direct-run behavior.
        try:
            r = run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        except subprocess.TimeoutExpired:
            return _result(False, None, "", "",
                           "%s timed out after %ss" % (argv0, timeout))
        except (FileNotFoundError, OSError):
            return _result(False, None, "", "", "%s not available" % argv0)
        except Exception as exc:  # never raise into a lens's collect()
            return _result(False, None, "", "", "%s failed: %s" % (argv0, exc))

        exit_code = getattr(r, "returncode", None)
        stdout = getattr(r, "stdout", "")
        stderr = getattr(r, "stderr", "")
        if exit_code in ok_exits:
            return _result(True, exit_code, stdout, stderr, None)
        return _result(False, exit_code, stdout, stderr,
                       "%s exited %s" % (argv0, exit_code))

    # PRODUCTION — route the real spawn through invoke's hardening. Must never raise.
    if not argv:
        return _result(False, None, "", "", "%s: no command to run" % argv0)
    try:
        repo = os.path.realpath(cwd or os.getcwd())
        res = gt.invoke(argv[0], list(argv[1:]), repo, targets=(),
                        run=None, timeout=timeout)
        return _translate_invoke_result(res, argv, ok_exits)
    except Exception as exc:  # realpath/invoke ValueError etc. — fail closed, never raise
        return _result(False, None, "", "", "%s failed: %s" % (argv0, exc))


def collected():
    """Status fragment for a complete collection — carries no reason."""
    return {"status": "collected"}


def partial(reason):
    """Status fragment: some of the collection succeeded; `reason` names what did not."""
    return {"status": "partial", "reason": reason}


def not_collected(reason):
    """Status fragment: nothing was collected. NEVER return empty candidates instead."""
    return {"status": "not-collected", "reason": reason}
