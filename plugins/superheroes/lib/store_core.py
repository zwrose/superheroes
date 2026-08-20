#!/usr/bin/env python3
"""Shared two-key pointer + self-heal resolution algorithm.

Extracted from store.py (test-pilot) and review_store.py (review-crew).
Both consumers implemented the same algorithm; this module is the single
authoritative copy. Each consumer keeps its own public surface (store-root
constants, kind-keyed resolve/create, artifact_key, etc.).

Stdlib-only; no third-party dependencies.
"""
import collections
import contextlib
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading

GIT_OK = "ok"
GIT_DECLINED = "declined"        # git ran and exited non-zero — an authoritative "no"
GIT_UNAVAILABLE = "unavailable"  # git could not be run at all — the answer is unknown

GitResult = collections.namedtuple("GitResult", "out status detail")

POINTER_OK = "ok"
POINTER_ABSENT = "absent"
POINTER_UNREADABLE = "unreadable"
PointerResult = collections.namedtuple("PointerResult", "entry_id status detail")


class PointerUnreadable(Exception):
    """A store key pointer or its entry directory exists but could not be read, so which entry
    belongs to this repository is UNKNOWN (issue #782).

    Deliberately NOT an OSError: no incidental ``except OSError`` may absorb this into a local
    story (unreadable pointer, absent file, dangling entry). Callers that need to translate it
    must catch ``PointerUnreadable`` by name."""

    def __init__(self, message, *, path=None, status=None, detail=None):
        super().__init__(message)
        self.path = path
        self.status = status
        self.detail = detail


class RepoRootUnavailable(Exception):
    """Git could not be RUN, so the repository root is unknown (issue #699 rider 11).

    Deliberately NOT an OSError: no incidental ``except OSError`` may absorb this into a local
    story (unreadable core.md, absent file, legacy-profile-unsupported). Callers that need to
    translate it must catch ``RepoRootUnavailable`` by name."""

    def __init__(self, message, *, git_status=None):
        super().__init__(message)
        # None (default) means origin unknown — never memo-cache. GIT_UNAVAILABLE means git
        # could not be run (transient); GIT_DECLINED means git ran and the refusal is authoritative.
        self.git_status = git_status


def _declined_not_a_repository_outcome(res, cwd):
    """Shared fail-closed classification for declined not-a-repository git results.

    Returns ``realpath(cwd)`` only for genuine greenfield (no ``.git`` ancestor,
    no env pointer). Otherwise raises ``RepoRootUnavailable``."""
    try:
        git_ancestor = git_dot_entry_ancestor(cwd)
    except OSError as exc:
        raise RepoRootUnavailable(
            "cannot determine repository root at %s: %s" % (cwd, exc),
            git_status=GIT_DECLINED)
    if git_ancestor is not None:
        if res.status == GIT_OK:
            raise RepoRootUnavailable(
                "repository root indeterminate at %s: .git present at %s but git returned "
                "empty rev-parse --show-toplevel" % (cwd, git_ancestor),
                git_status=GIT_DECLINED)
        raise RepoRootUnavailable(
            "repository root indeterminate at %s: .git present at %s but git declined: %s"
            % (cwd, git_ancestor, res.detail),
            git_status=GIT_DECLINED)
    if os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE"):
        raise RepoRootUnavailable(
            "git declined at %s with GIT_DIR or GIT_WORK_TREE set: %s"
            % (cwd, res.detail),
            git_status=GIT_DECLINED)
    return os.path.realpath(cwd)


_repo_identity_memo_local = threading.local()


def _active_repo_identity_memo():
    stack = getattr(_repo_identity_memo_local, "stack", None)
    if stack:
        return stack[-1]
    return None


def _memo_cacheable_repo_exc(exc):
    """True only when ``exc.git_status`` is set explicitly and is not ``GIT_UNAVAILABLE``."""
    status = exc.git_status
    return status is not None and status != GIT_UNAVAILABLE


