import json
import os

import guardian_lens as gl
import guardian_report as gr
import guardian_store as gs
import guardian_sweep as gsw
import store_core as sc
from guardian_fixtures import (
    FixtureLens, benched_fixture_ledger, funnel_conserved, init_calibrated_repo,
    write_guardian_layer, write_ledger,
)


def _store(tmp_path):
    return str(tmp_path / "store")


def test_read_config_cadence_defaults_when_absent(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["cadence"] == dict(gsw.CADENCE_DEFAULTS)
    assert cfg["cadenceTuned"] == {}


def test_read_config_cadence_tuned_from_guardian_layer(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"cadence": {"minMerges": 12, "minDays": 7}})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["cadence"] == {"minMerges": 12, "minDays": 7}
    assert cfg["cadenceTuned"] == {"minMerges": True, "minDays": True}


def test_read_config_cadence_malformed_falls_back_to_defaults(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"cadence": {"minMerges": "ten", "minDays": -1}})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["cadence"] == dict(gsw.CADENCE_DEFAULTS)
    assert cfg["cadenceTuned"] == {}


def test_first_sweep_red_line_surfaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens])
    ids = [s["id"] for s in bundle["surfaced"]]
    assert "fixture:red-line" in ids
    assert bundle["surfaced"][0]["driftReason"] == "red-line"


def test_first_seed_high_precision_surfaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    lens = FixtureLens(emit_normal=True)
    bundle = gsw.collect(repo, lenses=[lens])
    ids = [s["id"] for s in bundle["surfaced"]]
    assert "fixture:normal" in ids
    by_id = {s["id"]: s for s in bundle["surfaced"]}
    assert by_id["fixture:normal"]["driftReason"] == "first-baseline"
    assert funnel_conserved(bundle)


