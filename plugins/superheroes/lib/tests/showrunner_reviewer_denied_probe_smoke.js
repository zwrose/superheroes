// plugins/superheroes/lib/tests/showrunner_reviewer_denied_probe_smoke.js
// Task 10 (FR-2): a reviewer leaf whose verification probe was DENIED (a permission_denied recorded
// for that reviewer's probe) is read by the review loop as confidence:'low' and routed to the existing
// deep-retry / degraded-dimension path — never silently passed. A probe whose deep retry is ALSO denied
// is reported as a degraded dimension and NOT retried again (the loop's existing single-retry ceiling).
// The denial is written to the journal via the Python journal.append seam, tagged step review:<reviewer>.
// Run: node plugins/superheroes/lib/tests/showrunner_reviewer_denied_probe_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
function fresh() { return fs.mkdtempSync(path.join(os.tmpdir(), 'rdenied-')) }
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

// ---------------------------------------------------------------------------
// Unit: ensureReviewerShape maps a denied probe to low confidence + records it.
// ---------------------------------------------------------------------------
function unitEnsureShape() {
  const recorded = []
  const orig = sr._denialRecorder
  sr._denialRecorder = (reviewer, eventsPath) => { recorded.push({ reviewer, eventsPath }) }
  try {
    // A leaf that ran but had its probe denied: it may even return a high-confidence-looking body,
    // but a denied probe means the dimension was NOT verified -> force low + one deep retry.
    const out = sr.ensureReviewerShape(
      { findings: [], confidence: 'high', permissionDenied: true },
      { reviewer: 'security-reviewer', eventsPath: '/tmp/events.jsonl' })
    assert.strictEqual(out.confidence, 'low', 'a denied probe forces confidence:low')
    assert.ok(out.receiptMissing, 'a denied probe marks receiptMissing so the shell deep-retries once')
    assert.ok(out.permissionDenied, 'the denial flag is preserved on the shaped result')
    assert.strictEqual(recorded.length, 1, 'the denial is recorded exactly once')
    assert.strictEqual(recorded[0].reviewer, 'security-reviewer', 'the recorded step names the reviewer')

    // A clean (non-denied) probe is untouched by the denial branch.
    recorded.length = 0
    const clean = sr.ensureReviewerShape(
      { findings: [], confidence: 'high',
        verificationReceipt: { artifact: 'a', chain: [
          { step: 'citation', evidence: 'e' }, { step: 'reachability', evidence: 'e' },
          { step: 'missing-check', evidence: 'e' }, { step: 'tooling', evidence: 'e' }],
          coverageDecisionIds: [] } },
      { reviewer: 'code-reviewer', eventsPath: '/tmp/events.jsonl' })
    assert.strictEqual(clean.confidence, 'high', 'a non-denied receipt-bearing result stays high')
    assert.strictEqual(recorded.length, 0, 'no denial recorded for a clean probe')
  } finally { sr._denialRecorder = orig }
}

// ---------------------------------------------------------------------------
// Integration: drive the REAL reviewCodePhase deep-retry path. The security-reviewer's probe is
// denied on EVERY attempt; assert the dimension degrades (loop cannot certify -> park), the reviewer
// leaf is invoked the single-retry ceiling number of times (deep + one retry, no extra cycle), and
// the denial is recorded via the journal seam.
// ---------------------------------------------------------------------------
function reviewerPayload(runDir, round, denied) {
  const body = {
    findings: [],
    confidence: 'high',
    verificationReceipt: {
      artifact: `${runDir}:round-${round}`,
      chain: [
        { step: 'citation', evidence: 'reviewed citations' },
        { step: 'reachability', evidence: 'validated call path' },
        { step: 'missing-check', evidence: 'checked missing FRs' },
        { step: 'tooling', evidence: 'smoke passed' },
      ],
      coverageDecisionIds: [],
    },
    usage: { input: 0, output: 0, total: 1 },
  }
  if (denied) body.permissionDenied = true
  return body
}

const STUB_WT = '/tmp/review-denied-stub-wt'
const stubResolveTarget = async () => ({ worktree: STUB_WT, expectedHead: null })

