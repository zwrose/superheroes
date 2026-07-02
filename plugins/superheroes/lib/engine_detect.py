#!/usr/bin/env python3
"""Engine readiness preflight — the gh_preflight.py shape for Codex + Cursor (FR-11).
Pure decide + best-effort injectable probe + JSON CLI verdict. Read-only; never prints or
persists credentials; probe NEVER raises (any exception/timeout → error)."""
import argparse
import json
import shutil
import subprocess
import sys

# engine -> (the CLI binary, the cheap auth/whoami argv).
_CLI = {
    "codex": ("codex", ["codex", "login", "status"]),
    "cursor": ("cursor-agent", ["cursor-agent", "status"]),
}

_CAUSE_TEXT = {
    "not_installed": "the CLI is not installed",
    "not_authenticated": "the CLI is not signed in",
    "indeterminate": "engine readiness could not be determined",
}


def _remediation(engine, cause):
    if cause == "not_installed":
        if engine == "codex":
            return "install Codex — see https://github.com/openai/codex"
        return "install Cursor — see https://cursor.com/cli"
    if cause == "not_authenticated":
        return "codex login" if engine == "codex" else "cursor-agent login"
    return "verify the engine CLI is installed and signed in, then retry"


def _probe_one(engine, root, run):
    binary, auth_argv = _CLI[engine]
    rec = {"installed": False, "authed": False, "error": None}
    try:
        if shutil.which(binary) is None:
            return rec
        rec["installed"] = True
        proc = run(auth_argv, capture_output=True, text=True, timeout=10, cwd=root)
        rec["authed"] = (proc.returncode == 0)
        return rec
    except Exception as exc:  # timeout, OSError, anything — never propagate
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        return rec


def probe(root, run=None):
    """Best-effort world-read → {codex:{...}, cursor:{...}}. NEVER raises; never prints creds."""
    if run is None:
        run = subprocess.run
    return {"codex": _probe_one("codex", root, run),
            "cursor": _probe_one("cursor", root, run)}


def decide(probe_dict, engine):
    """(ok, cause, remediation). Pure + fail-closed."""
    if engine not in _CLI or not isinstance(probe_dict, dict):
        return (False, "indeterminate", _remediation(engine, "indeterminate"))
    rec = probe_dict.get(engine)
    if not isinstance(rec, dict):
        return (False, "indeterminate", _remediation(engine, "indeterminate"))
    if rec.get("error"):
        return (False, "indeterminate", _remediation(engine, "indeterminate"))
    if rec.get("installed") is not True:
        return (False, "not_installed", _remediation(engine, "not_installed"))
    if rec.get("authed") is not True:
        return (False, "not_authenticated", _remediation(engine, "not_authenticated"))
    return (True, None, None)


def message(probe_dict, engine, ok, cause, remediation):
    if ok:
        return "%s is ready" % engine
    parts = ["%s: %s" % (engine, _CAUSE_TEXT.get(cause, _CAUSE_TEXT["indeterminate"]))]
    rec = probe_dict.get(engine) if isinstance(probe_dict, dict) else None
    if cause == "indeterminate" and isinstance(rec, dict) and rec.get("error"):
        parts.append("(%s)" % str(rec["error"]).strip())
    parts.append("Fix: %s" % remediation)
    return " — ".join(parts)


def _verdict(p, engine):
    """One engine's full verdict dict (ok/cause/remediation/message + the raw installed/authed)."""
    ok, cause, rem = decide(p, engine)
    rec = p.get(engine) if isinstance(p, dict) else {}
    rec = rec if isinstance(rec, dict) else {}
    return {"engine": engine, "ok": ok, "cause": cause, "remediation": rem,
            "message": message(p, engine, ok, cause, rem),
            "installed": bool(rec.get("installed")), "authed": bool(rec.get("authed"))}


def main(argv, run=None):
    ap = argparse.ArgumentParser(prog="engine_detect")
    # --engine OPTIONAL: with it, the single-engine verdict; without it, the both-engines MATRIX
    # (what configure's FR-11 availability step shells).
    ap.add_argument("--engine", default=None, choices=("codex", "cursor"))
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    try:
        p = probe(args.root, run=run)
    except Exception as exc:  # fail-CLOSED catch-all (probe already never raises; belt-and-suspenders)
        p = {"codex": {"installed": False, "authed": False, "error": "%s: %s" % (type(exc).__name__, exc)},
             "cursor": {"installed": False, "authed": False, "error": "%s: %s" % (type(exc).__name__, exc)}}
    if args.engine is None:
        # MATRIX mode: a verdict per engine; exit 0 if ANY engine is ready.
        matrix = {"codex": _verdict(p, "codex"), "cursor": _verdict(p, "cursor")}
        sys.stdout.write(json.dumps(matrix) + "\n")
        return 0 if (matrix["codex"]["ok"] or matrix["cursor"]["ok"]) else 1
    verdict = _verdict(p, args.engine)
    sys.stdout.write(json.dumps(verdict) + "\n")
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