def test_late_seeding_new_lens_validated_existing_untouched(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    lens_a = FixtureLens(
        name="lens-a", emit_normal=True, digest={"v": 1}, diff_new=[])
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"lens-a": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    lens_b = FixtureLens(
        name="lens-b", emit_normal=True, emit_red_line=True, digest={"v": 1})
    bundle = gsw.collect(repo, lenses=[lens_a, lens_b], root=root)
    surfaced = {s["id"]: s for s in bundle["surfaced"]}
    assert "lens-b:normal" in surfaced
    assert surfaced["lens-b:normal"]["driftReason"] == "first-baseline"
    assert "lens-b:red-line" in surfaced
    assert surfaced["lens-b:red-line"]["driftReason"] == "red-line"
    assert "lens-a:normal" not in surfaced
    killed = {k["id"]: k for k in bundle["funnel"]["killedByDrift"]}
    assert killed["lens-a:normal"]["reason"] == "no-drift"
    assert funnel_conserved(bundle)


class _MultiCandidateLens(FixtureLens):
    """Emits N distinct normal candidates for first-baseline bound tests."""

    def __init__(self, n, *, emit_red_line=False, **kwargs):
        super().__init__(**kwargs)
        self._n = n
        self._emit_red_line = emit_red_line

    def collect(self, ctx):
        candidates = []
        for i in range(self._n):
            candidates.append({
                "id": "%s:normal-%d" % (self.name, i),
                "complexity": 5,
                "metric": self._metric,
            })
        if self._emit_red_line:
            candidates.append({
                "id": "%s:red-line" % self.name,
                "complexity": gl.RED_LINE_THRESHOLDS["complexity"],
                "metric": self._metric,
            })
        return {"candidates": candidates, "digest": self._digest}


def test_first_seed_volume_above_bound_quiet_and_disclosed(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": 2})
    lens = _MultiCandidateLens(
        3, name="volume-lens", first_baseline_precision="volume")
    bundle = gsw.collect(repo, lenses=[lens])
    assert bundle["surfaced"] == []
    killed = bundle["funnel"]["killedByDrift"]
    assert len(killed) == 3
    assert all(
        k["reason"] == gr.FIRST_BASELINE_UNVALIDATED_REASON for k in killed)
    assert funnel_conserved(bundle)
    md = gr.render(bundle, [], {"byId": {}})
    assert gr.FUNNEL_FIRST_BASELINE_UNVALIDATED in md
    assert "volume-lens: 3 candidate(s) baselined unreviewed (first baseline)" in md


def test_first_seed_volume_below_bound_surfaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": 2})
    lens = _MultiCandidateLens(
        2, name="volume-lens", first_baseline_precision="volume")
    bundle = gsw.collect(repo, lenses=[lens])
    assert len(bundle["surfaced"]) == 2
    assert all(s["driftReason"] == "first-baseline" for s in bundle["surfaced"])
    assert funnel_conserved(bundle)


def test_first_seed_volume_above_bound_red_line_still_surfaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": 2})
    lens = _MultiCandidateLens(
        3, name="volume-lens", first_baseline_precision="volume", emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens])
    surfaced = {s["id"]: s for s in bundle["surfaced"]}
    assert "volume-lens:red-line" in surfaced
    assert surfaced["volume-lens:red-line"]["driftReason"] == "red-line"
    normal_ids = ["volume-lens:normal-%d" % i for i in range(3)]
    assert not any(nid in surfaced for nid in normal_ids)
    killed = {k["id"]: k for k in bundle["funnel"]["killedByDrift"]}
    for nid in normal_ids:
        assert killed[nid]["reason"] == gr.FIRST_BASELINE_UNVALIDATED_REASON
    assert funnel_conserved(bundle)


def test_first_seed_high_precision_above_bound_validates_prefix_and_discloses(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    max_n = 2
    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": max_n})
    lens = _MultiCandidateLens(4, name="high-lens", first_baseline_precision="high")
    all_ids = ["high-lens:normal-%d" % i for i in range(4)]
    bundle = gsw.collect(repo, lenses=[lens])
    surfaced_ids = [s["id"] for s in bundle["surfaced"]]
    assert surfaced_ids == all_ids[:max_n]
    assert all(s["driftReason"] == "first-baseline" for s in bundle["surfaced"])
    killed = [k for k in bundle["funnel"]["killedByDrift"]
              if k["reason"] == gr.FIRST_BASELINE_UNVALIDATED_REASON]
    assert {k["id"] for k in killed} == set(all_ids[max_n:])
    assert funnel_conserved(bundle)
    md = gr.render(bundle, [], {"byId": {}})
    assert "high-lens: 2 candidate(s) baselined unreviewed (first baseline)" in md


def test_first_seed_permanent_partial_composes(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"other-lens": {"collectorVersion": "1", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    class _FirstSeedBoundaryLens(FixtureLens):
        def collect(self, ctx):
            out = super().collect(ctx)
            out["status"] = "partial"
            out["reason"] = "structural capability limit"
            out["permanentBoundary"] = True
            return out

    new_digest = {"v": 1, "boundary": True}
    lens = _FirstSeedBoundaryLens(
        name="new-boundary",
        emit_normal=True,
        digest=new_digest,
    )
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["surfaced"]) == 1
    assert bundle["surfaced"][0]["driftReason"] == "first-baseline"
    entry = bundle["nextSnapshot"]["lenses"]["new-boundary"]
    assert entry["collectorVersion"] == "0.0.0-test"
    assert entry["digest"] == new_digest


def test_first_baseline_validation_end_to_end(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(emit_normal=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["surfaced"]) == 1
    cid = bundle["surfaced"][0]["id"]
    disp = [{
        "id": cid,
        "verdict": "validated",
        "consequence": "Refactor the fixture module.",
        "receipt": "complexity=5",
        "effort": "small",
        "ledgerJoin": cid,
    }]
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    with open(gs.report_path(repo, root=root), encoding="utf-8") as fh:
        md = fh.read()
    assert gr.HEADER_VALIDATED in md
    assert "Refactor the fixture module." in md


def test_first_baseline_config_default_and_override(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["firstBaselineValidateMax"] == 10

    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": 5})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["firstBaselineValidateMax"] == 5

    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": -1})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["firstBaselineValidateMax"] == 10

    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": True})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["firstBaselineValidateMax"] == 10

    write_guardian_layer(tmp_path, {"firstBaselineValidateMax": "ten"})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["firstBaselineValidateMax"] == 10


def test_version_rebaseline_stays_quiet(tmp_path):
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
    assert len(bundle["funnel"]["killedByDrift"]) == 1
    assert bundle["funnel"]["killedByDrift"][0]["reason"] == "quiet-baseline"
    assert bundle["funnel"]["killedByDrift"][0]["reason"] != (
        gr.FIRST_BASELINE_UNVALIDATED_REASON)
    assert bundle["nextSnapshot"]["lenses"]["fixture"]["collectorVersion"] == "2"


def test_later_sweep_no_drift_stays_quiet(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(emit_normal=True, digest={"v": 1}, diff_new=[])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["surfaced"] == []
    assert len(bundle["funnel"]["killedByDrift"]) == 1
    assert bundle["funnel"]["killedByDrift"][0]["reason"] == "no-drift"


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


class _CtxCaptureLens(FixtureLens):
    """Records the ctx it was handed so a test can assert what the sweep threaded in."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen_ctx = None

    def collect(self, ctx):
        self.seen_ctx = dict(ctx)
        return super().collect(ctx)


def test_collect_threads_calibrated_verify_command_onto_ctx(tmp_path):
    """The sweep resolves the calibrated verifyCommand once and hands it to every lens on
    ctx['verifyCommand'] — the tool-free docs lens reads it instead of re-reading core.md.
    A lens that declares NO verify-command fact still receives it (docs does not gate on
    the fact, which would run the command)."""
    repo = init_calibrated_repo(tmp_path, verify_command="python3 scripts/check.py")
    lens = _CtxCaptureLens()
    gsw.collect(repo, lenses=[lens])
    assert lens.seen_ctx is not None
    assert lens.seen_ctx["verifyCommand"] == "python3 scripts/check.py"


def test_collect_threads_none_verify_command_when_calibration_absent(tmp_path):
    """No calibrated verifyCommand → ctx['verifyCommand'] is None (never a false command),
    which a tool-free lens treats as 'no calibration'."""
    repo = init_calibrated_repo(tmp_path, verify_command="")
    os.remove(os.path.join(repo, ".claude", "superheroes", "core.md"))
    lens = _CtxCaptureLens()
    gsw.collect(repo, lenses=[lens])
    assert lens.seen_ctx is not None
    assert lens.seen_ctx["verifyCommand"] is None


def test_verify_config_returns_calibrated_verify_command(tmp_path):
    """verify_config exposes the verifyCommand it read (reused, not a second core.md read)."""
    repo = init_calibrated_repo(tmp_path, verify_command="make test")
    out = gsw.verify_config(repo, root=_store(tmp_path), needed_facts=set())
    assert out["verifyCommand"] == "make test"


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
        "reason": "tolerated for now",
        "metricAtDisposition": {"metric": 5},
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
        "reason": "tolerated for now",
        "metricAtDisposition": {"metric": 5},
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
    assert len(bundle["surfaced"]) == 1
    assert bundle["surfaced"][0]["id"] == "fixture:dup"
    assert bundle["surfaced"][0]["driftReason"] == "first-baseline"
    assert bundle["funnel"]["killedByDrift"] == []

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
         "issue": None, "reason": "a", "metricAtDisposition": {"metric": 1}},
        {"id": "fixture:tool:a.py:20", "disposition": "declined",
         "issue": None, "reason": "b", "metricAtDisposition": {"metric": 1}},
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
    write_guardian_layer(tmp_path, {"vitals": True})

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""
        return R()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    assert bundle["vitalsCollected"] is True
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


def test_finalize_does_not_write_ledger(tmp_path):
    """finalize is read-only on ledger.md; snapshot still commits when vitals succeed."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:keep",
        "disposition": "accepted",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": {"metric": 5},
        "reason": "kept",
        "reraiseWhen": None,
    }], root=root)
    path = gs.ledger_path(repo, root)
    before = open(path, "rb").read()
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
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True
    assert "ledgerWrite" not in result
    assert open(path, "rb").read() == before
    assert os.path.isfile(gs.snapshot_path(repo, root=root))


def test_commit_ledger_appends_sweep_roster_across_cycles_and_retries(tmp_path):
    """Seam guard: two real collect→finalize→commit_ledger cycles grow the roster;
    a retry does not.

    Would have caught the original defect where finalize hard-coded sweeps=None and
    treated None as erase."""
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
    c1 = gsw.commit_ledger(repo, b1, disp1, root=root)
    assert c1["ok"] is True, c1
    roster1 = _ledger_sweeps(repo, root)
    assert len(roster1) == 1
    assert roster1[0]["sweepId"] == b1["sweepId"]

    # Retried commit of the same sweepId must leave the roster at one entry.
    c1_retry = gsw.commit_ledger(repo, b1, disp1, root=root)
    assert c1_retry["ok"] is True, c1_retry
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
    c2 = gsw.commit_ledger(repo, b2, disp2, root=root)
    assert c2["ok"] is True, c2
    roster2 = _ledger_sweeps(repo, root)
    assert [s["sweepId"] for s in roster2] == [b1["sweepId"], b2["sweepId"]]


def test_commit_ledger_write_failure_does_not_mutate_opaque_path(tmp_path, monkeypatch):
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
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True
    path = gs.ledger_path(repo, root)
    # Ensure a ledger exists so write() takes the splice path.
    if not os.path.isfile(path):
        write_ledger(tmp_path, [], root=root)
    before = open(path, "rb").read() if os.path.isfile(path) else None

    def boom(*args, **kwargs):
        return {"ok": False, "reason": "simulated ledger write failure", "path": path}

    monkeypatch.setattr(gled, "_write_locked", boom)
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is False
    assert "simulated ledger write failure" in (result.get("reason") or "")
    if before is not None:
        assert open(path, "rb").read() == before


def test_finalize_vitals_append_failure_does_not_advance_baseline(tmp_path, monkeypatch):
    import guardian_vitals as gv

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": True})

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""
        return R()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    prev_identity = bundle["prevIdentity"]
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
    assert result["ok"] is False
    assert result["reason"] == "durable-write-failed"
    assert os.path.isfile(gs.report_path(repo, root=root))
    assert not os.path.isfile(gs.snapshot_path(repo, root=root))
    assert result["vitalsAppend"]["ok"] is False
    assert "simulated vitals append failure" in result["vitalsAppend"]["reason"]
    assert gs.snapshot_identity(gs.read_snapshot(repo, root=root)) == prev_identity


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
    assert "ledgerWrite" not in result
    assert result.get("closuresUnavailable") and "newer" in result["closuresUnavailable"]
    after = open(path, "rb").read()
    assert after == before, "newer-schema ledger bytes must be left untouched"
    assert b"owner accepted this trade" in after
    assert b"Owner ledger prose" in after
    # Advisor commit also fails closed — never rewrites opaque content.
    commit = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert commit["ok"] is False
    assert "newer" in (commit.get("skipped") or commit.get("reason") or "")
    assert open(path, "rb").read() == before


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
    assert "ledgerWrite" not in result
    assert result.get("closuresUnavailable")
    assert open(path, "rb").read() == before
    commit = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert commit["ok"] is False
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
    assert "ledgerWrite" not in result
    assert (result.get("closureAdvances") or []) == []
    # finalize does not persist — ledger stays filed until commit_ledger
    read = gs.read_ledger(repo, root=root)
    assert read["byId"]["fixture:normal"]["disposition"] == "filed"
    commit = gsw.commit_ledger(repo, bundle, [], root=root)
    assert commit["ok"] is True, commit
    assert (commit.get("advances") or []) == []
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
    assert "ledgerWrite" not in result
    advances = result.get("closureAdvances") or []
    assert any(a.get("to") == "reopened" for a in advances)
    # Proposed only — on-disk still filed until commit_ledger
    assert gs.read_ledger(repo, root=root)["byId"]["fixture:normal"]["disposition"] == "filed"
    report = open(gs.report_path(repo, root), encoding="utf-8").read()
    assert "reopened" in report
    commit = gsw.commit_ledger(repo, bundle, [], root=root)
    assert commit["ok"] is True, commit
    assert any(a.get("to") == "reopened" for a in (commit.get("advances") or []))
    read = gs.read_ledger(repo, root=root)
    assert read["byId"]["fixture:normal"]["disposition"] == "reopened"


def test_malformed_report_card_overrides_do_not_bench(tmp_path):
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
    lens = FixtureLens(emit_red_line=True, emit_normal=True)
    # Seed a quiet baseline so the later sweep can show ordinary drift.
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    later = FixtureLens(
        emit_red_line=True, emit_normal=True, digest={"v": 2},
        diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[later], root=root)
    assert bundle["reportCard"]["fixture"]["benched"] is False
    assert bundle["reportCardNotes"]
    assert any("benching disabled" in n or "minAdjudicated" in n
               for n in bundle["reportCardNotes"])
    assert any(s["id"] == "fixture:normal" for s in bundle["surfaced"])
    assert not any(k["id"] == "fixture:normal" for k in bundle["funnel"]["killedByBench"])


def test_finalize_leaves_unreadable_ledger_bytes_untouched(tmp_path):
    """CRITICAL: existing-but-unreadable ledger must not be rewritten as empty."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    owner_text = (
        "# Owner ledger prose — must survive\n\n"
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({
            "schemaVersion": 1,
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
    os.chmod(path, 0)
    try:
        probe = gs.read_ledger(repo, root=root)
        if probe["status"] != "unreadable":
            import pytest
            pytest.skip("cannot make the ledger unreadable in this environment")
        lens = FixtureLens(emit_red_line=True)
        bundle = gsw.collect(repo, lenses=[lens], root=root)
        assert bundle["ledgerState"] == "unreadable"
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
        assert "ledgerWrite" not in result
        assert result.get("closuresUnavailable")
        skipped = result["closuresUnavailable"]
        assert "unreadable" in skipped
    finally:
        os.chmod(path, 0o644)
    after = open(path, "rb").read()
    assert after == before, "unreadable ledger bytes must be left untouched"
    assert b"owner accepted this trade" in after
    assert b"Owner ledger prose" in after


def test_finalize_leaves_partial_ledger_bytes_untouched(tmp_path):
    """Schema-v1 with one valid + one skipped record must not be rewritten."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    owner_text = (
        "# Owner history — must survive\n\n"
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({
            "schemaVersion": 1,
            "records": [
                {
                    "id": "fixture:valid",
                    "disposition": "filed",
                    "date": "2026-07-01",
                    "issue": "#1",
                    "metricAtDisposition": {"metric": 5},
                    "reason": None,
                    "reraiseWhen": None,
                },
                {
                    "id": "fixture:invalid-trade",
                    "disposition": "accepted",
                    "date": "2026-07-01",
                    "issue": None,
                    "metricAtDisposition": {"metric": 5},
                    # missing required reason — reader skips, status partial
                },
            ],
            "sweeps": [],
        }, indent=2))
    )
    path = gs.ledger_path(repo, root)
    sc.atomic_write(path, owner_text)
    before = open(path, "rb").read()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "partial"
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
    assert "ledgerWrite" not in result
    skipped = result.get("closuresUnavailable") or ""
    assert "partial" in skipped or "partial-skip" in skipped
    after = open(path, "rb").read()
    assert after == before
    assert b"fixture:invalid-trade" in after
    assert b"Owner history" in after
    commit = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert commit["ok"] is False
    assert open(path, "rb").read() == before


def test_benching_does_not_defeat_ambiguous_identity_fail_open(tmp_path):
    """Collect-level: ≥10 colliding records across 3 sweeps must not killByBench."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    records = []
    for i in range(10):
        records.append({
            "id": "fixture:tool:a.py:%d" % (i + 1),
            "disposition": "triaged-out",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": None,
            "reason": None,
            "reraiseWhen": None,
            "adjudicatedIn": "s%d" % (i % 3),
        })
    write_ledger(tmp_path, records, root=root)
    write_guardian_layer(tmp_path, {"vitals": False})
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    class CollisionLens(FixtureLens):
        def collect(self, ctx):
            return {
                "candidates": [{"id": "fixture:tool:a.py:99", "complexity": 5, "metric": 1}],
                "digest": {"v": 2},
            }

    lens = CollisionLens(digest={"v": 2}, diff_new=["fixture:tool:a.py:99"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert any(s["id"] == "fixture:tool:a.py:99" for s in bundle["surfaced"]), bundle
    assert not any(k["id"] == "fixture:tool:a.py:99"
                   for k in bundle["funnel"]["killedByBench"])
    notes = bundle["funnel"]["matchNotes"]
    assert notes and "ambiguous" in notes[0]["note"]
    assert bundle["reportCard"].get("fixture", {}).get("benched") is not True


def test_vitals_carried_forward_digest_not_published_as_fresh(tmp_path):
    """§4 stale-digest bug: a lens that did not run must not publish last sweep's vitals."""
    import guardian_lens_duplication as gld_mod

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": True})
    prior_digest = {
        "duplicationPercent": 42.0,
        "pairs": {},
        "surfaceIds": [],
    }
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {"duplicationPercent": 42.0},
        "lenses": {
            "duplication": {
                "collectorVersion": gld_mod.LENS.collector_version,
                "digest": prior_digest,
            },
        },
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    class SkipLens(FixtureLens):
        name = "duplication"
        collector_version = gld_mod.LENS.collector_version

        def collect(self, ctx):
            raise AssertionError("duplication lens must not run this sweep")

    bundle = gsw.collect(repo, lenses=[SkipLens()], root=root)
    assert bundle["nextSnapshot"]["vitals"].get("duplicationPercent") is None
    assert "duplicationPercent" in bundle["vitalsDelta"]["notCollected"]


def test_verify_stdout_sentinel_absent_from_collect_bundle(tmp_path):
    """Trust boundary: raw verify stdout must not enter the model-facing bundle."""
    repo = init_calibrated_repo(tmp_path, verify_command="true")
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": True})
    sentinel = "SUPERHEROES_VERIFY_SECRET_SENTINEL_9f3a"

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "1 passed in 0.01s\n%s\n" % sentinel
            stderr = ""
        return R()

    lens = FixtureLens(required_facts=("verify-command",), emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    serialized = json.dumps(bundle)
    assert sentinel not in serialized
    for fact in bundle["factVerdicts"]:
        assert "stdout" not in fact


def test_vitals_disabled_finalize_does_not_append_stale_measurements(tmp_path):
    import guardian_vitals as gv

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    prior_vitals = {"locTotal": 100, "fileCount": 10}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": prior_vitals,
        "lenses": {},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    # Seed an existing trend so append would be meaningful if wrongly called.
    gv.append(repo, prior_vitals, sweep_id="prior-s0", swept_sha="abc", root=root)

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["vitalsCollected"] is False
    before = open(gs.vitals_path(repo, root), "rb").read()
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
    assert result["vitalsAppend"].get("skipped") == "vitals-not-collected"
    after = open(gs.vitals_path(repo, root), "rb").read()
    assert after == before


def test_metric_improved_scoped_closure_does_not_verify_on_side_metric(tmp_path, monkeypatch):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "filed",
        "date": "2026-07-01",
        "issue": "#123",
        "metricAtDisposition": {"cloneLines": 50, "files": 2},
        "reason": None,
        "reraiseWhen": "cloneLines grows",
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
        emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"],
        candidate_fields={"cloneLines": 60, "files": 1})
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    result = gsw.finalize(repo, bundle, [], root=root)
    assert result["ok"] is True, result
    advances = result.get("closureAdvances") or []
    assert any(a.get("to") == "reopened" for a in advances)
    assert not any(a.get("to") == "verified-fixed" for a in advances)
    report = open(gs.report_path(repo, root), encoding="utf-8").read()
    assert "reopened" in report
    assert gs.read_ledger(repo, root=root)["byId"]["fixture:normal"]["disposition"] == "filed"
    commit = gsw.commit_ledger(repo, bundle, [], root=root)
    assert commit["ok"] is True, commit
    assert any(a.get("to") == "reopened" for a in (commit.get("advances") or []))


def test_resolve_issue_state_real_gh_shim_on_path(tmp_path, monkeypatch):
    """§12.2: exercise the real subprocess argv shape via a PATH gh shim."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "filed",
        "date": "2026-07-01",
        "issue": "#456",
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

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "echo \"$@\" > \"%s/gh-argv.txt\"\n"
        "if [ \"$1\" = \"issue\" ] && [ \"$2\" = \"view\" ] && [ \"$3\" = \"456\" ] "
        "&& [ \"$4\" = \"--json\" ] && [ \"$5\" = \"state\" ]; then\n"
        "  printf '%%s\\n' '{\"state\":\"CLOSED\"}'\n"
        "  exit 0\n"
        "fi\n"
        "echo 'unexpected argv' >&2\n"
        "exit 1\n" % tmp_path
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", "%s:%s" % (bin_dir, os.environ.get("PATH", "")))

    # Do NOT monkeypatch _resolve_issue_state or subprocess.run.
    state = gsw._resolve_issue_state("#456", cwd=repo)
    assert state == "closed"
    argv = (tmp_path / "gh-argv.txt").read_text().strip()
    assert argv == "issue view 456 --json state"

    lens = FixtureLens(
        emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"], metric=5)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["filedObservations"]["fixture:normal"]["issueState"] == "closed"
    result = gsw.finalize(repo, bundle, [], root=root)
    assert result["ok"] is True
    advances = result.get("closureAdvances") or []
    assert any(a.get("to") == "reopened" for a in advances)
    report = open(gs.report_path(repo, root), encoding="utf-8").read()
    assert "reopened" in report
    commit = gsw.commit_ledger(repo, bundle, [], root=root)
    assert commit["ok"] is True, commit


# --- WO-13 batch E regressions -----------------------------------------------


def test_read_config_healthy_absent_vs_degraded_malformed(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    cfg = gsw.read_config(repo, root=root)
    assert cfg["configStatus"] == "healthy"

    layer = tmp_path / ".claude" / "superheroes" / "guardian.md"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_text(
        "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
        "```json guardian-config\n{ not json\n```\n")
    cfg2 = gsw.read_config(repo, root=root)
    assert cfg2["configStatus"] == "degraded"
    assert cfg2["cadence"] == dict(gsw.CADENCE_DEFAULTS)
    assert any("malformed" in n for n in cfg2["configNotes"])


def test_read_config_non_object_report_card_is_degraded(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write_guardian_layer(tmp_path, {"reportCard": ["nope"]})
    cfg = gsw.read_config(repo, root=_store(tmp_path))
    assert cfg["configStatus"] == "degraded"
    assert cfg["reportCard"] is None


def test_malformed_config_revokes_benching_authority(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_ledger(tmp_path, benched_fixture_ledger(), root=root)
    layer = tmp_path / ".claude" / "superheroes" / "guardian.md"
    layer.write_text(
        "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
        "```json guardian-config\n{ broken\n```\n")
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = FixtureLens(digest={"v": 2}, diff_new=["fixture:tool:new"], emit_normal=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["reportCard"].get("fixture", {}).get("benched") is not True
    assert any("degraded" in n for n in bundle.get("reportCardNotes") or [])


def test_partial_ledger_valid_plus_invalid_collision_surfaces(tmp_path):
    """Valid :1 + invalid :2 must not make a :3 candidate look uniquely settled."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    records = [
        {
            "id": "fixture:tool:a.py:1",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"metric": 1},
            "reason": "owner accepted",
            "reraiseWhen": None,
        },
        {
            "id": "fixture:tool:a.py:2",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"metric": 1},
            # missing required reason → invalid → partial
        },
    ]
    write_ledger(tmp_path, records, root=root)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    class CollisionLens(FixtureLens):
        def collect(self, ctx):
            return {
                "candidates": [{"id": "fixture:tool:a.py:3", "metric": 1}],
                "digest": {"v": 2},
            }

    lens = CollisionLens(digest={"v": 2}, diff_new=["fixture:tool:a.py:3"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "partial"
    assert any(s["id"] == "fixture:tool:a.py:3" for s in bundle["surfaced"]), bundle
    assert not any(k["id"] == "fixture:tool:a.py:3"
                   for k in bundle["funnel"]["killedByLedger"])


def test_finalize_schema_version_matrix_skips_write_and_preserves_bytes(tmp_path):
    """Invalid schemaVersion values must not authorize a rewrite."""
    import pytest

    cases = [
        ("missing", None),
        ("string-2", "2"),
        ("bool-true", True),
        ("zero", 0),
        ("negative", -1),
        ("future", 99),
    ]
    for label, ver in cases:
        case_root = tmp_path / label
        case_root.mkdir()
        repo = init_calibrated_repo(case_root)
        root = _store(case_root)
        write_guardian_layer(case_root, {"vitals": False})
        block = {
            "records": [{
                "id": "fixture:trade",
                "disposition": "accepted",
                "date": "2026-07-01",
                "issue": None,
                "metricAtDisposition": {"metric": 5},
                "reason": "owner accepted this trade",
                "reraiseWhen": None,
            }],
            "sweeps": [],
            "ownerNotes": "must survive %s" % label,
        }
        if ver is not None:
            block["schemaVersion"] = ver
        owner_text = (
            "# Owner prose %s — must survive\n\n"
            "```json %s\n%s\n```\n"
            % (label, gs.LEDGER_FENCE, json.dumps(block, indent=2))
        )
        path = gs.ledger_path(repo, root)
        sc.atomic_write(path, owner_text)
        before = open(path, "rb").read()
        lens = FixtureLens(emit_red_line=True)
        bundle = gsw.collect(repo, lenses=[lens], root=root)
        assert bundle["ledgerState"] in ("malformed", "newer"), (label, bundle["ledgerState"])
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
        assert "ledgerWrite" not in result, label
        assert result.get("closuresUnavailable"), label
        after = open(path, "rb").read()
        assert after == before, label
        commit = gsw.commit_ledger(repo, bundle, disp, root=root)
        assert commit["ok"] is False, label
        assert open(path, "rb").read() == before, label


def test_finalize_malformed_sweeps_skips_write(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    owner_text = (
        "# Owner history — must survive\n\n"
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps({
            "schemaVersion": 1,
            "records": [{
                "id": "fixture:valid",
                "disposition": "filed",
                "date": "2026-07-01",
                "issue": "#1",
                "metricAtDisposition": {"metric": 5},
                "reason": None,
                "reraiseWhen": None,
            }],
            "sweeps": "not-a-list",
        }, indent=2))
    )
    path = gs.ledger_path(repo, root)
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
    assert "ledgerWrite" not in result
    assert result.get("closuresUnavailable")
    assert open(path, "rb").read() == before
    commit = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert commit["ok"] is False
    assert open(path, "rb").read() == before


def test_commit_ledger_successful_sweep_preserves_bytes_outside_machine_regions(tmp_path):
    """Successful writable commit: bytes outside report-card + fence regions stay identical."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    owner_prefix = (
        "<!-- guardian-ledger: schemaVersion=1 status=confirmed "
        "created=2026-07-01 updated=2026-07-01 -->\n\n"
        "# Owner history — must survive a successful sweep\n\n"
        "Hand-written note.\n\n"
        "<!-- owner comment -->\n\n"
    )
    card = (
        "<!-- guardian-report-card:begin updated=2026-07-01 -->\n\n"
        "## Report card\n\n_custom_\n\n"
        "<!-- guardian-report-card:end -->\n\n"
    )
    block = {
        "schemaVersion": 1,
        "ownerNotes": "opaque top-level",
        "records": [{
            "id": "fixture:keep",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"metric": 5},
            "reason": "kept",
            "reraiseWhen": None,
            "extraField": "per-record opaque",
        }],
        "sweeps": [],
    }
    text = owner_prefix + card + "```json %s\n%s\n```\n\nTrailing.\n" % (
        gs.LEDGER_FENCE, json.dumps(block, indent=2))
    path = gs.ledger_path(repo, root)
    sc.atomic_write(path, text)
    before = open(path, encoding="utf-8").read()
    import guardian_ledger as gled
    fence_before = gs._LEDGER_BLOCK.search(before)
    card_before = gled._REPORT_CARD_REGION.search(before)
    owner_before = (
        before[:card_before.start()] + before[card_before.end():fence_before.start()]
        + before[fence_before.end():]
    )

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "ok"
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True
    assert "ledgerWrite" not in fin
    assert open(path, encoding="utf-8").read() == before  # finalize untouched
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result.get("ok") is True, result
    after = open(path, encoding="utf-8").read()
    fence_after = gs._LEDGER_BLOCK.search(after)
    card_after = gled._REPORT_CARD_REGION.search(after)
    owner_after = (
        after[:card_after.start()] + after[card_after.end():fence_after.start()]
        + after[fence_after.end():]
    )
    assert owner_after == owner_before
    parsed = json.loads(fence_after.group(1))
    assert parsed["ownerNotes"] == "opaque top-level"
    assert parsed["records"][0]["extraField"] == "per-record opaque"
    assert "_custom_" not in card_after.group(0)


def test_ambiguous_duplicate_fences_fail_closed_collect_and_finalize(tmp_path):
    """Two guardian-ledger fences: malformed, no suppression, no write, bytes preserved."""
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    block_v1 = {
        "schemaVersion": 1,
        "records": [{
            "id": "fixture:tool:a.py:1",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"metric": 1},
            "reason": "stale first block",
            "reraiseWhen": None,
        }],
        "sweeps": [],
    }
    block_v99 = {
        "schemaVersion": 99,
        "records": [{
            "id": "fixture:tool:a.py:1",
            "disposition": "declined",
            "date": "2026-07-21",
            "issue": None,
            "metricAtDisposition": {"metric": 9},
            "reason": "competing second block",
            "reraiseWhen": None,
        }],
        "sweeps": [],
    }
    owner_text = (
        "# Ambiguous ledger\n\n"
        "```json %s\n%s\n```\n\n"
        "```json %s\n%s\n```\n"
        % (gs.LEDGER_FENCE, json.dumps(block_v1, indent=2),
           gs.LEDGER_FENCE, json.dumps(block_v99, indent=2))
    )
    path = gs.ledger_path(repo, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(owner_text.encode("utf-8"))
    before = open(path, "rb").read()

    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    class DriftLens(FixtureLens):
        def collect(self, ctx):
            return {
                "candidates": [{"id": "fixture:tool:a.py:1", "metric": 1}],
                "digest": {"v": 2},
            }

    lens = DriftLens(digest={"v": 2}, diff_new=["fixture:tool:a.py:1"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["ledgerState"] == "malformed"
    assert any(s["id"] == "fixture:tool:a.py:1" for s in bundle["surfaced"])
    assert not bundle["funnel"]["killedByLedger"]

    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is True  # opaque ledger still commits baseline
    assert "ledgerWrite" not in result
    assert result.get("closuresUnavailable")
    skipped = result["closuresUnavailable"]
    assert "ambiguous" in skipped or "malformed" in skipped
    assert open(path, "rb").read() == before
    commit = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert commit["ok"] is False
    assert open(path, "rb").read() == before


def test_triaged_out_finding_is_not_re_derived(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:normal",
        "disposition": "triaged-out",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": {"metric": 1},
        "reason": "noise",
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
    lens = FixtureLens(emit_normal=True, digest={"v": 2},
                       diff_new=["fixture:normal"], metric=1)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert not any(s["id"] == "fixture:normal" for s in bundle["surfaced"])
    assert any(k["id"] == "fixture:normal" and k["disposition"] == "triaged-out"
               for k in bundle["funnel"]["killedByLedger"])


def test_skill_cadence_phrase_matches_cadence_defaults():
    """§11 drift guard: SKILL.md cadence phrase ↔ CADENCE_DEFAULTS (no hand-typed expect)."""
    import re
    skill = os.path.join(
        os.path.dirname(__file__), "..", "..", "skills", "guardian", "SKILL.md")
    text = open(skill, encoding="utf-8").read()
    matches = re.findall(
        r"≥(\d+)\s+merges\s+or\s+≥(\d+)\s+days", text)
    assert len(matches) == 1, (
        "SKILL.md cadence phrase not uniquely parseable — reword the Cost + cadence "
        "sentence to contain exactly one '≥N merges or ≥N days' form (found %r)"
        % (matches,))
    merges, days = (int(matches[0][0]), int(matches[0][1]))
    assert merges == gsw.CADENCE_DEFAULTS["minMerges"]
    assert days == gsw.CADENCE_DEFAULTS["minDays"]


def test_issue_resolve_respects_aggregate_deadline(monkeypatch, tmp_path):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise OSError("gh missing")

    monkeypatch.setattr(gsw.subprocess, "run", fake_run)
    deadline = gsw.time.monotonic() + 0.01
    gsw.time.sleep(0.02)
    assert gsw._resolve_issue_state("#1", cwd=str(tmp_path), deadline=deadline) is None
    assert calls == []
    cache = {}
    assert gsw._resolve_issue_state("#2", cwd=str(tmp_path),
                                    deadline=gsw.time.monotonic() + 5,
                                    cache=cache) is None
    assert len(calls) == 1
    assert gsw._resolve_issue_state("#2", cwd=str(tmp_path),
                                    deadline=gsw.time.monotonic() + 5,
                                    cache=cache) is None
    assert len(calls) == 1, "cached issue must not re-call gh"


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


def test_trend_ahead_of_snapshot_no_false_vitals_crossing(tmp_path):
    """Snapshot stuck on s1 while trend has s2 — completeness join must use s1, not s2."""
    import guardian_vitals as gv
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "sweepId": "s1",
        "vitals": {"vulnCount": 2},
        "lenses": {},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    gv.append_unlocked(repo, {"vulnCount": 2}, sweep_id="s1",
                       completeness={"vulnCount": {"state": "complete"}},
                       root=root, now="2026-07-21")
    gap = "orphan trend row from failed snapshot write"
    gv.append_unlocked(repo, {"vulnCount": 2}, sweep_id="s2",
                       completeness={"vulnCount": {"state": "partial",
                                                   "reason": gap}},
                       root=root, now="2026-07-22")

    class DepsLens:
        name = "deps"

        def vitals(self, digest):
            return {"vulnCount": (2, gap)}

        def collect(self, ctx):
            return {"candidates": [], "digest": {}}

        required_facts = ()
        collector_version = "0"
        red_lines = lambda self, c: []
        diff = lambda self, p, c: {"new": [], "worsened": [], "resolved": []}
        degrade = lambda self, r: {"lens": self.name, "reason": r}

    bundle = gsw.collect(repo, lenses=[DepsLens()], root=root)
    # Wrong join (s2 partial) would compare partial→partial with matching gap and
    # fabricate a quiet delta; s1 complete vs cur partial must surface non-comparable.
    assert bundle["vitalsDelta"].get("crossings") == []
    not_comp = bundle["vitalsDelta"].get("delta", {}).get("_notComparable", {})
    assert "vulnCount" in not_comp
    assert gv.completeness_for_sweep(repo, "s1", root=root)["vulnCount"]["state"] == "complete"


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


# --- WO-1 permanent capability boundary --------------------------------------


class _PermanentBoundaryLens(FixtureLens):
    """Returns partial + permanentBoundary for version-change seeding tests."""

    def collect(self, ctx):
        out = super().collect(ctx)
        out["status"] = "partial"
        out["reason"] = "structural capability limit"
        out["permanentBoundary"] = True
        return out


def test_permanent_boundary_partial_seeds_new_version_baseline(tmp_path):
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
    new_digest = {"v": 2, "boundary": True}
    lens = _PermanentBoundaryLens(
        collector_version="2",
        emit_normal=True,
        digest=new_digest,
        diff_new=["fixture:normal"],
    )
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    entry = bundle["nextSnapshot"]["lenses"]["fixture"]
    assert entry["collectorVersion"] == "2"
    assert entry["digest"] == new_digest


def test_permanent_boundary_partial_still_degrades(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_entry = {"collectorVersion": "1", "digest": {"v": 1}}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": prior_entry},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    lens = _PermanentBoundaryLens(
        collector_version="2",
        emit_normal=True,
        digest={"v": 2},
        diff_new=["fixture:normal"],
    )
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    degraded = bundle["funnel"]["degradedLenses"]
    assert len(degraded) == 1
    assert degraded[0]["lens"] == "fixture"
    assert degraded[0]["reason"] == "structural capability limit"


def test_permanent_boundary_second_sweep_reports_drift(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_entry = {"collectorVersion": "1", "digest": {"v": 1}}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": prior_entry},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)
    seed_lens = _PermanentBoundaryLens(
        collector_version="2",
        emit_normal=True,
        digest={"v": 2},
        diff_new=["fixture:normal"],
    )
    first = gsw.collect(repo, lenses=[seed_lens], root=root)
    assert first["surfaced"] == []
    assert len(first["funnel"]["killedByDrift"]) == 1
    assert first["funnel"]["killedByDrift"][0]["reason"] == "quiet-baseline"
    gs.write_snapshot_cas(repo, first["nextSnapshot"], first["prevIdentity"], root=root)

    drift_lens = _PermanentBoundaryLens(
        collector_version="2",
        emit_normal=True,
        digest={"v": 3},
        diff_new=["fixture:normal"],
    )
    second = gsw.collect(repo, lenses=[drift_lens], root=root)
    ids = [s["id"] for s in second["surfaced"]]
    assert "fixture:normal" in ids
    assert second["surfaced"][0]["driftReason"] == "new"


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


def test_red_lines_raises_degrades_without_crashing_siblings(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)

    class RedLinesRaisesLens(FixtureLens):
        def red_lines(self, candidates):
            raise RuntimeError("red_lines boom")

    bad = RedLinesRaisesLens(name="bad-red", emit_normal=True)
    good = FixtureLens(name="good-red", emit_red_line=True)
    # Sweep must not raise even though a lens's red_lines() blows up.
    bundle = gsw.collect(repo, lenses=[bad, good], root=root)
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["funnel"]["degradedLenses"][0]["lens"] == "bad-red"
    assert "diff/red_lines raised" in bundle["funnel"]["degradedLenses"][0]["reason"]
    # The fix clears the funnel for the degraded lens: its key was popped so
    # the degraded lens reads consistently. Without the pop, "bad-red" would
    # still appear in raised (it collected one candidate before red_lines raised).
    assert "bad-red" not in bundle["funnel"]["raised"]
    # The healthy sibling is processed normally and still surfaces its red line.
    assert bundle["funnel"]["raised"].get("good-red") == 1
    assert any(s["id"] == "good-red:red-line" for s in bundle["surfaced"])


def test_partial_digest_none_preserves_baseline(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    prior_entry = {"collectorVersion": "0.0.0-test", "digest": {"v": 1, "prior": True}}
    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {},
        "lenses": {"fixture": prior_entry},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    class PartialNoDigestLens(FixtureLens):
        def collect(self, ctx):
            return {
                "candidates": [{"id": "fixture:normal", "complexity": 5, "metric": 1}],
                "digest": None,
                "status": "partial",
                "reason": "incomplete digest",
            }

    lens = PartialNoDigestLens(emit_normal=True, diff_new=["fixture:normal"])
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert len(bundle["funnel"]["degradedLenses"]) == 1
    assert bundle["nextSnapshot"]["lenses"]["fixture"] == prior_entry


# --- WO-1 advisor commit_ledger / single-writer relocation -------------------


def test_commit_ledger_idempotent_byte_identical(tmp_path):
    """Two back-to-back commit_ledger runs with the same bundle leave bytes identical."""
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

    lens = FixtureLens(
        emit_normal=True, digest={"v": 2}, diff_new=["fixture:normal"], metric=5)
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    # Force closed so a closure advance happens on the first commit.
    bundle = dict(bundle)
    fo = dict(bundle.get("filedObservations") or {})
    obs = dict(fo.get("fixture:normal") or {})
    obs["issueState"] = "closed"
    obs["present"] = True
    fo["fixture:normal"] = obs
    bundle["filedObservations"] = fo

    fin = gsw.finalize(repo, bundle, [], root=root)
    assert fin["ok"] is True
    c1 = gsw.commit_ledger(repo, bundle, [], root=root)
    assert c1["ok"] is True, c1
    after_first = open(gs.ledger_path(repo, root), "rb").read()
    c2 = gsw.commit_ledger(repo, bundle, [], root=root)
    assert c2["ok"] is True, c2
    after_second = open(gs.ledger_path(repo, root), "rb").read()
    assert after_second == after_first


def test_commit_ledger_stale_bundle_refuses(tmp_path):
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
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True
    # Advance latest.json as if another session finalized a newer sweep.
    newer = dict(bundle["nextSnapshot"])
    newer["sweptSha"] = (newer.get("sweptSha") or "x") + "-newer"
    sc.atomic_write(
        gs.snapshot_path(repo, root),
        json.dumps(newer, indent=2) + "\n")
    path = gs.ledger_path(repo, root)
    before = open(path, "rb").read() if os.path.isfile(path) else None
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is False
    assert result["reason"] == "stale-bundle"
    if before is not None:
        assert open(path, "rb").read() == before


def test_commit_ledger_roster_read_failed_refuses(tmp_path, monkeypatch):
    import guardian_ledger as gled

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": "fixture:keep",
        "disposition": "accepted",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": {"metric": 1},
        "reason": "kept",
        "reraiseWhen": None,
    }], root=root)
    # Seed a non-empty roster so a wipe would be observable.
    path = gs.ledger_path(repo, root)
    text = open(path, encoding="utf-8").read()
    fence = gs.find_ledger_fences(text)[0]
    block = json.loads(fence.group(1))
    block["sweeps"] = [{"sweepId": "prior-s0", "sweptSha": "abc", "date": "2026-07-01"}]
    mutated = (
        text[:fence.start()]
        + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
        + text[fence.end():]
    )
    open(path, "wb").write(mutated.encode("utf-8"))
    before = open(path, "rb").read()

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
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True

    def boom(_path):
        return "read-failed", []

    monkeypatch.setattr(gled, "_read_sweeps_result", boom)
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is False
    assert result["reason"] == "roster-read-failed"
    assert result.get("retryable") is True
    assert open(path, "rb").read() == before
    assert b"prior-s0" in open(path, "rb").read()


def test_commit_ledger_genuinely_empty_roster_appends(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [], root=root)
    path = gs.ledger_path(repo, root)
    text = open(path, encoding="utf-8").read()
    fence = gs.find_ledger_fences(text)[0]
    block = json.loads(fence.group(1))
    block["sweeps"] = []
    mutated = (
        text[:fence.start()]
        + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
        + text[fence.end():]
    )
    open(path, "wb").write(mutated.encode("utf-8"))

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
    assert gsw.finalize(repo, bundle, disp, root=root)["ok"] is True
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is True, result
    roster = _ledger_sweeps(repo, root)
    assert len(roster) == 1
    assert roster[0]["sweepId"] == bundle["sweepId"]


def test_cli_commit_ledger_writes_ledger(tmp_path):
    """Real CLI: main(['commit-ledger', ...]) writes roster + report card to ledger.md."""
    import io
    from contextlib import redirect_stdout

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
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True
    assert "ledgerWrite" not in fin

    bundle_path = str(tmp_path / "bundle.json")
    disp_path = str(tmp_path / "disp.json")
    open(bundle_path, "w", encoding="utf-8").write(json.dumps(bundle))
    open(disp_path, "w", encoding="utf-8").write(json.dumps(disp))

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = gsw.main([
            "commit-ledger",
            "--cwd", repo,
            "--root", root,
            "--bundle", bundle_path,
            "--dispositions", disp_path,
        ])
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["ok"] is True, out
    path = gs.ledger_path(repo, root)
    assert os.path.isfile(path)
    roster = _ledger_sweeps(repo, root)
    assert len(roster) == 1
    assert roster[0]["sweepId"] == bundle["sweepId"]
    text = open(path, encoding="utf-8").read()
    assert "guardian-report-card:begin" in text
    assert "```json %s" % gs.LEDGER_FENCE in text


# --- WO-1c: atomic commit_ledger + fail-closed vitals commit marker ----------


def test_finalize_ok_string_failed_does_not_advance_snapshot(tmp_path, monkeypatch):
    """WO-1d Fix C: only literal ok=True is non-blocking; ok='failed' still blocks."""
    import guardian_vitals as gv

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": True})

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""
        return R()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    prev_identity = bundle["prevIdentity"]
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]

    def truthy_but_not_true(*args, **kwargs):
        return {"ok": "failed", "skipped": "x"}

    monkeypatch.setattr(gv, "append_unlocked", truthy_but_not_true)
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is False
    assert result["reason"] == "durable-write-failed"
    assert not os.path.isfile(gs.snapshot_path(repo, root=root))
    assert gs.snapshot_identity(gs.read_snapshot(repo, root=root)) == prev_identity


def test_finalize_persists_sweep_id_and_same_session_commit_succeeds(tmp_path):
    """WO-1d Fix A: latest.json carries sweepId; same-session commit_ledger succeeds."""
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
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True
    head = gs.read_snapshot(repo, root=root)
    assert head.get("sweepId") == bundle["sweepId"]
    # Identity ignores the extra field.
    assert gs.snapshot_identity(head) == gs.snapshot_identity(bundle["nextSnapshot"])
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is True, result


def test_commit_ledger_stale_bundle_when_sweep_id_differs(tmp_path):
    """WO-1d Fix A: identical nextSnapshot but older sweepId → stale-bundle."""
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
    fin = gsw.finalize(repo, bundle, disp, root=root)
    assert fin["ok"] is True
    assert gsw.commit_ledger(repo, bundle, disp, root=root)["ok"] is True

    older = dict(bundle)
    older["sweepId"] = "older-" + bundle["sweepId"]
    older["filedObservations"] = {"different": True}  # would close wrong if landed
    path = gs.ledger_path(repo, root)
    before = open(path, "rb").read()
    result = gsw.commit_ledger(repo, older, disp, root=root)
    assert result["ok"] is False
    assert result["reason"] == "stale-bundle"
    assert result.get("onDiskSweepId") == bundle["sweepId"]
    assert result.get("expectedSweepId") == older["sweepId"]
    assert open(path, "rb").read() == before


def test_collect_after_finalize_ignores_persisted_sweep_id(tmp_path):
    """WO-1d Fix A: next collect still works when latest.json carries sweepId."""
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
    assert gsw.finalize(repo, bundle, disp, root=root)["ok"] is True
    head = gs.read_snapshot(repo, root=root)
    assert "sweepId" in head
    # Second collect must treat head as a valid prev (extra field ignored by identity/CAS).
    bundle2 = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle2["prevIdentity"] == gs.snapshot_identity(head)
    assert bundle2["prevIdentity"] == gs.snapshot_identity(bundle["nextSnapshot"])
    assert bundle2["sweepId"]
    assert set(bundle2["nextSnapshot"]) == set(gs.SNAPSHOT_KEYS)


def test_finalize_ok_false_vitals_with_skipped_key_does_not_advance_snapshot(
        tmp_path, monkeypatch):
    """Fix 6: ok=False must block latest.json even when a skipped key is present."""
    import guardian_vitals as gv

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": True})

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""
        return R()

    lens = FixtureLens(emit_red_line=True)
    bundle = gsw.collect(repo, lenses=[lens], root=root, run=fake_run)
    prev_identity = bundle["prevIdentity"]
    disp = [{
        "id": bundle["surfaced"][0]["id"],
        "verdict": "validated",
        "consequence": "x",
        "receipt": "y",
        "effort": "z",
        "ledgerJoin": bundle["surfaced"][0]["id"],
    }]

    def bad_skip(*args, **kwargs):
        return {
            "ok": False,
            "skipped": "should-not-unblock",
            "reason": "durable vitals write failed",
        }

    monkeypatch.setattr(gv, "append_unlocked", bad_skip)
    result = gsw.finalize(repo, bundle, disp, root=root)
    assert result["ok"] is False
    assert result["reason"] == "durable-write-failed"
    assert not os.path.isfile(gs.snapshot_path(repo, root=root))
    assert gs.snapshot_identity(gs.read_snapshot(repo, root=root)) == prev_identity


def test_commit_ledger_preserves_concurrent_roster_entry(tmp_path, monkeypatch):
    """Fix 2 via commit_ledger: a sweep landed after the caller's roster read survives."""
    import guardian_ledger as gled

    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [], root=root)
    path = gs.ledger_path(repo, root)
    text = open(path, encoding="utf-8").read()
    fence = gs.find_ledger_fences(text)[0]
    block = json.loads(fence.group(1))
    block["sweeps"] = [{"sweepId": "prior-s0", "sweptSha": "abc", "date": "2026-07-01"}]
    open(path, "wb").write((
        text[:fence.start()]
        + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
        + text[fence.end()]
    ).encode("utf-8"))

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
    assert gsw.finalize(repo, bundle, disp, root=root)["ok"] is True

    real_read = gled._read_sweeps_result

    def stale_then_concurrent(p):
        status, roster = real_read(p)
        # Simulate a concurrent commit appending between read and write.
        cur = open(path, encoding="utf-8").read()
        f = gs.find_ledger_fences(cur)[0]
        b = json.loads(f.group(1))
        b["sweeps"] = list(b.get("sweeps") or []) + [{
            "sweepId": "concurrent-s1",
            "sweptSha": "def",
            "date": "2026-07-21",
        }]
        open(path, "wb").write((
            cur[:f.start()]
            + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(b, indent=2))
            + cur[f.end()]
        ).encode("utf-8"))
        return status, roster  # stale (missing concurrent-s1)

    monkeypatch.setattr(gled, "_read_sweeps_result", stale_then_concurrent)
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is True, result
    ids = [s["sweepId"] for s in _ledger_sweeps(repo, root)]
    assert "prior-s0" in ids
    assert "concurrent-s1" in ids
    assert bundle["sweepId"] in ids


