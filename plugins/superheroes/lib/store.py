#!/usr/bin/env python3
"""test-pilot storage resolver + artifact key derivation.

artifact_key() is THE one key-derivation function for every artifact name
that embeds branch+slot identity (manifests, plan records, fallback files,
comment markers). Injective: % is encoded before /, and the slot delimiter ~
is illegal in git refnames, so distinct (branch, slot) pairs never collide.

The two-key pointer + self-heal resolution algorithm lives in store_core.py;
this module is the test-pilot-specific adapter on top.
"""
import json
import os
import re
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
    atomic_write,
    run_git,
)

SLOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# The ONE definition of the machine-readable calibration block (```json test-pilot-config```).
# Both resolve()'s layer presence gate (here) and engine.load_profile_config match this exact
# pattern — engine imports store (never the reverse), so sharing it here keeps the edge
# one-directional while the store's gate can never drift from what the engine parses (#412).
CONFIG_BLOCK_RE = re.compile(r"```json\s+test-pilot-config\s*\n(.*?)\n```", re.S)


def has_config_block(text):
    """True when `text` carries the fenced ```json test-pilot-config``` block."""
    return CONFIG_BLOCK_RE.search(text) is not None


def sanitize_branch(branch):
    if not isinstance(branch, str) or not branch.strip():
        raise ValueError("empty branch name")
    return branch.replace("%", "%25").replace("/", "%2F")


def artifact_key(branch, slot=None):
    if slot is not None and not SLOT_RE.match(slot):
        raise ValueError(
            f"invalid slot {slot!r}: must match {SLOT_RE.pattern}")
    key = sanitize_branch(branch)
    return f"{key}~{slot}" if slot is not None else key


def get_repo_root(cwd):
    """Return the git worktree top-level for cwd (fallback: cwd itself)."""
    out = run_git(cwd, "rev-parse", "--show-toplevel")
    if out:
        return os.path.realpath(out)
    return os.path.realpath(cwd)


def store_root():
    return os.path.realpath(os.path.expanduser(
        os.environ.get("TEST_PILOT_STORE_ROOT", "~/.claude/test-pilot")))

# Re-export TEST_PILOT_STORE_ROOT as a sentinel name callers may use.
TEST_PILOT_STORE_ROOT = "~/.claude/test-pilot"


def _entry_dirs(entry_dir):
    return {"blocks_dir": os.path.join(entry_dir, "blocks"),
            "manifests_dir": os.path.join(entry_dir, "manifests"),
            "plans_dir": os.path.join(entry_dir, "plans"),
            "state_dir": os.path.join(entry_dir, "state")}


def _in_repo_layer(repo_root):
    """Physical in-repo path to the unified calibration layer (#412), or None if absent.
    Same convention core_md/calibration_resolve use for the in-repo layer — a direct
    file probe, so this read path never triggers a mode_registry backfill WRITE."""
    p = os.path.join(repo_root, ".claude", "superheroes", "test-pilot.md")
    return p if os.path.isfile(p) else None


def _global_layer(cwd):
    """Physical out-of-repo (project store) path to the unified layer (#412), or None.
    Mode-aware via mode_registry.project_store_dir (mirrors core_md.core_path's global
    branch and calibration_resolve._unified_global_layer) — never a hardcoded ~/.claude
    path. Always the real control-plane project store: resolve()'s `root` is TEST-PILOT's
    store root, not the superheroes core store base, so it must not be threaded here."""
    import mode_registry
    p = os.path.join(mode_registry.project_store_dir(cwd), "config", "test-pilot.md")
    return p if os.path.isfile(p) else None


