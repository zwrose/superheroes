"""Cross-twin parity guard for the reviewer re-dispatch budget (#525).

The reviewer re-dispatch budget is ONE, identically, across the JS shell
(review_panel_shell.dispatchReviewer), the code-leg driver (round_driver — #507, which absorbed
the retired code_loop_plan), and the spec-leg scheduler (spec_loop_plan). Documented intent:
#350 ("re-dispatch … once … never asks twice"). The same invariant is stated in
skills/review-code/SKILL.md, skills/review-spec/SKILL.md, and
skills/review-code/reference/round-scheduler.md ("re-dispatch … once … never asks twice").
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

EXPECTED_REDISPATCHES = 1

ROOT = Path(__file__).resolve().parents[4]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load(os.path.join(_HERE, "..", "round_driver.py"), "round_driver")
SLP = _load(os.path.join(_HERE, "..", "spec_loop_plan.py"), "spec_loop_plan")
LPC = _load(os.path.join(_HERE, "..", "loop_plan_common.py"), "loop_plan_common")


def test_expected_redispatches_matches_budget_home():
    # The pin (EXPECTED_REDISPATCHES) and the single-home constant must not drift: the whole
    # point of REDISPATCH_BUDGET is that ONE value drives every leg.
    assert EXPECTED_REDISPATCHES == LPC.REDISPATCH_BUDGET

# --- round_driver code-leg fixtures (#507: code_loop_plan retired into round_driver) ----------
# The code-leg re-dispatch budget now lives in round_driver.run_loop's reviewer seam loop, which
# reads loop_plan_common.REDISPATCH_BUDGET (the single home). A persistently receipt-missing seat
# is re-dispatched exactly REDISPATCH_BUDGET times, then recorded terminal `missing`.

_RD_DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1 +1,2 @@\n-old\n+new\n+more\n")

SPEC_V1 = "# Spec\n\n## Requirements\n\nFR-1 the system shall foo.\n\n## Coverage\n\nEmpty state: N-A.\n"
SPEC_V2 = "# Spec\n\n## Requirements\n\nFR-1 the system shall foo precisely.\n\n## Coverage\n\nEmpty state: N-A.\n"

SLP_DIMS = ["architecture-reviewer", "code-reviewer", "security-reviewer",
            "test-reviewer", "premortem-reviewer", "grounding-reviewer"]
SLP_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
              "security-reviewer": "security", "test-reviewer": "test",
              "premortem-reviewer": "premortem", "grounding-reviewer": "grounding"}


def _rd_dispatch_count_for_missing_seat(missing_dim, missing_round):
    """Drive round_driver.run_loop with `missing_dim` returning a persistently receipt-missing
    answer at round `missing_round`. Returns (dispatch_count, recorded_seat_status)."""
    calls = {"n": 0}
    seat_status = {"value": None}

    def reviewer(dim, tier, rnd, ctx):
        if dim == missing_dim and rnd == missing_round:
            calls["n"] += 1
            return {"findings": [], "receiptMissing": True}
        return []

    orig_fold = RD._fold_panel

    def spy_fold(state, config, artifact):
        orig_fold(state, config, artifact)
        rec = state["rounds"].get(str(state["round"]), {})
        if rec.get("seatStatus"):
            seat_status["value"] = rec["seatStatus"].get(missing_dim)

    RD._fold_panel = spy_fold
    try:
        RD.run_loop({
            "reviewer": reviewer,
            "verifier": lambda cl, rnd: [{"id": i, "verdict": "PLAUSIBLE"}
                                         for c in (cl or []) for i in c.get("ids", [])],
            "synthesis": lambda f, rnd: None,
            "auditor": lambda t, rnd: [{"id": x["id"], "ruling": "discharged", "reason": "r",
                                        "evidence": "e"} for x in (t or [])],
            "fix_step": lambda b, rnd, p: {"fixes": [], "headDiff": _RD_DIFF, "changedSubjects": []},
            "verify_runner": lambda c, rnd: "pass",
            "io": {},
        }, {"leg": "code", "vendors": ["claude", "codex"], "diff": _RD_DIFF, "fixerVendor": "claude"})
    finally:
        RD._fold_panel = orig_fold
    return calls["n"], seat_status["value"]


# --- spec_loop_plan fixtures (mirrors test_spec_loop_plan.py) -------------------

def _slp_session(tmp_path, spec_text=SPEC_V1):
    d = tmp_path / "sess"
    d.mkdir()
    (d / "spec.md").write_text(spec_text, encoding="utf-8")
    return str(d)


def _slp_write_findings(session_dir, dim, findings):
    path = os.path.join(session_dir, "findings-%s.json" % SLP_SUFFIX[dim])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(findings, fh)
    return path


def _slp_blocker(dim_label):
    return {"id": "x-001", "severity": "Important", "dimension": dim_label,
            "title": "vague requirement", "file": "spec.md", "line": 5,
            "body": "b", "confidence": "High"}


def _slp_run(capsys, *args):
    rc = SLP.main(list(args))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    return out


def _slp_plan(capsys, session_dir, rnd):
    return _slp_run(capsys, "plan", "--session-dir", session_dir, "--round", str(rnd))


def _slp_record(capsys, session_dir, rnd):
    return _slp_run(capsys, "record", "--session-dir", session_dir, "--round", str(rnd))


def _slp_decide(capsys, session_dir, rnd, skipped=0, max_rounds=7, compiled=None):
    compiled = compiled or os.path.join(session_dir, "compiled.json")
    return _slp_run(capsys, "decide", "--session-dir", session_dir, "--round", str(rnd),
                    "--max-rounds", str(max_rounds), "--compiled", compiled,
                    "--skipped-blocking", str(skipped))


def _slp_round1(capsys, session_dir, findings_by_dim=None):
    plan = _slp_plan(capsys, session_dir, 1)
    findings_by_dim = findings_by_dim or {}
    for dim in SLP_DIMS:
        _slp_write_findings(session_dir, dim, findings_by_dim.get(dim, []))
    rec = _slp_record(capsys, session_dir, 1)
    return plan, rec


def _slp_write_compiled(session_dir, findings):
    path = os.path.join(session_dir, "compiled.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"summary": "s", "verdict": "v", "findings": findings}, fh)
    return path


def _slp_reach_round2_with_cheap_arch(tmp_path, capsys):
    session_dir = _slp_session(tmp_path)
    _slp_round1(capsys, session_dir, {"architecture-reviewer": [_slp_blocker("Architecture")]})
    _slp_write_compiled(session_dir, [_slp_blocker("Architecture")])
    (tmp_path / "sess" / "spec.md").write_text(SPEC_V2, encoding="utf-8")
    decided = _slp_decide(capsys, session_dir, 1)
    return session_dir, decided


def _slp_record_until_dry(capsys, session_dir, rnd, missing_dim):
    escalations = 0
    last_rec = None
    for _ in range(4):
        for dim in SLP_DIMS:
            if dim != missing_dim:
                _slp_write_findings(session_dir, dim, [])
        last_rec = _slp_record(capsys, session_dir, rnd)
        for esc in last_rec.get("escalate", []):
            if esc["dimension"] == missing_dim:
                escalations += 1
        if not last_rec.get("escalate"):
            break
    return escalations, last_rec


# --- JS harness (mirrors test_review_panel_dispatch.py) -----------------------

JS_RETRY_BUDGET_SCRIPT = r"""
const { dispatchReviewer, _retryDiscloseSeam } = require('./plugins/superheroes/lib/review_panel_shell.js')

