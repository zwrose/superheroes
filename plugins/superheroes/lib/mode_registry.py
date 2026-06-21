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
def config_lock(cwd, root=None):
    """Advisory flock on the project store's config.lock (§4.4). Non-blocking
    try-acquire: yields True if acquired, False if held by another process.
    OS-released when the fd closes — a holder that dies leaves no stuck lock."""
    d = project_store_dir(cwd, root)
    os.makedirs(d, exist_ok=True)
    fd = os.open(os.path.join(d, "config.lock"), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


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
