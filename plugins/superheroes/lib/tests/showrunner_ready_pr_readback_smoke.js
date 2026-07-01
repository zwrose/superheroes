const assert = require('assert')

const labels = []
global.log = () => {}
global.agent = async (_prompt, opts) => {
  labels.push(opts && opts.label)
  if ((opts && opts.label) === 'mark PR ready') {
    return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: false, reason: 'read-back mismatch' }) }]
  }
  throw new Error(`unexpected label ${(opts && opts.label) || 'none'}`)
}

delete require.cache[require.resolve('../showrunner.js')]
const sr = require('../showrunner.js')

;(async () => {
  const out = await sr.markReadyPhase('my-work-item')
  assert.strictEqual(out.phaseResult.confidence, 'low')
  assert.strictEqual(out.sideEffect, null)
  assert.deepStrictEqual(labels, ['mark PR ready'])
  console.log('ok: ready PR read-back gate')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
