#!/usr/bin/env python3
"""Resolve where a project's review-crew profile/decisions live.

Two locations, checked in order: in-repo (./.claude/) then a global per-repo
store at ~/.claude/review-crew/ keyed by BOTH the normalized origin URL and the
git-common-dir path (per-key pointer files, self-healing). See
docs/superpowers/specs/2026-06-07-review-crew-profile-storage-design.md.

All git calls use argv arrays with a timeout — never shell=True.

The two-key pointer + self-heal resolution algorithm lives in store_core.py;
this module is the review-crew-specific adapter on top.
"""
import json
import os
import sys

from store_core import (
    normalize_remote,
    short_hash,
    get_remote,
    derive_identifiers,
    read_pointer,
    write_pointer,
    _write_keys_json,
    resolve_global,
    _run_git,
)

FILENAMES = {"profile": "review-profile.md", "decisions": "review-decisions.json"}


def get_gitdir(cwd):
    """realpath of the git-common-dir (shared by all worktrees).

    Falls back to --absolute-git-dir for git < 2.31, then to realpath(cwd)
    for non-git dirs. Defined here (not re-exported from store_core) so that
    tests can monkeypatch review_store._run_git and have it take effect.
    """
    out = _run_git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if out is None:
        out = _run_git(cwd, "rev-parse", "--absolute-git-dir")
    return os.path.realpath(out if out is not None else cwd)

REVIEW_CREW_STORAGE = "~/.claude/review-crew"


def store_root():
    return os.path.realpath(os.path.expanduser(REVIEW_CREW_STORAGE))


def create(cwd, kind, location, root):
    """Return the path to write `kind` at `location`. Non-destructive: never
    truncates an existing profile/decisions file or overwrites an existing
    keys.json. For 'global', mints/reuses the entry and registers both pointers."""
    if location == "in-repo":
        d = os.path.join(cwd, ".claude")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, FILENAMES[kind])
    if location != "global":
        raise ValueError(f"unknown location: {location}")

    ident = derive_identifiers(cwd)
    entry_id = ident["gitdir_hash"]
    entry_dir = os.path.join(root, "entries", entry_id)
    os.makedirs(entry_dir, exist_ok=True)
    if not os.path.exists(os.path.join(entry_dir, "keys.json")):
        _write_keys_json(entry_dir, ident)
    write_pointer(root, ident["gitdir_hash"], entry_id)
    if ident["remote_hash"]:
        write_pointer(root, ident["remote_hash"], entry_id)
    return os.path.join(entry_dir, FILENAMES[kind])


def resolve(cwd, kind, root):
    """Resolve `kind`'s path. Location is keyed on the PROFILE: in-repo profile
    wins, else a global entry whose profile exists, else none. Decisions
    co-locate with the profile."""
    in_repo_profile = os.path.join(cwd, ".claude", "review-profile.md")
    if os.path.exists(in_repo_profile):
        path = os.path.join(cwd, ".claude", FILENAMES[kind])
        return {"kind": kind, "path": path, "location": "in-repo",
                "exists": os.path.exists(path), "healed": False, "entry_id": None}

    g = resolve_global(cwd, root, _consumer="review_store")
    if g is not None and os.path.exists(os.path.join(g["dir"], "review-profile.md")):
        path = os.path.join(g["dir"], FILENAMES[kind])
        return {"kind": kind, "path": path, "location": "global",
                "exists": os.path.exists(path), "healed": g["healed"],
                "entry_id": g["entry_id"]}

    return {"kind": kind, "path": None, "location": "none", "exists": False,
            "healed": g["healed"] if g else False,
            "entry_id": g["entry_id"] if g else None}


def decide_location(env_value, interactive):
    """Where to create when nothing resolved. Env override wins; else interactive
    callers must ask; else (headless) default to global (zero-footprint)."""
    if env_value in ("in-repo", "global"):
        return env_value
    return "ask" if interactive else "global"


def _parse_kv(args, flag):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def main(argv):
    args = argv[1:]
    if not args:
        sys.stderr.write("Usage: review_store.py resolve|create|decide-location ...\n")
        return 2
    cmd = args[0]
    try:
        if cmd == "resolve":
            kind = _parse_kv(args, "--kind") or "profile"
            if kind not in FILENAMES:
                sys.stderr.write(f"bad --kind: {kind}\n")
                return 2
            sys.stdout.write(json.dumps(resolve(os.getcwd(), kind, store_root())) + "\n")
            return 0
        if cmd == "create":
            kind = _parse_kv(args, "--kind") or "profile"
            location = _parse_kv(args, "--location")
            if kind not in FILENAMES or location not in ("global", "in-repo"):
                sys.stderr.write("usage: create --kind profile|decisions --location global|in-repo\n")
                return 2
            sys.stdout.write(create(os.getcwd(), kind, location, store_root()) + "\n")
            return 0
        if cmd == "decide-location":
            interactive = _parse_kv(args, "--interactive") != "false"
            sys.stdout.write(
                decide_location(os.environ.get("REVIEW_CREW_STORAGE"), interactive) + "\n")
            return 0
    except Exception as exc:  # internal error -> non-zero exit per the failure contract
        sys.stderr.write(f"review_store error: {exc}\n")
        return 1
    sys.stderr.write(f"unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
