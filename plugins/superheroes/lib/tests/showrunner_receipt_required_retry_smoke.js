// plugins/superheroes/lib/tests/showrunner_receipt_required_retry_smoke.js
// #418: a reviewer leaf that returns the schema-minimal {findings:[],confidence:"high"} (no
// verificationReceipt) satisfied FINDINGS_SCHEMA and burned the whole retry budget before parking
// receipt-missing. The fix promotes verificationReceipt into the SCHEMA's `required` list on the
// receipt-missing RETRY ONLY (a legal top-level `required`, not a combinator), so the StructuredOutput
// tool rejects the empty shell and re-prompts the model in-turn instead of accepting it and spending a
// dispatch. Applied only to the receipt-missing retry and only on the native reviewer path; the low
// escape hatch (and permission-denied, which must NOT demand a receipt) stay untouched (#183).
// Run: node plugins/superheroes/lib/tests/showrunner_receipt_required_retry_smoke.js
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
function fresh() { return fs.mkdtempSync(path.join(os.tmpdir(), 'receipt-req-')) }
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }
function requiresReceipt(schema) {
  return !!(schema && Array.isArray(schema.required) && schema.required.includes('verificationReceipt'))
}

// ---------------------------------------------------------------------------
// Unit: the exported schema variant is a proper SUPERSET of FINDINGS_SCHEMA — same property set,
// with verificationReceipt promoted into `required`. Never a top-level combinator (guard-safe).
// ---------------------------------------------------------------------------
function unitSchemaVariant() {
  const base = sr.FINDINGS_SCHEMA
  const req = sr.FINDINGS_SCHEMA_RECEIPT_REQUIRED
  assert.ok(base && req, 'both schema literals are exported')
  assert.ok(!requiresReceipt(base), 'the general schema does NOT require verificationReceipt (a low answer omits it)')
  assert.ok(requiresReceipt(req), 'the receipt-required variant lists verificationReceipt in required')
  assert.deepStrictEqual(Object.keys(req.properties).sort(), Object.keys(base.properties).sort(),
    'the variant shares the same properties as the base (a pure superset, no drift)')
  for (const k of ['allOf', 'oneOf', 'anyOf']) {
    assert.ok(!Object.prototype.hasOwnProperty.call(req, k), `no top-level ${k} combinator on the variant`)
  }
  // The variant selector picks the tighter schema ONLY for receipt-missing.
  assert.strictEqual(sr.reviewerSchemaFor(undefined), base, 'no retryReason -> general schema')
  assert.strictEqual(sr.reviewerSchemaFor('receipt-missing'), req, 'receipt-missing -> receipt-required schema')
  assert.strictEqual(sr.reviewerSchemaFor('permission-denied'), base, 'permission-denied -> general schema (never demand a receipt for a denied probe)')
  assert.strictEqual(sr.reviewerSchemaFor('receipt-stale'), base, 'receipt-stale -> general schema (a receipt is already present)')
  assert.strictEqual(sr.reviewerSchemaFor('malformed'), base, 'malformed -> general schema')
}

// ---------------------------------------------------------------------------
// Unit: docReviewerAgent dispatches the receipt-required schema on the receipt-missing retry only.
// ---------------------------------------------------------------------------
async function captureDocSchema(retryReason) {
  let captured = null
  global.agent = async (prompt, opts) => {
    captured = { schema: opts && opts.schema, prompt }
    return { findings: [], confidence: 'low' }
  }
  const opts = Object.assign({ coverageDecisions: [] }, retryReason ? { retryReason } : {})
  await sr.docReviewerAgent('architecture-reviewer',
    { docType: 'plan', docPath: '/tmp/plan.md', receiptArtifact: 'run:round-1' },
    'review-base', '/tmp/rd', 1, opts)
  return captured
}
async function unitDocReviewerSchema() {
  const initial = await captureDocSchema(null)
  assert.ok(!requiresReceipt(initial.schema), 'doc initial dispatch uses the general schema')
  const retry = await captureDocSchema('receipt-missing')
  assert.ok(requiresReceipt(retry.schema), 'doc receipt-missing retry dispatches the receipt-required schema')
  assert.ok(/verificationReceipt/.test(retry.prompt), 'the receipt-missing retry prompt still carries the corrective instruction')
  const denied = await captureDocSchema('permission-denied')
  assert.ok(!requiresReceipt(denied.schema), 'doc permission-denied retry does NOT demand a receipt')
}

