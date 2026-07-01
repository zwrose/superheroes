const assert = require('assert')
const showrunner = require('../showrunner.js')

;(async () => {
  const labels = []
  global.log = () => {}
  global.agent = async (_prompt, opts) => {
    labels.push(opts.label)
    return [{ ok: true, stdout: JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true }) }]
  }

  let result = await showrunner.persistPhase('wi', {
    step: 2,
    phase: 'build',
    record: { phase: 'build', confidence: 'high' },
  })
  assert.deepStrictEqual(labels, ['save phase progress'])
  assert.strictEqual(result.ok, true)

  labels.length = 0
  global.agent = async (_prompt, opts) => {
    labels.push(opts.label)
    return [{ ok: true, stdout: JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: false }) }]
  }
  result = await showrunner.persistPhase('wi', {
    step: 2,
    phase: 'build',
    record: { phase: 'build', confidence: 'high' },
  })
  assert.deepStrictEqual(labels, ['save phase progress'])
  assert.strictEqual(result.ok, false)

  console.log('ok: showrunner phase progress one-leaf budget')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
