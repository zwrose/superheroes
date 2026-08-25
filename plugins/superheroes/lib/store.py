#!/usr/bin/env python3
"""test-pilot storage resolver + artifact key derivation.

artifact_key() is THE one key-derivation function for every artifact name
that embeds branch+slot identity (manifests, plan records, fallback files,
comment markers). Injective: % is encoded before /, and the slot delimiter ~
is illegal in git refnames, so distinct (branch, slot) pairs never collide.

The two-key pointer + self-heal resolution algorithm lives in store_core.py;
this module is the test-pilot-specific adapter on top.
"""
import collections
import json
import os
import re
import stat
import sys

import core_md
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
    repo_root,
    PointerUnreadable,
)

LAYER_OK = "ok"
LAYER_ABSENT = "absent"
LAYER_UNREADABLE = "unreadable"
LayerResult = collections.namedtuple("LayerResult", "has_block status detail")

STORE_REASON_LAYER_UNREADABLE = "test-pilot-layer-unreadable"
STORE_REASON_POINTER_UNREADABLE = "test-pilot-store-pointer-unreadable"


class LayerUnreadable(Exception):
    """A calibration layer candidate exists but could not be read — refuse before mutating."""

    def __init__(self, path, status, detail, *, reason=STORE_REASON_LAYER_UNREADABLE):
        super().__init__("%s: %s" % (reason, detail))
        self.path = path
        self.status = status
        self.detail = detail
        self.reason = reason

SLOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\Z")

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
    """Return the git worktree top-level for cwd.

    Raises RepoRootUnavailable when the root cannot be determined fail-closed.
    Returns realpath(cwd) only for genuine greenfield (no .git ancestor)."""
    return repo_root(cwd)


def store_root():
    return os.path.realpath(os.path.expanduser(
        os.environ.get("TEST_PILOT_STORE_ROOT", "~/.claude/test-pilot")))

# Re-export TEST_PILOT_STORE_ROOT as a sentinel name callers may use.
TEST_PILOT_STORE_ROOT = "~/.claude/test-pilot"


def _entry_dirs(entry_dir):
    return {"blocks_dir": os.path.join(entry_dir, "blocks"),
            "manifests_dir": os.path.join(entry_dir, "manifests"),
            "plans_dir": os.path.join(entry_dir, "plans"),
            "state_dir": os.path.join(entry_dir, "state"),
            "artifacts_dir": os.path.join(entry_dir, "artifacts")}


def _legacy_in_repo_profile_path(repo_root):
    return os.path.join(repo_root, ".claude", "test-pilot", "profile.md")


def _legacy_global_profile_path(g):
    return os.path.join(g["dir"], "profile.md")


def _in_repo_layer_path(repo_root):
    return os.path.join(repo_root, ".claude", "superheroes", "test-pilot.md")


def _global_layer_path(cwd):
    import mode_registry  # lazy: mode_registry lazily imports store (decide_mode path)
    return os.path.join(mode_registry.project_store_dir(cwd), "config", "test-pilot.md")


def candidate_profile_paths(cwd, root):
    """The ordered profile-source candidates resolve() considers, existing or not."""
    repo_root_path = get_repo_root(cwd)
    candidates = [_legacy_in_repo_profile_path(repo_root_path)]
    g = resolve_global(cwd, root, _consumer="test_pilot store")
    if g is not None:
        candidates.append(_legacy_global_profile_path(g))
    candidates.append(_in_repo_layer_path(repo_root_path))
    candidates.append(_global_layer_path(cwd))
    return candidates


