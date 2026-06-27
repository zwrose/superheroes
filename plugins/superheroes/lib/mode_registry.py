#!/usr/bin/env python3
"""Band-wide storage-mode registry + resolver (CONVENTIONS §2.3/§2.4/§4.2/§6.2/§6.3).
Stdlib-only. The authoritative per-project mode record + the one shared resolver every
hero reads. Ships inert: this module is consumed by tests/CLI now, heroes/init later.
"""
import datetime
import fcntl
import json
import os
import subprocess
import sys
from contextlib import contextmanager

import control_plane
import store_core

SCHEMA_VERSION = 1
IN_REPO = "in-repo"
GLOBAL = "global"


def config_key(cwd):
    """§6.2 config-key: <remote-key> when a remote exists, else <common-dir-key>."""
    ident = store_core.derive_identifiers(cwd)
    return ident["remote_hash"] or ident["gitdir_hash"]


def project_store_dir(cwd, root=None):
    base = root or control_plane.store_root()
    return os.path.join(base, "projects", config_key(cwd))


@contextmanager
def config_lock_at(store_dir):
    """Advisory flock on an explicit store directory's config.lock (§4.4). Non-blocking
    try-acquire: yields True if acquired, False if held. OS-released when the fd closes.
    The location-keyed variant — the rebind locks the rebind-invariant <common-dir-key>
    store, which config_lock(cwd, root) (keyed on config_key) cannot address."""
    os.makedirs(store_dir, exist_ok=True)
    fd = os.open(os.path.join(store_dir, "config.lock"), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


def config_lock(cwd, root=None):
    """Advisory flock on the project store's config.lock (§4.4). Non-blocking
    try-acquire: yields True if acquired, False if held by another process.
    OS-released when the fd closes — a holder that dies leaves no stuck lock."""
    return config_lock_at(project_store_dir(cwd, root))


class UnknownSchemaVersion(Exception):
    pass


def registry_path(cwd, root=None):
    return os.path.join(project_store_dir(cwd, root), "registry.json")


def read_registry(cwd, root=None):
    """Valid record, or None if absent/corrupt/semantically-invalid. Raise
    UnknownSchemaVersion on a newer schemaVersion (fail-closed, NF2/UFR-4)."""
    try:
        with open(registry_path(cwd, root), encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict):
        return None
    # Order matters (UFR-3 corrupt→absent / UFR-4 / §6.3-6.4 fail-closed on unknown-newer):
    # a malformed/missing/bool/<1 schemaVersion is a corrupt record (→ absent), but a parseable
    # NEWER version must still RAISE (fail-closed), so the raise precedes the corrupt-shape returns.
    ver = rec.get("schemaVersion")
    # isinstance(True, int) is True in Python, so the explicit bool exclusion is required.
    if not isinstance(ver, int) or isinstance(ver, bool) or ver < 1:
        return None  # malformed/missing/bool/<1 → corrupt (UFR-3)
    if ver > SCHEMA_VERSION:
        raise UnknownSchemaVersion(
            f"registry.json schemaVersion={ver} is newer than {SCHEMA_VERSION} — "
            "update the plugin or migrate the file")
    if rec.get("storageMode") not in (IN_REPO, GLOBAL):
        return None  # parseable but invalid → corrupt (UFR-3)
    rk = rec.get("remoteKey")
    if rk is not None and not isinstance(rk, str):
        return None  # malformed remoteKey → corrupt (UFR-3)
    created = rec.get("createdAt")
    if not isinstance(created, str) or not created:
        return None  # missing/empty createdAt → corrupt (UFR-3)
    return rec


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_registry(cwd, mode, remote_key, root=None, allow_migration=False, now=None):
    """Record the authoritative mode under the config lock. Refuse to change an
    existing authoritative mode unless allow_migration (FR-3/UFR-1). Returns the
    record, or None if skipped (lock contended) or refused."""
    if mode not in (IN_REPO, GLOBAL):
        raise ValueError(f"invalid storageMode: {mode!r}")
    if ensure_project_store(cwd, root) is None:
        return None
    with config_lock(cwd, root) as got:
        if not got:
            return None  # NF5: another writer holds it — never block
        existing = read_registry(cwd, root)
        if existing and existing["storageMode"] != mode and not allow_migration:
            return None
        if existing and existing["storageMode"] == mode:
            return existing
        # Preserve an existing non-empty string createdAt; else stamp a new one. Gate on
        # PRESENCE not truthiness (a falsy stored value must not regenerate spuriously; with
        # the hardened read_registry a valid existing record already has a non-empty createdAt).
        created = (existing.get("createdAt")
                   if (existing and isinstance(existing.get("createdAt"), str)
                       and existing.get("createdAt"))
                   else (now or _utc_now()))
        rec = {"schemaVersion": SCHEMA_VERSION, "storageMode": mode,
               "remoteKey": remote_key, "createdAt": created}
        store_core.atomic_write(registry_path(cwd, root), json.dumps(rec, indent=2))
        return rec


# mode_registry owns the in-repo subpath + filename (the heroes keep them inline today);
# the GLOBAL store root is read from each hero's own store_root() via a deferred import.
_HERO_INREPO = {
    "review-crew": os.path.join(".claude", "review-profile.md"),
    "test-pilot": os.path.join(".claude", "test-pilot", "profile.md"),
}
_HERO_GLOBAL_FILENAME = {"review-crew": "review-profile.md", "test-pilot": "profile.md"}


def _hero_global_root(name):
    if name == "review-crew":
        import review_store
        return review_store.store_root()
    import store as test_pilot_store
    return test_pilot_store.store_root()


def _repo_root(cwd):
    out = store_core.run_git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if out else os.path.realpath(cwd)


def hero_evidence(cwd, root=None, hero_roots=None):
    """Pure read-only probe of each hero's calibration location. In-repo is anchored at
    the REPO ROOT; global is resolved read-only (resolve_global heal=False). Returns
    {hero: 'in-repo'|'global'|'none'}. hero_roots overrides each global root for tests."""
    repo = _repo_root(cwd)
    out = {}
    for name, subpath in _HERO_INREPO.items():
        if os.path.isfile(os.path.join(repo, subpath)):
            out[name] = IN_REPO
            continue
        groot = (hero_roots or {}).get(name) or _hero_global_root(name)
        g = store_core.resolve_global(cwd, groot, heal=False)
        if g and os.path.isfile(os.path.join(g["dir"], _HERO_GLOBAL_FILENAME[name])):
            out[name] = GLOBAL
        else:
            out[name] = "none"
    return out


def evidence_verdict(hero_locs):
    """Present-heroes-only: all-present-agree → that mode; ≥2 present in different modes
    → 'disagree'; none present → 'none' (greenfield)."""
    present = [v for v in hero_locs.values() if v != "none"]
    if not present:
        return "none"
    if all(v == present[0] for v in present):
        return present[0]
    return "disagree"


def resolve(cwd, root=None):
    """The shared band-wide mode resolver. Never blocks, never hits the network.
    Raises UnknownSchemaVersion on a newer record (fail-closed)."""
    rec = read_registry(cwd, root)
    if rec is not None:
        return {"mode": rec["storageMode"], "authoritative": True,
                "source": "registry", "evidence": None}
    verdict = evidence_verdict(hero_evidence(cwd, root))
    if verdict in (IN_REPO, GLOBAL):
        remote_hash = store_core.derive_identifiers(cwd)["remote_hash"]
        wrote = write_registry(cwd, verdict, remote_hash, root)  # best-effort (skips on lock contention/wedged store)
        if wrote is None:
            sys.stderr.write(
                f"mode_registry: backfill of {verdict!r} could not be persisted "
                "(store contended or unwritable); reporting non-authoritative\n")
        # mode stays the evidence verdict; authoritative reflects whether the write landed.
        return {"mode": verdict, "authoritative": wrote is not None,
                "source": "backfilled", "evidence": verdict}
    return {"mode": GLOBAL, "authoritative": False, "source": "provisional", "evidence": verdict}


def decide_mode(cwd, env_value, interactive, root=None):
    """Band-wide create-time mode decision (CONVENTIONS §2.3/§2.4). The single
    decision both heroes' decide_location delegate to, so review-crew and test-pilot
    never diverge. Precedence: env override → recorded/backfilled mode →
    (interactive ? 'ask' : provisional GLOBAL). Returns 'in-repo' | 'global' | 'ask'.
    Propagates UnknownSchemaVersion from resolve() so a newer registry fails closed
    (UFR-2); local-only and never blocks (UFR-3). The env path never records (UFR-7);
    a headless greenfield returns GLOBAL without recording (UFR-5)."""
    if env_value in (IN_REPO, GLOBAL):
        return env_value
    r = resolve(cwd, root)
    if r["source"] in ("registry", "backfilled"):
        return r["mode"]
    return "ask" if interactive else GLOBAL


def resolve_artifact(cwd, in_repo_path, global_path, root=None):
    """FR-6: an EXISTING artifact resolves to where it physically lives; a NEW artifact
    resolves by the recorded mode."""
    if os.path.exists(in_repo_path):
        return in_repo_path
    if os.path.exists(global_path):
        return global_path
    return in_repo_path if resolve(cwd, root)["mode"] == IN_REPO else global_path


def ensure_project_store(cwd, root=None):
    """Create the per-project store (git repo + meta.json). Idempotent and safe under
    concurrent first-touch by parallel worktrees (§4.2): makedirs(exist_ok), guarded
    git-init (a racing re-init is harmless), atomic meta.json. Returns dir or None."""
    d = project_store_dir(cwd, root)
    try:
        os.makedirs(d, exist_ok=True)
        if not os.path.isdir(os.path.join(d, ".git")):
            r = subprocess.run(["git", "-C", d, "init", "-q"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0 and not os.path.isdir(os.path.join(d, ".git")):
                return None
        meta = os.path.join(d, "meta.json")
        if not os.path.isfile(meta):
            store_core.atomic_write(meta, json.dumps({"schemaVersion": SCHEMA_VERSION}))
        return d
    except (OSError, subprocess.SubprocessError):
        return None
