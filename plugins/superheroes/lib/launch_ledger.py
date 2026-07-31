#!/usr/bin/env python3
"""Durable dispatch record behind R1 mechanical park/refusal accounting.

The ledger's whole job is to be unable to report a resolved batch it cannot
actually see — torn tails, interior corruption, and unresolved members all
refuse to ground a rate. Never raises to callers.
"""
import hashlib
import json
import os
import posixpath
import subprocess
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import file_lock  # noqa: E402

LEDGER_ROOT_ENV = "SUPERHEROES_LAUNCH_LEDGER_ROOT"
LEDGER_DIR_NAME = "superheroes-launch-ledger"
LEDGER_NAME = "launch-ledger.jsonl"
SCHEMA = 1
EVENT_KINDS = ("reserved", "started", "retry", "refused", "outcome")
TERMINAL_OUTCOMES = ("handback", "park", "refusal", "died")
WHOLE_REPO = ":whole-repo:"

_LOCK_SUFFIX = ".lock"
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


def _root_has_symlink(path):
    path = os.path.abspath(path)
    if os.path.islink(path):
        return True
    parent = os.path.dirname(path)
    if parent == path:
        return False
    return _root_has_symlink(parent)


def _is_group_or_world_accessible(path):
    try:
        mode = os.stat(path).st_mode & 0o777
        return bool(mode & 0o077)
    except OSError:
        return True


def _validate_ledger_paths(root, repo_id):
    """Refuse symlink escapes and insecure pre-existing ledger paths."""
    repo_dir = os.path.join(root, repo_id)
    ledger_file = os.path.join(repo_dir, LEDGER_NAME)
    lock_file = _lock_path(ledger_file)

    checks = (
        ("repo-dir", repo_dir, os.path.isdir, True),
        ("file", ledger_file, os.path.isfile, True),
        ("lock", lock_file, os.path.isfile, False),
    )
    for label, path, is_type, check_insecure in checks:
        if os.path.islink(path):
            return {"ok": False, "reason": "ledger-%s-symlink" % label}
        if os.path.exists(path):
            try:
                real = os.path.realpath(path)
            except OSError:
                return {"ok": False, "reason": "ledger-path-unusable"}
            if not _path_inside(root, real):
                return {"ok": False, "reason": "ledger-path-escapes-root"}
            if check_insecure and is_type(path) and _is_group_or_world_accessible(path):
                return {"ok": False, "reason": "ledger-%s-insecure" % label}

    return {"ok": True, "reason": None}


def _prepare_ledger_parent(ledger_file):
    """Create the repo-id directory with secure mode before file_lock touches it."""
    parent = os.path.dirname(ledger_file)
    if os.path.islink(parent):
        return False
    if os.path.exists(parent):
        if _is_group_or_world_accessible(parent):
            return False
        return True
    try:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    except OSError:
        return False
    return not _is_group_or_world_accessible(parent)


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


def _release_lock(lock_path):
    try:
        file_lock.release(lock_path)
    except Exception:
        pass


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


def resolve_root(repo_root, env=None):
    """Resolve ledger root outside the repo; refuse symlink or in-repo paths."""
    if env is None:
        env = os.environ
    if not _has_git_entry(repo_root):
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}
    if repo_identity(repo_root) is None:
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}

    override = env.get(LEDGER_ROOT_ENV)
    root = override if override else os.path.join(tempfile.gettempdir(), LEDGER_DIR_NAME)
    try:
        root = os.path.abspath(root)
    except OSError:
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    if _root_has_symlink(root):
        return {"ok": False, "root": None, "reason": "ledger-root-symlink"}

    repo_real = os.path.realpath(repo_root)
    proc = _git_scrubbed(repo_root, "rev-parse", "--git-common-dir", env=env)
    if proc is None or proc.returncode != 0:
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}
    common = (proc.stdout or "").strip()
    if not os.path.isabs(common):
        common = os.path.join(repo_root, common)
    try:
        common_real = os.path.realpath(common)
    except OSError:
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}

    if _path_inside(repo_real, root) or _path_inside(common_real, root):
        return {"ok": False, "root": None, "reason": "ledger-root-in-repo"}

    try:
        os.makedirs(root, mode=0o700, exist_ok=True)
    except OSError:
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    if not os.path.isdir(root) or not os.access(root, os.W_OK):
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    if _is_group_or_world_accessible(root):
        return {"ok": False, "root": None, "reason": "ledger-root-insecure"}

    return {"ok": True, "root": root, "reason": None}


def ledger_path(repo_root, env=None):
    resolved = resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return {"ok": False, "path": None, "reason": resolved["reason"]}
    repo_id = repo_identity(repo_root)
    if repo_id is None:
        return {"ok": False, "path": None, "reason": "ledger-repo-identity-unavailable"}

    layout = _validate_ledger_paths(resolved["root"], repo_id)
    if not layout["ok"]:
        return {"ok": False, "path": None, "reason": layout["reason"]}

    path = os.path.join(resolved["root"], repo_id, LEDGER_NAME)
    return {"ok": True, "path": path, "reason": None}


