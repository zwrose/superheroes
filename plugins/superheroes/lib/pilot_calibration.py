#!/usr/bin/env python3
"""Probe whether a project's calibration declares pilot slots. Never raises."""
from __future__ import annotations

import json
import os
import stat
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import pilot_contract  # noqa: E402
import store  # noqa: E402

STATE_DECLARED = "declared"
STATE_ABSENT = "absent"
STATE_CANNOT_TELL = "cannot-tell"

CAUSE_DECLARED = "declared"
CAUSE_NO_CALIBRATION = "no-calibration"
CAUSE_NO_PILOT_BLOCK = "no-pilot-block"
CAUSE_CREDENTIAL_SET_EMPTY = "credential-set-empty"
CAUSE_REPO_ROOT_INVALID = "repo-root-invalid"
CAUSE_RESOLVER_FAILED = "resolver-failed"
CAUSE_CALIBRATION_UNRESOLVED = "calibration-unresolved"
CAUSE_CALIBRATION_UNREADABLE = "calibration-unreadable"
CAUSE_NO_CONFIG_BLOCK = "no-config-block"
CAUSE_CONFIG_UNPARSEABLE = "config-unparseable"
CAUSE_PILOT_BLOCK_MALFORMED = "pilot-block-malformed"
CAUSE_CREDENTIAL_SET_MALFORMED = "credential-set-malformed"

CAUSE_STATE_MAP = {
    CAUSE_DECLARED: STATE_DECLARED,
    CAUSE_NO_CALIBRATION: STATE_ABSENT,
    CAUSE_NO_PILOT_BLOCK: STATE_ABSENT,
    CAUSE_CREDENTIAL_SET_EMPTY: STATE_ABSENT,
    CAUSE_REPO_ROOT_INVALID: STATE_CANNOT_TELL,
    CAUSE_RESOLVER_FAILED: STATE_CANNOT_TELL,
    CAUSE_CALIBRATION_UNRESOLVED: STATE_CANNOT_TELL,
    CAUSE_CALIBRATION_UNREADABLE: STATE_CANNOT_TELL,
    CAUSE_NO_CONFIG_BLOCK: STATE_CANNOT_TELL,
    CAUSE_CONFIG_UNPARSEABLE: STATE_CANNOT_TELL,
    CAUSE_PILOT_BLOCK_MALFORMED: STATE_CANNOT_TELL,
    CAUSE_CREDENTIAL_SET_MALFORMED: STATE_CANNOT_TELL,
}


def _answer(state, cause, path):
    return {"state": state, "cause": cause, "path": path}


_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


