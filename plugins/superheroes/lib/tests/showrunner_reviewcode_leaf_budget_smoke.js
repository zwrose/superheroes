const assert = require('assert')
const sr = require('../showrunner.js')

global.log = () => {}
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }

;(async () => {
  const labels = []
  let reviewerCalls = 0
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/tmp/wt', expectedHead: 'abc123' }) }]
    }
    if (label === 'lib' && prompt.includes('rev-parse')) return 'abc123'
    if (label === 'lib' && prompt.includes('review_code_config.py')) return { verifyCommand: 'none', tiers: {} }
    if (label === 'branch-reviewer:r1') {
      reviewerCalls += 1
      return { findings: reviewerCalls === 1 ? [{ id: 'X', file: 'a.js', title: 'bug', severity: 'Important' }] : [] }
    }
    if (label === 'fix-code') return { fixed: ['X'] }
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label === 'stamp review coverage') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (label.startsWith('synthesis:')) return { verdicts: [] }
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }

  const out = await sr.reviewCodePhase('wi')
  assert.strictEqual(out.gate, 'passed')
  assert.ok(labels.includes('resolve review target'))
  assert.ok(labels.includes('run verify'))
  assert.ok(labels.includes('branch-reviewer:r1'))
  assert.ok(labels.includes('stamp review coverage'))
  assert.ok(labels.filter((l) => l === 'run verify').length >= 1)
  console.log('ok: review-code leaf budget folds')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
