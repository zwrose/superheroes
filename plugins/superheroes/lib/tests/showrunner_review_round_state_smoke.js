const assert = require('assert')
const fs = require('fs')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

function clean(wi) {
  try { fs.rmSync(`/tmp/showrunner-${wi}-review-plan`, { recursive: true, force: true }) } catch (_) {}
}

;(async () => {
  // pid-unique work item: reviewDocPhase derives its runDir as the machine-global
  // /tmp/showrunner-<wi>-review-plan, so a fixed name collides with a concurrent pytest
  // suite on the same machine (see _final_review_probe.js for the flake story). The
  // pid-named runDir is reaped on a PASSING exit; a failing run keeps it as evidence.
  const WI = `wi-round-state-pid${process.pid}`
  process.on('exit', (code) => { if (code === 0) clean(WI) })
  clean(WI)
  const runDir = `/tmp/showrunner-${WI}-review-plan`
  fs.mkdirSync(runDir, { recursive: true })
  fs.writeFileSync(`${runDir}/deferred-set.json`, JSON.stringify({ 'A-1': 'Critical' }))
  const labels = []
  let reviewRound = 0
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'exec') {
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
      if (prompt.includes('set-gate')) {
        return [
          { index: 0, ok: true, stdout: JSON.stringify({ review: 'passed', status: 'reviewed' }) },
          { index: 1, ok: true, stdout: JSON.stringify({ ok: true }) },
          { index: 2, ok: true, stdout: JSON.stringify({ ok: true }) },
        ]
      }
      if (prompt.includes('record-deferred')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (label === 'save round state') return [{ ok: true, stdout: JSON.stringify({ ok: false }) }]
    if (label === 'revise-doc') return { fixes: [], deferred: [{ identity: 'A-1', severity: 'Critical' }] }
    if (label.startsWith('synthesis:')) return { verdicts: [] }
    if (label.endsWith('-reviewer')) {
      reviewRound += 1
      if (reviewRound === 1) {
        return { findings: [{ file: 'a.md', line: 1, title: 'missing section', severity: 'Critical', evidence: 'e' }] }
      }
      return { findings: [] }
    }
    return { ok: true }
  }

  const out = await sr.reviewDocPhase('plan', WI)
  const runtimeDeferredIds = out.runtimeDeferredIds || []
  assert.ok(labels.includes('save round state'))
  assert.strictEqual(labels.filter((label) => label === 'save round state').length, 1)
  assert.deepStrictEqual(runtimeDeferredIds, ['A-1'])
  console.log('ok: review round state kept in memory with best-effort save')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