def test_commit_ledger_calls_write_locked_not_lock_acquiring_write(
        tmp_path, monkeypatch):
    """Fix 1: commit_ledger holds the sweep lock and must call _write_locked (no self-deadlock)."""
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
    assert gsw.finalize(repo, bundle, disp, root=root)["ok"] is True

    write_calls = []
    locked_calls = []
    real_write = gled.write
    real_locked = gled._write_locked

    def spy_write(*a, **k):
        write_calls.append(1)
        return real_write(*a, **k)

    def spy_locked(*a, **k):
        locked_calls.append(1)
        # Sweep lock must already be held by commit_ledger.
        lock_path = gs.sweep_lock_path(repo, root)
        assert os.path.isdir(lock_path) or os.path.exists(lock_path)
        return real_locked(*a, **k)

    monkeypatch.setattr(gled, "write", spy_write)
    monkeypatch.setattr(gled, "_write_locked", spy_locked)
    result = gsw.commit_ledger(repo, bundle, disp, root=root)
    assert result["ok"] is True, result
    assert locked_calls, "commit_ledger must call _write_locked"
    assert not write_calls, "commit_ledger must not call lock-acquiring write"


def _stack_tags_fact(tmp_path, repo):
    out = gsw.verify_config(repo, root=_store(tmp_path), needed_facts=set())
    return {f["fact"]: f for f in out["facts"]}["stack-tags"]


