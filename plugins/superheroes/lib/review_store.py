#!/usr/bin/env python3
"""Resolve where a project's review-crew profile/decisions live.

Two locations, checked in order: in-repo (./.claude/) then a global per-repo
store at ~/.claude/review-crew/ keyed by BOTH the normalized origin URL and the
git-common-dir path (per-key pointer files, self-healing). See
docs/superheroes/specs/2026-06-07-review-crew-profile-storage-design.md.

Unified layout (#81): calibration lives in core.md + review-crew.md layer
(.claude/superheroes/ in-repo, or the control-plane project store globally).
Legacy review-profile.md is a migration source only.

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
    get_gitdir,
    derive_identifiers,
    read_pointer,
    write_pointer,
    write_keys_json,
    resolve_global,
    run_git,
)

FILENAMES = {"profile": "review-profile.md", "decisions": "review-decisions.json"}
UNIFIED_LAYER = "review-crew.md"
UNIFIED_DIR = os.path.join(".claude", "superheroes")

REVIEW_CREW_STORAGE = "~/.claude/review-crew"


def store_root():
    return os.path.realpath(os.path.expanduser(REVIEW_CREW_STORAGE))


def _repo_root(cwd):
    top = run_git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(top) if top else os.path.realpath(cwd)


def _unified_in_repo(cwd):
    layer = os.path.join(_repo_root(cwd), UNIFIED_DIR, UNIFIED_LAYER)
    return layer if os.path.isfile(layer) else None


def _legacy_in_repo(cwd):
    path = os.path.join(_repo_root(cwd), ".claude", FILENAMES["profile"])
    return path if os.path.isfile(path) else None


def _unified_global(cwd, registry_root=None):
    """Unified global layer lives in the control-plane store, never review-crew's store."""
    import mode_registry
    path = os.path.join(
        mode_registry.project_store_dir(cwd, registry_root), "config", UNIFIED_LAYER)
    return path if os.path.isfile(path) else None


def _legacy_global(cwd, legacy_root):
    g = resolve_global(cwd, legacy_root, _consumer="review_store")
    if g is None:
        return None, g
    legacy = os.path.join(g["dir"], FILENAMES["profile"])
    if os.path.isfile(legacy):
        return legacy, g
    return None, g


def _legacy_global_decisions(cwd, legacy_root):
    g = resolve_global(cwd, legacy_root, heal=False)
    if g is None:
        return None
    path = os.path.join(g["dir"], FILENAMES["decisions"])
    return path if os.path.isfile(path) else None


def _profile_anchor(cwd, legacy_root, registry_root=None):
    """Return (path, location, healed, entry_id) for the profile anchor, or Nones."""
    layer = _unified_in_repo(cwd)
    if layer:
        return layer, "in-repo", False, None
    legacy = _legacy_in_repo(cwd)
    if legacy:
        return legacy, "in-repo", False, None
    layer = _unified_global(cwd, registry_root)
    if layer:
        return layer, "global", False, None
    legacy, g = _legacy_global(cwd, legacy_root)
    if legacy:
        return legacy, "global", g["healed"], g["entry_id"]
    healed = g["healed"] if g else False
    eid = g["entry_id"] if g else None
    return None, "none", healed, eid


def _decisions_path(cwd, profile_path, location, legacy_root, registry_root=None):
    """Decisions: in-repo at .claude/; global prefers legacy-store copy, else co-locates."""
    if location == "in-repo":
        return os.path.join(_repo_root(cwd), ".claude", FILENAMES["decisions"])
    legacy_dec = _legacy_global_decisions(cwd, legacy_root)
    if legacy_dec:
        return legacy_dec
    unified = _unified_global(cwd, registry_root)
    if unified:
        return os.path.join(os.path.dirname(unified), FILENAMES["decisions"])
    return os.path.join(os.path.dirname(profile_path), FILENAMES["decisions"])


