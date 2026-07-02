const assert = require('assert')
const sr = require('../showrunner.js')

const labels = []
global.log = () => {}
global.agent = async (_prompt, opts) => {
  labels.push(opts.label)
  if (opts.label === 'read world-snapshot') return [{ ok: true, stdout: JSON.stringify({ ok: true, snapshot: {} }) }]
  if (opts.label === 'read startup state') {
    return [{ ok: true, stdout: JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '' }) }]
  }
  return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
}

;(async () => {
  const facts = await sr.readStartupState('wi')
  assert.strictEqual(facts.spec_gate, 'passed')
  assert.deepStrictEqual(facts.model_overrides, {})
  assert.deepStrictEqual(labels.filter((x) => x === 'read startup state'), ['read startup state'])
  console.log('ok: startup folded reads')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