def test_stack_tags_we_shaped_fixture_zero_mismatch_noise(tmp_path):
    repo = init_calibrated_repo(
        tmp_path,
        stack_tags=["node", "ts", "typescript", "nextjs", "react", "mongodb"],
    )
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14", "react": "18", "mongodb": "6"}}))
    (tmp_path / "tsconfig.json").write_text("{}")
    fact = _stack_tags_fact(tmp_path, repo)
    assert fact["receipt"]["mismatched"] == []
    assert fact["status"] == "match"


def test_stack_tags_genuine_wrong_tag_still_mismatched(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["python"])
    (tmp_path / "package.json").write_text("{}")
    fact = _stack_tags_fact(tmp_path, repo)
    assert fact["status"] == "mismatch"
    assert "python" in fact["receipt"]["mismatched"]


def test_stack_tags_unknown_tag_unverifiable(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["cobol"])
    fact = _stack_tags_fact(tmp_path, repo)
    assert fact["status"] == "unverifiable"
    assert "cobol" in fact["receipt"]["unverifiable"]
    assert "cobol" not in fact["receipt"]["mismatched"]


def test_stack_tags_framework_absence_unverifiable_not_mismatch(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["nextjs"])
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"react": "18"}}))
    fact = _stack_tags_fact(tmp_path, repo)
    assert "nextjs" not in fact["receipt"]["mismatched"]
    assert "nextjs" in fact["receipt"]["unverifiable"]


