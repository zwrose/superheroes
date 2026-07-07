require('./_smoke_checkout_root.js')
const assert = require('assert')
// pid-unique runDir + reason-bearing terminal assertions (see _final_review_probe.js;
// must load before build_phase.js binds reviewPanel).
const { uniqueWorkItem, resetRunDir, assertTerminal } = require('./_final_review_probe.js')
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
    if (label.startsWith('branch-reviewer:')) {
      reviewerCalls += 1
      return { findings: reviewerCalls === 1 ? [{ id: 'F-1', title: 'bug', file: 'a.js', line: 1, severity: 'Important', evidence: 'e' }] : [] }
    }
    if (label === 'exec' && prompt.includes('fence_cli.py')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label === 'stamp build coverage') return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, clean: true }) }]
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }

  const WI = uniqueWorkItem()
  resetRunDir(WI)

  const fr = await bp.runFinalReview(WI, 5, 'superheroes/wi', '/tmp/wt')
  assertTerminal(fr, 'clean', 'coverage-folds final review certifies clean')
  const stamp = await bp.recordFinalReviewClean(WI)
  assert.strictEqual(stamp.ok, true)
  assert.strictEqual(stamp.read_back, true)
  assert.ok(labels.includes('read verify + minors'))
  assert.ok(labels.some((label) => label.startsWith('branch-reviewer:')))
  assert.ok(labels.includes('stamp build coverage'))
  console.log('ok: build final review coverage folds')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
