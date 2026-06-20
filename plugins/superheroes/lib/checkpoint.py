# plugins/workhorse/lib/checkpoint.py
"""checkpoint.json — the §4.3 LOCKED resume cursor. This slice implements the
writer/reader for the schema CONVENTIONS §4.3 already locked; it does NOT redefine
it. An unknown (newer) schemaVersion fails closed (read -> None) so the caller
re-derives from reality (design §2, §6.4).
"""
import json
import os
import time

import control_plane

SCHEMA_VERSION = 1


def new(work_item, branch, issue=None, size=None, phase="build",
        gates=None, patterns_pin=None, pr=None, last_good_step=None,
        lock_generation=None):
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
        "updatedAt": None,
    }


def write(path, ckpt):
    ckpt = dict(ckpt)
    ckpt["schemaVersion"] = SCHEMA_VERSION
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
    if not isinstance(data, dict) or data.get("schemaVersion") != SCHEMA_VERSION:
        return None   # unknown/missing schema -> fail closed (world-derive)
    return data
