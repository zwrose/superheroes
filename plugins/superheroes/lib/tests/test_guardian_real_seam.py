import json
import os
import subprocess
import sys

import guardian_store as gs
import guardian_sweep as gsw
from guardian_fixtures import FixtureLens, init_calibrated_repo


_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_real_seam_collect_finalize_writes_artifacts(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = str(tmp_path / "store")
    lens = FixtureLens(emit_red_line=True, emit_normal=True)
    bundle = gsw.collect(cwd=repo, lenses=[lens], root=store)

    raised = sum(bundle["funnel"]["raised"].values())
    killed_drift = len(bundle["funnel"]["killedByDrift"])
    killed_ledger = len(bundle["funnel"]["killedByLedger"])
    tracked_filed = len(bundle["funnel"]["trackedFiled"])
    surfaced = len(bundle["surfaced"])
    assert raised == killed_drift + killed_ledger + tracked_filed + surfaced

    dispositions = []
    for s in bundle["surfaced"]:
        dispositions.append({
            "id": s["id"],
            "verdict": "validated",
            "consequence": "Address the finding.",
            "receipt": "fixture receipt",
            "effort": "small",
            "ledgerJoin": s["id"],
        })
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


def test_cli_collect_subprocess_smoke(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = str(tmp_path / "store")
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
