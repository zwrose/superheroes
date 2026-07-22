import json
import os
import shutil
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

# Tiny verify command that emits a pytest-style summary the vitals suite parser reads.
# Exercised for real (no monkeypatch of guardian_vitals.collect / verify seam).
_VERIFY_PYTEST_SUMMARY = (
    "python3 -c \"print('===== 2 passed, 1 skipped in 0.05s')\""
)


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


def _ledger_record_ids(repo, root=None):
    read = gs.read_ledger(repo, root=root)
    return {r["id"]: r for r in read["records"] if isinstance(r, dict) and "id" in r}


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
    """Real collect→finalize with vitals ON: five files, measured vitals, ledger survival."""
    root = str(tmp_path / "store")
    digest = {
        "v": 2,
        "duplicationPercent": 12.5,
        "majorsBehind": 2,
        "vulnCount": 1,
    }
    if mode == mr.GLOBAL:
        repo = init_calibrated_repo(
            tmp_path, remote="git@github.com:o/r.git",
            verify_command=_VERIFY_PYTEST_SUMMARY)
        store = mr.ensure_project_store(repo, root=root)
        cfg = os.path.join(store, "config")
        os.makedirs(cfg, exist_ok=True)
        sc.atomic_write(os.path.join(cfg, "core.md"), cm.render_core(
            {"verifyCommand": _VERIFY_PYTEST_SUMMARY, "stackTags": [],
             "threatModel": "t", "patterns": ""},
            "confirmed", "2026-01-01", "2026-01-01"))
        mr.write_registry(repo, mr.GLOBAL, "rk", root=root, now="2026-06-21T00:00:00Z")
        layer = os.path.join(cfg, "guardian.md")
        sc.atomic_write(
            layer,
            "<!-- guardian: schemaVersion=1 status=confirmed -->\n\n"
            "```json guardian-config\n%s\n```\n" % json.dumps({"vitals": True}))
    else:
        repo = init_calibrated_repo(tmp_path, verify_command=_VERIFY_PYTEST_SUMMARY)
        write_guardian_layer(tmp_path, {"vitals": True})
        mr.write_registry(repo, mr.IN_REPO, "rk", root=root, now="2026-06-21T00:00:00Z")

    # Seed a benched lens ledger so report-card state is present, plus an accepted
    # trade that should suppress ordinary drift. Object-shaped metric (writer schema).
    records = benched_fixture_ledger()
    accepted = {
        "id": "fixture:normal",
        "disposition": "accepted",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": {"metric": 5},
        "reason": "tolerated",
        "reraiseWhen": None,
        "adjudicatedIn": "s0",
    }
    records.append(accepted)
    write_ledger(tmp_path if mode == mr.IN_REPO else repo, records, root=root)
    seeded_ids = {r["id"]: dict(r) for r in records}

    snap = {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "abc",
        "vitals": {"locTotal": 10, "fileCount": 2},
        "lenses": {"fixture": {"collectorVersion": "0.0.0-test", "digest": {"v": 1}}},
    }
    gs.write_snapshot_cas(repo, snap, None, root=root)

    # Production vital keys on the digest — fixture lens name won't feed DIGEST_SOURCES
    # (those look for duplication/deps lenses), so also attach a companion digest via a
    # second lens-shaped entry is out of FixtureLens scope; suite + repo vitals are the
    # seam under test here. Provide a digests map by using a named lens that matches.
    class DupDigestLens(FixtureLens):
        name = "duplication"
        collector_version = "0.0.0-test"

        def __init__(self):
            super().__init__(
                name="duplication", emit_red_line=False, emit_normal=False,
                digest={
                    "duplicationPercent": 12.5,
                    "percentDuplicated": 12.5,
                })

    class DepsDigestLens(FixtureLens):
        def __init__(self):
            super().__init__(
                name="dependencies", emit_red_line=False, emit_normal=False,
                digest={"majorsBehind": 2, "vulnCount": 1})

    lens = FixtureLens(
        emit_red_line=True, emit_normal=True, digest=digest,
        diff_new=["fixture:normal"], metric=5)
    bundle = gsw.collect(
        cwd=repo, lenses=[lens, DupDigestLens(), DepsDigestLens()], root=root)
    assert funnel_conserved(bundle)
    assert bundle["storageMode"] == mode
    assert bundle["reportCard"]["fixture"]["benched"] is True
    surfaced_ids = [s["id"] for s in bundle["surfaced"]]
    assert "fixture:red-line" in surfaced_ids
    assert "fixture:normal" not in surfaced_ids
    assert any(k.get("disposition") == "accepted"
               for k in bundle["funnel"]["killedByLedger"])

    # Measured vitals must flow through nextSnapshot (real verify + digest seam).
    snap_vitals = bundle["nextSnapshot"]["vitals"]
    assert snap_vitals.get("suiteTestCount") == 3  # 2 passed + 1 skipped
    assert snap_vitals.get("suiteSkipped") == 1
    assert snap_vitals.get("suiteRuntimeSeconds") == 0.05
    assert snap_vitals.get("duplicationPercent") == 12.5
    assert snap_vitals.get("majorsBehind") == 2
    assert snap_vitals.get("vulnCount") == 1
    assert isinstance(snap_vitals.get("locTotal"), int)
    assert isinstance(snap_vitals.get("fileCount"), int)

    result = gsw.finalize(repo, bundle, _dispositions_for(bundle), root=root)
    assert result["ok"] is True
    assert "ledgerWrite" not in result
    _assert_five_files(repo, root)

    # finalize is read-only on the ledger — seeded history still present before commit.
    before_commit = _ledger_record_ids(repo, root)
    for rid, seeded in seeded_ids.items():
        assert rid in before_commit, "seeded record %s missing after finalize" % rid
        assert before_commit[rid]["disposition"] == seeded["disposition"]

    commit = gsw.commit_ledger(repo, bundle, _dispositions_for(bundle), root=root)
    assert commit["ok"] is True, commit

    # Ledger history survives commit — regression guard for opaque-ledger overwrite.
    after_by_id = _ledger_record_ids(repo, root)
    for rid, seeded in seeded_ids.items():
        assert rid in after_by_id, "seeded record %s missing after commit_ledger" % rid
        assert after_by_id[rid]["disposition"] == seeded["disposition"]
        if seeded.get("reason") is not None:
            assert after_by_id[rid].get("reason") == seeded["reason"]

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

    # Persisted vitals.jsonl carries the measured values (no monkeypatch of the seam).
    trend = gv.read_trend(repo, root=root)
    assert trend["status"] == "ok"
    matching = [r for r in trend["records"] if r.get("sweepId") == bundle["sweepId"]]
    assert len(matching) == 1
    persisted = matching[0]["vitals"]
    assert persisted.get("suiteTestCount") == 3
    assert persisted.get("suiteSkipped") == 1
    assert persisted.get("duplicationPercent") == 12.5
    assert persisted.get("majorsBehind") == 2
    assert persisted.get("vulnCount") == 1

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
    # Seeded history still intact after finalize retry (ledger write is commit_ledger's).
    after_retry = _ledger_record_ids(repo, root)
    for rid in seeded_ids:
        assert after_retry[rid]["disposition"] == seeded_ids[rid]["disposition"]
    # Retried commit of the same sweepId must leave the roster at one entry.
    commit_retry = gsw.commit_ledger(
        repo, bundle, _dispositions_for(bundle), root=root)
    assert commit_retry["ok"] is True, commit_retry
    assert len(_ledger_sweeps(repo, root)) == 1

    # Second real sweep grows the roster — five-file assertion also means history grows.
    subprocess.run(
        ["git", "-C", repo,
         "-c", "user.email=guardian@test.local", "-c", "user.name=guardian-test",
         "commit", "-q", "--allow-empty", "-m", "second-sweep"],
        check=True)
    lens2 = FixtureLens(
        emit_red_line=True, emit_normal=True, digest={"v": 3, "duplicationPercent": 12.5},
        diff_new=["fixture:normal"], metric=5)
    bundle3 = gsw.collect(
        cwd=repo, lenses=[lens2, DupDigestLens(), DepsDigestLens()], root=root)
    assert funnel_conserved(bundle3)
    assert bundle3["sweepId"] != bundle["sweepId"]
    result2 = gsw.finalize(repo, bundle3, _dispositions_for(bundle3), root=root)
    assert result2["ok"] is True
    commit2 = gsw.commit_ledger(repo, bundle3, _dispositions_for(bundle3), root=root)
    assert commit2["ok"] is True, commit2
    _assert_five_files(repo, root)
    roster = _ledger_sweeps(repo, root)
    assert [s["sweepId"] for s in roster] == [bundle["sweepId"], bundle3["sweepId"]]
    final_by_id = _ledger_record_ids(repo, root)
    for rid in seeded_ids:
        assert final_by_id[rid]["disposition"] == seeded_ids[rid]["disposition"]


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

    # The subprocess inherits env = os.environ.copy() (same PATH), so
    # shutil.which("jscpd") in this process matches the subprocess's tool
    # availability. duplication (jscpd) is the only tool-dependent lens in this
    # smoke test — the calibrated fixture repo has no .py/.js files, so the
    # hotspots lens collects-empty and never degrades here. Assert BOTH sides,
    # keyed on jscpd availability, so this is green locally AND in CI.
    degraded = out["funnel"]["degradedLenses"]
    dup = [d for d in degraded if d.get("lens") == "duplication"]
    if shutil.which("jscpd"):
        # tool present ⇒ the lens must NOT degrade, and candidates are well-formed
        assert dup == [], "jscpd present ⇒ duplication must not degrade; got %r" % (degraded,)
        assert isinstance(out["surfaced"], list)
        for c in out["surfaced"]:
            assert isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"], c
    else:
        # tool absent ⇒ EXACTLY the well-formed degrade entry, with install guidance
        assert len(dup) == 1, "jscpd absent ⇒ exactly one duplication degrade entry; got %r" % (degraded,)
        entry = dup[0]
        assert entry.get("degraded") is True
        assert entry.get("lens") == "duplication"
        reason = entry.get("reason") or ""
        assert "jscpd" in reason, reason
        assert "npm install -g jscpd" in reason, reason
