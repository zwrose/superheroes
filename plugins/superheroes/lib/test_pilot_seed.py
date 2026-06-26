"""Workflow helpers for preparing and restoring test-pilot seed data."""

import os

import engine as engine_mod
import store
import test_pilot_budget


def _park(reason, **extra):
    return {"action": "park", "reason": reason, **extra}


def _ready(action, records, status):
    return {"action": action, "records": records, "status": status}


def _record_key(record):
    key = record.get("key")
    if isinstance(key, str) and key:
        return key
    return store.artifact_key(record.get("branch"), record.get("slot"))


def _validate_record_shape(record):
    if not isinstance(record, dict):
        return "malformed plan details: record must be a JSON object"
    if not isinstance(record.get("branch"), str) or not record["branch"].strip():
        return "malformed plan details: record branch is required"
    steps = record.get("steps")
    if not isinstance(steps, list) or not steps:
        return "malformed plan details: steps must be a non-empty list"
    for step in steps:
        if not isinstance(step, dict):
            return "malformed plan details: every step must be an object"
        for field in ("id", "instruction", "expected"):
            if not isinstance(step.get(field), str) or not step[field].strip():
                return "malformed plan details: step missing %s" % field
        scenario_ids = step.get("scenarioIds", [])
        if not isinstance(scenario_ids, list) or not all(
                isinstance(sid, str) and sid for sid in scenario_ids):
            return "malformed plan details: step scenarioIds must be strings"
    return None


class EngineAdapter:
    """Adapt the engine module's manifest functions to the workflow interface."""

    def __init__(self, module=engine_mod):
        self.module = module
        self._resolved = None

    def _paths_and_profile(self, record=None):
        record = record or {}
        paths = record.get("paths")
        profile_cfg = record.get("profileCfg") or record.get("profile_cfg")
        if paths:
            return paths, profile_cfg or {}
        if self._resolved is None:
            paths, resolved = self.module._resolve_paths()
            self._resolved = (paths, resolved)
        paths, resolved = self._resolved
        if profile_cfg is None:
            profile_cfg = self.module.load_profile_config(resolved["profile"])
        return paths, profile_cfg

    def validate_plan(self, record):
        paths, _profile_cfg = self._paths_and_profile(record)
        branch = record["branch"]
        slot = record.get("slot")
        key = store.artifact_key(branch, slot)
        manifest_path = os.path.join(paths["manifests_dir"], "%s.json" % key)
        manifest = self.module.load_manifest(manifest_path)
        self.module._check_manifest_identity(manifest, manifest_path, branch, slot)
        plan_path = record.get("planPath") or os.path.join(
            paths["manifests_dir"], "%s.plan.json" % key)
        plan = self.module.load_plan_record(
            plan_path, manifest, branch=branch, slot=slot)
        return {"ok": True, "key": key, "steps": len(plan["steps"])}

    def apply(self, record, *, dry_run=False, allow_protected=False):
        paths, profile_cfg = self._paths_and_profile(record)
        return self.module.apply_manifest(
            paths, record["branch"], record.get("slot"), profile_cfg,
            allow_protected=allow_protected, dry_run=dry_run)

    def clean(self, record, *, allow_protected=False):
        paths, profile_cfg = self._paths_and_profile(record)
        return self.module.clean_manifest(
            paths, record["branch"], record.get("slot"), profile_cfg,
            allow_protected=allow_protected)

    def status(self):
        paths, _profile_cfg = self._paths_and_profile({})
        return self.module.status(paths)

    def unlock(self):
        paths, _profile_cfg = self._paths_and_profile({})
        return self.module.unlock(paths)


def _budget_ok(records, budget):
    budget = budget or test_pilot_budget
    counts = {
        "planRecords": len(records),
        "browserSteps": sum(len(record.get("steps", [])) for record in records
                            if isinstance(record, dict)),
        "uniqueScenarios": len({
            sid
            for record in records if isinstance(record, dict)
            for step in record.get("steps", []) if isinstance(step, dict)
            for sid in step.get("scenarioIds", [])
            if isinstance(sid, str)
        }),
        "seedOperations": len(records) * 3,
    }
    decide = getattr(budget, "decide", budget)
    result = decide(counts)
    if isinstance(result, dict) and result.get("action") != "within_budget":
        return _park(result.get("reason", "seed workflow exceeded budget"))
    return None


