#!/usr/bin/env python3
"""The show-but-don't-apply build-authorization helper (FR-13) + the run-time write preflight
(UFR-4) + the configure CLIs (snippet / test-dispatch). Authorization is HOST-ENFORCED — the band
never writes the owner's autoMode.allow grant; it shows the exact snippet and, at run time,
behaviorally observes allow vs deny via a throwaway external write, run through THAT engine's own
write command, inside the managed worktree. A wrong assumption only falls OPEN to Claude (a cost,
never a corrupt result), so the failure mode is safe by construction."""
import argparse
import json
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# engine -> the dispatch command the owner's autoMode.allow rule must match (host-global grant).
_DISPATCH_CMD = {"codex": "codex exec", "cursor": "cursor-agent"}


def _probe_timeout(overrides=None):
    """The subprocess timeout for the throwaway dispatch probe — the SAME configurable, test-settable
    limit as UFR-5 (`engine_pref.resolve_timeout`, default DEFAULT_STALL_LIMIT_SECONDS=300). Any import
    or resolution failure falls open to the 300s default; never raises."""
    try:
        import engine_pref
        return engine_pref.resolve_timeout(overrides)
    except Exception:
        return 300


def authorization_snippet(host, engine):
    """Return the exact autoMode.allow block for `engine` on `host` + WHERE to paste it. NEVER
    writes anything. The grant is host-global (matches the dispatch command, not a path)."""
    cmd = _DISPATCH_CMD.get(engine, engine)
    block = {"autoMode": {"allow": ["Bash(%s:*)" % cmd]}}
    location = ".claude/settings.local.json"
    return (
        "To let %s build autonomously on the %s host, add this one-time grant to your own\n"
        "%s (the band never writes it for you):\n\n"
        "%s\n\n"
        "This authorizes the `%s` dispatch command; remove it to revoke."
        % (engine, host, location, json.dumps(block, indent=2), cmd)
    )


def implementation_dispatch_allowed(cwd, engine, run=None, overrides=None):
    """Run-time preflight: a trivial throwaway external WRITE inside the managed worktree to
    observe allow vs deny before the first real build/fix write. The probe is issued through
    `engine`'s OWN write command (`codex exec …` / `cursor-agent …`) so the host's per-engine
    autoMode.allow rule (`Bash(codex exec:*)` vs `Bash(cursor-agent:*)`) is exactly what is tested.
    An unknown engine, a denied/failed/errored/timed-out write → False (→ implementation role falls
    open to Claude, UFR-4). The subprocess is bounded by the SAME configurable, test-settable limit
    as UFR-5 (`engine_pref.resolve_timeout(overrides)`, default 300s) — `overrides` is threaded
    straight through so callers/tests can set it exactly like UFR-5's stall limit. Never raises."""
    if run is None:
        run = subprocess.run
    dispatch = _DISPATCH_CMD.get(engine)
    if dispatch is None:
        return False  # unknown engine -> fall open (safe): the impl role runs on Claude
    probe_file = os.path.join(cwd, ".superheroes-authz-probe")
    # A harmless throwaway write, but run as the ENGINE's own workspace-write dispatch command so the
    # host's autoMode classifier decides allow vs deny against the SAME grant a real build would hit.
    # `codex exec --sandbox workspace-write -C <cwd> "<prompt>"` / `cursor-agent -p -f "<prompt>"`.
    write_prompt = "write an empty file named .superheroes-authz-probe and exit"
    if engine == "codex":
        argv = ["codex", "exec", "--sandbox", "workspace-write", "-C", cwd, write_prompt]
    else:  # cursor
        # -p/--print is required for a headless run (without it cursor-agent goes interactive and
        # the probe hangs to the timeout, always reporting the engine not-ready); -f forces/trusts.
        argv = ["cursor-agent", "-p", "-f", write_prompt]
    timeout = _probe_timeout(overrides)
    try:
        proc = run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        allowed = (getattr(proc, "returncode", 1) == 0)
    except Exception:
        # includes subprocess.TimeoutExpired: no response within the bounded limit -> deny/fall-open
        allowed = False
    finally:
        try:
            os.remove(probe_file)
        except OSError:
            pass
    return bool(allowed)


def _cmd_snippet(args):
    sys.stdout.write(authorization_snippet(args.host, args.engine) + "\n")
    return 0


def _cmd_test_dispatch(args, run):
    overrides = {"timeout": args.timeout} if args.timeout is not None else None
    ok = implementation_dispatch_allowed(args.cwd, args.engine, run=run, overrides=overrides)
    sys.stdout.write(json.dumps({"engine": args.engine, "ok": bool(ok)}) + "\n")
    return 0


def main(argv, run=None):
    ap = argparse.ArgumentParser(prog="engine_authz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snippet")
    s.add_argument("--host", required=True)
    s.add_argument("--engine", required=True, choices=("codex", "cursor"))
    t = sub.add_parser("test-dispatch")
    t.add_argument("--engine", required=True, choices=("codex", "cursor"))
    t.add_argument("--cwd", default=".")
    # optional override of the UFR-5 stall limit (engine_pref.resolve_timeout); default is None,
    # meaning "use resolve_timeout(None)" == DEFAULT_STALL_LIMIT_SECONDS (300), NOT a hardcoded 10.
    t.add_argument("--timeout", type=int, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "snippet":
        return _cmd_snippet(args)
    if args.cmd == "test-dispatch":
        return _cmd_test_dispatch(args, run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