def append(path, record):
    """Append one JSON line with flush+fsync. False on OSError; never raises."""
    try:
        parent = os.path.dirname(path)
        if os.path.exists(parent) and _is_group_or_world_accessible(parent):
            return False
        os.makedirs(parent, mode=0o700, exist_ok=True)
        if os.path.exists(parent) and _is_group_or_world_accessible(parent):
            return False
        line = json.dumps(record, separators=(",", ":")) + "\n"
        if not os.path.exists(path):
            fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
        else:
            if _is_group_or_world_accessible(path):
                return False
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
        return True
    except OSError:
        return False


def read(path):
    """Read ledger; surface torn tails and interior corruption fail-closed."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return {"state": "missing", "records": []}
    except OSError:
        return {"state": "unreadable", "records": []}

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


def _validate_event_fields(rec):
    event = rec["event"]
    if event == "reserved":
        fields = _RESERVED_FIELDS
    elif event == "started":
        fields = _STARTED_FIELDS
    elif event == "retry":
        fields = _RETRY_FIELDS
    elif event == "refused":
        fields = _REFUSED_FIELDS
    elif event == "outcome":
        fields = _OUTCOME_FIELDS
    else:
        return "fold-unknown-event:%s" % event

    for field in fields:
        if field not in rec:
            return "fold-missing-field:%s:%s" % (event, field)

    if event == "started":
        attempt = rec["attempt"]
        pid = rec["pid"]
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            return "fold-bad-field:started:attempt"
        if not isinstance(pid, int) or isinstance(pid, bool):
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
    return None


def fold(records):
    """Per-launch state machine over event records."""
    launches = {}
    for rec in records:
        if not isinstance(rec, dict):
            return {"ok": False, "reason": "fold-not-an-object", "launches": {}}
        if rec.get("event") == "batch-declared":
            continue

        err = _validate_common(rec)
        if err:
            return {"ok": False, "reason": err, "launches": {}}
        err = _validate_event_fields(rec)
        if err:
            return {"ok": False, "reason": err, "launches": {}}

        event = rec["event"]
        launch_id = rec["launchId"]

        if event == "reserved":
            if launch_id in launches:
                return {
                    "ok": False,
                    "reason": "fold-duplicate-reserved:%s" % launch_id,
                    "launches": {},
                }
            launches[launch_id] = {
                "batchId": rec["batchId"],
                "surfaces": rec["surfaces"],
                "terminal": False,
                "outcome": None,
                "terminalKind": None,
                "reservedTs": rec["ts"],
                "attempts": 0,
                "started": False,
            }
            continue

        if launch_id not in launches:
            return {"ok": False, "reason": "fold-orphan-event:%s" % launch_id, "launches": {}}

        info = launches[launch_id]
        if info["terminal"]:
            return {
                "ok": False,
                "reason": "fold-conflicting-terminal:%s" % launch_id,
                "launches": {},
            }

        if event == "started":
            info["attempts"] += 1
            info["started"] = True
        elif event == "retry":
            if not info["started"]:
                return {
                    "ok": False,
                    "reason": "fold-retry-without-started:%s" % launch_id,
                    "launches": {},
                }
        elif event == "refused":
            info["terminal"] = True
            info["terminalKind"] = "refused"
        elif event == "outcome":
            if not info["started"]:
                return {
                    "ok": False,
                    "reason": "fold-outcome-without-started:%s" % launch_id,
                    "launches": {},
                }
            info["terminal"] = True
            info["terminalKind"] = "outcome"
            info["outcome"] = rec["outcome"]

    return {"ok": True, "reason": None, "launches": launches}


def _batch_declarations(records, batch_id):
    decls = []
    for rec in records:
        if rec.get("event") != "batch-declared":
            continue
        if rec.get("schema") != SCHEMA:
            continue
        if rec.get("batchId") != batch_id:
            continue
        expected = rec.get("expectedLaunches")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
            continue
        if not _is_number(rec.get("ts")):
            continue
        decls.append(expected)
    return decls


def declare_batch(repo_root, batch_id, expected_launches, env=None,
                  lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Record expected launch cardinality for a batch before any reserve."""
    if not isinstance(batch_id, str) or not batch_id.strip():
        return {"ok": False, "reason": "batch-id-empty"}
    if (not isinstance(expected_launches, int) or isinstance(expected_launches, bool)
            or expected_launches < 1):
        return {"ok": False, "reason": "batch-expected-invalid"}

    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {"ok": False, "reason": lp["reason"]}

    path = lp["path"]
    if not _prepare_ledger_parent(path):
        return {"ok": False, "reason": "ledger-repo-dir-insecure"}

    lock_path = _lock_path(path)
    if not _acquire_lock(lock_path, lock_timeout):
        return {"ok": False, "reason": "lock-unavailable"}

    try:
        read_result = read(path)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {"ok": False, "reason": "ledger-unreadable:%s" % state}

        event = {
            "event": "batch-declared",
            "batchId": batch_id,
            "expectedLaunches": expected_launches,
            "ts": time.time(),
            "schema": SCHEMA,
        }
        if not append(path, event):
            return {"ok": False, "reason": "ledger-append-failed"}
        return {"ok": True, "reason": None}
    finally:
        _release_lock(lock_path)


