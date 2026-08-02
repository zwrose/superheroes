#!/usr/bin/env python3
"""Durable forfeit ledger and attribution decider (#747).

Every terminal dispatched run leaves a structured row outside the session that
produced it — telemetry, evidence pointers, and an attribution. A forfeit is
presumed self-inflicted until attributed. Unknown is a queue, not a bucket —
unattributed forfeit is pending work.

The ledger is a record, never a control input: nothing here decides what a
dispatch does.
"""
import argparse
import fcntl
import hashlib
import json
import os
import stat
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import file_lock  # noqa: E402
import launch_ledger as ll  # noqa: E402
from dispatch_outcome import (  # noqa: E402
    ATTRIBUTION_CALLER_ERROR,
    ATTRIBUTION_ENGINE_SIDE,
    ATTRIBUTION_ENVIRONMENT,
    ATTRIBUTION_TRANSPORT,
    ATTRIBUTION_UNKNOWN,
    ATTRIBUTIONS,
    FORFEIT_REASONS,
    REASON_UNRUNNABLE,
    is_forfeit,
)

LEDGER_ROOT_ENV = "SUPERHEROES_FORFEIT_LEDGER_ROOT"
FORFEIT_LEDGER_ROOT_DIR = "superheroes-forfeit-ledger"
FORFEIT_LEDGER_FILE = "forfeit-ledger.jsonl"
SCHEMA = 1
ACTIVE_SILENCE_SECONDS = 60

_LOCK_SUFFIX = ".lock"
_LOCK_NAME = FORFEIT_LEDGER_FILE + _LOCK_SUFFIX
_DEFAULT_LOCK_TIMEOUT = 30.0
_COMPLETENESS_LEDGER_ONLY = "ledger-only"
_COMPLETENESS_CAVEAT = (
    "ledger-only: a run whose append failed is invisible to this summary"
)
_COMPLETENESS_PARTIAL = "ledger-partial"
_COMPLETENESS_PARTIAL_CAVEAT = (
    "ledger-partial: interior corruption dropped rows from this summary"
)
_REASON_KEY_OK = "ok"


def run_id_from_run_dir(run_dir):
    """Stable digest of a run directory's real path; never raises."""
    if not run_dir or not isinstance(run_dir, str):
        return None
    try:
        real = os.path.realpath(run_dir)
    except OSError:
        return None
    return hashlib.sha256(real.encode("utf-8")).hexdigest()


def _validate_resolved_root(repo_root, root, env):
    if not ll._has_git_entry(repo_root):
        return False
    if ll.repo_identity(repo_root) is None:
        return False
    return ll.validate_candidate_root(repo_root, root, env=env)


def _resolve_root(repo_root, env=None):
    """Resolve ledger root outside the repo; refuse in-repo paths. Never raises."""
    if env is None:
        env = os.environ
    if ll.repo_identity(repo_root) is None:
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}

    override = env.get(LEDGER_ROOT_ENV)
    root = override if override else os.path.join(tempfile.gettempdir(), FORFEIT_LEDGER_ROOT_DIR)
    try:
        root = os.path.realpath(os.path.abspath(root))
    except OSError:
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    if not _validate_resolved_root(repo_root, root, env):
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    return {"ok": True, "root": root, "reason": None}


def ledger_path(repo_root, env=None):
    """Absolute path to this repo's ledger file, or None on failure. Never raises."""
    resolved = _resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return None
    repo_id = ll.repo_identity(repo_root)
    if repo_id is None:
        return None
    return os.path.join(resolved["root"], repo_id, FORFEIT_LEDGER_FILE)


def _lock_path(ledger_file):
    return ledger_file + _LOCK_SUFFIX


def _close_fd(fd):
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass


def _clear_nonblock(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)


def _is_fd_group_or_world_accessible(fd):
    try:
        mode = os.fstat(fd).st_mode & 0o777
        return bool(mode & 0o077)
    except OSError:
        return True


def _can_repair_regular_file_fd(fd):
    """True when fd is our regular file with link count 1."""
    try:
        st = os.fstat(fd)
    except OSError:
        return False
    if not stat.S_ISREG(st.st_mode):
        return False
    if st.st_uid != os.geteuid():
        return False
    return st.st_nlink == 1


