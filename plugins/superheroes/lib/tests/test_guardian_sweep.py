import json
import os

import guardian_lens as gl
import guardian_store as gs
import guardian_sweep as gsw
import store_core as sc
from guardian_fixtures import (
    FixtureLens, benched_fixture_ledger, funnel_conserved, init_calibrated_repo,
    write_guardian_layer, write_ledger,
)


def _store(tmp_path):
    return str(tmp_path / "store")


def test_first_sweep_red_line_surfaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens])
    ids = [s["id"] for s in bundle["surfaced"]]
    assert "fixture:red-line" in ids
    assert bundle["surfaced"][0]["driftReason"] == "red-line"


def test_first_sweep_normal_candidate_quiet(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    lens = FixtureLens(emit_normal=True)
    bundle = gsw.collect(repo, lenses=[lens])
    assert bundle["surfaced"] == []
    assert len(bundle["funnel"]["killedByDrift"]) == 1


def test_second_sweep_new_candidate_surfaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    lens2 = FixtureLens(emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[lens2], root=root)
    ids = [s["id"] for s in bundle["surfaced"]]
    assert "fixture:normal" in ids
    assert bundle["surfaced"][0]["driftReason"] == "new"


def test_per_lens_baseline_new_lens_quiet_except_red_lines(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    lens_a = FixtureLens(name="lens-a", emit_normal=True, digest={"v": 1},
                         diff_new=["lens-a:normal"])
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"lens-a": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    lens_b = FixtureLens(name="lens-b", emit_normal=True, emit_red_line=True, digest={"v": 1})
    bundle = gsw.collect(repo, lenses=[lens_a, lens_b], root=root)
    surfaced_ids = [s["id"] for s in bundle["surfaced"]]
    assert "lens-a:normal" in surfaced_ids
    assert "lens-b:normal" not in surfaced_ids
    assert "lens-b:red-line" in surfaced_ids


def test_verify_command_failed_degrades_lens(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="false")
    root = _store(tmp_path)

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = ""
        return R()

    lens = FixtureLens(required_facts=("verify-command",))
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    facts = {f["fact"]: f["status"] for f in bundle["factVerdicts"]}
    assert facts["verify-command"] == "failed"
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["funnel"]["degradedLenses"][0]["lens"] == "fixture"


def test_all_four_facts_in_verdicts(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["python"])
    write_guardian_layer(tmp_path, {"coverage": [{"path": "README.md"}]})
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "README.md").write_text("# x\n")
    bundle = gsw.collect(repo, lenses=[])
    facts = {f["fact"] for f in bundle["factVerdicts"]}
    assert facts == set(gl.FACTS)


def test_filed_open_candidate_tracked_in_funnel_conservation(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "filed",
        "issue": "#42",
    }], root=root)

    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    lens = FixtureLens(emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["surfaced"] == []
    assert len(bundle["ledgerStatus"]) == 1
    assert len(bundle["funnel"]["trackedFiled"]) == 1
    assert bundle["funnel"]["trackedFiled"][0]["id"] == "fixture:normal"

    raised = sum(bundle["funnel"]["raised"].values())
    killed_drift = len(bundle["funnel"]["killedByDrift"])
    killed_ledger = len(bundle["funnel"]["killedByLedger"])
    tracked_filed = len(bundle["funnel"]["trackedFiled"])
    malformed = len(bundle["funnel"]["malformed"])
    surfaced = len(bundle["surfaced"])
    assert raised == malformed + killed_drift + killed_ledger + tracked_filed + surfaced
    assert funnel_conserved(bundle)


def test_collect_skips_verify_when_lens_does_not_require_it(tmp_path):
    """With vitals disabled, verify stays not-run when no lens requests it.

    Finding: vitals (default on) is now a legitimate verify-command requester, so
    this pin only holds when vitals collection is off."""
    repo = init_calibrated_repo(tmp_path, verify_command="false")
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class R:
            returncode = 1
            stdout = ""
            stderr = ""
        return R()

    lens = FixtureLens()
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    facts = {f["fact"]: f["status"] for f in bundle["factVerdicts"]}
    assert facts["verify-command"] == "not-run"
    assert calls == []


def test_collect_runs_verify_once_when_lens_and_vitals_both_need_it(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="false")
    root = _store(tmp_path)
    verify_calls = []

    def fake_run(cmd, **kwargs):
        if kwargs.get("shell"):
            verify_calls.append(cmd)
        class R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""
        return R()

    lens = FixtureLens(required_facts=("verify-command",))
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    facts = {f["fact"]: f["status"] for f in bundle["factVerdicts"]}
    assert facts["verify-command"] == "ok"
    assert len(verify_calls) == 1


def test_collect_runs_verify_when_lens_requires_it(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="false")
    root = _store(tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    lens = FixtureLens(required_facts=("verify-command",))
    # Vitals off so only the lens requests verify — preserves the original pin.
    write_guardian_layer(tmp_path, {"vitals": False})
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    facts = {f["fact"]: f["status"] for f in bundle["factVerdicts"]}
    assert facts["verify-command"] == "ok"
    assert len(calls) == 1


def test_ledger_filed_moves_to_status(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "filed",
        "issue": "#42",
    }], root=root)

    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    lens = FixtureLens(emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["surfaced"] == []
    assert len(bundle["ledgerStatus"]) == 1
    assert "#42" in bundle["ledgerStatus"][0]["line"]


def test_malformed_ledger_suppresses_nothing(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    gs.write_snapshot_cas(repo, {
        "schemaVersion": 1, "sweptSha": "a", "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }, None, root=root)
    sc.atomic_write(gs.ledger_path(repo, root), "bad ledger\n")

    lens = FixtureLens(emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "malformed"
    assert len(bundle["surfaced"]) == 1


def test_validate_dispositions_missing_id(tmp_path):
    bundle = {"surfaced": [{"id": "a"}]}
    ok, errors = gsw.validate_dispositions(bundle, [])
    assert ok is False
    assert any("a" in e for e in errors)


def test_validate_dispositions_extra_id(tmp_path):
    bundle = {"surfaced": []}
    ok, errors = gsw.validate_dispositions(
        bundle, [{"id": "extra", "verdict": "rejected"}])
    assert ok is False
    assert any("extra" in e for e in errors)


def test_validate_dispositions_validated_requires_fields(tmp_path):
    bundle = {"surfaced": [{"id": "a"}]}
    ok, errors = gsw.validate_dispositions(
        bundle, [{"id": "a", "verdict": "validated"}])
    assert ok is False
    assert len(errors) >= 4


def test_validate_dispositions_complete_ok(tmp_path):
    bundle = {"surfaced": [{"id": "a"}]}
    disp = [{
        "id": "a",
        "verdict": "validated",
        "consequence": "Fix it.",
        "receipt": "saw it",
        "effort": "small",
        "ledgerJoin": "a",
    }]
    ok, errors = gsw.validate_dispositions(bundle, disp)
    assert ok is True
    assert errors == []


def test_finalize_writes_report_and_snapshot(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "Reduce complexity.",
        "receipt": "complexity=100",
        "effort": "medium",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    assert os.path.isfile(gs.report_path(repo, root=root))
    assert os.path.isfile(gs.snapshot_path(repo, root=root))


def test_finalize_raced_does_not_write_report(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    initial = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "baseline-sha",
        "vitals": {},
        "lenses": {},
    }
    gs.write_snapshot_cas(repo, initial, None, root=root)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    concurrent = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "baseline-sha",
        "vitals": {},
        "lenses": {"tampered": {"collectorVersion": "x", "digest": {"v": 99}}},
    }
    sc.atomic_write(
        gs.snapshot_path(repo, root=root),
        json.dumps(concurrent, indent=2) + "\n")
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is False
    assert result["reason"] == "raced"
    assert not os.path.isfile(gs.report_path(repo, root=root))
    assert gs.read_snapshot(repo, root=root)["lenses"] == concurrent["lenses"]


def test_finalize_invalid_dispositions_writes_nothing(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    result = gsw.finalize(repo, bundle, [], root=root)
    assert result["ok"] is False
    assert not os.path.isfile(gs.report_path(repo, root=root))
    assert not os.path.isfile(gs.snapshot_path(repo, root=root))


def test_accepted_trade_suppressed_when_not_worsened(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "accepted",
        "issue": None,
        "metricAtDisposition": 5,
    }], root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"], metric=3)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["surfaced"] == []
    assert len(bundle["funnel"]["killedByLedger"]) == 1
    assert bundle["funnel"]["killedByLedger"][0]["disposition"] == "accepted"


def test_accepted_trade_resurfaces_when_materially_worsened(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "accepted",
        "issue": None,
        "metricAtDisposition": 5,
    }], root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"], metric=10)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["surfaced"]) == 1
    assert bundle["surfaced"][0]["id"] == "fixture:normal"


def test_recorded_coverage_absent_degrades_lens(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    lens = FixtureLens(required_facts=("recorded-coverage",))
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["funnel"]["degradedLenses"][0]["lens"] == "fixture"


def test_collector_version_change_treats_lens_as_new_baseline(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "1", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(
        collector_version="2", emit_normal=True, digest={"v": 2},
        diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["surfaced"] == []
    assert bundle["nextSnapshot"]["lenses"]["fixture"]["collectorVersion"] == "2"


def test_degraded_lens_preserves_prior_baseline(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_entry = {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": prior_entry},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(required_facts=("recorded-coverage",))
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["nextSnapshot"]["lenses"]["fixture"] == prior_entry


def test_bundle_lens_meta_for_surfaced_lens(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens])
    meta = bundle["lensMeta"]["fixture"]
    assert meta["validationGuidance"] == lens.validation_guidance
    assert meta["consequenceTemplate"] == lens.consequence_template
    assert meta["cost"] == lens.cost


def test_duplicate_candidate_id_lands_in_malformed_and_conserves_funnel(tmp_path):
    repo = init_calibrated_repo(tmp_path)

    class DuplicateIdLens(FixtureLens):
        def collect(self, ctx):
            return {
                "candidates": [
                    {"id": "fixture:dup", "complexity": 5, "metric": 1},
                    {"id": "fixture:dup", "complexity": 5, "metric": 2},
                ],
                "digest": {"v": 1},
            }

    lens = DuplicateIdLens()
    bundle = gsw.collect(repo, lenses=[lens])
    malformed = bundle["funnel"]["malformed"]
    assert len(malformed) == 1
    assert malformed[0]["reason"] == "duplicate-id"
    assert malformed[0]["index"] == 1
    assert bundle["surfaced"] == []
    assert len(bundle["funnel"]["killedByDrift"]) == 1
    assert bundle["funnel"]["killedByDrift"][0]["id"] == "fixture:dup"

    raised = sum(bundle["funnel"]["raised"].values())
    killed_drift = len(bundle["funnel"]["killedByDrift"])
    killed_ledger = len(bundle["funnel"]["killedByLedger"])
    tracked_filed = len(bundle["funnel"]["trackedFiled"])
    malformed_count = len(bundle["funnel"]["malformed"])
    surfaced = len(bundle["surfaced"])
    assert raised == malformed_count + killed_drift + killed_ledger + tracked_filed + surfaced


def test_malformed_candidate_lands_in_funnel_malformed(tmp_path):
    repo = init_calibrated_repo(tmp_path)

    class MalformedLens(FixtureLens):
        def collect(self, ctx):
            out = super().collect(ctx)
            out["candidates"] = out["candidates"] + ["not-a-dict"]
            return out

    lens = MalformedLens(emit_normal=True)
    bundle = gsw.collect(repo, lenses=[lens])
    assert len(bundle["funnel"]["malformed"]) == 1
    raised = sum(bundle["funnel"]["raised"].values())
    killed_drift = len(bundle["funnel"]["killedByDrift"])
    killed_ledger = len(bundle["funnel"]["killedByLedger"])
    tracked_filed = len(bundle["funnel"]["trackedFiled"])
    malformed = len(bundle["funnel"]["malformed"])
    surfaced = len(bundle["surfaced"])
    assert raised == malformed + killed_drift + killed_ledger + tracked_filed + surfaced


def test_finalize_report_written_before_snapshot_failure(tmp_path, monkeypatch):
    import pytest

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    prior_snap = gs.read_snapshot(repo, root=root)
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    snap_path = gs.snapshot_path(repo, root=root)
    real_atomic_write = sc.atomic_write

    def flaky_atomic_write(path, content):
        if path == snap_path:
            raise OSError("simulated snapshot write failure")
        return real_atomic_write(path, content)

    monkeypatch.setattr(sc, "atomic_write", flaky_atomic_write)
    with pytest.raises(OSError, match="simulated snapshot"):
        gsw.finalize(repo, bundle, disp, root=root)
    assert os.path.isfile(gs.report_path(repo, root=root))
    assert gs.read_snapshot(repo, root=root) == prior_snap


def test_benched_lens_still_surfaces_red_line_first_and_later_sweep(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, benched_fixture_ledger(), root=root)
    write_guardian_layer(tmp_path, {"vitals": False})

    lens = FixtureLens(emit_red_line=True, emit_normal=True)
    first = gsw.collect(repo, lenses=[lens], root=root)
    assert first["reportCard"]["fixture"]["benched"] is True
    ids = [s["id"] for s in first["surfaced"]]
    assert "fixture:red-line" in ids
    assert "fixture:normal" not in ids

    gs.write_snapshot_cas(repo, first["nextSnapshot"], first["prevIdentity"], root=root)
    later = FixtureLens(
        emit_red_line=True, emit_normal=True, digest={"v": 2},
        diff_new=["fixture:normal"])
    second = gsw.collect(repo, lenses=[later], root=root)
    ids2 = [s["id"] for s in second["surfaced"]]
    assert "fixture:red-line" in ids2
    assert "fixture:normal" not in ids2
    assert any(k["id"] == "fixture:normal" for k in second["funnel"]["killedByBench"])
    assert funnel_conserved(second)


def test_object_shaped_metric_at_disposition_reraises_on_worsening(tmp_path):
    """Regression: float(dict) on {"cloneLines": 177} used to swallow worsening."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "accepted",
        "issue": None,
        "reason": "tolerated pending shared include",
        "metricAtDisposition": {"cloneLines": 177},
        "reraiseWhen": "cloneLines grows",
    }], root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(
        emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"],
        candidate_fields={"cloneLines": 400})
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["surfaced"]) == 1
    assert bundle["surfaced"][0]["id"] == "fixture:normal"


def test_ambiguous_matcher_collision_surfaces_with_breadcrumb(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, [
        {"id": "fixture:tool:a.py:10", "disposition": "accepted",
         "issue": None, "reason": "a", "metricAtDisposition": 1},
        {"id": "fixture:tool:a.py:20", "disposition": "declined",
         "issue": None, "reason": "b", "metricAtDisposition": 1},
    ], root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    write_guardian_layer(tmp_path, {"vitals": False})

    class CollisionLens(FixtureLens):
        def collect(self, ctx):
            return {
                "candidates": [{"id": "fixture:tool:a.py:15", "complexity": 5, "metric": 1}],
                "digest": {"v": 2},
            }

    lens = CollisionLens(digest={"v": 2}, diff_new=["fixture:tool:a.py:15"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert any(s["id"] == "fixture:tool:a.py:15" for s in bundle["surfaced"])
    notes = bundle["funnel"]["matchNotes"]
    assert notes and "ambiguous" in notes[0]["note"]


def test_finalize_idempotent_vitals_append_on_retry(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    first = gsw.finalize(repo, bundle, disp, root=root)
    assert first["ok"] is True
    # Retried finalize against the same prevIdentity will race — rebuild bundle
    # identity to the just-written snapshot so the retry exercises append idempotency.
    bundle2 = dict(bundle)
    bundle2["prevIdentity"] = gs.snapshot_identity(
        gs.read_snapshot(repo, root=root))
    second = gsw.finalize(repo, bundle2, disp, root=root)
    assert second["ok"] is True
    assert second["vitalsAppend"].get("skipped") == "duplicate-sweepId" \
        or second["vitalsAppend"].get("ok") is True
    trend = __import__("guardian_vitals", fromlist=["read_trend"]).read_trend(
        repo, root=root)
    matching = [r for r in trend["records"] if r.get("sweepId") == bundle["sweepId"]]
    assert len(matching) == 1


def _ledger_sweeps(repo, root=None):
    text = open(gs.ledger_path(repo, root), encoding="utf-8").read()
    fence = gs.LEDGER_FENCE
    block = json.loads(text.split("```json %s\n" % fence)[1].split("\n```")[0])
    return block.get("sweeps") or []


def test_finalize_appends_sweep_roster_across_cycles_and_retries(tmp_path):
    """Seam guard: two real collect→finalize cycles grow the roster; a retry does not.

    Would have caught the original defect where finalize hard-coded sweeps=None and
    write_unlocked treated None as erase."""
    import subprocess

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})

    lens1 = FixtureLens(emit_red_line=True, digest={"v": 1})
    b1 = gsw.collect(repo, lenses=[lens1], root=root)
    disp1 = [{
        "id": b1["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": b1["surfaced"][0]["id"],
    }]
    r1 = gsw.finalize(repo, b1, disp1, root=root)
    assert r1["ok"] is True
    roster1 = _ledger_sweeps(repo, root)
    assert len(roster1) == 1
    assert roster1[0]["sweepId"] == b1["sweepId"]

    # Retried finalize of the same sweepId must leave the roster at one entry.
    b1_retry = dict(b1)
    b1_retry["prevIdentity"] = gs.snapshot_identity(
        gs.read_snapshot(repo, root=root))
    r1_retry = gsw.finalize(repo, b1_retry, disp1, root=root)
    assert r1_retry["ok"] is True
    assert len(_ledger_sweeps(repo, root)) == 1

    # Second cycle needs a distinct sweptSha so sweepId differs.
    subprocess.run(
        ["git", "-C", repo,
         "-c", "user.email=guardian@test.local", "-c", "user.name=guardian-test",
         "commit", "-q", "--allow-empty", "-m", "second-sweep"],
        check=True)
    lens2 = FixtureLens(emit_red_line=True, digest={"v": 2})
    b2 = gsw.collect(repo, lenses=[lens2], root=root)
    assert b2["sweepId"] != b1["sweepId"]
    disp2 = [{
        "id": b2["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": b2["surfaced"][0]["id"],
    }]
    r2 = gsw.finalize(repo, b2, disp2, root=root)
    assert r2["ok"] is True
    roster2 = _ledger_sweeps(repo, root)
    assert [s["sweepId"] for s in roster2] == [b1["sweepId"], b2["sweepId"]]


def test_finalize_ledger_write_failure_leaves_report_snapshot_and_reports(tmp_path, monkeypatch):
    import guardian_ledger as gled

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]

    def boom(*args, **kwargs):
        raise OSError("simulated ledger write failure")

    monkeypatch.setattr(gled, "write_unlocked", boom)
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    assert os.path.isfile(gs.report_path(repo, root=root))
    assert os.path.isfile(gs.snapshot_path(repo, root=root))
    assert result["ledgerWrite"]["ok"] is False
    assert "simulated ledger write failure" in result["ledgerWrite"]["reason"]


def test_finalize_vitals_append_failure_leaves_report_snapshot_and_reports(tmp_path, monkeypatch):
    import guardian_vitals as gv

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]

    def boom(*args, **kwargs):
        raise OSError("simulated vitals append failure")

    monkeypatch.setattr(gv, "append_unlocked", boom)
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    assert os.path.isfile(gs.report_path(repo, root=root))
    assert os.path.isfile(gs.snapshot_path(repo, root=root))
    assert result["vitalsAppend"]["ok"] is False
    assert "simulated vitals append failure" in result["vitalsAppend"]["reason"]


def test_bundle_carries_storage_mode_and_committed(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    bundle = gsw.collect(repo, lenses=[], root=_store(tmp_path))
    assert bundle["storageMode"] in ("in-repo", "global")
    assert bundle["committed"] in ("committed", "uncommitted", "machine-local", "unknown")
    assert bundle["sweepId"]
    assert "vitals" in bundle["nextSnapshot"]


def test_finalize_leaves_newer_ledger_bytes_untouched(tmp_path):
    """CRITICAL: records=[] from a newer-schema read is opaque, not empty — do not rewrite."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    owner_text = (
        "# Owner ledger prose — must survive\n\n"
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({
            "schemaVersion": 99,
            "records": [{
                "id": "fixture:trade",
                "disposition": "accepted",
                "date": "2026-07-01",
                "issue": None,
                "metricAtDisposition": {"metric": 5},
                "reason": "owner accepted this trade",
                "reraiseWhen": None,
            }],
            "sweeps": [{"sweepId": "owner-s0", "sweptSha": "abc", "date": "2026-07-01"}],
        }, indent=2))
    )
    path = gs.ledger_path(repo, root)
    sc.atomic_write(path, owner_text)
    before = open(path, "rb").read()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "newer"
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    assert result["ledgerWrite"]["ok"] is False
    assert "newer" in (result["ledgerWrite"].get("skipped")
                       or result["ledgerWrite"].get("reason") or "")
    after = open(path, "rb").read()
    assert after == before, "newer-schema ledger bytes must be left untouched"
    assert b"owner accepted this trade" in after
    assert b"Owner ledger prose" in after


def test_finalize_leaves_malformed_ledger_bytes_untouched(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    path = gs.ledger_path(repo, root)
    owner_text = "# hand-damaged\n\n```json guardian-ledger\n{not json\n```\n"
    sc.atomic_write(path, owner_text)
    before = open(path, "rb").read()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "malformed"
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    assert result["ledgerWrite"]["ok"] is False
    assert open(path, "rb").read() == before


def test_filed_open_issue_stays_filed_after_sweep(tmp_path, monkeypatch):
    """A still-open filed issue must not flip to reopened on the next sweep."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "filed",
        "date": "2026-07-01",
        "issue": "#123",
        "metricAtDisposition": {"metric": 5},
        "reason": None,
        "reraiseWhen": None,
        "adjudicatedIn": "s0",
    }], root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    monkeypatch.setattr(gsw, "_resolve_issue_state", lambda *a, **k: "open")

    lens = FixtureLens(
        emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"], metric=5)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    obs = bundle["filedObservations"]["fixture:normal"]
    assert obs["present"] is True
    assert obs["issueState"] == "open"
    result = gsw.finalize(repo, bundle, [], root=root)
    assert result["ok"] is True
    advances = result["ledgerWrite"].get("advances") or []
    assert advances == []
    read = gs.read_ledger(repo, root=root)
    assert read["byId"]["fixture:normal"]["disposition"] == "filed"


def test_filed_closed_issue_unmoved_metric_reopens(tmp_path, monkeypatch):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "filed",
        "date": "2026-07-01",
        "issue": "#123",
        "metricAtDisposition": {"metric": 5},
        "reason": None,
        "reraiseWhen": None,
        "adjudicatedIn": "s0",
    }], root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    monkeypatch.setattr(gsw, "_resolve_issue_state", lambda *a, **k: "closed")

    lens = FixtureLens(
        emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"], metric=5)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    result = gsw.finalize(repo, bundle, [], root=root)
    assert result["ok"] is True
    advances = result["ledgerWrite"].get("advances") or []
    assert any(a.get("to") == "reopened" for a in advances)
    read = gs.read_ledger(repo, root=root)
    assert read["byId"]["fixture:normal"]["disposition"] == "reopened"


def test_malformed_report_card_overrides_do_not_abort_collect(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {
        "vitals": False,
        "reportCard": {
            "minAdjudicated": "ten",
            "minSweeps": False,
            "actionabilityBar": "high",
        },
    })
    write_ledger(tmp_path, benched_fixture_ledger(), root=root)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["reportCard"]["fixture"]["benched"] is True
    assert bundle["reportCardNotes"]
    assert any("minAdjudicated" in n for n in bundle["reportCardNotes"])
