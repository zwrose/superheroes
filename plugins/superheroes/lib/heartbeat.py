#!/usr/bin/env python3
"""Semantic builder heartbeat — builder stamps state; advisor sweeps.

Fail-closed: a false \"fresh\" is the dangerous answer. Never raises to callers.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
from datetime import datetime, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import launch_ledger as ll  # noqa: E402

HEARTBEAT_ROOT_ENV = "SUPERHEROES_HEARTBEAT_ROOT"
LAUNCH_ID_ENV = "SUPERHEROES_LAUNCH_ID"
HEARTBEATS_DIR_NAME = "heartbeats"
SCHEMA = 1

STATES = frozenset({
    "working",
    "awaiting-dispatch",
    "blocked",
    "parked",
    "handback",
})
TERMINAL_STATES = frozenset({"parked", "handback"})
SWEEP_CLASSES = frozenset({"fresh", "stale", "terminal", "unknown"})

REASON_LAUNCH_ID_UNAVAILABLE = "heartbeat-launch-id-unavailable"
REASON_LAUNCH_ID_INVALID = "heartbeat-launch-id-invalid"
REASON_ROOT_UNRESOLVED = "heartbeat-root-unresolved"
REASON_REPO_IDENTITY_UNAVAILABLE = "heartbeat-repo-identity-unavailable"
REASON_WRITE_FAILED = "heartbeat-write-failed"
REASON_LEDGER_UNREADABLE = "heartbeat-ledger-unreadable"
REASON_HEARTBEAT_MISSING = "heartbeat-missing"

_LAUNCH_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_STALE_AFTER_MIN = 1
_STALE_AFTER_MAX = 86400
_NOTE_MAX_LEN = 500
_PHASE_MIN_LEN = 1
_PHASE_MAX_LEN = 64


def _reject_constant(_tok):
    raise ValueError("non-finite JSON constant")


def _is_finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_positive_int(value, *, min_val, max_val):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and min_val <= value <= max_val
    )


def _path_inside(parent, child):
    parent = os.path.realpath(parent)
    child = os.path.realpath(child)
    return child == parent or child.startswith(parent + os.sep)


def _is_iso8601_utc(value):
    if not isinstance(value, str) or not value:
        return False
    text = value.strip()
    if not text.endswith("Z"):
        return False
    try:
        dt = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return False
    return dt.tzinfo is not None


def _validate_resolved_root(repo_root, root, env):
    if not ll._has_git_entry(repo_root):
        return False
    if ll.repo_identity(repo_root) is None:
        return False
    return ll.validate_candidate_root(repo_root, root, env=env)


def _fail(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _ok(**extra):
    out = {"ok": True, "reason": None}
    out.update(extra)
    return out


def resolve_root(repo_root, env=None):
    """Resolve heartbeat store root. Never raises."""
    if env is None:
        env = os.environ
    override = env.get(HEARTBEAT_ROOT_ENV)
    if override:
        try:
            root = os.path.realpath(os.path.abspath(override))
        except OSError:
            return _fail(REASON_ROOT_UNRESOLVED, root=None)
        if not _validate_resolved_root(repo_root, root, env):
            if ll.repo_identity(repo_root) is None:
                return _fail(REASON_REPO_IDENTITY_UNAVAILABLE, root=None)
            return _fail(REASON_ROOT_UNRESOLVED, root=None)
        return _ok(root=root)
    resolved = ll.resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        reason = resolved["reason"]
        if reason == "ledger-repo-identity-unavailable":
            return _fail(REASON_REPO_IDENTITY_UNAVAILABLE, root=None)
        return _fail(REASON_ROOT_UNRESOLVED, root=None)
    return _ok(root=resolved["root"])


def _validate_launch_id(launch_id):
    if not isinstance(launch_id, str) or not launch_id:
        return False
    if not _LAUNCH_ID_RE.match(launch_id):
        return False
    if "/" in launch_id or "\\" in launch_id or ".." in launch_id:
        return False
    return True


def heartbeat_path(repo_root, launch_id, env=None):
    """Pure path query for one heartbeat file. Never raises."""
    if not _validate_launch_id(launch_id):
        return _fail(REASON_LAUNCH_ID_INVALID, path=None)
    resolved = resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return _fail(resolved["reason"], path=None)
    repo_id = ll.repo_identity(repo_root)
    if repo_id is None:
        return _fail(REASON_REPO_IDENTITY_UNAVAILABLE, path=None)
    path = os.path.join(
        resolved["root"],
        repo_id,
        HEARTBEATS_DIR_NAME,
        "%s.json" % launch_id,
    )
    return _ok(path=path)


def _heartbeat_dir(repo_root, env=None):
    resolved = resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return resolved
    repo_id = ll.repo_identity(repo_root)
    if repo_id is None:
        return _fail(REASON_REPO_IDENTITY_UNAVAILABLE, dir=None)
    directory = os.path.join(resolved["root"], repo_id, HEARTBEATS_DIR_NAME)
    return _ok(dir=directory, root=resolved["root"], repo_id=repo_id)


def _ensure_heartbeat_store(repo_root, env=None):
    """Create validated heartbeat store dirs with 0o700 on every level. Never raises."""
    dir_result = _heartbeat_dir(repo_root, env=env)
    if not dir_result["ok"]:
        return dir_result
    root = dir_result["root"]
    repo_id = dir_result["repo_id"]
    root_fd = None
    repo_fd = None
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        if ll._is_fd_group_or_world_accessible(root_fd):
            return _fail(REASON_ROOT_UNRESOLVED, dir=None)
        try:
            os.mkdir(repo_id, mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            pass
        except OSError:
            return _fail(REASON_WRITE_FAILED, dir=None)
        try:
            repo_fd = os.open(
                repo_id,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY,
                dir_fd=root_fd,
            )
        except OSError:
            return _fail(REASON_WRITE_FAILED, dir=None)
        if ll._is_fd_group_or_world_accessible(repo_fd):
            return _fail(REASON_ROOT_UNRESOLVED, dir=None)
        try:
            os.mkdir(HEARTBEATS_DIR_NAME, mode=0o700, dir_fd=repo_fd)
        except FileExistsError:
            pass
        except OSError:
            return _fail(REASON_WRITE_FAILED, dir=None)
    except OSError:
        return _fail(REASON_WRITE_FAILED, dir=None)
    finally:
        if repo_fd is not None:
            try:
                os.close(repo_fd)
            except OSError:
                pass
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError:
                pass
    return _ok(dir=dir_result["dir"])


def _validate_last_dispatch(value):
    if value is None:
        return True, None
    if not isinstance(value, dict):
        return False, "heartbeat-last-dispatch-invalid"
    required = ("kind", "engine", "model", "runId", "startedAt")
    for field in required:
        if field not in value:
            return False, "heartbeat-last-dispatch-invalid"
    for field in ("kind", "engine", "model", "runId"):
        if not isinstance(value[field], str) or not value[field]:
            return False, "heartbeat-last-dispatch-invalid"
    started_at = value["startedAt"]
    if not _is_iso8601_utc(started_at):
        return False, "heartbeat-last-dispatch-invalid"
    return True, None


def _validate_record(record, *, launch_id, now):
    if not isinstance(record, dict):
        return False, "heartbeat-not-an-object"
    if record.get("schema") != SCHEMA:
        return False, "heartbeat-schema-invalid"
    rec_launch_id = record.get("launchId")
    if not _validate_launch_id(rec_launch_id) or rec_launch_id != launch_id:
        return False, "heartbeat-launch-id-invalid"
    issue = record.get("issue")
    if issue is not None and (not isinstance(issue, int) or isinstance(issue, bool)):
        return False, "heartbeat-issue-invalid"
    state = record.get("state")
    if not isinstance(state, str) or state not in STATES:
        return False, "heartbeat-state-invalid"
    phase = record.get("phase")
    if not isinstance(phase, str) or not (_PHASE_MIN_LEN <= len(phase) <= _PHASE_MAX_LEN):
        return False, "heartbeat-phase-invalid"
    ok_ld, reason_ld = _validate_last_dispatch(record.get("lastDispatch"))
    if not ok_ld:
        return False, reason_ld
    ts = record.get("ts")
    if not _is_finite_number(ts):
        return False, "heartbeat-ts-invalid"
    if ts > now:
        return False, "heartbeat-ts-future"
    stale_after = record.get("staleAfterSeconds")
    if not _is_positive_int(stale_after, min_val=_STALE_AFTER_MIN, max_val=_STALE_AFTER_MAX):
        return False, "heartbeat-stale-after-invalid"
    note = record.get("note")
    if note is not None:
        if not isinstance(note, str) or len(note) > _NOTE_MAX_LEN:
            return False, "heartbeat-note-invalid"
    return True, None


def _load_record(path):
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None, "heartbeat-unreadable"
        with os.fdopen(fd, encoding="utf-8") as fh:
            fd = None
            raw = json.load(fh, parse_constant=_reject_constant)
    except OSError:
        return None, "heartbeat-unreadable"
    except (ValueError, json.JSONDecodeError):
        return None, "heartbeat-corrupt"
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
    if not isinstance(raw, dict):
        return None, "heartbeat-not-an-object"
    return raw, None


def _classify_record(record, *, launch_id, now):
    valid, reason = _validate_record(record, launch_id=launch_id, now=now)
    if not valid:
        return {
            "class": "unknown",
            "reason": reason,
            "state": record.get("state") if isinstance(record, dict) else None,
            "phase": record.get("phase") if isinstance(record, dict) else None,
            "lastDispatch": record.get("lastDispatch") if isinstance(record, dict) else None,
            "staleAfterSeconds": record.get("staleAfterSeconds") if isinstance(record, dict) else None,
            "note": record.get("note") if isinstance(record, dict) else None,
            "ageSeconds": None,
        }

    ts = float(record["ts"])
    stale_after = int(record["staleAfterSeconds"])
    age = now - ts
    state = record["state"]
    if state in TERMINAL_STATES:
        sweep_class = "terminal"
    elif age > stale_after:
        sweep_class = "stale"
    else:
        sweep_class = "fresh"

    return {
        "class": sweep_class,
        "reason": None,
        "state": state,
        "phase": record["phase"],
        "lastDispatch": record.get("lastDispatch"),
        "staleAfterSeconds": stale_after,
        "note": record.get("note"),
        "ageSeconds": age,
    }


def _unknown_classification(launch_id, reason):
    return _ok(
        launchId=launch_id,
        class_="unknown",
        state=None,
        phase=None,
        lastDispatch=None,
        ageSeconds=None,
        staleAfterSeconds=None,
        note=None,
        reason=reason,
    )


def _read_file_classification(repo_root, launch_id, *, env=None, now=None):
    if now is None:
        now = time.time()
    if not _validate_launch_id(launch_id):
        return _unknown_classification(launch_id, REASON_LAUNCH_ID_INVALID)
    path_result = heartbeat_path(repo_root, launch_id, env=env)
    if not path_result["ok"]:
        return _unknown_classification(launch_id, path_result["reason"])
    path = path_result["path"]
    if not os.path.isfile(path):
        return _ok(
            launchId=launch_id,
            class_="unknown",
            state=None,
            phase=None,
            lastDispatch=None,
            ageSeconds=None,
            staleAfterSeconds=None,
            note=None,
            reason=REASON_HEARTBEAT_MISSING,
        )
    record, load_reason = _load_record(path)
    if record is None:
        return _ok(
            launchId=launch_id,
            class_="unknown",
            state=None,
            phase=None,
            lastDispatch=None,
            ageSeconds=None,
            staleAfterSeconds=None,
            note=None,
            reason=load_reason,
        )
    classified = _classify_record(record, launch_id=launch_id, now=now)
    out = _ok(
        launchId=launch_id,
        class_=classified["class"],
        state=classified["state"],
        phase=classified["phase"],
        lastDispatch=classified["lastDispatch"],
        ageSeconds=classified["ageSeconds"],
        staleAfterSeconds=classified["staleAfterSeconds"],
        note=classified["note"],
        reason=classified["reason"],
    )
    if classified["class"] == "terminal":
        out["actionable"] = True
        out["pendingAction"] = "record-outcome"
    return out


def read_heartbeat(repo_root, launch_id, *, env=None, now=None):
    """Classify one heartbeat without consulting the ledger. Never raises."""
    result = _read_file_classification(repo_root, launch_id, env=env, now=now)
    if result.get("class_") is not None:
        result["class"] = result.pop("class_")
    return result


def stamp(
    repo_root,
    *,
    state,
    phase,
    launch_id=None,
    issue=None,
    stale_after_seconds=300,
    last_dispatch=None,
    note=None,
    env=None,
    now=None,
):
    """Validate and atomically write a heartbeat record. Never raises."""
    if env is None:
        env = os.environ
    if now is None:
        now = time.time()
    if launch_id is None:
        launch_id = env.get(LAUNCH_ID_ENV)
    if not launch_id:
        return _fail(REASON_LAUNCH_ID_UNAVAILABLE)
    if not _validate_launch_id(launch_id):
        return _fail(REASON_LAUNCH_ID_INVALID)

    record = {
        "schema": SCHEMA,
        "launchId": launch_id,
        "issue": issue,
        "state": state,
        "phase": phase,
        "lastDispatch": last_dispatch,
        "ts": float(now),
        "staleAfterSeconds": int(stale_after_seconds),
        "note": note,
    }
    valid, reason = _validate_record(record, launch_id=launch_id, now=now)
    if not valid:
        return _fail(reason)

    path_result = heartbeat_path(repo_root, launch_id, env=env)
    if not path_result["ok"]:
        return _fail(path_result["reason"])
    path = path_result["path"]

    store_result = _ensure_heartbeat_store(repo_root, env=env)
    if not store_result["ok"]:
        return _fail(store_result["reason"])
    directory = store_result["dir"]
    if not _path_inside(directory, path):
        return _fail(REASON_LAUNCH_ID_INVALID)

    text = json.dumps(record, sort_keys=True) + "\n"
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".heartbeat-", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        return _ok(launchId=launch_id, path=path)
    except OSError:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return _fail(REASON_WRITE_FAILED)


def _ledger_live_launches(repo_root, env=None):
    read_result = ll.read(repo_root, env=env)
    state = read_result["state"]
    if state not in ("ok", "missing"):
        return _fail(REASON_LEDGER_UNREADABLE, live=[])
    if state == "missing":
        return _fail(REASON_LEDGER_UNREADABLE, live=[])
    folded = ll.fold(read_result["records"])
    if not folded["ok"]:
        return _fail(REASON_LEDGER_UNREADABLE, live=[])
    live = ll.live_launches(read_result["records"])
    return _ok(live=live)


def sweep(repo_root, *, env=None, now=None):
    """Sweep all live launches from the ledger. Never raises."""
    if now is None:
        now = time.time()
    ledger = _ledger_live_launches(repo_root, env=env)
    if not ledger["ok"]:
        return _fail(ledger["reason"])

    entries = []
    for launch_id in ledger["live"]:
        classified = _read_file_classification(repo_root, launch_id, env=env, now=now)
        entry_class = classified.get("class_") or classified.get("class")
        if entry_class not in SWEEP_CLASSES:
            entry_class = "unknown"
        entry = {
            "launchId": launch_id,
            "class": entry_class,
            "state": classified.get("state"),
            "phase": classified.get("phase"),
            "lastDispatch": classified.get("lastDispatch"),
            "ageSeconds": classified.get("ageSeconds"),
            "staleAfterSeconds": classified.get("staleAfterSeconds"),
            "note": classified.get("note"),
            "reason": classified.get("reason"),
        }
        if entry["class"] == "terminal":
            entry["actionable"] = True
            entry["pendingAction"] = "record-outcome"
        entries.append(entry)

    return _ok(launches=entries)


def _cli_stamp(args):
    last_dispatch = None
    if args.last_dispatch is not None:
        try:
            last_dispatch = json.loads(args.last_dispatch, parse_constant=_reject_constant)
        except (ValueError, json.JSONDecodeError):
            return _fail("heartbeat-last-dispatch-invalid")
    return stamp(
        args.repo_root,
        state=args.state,
        phase=args.phase,
        launch_id=args.launch_id,
        issue=args.issue,
        stale_after_seconds=args.stale_after,
        last_dispatch=last_dispatch,
        note=args.note,
        env=os.environ,
    )


def _cli_read(args):
    return read_heartbeat(args.repo_root, args.launch_id, env=os.environ)


def _cli_sweep(args):
    return sweep(args.repo_root, env=os.environ)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="heartbeat")
    sub = parser.add_subparsers(dest="command", required=True)

    st = sub.add_parser("stamp")
    st.add_argument("--repo-root", required=True)
    st.add_argument("--state", required=True)
    st.add_argument("--phase", required=True)
    st.add_argument("--issue", type=int, default=None)
    st.add_argument("--stale-after", type=int, default=300, dest="stale_after")
    st.add_argument("--last-dispatch", default=None, dest="last_dispatch")
    st.add_argument("--note", default=None)
    st.add_argument("--launch-id", default=None, dest="launch_id")
    st.set_defaults(func=_cli_stamp)

    rd = sub.add_parser("read")
    rd.add_argument("--repo-root", required=True)
    rd.add_argument("--launch-id", required=True, dest="launch_id")
    rd.set_defaults(func=_cli_read)

    sw = sub.add_parser("sweep")
    sw.add_argument("--repo-root", required=True)
    sw.set_defaults(func=_cli_sweep)

    try:
        args = parser.parse_args(argv)
        result = args.func(args)
    except Exception:
        result = _fail("heartbeat-internal-error")
    if result.get("class_") is not None:
        result["class"] = result.pop("class_")
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
