// plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js
// #115 Task 12: reconcile() uses exec (not cmdRunner), readGate uses exec (not cmdRunner), and
// phaseStep is the JS twin (not phase_step_cli.py). The agent stub provides exec stdout JSON.
const assert = require('assert')
// exec (label='exec') returns array of {ok, stdout}; parse stdout as JSON for each call.
const SNAPSHOT = JSON.stringify({ checkpoint: null, world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }, generation: null })
const GATE_RESULT = JSON.stringify({ review: 'pending' })
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'exec') {
    // exec batches multiple commands in one call; parse which ones are in the prompt.
    if (prompt.includes('recover_entry')) return [{ index: 0, ok: true, stdout: SNAPSHOT }]
    if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: GATE_RESULT }]
  }
  throw new Error('unexpected agent: ' + label + ' ' + prompt.slice(0, 40))
}
global.log = () => {}
const { showrunner } = require('../showrunner.js')
;(async () => {
  const out = await showrunner({ workItem: 'wi' })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.phase, 'startup')
  // The spec gate is 'pending' -> phaseStep twin returns park_pending with reason containing 'pending'
  assert.ok(/pending/.test(out.reason))
  console.log('OK: UFR-1 — unapproved (pending) spec refuses to run')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
