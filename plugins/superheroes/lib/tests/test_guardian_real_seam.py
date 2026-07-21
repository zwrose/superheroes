import json
import os
import subprocess
import sys

import core_md as cm
import guardian_store as gs
import guardian_sweep as gsw
import guardian_vitals as gv
import mode_registry as mr
import store_core as sc
from guardian_fixtures import (
    FixtureLens, benched_fixture_ledger, funnel_conserved, init_calibrated_repo,
    write_guardian_layer, write_ledger,
)


_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dispositions_for(bundle):
    out = []
    for s in bundle["surfaced"]:
        out.append({
            "id": s["id"],
            "verdict": "validated",
            "consequence": "Address the finding.",
            "receipt": "fixture receipt",
            "effort": "small",
            "ledgerJoin": s["id"],
        })
    return out


def _assert_five_files(repo, root):
    assert os.path.isfile(gs.guardian_layer_path(repo, root)), "guardian.md missing"
    assert os.path.isfile(gs.report_path(repo, root)), "report.md missing"
    assert os.path.isfile(gs.snapshot_path(repo, root)), "latest.json missing"
    assert os.path.isfile(gs.ledger_path(repo, root)), "ledger.md missing"
    assert os.path.isfile(gs.vitals_path(repo, root)), "vitals.jsonl missing"


def _ledger_sweeps(repo, root=None):
    text = open(gs.ledger_path(repo, root), encoding="utf-8").read()
    block = json.loads(
        text.split("```json %s\n" % gs.LEDGER_FENCE)[1].split("\n```")[0])
    return block.get("sweeps") or []