def _repair_regular_file_fd(fd):
    """fchmod our regular file (nlink==1) to 0600. Never raises."""
    if not _can_repair_regular_file_fd(fd):
        return False
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        return False
    return not _is_fd_group_or_world_accessible(fd)


def _can_repair_dir_fd(fd):
    """True when fd is our directory."""
    try:
        st = os.fstat(fd)
    except OSError:
        return False
    if not stat.S_ISDIR(st.st_mode):
        return False
    return st.st_uid == os.geteuid()


def _repair_dir_fd(fd):
    """fchmod our directory to 0700. Never raises."""
    if not _can_repair_dir_fd(fd):
        return False
    try:
        os.fchmod(fd, 0o700)
    except OSError:
        return False
    return not _is_fd_group_or_world_accessible(fd)


def _ensure_regular_file_fd_secure(fd):
    """Refuse hardlinks and foreign owners; repair permissive modes on our file."""
    try:
        st = os.fstat(fd)
    except OSError:
        return False
    if not stat.S_ISREG(st.st_mode):
        return False
    if st.st_uid != os.geteuid():
        return False
    if st.st_nlink != 1:
        return False
    if not _is_fd_group_or_world_accessible(fd):
        return True
    return _repair_regular_file_fd(fd)


def _ensure_fd_secure(fd, *, is_dir=False):
    """Repair permissive modes on our fds; refuse only what we cannot make safe."""
    if is_dir:
        if not _is_fd_group_or_world_accessible(fd):
            return True
        return _repair_dir_fd(fd)
    return _ensure_regular_file_fd_secure(fd)


def _ledger_open_refusal(reason, root_fd=None, repo_fd=None, ledger_fd=None):
    _close_fd(ledger_fd)
    _close_fd(repo_fd)
    _close_fd(root_fd)
    return {"ok": False, "reason": reason, "fh": None, "path": None}


def _open_ledger_dirs(repo_root, env=None):
    """Open validated root and repo-id directory fds. Never raises."""
    if env is None:
        env = os.environ

    resolved = _resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return {"ok": False, "reason": resolved["reason"], "root_fd": None,
                "repo_fd": None, "root": None, "repo_id": None}

    repo_id = ll.repo_identity(repo_root)
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

    if not _ensure_fd_secure(root_fd, is_dir=True):
        return _ledger_open_refusal(
            "ledger-root-insecure", root_fd=root_fd,
        )

    try:
        os.mkdir(repo_id, mode=0o700, dir_fd=root_fd)
    except FileExistsError:
        pass
    except OSError:
        return _ledger_open_refusal("ledger-repo-dir-unusable", root_fd=root_fd)

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
        return _ledger_open_refusal(reason, root_fd=root_fd)

    if not _ensure_fd_secure(repo_fd, is_dir=True):
        return _ledger_open_refusal(
            "ledger-repo-dir-insecure", root_fd=root_fd, repo_fd=repo_fd,
        )

    return {
        "ok": True,
        "reason": None,
        "root_fd": root_fd,
        "repo_fd": repo_fd,
        "root": root,
        "repo_id": repo_id,
    }


