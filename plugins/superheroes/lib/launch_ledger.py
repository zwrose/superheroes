#!/usr/bin/env python3
"""Durable dispatch record behind R1 mechanical park/refusal accounting.

The ledger's whole job is to be unable to report a resolved batch it cannot
actually see — torn tails, interior corruption, and unresolved members all
refuse to ground a rate. Never raises to callers.

Every locked writer validates its candidate record against the reader
(read → fold(records + [candidate])) before appending; that invariant keeps
one grammar across reserve, append_under_lock, declare_batch, and terminalize.

The ledger's event grammar is version-coupled to the plugin build that wrote
it: a record kind an older build does not understand (for example ``amendment``)
makes ``fold`` refuse the whole stream with ``fold-unknown-event:<kind>``, and
every ledger door fails closed until the file is cleared. Recovery is deleting
the ledger file at the path ``ledger_path()`` reports — there is no in-place
prune or forward-compat skip for unknown events.
"""
import fcntl
import hashlib
import json
import os
import posixpath
import signal
import stat
import subprocess
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import file_lock  # noqa: E402
import pilot_boundary  # noqa: E402
import pilot_provision  # noqa: E402
import pilot_slot  # noqa: E402

LEDGER_ROOT_ENV = "SUPERHEROES_LAUNCH_LEDGER_ROOT"
LEDGER_DIR_NAME = "superheroes-launch-ledger"
LEDGER_NAME = "launch-ledger.jsonl"
SCHEMA = 1
EVENT_KINDS = ("reserved", "started", "retry", "refused", "outcome", "amendment")
TERMINAL_OUTCOMES = ("handback", "park", "refusal", "died")
AMENDMENT_EVENT = "amendment"
AMENDMENT_REOUTCOME = "reoutcome"
AMENDMENT_KINDS = ("reoutcome", "vet", "evidence")
# What a caller may write by hand. `reoutcome` is a recorded consequence of a real second
# record_outcome call, never a hand-written claim.
CALLER_WRITABLE_AMENDMENT_KINDS = ("vet", "evidence")
VET_RULINGS = ("ready", "not-ready", "parked-blocker")
_AMENDMENT_FIELDS = ("kind", "value", "note")
TERMINAL_EVENTS = ("outcome", "refused")
WHOLE_REPO = ":whole-repo:"

_LOCK_SUFFIX = ".lock"
_LOCK_NAME = LEDGER_NAME + _LOCK_SUFFIX
_DEFAULT_LOCK_TIMEOUT = 30.0
_GIT_SCRUB_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
)

_RESERVED_FIELDS = (
    "batchId", "repoId", "issue", "surfaces", "premise", "preflight",
    "argv", "doctrineDigest", "model",
)
_STARTED_FIELDS = ("attempt", "pid", "logPath", "errPath")
_RETRY_FIELDS = ("attempt", "reason", "delaySeconds")
_REFUSED_FIELDS = ("stage", "reason")
_OUTCOME_FIELDS = ("outcome", "evidence")
_COMMON_FIELDS = ("event", "launchId", "ts", "schema")
_BATCH_DECLARED_FIELDS = ("batchId", "expectedLaunches")

_INSPECT_REASON = (
    "zero parks and zero refusals is a signal to inspect, never a clean sheet"
)
COUNT_RESULT_BLOCKS = ("counts", "amendments", "lanes", "attempts", "laneDetail", "slots")
# The count-result blocks the advisor's charter names by hand; the drift test reads THIS.
CHARTER_NAMED_COUNT_BLOCKS = ("lanes", "attempts", "laneDetail")


def _scrub_env(env=None):
    base = dict(env if env is not None else os.environ)
    for key in _GIT_SCRUB_VARS:
        base.pop(key, None)
    base.pop(LEDGER_ROOT_ENV, None)
    return base


