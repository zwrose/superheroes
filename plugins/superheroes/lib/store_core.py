#!/usr/bin/env python3
"""Shared two-key pointer + self-heal resolution algorithm.

Extracted from store.py (test-pilot) and review_store.py (review-crew).
Both consumers implemented the same algorithm; this module is the single
authoritative copy. Each consumer keeps its own public surface (store-root
constants, kind-keyed resolve/create, artifact_key, etc.).

Stdlib-only; no third-party dependencies.
"""
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

GIT_OK = "ok"
GIT_DECLINED = "declined"        # git ran and exited non-zero — an authoritative "no"
GIT_UNAVAILABLE = "unavailable"  # git could not be run at all — the answer is unknown

GitResult = collections.namedtuple("GitResult", "out status detail")


class RepoRootUnavailable(Exception):
    """Git could not be RUN, so the repository root is unknown (issue #699 rider 11).

    Deliberately NOT an OSError: no incidental ``except OSError`` may absorb this into a local
    story (unreadable core.md, absent file, legacy-profile-unsupported). Callers that need to
    translate it must catch ``RepoRootUnavailable`` by name."""


def _declined_not_a_repository_outcome(res, cwd):
    """Shared fail-closed classification for declined not-a-repository git results.

    Returns ``realpath(cwd)`` only for genuine greenfield (no ``.git`` ancestor,
    no env pointer). Otherwise raises ``RepoRootUnavailable``."""
    try:
        git_ancestor = git_dot_entry_ancestor(cwd)
    except OSError as exc:
        raise RepoRootUnavailable(
            "cannot determine repository root at %s: %s" % (cwd, exc))
    if git_ancestor is not None:
        if res.status == GIT_OK:
            raise RepoRootUnavailable(
                "repository root indeterminate at %s: .git present at %s but git returned "
                "empty rev-parse --show-toplevel" % (cwd, git_ancestor))
        raise RepoRootUnavailable(
            "repository root indeterminate at %s: .git present at %s but git declined: %s"
            % (cwd, git_ancestor, res.detail))
    if os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE"):
        raise RepoRootUnavailable(
            "git declined at %s with GIT_DIR or GIT_WORK_TREE set: %s"
            % (cwd, res.detail))
    return os.path.realpath(cwd)


def repo_root(cwd):
    """Fail-closed repository root for ``cwd`` (issue #742)."""
    res = run_git_result(cwd, "rev-parse", "--show-toplevel")
    if res.status == GIT_UNAVAILABLE:
        raise RepoRootUnavailable(
            "git could not be run at %s: %s" % (cwd, res.detail))
    if res.status == GIT_OK:
        if not res.out:
            return _declined_not_a_repository_outcome(res, cwd)
        resolved = os.path.realpath(res.out)
        if not os.path.isdir(resolved):
            raise RepoRootUnavailable(
                "git rev-parse --show-toplevel at %s named a non-directory path: %s"
                % (cwd, res.out))
        return resolved
    if not_a_repository(res):
        return _declined_not_a_repository_outcome(res, cwd)
    if not os.path.isdir(cwd):
        return _declined_not_a_repository_outcome(res, cwd)
    raise RepoRootUnavailable(
        "git declined rev-parse --show-toplevel at %s: %s" % (cwd, res.detail))


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


def not_a_repository(res):
    """True when git declined with its canonical not-a-repository message (issue #699)."""
    if res.status != GIT_DECLINED:
        return False
    detail = (res.detail or "").lower()
    return "not a git repository" in detail or "not a git repo" in detail


def git_dot_entry_ancestor(cwd):
    """Nearest ancestor directory containing a ``.git`` entry, or None.

    Uses ``lstat`` so a dangling ``.git`` symlink or an unreadable-but-present ``.git``
    directory still counts — only the entry's existence is tested, not readability.

    Returns the ancestor directory path (the parent of ``.git``), not the ``.git`` path
    itself.  Raises ``OSError`` when ``cwd`` cannot be resolved or the walk cannot
    complete (untraversable component).
    """
    path = os.path.realpath(cwd)
    while True:
        try:
            os.lstat(os.path.join(path, ".git"))
            return path
        except FileNotFoundError:
            pass
        except OSError:
            raise
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def run_git_result(cwd, *args):
    """`run_git` plus WHY there is no output (issue #699 rider 11).

    ``GIT_DECLINED`` means git ran and answered no — callers may believe it. ``GIT_UNAVAILABLE``
    means git never ran (missing binary, OSError, timeout), so a caller that would otherwise fall
    back to a default must fail closed instead: it has no answer, not a negative one."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANGUAGE"] = "C"  # stderr messages only; path output is locale-independent
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=10, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        return GitResult(None, GIT_UNAVAILABLE, "%s: %s" % (type(exc).__name__, exc))
    if r.returncode != 0:
        return GitResult(None, GIT_DECLINED, (r.stderr or "").strip())
    return GitResult(r.stdout.strip(), GIT_OK, None)


def run_git(cwd, *args):
    """Run git with an argv array + timeout. Return stdout (stripped) or None.
    Thin wrapper over `run_git_result` — see it for the failure distinction."""
    return run_git_result(cwd, *args).out


def get_remote(cwd):
    """Normalized origin URL, or None."""
    return normalize_remote(run_git(cwd, "remote", "get-url", "origin"))


def get_gitdir(cwd):
    """realpath of the git-common-dir (shared by all worktrees).

    Three-step chain mirrors ``control_plane._common_git_dir``: absolute common-dir,
    bare common-dir (joining relative output onto ``cwd``), then absolute-git-dir.
    On total failure, classifies the terminal result fail-closed (issue #742).
    """
    res = run_git_result(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if res.status == GIT_OK and res.out:
        return os.path.realpath(res.out)

    res = run_git_result(cwd, "rev-parse", "--git-common-dir")
    if res.status == GIT_OK and res.out:
        out = res.out if os.path.isabs(res.out) else os.path.join(cwd, res.out)
        resolved = os.path.realpath(out)
        if not os.path.exists(resolved):
            raise RepoRootUnavailable(
                "git rev-parse --git-common-dir at %s named a nonexistent path: %s"
                % (cwd, out))
        return resolved

    res = run_git_result(cwd, "rev-parse", "--absolute-git-dir")
    if res.status == GIT_OK and res.out:
        return os.path.realpath(res.out)

    if res.status == GIT_UNAVAILABLE:
        raise RepoRootUnavailable(
            "git could not be run at %s: %s" % (cwd, res.detail))
    if not_a_repository(res):
        return _declined_not_a_repository_outcome(res, cwd)
    if not os.path.isdir(cwd):
        return _declined_not_a_repository_outcome(res, cwd)
    raise RepoRootUnavailable(
        "git declined rev-parse --absolute-git-dir at %s: %s" % (cwd, res.detail))


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


def resolve_global(cwd, root, _consumer="store_core", heal=True):
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

    # Self-heal: point both available keys at the chosen live entry (skipped when heal=False).
    healed = False
    if heal and gh and p_gitdir != entry_id:
        write_pointer(root, gh, entry_id)
        healed = True
    if heal and rh and p_remote != entry_id:
        write_pointer(root, rh, entry_id)
        healed = True

    entry_dir = os.path.join(root, "entries", entry_id)
    if heal and healed:
        write_keys_json(entry_dir, ident)
    return {"entry_id": entry_id, "dir": entry_dir, "healed": healed}