def open_ledger(repo_root, mode, env=None):
    """The only way to obtain a ledger file handle. Never raises."""
    if mode not in ("r", "a", "w"):
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
                    FORFEIT_LEDGER_FILE,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=repo_fd,
                )
            except FileNotFoundError:
                _close_fd(repo_fd)
                _close_fd(root_fd)
                return {"ok": False, "reason": "ledger-missing", "fh": None, "path": None}
            except OSError:
                reason = "ledger-file-unusable"
                ledger_path_str = os.path.join(root, repo_id, FORFEIT_LEDGER_FILE)
                if os.path.islink(ledger_path_str):
                    reason = "ledger-file-symlink"
                return _ledger_open_refusal(
                    reason, root_fd=root_fd, repo_fd=repo_fd, ledger_fd=ledger_fd,
                )
        elif mode == "w":
            try:
                ledger_fd = os.open(
                    FORFEIT_LEDGER_FILE,
                    os.O_WRONLY | os.O_TRUNC | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                    mode=0o600,
                    dir_fd=repo_fd,
                )
            except OSError:
                reason = "ledger-file-unusable"
                ledger_path_str = os.path.join(root, repo_id, FORFEIT_LEDGER_FILE)
                if os.path.islink(ledger_path_str):
                    reason = "ledger-file-symlink"
                return _ledger_open_refusal(
                    reason, root_fd=root_fd, repo_fd=repo_fd, ledger_fd=ledger_fd,
                )
        else:
            try:
                ledger_fd = os.open(
                    FORFEIT_LEDGER_FILE,
                    os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                    mode=0o600,
                    dir_fd=repo_fd,
                )
            except OSError:
                reason = "ledger-file-unusable"
                ledger_path_str = os.path.join(root, repo_id, FORFEIT_LEDGER_FILE)
                if os.path.islink(ledger_path_str):
                    reason = "ledger-file-symlink"
                else:
                    try:
                        st = os.stat(
                            FORFEIT_LEDGER_FILE, dir_fd=repo_fd, follow_symlinks=False,
                        )
                        if not stat.S_ISREG(st.st_mode):
                            reason = "ledger-file-not-regular"
                    except OSError:
                        pass
                return _ledger_open_refusal(
                    reason, root_fd=root_fd, repo_fd=repo_fd, ledger_fd=ledger_fd,
                )

        st = os.fstat(ledger_fd)
        if not stat.S_ISREG(st.st_mode):
            return _ledger_open_refusal(
                "ledger-file-not-regular",
                root_fd=root_fd,
                repo_fd=repo_fd,
                ledger_fd=ledger_fd,
            )
        # axis: that a 0644 ledger stays writable — not that a mode check exists.
        if not _ensure_fd_secure(ledger_fd, is_dir=False):
            return _ledger_open_refusal(
                "ledger-file-insecure",
                root_fd=root_fd,
                repo_fd=repo_fd,
                ledger_fd=ledger_fd,
            )

        _clear_nonblock(ledger_fd)
        ledger_path_str = os.path.join(root, repo_id, FORFEIT_LEDGER_FILE)
        if mode == "r":
            fh = os.fdopen(ledger_fd, "rb")
        elif mode == "w":
            fh = os.fdopen(ledger_fd, "wb")
        else:
            fh = os.fdopen(ledger_fd, "ab")
        ledger_fd = None
        _close_fd(repo_fd)
        repo_fd = None
        _close_fd(root_fd)
        root_fd = None
        return {"ok": True, "reason": None, "fh": fh, "path": ledger_path_str}
    except OSError:
        return _ledger_open_refusal(
            "ledger-file-unusable",
            root_fd=root_fd,
            repo_fd=repo_fd,
            ledger_fd=ledger_fd,
        )


def _ensure_lock_file(repo_root, env=None):
    """Validate the lock path before acquire. Never raises."""
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
            _close_fd(root_fd)
            return {"ok": True, "reason": None, "path": lock_path}
        except OSError:
            lock_path = os.path.join(root, repo_id, _LOCK_NAME)
            if os.path.islink(lock_path):
                return _ledger_open_refusal(
                    "ledger-lock-symlink", root_fd=root_fd, repo_fd=repo_fd,
                )
            return _ledger_open_refusal(
                "ledger-lock-unusable", root_fd=root_fd, repo_fd=repo_fd,
            )

        st = os.fstat(lock_fd)
        if not stat.S_ISREG(st.st_mode):
            return _ledger_open_refusal(
                "ledger-lock-not-regular",
                root_fd=root_fd,
                repo_fd=repo_fd,
                ledger_fd=lock_fd,
            )
        lock_path = os.path.join(root, repo_id, _LOCK_NAME)
        _close_fd(lock_fd)
        lock_fd = None
        _close_fd(repo_fd)
        repo_fd = None
        _close_fd(root_fd)
        root_fd = None
        return {"ok": True, "reason": None, "path": lock_path}
    except OSError:
        return _ledger_open_refusal(
            "ledger-lock-unusable",
            root_fd=root_fd,
            repo_fd=repo_fd,
            ledger_fd=lock_fd,
        )


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


