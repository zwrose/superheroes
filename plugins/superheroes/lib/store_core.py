#!/usr/bin/env python3
"""Shared two-key pointer + self-heal resolution algorithm.

Extracted from store.py (test-pilot) and review_store.py (review-crew).
Both consumers implemented the same algorithm; this module is the single
authoritative copy. Each consumer keeps its own public surface (store-root
constants, kind-keyed resolve/create, artifact_key, etc.).

Stdlib-only; no third-party dependencies.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile


def normalize_remote(url):
    """Normalize a remote URL to host/path. None for empty/unparseable.

    Lowercases the host, drops scheme/userinfo/port, strips trailing .git
    and slashes. Handles scp-style (git@host:org/repo.git) and scheme URLs.
    """
    if not url:
        return None
    s = url.strip()
    if not s:
        return None
    # scp-like: git@host:org/repo.git
    m = re.match(r"^[^@/]+@([^:/]+):(.+)$", s)
    if m:
        host, path = m.group(1), m.group(2)
    else:
        # scheme://[user@]host[:port]/path
        m = re.match(
            r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/]+@)?([^:/]+)(?::\d+)?/(.+)$", s)
        if m:
            host, path = m.group(1), m.group(2)
        else:
            return None
    host = host.lower()
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host}/{path.strip('/')}"


def short_hash(s):
    """First 16 hex chars of sha256(s.encode('utf-8'))."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def run_git(cwd, *args):
    """Run git with an argv array + timeout. Return stdout (stripped) or None."""
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def get_remote(cwd):
    """Normalized origin URL, or None."""
    return normalize_remote(run_git(cwd, "remote", "get-url", "origin"))


def get_gitdir(cwd):
    """realpath of the git-common-dir (shared by all worktrees).

    Falls back to --absolute-git-dir for git < 2.31, then to realpath(cwd)
    for non-git dirs.
    """
    out = run_git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if out is None:
        out = run_git(cwd, "rev-parse", "--absolute-git-dir")
    return os.path.realpath(out if out is not None else cwd)


def derive_identifiers(cwd):
    """Return dict with remote, gitdir, remote_hash, gitdir_hash for cwd."""
    remote = get_remote(cwd)
    gitdir = get_gitdir(cwd)
    return {
        "remote": remote,
        "gitdir": gitdir,
        "remote_hash": short_hash(remote) if remote else None,
        "gitdir_hash": short_hash(gitdir),
    }


def atomic_write(path, text, tmp_prefix=".store-core."):
    """Write text atomically via temp file + os.replace in the same directory."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=tmp_prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_pointer(root, key_hash):
    """Read the entry-id stored at root/keys/<key_hash>. None if absent/empty."""
    try:
        with open(os.path.join(root, "keys", key_hash)) as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def write_pointer(root, key_hash, entry_id):
    """Atomically write entry_id to root/keys/<key_hash>."""
    atomic_write(os.path.join(root, "keys", key_hash), entry_id)


def write_keys_json(entry_dir, ident):
    """Write a keys.json snapshot of ident into entry_dir (atomic)."""
    atomic_write(os.path.join(entry_dir, "keys.json"),
                 json.dumps({
                     "remote": ident["remote"],
                     "gitdir": ident["gitdir"],
                     "remote_hash": ident["remote_hash"],
                     "gitdir_hash": ident["gitdir_hash"],
                 }, indent=2))


def resolve_global(cwd, root, _consumer="store_core"):
    """Find the live global entry for cwd via key pointers (remote preferred),
    self-healing dangling/stale pointers.

    Returns {entry_id, dir, healed} or None if no live entry exists.
    This is the shared algorithm used by both test-pilot (store.py) and
    review-crew (review_store.py).
    """
    ident = derive_identifiers(cwd)
    rh, gh = ident["remote_hash"], ident["gitdir_hash"]
    p_remote = read_pointer(root, rh) if rh else None
    p_gitdir = read_pointer(root, gh)

    # Candidate entry-ids in preference order (remote first), deduped.
    candidates = []
    for c in (p_remote, p_gitdir):
        if c and c not in candidates:
            candidates.append(c)
    if not candidates:
        return None

    # Resolve to a LIVE entry: first candidate whose entry dir exists.
    # A dangling pointer (entry dir deleted out of band) falls through to the
    # other; if none is live, treat as absent.
    entry_id = next(
        (c for c in candidates
         if os.path.isdir(os.path.join(root, "entries", c))), None)
    if entry_id is None:
        return None

    # Warn only on a GENUINE conflict: both keys point at live-but-different
    # entries. A mere dangling pointer is routine self-heal, not a conflict.
    if (p_remote and p_gitdir and p_remote != p_gitdir
            and os.path.isdir(os.path.join(root, "entries", p_remote))
            and os.path.isdir(os.path.join(root, "entries", p_gitdir))):
        sys.stderr.write(
            f"{_consumer}: key disagreement — both keys point at live but "
            "different entries; preferring the remote-keyed entry\n")

    # Self-heal: point both available keys at the chosen live entry.
    healed = False
    if gh and p_gitdir != entry_id:
        write_pointer(root, gh, entry_id)
        healed = True
    if rh and p_remote != entry_id:
        write_pointer(root, rh, entry_id)
        healed = True

    entry_dir = os.path.join(root, "entries", entry_id)
    if healed:
        write_keys_json(entry_dir, ident)
    return {"entry_id": entry_id, "dir": entry_dir, "healed": healed}