def _read_calibration_text(path):
    """Read a calibration file safely. Returns (text, cause) — exactly one is None."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None, "not-found"
    except OSError:
        return None, "cannot-tell"
    mode = st.st_mode
    if stat.S_ISLNK(mode):
        try:
            st = os.stat(path)
            mode = st.st_mode
        except FileNotFoundError:
            return None, "cannot-tell"
        except OSError:
            return None, "cannot-tell"
    if not stat.S_ISREG(mode):
        return None, "cannot-tell"
    fd = None
    try:
        try:
            fd = os.open(path, os.O_RDONLY | _O_NONBLOCK)
        except FileNotFoundError:
            return None, "cannot-tell"
        except OSError:
            return None, "cannot-tell"
        try:
            fst = os.fstat(fd)
        except OSError:
            return None, "cannot-tell"
        if not stat.S_ISREG(fst.st_mode):
            return None, "cannot-tell"
        try:
            with os.fdopen(fd, encoding="utf-8") as fh:
                fd = None
                try:
                    text = fh.read()
                except (OSError, UnicodeDecodeError):
                    return None, "cannot-tell"
        except OSError:
            return None, "cannot-tell"
    finally:
        if fd is not None:
            os.close(fd)
    return text, None


def _path_from_layer_refusal_detail(detail):
    """Extract the layer path embedded in a store layer-unreadable refusal detail."""
    if " at " not in detail:
        return None
    suffix = detail.rsplit(" at ", 1)[1]
    if suffix.startswith("/"):
        return suffix.split(": ", 1)[0]
    return suffix


def _legacy_profile_selected(path):
    """True when ``path`` is a legacy profile.md the store resolver would select."""
    return path is not None and (
        path.endswith(os.path.join("test-pilot", "profile.md"))
        or path.endswith("/profile.md")
    )


def declares_slots(repo_root):
    """Return whether pilot slots are declared in the project's calibration profile."""
    if not isinstance(repo_root, str) or not repo_root:
        return _answer(STATE_CANNOT_TELL, CAUSE_REPO_ROOT_INVALID, None)
    try:
        # Store-level refusal is not short-circuited here — this module performs its
        # own, more specific candidate classification in the walk below (#913).
        info = store.resolve(repo_root, store.store_root())
        refusal = info.get("refusal")
        if refusal is not None and not info.get("exists"):
            reason = refusal.get("reason")
            detail = refusal.get("detail") or ""
            if reason == store.STORE_REASON_POINTER_UNREADABLE:
                return _answer(STATE_CANNOT_TELL, CAUSE_RESOLVER_FAILED, None)
            if reason == store.STORE_REASON_LAYER_UNREADABLE:
                refused_path = _path_from_layer_refusal_detail(detail)
                if _legacy_profile_selected(refused_path):
                    return _answer(
                        STATE_CANNOT_TELL, CAUSE_CALIBRATION_UNREADABLE,
                        refused_path)
        path = info.get("profile") if info.get("exists") else None
    except Exception:
        return _answer(STATE_CANNOT_TELL, CAUSE_RESOLVER_FAILED, None)
    if path is None:
        try:
            candidates = store.candidate_profile_paths(
                repo_root, store.store_root())
        except Exception:
            return _answer(STATE_CANNOT_TELL, CAUSE_RESOLVER_FAILED, None)
        for candidate in candidates:
            try:
                _, read_cause = _read_calibration_text(candidate)
                if read_cause == "not-found":
                    continue
                if read_cause is not None:
                    return _answer(
                        STATE_CANNOT_TELL, CAUSE_CALIBRATION_UNRESOLVED,
                        candidate)
            except Exception:
                return _answer(
                    STATE_CANNOT_TELL, CAUSE_CALIBRATION_UNRESOLVED,
                    candidate)
        return _answer(STATE_ABSENT, CAUSE_NO_CALIBRATION, None)
    text, read_cause = _read_calibration_text(path)
    if read_cause is not None:
        return _answer(STATE_CANNOT_TELL, CAUSE_CALIBRATION_UNREADABLE, path)
    match = store.CONFIG_BLOCK_RE.search(text)
    if not match:
        return _answer(STATE_CANNOT_TELL, CAUSE_NO_CONFIG_BLOCK, path)
    try:
        cfg = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _answer(STATE_CANNOT_TELL, CAUSE_CONFIG_UNPARSEABLE, path)
    if not isinstance(cfg, dict):
        return _answer(STATE_CANNOT_TELL, CAUSE_CONFIG_UNPARSEABLE, path)
    if pilot_contract.PILOT_BLOCK_KEY not in cfg:
        return _answer(STATE_ABSENT, CAUSE_NO_PILOT_BLOCK, path)
    pilot = cfg[pilot_contract.PILOT_BLOCK_KEY]
    if not isinstance(pilot, dict):
        return _answer(STATE_CANNOT_TELL, CAUSE_PILOT_BLOCK_MALFORMED, path)
    cred = pilot.get("credentialSet")
    if cred is None:
        return _answer(STATE_ABSENT, CAUSE_CREDENTIAL_SET_EMPTY, path)
    if not isinstance(cred, list):
        return _answer(STATE_CANNOT_TELL, CAUSE_CREDENTIAL_SET_MALFORMED, path)
    if not cred:
        return _answer(STATE_ABSENT, CAUSE_CREDENTIAL_SET_EMPTY, path)
    return _answer(STATE_DECLARED, CAUSE_DECLARED, path)