def reserve(repo_root, record, env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Reserve a launch under lock with overlap detection."""
    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {"ok": False, "reason": lp["reason"], "path": None}

    path = lp["path"]
    if not _prepare_ledger_parent(path):
        return {"ok": False, "reason": "ledger-repo-dir-insecure", "path": None}

    lock_path = _lock_path(path)
    if not _acquire_lock(lock_path, lock_timeout):
        return {"ok": False, "reason": "lock-unavailable", "path": None}

    try:
        read_result = read(path)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {"ok": False, "reason": "ledger-unreadable:%s" % state, "path": None}

        folded = fold(read_result["records"])
        if not folded["ok"]:
            return {"ok": False, "reason": folded["reason"], "path": None}

        norm = normalize_surfaces(repo_root, record.get("surfaces", []))
        if not norm["ok"]:
            return {"ok": False, "reason": norm["reason"], "path": None}

        new_surfaces = norm["surfaces"]
        for launch_id in live_launches(read_result["records"]):
            info = folded["launches"][launch_id]
            existing = info.get("surfaces") or []
            if surfaces_overlap(new_surfaces, existing):
                return {
                    "ok": False,
                    "reason": "surface-overlap:%s" % launch_id,
                    "blockingLaunchId": launch_id,
                    "blockingSurfaces": list(existing),
                    "path": None,
                }

        to_write = dict(record)
        to_write["surfaces"] = new_surfaces
        if not append(path, to_write):
            return {"ok": False, "reason": "ledger-append-failed", "path": None}
        return {"ok": True, "reason": None, "path": path}
    finally:
        _release_lock(lock_path)


def record_outcome(repo_root, launch_id, outcome, evidence, env=None,
                   lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Record a terminal outcome under lock."""
    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {"ok": False, "reason": lp["reason"]}

    if outcome not in TERMINAL_OUTCOMES:
        return {"ok": False, "reason": "outcome-invalid:%s" % outcome}
    if not isinstance(evidence, str) or not evidence.strip():
        return {"ok": False, "reason": "outcome-evidence-empty"}

    path = lp["path"]
    if not _prepare_ledger_parent(path):
        return {"ok": False, "reason": "ledger-repo-dir-insecure"}

    lock_path = _lock_path(path)
    if not _acquire_lock(lock_path, lock_timeout):
        return {"ok": False, "reason": "lock-unavailable"}

    try:
        read_result = read(path)
        state = read_result["state"]
        if state not in ("ok", "missing"):
            return {"ok": False, "reason": "ledger-unreadable:%s" % state}

        folded = fold(read_result["records"])
        if not folded["ok"]:
            return {"ok": False, "reason": folded["reason"]}

        if launch_id not in folded["launches"]:
            return {"ok": False, "reason": "outcome-unknown-launch"}

        info = folded["launches"][launch_id]
        if info.get("terminal"):
            return {"ok": False, "reason": "outcome-already-terminal"}

        if not info.get("started"):
            return {"ok": False, "reason": "outcome-without-started"}

        event = {
            "event": "outcome",
            "launchId": launch_id,
            "ts": time.time(),
            "schema": SCHEMA,
            "outcome": outcome,
            "evidence": evidence,
        }
        if not append(path, event):
            return {"ok": False, "reason": "ledger-append-failed"}
        return {"ok": True, "reason": None}
    finally:
        _release_lock(lock_path)


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
        "inspect": False,
        "inspectReason": "",
    }


def count(repo_root, batch_id, env=None):
    """R1 accounting — refuses to report a resolved batch it cannot ground."""
    lp = ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return _count_indeterminate(batch_id, lp["reason"])

    read_result = read(lp["path"])
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

    decls = _batch_declarations(read_result["records"], batch_id)
    if len(decls) == 0:
        return _count_indeterminate(batch_id, "batch-undeclared")
    if len(decls) > 1:
        return _count_indeterminate(batch_id, "batch-duplicate-declaration")
    if len(batch_launches) != decls[0]:
        return _count_indeterminate(batch_id, "batch-reservation-mismatch")

    counts = {
        "handback": 0,
        "park": 0,
        "refusal": 0,
        "died": 0,
        "refusedToLaunch": 0,
        "total": 0,
    }

    for lid in batch_launches:
        info = folded["launches"][lid]
        if not info.get("terminal"):
            return _count_indeterminate(batch_id, "batch-unresolved:%s" % lid)

    for lid in batch_launches:
        info = folded["launches"][lid]
        counts["total"] += 1
        if info.get("terminalKind") == "refused":
            counts["refusedToLaunch"] += 1
        elif info.get("terminalKind") == "outcome":
            outcome = info.get("outcome")
            if outcome in counts:
                counts[outcome] += 1

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
        "inspect": inspect,
        "inspectReason": _INSPECT_REASON if inspect else "",
    }