def _parse_ledger_bytes(raw):
    """Parse ledger bytes; skip torn trailing write; flag interior corruption.

    axis: classification of damage — torn trailing skipped, interior corruption flagged.
    """
    records = []
    interior_corrupt = False
    if not raw:
        return records, interior_corrupt
    torn = raw[-1:] != b"\n"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return records, True
    lines = text.split("\n")
    if torn:
        lines.pop()
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
    return records, interior_corrupt


def _valid_ledger_prefix(raw):
    """Bytes through the last complete newline; empty when nothing is valid."""
    if not raw:
        return b""
    if raw[-1:] == b"\n":
        return raw
    last_nl = raw.rfind(b"\n")
    if last_nl < 0:
        return b""
    return raw[:last_nl + 1]


def read(repo_root, env=None):
    """Return (rows, interior_corrupt). Never raises."""
    opened = open_ledger(repo_root, "r", env=env)
    if opened["ok"]:
        try:
            raw = opened["fh"].read()
        except OSError:
            return [], False
        finally:
            opened["fh"].close()
        return _parse_ledger_bytes(raw)

    # axis: that a refused open yields no rows — not that the refusal is computed.
    if opened["reason"] == "ledger-missing":
        return [], False

    return [], False


def _atomic_replace_ledger(repo_root, content_bytes, env=None):
    """Write ledger bytes via temp file + dir-fd rename. False on failure; never raises.

    axis: that an interrupted repair preserves prior rows — not that repair works.
    """
    opened = _open_ledger_dirs(repo_root, env=env)
    if not opened["ok"]:
        return False

    root_fd = opened["root_fd"]
    repo_fd = opened["repo_fd"]
    tmp_name = ".forfeit-ledger.%d.tmp" % os.getpid()
    tmp_fd = None
    try:
        try:
            tmp_fd = os.open(
                tmp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                mode=0o600,
                dir_fd=repo_fd,
            )
        except OSError:
            return False

        try:
            with os.fdopen(tmp_fd, "wb") as fh:
                tmp_fd = None
                fh.write(content_bytes)
                fh.flush()
                os.fsync(fh.fileno())
        except (OSError, TypeError, ValueError):
            return False
        finally:
            _close_fd(tmp_fd)

        try:
            os.rename(
                tmp_name,
                FORFEIT_LEDGER_FILE,
                src_dir_fd=repo_fd,
                dst_dir_fd=repo_fd,
            )
        except OSError:
            return False

        try:
            os.fsync(repo_fd)
        except OSError:
            pass
        return True
    finally:
        try:
            os.unlink(tmp_name, dir_fd=repo_fd)
        except OSError:
            pass
        _close_fd(repo_fd)
        _close_fd(root_fd)


def _append_raw(repo_root, row, env=None, existing_raw=None):
    """Append one JSON line with flush+fsync. False on failure; never raises.

    axis: where the write lands — O_NOFOLLOW containment with torn-tail repair.
    """
    line_bytes = None
    try:
        line = json.dumps(row, separators=(",", ":")) + "\n"
        line_bytes = line.encode("utf-8")
    except (TypeError, ValueError):
        return False

    if existing_raw is None:
        opened = open_ledger(repo_root, "r", env=env)
        if opened["ok"]:
            try:
                existing_raw = opened["fh"].read()
            except OSError:
                return False
            finally:
                opened["fh"].close()
        elif opened["reason"] == "ledger-missing":
            existing_raw = b""
        else:
            return False

    valid_prefix = _valid_ledger_prefix(existing_raw)
    torn = len(valid_prefix) < len(existing_raw)

    if torn:
        return _atomic_replace_ledger(
            repo_root, valid_prefix + line_bytes, env=env,
        )

    opened = open_ledger(repo_root, "a", env=env)
    if not opened["ok"]:
        return False
    try:
        opened["fh"].write(line_bytes)
        opened["fh"].flush()
        os.fsync(opened["fh"].fileno())
    except (OSError, TypeError, ValueError):
        return False
    finally:
        opened["fh"].close()
    return True


