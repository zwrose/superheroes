"""Durable per-run dispatch overrides + the frozen preflight-readout snapshot (spec FR-13/FR-14).
Persists to the control-plane run record (the substrate the run's journal/checkpoint/resume use),
so an override outlives one launch and is reapplied on relaunch. Fail-OPEN on an unreadable/older
record -> {overrides:{}, frozenSnapshot:None}: a lost/garbled override is a cost concern, never a
correctness one (the run still resolves each phase through the live resolvers). stdlib only."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane

SCHEMA_VERSION = 1
_FILENAME = "run-overrides.json"


def _record_path(work_item, root, cwd=None):
    cwd = cwd if cwd is not None else os.getcwd()
    return os.path.join(control_plane.issue_dir(cwd, work_item, root), _FILENAME)


def write(work_item, root, overrides, frozen_snapshot, cwd=None):
    """Persist the accepted overrides + the frozen snapshot atomically. Returns True on success."""
    cwd = cwd if cwd is not None else os.getcwd()
    control_plane.ensure_store(cwd, root)
    path = _record_path(work_item, root, cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"schemaVersion": SCHEMA_VERSION,
           "overrides": overrides if isinstance(overrides, dict) else {},
           "frozenSnapshot": frozen_snapshot}
    try:
        control_plane.atomic_write(path, json.dumps(rec, indent=2))
        return True
    except OSError:
        return False


def read(work_item, root, cwd=None):
    """Return {overrides, frozenSnapshot}. Fail-open to {overrides:{}, frozenSnapshot:None} on an
    absent, unreadable, corrupt, or newer-schema record (never raises)."""
    empty = {"overrides": {}, "frozenSnapshot": None}
    try:
        path = _record_path(work_item, root, cwd)
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return empty
    if not isinstance(rec, dict):
        return empty
    if rec.get("schemaVersion", SCHEMA_VERSION) != SCHEMA_VERSION:
        return empty  # older/newer shape -> fail open (FR-14 re-validation still surfaces stale-but-readable)
    ov = rec.get("overrides")
    return {"overrides": ov if isinstance(ov, dict) else {},
            "frozenSnapshot": rec.get("frozenSnapshot")}