// ---------------------------------------------------------------------------
// Unit: the review-code reviewerAgent (native path) mirrors the doc leg.
// ---------------------------------------------------------------------------
async function captureCodeSchema(retryReason) {
  let captured = null
  global.agent = async (prompt, opts) => {
    captured = { schema: opts && opts.schema, prompt }
    return { findings: [], confidence: 'low' }
  }
  const leaves = sr.reviewCodeLeaves({ reviewer: 'sonnet', reviewerDeep: 'opus' }, {})
  const opts = Object.assign({ tier: 'reviewer-deep', coverageDecisions: [] }, retryReason ? { retryReason } : {})
  await leaves.reviewerAgent('code-reviewer',
    { workItem: 'wi', receiptArtifact: 'run:round-1' }, 'review-code', '/tmp/rd', 1, opts)
  return captured
}
async function unitCodeReviewerSchema() {
  const initial = await captureCodeSchema(null)
  assert.ok(!requiresReceipt(initial.schema), 'code initial dispatch uses the general schema')
  const retry = await captureCodeSchema('receipt-missing')
  assert.ok(requiresReceipt(retry.schema), 'code receipt-missing retry dispatches the receipt-required schema')
}

// ---------------------------------------------------------------------------
// Integration: drive the REAL reviewCodePhase. Model the runtime honestly — a reviewer returns the
// schema-minimal shell whenever the tool does NOT force a receipt, and supplies a full receipt once the
// tool schema requires it. On the pre-#418 shape the retry schema never required the receipt, so both
// attempts returned the shell and the seat parked. With the fix the retry forces the receipt, the seat
// complies, and the panel certifies — the tail no longer burns the budget.
// ---------------------------------------------------------------------------
const STUB_WT = '/tmp/receipt-req-stub-wt'
const stubResolveTarget = async () => ({ worktree: STUB_WT, expectedHead: null })

function fullReceipt(runDir, round) {
  return {
    findings: [], confidence: 'high',
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
}

function installAgent(state) {
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
      if (reviewer === state.target) {
        state.dispatches += 1
        state.schemas.push(opts && opts.schema)
        // The target seat only produces a real receipt when the SCHEMA forces it (models the tool
        // rejecting the empty shell and re-prompting the model in-turn). state.stubborn keeps it a
        // shell even under the forced schema — the fabrication-proof control.
        if (!state.stubborn && requiresReceipt(opts && opts.schema)) return fullReceipt(rd, round)
        return { findings: [], confidence: 'high' }   // schema-minimal shell (no receipt)
      }
      return fullReceipt(rd, round)
    }
    return fullReceipt('run', 1)
  }
}

async function integrationTailResolved() {
  // Leg A (the fix at work): the target seat complies once the retry forces the receipt -> certifies.
  const stA = { target: 'test-reviewer', dispatches: 0, schemas: [], stubborn: false }
  installAgent(stA)
  const a = await sr.reviewCodePhase('wi-fixed', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(a.gate, 'passed', 'a schema-minimal seat that complies on the receipt-forced retry now certifies')
  assert.ok(stA.schemas.some(requiresReceipt), 'the receipt-missing retry dispatched the receipt-required schema')
  assert.ok(!requiresReceipt(stA.schemas[0]), 'the initial dispatch used the general schema')
  // The economy claim (#418): the fix re-prompts IN-TURN, it does not add retry cycles. The seat is
  // dispatched exactly twice — one initial shell + one receipt-forced retry that certifies — and the
  // panel converges in round 1 (no extra dispatch burned).
  assert.strictEqual(stA.dispatches, 2, 'target seat dispatched exactly twice: initial shell + one receipt-forced retry')

  // Leg B (meaning preserved): a seat that returns an empty shell even under the forced schema still
  // parks honestly — the fix never invents a receipt or passes an unverified seat (#183).
  const stB = { target: 'test-reviewer', dispatches: 0, schemas: [], stubborn: true }
  installAgent(stB)
  const b = await sr.reviewCodePhase('wi-stubborn', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(b.gate, 'changes-requested', 'a persistently receipt-less seat still cannot certify -> park')
  // Self-contained: the forced schema WAS applied on the receipt-missing retry and the seat STILL parked
  // — the fix never fabricates a receipt to paper over a seat that skipped it (#183).
  assert.ok(stB.schemas.some(requiresReceipt), 'the receipt-required schema was dispatched, yet the receipt-less seat still parked (no fabrication)')
}

async function main() {
  unitSchemaVariant()
  await unitDocReviewerSchema()
  await unitCodeReviewerSchema()
  await integrationTailResolved()
  console.log('ok: receipt-required schema on the receipt-missing retry -> schema-minimal shell stops burning the budget (#418)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
