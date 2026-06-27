#!/usr/bin/env python3
"""Resolve the test-pilot phase context (the showrunner spine's `resolveContext` leaf).

Gathers all the IO the phase needs — checkpoint, git refs, store/profile resolution, the changed-file
diff, and dev-server detection — and prints the context as one JSON object. Extracted verbatim from an
inline `python3 -c` heredoc in showrunner.js so it is testable and lintable like the other test-pilot
leaves (the spine orchestrates; the leaves do the IO — CONVENTIONS §10.1).
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import checkpoint
import control_plane
import detect
import engine
import store


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def resolve(work_item, generation):
    paths = control_plane.paths(os.getcwd(), work_item)
    cp = checkpoint.read(paths["checkpoint"])
    if isinstance(cp, dict) and cp.get("_incompatible"):
        # recover_entry gates an incompatible checkpoint at startup, so this is defense in depth: don't
        # carry the truthy marker dict forward — re-derive branch/pr from git reality (treat as empty).
        cp = {}
    cp = cp or {}
    root = _git("rev-parse", "--show-toplevel") or os.getcwd()
    head = _git("rev-parse", "HEAD")
    branch = cp.get("branch") or _git("rev-parse", "--abbrev-ref", "HEAD")
    res = store.resolve(os.getcwd(), store.store_root())
    trusted_store = control_plane.ensure_store(root)
    profile = {}
    profile_error = None
    if res.get("profile"):
        try:
            profile = engine.load_profile_config(res["profile"])
        except Exception as exc:  # noqa: BLE001 - a profile load failure is surfaced, not fatal
            profile_error = str(exc)
    base = profile.get("baseUrl") or profile.get("base_url")
    allowed = (profile.get("allowedOrigins") or profile.get("allowed_origins")
               or ([base] if base else []))
    browser_tools = (profile.get("browserTools") or profile.get("browser_tools")
                     or profile.get("browserTool"))
    files = subprocess.run(["git", "diff", "--name-only", "main...HEAD"],
                           capture_output=True, text=True, timeout=20)
    changed = [line for line in files.stdout.splitlines() if line]
    return {
        "workItem": work_item, "generation": generation,
        "worktree": root, "branch": branch, "head": head,
        "pr": cp.get("pr"), "store": trusted_store,
        "profile": profile or None, "profileError": profile_error,
        "baseUrl": base, "allowedOrigins": allowed,
        "browserTool": {"source": "profile", "tools": browser_tools} if browser_tools else None,
        "diff": {"files": changed},
        "detectors": detect.detect_dev_server(root, profile),
    }


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot context resolver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    res = sub.add_parser("resolve")
    res.add_argument("--work-item", required=True)
    res.add_argument("--generation", default=None)
    args = ap.parse_args(argv[1:])

    if args.cmd == "resolve":
        # Preserve the original heredoc's contract: a numeric generation stays a JSON number.
        generation = args.generation
        if isinstance(generation, str) and generation.isdigit():
            generation = int(generation)
        sys.stdout.write(json.dumps(resolve(args.work_item, generation)) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