def test_stack_tags_typescript_maps_to_ts(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["typescript"])
    (tmp_path / "package.json").write_text("{}")
    fact = _stack_tags_fact(tmp_path, repo)
    assert "typescript" in fact["receipt"]["matched"]
    assert fact["receipt"]["mismatched"] == []


def test_stack_tags_empty_repo_ecosystem_tag_unverifiable(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["python"])
    fact = _stack_tags_fact(tmp_path, repo)
    assert fact["status"] == "unverifiable"
    assert "python" in fact["receipt"]["unverifiable"]
    assert fact["receipt"]["mismatched"] == []


def test_stack_tags_malformed_package_json_framework_unverifiable(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["react"])
    (tmp_path / "package.json").write_text("{ not json")
    fact = _stack_tags_fact(tmp_path, repo)
    assert "react" in fact["receipt"]["unverifiable"]


def test_stack_tags_mixed_precedence_mismatch_over_unverifiable(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["python", "cobol"])
    (tmp_path / "package.json").write_text("{}")
    fact = _stack_tags_fact(tmp_path, repo)
    assert fact["status"] == "mismatch"
    assert "python" in fact["receipt"]["mismatched"]
    assert "cobol" in fact["receipt"]["unverifiable"]


def test_stack_tags_non_string_tag_unverifiable_unit():
    assert gsw._classify_stack_tag(123, set(), None) == "unverifiable"
    assert gsw._classify_stack_tag(None, set(), None) == "unverifiable"