def _ensure_lock_clear(engine):
    try:
        status = engine.status()
    except Exception as exc:
        return _park("unreadable engine status: %s" % exc)
    if not isinstance(status, dict) or status.get("ok") is False:
        return _park("unreadable engine status")
    if status.get("lock"):
        if status.get("lockStale") is True:
            try:
                engine.unlock()
            except Exception as exc:
                return _park("failed to unlock stale engine lock: %s" % exc)
            return None
        return _park("engine lock is held; park until the active seed operation exits")
    return None


def _verify_seeded(records, engine):
    try:
        status = engine.status()
    except Exception as exc:
        return _park("unreadable engine status: %s" % exc)
    if not isinstance(status, dict) or status.get("ok") is False:
        return _park("unreadable engine status")
    entries = {entry.get("key"): entry for entry in status.get("entries", [])
               if isinstance(entry, dict)}
    for record in records:
        key = _record_key(record)
        entry = entries.get(key)
        if not entry:
            return _park("seeded state is unverified: %s missing from engine status" % key,
                         status=status)
        if entry.get("orphan"):
            return _park("seeded state is unverified: %s is orphaned" % key,
                         status=status)
        if entry.get("manifestError"):
            return _park("seeded state is unverified: %s manifest error: %s" %
                         (key, entry.get("manifestError")), status=status)
        if entry.get("drift"):
            return _park("seeded state is unverified: %s drift %s" %
                         (key, entry.get("drift")), status=status)
    return _ready("verified", records, status)


def _validate_shapes(records):
    for record in records:
        problem = _validate_record_shape(record)
        if problem:
            return _park(problem)
    return None


def _validate_plans(records, engine):
    for record in records:
        try:
            engine.validate_plan(record)
        except Exception as exc:
            return _park("plan validation failed: %s" % exc)
    return None


def _dry_run(records, engine):
    for record in records:
        try:
            engine.apply(record, dry_run=True, allow_protected=False)
        except Exception as exc:
            msg = str(exc).replace("-", " ")
            if "protected target refusal" in msg.lower():
                return _park("protected target refusal: %s" % exc)
            return _park("dry-run apply failed: %s" % exc)
    return None


def prepare_records(records, engine=None, budget=None):
    """Validate, dry-run, apply, and verify seed data before browser execution."""
    engine = engine or EngineAdapter()
    if not hasattr(engine, "validate_plan") and hasattr(engine, "apply_manifest"):
        engine = EngineAdapter(engine)
    records = records if isinstance(records, list) else []
    budget_problem = _budget_ok(records, budget)
    if budget_problem:
        return budget_problem
    problem = _validate_shapes(records)
    if problem:
        return problem
    problem = _validate_plans(records, engine)
    if problem:
        return problem
    lock_problem = _ensure_lock_clear(engine)
    if lock_problem:
        return lock_problem
    problem = _dry_run(records, engine)
    if problem:
        return problem
    for record in records:
        try:
            engine.apply(record, dry_run=False, allow_protected=False)
        except Exception as exc:
            msg = str(exc).replace("-", " ")
            if "protected target refusal" in msg.lower():
                return _park("protected target refusal: %s" % exc)
            return _park("apply failed: %s" % exc)
    verified = _verify_seeded(records, engine)
    if verified.get("action") == "verified":
        return _ready("ready_for_browser", records, verified["status"])
    return verified


def restore_baseline(records, engine=None, budget=None):
    """Clean and re-apply planned seed slots, then verify that no drift remains."""
    engine = engine or EngineAdapter()
    if not hasattr(engine, "validate_plan") and hasattr(engine, "apply_manifest"):
        engine = EngineAdapter(engine)
    records = records if isinstance(records, list) else []
    budget_problem = _budget_ok(records, budget)
    if budget_problem:
        return budget_problem
    problem = _validate_shapes(records)
    if problem:
        return problem
    problem = _validate_plans(records, engine)
    if problem:
        return problem
    lock_problem = _ensure_lock_clear(engine)
    if lock_problem:
        return lock_problem
    problem = _dry_run(records, engine)
    if problem:
        return problem
    for record in records:
        try:
            engine.clean(record, allow_protected=False)
        except Exception as exc:
            msg = str(exc).replace("-", " ")
            if "protected target refusal" in msg.lower():
                return _park("clean failed: protected target refusal: %s" % exc)
            return _park("clean failed: %s" % exc)
    for record in records:
        try:
            engine.apply(record, dry_run=False, allow_protected=False)
        except Exception as exc:
            return _park("apply failed: %s" % exc)
    verified = _verify_seeded(records, engine)
    if verified.get("action") == "verified":
        return _ready("baseline_restored", records, verified["status"])
    return verified
