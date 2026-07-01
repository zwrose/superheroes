// plugins/superheroes/lib/tests/showrunner_draftpr_smoke.js
// Task 8: draft-PR is one folded courier leaf with read-back confirmation.
const assert = require('assert')

const labels = []
global.log = () => {}
global.agent = async (_prompt, opts) => {
  labels.push(opts && opts.label)
  if ((opts && opts.label) === 'open draft PR') {
    return [{ ok: true, stdout: JSON.stringify({
      ok: true,
      pr: { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' },
      read_back: true,
    }) }]
  }
  throw new Error(`unexpected label ${(opts && opts.label) || 'none'}`)
}

delete require.cache[require.resolve('../showrunner.js')]
const sr = require('../showrunner.js')

;(async () => {
  const out = await sr.draftPRPhase('my-work-item')
  assert.strictEqual(out.phaseResult.confidence, 'high')
  assert.deepStrictEqual(out.sideEffect, { pr: { number: 8, url: 'https://github.com/x/y/pull/8', state: 'open' } })
  assert.deepStrictEqual(labels, ['open draft PR'])
  console.log('ok: draft PR folded read-back leaf')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
