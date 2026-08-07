#!/usr/bin/env python3
"""Probe whether a project's calibration declares pilot slots. Never raises."""
from __future__ import annotations

import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import pilot_contract  # noqa: E402
import store  # noqa: E402

REASON_DECLARED = "declared"
REASON_NO_CALIBRATION = "no-calibration"
REASON_NO_CONFIG_BLOCK = "no-config-block"
REASON_CONFIG_UNPARSEABLE = "config-unparseable"
REASON_NO_PILOT_BLOCK = "no-pilot-block"
REASON_CREDENTIAL_SET_EMPTY = "credential-set-empty"
REASON_CALIBRATION_UNREADABLE = "calibration-unreadable"


def _unknown_calibration(path, reason):
    return {"declares": False, "unknown": True, "reason": reason, "path": path}


def declares_slots(repo_root):
    """Return whether pilot slots are declared in the project's calibration profile."""
    if not isinstance(repo_root, str) or not repo_root:
        return {"declares": False, "reason": REASON_NO_CALIBRATION, "path": None}
    try:
        info = store.resolve(repo_root, store.store_root())
        path = info.get("profile") if info.get("exists") else None
    except Exception:
        return {"declares": False, "reason": REASON_NO_CALIBRATION, "path": None}
    if path is None:
        return {"declares": False, "reason": REASON_NO_CALIBRATION, "path": None}
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        return _unknown_calibration(path, REASON_CALIBRATION_UNREADABLE)
    except OSError:
        return _unknown_calibration(path, REASON_CALIBRATION_UNREADABLE)
    match = store.CONFIG_BLOCK_RE.search(text)
    if not match:
        return {"declares": False, "reason": REASON_NO_CONFIG_BLOCK, "path": path}
    try:
        cfg = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _unknown_calibration(path, REASON_CONFIG_UNPARSEABLE)
    if not isinstance(cfg, dict):
        return _unknown_calibration(path, REASON_CONFIG_UNPARSEABLE)
    if pilot_contract.PILOT_BLOCK_KEY not in cfg:
        return {"declares": False, "reason": REASON_NO_PILOT_BLOCK, "path": path}
    pilot = cfg[pilot_contract.PILOT_BLOCK_KEY]
    if not isinstance(pilot, dict):
        return _unknown_calibration(path, REASON_NO_PILOT_BLOCK)
    cred = pilot.get("credentialSet")
    if cred is None:
        return {"declares": False, "reason": REASON_CREDENTIAL_SET_EMPTY, "path": path}
    if not isinstance(cred, list):
        return _unknown_calibration(path, REASON_CREDENTIAL_SET_EMPTY)
    if not cred:
        return {"declares": False, "reason": REASON_CREDENTIAL_SET_EMPTY, "path": path}
    return {"declares": True, "reason": REASON_DECLARED, "path": path}