const disclosures = []
_retryDiscloseSeam.record = (_path, event) => { disclosures.push(event) }
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const staleReceipt = {
  artifact: 'wrong-artifact',
  chain: [
    { step: 'citation', evidence: 'x' },
    { step: 'reachability', evidence: 'x' },
    { step: 'missing-check', evidence: 'x' },
    { step: 'tooling', evidence: 'x' },
  ],
  coverageDecisionIds: ['RCD-1'],
}

let calls = 0
global.reviewerAgent = async () => {
  calls += 1
  return {
    findings: [{ title: 't', severity: 'Minor', dimension: 'code-reviewer' }],
    confidence: 'high',
    verificationReceipt: staleReceipt,
  }
}

async function main() {
  const tier = process.argv[1] || 'reviewer'
  const roundFindings = {}
  await dispatchReviewer('code-reviewer', {}, {}, '/tmp/run', 1, roundFindings, {
    tier,
    receiptArtifact: 'run-1:round-1',
    coverageDecisions: [{ id: 'RCD-1' }],
  })
  process.stdout.write(JSON.stringify({
    calls,
    disclosures: disclosures.length,
    status: roundFindings['code-reviewer'].status,
    escalated: roundFindings['code-reviewer'].escalated,
  }))
}

main().catch((e) => { console.error(e); process.exit(1) })
"""


def _run_js_retry_budget(tier):
    result = subprocess.run(
        ["node", "-e", JS_RETRY_BUDGET_SCRIPT, tier],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


# --- JS parity cases ----------------------------------------------------------

def test_js_cheap_start_retry_budget():
    payload = _run_js_retry_budget("reviewer")
    assert payload["calls"] == 1 + EXPECTED_REDISPATCHES
    assert payload["disclosures"] == EXPECTED_REDISPATCHES
    assert payload["status"] == "missing"
    assert payload["escalated"] is True


def test_js_deep_start_retry_budget():
    payload = _run_js_retry_budget("reviewer-deep")
    assert payload["calls"] == 1 + EXPECTED_REDISPATCHES
    assert payload["status"] == "missing"
    assert payload["disclosures"] == EXPECTED_REDISPATCHES
    assert payload["escalated"] is False


# --- round_driver (code-leg) parity cases ---------------------------------------
# The code leg's re-dispatch bound now rides through round_driver, which reads
# loop_plan_common.REDISPATCH_BUDGET (asserted in test_expected_redispatches_matches_budget_home).
# A persistently receipt-missing seat is dispatched 1 + EXPECTED_REDISPATCHES times, then `missing`.

def test_round_driver_round1_missing_retry_budget():
    dispatches, status = _rd_dispatch_count_for_missing_seat("code-reviewer", 1)
    assert dispatches == 1 + EXPECTED_REDISPATCHES
    assert status == "missing"


def test_round_driver_budget_reads_single_home():
    # the code-leg budget is NOT a local literal — it reads the single home.
    assert RD.REDISPATCH_BUDGET == LPC.REDISPATCH_BUDGET


# --- spec_loop_plan parity cases ------------------------------------------------

def test_spec_loop_plan_deep_round1_missing_retry_budget(tmp_path, capsys):
    session_dir = _slp_session(tmp_path)
    _slp_plan(capsys, session_dir, 1)
    escalations, rec = _slp_record_until_dry(capsys, session_dir, 1, "architecture-reviewer")
    assert escalations == EXPECTED_REDISPATCHES
    assert rec["dimensions"]["architecture-reviewer"]["status"] == "missing"


def test_spec_loop_plan_cheap_round2_missing_retry_budget(tmp_path, capsys):
    session_dir, _ = _slp_reach_round2_with_cheap_arch(tmp_path, capsys)
    _slp_plan(capsys, session_dir, 2)
    escalations, rec = _slp_record_until_dry(capsys, session_dir, 2, "architecture-reviewer")
    assert escalations == EXPECTED_REDISPATCHES
    assert rec["dimensions"]["architecture-reviewer"]["status"] == "missing"