def _git_scrubbed(repo_root, *args, env=None, timeout=None):
    try:
        return subprocess.run(
            ["git", "-C", repo_root, *args],
            capture_output=True,
            text=True,
            env=_scrub_env(env),
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _has_git_entry(path):
    path = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def _path_inside(parent, child):
    parent = os.path.realpath(parent)
    child = os.path.realpath(child)
    return child == parent or child.startswith(parent + os.sep)


def _is_group_or_world_accessible(path):
    try:
        mode = os.stat(path).st_mode & 0o777
        return bool(mode & 0o077)
    except OSError:
        return True


def _is_fd_group_or_world_accessible(fd):
    try:
        mode = os.fstat(fd).st_mode & 0o777
        return bool(mode & 0o077)
    except OSError:
        return True


def _close_fd(fd):
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass


def _clear_nonblock(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)


def _ledger_refusal(reason, root_fd=None, repo_fd=None, ledger_fd=None):
    _close_fd(ledger_fd)
    _close_fd(repo_fd)
    _close_fd(root_fd)
    return {"ok": False, "reason": reason, "fh": None, "path": None}


def _open_ledger_dirs(repo_root, env=None):
    """Open validated root and repo-id directory fds. Never raises."""
    if env is None:
        env = os.environ

    resolved = resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return {"ok": False, "reason": resolved["reason"], "root_fd": None,
                "repo_fd": None, "root": None, "repo_id": None}

    repo_id = repo_identity(repo_root)
    if repo_id is None:
        return {"ok": False, "reason": "ledger-repo-identity-unavailable",
                "root_fd": None, "repo_fd": None, "root": None, "repo_id": None}

    root = resolved["root"]
    root_fd = None
    repo_fd = None
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return {"ok": False, "reason": "ledger-root-unusable", "root_fd": None,
                "repo_fd": None, "root": root, "repo_id": repo_id}

    if _is_fd_group_or_world_accessible(root_fd):
        return _ledger_refusal("ledger-root-insecure", root_fd=root_fd)

    try:
        os.mkdir(repo_id, mode=0o700, dir_fd=root_fd)
    except FileExistsError:
        pass
    except OSError:
        return _ledger_refusal("ledger-repo-dir-unusable", root_fd=root_fd)

    try:
        repo_fd = os.open(
            repo_id,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY,
            dir_fd=root_fd,
        )
    except OSError as exc:
        reason = "ledger-repo-dir-unusable"
        if isinstance(exc, FileNotFoundError):
            reason = "ledger-repo-dir-missing"
        elif getattr(exc, "errno", None) in (getattr(os, "ENOTDIR", None),):
            reason = "ledger-repo-dir-not-directory"
        else:
            repo_path = os.path.join(root, repo_id)
            if os.path.islink(repo_path):
                reason = "ledger-repo-dir-symlink"
        return _ledger_refusal(reason, root_fd=root_fd)

    if _is_fd_group_or_world_accessible(repo_fd):
        return _ledger_refusal("ledger-repo-dir-insecure", root_fd=root_fd, repo_fd=repo_fd)

    return {
        "ok": True,
        "reason": None,
        "root_fd": root_fd,
        "repo_fd": repo_fd,
        "root": root,
        "repo_id": repo_id,
    }


def open_ledger(repo_root, mode, env=None):
    """The ONLY way to obtain a ledger file handle. Never raises."""
    if mode not in ("r", "a"):
        return {"ok": False, "reason": "ledger-mode-invalid", "fh": None, "path": None}

    opened = _open_ledger_dirs(repo_root, env=env)
    if not opened["ok"]:
        return {"ok": False, "reason": opened["reason"], "fh": None, "path": None}

    root_fd = opened["root_fd"]
    repo_fd = opened["repo_fd"]
    root = opened["root"]
    repo_id = opened["repo_id"]
    ledger_fd = None
    try:
        if mode == "r":
            try:
                ledger_fd = os.open(
                    LEDGER_NAME,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=repo_fd,
                )
            except FileNotFoundError:
                _close_fd(repo_fd)
                _close_fd(root_fd)
                return {"ok": False, "reason": "ledger-missing", "fh": None, "path": None}
            except OSError as exc:
                reason = "ledger-file-unusable"
                ledger_path = os.path.join(root, repo_id, LEDGER_NAME)
                if os.path.islink(ledger_path):
                    reason = "ledger-file-symlink"
                return _ledger_refusal(reason, root_fd=root_fd, repo_fd=repo_fd, ledger_fd=ledger_fd)
        else:
            try:
                ledger_fd = os.open(
                    LEDGER_NAME,
                    os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                    mode=0o600,
                    dir_fd=repo_fd,
                )
            except OSError as exc:
                reason = "ledger-file-unusable"
                ledger_path = os.path.join(root, repo_id, LEDGER_NAME)
                if os.path.islink(ledger_path):
                    reason = "ledger-file-symlink"
                else:
                    try:
                        st = os.stat(LEDGER_NAME, dir_fd=repo_fd, follow_symlinks=False)
                        if not stat.S_ISREG(st.st_mode):
                            reason = "ledger-file-not-regular"
                    except OSError:
                        pass
                return _ledger_refusal(reason, root_fd=root_fd, repo_fd=repo_fd, ledger_fd=ledger_fd)

        st = os.fstat(ledger_fd)
        if not stat.S_ISREG(st.st_mode):
            return _ledger_refusal(
                "ledger-file-not-regular",
                root_fd=root_fd,
                repo_fd=repo_fd,
                ledger_fd=ledger_fd,
            )
        if _is_fd_group_or_world_accessible(ledger_fd):
            return _ledger_refusal(
                "ledger-file-insecure",
                root_fd=root_fd,
                repo_fd=repo_fd,
                ledger_fd=ledger_fd,
            )

        _clear_nonblock(ledger_fd)

        ledger_path = os.path.join(root, repo_id, LEDGER_NAME)
        if mode == "r":
            fh = os.fdopen(ledger_fd, "rb")
        else:
            fh = os.fdopen(ledger_fd, "ab")
        ledger_fd = None
        _close_fd(repo_fd)
        repo_fd = None
        _close_fd(root_fd)
        root_fd = None
        return {"ok": True, "reason": None, "fh": fh, "path": ledger_path}
    except OSError:
        return _ledger_refusal(
            "ledger-file-unusable",
            root_fd=root_fd,
            repo_fd=repo_fd,
            ledger_fd=ledger_fd,
        )


def _ensure_lock_file(repo_root, env=None):
    """Validate the lock path is absent or a regular non-symlink file before acquire.

    Does not create the lock file. There is a TOCTOU window between this
    validation and ``file_lock.acquire``. Never raises.
    """
    opened = _open_ledger_dirs(repo_root, env=env)
    if not opened["ok"]:
        return {"ok": False, "reason": opened["reason"], "path": None}

    root_fd = opened["root_fd"]
    repo_fd = opened["repo_fd"]
    root = opened["root"]
    repo_id = opened["repo_id"]
    lock_fd = None
    try:
        try:
            lock_fd = os.open(
                _LOCK_NAME,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=repo_fd,
            )
        except FileNotFoundError:
            lock_path = os.path.join(root, repo_id, _LOCK_NAME)
            _close_fd(repo_fd)
            repo_fd = None
            _close_fd(root_fd)
            root_fd = None
            return {"ok": True, "reason": None, "path": lock_path}
        except OSError:
            lock_path = os.path.join(root, repo_id, _LOCK_NAME)
            if os.path.islink(lock_path):
                return _ledger_refusal("ledger-lock-symlink", root_fd=root_fd, repo_fd=repo_fd)
            return _ledger_refusal("ledger-lock-unusable", root_fd=root_fd, repo_fd=repo_fd)

        st = os.fstat(lock_fd)
        if not stat.S_ISREG(st.st_mode):
            return _ledger_refusal(
                "ledger-lock-not-regular",
                root_fd=root_fd,
                repo_fd=repo_fd,
                ledger_fd=lock_fd,
            )
        _close_fd(lock_fd)
        lock_fd = None
        _close_fd(repo_fd)
        repo_fd = None
        _close_fd(root_fd)
        root_fd = None
        lock_path = os.path.join(root, repo_id, _LOCK_NAME)
        return {"ok": True, "reason": None, "path": lock_path}
    except OSError:
        return _ledger_refusal(
            "ledger-lock-unusable",
            root_fd=root_fd,
            repo_fd=repo_fd,
            ledger_fd=lock_fd,
        )


def _lock_path(ledger_file):
    return ledger_file + _LOCK_SUFFIX


def _acquire_lock(lock_path, timeout):
    deadline = time.monotonic() + timeout
    while True:
        try:
            file_lock.acquire(lock_path)
            return True
        except file_lock.LockHeld:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
        except OSError:
            return False


def _release_lock(lock_path):
    try:
        file_lock.release(lock_path)
    except Exception:
        pass


def append_under_lock(repo_root, record, env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Append a ledger record under the canonical lock gate. Never raises.

    Terminal events (``outcome``, ``refused``) must use ``terminalize`` — this
    is not that door.
    """
    if isinstance(record, dict) and record.get("event") in TERMINAL_EVENTS:
        return {
            "ok": False,
            "reason": "append-terminal-must-use-terminalize",
            "path": None,
        }
    lock_result = _ensure_lock_file(repo_root, env=env)
    if not lock_result["ok"]:
        return {"ok": False, "reason": lock_result["reason"], "path": None}
    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {"ok": False, "reason": lp["reason"], "path": None}
    path = lp["path"]
    lock_path = lock_result["path"]
    if not _acquire_lock(lock_path, lock_timeout):
        return {"ok": False, "reason": "lock-unavailable", "path": None}
    try:
        read_result = read(repo_root, env=env)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {"ok": False, "reason": "ledger-unreadable:%s" % state, "path": None}

        folded = fold(read_result["records"] + [record])
        if not folded["ok"]:
            return {"ok": False, "reason": folded["reason"], "path": None}

        if not append(repo_root, record, env=env):
            return {"ok": False, "reason": "ledger-append-failed", "path": None}
        return {"ok": True, "reason": None, "path": path}
    finally:
        _release_lock(lock_path)


def repo_identity(repo_root):
    """sha256 hex of realpath(git-common-dir); None on any failure."""
    if not repo_root or not isinstance(repo_root, str):
        return None
    root = repo_root.strip()
    if not root or not _has_git_entry(root):
        return None
    proc = _git_scrubbed(root, "rev-parse", "--git-common-dir")
    if proc is None or proc.returncode != 0:
        return None
    common = (proc.stdout or "").strip()
    if not common:
        return None
    if not os.path.isabs(common):
        common = os.path.join(root, common)
    try:
        real = os.path.realpath(common)
    except OSError:
        return None
    return hashlib.sha256(real.encode("utf-8")).hexdigest()


def _candidate_root_validation_reason(repo_root, root, env=None):
    """Return a refusal reason token, or None when root is usable. Never raises."""
    if env is None:
        env = os.environ
    repo_real = os.path.realpath(repo_root)
    proc = _git_scrubbed(repo_root, "rev-parse", "--git-common-dir", env=env)
    if proc is None or proc.returncode != 0:
        return "ledger-repo-identity-unavailable"
    common = (proc.stdout or "").strip()
    if not os.path.isabs(common):
        common = os.path.join(repo_root, common)
    try:
        common_real = os.path.realpath(common)
    except OSError:
        return "ledger-repo-identity-unavailable"

    if _path_inside(repo_real, root) or _path_inside(common_real, root):
        return "ledger-root-in-repo"

    try:
        os.makedirs(root, mode=0o700, exist_ok=True)
    except OSError:
        return "ledger-root-unusable"

    if not os.path.isdir(root) or not os.access(root, os.W_OK):
        return "ledger-root-unusable"

    if _is_group_or_world_accessible(root):
        return "ledger-root-insecure"

    return None


def validate_candidate_root(repo_root, root, env=None):
    """True when `root` is a usable store root for `repo_root`. Never raises."""
    return _candidate_root_validation_reason(repo_root, root, env=env) is None


def resolve_root(repo_root, env=None):
    """Resolve ledger root outside the repo; refuse in-repo paths."""
    if env is None:
        env = os.environ
    if not _has_git_entry(repo_root):
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}
    if repo_identity(repo_root) is None:
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}

    override = env.get(LEDGER_ROOT_ENV)
    root = override if override else os.path.join(tempfile.gettempdir(), LEDGER_DIR_NAME)
    try:
        root = os.path.realpath(os.path.abspath(root))
    except OSError:
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    reason = _candidate_root_validation_reason(repo_root, root, env=env)
    if reason is not None:
        return {"ok": False, "root": None, "reason": reason}

    return {"ok": True, "root": root, "reason": None}


def ledger_path(repo_root, env=None):
    """Pure query for reporting/refusal reasons; does not open the ledger."""
    resolved = resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return {"ok": False, "path": None, "reason": resolved["reason"]}
    repo_id = repo_identity(repo_root)
    if repo_id is None:
        return {"ok": False, "path": None, "reason": "ledger-repo-identity-unavailable"}

    path = os.path.join(resolved["root"], repo_id, LEDGER_NAME)
    return {"ok": True, "path": path, "reason": None}


def _parse_ledger_bytes(raw):
    """Parse ledger bytes into state + records."""
    if not raw:
        return {"state": "ok", "records": []}

    torn = raw[-1:] != b"\n"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"state": "interiorCorrupt", "records": []}

    lines = text.split("\n")
    if torn:
        lines.pop()

    records = []
    interior_corrupt = False
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except (ValueError, TypeError):
            interior_corrupt = True
            continue
        if not isinstance(parsed, dict):
            interior_corrupt = True
            continue
        records.append(parsed)

    if interior_corrupt:
        return {"state": "interiorCorrupt", "records": records}
    if torn:
        return {"state": "tornTail", "records": records}
    return {"state": "ok", "records": records}


def _append_raw(repo_root, record, env=None):
    """Module-internal append primitive. False on failure; never raises."""
    opened = open_ledger(repo_root, "a", env=env)
    if not opened["ok"]:
        return False
    fh = opened["fh"]
    try:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        fh.write(line.encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
        return True
    except (OSError, TypeError, ValueError):
        return False
    finally:
        try:
            fh.close()
        except OSError:
            pass


def append(repo_root, record, env=None):
    """Append one JSON line with flush+fsync. False on failure; never raises.

    Terminal events (``outcome``, ``refused``) must use ``terminalize`` — this
    is not that door.
    """
    if isinstance(record, dict) and record.get("event") in TERMINAL_EVENTS:
        return False
    return _append_raw(repo_root, record, env=env)


def read(repo_root, env=None):
    """Read ledger; surface torn tails and interior corruption fail-closed."""
    opened = open_ledger(repo_root, "r", env=env)
    if not opened["ok"]:
        if opened["reason"] == "ledger-missing":
            return {"state": "missing", "records": []}
        return {"state": "unreadable", "records": []}
    fh = opened["fh"]
    try:
        raw = fh.read()
    except OSError:
        return {"state": "unreadable", "records": []}
    finally:
        try:
            fh.close()
        except OSError:
            pass
    return _parse_ledger_bytes(raw)


def _canonical_surface(repo_real, norm):
    full = os.path.realpath(os.path.join(repo_real, norm.replace("/", os.sep)))
    rel = os.path.relpath(full, repo_real)
    return posixpath.normpath(rel.replace(os.sep, "/"))


def normalize_surfaces(repo_root, surfaces):
    """Normalize repo-relative surfaces to canonical paths; refuse escapes."""
    if not surfaces:
        return {"ok": False, "surfaces": [], "reason": "surfaces-empty"}
    if not isinstance(surfaces, (list, tuple)):
        return {"ok": False, "surfaces": [], "reason": "surfaces-empty"}

    repo_real = os.path.realpath(repo_root)
    out = []
    for entry in surfaces:
        if entry is None or (isinstance(entry, str) and not entry.strip()):
            return {"ok": False, "surfaces": [], "reason": "surface-empty"}
        if entry == WHOLE_REPO:
            out.append(WHOLE_REPO)
            continue
        if not isinstance(entry, str):
            return {"ok": False, "surfaces": [], "reason": "surface-empty"}
        if os.path.isabs(entry):
            return {"ok": False, "surfaces": [], "reason": "surface-absolute"}
        norm = posixpath.normpath(entry.replace(os.sep, "/"))
        if norm in ("", "."):
            return {"ok": False, "surfaces": [], "reason": "surface-empty"}
        if norm.startswith("../") or norm == "..":
            return {"ok": False, "surfaces": [], "reason": "surface-escapes-repo"}
        parts = norm.split("/")
        if ".." in parts:
            return {"ok": False, "surfaces": [], "reason": "surface-escapes-repo"}
        full = os.path.realpath(os.path.join(repo_real, norm.replace("/", os.sep)))
        if not _path_inside(repo_real, full):
            return {"ok": False, "surfaces": [], "reason": "surface-escapes-repo"}
        out.append(_canonical_surface(repo_real, norm))

    return {"ok": True, "surfaces": sorted(set(out)), "reason": None}


def _surface_ancestor(ancestor, path):
    ancestor = ancestor.rstrip("/").lower()
    path = path.rstrip("/").lower()
    if ancestor == path:
        return True
    return path.startswith(ancestor + "/")


def surfaces_overlap(a, b):
    """True when either side is whole-repo or any pair shares a path ancestor."""
    if WHOLE_REPO in a or WHOLE_REPO in b:
        return True
    for left in a:
        for right in b:
            if left.lower() == right.lower():
                return True
            if _surface_ancestor(left, right) or _surface_ancestor(right, left):
                return True
    return False


def live_launches(records):
    folded = fold(records)
    if not folded["ok"]:
        return []
    live = []
    for launch_id, info in folded["launches"].items():
        if not info.get("terminal"):
            live.append(launch_id)
    return live


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_BOUNDARY_RECORD_KEYS = frozenset({
    "slotRef",
    "result",
    "provenance",
    "strength",
    "match",
    "policyDigest",
    "verifiedAt",
    "weakerAccepted",
    "acceptedBy",
    "acceptedAt",
    "acceptanceReason",
})


def boundary_record(verdict, *, weaker_acceptance=None):
    """Project a boundary verdict into the flat results-only ledger block."""
    if not isinstance(verdict, dict):
        return {"ok": False, "reason": "ledger-boundary-verdict-invalid"}
    if verdict.get("schemaVersion") != pilot_boundary.BOUNDARY_SCHEMA_VERSION:
        return {"ok": False, "reason": "ledger-boundary-schema-version"}
    identity = verdict.get("datastoreIdentity")
    if not isinstance(identity, dict):
        return {"ok": False, "reason": "ledger-boundary-datastore-identity-absent"}
    provenance = identity.get("provenance")
    if not isinstance(provenance, str) or not provenance:
        return {"ok": False, "reason": "ledger-boundary-datastore-identity-absent"}
    strength = identity.get("strength")
    if strength not in (pilot_boundary.STRENGTH_STRONG, pilot_boundary.STRENGTH_WEAKER):
        return {"ok": False, "reason": "ledger-boundary-strength-unknown"}
    match = identity.get("match")
    if type(match) is not bool:
        return {"ok": False, "reason": "ledger-boundary-datastore-identity-absent"}
    slot_ref = verdict.get("slotRef")
    if not isinstance(slot_ref, str) or not slot_ref:
        return {"ok": False, "reason": "ledger-boundary-verdict-invalid"}
    result = verdict.get("result")
    if not isinstance(result, str) or not result:
        return {"ok": False, "reason": "ledger-boundary-verdict-invalid"}
    policy_digest = verdict.get("policyDigest")
    if not isinstance(policy_digest, str) or not policy_digest:
        return {"ok": False, "reason": "ledger-boundary-verdict-invalid"}
    verified_at = verdict.get("verifiedAt")
    if not isinstance(verified_at, str) or not verified_at:
        return {"ok": False, "reason": "ledger-boundary-verdict-invalid"}

    acceptance = None
    if strength == pilot_boundary.STRENGTH_WEAKER:
        if weaker_acceptance is None:
            return {"ok": False, "reason": "ledger-boundary-weaker-unaccepted"}
        try:
            acceptance = pilot_provision.validate_weaker_acceptance(weaker_acceptance)
        except pilot_provision.PilotProvisionError:
            return {"ok": False, "reason": "ledger-boundary-weaker-acceptance-invalid"}
    elif weaker_acceptance is not None:
        return {"ok": False, "reason": "ledger-boundary-strong-with-acceptance"}

    weaker_accepted = strength == pilot_boundary.STRENGTH_WEAKER
    accepted_by = None
    accepted_at = None
    acceptance_reason = None
    if acceptance is not None:
        accepted_by = acceptance["acceptedBy"]
        accepted_at = acceptance["acceptedAt"]
        reason_text = acceptance["reason"]
        if len(reason_text) > 500:
            return {"ok": False, "reason": "ledger-boundary-acceptance-reason-too-long"}
        acceptance_reason = reason_text

    record = {
        "slotRef": slot_ref,
        "result": result,
        "provenance": provenance,
        "strength": strength,
        "match": match,
        "policyDigest": policy_digest,
        "verifiedAt": verified_at,
        "weakerAccepted": weaker_accepted,
        "acceptedBy": accepted_by,
        "acceptedAt": accepted_at,
        "acceptanceReason": acceptance_reason,
    }
    return {"ok": True, "record": record}


def _validate_boundary_block(block, slot, generation):
    if not isinstance(block, dict):
        return "fold-bad-field:reserved:boundary-shape"
    if set(block.keys()) != _BOUNDARY_RECORD_KEYS:
        return "fold-bad-field:reserved:boundary-keys"
    if not isinstance(block.get("slotRef"), str) or not block["slotRef"]:
        return "fold-bad-field:reserved:boundary-slotRef"
    if not isinstance(block.get("result"), str) or not block["result"]:
        return "fold-bad-field:reserved:boundary-result"
    if not isinstance(block.get("provenance"), str) or not block["provenance"]:
        return "fold-bad-field:reserved:boundary-provenance"
    block_strength = block.get("strength")
    if block_strength not in (
        pilot_boundary.STRENGTH_STRONG,
        pilot_boundary.STRENGTH_WEAKER,
    ):
        return "fold-bad-field:reserved:boundary-strength"
    if type(block.get("match")) is not bool:
        return "fold-bad-field:reserved:boundary-match"
    if not isinstance(block.get("policyDigest"), str) or not block["policyDigest"]:
        return "fold-bad-field:reserved:boundary-policyDigest"
    if not isinstance(block.get("verifiedAt"), str) or not block["verifiedAt"]:
        return "fold-bad-field:reserved:boundary-verifiedAt"
    if type(block.get("weakerAccepted")) is not bool:
        return "fold-bad-field:reserved:boundary-weakerAccepted"
    for nullable_field in ("acceptedBy", "acceptedAt", "acceptanceReason"):
        nullable_value = block.get(nullable_field)
        if nullable_value is not None and (
            not isinstance(nullable_value, str) or not nullable_value
        ):
            return "fold-bad-field:reserved:boundary-nullable"
    try:
        expected_ref = pilot_slot.format_slot_ref(slot, generation)
    except pilot_slot.PilotSlotError:
        return "fold-bad-field:reserved:boundary-slotRef"
    if block["slotRef"] != expected_ref:
        return "fold-bad-field:reserved:boundary-slotRef"
    return None


def _validate_reserved_optional_fields(rec):
    slot_present = "slot" in rec
    generation_present = "generation" in rec
    boundary_present = "boundary" in rec

    if slot_present and not generation_present:
        return "fold-bad-field:reserved:slot-generation"
    if generation_present and not slot_present:
        return "fold-bad-field:reserved:slot-generation"

    if slot_present:
        try:
            pilot_slot.validate_slot_id(rec["slot"])
        except pilot_slot.PilotSlotError:
            return "fold-bad-field:reserved:slot"
        generation = rec["generation"]
        if not isinstance(generation, int) or isinstance(generation, bool):
            return "fold-bad-field:reserved:generation"
        try:
            pilot_slot.validate_generation(generation)
        except pilot_slot.PilotSlotError:
            return "fold-bad-field:reserved:generation"

    if boundary_present:
        if not slot_present or not generation_present:
            return "fold-bad-field:reserved:boundary"
        return _validate_boundary_block(rec["boundary"], rec["slot"], rec["generation"])

    return None


def _validate_common(rec):
    for field in _COMMON_FIELDS:
        if field not in rec:
            return "fold-missing-field:%s:%s" % (rec.get("event", "?"), field)
    event = rec["event"]
    if rec["schema"] != SCHEMA:
        return "fold-schema:%s" % rec["schema"]
    if not _is_number(rec["ts"]):
        return "fold-bad-field:%s:ts" % event
    if not isinstance(rec["launchId"], str) or not rec["launchId"]:
        return "fold-missing-field:%s:launchId" % event
    return None


def _validate_batch_declared(rec):
    if rec.get("schema") != SCHEMA:
        return "fold-schema:%s" % rec.get("schema", "?")
    if not isinstance(rec.get("batchId"), str) or not rec.get("batchId"):
        return "fold-missing-field:batch-declared:batchId"
    expected = rec.get("expectedLaunches")
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
        return "fold-bad-field:batch-declared:expectedLaunches"
    if not _is_number(rec.get("ts")):
        return "fold-bad-field:batch-declared:ts"
    for field in _BATCH_DECLARED_FIELDS:
        if field not in rec:
            return "fold-missing-field:batch-declared:%s" % field
    return None


def _validate_event_fields(rec):
    event = rec["event"]
    if event == "reserved":
        fields = _RESERVED_FIELDS
    elif event == "started":
        fields = _STARTED_FIELDS
    elif event == "retry":
        fields = _RETRY_FIELDS
    elif event in TERMINAL_EVENTS:
        fields = _REFUSED_FIELDS if event == "refused" else _OUTCOME_FIELDS
    elif event == AMENDMENT_EVENT:
        fields = _AMENDMENT_FIELDS
    else:
        return "fold-unknown-event:%s" % event

    for field in fields:
        if field not in rec:
            return "fold-missing-field:%s:%s" % (event, field)

    if event == AMENDMENT_EVENT:
        kind = rec["kind"]
        if kind not in AMENDMENT_KINDS:
            return "fold-bad-amendment-kind:%s" % rec["launchId"]
        value = rec["value"]
        if not isinstance(value, str) or not value:
            return "fold-missing-amendment-value:%s" % rec["launchId"]
        note = rec["note"]
        if not isinstance(note, str) or not note:
            return "fold-missing-amendment-note:%s" % rec["launchId"]
        if kind == "reoutcome" and value not in TERMINAL_OUTCOMES:
            return "fold-bad-amendment-value:%s" % rec["launchId"]
        if kind == "vet" and value not in VET_RULINGS:
            return "fold-bad-amendment-value:%s" % rec["launchId"]
    elif event == "started":
        attempt = rec["attempt"]
        pid = rec["pid"]
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            return "fold-bad-field:started:attempt"
        if not isinstance(pid, int) or isinstance(pid, bool) or pid < 2:
            return "fold-bad-field:started:pid"
    elif event == "retry":
        attempt = rec["attempt"]
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            return "fold-bad-field:retry:attempt"
    elif event == "outcome":
        if rec["outcome"] not in TERMINAL_OUTCOMES:
            return "fold-bad-outcome:%s" % rec["launchId"]
        evidence = rec["evidence"]
        if not isinstance(evidence, str) or not evidence.strip():
            return "fold-missing-evidence:%s" % rec["launchId"]
    elif event == "reserved":
        optional_err = _validate_reserved_optional_fields(rec)
        if optional_err:
            return optional_err
    return None


def fold(records):
    """Per-launch state machine over event records.

    ``retry`` on a non-terminal launch is legal whether or not ``started`` has been seen.
    """
    launches = {}
    batch_declarations = {}
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            return {"ok": False, "reason": "fold-not-an-object", "launches": {},
                    "batchDeclarations": {}}

        if rec.get("event") == "batch-declared":
            err = _validate_batch_declared(rec)
            if err:
                return {"ok": False, "reason": err, "launches": {},
                        "batchDeclarations": {}}
            batch_id = rec["batchId"]
            batch_declarations.setdefault(batch_id, []).append(dict(rec, index=idx))
            continue

        err = _validate_common(rec)
        if err:
            return {"ok": False, "reason": err, "launches": {},
                    "batchDeclarations": batch_declarations}
        err = _validate_event_fields(rec)
        if err:
            return {"ok": False, "reason": err, "launches": {},
                    "batchDeclarations": batch_declarations}

        event = rec["event"]
        launch_id = rec["launchId"]

        if event == "reserved":
            if launch_id in launches:
                return {
                    "ok": False,
                    "reason": "fold-duplicate-reserved:%s" % launch_id,
                    "launches": {},
                    "batchDeclarations": batch_declarations,
                }
            launches[launch_id] = {
                "batchId": rec["batchId"],
                "issue": rec["issue"],
                "surfaces": rec["surfaces"],
                "terminal": False,
                "outcome": None,
                "terminalKind": None,
                "terminalIndex": None,
                "reservedTs": rec["ts"],
                "reservedIndex": idx,
                "attempts": 0,
                "started": False,
                "amendments": [],
                "slot": rec.get("slot"),
                "generation": rec.get("generation"),
                "boundary": rec.get("boundary"),
            }
            continue

        if launch_id not in launches:
            return {"ok": False, "reason": "fold-orphan-event:%s" % launch_id,
                    "launches": {}, "batchDeclarations": batch_declarations}

        info = launches[launch_id]
        if event == AMENDMENT_EVENT:
            if not info["terminal"]:
                return {"ok": False,
                        "reason": "fold-amendment-before-terminal:%s" % launch_id,
                        "launches": {}, "batchDeclarations": batch_declarations}
            info["amendments"].append({
                "kind": rec["kind"], "value": rec["value"], "note": rec["note"], "ts": rec["ts"],
            })
            continue
        if info["terminal"]:
            return {
                "ok": False,
                "reason": "fold-conflicting-terminal:%s" % launch_id,
                "launches": {},
                "batchDeclarations": batch_declarations,
            }

        if event == "started":
            prev_attempt = info.get("attempt")
            if prev_attempt is not None and rec["attempt"] <= prev_attempt:
                return {
                    "ok": False,
                    "reason": "fold-started-attempt-not-increasing:%s" % launch_id,
                    "launches": {},
                    "batchDeclarations": batch_declarations,
                }
            info["attempts"] += 1
            info["started"] = True
            info["pid"] = rec["pid"]
            info["attempt"] = rec["attempt"]
            pids = list(info.get("pids", []))
            if rec["pid"] not in pids:
                pids.append(rec["pid"])
            info["pids"] = pids
        elif event == "retry":
            pass
        elif event in TERMINAL_EVENTS:
            if event == "refused":
                if info["started"]:
                    return {
                        "ok": False,
                        "reason": "fold-refused-after-started:%s" % launch_id,
                        "launches": {},
                        "batchDeclarations": batch_declarations,
                    }
                info["terminal"] = True
                info["terminalKind"] = "refused"
                info["terminalIndex"] = idx
            else:
                if not info["started"]:
                    return {
                        "ok": False,
                        "reason": "fold-outcome-without-started:%s" % launch_id,
                        "launches": {},
                        "batchDeclarations": batch_declarations,
                    }
                info["terminal"] = True
                info["terminalKind"] = "outcome"
                info["outcome"] = rec["outcome"]
                info["terminalIndex"] = idx

    return {"ok": True, "reason": None, "launches": launches,
            "batchDeclarations": batch_declarations}


def _batch_declarations(records, batch_id, folded=None):
    if folded is not None and folded.get("batchDeclarations") is not None:
        decls = folded["batchDeclarations"].get(batch_id, [])
        return [d["expectedLaunches"] for d in decls]
    decls = []
    for rec in records:
        if rec.get("event") != "batch-declared":
            continue
        if rec.get("batchId") != batch_id:
            continue
        err = _validate_batch_declared(rec)
        if err:
            return None
        decls.append(rec["expectedLaunches"])
    return decls


def _declaration_index(records, batch_id, folded=None):
    if folded is not None and folded.get("batchDeclarations") is not None:
        decls = folded["batchDeclarations"].get(batch_id, [])
        if not decls:
            return None
        return decls[0]["index"]
    for idx, rec in enumerate(records):
        if rec.get("event") != "batch-declared":
            continue
        if rec.get("batchId") != batch_id:
            continue
        err = _validate_batch_declared(rec)
        if err:
            return None
        return idx
    return None


def declare_batch(repo_root, batch_id, expected_launches, env=None,
                  lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Record expected launch cardinality for a batch before any reserve."""
    if not isinstance(batch_id, str) or not batch_id.strip():
        return {"ok": False, "reason": "batch-id-empty"}
    if (not isinstance(expected_launches, int) or isinstance(expected_launches, bool)
            or expected_launches < 1):
        return {"ok": False, "reason": "batch-expected-invalid"}

    lock_result = _ensure_lock_file(repo_root, env=env)
    if not lock_result["ok"]:
        return {"ok": False, "reason": lock_result["reason"]}

    lock_path = lock_result["path"]
    if not _acquire_lock(lock_path, lock_timeout):
        return {"ok": False, "reason": "lock-unavailable"}

    try:
        read_result = read(repo_root, env=env)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {"ok": False, "reason": "ledger-unreadable:%s" % state}

        folded = fold(read_result["records"])
        if not folded["ok"]:
            return {"ok": False, "reason": folded["reason"]}

        for launch_id, info in folded["launches"].items():
            if info.get("batchId") == batch_id:
                return {"ok": False, "reason": "batch-already-has-reservations"}

        event = {
            "event": "batch-declared",
            "batchId": batch_id,
            "expectedLaunches": expected_launches,
            "ts": time.time(),
            "schema": SCHEMA,
        }
        folded_with_event = fold(read_result["records"] + [event])
        if not folded_with_event["ok"]:
            return {"ok": False, "reason": folded_with_event["reason"]}
        if not append(repo_root, event, env=env):
            return {"ok": False, "reason": "ledger-append-failed"}
        return {"ok": True, "reason": None}
    finally:
        _release_lock(lock_path)


def reserve(repo_root, record, env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Reserve a launch under lock with overlap detection."""
    if not isinstance(record, dict):
        return {"ok": False, "reason": "fold-not-an-object", "path": None}
    launch_id = record.get("launchId")
    if not isinstance(launch_id, str) or not launch_id:
        return {"ok": False, "reason": "reserve-launch-id-invalid", "path": None}

    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {"ok": False, "reason": lp["reason"], "path": None}

    lock_result = _ensure_lock_file(repo_root, env=env)
    if not lock_result["ok"]:
        return {"ok": False, "reason": lock_result["reason"], "path": None}

    lock_path = lock_result["path"]
    if not _acquire_lock(lock_path, lock_timeout):
        return {"ok": False, "reason": "lock-unavailable", "path": None}

    try:
        read_result = read(repo_root, env=env)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {"ok": False, "reason": "ledger-unreadable:%s" % state, "path": None}

        folded = fold(read_result["records"])
        if not folded["ok"]:
            return {"ok": False, "reason": folded["reason"], "path": None}

        if launch_id in folded["launches"]:
            return {
                "ok": False,
                "reason": "reserve-duplicate-launch-id:%s" % launch_id,
                "path": None,
            }

        norm = normalize_surfaces(repo_root, record.get("surfaces", []))
        if not norm["ok"]:
            return {"ok": False, "reason": norm["reason"], "path": None}

        new_surfaces = norm["surfaces"]
        for live_id in live_launches(read_result["records"]):
            info = folded["launches"][live_id]
            existing = info.get("surfaces") or []
            if surfaces_overlap(new_surfaces, existing):
                return {
                    "ok": False,
                    "reason": "surface-overlap:%s" % live_id,
                    "blockingLaunchId": live_id,
                    "blockingSurfaces": list(existing),
                    "path": None,
                }

        to_write = dict(record)
        to_write["surfaces"] = new_surfaces
        # General guard: refuse any record the reader would reject after append.
        # The explicit launch-id checks above are the named, specific refusals.
        folded_with_new = fold(read_result["records"] + [to_write])
        if not folded_with_new["ok"]:
            return {
                "ok": False,
                "reason": folded_with_new["reason"],
                "path": None,
            }
        if not append(repo_root, to_write, env=env):
            return {"ok": False, "reason": "ledger-append-failed", "path": None}
        return {"ok": True, "reason": None, "path": lp["path"]}
    finally:
        _release_lock(lock_path)


def _reap_process(proc):
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    time.sleep(0.2)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def _started_pids_to_probe(info):
    """Pids of every started attempt for liveness probing; backward-compatible."""
    pids = info.get("pids")
    if pids:
        return pids
    pid = info.get("pid")
    if pid is not None:
        return [pid]
    return []


def _child_group_is_live(pid):
    """True when the recorded pid or its process group still has live members.

    Signal 0 is an existence probe, never a real signal: this function must never
    change another process's state. Every uncertain answer is True, because the
    caller refuses on True — a wrong answer here costs a refusal, not a kill.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if pid == 1:
        return True
    settle_seconds = 2.0
    try:
        if pid == os.getpid() or pid == os.getpgid(0):
            return True
    except OSError:
        return True
    deadline = time.monotonic() + settle_seconds
    while True:
        proc_alive = False
        group_alive = False
        try:
            os.kill(pid, 0)
            proc_alive = True
        except ProcessLookupError:
            pass
        except PermissionError:
            return True
        except OSError:
            return True
        try:
            os.killpg(pid, 0)
            group_alive = True
        except ProcessLookupError:
            pass
        except PermissionError:
            return True
        except OSError:
            return True
        if proc_alive or group_alive:
            if time.monotonic() >= deadline:
                return True
            time.sleep(0.05)
        else:
            return False


def _validate_started_repair(started_repair):
    if not isinstance(started_repair, dict):
        return False
    attempt = started_repair.get("attempt")
    pid = started_repair.get("pid")
    log_path = started_repair.get("logPath")
    err_path = started_repair.get("errPath")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        return False
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 2:
        return False
    if not isinstance(log_path, str):
        return False
    if not isinstance(err_path, str):
        return False
    return True


def terminalize(repo_root, launch_id, *, child_ever_spawned=False, reason=None, evidence=None,
                stage=None, outcome=None, proc=None, started_repair=None, require_started=False,
                env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """The ONLY writer of a terminal ledger event. Never raises."""
    reaped = False
    lock_path = None
    locked = False
    try:
        if proc is not None and proc.poll() is None:
            _reap_process(proc)
            if proc.poll() is None:
                return {
                    "ok": False,
                    "reason": "terminal-child-live:%s" % proc.pid,
                    "kind": None, "outcome": None, "reaped": False,
                }
            reaped = True

        if not isinstance(launch_id, str) or not launch_id:
            return {
                "ok": False, "reason": "terminal-launch-id-invalid",
                "kind": None, "outcome": None, "reaped": reaped,
            }

        if outcome is not None and outcome not in TERMINAL_OUTCOMES:
            return {
                "ok": False, "reason": "outcome-invalid:%s" % outcome,
                "kind": None, "outcome": None, "reaped": reaped,
            }
        if outcome is not None and (not isinstance(evidence, str) or not evidence.strip()):
            return {
                "ok": False, "reason": "outcome-evidence-empty",
                "kind": None, "outcome": None, "reaped": reaped,
            }

        lock_result = _ensure_lock_file(repo_root, env=env)
        if not lock_result["ok"]:
            return {
                "ok": False, "reason": lock_result["reason"],
                "kind": None, "outcome": None, "reaped": reaped,
            }

        lock_path = lock_result["path"]
        if not _acquire_lock(lock_path, lock_timeout):
            return {
                "ok": False, "reason": "lock-unavailable",
                "kind": None, "outcome": None, "reaped": reaped,
            }
        locked = True

        read_result = read(repo_root, env=env)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {
                "ok": False, "reason": "ledger-unreadable:%s" % state,
                "kind": None, "outcome": None, "reaped": reaped,
            }

        folded = fold(read_result["records"])
        if not folded["ok"]:
            return {
                "ok": False, "reason": folded["reason"],
                "kind": None, "outcome": None, "reaped": reaped,
            }

        if launch_id not in folded["launches"]:
            return {
                "ok": False, "reason": "terminal-unknown-launch",
                "kind": None, "outcome": None, "reaped": reaped,
            }

        info = folded["launches"][launch_id]
        if info.get("terminal"):
            return {
                "ok": False, "reason": "outcome-already-terminal",
                "kind": None, "outcome": None, "reaped": reaped,
            }

        if require_started and not info.get("started"):
            return {
                "ok": False, "reason": "outcome-without-started",
                "kind": None, "outcome": None, "reaped": reaped,
            }

        if info.get("started"):
            # One _child_group_is_live per recorded attempt, each with bounded
            # settle — all inside the lock. At most one started per launch today.
            for pid in _started_pids_to_probe(info):
                if _child_group_is_live(pid):
                    return {
                        "ok": False,
                        "reason": "terminal-child-live:%s" % pid,
                        "kind": None, "outcome": None, "reaped": reaped,
                    }

        records = list(read_result["records"])
        started = info.get("started")
        if started or child_ever_spawned:
            if child_ever_spawned and not started:
                if not _validate_started_repair(started_repair):
                    return {
                        "ok": False, "reason": "terminal-repair-unavailable",
                        "kind": None, "outcome": None, "reaped": reaped,
                    }
                if _child_group_is_live(started_repair["pid"]):
                    return {
                        "ok": False,
                        "reason": "terminal-child-live:%s" % started_repair["pid"],
                        "kind": None, "outcome": None, "reaped": reaped,
                    }
                started_record = {
                    "event": "started",
                    "launchId": launch_id,
                    "ts": time.time(),
                    "schema": SCHEMA,
                    "attempt": started_repair["attempt"],
                    "pid": started_repair["pid"],
                    "logPath": started_repair["logPath"],
                    "errPath": started_repair["errPath"],
                    "repaired": True,
                }
                folded_repair = fold(records + [started_record])
                if not folded_repair["ok"]:
                    return {
                        "ok": False, "reason": folded_repair["reason"],
                        "kind": None, "outcome": None, "reaped": reaped,
                    }
                if not append(repo_root, started_record, env=env):
                    return {
                        "ok": False, "reason": "ledger-append-failed",
                        "kind": None, "outcome": None, "reaped": reaped,
                    }
                records.append(started_record)
            kind = "outcome"
            written_outcome = outcome if outcome is not None else "park"
            written_evidence = (
                evidence if isinstance(evidence, str) and evidence.strip()
                else reason if isinstance(reason, str) and reason.strip()
                else "unknown"
            )
            record = {
                "event": "outcome",
                "launchId": launch_id,
                "ts": time.time(),
                "schema": SCHEMA,
                "outcome": written_outcome,
                "evidence": written_evidence,
            }
            if started and not child_ever_spawned:
                record["reconciled"] = True
        elif outcome is not None:
            return {
                "ok": False, "reason": "terminal-outcome-without-child",
                "kind": None, "outcome": None, "reaped": reaped,
            }
        else:
            kind = "refused"
            written_outcome = None
            park_stage = stage if isinstance(stage, str) and stage.strip() else "unknown"
            park_reason = reason if isinstance(reason, str) and reason.strip() else "unknown"
            record = {
                "event": "refused",
                "launchId": launch_id,
                "ts": time.time(),
                "schema": SCHEMA,
                "stage": park_stage,
                "reason": park_reason,
            }

        if reaped:
            record["reaped"] = True

        folded_terminal = fold(records + [record])
        if not folded_terminal["ok"]:
            return {
                "ok": False, "reason": folded_terminal["reason"],
                "kind": None, "outcome": None, "reaped": reaped,
            }

        if not _append_raw(repo_root, record, env=env):
            return {
                "ok": False, "reason": "ledger-append-failed",
                "kind": None, "outcome": None, "reaped": reaped,
            }
        return {
            "ok": True, "reason": None, "kind": kind,
            "outcome": written_outcome, "reaped": reaped,
        }
    except Exception:
        return {
            "ok": False, "reason": "terminalize-failed",
            "kind": None, "outcome": None, "reaped": reaped,
        }
    finally:
        if locked and lock_path is not None:
            _release_lock(lock_path)


def _record_outcome_response(ok, reason=None, recorded=None, amendment_kind=None,
                             attempted_outcome=None, terminal_outcome=None):
    return {
        "ok": ok,
        "reason": reason,
        "recorded": recorded,
        "amendmentKind": amendment_kind,
        "attemptedOutcome": attempted_outcome,
        "terminalOutcome": terminal_outcome,
    }


def record_outcome(repo_root, launch_id, outcome, evidence, env=None,
                   lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Record a terminal outcome under lock. Never raises."""
    if outcome not in TERMINAL_OUTCOMES:
        return _record_outcome_response(
            False, reason="outcome-invalid:%s" % outcome,
        )
    if not isinstance(evidence, str) or not evidence.strip():
        return _record_outcome_response(False, reason="outcome-evidence-empty")

    result = terminalize(
        repo_root, launch_id, outcome=outcome, evidence=evidence,
        require_started=True, env=env, lock_timeout=lock_timeout,
    )
    mapped_reason = result["reason"]
    if mapped_reason in ("terminal-unknown-launch", "terminal-launch-id-invalid"):
        mapped_reason = "outcome-unknown-launch"
    if not result["ok"] and result["reason"] == "outcome-already-terminal":
        read_result = read(repo_root, env=env)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return _record_outcome_response(
                False, reason="ledger-unreadable:%s" % state,
            )
        folded = fold(read_result["records"])
        if not folded["ok"]:
            return _record_outcome_response(False, reason=folded["reason"])
        if launch_id not in folded["launches"]:
            return _record_outcome_response(False, reason="outcome-unknown-launch")

        info = folded["launches"][launch_id]
        # Terminal kind is immutable once terminal; a stale read cannot flip it.
        if info.get("terminalKind") == "refused" or not info.get("started"):
            return _record_outcome_response(False, reason="outcome-without-started")

        amended = amend(repo_root, launch_id, AMENDMENT_REOUTCOME, outcome, evidence,
                        env=env, lock_timeout=lock_timeout, dedupe_identical=True)
        if not amended["ok"]:
            amend_reason = amended["reason"]
            if amend_reason == "amend-failed":
                return _record_outcome_response(False, reason="amend-failed")
            return _record_outcome_response(
                False, reason="amend-failed:%s" % amend_reason,
            )
        recorded = "amendment-existing" if amended["deduped"] else "amendment"
        return _record_outcome_response(
            True, recorded=recorded,
            amendment_kind=AMENDMENT_REOUTCOME,
            attempted_outcome=outcome,
            terminal_outcome=amended["terminalOutcome"],
        )
    if result["ok"]:
        return _record_outcome_response(
            True, recorded="outcome",
            attempted_outcome=outcome,
            terminal_outcome=result["outcome"],
        )
    return _record_outcome_response(False, reason=mapped_reason)


def _amend_response(ok, reason=None, kind=None, value=None, terminal_outcome=None,
                    terminal_kind=None, deduped=False):
    return {
        "ok": ok,
        "reason": reason,
        "kind": kind,
        "value": value,
        "terminalOutcome": terminal_outcome,
        "terminalKind": terminal_kind,
        "deduped": deduped,
    }


def amend(repo_root, launch_id, kind, value, note, env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT,
          *, dedupe_identical=False):
    """Record a post-terminal annotation on a terminal launch. Never mutates the terminal
    outcome, and never raises."""
    try:
        if not isinstance(launch_id, str) or not launch_id:
            return _amend_response(False, reason="amend-launch-id-invalid")
        if kind not in AMENDMENT_KINDS:
            return _amend_response(False, reason="amend-kind-invalid:%s" % kind)
        if not isinstance(value, str) or not value:
            return _amend_response(False, reason="amend-value-empty")
        if not isinstance(note, str) or not note:
            return _amend_response(False, reason="amend-note-empty")
        if kind == "reoutcome" and value not in TERMINAL_OUTCOMES:
            return _amend_response(False, reason="amend-value-invalid:%s" % value)
        if kind == "vet" and value not in VET_RULINGS:
            return _amend_response(False, reason="amend-value-invalid:%s" % value)

        lock_result = _ensure_lock_file(repo_root, env=env)
        if not lock_result["ok"]:
            return _amend_response(False, reason=lock_result["reason"])

        lock_path = lock_result["path"]
        if not _acquire_lock(lock_path, lock_timeout):
            return _amend_response(False, reason="lock-unavailable")

        try:
            read_result = read(repo_root, env=env)
            state = read_result["state"]
            if state not in ("ok", "missing"):
                return _amend_response(False, reason="ledger-unreadable:%s" % state)

            folded = fold(read_result["records"])
            if not folded["ok"]:
                return _amend_response(False, reason=folded["reason"])

            if launch_id not in folded["launches"]:
                return _amend_response(False, reason="amend-unknown-launch")

            info = folded["launches"][launch_id]
            if not info.get("terminal"):
                return _amend_response(False, reason="amend-not-terminal")

            if dedupe_identical:
                for existing in info.get("amendments") or []:
                    if (existing.get("kind") == kind
                            and existing.get("value") == value
                            and existing.get("note") == note):
                        return _amend_response(
                            True, kind=kind, value=value,
                            terminal_outcome=info.get("outcome"),
                            terminal_kind=info.get("terminalKind"),
                            deduped=True,
                        )

            record = {
                "event": AMENDMENT_EVENT,
                "launchId": launch_id,
                "ts": time.time(),
                "schema": SCHEMA,
                "kind": kind,
                "value": value,
                "note": note,
            }
            folded_with = fold(read_result["records"] + [record])
            if not folded_with["ok"]:
                return _amend_response(False, reason=folded_with["reason"])

            if not append(repo_root, record, env=env):
                return _amend_response(False, reason="ledger-append-failed")

            return _amend_response(
                True, kind=kind, value=value,
                terminal_outcome=info.get("outcome"),
                terminal_kind=info.get("terminalKind"),
            )
        finally:
            _release_lock(lock_path)
    except Exception:
        return _amend_response(False, reason="amend-failed")


def _vet_count_key(ruling):
    return "vet" + "".join(part.capitalize() for part in ruling.split("-"))


def _zero_amendments():
    zeroed = {"reoutcome": 0, "rehandback": 0, "evidence": 0, "total": 0}
    for ruling in VET_RULINGS:
        zeroed[_vet_count_key(ruling)] = 0
    return zeroed


def _zero_attempt_outcomes():
    return {
        "handback": 0,
        "park": 0,
        "refusal": 0,
        "died": 0,
        "refusedToLaunch": 0,
    }


def _valid_lane_issue(issue):
    return isinstance(issue, int) and not isinstance(issue, bool) and issue > 0


def _attempt_outcome_label(info):
    if info.get("terminalKind") == "refused":
        return "refusedToLaunch"
    return info.get("outcome")


def _count_indeterminate(batch_id, reason):
    return {
        "ok": True,
        "batchId": batch_id,
        "resolved": False,
        "indeterminate": True,
        "reason": reason,
        "counts": {
            "handback": 0,
            "park": 0,
            "refusal": 0,
            "died": 0,
            "refusedToLaunch": 0,
            "total": 0,
        },
        "amendments": _zero_amendments(),
        "amendedLaunches": 0,
        "lanes": {"declared": 0, "resolved": 0},
        "attempts": {"total": 0, "extra": 0, "outcomes": _zero_attempt_outcomes()},
        "laneDetail": [],
        "slots": [],
        "inspect": False,
        "inspectReason": "",
    }


def count(repo_root, batch_id, env=None):
    """R1 accounting — refuses to report a resolved batch it cannot ground."""
    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return _count_indeterminate(batch_id, lp["reason"])

    read_result = read(repo_root, env=env)
    state = read_result["state"]
    if state != "ok":
        return _count_indeterminate(batch_id, "ledger-%s" % state)

    folded = fold(read_result["records"])
    if not folded["ok"]:
        return _count_indeterminate(batch_id, folded["reason"])

    batch_launches = [
        lid for lid, info in folded["launches"].items()
        if info.get("batchId") == batch_id
    ]
    if not batch_launches:
        return _count_indeterminate(batch_id, "batch-empty")

    decls = _batch_declarations(read_result["records"], batch_id, folded=folded)
    if decls is None:
        return _count_indeterminate(batch_id, "batch-declaration-malformed")
    if len(decls) == 0:
        return _count_indeterminate(batch_id, "batch-undeclared")
    if len(decls) > 1:
        return _count_indeterminate(batch_id, "batch-duplicate-declaration")

    for lid in batch_launches:
        issue = folded["launches"][lid].get("issue")
        if not _valid_lane_issue(issue):
            return _count_indeterminate(
                batch_id, "batch-lane-issue-invalid:%s" % lid,
            )

    lane_groups = {}
    for lid in batch_launches:
        issue = folded["launches"][lid]["issue"]
        lane_groups.setdefault(issue, []).append(lid)

    distinct_lanes = len(lane_groups)
    if distinct_lanes != decls[0]:
        return _count_indeterminate(batch_id, "batch-reservation-mismatch")

    decl_index = _declaration_index(read_result["records"], batch_id, folded=folded)
    if decl_index is None:
        return _count_indeterminate(batch_id, "batch-declaration-malformed")
    for lid in batch_launches:
        reserved_index = folded["launches"][lid].get("reservedIndex")
        if reserved_index is not None and decl_index > reserved_index:
            return _count_indeterminate(batch_id, "batch-declaration-after-reservations")

    for issue, lane_launch_ids in lane_groups.items():
        ordered = sorted(
            lane_launch_ids,
            key=lambda launch_id: folded["launches"][launch_id]["reservedIndex"],
        )
        for idx in range(len(ordered) - 1):
            earlier = folded["launches"][ordered[idx]]
            later = folded["launches"][ordered[idx + 1]]
            earlier_terminal = earlier.get("terminalIndex")
            if earlier_terminal is None or earlier_terminal >= later["reservedIndex"]:
                return _count_indeterminate(
                    batch_id, "batch-lane-concurrent:%s" % issue,
                )

    for lid in batch_launches:
        info = folded["launches"][lid]
        if not info.get("terminal"):
            return _count_indeterminate(batch_id, "batch-unresolved:%s" % lid)

    counts = {
        "handback": 0,
        "park": 0,
        "refusal": 0,
        "died": 0,
        "refusedToLaunch": 0,
        "total": 0,
    }
    attempt_outcomes = _zero_attempt_outcomes()
    lane_detail = []

    for issue in sorted(lane_groups):
        lane_launch_ids = lane_groups[issue]
        ordered = sorted(
            lane_launch_ids,
            key=lambda launch_id: folded["launches"][launch_id]["reservedIndex"],
        )
        attempt_labels = []
        for launch_id in ordered:
            attempt_labels.append(_attempt_outcome_label(folded["launches"][launch_id]))

        for launch_id in ordered[:-1]:
            label = _attempt_outcome_label(folded["launches"][launch_id])
            if label in attempt_outcomes:
                attempt_outcomes[label] += 1

        final_info = folded["launches"][ordered[-1]]
        counts["total"] += 1
        if final_info.get("terminalKind") == "refused":
            counts["refusedToLaunch"] += 1
        elif final_info.get("terminalKind") == "outcome":
            outcome = final_info.get("outcome")
            if outcome in counts:
                counts[outcome] += 1

        lane_detail.append({
            "issue": issue,
            "attempts": len(ordered),
            "outcome": final_info.get("outcome"),
            "terminalKind": final_info.get("terminalKind"),
            "attemptOutcomes": attempt_labels,
        })

    amendments = _zero_amendments()
    amended_launches = 0
    for lid in batch_launches:
        info = folded["launches"][lid]
        lane_amendments = info.get("amendments") or []
        if lane_amendments:
            amended_launches += 1
        for amend_rec in lane_amendments:
            amendments["total"] += 1
            kind = amend_rec["kind"]
            value = amend_rec["value"]
            if kind == "reoutcome":
                amendments["reoutcome"] += 1
                # Genuine re-handback: second write was handback on a lane that ended handback.
                if value == "handback" and info.get("outcome") == "handback":
                    amendments["rehandback"] += 1
            elif kind == "vet":
                amendments[_vet_count_key(value)] += 1
            elif kind == "evidence":
                amendments["evidence"] += 1

    slots_block = []
    for lid in batch_launches:
        info = folded["launches"][lid]
        slot = info.get("slot")
        if slot is None:
            continue
        boundary = info.get("boundary")
        generation = info.get("generation")
        if boundary is not None:
            slot_ref = boundary["slotRef"]
            strength = boundary["strength"]
            weaker_accepted = boundary["weakerAccepted"]
        else:
            try:
                slot_ref = pilot_slot.format_slot_ref(slot, generation)
            except pilot_slot.PilotSlotError:
                slot_ref = None
            strength = None
            weaker_accepted = False
        slots_block.append({
            "slot": slot,
            "generation": generation,
            "slotRef": slot_ref,
            "strength": strength,
            "weakerAccepted": weaker_accepted,
        })

    inspect = (
        counts["park"] + counts["refusal"] + counts["refusedToLaunch"] == 0
    )
    return {
        "ok": True,
        "batchId": batch_id,
        "resolved": True,
        "indeterminate": False,
        "reason": None,
        "counts": counts,
        "amendments": amendments,
        "amendedLaunches": amended_launches,
        "lanes": {"declared": decls[0], "resolved": distinct_lanes},
        "attempts": {
            "total": len(batch_launches),
            "extra": len(batch_launches) - distinct_lanes,
            "outcomes": attempt_outcomes,
        },
        "laneDetail": lane_detail,
        "slots": slots_block,
        "inspect": inspect,
        "inspectReason": _INSPECT_REASON if inspect else "",
    }
