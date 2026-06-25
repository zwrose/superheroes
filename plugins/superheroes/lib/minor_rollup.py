# plugins/superheroes/lib/minor_rollup.py
"""Carry-forward Minor-findings roll-up (FR-7 -> FR-8): append per-task Minor findings to a
roll-up file and read them back for the whole-branch final review. Idempotent append (deduped by
finding identity); fail-closed read (missing/garbled -> [])."""
import json
import os

import circuit_breaker
import control_plane


def read(path):
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError):
        return []
    return obj if isinstance(obj, list) else []


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
