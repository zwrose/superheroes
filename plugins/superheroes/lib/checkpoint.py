# plugins/superheroes/lib/checkpoint.py
"""checkpoint.json — the §4.3 LOCKED resume cursor. This slice implements the
writer/reader for the schema CONVENTIONS §4.3 already locked; it does NOT redefine
it. Unknown/newer durable shapes fail closed with an incompatibility marker so the
caller parks instead of re-deriving from reality.
"""
import json
import os
import time

import control_plane

SCHEMA_VERSION = 1


def new(work_item, branch, issue=None, size=None, phase="build",
        gates=None, patterns_pin=None, pr=None, last_good_step=None,
        lock_generation=None, last_good_phase=None):
    return {
        "schemaVersion": SCHEMA_VERSION,
        "workItem": work_item,
        "issue": issue,
        "size": size,
        "phase": phase,                       # §4.3 enum; producer writes build/verify/ship
        "gates": gates or {},
        "patternsPin": patterns_pin,
        "branch": branch,                     # §6.3 content-addressed anchor
        "lockGeneration": lock_generation,    # §4.4 fence
        "pr": pr,
        "lastGoodStep": last_good_step,
        "lastGoodPhase": last_good_phase,
        "updatedAt": None,
    }


def _incompatible(reason):
    return {"_incompatible": True, "reason": reason}


def _is_numeric_step(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_shape(data):
    if not isinstance(data, dict):
        return _incompatible("checkpoint is not an object")
    if data.get("schemaVersion") != SCHEMA_VERSION:
        return _incompatible("unsupported checkpoint schemaVersion")
    step = data.get("lastGoodStep")
    if step is not None and not _is_numeric_step(step):
        return _incompatible("checkpoint lastGoodStep must be numeric or null")
    if "lastGoodPhase" not in data:
        if step is None:
            data["lastGoodPhase"] = None
        else:
            return _incompatible("checkpoint lastGoodStep is set but lastGoodPhase is missing")
    if step is None and data.get("lastGoodPhase") is not None:
        return _incompatible("checkpoint lastGoodPhase is set but lastGoodStep is null")
    if step is not None and not isinstance(data.get("lastGoodPhase"), str):
        return _incompatible("checkpoint lastGoodPhase must be present when lastGoodStep is set")
    return None


def write(path, ckpt):
    ckpt = dict(ckpt)
    ckpt["schemaVersion"] = SCHEMA_VERSION
    ckpt.setdefault("lastGoodPhase", None)
    ckpt["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    control_plane.atomic_write(path, json.dumps(ckpt, indent=2))


def read(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    incompatible = _validate_shape(data)
    if incompatible:
        return incompatible
    return data
