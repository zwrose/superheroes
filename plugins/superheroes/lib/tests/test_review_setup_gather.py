"""Tests for review_setup_gather.py — the fold-2 (#141) pre-round setup gather (#211 decision shape).

The gather folds the review loop's entry seam calls (run-dir mkdir, deferred-set seed, the resume
DECISION, the round-1 plan, coverage_decisions load) into ONE Python-side leaf. Under #211 it rides
DECISIONS, not records: `resume` must be byte-parity with review_loop_plan entry-bootstrap and `plan`
with plan-round, `coverage` with coverage_decisions load, so the shell can drop them straight into its
resume/plan/coverage/deferred state. It must also create the run dir (the mkdir fold) and stay
all-Python-side (no courier prose in any integrity field), with NO finding ever riding the answer."""

import json
import os
import subprocess
import sys

LIB = os.path.join(os.path.dirname(__file__), "..")


def gather(args):
    proc = subprocess.run(
        [sys.executable, os.path.join(LIB, "review_setup_gather.py"), *args],
        capture_output=True, text=True)
    assert proc.returncode == 0, f"gather exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def resume_decider(records_path, dimensions, extras_path):
    proc = subprocess.run(
        [sys.executable, os.path.join(LIB, "review_loop_plan.py"), "entry-bootstrap",
         "--path", records_path, "--dimensions", json.dumps(dimensions),
         "--extras-path", extras_path],
        capture_output=True, text=True)
    return json.loads(proc.stdout)


def load_coverage(path, mode):
    proc = subprocess.run(
        [sys.executable, os.path.join(LIB, "coverage_decisions.py"), "load",
         "--path", path, "--mode", mode],
        capture_output=True, text=True)
    return json.loads(proc.stdout)


def _args(run_dir, dimensions=("code",), coverage_mode="code", coverage_path=None):
    return [
        "gather",
        "--run-dir", str(run_dir),
        "--records-path", os.path.join(str(run_dir), "round-records.json"),
        "--dimensions", json.dumps(list(dimensions)),
        "--extras-path", os.path.join(str(run_dir), "last-extras.json"),
        "--deferred-path", os.path.join(str(run_dir), "deferred-set.json"),
        "--coverage-path", coverage_path or os.path.join(str(run_dir), "review-coverage-decisions.json"),
        "--coverage-mode", coverage_mode,
    ]


def test_gather_creates_the_run_dir(tmp_path):
    run_dir = tmp_path / "run"  # does not exist yet
    assert not run_dir.exists()
    out = gather(_args(run_dir))
    assert out["ok"] is True
    assert run_dir.is_dir(), "the gather folds the run-dir mkdir"


def test_fresh_run_returns_empty_bounded_state(tmp_path):
    run_dir = tmp_path / "run"
    out = gather(_args(run_dir))
    assert out["resume"]["ok"] is True
    assert out["resume"]["round"] == 1
    assert out["resume"]["extras"] is None
    assert "records" not in out and "records" not in out["resume"], "#211: no records ride the gather"
    assert out["plan"]["ok"] is True and out["plan"]["roundKind"] == "baseline"
    assert out["plan"]["dimensions"]["code"]["action"] == "run"
    assert out["deferredSet"] == {}
    assert out["coverage"]["ok"] is True
    assert out["coverage"]["decisions"] == []


def test_gather_is_byte_parity_with_separate_helpers(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # a realistic prior round with evidence bodies (must come back as bounded skeletons)
    records = [{
        "schemaVersion": 2, "round": 1, "kind": "baseline", "confirmationPending": False,
        "changedSubjects": ["Code"], "coverageDecisions": [], "tokenUsage": {},
        "findings": [{"file": "a.py", "line": 3, "title": "bug", "severity": "Critical",
                      "taxonomy": "bug", "evidence": "y" * 500}],
        "dimensions": {"code": {"dimension": "code", "status": "run", "confidence": "high",
                                "round": 1, "findings": [], "subjects": ["Code"]}},
    }]
    (run_dir / "round-records.json").write_text(json.dumps(records), encoding="utf-8")
    (run_dir / "last-extras.json").write_text(json.dumps({"changedSubjects": ["Code"]}), encoding="utf-8")
    (run_dir / "deferred-set.json").write_text(json.dumps({"a.py::bug": "Critical"}), encoding="utf-8")
    (run_dir / "review-coverage-decisions.json").write_text(
        json.dumps([{"id": "RCD-1", "classKey": "Code::bug::x", "sourceRound": 1}]), encoding="utf-8")

    out = gather(_args(run_dir))
    resume = resume_decider(str(run_dir / "round-records.json"), ["code"], str(run_dir / "last-extras.json"))
    cov = load_coverage(str(run_dir / "review-coverage-decisions.json"), "code")

    assert out["resume"] == resume, "resume field must be byte-parity with review_loop_plan entry-bootstrap"
    assert out["coverage"] == cov, "coverage field must be byte-parity with coverage_decisions load"
    assert out["deferredSet"] == {"a.py::bug": "Critical"}, "the deferred-set seed rides the gather"
    assert out["resume"]["round"] == 2, "the resume DECISION reports the next round"
    # #211: NO finding — blocking or not — and no records ride the gather answer.
    assert "y" * 500 not in json.dumps(out), "evidence bodies must not ride the gather stdout"
    assert "bug" not in json.dumps(out["resume"]), "no finding rides the resume answer"
    assert "records" not in out["resume"], "the resume answer ships a decision, not records"


def test_doc_mode_coverage_parses_from_the_doc(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    doc = tmp_path / "plan.md"
    doc.write_text("# Plan\n\n## Review coverage decisions\n\n- RCD-1-test — principle — "
                   "`Code::x::y` (round 2): Cover every FR.\n", encoding="utf-8")
    out = gather(_args(run_dir, coverage_mode="doc", coverage_path=str(doc)))
    cov = load_coverage(str(doc), "doc")
    assert out["coverage"] == cov
    assert out["coverage"]["ok"] is True
