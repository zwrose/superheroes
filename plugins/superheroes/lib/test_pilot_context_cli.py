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

import base_ref
import checkpoint
import control_plane
import detect
import engine
import store


def _git(*args, cwd=None):
    cmd = ["git"]
    if cwd:
        cmd += ["-C", cwd]
    cmd += list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def resolve(work_item, generation, worktree=None, base_name="main"):
    """Resolve the test-pilot phase context.

    Args:
        work_item: The work-item identifier.
        generation: The generation number (or None).
        worktree: Optional path to the build worktree. When given, all git ops run
            against that tree (not the showrunner cwd) so the diff reflects the
            deliverable, not the orchestrator's state (FIX B).
        base_name: Base branch name for the diff (default 'main'). Resolved via
            base_ref.resolve_configured_base for local→origin fallback. When
            unresolvable, falls back to 'main...HEAD' rather than crashing (FIX B).
    """
    paths = control_plane.paths(os.getcwd(), work_item)
    cp = checkpoint.read(paths["checkpoint"])
    if isinstance(cp, dict) and cp.get("_incompatible"):
        # recover_entry gates an incompatible checkpoint at startup, so this is defense in depth: don't
        # carry the truthy marker dict forward — re-derive branch/pr from git reality (treat as empty).
        cp = {}
    cp = cp or {}

    # FIX B: git ops run against the build worktree when provided; fall back to cwd root.
    git_root = worktree if worktree else (_git("rev-parse", "--show-toplevel") or os.getcwd())
    head = _git("rev-parse", "HEAD", cwd=git_root)
    branch = cp.get("branch") or _git("rev-parse", "--abbrev-ref", "HEAD", cwd=git_root)

    res = store.resolve(os.getcwd(), store.store_root())
    # The control-plane store is keyed per CLONE (sha256 of the git COMMON dir, shared across a
    # clone's worktrees) and holds the generation lease acquired in the SHOWRUNNER's own checkout.
    # Resolve it from os.getcwd() (the showrunner root): the store is control-plane state, not a git
    # op, so only the GIT ops (head/branch/diff/detectors/base) above target git_root. Under
    # common-dir keying a build worktree now resolves to the SAME store as the showrunner root
    # (both share the clone's common dir), so publish's renew()/fence_ok() find the live lease
    # either way — os.getcwd() stays the canonical control-plane cwd. (Matches
    # control_plane.paths(os.getcwd()) and store.resolve(os.getcwd()) here.)
    trusted_store = control_plane.ensure_store(os.getcwd())
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

    # FIX B: resolve the base ref (local→origin fallback) and diff against the build worktree.
    # Unresolvable base falls back to 'main...HEAD' (note: degraded, not a crash).
    resolved_base = base_ref.resolve_configured_base(git_root, base_name)
    if resolved_base is None:
        # Fall back to hardcoded main...HEAD (preserves prior behavior, noted as degradation).
        resolved_base = "main"
    diff_range = "%s...HEAD" % resolved_base
    diff_cmd = ["git", "-C", git_root, "diff", "--name-only", diff_range]
    files = subprocess.run(diff_cmd, capture_output=True, text=True, timeout=20)
    changed = [line for line in files.stdout.splitlines() if line]

    return {
        "workItem": work_item, "generation": generation,
        "worktree": git_root, "branch": branch, "head": head,
        "pr": cp.get("pr"), "store": trusted_store,
        "profile": profile or None, "profileError": profile_error,
        "profileSource": res.get("profileSource"),
        "baseUrl": base, "allowedOrigins": allowed,
        "browserTool": {"source": "profile", "tools": browser_tools} if browser_tools else None,
        "diff": {"files": changed},
        "detectors": detect.detect_dev_server(git_root, profile),
    }


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot context resolver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    res = sub.add_parser("resolve")
    res.add_argument("--work-item", required=True)
    res.add_argument("--generation", default=None)
    res.add_argument("--worktree", default=None,
                     help="Path to the build worktree (FIX B). When given, git ops run "
                          "against that tree so the diff reflects the deliverable.")
    res.add_argument("--base", default="main",
                     help="Base branch name for diff (FIX B, default: main).")
    args = ap.parse_args(argv[1:])

    if args.cmd == "resolve":
        # Preserve the original heredoc's contract: a numeric generation stays a JSON number.
        generation = args.generation
        if isinstance(generation, str) and generation.isdigit():
            generation = int(generation)
        sys.stdout.write(json.dumps(resolve(
            args.work_item,
            generation,
            worktree=args.worktree,
            base_name=args.base,
        )) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