@contextlib.contextmanager
def repo_identity_memo():
    """Memoize repository IDENTITY lookups for the duration of a ``with`` block.

    Caches ``repo_root(cwd)`` and ``derive_identifiers(cwd)`` per ``cwd`` — including an
    authoritative ``RepoRootUnavailable`` (``git_status`` is ``GIT_DECLINED``), so a deterministic
    refusal fails identically every time inside the block instead of silently re-probing. Repo
    identity cannot change inside one lock-guarded config operation, so caching authoritative
    refusals is safe; MUTABLE git state is deliberately NOT cached — the memo sits at the identity
    functions, never at ``run_git_result``, so ``status --porcelain`` and ``rev-parse HEAD`` are
    untouched.

    An identity derived while git was UNAVAILABLE is NOT cached — neither successful values nor
  raised exceptions: ``get_remote`` collapses "no origin" and "git could not run" to the same
    ``None``, so caching the latter would pin a project to the wrong store key, and caching a
    transient timeout would replay it after git recovers. Exceptions with no ``git_status`` are
    treated the same way (not cacheable). Unauthoritative lookups re-derive every call, exactly as
    they do without the memo.

    Reentrant (a nested ``with`` reuses the outer memo) and thread-local (concurrent threads never
    share a cache). Outside any block, every function behaves exactly as it does today."""
    stack = getattr(_repo_identity_memo_local, "stack", None)
    if stack is None:
        stack = []
        _repo_identity_memo_local.stack = stack
    if stack:
        yield
        return
    state = {
        "root": {},
        "root_exc": {},
        "ident": {},
        "ident_exc": {},
    }
    stack.append(state)
    try:
        yield
    finally:
        stack.pop()


def repo_root(cwd):
    """Fail-closed repository root for ``cwd`` (issue #742)."""
    memo = _active_repo_identity_memo()
    if memo is not None:
        if cwd in memo["root"]:
            return memo["root"][cwd]
        if cwd in memo["root_exc"]:
            raise memo["root_exc"][cwd]
    try:
        resolved = _repo_root_uncached(cwd)
    except RepoRootUnavailable as exc:
        if memo is not None and _memo_cacheable_repo_exc(exc):
            memo["root_exc"][cwd] = exc
        raise
    if memo is not None:
        memo["root"][cwd] = resolved
    return resolved


def _repo_root_uncached(cwd):
    res = run_git_result(cwd, "rev-parse", "--show-toplevel")
    if res.status == GIT_UNAVAILABLE:
        raise RepoRootUnavailable(
            "git could not be run at %s: %s" % (cwd, res.detail),
            git_status=GIT_UNAVAILABLE)
    if res.status == GIT_OK:
        if not res.out:
            return _declined_not_a_repository_outcome(res, cwd)
        resolved = os.path.realpath(res.out)
        if not os.path.isdir(resolved):
            raise RepoRootUnavailable(
                "git rev-parse --show-toplevel at %s named a non-directory path: %s"
                % (cwd, res.out),
                git_status=GIT_DECLINED)
        return resolved
    if not_a_repository(res):
        return _declined_not_a_repository_outcome(res, cwd)
    if not os.path.isdir(cwd):
        return _declined_not_a_repository_outcome(res, cwd)
    raise RepoRootUnavailable(
        "git declined rev-parse --show-toplevel at %s: %s" % (cwd, res.detail),
        git_status=GIT_DECLINED)


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


def get_remote_result(cwd):
    """``get_remote`` plus WHY there is no remote — (normalized_remote, status).

    ``status`` is the ``run_git_result`` status: ``GIT_OK``/``GIT_DECLINED`` are authoritative
    answers a caller may cache; ``GIT_UNAVAILABLE`` means git never ran, so the "no remote" is
    unknown, not negative, and must never be memoized as fact."""
    res = run_git_result(cwd, "remote", "get-url", "origin")
    return normalize_remote(res.out), res.status