def append(repo_root, row, env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Append one row under lock; idempotent per runId. Never raises.

    axis: failure containment — OSError returns written=False, never reaches callers.

    Returns {"written": bool, "deduped": bool, "path": str|None, "why": str|None}.
    """
    failure = {"written": False, "deduped": False, "path": None, "why": None}
    if not isinstance(row, dict):
        failure["why"] = "row-not-a-dict"
        return failure

    run_id = row.get("runId")
    if not run_id:
        run_dir = row.get("runDir")
        run_id = run_id_from_run_dir(run_dir) if run_dir else None
        if run_id:
            row = dict(row)
            row["runId"] = run_id
    if not run_id:
        failure["why"] = "run-id-unavailable"
        return failure

    path = ledger_path(repo_root, env=env)
    if path is None:
        failure["why"] = "ledger-path-unavailable"
        return failure

    lock_result = _ensure_lock_file(repo_root, env=env)
    if not lock_result["ok"]:
        failure["why"] = lock_result["reason"]
        return failure

    lock_path = lock_result["path"]
    if not _acquire_lock(lock_path, lock_timeout):
        failure["why"] = "lock-unavailable"
        return failure

    try:
        opened = open_ledger(repo_root, "r", env=env)
        if opened["ok"]:
            try:
                existing_raw = opened["fh"].read()
            except OSError:
                failure["why"] = "ledger-read-failed"
                failure["path"] = path
                return failure
            finally:
                opened["fh"].close()
        elif opened["reason"] == "ledger-missing":
            existing_raw = b""
        else:
            failure["why"] = opened["reason"]
            failure["path"] = path
            return failure

        existing, _ = _parse_ledger_bytes(existing_raw)
        for prior in existing:
            if prior.get("runId") == run_id:
                return {
                    "written": True,
                    "deduped": True,
                    "path": path,
                    "why": None,
                }

        # axis: refusal to double-count a continuation — skip when runId already present.
        if not _append_raw(repo_root, row, env=env, existing_raw=existing_raw):
            failure["why"] = "ledger-append-failed"
            failure["path"] = path
            return failure
        return {"written": True, "deduped": False, "path": path, "why": None}
    finally:
        _release_lock(lock_path)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _attribution_from_refusal(refusal):
    """Map runner refusal to attribution; None when absent; unknown when unrecognised."""
    if not refusal or not isinstance(refusal, str):
        return None
    if refusal.startswith("spawn-failed:"):
        return ATTRIBUTION_ENVIRONMENT
    if refusal == "journal-append-failed":
        return ATTRIBUTION_ENVIRONMENT
    return ATTRIBUTION_UNKNOWN


def _attempt_is_engine_side(attempt):
    if not isinstance(attempt, dict):
        return False
    refusal = attempt.get("refusal")
    if isinstance(refusal, str) and refusal:
        return False
    if attempt.get("signalSource") == "engine":
        return True
    exit_code = attempt.get("exit")
    if exit_code is not None and exit_code != 0:
        if not attempt.get("timedOut") and attempt.get("signalSource") != "runner-timeout":
            return True
    return False


def classify_attempt(attempt, row):
    """Return attribution for one attempt. Pure; never raises.

    axis: which class a runner-inflicted failure books to — refusal precedes exit-code rules.
    """
    if not isinstance(attempt, dict):
        return {
            "class": ATTRIBUTION_UNKNOWN,
            "why": "attempt record missing or not a dict",
        }

    refusal = attempt.get("refusal")
    refusal_class = _attribution_from_refusal(refusal)
    if refusal_class is not None:
        if refusal_class == ATTRIBUTION_UNKNOWN:
            return {
                "class": ATTRIBUTION_UNKNOWN,
                "why": "unrecognised runner refusal: %s" % refusal,
            }
        return {
            "class": refusal_class,
            "why": "runner refusal: %s" % refusal,
        }

    signal_source = attempt.get("signalSource")
    if signal_source == "engine":
        sig = attempt.get("signal")
        return {
            "class": ATTRIBUTION_ENGINE_SIDE,
            "why": "engine delivered signal %s (signalSource engine)" % sig,
        }

    exit_code = attempt.get("exit")
    timed_out = attempt.get("timedOut")
    if exit_code is not None and exit_code != 0:
        if not timed_out and signal_source != "runner-timeout":
            return {
                "class": ATTRIBUTION_ENGINE_SIDE,
                "why": "exit %s without runner timeout attribution" % exit_code,
            }

    silence = attempt.get("silenceSeconds")
    if timed_out and _is_number(silence) and silence <= ACTIVE_SILENCE_SECONDS:
        cap = attempt.get("capSeconds")
        return {
            "class": ATTRIBUTION_ENVIRONMENT,
            "why": "timed out with silenceSeconds=%s under capSeconds=%s" % (silence, cap),
        }

    stages = row.get("stages") if isinstance(row.get("stages"), dict) else {}
    stdout_bytes = attempt.get("stdoutBytes")
    if (
        not timed_out
        and exit_code == 0
        and _is_number(stdout_bytes)
        and stdout_bytes > 0
        and stages.get("delivered") is False
    ):
        return {
            "class": ATTRIBUTION_TRANSPORT,
            "why": "exit 0 with stdout but stages.delivered is False",
        }

    parts = []
    if timed_out:
        parts.append("timedOut=True")
    if silence is not None:
        parts.append("silenceSeconds=%s" % silence)
    if exit_code is not None:
        parts.append("exit=%s" % exit_code)
    if not parts:
        parts.append("insufficient attempt telemetry")
    return {
        "class": ATTRIBUTION_UNKNOWN,
        "why": "would need timeout silence, engine signal, or transport shape; saw %s"
        % ", ".join(parts),
    }


def _matches_caller_error(row):
    return (
        row.get("reason") == REASON_UNRUNNABLE
        and row.get("attemptCount") == 0
    )


def _run_refusal_attribution(row):
    """Run-level attribution from runner refusal when present on any attempt."""
    for attempt in row.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        refusal = attempt.get("refusal")
        refusal_class = _attribution_from_refusal(refusal)
        if refusal_class is not None:
            if refusal_class == ATTRIBUTION_UNKNOWN:
                return {
                    "class": ATTRIBUTION_UNKNOWN,
                    "why": "unrecognised runner refusal: %s" % refusal,
                }
            return {
                "class": refusal_class,
                "why": "runner refusal: %s" % refusal,
            }
    return None


def _matches_engine_side(row):
    for attempt in row.get("attempts") or []:
        if _attempt_is_engine_side(attempt):
            return True
    return False


def _matches_environment(row):
    for attempt in row.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        if attempt.get("timedOut"):
            silence = attempt.get("silenceSeconds")
            if _is_number(silence) and silence <= ACTIVE_SILENCE_SECONDS:
                return True
    return False


def _matches_transport(row):
    attempts = row.get("attempts") or []
    if not attempts:
        return False
    stages = row.get("stages") if isinstance(row.get("stages"), dict) else {}
    if stages.get("delivered") is not False:
        return False
    for attempt in attempts:
        if not isinstance(attempt, dict):
            return False
        if attempt.get("timedOut"):
            return False
        if attempt.get("exit") != 0:
            return False
    return any(
        _is_number(att.get("stdoutBytes")) and att.get("stdoutBytes") > 0
        for att in attempts
        if isinstance(att, dict)
    )


def _run_level_attribution(row):
    """Derive run-level class by stated precedence. Pure."""
    if _matches_caller_error(row):
        detail = row.get("detail") or "unrunnable before spawn"
        return {
            "class": ATTRIBUTION_CALLER_ERROR,
            "why": "unrunnable before any engine spawned: %s" % detail,
        }
    refusal_attr = _run_refusal_attribution(row)
    if refusal_attr is not None:
        return refusal_attr
    if _matches_engine_side(row):
        return {
            "class": ATTRIBUTION_ENGINE_SIDE,
            "why": "engine-side signal or exit on at least one attempt",
        }
    if _matches_environment(row):
        for attempt in row.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            if attempt.get("timedOut"):
                silence = attempt.get("silenceSeconds")
                if _is_number(silence) and silence <= ACTIVE_SILENCE_SECONDS:
                    cap = attempt.get("capSeconds")
                    return {
                        "class": ATTRIBUTION_ENVIRONMENT,
                        "why": "timed out with silenceSeconds=%s under capSeconds=%s"
                        % (silence, cap),
                    }
        return {
            "class": ATTRIBUTION_ENVIRONMENT,
            "why": "runner cap fired while output was still moving",
        }
    if _matches_transport(row):
        return {
            "class": ATTRIBUTION_TRANSPORT,
            "why": "every attempt exit 0 with stdout but stages.delivered is False",
        }
    return {
        "class": ATTRIBUTION_UNKNOWN,
        "why": "no precedence rule matched; need more telemetry",
    }


def classify(row):
    """Classify each attempt, then the run. Mutates attempts with attribution. Pure.

    axis: which cause wins when attempts disagree — precedence order sets mixed when they differ.
    """
    if not isinstance(row, dict):
        return {
            "class": ATTRIBUTION_UNKNOWN,
            "why": "row missing or not a dict",
        }

    attempts = row.get("attempts")
    if attempts is None:
        attempts = []
    attempt_classes = []
    for attempt in attempts:
        if isinstance(attempt, dict):
            att = classify_attempt(attempt, row)
            attempt["attribution"] = att
            attempt_classes.append(att["class"])

    run_attr = _run_level_attribution(row)
    unique_classes = set(attempt_classes)
    if len(unique_classes) > 1:
        causes = []
        for attempt in attempts:
            if isinstance(attempt, dict) and "attribution" in attempt:
                att = attempt["attribution"]
                causes.append("%s (%s)" % (att["class"], att["why"]))
        run_attr = dict(run_attr)
        run_attr["mixed"] = True
        run_attr["why"] = (
            "mixed causes: %s; run-level precedence chose %s"
            % ("; ".join(causes), run_attr["class"])
        )
    return run_attr


def build_row(
    *,
    at=None,
    run_dir=None,
    order_id=None,
    engine=None,
    engine_model=None,
    run_kind=None,
    reason=None,
    detail=None,
    attempt_count=None,
    attempts=None,
    stages=None,
    engagement=None,
    evidence=None,
    ok=None,
):
    """Assemble one ledger row from runner inputs. Pure; no I/O."""
    if at is None:
        at = time.time()
    if attempts is None:
        attempts = []
    if stages is None:
        stages = {"engaged": None, "delivered": None}
    if evidence is None:
        evidence = {
            "stdoutPaths": [],
            "stderrPaths": [],
            "journalPath": None,
            "promptPath": None,
        }

    row = {
        "at": at,
        "schema": SCHEMA,
        "runDir": run_dir,
        "runId": run_id_from_run_dir(run_dir) if run_dir else None,
        "orderId": order_id,
        "engine": engine,
        "engineModel": engine_model,
        "runKind": run_kind,
        "reason": reason,
        "detail": detail,
        "attemptCount": attempt_count,
        "attempts": [dict(a) for a in attempts if isinstance(a, dict)],
        "stages": dict(stages) if isinstance(stages, dict) else stages,
        "engagement": engagement,
        "evidence": dict(evidence) if isinstance(evidence, dict) else evidence,
        "salvage": None,
        "ok": ok if ok is not None else (reason is None),
    }
    if row["ok"]:
        row["attribution"] = None
    else:
        row["attribution"] = classify(row)
    return row


def summarize(rows, *, window_seconds=None, now=None, interior_corrupt=False):
    """Standing accounting over ledger rows. Pure.

    axis: the denominator includes successes — rates use every terminal row in the window.
    """
    if now is None:
        now = time.time()
    if window_seconds is None:
        window = {"seconds": None, "from": None, "to": now}
        filtered = list(rows)
    else:
        cutoff = now - window_seconds
        window = {"seconds": window_seconds, "from": cutoff, "to": now}
        filtered = [
            r for r in rows
            if isinstance(r, dict) and _is_number(r.get("at")) and r["at"] >= cutoff
        ]

    total = len(filtered)
    by_reason = {}
    by_attribution = {key: 0 for key in sorted(ATTRIBUTIONS)}
    by_engine = {}
    salvage_count = 0
    forfeit_count = 0
    unattributed = 0

    for row in filtered:
        if not isinstance(row, dict):
            continue
        reason = row.get("reason")
        # axis: byReason keys are strings so mixed success/forfeit ledgers JSON-serialise.
        reason_key = reason if isinstance(reason, str) else _REASON_KEY_OK
        by_reason[reason_key] = by_reason.get(reason_key, 0) + 1
        if is_forfeit(reason):
            forfeit_count += 1
        # axis: who is counted as unattributed — successes carry no attribution.
        is_success = row.get("ok") is True and reason is None
        if not is_success:
            attr = row.get("attribution")
            if isinstance(attr, dict):
                cls = attr.get("class")
                if cls in by_attribution:
                    by_attribution[cls] += 1
                else:
                    by_attribution[ATTRIBUTION_UNKNOWN] += 1
                if cls == ATTRIBUTION_UNKNOWN or cls not in ATTRIBUTIONS:
                    unattributed += 1
            else:
                by_attribution[ATTRIBUTION_UNKNOWN] += 1
                unattributed += 1
        engine = row.get("engine")
        if engine is not None:
            by_engine[engine] = by_engine.get(engine, 0) + 1
        salvage = row.get("salvage")
        if isinstance(salvage, dict) and salvage.get("detected"):
            salvage_count += 1

    salvage_rate = salvage_count / total if total > 0 else None
    forfeit_rate = forfeit_count / total if total > 0 else None

    completeness = _COMPLETENESS_LEDGER_ONLY
    completeness_caveat = _COMPLETENESS_CAVEAT
    if interior_corrupt:
        completeness = _COMPLETENESS_PARTIAL
        completeness_caveat = _COMPLETENESS_PARTIAL_CAVEAT

    return {
        "window": window,
        "total": total,
        "byReason": by_reason,
        "byAttribution": by_attribution,
        "byEngine": by_engine,
        "forfeit": {"count": forfeit_count, "rate": forfeit_rate},
        "salvage": {"count": salvage_count, "rate": salvage_rate},
        "unattributed": unattributed,
        "interiorCorrupt": interior_corrupt,
        "completeness": completeness,
        "completenessCaveat": completeness_caveat,
    }


def _format_human_summary(summary):
    window = summary["window"]
    if window["seconds"] is None:
        window_line = "window: all rows (to %s)" % window["to"]
    else:
        window_line = "window: %ss from %s to %s" % (
            window["seconds"], window["from"], window["to"],
        )
    lines = [window_line, "total: %d" % summary["total"]]
    for cls in sorted(ATTRIBUTIONS):
        lines.append("%s: %d" % (cls, summary["byAttribution"][cls]))
    forfeit = summary.get("forfeit", {})
    lines.append(
        "forfeit: count=%d rate=%s" % (
            forfeit.get("count", 0),
            forfeit.get("rate"),
        )
    )
    salvage = summary["salvage"]
    lines.append(
        "salvage: count=%d rate=%s" % (salvage["count"], salvage["rate"])
    )
    lines.append("unattributed: %d" % summary["unattributed"])
    lines.append("completeness: %s" % summary["completeness"])
    if summary.get("interiorCorrupt"):
        lines.append("interior-corrupt: rows dropped from this summary")
    return "\n".join(lines)


def _cmd_report(args):
    rows, interior_corrupt = read(args.repo_root)
    if interior_corrupt and not rows:
        print("ledger unreadable: interior corruption", file=sys.stderr)
        return 1
    summary = summarize(
        rows,
        window_seconds=args.window_seconds,
        interior_corrupt=interior_corrupt,
    )
    if args.json:
        print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
    else:
        print(_format_human_summary(summary))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forfeit ledger report")
    sub = parser.add_subparsers(dest="command")
    report = sub.add_parser("report")
    report.add_argument("--repo-root", required=True)
    report.add_argument("--window-seconds", type=float, default=None)
    report.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "report":
        return _cmd_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
