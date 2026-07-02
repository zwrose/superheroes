// plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js
// #115 Task 12: reconcile() uses exec; readStartupState uses the folded startup courier leaf.
const assert = require('assert')

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

const SNAPSHOT = JSON.stringify({ checkpoint: null, world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }, generation: null })

global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'exec') {
    if (prompt.includes('recover_entry')) return [{ index: 0, ok: true, stdout: SNAPSHOT }]
    if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: '{"review":"pending"}' }]
  }
  if (label === 'read startup state') {
    return jsonOut({ ok: true, spec_gate: 'pending', model_overrides: {} })
  }
  throw new Error('unexpected agent: ' + label + ' ' + prompt.slice(0, 40))
}
global.log = () => {}
const { showrunner } = require('../showrunner.js')
;(async () => {
  const out = await showrunner({ workItem: 'wi' })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.phase, 'startup')
  assert.ok(/pending/.test(out.reason))
  console.log('OK: UFR-1 — unapproved (pending) spec refuses to run')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
