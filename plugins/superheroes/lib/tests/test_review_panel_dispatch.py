"""Regression tests for review_panel_shell.dispatchReviewer (#505)."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

DISPATCH_STALE_RECEIPT_SCRIPT = r"""
const { dispatchReviewer, _retryDiscloseSeam } = require('./plugins/superheroes/lib/review_panel_shell.js')

_retryDiscloseSeam.record = () => {}
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

global.reviewerAgent = async () => ({
  findings: [{ title: 't', severity: 'Minor', dimension: 'code-reviewer' }],
  confidence: 'high',
  verificationReceipt: staleReceipt,
})

async function main() {
  const roundFindings = {}
  await dispatchReviewer('code-reviewer', {}, {}, '/tmp/run', 1, roundFindings, {
    tier: 'reviewer',
    receiptArtifact: 'run-1:round-1',
    coverageDecisions: [{ id: 'RCD-1' }],
  })
  process.stdout.write(JSON.stringify(roundFindings))
}

main().catch((e) => { console.error(e); process.exit(1) })
"""

DISPATCH_GRADE_RETIREMENT_SCRIPT = r"""
const { dispatchReviewer, _retryDiscloseSeam } = require('./plugins/superheroes/lib/review_panel_shell.js')

_retryDiscloseSeam.record = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const freshReceipt = {
  artifact: 'run-1:round-1',
  chain: [
    { step: 'citation', evidence: 'x' },
    { step: 'reachability', evidence: 'x' },
    { step: 'missing-check', evidence: 'x' },
    { step: 'tooling', evidence: 'x' },
  ],
  coverageDecisionIds: ['RCD-1'],
}

let reviewerCallCount = 0
global.reviewerAgent = async () => {
  reviewerCallCount += 1
  return {
    findings: [{ title: 't', severity: 'Minor', dimension: 'code-reviewer' }],
    confidence: 'low',
    verificationReceipt: freshReceipt,
  }
}

async function main() {
  const roundFindings = {}
  await dispatchReviewer('code-reviewer', {}, {}, '/tmp/run', 1, roundFindings, {
    tier: 'reviewer',
    receiptArtifact: 'run-1:round-1',
    coverageDecisions: [{ id: 'RCD-1' }],
  })
  process.stdout.write(JSON.stringify({ roundFindings, reviewerCallCount }))
}

main().catch((e) => { console.error(e); process.exit(1) })
"""


def test_dispatch_stale_receipt_after_retry_records_missing():
    """#505: a persistently stale receipt must not record as a clean run after bounded retry."""
    result = subprocess.run(
        ["node", "-e", DISPATCH_STALE_RECEIPT_SCRIPT],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    findings = json.loads(result.stdout)
    rec = findings["code-reviewer"]
    assert rec["status"] == "missing"
    assert rec.get("receiptStale") is True
    assert rec["confidence"] == "low"
    assert rec["escalated"] is True


def test_dispatch_valid_cheap_non_empty_findings_not_graded_or_escalated():
    """#505: a valid cheap-tier result with findings stands as run/high, no re-dispatch."""
    result = subprocess.run(
        ["node", "-e", DISPATCH_GRADE_RETIREMENT_SCRIPT],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    rec = payload["roundFindings"]["code-reviewer"]
    assert rec["status"] == "run"
    assert rec["confidence"] == "high"
    assert rec["escalated"] is False
    assert len(rec["findings"]) > 0
    assert payload["reviewerCallCount"] == 1