def classify_layer_config_block(path):
    """Classify a calibration-layer candidate. Never raises."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        try:
            os.lstat(path)
        except FileNotFoundError:
            return LayerResult(False, LAYER_ABSENT, None)
        except OSError as exc:
            return LayerResult(
                False,
                LAYER_UNREADABLE,
                "lstat failed at %s: %s" % (path, exc),
            )
        return LayerResult(
            False,
            LAYER_UNREADABLE,
            "dangling symlink at %s" % path,
        )
    except OSError as exc:
        return LayerResult(
            False,
            LAYER_UNREADABLE,
            core_md.gate_refusal_detail(exc, at=path),
        )

    if not stat.S_ISREG(st.st_mode):
        return LayerResult(
            False,
            LAYER_UNREADABLE,
            "not a regular file at %s" % path,
        )

    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return LayerResult(
            False,
            LAYER_UNREADABLE,
            "layer existed at stat but was missing at open (read race) at %s" % path,
        )
    except OSError as exc:
        return LayerResult(
            False,
            LAYER_UNREADABLE,
            core_md.gate_refusal_detail(exc, at=path, verb="opening"),
        )
    except UnicodeDecodeError as exc:
        return LayerResult(
            False,
            LAYER_UNREADABLE,
            "UTF-8 decode failed at %s: %s" % (path, exc),
        )

    return LayerResult(has_config_block(text), LAYER_OK, None)


def _layer_refusal(path, detail, *, source):
    return dict(
        core_md.gate_refusal(STORE_REASON_LAYER_UNREADABLE, detail),
        path=path,
        source=source,
    )


def _pointer_refusal(exc):
    return dict(
        core_md.gate_refusal(
            STORE_REASON_POINTER_UNREADABLE,
            exc.detail if exc.detail is not None else str(exc),
        ),
        path=exc.path,
    )


def _raise_layer_unreadable(path, result, *, reason=STORE_REASON_LAYER_UNREADABLE):
    raise LayerUnreadable(path, result.status, result.detail, reason=reason)


def _none_resolve(entry_id, machine, refusal=None):
    return {"location": "none", "exists": False, "entry_id": entry_id,
            "profile": None, "profileSource": "none",
            "blocks_dir": None, "manifests_dir": None,
            "refusal": refusal,
            **machine}


def resolve(cwd, root):
    """Resolve all artifact locations. Location keys on the PROFILE source, in precedence
    order: legacy in-repo profile.md → legacy global-entry profile.md → the unified
    calibration layer (.claude/superheroes/test-pilot.md, in-repo then out-of-repo project
    store) → none. `profileSource` names the winner: `profile-md` | `layer` | `none`.

    Legacy profile.md wins when present so un-migrated projects keep working byte-identically;
    the layer is the new primary for migrated projects (#412 — profile.md copied into the
    layer). The core_md migration path that deleted profile.md was removed (#724); a legacy
    profile.md now produces a named refusal via core_md.resolve_shared. blocks_dir/manifests_dir
    follow the mode the
    winning source physically lives in. plans_dir/state_dir/artifacts_dir ALWAYS point into the global
    entry (machine-local)."""
    repo_root = get_repo_root(cwd)
    ident = derive_identifiers(cwd)
    try:
        g = resolve_global(cwd, root, _consumer="test_pilot store", strict=True)
    except PointerUnreadable as exc:
        entry_id = ident["gitdir_hash"]
        entry_dir = os.path.join(root, "entries", entry_id)
        machine = {k: v for k, v in _entry_dirs(entry_dir).items()
                   if k in ("plans_dir", "state_dir", "artifacts_dir")}
        return _none_resolve(entry_id, machine, _pointer_refusal(exc))
    entry_id = g["entry_id"] if g else ident["gitdir_hash"]
    entry_dir = os.path.join(root, "entries", entry_id)
    machine = {k: v for k, v in _entry_dirs(entry_dir).items()
               if k in ("plans_dir", "state_dir", "artifacts_dir")}

    legacy_in_repo = _legacy_in_repo_profile_path(repo_root)
    in_repo = os.path.dirname(legacy_in_repo)
    legacy_in_repo_result = classify_layer_config_block(legacy_in_repo)
    if legacy_in_repo_result.status == LAYER_UNREADABLE:
        return _none_resolve(
            entry_id, machine,
            _layer_refusal(
                legacy_in_repo, legacy_in_repo_result.detail, source="profile-md"))
    if legacy_in_repo_result.status == LAYER_OK:
        return {"location": "in-repo", "exists": True, "entry_id": entry_id,
                "profile": legacy_in_repo,
                "profileSource": "profile-md",
                "blocks_dir": os.path.join(in_repo, "blocks"),
                "manifests_dir": os.path.join(in_repo, "manifests"),
                "refusal": None,
                **machine}
    if g is not None:
        legacy_global = _legacy_global_profile_path(g)
        legacy_global_result = classify_layer_config_block(legacy_global)
        if legacy_global_result.status == LAYER_UNREADABLE:
            return _none_resolve(
                entry_id, machine,
                _layer_refusal(
                    legacy_global, legacy_global_result.detail, source="profile-md"))
        if legacy_global_result.status == LAYER_OK:
            d = _entry_dirs(g["dir"])
            return {"location": "global", "exists": True, "entry_id": g["entry_id"],
                    "profile": legacy_global,
                    "profileSource": "profile-md", "refusal": None, **d}
    # #412: migrated projects carry calibration in the unified layer, not profile.md. The
    # layer is the calibration SSOT; read the same config block from it (in-repo first, then
    # the out-of-repo project store). blocks/manifests follow the mode the layer lives in.
    in_repo_layer = _in_repo_layer_path(repo_root)
    in_repo_layer_result = classify_layer_config_block(in_repo_layer)
    if in_repo_layer_result.status == LAYER_UNREADABLE:
        return _none_resolve(
            entry_id, machine,
            _layer_refusal(
                in_repo_layer, in_repo_layer_result.detail, source="layer"))
    if in_repo_layer_result.status == LAYER_OK and in_repo_layer_result.has_block:
        return {"location": "in-repo", "exists": True, "entry_id": entry_id,
                "profile": in_repo_layer, "profileSource": "layer",
                "blocks_dir": os.path.join(in_repo, "blocks"),
                "manifests_dir": os.path.join(in_repo, "manifests"),
                "refusal": None,
                **machine}
    global_layer = _global_layer_path(cwd)
    global_layer_result = classify_layer_config_block(global_layer)
    if global_layer_result.status == LAYER_UNREADABLE:
        return _none_resolve(
            entry_id, machine,
            _layer_refusal(
                global_layer, global_layer_result.detail, source="layer"))
    if global_layer_result.status == LAYER_OK and global_layer_result.has_block:
        e_dir = g["dir"] if g is not None else entry_dir
        e_id = g["entry_id"] if g is not None else entry_id
        d = _entry_dirs(e_dir)
        return {"location": "global", "exists": True, "entry_id": e_id,
                "profile": global_layer, "profileSource": "layer",
                "refusal": None, **d}
    return _none_resolve(entry_id, machine, None)


def create(cwd, location, root):
    """Create the directory skeleton for `location` and ALWAYS mint the global
    entry (state/plans live there in both modes). Non-destructive. Returns the
    same dict shape as resolve(). On a MIGRATED project (a unified layer carrying
    the test-pilot-config block, no legacy profile.md anywhere resolve() would
    prefer) `profile` points at the LAYER (profileSource "layer"); otherwise it
    is the legacy scaffold path (profileSource "profile-md") — which create()
    never writes (#428)."""
    repo_root = get_repo_root(cwd)
    ident = derive_identifiers(cwd)
    try:
        existing = resolve_global(cwd, root, _consumer="test_pilot store", strict=True)
    except PointerUnreadable as exc:
        _raise_layer_unreadable(
            exc.path, LayerResult(False, exc.status, exc.detail),
            reason=STORE_REASON_POINTER_UNREADABLE)

    legacy_in_repo = _legacy_in_repo_profile_path(repo_root)
    legacy_in_repo_result = classify_layer_config_block(legacy_in_repo)
    if legacy_in_repo_result.status == LAYER_UNREADABLE:
        _raise_layer_unreadable(legacy_in_repo, legacy_in_repo_result)

    if existing is not None:
        entry_id = existing["entry_id"]
        entry_dir = existing["dir"]
    else:
        entry_id = ident["gitdir_hash"]
        entry_dir = os.path.join(root, "entries", entry_id)

    # #428/#724: classify the global-entry legacy candidate unconditionally (using the same
    # entry_dir fallback as pre-#782), so a surviving entry dir with profile.md but no key
    # pointer keeps resolve()'s legacy-first precedence — create() must not hand back the
    # layer while the engine keeps reading the legacy.
    legacy_global = os.path.join(entry_dir, "profile.md")
    legacy_global_result = classify_layer_config_block(legacy_global)
    if legacy_global_result.status == LAYER_UNREADABLE:
        _raise_layer_unreadable(legacy_global, legacy_global_result)

    in_repo_layer = _in_repo_layer_path(repo_root)
    in_repo_layer_result = classify_layer_config_block(in_repo_layer)
    if in_repo_layer_result.status == LAYER_UNREADABLE:
        _raise_layer_unreadable(in_repo_layer, in_repo_layer_result)

    global_layer = _global_layer_path(cwd)
    global_layer_result = classify_layer_config_block(global_layer)
    if global_layer_result.status == LAYER_UNREADABLE:
        _raise_layer_unreadable(global_layer, global_layer_result)

    legacy_anywhere = (
        legacy_in_repo_result.status == LAYER_OK
        or (legacy_global_result is not None
            and legacy_global_result.status == LAYER_OK))

    if existing is not None:
        entry_id = existing["entry_id"]
        entry_dir = existing["dir"]
    else:
        entry_id = ident["gitdir_hash"]
        entry_dir = os.path.join(root, "entries", entry_id)

    if location == "in-repo":
        base = os.path.join(repo_root, ".claude", "test-pilot")
        blocks, manifests = (os.path.join(base, "blocks"),
                             os.path.join(base, "manifests"))
        legacy = os.path.join(base, "profile.md")
        layer_path = in_repo_layer
        layer_result = in_repo_layer_result
    elif location == "global":
        d_pre = _entry_dirs(entry_dir)
        blocks, manifests = d_pre["blocks_dir"], d_pre["manifests_dir"]
        legacy = os.path.join(entry_dir, "profile.md")
        layer_path = global_layer
        layer_result = global_layer_result
    else:
        raise ValueError(f"unknown location: {location}")

    if not legacy_anywhere and layer_result.status == LAYER_OK and layer_result.has_block:
        profile, profile_source = layer_path, "layer"
    else:
        profile, profile_source = legacy, "profile-md"

    os.makedirs(entry_dir, exist_ok=True)
    if not os.path.exists(os.path.join(entry_dir, "keys.json")):
        write_keys_json(entry_dir, ident)
    write_pointer(root, ident["gitdir_hash"], entry_id)
    if ident["remote_hash"]:
        write_pointer(root, ident["remote_hash"], entry_id)
    d = _entry_dirs(entry_dir)
    os.makedirs(d["plans_dir"], exist_ok=True)
    os.makedirs(d["state_dir"], exist_ok=True)
    # Do not makedirs artifacts_dir here — pilot_artifacts creates it with 0o700; a
    # directory pre-created under the ambient umask would be 0o755 and refused.

    if location == "in-repo":
        os.makedirs(blocks, exist_ok=True)
        os.makedirs(manifests, exist_ok=True)
    elif location == "global":
        os.makedirs(d["blocks_dir"], exist_ok=True)
        os.makedirs(d["manifests_dir"], exist_ok=True)

    return {"location": location, "exists": os.path.exists(profile),
            "entry_id": entry_id, "profile": profile, "profileSource": profile_source,
            "blocks_dir": blocks, "manifests_dir": manifests,
            "plans_dir": d["plans_dir"], "state_dir": d["state_dir"],
            "artifacts_dir": d["artifacts_dir"]}


def decide_location(env_value, cwd=None, root=None):
    """Band-wide registry-aware create-time decision (CONVENTIONS §2.3/§2.4): env
    override wins, else the recorded/backfilled band mode, else provisional 'global'
    with provisional=True. Returns a dict {"mode", "source", "provisional"}. Delegates
    to the one shared resolver so test-pilot and review-crew never diverge. Lazy import
    avoids an import cycle; root defaults to the registry's own project store (NOT
    test-pilot's store_root)."""
    import mode_registry
    return mode_registry.decide_mode(
        cwd if cwd is not None else os.getcwd(), env_value, root=root)


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
            result = resolve(os.getcwd(), store_root())
            sys.stdout.write(json.dumps(result) + "\n")
            return 1 if result.get("refusal") is not None else 0
        if cmd == "create":
            location = _parse_kv(args, "--location")
            if location not in ("global", "in-repo"):
                sys.stderr.write("usage: create --location global|in-repo\n")
                return 2
            sys.stdout.write(
                json.dumps(create(os.getcwd(), location, store_root())) + "\n")
            return 0
        if cmd == "decide-location":
            if "--interactive" in args:
                sys.stderr.write(
                    "decide-location: --interactive was removed (#1136); omit the flag\n")
                return 2
            sys.stdout.write(json.dumps(
                decide_location(os.environ.get("TEST_PILOT_STORAGE"))) + "\n")
            return 0
        if cmd == "key":
            branch = _parse_kv(args, "--branch")
            if not branch:
                sys.stderr.write("usage: key --branch B [--slot S]\n")
                return 2
            sys.stdout.write(artifact_key(branch, _parse_kv(args, "--slot")) + "\n")
            return 0
    except LayerUnreadable as exc:
        sys.stdout.write(json.dumps(core_md.gate_refusal(exc.reason, exc.detail)) + "\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"store error: {exc}\n")
        return 1
    sys.stderr.write(f"unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
