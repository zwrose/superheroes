import json
import os

import guardian_lens as gl
import guardian_store as gs
import guardian_sweep as gsw
import store_core as sc
from guardian_fixtures import (
    FixtureLens, init_calibrated_repo, write_guardian_layer, write_ledger,
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


def test_collect_skips_verify_when_lens_does_not_require_it(tmp_path):
    repo = init_calibrated_repo(tmp_path, verify_command="false")
    root = _store(tmp_path)
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


def test_not_collected_lens_degrades_preserves_snapshot(tmp_path):
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
    lens = FixtureLens(
        collect_status="not-collected",
        collect_reason="tool missing",
        emit_normal=True,
        diff_new=["fixture:normal"],
    )
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["surfaced"] == []
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["funnel"]["degradedLenses"][0]["reason"] == "tool missing"
    assert "fixture" not in bundle["funnel"]["raised"]
    assert bundle["nextSnapshot"]["lenses"]["fixture"] == prior_entry


def test_partial_lens_degrades_and_processes_candidates(tmp_path):
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
    lens = FixtureLens(
        collect_status="partial",
        collect_reason="half the tree",
        emit_normal=True,
        digest={"v": 2, "merged": True},
        diff_new=["fixture:normal"],
    )
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["funnel"]["degradedLenses"][0]["reason"] == "half the tree"
    assert len(bundle["surfaced"]) == 1
    assert bundle["surfaced"][0]["id"] == "fixture:normal"
    assert bundle["nextSnapshot"]["lenses"]["fixture"]["digest"] == {"v": 2, "merged": True}


def test_prev_digest_reset_on_version_change(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "1", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(collector_version="2")
    gsw.collect(repo, lenses=[lens], root=root)
    assert lens.last_prev_digest is None


def test_prev_digest_carried_on_unchanged_version(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_digest = {"v": 1}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": prior_digest}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens()
    gsw.collect(repo, lenses=[lens], root=root)
    assert lens.last_prev_digest == prior_digest


def test_partial_version_change_withholds_baseline_write(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_entry = {"collectorVersion": "1", "digest": {"v": 1, "prior": True}}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": prior_entry},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(
        collector_version="2",
        collect_status="partial",
        collect_reason="incomplete new baseline",
        emit_red_line=True,
        digest={"v": 2, "partial": True},
    )
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert lens.last_prev_digest is None
    assert len(bundle["surfaced"]) == 1
    assert bundle["surfaced"][0]["id"] == "fixture:red-line"
    assert bundle["funnel"]["raised"]["fixture"] == 1
    assert bundle["nextSnapshot"]["lenses"]["fixture"] == prior_entry


def test_collected_version_change_writes_fresh_baseline(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_entry = {"collectorVersion": "1", "digest": {"v": 1, "prior": True}}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": prior_entry},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    new_digest = {"v": 2, "fresh": True}
    lens = FixtureLens(collector_version="2", digest=new_digest)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    entry = bundle["nextSnapshot"]["lenses"]["fixture"]
    assert entry["collectorVersion"] == "2"
    assert entry["digest"] == new_digest


def test_collect_raises_degrades_without_crashing_siblings(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    bad = FixtureLens(name="bad", collect_raises=RuntimeError("boom"))
    good = FixtureLens(name="good", emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[bad, good], root=root)
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["funnel"]["degradedLenses"][0]["lens"] == "bad"
    assert "collect raised" in bundle["funnel"]["degradedLenses"][0]["reason"]
    assert any(s["id"] == "good:red-line" for s in bundle["surfaced"])