def _layer_has_config_block(path):
    """True when the layer file carries the ```json test-pilot-config``` block — the exact
    block the engine parses (CONFIG_BLOCK_RE above, shared with engine.load_profile_config
    so this presence gate can never drift from what the engine extracts downstream). A layer
    with only prose (no block) is genuinely un-calibrated for the engine → resolve() falls
    through to `location: none` (epic #327: "missing calibration" must mean calibration is
    actually missing)."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        # A present-but-unreadable layer must not silently masquerade as greenfield
        # (the legacy profile.md path surfaces read errors via load_profile_config;
        # this gate reads earlier, so at least leave a trace on stderr).
        sys.stderr.write(f"test-pilot store: calibration layer {path} exists but "
                         f"could not be read ({exc}); treating as no calibration\n")
        return False
    return has_config_block(text)


def resolve(cwd, root):
    """Resolve all artifact locations. Location keys on the PROFILE source, in precedence
    order: legacy in-repo profile.md → legacy global-entry profile.md → the unified
    calibration layer (.claude/superheroes/test-pilot.md, in-repo then out-of-repo project
    store) → none. `profileSource` names the winner: `profile-md` | `layer` | `none`.

    Legacy profile.md wins when present so un-migrated projects keep working byte-identically;
    the layer is the new primary for projects the calibration migration moved (#412 —
    `core_md migrate --hero test-pilot` deletes profile.md after copying the same
    `test-pilot-config` block into the layer). blocks_dir/manifests_dir follow the mode the
    winning source physically lives in. plans_dir/state_dir ALWAYS point into the global
    entry (machine-local)."""
    repo_root = get_repo_root(cwd)
    ident = derive_identifiers(cwd)
    g = resolve_global(cwd, root, _consumer="test_pilot store")
    entry_id = g["entry_id"] if g else ident["gitdir_hash"]
    entry_dir = os.path.join(root, "entries", entry_id)
    machine = {k: v for k, v in _entry_dirs(entry_dir).items()
               if k in ("plans_dir", "state_dir")}

    in_repo = os.path.join(repo_root, ".claude", "test-pilot")
    if os.path.exists(os.path.join(in_repo, "profile.md")):
        return {"location": "in-repo", "exists": True, "entry_id": entry_id,
                "profile": os.path.join(in_repo, "profile.md"),
                "profileSource": "profile-md",
                "blocks_dir": os.path.join(in_repo, "blocks"),
                "manifests_dir": os.path.join(in_repo, "manifests"),
                **machine}
    if g is not None and os.path.exists(os.path.join(g["dir"], "profile.md")):
        d = _entry_dirs(g["dir"])
        return {"location": "global", "exists": True, "entry_id": g["entry_id"],
                "profile": os.path.join(g["dir"], "profile.md"),
                "profileSource": "profile-md", **d}
    # #412: migrated projects carry calibration in the unified layer, not profile.md. The
    # layer is the calibration SSOT; read the same config block from it (in-repo first, then
    # the out-of-repo project store). blocks/manifests follow the mode the layer lives in.
    layer = _in_repo_layer(repo_root)
    if layer is not None and _layer_has_config_block(layer):
        return {"location": "in-repo", "exists": True, "entry_id": entry_id,
                "profile": layer, "profileSource": "layer",
                "blocks_dir": os.path.join(in_repo, "blocks"),
                "manifests_dir": os.path.join(in_repo, "manifests"),
                **machine}
    layer = _global_layer(cwd)
    if layer is not None and _layer_has_config_block(layer):
        e_dir = g["dir"] if g is not None else entry_dir
        e_id = g["entry_id"] if g is not None else entry_id
        d = _entry_dirs(e_dir)
        return {"location": "global", "exists": True, "entry_id": e_id,
                "profile": layer, "profileSource": "layer", **d}
    return {"location": "none", "exists": False, "entry_id": entry_id,
            "profile": None, "profileSource": "none",
            "blocks_dir": None, "manifests_dir": None,
            **machine}


def create(cwd, location, root):
    """Create the directory skeleton for `location` and ALWAYS mint the global
    entry (state/plans live there in both modes). Non-destructive. Returns the
    same dict shape as resolve()."""
    repo_root = get_repo_root(cwd)
    ident = derive_identifiers(cwd)
    # Reuse an existing live entry if one already exists (avoids orphaning
    # applied state when a second clone creates a fresh gitdir-hash entry).
    existing = resolve_global(cwd, root, _consumer="test_pilot store")
    if existing is not None:
        entry_id = existing["entry_id"]
        entry_dir = existing["dir"]
    else:
        entry_id = ident["gitdir_hash"]
        entry_dir = os.path.join(root, "entries", entry_id)
    os.makedirs(entry_dir, exist_ok=True)
    if not os.path.exists(os.path.join(entry_dir, "keys.json")):
        write_keys_json(entry_dir, ident)
    write_pointer(root, ident["gitdir_hash"], entry_id)
    if ident["remote_hash"]:
        write_pointer(root, ident["remote_hash"], entry_id)
    d = _entry_dirs(entry_dir)
    os.makedirs(d["plans_dir"], exist_ok=True)
    os.makedirs(d["state_dir"], exist_ok=True)

    # #428: a MIGRATED project's calibration lives in the unified layer — create() must
    # point callers (test-pilot-init Step 6 writes the profile at this path) AT THE LAYER,
    # never back at the legacy .claude/test-pilot/profile.md. Re-minting the legacy file on
    # a migrated project re-arms core_md.migrate_on_read inside build worktrees — the exact
    # chain that committed a destructive layer deletion (weekly-eats 9dad0f6). Only a
    # genuinely un-migrated project (no layer with a config block) still scaffolds at the
    # legacy path, byte-identical to before.
    if location == "in-repo":
        base = os.path.join(repo_root, ".claude", "test-pilot")
        blocks, manifests = (os.path.join(base, "blocks"),
                             os.path.join(base, "manifests"))
        os.makedirs(blocks, exist_ok=True)
        os.makedirs(manifests, exist_ok=True)
        legacy = os.path.join(base, "profile.md")
        layer = _in_repo_layer(repo_root)
        if (not os.path.exists(legacy)  # a still-present legacy keeps resolve()'s precedence
                and layer is not None and _layer_has_config_block(layer)):
            profile, profile_source = layer, "layer"
        else:
            profile, profile_source = legacy, "profile-md"
    elif location == "global":
        os.makedirs(d["blocks_dir"], exist_ok=True)
        os.makedirs(d["manifests_dir"], exist_ok=True)
        blocks, manifests = d["blocks_dir"], d["manifests_dir"]
        legacy = os.path.join(entry_dir, "profile.md")
        layer = _global_layer(cwd)
        if (not os.path.exists(legacy)  # a still-present legacy keeps resolve()'s precedence
                and layer is not None and _layer_has_config_block(layer)):
            profile, profile_source = layer, "layer"
        else:
            profile, profile_source = legacy, "profile-md"
    else:
        raise ValueError(f"unknown location: {location}")
    return {"location": location, "exists": os.path.exists(profile),
            "entry_id": entry_id, "profile": profile, "profileSource": profile_source,
            "blocks_dir": blocks, "manifests_dir": manifests,
            "plans_dir": d["plans_dir"], "state_dir": d["state_dir"]}


def decide_location(env_value, interactive, cwd=None, root=None):
    """Band-wide registry-aware create-time decision (CONVENTIONS §2.3/§2.4): env
    override wins, else the recorded/backfilled band mode, else (interactive) 'ask' /
    (headless) provisional 'global'. Delegates to the one shared resolver so
    test-pilot and review-crew never diverge. Lazy import avoids an import cycle;
    root defaults to the registry's own project store (NOT test-pilot's store_root)."""
    import mode_registry
    return mode_registry.decide_mode(
        cwd if cwd is not None else os.getcwd(), env_value, interactive, root=root)


def _parse_kv(args, flag, default=None):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            return args[i + 1]
    return default


def main(argv):
    args = argv[1:]
    if not args:
        sys.stderr.write(
            "Usage: store.py resolve|create|decide-location|key ...\n")
        return 2
    cmd = args[0]
    try:
        if cmd == "resolve":
            sys.stdout.write(json.dumps(resolve(os.getcwd(), store_root())) + "\n")
            return 0
        if cmd == "create":
            location = _parse_kv(args, "--location")
            if location not in ("global", "in-repo"):
                sys.stderr.write("usage: create --location global|in-repo\n")
                return 2
            sys.stdout.write(
                json.dumps(create(os.getcwd(), location, store_root())) + "\n")
            return 0
        if cmd == "decide-location":
            interactive = _parse_kv(args, "--interactive") != "false"
            sys.stdout.write(decide_location(
                os.environ.get("TEST_PILOT_STORAGE"), interactive) + "\n")
            return 0
        if cmd == "key":
            branch = _parse_kv(args, "--branch")
            if not branch:
                sys.stderr.write("usage: key --branch B [--slot S]\n")
                return 2
            sys.stdout.write(artifact_key(branch, _parse_kv(args, "--slot")) + "\n")
            return 0
    except Exception as exc:
        sys.stderr.write(f"store error: {exc}\n")
        return 1
    sys.stderr.write(f"unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
