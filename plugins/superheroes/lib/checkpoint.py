# plugins/superheroes/lib/checkpoint.py
"""checkpoint.json — the §4.3 LOCKED resume cursor. This slice implements the
writer/reader for the schema CONVENTIONS §4.3 already locked; it does NOT redefine
it. Unknown/newer durable shapes fail closed with an incompatibility marker so the
caller parks instead of re-deriving from reality.

Schema versions: v2 is current — its `lastGoodStep` indexes CURRENT_PHASES (the
test-pilot-aware phase list). v1 is the pre-test-pilot legacy shape whose
`lastGoodStep` indexes LEGACY_PHASES_PRE_TEST_PILOT; the reader still ACCEPTS v1 and
migrates it forward so this (newer) code resumes an in-flight v1 run. Bumping
SCHEMA_VERSION to 2 is the rollback fence: code that predates the test-pilot insert
only accepts schemaVersion==1, so it fail-closes (parks) on a v2 checkpoint rather
than resuming at a phase index the test-pilot insert silently shifted out from under it.
"""
import json
import os
import time

import control_plane

SCHEMA_VERSION = 2
_SUPPORTED_READ_VERSIONS = (1, 2)
CURRENT_PHASES = ["plan", "review-plan", "tasks", "review-tasks", "workhorse",
                  "review-code", "draft-PR", "test-pilot", "mark-ready", "ship"]
LEGACY_PHASES_PRE_TEST_PILOT = ["plan", "review-plan", "tasks", "review-tasks",
                                "workhorse", "review-code", "draft-PR",
                                "mark-ready", "ship"]

# #450 terminal marker for the `phase` field: a run that was PARKED and then finished BY HAND
# (native gate, PR, review, ready-flip) outside the spine. It is deliberately NOT one of
# CURRENT_PHASES — a resume must never try to re-enter a hand-shipped run — and the manual-
# completion receipt (manual_completion.py) is its only writer. Record-readers treat a
# TERMINAL_PHASES `phase` as authoritative over the (truthfully frozen) lastGoodPhase resume
# cursor so the record reads "shipped" instead of the stale parked phase (epic #327).
SHIPPED_MANUAL = "shipped-manual"
TERMINAL_PHASES = frozenset({SHIPPED_MANUAL})


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


def _infer_legacy_phase(data, step):
    if step < 0 or step >= len(LEGACY_PHASES_PRE_TEST_PILOT):
        return _incompatible("checkpoint lastGoodStep is outside the legacy phase list")
    phase = LEGACY_PHASES_PRE_TEST_PILOT[step]
    data["lastGoodPhase"] = phase
    if phase in CURRENT_PHASES:
        data["lastGoodStep"] = CURRENT_PHASES.index(phase)
    return None


def _validate_shape(data):
    if not isinstance(data, dict):
        return _incompatible("checkpoint is not an object")
    version = data.get("schemaVersion")
    if version not in _SUPPORTED_READ_VERSIONS:
        return _incompatible("unsupported checkpoint schemaVersion")
    step = data.get("lastGoodStep")
    if step is not None and not _is_numeric_step(step):
        return _incompatible("checkpoint lastGoodStep must be numeric or null")
    if version == 1:
        return _migrate_legacy(data, step)
    return _validate_current(data, step)


def _migrate_legacy(data, step):
    # Pre-test-pilot (v1) checkpoint: lastGoodStep indexes the 9-phase legacy list and
    # there is no lastGoodPhase. Map it onto CURRENT_PHASES so this (newer) code resumes
    # the in-flight run at the right phase, then normalize to the current shape in memory.
    if step is None:
        data["lastGoodPhase"] = None
    else:
        incompatible = _infer_legacy_phase(data, step)
        if incompatible:
            return incompatible
    data["schemaVersion"] = SCHEMA_VERSION
    return None


def _validate_current(data, step):
    # Current (v2) checkpoint: lastGoodStep indexes CURRENT_PHASES and lastGoodPhase is
    # authoritative. The writer always stamps lastGoodPhase, so a present step with a
    # missing/non-string phase is a corrupt durable shape -> fail closed (never re-infer).
    phase = data.get("lastGoodPhase")
    if step is None:
        if phase is not None:
            return _incompatible("checkpoint lastGoodPhase is set but lastGoodStep is null")
        data["lastGoodPhase"] = None
        return None
    if not isinstance(phase, str):
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