def get_remote(cwd):
    """Normalized origin URL, or None."""
    return get_remote_result(cwd)[0]


def _terminal_gitdir_outcome(res, cwd, what):
    """Shared fail-closed classification for a terminal git-dir rev-parse result (issue #742).

    ONE classification, used by every sanctioned git-dir resolver here: git-could-not-run is
    unknown (``GIT_UNAVAILABLE``), a canonical not-a-repository decline (and a decline at a cwd
    that is not a directory) goes through ``_declined_not_a_repository_outcome``, and anything
    else is an authoritative refusal."""
    if res.status == GIT_UNAVAILABLE:
        raise RepoRootUnavailable(
            "git could not be run at %s: %s" % (cwd, res.detail),
            git_status=GIT_UNAVAILABLE)
    if not_a_repository(res):
        return _declined_not_a_repository_outcome(res, cwd)
    if not os.path.isdir(cwd):
        return _declined_not_a_repository_outcome(res, cwd)
    raise RepoRootUnavailable(
        "git declined %s at %s: %s" % (what, cwd, res.detail),
        git_status=GIT_DECLINED)


def get_worktree_gitdir(cwd, run=None):
    """realpath of THIS worktree's own git dir (never the shared common-dir).

    ``get_gitdir`` answers the git-COMMON-dir, which every linked worktree of a repository
    shares; a caller that writes a PER-WORKTREE artifact (the review handback sidecar) must not
    use it, or two sibling worktrees read and write one another's file. This resolver answers
    ``rev-parse --absolute-git-dir`` — inside a linked worktree that is
    ``<common>/worktrees/<name>`` — and classifies its terminal result through the SAME
    fail-closed handling ``get_gitdir`` uses (``_terminal_gitdir_outcome``), including the same
    declined-not-a-repository outcome.

    ``run`` is an injectable ``run_git_result``-shaped seam (default: ``run_git_result``) so a
    caller's test can drive the failure path without a real broken repository."""
    runner = run or run_git_result
    res = runner(cwd, "rev-parse", "--absolute-git-dir")
    if res.status == GIT_OK and res.out:
        return os.path.realpath(res.out)
    return _terminal_gitdir_outcome(res, cwd, "rev-parse --absolute-git-dir")


