const assert = require('assert')
const fs = require('fs')
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

  const runDir = '/tmp/workhorse-wi-final-review'
  fs.rmSync(runDir, { recursive: true, force: true })
  fs.mkdirSync(runDir, { recursive: true })

  const fr = await bp.runFinalReview('wi', 5, 'superheroes/wi', '/tmp/wt')
  assert.strictEqual(fr.terminal, 'clean')
  const stamp = await bp.recordFinalReviewClean('wi')
  assert.strictEqual(stamp.ok, true)
  assert.strictEqual(stamp.read_back, true)
  assert.ok(labels.includes('read verify + minors'))
  assert.ok(labels.some((label) => label.startsWith('branch-reviewer:')))
  assert.ok(labels.includes('stamp build coverage'))
  console.log('ok: build final review coverage folds')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
