#!/usr/bin/env python3
"""Micro engine check (#299 Phase 4): the fast pre-release engine sanity step.

For each authorized external engine in the calibration, run ONE real end-to-end engine_adapter
dispatch — build_argv → the engine CLI (as a real subprocess) → parse_result → commit_result —
against a THROWAWAY git dir, and assert (a) the engine actually produced its artifact and (b) the
parsed result is an honest ok. Minutes-and-pennies instead of a full acceptance run; directly
exercises the deterministic argv/parse/commit core the spine's external dispatch rides.

This is the HOST-side twin of the in-sandbox dispatch (engine_dispatch.js): it does NOT go through
the Workflow staging chain — it verifies the engine_adapter core + the engine binaries answer
honestly. The acceptance dispatch-census (dispatch_census.py) covers the in-sandbox path.

CI never needs live codex/cursor: tests stub the engine binaries by putting fake `codex` /
`cursor-agent` executables on PATH (a realistic stub — build_argv + the real subprocess + parse_result
all run; only the model binary is fake). stdlib only; never raises past a per-engine {ok:false}.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import engine_adapter
import engine_pref
import store_core  # shared `git -C <cwd> ...` runner (stripped stdout or None, with a timeout)

# The artifact the build probe asks the engine to create — a fixed, boring filename so the check is
# deterministic and the assertion is a plain os.path.isfile, no engine free-text parsed for success.
_ARTIFACT = "engine-check.txt"
_BUILD_PROMPT = (
    "Create a file named %s in the current directory containing exactly the line "
    "'engine-check ok'. Make no other changes. Then return a JSON object "
    '{"ok": true, "signal": "ok", "evidence": {"testPassed": false, "testFailed": false}}.'
) % _ARTIFACT

_DEFAULT_TIMEOUT = 300


def _init_throwaway_repo(path):
    """A minimal git repo with one commit so a preSHA exists (commit_result folds onto it)."""
    store_core.run_git(path, "init", "-q")
    store_core.run_git(path, "config", "user.email", "engine-check@superheroes.local")
    store_core.run_git(path, "config", "user.name", "engine-check")
    open(os.path.join(path, ".gitkeep"), "w").close()
    store_core.run_git(path, "add", "-A")
    store_core.run_git(path, "commit", "-q", "-m", "init")


def check_engine(engine, *, workdir=None, effort=None, timeout=_DEFAULT_TIMEOUT):
    """Run one real build dispatch against a throwaway repo. Returns a per-engine result dict:
    {engine, ok, reason, artifact, sha}. `ok` is True ONLY when the parsed result is honest-ok AND
    the artifact exists AND the adapter committed it. Never raises."""
    result = {"engine": engine, "ok": False, "reason": None, "artifact": False, "sha": None}
    if effort is None:
        effort = engine_pref.resolve_effort(engine, "build", None)
    tmp = workdir or tempfile.mkdtemp(prefix="engine-check-%s-" % engine)
    try:
        _init_throwaway_repo(tmp)
        pre_sha = store_core.run_git(tmp, "rev-parse", "HEAD")
        if not pre_sha:
            result["reason"] = "could-not-init-throwaway-repo"
            return result

        argv = engine_adapter.build_argv(engine, "build", effort, {"cwd": tmp})
        if not argv:
            result["reason"] = "unknown-engine (empty argv)"
            return result

        prompt_path = os.path.join(tmp, ".engine-check.prompt")
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(_BUILD_PROMPT)

        try:
            with open(prompt_path, encoding="utf-8") as stdin_fh:
                proc = subprocess.run(argv, cwd=tmp, stdin=stdin_fh,
                                      capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            result["reason"] = "engine binary not found: %s" % argv[0]
            return result
        except subprocess.TimeoutExpired:
            result["reason"] = "timeout"
            return result

        # Don't let the transient prompt file masquerade as the engine's artifact.
        try:
            os.remove(prompt_path)
        except OSError:
            pass

        parsed = engine_adapter.parse_result(engine, "build", proc.stdout)
        if not parsed.get("ok"):
            result["reason"] = "engine did not return an honest ok (%s)" % (parsed.get("reason")
                                                                            or parsed.get("signal") or "unreadable")
            return result

        artifact_path = os.path.join(tmp, _ARTIFACT)
        result["artifact"] = os.path.isfile(artifact_path)
        if not result["artifact"]:
            result["reason"] = "engine returned ok but produced no artifact (%s)" % _ARTIFACT
            return result

        commit = engine_adapter.commit_result(tmp, "engine-check", pre_sha)
        if not commit.get("ok"):
            result["reason"] = "commit failed: %s" % commit.get("error")
            return result
        result["sha"] = commit.get("sha")
        result["ok"] = True
        return result
    except Exception as exc:  # never raise past the boundary
        result["reason"] = "%s: %s" % (type(exc).__name__, exc)
        return result
    finally:
        if workdir is None:
            _cleanup(tmp)


def _cleanup(path):
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _authorized_calibration_engines(root):
    """The external engines the calibration ROUTES to AND that the host authorizes — the set the
    check should exercise. Best-effort: any read failure yields an empty set (nothing to check)."""
    engines = set()
    try:
        prefs = engine_pref.load_engine_prefs(root, None)
        for role_kind in ("review", "build", "fix", "author-plan"):
            eng = engine_pref.resolve_engine(role_kind, prefs)
            if eng in ("codex", "cursor"):
                engines.add(eng)
    except Exception:
        return set()
    try:
        import engine_detect
        authz = engine_detect.probe(root)
        return {e for e in engines if engine_detect.decide(authz, e)[0]}
    except Exception:
        return engines


def run_check(engines, *, timeout=_DEFAULT_TIMEOUT):
    results = [check_engine(e, timeout=timeout) for e in engines]
    return {"ok": all(r["ok"] for r in results) if results else True,
            "engines": engines, "results": results}


def main(argv):
    ap = argparse.ArgumentParser(prog="engine_check_cli",
                                 description="micro engine check: one real dispatch per authorized engine")
    ap.add_argument("--engines", default=None,
                    help="comma-separated engines to check (codex,cursor); default = authorized "
                         "engines the calibration routes to")
    ap.add_argument("--root", default=".", help="repo root for calibration/authz resolution")
    ap.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT)
    ap.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = ap.parse_args(argv)

    if args.engines is not None:
        engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    else:
        engines = sorted(_authorized_calibration_engines(args.root))

    out = run_check(engines, timeout=args.timeout)
    if args.json:
        sys.stdout.write(json.dumps(out) + "\n")
    else:
        if not engines:
            sys.stdout.write("engine check: no authorized external engines in the calibration — nothing to check\n")
        for r in out["results"]:
            sys.stdout.write("  %-7s %s%s\n" % (
                r["engine"], "ok" if r["ok"] else "FAIL",
                "" if r["ok"] else " — %s" % r["reason"]))
        sys.stdout.write("engine check: %s\n" % ("ok" if out["ok"] else "FAIL"))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
