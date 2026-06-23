// plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js
const assert = require('assert')
global.agent = async (prompt) => {
  if (prompt.includes('recover')) return { action: 'continue', from_step: 0 }
  if (prompt.includes('read-gate')) return { review: 'pending' }   // spec NOT approved
  if (prompt.includes('phase_step_cli.py')) return { action: 'park_pending', reason: 'gate not passed (pending / not yet approved)' }
  throw new Error('unexpected agent: ' + prompt.slice(0, 40))
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
