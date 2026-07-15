"""Task 9 (#397): gather threads doc_mode into round 1's folded plan-round answer.

`review_setup_gather.gather` folds round 1's `plan-round` decision (the round that never calls
`planRoundDecider` directly — the shell consumes the folded `plan` instead). In doc mode ANY open
blocking finding (Critical OR Important) must re-arm the confirmation panel — the same rule Task 8
pinned on the standalone `plan_round_decider`. Without `--doc-mode` threaded through gather, round 1
of every doc panel would silently schedule under code-mode economics while every later round ran
doc mode. This pins gather's answer to the standalone decider's doc-mode answer.
"""
import json
import os
import subprocess
import sys

import review_loop_plan as rlp
import review_memory

LIB = os.path.join(os.path.dirname(__file__), "..")

FULL_ROSTER = ["architecture-reviewer", "code-reviewer", "security-reviewer",
               "test-reviewer", "premortem-reviewer"]


def _dim(status="run", confidence="high", tier="reviewer-deep", findings=None):
    return {"status": status, "confidence": confidence, "tier": tier,
            "dimension": None, "findings": findings or []}


def _skeleton_round(round_no, dim_results, kind="baseline", changed_subjects=None,
                    confirmation_pending=False):
    """One durable skeleton record, exactly as persistRoundRecord would write it."""
    results = {name: dict(spec, dimension=name) for name, spec in dim_results.items()}
    rec = review_memory.record_from_dimension_results(
        round_no, kind, results, changed_subjects, [], {}, confirmation_pending)
    return review_memory.summarize_record(rec)


def _gather(run_dir, doc_mode):
    args = [sys.executable, os.path.join(LIB, "review_setup_gather.py"), "gather",
            "--run-dir", str(run_dir),
            "--records-path", os.path.join(str(run_dir), "round-records.json"),
            "--dimensions", json.dumps(FULL_ROSTER),
            "--extras-path", os.path.join(str(run_dir), "last-extras.json"),
            "--deferred-path", os.path.join(str(run_dir), "deferred-set.json"),
            "--coverage-path", os.path.join(str(run_dir), "review-coverage-decisions.json"),
            "--coverage-mode", "code"]
    if doc_mode:
        args.append("--doc-mode")
    proc = subprocess.run(args, capture_output=True, text=True)
    assert proc.returncode == 0, f"gather exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def _fixture(tmp_path):
    """One qualifying confirmation panel (round 1) then an intermediate round 2 that surfaces a
    plain, non-Critical, non-cross-cutting open Important. resume round = 3, so gather folds the
    round-3 plan-round answer — exactly Task 8's standalone plan-round doc-mode fixture."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    important = [{"title": "spec gap", "file": "a.js", "severity": "Important", "dimension": "Code"}]
    recs = [
        _skeleton_round(1, {n: _dim() for n in FULL_ROSTER}, kind="confirmation",
                        confirmation_pending=True, changed_subjects=["Code"]),
        _skeleton_round(2, dict({n: _dim() for n in FULL_ROSTER},
                                **{"code-reviewer": _dim(findings=important)}),
                        kind="intermediate", changed_subjects=["Code"]),
    ]
    (run_dir / "round-records.json").write_text(json.dumps(recs), encoding="utf-8")
    (run_dir / "last-extras.json").write_text(
        json.dumps({"changedSubjects": ["Code"]}), encoding="utf-8")
    return run_dir


def test_gather_doc_mode_schedules_confirmation_for_open_important(tmp_path):
    run_dir = _fixture(tmp_path)
    # doc mode: any open blocker re-arms the confirmation panel at round 1's fold
    doc = _gather(run_dir, doc_mode=True)
    assert doc["plan"]["enterConfirmation"] is True
    # code mode (default): a plain Important does NOT re-arm
    code = _gather(run_dir, doc_mode=False)
    assert code["plan"]["enterConfirmation"] is False
    # gather's doc-mode answer matches the standalone plan_round_decider(doc_mode=True) from Task 8
    standalone = rlp.plan_round_decider(
        str(run_dir / "round-records.json"), 3, FULL_ROSTER, ["Code"],
        just_marked=False, doc_mode=True)
    assert standalone["enterConfirmation"] is True
    assert doc["plan"]["enterConfirmation"] == standalone["enterConfirmation"]
