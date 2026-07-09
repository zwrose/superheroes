# plugins/superheroes/lib/minor_rollup.py
"""Carry-forward Minor-findings roll-up (FR-7 -> FR-8): append per-task Minor findings to a
roll-up file and read them back for the whole-branch final review. Idempotent append (deduped by
finding identity); fail-closed read (missing/garbled -> [])."""
import json
import os

import circuit_breaker
import control_plane


def read(path):
    findings, _corrupt = read_status(path)
    return findings


def read_status(path):
    """(findings, corrupt): findings is the fail-closed [] on any unreadable/garbled file (unchanged
    behavior). corrupt is True ONLY when the file EXISTS but could not be parsed into a list — a
    silent loss of carried-forward Minor findings the owner must be told about (B4, #315). A missing
    file (nothing was ever rolled up) is NOT corruption; corrupt stays False."""
    if not os.path.isfile(path):
        return [], False
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError):
        return [], True
    if not isinstance(obj, list):
        return [], True
    return obj, False


def append(path, findings):
    existing = read(path)
    seen = {circuit_breaker.finding_identity(f) for f in existing}
    merged = list(existing)
    for f in findings or []:
        ident = circuit_breaker.finding_identity(f)
        if ident not in seen:
            seen.add(ident)
            merged.append(f)
    control_plane.atomic_write(path, json.dumps(merged))
    return merged