function installAgent(counter, denySecurity) {
  global.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'resume') return '1'
      if (label === 'run verify') return { command: 'run-tests', returncode: 0, timedOut: false }
      if (label.startsWith('synthesis')) return { verdicts: [], usage: { total: 1 } }
      if (opts && opts.courier && prompt.includes('record_deferred.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, extras: { fixes: [] } }) }]
      }
      if (label === 'readout') return '## Review loop — done'
      if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
      if (label === 'stamp review coverage') return jsonOut({ ok: true })
      if (opts && opts.courier && prompt.includes('review_code_config.py')) {
        return JSON.stringify({ verifyCommand: 'none', tiers: { reviewer: 'sonnet', reviewerDeep: 'opus', synthesis: 'opus', fixer: 'sonnet' } })
      }
      if (opts && opts.courier && prompt.includes('git rev-parse')) return 'stub-head\n'
      if (label === 'lib') return { ok: true }
      if (opts && opts.courier) return []
      const m = label.match(/^(architecture|code|security|test|premortem)-reviewer:r(\d+)/)
      if (m) {
        const reviewer = `${m[1]}-reviewer`
        const round = Number(m[2]) || 1
        const ctxStr = (prompt.match(/Prompt context: (\{.*\})/) || [])[1]
        let ctx = {}; try { ctx = JSON.parse(ctxStr || '{}') } catch (_) {}
        const rd = ctx.receiptArtifact ? ctx.receiptArtifact.replace(/:round-\d+$/, '') : 'run'
        // The security-reviewer's probe is denied on EVERY dispatch (only when denySecurity).
        if (reviewer === 'security-reviewer') {
          counter.security += 1
          if (counter.securityPrompts) counter.securityPrompts.push(prompt)
          return reviewerPayload(rd, round, denySecurity)
        }
        return reviewerPayload(rd, round, false)
      }
      return reviewerPayload('run', 1, false)
  }
}

async function integrationDeniedProbe() {
  const orig = sr._denialRecorder

  // Control leg: the IDENTICAL fixture with NO denial converges clean -> passed. This proves the park
  // in the denial leg is caused by the denied probe, not by the fixture itself.
  const ctrlCounter = { security: 0 }
  installAgent(ctrlCounter, false)
  const ctrl = await sr.reviewCodePhase('wi-clean', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(ctrl.gate, 'passed', 'control (no denial): the same fixture reaches passed')

  // Denial leg: the security-reviewer's probe is denied on every dispatch.
  const recorded = []
  sr._denialRecorder = (reviewer) => { recorded.push(reviewer) }
  const counter = { security: 0, securityPrompts: [] }
  installAgent(counter, true)
  try {
    const r = await sr.reviewCodePhase('wi-denied', { runDir: fresh(), resolveTarget: stubResolveTarget })
    // A degraded (never-verified) dimension cannot certify a clean pass -> the loop parks.
    assert.strictEqual(r.gate, 'changes-requested', 'a denied/degraded probe cannot certify -> park')
    // FR-1/FR-2: the deep-retry of a permission-DENIED probe must be told the denied probe is FINAL —
    // do not re-attempt the same denied probe (verify another way / return low), NOT the misleading
    // "supply a receipt" correction. The retry (2nd) dispatch is the one carrying the correction.
    assert.ok(counter.securityPrompts.length >= 2, 'the security probe was dispatched at least twice (base + deep retry)')
    assert.ok(/do NOT re-attempt the same denied probe/.test(counter.securityPrompts[1]),
      'the denied-probe deep-retry prompt tells the leaf the denied probe is FINAL — do not re-attempt it')
    // Single-retry ceiling: round 1 (baseline) schedules every dimension at tier 'reviewer-deep', so the
    // deep-tier arm fires — base (1) + exactly ONE deep retry (1) = 2 dispatches. The retry is ALSO
    // denied (still receiptMissing/low), so the dimension is reported degraded and NOT re-cycled: the
    // "deep retry also denied -> report degraded, don't re-cycle" bound reuses this existing ceiling,
    // adding no new counter.
    assert.strictEqual(counter.security, 2, 'denied probe: base + one deep-retry (single-retry ceiling), then no re-cycle')
    assert.ok(recorded.filter((x) => x === 'security-reviewer').length >= 1,
      'the denial is recorded to the journal for the security-reviewer')
  } finally { sr._denialRecorder = orig }
}

async function main() {
  unitEnsureShape()
  await integrationDeniedProbe()
  console.log('ok: reviewer denied probe -> confidence:low + degraded-dimension (single-retry ceiling) + journal record')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
