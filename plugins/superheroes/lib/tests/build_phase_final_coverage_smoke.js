const assert = require('assert')
const bp = require('../build_phase.js')

global.log = () => {}
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }

;(async () => {
  const labels = []
  let reviewerCalls = 0
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'read verify + minors') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, verify_command: 'none', minors: [] }) }]
    }
    if (label === 'branch-reviewer:r1') {
      reviewerCalls += 1
      return { findings: reviewerCalls === 1 ? [{ id: 'F-1', title: 'bug', file: 'a.js', severity: 'Important' }] : [] }
    }
    if (label === 'fix-branch') return { fixed: ['F-1'] }
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label === 'stamp build coverage') return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, clean: true }) }]
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }

  const fr = await bp.runFinalReview('wi', 5, 'superheroes/wi', '/tmp/wt')
  assert.strictEqual(fr.terminal, 'clean')
  const stamp = await bp.recordFinalReviewClean('wi')
  assert.strictEqual(stamp.ok, true)
  assert.strictEqual(stamp.read_back, true)
  assert.ok(labels.includes('read verify + minors'))
  assert.ok(labels.includes('branch-reviewer:r1'))
  assert.ok(labels.includes('stamp build coverage'))
  console.log('ok: build final review coverage folds')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