def test_real_seam_collect_finalize_writes_artifacts(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = str(tmp_path / "store")
    write_guardian_layer(tmp_path, {"vitals": False})
    lens = FixtureLens(emit_red_line=True, emit_normal=True)
    bundle = gsw.collect(cwd=repo, lenses=[lens], root=store)

    assert funnel_conserved(bundle)

    dispositions = _dispositions_for(bundle)
    result = gsw.finalize(repo, bundle, dispositions, root=store)
    assert result["ok"] is True

    report_p = gs.report_path(repo, root=store)
    snap_p = gs.snapshot_path(repo, root=store)
    assert os.path.isfile(report_p)
    assert os.path.isfile(snap_p)

    snap = json.load(open(snap_p))
    assert snap["schemaVersion"] == gs.SNAPSHOT_SCHEMA_VERSION
    assert "lenses" in snap
    assert "fixture" in snap["lenses"]

    report_text = open(report_p).read()
    assert "# Guardian sweep report" in report_text
    assert "Candidate funnel" in report_text


def _real_seam_both_modes(tmp_path, *, mode):
    """Real collect→finalize: five files, ledger suppression, report card, idempotent retry."""
    root = str(tmp_path / "store")
    if mode == mr.GLOBAL:
        repo = init_calibrated_repo(tmp_path, remote="git@github.com:o/r.git")
        store = mr.ensure_project_store(repo, root=root)
        cfg = os.path.join(store, "config")
        os.makedirs(cfg, exist_ok=True)
        sc.atomic_write(os.path.join(cfg, "core.md"), cm.render_core(
            {"verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": ""},
            "confirmed", "2026-01-01", "2026-01-01"))
        mr.write_registry(repo, mr.GLOBAL, "rk", root=root, now="2026-06-21T00:00:00Z")
        layer = os.path.join(cfg, "guardian.md")
        sc.atomic_write(
            layer,
            "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
            "```json guardian-config\n%s\n```\n" % json.dumps({"vitals": False}))
    else:
        repo = init_calibrated_repo(tmp_path)
        write_guardian_layer(tmp_path, {"vitals": False})
        mr.write_registry(repo, mr.IN_REPO, "rk", root=root, now="2026-06-21T00:00:00Z")

    # Seed a benched lens ledger so report-card state is present, plus an accepted
    # trade that should suppress ordinary drift.
    records = benched_fixture_ledger()
    records.append({
        "id": "fixture:normal",
        "disposition": "accepted",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": 5,
        "reason": "tolerated",
        "reraiseWhen": None,
        "adjudicatedIn": "s0",
    })
    write_ledger(tmp_path if mode == mr.IN_REPO else repo, records, root=root)

    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {"locTotal": 10, "fileCount": 2},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    lens = FixtureLens(
        emit_red_line=True, emit_normal=True, digest={"v": 2},
        diff_new=["fixture:normal"], metric=5)
    bundle = gsw.collect(cwd=repo, lenses=[lens], root=root)
    assert funnel_conserved(bundle)
    assert bundle["storageMode"] == mode
    assert bundle["reportCard"]["fixture"]["benched"] is True
    surfaced_ids = [s["id"] for s in bundle["surfaced"]]
    assert "fixture:red-line" in surfaced_ids
    assert "fixture:normal" not in surfaced_ids
    assert any(k.get("disposition") == "accepted"
               for k in bundle["funnel"]["killedByLedger"])

    result = gsw.finalize(repo, bundle, _dispositions_for(bundle), root=root)
    assert result["ok"] is True
    _assert_five_files(repo, root)

    roster_after_first = _ledger_sweeps(repo, root)
    assert len(roster_after_first) == 1
    assert roster_after_first[0]["sweepId"] == bundle["sweepId"]

    report_text = open(gs.report_path(repo, root=root)).read()
    if mode == mr.IN_REPO:
        assert "storage: in-repo" in report_text
    else:
        assert "storage: global" in report_text
        assert "machine-local" in report_text
    assert "Report card" in report_text
    assert "benched" in report_text

    # Idempotent retry: same sweepId appends exactly one vitals record and one roster entry.
    bundle2 = dict(bundle)
    bundle2["prevIdentity"] = gs.snapshot_identity(
        gs.read_snapshot(repo, root=root))
    retry = gsw.finalize(repo, bundle2, _dispositions_for(bundle2), root=root)
    assert retry["ok"] is True
    trend = gv.read_trend(repo, root=root)
    matching = [r for r in trend["records"] if r.get("sweepId") == bundle["sweepId"]]
    assert len(matching) == 1
    assert len(_ledger_sweeps(repo, root)) == 1

    # Second real sweep grows the roster — five-file assertion also means history grows.
    subprocess.run(
        ["git", "-C", repo,
         "-c", "user.email=guardian@test.local", "-c", "user.name=guardian-test",
         "commit", "-q", "--allow-empty", "-m", "second-sweep"],
        check=True)
    lens2 = FixtureLens(
        emit_red_line=True, emit_normal=True, digest={"v": 3},
        diff_new=["fixture:normal"], metric=5)
    bundle3 = gsw.collect(cwd=repo, lenses=[lens2], root=root)
    assert funnel_conserved(bundle3)
    assert bundle3["sweepId"] != bundle["sweepId"]
    result2 = gsw.finalize(repo, bundle3, _dispositions_for(bundle3), root=root)
    assert result2["ok"] is True
    _assert_five_files(repo, root)
    roster = _ledger_sweeps(repo, root)
    assert [s["sweepId"] for s in roster] == [bundle["sweepId"], bundle3["sweepId"]]


def test_real_seam_in_repo_mode(tmp_path):
    _real_seam_both_modes(tmp_path, mode=mr.IN_REPO)


def test_real_seam_global_mode(tmp_path):
    _real_seam_both_modes(tmp_path, mode=mr.GLOBAL)


def test_cli_collect_subprocess_smoke(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = str(tmp_path / "store")
    write_guardian_layer(tmp_path, {"vitals": False})
    env = os.environ.copy()
    env["WORKHORSE_STORE_ROOT"] = store
    r = subprocess.run(
        [sys.executable, os.path.join(_LIB, "guardian_sweep.py"),
         "collect", "--cwd", repo, "--root", store],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "surfaced" in out
    assert "funnel" in out
    assert out["funnel"]["degradedLenses"] == []
