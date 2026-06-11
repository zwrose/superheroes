#!/usr/bin/env python3
"""test-pilot engine: manifest/plan-record validation, protected-target gate,
and apply/clean/status/unlock orchestration. CLI contract is JSON (--json).

Run as a script from this directory; sibling modules (store, state, lock,
blocks) import directly because the script dir is on sys.path.
"""
import fnmatch
import hashlib
import json
import os
import sys
import time

import blocks
import lock
import state
import store

MANIFEST_SCHEMA_VERSION = 1
PLAN_RECORD_SCHEMA_VERSION = 1


class EngineError(Exception):
    """Structured engine failure; payload feeds the --json error contract."""

    def __init__(self, message, **payload):
        self.payload = {"error": message, **payload}
        super().__init__(message)


def _load_json(path, what):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise EngineError(f"unreadable {what} {path}: {exc}") from exc


def load_manifest(path):
    m = _load_json(path, "manifest")
    v = m.get("schemaVersion")
    if v != MANIFEST_SCHEMA_VERSION:
        raise EngineError(
            f"manifest {path} has schemaVersion {v!r}; this engine supports "
            f"{MANIFEST_SCHEMA_VERSION}. Update the test-pilot plugin or "
            f"regenerate the manifest.")
    if not isinstance(m.get("branch"), str) or not m["branch"].strip():
        raise EngineError(f"manifest {path} is missing the `branch` field "
                          f"(identity lives in the JSON, not the filename)")
    if m.get("slot") is not None and not store.SLOT_RE.match(m["slot"]):
        raise EngineError(f"manifest {path} has an invalid slot {m['slot']!r}")
    scenarios = m.get("scenarios")
    if not isinstance(scenarios, list):
        raise EngineError(f"manifest {path}: `scenarios` must be a list")
    ids = [sc.get("id") for sc in scenarios]
    if any(not isinstance(i, str) or not i for i in ids):
        raise EngineError(f"manifest {path}: every scenario needs a string id")
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise EngineError(f"manifest {path}: duplicate scenario ids {sorted(dupes)}")
    id_set = set(ids)
    for sc in scenarios:
        if not isinstance(sc.get("block"), str) or not sc["block"]:
            raise EngineError(
                f"scenario {sc['id']!r} needs a `block`", scenarioId=sc["id"])
        if not isinstance(sc.get("config"), dict):
            raise EngineError(
                f"scenario {sc['id']!r} needs a `config` object",
                scenarioId=sc["id"])
        for dep in sc.get("dependsOn", []):
            if dep not in id_set:
                raise EngineError(
                    f"scenario {sc['id']!r} dependsOn unknown scenario "
                    f"{dep!r}", scenarioId=sc["id"])
    topo_order(scenarios)  # raises on cycles
    return m


def topo_order(scenarios):
    """Kahn's algorithm. Returns ids in dependency order; cycle -> EngineError."""
    deps = {sc["id"]: set(sc.get("dependsOn", [])) for sc in scenarios}
    order = []
    ready = sorted(i for i, d in deps.items() if not d)
    while ready:
        n = ready.pop(0)
        order.append(n)
        for i in sorted(deps):
            if n in deps[i]:
                deps[i].discard(n)
                if not deps[i] and i not in order and i not in ready:
                    ready.append(i)
    if len(order) != len(deps):
        stuck = sorted(set(deps) - set(order))
        raise EngineError(f"dependsOn cycle involving scenarios {stuck}")
    return order


def load_plan_record(path, manifest):
    rec = _load_json(path, "plan record")
    v = rec.get("schemaVersion")
    if v != PLAN_RECORD_SCHEMA_VERSION:
        raise EngineError(
            f"plan record {path} has schemaVersion {v!r}; this engine "
            f"supports {PLAN_RECORD_SCHEMA_VERSION}.")
    ids = {sc["id"] for sc in manifest["scenarios"]}
    for step in rec.get("steps", []):
        for f in ("id", "instruction", "expected"):
            if not isinstance(step.get(f), str) or not step[f]:
                raise EngineError(
                    f"plan record {path}: step missing `{f}`",
                    step=step.get("id"))
        missing = [s for s in step.get("scenarioIds", []) if s not in ids]
        if missing:
            raise EngineError(
                f"plan record {path}: step {step['id']!r} references missing "
                f"scenario id(s) {missing} — regenerate the plan, do not "
                f"treat this as an app bug", step=step["id"])
    return rec
