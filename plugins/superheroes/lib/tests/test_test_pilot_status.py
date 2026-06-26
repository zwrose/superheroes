import json
import subprocess
import sys
from pathlib import Path

import control_plane
import test_pilot_status as status


HEAD = "abc123"
BRANCH = "feature/test-pilot"
REPO_ROOT = Path(__file__).resolve().parents[4]


def _applicable(**overrides):
    data = {
        "schemaVersion": 1,
        "verdict": "applicable",
        "head": HEAD,
        "branch": BRANCH,
        "baseline": {"head": HEAD},
        "review": {"covers": HEAD},
        "remotePr": {"head": HEAD},
        "artifacts": {"plan": "plan.md", "results": "results.md"},
        "records": [{"kind": "browser", "status": "passed"}],
    }
    data.update(overrides)
    return data


def test_ready_applicable_accepts_current_complete_status():
    result = status.ready_applicable(_applicable(), HEAD)
    assert result["ok"] is True


def test_ready_applicable_rejects_missing_or_stale_core_identity():
    assert status.ready_applicable(_applicable(head="old"), HEAD)["ok"] is False
    assert "stale head" in status.ready_applicable(_applicable(head="old"), HEAD)["reason"]

    missing_branch = _applicable()
    missing_branch.pop("branch")
    assert status.ready_applicable(missing_branch, HEAD)["ok"] is False
    assert "branch" in status.ready_applicable(missing_branch, HEAD)["reason"]


def test_ready_applicable_requires_browser_executed_record_and_all_passed():
    no_browser = _applicable(records=[{"kind": "api", "status": "passed"}])
    assert status.ready_applicable(no_browser, HEAD)["ok"] is False
    assert "browser-executed" in status.ready_applicable(no_browser, HEAD)["reason"]

    failed = _applicable(records=[{"kind": "browser", "status": "failed"}])
    assert status.ready_applicable(failed, HEAD)["ok"] is False
    assert "not passed" in status.ready_applicable(failed, HEAD)["reason"]


def test_ready_applicable_allows_preserved_skipped_steps_only():
    allowed = _applicable(
        records=[
            {"kind": "browser", "status": "passed"},
            {"kind": "browser", "status": "skipped", "allowed": True, "preserved": True},
        ]
    )
    assert status.ready_applicable(allowed, HEAD)["ok"] is True

    skipped = _applicable(records=[{"kind": "browser", "status": "skipped", "allowed": True}])
    assert status.ready_applicable(skipped, HEAD)["ok"] is False
    assert "not passed" in status.ready_applicable(skipped, HEAD)["reason"]


def test_ready_applicable_requires_artifacts_and_fallback_when_posting_failed():
    no_plan = _applicable(artifacts={"results": "results.md"})
    assert status.ready_applicable(no_plan, HEAD)["ok"] is False
    assert "plan artifact" in status.ready_applicable(no_plan, HEAD)["reason"]

    posting_failed = _applicable(prPosting={"ok": False}, artifacts={"plan": "plan.md", "results": "results.md"})
    assert status.ready_applicable(posting_failed, HEAD)["ok"] is False
    assert "fallback artifacts" in status.ready_applicable(posting_failed, HEAD)["reason"]

    with_fallback = _applicable(
        prPosting={"ok": False},
        artifacts={"plan": "plan.md", "results": "results.md", "fallback": ["plan.md", "results.md"]},
    )
    assert status.ready_applicable(with_fallback, HEAD)["ok"] is True


def test_ready_applicable_requires_fresh_baseline_review_verify_and_remote_pr():
    assert status.ready_applicable(_applicable(baseline={"head": "old"}), HEAD)["ok"] is False
    assert "baseline" in status.ready_applicable(_applicable(baseline={"head": "old"}), HEAD)["reason"]

    assert status.ready_applicable(_applicable(review={"covers": "old"}), HEAD)["ok"] is False
    assert "review coverage" in status.ready_applicable(_applicable(review={"covers": "old"}), HEAD)["reason"]

    fixes = _applicable(fixes={"count": 1}, verify={"result": "pass", "head": "old"})
    assert status.ready_applicable(fixes, HEAD)["ok"] is False
    assert "verify-pass" in status.ready_applicable(fixes, HEAD)["reason"]

    assert status.ready_applicable(_applicable(remotePr={"head": "old"}), HEAD)["ok"] is False
    assert "remote PR head" in status.ready_applicable(_applicable(remotePr={"head": "old"}), HEAD)["reason"]


def test_ready_not_applicable_only_requires_current_head_and_rationale():
    result = status.ready_not_applicable(
        {
            "schemaVersion": 1,
            "verdict": "not_applicable",
            "head": HEAD,
            "branch": BRANCH,
            "rationale": "docs-only change",
        },
        HEAD,
    )
    assert result["ok"] is True

    stale = status.ready_not_applicable(
        {"schemaVersion": 1, "verdict": "not_applicable", "head": "old", "rationale": "docs-only"},
        HEAD,
    )
    assert stale["ok"] is False
    assert "stale head" in stale["reason"]


def test_missing_malformed_wrong_schema_or_park_status_parks(tmp_path):
    missing = status.assert_current(str(tmp_path / "missing.json"), HEAD)
    assert missing["ok"] is False and missing["verdict"] == "park"

    malformed = tmp_path / "bad.json"
    malformed.write_text("{bad")
    assert status.assert_current(str(malformed), HEAD)["verdict"] == "park"

    wrong_schema = tmp_path / "wrong.json"
    wrong_schema.write_text(json.dumps({"schemaVersion": 2}))
    assert status.assert_current(str(wrong_schema), HEAD)["verdict"] == "park"

    parked = tmp_path / "park.json"
    parked.write_text(json.dumps({"schemaVersion": 1, "verdict": "park", "head": HEAD}))
    assert status.assert_current(str(parked), HEAD)["verdict"] == "park"


def test_write_read_and_cli_use_control_plane_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    data = _applicable()
    status_path = status.status_path(str(tmp_path), "issue-90")
    status.write(status_path, data)
    assert status.read(status_path)["head"] == HEAD
    assert status_path == str(tmp_path / "store" / "checkouts" / control_plane.checkout_key(str(tmp_path)) / "issues" / "issue-90" / "test-pilot-status.json")

    source = tmp_path / "status-source.json"
    source.write_text(json.dumps(data))
    write = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "plugins/superheroes/lib/test_pilot_status_cli.py"),
            "write",
            "--work-item",
            "issue-90",
            "--status-json",
            str(source),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(write.stdout)["ok"] is True

    asserted = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "plugins/superheroes/lib/test_pilot_status_cli.py"),
            "assert-current",
            "--work-item",
            "issue-90",
            "--head",
            HEAD,
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(asserted.stdout)["ok"] is True