def create(cwd, kind, location, legacy_root=None, registry_root=None):
    """Return the path to write `kind` at `location`. Non-destructive: never
    truncates an existing profile/decisions file or overwrites an existing
    keys.json. Global unified profiles use the control-plane store (registry_root);
    legacy global decisions use the review-crew store (legacy_root)."""
    legacy_root = legacy_root or store_root()
    if location == "in-repo":
        if kind == "profile":
            d = os.path.join(cwd, UNIFIED_DIR)
            os.makedirs(d, exist_ok=True)
            return os.path.join(d, UNIFIED_LAYER)
        d = os.path.join(cwd, ".claude")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, FILENAMES[kind])
    if location != "global":
        raise ValueError(f"unknown location: {location}")

    if kind == "profile":
        import mode_registry
        store_dir = mode_registry.ensure_project_store(cwd, registry_root)
        if store_dir is None:
            raise OSError("could not ensure project store")
        d = os.path.join(store_dir, "config")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, UNIFIED_LAYER)

    unified = _unified_global(cwd, registry_root)
    if unified:
        d = os.path.dirname(unified)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, FILENAMES["decisions"])
    import mode_registry
    store_dir = mode_registry.ensure_project_store(cwd, registry_root)
    if store_dir:
        config_dir = os.path.join(store_dir, "config")
        if os.path.isdir(config_dir):
            return os.path.join(config_dir, FILENAMES["decisions"])

    ident = derive_identifiers(cwd)
    entry_id = ident["gitdir_hash"]
    entry_dir = os.path.join(legacy_root, "entries", entry_id)
    os.makedirs(entry_dir, exist_ok=True)
    if not os.path.exists(os.path.join(entry_dir, "keys.json")):
        write_keys_json(entry_dir, ident)
    write_pointer(legacy_root, ident["gitdir_hash"], entry_id)
    if ident["remote_hash"]:
        write_pointer(legacy_root, ident["remote_hash"], entry_id)
    return os.path.join(entry_dir, FILENAMES[kind])


def resolve(cwd, kind, legacy_root=None, registry_root=None):
    """Resolve `kind`'s path. Profile location follows unified layer, then legacy profile."""
    legacy_root = legacy_root or store_root()
    g = resolve_global(cwd, legacy_root, _consumer="review_store")
    anchor, location, healed, entry_id = _profile_anchor(cwd, legacy_root, registry_root)
    if anchor is None:
        return {"kind": kind, "path": None, "location": "none", "exists": False,
                "healed": g["healed"] if g else False,
                "entry_id": g["entry_id"] if g else None}

    if kind == "profile":
        path = anchor
    else:
        path = _decisions_path(cwd, anchor, location, legacy_root, registry_root)
    return {"kind": kind, "path": path, "location": location,
            "exists": os.path.exists(path), "healed": healed, "entry_id": entry_id}


def decide_location(env_value, interactive, cwd=None, root=None):
    """Where to create when nothing resolved — now band-wide registry-aware.
    Delegates the mode decision to the shared resolver so review-crew and test-pilot
    never diverge (CONVENTIONS §2.3/§2.4): env override wins, else the recorded/
    backfilled band mode, else (interactive) 'ask' / (headless) provisional 'global'.
    The lazy import avoids any import cycle with mode_registry; root defaults to the
    registry's own project store (NOT review-crew's store_root)."""
    import mode_registry
    return mode_registry.decide_mode(
        cwd if cwd is not None else os.getcwd(), env_value, interactive, root=root)


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
    legacy_root = store_root()
    try:
        if cmd == "resolve":
            kind = _parse_kv(args, "--kind") or "profile"
            if kind not in FILENAMES:
                sys.stderr.write(f"bad --kind: {kind}\n")
                return 2
            sys.stdout.write(json.dumps(resolve(os.getcwd(), kind, legacy_root)) + "\n")
            return 0
        if cmd == "create":
            kind = _parse_kv(args, "--kind") or "profile"
            location = _parse_kv(args, "--location")
            if kind not in FILENAMES or location not in ("global", "in-repo"):
                sys.stderr.write("usage: create --kind profile|decisions --location global|in-repo\n")
                return 2
            sys.stdout.write(
                create(os.getcwd(), kind, location, legacy_root=legacy_root) + "\n")
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
