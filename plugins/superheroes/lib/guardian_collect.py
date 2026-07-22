#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_collect.py
"""Shared collector helpers for Guardian lenses — one tool-running behavior, not three.

Stdlib-only. Lens `collect()` implementations use these so "tool missing", "tool timed
out", and "tool failed" degrade the same way in every lens (CONVENTIONS §11 — one home
for the behavior). run_tool never raises: it normalizes every failure into a dict a lens
can turn into a `not-collected` / `partial` status.
"""
import os
import shutil
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

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


def run_tool(argv, ctx=None, timeout=DEFAULT_TIMEOUT, cwd=None, ok_exits=(0,)):
    """Run `argv` and normalize the outcome. Never raises.

    Returns {"ok": bool, "exit": int|None, "stdout": str, "stderr": str, "reason": str|None}.
    `ctx["run"]` is used when present so tests inject without spawning anything.

    `ok_exits` is the set of exit codes that mean the tool succeeded (default `(0,)`).
    Many OSS analyzers exit non-zero when they *find* something — vulture exits 3,
    knip exits 1, npm audit exits 1, pip-audit exits 1 — and those are successful
    collections, not failures. Pass the tool's real success codes here so `ok` is
    trustworthy; do not override `ok` locally after the fact (a future author who
    trusts the flag would otherwise silently misclassify a findings run as a failure,
    which reads as clean).
    """
    run = (ctx or {}).get("run") or subprocess.run
    argv0 = argv[0] if argv else "<empty argv>"
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


def collected():
    """Status fragment for a complete collection — carries no reason."""
    return {"status": "collected"}


def partial(reason):
    """Status fragment: some of the collection succeeded; `reason` names what did not."""
    return {"status": "partial", "reason": reason}


def not_collected(reason):
    """Status fragment: nothing was collected. NEVER return empty candidates instead."""
    return {"status": "not-collected", "reason": reason}