def test_stack_tags_non_string_tag_does_not_crash_sweep(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=[123, "python"])
    (tmp_path / "package.json").write_text("{}")
    fact = _stack_tags_fact(tmp_path, repo)
    assert 123 in fact["receipt"]["unverifiable"]
    assert "python" in fact["receipt"]["mismatched"]


def test_stack_tags_same_family_manifest_not_mismatch(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["node"])
    (tmp_path / "tsconfig.json").write_text("{}")
    fact = _stack_tags_fact(tmp_path, repo)
    assert "node" not in fact["receipt"]["mismatched"]
    assert "node" in fact["receipt"]["unverifiable"]


def test_stack_tags_casefold_matches_and_preserves_original(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["TypeScript", "NextJS"])
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14"}}))
    fact = _stack_tags_fact(tmp_path, repo)
    assert "TypeScript" in fact["receipt"]["matched"]
    assert "NextJS" in fact["receipt"]["matched"]
    assert fact["receipt"]["mismatched"] == []


def test_stack_tags_deeply_nested_package_json_no_crash(tmp_path):
    repo = init_calibrated_repo(tmp_path, stack_tags=["react"])
    (tmp_path / "package.json").write_text('{"x":' * 1100 + '0' + '}' * 1100)
    fact = _stack_tags_fact(tmp_path, repo)
    assert "react" in fact["receipt"]["unverifiable"]
