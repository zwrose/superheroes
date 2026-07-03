#!/usr/bin/env python3
"""Code-leg verify gate (FR-17 / UFR-4).

A code leg must run the project's configured verify command and have it PASS before the loop
may declare a clean terminal. This module runs that command bounded and classifies the outcome
as `pass` / `fail` / `timeout` — a timeout is reported distinctly from a plain failure (UFR-4).
The terminal decision (clean requires pass; fail/timeout -> halted) is the tally's; this module
only produces the classified result it consumes.

`mode: unverified` projects pass the literal command "none" (or ""): the gate is SKIPPED — the
accepted no-verify limitation (spec › Ship-gate). Bounded by a default timeout mirroring the
band's project-command convention in blocks.py. Never raises; any execution error is a `fail`
(fail-closed — never a silent pass). stdlib only.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

DEFAULT_TIMEOUT = 600  # seconds; mirrors blocks.py's project-command bound, overridable


def _atomic_write_json(path, payload):
    text = json.dumps(payload, sort_keys=True) + "\n"
    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = None
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".verify-result-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def run_verify(command, cwd=None, timeout=DEFAULT_TIMEOUT, runner=subprocess.run):
    """Return {"result", "code", "tail"}. `command` is the project verify command (a shell
    string), or "none"/"" to skip."""
    if not command or command.strip().lower() == "none":
        return {"result": "skipped", "code": None, "tail": ""}
    try:
        proc = runner(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        tail = exc.output[-2000:] if isinstance(getattr(exc, "output", None), str) else ""
        return {"result": "timeout", "code": None, "tail": tail}
    except Exception as exc:  # OSError etc. — fail-closed, never a silent pass
        return {"result": "fail", "code": None, "tail": "verify could not run: %s" % exc}
    out = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
    return {"result": "pass" if proc.returncode == 0 else "fail",
            "code": proc.returncode, "tail": out}


def main(argv):
    ap = argparse.ArgumentParser(description="code-leg verify gate (review-crew)")
    ap.add_argument("--command", required=True)
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--out",
                    help="atomically write the result JSON to this path in addition to stdout")
    ap.add_argument("--emit-run", action="store_true",
                    help="IO-only mode: run subprocess and emit raw run data for the JS twin to classify")
    args = ap.parse_args(argv[1:])
    if args.emit_run:
        cmd = args.command
        if not cmd or cmd.strip().lower() == "none":
            res = {"command": cmd or "none", "returncode": None, "timedOut": False}
            if args.out:
                _atomic_write_json(args.out, res)
            sys.stdout.write(json.dumps(res) + "\n")
            return 0
        try:
            proc = subprocess.run(cmd, shell=True, cwd=args.cwd, capture_output=True,
                                  text=True, timeout=args.timeout)
            res = {"command": cmd, "returncode": proc.returncode, "timedOut": False}
        except subprocess.TimeoutExpired:
            res = {"command": cmd, "returncode": None, "timedOut": True}
        except Exception:
            # fail-closed: any exec error -> returncode 1 (non-zero = fail in the JS twin)
            res = {"command": cmd, "returncode": 1, "timedOut": False}
        if args.out:
            _atomic_write_json(args.out, res)
        sys.stdout.write(json.dumps(res) + "\n")
        return 0
    res = run_verify(args.command, cwd=args.cwd, timeout=args.timeout)
    if args.out:
        _atomic_write_json(args.out, res)
    sys.stdout.write(json.dumps(res, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