def get_gitdir(cwd):
    """realpath of the git-common-dir (shared by all worktrees).

    Three-step chain mirrors ``control_plane._common_git_dir``: absolute common-dir,
    bare common-dir (joining relative output onto ``cwd``), then absolute-git-dir.
    On total failure, classifies the terminal result fail-closed (issue #742).

    Per-worktree callers want ``get_worktree_gitdir`` instead — this answer is SHARED by every
    linked worktree of the repository.
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
                % (cwd, out),
                git_status=GIT_DECLINED)
        return resolved

    res = run_git_result(cwd, "rev-parse", "--absolute-git-dir")
    if res.status == GIT_OK and res.out:
        return os.path.realpath(res.out)

    return _terminal_gitdir_outcome(res, cwd, "rev-parse --absolute-git-dir")


def derive_identifiers(cwd):
    """Return dict with remote, gitdir, remote_hash, gitdir_hash for cwd."""
    memo = _active_repo_identity_memo()
    if memo is not None:
        if cwd in memo["ident"]:
            return memo["ident"][cwd]
        if cwd in memo["ident_exc"]:
            raise memo["ident_exc"][cwd]
    try:
        remote, remote_status = get_remote_result(cwd)
        gitdir = get_gitdir(cwd)
        ident = {
            "remote": remote,
            "gitdir": gitdir,
            "remote_hash": short_hash(remote) if remote else None,
            "gitdir_hash": short_hash(gitdir),
        }
    except RepoRootUnavailable as exc:
        if memo is not None and _memo_cacheable_repo_exc(exc):
            memo["ident_exc"][cwd] = exc
        raise
    if memo is not None and remote_status != GIT_UNAVAILABLE:
        memo["ident"][cwd] = ident
    return ident


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


def read_pointer_result(root, key_hash):
    """`read_pointer` plus WHY there is no entry id. Never raises."""
    path = os.path.join(root, "keys", key_hash)
    try:
        with open(path) as fh:
            text = fh.read()
    except FileNotFoundError:
        return PointerResult(None, POINTER_ABSENT, None)
    except UnicodeDecodeError as exc:
        return PointerResult(
            None, POINTER_UNREADABLE, "%s: %s" % (path, exc))
    except OSError as exc:
        return PointerResult(
            None, POINTER_UNREADABLE, "%s: %s" % (path, exc))
    entry_id = text.strip() or None
    if entry_id is None:
        return PointerResult(None, POINTER_ABSENT, None)
    return PointerResult(entry_id, POINTER_OK, None)


def read_pointer(root, key_hash):
    """Read the entry-id stored at root/keys/<key_hash>. None if absent/empty."""
    return read_pointer_result(root, key_hash).entry_id


def _entry_dir_is_live(root, entry_id, *, strict=False):
    """True when root/entries/<entry_id> is a live directory.

    In strict mode, an unstatable path or a non-directory raises ``PointerUnreadable``;
    ``FileNotFoundError`` returns False (dangling pointer). In fail-open mode, uses
    ``os.path.isdir`` (stat errors read as not live)."""
    path = os.path.join(root, "entries", entry_id)
    if not strict:
        return os.path.isdir(path)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        detail = "%s: %s" % (path, exc)
        raise PointerUnreadable(
            "entry directory could not be stat-ed at %s: %s" % (path, exc),
            path=path, status=POINTER_UNREADABLE, detail=detail) from exc
    if not stat.S_ISDIR(st.st_mode):
        detail = "%s: not a directory" % path
        raise PointerUnreadable(
            "entry path is not a directory at %s" % path,
            path=path, status=POINTER_UNREADABLE, detail=detail)
    return True


def _raise_pointer_unreadable(result, path):
    raise PointerUnreadable(
        "store key pointer could not be read at %s: %s" % (path, result.detail),
        path=path, status=result.status, detail=result.detail)


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


def resolve_global(cwd, root, _consumer="store_core", heal=True, *, strict=False):
    """Find the live global entry for cwd via key pointers (remote preferred),
    self-healing dangling/stale pointers.

    Returns {entry_id, dir, healed} or None if no live entry exists.
    This is the shared algorithm used by both test-pilot (store.py) and
    review-crew (review_store.py).

    With ``strict=True``, an unreadable pointer or unstatable entry directory
    raises ``PointerUnreadable`` before candidate selection or self-healing.
    """
    ident = derive_identifiers(cwd)
    rh, gh = ident["remote_hash"], ident["gitdir_hash"]

    if strict:
        if rh:
            r_remote = read_pointer_result(root, rh)
            if r_remote.status == POINTER_UNREADABLE:
                _raise_pointer_unreadable(
                    r_remote, os.path.join(root, "keys", rh))
            p_remote = r_remote.entry_id
        else:
            p_remote = None
        r_gitdir = read_pointer_result(root, gh)
        if r_gitdir.status == POINTER_UNREADABLE:
            _raise_pointer_unreadable(
                r_gitdir, os.path.join(root, "keys", gh))
        p_gitdir = r_gitdir.entry_id
    else:
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
        (c for c in candidates if _entry_dir_is_live(root, c, strict=strict)),
        None)
    if entry_id is None:
        return None

    # Warn only on a GENUINE conflict: both keys point at live-but-different
    # entries. A mere dangling pointer is routine self-heal, not a conflict.
    if (p_remote and p_gitdir and p_remote != p_gitdir
            and _entry_dir_is_live(root, p_remote, strict=strict)
            and _entry_dir_is_live(root, p_gitdir, strict=strict)):
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
