const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const sr = require('../showrunner.js')

global.log = () => {}
global.parallel = async (fns) => { const out = []; for (const f of (fns || [])) out.push(await f()); return out }

// A genuinely clean/complete review needs a real verificationReceipt matching the round's
// receiptArtifact + coverageDecisionIds (else the receipt-fabrication fix downgrades it to
// confidence:low, which fails the round -- and, on the post-fix confirmation round, an
// artifact/coverage mismatch fails cannot-certify even with a receipt present).
function receiptFor(prompt) {
  let ctx = { receiptArtifact: 'stub', receiptCoverageDecisionIds: [] }
  const m = prompt.match(/Prompt context: (\{.*\})$/s)
  if (m) { try { ctx = JSON.parse(m[1]) } catch (_) {} }
  return {
    artifact: ctx.receiptArtifact || 'stub',
    chain: [
      { step: 'citation', evidence: 'reviewed citations' },
      { step: 'reachability', evidence: 'validated call path' },
      { step: 'missing-check', evidence: 'checked missing FRs' },
      { step: 'tooling', evidence: 'smoke passed' },
    ],
    coverageDecisionIds: ctx.receiptCoverageDecisionIds || [],
  }
}

;(async () => {
  const labels = []
  let reviewerCalls = 0
  let staleReceiptCalls = 0
  let reviewerSchema = null
  const reviewerPrompts = []
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'resolve review target') {
      // #118 entry fold: the ONE gather carries worktree + head + config + cwd head
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/tmp/wt', expectedHead: 'abc123', config: { verifyCommand: 'none', tiers: {} }, cwdHead: 'cwd000' }) }]
    }
    if (label === 'exec' && prompt.includes('review_code_config.py')) {
      throw new Error('config must ride the resolve review target gather, not its own leaf (#118 entry fold)')
    }
    if (label === 'exec' && prompt.includes('git -C') && prompt.includes('rev-parse')) return 'abc123'
    if (label === 'exec' && prompt.includes('git rev-parse')) return 'cwd000'
    if (/^(architecture|code|security|test|premortem)-reviewer:r/.test(label)) {
      reviewerSchema = opts && opts.schema
      reviewerCalls += 1
      reviewerPrompts.push(prompt)
      const receipt = receiptFor(prompt)
      if (label === 'architecture-reviewer:r1' && staleReceiptCalls === 0) {
        staleReceiptCalls += 1
        return {
          findings: [],
          confidence: 'high',
          verificationReceipt: Object.assign({}, receipt, { artifact: 'stale-round-artifact' }),
        }
      }
      return {
        findings: reviewerCalls === 1 ? [{ id: 'X', file: 'a.js', title: 'bug', severity: 'Important' }] : [],
        confidence: 'high',
        verificationReceipt: receipt,
      }
    }
    if (label.startsWith('fix-code')) return { fixed: ['X'], deferred: [], changedSubjects: ['Code'], coverageDecisions: [] }
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label === 'stamp review coverage') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (label.startsWith('synthesis:')) return { verdicts: [] }
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }

  // fresh runDir per run: the default derived dir persists round-records.json across runs (stale-state trap)
  const out = await sr.reviewCodePhase('wi', { runDir: fs.mkdtempSync(path.join(os.tmpdir(), 'rc-budget-')) })
  assert.strictEqual(out.gate, 'passed')
  assert.ok(labels.includes('resolve review target'))
  assert.ok(labels.includes('run verify'))
  assert.ok(labels.some((l) => /^(architecture|code|security|test|premortem)-reviewer:r1$/.test(l)))
  assert.ok(labels.includes('stamp review coverage'))
  assert.ok(labels.filter((l) => l === 'run verify').length >= 1)
  assert.strictEqual(staleReceiptCalls, 1, 'a stale native reviewer receipt should be observed once')
  assert.ok(labels.filter((l) => l === 'architecture-reviewer:r1').length >= 2,
    'a stale native reviewer receipt must trigger one fresh retry')
  assert.ok(reviewerPrompts.some((p) => p.includes('Read review diff artifacts in bounded chunks') &&
    p.includes('<=800 lines') && p.includes('Never read the entire diff')),
    'native showrunner review-code reviewer prompts must require bounded diff reads')
  const schemaText = JSON.stringify(reviewerSchema || {})
  for (const comb of ['allOf', 'oneOf', 'anyOf']) {
    assert.ok(!Object.prototype.hasOwnProperty.call(reviewerSchema || {}, comb),
      `reviewer StructuredOutput schema must not use top-level ${comb} (Anthropic input_schema rejects it)`)
  }
  assert.ok(schemaText.includes('verificationReceipt'),
    'reviewer StructuredOutput keeps verificationReceipt as an optional property; decider downgrades missing receipts')
  console.log('ok: review-code leaf budget folds')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
