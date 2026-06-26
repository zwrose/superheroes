import pytest

import test_pilot_seed as seed


class FakeEngine:
    def __init__(self, *, status=None, fail=None, preserve_status_after_apply=False):
        self.calls = []
        self.status_payload = status or {
            "ok": True,
            "entries": [{"key": "feat%2Fx", "applied": 1, "drift": [],
                         "manifestError": None, "orphan": False}],
            "lock": None,
            "lockStale": False,
        }
        self.fail = fail or {}
        self.preserve_status_after_apply = preserve_status_after_apply

    def validate_plan(self, record):
        self.calls.append(("validate_plan", record["branch"]))
        if self.fail.get("validate_plan"):
            raise ValueError(self.fail["validate_plan"])
        return {"ok": True, "key": "feat%2Fx"}

    def apply(self, record, *, dry_run=False, allow_protected=False):
        assert allow_protected is False
        self.calls.append(("apply", record["branch"], dry_run, allow_protected))
        key = "apply_dry_run" if dry_run else "apply"
        if self.fail.get("%s_branch" % key) == record["branch"]:
            raise ValueError("%s failed for %s" % (key, record["branch"]))
        if self.fail.get(key):
            raise ValueError(self.fail[key])
        if not dry_run and not self.preserve_status_after_apply:
            self.status_payload = {
                "ok": True,
                "entries": [{"key": "feat%2Fx", "applied": 1, "drift": [],
                             "manifestError": None, "orphan": False}],
                "lock": None,
                "lockStale": False,
            }
        return {"ok": True, "key": "feat%2Fx",
                "wouldApply": ["scenario-a"] if dry_run else None,
                "applied": ["scenario-a"] if not dry_run else None}

    def clean(self, record, *, allow_protected=False):
        assert allow_protected is False
        self.calls.append(("clean", record["branch"], allow_protected))
        if self.fail.get("clean_branch") == record["branch"]:
            raise ValueError("clean failed for %s" % record["branch"])
        if self.fail.get("clean"):
            raise ValueError(self.fail["clean"])
        return {"ok": True, "key": "feat%2Fx", "cleaned": ["scenario-a"]}

    def status(self):
        self.calls.append(("status",))
        if self.fail.get("status"):
            raise ValueError(self.fail["status"])
        return self.status_payload

    def unlock(self):
        self.calls.append(("unlock",))
        if self.fail.get("unlock"):
            raise ValueError(self.fail["unlock"])
        self.status_payload = dict(self.status_payload, lock=None, lockStale=False)
        return {"ok": True, "released": True}


def _record():
    return {
        "branch": "feat/x",
        "slot": None,
        "steps": [{"id": "step-1", "instruction": "Open page",
                   "expected": "Dashboard loads", "scenarioIds": ["scenario-a"]}],
    }


def _record_for(branch):
    record = _record()
    record["branch"] = branch
    return record


def test_prepare_validates_and_dry_runs_before_apply_and_browser():
    engine = FakeEngine()
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "ready_for_browser"
    assert engine.calls[:4] == [
        ("validate_plan", "feat/x"),
        ("status",),
        ("apply", "feat/x", True, False),
        ("apply", "feat/x", False, False),
    ]
    assert engine.calls[-1] == ("status",)


def test_prepare_parks_on_malformed_plan_details_before_apply():
    engine = FakeEngine()
    bad = dict(_record(), steps=[{"id": "step-1"}])
    result = seed.prepare_records([bad], engine)
    assert result["action"] == "park"
    assert "malformed plan details" in result["reason"]
    assert engine.calls == []


def test_prepare_parks_on_protected_target_refusal():
    engine = FakeEngine(fail={"apply_dry_run": "protected-target refusal: main"})
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "park"
    assert "protected target refusal" in result["reason"]
    assert ("apply", "feat/x", False, False) not in engine.calls


def test_prepare_parks_on_partial_apply_failure():
    engine = FakeEngine(fail={"apply": "block apply failed for scenario-b"})
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "park"
    assert "apply failed" in result["reason"]
    assert engine.calls[:4] == [
        ("validate_plan", "feat/x"),
        ("status",),
        ("apply", "feat/x", True, False),
        ("apply", "feat/x", False, False),
    ]


def test_prepare_cleans_successfully_applied_records_when_later_apply_fails():
    engine = FakeEngine(fail={"apply_branch": "feat/y"})
    result = seed.prepare_records([_record_for("feat/x"), _record_for("feat/y")], engine)

    assert result["action"] == "park"
    assert "apply failed" in result["reason"]
    assert ("clean", "feat/x", False) in engine.calls


def test_prepare_parks_on_live_lock():
    engine = FakeEngine(status={"ok": True, "entries": [],
                                "lock": {"pid": 123}, "lockStale": False})
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "park"
    assert "engine lock is held" in result["reason"]
    assert engine.calls == [("validate_plan", "feat/x"), ("status",)]


def test_prepare_unlocks_stale_lock_then_applies():
    engine = FakeEngine(status={"ok": True, "entries": [],
                                "lock": {"pid": 999999}, "lockStale": True})
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "ready_for_browser"
    assert engine.calls[:4] == [
        ("validate_plan", "feat/x"),
        ("status",),
        ("unlock",),
        ("apply", "feat/x", True, False),
    ]


def test_prepare_parks_when_seeded_state_is_unverified():
    engine = FakeEngine(status={"ok": True, "entries": [
        {"key": "feat%2Fx", "applied": 1, "drift": ["scenario-a"],
         "manifestError": None, "orphan": False}],
        "lock": None, "lockStale": False}, preserve_status_after_apply=True)
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "park"
    assert "drift" in result["reason"]


def test_prepare_parks_when_status_is_unreadable():
    engine = FakeEngine(fail={"status": "cannot read state"})
    result = seed.prepare_records([_record()], engine)
    assert result["action"] == "park"
    assert "unreadable engine status" in result["reason"]


def test_restore_baseline_dry_runs_cleans_reapplies_and_verifies():
    engine = FakeEngine()
    result = seed.restore_baseline([_record()], engine)
    assert result["action"] == "baseline_restored"
    assert engine.calls[:4] == [
        ("validate_plan", "feat/x"),
        ("status",),
        ("apply", "feat/x", True, False),
        ("clean", "feat/x", False),
    ]
    assert ("apply", "feat/x", False, False) in engine.calls


def test_restore_baseline_parks_on_clean_failure():
    engine = FakeEngine(fail={"clean": "protected-target refusal: main"})
    result = seed.restore_baseline([_record()], engine)
    assert result["action"] == "park"
    assert "clean failed" in result["reason"]


def test_restore_baseline_reapplies_successfully_cleaned_records_when_later_clean_fails():
    engine = FakeEngine(fail={"clean_branch": "feat/y"})
    result = seed.restore_baseline([_record_for("feat/x"), _record_for("feat/y")], engine)

    assert result["action"] == "park"
    assert "clean failed" in result["reason"]
    assert engine.calls[-1] == ("apply", "feat/x", False, False)


def test_restore_baseline_recleans_successfully_applied_records_when_reapply_fails():
    engine = FakeEngine(fail={"apply_branch": "feat/y"})
    result = seed.restore_baseline([_record_for("feat/x"), _record_for("feat/y")], engine)

    assert result["action"] == "park"
    assert "apply failed" in result["reason"]
    assert engine.calls.count(("clean", "feat/x", False)) == 2
